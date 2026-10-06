#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow", "numpy"]
# ///
"""Mapillary 众包街景（官方 Graph API v4，图像 CC BY-SA 4.0）：找点、扫一片、按朝向出图、拼对比图。

批量比对的主力：许可允许下载、缓存和做计算机视觉分析，只需署名（出证据图时写 “© Mapillary contributors, CC BY-SA 4.0”）。
需要环境变量 MAPILLARY_TOKEN（mapillary.com/dashboard/developers 注册应用后取 Client Token）。
覆盖：欧美、日本、东南亚城市较好；中国大陆很少，国内用 baidu_pano.py。
普通照片只朝一个方向（compass_angle），只能挑方向接近的；360 全景可按任意朝向重投影成透视图。

示例：
  mapillary.py near 48.8584,2.2945 --radius 60
  mapillary.py scan 48.8584,2.2945 --radius 300 --out imgs.json
  mapillary.py sheet --panos imgs.json --toward 48.8606,2.3376 --out s.jpg         # 每个点朝向同一目标（普通照片按方向筛）
  mapillary.py sheet --at 48.8584,2.2945 --headings 0,90,180,270 --out around.jpg  # 只有全景能环视
  mapillary.py render 123456789 --heading 90 --out v.jpg
"""
from __future__ import annotations

import argparse
import json
import math
import os
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402
import providers  # noqa: E402
from baidu_pano import _font  # noqa: E402

API = "https://graph.mapillary.com"
FIELDS = "id,geometry,captured_at,compass_angle,computed_compass_angle,is_pano,thumb_1024_url,thumb_2048_url"
CACHE = Path(".geo-cache/mapillary")
ATTRIB = "© Mapillary contributors, CC BY-SA 4.0"


def _token() -> str:
    t = os.environ.get("MAPILLARY_TOKEN")
    if not t:
        sys.exit("mapillary.py 需要环境变量 MAPILLARY_TOKEN（mapillary.com/dashboard/developers 的 Client Token）。")
    return t


def _curl(url: str, proxy: str | None, out: Path | None = None, auth: bool = True) -> bytes:
    cmd = ["curl", "-s", "-m", "60", "-A", providers.UA]
    if auth:
        cmd += ["-H", f"Authorization: OAuth {_token()}"]
    if proxy:
        cmd += ["-x", proxy]
    if out:
        cmd += ["-o", str(out)]
    return subprocess.run(cmd + [url], capture_output=True).stdout


def _item(d: dict) -> dict:
    lon, lat = d["geometry"]["coordinates"]
    ang = d.get("computed_compass_angle", d.get("compass_angle"))
    ts = d.get("captured_at")
    date = None
    if ts:
        import datetime as _dt
        date = _dt.datetime.fromtimestamp(ts / 1000, _dt.timezone.utc).strftime("%Y-%m-%d")
    return {"id": str(d["id"]), "wgs": [lat, lon], "date": date, "angle": ang, "is_pano": bool(d.get("is_pano")),
            "thumb": d.get("thumb_2048_url") if d.get("is_pano") else d.get("thumb_1024_url")}


def query_bbox(s: float, w: float, n: float, e: float, proxy: str | None, limit: int = 2000) -> list[dict]:
    q = urllib.parse.urlencode({"fields": FIELDS, "bbox": f"{w},{s},{e},{n}", "limit": limit})
    try:
        d = json.loads(_curl(f"{API}/images?{q}", proxy) or b"{}")
    except json.JSONDecodeError:
        return []
    if "error" in d:
        sys.exit(f"Mapillary：{d['error'].get('message')}")
    return [_item(x) for x in d.get("data", []) if x.get("geometry")]


def scan(lat: float, lon: float, radius_m: float, proxy: str | None) -> dict:
    """半径内的全部图像（大范围按 0.005° 分块查，接口对单次 bbox 面积有限制）。"""
    s, w = geo.dest(geo.dest((lat, lon), 180, radius_m), 270, radius_m)
    n, e = geo.dest(geo.dest((lat, lon), 0, radius_m), 90, radius_m)
    step = 0.005
    found: dict = {}
    la = s
    while la < n:
        lo = w
        while lo < e:
            for it in query_bbox(la, lo, min(la + step, n), min(lo + step, e), proxy):
                if geo.distance((lat, lon), tuple(it["wgs"])) <= radius_m:
                    found[it["id"]] = it
            lo += step
        la += step
    return found


def get(image_id: str, proxy: str | None) -> dict:
    d = json.loads(_curl(f"{API}/{image_id}?fields={FIELDS}", proxy) or b"{}")
    if "error" in d or "geometry" not in d:
        sys.exit(f"Mapillary 图像 {image_id}：{d.get('error', {}).get('message', '未找到')}")
    return _item(d)


def _raw(it: dict, proxy: str | None) -> Image.Image:
    CACHE.mkdir(parents=True, exist_ok=True)
    p = CACHE / f"{it['id']}{'_pano' if it['is_pano'] else ''}.jpg"
    if not (p.exists() and p.stat().st_size > 2000):
        if not it.get("thumb"):
            it = get(it["id"], proxy)
        _curl(it["thumb"], proxy, p, auth=False)
    return Image.open(p).convert("RGB")


def _equirect_to_persp(img: Image.Image, yaw: float, pitch: float, fov: float, w: int, h: int) -> Image.Image:
    """等距柱状全景 → 透视图。yaw 相对全景中心（度，右正），pitch 正=抬头，fov 水平视角。"""
    src = np.asarray(img)
    H, W = src.shape[:2]
    f = (w / 2) / math.tan(math.radians(fov) / 2)
    xs, ys = np.meshgrid(np.arange(w) - w / 2, np.arange(h) - h / 2)
    x, y, z = xs, -ys, np.full_like(xs, f, dtype=float)
    cp, sp = math.cos(math.radians(pitch)), math.sin(math.radians(pitch))
    y, z = y * cp + z * sp, -y * sp + z * cp
    cy, sy = math.cos(math.radians(yaw)), math.sin(math.radians(yaw))
    x, z = x * cy + z * sy, -x * sy + z * cy
    lon = np.arctan2(x, z)
    lat = np.arctan2(y, np.hypot(x, z))
    u = ((lon / (2 * math.pi) + 0.5) * W).astype(int) % W
    v = np.clip(((0.5 - lat / math.pi) * H).astype(int), 0, H - 1)
    return Image.fromarray(src[v, u])


def render(image_id: str | dict, heading: float, pitch: float = 0, fov: float = 90, w: int = 640, h: int = 480,
           proxy: str | None = None, cache: Path | None = None) -> Image.Image:
    it = image_id if isinstance(image_id, dict) else get(image_id, proxy)
    raw = _raw(it, proxy)
    if it["is_pano"] and it.get("angle") is not None:
        return _equirect_to_persp(raw, (heading - it["angle"] + 540) % 360 - 180, pitch, fov, w, h)
    return raw.resize((w, h))


def usable(it: dict, heading: float, tol: float) -> bool:
    """普通照片只朝一个方向：方向差在 tol 内才可用；全景总是可用。"""
    if it["is_pano"] or it.get("angle") is None:
        return it["is_pano"]
    return abs((it["angle"] - heading + 540) % 360 - 180) <= tol


def sheet(items: list[dict], out: Path, proxy: str | None, cols: int = 3, tw: int = 480, th: int = 360) -> None:
    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(lambda it: render(it["meta"], it["heading"], it.get("pitch", 0), it.get("fov", 90),
                                            640, 480, proxy), items))
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, max(1, rows) * th + 20), "black")
    d = ImageDraw.Draw(S)
    f = _font(16)
    for i, (it, im) in enumerate(zip(items, ims)):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im.resize((tw, th)), (x, y))
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        d.text((x + 4, y + 2), it["label"], fill="yellow", font=f)
    d.text((4, S.height - 18), ATTRIB, fill="white", font=_font(12))
    S.save(out, quality=88)


def _neg_coords(argv: list[str]) -> list[str]:
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    sub = ap.add_subparsers(dest="cmd", required=True)
    n = sub.add_parser("near")
    n.add_argument("latlon")
    n.add_argument("--radius", type=float, default=60)
    sc = sub.add_parser("scan")
    sc.add_argument("center")
    sc.add_argument("--radius", type=float, default=250)
    sc.add_argument("--out", type=Path, required=True)
    r = sub.add_parser("render")
    r.add_argument("id")
    r.add_argument("--heading", type=float, default=None, help="全景必填；普通照片忽略")
    r.add_argument("--pitch", type=float, default=0)
    r.add_argument("--fov", type=float, default=90)
    r.add_argument("--out", type=Path, required=True)
    s = sub.add_parser("sheet")
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids")
    g.add_argument("--at", help="lat,lon：附近 --radius 内的图像")
    g.add_argument("--panos", type=Path, help="scan 输出")
    h = s.add_mutually_exclusive_group(required=True)
    h.add_argument("--heading", type=float)
    h.add_argument("--headings")
    h.add_argument("--toward")
    s.add_argument("--offset", type=float, default=0)
    s.add_argument("--tol", type=float, default=45, help="普通照片方向容差（度）")
    s.add_argument("--radius", type=float, default=60)
    s.add_argument("--pitch", type=float, default=0)
    s.add_argument("--fov", type=float, default=90)
    s.add_argument("--spread", type=float, help="抽稀：相邻两点至少相隔多少米")
    s.add_argument("--panos-only", action="store_true")
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--out", type=Path, required=True)
    a = ap.parse_args(_neg_coords(sys.argv[1:]))

    if a.cmd == "near":
        lat, lon = map(float, a.latlon.split(","))
        res = sorted(scan(lat, lon, a.radius, a.proxy).values(), key=lambda it: geo.distance((lat, lon), tuple(it["wgs"])))
        print(json.dumps([{k: v for k, v in it.items() if k != "thumb"} for it in res[:20]], ensure_ascii=False, indent=1)
              if res else "附近没有 Mapillary 图像（加大 --radius，或这里没覆盖）")
    elif a.cmd == "scan":
        lat, lon = map(float, a.center.split(","))
        res = scan(lat, lon, a.radius, a.proxy)
        a.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        np_ = sum(1 for v in res.values() if v["is_pano"])
        print(f"{len(res)} 张（全景 {np_}）-> {a.out}")
    elif a.cmd == "render":
        it = get(a.id, a.proxy)
        if it["is_pano"] and a.heading is None:
            sys.exit("全景需要 --heading")
        render(it, a.heading or 0, a.pitch, a.fov, proxy=a.proxy).save(a.out)
        print(a.out)
    else:
        if a.ids:
            imgs = {i: get(i, a.proxy) for i in a.ids.split(",")}
        elif a.at:
            lat, lon = map(float, a.at.split(","))
            imgs = scan(lat, lon, a.radius, a.proxy)
        else:
            imgs = json.loads(a.panos.read_text(encoding="utf-8"))
        if a.panos_only:
            imgs = {k: v for k, v in imgs.items() if v["is_pano"]}
        if a.spread:
            kept: dict = {}
            for k, v in imgs.items():
                if all(geo.distance(tuple(v["wgs"]), tuple(u["wgs"])) >= a.spread for u in kept.values()):
                    kept[k] = v
            imgs = kept
        target = tuple(map(float, a.toward.split(","))) if a.toward else None
        items = []
        for iid, it in imgs.items():
            heads = ([float(x) for x in a.headings.split(",")] if a.headings
                     else [geo.bearing(tuple(it["wgs"]), target) + a.offset] if target else [a.heading])
            for hd in heads:
                hd %= 360
                if not usable(it, hd, a.tol):
                    continue
                label = f"{len(items)}: {it['date'] or ''} {'360' if it['is_pano'] else 'img'} h{hd:.0f}"
                items.append({"id": iid, "heading": hd, "pitch": a.pitch, "fov": a.fov, "wgs": it["wgs"],
                              "date": it["date"], "label": label, "meta": it, "engine": "mapillary"})
        if not items:
            sys.exit("没有方向合适的图像：放宽 --tol、加大范围，或只用全景")
        pages = [items[k:k + a.limit] for k in range(0, len(items), a.limit)]
        for pi, page in enumerate(pages):
            out = a.out if pi == 0 else a.out.with_name(f"{a.out.stem}_{pi + 1}{a.out.suffix}")
            sheet(page, out, a.proxy)
            print(out)
        a.out.with_suffix(".index.json").write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(items)} 格；index -> {a.out.with_suffix('.index.json')}；署名：{ATTRIB}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
