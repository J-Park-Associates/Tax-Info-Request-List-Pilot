"""Rasterise the chosen icon: the plate supersampled 8x, the mark at 1x on top.

Chromium anti-aliases a rounded rectangle's top and bottom corners slightly
differently; drawing the plate at 8x and box-filtering it down makes all four
corners identical. The mark is drawn at 1x so its whole-pixel edges and its
pixel-stair curves stay exactly as drawn.
"""
import io

from mark import mark_svg, plate_svg
from PIL import Image


def icon_png(r, s) -> bytes:
    plate = Image.open(io.BytesIO(r.png(plate_svg(s), s, scale=8))).convert("RGBA")
    plate = plate.resize((s, s), Image.BOX)
    mark = Image.open(io.BytesIO(r.png(mark_svg(s), s))).convert("RGBA")
    plate.alpha_composite(mark)
    plate.putalpha(plate.getchannel("A").point(lambda a: 0 if a < 8 else a))
    buf = io.BytesIO()
    plate.save(buf, "PNG", optimize=True)
    return buf.getvalue()
