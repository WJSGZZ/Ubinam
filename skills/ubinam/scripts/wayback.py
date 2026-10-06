#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["pillow"]
# ///
"""Esri World Imagery Wayback：同一地点 2014 年以来的历代卫星影像，看“以前是什么样”、给拍摄年份定上下限。

用途：
  - 影像过时：候选地点近年改造过（湖岸、桥、新楼），当前影像和照片对不上时，先看历代版本再决定排不排除。
  - 推年份：照片里有的楼／桥／路在哪一版首次出现 → 拍摄不早于那一版的影像日期；照片里还在、后来拆掉的 → 不晚于。

  wayback.py list [--last 20]                                   # 全部版本（发布日期）
  wayback.py changes 31.6385,120.7590 [--zoom 17]               # 只列这里影像真正变过的版本（比瓦片内容）
  wayback.py sheet 31.6385,120.7590 [--zoom 17] [--radius 1] [--max 8] --out hist.jpg   # 历代版本并排拼图

发布日期不是拍摄日期：影像是在发布日期之前拍的，所以“首次出现的版本日期”只是上限，要和前一个版本一起给区间。
影像 © Esri 及其供应商，按 Esri 条款仅供查看分析；不缓存，取图写进进程临时目录。免密钥。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import sys
import tempfile
from pathlib import Path

CONFIG = "https://s3-us-west-2.amazonaws.com/config.maptiles.arcgis.com/waybackconfig.json"
TILE = "https://wayback.maptiles.arcgis.com/arcgis/rest/services/World_Imagery/WMTS/1.0.0/default028mm/MapServer/tile/{rel}/{z}/{y}/{x}"
TMP = Path(tempfile.mkdtemp(prefix="ubinam-wayback-"))
ATTR = "World Imagery Wayback © Esri and its imagery providers"


def _get(url: str, out: Path | None = None, proxy: str | None = None) -> bytes:
    cmd = ["curl", "-s", "-m", "40", "-A", "ubinam/0.1"]
    if proxy:
        cmd += ["-x", proxy]
    if out:
        cmd += ["-o", str(out)]
    return subprocess.run(cmd + [url], capture_output=True).stdout


def releases(proxy: str | None) -> list[tuple[int, str]]:
    d = json.loads(_get(CONFIG, proxy=proxy) or b"{}")
    out = [(int(k), v["itemTitle"].split("Wayback ")[-1].rstrip(")")) for k, v in d.items()]
    return sorted(out, key=lambda r: r[1])


def tile_xy(lat: float, lon: float, z: int) -> tuple[int, int]:
    n = 2 ** z
    x = int((lon + 180) / 360 * n)
    y = int((1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi) / 2 * n)
    return x, y


def fetch(rel: int, z: int, x: int, y: int, proxy: str | None) -> Path | None:
    p = TMP / f"{rel}_{z}_{x}_{y}.jpg"
    if not p.exists():
        _get(TILE.format(rel=rel, z=z, x=x, y=y), p, proxy)
    return p if p.exists() and p.stat().st_size > 1000 else None


def changes(lat: float, lon: float, z: int, proxy: str | None) -> list[tuple[int, str]]:
    """按时间顺序比瓦片内容，只留影像真正换过的版本（相邻版本内容相同的合并）。"""
    x, y = tile_xy(lat, lon, z)
    out, last = [], None
    for rel, date in releases(proxy):
        p = fetch(rel, z, x, y, proxy)
        if not p:
            continue
        h = hashlib.md5(p.read_bytes()).hexdigest()
        if h != last:
            out.append((rel, date))
            last = h
    return out


def sheet(lat: float, lon: float, z: int, radius: int, vers: list[tuple[int, str]], out: Path, proxy: str | None) -> None:
    from PIL import Image, ImageDraw
    cx, cy = tile_xy(lat, lon, z)
    n = 2 * radius + 1
    W = 256 * n
    cols = min(4, len(vers))
    rows = (len(vers) + cols - 1) // cols
    S = Image.new("RGB", (W * cols, (W + 28) * rows), "white")
    d = ImageDraw.Draw(S)
    for k, (rel, date) in enumerate(vers):
        m = Image.new("RGB", (W, W), "gray")
        for i in range(n):
            for j in range(n):
                p = fetch(rel, z, cx - radius + i, cy - radius + j, proxy)
                if p:
                    m.paste(Image.open(p).convert("RGB"), (256 * i, 256 * j))
        ox, oy = (k % cols) * W, (k // cols) * (W + 28)
        S.paste(m, (ox, oy + 28))
        d.text((ox + 6, oy + 6), f"{date}  (release {rel})", fill="black")
    S.save(out, quality=90)
    print(f"-> {out}（{len(vers)} 个版本；{ATTR}）")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--proxy")
    sub = ap.add_subparsers(dest="cmd", required=True)
    ls = sub.add_parser("list")
    ls.add_argument("--last", type=int, default=20)
    for name in ("changes", "sheet"):
        sp = sub.add_parser(name)
        sp.add_argument("at")
        sp.add_argument("--zoom", type=int, default=17)
        if name == "sheet":
            sp.add_argument("--radius", type=int, default=1)
            sp.add_argument("--max", type=int, default=8, help="最多拼几个版本（均匀取，含首尾）")
            sp.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    if a.cmd == "list":
        r = releases(a.proxy)
        print(f"共 {len(r)} 个版本")
        for rel, date in r[-a.last:]:
            print(f"  {date}  release {rel}")
        return
    lat, lon = map(float, a.at.split(","))
    vers = changes(lat, lon, a.zoom, a.proxy)
    print(f"{a.at} z{a.zoom}：影像变过 {len(vers)} 次")
    for rel, date in vers:
        print(f"  {date}  release {rel}")
    if a.cmd == "sheet":
        if len(vers) > a.max:
            idx = sorted({round(i * (len(vers) - 1) / (a.max - 1)) for i in range(a.max)})
            vers = [vers[i] for i in idx]
        sheet(lat, lon, a.zoom, a.radius, vers, a.out, a.proxy)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
