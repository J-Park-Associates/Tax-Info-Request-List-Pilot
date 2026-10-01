# Pilot: replace the app icon with Ledger 4e - SPEC

Status: **written 2026-10-01.** Decision P116 (`DECISIONS.md`), superseding the
artwork of P115. The wiring in [`SPEC-icon.md`](SPEC-icon.md) is unchanged: it
names files by path, and every path it names is regenerated here.

## What Jason chose

Concept 4e, "Gold tab", from the concept page
(https://claude.ai/artifact/MF8rLu5xoeTXdhFdYZHPgJ): a navy folder with a
light rim, its tab in gold, a cream request list with a gold tick and two
rules standing in it, and an angled navy front flap. His words: "go with 4e,
scale up by pixel at every microsoft size", with the file delivery of the
original brief (Square44x44Logo and Square150x150Logo at 100%, 200% and 400%;
target sizes 16, 24, 32, 48 and 256).

## The drawing

On a 48-unit grid (the master; `source/mark.py` holds the numbers):

| Part | Geometry (units) | Colour |
|---|---|---|
| Folder back | x 5-43, y 7-40; tab x 5-19 at the top, sloping to x 23 at y 11 | navy `#2E4675` to `#1B2A4A`, 120 degrees |
| Rim | 1 unit inside the back's and the flap's outline | `#9FB2D6` |
| Tab | the back left of the slope, above y 11 | gold `#A8862F` to `#94782A` |
| Sheet | x 15-37, y 12-32, radius 2 | cream `#FFFDF8` to `#F0E9DC` |
| Tick | (18.5, 17) to (20.3, 18.8) to (23.5, 15.1), stroke 2 | gold `#9C7F2C` (3.2:1 or more on the cream) |
| Rules | x 26-34 y 16-18; x 19-34 y 21-23 | `#9AA6BC` |
| Flap | top y 24 from x 9 to 46, bottom y 40 from x 5 to 42, corners radius 1.5; top band 1.5 | navy `#3D5A92` to `#2E4675`, rim all round |
| Shadow | 1 unit down, blur 1, 28% of `#0A1F3D` | at 48 px and up only |

**Contrast** (Windows grounds `#F3F3F3` and `#202020`). On a dark taskbar the
outer edge is the rim (7.6:1) or the gold tab (3.9:1). On a light one the rim
is pale (1.9:1), so the edge is carried by what sits directly inside it: the
navy back (8.4:1 or more), the flap (6.1:1 or more) and the gold tab (3.1:1).
The concept page drew the flap without a rim; the flap's bottom edge was then
1.7:1 on a dark taskbar. The rim all round fixes that, and is the one change
from the concept.

## Per size ("scale up by pixel")

No drawing is sharp at every size, so it is drawn two ways:

- **16, 20 and 24 px are pixel art** (`PIXEL_ART` in `mark.py`): one letter per
  pixel, flat colours, no blended pixel anywhere. They drop the two rules and
  the shadow and draw a larger tick, as Microsoft advises for small sizes. The
  tick's long arm is at least twice its short one; an even tick reads as a V.
- **30, 32, 36 and 40 px** are the vector drawing fitted to the size, without
  the rules, and with the tick built of whole pixels: a blended tick this
  small smudges into a blot.
- **48 px and up** are the full vector drawing fitted to the size: every
  horizontal and vertical edge on a whole pixel, the rim, the flap's top band
  and the corner radii whole pixels (`max(1, round(size / 48))` for the rim),
  so only the tab's slope, the flap's sides, the tick and the corner arcs are
  blended. The shadow is drawn from 48 px up.

## Files

`source/export.py ..` writes all of them; nothing is edited by hand.

| Folder | Files |
|---|---|
| `app/` | `icon.ico` (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256), `icon-16/32/48/64/128/256.png`, `icon.svg` (vector master), `mark.svg` (the drawing for any ground), `mark-mono.svg` (one colour, `currentColor`) |
| `installer/` | `setup.ico` (same as `app/icon.ico`), the seven wizard panels each way, now showing the new mark |
| `brand/` | the two lockups, now with the new mark |
| `windows/` (new) | `Square44x44Logo.scale-100/125/150/200/250/300/400.png` (44 to 176 px); `Square44x44Logo.targetsize-N.png`, `-N_altform-unplated.png` and `-N_altform-lightunplated.png` for N = 16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256; `Square150x150Logo.scale-100/125/150/200/250/300/400.png` (150 to 600 px) |

That is every size on Microsoft's construction page, a superset of the brief.
The three target-size forms are the same image: the icon passes contrast on
both themes, so it needs no per-theme version. Microsoft states no artwork
size for the 150 tile; the mark is drawn at two thirds of the tile, fitted
at that size and centred on a whole pixel.

`mark-light.svg` is removed: the old monogram needed a navy version for light
grounds, and this mark is the same on both.

## Checks

- A contact sheet (`source/sheet.py`) of every size on both grounds, with the
  16, 20, 24 and 32 px drawings at 8x.
- An independent review (a session that did not draw it) against this SPEC:
  sharpness per size, contrast, file names and pixel sizes.
- `python tools/repo_map.py update` and `check`; `python -m ruff check .`. No
  module in `tracker/` or the app changes, so no engine tests run; the guard
  files `test_layers`, `test_single_source` and `test_repo_map` do.
