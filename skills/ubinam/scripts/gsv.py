#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Google 街景（官方 Street View Static API）：找点、按朝向出图、拼对比图。用法和 baidu_pano.py 对齐。

需要环境变量 GOOGLE_MAPS_API_KEY（Google Cloud 控制台开通 Street View Static API）。元数据查询免费不计额度，出图按次计费。
条款限制（Google Maps Platform 3.2.3）：不得批量下载、不得缓存、不得与非 Google 地图混用。所以本脚本：
  - 不写持久缓存，图只放进进程临时目录，退出即删；你自己保存的 --out 文件仅供本次人工比对；
  - 单次进程最多出 60 张图；大范围批量比对改用 mapillary.py（开放许可）；
  - 官方接口只给每处最新一批全景，没有历史批次和邻点链，--date 不再支持。
国内几乎没有 Google 街景覆盖，国内照片用 baidu_pano.py；国内网络访问需代理（--proxy 或 GEO_PROXY）。

示例：
  gsv.py near 35.6595,139.7005 --radius 50                   # 最近的全景点：id、坐标、拍摄年月
  gsv.py render <pano_id> --heading 90 --out v.jpg
  gsv.py sheet --at 35.6595,139.7005 --headings 0,60,120,180,240,300 --out around.jpg   # 单点环视
  gsv.py sheet --points pts.json --toward 35.6600,139.7010 --out s.jpg                  # 每个点朝向同一目标
"""
from __future__ import annotations

import argparse
import json
import os
import re
import subprocess
import sys
import urllib.parse
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from PIL import Image, ImageDraw

sys.path.insert(0, str(Path(__file__).parent))
import geo  # noqa: E402
import providers  # noqa: E402
from baidu_pano import _font  # noqa: E402

API = "https://maps.googleapis.com/maps/api/streetview"
MAX_RENDERS = 60
_renders = 0


def _key() -> str:
    k = os.environ.get("GOOGLE_MAPS_API_KEY")
    if not k:
        sys.exit("gsv.py 需要环境变量 GOOGLE_MAPS_API_KEY（官方 Street View Static API）。没有密钥可用 mapillary.py。")
    return k


def _curl(url: str, proxy: str | None, out: Path | None = None) -> bytes:
    cmd = ["curl", "-s", "-m", "40", "-A", providers.UA]
    if proxy:
        cmd += ["-x", proxy]
    if out:
        cmd += ["-o", str(out)]
    r = subprocess.run(cmd + [url], capture_output=True)
    return r.stdout


def near(lat: float, lon: float, radius: float, proxy: str | None) -> dict | None:
    """官方元数据接口（免费）：最近的官方全景点。"""
    q = urllib.parse.urlencode({"location": f"{lat},{lon}", "radius": int(radius), "source": "outdoor", "key": _key()})
    try:
        d = json.loads(_curl(f"{API}/metadata?{q}", proxy) or b"{}")
    except json.JSONDecodeError:
        return None
    if d.get("status") != "OK":
        if d.get("status") not in ("ZERO_RESULTS", "NOT_FOUND"):
            print(f"Street View 元数据：{d.get('status')} {d.get('error_message', '')}", file=sys.stderr)
        return None
    loc = d.get("location") or {}
    return {"id": d.get("pano_id"), "wgs": [loc.get("lat"), loc.get("lng")], "date": d.get("date"),
            "copyright": d.get("copyright", "© Google")}


def render(pid: str, heading: float, pitch: float, fov: float, w: int, h: int, proxy: str | None,
           cache: Path | None = None) -> Image.Image:
    """heading 罗盘方位；pitch 正=抬头；fov 水平视角（官方上限 120）。不做持久缓存。"""
    global _renders
    _renders += 1
    if _renders > MAX_RENDERS:
        sys.exit(f"gsv.py 单次最多出 {MAX_RENDERS} 张图（条款禁止批量下载）；批量比对改用 mapillary.py")
    w, h = min(int(w), 640), min(int(h), 640)
    q = urllib.parse.urlencode({"pano": pid, "size": f"{w}x{h}", "heading": f"{heading % 360:.1f}",
                                "pitch": f"{pitch:.1f}", "fov": f"{min(fov, 120):.0f}", "return_error_code": "true",
                                "key": _key()})
    p = providers._tmpdir() / f"gsv_{pid}_{heading:.0f}_{pitch:.0f}_{fov:.0f}_{w}x{h}.jpg"
    if not (p.exists() and p.stat().st_size > 2000):
        _curl(f"{API}?{q}", proxy, p)
    try:
        return Image.open(p).convert("RGB")
    except Exception:  # noqa: BLE001
        return Image.new("RGB", (w, h), "gray")


def sheet(items: list[dict], out: Path, proxy: str | None, cache: Path, cols: int = 3, tw: int = 480, th: int = 360) -> None:
    with ThreadPoolExecutor(8) as ex:
        ims = list(ex.map(lambda it: render(it["id"], it["heading"], it.get("pitch", 0), it.get("fov", 90),
                                           640, 480, proxy, cache), items))
    rows = (len(items) + cols - 1) // cols
    S = Image.new("RGB", (cols * tw, max(1, rows) * th), "black")
    d = ImageDraw.Draw(S)
    f = _font(16)
    for i, (it, im) in enumerate(zip(items, ims)):
        x, y = (i % cols) * tw, (i // cols) * th
        S.paste(im.resize((tw, th)), (x, y))
        d.rectangle([x, y, x + tw, y + 22], fill="black")
        d.text((x + 4, y + 2), it.get("label") or f"{i}: …{it['id'][-8:]} h{it['heading']:.0f}", fill="yellow", font=f)
    S.save(out, quality=88)



def _neg_coords(argv: list[str]) -> list[str]:
    """argparse 把 -1.45,-48.5 这种负坐标当成选项名；前面补个空格就当普通值（float 会忽略空格）。南半球、西半球的题都要用。"""
    return [" " + a if re.match(r"^-\d[\d.]*(,-?[\d.]+)+$", a) else a for a in argv]


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--cache", type=Path, default=None, help="已停用：条款不允许缓存街景")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(sp):
        sp.add_argument("--proxy", default=argparse.SUPPRESS, help="写在子命令前后都行")
        sp.add_argument("--cache", type=Path, default=argparse.SUPPRESS)

    n = sub.add_parser("near")
    common(n)
    n.add_argument("latlon")
    n.add_argument("--radius", type=float, default=50)

    r = sub.add_parser("render")
    common(r)
    r.add_argument("id")
    r.add_argument("--heading", type=float, required=True)
    r.add_argument("--pitch", type=float, default=0, help="正=抬头")
    r.add_argument("--fov", type=float, default=90, help="水平视角")
    r.add_argument("--width", type=int, default=640, help="官方上限 640")
    r.add_argument("--height", type=int, default=640, help="官方上限 640")
    r.add_argument("--out", type=Path, required=True)

    s = sub.add_parser("sheet")
    common(s)
    g = s.add_mutually_exclusive_group(required=True)
    g.add_argument("--ids", help="逗号分隔的 panoid")
    g.add_argument("--at", help="lat,lon：取最近的全景点")
    g.add_argument("--points", type=Path, help="JSON {name:[lat,lon]}：每个点各取最近的全景点")
    h = s.add_mutually_exclusive_group(required=True)
    h.add_argument("--heading", type=float)
    h.add_argument("--headings", help="逗号分隔，如 0,60,120,180,240,300")
    h.add_argument("--toward", help="lat,lon：每个点朝向这个目标")
    s.add_argument("--offset", type=float, default=0)
    s.add_argument("--pitch", type=float, default=0)
    s.add_argument("--fov", type=float, default=90)
    s.add_argument("--radius", type=float, default=50)
    s.add_argument("--limit", type=int, default=12)
    s.add_argument("--out", type=Path, required=True)

    args = ap.parse_args(_neg_coords(sys.argv[1:]))
    if args.cmd == "near":
        lat, lon = map(float, args.latlon.split(","))
        res = near(lat, lon, args.radius, args.proxy)
        print(json.dumps(res, ensure_ascii=False, indent=1) if res else "附近没有官方 Google 街景（加大 --radius，或这里没覆盖；可试 mapillary.py）")
    elif args.cmd == "render":
        render(args.id, args.heading, args.pitch, args.fov, args.width, args.height, args.proxy, args.cache).save(args.out)
        print(args.out)
    else:
        panos: dict[str, dict] = {}
        if args.ids:
            panos = {pid: {"ll": None, "name": "", "date": ""} for pid in args.ids.split(",")}
        else:
            pts = {"at": list(map(float, args.at.split(",")))} if args.at else json.loads(args.points.read_text(encoding="utf-8"))
            for name, (la, lo) in pts.items():
                res = near(la, lo, args.radius, args.proxy)
                if res:
                    panos.setdefault(res["id"], {"ll": res["wgs"], "name": name, "date": res.get("date") or ""})
                else:
                    print(f"{name}: 附近没有全景", file=sys.stderr)
        target = tuple(map(float, args.toward.split(","))) if args.toward else None
        items = []
        for pid, meta in panos.items():
            ll = meta["ll"]
            if args.headings:
                heads = [float(x) for x in args.headings.split(",")]
            elif target:
                if ll is None:
                    info = near(*target, 5000, args.proxy)  # 只有 id 时拿不到坐标，按目标附近估；建议用 --points
                    ll = info["wgs"] if info else list(target)
                heads = [geo.bearing(tuple(ll), target) + args.offset]
            else:
                heads = [args.heading]
            for hd in heads:
                where = f"{ll[0]:.5f},{ll[1]:.5f}" if ll else f"…{pid[-8:]}"
                label = " ".join(x for x in (meta["name"][:18], where, meta["date"], f"h{hd % 360:.0f}") if x)
                items.append({"id": pid, "heading": hd % 360, "pitch": args.pitch, "fov": args.fov,
                              "label": f"{len(items)}: {label}", "point": meta["name"], "wgs": ll, "date": meta["date"]})
        pages = [items[k:k + args.limit] for k in range(0, len(items), args.limit)] or [[]]
        for pi, page in enumerate(pages):
            out = args.out if pi == 0 else args.out.with_name(f"{args.out.stem}_{pi + 1}{args.out.suffix}")
            sheet(page, out, args.proxy, args.cache)
            print(out)
        args.out.with_suffix(".index.json").write_text(json.dumps(items, indent=1), encoding="utf-8")


if __name__ == "__main__":
    # 中文 Windows 默认按 GBK 输出：遇到 m²、ñ 会崩，agent 读到的中文也是乱码
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8", errors="backslashreplace")
    main()
