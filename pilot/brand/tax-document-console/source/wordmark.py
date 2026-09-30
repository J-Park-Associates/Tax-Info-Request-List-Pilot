"""Set text as outlined SVG paths: shaped (kerned) by HarfBuzz, drawn by fontTools.

Outlines, not <text>, so the lockup renders the same inside an <img>, in an
installer, or on a PC without the webfonts - the caveat the design system
records against the firm's own lockup.
"""
import io
import re
import urllib.request
from functools import lru_cache
from pathlib import Path

import uharfbuzz as hb
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.ttLib import TTFont
from mark import f

FONTS = Path(__file__).parent / "fonts"

#: file name -> (Google Fonts family, weight). Fetched once into FONTS; both
#: faces are OFL-licensed and are the design system's own two voices.
FACES = {
    "PlayfairDisplay-700.woff": ("Playfair Display", 700),
    "Inter-600.woff": ("Inter", 600),
    "Inter-500.woff": ("Inter", 500),
}

# An old user agent makes the Google Fonts API answer with plain WOFF, which
# fontTools reads without extra compression libraries.
_UA = "Mozilla/5.0 (Windows NT 6.1) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/30.0 Safari/537.36"


def _fetch(name):
    family, weight = FACES[name]
    url = f"https://fonts.googleapis.com/css2?family={family.replace(' ', '+')}:wght@{weight}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": _UA})
        css = urllib.request.urlopen(req, timeout=30).read().decode()
        src = re.search(r"url\((https://[^)]+)\)", css)
        if not src:
            raise RuntimeError(f"no font URL in the Google Fonts answer for {family} {weight}")
        data = urllib.request.urlopen(src.group(1), timeout=30).read()
    except OSError as exc:
        raise SystemExit(f"Could not download {family} {weight} from Google Fonts ({exc}). "
                         f"Put {name} in {FONTS} by hand and run again.") from None
    FONTS.mkdir(exist_ok=True)
    (FONTS / name).write_bytes(data)


@lru_cache(None)
def _load(name):
    if not (FONTS / name).exists():
        _fetch(name)
    tt = TTFont(FONTS / name)
    tt.flavor = None
    buf = io.BytesIO()
    tt.save(buf)
    data = buf.getvalue()
    tt = TTFont(io.BytesIO(data))
    face = hb.Face(hb.Blob(data))
    return tt, hb.Font(face)


def metrics(name):
    tt, _ = _load(name)
    upm = tt["head"].unitsPerEm
    os2 = tt["OS/2"]
    return {"upm": upm, "cap": os2.sCapHeight / upm, "x": os2.sxHeight / upm}


def text_path(text, name, size, x, baseline, tracking=0.0):
    """Return (svg path data, advance width in px) for one line of text.

    `tracking` is in em, added after every glyph but the last, the way CSS
    letter-spacing would be if it were not also added after the last glyph.
    """
    tt, font = _load(name)
    upm = tt["head"].unitsPerEm
    scale = size / upm
    buf = hb.Buffer()
    buf.add_str(text)
    buf.guess_segment_properties()
    hb.shape(font, buf, {"kern": True, "liga": True})
    gs = tt.getGlyphSet()
    order = tt.getGlyphOrder()
    pen = SVGPathPen(gs, ntos=lambda v: f(v))
    pen_x = x
    n = len(buf.glyph_infos)
    for i, (info, pos) in enumerate(zip(buf.glyph_infos, buf.glyph_positions, strict=True)):
        gname = order[info.codepoint]
        tp = TransformPen(pen, (scale, 0, 0, -scale,
                                pen_x + pos.x_offset * scale, baseline - pos.y_offset * scale))
        gs[gname].draw(tp)
        pen_x += pos.x_advance * scale
        if i < n - 1:
            pen_x += tracking * size
    return pen.getCommands(), pen_x - x
