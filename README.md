<div align="center">

# Ubinam

**Where was this photo taken — and when? An agent skill that finds out, checks its answer against real map data, and shows its work.**

*Ubinam* is Latin for “where, exactly?”

[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

Hand your agent a photo, or a whole album, and ask where it was taken. Ubinam reads every sign and landmark, ranks candidate places with scripts, then verifies the best ones against satellite imagery, street-level photos, terrain and map databases. You get coordinates, an error radius, and a separate confidence level for country, city, street and building, plus the chain of evidence behind each one.

It is a standard [Agent Skill](https://agentskills.io): one folder with `SKILL.md`, plain Python scripts and reference notes. It works in Claude Code, Codex, Cursor, Gemini CLI, OpenCode, GitHub Copilot and any agent that can read `SKILL.md` and run shell commands.

## Why Ubinam

- **It checks instead of guessing.** Every “verified” claim must point to a command that actually ran and the file it produced. Exclusions need evidence, and an error radius under 100 m needs two independent constraints. A script-enforced candidate board keeps the model from settling on the most famous place that looks similar.
- **Geometry, not vibes.** It can estimate focal length from EXIF or vanishing points, measure distance and height against the horizon, compare building heights from their shadows on satellite imagery, resect the camera position from three or more known landmarks, bracket the exact spot on a road from the parallax between three landmarks, render mountain skylines from elevation data, match coastline shapes, and compute where the sun was.
- **Whole albums, not just single shots.** It locates the easy photos first (the ones with readable signs), uses them to bound the area, then goes back to the hard ones. It can plot every shooting spot on one satellite map, ranked by confidence.
- **When it was taken, too.** It uses sun and shadow math when there are shadows. When there aren't, it falls back to dated evidence: festival decorations, construction progress, historical weather, and how fast the light and crowds are changing. Esri Wayback gives every version of the satellite imagery since 2014 together with the date each image was actually captured, so a building's first appearance brackets the year; Sentinel-2 scenes every five days narrow construction and redevelopment down to the month. Geometric conclusions are reported separately from common-sense guesses.
- **Ready for China, not just the West.** It includes AMap and Baidu place search, WGS84/GCJ-02/BD-09 conversion, lookup tables for licence plates, area codes and scripts, and a workflow for Baidu's street panoramas, where Google Street View has no coverage.
- **Clean data sources.** It only uses official APIs or openly licensed data: Esri and Sentinel-2 imagery, Mapillary (CC BY-SA), OpenStreetMap, and the official Baidu, AMap and Google APIs with your own keys. It never scrapes undocumented endpoints.
- **Second opinions built in.** [GeoCLIP](https://github.com/VicenteVivan/geo-clip) gives an independent coarse guess from the image alone, and [MegaLoc](https://github.com/gmberton/MegaLoc) ranks street-level candidates by visual place recognition.
- **A quick mode for games.** For GeoGuessr-style rounds it reads, zooms, looks things up and commits to an answer, with a separate betting rule for distance-scored games.

## What it has done

Real photos, scored only after the answer was frozen:

| Photo | Result |
|---|---|
| Hotel window view across a river, two bank logos readable | Resected from landmark positions; hotel identified, about 20 m off |
| Traffic jam in Southeast Asia, one brand sign on a building | Company address led to the mall; street-level parallax put the camera about 30 m from the true spot |
| Sunset over the sea, no text at all | Coastline-shape match picked the right bay and island; the GeoCLIP second opinion agreed |
| Album of 14 city photos | 9 shooting spots pinned on one map; the hard lake shot was solved from a restaurant name reflected in the water |
| Cable-stayed bridge at dusk, no text | **Missed by about 190 km**: picked the wrong one among several look-alike bridges (see Limits) |

## How it works

| Layer | Who | Tools |
|---|---|---|
| **Decide**: which candidates, how to weigh evidence, what can be excluded, what to do next | scripts (candidate board) | `board.py` |
| **Perceive**: read text, look up tables, rank satellite cells and street-level images | scripts rank, the model looks at the top few | `intake.py` `ocr.py` `clues.py` `poi.py` `sat_scan.py` `match.py` |
| **Judge**: pull clues from the frame, propose hypotheses, choose among the ranked few | the model | `SKILL.md` + `references/` |

The full script list, data sources and licences are in [`skills/ubinam/references/data-sources.md`](skills/ubinam/references/data-sources.md). The skill instructions are written in Chinese; agents read them fine either way.

## Install

```bash
git clone https://github.com/WJSGZZ/Ubinam
cp -r ubinam/skills/ubinam ~/.agents/skills/              # Codex, Cursor, Gemini CLI, OpenCode, GitHub Copilot
ln -s ~/.agents/skills/ubinam ~/.claude/skills/ubinam     # Claude Code
```

You need Python 3.10+ and [`uv`](https://docs.astral.sh/uv/). Each script declares its own dependencies and `uv run` installs them on first use. `match.py`, `sat_scan.py` and `prior.py` download PyTorch and their models the first time they run.

## Keys (all optional)

It works without any keys: lookup tables, sun and terrain geometry, OpenStreetMap queries and Sentinel-2 imagery need none. Each key you add unlocks more:

| Variable | Service | What it unlocks |
|---|---|---|
| `ARCGIS_API_KEY` | [ArcGIS Location Platform](https://location.arcgis.com) (free tier) | Recent high-resolution satellite imagery; satellite scans at z17+ |
| `MAPILLARY_TOKEN` | [Mapillary developers](https://www.mapillary.com/dashboard/developers) (free) | Street-level images worldwide for bulk matching, including many Chinese city roads |
| `AMAP_KEY` | [AMap Open Platform](https://lbs.amap.com) (choose “Web service”) | Place search in China |
| `BAIDU_MAP_AK` / `BAIDU_MAP_SK` | [Baidu Maps Open Platform](https://lbsyun.baidu.com) | Place search in China (SK only if your app uses SN signing); the Panorama Static API is a paid add-on |
| `GOOGLE_MAPS_API_KEY` | [Google Maps Platform](https://developers.google.com/maps) | Small, manual checks with Street View and satellite tiles |

Run `python3 skills/ubinam/scripts/providers.py list` to see which sources are active and what each licence allows.

## Limits

These are worth knowing before you rely on it:

- **Look-alike structures.** Without text, many bridges, towers and residential blocks have near-twins. Ubinam lists every look-alike candidate before choosing one, but it can still pick the wrong twin.
- **Street-level coverage stops at the road.** Parks, campuses, lakeshores and residential compounds are rarely covered, so shots taken inside them are confirmed from satellite structure and public photos instead, with lower confidence.
- **Imagery ages.** A lake that was redeveloped last year can look completely different on older imagery. Before excluding a place, Ubinam looks up when the imagery was captured and checks current photos, but stale data can still mislead.
- **Blurry text stays blurry.** AI upscaling only makes guessed letters look sharp, so it is not used as evidence. Video helps, because several frames together contain real extra detail.
- **The model can be wrong.** Confidence is reported for each tier so that you can see how far to trust the answer.

## Responsible use

Use it on your own photos, public scenes, news images, or photos you have permission to analyse. Do not use it to find people who have not agreed to be found. When a photo shows a private person's home or current whereabouts and the goal is to locate that person, the skill stops at city level. It locates photos; it does not infer where a person lives from a set of their photos.

## Based on geo-sleuth

Ubinam builds on [**geo-sleuth**](https://github.com/Oldcircle/geo-sleuth) by Oldcircle (MIT), imported with its full commit history. The core method comes from that project: the candidate board, rules enforced in code, “scripts rank, the model judges”, and skyline and pier-spacing geometry. Ubinam replaces its undocumented Google, Baidu and 360 endpoints with official or openly licensed sources, and adds China place search, album-wide constraints, street-level parallax bracketing, capture-time estimation without shadows, GeoCLIP and MegaLoc, quick mode, and regression cases.

## Licence and credits

- Code: MIT, see [LICENSE](LICENSE). Copyright © 2026 Oldcircle (geo-sleuth) and © 2026 Xik (Ubinam modifications).
- Lookup tables in `skills/ubinam/data/` derived from Wikipedia are CC BY-SA 4.0; details are in [`data/README.md`](skills/ubinam/data/README.md). Administrative divisions come from [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China).
- Live data keeps its own licence, so credit it when you publish results: © OpenStreetMap contributors (ODbL); Sentinel-2 cloudless by EOX (CC BY 4.0); contains modified Copernicus Sentinel data (via Element84 Earth Search); © Mapillary contributors (CC BY-SA 4.0); Esri, Google, Baidu and AMap data under their providers' terms; AWS Terrain Tiles.
- Models: DINOv2 (Meta AI), CLIP (OpenAI), [GeoCLIP](https://github.com/VicenteVivan/geo-clip) (MIT), [MegaLoc](https://github.com/gmberton/MegaLoc) (MIT).
