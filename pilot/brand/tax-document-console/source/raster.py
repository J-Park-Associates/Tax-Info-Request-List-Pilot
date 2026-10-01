"""Rasterise the chosen icon at an exact pixel size.

16, 20 and 24px are painted straight from the pixel art, one pixel per letter,
so not one pixel is blended. Every other size is the drawing fitted to that
size's own pixel grid (mark.icon_svg) and rendered by Chromium; the fitting,
not a resize of a bigger render, is what keeps its straight edges sharp.
"""
import io

from mark import PIXEL_ART, icon_svg, pixel_art
from PIL import Image


def _png(im: Image.Image) -> bytes:
    buf = io.BytesIO()
    im.save(buf, "PNG", optimize=True)
    return buf.getvalue()


def _hex(c):
    return tuple(int(c[i:i + 2], 16) for i in (1, 3, 5)) + (255,)


def icon_png(r, s) -> bytes:
    if s in PIXEL_ART:
        im = Image.new("RGBA", (s, s), (0, 0, 0, 0))
        for y, row in enumerate(pixel_art(s)):
            for x, c in enumerate(row):
                if c:
                    im.putpixel((x, y), _hex(c))
        return _png(im)
    im = Image.open(io.BytesIO(r.png(icon_svg(s), s))).convert("RGBA")
    im.putalpha(im.getchannel("A").point(lambda a: 0 if a < 8 else a))   # no near-invisible fringe
    return _png(im)


def tile_png(r, tile) -> bytes:
    """A Square150x150Logo tile: the icon fitted at two thirds of the tile, centred on a whole pixel."""
    art = round(tile * 2 / 3)
    im = Image.new("RGBA", (tile, tile), (0, 0, 0, 0))
    im.alpha_composite(Image.open(io.BytesIO(icon_png(r, art))).convert("RGBA"), ((tile - art) // 2,) * 2)
    return _png(im)
