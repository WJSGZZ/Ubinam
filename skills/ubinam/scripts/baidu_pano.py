#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""百度全景（国内街景，官方「全景静态图」API）：按位置和朝向出图、扫一片、拼对比图。

需要环境变量 BAIDU_MAP_AK（百度地图开放平台申请，应用类型选「服务端」，开通全景静态图服务——高级权限需付费开通，未开通返回 240；应用设为 SN 校验时另配 BAIDU_MAP_SK）。国内直连，不走代理。
官方接口按坐标取最近的全景，不公开全景 id、路名和采集日期，所以：
  - 点的 id 写成 "loc:纬度,经度"（WGS84），渲染时按坐标取图；
  - scan / sample 只能在网格或随机点上取图，相邻点可能落到同一个全景，用 --spread 抽稀；
  - 没有 info（日期、路段、时间线）了；需要日期时看图里的水印或用别的来源。
不做持久缓存，单次进程最多出 150 张图；日配额以百度控制台为准。
坐标：输入输出一律 WGS84，请求时用 coordtype=wgs84ll，由百度换算。

示例：
  baidu_pano.py render loc:22.6047,114.0523 --heading 47 --out v.jpg
  baidu_pano.py scan 22.6050,114.0535 --radius 300 --step 60 --out panos.json
  baidu_pano.py sheet --panos panos.json --toward 22.6072,114.0564 --offset -12 --out s.jpg
  baidu_pano.py sheet --ids loc:22.6047,114.0523 --headings 0,60,120,180,240,300 --out around.jpg   # 单点环视
  baidu_pano.py sample --bbox 22.52,113.90,22.60,114.10 --n 24 --out cityA.jpg     # 候选城市街景抽样：比护栏、路灯、站台
"""
from __future__ import annotations

import argparse
import io
import json
import os
import re
import sys
import urllib.parse
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402

API = "https://api.map.baidu.com/panorama/v2"
MAX_RENDERS = 150
_renders = 0


def _get(url: str, timeout: int = 40) -> bytes:
    """curl 直连（国内服务不走代理）；用 curl 是为了不依赖 Python 自带的证书配置。"""
    r = subprocess.run(["curl", "-s", "--noproxy", "*", "-m", str(timeout), url], capture_output=True)
    return r.stdout


def _ak() -> str:
    k = os.environ.get("BAIDU_MAP_AK")
    if not k:
        sys.exit("baidu_pano.py 需要环境变量 BAIDU_MAP_AK（百度地图开放平台「全景静态图」服务）。")
    return k


def loc_id(lat: float, lon: float) -> str:
    return f"loc:{lat:.6f},{lon:.6f}"


def parse_id(pid: str) -> tuple[float, float]:
    if not pid.startswith("loc:"):
        sys.exit(f"{pid} 不是 loc:纬度,经度 形式；官方接口不支持旧版全景 id")
    la, lo = pid[4:].split(",")
    return float(la), float(lo)


def grid(lat: float, lon: float, radius_m: float, step_m: float) -> dict:
    """正方形网格上的取图点 {id: {wgs}}。"""
    n = int(radius_m // step_m)
    out: dict = {}
    for i in range(-n, n + 1):
        for j in range(-n, n + 1):
            p = geo.dest(geo.dest((lat, lon), 0, i * step_m), 90, j * step_m)
            out[loc_id(*p)] = {"id": loc_id(*p), "wgs": list(p)}
    return out


def thin(panos: dict, spread_m: float) -> dict:
    """按最小间距抽稀：相距不到 spread_m 的点只留第一个。"""
    kept: dict = {}
    for k, v in panos.items():
        if all(geo.distance(tuple(v["wgs"]), tuple(u["wgs"])) >= spread_m for u in kept.values()):
            kept[k] = v
    return kept


def sample(bbox: tuple[float, float, float, float], n: int, spread_m: float, seed: int) -> list[dict]:
    """范围内随机撒点、按间距抽稀取 n 个。官方接口没有行进方向，朝向由调用方给。"""
    import random
    rnd = random.Random(seed)
    s, w, nn, e = bbox
    found: dict = {}
    tries = 0
    while len(found) < n and tries < n * 20:
        tries += 1
        p = (rnd.uniform(s, nn), rnd.uniform(w, e))
        if all(geo.distance(p, tuple(u["wgs"])) >= spread_m for u in found.values()):
            found[loc_id(*p)] = {"id": loc_id(*p), "wgs": list(p)}
    return list(found.values())


def render(pid: str, heading: float, pitch: float = 10, fov: float = 90,
           w: int = 1024, h: int = 512, cache: Path | None = None) -> Image.Image:
    """按罗盘朝向出一张透视图。heading 0=北；pitch 0–90（正=抬头，官方不支持低头）；fov 水平视角 10–360。
    宽 ≤1024、高 ≤512。该处没有全景时返回灰图。"""
    global _renders
    _renders += 1
    if _renders > MAX_RENDERS:
        sys.exit(f"baidu_pano.py 单次最多出 {MAX_RENDERS} 张图；先用 --spread、--within 缩小范围")
    lat, lon = parse_id(pid)
    w, h = max(10, min(int(w), 1024)), max(10, min(int(h), 512))
    import providers
    url = providers.baidu_url(API, {"ak": _ak(), "width": w, "height": h, "location": f"{lon:.6f},{lat:.6f}",
                                "coordtype": "wgs84ll", "heading": f"{heading % 360:.0f}",
                                "pitch": f"{max(0, min(pitch, 90)):.0f}", "fov": f"{max(10, min(fov, 360)):.0f}"})
    data = b""
    try:
        data = _get(url)
        return Image.open(io.BytesIO(data)).convert("RGB")
    except Exception:  # noqa: BLE001  无全景或配额用尽时接口返回 JSON 错误，不是图片
        if data:
            print(f"百度全景 {pid}: {data[:160].decode('utf-8', 'replace')}", file=sys.stderr)
        return Image.new("RGB", (w, h), "gray")


def _font(size: int):
    for p in ("/System/Library/Fonts/STHeiti Medium.ttc", "/System/Library/Fonts/Hiragino Sans GB.ttc",
              "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc"):
        try:
            return ImageFont.truetype(p, size)
        except Exception:
            continue
    return ImageFont.load_default()


def sheet(items: list[dict], out: Path, cols: int = 3, tw: int = 480, th: int = 360,
          cache: Path | None = None) -> None:
    """items: [{id, heading, pitch?, fov?, label?}] → 带编号的拼图。"""
    def one(it):
        return render(it["id"], it["heading"], it.get("pitch", 10), it.get("fov", 90))

    with ThreadPoolExecutor(6) as ex:
        ims = list(ex.map(one, items))
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, max(1, rows) * th), "black")
    d = ImageDraw.Draw(S)
    f = _font(16)
    for i, (it, im) in enumerate(zip(items, ims)):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im.convert("RGB").resize((tw, th)), (x, y))
        text = it.get("label") or f"{i}: {it['id'][4:]} h{it['heading']:.0f}"
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        d.text((x + 4, y + 2), text, fill="yellow", font=f)
    S.save(out, quality=88)


def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def _pages(items: list[dict], limit: int, out: Path) -> None:
    pages = [items[k:k + limit] for k in range(0, len(items), limit)] or [[]]
    for pi, page in enumerate(pages):
        o = out if pi == 0 else out.with_name(f"{out.stem}_{pi + 1}{out.suffix}")
        sheet(page, o)
        print(o)
    idx = out.with_suffix(".index.json")
    idx.write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"index -> {idx}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--cache", type=Path, default=None, help="已停用：官方接口不缓存")
    sub = ap.add_subparsers(dest="cmd", required=True)

    s = sub.add_parser("scan", help="网格取图点（不联网，只生成点；出图在 sheet）")
    s.add_argument("center")
    s.add_argument("--radius", type=float, default=250)
    s.add_argument("--step", type=float, default=60)
    s.add_argument("--out", type=Path, required=True)

    r = sub.add_parser("render")
    r.add_argument("id", help="loc:纬度,经度")
    r.add_argument("--heading", type=float, required=True)
    r.add_argument("--pitch", type=float, default=10)
    r.add_argument("--fov", type=float, default=90)
    r.add_argument("--out", type=Path, required=True)

    sh = sub.add_parser("sheet")
    g = sh.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", help="逗号分隔会和坐标冲突，多个点用分号：loc:a,b;loc:c,d")
    g.add_argument("--panos", type=Path, help="scan 输出的 JSON")
    g.add_argument("--spec", type=Path, help="JSON 列表 [{id, heading, pitch, fov, label}]")
    sh.add_argument("--heading", type=float)
    sh.add_argument("--headings", help="每个点都出这几个朝向，如 0,60,120,180,240,300")
    sh.add_argument("--toward", help="lat,lon：每个点各自朝向这个目标")
    sh.add_argument("--offset", type=float, default=0)
    sh.add_argument("--pitch", type=float, default=10)
    sh.add_argument("--fov", type=float, default=90)
    sh.add_argument("--within", help="lat,lon,半径米：只取这个圆内的点")
    sh.add_argument("--spread", type=float, help="抽稀：相邻两点至少相隔多少米")
    sh.add_argument("--limit", type=int, default=12)
    sh.add_argument("--out", type=Path, required=True)

    sp = sub.add_parser("sample", help="候选城市/片区街景随机抽样拼图：比护栏、路灯、站台、路缘")
    sp.add_argument("--bbox", required=True, help="south,west,north,east（建成区范围，尽量贴着主干道）")
    sp.add_argument("--n", type=int, default=24)
    sp.add_argument("--spread", type=float, default=300)
    sp.add_argument("--seed", type=int, default=1)
    sp.add_argument("--headings", default="0,90,180,270", help="每点取哪些朝向；官方接口没有行进方向")
    sp.add_argument("--out", type=Path, required=True)

    for name in ("near", "info"):
        sub.add_parser(name, help="已停用：官方接口不提供全景 id 和元数据")

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd in ("near", "info"):
        sys.exit("官方全景静态图接口不提供全景 id、路名和日期；直接用 render loc:纬度,经度 取图。")
    if args.cmd == "scan":
        lat, lon = map(float, args.center.split(","))
        res = grid(lat, lon, args.radius, args.step)
        args.out.write_text(json.dumps(res, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"{len(res)} 个取图点 -> {args.out}（未联网；sheet 时才取图，注意 150 张上限）")
    elif args.cmd == "render":
        render(args.id, args.heading, args.pitch, args.fov).save(args.out)
        print(args.out)
    elif args.cmd == "sample":
        bb = tuple(map(float, args.bbox.split(",")))
        pts = sample(bb, args.n, args.spread, args.seed)
        heads = [float(x) for x in args.headings.split(",")]
        items = [{"id": p["id"], "heading": hd, "pitch": 0, "fov": 90, "wgs": p["wgs"],
                  "label": f"{p['wgs'][0]:.4f},{p['wgs'][1]:.4f} h{hd:.0f}"} for p in pts for hd in heads]
        _pages(items, 12, args.out)
        print("灰格 = 该点附近没有百度全景")
    else:
        if args.spec:
            items = json.loads(args.spec.read_text(encoding="utf-8"))
        else:
            if args.ids:
                panos = {p: {"id": p, "wgs": list(parse_id(p))} for p in args.ids.split(";") if p}
            else:
                panos = json.loads(args.panos.read_text(encoding="utf-8"))
            if args.within:
                wl, wo, wr = map(float, args.within.split(","))
                panos = {k: v for k, v in panos.items() if geo.distance((wl, wo), tuple(v["wgs"])) <= wr}
            if args.spread:
                panos = thin(panos, args.spread)
                print(f"--spread 抽稀后 {len(panos)} 个点")
            target = tuple(map(float, args.toward.split(","))) if args.toward else None
            items = []
            for pid, v in panos.items():
                if args.headings:
                    heads = [float(x) for x in args.headings.split(",")]
                elif target:
                    heads = [geo.bearing(tuple(v["wgs"]), target) + args.offset]
                elif args.heading is not None:
                    heads = [args.heading]
                else:
                    ap.error("需要 --heading、--headings 或 --toward")
                items += [{"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov, "wgs": v["wgs"]}
                          for hd in heads]
        _pages(items, args.limit, args.out)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
