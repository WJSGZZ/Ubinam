#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = ["geoclip", "pillow"]
# ///
"""GeoCLIP 粗定位：一张照片 → 最可能的几个经纬度（独立第二意见）。

GeoCLIP（NeurIPS 2023，MIT）用带坐标的照片训练，直接从画面预测 GPS。它擅长国家、大区级的整体判断，
不读文字、不懂推理，对没见过的小地方只能给大致区域。用法定位：
  - 第 1 步列候选时作为一条独立线索（status=inferred），和自己的判断对照；两者冲突时去找区分线索，不直接采信任何一方。
  - 不能单独作为排除或确认依据；top-k 分散在几个大洲时说明这张图信息少，正好用来估“可定位上限”。

  prior.py photo.jpg [--top 5] [--no-geocode] [--out prior.json]

第一次运行会下载模型（约 600 MB）。--no-geocode 不联网反查地名（默认用 Nominatim，遵守每秒 1 次）。
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import time
import urllib.parse
from pathlib import Path

UA = "ubinam/0.1 (photo geolocation research; https://github.com/WJSGZZ/Ubinam)"


def reverse(lat: float, lon: float, proxy: str | None) -> str:
    q = urllib.parse.urlencode({"lat": lat, "lon": lon, "format": "jsonv2", "zoom": 10, "accept-language": "zh-CN,en"})
    cmd = ["curl", "-s", "-m", "20", "-A", UA, f"https://nominatim.openstreetmap.org/reverse?{q}"]
    if proxy:
        cmd[1:1] = ["-x", proxy]
    try:
        return json.loads(subprocess.run(cmd, capture_output=True, text=True).stdout or "{}").get("display_name", "")
    except json.JSONDecodeError:
        return ""


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("image", type=Path)
    ap.add_argument("--top", type=int, default=5)
    ap.add_argument("--no-geocode", action="store_true")
    ap.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    ap.add_argument("--out", type=Path)
    a = ap.parse_args()
    if a.proxy:
        os.environ.setdefault("HTTPS_PROXY", a.proxy)
    from geoclip import GeoCLIP
    import torch
    t0 = time.time()
    model = GeoCLIP()
    dev = "mps" if torch.backends.mps.is_available() else "cpu"
    try:
        model = model.to(dev)
        model.device = dev
    except Exception:  # noqa: BLE001  个别版本不支持 mps 时退回 CPU
        model = model.to("cpu")
    gps, prob = model.predict(str(a.image), top_k=a.top)
    rows = []
    for (lat, lon), p in zip(gps.tolist(), prob.tolist()):
        name = "" if a.no_geocode else reverse(lat, lon, a.proxy)
        rows.append({"lat": round(lat, 5), "lon": round(lon, 5), "p": round(p, 4), "place": name})
        if not a.no_geocode:
            time.sleep(1.1)
    print(f"GeoCLIP（{time.time() - t0:.0f}s）top {a.top}：")
    for i, r in enumerate(rows, 1):
        print(f"  {i}. {r['lat']},{r['lon']}  p={r['p']:.3f}  {r['place'][:90]}")
    spread = max(abs(r["lat"] - rows[0]["lat"]) + abs(r["lon"] - rows[0]["lon"]) for r in rows)
    print("前几名相距很远：这张图信息少，先估可定位上限" if spread > 20 else
          "前几名集中只说明模型自己一致，不说明它对（实测曾集中错到 1000 km 外）；照常和其他线索对照")
    if a.out:
        a.out.write_text(json.dumps(rows, ensure_ascii=False, indent=1), encoding="utf-8")
        print(f"-> {a.out}")


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8")
    main()
