"""The chosen mark: Ledger 4e, a navy folder with a gold tab holding a request list.

The drawing: a navy folder back with a light rim, its tab in gold; a cream
sheet standing in it with a gold tick and two rules; an angled navy front
flap, rimmed all round, its top edge a lighter band. The rim is what keeps the
navy's edge on a dark taskbar; on a light one the navy inside the rim carries
it (SPEC-icon-ledger.md has the figures).

It is drawn two ways, because no single drawing is sharp at every size:
- 16, 20 and 24px are pixel art (PIXEL_ART): flat colours, no blended pixel,
  no rules and a larger tick;
- every other size is the 48-unit master fitted to its own pixel grid by
  icon_svg(s): each horizontal and vertical edge lands on a whole pixel and the
  rim is whole pixels, so only the slopes, the tick and the corner arcs blend.
  From 30 to 40px it is the small drawing (no rules) with a tick of whole
  pixels, because a blended tick that size smudges into a blot.
The pixel art keeps the fitted geometry's columns and rows but lifts the flap a
row where the sheet needs room, and draws the tick with its long arm at least
twice the short one: at these sizes an even tick reads as a V.
The vector masters (full_mark, app_icon) use the same drawing, unrounded.
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
RIM = "#9FB2D6"
TICK = "#9C7F2C"                    # gold-500 is too faint on cream for a mark this small
RULE = "#9AA6BC"
SHADOW = "#0A1F3D"

SIZES = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256]

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
..rnnnncccccccccttcnnr..
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


def _grad(gid, a, b):
    # 120 degrees in the CSS sense: from top-left toward bottom-right, 30 degrees below horizontal
    return (f'<linearGradient id="{gid}" x1="0.067" y1="0.25" x2="0.933" y2="0.75">'
            f'<stop offset="0" stop-color="{a}"/><stop offset="1" stop-color="{b}"/></linearGradient>')


def drawing(s, snap=True, shadow=True, uid="m", small=False):
    """The icon at s pixels (or s units, unsnapped): defs and shapes, no <svg> wrapper.

    snap=True puts every horizontal and vertical edge on a whole pixel and makes the
    rim and the flap's top band whole pixels; snap=False is the exact master.
    small=True is the drawing the pixel art starts from: no rules, a larger tick.
    """
    u = s / 48
    P = (lambda v: round(v * u)) if snap else (lambda v: v * u)
    rim = max(1, round(u)) if snap else u
    band = max(1, round(1.5 * u)) if snap else 1.5 * u
    rad = max(1, round(2 * u)) if snap else 2 * u
    frad = max(1, round(1.5 * u)) if snap else 1.5 * u

    x0, x1, top, body, y1 = P(5), P(43), P(7), P(11), P(40)
    t1, t2 = P(19), P(23)                       # the tab's slope: from (t1, top) to (t2, body)
    back = (f"M{f(x0)} {f(top + rad)}a{f(rad)} {f(rad)} 0 0 1 {f(rad)} {f(-rad)}H{f(t1)}L{f(t2)} {f(body)}"
            f"H{f(x1 - rad)}a{f(rad)} {f(rad)} 0 0 1 {f(rad)} {f(rad)}V{f(y1 - rad)}"
            f"a{f(rad)} {f(rad)} 0 0 1 {f(-rad)} {f(rad)}H{f(x0 + rad)}a{f(rad)} {f(rad)} 0 0 1 {f(-rad)} {f(-rad)}Z")
    tab = (f"M{f(x0 - 1)} {f(top - 1)}H{f(t1)}L{f(t2)} {f(body)}V{f(body + rim)}"
           f"H{f(x0 - 1)}Z")

    fx0, fx1, fx2, fx3, fy0, fy1 = P(9), P(46), P(42), P(5), P(24), P(40)
    flap = _rounded([(fx0, fy0), (fx1, fy0), (fx2, fy1), (fx3, fy1)], frad)

    sx0, sx1, sy0, sy1 = P(15), P(37), P(12), P(32)
    if small:
        tw = 3 * u
        tick = f"M{f(20 * u)} {f(19 * u)}l{f(2.88 * u)} {f(2.88 * u)}l{f(5.12 * u)} {f(-5.92 * u)}"
    else:
        tw = max(2, round(2 * u)) if snap else 2 * u
        tick = f"M{f(18.5 * u)} {f(17 * u)}l{f(1.8 * u)} {f(1.8 * u)}l{f(3.2 * u)} {f(-3.7 * u)}"
    if snap and small:
        tick_svg = _pixel_tick(math.floor(22.88 * u), round(21.88 * u), max(2, round(2.88 * u)), max(4, round(5.92 * u)))
    else:
        tick_svg = (f'<path d="{tick}" fill="none" stroke="{TICK}" stroke-width="{f(tw)}" '
                    'stroke-linecap="round" stroke-linejoin="round"/>')

    def rule(a, b, c, d):
        ry0, ry1 = P(c), max(P(c) + 1, P(d))
        return (f'<rect x="{f(P(a))}" y="{f(ry0)}" width="{f(P(b) - P(a))}" height="{f(ry1 - ry0)}" '
                f'rx="{f((ry1 - ry0) / 2)}" fill="{RULE}"/>')

    i = uid
    filt = (f'<filter id="{i}sh" x="-20%" y="-20%" width="140%" height="150%"><feDropShadow dx="0" '
            f'dy="{f(P(1) if snap else u)}" stdDeviation="{f(u)}" flood-color="{SHADOW}" flood-opacity="0.28"/></filter>')
    defs = (f"<defs>{_grad(i + 'b', *BACK)}{_grad(i + 'f', *FLAP)}{_grad(i + 't', *TAB)}{_grad(i + 's', *SHEET)}"
            f'{filt if shadow else ""}<clipPath id="{i}cb"><path d="{back}"/></clipPath>'
            f'<clipPath id="{i}cf"><path d="{flap}"/></clipPath></defs>')
    lift = f' filter="url(#{i}sh)"' if shadow else ""
    return (f'{defs}<g{lift}>'
            f'<path d="{back}" fill="url(#{i}b)"/>'
            f'<path d="{back}" fill="none" stroke="{RIM}" stroke-width="{f(2 * rim)}" clip-path="url(#{i}cb)"/>'
            f'<path d="{tab}" fill="url(#{i}t)" clip-path="url(#{i}cb)"/>'
            f'<rect x="{f(sx0)}" y="{f(sy0)}" width="{f(sx1 - sx0)}" height="{f(sy1 - sy0)}" rx="{f(rad)}" fill="url(#{i}s)"/>'
            f"{tick_svg}"
            f'{"" if small else rule(26, 34, 16, 18) + rule(19, 34, 21, 23)}'
            f'<path d="{flap}" fill="url(#{i}f)"/>'
            f'<path d="{flap}" fill="none" stroke="{RIM}" stroke-width="{f(2 * rim)}" clip-path="url(#{i}cf)"/>'
            f'<rect x="{f(fx3)}" y="{f(fy0)}" width="{f(fx1 - fx3)}" height="{f(band)}" fill="{RIM}" clip-path="url(#{i}cf)"/>'
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


def full_mark(ink=None, gold=None, uid="fm"):
    """The master drawing on a 100-unit grid, exact and without shadow.

    ink and gold are accepted so the lockup's call stays as it was; the mark is
    the same on every ground, so they are not used.
    """
    return f'<g transform="scale({f(100 / 48)})">{drawing(48, snap=False, shadow=False, uid=uid)}</g>'


def app_icon(s):
    """The whole icon as one vector SVG at s pixels, with its shadow (the rasters use raster.icon_png)."""
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48" width="{s}" height="{s}">'
            f"{drawing(48, snap=False, shadow=True)}</svg>")


def _mono():
    """One colour that follows the text: the folder solid, the sheet cut out, the tick and a gap above the flap."""
    m = drawing(48, snap=False, shadow=False, uid="mo")
    back = m.split('<path d="', 2)[1].split('"', 1)[0]
    flap = m.split('<clipPath id="mocf"><path d="', 1)[1].split('"', 1)[0]
    tick = "M18.5 17l1.8 1.8l3.2 -3.7"
    return (f'<defs><mask id="mom"><rect x="-2" y="-2" width="52" height="52" fill="#fff"/>'
            f'<rect x="15" y="12" width="22" height="20" rx="2" fill="#000"/>'
            f'<path d="{tick}" fill="none" stroke="#fff" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>'
            f'<path d="{flap}" fill="none" stroke="#000" stroke-width="3"/></mask></defs>'
            f'<g mask="url(#mom)" fill="currentColor"><path d="{back}"/></g>'
            f'<path d="{flap}" fill="currentColor"/>')


def bare_mark(theme):
    """The mark alone, for the app's surfaces: "color" for any ground, "mono" for contrast themes."""
    if theme == "mono":
        return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 48 48">{_mono()}</svg>'
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 104 104">{full_mark()}</svg>'
