"""The chosen mark, redrawn as exact geometry from the approved concept image.

The concept: a monogram frame - a top bar, a t (stem with a crossing bar) at
the left, a J-hook closing the lower right - holding a cream diamond ring with
a gold diamond core, and a gold folded corner at the top right.

It is drawn three ways, because no single drawing is sharp at every size:
- 16, 20 and 24px are drawn pixel by pixel (PIXEL_ART), with no blended edge
  except the plate's rounded corners;
- 30 to 256px are the vector drawing with every straight edge rounded to a
  whole pixel and a whole-pixel stroke from BIG. Up to 64px the J's curve is
  whole-pixel cells too; at 30-36 the centre is a whole-pixel gold diamond
  (the ring's band would be under two pixels), at 40-64 the ring and core are
  whole-pixel cells, and from 72 up they are vector diamonds;
- the SVG masters use the same drawing on its 100-unit grid, unrounded.
"""
import math

# The J Park & Associates design-system tokens
NAVY = "#1B2A4A"    # navy-900: the plate, and the mark on light grounds
GOLD = "#C9A84C"    # gold-500: the one accent
CREAM = "#F5F0E8"   # cream-50: the mark on navy


def f(v):
    """Short number formatting for SVG output."""
    return f"{v:.3f}".rstrip("0").rstrip(".")

SIZES = [16, 20, 24, 30, 32, 36, 40, 48, 60, 64, 72, 80, 96, 128, 256]

THEMES = {
    "dark": (CREAM, GOLD),
    "light": (NAVY, GOLD),
    "mono": ("currentColor", "currentColor"),
}

# c = cream, g = gold, . = the plate. Row 0 is the top pixel row.
PIXEL_ART = {
    16: """
................
................
..ccccccccc.gg..
.............g..
...c............
...c............
..ccc...g....c..
...c...ggg...c..
...c..ggggg..c..
...c...ggg...c..
...c....g....c..
...c.........c..
...c.........c..
...c...cccccc...
................
................""",
    20: """
....................
....................
....................
...ccccccccc.gggg...
...ccccccccc.gggg...
...............gg...
....cc.........gg...
....cc..............
...cccc...g....cc...
...cccc..ggg...cc...
....cc..ggggg..cc...
....cc...ggg...cc...
....cc....g....cc...
....cc.........cc...
....cc.........cc...
....cc...ccccccc....
....cc...cccccc.....
....................
....................
....................""",
    24: """
........................
........................
........................
........................
....ccccccccccc.gggg....
....ccccccccccc.gggg....
..................gg....
......cc..........gg....
......cc................
....cccccc........cc....
....cccccc..g.....cc....
......cc...ggg....cc....
......cc..ggggg...cc....
......cc...ggg....cc....
......cc....g.....cc....
......cc..........cc....
......cc..........cc....
......cc..........cc....
......cc...cccccccc.....
......cc...ccccccc......
........................
........................
........................
........................""",
}

# size: (mark width in px, stroke in px) for the snapped vector sizes
BIG = {30: (22, 3), 32: (22, 3), 36: (24, 3), 40: (28, 3), 48: (30, 3), 60: (34, 4),
       64: (34, 4), 72: (38, 5), 80: (42, 5), 96: (50, 6), 128: (66, 8), 256: (128, 16)}


# size: (gold core, ring inner, ring outer) as cell distances from the centre pixel;
# the two-level clear band between core and ring keeps them from touching diagonally
PIXEL_RING = {40: (2, 5, 7), 48: (2, 5, 7), 60: (3, 6, 9), 64: (3, 6, 9)}


def _diamond(cx, cy, r):
    return f"M{f(cx)} {f(cy - r)}L{f(cx + r)} {f(cy)}L{f(cx)} {f(cy + r)}L{f(cx - r)} {f(cy)}Z"


def drawing(M, t, ink, gold, snap=True, ring=True, pixel_ring=None, pixel_j=False):
    """The mark in a box M wide with stroke t; one grid unit is M/100."""
    u = M / 100

    def R(v):
        return round(v * u) if snap else v * u

    one = 1 if snap else 0
    bar_end = R(76)
    ys = t + max(one, R(8))                     # the stem's top, a gap below the top bar
    # the ascender above the crossbar is never shorter than the stroke: up to 64px the
    # crossbar moves down; above that the stem reaches up instead, so the crossbar keeps
    # its clearance from the ring
    if snap and M <= 34:
        cb = ys + max(one, R(10), t)
    else:
        cb = ys + max(one, R(10))
        ys = cb - max(t, R(10))
    sx = R(10)
    ro = R(30)
    ri = ro - t
    jc = M - ro                                 # the J curve's centre, on both axes
    # the gold folded corner: flush with the top bar, arms never under 3/4 of the stroke,
    # a square L at least two pixels wider than its arm so the notch always shows; the
    # top bar stops one pixel short of it
    if snap:
        a = max(R(9), math.ceil(0.75 * t - 1e-9))
        L = max(R(18), a + 2)
        k0 = min(max(R(82), bar_end + 1), M - L)
        bar_end = min(bar_end, k0 - 1)
    else:
        a, L, k0 = R(9), R(18), R(82)
    ink_d = (
        f"M0 0H{f(bar_end)}V{f(t)}H0Z"
        f"M{f(sx)} {f(ys)}H{f(sx + t)}V{f(M)}H{f(sx)}Z"
        f"M0 {f(cb)}H{f(2 * sx + t)}V{f(cb + t)}H0Z"   # arms equal either side of the stem
    )
    if pixel_j:
        # below 48px the curve is whole pixels: a cell is in when its centre lies in the
        # ring, so the stair is exactly mirror-symmetric about the diagonal
        jtop = max(R(26), L + 2)                # two clear rows under the gold corner
        ink_d += f"M{M - t} {jtop}H{M}V{jc}H{M - t}ZM{R(40)} {M - t}H{jc}V{M}H{R(40)}Z"
        for j in range(ro):
            for i in range(ro):
                d = ((i + 0.5) ** 2 + (j + 0.5) ** 2) ** 0.5
                if ri <= d <= ro:
                    ink_d += f"M{jc + i} {jc + j}h1v1h-1Z"
    else:
        ink_d += (f"M{f(M - t)} {f(R(26))}H{f(M)}V{f(jc)}A{f(ro)} {f(ro)} 0 0 1 {f(jc)} {f(M)}"
                  f"H{f(R(40))}V{f(M - t)}H{f(jc)}A{f(ri)} {f(ri)} 0 0 0 {f(M - t)} {f(jc)}Z")
    # the ring centred between the t's stem and the J's inner edge
    # (whole pixels for the cell ring; the vector ring may sit on a half pixel)
    mid = sx + M
    cx, cy = ((mid // 2 if pixel_ring else mid / 2) if snap else 55), R(54)
    corner = f"M{f(k0)} 0H{f(M)}V{f(L)}H{f(M - a)}V{f(a)}H{f(k0)}Z"
    # the crossbar overlaps the stem, so the frame fills nonzero; only the ring is evenodd
    out = [f'<path d="{ink_d}" fill="{ink}"/>', f'<path d="{corner}" fill="{gold}"/>']
    if pixel_ring:
        # up to 64px a vector ring blurs on its diagonals; draw ring and core as cells
        # by distance from the centre pixel (PIXEL_RING)
        core, ring_in, ring_out = pixel_ring
        for dy in range(-ring_out, ring_out + 1):
            for dx in range(-ring_out, ring_out + 1):
                d = abs(dx) + abs(dy)
                colour = ink if ring_in <= d <= ring_out else gold if d <= core else None
                if colour:
                    out.append(f'<rect x="{cx + dx}" y="{cy + dy}" width="1" height="1" fill="{colour}"/>')
    elif ring:
        out.append(f'<path d="{_diamond(cx, cy, R(26)) + _diamond(cx, cy, R(15))}" '
                   f'fill="{ink}" fill-rule="evenodd"/>')
        out.append(f'<path d="{_diamond(cx, cy, R(10))}" fill="{gold}"/>')
    else:
        out.append(_even_diamond((sx + M) // 2, R(54), 8, gold))
    return "".join(out)


def _even_diamond(x_edge, y_edge, w, colour):
    """A gold diamond w (even) pixels across centred on a pixel corner, rows 2, 4, ..., w, w, ..., 2.

    Used at 30-36px, where the space between the t's stem and the J is an even
    number of pixels, so only an even diamond sits exactly centred in it.
    """
    rows = list(range(2, w + 1, 2))
    rows = rows + rows[::-1]
    top = y_edge - len(rows) // 2
    return "".join(f'<rect x="{x_edge - n // 2}" y="{top + i}" width="{n}" height="1" fill="{colour}"/>'
                   for i, n in enumerate(rows))


def full_mark(ink, gold):
    """The master drawing on its 100-unit grid, stroke 12."""
    return drawing(100, 12, ink, gold, snap=False)


def _art(s):
    rows = PIXEL_ART[s].strip("\n").split("\n")
    if len(rows) != s or any(len(r) != s for r in rows):
        raise ValueError(f"the {s}px drawing is not {s} x {s}")
    out = []
    for y, row in enumerate(rows):
        for colour, ch in ((CREAM, "c"), (GOLD, "g")):
            x = 0
            while x < s:
                if row[x] != ch:
                    x += 1
                    continue
                x1 = x
                while x1 < s and row[x1] == ch:
                    x1 += 1
                out.append(f'<rect x="{x}" y="{y}" width="{x1 - x}" height="1" fill="{colour}"/>')
                x = x1
    return "".join(out)


def plate(s):
    inset = {16: 0, 20: 1, 24: 1, 30: 1, 32: 1, 36: 1, 40: 1, 48: 2}.get(s, round(s / 16))
    size = s - 2 * inset
    r = max(3, round(size * 0.22))       # a whole-pixel radius: no spill beside the corners
    rim = ""
    if s >= 16:  # a faint cream rim so the navy plate keeps its edge on a dark taskbar
        w = 1 if s < 192 else 2
        rim = (f'<rect x="{f(inset + w / 2)}" y="{f(inset + w / 2)}" width="{f(size - w)}" '
               f'height="{f(size - w)}" rx="{f(r - w / 2)}" fill="none" stroke="{CREAM}" '
               f'stroke-opacity="0.16" stroke-width="{f(w)}"/>')
    return inset, size, (f'<rect x="{inset}" y="{inset}" width="{size}" height="{size}" '
                         f'rx="{f(r)}" fill="{NAVY}"/>{rim}')


def plate_svg(s):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">{plate(s)[2]}</svg>'


def mark_svg(s):
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">{_body(s)}</svg>'


def app_icon(s):
    """The whole icon as one SVG (the vector master; rasters use raster.icon_png)."""
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {s} {s}">{plate(s)[2]}{_body(s)}</svg>'


def _body(s):
    inset, size, _ = plate(s)
    if s in PIXEL_ART:
        body = _art(s)
    else:
        M, t = BIG[s]
        x0 = inset + (size - M) // 2
        body = (f'<g transform="translate({x0} {x0})">'
                f'{drawing(M, t, CREAM, GOLD, ring=s >= 40, pixel_ring=PIXEL_RING.get(s), pixel_j=s <= 64)}</g>')
    return body


def bare_mark(theme):
    ink, gold = THEMES[theme]
    return f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="-2 -2 104 104">{full_mark(ink, gold)}</svg>'
