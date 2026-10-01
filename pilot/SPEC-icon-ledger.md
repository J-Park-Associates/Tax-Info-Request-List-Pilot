# Pilot: replace the app icon with Ledger 4e - SPEC

Status: **written 2026-10-01.** Decision P191 (`DECISIONS.md`), superseding the
artwork of P190. The wiring in [`SPEC-icon.md`](SPEC-icon.md) is unchanged: it
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
| Folder back | x 4-42, y 7-40; tab x 4-18 at the top, sloping to x 22 at y 11 (the tab is 4 units tall) | navy `#2E4675` to `#1B2A4A`, 120 degrees |
| Rim | 1 unit inside the back's and the flap's outline (1.5 px on the flap's slopes where fitted to a one-pixel rim, 30-71 px; see Contrast) | mid-blue `#6A87C2` |
| Tab | the back left of the slope, above y 11 | gold `#A8862F` to `#94782A` |
| Sheet | x 14-36, y 12-32, radius 2 | cream `#FFFDF8` to `#F0E9DC` |
| Tick | (17.5, 17) to (19.3, 18.8) to (22.5, 15.1), stroke 2 | gold `#9C7F2C`: 3.8:1 on `#FFFDF8`, where it sits; 3.2:1 at the sheet's darker end |
| Rules | x 25-33 from y 16; x 18-33 from y 21; each 2 tall | `#9AA6BC` |
| Flap | top y 24 from x 8 to 45, bottom y 40 from x 4 to 41, corners radius 1.5; top band 1.5 | navy `#3D5A92` to `#2E4675`, rim all round |
| Shadow | 1 unit down, blur 1, 28% of `#0A1F3D` | at 48 px and up only |

**Contrast** (Windows grounds `#F3F3F3` and `#202020`). On a dark taskbar the
outer edge is the rim (4.5:1) or the gold tab (3.9:1 or more). On a light one
it is the rim (3.2:1) or the gold tab (3.1:1 or more). So the whole outline
meets 3:1 on both themes, including the strip over the cream sheet, where
nothing but the rim stands between sheet and ground. Measured as the weakest
point between ground and navy at every generated size, blended pixels
included: 3.03:1 on dark, 3.09:1 on light. Where the fitted rim is one pixel
(30-71 px), the flap's sloped sides take a 1.5 px rim: a 1 px rim on a slope splits into two
half-tone pixels, and neither reaches 3:1 on a dark taskbar.
Three changes from the concept: the flap is rimmed all round (drawn without a
rim, its bottom edge was 1.7:1 on a dark taskbar); the rim is mid-blue, not
the concept's pale `#9FB2D6`, which was 1.9:1 on a light taskbar above the
sheet; and the whole drawing moves a unit left, so its extent (x 4-45, the
flap overhanging the back on the right) is centred within half a unit in the
master, and within half a unit plus half a pixel once fitted to a size.

## Per size ("scale up by pixel")

No drawing is sharp at every size, so it is drawn in three bands:

- **16, 20 and 24 px are pixel art** (`PIXEL_ART` in `mark.py`): one letter per
  pixel, flat colours, no blended pixel anywhere. They drop the two rules and
  the shadow and draw a larger tick, as Microsoft advises for small sizes. The
  tick's long arm is at least twice its short one; an even tick reads as a V.
  At 16 and 20 the flap sits a row lower than the fitted geometry so the
  sheet has room for the tick.
- **30 to 47 px** (30, 32, 36, 40 and Square44x44Logo's 44) are the vector
  drawing fitted to the size, without the rules, the tick built of whole
  pixels with a clear row above it and below it: a blended tick this small
  smudges into a blot.
- **48 px and up** are the full vector drawing fitted to the size: every
  horizontal and vertical edge on a whole pixel, the rim, the flap's top band
  and the corner radii whole pixels (`max(1, floor(size / 48 + 0.5))` for the rim),
  both rules one height, so only the tab's slope, the flap's sides, the tick,
  the rules' round ends and the corner arcs are blended. The shadow is drawn
  from 48 px up.

Fitting rounds half up, never Python's round-half-to-even, which sends edges
on a half pixel in opposite directions. Where two edges sit a fixed distance
apart in the master, the second is laid off from the first: the body's top
from the tab's top, and the sheet's top one rim below the body's top, so the
rim above the sheet keeps its full width.

## Files

`source/export.py ..` writes all of them; nothing is edited by hand.

| Folder | Files |
|---|---|
| `app/` | `icon.ico` (16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256), `icon-16/32/48/64/128/256.png`, `icon.svg` (vector master), `mark.svg` (the drawing for any ground), `mark-mono.svg` (one colour, `currentColor`; 24 px and up, below which the tick closes up) |
| `installer/` | `setup.ico` (same as `app/icon.ico`), the seven wizard panels each way, now showing the new icon fitted at its own size on whole pixels |
| `brand/` | the two lockups, now with the new mark, sized by its drawn extent |
| `windows/` (new) | `Square44x44Logo.scale-100/125/150/200/250/300/400.png` (44 to 176 px); `Square44x44Logo.targetsize-N.png`, `-N_altform-unplated.png` and `-N_altform-lightunplated.png` for N = 16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256; `Square150x150Logo.scale-100/125/150/200/250/300/400.png` (150 to 600 px) |

That is every size on Microsoft's construction page, a superset of the brief.
The three target-size forms are the same image: the icon passes contrast on
both themes, so it needs no per-theme version. Microsoft states no artwork
size for the 150 tile; the icon is drawn at two thirds of the tile, fitted
at that size, its box centred on a whole pixel (the drawing within half a
unit of centre, as above).

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
