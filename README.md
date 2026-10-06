<div align="center">

# Ubinam

**Where was this photo taken? Ubinam finds out, and tells you exactly how sure it is.**

*Ubinam* is Latin for “where, exactly?”

[English](README.md) · [简体中文](README.zh-CN.md)

</div>

---

Some photos can be pinned to within tens of metres. Others only to a city. That depends on what is in the frame and on how much map data exists for that place, and no tool can promise more than that. Ubinam goes as far as the evidence allows, then stops and tells you why.

What you get back:

- **Coordinates with an honest error radius**: tens of metres when a readable sign and street-level imagery agree, a whole district when all there is to go on is a skyline.
- **A confidence level for each step**: country, city, street, building and floor are judged separately, so a shaky building guess doesn't drag down a solid street.
- **The evidence**: annotated satellite images and side-by-side comparisons, each tied to a command that actually ran.
- **What's missing**: when it can't go further, it says what kind of photo or data would get it there.

It is an [Agent Skill](https://agentskills.io): a folder of instructions and plain Python scripts. It works in Claude Code, Codex, Cursor, Gemini CLI, OpenCode and any agent that can read `SKILL.md` and run shell commands.

## Track record

Real photos. The answer was frozen before the truth was revealed.

| The photo | What Ubinam did |
|---|---|
| A traffic jam in Southeast Asia, one brand sign on a building | Looked up the brand's branch address to find the mall, then pinned the camera **about 30 m** from where it really was |
| A hotel window view across a river | Worked out the camera position from the landmarks in view and named the hotel, **about 20 m** off |
| A sunset over the sea, no text anywhere | Matched the coastline's shape to find the right bay and island |
| An album of 14 photos from one city | Pinned **12 of them** on one map and reported the other two as unplaced rather than guessing. A restaurant name **reflected in the water** in one night shot then cracked a separate lake photo that had no signs at all |
| A cable-stayed bridge at dusk, no text | **Wrong by about 190 km**: it picked the wrong one of several look-alike bridges. We list our misses too |

## How precise, realistically

From our test cases so far (a small sample, so treat these as rough):

| What the photo gives it | What to expect |
|---|---|
| A readable shop sign or street name, in a city with street-level imagery | The street, often the building: tens of metres |
| Several landmarks it can identify on a map (a window view, a skyline) | The camera position: tens of metres |
| A distinctive natural shape (coastline, mountain ridge) but no text | The right bay or valley; the exact spot is looser |
| A generic scene: a park path, a housing estate, a lakeshore | The district at best |
| A look-alike structure with no text | It can be wrong by a long way, as with the 190 km bridge |

**Where the photo was taken matters as much as what's in it.** Street-level imagery, building outlines and building heights are far more complete in much of Europe and North America than in most of China. Google Street View doesn't cover mainland China, Baidu's panoramas follow city roads only, and many buildings have no recorded height or floor count. Small towns are harder everywhere: fewer photos online, fewer mapped buildings, older satellite imagery.

## What it can do

**Find the place**
- Reads shop signs, plates, phone numbers and street furniture, and looks them up in country tables.
- Turns a brand name into a company or branch address, and a scene (“a bridge with a tower in view”) into a map query.
- Ranks thousands of satellite tiles or street-level images automatically, so the model only inspects the top few.

**Pin the exact spot**
- Works out the camera position from three or more landmarks it can identify on a map.
- Narrows a spot on a road down to tens of metres from how near and far objects shift against each other.
- Renders mountain skylines from elevation data and matches them to the photo.

**Work out when**
- Calculates the time and direction from shadows and the sun.
- With no shadows, dates the photo from evidence: satellite imagery back to 2014 with real capture dates, Sentinel-2 scenes every five days for construction and redevelopment, festival decorations and historical weather.

**Handle whole albums**
- Solves the easy photos first, uses them to narrow the area, then goes back for the hard ones.
- Plots every shooting spot on one map, with each photo shown beside its point.

**Work in China too**
- AMap and Baidu place search, conversion between China's three coordinate systems, and a workflow for Baidu panoramas where Google Street View has nothing.

**Play GeoGuessr**
- A quick mode that reads, zooms, looks up and commits, with a betting rule for distance-scored rounds.

## Why you can trust the answer

The rules that matter are enforced by scripts, not left to the model's good intentions:

- **No made-up verification.** “Matched on street view” must point to a file produced in the same session.
- **Ruling out a place takes the same evidence as confirming one.** A hunch can lower a candidate's rank but never remove it.
- **Fame is not evidence.** The model cannot jump to the best-known place that looks similar. Every candidate goes on a scored board first.
- **Precision has to be earned.** An error radius under 100 m needs two independent lines of evidence.

## Install

```bash
git clone https://github.com/WJSGZZ/Ubinam
cp -r Ubinam/skills/ubinam ~/.agents/skills/              # Codex, Cursor, Gemini CLI, OpenCode, GitHub Copilot
ln -s ~/.agents/skills/ubinam ~/.claude/skills/ubinam     # Claude Code
```

Then just ask your agent “where was this taken?” and attach a photo.

You need Python 3.10+ and [`uv`](https://docs.astral.sh/uv/). Each script declares its own dependencies, and `uv run` installs them the first time. The image-matching scripts (`match.py`, `sat_scan.py`, `prior.py`) download PyTorch and their models on first use.

## Keys (all optional)

It works with no keys at all: lookup tables, sun and terrain geometry, OpenStreetMap, historical Esri imagery and Sentinel-2 are free. Each key you add unlocks more:

| Variable | Service | What it unlocks |
|---|---|---|
| `ARCGIS_API_KEY` | [ArcGIS Location Platform](https://location.arcgis.com) (free tier) | Current high-resolution satellite imagery and close-up satellite scans |
| `MAPILLARY_TOKEN` | [Mapillary developers](https://www.mapillary.com/dashboard/developers) (free) | Street-level images worldwide for bulk matching, including many roads in Chinese cities |
| `AMAP_KEY` | [AMap Open Platform](https://lbs.amap.com) (choose “Web service”) | Place search in China |
| `BAIDU_MAP_AK` / `BAIDU_MAP_SK` | [Baidu Maps Open Platform](https://lbsyun.baidu.com) | Place search in China (SK only if your app uses SN signing). Panoramas are a paid add-on |
| `GOOGLE_MAPS_API_KEY` | [Google Maps Platform](https://developers.google.com/maps) | A few manual Street View and satellite checks |

`python3 skills/ubinam/scripts/providers.py list` shows which sources are active and what each licence allows. Ubinam only uses official APIs and openly licensed data. It never scrapes undocumented endpoints.

## Limits

- **Look-alikes.** Without text, many bridges, towers and housing blocks have near-twins. Ubinam lists them all before choosing, but it can still pick the wrong twin.
- **Street-level imagery stops at the road.** Parks, campuses, lakeshores and residential compounds are rarely covered, so shots taken inside them get lower confidence.
- **Imagery ages.** A lake redeveloped last year can look nothing like the satellite image. Ubinam checks when each image was captured before ruling a place out, but stale data can still mislead.
- **Blurry text stays blurry.** AI upscaling invents strokes, so it never counts as evidence. Video is different: stacking frames recovers real detail, and Ubinam does that.

## Responsible use

Use it on your own photos, public scenes, news images, or photos you have permission to analyse. Don't use it to find people who don't want to be found. When a photo shows a private person's home or current whereabouts and the aim is to locate that person, the skill stops at city level. It locates photos. It does not work out where someone lives from a set of their pictures.

## Based on geo-sleuth

Ubinam builds on [**geo-sleuth**](https://github.com/Oldcircle/geo-sleuth) by Oldcircle (MIT), imported with its full commit history. The core method comes from that project: the candidate board, rules enforced in code, “scripts rank, the model judges”, and skyline and pier-spacing geometry. Ubinam replaces its undocumented Google, Baidu and 360 endpoints with official or openly licensed sources. It adds China place search, album-wide constraints, camera pinning on a road, capture dating with historical imagery and Sentinel-2, multi-frame text recovery, GeoCLIP and MegaLoc, a quick mode, and regression cases.

## Licence and credits

- Code: MIT, see [LICENSE](LICENSE). Copyright © 2026 Oldcircle (geo-sleuth) and © 2026 Xik (Ubinam modifications).
- Lookup tables in `skills/ubinam/data/` derived from Wikipedia are CC BY-SA 4.0; details are in [`data/README.md`](skills/ubinam/data/README.md). Administrative divisions come from [modood/Administrative-divisions-of-China](https://github.com/modood/Administrative-divisions-of-China).
- Live data keeps its own licence, so credit it when you publish results: © OpenStreetMap contributors (ODbL); Sentinel-2 cloudless by EOX (CC BY 4.0); contains modified Copernicus Sentinel data (via Element84 Earth Search); © Mapillary contributors (CC BY-SA 4.0); Esri, Google, Baidu and AMap data under their providers' terms; AWS Terrain Tiles.
- Models: DINOv2 (Meta AI), CLIP (OpenAI), [GeoCLIP](https://github.com/VicenteVivan/geo-clip) (MIT), [MegaLoc](https://github.com/gmberton/MegaLoc) (MIT).
