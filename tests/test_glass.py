"""The glass theme (pilot SPEC-glass): its lens map, page hooks, style and script.

Everything is read as text; nothing here needs a browser. The rendered checks
(contrast sweep, reduced-preference emulation, speed) run in scratch scripts
and their results are recorded in the handoff.
"""

import base64
import importlib
import importlib.util
import re
import struct
import zlib
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "app" / "renderer"


def _load_lens_generator():
    spec = importlib.util.spec_from_file_location("make_glass_lens", REPO / "pilot" / "make_glass_lens.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _decode_png(data: bytes):
    assert data[:8] == b"\x89PNG\r\n\x1a\n"
    pos, idat, header = 8, b"", None
    while pos < len(data):
        (length,) = struct.unpack(">I", data[pos : pos + 4])
        kind = data[pos + 4 : pos + 8]
        body = data[pos + 8 : pos + 8 + length]
        if kind == b"IHDR":
            header = struct.unpack(">IIBBBBB", body)
        elif kind == b"IDAT":
            idat += body
        pos += 12 + length
    return header, zlib.decompress(idat)


def test_the_lens_map_is_what_its_generator_draws():
    lens = _load_lens_generator()
    header, raw = _decode_png((RENDERER / "glass-lens.png").read_bytes())
    assert header == (lens.SIZE, lens.SIZE, 8, 2, 0, 0, 0)
    stride = 1 + lens.SIZE * 3
    assert len(raw) == stride * lens.SIZE
    for y in range(lens.SIZE):
        row = raw[y * stride : (y + 1) * stride]
        assert row[0] == 0, y
        for x in range(lens.SIZE):
            assert tuple(row[1 + x * 3 : 4 + x * 3]) == lens.pixel(x, y), (x, y)


# ── Reading the theme's files ────────────────────────────────────────────

GLASS_CSS = RENDERER / "glass.css"
GLASS_JS = RENDERER / "glass.js"
HTML = RENDERER / "index.html"

# The closed list of app selectors glass.css may restyle (P33). Adding one
# means adding it here, in the same commit, where a reviewer sees it.
GLASS_TARGETS = (
    ".topbar", ".brand-product", ".main", ".toolbar", "#eng-select", ".btn",
    "#review-card", "#reminder-card", "#moved-card", "#review-list",
    "#moved-list", "#review-deck", "#dismissed-card", ".rem-preview",
    ".rem-stages", ".card", ".modal", ".modal-overlay", ".chip",
)
OWN_NAMES = (":root", "body", ".glass-", "#glass-")
PILOT_NAMES = (".pilot-", "#pilot-")
SCOPES = (":root.glass-standard ", ":root.glass-full ", ":root.glass-solid ",
          ":root.glass-scrolled ", ":root.glass-paused ")
REDUCED = ("prefers-reduced-transparency", "prefers-reduced-motion",
           "prefers-contrast", "forced-colors")
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\bhsla?\(")


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8")


class Rule:
    def __init__(self, selector, body, at, order):
        self.selectors = [s.strip() for s in selector.split(",") if s.strip()]
        self.at = at
        self.order = order
        self.decls = split_declarations(body)

    def value(self, prop):
        for name, value in self.decls:
            if name == prop:
                return value
        return None

    def props(self):
        return [name for name, _ in self.decls]


def split_declarations(body):
    out, depth, current = [], 0, ""
    for ch in body:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == ";" and depth == 0:
            out.append(current)
            current = ""
        else:
            current += ch
    out.append(current)
    pairs = []
    for item in out:
        if ":" in item:
            name, value = item.split(":", 1)
            pairs.append((name.strip(), " ".join(value.split())))
    return pairs


def parse_css(text, at=(), counter=None):
    counter = counter if counter is not None else [0]
    rules, i = [], 0
    while True:
        j = text.find("{", i)
        if j == -1:
            return rules
        prelude = text[i:j].strip()
        depth, k = 1, j + 1
        while depth:
            depth += {"{": 1, "}": -1}.get(text[k], 0)
            k += 1
        body = text[j + 1:k - 1]
        counter[0] += 1
        if prelude.startswith("@"):
            if prelude.startswith(("@media", "@supports", "@starting-style", "@keyframes")):
                rules.extend(parse_css(body, at + (" ".join(prelude.split()),), counter))
        else:
            rules.append(Rule(prelude, body, at, counter[0]))
        i = k


def glass_rules():
    text = re.sub(r"/\*.*?\*/", "", read(GLASS_CSS), flags=re.S)
    return parse_css(text)


def token(name, rules=None):
    """A custom property's value from glass.css's own :root block."""
    for rule in rules or glass_rules():
        if rule.selectors == [":root"] and not rule.at:
            value = rule.value(name)
            if value is not None:
                return value
    raise AssertionError(name)


def px(value):
    assert value.endswith("px"), value
    return float(value[:-2])


def ms(value):
    if value.endswith("ms"):
        return float(value[:-2])
    assert value.endswith("s"), value
    return float(value[:-1]) * 1000


def keyframes(rule):
    return any(a.startswith("@keyframes") for a in rule.at)


# ── The page ─────────────────────────────────────────────────────────────

def test_the_page_loads_the_glass_last():
    html = read(HTML)
    assert html.count('href="glass.css"') == 1 and html.count('src="glass.js"') == 1
    assert html.index('href="glass.css"') > html.index('href="pilot-style.css"')
    assert html.index('src="glass.js"') > html.index('src="tour.js"')


def test_the_refraction_filter_is_markup_the_policy_allows():
    html = read(HTML)
    block = re.search(r'<svg class="glass-defs".*?</svg>', html, flags=re.S)
    assert block, "the refraction <svg> is missing"
    svg = block.group(0)
    assert svg.count('<filter id="glass-refract"') == 1
    assert svg.count("<feImage") == 1 and svg.count("<feDisplacementMap") == 1
    assert "style=" not in svg and "<script" not in svg
    assert not re.search(r"\son\w+=", svg)
    href = re.search(r'<feImage[^>]*\shref="([^"]+)"', svg).group(1)
    lens = (RENDERER / "glass-lens.png").read_bytes()
    if href.startswith("data:image/png;base64,"):
        assert base64.b64decode(href.split(",", 1)[1]) == lens
    else:
        assert href == "glass-lens.png" and (RENDERER / href).is_file()
    assert ("default-src 'none'; script-src 'self'; style-src 'self'; "
            "img-src 'self' data:; font-src 'self'") in html


def test_the_page_changes_only_by_the_glass_lines():
    """index.html's glass additions are the three of SPEC-glass section 3."""
    html = read(HTML)
    assert html.count("glass") == html.count("glass.css") + html.count("glass-defs") \
        + html.count("glass-refract") + html.count("glass.js") + html.count("glass-lens")


# ── What glass.css may touch ─────────────────────────────────────────────

def test_the_glass_style_targets_only_what_it_is_allowed():
    allowed = OWN_NAMES + PILOT_NAMES + GLASS_TARGETS
    bad = []
    for rule in glass_rules():
        if keyframes(rule):
            assert all(s in ("from", "to") for s in rule.selectors), rule.selectors
            continue
        for selector in rule.selectors:
            for scope in SCOPES:
                if selector.startswith(scope):
                    selector = selector[len(scope):]
                    break
            if not selector.startswith(allowed):
                bad.append(selector)
    assert not bad, bad


def test_every_glass_target_is_on_the_page():
    html, style = read(HTML), read(RENDERER / "style.css")
    for target in GLASS_TARGETS:
        name = target[1:]
        if target.startswith("#"):
            assert f'id="{name}"' in html, target
        else:
            in_html = re.search(rf'class="[^"]*\b{re.escape(name)}\b[^"]*"', html)
            in_style = re.search(rf"\.{re.escape(name)}\b", style)
            assert in_html or in_style, target


def test_the_glass_style_types_colour_only_in_its_tokens():
    bad = []
    for rule in glass_rules():
        for name, value in rule.decls:
            if name.startswith("--"):
                continue
            # A mask is read for its alpha, never painted, so its #000 is not a colour.
            if name in ("-webkit-mask", "mask") and value.replace("#000", "").count("#") == 0:
                continue
            if COLOUR.search(value):
                bad.append((rule.selectors, name, value))
    assert not bad, bad


def test_the_glass_leaves_the_status_chips_and_the_reminder_colours_alone():
    css = read(GLASS_CSS)
    assert not re.search(r"\.chip-", css)
    for name in ("--stage-ink", "--rem-ink", "--rem-paper"):
        assert name not in css


# ── Contrast (SPEC-glass 10.2, P42) ──────────────────────────────────────

def hex_rgb(value):
    value = value.strip().lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))


def rgba(value):
    m = re.fullmatch(r"rgba\((\d+),\s*(\d+),\s*(\d+),\s*([\d.]+)\)", value.strip())
    return (int(m[1]), int(m[2]), int(m[3])), float(m[4])


def saturate(rgb, s):
    r, g, b = rgb
    out = (
        (0.213 + 0.787 * s) * r + (0.715 - 0.715 * s) * g + (0.072 - 0.072 * s) * b,
        (0.213 - 0.213 * s) * r + (0.715 + 0.285 * s) * g + (0.072 - 0.072 * s) * b,
        (0.213 - 0.213 * s) * r + (0.715 - 0.715 * s) * g + (0.072 + 0.928 * s) * b,
    )
    return tuple(min(255.0, max(0.0, c)) for c in out)


def bright(rgb, b):
    return tuple(min(255.0, c * b) for c in rgb)


def over(top, alpha, bottom):
    return tuple(t * alpha + u * (1 - alpha) for t, u in zip(top, bottom))


def luminance(rgb):
    def lin(c):
        c /= 255
        return c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
    r, g, b = (lin(c) for c in rgb)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def ratio(a, b):
    hi, lo = sorted((luminance(a), luminance(b)), reverse=True)
    return (hi + 0.05) / (lo + 0.05)


def test_every_text_on_glass_meets_aa_contrast():
    rules = glass_rules()
    style = read(RENDERER / "style.css")
    sat, brt = float(token("--glass-saturate", rules)), float(token("--glass-brightness", rules))

    stops = [hex_rgb(h) for h in re.findall(r"#[0-9a-fA-F]{6}", token("--glass-backdrop-linear", rules))]
    glows = [rgba(c + ")")[0] for c in re.findall(r"(rgba\([^)]*)\)", token("--glass-backdrop-glows", rules))]
    navy_deep = hex_rgb(re.search(r"--navy-deep:\s*(#[0-9a-fA-F]{6})", style)[1])
    pilot_css = read(RENDERER / "pilot-style.css")
    dim_rgb, dim_alpha = rgba(re.search(
        r"\.pilot-terms-overlay\s*\{[^}]*background:\s*(rgba\([^)]*\))", pilot_css)[1])
    assert dim_alpha == 0.6

    mid = tuple((a + b) / 2 for a, b in zip(stops[0], stops[1]))
    # Why each set: the header sits over the top of the fixed backdrop only,
    # since nothing scrolls under it; the cards never overlap each other or the
    # header, so only the fixed backdrop is behind them; the toolbar also has
    # the solid lists (white) and the darkest navy scrolling under it; a dialog
    # sits over the whole page, dimmed by the strongest overlay the page uses.
    header_set = [stops[0], stops[1], glows[0], mid]
    card_set = stops + glows
    toolbar_set = card_set + [(255, 255, 255), navy_deep]
    strong_set = toolbar_set + [over(dim_rgb, dim_alpha, c) for c in toolbar_set]

    def corners(candidates):
        seen = [bright(saturate(c, sat), brt) for c in candidates]
        return [tuple(min(c[i] for c in seen) for i in range(3)),
                tuple(max(c[i] for c in seen) for i in range(3))]

    def surface(name, candidates):
        tint, alpha = rgba(token(name, rules))
        return [over(tint, alpha, c) for c in corners(candidates)]

    def text(name):
        value = token(name, rules)
        return hex_rgb(value)

    body_text = [hex_rgb(re.search(r"--text:\s*(#[0-9a-fA-F]{6})", style)[1]),
                 hex_rgb(re.search(r"--navy:\s*(#[0-9a-fA-F]{6})", style)[1]),
                 text("--glass-secondary"), text("--glass-accent"),
                 text("--glass-ok"), text("--glass-warn")]
    bar_text = [text("--glass-on-bar"), text("--glass-on-bar-soft")]

    toolbar = surface("--glass-tint-toolbar", toolbar_set)
    control_tint, control_alpha = rgba(token("--glass-control", rules))
    surfaces = {
        "header": (surface("--glass-tint-bar", header_set), bar_text),
        "card": (surface("--glass-tint", card_set), body_text),
        "toolbar": (toolbar, body_text),
        "dialog": (surface("--glass-tint-strong", strong_set), body_text),
        "toolbar control": ([over(control_tint, control_alpha, c) for c in toolbar], body_text),
    }
    for name, (backs, texts) in surfaces.items():
        for back in backs:
            for fore in texts:
                got = ratio(fore, back)
                assert got >= 4.5, f"{name}: text {fore} on {tuple(round(c) for c in back)} is {got:.2f}:1"

    solid = next(r for r in rules if r.selectors == [":root.glass-solid"])
    for name, texts in (("--glass-tint-bar", bar_text), ("--glass-tint", body_text),
                        ("--glass-tint-toolbar", body_text), ("--glass-tint-strong", body_text),
                        ("--glass-control", body_text)):
        back = hex_rgb(solid.value(name))
        for fore in texts:
            assert ratio(fore, back) >= 4.5, (name, fore)


# ── Levels and fallbacks ─────────────────────────────────────────────────

def test_refraction_is_used_only_at_the_full_level():
    for rule in glass_rules():
        for name, value in rule.decls:
            if "url(#" in value:
                assert "url(#glass-refract)" in value
                assert all(s.startswith(":root.glass-full") for s in rule.selectors), (rule.selectors, name)


def test_every_glass_rule_reads_its_filter_from_a_token():
    found = 0
    for rule in glass_rules():
        value = rule.value("backdrop-filter")
        if value is not None:
            found += 1
            assert re.fullmatch(r"var\(--glass-filter[a-z-]*\)", value), (rule.selectors, value)
    assert found


def test_the_system_asking_for_less_makes_the_screen_solid_and_still():
    rules = glass_rules()
    levels = [r for r in rules if not r.at and r.selectors and r.selectors[0] in (":root", ":root.glass-full", ":root.glass-solid")]
    last_level = max(r.order for r in levels)
    solid = next(r for r in rules if r.selectors == [":root.glass-solid"])
    every = [":root", ":root.glass-standard", ":root.glass-full", ":root.glass-solid"]

    media = [r for r in rules if r.at and r.at[0].startswith("@media")
             and all(f in r.at[0] for f in REDUCED)]
    assert media, "the reduced-preference @media block is missing"
    block = [r for r in media if r.selectors == every]
    assert len(block) == 1 and block[0].decls == solid.decls
    assert any(r.selectors == [":root.glass-full body::before"] and r.value("animation") == "none" for r in media)

    supports = [r for r in rules if r.at and r.at[0] == "@supports not (backdrop-filter: blur(1px))"]
    assert len(supports) == 1 and supports[0].selectors == every and supports[0].decls == solid.decls
    assert min(r.order for r in media) > last_level and supports[0].order > max(r.order for r in media)

    for name, value in solid.decls:
        if name.startswith("--glass-filter"):
            assert value == "none", name
        if name.startswith(("--glass-tint", "--glass-control")) and name != "--glass-control-gloss":
            assert re.fullmatch(r"#[0-9a-fA-F]{6}", value), (name, value)
    assert solid.value("--glass-sheen") == "transparent"


# ── Motion ───────────────────────────────────────────────────────────────

MOTION_OK = {"transform", "opacity", "box-shadow", "background-color"}
SPOT_OK = {"top", "left", "width", "height", "border-radius"}


def transition_items(value):
    items, depth, current = [], 0, ""
    for ch in value:
        depth += {"(": 1, ")": -1}.get(ch, 0)
        if ch == "," and depth == 0:
            items.append(current.strip())
            current = ""
        else:
            current += ch
    items.append(current.strip())
    return items


def test_motion_moves_only_what_the_compositor_can():
    seen = 0
    for rule in glass_rules():
        if keyframes(rule):
            assert {n for n in rule.props()} <= {"transform"}, rule.selectors
            continue
        value = rule.value("transition")
        if value is None:
            continue
        for item in transition_items(value):
            seen += 1
            prop = item.split()[0]
            if prop == "display":
                assert "allow-discrete" in item
            elif rule.selectors == [".pilot-tour-spot"]:
                assert prop in SPOT_OK, prop
            else:
                assert prop in MOTION_OK, (rule.selectors, prop)
    assert seen
    assert not [r for r in glass_rules() if r.value("transition-property")]


def test_the_backdrop_drifts_only_at_the_full_level():
    rules = glass_rules()
    animated = [r for r in rules if r.value("animation") is not None]
    assert animated
    for rule in animated:
        assert rule.selectors == [":root.glass-full body::before"], rule.selectors
    assert any(r.selectors == [":root.glass-paused body::before"]
               and r.value("animation-play-state") == "paused" for r in rules)


def test_the_pointer_light_is_drawn_only_at_the_full_level():
    for rule in glass_rules():
        for name, value in rule.decls:
            if "var(--glass-sheen)" in value:
                assert all(s.startswith(":root.glass-full") for s in rule.selectors), rule.selectors
    assert "glass-full" in read(GLASS_JS)


def test_reduced_motion_still_stops_every_animation():
    style = read(RENDERER / "style.css")
    rule = re.search(r"@media \(prefers-reduced-motion: reduce\)\s*\{(.*?)\n\}", style, flags=re.S)
    assert rule and "animation: none !important" in rule[1] and "transition: none !important" in rule[1]
    assert "!important" not in read(GLASS_CSS)


def test_no_animation_runs_longer_than_its_limit():
    rules = glass_rules()
    checked = 0
    for rule in rules:
        for name, value in rule.decls:
            if name == "--glass-drift":
                continue
            if name.startswith("--glass-t-") or (not name.startswith("--") and name.startswith(("transition", "animation"))):
                for literal in re.findall(r"(?<![\w.-])(\d+(?:\.\d+)?m?s)\b", value):
                    checked += 1
                    assert ms(literal) <= 200, (name, value)
    assert checked
    assert ms(token("--glass-drift", rules)) > 200


def test_the_pointer_light_sets_only_its_two_numbers():
    js = read(GLASS_JS)
    calls = re.findall(r"\.setProperty\(", js)
    named = re.findall(r'\.style\.setProperty\(\s*"(--glass-[xy])"', js)
    assert calls and len(calls) == len(named) == 2 and set(named) == {"--glass-x", "--glass-y"}
    assert "requestAnimationFrame" in js
    for event in ("pointerover", "pointermove", "scroll", "resize"):
        m = re.search(rf'addEventListener\("{event}",.*?\}}, \{{ passive: true \}}\);', js, flags=re.S)
        assert m, event
    assert js.count("getBoundingClientRect") == 1
    assert re.search(r"if \(!rect\) rect = \w+\.getBoundingClientRect\(\)", js)
    assert "if (now === scrolled) return;" in js
    assert "setInterval" not in js and "setTimeout" not in js


# ── Corners ──────────────────────────────────────────────────────────────

def test_nested_corners_are_concentric():
    rules = glass_rules()

    def t(name):
        return px(token(name, rules))

    low = t("--r-min")
    assert t("--r-card-inner") == max(low, t("--r-card") - t("--pad-card"))
    assert t("--r-dialog-inner") == max(low, t("--r-dialog") - t("--pad-dialog"))
    assert t("--r-tour-inner") == max(low, t("--r-tour") - t("--pad-tour"))
    assert t("--r-toolbar-control") == max(low, t("--r-toolbar") - t("--pad-toolbar"))
    assert t("--r-toolbar-control") * 2 == t("--h-toolbar-control")


def test_every_rounded_glass_shape_has_continuous_corners():
    rules = [r for r in glass_rules() if not keyframes(r)]
    shaped = {s for r in rules if r.value("corner-shape") == "var(--glass-corner)" for s in r.selectors}
    for rule in rules:
        radius = rule.value("border-radius")
        if radius is None or radius == "0":
            continue
        for selector in rule.selectors:
            assert selector in shaped, (selector, radius)


# ── The wording, the script and the neighbours ───────────────────────────

def test_the_glass_wording_lives_in_the_pilot_content():
    pilot = importlib.import_module("tests.test_pilot")
    glass = pilot.content()["glass"]
    keys = [level["key"] for level in glass["levels"]]
    assert keys == ["standard", "full", "solid"]
    assert glass["default"] in keys and glass["label"].strip() and glass["system_note"].strip()
    js = read(GLASS_JS)
    for text in (glass["label"], glass["system_note"], *(level["name"] for level in glass["levels"])):
        assert f'"{text}"' not in js and text not in js, text


def test_the_glass_level_is_kept_in_storage_safely():
    js = read(GLASS_JS)
    assert '"pilot.glass.level"' in js
    uses = [m.start() for m in re.finditer("localStorage", js)]
    assert uses
    for i in uses:
        start = js.rfind("try {", 0, i)
        assert start != -1 and js.find("} catch", start, i) == -1 and js.find("} catch", i) != -1, i


def test_the_theme_touches_no_app_file():
    for name in ("app.js", "style.css"):
        assert "glass" not in read(RENDERER / name).lower(), name
    for name in ("main.js", "preload.js"):
        assert "glass" not in read(REPO / "app" / name).lower(), name


def test_the_theme_never_names_its_inspiration():
    banned = re.compile(r"\bapple\b|liquid\s+glass|\bios\b|\bmacos\b|swiftui", re.IGNORECASE)
    for path in (GLASS_CSS, GLASS_JS, RENDERER / "pilot-content.js", REPO / "pilot" / "Tester Guide.md"):
        assert not banned.search(read(path)), path.name
