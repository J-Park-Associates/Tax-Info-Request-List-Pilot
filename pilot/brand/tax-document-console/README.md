# Tax Document Console: the app icon and lockup

Jason picked this mark on 2026-10-01 (P116): concept 4e, "Gold tab", from the
concept page (https://claude.ai/artifact/MF8rLu5xoeTXdhFdYZHPgJ). It replaces
the monogram of P115; `concept-approved.png` is that earlier mark's concept,
kept for the record. [`../../SPEC-icon-ledger.md`](../../SPEC-icon-ledger.md)
is the drawing's SPEC.

The mark: a navy folder with a mid-blue rim, its tab in gold; a cream request
list standing in it with a gold tick and two rules; an angled navy front flap,
rimmed all round. The rim and the gold tab form the whole outline, and both
meet 3:1 on a light and a dark taskbar (figures in the SPEC).

Colours are the J Park & Associates navy family with two darker golds: the
tab's gold `#A8862F`-`#94782A` is dark enough for 3:1 on a light taskbar, and
the tick's `#9C7F2C` stays visible on the cream, where gold-500 `#C9A84C` fades.
The lockup's wordmark is Playfair Display 700 and the firm line Inter 600 at
0.30em tracking, the design system's two voices.

## Pixel perfect, and how

No single drawing is sharp at every size, so the icon is drawn three ways
(`source/mark.py` states the bands):

- **16, 20 and 24px** are pixel art: one letter per pixel, no blended pixel.
  They drop the rules and the shadow, and the tick's long arm is at least
  twice its short one, because an even tick reads as a V at these sizes.
  At 16 and 20 the flap sits a row lower so the sheet has room for the tick.
- **30 to 47px** (30, 32, 36, 40 and Square44x44Logo's 44) are the drawing
  fitted to the size without the rules, the tick built of whole pixels.
- **48px and up** are the full drawing fitted to the size: every horizontal
  and vertical edge, the rim and the corner radii on whole pixels (the flap's
  sloped sides take a 1.5px rim where the rim is one pixel, so they hold 3:1 on
  a dark taskbar), so only the
  tab's slope, the flap's sides, the tick, the rules' round ends and the
  corner arcs are blended.

Every size is drawn at that size; none is a resize of another.

## What each folder holds

| File | Where it is seen |
|---|---|
| `app/icon.ico` | The program file, its shortcuts on the desktop and Start menu, the taskbar, the title bar and Alt+Tab: 15 sizes, 16 to 256px. Below 256 the sizes are 32-bit bitmaps, 256 is PNG |
| `app/icon-16.png` ... `icon-256.png` | The same icon as single PNGs, for anything that takes one image |
| `app/icon.svg` | The icon as vector, with its shadow |
| `app/mark.svg` | The mark alone, the same on any ground |
| `app/mark-mono.svg` | The mark in one colour that follows the surrounding text colour, for Windows contrast themes; 24px and up |
| `installer/setup.ico` | The installer's own icon (the same file as `app/icon.ico`) |
| `installer/wizard-large-1.bmp` ... `-7.bmp` | The setup wizard's side panel at the seven scalings Inno Setup 6 picks from (164x314 to 410x797) |
| `installer/wizard-small-1.bmp` ... `-7.bmp` | The setup wizard's corner image at the same seven scalings (55x55 to 138x140) |
| `brand/lockup-light.svg`, `lockup-dark.svg` | Mark and wordmark side by side for light and navy grounds; the letters are outlines, so they look the same with or without the fonts installed |
| `brand/lockup-light.png`, `lockup-dark.png` | The lockups at 2x, for documents and email |
| `windows/Square44x44Logo.scale-100.png` ... `scale-400.png` | The packaged-app icon at Microsoft's seven scales, 44 to 176px |
| `windows/Square44x44Logo.targetsize-N.png` | The icon at each target size Microsoft lists, 16 to 256px, with `_altform-unplated` (taskbar, dark theme) and `_altform-lightunplated` (light theme) copies; the three are one image, since the mark meets 3:1 on both themes |
| `windows/Square150x150Logo.scale-100.png` ... `scale-400.png` | The Start tile at the seven scales, 150 to 600px; the icon is fitted at two thirds of the tile, its box centred on a whole pixel |

## Rebuilding

`source/` is the generator. It needs Python 3.11+ with `fonttools`,
`uharfbuzz`, `pillow` and `playwright` and a Chromium. These are design tools,
not app dependencies, so they are not in the app's lock files. The two
typefaces are downloaded from Google Fonts into `source/fonts/` on first run
(ignored by Git).

```
cd pilot/brand/tax-document-console/source
python export.py ..        # rewrites app/, installer/, brand/ and windows/
python sheet.py sheet.png  # every size 1:1 on light and dark, plus 8x zooms
```

Set `CHROME_PATH` to use a particular Chromium. After any change to
`source/mark.py`, check the sheet's 16, 20, 24 and 32px zooms before accepting it.
