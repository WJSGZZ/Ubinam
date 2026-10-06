#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["rasterio", "pillow", "numpy"]
# ///
"""Sentinel-2 时间序列：同一地点约每 5 天一景（2017 起），把拍摄时间推到“哪几个月之间”。

Esri Wayback 一年只有一两期影像；要知道一个工地、湖岸改造、新楼封顶、作物收割发生在哪个月，用这个。
10 米分辨率，看得见大型施工、水面变化、农田季相、大片新建筑，看不清单栋小楼和招牌。

  s2time.py list 31.6386,120.7576 --from 2024-01 --to 2025-06 [--max-cloud 30]      # 列景：日期、整景云量
  s2time.py sheet 31.6386,120.7576 --from 2024-01 --to 2025-06 --monthly [--size 1500] --out s2.jpg   # 每月取云最少的一景，裁出这一点周围拼图

用法要点：照片里有、影像里还没有的东西 → 拍摄不早于它首次出现的那一景；照片里还在、影像里已经消失的 → 不晚于。
两景之间就是区间，区间宽度取决于中间有几景没被云挡住。整景云量低不代表这一点没云，拼图里看。
数据：Copernicus Sentinel-2 L2A（Element84 Earth Search 的 AWS 开放数据，免密钥）。署名“Contains modified Copernicus Sentinel data <年份>”。
"""
from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

STAC = "https://earth-search.aws.element84.com/v1/search"
ATTR = "Contains modified Copernicus Sentinel data"


def _month_end(ym: str) -> str:
    y, m = map(int, ym.split("-")[:2])
    y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return f"{y:04d}-{m:02d}-01T00:00:00Z"


def search(lat: float, lon: float, t0: str, t1: str, max_cloud: float, proxy: str | None) -> list[dict]:
    """返回按日期排序的景：id、date、cloud、href（真彩色 COG）、epsg。翻页取全。"""
    body = {"collections": ["sentinel-2-l2a"], "intersects": {"type": "Point", "coordinates": [lon, lat]},
            "datetime": f"{t0}-01T00:00:00Z/{_month_end(t1)}", "limit": 200,
            "query": {"eo:cloud_cover": {"lt": max_cloud}}}
    out, url, payload = [], STAC, body
    while url:
        cmd = ["curl", "-s", "-m", "60", "-X", "POST", url, "-H", "Content-Type: application/json", "-d", json.dumps(payload)]
        if proxy:
            cmd[1:1] = ["-x", proxy]
        d = json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout or "{}")
        for f in d.get("features", []):
            p = f["properties"]
            epsg = p.get("proj:epsg") or int(str(p.get("proj:code", "EPSG:0")).split(":")[-1])
            out.append({"id": f["id"], "date": p["datetime"][:10], "cloud": round(p.get("eo:cloud_cover", -1), 1),
                        "href": f["assets"]["visual"]["href"], "epsg": epsg})
        nxt = next((l for l in d.get("links", []) if l.get("rel") == "next"), None)
        url, payload = (nxt["href"], nxt.get("body", payload)) if nxt else (None, None)
    seen, uniq = set(), []
    for s in sorted(out, key=lambda s: (s["date"], s["cloud"])):   # 同一天相邻图幅重复时留云少的
        if s["date"] not in seen:
            seen.add(s["date"])
            uniq.append(s)
    return uniq


def monthly(scenes: list[dict]) -> list[dict]:
    best: dict[str, dict] = {}
    for s in scenes:
        m = s["date"][:7]
        if m not in best or s["cloud"] < best[m]["cloud"]:
            best[m] = s
    return [best[m] for m in sorted(best)]


def crop(s: dict, lat: float, lon: float, size: float, px: int = 300):
    import numpy as np
    import rasterio
    from PIL import Image
    from rasterio.warp import transform
    from rasterio.windows import from_bounds
    with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN="EMPTY_DIR", AWS_NO_SIGN_REQUEST="YES"):
        with rasterio.open(s["href"]) as ds:
            xs, ys = transform("EPSG:4326", ds.crs, [lon], [lat])
            h = size / 2
            win = from_bounds(xs[0] - h, ys[0] - h, xs[0] + h, ys[0] + h, ds.transform)
            a = ds.read([1, 2, 3], window=win, boundless=True, fill_value=0)
    img = Image.fromarray(np.moveaxis(a, 0, -1).astype("uint8")).resize((px, px), Image.LANCZOS)
    return img


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("list", "sheet"):
        sp = sub.add_parser(name)
        sp.add_argument("at")
        sp.add_argument("--from", dest="t0", required=True, help="YYYY-MM")
        sp.add_argument("--to", dest="t1", required=True, help="YYYY-MM")
        sp.add_argument("--max-cloud", type=float, default=40)
        if name == "sheet":
            sp.add_argument("--monthly", action="store_true", help="每月只取整景云量最少的一景")
            sp.add_argument("--size", type=float, default=1500, help="裁剪边长 m（10 m/像素，1500 m≈150 像素）")
            sp.add_argument("--max", type=int, default=24)
            sp.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    lat, lon = map(float, a.at.split(","))
    scenes = search(lat, lon, a.t0, a.t1, a.max_cloud, a.proxy)
    if a.cmd == "list":
        print(f"{a.at} {a.t0}–{a.t1} 整景云量 < {a.max_cloud}%：{len(scenes)} 景")
        for s in scenes:
            print(f"  {s['date']}  云 {s['cloud']:5.1f}%  {s['id']}")
        return
    if a.monthly:
        scenes = monthly(scenes)
    if len(scenes) > a.max:
        idx = sorted({round(i * (len(scenes) - 1) / (a.max - 1)) for i in range(a.max)})
        scenes = [scenes[i] for i in idx]
    if not scenes:
        sys.exit("没有符合条件的景：放宽 --max-cloud 或时间范围")
    from concurrent.futures import ThreadPoolExecutor
    from PIL import Image, ImageDraw
    with ThreadPoolExecutor(6) as ex:
        tiles = list(ex.map(lambda s: crop(s, lat, lon, a.size), scenes))
    cols = min(6, len(tiles))
    rows = (len(tiles) + cols - 1) // cols
    S = Image.new("RGB", (300 * cols, 322 * rows), "white")
    d = ImageDraw.Draw(S)
    for k, (s, t) in enumerate(zip(scenes, tiles)):
        ox, oy = (k % cols) * 300, (k // cols) * 322
        S.paste(t, (ox, oy + 22))
        d.text((ox + 4, oy + 5), f"{s['date']}  cloud {s['cloud']:.0f}%", fill="black")
        d.line([(ox + 145, oy + 172), (ox + 155, oy + 172)], fill="red")
        d.line([(ox + 150, oy + 167), (ox + 150, oy + 177)], fill="red")
    S.save(a.out, quality=90)
    print(f"-> {a.out}（{len(scenes)} 景，红十字是查询点，边长 {a.size:.0f} m；{ATTR}）")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
