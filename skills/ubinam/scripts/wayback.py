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
  wayback.py meta 31.6385,120.7590 [--all]                      # 这里影像的真实拍摄日期、卫星、分辨率（--all：每个变过的版本都查）

发布日期不是拍摄日期：changes/sheet 列的是发布日期（只是上限），meta 查 Esri 元数据图层给出的拍摄日期（SRC_DATE），
推年份、判断“影像是不是比照片旧”时用拍摄日期。发布更晚不代表影像更新（实测一处 2019 年发布的版本用的是 2011 年的影像），
瓦片内容变了也可能只是重新调色，拍摄日期相同的版本算同一期。卫星名（WV02/WV03/GE01 等）可用于估过境时刻，见 geometry.md“卫星图影子测高”。
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


_CFG: dict = {}


def config(proxy: str | None) -> dict:
    if not _CFG:
        _CFG.update(json.loads(_get(CONFIG, proxy=proxy) or b"{}"))
    return _CFG


def releases(proxy: str | None) -> list[tuple[int, str]]:
    out = [(int(k), v["itemTitle"].split("Wayback ")[-1].rstrip(")")) for k, v in config(proxy).items()]
    return sorted(out, key=lambda r: r[1])


def capture(rel: int, lat: float, lon: float, proxy: str | None) -> dict | None:
    """该版本在这一点用的影像：拍摄日期、卫星/传感器、原始分辨率（取最细一级元数据图层）。"""
    url = config(proxy).get(str(rel), {}).get("metadataLayerUrl")
    if not url:
        return None
    q = (f"{url}/identify?geometry={lon},{lat}&geometryType=esriGeometryPoint&sr=4326&layers=all&tolerance=1"
         f"&mapExtent={lon - .01},{lat - .01},{lon + .01},{lat + .01}&imageDisplay=800,600,96&returnGeometry=false&f=json")
    try:
        res = json.loads(_get(q, proxy=proxy) or b"{}").get("results", [])
    except json.JSONDecodeError:
        return None
    if not res:
        return None
    a = min(res, key=lambda r: r["layerId"])["attributes"]
    d = a.get("SRC_DATE", "")
    return {"date": f"{d[:4]}-{d[4:6]}-{d[6:8]}" if len(d) == 8 else d, "sensor": a.get("SRC_DESC", ""),
            "res_m": a.get("SRC_RES", ""), "acc_m": a.get("SRC_ACC", ""), "vendor": a.get("NICE_DESC", "")}


def _cap_str(c: dict | None) -> str:
    return f"拍摄 {c['date']}  {c['sensor']} {c['res_m']} m（{c['vendor']}）" if c else "拍摄日期未知"


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
    from concurrent.futures import ThreadPoolExecutor
    x, y = tile_xy(lat, lon, z)
    rels = releases(proxy)
    with ThreadPoolExecutor(12) as ex:  # 196 个版本逐个取要几分钟，并行取
        tiles = list(ex.map(lambda r: fetch(r[0], z, x, y, proxy), rels))
    out, last = [], None
    for (rel, date), p in zip(rels, tiles):
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
    for name in ("changes", "sheet", "meta"):
        sp = sub.add_parser(name)
        sp.add_argument("at")
        sp.add_argument("--zoom", type=int, default=17)
        if name == "meta":
            sp.add_argument("--all", action="store_true", help="每个影像变过的版本都查拍摄日期")
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
    if a.cmd == "meta" and not a.all:
        rel, date = releases(a.proxy)[-1]
        print(f"{a.at} 最新版（发布 {date}，release {rel}）：{_cap_str(capture(rel, lat, lon, a.proxy))}")
        return
    vers = changes(lat, lon, a.zoom, a.proxy)
    print(f"{a.at} z{a.zoom}：影像变过 {len(vers)} 次")
    caps = {}
    if a.cmd == "meta":
        from concurrent.futures import ThreadPoolExecutor
        with ThreadPoolExecutor(8) as ex:
            caps = dict(zip([r for r, _ in vers], ex.map(lambda v: capture(v[0], lat, lon, a.proxy), vers)))
    for rel, date in vers:
        print(f"  发布 {date}  release {rel}" + (f"  {_cap_str(caps[rel])}" if a.cmd == "meta" else ""))
    if a.cmd == "sheet":
        if len(vers) > a.max:
            idx = sorted({round(i * (len(vers) - 1) / (a.max - 1)) for i in range(a.max)})
            vers = [vers[i] for i in idx]
        sheet(lat, lon, a.zoom, a.radius, vers, a.out, a.proxy)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
