<div align="center">

# Ubinam

**给 agent 一张照片，它告诉你在哪拍的、什么时候拍的，并且拿出证据。**

*Ubinam* 是拉丁语，意思是“究竟在哪里”。

[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

大多数 AI 看图定位，给你一个很自信的答案就结束了。Ubinam 更像一个调查员：读完画面里每一块招牌，把可能的地点全部列出来，再拿卫星图、街景、地形和地图数据逐个核对，只留下经得起核对的结论。

你会拿到：

- **带误差半径的坐标**：说的是“误差 30 米以内”，不只是一个城市名。
- **每一级单独的把握**：国家、城市、街道、楼、楼层分开判断，楼认不准不影响街道的把握。
- **证据**：标好机位的卫星图和并排对比图，每一张都对应一条实际跑过的命令。
- **老实的停止**：照片只够定到“这一片”，就说到这一片，并说明还缺什么信息。

它是一个 [Agent Skill](https://agentskills.io)：一个文件夹，里面是说明文档和普通 Python 脚本。Claude Code、Codex、Cursor、Gemini CLI、OpenCode，以及任何能读 `SKILL.md`、能跑命令行的 agent 都能用。

## 实测成绩

都是真实照片，先写下答案，再看真值。

| 照片 | Ubinam 怎么做的 |
|---|---|
| 东南亚城市堵车街景，楼上只有一块品牌招牌 | 查到这个品牌分公司的地址，定位到商场，再把机位定在离真实位置**约 30 米**处 |
| 隔江的酒店窗景 | 用画面里几个地标反推出机位，认出是哪家酒店，误差**约 20 米** |
| 海上日落，没有一个字 | 比对海岸线形状，找到对应的海湾和小岛 |
| 同一座城市的 14 张照片 | **12 张**标到同一张地图上，另外 2 张直接说定不到，不硬猜。其中一张夜景**水面倒影里的餐厅名**，还顺带破解了另一张完全没有招牌的湖景 |
| 黄昏的斜拉桥，没有文字 | **错了约 190 公里**：在几座长得很像的桥里选错了一座。错的我们也列出来 |

## 能做什么

**找到地方**
- 读招牌、车牌、电话号码、路边设施，按国家查表。
- 从品牌名查到公司或分店地址，把“能看见塔的桥”这样的场景翻译成地图查询。
- 卫星图格子、街景图片成千上万张，先由脚本排序，模型只看前几名。

**定到具体机位**
- 地图上认得出三个以上地标，就能反推拍摄者站在哪里。
- 根据远近物体在画面里的错位，把路上的拍摄点缩到几十米内。
- 用高程数据渲染山的轮廓，和照片里的山对比。

**推拍摄时间**
- 有影子，用太阳位置算时刻和朝向。
- 没影子，就看有日期的证据：2014 年以来带真实拍摄日期的历代卫星图，Sentinel-2 约 5 天一张、能把施工和改造推到月份，还有节日布置和历史天气。

**一次处理一组照片**
- 先定位好认的几张，划出范围，再回头查难的。
- 所有拍摄点标在同一张地图上，每个点旁边配上对应的照片。

**国内也能用**
- 内置高德、百度地点检索，国内三套坐标系互转，没有 Google 街景时有百度全景的流程。

**玩 GeoGuessr**
- 快速模式：读图、放大、查表，然后下判断；按距离计分的游戏另有下注规则。

## 为什么结论可信

关键规则由脚本强制执行，不靠模型自觉：

- **不编造核验。** 说“街景对上了”，就必须有本次生成的比对文件。
- **排除和确认用同一个标准。** 凭感觉只能把候选往后排，不能把它划掉。
- **名气不是证据。** 不许直接挑长得像的地方里最有名的那个，所有候选先上记分板再排名。
- **精度要有依据。** 误差半径小于 100 米，必须有两条互相独立的证据。

## 安装

```bash
git clone https://github.com/WJSGZZ/Ubinam
cp -r Ubinam/skills/ubinam ~/.agents/skills/              # Codex、Cursor、Gemini CLI、OpenCode、GitHub Copilot
ln -s ~/.agents/skills/ubinam ~/.claude/skills/ubinam     # Claude Code
```

装好后，发一张照片给 agent，问“这是在哪拍的”就行。

需要 Python 3.10+ 和 [`uv`](https://docs.astral.sh/uv/)。每个脚本自己声明依赖，`uv run` 第一次运行时自动安装。图像比对脚本（`match.py`、`sat_scan.py`、`prior.py`）第一次会下载 PyTorch 和模型。

## 密钥（全部可选）

一个密钥都不配也能用：查表、太阳和地形几何、OpenStreetMap、Esri 历代卫星图、Sentinel-2 都免费。每多配一个，就多一项能力：

| 环境变量 | 服务 | 多出什么 |
|---|---|---|
| `ARCGIS_API_KEY` | [ArcGIS Location Platform](https://location.arcgis.com)（有免费额度） | 最新的高清卫星图，近距离卫星图扫描 |
| `MAPILLARY_TOKEN` | [Mapillary 开发者](https://www.mapillary.com/dashboard/developers)（免费） | 全球街景批量比对，国内不少城市主干道也有 |
| `AMAP_KEY` | [高德开放平台](https://lbs.amap.com)（选“Web 服务”） | 国内地点搜索 |
| `BAIDU_MAP_AK` / `BAIDU_MAP_SK` | [百度地图开放平台](https://lbsyun.baidu.com) | 国内地点搜索（应用设为 SN 校验时才需要 SK）；全景需付费开通 |
| `GOOGLE_MAPS_API_KEY` | [Google Maps Platform](https://developers.google.com/maps) | 少量人工核对用的街景和卫星图 |

运行 `python3 skills/ubinam/scripts/providers.py list` 可以看到哪些数据源可用、各自许可允许做什么。Ubinam 只用官方接口和开放许可的数据，不抓取任何未公开接口。

## 局限

- **长得像的建筑。** 没有文字时，很多桥、塔、住宅楼都有“双胞胎”。Ubinam 会先把相似的全部列出来再选，但仍可能选错。
- **街景只到马路。** 公园、校园、湖边、小区内部基本没有街景，在这些地方拍的照片把握会低一些。
- **卫星图会过时。** 去年刚改造的湖，在旧卫星图上可能完全认不出。Ubinam 排除一个地点前会先查卫星图是哪天拍的，但旧数据仍可能误导。
- **模糊的字救不回来。** AI 放大会凭空补笔画，所以不当证据用。视频不一样：多帧叠加能恢复真实细节，Ubinam 会这样做。

## 负责任地使用

用在自己拍的照片、公共场景、新闻图片，或得到许可的照片上。不要用它去找不愿被找到的人。照片显示的是某个人的住处或当下行踪、而目的是找到这个人时，技能最多给到城市级。它定位的是照片，不会根据一个人的一组照片推断他住在哪。

## 基于 geo-sleuth

Ubinam 以 Oldcircle 的 [**geo-sleuth**](https://github.com/Oldcircle/geo-sleuth)（MIT 许可）为基础，导入了它的完整提交历史。核心方法来自原项目：候选记分板、写成代码的规则、“脚本排序、模型判断”、天际线和桥墩间距几何。Ubinam 把原项目里未公开的 Google、百度、360 接口全部换成官方接口或开放数据，并新增了国内地点检索、整组照片互相约束、沿路定机位、用历代卫星图和 Sentinel-2 推拍摄时间、多帧叠加读字、GeoCLIP 和 MegaLoc、快速模式和回归案例。

## 许可与致谢

- 代码：MIT，见 [LICENSE](LICENSE)。Copyright © 2026 Oldcircle（geo-sleuth）及 © 2026 Xik（Ubinam 的修改）。
- `skills/ubinam/data/` 里源自维基百科的查表数据为 CC BY-SA 4.0，详见 [`data/README.md`](skills/ubinam/data/README.md)。行政区划数据来自 [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China)。
- 实时数据各有许可，发布结果时请署名：© OpenStreetMap contributors（ODbL）；Sentinel-2 cloudless by EOX（CC BY 4.0）；Contains modified Copernicus Sentinel data（经 Element84 Earth Search）；© Mapillary contributors（CC BY-SA 4.0）；Esri、Google、百度、高德数据按各自服务条款；AWS Terrain Tiles。
- 模型：DINOv2（Meta AI）、CLIP（OpenAI）、[GeoCLIP](https://github.com/VicenteVivan/geo-clip)（MIT）、[MegaLoc](https://github.com/gmberton/MegaLoc)（MIT）。
