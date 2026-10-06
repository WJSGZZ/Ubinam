# 画面里的东西 → OSM 标签

`osm.py find / near / coverage` 都要写 Overpass 标签。下表是照片里常见地物对应的标签（写法照 OSM Wiki 的 Map Features）；“近旁组合”用 `osm.py near --a … --b … --within …`，思路同 Bellingcat 的 OSM Search 工具：把画面里同框的两三样东西翻成标签，找它们挨在一起的地方。

**先查覆盖再用**：OSM 在国内很不均匀。实测一个县级市城区（10 km × 11 km，2026-10）：桥 575、电塔 74、停车场 66、学校 59、运河 52、篮球场 25 都收得不错；但古塔 0（城里有一座宋代古塔）、急诊入口 0、游乐场 0、码头栈道 0、酒店只有 9。路、水、桥、电力线这类线状地物在国内靠得住；店铺、景点、楼栋入口这类点状地物在国内改用 `poi.py`（高德、百度关键词）。没查到不等于没有，不能当排除理由（硬规则 9）。

| 画面里 | 标签 | 备注 |
|---|---|---|
| 医院 | `["amenity"="hospital"]` | 急诊入口 `["emergency"="emergency_ward_entrance"]` 很少有人标 |
| 喷泉 | `["amenity"="fountain"]` | |
| 步行街 | `["highway"="pedestrian"]` | 广场常标成 `highway=pedestrian` 加 `area=yes`，少数是 `["place"="square"]` |
| 桥（车行） | `["bridge"="yes"]["highway"]` | 人行桥 `["highway"="footway"]["bridge"="yes"]`；桥名常在 `bridge:name` |
| 船闸、水闸、堰 | `["waterway"~"^(lock_gate\|sluice_gate\|weir\|dam)$"]` | |
| 河 / 运河 / 小河沟 | `["waterway"~"^(river\|canal\|stream\|drain)$"]` | 水面多边形是 `["natural"="water"]`，再用 `water=river/lake/reservoir/canal` 分 |
| 码头、亲水栈道 | `["man_made"="pier"]` | 游船码头 `["amenity"="ferry_terminal"]` |
| 古塔、楼阁 | `["building"="pagoda"]`、`["historic"]` 加 `["man_made"="tower"]` | 写法很乱，按名字搜 `["name"~"塔"]` 更全 |
| 电视塔、通信塔 | `["man_made"~"^(tower\|mast)$"]["tower:type"="communication"]` | |
| 烟囱、水塔、冷却塔 | `["man_made"="chimney"]`、`["man_made"="water_tower"]`、`["tower:type"="cooling"]` | |
| 电塔、电线 | `["power"="tower"]`、`["power"="line"]` | 线路电压在 `voltage` |
| 商场 | `["shop"="mall"]` | 国内很多商场只标成 `building=retail` |
| 操场跑道、体育场 | `["leisure"="track"]`、`["leisure"="stadium"]` | 学校跑道漏标多，用 `sat_scan.py --preset track` |
| 篮球场、游泳池 | `["sport"="basketball"]`、`["leisure"="swimming_pool"]` | |
| 公园、儿童游乐设施 | `["leisure"="park"]`、`["leisure"="playground"]` | |
| 摩天轮、水上乐园 | `["attraction"="big_wheel"]`、`["leisure"="water_park"]` | |
| 观景台 | `["tourism"="viewpoint"]` | |
| 寺庙、教堂、清真寺 | `["amenity"="place_of_worship"]["religion"~"^(buddhist\|taoist\|christian\|muslim)$"]` | |
| 墓地 | `["landuse"="cemetery"]` | |
| 加油站、充电站 | `["amenity"="fuel"]`、`["amenity"="charging_station"]` | 品牌在 `brand` |
| 公交站、地铁口、火车站 | `["highway"="bus_stop"]`、`["railway"="subway_entrance"]`、`["railway"="station"]` | 线路用 `osm.py route` |
| 停车场、停车场入口 | `["amenity"="parking"]`、`["amenity"="parking_entrance"]` | |
| 酒店 | `["tourism"="hotel"]` | 国内漏标多，用 `poi.py` |
| 学校、大学 | `["amenity"="school"]`、`["amenity"="university"]` | |
| 山峰 | `["natural"="peak"]` | 高程在 `ele`；天际线比对用 `terrain.py` |
| 光伏、大棚、采石场 | `["plant:source"="solar"]`、`["landuse"="greenhouse_horticulture"]`、`["landuse"="quarry"]` | 卫星图上更好认，用 `sat_scan.py` 预设 |
| 高尔夫球场 | `["leisure"="golf_course"]` | |

组合示例（第一条在上述城区实跑过，0 个结果，正好是覆盖不足的例子）：

```bash
python3 scripts/osm.py near --a '["amenity"="fountain"]' --b '["shop"="mall"]' --within 150 --bbox <s,w,n,e>          # 商场前的喷泉广场
python3 scripts/osm.py near --a '["bridge"="yes"]["highway"]' --b '["man_made"="tower"]' --within 800 --bbox <s,w,n,e>  # 能看见塔的桥
python3 scripts/osm.py coverage --areas <区县1,区县2> --filter '["amenity"="hospital"]'                                                  # 枚举前先看覆盖
```
