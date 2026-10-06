---
name: ubinam
description: 照片拍摄地点定位（看图找地点 / 网络迷踪 / 图寻 / GeoGuessr / 推拍摄时间）。分快速模式（只看图、放大、搜索，适合限时游戏和国家省级判断）和深度模式：给一张或几张照片，先一条命令做完元数据、OCR（intake.py，以图搜图需用户同意后加 --rev），把线索和候选记到候选盘（board.py）上由脚本排名、给下一步；查表线索用 clues.py；卫星图和街景都是"机器先排序、人只看前几名"（sat_scan.py、match.py）；每个结论都用真实数据核对，输出坐标 + 误差半径、证据图和分档置信度。Geolocate or chronolocate a photo with tool-verified reasoning using only official APIs or openly licensed data — EXIF, OCR, opt-in reverse image search, lookup tables (plates, area codes, calling codes, driving side, territories), candidate board with likelihood ranking, sun and shadow math, OSM Overpass, CLIP-ranked satellite scan, DINOv2+SIFT-ranked street-level matching (Mapillary, Baidu, Google official), DEM skyline rendering. Use when the user shares a photo and asks 这是哪 / 在哪拍的 / 帮我定位这张照片 / 网络迷踪 / 几点拍的 / where was this taken / geolocate this.
---

# Ubinam · 到底在哪里

> Ubinam（拉丁语“究竟在哪里”）基于 [geo-sleuth](https://github.com/Oldcircle/geo-sleuth)（MIT，Oldcircle）改进。下文“流程”及之后的深度模式主体来自原项目，快速模式、计分游戏、练习计分和上传规则为本项目新增。

目标：找到一个**经得起核对**的地点，每个结论都能指出用了哪条线索、跑了哪个命令、产出了哪个文件。

> 命令里的 `${CLAUDE_SKILL_DIR}` 指本 SKILL.md 所在目录（references 里的命令也一样）。Claude Code 会自动替换；其他 agent 先 `export CLAUDE_SKILL_DIR=<本目录的绝对路径>` 再跑（shell 不跨命令保留变量时，每条命令前都带上这句），或者直接把它换成这个路径。

## 选模式

- **快速模式**：限时游戏、只需国家／省级、日常随手问。不跑 intake 和候选盘，只看图、`imgprep.py zoom` 放大、`clues.py lookup` 查表、搜索和地图，按下面五步走；卡在城市级以上或需要街道级时转深度模式。
  0. 先估上限：看完线索清单后，判断这张图凭现有信息最细可能定到哪一级（有可读地名或独有地标→点；只有独特轮廓组合→片区；只有同类常见设施、普通室内→国家或大区，甚至无法判断），并写出要定得更细还缺什么。结论不超过这个上限；用户想要更细时，先说明需要补什么，而不是硬给精确坐标。室内照片优先找窗外景、文字与品牌、插座开关制式，其次才是装修风格。
  1. 列线索清单再猜：四边四角和远处每块牌子、每辆车都放大看；按 `references/observe.md` 的层级和 `references/clues/quick-reference.md` 分 A／B／C 级。
  1.5 可选第二意见：`prior.py photo.jpg` 用 GeoCLIP 给出 top-5 经纬度，只当一条独立线索（inferred）；它和你的判断冲突时去找区分线索，前几名分散在几个大洲时说明可定位上限低。
  2. 至少写 3 个候选，各配支持与冲突线索，再找最能区分它们的那一条去看或查；A 级一条压倒多条 C 级，同源线索不算独立。
  3. 逐级缩小，每级重复“候选—区分—核验”。
     以图搜图放在最后、且可选：先不搜，靠自己的线索列全候选并冻结判断；只有画面里有可能被大量拍过的对象（地标、景区、网红店门头、连锁店面）时才搜，搜到的结果只用来核对已列候选，不能用来定城市或新增唯一答案。普通街巷、室内、常见设施不搜（实测一次带偏约 193 km、一次只认出“罗马帘”，两次成功都没用它）。
     以图搜图给出的地名只是一条单一来源线索：先列出同类外形的全部候选（同一水系、同一塔型的桥、楼、景点），用外形细节或几何逐个区分，再决定是否采信；来源帖打不开、无法确认对象时，结论最多“中”，并把同类候选写进备选。
     推测出的条件（日出还是日落、朝向、季节、拍摄顺序）不写进搜索约束：先不加限制地搜，再看结果是否推出同样的结论；推得出才算证据，推不出就保持为未定。
     招牌上的品牌不是门店而是制造商、公司（饼干厂、面包厂的招牌挂在楼上）时，查它的办公地址、分公司、办事处：招牌常挂在自家办公所在的楼上（实测一例由饼干品牌的分公司地址直接定到商场）。找到候选建筑后，用 OSM 列出周边每栋楼的名字和轮廓，再搜各楼的外观照片逐栋认画面里的楼。
     有街景时定机位用“视差夹逼”（`references/verify.md` 第 4 节末），地物坐标都认得出时用 `pose.py along` 直接沿路算；国内没有 Google 街景，Google 3D 贴近地面也是平的，只能靠百度全景（沿市政道路）、地图 POI 实拍和几何。
     画面里有 ≥3 栋认得出、能在 OSM 或地图上查到坐标的地标时，直接做后方交会：在候选范围内逐点算各地标方位角，和照片里的左右位置（像素列）拟合，同时解出镜头朝向和视角；视角接近常见手机焦段、且“没出现在画面里的地标”按解算确实落在框外，才算自洽（`pose.py solve` 或同等的方位拟合）。解算出的点再去对附近的酒店、楼盘名单逐个打分。
  4. 先在聊天里写下判断（各级置信度、最佳单点、误差半径），再下注或提交。
  5. 下面的硬规则同样适用，尤其 1、3、5、8、10。
- **深度模式**：从“工作方式分三层”起全文。

**计分游戏的例外**：GeoGuessr 类按距离给分，同一国家内两个邻近候选分不开时，下注在两者之间可能期望得分更高；这是下注策略，不是判断，报告里仍以第一名为主答案（硬规则 8 不变）。网页游戏的小地图要悬停才展开、窗口尺寸会变，每次在同一批操作里悬停、点击、截图确认。

**上传和重依赖先问**：`intake.py --rev` 和 `revimg.py` 会把照片上传到百度、Yandex（默认不做）；`sat_scan.py`、`match.py` 首次要装 PyTorch 并下载模型。照片涉及用户本人、他人面孔或住处时，上传前先征得同意。

**数据源只用官方接口或开放许可**（`providers.py list` 查看哪些已配密钥）：卫星图 Esri（`ARCGIS_API_KEY`）或 Sentinel-2（免密钥、10 米、最高 z15）；Google 卫星图只能人工看少量瓦片，不能批量扫描；街景批量比对用 Mapillary（`MAPILLARY_TOKEN`），百度（`BAIDU_MAP_AK`）和 Google（`GOOGLE_MAPS_API_KEY`）官方街景不缓存、单次 150／60 张以内；国内地点搜索用高德（`AMAP_KEY`）或百度。缺密钥就说明缺什么、降级做什么，不改回非官方接口。

**本机说明**：`references/local.md` 若存在（个人本地配置，不随仓库发布），开始前先读它。

**工具要主动用，不等用户点名**：开始时跑一次 `providers.py list` 看哪些密钥可用，然后每遇到下表左列的情况就直接用右列的工具；某个工具这次没用，结论里写一句为什么（缺密钥、没覆盖、和问题无关）。实测多次：地图出入口查询、Mapillary 实景、高清卫星图都是用户问了才想起用。

| 手里有什么 / 想知道什么 | 先用 |
|---|---|
| 任何能读的字：店名、楼名、单位名、门牌、路名 | `poi.py`（高德+百度+OSM，同名全列；连锁店先按门店分布排）；出入口、楼栋、院区分部也能搜（“XX医院 东门”“门急诊楼”） |
| 一组照片 | 先定位有字的几张划范围，再回头查难的（`references/verify.md`“同一组照片互相约束”） |
| 有候选点，要看现状 | `tiles.py fetch --zoom 17–19`（Esri 高清，近年影像）；比 Google 网页卫星图新，排除前先看它 |
| 候选地点可能改造过、或想知道照片是哪年拍的 | `wayback.py meta`（这里的卫星图哪天拍的）、`changes / sheet`（Esri 历代影像，2014 起，免密钥）：看楼、桥、岸线哪一版出现或消失；排除候选前先 meta 看影像是不是早于改造 |
| 有视频或连拍、字模糊 | `frames.py stack`（多帧对齐叠加，结果可当 read 级；单图 AI 超分不行） |
| 要按“画面里同框的几样东西”在地图上找 | `references/osm-tags.md` 查标签 → `osm.py near`；国内点状地物 OSM 漏标多，改用 `poi.py` |
| 要把时间推到月份（施工、湖岸改造、农田季相） | `s2time.py sheet --monthly`（Sentinel-2，2017 起约 5 天一景，免密钥，10 米） |
| 有候选点，要看地面 | 国外 `mapillary.py scan`（国内城市主干道也常有 2024 年全景）→ `match.py`；国内再加百度网页版全景人工看；公园、校园、湖边内部搜游客照和效果图 |
| 认出一栋楼，不知道名字 | OSM 周边楼名 + `poi.py` 周边 POI，再搜各楼外观照片逐栋比 |
| 远处有山 | `terrain.py profile / view` 算天际线 |
| 画面里 ≥3 个已知地标 | 后方交会（`pose.py solve`） |
| 拍摄者在某条路上、≥3 个地物坐标已知 | 沿路视差夹逼（`pose.py along --line …`），给最优点和路段区间 |
| 没有文字、没有地标 | `prior.py`（GeoCLIP）给粗范围；`sat_scan.py` 按场景描述扫卫星图 |
| 想知道拍摄时间 | `references/sky.md`：影子 → `sun.py`；没影子按“时间线索”一节 |
| 模糊的字、二维码 | `imgprep.py zoom` + `ocr.py`；二维码 `cv2.QRCodeDetector`；有视频先多帧叠加 |

工作方式分三层，先记住这个，再看流程：

| 层 | 谁做 | 工具 |
|---|---|---|
| 决策：候选有哪些、证据怎么算分、能不能排除、下一步扫哪 | **脚本**（候选盘） | `board.py` |
| 感知：读字、查表、卫星图上找目标、街景比对 | **脚本先算先排，人只看前几名** | `intake.py` `ocr.py` `clues.py` `sat_scan.py` `match.py` `geo.py bearings` |
| 判断：从画面里提线索、查表没有时提假设、在机器排好的前几名里裁定 | **你** | — |

方法来自 14 个网络迷踪博主视频、22 道题的拆解和多轮盲测对照；拆解笔记不随仓库发布。v1 的教训：规则写成散文不会被执行，同一版 skill 两次跑结果差很大；所以 v2 把能写成代码的规则都放进了 `board.py`。

## 硬规则（全程有效；标 ★ 的由 board.py 强制，你照做就行）

0. 用户说照片不是自己拍的，或画面里是私人住处、未成年人，先问一句用途再继续；提示里已写明来源或用途（评测题、出题人提示、用户明说是自己拍的）时不问，照常做到最细一级。
1. **不编核验**。"在地图上量过""街景对上了""±10 m"必须对应本次会话里实际跑过的命令和产出的文件。没跑过就写"未核实"。
2. **精度要有出处**：误差半径 ≤100 m，必须有两条独立约束的交会，或实景比对 ≥3 项不变特征。报机位前先跑一次自检：`pose.py project --horizon <海天线行号>` 会算出 pitch 该是多少、各地物按当前机位"应落在第几行"，和照片对账（目标的俯角 ≠ 相机的俯仰角；机位高程用 `terrain.py elev` 查，高差和画面俯角对不上就是机位错了）。
3. **找到唯一锚点就闭环**：后面的搜索和几何都从锚点出发，不再回到"湖水蓝绿""热带公园"这类泛化特征挑同类里最有名的地方。
4. **先算方位，再认构件**：照片里的塔、烟囱对应卫星图上哪个方块本身是解读。先用 `sun.py compass` 或已确认地标算出它在画面里的真实方位，再用 `geo.py bearings` 看候选机位周围哪个轮廓落在那个方位上；对不上时先做"原图/镜像""日出/日落"双模板，没核实就只降档不排除。
5. ★ **类别推断先列全**：从"山城""热带""IP 直辖市"推地区时，`board.py children` 把全部下级行政区加进候选，再用证据排。不默认主城，不按人口挑。
6. **元数据和提示都是假设**：EXIF、IP 属地、定位标签、出题人的话和画面冲突时以画面为准，不编故事去圆。IP 是 A 国、提示或制式指向另一大洲：`clues.py lookup territories <A国> --continent <洲>` 求交集。**不拿用户本人的背景（住址、学校、档案、过往聊天里的行踪）当先验**：只用照片和用户这次明说的提示；用户要求时也只能当待核线索。
7. **自洽性**：关键判断换一个裁剪或一组关键词重做一次，两次结果差几十公里以上就降档。
8. ★ **定不到点就给区间 + 缺什么信息**；候选是离散的几个时不取中点：`board.py report` 的主答案永远是第一名，其余进备选并写区分检验。
9. ★ **排除和确认用同一个标准**：`board.py exclude` 只接受 read/computed 级线索 + 算过的文件（`geo.py frame`、`terrain.py` 等的产出）；观察和推测只能 `evidence --against` 降权，似然比被夹在 1/3–3（推测）或 1/5–5（观察）。用"附近有 X"生成候选也是过滤，X 必须是画面里确认过的东西。校园、小区、街段这类细层候选同样要进盘：一批的用 `board.py add --from <poi.py --out / osm.py geom 的输出> --level area/road` 一次全进，不手挑；放弃一个就写 `evidence --against` 附比对图，`check` 会列出一条证据都没有的（等于没看过）；第三方数据的标签（市政清单的树种、校名精确匹配）只能降权，不能当排除理由（两例都是真值被这样手动跳过）。**排除范围必须 ≤ 证据范围**：区县/片区/路这类有延展的候选，`exclude` 要用 `--covers lat,lon[:lat,lon]` 写明证据覆盖到哪一段，覆盖不足一半会被脚本拒（在一条路的一个点上看过就整条排除，两例都栽过）。
10. ★ **人口、名气不是证据**；扫描顺序按"份额 ÷ 页数"（`board.py next`）：小城区先扫完，大城区放最后并设页数上限。

## 流程

不必走满：第 1 步识图直接命中时，跳到第 6、7 步确认。每一步的产出都要进候选盘。

### 第 1 步：一条命令做完第 0–3 步

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/intake.py photo.jpg --out-dir intake/ [--box x0,y0,x1,y1 ...] [--rev] [--proxy socks5://127.0.0.1:10808]
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py init --photo photo.jpg
```

默认只做元数据、边缘图、变体和 OCR，不上传照片；用户同意上传后加 `--rev` 再跑以图搜图（一般 1–2 分钟，第一次装依赖更久，超时给够或放后台；被打断时识图子进程可能还在写 `rev/`，但不会生成 `intake.md`，别当成已经跑完）。

`intake.md` 里有：元数据、OCR 文字（放大/切块读出的标 pass=up/tile，是假设）、边缘图清单、失败项；加 `--rev` 时另有百度相似图片（来源站点计数 + 编号拼图）、识图标签分级计票、疑似小区/楼盘名。然后你做四件事：

- **看图**：`edges/` 四边四角逐张看；`references/observe.md` 的清单过一遍；每条线索 `board.py clue "<文本>" --kind <类> --status observed|read|inferred|computed --file <放大图>`。状态要诚实：读出来的字是 read，"楼大概 8 层""路在上坡"是 inferred。
- **查表**：车牌、区号、电话国家码、行驶方向、海外领地 → `clues.py lookup <kind> <value>`；能落到行政区的直接 `board.py apply --kind plate --value 渝G --file <放大图>`（自动加候选和证据，同级其余候选只降权不排除）。
- **识图结果**（只在第 2 步列全候选之后、且画面里有被大量拍过的对象时才跑 `--rev`）：先打开 `rev/<名>_baidu_similar.jpg`（左上角是查询图），找同一个物体或同一处场景的近重复照片，有就按编号去 JSON 的 `similar[i].from` 看来源页；标签里的小区名、楼盘名、酒店名 → `poi.py "<名>" --city <城市> --out pois.json` 落坐标，同名的（几个校区、几家分店）`board.py add --from pois.json --level area` 全部进盘再核；截图务必打开看，命中帖子后把同组照片也看一遍。检索处按物体类型选（`references/search.md`）。
- **提示与元数据**：逐条登记为 inferred 线索，写明可信度；IP 属地只说明发帖时人在哪，发帖时间不是拍摄时间。

### 第 2 步：候选列全、证据打分、看下一步

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py children <上级行政区名>          # 直辖市 → 全部区县；国家 → 一级行政区（gazetteer.py 查 OSM，带 bbox）
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py evidence --clue K1 --for <候选A>:5 --for <候选B>:2 --against <候选C>:0.3 --why "…" --file <比对图>
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py rank
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py next
```

`next` 只会说两种话：
- **分不开**：按便宜到贵做区分检验，每项对全部候选一起做——查表 → 地形（平原 vs 山城，`tiles.py fetch --zoom 13` 或 `terrain.py`）→ 车辆涂装（`revimg.py --query "<城市> <颜色> 公交"`，从结果图读线路牌，按区县比车尾腰线）→ 市政设施（`baidu_pano.py sample --bbox <建成区> --n 24`）→ 水系/路网模板。都做过仍分不开：不要停，按它给的"份额 ÷ 页数"顺序扫。
- **可以缩圈**：先 `board.py urban <候选>` 把范围缩到建成区（或 `scan-bbox` 手动给），再 `board.py falsify <候选> --text "…"` 写证伪条件，然后进第 3 步。

环境粗定位的规则仍在：地形先于河宽和建筑色；物候必须配月份；罕见设施组合取交集；认得出的物种只当排除工具；只有地类时先用土地覆盖图缩到那类地块（`references/clues/`）。

### 第 3 步：选分支缩圈

| 手里有什么 | 做法 | 读 |
|---|---|---|
| 唯一锚点（楼、雕像、塔、景区建筑） | 锚点几何：视线交会、对齐线、切线、按拍摄高度筛楼 | `geometry.md` |
| 远山、天际线 | `terrain.py view` 渲染候选机位比对，只定一条视线，再找第二条约束 | `geometry.md` |
| 清晰影子、受光面、太阳在画面里 | `sun.py locate / when / facing / compass`：地带、时刻、朝向、画面里物体的真实方位 | `sky.md` |
| 线路号、铁路或输电线规格、大河 | 线状走廊 + 线变点：`osm.py route / crossings / along` | `corridors.md` |
| 两三种基础设施同框 | `osm.py near --report`、两类线交叉 `osm.py intersect`（折角只标注不删） | `corridors.md` |
| 线状设施 + 认不出的山，没有文字 | 设施沿线接高程算地平线，整个大区过滤 → 天际线 + 设施距离数值打分 → 前 3–5 名叠图 → 等间距构件定机位：`terrain.py scan --lines … --out hits.json --clusters-out clusters.json` → `terrain.py ridge photo.jpg --x0 … --x1 … --out ridge.json` → `terrain.py fit --hits hits.json --ridge ridge.json [--line … --line-dist …] --sheet top.jpg --photo photo.jpg`（精搜换 `--at lat,lon --radius 800 --grid 100 --zoom 13`）→ `imgprep.py piers photo.jpg --rows … --out cols.json --sheet piers.jpg` → `geo.py spacing --cols … --line … --span … --center lat,lon --ridge ridge.json` | `corridors.md` 4.3、`geometry.md` 7.4 / 7.7 |
| 街道格局清楚、没有锚点 | `osm.py street-scan` 筛路口 → `tiles.py sheet` → 街景 | `corridors.md` |
| 识图无近重复、没有文字，只有一组场景要素（路的规格 + 相邻地物 + 地貌） | **别先手挑点位**：把场景写成一句英文 query，`sat_scan.py grid --bbox <海岸带/走廊> --zoom 17 --cell 360 --query … --neg …` 让 CLIP 排序，人只看前 20–30 名缩略图；`grid` 优于 `points`，因为 OSM 的 `amenity=parking` 一类要素未必收全 | `search.md` |
| 画面里 ≥4 个已知位置的点（窗景、俯拍；平视拍远处塔桥码头也行，fix 掉 height） | `pose.py solve` 反解机位、朝向、高度；几处候选都说得通时 `pose.py check --cands` 逐个打分，稳健Δchi2 > 9 的才能 `board.py exclude --computed` | `geometry.md` 第 10 节 |
| 想用"画面里没有 X"排除 | `geo.py frame` 先算 X 该不该在框里、够不够大、会不会被挡；能排除的才 `board.py exclude --computed` | `geometry.md` 第 11 节 |
| 认得出设施类型（烘干塔、饲料厂、糖厂、水泥站） | 查产业分布 → `osm.py buildings` 枚举大建筑 → `sat_scan.py points` 排序 | `search.md` |
| 连锁品牌子品牌门店 | 先搜开业新闻稿拿地址，定位器只当候选池 → `osm.py along` + 街景抽样 | `search.md` |
| 机窗、无人机俯拍 | 航拍分支 | `aerial.md` |

### 第 4 步：卫星图找点——机器先排序

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/sat_scan.py grid --bbox <scan_bbox> --zoom 17 --preset track --multi-scale --top 30 --out sat.json --sheet sat_top.jpg --heat heat.jpg   # 需 ARCGIS_API_KEY；无密钥只能 --source s2cloudless --zoom 14–15 看大地物
uv run ${CLAUDE_SKILL_DIR}/scripts/poi.py "<区县> 学校" --city <地级市> --out schools.json      # 种子：--seeds schools.json 给附近格子加分
uv run ${CLAUDE_SKILL_DIR}/scripts/sat_scan.py points --points big.json --preset factory --out r.json --sheet r.jpg   # osm.py buildings / poi.py 的候选点排序
```

- 预设：track（操场跑道）、stadium、factory、silo、dam、bridge、quarry、solar、greenhouse、port；自定义 `--query`。实测：城区 300 多格里，OSM 标注的跑道一半以上进前 30 名；国内 OSM 空白的老城，学校操场也能排第一。**它是排序不是判定**：看前 20–30 格的缩略图，再按照片里的方位、形状核。
- 把画面描述翻译成俯视特征后再看：圆弧楼、八角亭屋顶、球场、车位和铁路垂直；高楼看楼底；影像有年代。
- 候选多时列候选表：一行一个点，一列一条照片里直接看得到的标准。
- 前 30 名都没对上：先回头看 `board.py check` 列的"被推测降权的候选"和证伪条件，再换预设或 z18，最后才扩大范围。

### 第 5 步：确认——街景也先排序

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/mapillary.py scan <lat,lon> --radius 300 --out imgs.json                         # 国外首选：开放许可，可批量
uv run ${CLAUDE_SKILL_DIR}/scripts/baidu_pano.py scan <lat,lon> --radius 300 --step 60 --out panos.json             # 国内：生成取图点，单次 ≤150 张
uv run ${CLAUDE_SKILL_DIR}/scripts/match.py rank --query photo.jpg --panos imgs.json --toward <地标lat,lon> --spread 15 --refine sift --top 10 --out m.json --sheet m.jpg
uv run ${CLAUDE_SKILL_DIR}/scripts/match.py rank --query photo.jpg --items around.index.json --spread-headings -30,0,30 --out m.json --sheet m.jpg   # gsv.py 的 index 只适合 ≤60 张
```

- `match.py` 用 DINOv2 全局相似度粗排、SIFT 内点精排（`--method megaloc` 换用专门的视觉地点识别模型 MegaLoc，同一地点不同视角、年份更稳，第一次下载约 1 GB）；实测同一地点不同年份的街景真值都进前 4。只打开前 10 名，比**不变特征**（楼的轮廓、窗位、阳台、电杆位置、路缘、山脊），不比车辆、招牌、树叶。到路 ≥2 项、到楼 ≥3 项。内点 ≥15 的一张都没有**不代表不对**：换季、老批次、照片在人行道而街景在路中间时，真值实测只有 5 个、0–8 个内点（两例），先打开前 10 张比不变特征，都不对再换 `--spread-headings` 或扩大 `--within`。全局分会被季节主导（花期批次不论在哪都排前面），Mapillary 有多年份图像，按 `date` 挑和照片同季节的比。官方 Google、百度接口只给最新一批，没有历史批次。
- 点多时先 `--within`、`--spread` 缩范围；百度、Google 有单次张数上限，先用 Mapillary 或卫星图缩到几十个候选再用它们确认。
- 没有街景不等于不能确认：`terrain.py view --photo` 比山脊；给候选设施找名字（OSM 名字、附近地名 + 当地语言的设施类型词），搜新闻、百科、官网配图比立面细节。
- 街景比照片早很多年时，以老建筑和永久结构为准。

### 第 6 步：定机位与输出

- 回头看：在对上的街景点转 180°，看拍摄者那一侧是什么。
- 机位要两条独立约束（`geo.py intersect` 视线交会、`geo.py line` 对齐线、`pose.py` 多点反解、拍摄高度、反向街景）；只有一条时，楼级置信度最高"中"。
- 朝向没有可量的影子时用受光面：`sun.py facing --lit left --shaded camera`。车里、船上、火车上拍的写出行进方向。

```bash
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py check                      # 出结论前：排除有文件吗、主答案有核实证据吗、哪些线索没用上
uv run ${CLAUDE_SKILL_DIR}/scripts/board.py report --merge result.json # 主答案=第一名；备选、排除、未用线索自动写进 result.json
uv run ${CLAUDE_SKILL_DIR}/scripts/evidence.py spec.json --out evidence.jpg
```

输出：
1. 一句话结论：地点 + 机位 + 朝向（+ 行进方向、拍摄时间，如适用）
2. 坐标：WGS84 和 GCJ-02（`geo.py convert`），**带误差半径**
3. 证据图（卫星图标机位和朝向扇形 + 比对图）
4. 推理链：线索 → 推断 → **实际跑过的命令和产出文件** → 范围
5. 分档置信度（下表）。**每一级分开评，自报档位取"中"及以上的最细一级**：楼级低不拖累片区级高
6. 排除过的候选和理由、备选和区分检验、没用上或没解开的线索（`board.py report` 生成）
7. 定不到点时：已确定到哪一级 + 还需要什么信息
8. 一组照片：每张一个拍摄站立点（同一地点、只差拍摄时间的几张合并成一个点），列表和图例按把握从高到低排列；地图两侧配每个点对应的照片缩略图并用连线指向红点（按点的东西位置分到左右两栏、各栏按南北排序，连线少交叉），没定位的照片单独列在图例下；离其余点很远、证据又弱的点，先问用户要不要保留

| 级别 | 高 | 中 | 低 |
|---|---|---|---|
| 城市 | 文字、车牌、区号或确认过的锚点 | 多条独立弱线索一致 | 单条弱线索或只靠提示 |
| 片区 | 唯一的设施或地标在卫星图上对上 ≥3 项俯视特征（全候选区看完、没有第二处） | 候选区里最像的一处，还有没看完的候选 | 推测 |
| 路 | 实景对上 ≥2 项独有特征 | 格局一致，独有特征 1 项；**没有任何地面照片时**：片区级为高 + 方位自检通过 | 只有卫星图格局 |
| 楼 | 两条独立约束 + 实景 ≥3 项 | 两者之一 | 推测 |
| 楼层 | 两种参照交叉 | 单一参照 | 不给 |

## 预算与停止条件

- `intake.py` 算一次调用；识图换 3 组关键词无果就停，回清单找别的线索。
- **候选还分不开时不做任何逐个扫点**（`board.py next` 说"分不开"就先做区分检验）；便宜检验做完仍分不开，按它给的顺序扫，每个候选先扫建成区前 3 页。
- 扫描和确认一律先排序：`sat_scan.py` 看前 30 格，`match.py` 看前 10 张；前几名全不对再扩大，不是逐页翻。
- 用 OSM 枚举候选前先 `osm.py coverage`：偏少的区县会被静默排除，改用 `sat_scan.py grid`，并在结论里写明。
- 单个片区全景点 ≤500 个；3 个片区都没对上就停，`board.py report` 报告已确定到哪一级。
- 停之前 `board.py check`：被推测降权但没排除的候选按排序先回头看前 20 个。

## 运行环境

- Python 3.10+；一律 `uv run ${CLAUDE_SKILL_DIR}/scripts/xxx.py`（脚本头写了依赖；`match.py`、`sat_scan.py` 第一次会装 torch 并下载模型）。references 里的 `scripts/` 都相对于本 skill 目录。`revimg.py`/`intake.py --rev` 需要本机 Chrome；`ocr.py` 在 macOS 用 Apple Vision。
- 密钥用环境变量：`ARCGIS_API_KEY`、`MAPILLARY_TOKEN`、`GOOGLE_MAPS_API_KEY`、`BAIDU_MAP_AK`（应用设为 SN 校验时另配 `BAIDU_MAP_SK`，自动签名）、`AMAP_KEY`，都可选；`providers.py list` 看哪些已配、各自许可。
- 代理（`GEO_PROXY`，例如 `socks5h://127.0.0.1:10808`）只在本机直连不通时用：国内访问 Google、Overpass、Yandex、HuggingFace、Mapillary 常需要；百度、高德、高程切片直连。`intake.py --proxy` 写 `socks5://`（Chrome 的写法）。
- 只有许可允许的数据才写当前目录 `.geo-cache/`（Sentinel-2、Mapillary、高程、OSM）；Esri、Google、百度的图只进进程临时目录。候选盘是当前目录 `board.json`。脚本清单和数据源见 `references/data-sources.md`。
- macOS 没有 `timeout` 命令；zsh 里 `$var` 不分词，循环用 `bash -c` 或 `${=var}`。整省 Overpass 查询可能要几分钟，放后台跑。

## 练习与计分

**新方法以“准”为标准，并写明来源和验证情况**：来源可以是教材、论文、标准、调查机构指南，也可以是高手的公开经验（博主、GeoGuessr 玩家、调查记者）或本项目自己摸索出的技巧；不论来源，都要在条目里写明出处和验证情况——已在有答案的案例里用对过的写“实测 N 例”，还没验证的标“待验证”，只降权、不排除，用对了再升级。改技能时不削弱硬规则和“脚本排序、模型判断、结论必须对应跑过的命令”这条主线。

**每次使用后都要复盘，不只是测试时**：结束前花一两句回答——哪条线索最后定了位置、哪一步走了弯路、哪个工具本该更早用；有可复用的经验就当场写回对应的参考文件（不是只在聊天里说），并在 `evals/evals.json` 追加一条案例（答案未知时 `lesson` 写“待揭晓”，用户给出答案后补计分）。每新增约 10 条案例，回看全部 `lesson`，找重复出现的错误类型，改成规则或脚本检查。

拿已知答案测试时，先冻结判断再看答案，按“国家对否／25／200／750 km”记（距离用 `geo.py bearing A B` 或游戏给的值）。错了先找第一个出错的步骤（漏看、误读、锚定、过信弱线索、没核验、操作超时），方法缺陷写回对应步骤，并在 `evals/evals.json` 追加带 `lesson` 的案例；单次失误不改线索分级标准。不保存用户原图。

