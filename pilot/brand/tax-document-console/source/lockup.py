"""The horizontal lockup for the chosen mark, as in the approved concept.

"Tax Document Console" in Playfair Display 700; "J PARK & ASSOCIATES" beneath
in Inter 600 caps, tracked 0.30em. Words in the tracked line are set one by one
with a fixed gap, so tracking does not also widen the word spaces.
"""
from mark import CREAM, FULL_W, GOLD, NAVY, f, full_mark
from wordmark import metrics, text_path

GOLD_TEXT_ON_LIGHT = "#7A5F16"   # gold-800: gold-500 is 2.0:1 on cream, not a text colour
PF, INTER = "PlayfairDisplay-700.woff", "Inter-600.woff"


def tracked(text, font, size, x, baseline, tracking, word_gap):
    paths, cx = [], x
    for i, word in enumerate(text.split(" ")):
        if i:
            cx += word_gap * size
        d, w = text_path(word, font, size, cx, baseline, tracking=tracking)
        paths.append(d)
        cx += w + tracking * size   # the tracking after a word's last letter, once
    return "".join(paths), cx - tracking * size - x


def lockup(theme):
    ink = CREAM if theme == "dark" else NAVY
    sub = GOLD if theme == "dark" else GOLD_TEXT_ON_LIGHT
    s1, s2 = 56, 15
    cap1, cap2 = metrics(PF)["cap"] * s1, metrics(INTER)["cap"] * s2
    gap = 18
    block = cap1 + gap + cap2
    mark_h = block * 1.12
    pad = 10
    # full_mark is cropped to the drawing: FULL_W by 100 units
    scale = mark_h / 100
    mark_w = FULL_W * scale
    top = pad + (mark_h - block) / 2
    tx = pad + mark_w + mark_h * 0.26
    b1 = top + cap1
    d1, w1 = text_path("Tax Document Console", PF, s1, tx, b1, tracking=0.0)
    d2, w2 = tracked("J PARK & ASSOCIATES", INTER, s2, tx + 1, b1 + gap + cap2, 0.30, 0.34)
    W = tx + max(w1, w2) + pad
    H = mark_h + 2 * pad
    svg = (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {f(W)} {f(H)}">'
           f'<g transform="translate({f(pad)} {f(pad)}) scale({f(scale)})">'
           f'{full_mark()}</g>'
           f'<path d="{d1}" fill="{ink}"/><path d="{d2}" fill="{sub}"/></svg>')
    return svg, W, H
