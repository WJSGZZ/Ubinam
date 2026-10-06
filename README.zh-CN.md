<div align="center">

# Ubinam

**这张照片在哪拍的、什么时候拍的？一个会查清楚、拿真实地图数据核对、并把过程摆出来的 Agent 技能。**

*Ubinam* 是拉丁语，意思是“究竟在哪里”。

[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

把一张照片或一整组照片交给你的 agent，问它在哪拍的。Ubinam 会读出画面里的每块招牌、每个地标，用脚本给候选地点排序，再拿卫星图、街景、地形和地图数据库逐一核对。最后给出坐标、误差半径，以及国家、城市、街道、楼各级分开的置信度，每一级都附上证据链。

它是标准的 [Agent Skill](https://agentskills.io)：一个文件夹，里面是 `SKILL.md`、普通 Python 脚本和参考笔记。Claude Code、Codex、Cursor、Gemini CLI、OpenCode、GitHub Copilot，以及任何能读 `SKILL.md`、能跑命令行的 agent 都能用。

## 为什么用 Ubinam

- **核对，而不是猜。** 每个“已核实”都必须对应一条实际跑过的命令和它产出的文件；排除要有证据；误差半径小于 100 米必须有两条独立约束。候选盘由脚本强制执行，防止模型挑“长得像的地方里最有名的那个”。
- **靠几何，不靠感觉。** 能从 EXIF 或消失点求焦距，拿地平线当尺量距离和高度，用卫星图上的影子比楼高，用三个以上已知地标反解机位，用三个地物的视差把拍摄点夹到路上某一段，用高程数据渲染山脊天际线，比对海岸线形状，计算太阳位置。
- **整组照片一起看。** 先定位有招牌、好认的几张，划出范围，再回头查难的那张；所有拍摄点可以标在同一张卫星图上，按把握从高到低排列。
- **也能推拍摄时间。** 有影子用太阳几何算；没有影子就看有日期的证据：节日布置、施工进度、历史天气、天色和人流。Esri Wayback 提供 2014 年以来每一版卫星图和每张影像的真实拍摄日期，某栋楼首次出现在哪一版，就能给拍摄年份定区间；Sentinel-2 约 5 天一景，能把施工、改造推到月份。几何算出的结论和常识推断分开写。
- **为中国准备好了。** 内置高德、百度地点检索，WGS84、GCJ-02、BD-09 坐标互转，车牌、区号、文字等查表，以及没有 Google 街景时用百度全景的流程。
- **数据来源干净。** 只用官方接口或开放许可的数据：Esri 和 Sentinel-2 影像、Mapillary（CC BY-SA）、OpenStreetMap，以及用你自己密钥调用的百度、高德、Google 官方接口。不抓取任何未公开接口。
- **自带第二意见。** [GeoCLIP](https://github.com/VicenteVivan/geo-clip) 只凭画面给出独立的粗略位置，[MegaLoc](https://github.com/gmberton/MegaLoc) 用视觉地点识别给街景候选排序。
- **游戏用的快速模式。** GeoGuessr 这类限时游戏里，读图、放大、查表后直接下判断；按距离计分的游戏另有下注规则。

## 实测成绩

都是真实照片，先冻结判断再看答案：

| 照片 | 结果 |
|---|---|
| 隔江的酒店窗景，读得出两家银行招牌 | 用地标坐标反解机位，认出酒店，误差约 20 米 |
| 东南亚城市堵车街景，楼上一块品牌招牌 | 查品牌公司地址定到商场，再用街景视差把机位夹到离真实位置约 30 米 |
| 海上日落，没有任何文字 | 海岸线形状比对选中正确的海湾和小岛，GeoCLIP 第二意见一致 |
| 一组 14 张城市照片 | 9 个拍摄点标在同一张地图上；最难的湖景是靠水面倒影里的餐厅名破解的 |
| 黄昏的斜拉桥，没有文字 | **错了约 190 公里**：在几座外形相近的桥里选错了一座（见“局限”） |

## 工作方式

| 层 | 谁做 | 工具 |
|---|---|---|
| **决策**：候选有哪些、证据怎么加权、能否排除、下一步做什么 | 脚本（候选盘） | `board.py` |
| **感知**：读字、查表、给卫星图格子和街景图排序 | 脚本先排，模型只看前几名 | `intake.py` `ocr.py` `clues.py` `poi.py` `sat_scan.py` `match.py` |
| **判断**：从画面提线索、提出假设、在排好的前几名里裁定 | 模型 | `SKILL.md` + `references/` |

完整脚本清单、数据源和许可见 [`skills/ubinam/references/data-sources.md`](skills/ubinam/references/data-sources.md)。

## 安装

```bash
git clone https://github.com/WJSGZZ/Ubinam
cp -r ubinam/skills/ubinam ~/.agents/skills/              # Codex、Cursor、Gemini CLI、OpenCode、GitHub Copilot
ln -s ~/.agents/skills/ubinam ~/.claude/skills/ubinam     # Claude Code
```

需要 Python 3.10+ 和 [`uv`](https://docs.astral.sh/uv/)。每个脚本自己声明依赖，`uv run` 第一次运行时自动安装；`match.py`、`sat_scan.py`、`prior.py` 第一次会下载 PyTorch 和模型。

## 密钥（全部可选）

没有任何密钥也能跑：查表、太阳和地形几何、OpenStreetMap 查询、Sentinel-2 影像都不需要密钥。每多配一个，就多解锁一部分：

| 环境变量 | 服务 | 解锁什么 |
|---|---|---|
| `ARCGIS_API_KEY` | [ArcGIS Location Platform](https://location.arcgis.com)（有免费额度） | 近年的高清卫星图；z17 以上的卫星图扫描 |
| `MAPILLARY_TOKEN` | [Mapillary 开发者](https://www.mapillary.com/dashboard/developers)（免费） | 全球街景批量比对，国内不少城市主干道也有 |
| `AMAP_KEY` | [高德开放平台](https://lbs.amap.com)（选“Web 服务”） | 国内地点搜索 |
| `BAIDU_MAP_AK` / `BAIDU_MAP_SK` | [百度地图开放平台](https://lbsyun.baidu.com) | 国内地点搜索（应用设为 SN 校验时才需要 SK）；全景静态图需付费开通 |
| `GOOGLE_MAPS_API_KEY` | [Google Maps Platform](https://developers.google.com/maps) | 少量人工核对用的街景和卫星图 |

运行 `python3 skills/ubinam/scripts/providers.py list` 可以看到哪些数据源可用、各自许可允许做什么。

## 局限

用之前值得知道这几点：

- **长得像的建筑。** 没有文字时，很多桥、塔、住宅楼都有“双胞胎”。Ubinam 会先把外形相近的候选列全再选，但仍可能选错。
- **街景只到马路。** 公园、校园、湖边、小区内部基本没有街景，在这些地方拍的照片只能靠卫星图结构和网上照片确认，置信度会低一些。
- **影像会过时。** 去年刚改造的湖，在旧影像上可能完全是另一个样子。Ubinam 排除候选前会先查卫星图是哪天拍的、再看现在的照片，但旧数据仍可能误导。
- **模糊的字救不回来。** AI 放大只会让猜出来的笔画看起来清楚，所以不当证据用；视频有帮助，因为多帧叠加里有真实的额外细节。
- **模型会出错。** 所以每一级都单独给置信度，方便你判断能信到哪一步。

## 负责任地使用

用在自己拍的照片、公共场景、新闻图片，或得到许可的照片上。不要用它去找不愿被找到的人。照片显示的是某个私人的住处或当下行踪、且目的是找到这个人时，技能最多给到城市级。它定位的是照片，不会根据一个人的一组照片去推断他住在哪。

## 基于 geo-sleuth

Ubinam 以 Oldcircle 的 [**geo-sleuth**](https://github.com/Oldcircle/geo-sleuth)（MIT 许可）为基础，导入了它的完整提交历史。核心方法来自原项目：候选盘、写成代码的规则、“脚本排序、模型判断”、天际线和桥墩间距几何。Ubinam 把原项目里未公开的 Google、百度、360 接口全部换成官方接口或开放数据，并新增了国内地点检索、整组照片互相约束、街景视差定机位、无影子推拍摄时间、GeoCLIP 和 MegaLoc、快速模式和回归案例。

## 许可与致谢

- 代码：MIT，见 [LICENSE](LICENSE)。Copyright © 2026 Oldcircle（geo-sleuth）及 © 2026 Xik（Ubinam 的修改）。
- `skills/ubinam/data/` 里源自维基百科的查表数据为 CC BY-SA 4.0，详见 [`data/README.md`](skills/ubinam/data/README.md)。行政区划数据来自 [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China)。
- 实时数据各有许可，发布结果时请署名：© OpenStreetMap contributors（ODbL）；Sentinel-2 cloudless by EOX（CC BY 4.0）；Contains modified Copernicus Sentinel data（经 Element84 Earth Search）；© Mapillary contributors（CC BY-SA 4.0）；Esri、Google、百度、高德数据按各自服务条款；AWS Terrain Tiles。
- 模型：DINOv2（Meta AI）、CLIP（OpenAI）、[GeoCLIP](https://github.com/VicenteVivan/geo-clip)（MIT）、[MegaLoc](https://github.com/gmberton/MegaLoc)（MIT）。
