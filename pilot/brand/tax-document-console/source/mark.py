"""The chosen mark: Ledger 4e, a navy folder with a gold tab holding a request list.

The drawing: a navy folder back with a mid-blue rim, its tab in gold; a cream
sheet standing in it with a gold tick and two rules; an angled navy front
flap, rimmed all round, its top edge a band of the rim's colour. The rim and
the tab are the whole outline, and both meet 3:1 on a light and a dark
taskbar (SPEC-icon-ledger.md has the figures).

It is drawn in three bands, because no single drawing is sharp at every size:
- 16, 20 and 24px are pixel art (PIXEL_ART): flat colours, no blended pixel,
  no rules and a larger tick. They keep within a pixel of the fitted geometry, but at
  16 and 20 the flap sits a row lower so the sheet has room for its tick, and
  the tick's long arm is at least twice the short one: an even tick reads as
  a V at these sizes;
- 30 to 47px (30, 32, 36, 40 and Square44x44Logo's 44) are the master fitted
  to the size by icon_svg(s), without the rules, the tick built of whole
  pixels: a blended tick that small smudges into a blot;
- 48px and up are the full master fitted to the size: every horizontal and
  vertical edge on a whole pixel, the rim, band and radii whole pixels, so only
  the slopes, the tick, the rules' round ends and the corner arcs blend.
In both fitted bands, where the rim is one pixel (30 to 71px) the flap's sloped
sides take SLOPE_RIM, so their blended rim still holds 3:1 on a dark taskbar.
Fitting rounds half up (never Python's round-half-to-even, which sends edges
that fall on a half pixel in opposite directions) and places a length from a
snapped edge where two edges must stay a fixed distance apart.
The vector masters (full_mark, app_icon) use the same geometry, unrounded.
"""

import math

# The J Park & Associates design-system tokens, used by the lockup and the wizard panels
NAVY = "#1B2A4A"    # navy-900
GOLD = "#C9A84C"    # gold-500
CREAM = "#F5F0E8"   # cream-50

BACK = ("#2E4675", NAVY)            # the folder back, 120-degree gradient
FLAP = ("#3D5A92", "#2E4675")       # the front flap
TAB = ("#A8862F", "#94782A")        # gold dark enough for 3:1 on a light taskbar
SHEET = ("#FFFDF8", "#F0E9DC")
RIM = "#6A87C2"                     # 3:1 on both taskbars; a paler rim fails on light above the sheet
TICK = "#9C7F2C"                    # gold-500 is too faint on cream for a mark this small
RULE = "#9AA6BC"
SHADOW = "#0A1F3D"

SIZES = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256]

# The master geometry on its 48-unit grid. The drawing spans x 4-45 and y 7-40,
# so the master sits centred within half a unit (the flap overhangs the back on the right);
# fitted to a size, within half a unit plus half a pixel.
BACK_X = (4, 42)                    # the back's left and right edges
TOP, TAB_H, BOTTOM = 7, 4, 40       # the tab's top, its height (the body's top is TOP + TAB_H), the bottom
SLOPE = (18, 22)                    # the tab's slope runs from (18, TOP) to (22, TOP + TAB_H)
FLAP_TOP, FLAP_X_TOP, FLAP_X_BOTTOM = 24, (8, 45), (4, 41)
SHEET_BOX = (14, 12, 36, 32)        # x0, y0, x1, y1
TICK_PTS = ((17.5, 17), (19.3, 18.8), (22.5, 15.1))
RULES = ((25, 33, 16), (18, 33, 21))   # x0, x1, top; each 2 units tall
SMALL_TICK_CORNER = (21.88, 21.88)  # the whole-pixel tick's corner, 30-47px
DRAWN = (4, 7, 45, 40)              # the drawing's extent, for the lockup and the panels
SLOPE_RIM = 1.5                     # pixels: the least rim the flap's sloped sides take when fitted

# One letter per pixel, row 0 at the top: r rim, n navy, f flap, g gold tab,
# c cream sheet, t tick, . clear.
PIXEL_ART = {
    16: """
................
................
..gggg..........
..ggggg.........
..ggggggrrrrrr..
..rnnccccctcnr..
..rnncccctccnr..
..rnnctctcccnr..
..rnncctccccnr..
..rrrrrrrrrrrrr.
..rrffffffffffr.
..rrfffffffffr..
..rffffffffffr..
..rrrrrrrrrrrr..
................
................""",
    20: """
....................
....................
....................
..gggggg............
..ggggggg...........
..ggggggggrrrrrrrr..
..rnnnccccccctcnnr..
..rnnncccccctccnnr..
..rnnnctccctcccnnr..
..rnnncctctccccnnr..
..rnnnccctcccccnnr..
..rnrrrrrrrrrrrrrrr.
..rnrfffffffffffffr.
..rrffffffffffffffr.
..rrfffffffffffffr..
..rffffffffffffffr..
..rrrrrrrrrrrrrrrr..
....................
....................
....................""",
    24: """
........................
........................
........................
..ggggggg...............
..gggggggg..............
..gggggggggrrrrrrrrrrr..
..rnnnnccccccccccccnnr..
..rnnnnccccccccttccnnr..
..rnnnncccccccttcccnnr..
..rnnnnccttccttccccnnr..
..rnnnncccttttcccccnnr..
..rnnnnccccttccccccnnr..
..rnrrrrrrrrrrrrrrrrrrr.
..rnrfffffffffffffffffr.
..rnrfffffffffffffffffr.
..rrfffffffffffffffffr..
..rrfffffffffffffffffr..
..rfffffffffffffffffr...
..rfffffffffffffffffr...
..rrrrrrrrrrrrrrrrrrr...
........................
........................
........................
........................""",
}

PIXEL_COLOURS = {"r": RIM, "n": BACK[0], "f": FLAP[0], "g": TAB[0], "c": SHEET[0], "t": TICK}


def f(v):
    """Short number formatting for SVG output."""
    return f"{v:.3f}".rstrip("0").rstrip(".")


def _half_up(v):
    return math.floor(v + 0.5)


def _grad(gid, a, b):
    # 120 degrees in the CSS sense: from top-left toward bottom-right, 30 degrees below horizontal
    return (f'<linearGradient id="{gid}" x1="0.067" y1="0.25" x2="0.933" y2="0.75">'
            f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>')


def _geometry(s, snap):
    """Every shape's coordinates at s pixels (snap) or s units (exact), as SVG path data and boxes."""
    u = s / 48

    def P(v):        # a position: on the pixel grid when snapped
        return _half_up(v * u) if snap else v * u

    def L(v, least=1):   # a length: whole pixels, never under `least`, when snapped
        return max(least, _half_up(v * u)) if snap else v * u

    g = {"u": u, "rim": L(1), "band": L(1.5), "rad": L(2), "frad": L(1.5)}
    rad = g["rad"]
    x0, x1, top, y1 = P(BACK_X[0]), P(BACK_X[1]), P(TOP), P(BOTTOM)
    body = top + L(TAB_H)
    t1, t2 = P(SLOPE[0]), P(SLOPE[1])
    g["back"] = (f"M{f(x0)} {f(top + rad)}a{f(rad)} {f(rad)} 0 0 1 {f(rad)} {f(-rad)}H{f(t1)}L{f(t2)} {f(body)}"
                 f"H{f(x1 - rad)}a{f(rad)} {f(rad)} 0 0 1 {f(rad)} {f(rad)}V{f(y1 - rad)}"
                 f"a{f(rad)} {f(rad)} 0 0 1 {f(-rad)} {f(rad)}H{f(x0 + rad)}a{f(rad)} {f(rad)} 0 0 1 {f(-rad)} {f(-rad)}Z")
    g["tab"] = f"M{f(x0 - 1)} {f(top - 1)}H{f(t1)}L{f(t2)} {f(body)}V{f(body + g['rim'])}H{f(x0 - 1)}Z"
    fy0 = P(FLAP_TOP)
    g["flap_top"], g["flap_x"] = fy0, (P(FLAP_X_BOTTOM[0]), P(FLAP_X_TOP[1]))
    g["flap"] = _rounded([(P(FLAP_X_TOP[0]), fy0), (P(FLAP_X_TOP[1]), fy0),
                          (P(FLAP_X_BOTTOM[1]), y1), (P(FLAP_X_BOTTOM[0]), y1)], g["frad"])
    # A 1px rim on a slope is split across two half-tone pixels, neither 3:1 on a dark
    # taskbar, so where the rim is one pixel the flap's two sloped sides get SLOPE_RIM.
    # From 72px the rim is 2px or more and holds on its own; extra lines there would
    # stack on the flap's own stroke and make the slopes heavier than the bottom.
    g["slope_rim"] = SLOPE_RIM
    g["slopes"] = (((P(FLAP_X_TOP[0]), fy0, P(FLAP_X_BOTTOM[0]), y1),
                    (P(FLAP_X_TOP[1]), fy0, P(FLAP_X_BOTTOM[1]), y1))
                   if snap and g["rim"] < SLOPE_RIM else ())
    # the sheet's top is one rim below the body's top in the master, so it is laid off from it:
    # snapped separately the two can meet (the sheet hides the rim) or part (a navy gap)
    sx0, sy0 = P(SHEET_BOX[0]), (body + g["rim"]) if snap else P(SHEET_BOX[1])
    g["sheet"] = (sx0, sy0, L(SHEET_BOX[2] - SHEET_BOX[0]), L(SHEET_BOX[3] - SHEET_BOX[1]))
    (ax, ay), (bx, by), (cx, cy) = TICK_PTS
    g["tick"] = f"M{f(ax * u)} {f(ay * u)}L{f(bx * u)} {f(by * u)}L{f(cx * u)} {f(cy * u)}"
    g["tick_w"] = L(2, 2)
    g["rules"] = [(P(a), P(c), P(b) - P(a), L(2)) for a, b, c in RULES]   # one height for both
    if snap:
        vy = min(_half_up(SMALL_TICK_CORNER[1] * u), fy0 - 2)   # a clear row between tick and flap
        g["pixel_tick"] = (math.floor(SMALL_TICK_CORNER[0] * u), vy,
                           max(2, _half_up(2.88 * u)), max(4, vy - sy0 - 2))   # a clear row above
    return g


def drawing(s, snap=True, shadow=True, uid="m", small=False):
    """The icon at s pixels (or s units, unsnapped): defs and shapes, no <svg> wrapper.

    snap=True puts every horizontal and vertical edge on a whole pixel and makes the
    rim, band and radii whole pixels; snap=False is the exact master.
    small=True (with snap) is the 30-47px drawing: no rules, the tick of whole pixels.
    """
    g = _geometry(s, snap)
    i = uid
    if small:
        tick = _pixel_tick(*g["pixel_tick"])
        rules = ""
    else:
        tick = (f'<path d="{g["tick"]}" fill="none" stroke="{TICK}" stroke-width="{f(g["tick_w"])}" '
                'stroke-linecap="round" stroke-linejoin="round"/>')
        rules = "".join(f'<rect x="{f(x)}" y="{f(y)}" width="{f(w)}" height="{f(h)}" rx="{f(h / 2)}" fill="{RULE}"/>'
                        for x, y, w, h in g["rules"])
    sx, sy, sw, sh = g["sheet"]
    fx0, fx1 = g["flap_x"]
    filt = (f'<filter id="{i}sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" '
            f'dy="{f(_half_up(g["u"]) if snap else g["u"])}" stdDeviation="{f(g["u"])}" '
            f'flood-color="{SHADOW}" flood-opacity="0.28"/></filter>')
    defs = (f"<defs>{_grad(i + 'b', *BACK)}{_grad(i + 'f', *FLAP)}{_grad(i + 't', *TAB)}{_grad(i + 's', *SHEET)}"
            f'{filt if shadow else ""}<clipPath id="{i}cb"><path d="{g["back"]}"/></clipPath>'
            f'<clipPath id="{i}cf"><path d="{g["flap"]}"/></clipPath></defs>')
    lift = f' filter="url(#{i}sh)"' if shadow else ""
    return (f'{defs}<g{lift}>'
            f'<path d="{g["back"]}" fill="url(#{i}b)"/>'
            f'<path d="{g["back"]}" fill="none" stroke="{RIM}" stroke-width="{f(2 * g["rim"])}" clip-path="url(#{i}cb)"/>'
            f'<path d="{g["tab"]}" fill="url(#{i}t)" clip-path="url(#{i}cb)"/>'
            f'<rect x="{f(sx)}" y="{f(sy)}" width="{f(sw)}" height="{f(sh)}" rx="{f(g["rad"])}" fill="url(#{i}s)"/>'
            f"{tick}{rules}"
            f'<path d="{g["flap"]}" fill="url(#{i}f)"/>'
            f'<path d="{g["flap"]}" fill="none" stroke="{RIM}" stroke-width="{f(2 * g["rim"])}" clip-path="url(#{i}cf)"/>'
            + "".join(f'<line x1="{f(a)}" y1="{f(b)}" x2="{f(c)}" y2="{f(d)}" stroke="{RIM}" '
                      f'stroke-width="{f(2 * g["slope_rim"])}" clip-path="url(#{i}cf)"/>'
                      for a, b, c, d in g["slopes"]) +
            f'<rect x="{f(fx0)}" y="{f(g["flap_top"])}" width="{f(fx1 - fx0)}" height="{f(g["band"])}" '
            f'fill="{RIM}" clip-path="url(#{i}cf)"/>'
            "</g>")


def _pixel_tick(vx, vy, short, long):
    """A tick of whole 2-pixel cells: the corner pair at (vx, vy), arms rising one pixel per row."""
    cells = [(vx, vy)] + [(vx + k, vy - k) for k in range(1, long + 1)] + [(vx - k, vy - k) for k in range(1, short + 1)]
    return "".join(f'<rect x="{x}" y="{y}" width="2" height="1" fill="{TICK}"/>' for x, y in cells)


def _rounded(pts, r):
    """A closed polygon path with each corner rounded by a quadratic arc of reach r."""
    out = []
    n = len(pts)
    for k in range(n):
        (ax, ay), (bx, by), (cx, cy) = pts[k - 1], pts[k], pts[(k + 1) % n]
        da = ((ax - bx) ** 2 + (ay - by) ** 2) ** 0.5
        dc = ((cx - bx) ** 2 + (cy - by) ** 2) ** 0.5
        p = (bx + (ax - bx) * r / da, by + (ay - by) * r / da)
        q = (bx + (cx - bx) * r / dc, by + (cy - by) * r / dc)
        out.append(f"{'M' if k == 0 else 'L'}{f(p[0])} {f(p[1])}Q{f(bx)} {f(by)} {f(q[0])} {f(q[1])}")
    return "".join(out) + "Z"


def icon_svg(s):
    """The icon fitted to s pixels (not for the PIXEL_ART sizes); below 48px, the small drawing."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">'
            f"{drawing(s, snap=True, shadow=s >= 48, small=s < 48)}</svg>")


def pixel_art(s):
    """The PIXEL_ART drawing as rows of colours (None = clear)."""
    rows = PIXEL_ART[s].strip("\n").split("\n")
    if len(rows) != s or any(len(r) != s for r in rows):
        raise ValueError(f"the {s}px drawing is not {s} x {s}")
    bad = {ch for r in rows for ch in r} - set(PIXEL_COLOURS) - {"."}
    if bad:
        raise ValueError(f"the {s}px drawing uses unknown letters {sorted(bad)}")
    return [[PIXEL_COLOURS.get(ch) for ch in r] for r in rows]


# full_mark's frame: the drawing's extent scaled to 100 units tall
FULL_W = 100 * (DRAWN[2] - DRAWN[0]) / (DRAWN[3] - DRAWN[1])


def full_mark(uid="fm"):
    """The master drawing, exact and without shadow, cropped to its extent: FULL_W wide, 100 tall."""
    k = 100 / (DRAWN[3] - DRAWN[1])
    return (f'<g transform="scale({f(k)}) translate({-DRAWN[0]} {-DRAWN[1]})">'
            f"{drawing(48, snap=False, shadow=False, uid=uid)}</g>")


def app_icon(s):
    """The whole icon as one vector SVG at s pixels, with its shadow (the rasters use raster.icon_png)."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="{s}" height="{s}">'
            f"{drawing(48, snap=False, shadow=True)}</svg>")


def _mono():
    """One colour that follows the text: the folder solid, the sheet cut out, the tick and a gap above the flap."""
    g = _geometry(48, snap=False)
    sx, sy, sw, sh = g["sheet"]
    return (f'<defs><mask id="mom"><rect x="-2" y="-2" width="52" height="52" fill="#fff"/>'
            f'<rect x="{f(sx)}" y="{f(sy)}" width="{f(sw)}" height="{f(sh)}" rx="{f(g["rad"])}" fill="#000"/>'
            f'<path d="{g["tick"]}" fill="none" stroke="#fff" stroke-width="{f(g["tick_w"])}" '
            'stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{g["flap"]}" fill="none" stroke="#000" stroke-width="3"/></mask></defs>'
            f'<g mask="url(#mom)" fill="currentColor"><path d="{g["back"]}"/></g>'
            f'<path d="{g["flap"]}" fill="currentColor"/>')


def bare_mark(theme):
    """The mark alone, for the app's surfaces: "color" for any ground, "mono" (24px and up) for contrast themes."""
    if theme == "mono":
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">{_mono()}</svg>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 {f(FULL_W + 4)} 104">{full_mark()}</svg>'
