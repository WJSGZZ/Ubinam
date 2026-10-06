# 脚本、数据源与坐标系

## 脚本总表（`scripts/`）

| 脚本 | 做什么 | 网络 |
|---|---|---|
| `exif.py` | GPS、拍摄时间、等效焦距、镜头朝向 | — |
| `imgprep.py` | zoom 放大读字 / edges 四边四角 / variants 搜图变体 / grid 切块 / `piers` 沿指定行取亮度剖面找等间距构件的像素列（出核对图） | — |
| `revimg.py` | 百度识图 + Yandex 以图搜图；`--query` 中文关键词搜索（必应国内版、百度/搜狗图片）。**自动化访问公开网页并上传图片，默认不用，用户同意后才跑** | 百度、必应直连；Yandex 可能要代理 |
| `geo.py` | 坐标系换算、方位距离、相机几何（`range --hfov a:b` 距离区间）、`line` 对齐线、`intersect` 视线交会、`frame` 排除前算画框和遮挡、`spacing` 等间距构件像素列 × 已知折线反解机位（可选和天际线联合打分） | 仅 `spacing` 取高程切片，直连或代理均可 |
| `wayback.py` | Esri World Imagery Wayback：同一地点 2014 年以来的历代影像，`changes` 只列真正变过的版本，`sheet` 并排拼图；看改造前后、给拍摄年份定上下限 | 免密钥，不缓存 |
| `poi.py` | 地名、小区名、楼盘名、店名 → 坐标候选（高德 `AMAP_KEY` + 百度 `BAIDU_MAP_AK` + OSM Nominatim），全国同名点都列出 | 高德、百度直连；Nominatim 国内可能要代理 |
| `sun.py` | 太阳位置、影长比、`locate` 地带、`when` 时刻、`street` 街道走向、`facing` 受光面定朝向、`dish` 卫星锅 | — |
| `osm.py` | Overpass：find / near 共现 / crossings 线变点 / route 线路走廊 / intersect 两类线交叉（折角只标注，`--rank-near` 排序）/ street-scan 街景几何模板 / geom 导出几何 | 国内可能要代理 |
| `tiles.py` | 卫星切片拼图、`mark` 标点 + 叠 GeoJSON 线 + 视野扇形、`sheet` 候选点带编号缩略图；影像源由 `providers.py` 决定 | 按影像源 |
| `baidu_pano.py` | 百度官方全景静态图（`BAIDU_MAP_AK`）：scan 生成取图点 / render / sheet（`--headings` 单点环视、`--spread`）/ sample 候选城市街景抽样；按坐标取图，无全景 id、路名、日期；单次 ≤150 张、不缓存 | 直连 |
| `gsv.py` | Google 官方 Street View Static API（`GOOGLE_MAPS_API_KEY`）：near（元数据免费）/ render / sheet；只给最新一批；单次 ≤60 张、不缓存 | 国内要代理 |
| `pose.py` | 多点反解机位：经纬度、高度、朝向、俯仰、横滚、视角 + 误差半径 + 逐点检查；`check` 给离散候选机位打分；`project` 把地图点投回照片 | — |
| `terrain.py` | 高程：view 合成山体视图（`--overlay` 天际线叠照片、`--roll`）/ profile 天际线 / elev / `ridge` 从照片读山脊像素点 / `scan` 沿设施线整区筛「近处平 + 有山」的点并聚簇 / `fit` 候选机位批量天际线打分（可选设施距离约束，出前 N 名叠图） | 直连或代理均可（`ridge` 不联网） |
| `evidence.py` | 证据图：卫星图 + 机位扇形 + 比对格 | — |
| `intake.py` | 第 0–3 步一条命令：exif + 边缘图 + 变体 + OCR；加 `--rev` 才并行做百度/Yandex 识图，出 intake.md（分级计票、疑似地名） | 默认不联网；`--rev` 同 revimg |
| `ocr.py` | 读照片文字（Apple Vision，回退 RapidOCR）：整图 + 放大 + 切块合并，放大才读出的标 pass | — |
| `clues.py` | 查表：车牌前缀、固话区号、国家电话码、行驶方向、海外领地、行政区上下级；表在 `data/`，`update` 重抓 | lookup 不联网；update 代理 |
| `board.py` | 候选盘：候选、线索、证据似然比、排除（要算过的文件）、排名、扫描成本、下一步、出结论检查、生成 result.json 字段 | — |
| `gazetteer.py` | 行政区名录：下级列全（带 bbox）、建成区范围、扫描页数 | Overpass |
| `sat_scan.py` | 卫星图网格/候选点 CLIP 零样本打分排序（操场、厂房、筒仓、水坝…），前 N 名缩略图 + 热图；只接受许可允许批量的影像源（Esri、Sentinel-2） | 按影像源；首次下模型 |
| `match.py` | 照片 vs 候选实景图排名：DINOv2 或 MegaLoc（VPR，MIT）全局相似度 + SIFT 内点精排；候选可由 Mapillary / 百度 / Google 现场渲染 | 按街景源；首次下模型 |
| `providers.py` | 影像源注册表：`list` 看哪些源可用（密钥是否已设）、许可、能否缓存和批量；`check <源>` 试取一张 | 按影像源 |
| `mapillary.py` | Mapillary 众包街景（`MAPILLARY_TOKEN`，CC BY-SA 4.0）：near / scan / render（全景可按朝向重投影）/ sheet；批量比对首选，可缓存 | 国内可能要代理 |
| `prior.py` | GeoCLIP（MIT）粗定位：照片 → top-k 经纬度 + Nominatim 反查地名；独立第二意见，不作排除依据 | 首次下模型；反查用 Nominatim |
| `geo.py bearings` | 机位 → GeoJSON 里每个轮廓的方位角、角宽、距离；配 `sun.py compass` 先算方位再认构件 | — |

## 坐标系（国内必须分清）

| 代号 | 名称 | 谁在用 |
|---|---|---|
| wgs | WGS84 | GPS、照片 EXIF、Google 卫星图、OpenStreetMap、高程切片 |
| gcj | GCJ-02 | 高德、腾讯、360 地图、Google 中国区道路图，**Google Earth 国内的中文标注图层** |
| bd | BD-09 | 百度地图经纬度 |
| bdmc | 百度墨卡托 | 百度地图 URL 里的 `@x,y`、百度全景接口 |

国内同一个点在 WGS84 和 GCJ-02 之间差几百米。换算：`scripts/geo.py convert --from X --to Y a b`。
- 高德链接用 gcj：`https://uri.amap.com/marker?position=经度,纬度`；Google 链接用 wgs。
- **Google Earth 在国内：影像是 WGS84，中文地名标注是 GCJ-02，两者错开几百米**（v005：码头的中文标签落在江面上）。打点、读坐标以影像为准。
- 从国内地图 App 或网页读来的坐标，先确认坐标系再用。

## 卫星图

影像源由 `providers.py` 统一管理：有 `ARCGIS_API_KEY` 默认 Esri，否则 Sentinel-2；`UBINAM_IMAGERY` 可指定。新增来源前先读其条款，在注册表里如实填写能否缓存、能否批量。

| 来源 | 许可与限制 | 用途 |
|---|---|---|
| Esri World Imagery（`ibasemaps-api.arcgis.com`） | ArcGIS Location Platform 官方底图，需 `ARCGIS_API_KEY`，免费账号有月度瓦片额度；默认不缓存 | 0.3–1 m，sat_scan 批量排序的主力 |
| Sentinel-2 cloudless 2016（EOX） | CC BY 4.0，免密钥，可缓存；只有 2016 版是 CC BY，更新年份为非商用，不换 | 约 10 m、最高 z15：海岸、河流、大片农田、城区轮廓 |
| Google Map Tiles API | 官方，需 `GOOGLE_MAPS_API_KEY`；条款禁止批量下载、缓存、与非 Google 地图混用 | 只供 `tiles.py fetch/sheet` 人工看少量瓦片，sat_scan 不接受 |
| Google Earth 桌面版、Esri Wayback | 人工浏览 | 历史影像时间轴、倾斜 3D |

- 同一地点不同缩放级别可能是不同年份、不同倾斜角度的影像。
- 17 级约 1.1 m/像素看片区；19 级约 0.28 m/像素看单栋楼；7–9 级给 `sun.py locate --mosaic` 当底图。

## 街景与实景

| 来源 | 许可与限制 | 用法 |
|---|---|---|
| Mapillary | 官方 Graph API v4，`MAPILLARY_TOKEN`；图像 CC BY-SA 4.0，可下载、缓存、做视觉分析，证据图写 “© Mapillary contributors” | `mapillary.py`；批量比对首选；欧美日、东南亚城市覆盖好，国内很少；普通照片只朝一个方向，全景可任意朝向 |
| 百度全景静态图 | 百度地图开放平台官方接口，`BAIDU_MAP_AK`（服务端应用；设为 SN 校验时另配 `BAIDU_MAP_SK`，由 `providers.baidu_url` 按官方算法签名）；按坐标取最近全景，不给 id、路名、日期；**属高级权限、需付费开通**（个人可联系百度申请 15 天试用），未开通返回 status 240「APP 服务被禁用」；地点检索等普通服务免费 | `baidu_pano.py`；国内主力；不缓存、单次 ≤150 张；`coordtype=wgs84ll` 由百度换算坐标 |
| Google Street View Static API | 官方，`GOOGLE_MAPS_API_KEY`；元数据免费、出图计费；只给最新一批；条款禁止批量下载和缓存 | `gsv.py`；国外少量候选的人工确认；单次 ≤60 张 |
| KartaView | 众包街景，覆盖少 | 人工 |
| 地图 POI 图片、酒店/景区网上实拍、游客照 | 各站条款 | 没有街景时比天际线、楼形；拍摄角度不可控 |

- heading 一律是罗盘方位，0 = 正北，顺时针。
- 全景静态图未开通时：在浏览器里打开百度地图网页版的全景，人工看少量点（和 Google 一样只做人工查看，不批量抓取）。
- 国内：Google 街景基本没有，Google 3D 贴地无立面；腾讯街景旧且未接入；高德无公开街景接口。百度全景只沿市政道路，公园步道、校园、小区内部基本没有。
- 百度街景国内多为 2017–2019 年采集，新楼看不到；小区内部基本没有。

## 搜索

| 来源 | 擅长 | 用法 |
|---|---|---|
| 百度识图 | 中文网页、微博、百家号、电商、景区；会给"图中可能是…" | `revimg.py`（自动化、会上传，先征得同意），或在用户浏览器里手动传图 |
| Yandex 图片 | 建筑、街景、外国内容；给标签和来源站 | 同上 |
| Google Lens | 认"这是什么"（物种、车型、雕像、景点），常比百度 Yandex 强 | 服务器出口会被要求验证；有浏览器操作工具时在用户浏览器里用；AI 概览会凭相似图硬报地名 |
| 必应国内版、百度图片、搜狗图片 | 中文关键词网页和图片搜索 | `revimg.py --query`；百度网页搜索会弹验证，不用 |
| 抖音、小红书、微博 | 网红打卡点、景区官方号、同城内容 | 网页搜索或用户协助 |
| 房产网楼盘相册（安居客、房天下、楼盘网等） | 新楼盘、商业综合体，相册里有立牌 | 网页搜索楼盘名 |
| 旅游点评站（Tripadvisor、携程） | 雕像、公园、景点用户图 | 网页搜索 |
| 图库（视觉中国、Getty、Alamy） | 图片说明带精确地名、年代 | 网页搜索 |
| 地方政府、地方媒体网站 | 核对景区、塔、雕像的名称和尺寸 | 网页搜索 |

## 地名 → 坐标（国内）

| 来源 | 说明 |
|---|---|
| 高德 Web 服务地点搜索 v5 | `AMAP_KEY`，直连；小区、楼盘、店铺、单位覆盖好；GCJ-02（`poi.py` 已转 WGS84） |
| 百度地图地点检索 v2 | `BAIDU_MAP_AK`，直连；同上；不给城市时返回全国各城市同名结果数 |
| OpenStreetMap Nominatim | 免密钥，遵守每秒 1 次的使用政策；有名字的小区、公园、道路；WGS84 |

## 地名 → 坐标（国外）

- `poi.py "<地址或地名>" --sources osm --country <两位国家代码> --proxy socks5h://127.0.0.1:10808`（Nominatim，WGS84）。门牌地址搜不到时去掉门牌号只搜街道 + 区名。

## 地面照片（没有街景时）

| 来源 | 说明 |
|---|---|
| 新闻、百科、企业官网、博客配图 | 先给设施找名字（OSM 名字、附近地名 + 当地语言的设施类型词）再搜；乡间厂房、废弃设施常只有这一种地面照片 |
| Wikimedia Commons 按坐标搜图 | `commons.wikimedia.org/w/api.php?action=query&list=geosearch&gscoord=<lat>|<lon>&gsradius=10000&gsnamespace=6&format=json`，免 key、走代理；偏远地区常只有几张 |
| Mapillary | `mapillary.py near`；乡村道路常有众包图像 |
| KartaView | 接口免 key，覆盖很少 |

## 专题图与结构化数据

| 来源 | 用途 | 已知问题 |
|---|---|---|
| OpenStreetMap Overpass | 要素共现、线变点、线路走廊、线交叉、街景模板、沿路取点、大建筑 | `osm.py`；公共服务器常忙或限流（脚本换镜像重试，结果带 remark 会提示不全）；**上百公里的范围加名字正则（`[~"name"~...]`）常超时**，去掉正则或分区查；国内县乡建筑、停车场基本为空，江河常只有中心线 |
| OpenRailwayMap（openrailwaymap.org） | 铁路等级、单双线、电气化、车站 | 网页人工看；数据同 OSM |
| OpenInfraMap（openinframap.org） | 输电线路和电压、变电站 | 网页人工看；电压可能没标 |
| AWS Terrain Tiles（Terrarium） | 全球约 30 m 高程 | `terrain.py`；细节小于百米不可靠 |
| 城市开放数据 | 行道树（树种、胸径、位置）等 | 国外城市多，国内少 |

## 时间与天气

| 来源 | 用途 |
|---|---|
| `sun.py`（NOAA 算法，和 NREL SPA 差 ≤0.02°） | 太阳位置，替代 SunCalc |
| 历史逐日天气（气温、晴雨） | 核对"结冰""晴天"；有日期时排除阴雨地区 |
| 历史气象卫星云图 | 当天大片云区排除（台风、锋面时才有明显效果） |
| Flightradar24、FlightAware | 按注册号查航班历史；付费档可下载 KML/CSV 航迹 |

## 网络

- 代理（`--proxy` 或环境变量 `GEO_PROXY`，例如 `socks5h://127.0.0.1:10808`）只在直连不通时用；国内访问 Google、Overpass、Yandex、Mapillary、HuggingFace 常需要。
- 直连：百度、高德、必应国内版。高程切片两种都行。
- macOS 没有 `timeout` 命令；zsh 的 for 循环里 `$var` 不分词（写 `${=var}` 或用 `bash -c`）；zsh 里 `echo =====` 这类以 `=` 开头的词会被当成命令路径展开而报错，分隔线用 `-----`。
- `revimg.py` 用的 Chrome 代理写 `socks5://`（脚本会自动把 `socks5h://` 改掉）。
- 国外新闻站 WebFetch 报 "Socket closed" 时，改 `curl -s -A 'Mozilla/5.0' --socks5-hostname 127.0.0.1:10808 <url>` 抓 HTML 再提正文。
