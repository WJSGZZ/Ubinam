#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""地名、小区名、楼盘名、店名 → 坐标候选（官方接口）。

以图搜图常给出"图中可能是 XX花园""XX大厦"，网页里读到一个小区名、酒店名，都要先落到坐标才能核对。
同名的地方全国常有几十个，脚本把各地的同名点都列出来，由画面里的其他线索去挑。

来源（默认用所有已配密钥的来源 + osm）：
  amap   高德 Web 服务地点搜索 v5（AMAP_KEY，直连）：小区、楼盘、店铺、单位覆盖好；GCJ-02 已转 WGS84
  baidu  百度地图开放平台地点检索 v2（BAIDU_MAP_AK，直连）：同上；不给城市时还列出全国各城市的同名结果数
  osm    OpenStreetMap Nominatim（免密钥，遵守每秒 1 次的使用政策；国内可能要代理）：有名字的小区、公园、道路

示例：
  poi.py "<小区名>" --city <城市>                 # 城市里所有同名点，出 {名字: [lat, lon]}
  poi.py "<区县> <路名> 学校" --city <直辖市或地级市>   # --city 只认地级市，区县写进关键词
  poi.py "<门牌地址或地名>" --sources osm --country mx --proxy socks5h://127.0.0.1:10808（示例）   # 国外
  poi.py "<小区名>"                                # 不给城市：列出全国哪些城市有同名点
  poi.py "<酒店名>" --city <城市> --out pois.json && tiles.py sheet --points pois.json --zoom 18 --out pois_sheet.jpg

高德、百度的密钥都在各自开放平台免费申请（个人开发者有日配额）。
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

UA = "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/126.0 Safari/537.36"


def _curl(url: str, proxy: str | None = None, ua: str = UA, timeout: int = 25) -> str:
    cmd = ["curl", "-sS", "-m", str(timeout), "-A", ua, url]
    cmd[1:1] = ["-x", proxy] if proxy else ["--noproxy", "*"]
    # 网页是 UTF-8。不写 encoding 的话中文 Windows 按 GBK 解码，解不开时 stdout 是 None
    r = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        print(f"请求没成功（curl 退出码 {r.returncode}）：{r.stderr.strip()[:200]}", file=sys.stderr)
    return r.stdout


def search_amap(kw: str, city: str | None, n: int) -> list[dict]:
    key = os.environ.get("AMAP_KEY")
    if not key:
        return []
    q = {"key": key, "keywords": kw, "page_size": min(n, 25)}
    if city:
        q.update(region=city, city_limit="true")
    try:
        d = json.loads(_curl("https://restapi.amap.com/v5/place/text?" + urllib.parse.urlencode(q)))
    except json.JSONDecodeError:
        return []
    if d.get("status") != "1":
        print(f"高德：{d.get('info')}（{d.get('infocode')}）", file=sys.stderr)
        return []
    rows = []
    for p in d.get("pois") or []:
        if not p.get("location"):
            continue
        lon, lat = map(float, p["location"].split(","))
        lat, lon = geo.gcj2wgs(lat, lon)
        rows.append({"src": "amap", "name": p.get("name", ""), "city": p.get("cityname", ""), "area": p.get("adname", ""),
                     "address": p.get("address", "") if isinstance(p.get("address"), str) else "",
                     "type": p.get("type", ""), "wgs": [round(lat, 6), round(lon, 6)]})
    return rows


def search_baidu(kw: str, city: str | None, n: int) -> tuple[list[dict], list[dict]]:
    ak = os.environ.get("BAIDU_MAP_AK")
    if not ak:
        return [], []
    q = {"query": kw, "region": city or "全国", "output": "json", "ak": ak, "page_size": min(n, 20),
         "ret_coordtype": "gcj02ll", "scope": 2}
    if city:
        q["city_limit"] = "true"
    try:
        import providers
        d = json.loads(_curl(providers.baidu_url("https://api.map.baidu.com/place/v2/search", q)))
    except json.JSONDecodeError:
        return [], []
    if d.get("status") != 0:
        print(f"百度地点检索：{d.get('message')}（{d.get('status')}）", file=sys.stderr)
        return [], []
    rows, cities = [], []
    for p in d.get("results") or []:
        loc = p.get("location")
        if loc:
            lat, lon = geo.gcj2wgs(float(loc["lat"]), float(loc["lng"]))
            rows.append({"src": "baidu", "name": p.get("name", ""), "city": p.get("city", ""), "area": p.get("area", ""),
                         "address": p.get("address", ""), "type": (p.get("detail_info") or {}).get("tag", ""),
                         "wgs": [round(lat, 6), round(lon, 6)]})
        elif p.get("num"):  # 全国范围检索时返回的是各城市的结果数
            cities.append({"city": p.get("name"), "count": p.get("num")})
    return rows, cities


def search_osm(kw: str, city: str | None, n: int, proxy: str | None, country: str) -> list[dict]:
    q = {"q": f"{kw} {city}" if city else kw, "format": "jsonv2", "limit": n, "accept-language": "zh-CN"}
    if country:
        q["countrycodes"] = country
    raw = _curl("https://nominatim.openstreetmap.org/search?" + urllib.parse.urlencode(q), proxy=proxy,
                ua="ubinam/0.1 (photo geolocation research; https://github.com/WJSGZZ/Ubinam)")
    try:
        d = json.loads(raw)
    except json.JSONDecodeError:
        print(f"Nominatim 没返回 JSON（国内要走代理）：{raw[:120]}", file=sys.stderr)
        return []
    return [{"src": "osm", "name": p.get("name") or p.get("display_name", "").split(",")[0],
             "city": "", "area": "", "address": p.get("display_name", ""), "type": f"{p.get('category')}/{p.get('type')}",
             "wgs": [round(float(p["lat"]), 6), round(float(p["lon"]), 6)]} for p in d]


def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("keyword", help="地名、小区名、楼盘名、店名")
    ap.add_argument("--city", help="城市名，如 某某市 或 某某（不给就全国查）")
    ap.add_argument("--sources", help="amap,baidu,osm 任选，逗号分隔；默认用所有已配密钥的来源 + osm")
    ap.add_argument("--limit", type=int, default=10, help="每个来源最多几条")
    ap.add_argument("--country", default="cn", help="Nominatim 的国家代码，国外地名改成对应代码或留空")
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"), help="Nominatim 用；高德、百度始终直连")
    ap.add_argument("--out", type=Path, help="写出 {名字: [lat, lon]}（WGS84），给 tiles.py mark / sheet")
    args = ap.parse_args(_neg_coords(sys.argv[1:]))

    if args.sources:
        src = set(args.sources.split(","))
    else:
        src = {"osm"} | ({"amap"} if os.environ.get("AMAP_KEY") else set()) | ({"baidu"} if os.environ.get("BAIDU_MAP_AK") else set())
        if src == {"osm"} and args.country == "cn":
            print("提示：未配 AMAP_KEY / BAIDU_MAP_AK，只查 OSM；国内小区、店铺覆盖会差很多", file=sys.stderr)
    rows: list[dict] = []
    if "amap" in src:
        rows += search_amap(args.keyword, args.city, args.limit)
    if "baidu" in src:
        b_rows, cities = search_baidu(args.keyword, args.city, args.limit)
        rows += b_rows
        if cities:
            print("百度：全国有同名结果的城市（结果数）")
            print("  " + "、".join(f"{c['city']}({c['count']})" for c in cities[:30]))
    if "osm" in src:
        rows += search_osm(args.keyword, args.city, args.limit, args.proxy, args.country)

    # 同一个地方两个来源都有时去重（相距 150 m 内且名字互相包含）
    uniq: list[dict] = []
    for r in rows:
        if any(geo.distance(r["wgs"], u["wgs"]) < 150 and (r["name"] in u["name"] or u["name"] in r["name"]) for u in uniq):
            continue
        uniq.append(r)
    print(f"\n{len(uniq)} 个带坐标的候选（WGS84）：")
    pts = {}
    for i, r in enumerate(uniq, 1):
        label = f"{i:02d} {r['name']} {r['area']}".strip()
        pts[label] = r["wgs"]
        print(f"  {label}  {r['wgs'][0]},{r['wgs'][1]}  [{r['src']}] {r['type']}  {r['address'][:60]}")
    if not uniq:
        print("  没有。换写法（去掉\"小区/花园\"后缀、加区县名），或用 revimg.py --query 搜网页找地址")
    if args.out:
        args.out.write_text(json.dumps(pts, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {args.out}")
    if len(uniq) >= 2:
        # 同一所学校的几个校区、连锁店的几家分店都会列在这里，第一条不一定是对的那处
        print(f"\n{len(uniq)} 处都要当候选，不要只取第一条："
              + (f"`board.py add --from {args.out} --level area --parent <上级>` 全部进候选盘" if args.out
                 else "加 --out pois.json，再 `board.py add --from pois.json --level area` 全部进候选盘"))


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
