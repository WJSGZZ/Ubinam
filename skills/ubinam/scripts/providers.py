#!/usr/bin/env python3
# /// script
# requires-python = ">=3.10"
# dependencies = []
# ///
"""数据源注册表：卫星影像和街景从哪里取、要什么密钥、许可允许怎么用。

所有取外部影像的脚本都经过这里，不在脚本里直接写服务地址。每个数据源声明：
  key_env     需要的环境变量（没有就不可用）
  cache       许可是否允许把取到的图存进 .geo-cache 反复使用
  bulk        是否允许批量扫描（sat_scan 网格、街景批量比对）
  max_per_run 单次进程最多取多少张（防止无意中批量下载）
  license     许可与署名，出证据图时照写

只用官方接口或开放许可的数据。新增数据源前先读它的服务条款，把上面几项如实填好。

  providers.py list                 列出数据源、是否可用（密钥是否已设）、许可要点
  providers.py check esri           试取一张瓦片，确认密钥有效
"""
from __future__ import annotations

import atexit
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path

UA = "ubinam/0.1 (photo geolocation research; https://github.com/WJSGZZ/Ubinam)"


@dataclass
class Imagery:
    name: str
    title: str
    key_env: str | None
    cache: bool
    bulk: bool
    max_per_run: int
    max_zoom: int
    license: str
    url: str = ""                       # {z} {x} {y} {key}
    notes: str = ""
    _count: int = field(default=0, repr=False)


IMAGERY: dict[str, Imagery] = {
    "esri": Imagery(
        "esri", "Esri World Imagery（ArcGIS Location Platform 官方底图服务）",
        key_env="ARCGIS_API_KEY", cache=False, bulk=True, max_per_run=5000, max_zoom=19,
        license="Imagery © Esri, Vantor and the GIS User Community；按 ArcGIS Location Platform 条款使用",
        url="https://ibasemaps-api.arcgis.com/arcgis/rest/services/World_Imagery/MapServer/tile/{z}/{y}/{x}?token={key}",
        notes="免费账号有月度底图瓦片额度；密钥在 location.arcgis.com 申请。条款对缓存的限制以 Esri 官方为准，这里默认不缓存。"),
    "s2cloudless": Imagery(
        "s2cloudless", "Sentinel-2 cloudless 2016（EOX，免密钥）",
        key_env=None, cache=True, bulk=True, max_per_run=20000, max_zoom=15,
        license="Sentinel-2 cloudless - https://s2maps.eu by EOX IT Services GmbH (Contains modified Copernicus Sentinel data 2016)，CC BY 4.0",
        url="https://tiles.maps.eox.at/wmts/1.0.0/s2cloudless_3857/default/g/{z}/{y}/{x}.jpg",
        notes="分辨率约 10 米：看得出海岸、河流、大片农田和城区轮廓，看不出操场和单栋楼。只有 2016 年这一版是 CC BY 4.0，更新年份是非商用许可，不要换。"),
    "google": Imagery(
        "google", "Google Map Tiles API 卫星图（官方，需密钥）",
        key_env="GOOGLE_MAPS_API_KEY", cache=False, bulk=False, max_per_run=200, max_zoom=21,
        license="Imagery © Google；按 Google Maps Platform 条款使用，图上须保留 Google 署名",
        notes="条款 3.2.3 禁止批量下载、缓存、以及与非 Google 地图混用，所以只能用来人工看少量候选（tiles.py fetch/sheet），sat_scan 不接受它。"),
}


STREET = [
    ("mapillary.py", "MAPILLARY_TOKEN", "众包街景，CC BY-SA 4.0，允许缓存和批量比对；批量比对首选"),
    ("gsv.py", "GOOGLE_MAPS_API_KEY", "Google 官方 Street View Static API；不缓存、单次 ≤60 张，只供人工核对少量候选"),
    ("baidu_pano.py", "BAIDU_MAP_AK", "百度官方全景静态图；国内主力；不缓存、单次 ≤150 张"),
]


# 本机插件：scripts/local/providers_local.py 若存在（不进仓库），可追加影像源和街景条目
try:
    sys.path.insert(0, str(Path(__file__).resolve().parent / "local"))
    import providers_local  # type: ignore
    providers_local.register(Imagery, IMAGERY, STREET)
except ImportError:
    pass


def baidu_url(base: str, params: dict) -> str:
    """百度地图 Web 服务请求地址。设了 BAIDU_MAP_SK（控制台把应用设为「SN 校验」）时按官方算法加 sn：
    原始 querystring 按参数插入顺序拼接，前接 URI 路径，quote（safe 同官方示例）后直接接 SK，再 quote_plus 取 MD5；
    实际请求必须用同一个 querystring、同一顺序，sn 放最后。见 lbsyun.baidu.com 附录「SN 计算算法」。"""
    import hashlib
    import urllib.parse
    raw = "&".join(f"{k}={v}" for k, v in params.items())
    sk = os.environ.get("BAIDU_MAP_SK")
    if not sk:
        return f"{base}?{urllib.parse.urlencode(params)}"
    path = urllib.parse.urlsplit(base).path
    enc = urllib.parse.quote(f"{path}?{raw}", safe="/:=&?#+!$,;'@()*[]")
    sn = hashlib.md5(urllib.parse.quote_plus(enc + sk).encode()).hexdigest()
    return f"{base}?{enc.split('?', 1)[1]}&sn={sn}"


def default_imagery() -> str:
    """UBINAM_IMAGERY 指定优先；否则有 Esri 密钥用 Esri，再否则用 Sentinel-2。"""
    v = os.environ.get("UBINAM_IMAGERY")
    if v:
        if v not in IMAGERY:
            sys.exit(f"UBINAM_IMAGERY={v} 不认识；可选 {', '.join(IMAGERY)}")
        return v
    return "esri" if os.environ.get("ARCGIS_API_KEY") else "s2cloudless"


def require(name: str, purpose: str = "", bulk: bool = False) -> Imagery:
    if name not in IMAGERY:
        sys.exit(f"未知影像源 {name}；可选 {', '.join(IMAGERY)}")
    p = IMAGERY[name]
    if p.key_env and not os.environ.get(p.key_env):
        sys.exit(f"影像源 {name} 需要环境变量 {p.key_env}。{p.notes}\n没有密钥可改用 --source s2cloudless（低分辨率，免密钥）。")
    if bulk and not p.bulk:
        sys.exit(f"影像源 {name} 的条款不允许批量扫描（{purpose}）。{p.notes}\n改用 --source esri（需 ARCGIS_API_KEY）或 s2cloudless。")
    return p


_TMP: Path | None = None


def _tmpdir() -> Path:
    global _TMP
    if _TMP is None:
        _TMP = Path(tempfile.mkdtemp(prefix="ubinam-nocache-"))
        atexit.register(shutil.rmtree, _TMP, True)
    return _TMP


def _curl(url: str, out: Path, proxy: str | None, headers: list[str] | None = None, data: str | None = None) -> int:
    cmd = ["curl", "-s", "-m", "60", "-A", UA, "-o", str(out), "-w", "%{http_code}"]
    for h in headers or []:
        cmd += ["-H", h]
    if data is not None:
        cmd += ["-X", "POST", "--data", data]
    if proxy:
        cmd[1:1] = ["-x", proxy]
    r = subprocess.run(cmd + [url], capture_output=True, text=True)
    try:
        return int(r.stdout.strip() or 0)
    except ValueError:
        return 0


_GSESSION: dict = {}


def _google_session(proxy: str | None) -> str:
    """Map Tiles API 要先建会话；会话有有效期，过期重建。"""
    if _GSESSION.get("exp", 0) > time.time() + 60:
        return _GSESSION["session"]
    key = os.environ["GOOGLE_MAPS_API_KEY"]
    out = _tmpdir() / "gsession.json"
    code = _curl(f"https://tile.googleapis.com/v1/createSession?key={key}", out, proxy,
                 headers=["Content-Type: application/json"],
                 data=json.dumps({"mapType": "satellite", "language": "en-US", "region": "US"}))
    d = json.loads(out.read_text() or "{}")
    if code != 200 or "session" not in d:
        sys.exit(f"Google Map Tiles 会话创建失败（HTTP {code}）：{str(d)[:300]}")
    _GSESSION.update(session=d["session"], exp=float(d.get("expiry", time.time() + 3600)))
    return d["session"]


def tile_url(name: str, z: int, x: int, y: int, proxy: str | None = None) -> str:
    p = IMAGERY[name]
    if name == "google":
        key = os.environ["GOOGLE_MAPS_API_KEY"]
        return f"https://tile.googleapis.com/v1/2dtiles/{z}/{x}/{y}?session={_google_session(proxy)}&key={key}"
    key = os.environ.get(p.key_env, "") if p.key_env else ""
    return p.url.format(z=z, x=x, y=y, key=key)


def fetch_tile(name: str, z: int, x: int, y: int, cache: Path, proxy: str | None = None) -> Path | None:
    """取一张 256×256 瓦片，返回本地路径；许可不允许缓存的写进进程临时目录，退出即删。"""
    p = require(name)
    if z > p.max_zoom:
        sys.exit(f"影像源 {name} 最大缩放 {p.max_zoom}，请求了 z{z}。{p.notes}")
    if p.cache:
        cache.mkdir(parents=True, exist_ok=True)
        path = cache / f"{name}_{z}_{x}_{y}.jpg"
        if path.exists() and path.stat().st_size > 1000:
            return path
    else:
        path = _tmpdir() / f"{name}_{z}_{x}_{y}.jpg"
        if path.exists() and path.stat().st_size > 1000:
            return path
    p._count += 1
    if p._count > p.max_per_run:
        sys.exit(f"影像源 {name} 单次最多取 {p.max_per_run} 张瓦片（{p.notes}）")
    code = _curl(tile_url(name, z, x, y, proxy), path, proxy)
    if code == 200 and path.exists() and path.stat().st_size > 1000:
        return path
    path.unlink(missing_ok=True)
    return None


def attribution(names: set[str] | list[str]) -> str:
    return "；".join(IMAGERY[n].license for n in names if n in IMAGERY)


def main() -> None:
    import argparse
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("list")
    c = sub.add_parser("check")
    c.add_argument("name")
    c.add_argument("--proxy", default=os.environ.get("GEO_PROXY"))
    a = ap.parse_args()
    if a.cmd == "list":
        print(f"默认影像源：{default_imagery()}（UBINAM_IMAGERY 可改）\n")
        for p in IMAGERY.values():
            ok = "可用" if not p.key_env or os.environ.get(p.key_env) else f"缺 {p.key_env}"
            print(f"[{p.name}] {p.title} — {ok}；缓存 {'允许' if p.cache else '不缓存'}；批量 {'允许' if p.bulk else '禁止'}；最大 z{p.max_zoom}")
            print(f"    许可：{p.license}\n    {p.notes}")
        print("\n街景：")
        for name, env, note in STREET:
            ok = "可用" if not env or os.environ.get(env) else f"缺 {env}"
            print(f"[{name}] {ok} — {note}")
        return
    path = fetch_tile(a.name, 12, 3372, 1686, Path(".geo-cache/tiles"), a.proxy)
    print(f"{a.name}: {'OK ' + str(path) if path else '失败'}")


if __name__ == "__main__":
    main()
