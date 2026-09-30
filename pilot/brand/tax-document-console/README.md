# Tax Document Console: the app icon and lockup

Jason picked this mark on 2026-09-30 (P115) from a concept image generated
with Nano Banana ([`concept-approved.png`](concept-approved.png)). The image
is the target look, not the artwork: its geometry is freehand and it
dissolves at 16px. Everything here is a redraw of it as exact geometry: a
monogram frame (a top bar, a lowercase t at the left, a J-hook at the lower
right) holding a cream diamond ring with a gold core, and a gold folded
corner at the top right, on the firm's navy plate.

Colours are the J Park & Associates design-system tokens: navy `#1B2A4A`
(navy-900) for the plate, gold `#C9A84C` (gold-500) as the one accent, cream
`#F5F0E8` (cream-50) for the mark on navy, and gold `#7A5F16` (gold-800) where
gold is text on a light ground. The wordmark is Playfair Display 700 and the
firm line Inter 600 at 0.30em tracking, the design system's two voices.

Nothing here is wired into the app yet. [`../../SPEC-icon.md`](../../SPEC-icon.md)
says where each file goes.

## Pixel perfect, and how that was checked

No single drawing is sharp at every size, so the icon is drawn three ways
(`source/mark.py` states the bands):

- **16, 20 and 24px** are drawn pixel by pixel. No edge in the mark is blended.
- **30 to 64px** are the vector drawing with every edge on a whole pixel, the
  J's curve and the diamond built from whole-pixel cells.
- **72 to 256px** are the vector drawing with straight edges on whole pixels;
  only the J's curve and the diamond's diagonals are anti-aliased.

The plate is drawn at 8x and scaled down so its four corners come out
identical, with a faint cream rim so it keeps its edge on a dark taskbar.

It was reviewed in a loop: an independent reviewer measured every size pixel
by pixel against the concept, the findings were fixed, and a fresh reviewer
checked again, until round 18 came back with no findings (63 fixes in all).
Two decisions from that loop are deliberate and should not be "fixed":

- at 16, 20 and 24px the gold core is an odd-width pointed diamond (rows 1, 3,
  5, 3, 1), because an even one reads as a plus sign at that size; at 24px it
  therefore sits half a pixel toward the t;
- the 30px mark fills more of its plate (0.79) than its neighbours, because a
  smaller mark makes the diamond touch the crossbar.

## What each folder holds

| File | Where it is seen |
|---|---|
| `app/icon.ico` | The program file, its shortcuts on the desktop and Start menu, the taskbar, the title bar and Alt+Tab: 15 sizes, 16 to 256px. Below 256 the sizes are 32-bit bitmaps, 256 is PNG |
| `app/icon-16.png` ... `icon-256.png` | The same icon as single PNGs, for anything that takes one image |
| `app/icon.svg` | The 256px icon as vector |
| `app/mark.svg` | The mark alone on navy (cream and gold), for the app's own navy surfaces |
| `app/mark-light.svg` | The mark alone on light grounds (navy and gold) |
| `app/mark-mono.svg` | The mark in one colour that follows the surrounding text colour, for Windows contrast themes |
| `installer/setup.ico` | The installer's own icon (the same file as `app/icon.ico`) |
| `installer/wizard-large-1.bmp` ... `-7.bmp` | The setup wizard's side panel at the seven scalings Inno Setup 6 picks from (164x314 to 410x797) |
| `installer/wizard-small-1.bmp` ... `-7.bmp` | The setup wizard's corner image at the same seven scalings (55x55 to 138x140) |
| `brand/lockup-light.svg`, `lockup-dark.svg` | Mark and wordmark side by side for light and navy grounds; the letters are outlines, so they look the same with or without the fonts installed |
| `brand/lockup-light.png`, `lockup-dark.png` | The lockups at 2x, for documents and email |

## Rebuilding

`source/` is the generator. It needs Python 3.11+ with `fonttools`,
`uharfbuzz`, `pillow` and `playwright` and a Chromium. These are design tools,
not app dependencies, so they are not in the app's lock files. The two
typefaces are downloaded from Google Fonts into `source/fonts/` on first run
(ignored by Git).

```
cd pilot/brand/tax-document-console/source
python export.py ..        # rewrites app/, installer/ and brand/
python sheet.py sheet.png  # every size 1:1 on light and dark, plus 8x zooms
```

Set `CHROME_PATH` to use a particular Chromium. A rebuild from these scripts
reproduces the committed files byte for byte. After any change to
`source/mark.py`, check the 16, 20 and 24px zooms on the sheet before
accepting it.
