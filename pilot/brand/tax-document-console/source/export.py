"""Export every file the app, its build and its installer need from the chosen mark.

    python export.py OUT_DIR

Writes app/ (the .ico, PNGs, the in-app SVG marks), installer/ (the Inno Setup
icon and the wizard bitmaps at every DPI Inno Setup 6 accepts), brand/
(lockups for documents and the client-facing pages) and windows/ (every
Square44x44Logo and Square150x150Logo file on Microsoft's construction page).
"""
import io
import sys
from pathlib import Path

from ico import pack
from lockup import lockup
from mark import CREAM, NAVY, SIZES, app_icon, bare_mark
from PIL import Image
from raster import icon_png, tile_png
from render import Renderer

# Inno Setup 6 picks the bitmap that fits the screen's scaling (100%-250%).
WIZARD_LARGE = [(164, 314), (192, 386), (246, 459), (273, 523), (328, 628), (355, 665), (410, 797)]
WIZARD_SMALL = [(55, 55), (64, 68), (83, 80), (92, 97), (110, 106), (119, 123), (138, 140)]

# Microsoft's scale qualifiers (percent) and target sizes for packaged app icons
SCALES = [100, 125, 150, 200, 250, 300, 400]
TARGETS = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 256]
# One image serves all three target-size forms: it meets 3:1 on both themes as drawn.
TARGET_FORMS = ["", "_altform-unplated", "_altform-lightunplated"]


def _bmp(png: bytes, path: Path):
    Image.open(io.BytesIO(png)).convert("RGB").save(path, "BMP")


def _panel(w, h, mark_frac, ground):
    """A flat panel with the mark centred, for the wizard bitmaps."""
    m = round(min(w, h) * mark_frac)
    inner = bare_mark("color").split(">", 1)[1].rsplit("</svg>", 1)[0]
    x, y = (w - m) / 2, (h - m) / 2 if h < w * 1.5 else h * 0.30 - m / 2
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}">'
            f'<rect width="{w}" height="{h}" fill="{ground}"/>'
            f'<svg x="{x}" y="{y}" width="{m}" height="{m}" viewBox="-2 -2 104 104">{inner}</svg></svg>')


def export(out: Path):
    app, inst, brand, win = out / "app", out / "installer", out / "brand", out / "windows"
    for d in (app, inst, brand, win):
        d.mkdir(parents=True, exist_ok=True)
    with Renderer() as r:
        pngs = {s: icon_png(r, s) for s in SIZES}
        ico = pack(pngs)
        (app / "icon.ico").write_bytes(ico)
        (inst / "setup.ico").write_bytes(ico)
        for s in (16, 32, 48, 64, 128, 256):
            (app / f"icon-{s}.png").write_bytes(pngs[s])
        (app / "icon.svg").write_text(app_icon(256), encoding="utf-8")
        (app / "mark.svg").write_text(bare_mark("color"), encoding="utf-8")
        (app / "mark-mono.svg").write_text(bare_mark("mono"), encoding="utf-8")
        for pct in SCALES:
            (win / f"Square44x44Logo.scale-{pct}.png").write_bytes(icon_png(r, round(44 * pct / 100)))
            (win / f"Square150x150Logo.scale-{pct}.png").write_bytes(tile_png(r, round(150 * pct / 100)))
        for t in TARGETS:
            png = pngs[t] if t in pngs else icon_png(r, t)
            for form in TARGET_FORMS:
                (win / f"Square44x44Logo.targetsize-{t}{form}.png").write_bytes(png)
        for i, (w, h) in enumerate(WIZARD_LARGE):
            _bmp(r.png(_panel(w, h, 0.62, NAVY), w, h), inst / f"wizard-large-{i + 1}.bmp")
        for i, (w, h) in enumerate(WIZARD_SMALL):
            _bmp(r.png(_panel(w, h, 0.78, CREAM), w, h), inst / f"wizard-small-{i + 1}.bmp")
        for theme in ("light", "dark"):
            svg, w, h = lockup(theme)
            (brand / f"lockup-{theme}.svg").write_text(svg, encoding="utf-8")
            (brand / f"lockup-{theme}.png").write_bytes(r.png(svg, round(w), round(h), scale=2))
    print(f"exported to {out}: .ico {len(ico):,} bytes, {len(SIZES)} sizes, "
          f"{len(list(win.glob('*.png')))} Windows assets")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    export(Path(sys.argv[1]))
