"""The app shell's renderer half (pilot SPEC-shell.md, decisions P58-P77).

What can be pinned without a browser: the tokens and their contrast in both
themes, the shell stylesheet's discipline (tokens only, the 4px grid), the
guards every renderer file keeps, the words the new files may not type, and -
run in node against the files' own functions, as the repository's other
renderer tests do - the route, the search, the sort icon and the menu's
enable list. The rendered claims (a screenshot of every scenario, light and
dark, at both sizes) come from ``pilot/harness/shoot.mjs`` and are reported in
``pilot/handoffs/shell-S3.md``.

This file is S3's part of SPEC section 14.1. S2 adds the menu half (the
template, the ``menu`` channel, the first paint), S4 the pages' node tests and
S5 the sheet's; the lists below that name the files a claim covers
(``SHELL_FILES``, ``TITLE_FREE``) are the ones they extend.
"""

from __future__ import annotations

import hashlib
import json
import re
import shutil
import subprocess
from pathlib import Path

import pytest

from tests.test_pilot_ui import (
    GRID_PROPS,
    GRID_TOKEN,
    RENDERER,
    blocks,
    colour_faults,
    declarations,
    read,
    stripped,
    top_level,
)

REPO = Path(__file__).resolve().parent.parent

#: The new renderer scripts. S4 adds pages.js and S5 sheet.js.
SHELL_FILES = ("shell.js", "tooltip.js")
#: Files that hold no ``title`` attribute (SPEC 13). S4 adds app.js and
#: index.html when it deletes the last ones.
TITLE_FREE = ("shell.js", "tooltip.js", "shell.css", "pilot.js", "tour.js")
#: Floating UI, vendored (decision P86), in the order index.html loads it: the
#: DOM build asks for the core build's global, so core comes first.
FLOATING_UI = RENDERER / "vendor" / "floating-ui"
FLOATING_UI_SCRIPTS = ("vendor/floating-ui/floating-ui.core.umd.min.js", "vendor/floating-ui/floating-ui.dom.umd.min.js")
#: SHA-256 of each vendored file, the bytes of the published packages
#: @floating-ui/dom 1.8.0, @floating-ui/core 1.8.0 and @floating-ui/utils
#: 0.2.12 (the tarballs' integrity is in the folder's README).
FLOATING_UI_SHA256 = {
    "floating-ui.core.umd.min.js": "65940d866a6b6d831394a4bbed99ed0a39330bac98b643386d9a2f87a1a1d5da",
    "floating-ui.dom.umd.min.js": "61a46f943c4e99379eaf073447811aec7e8b8f120d2f646316e01b7694bc90a3",
    "LICENSE-dom": "0e4c9a9b6c71019cbbea3bdc20b01223110a9035700f9c960c8fcbf78c2325ce",
    "LICENSE-core": "0e4c9a9b6c71019cbbea3bdc20b01223110a9035700f9c960c8fcbf78c2325ce",
    "LICENSE-utils": "0e4c9a9b6c71019cbbea3bdc20b01223110a9035700f9c960c8fcbf78c2325ce",
}



# ── tokens ────────────────────────────────────────────────────────────────

TOKENS = {
    # name: (light, dark): SPEC-shell 10.1, word for word.
    "--bg-page": ("#ffffff", "#1b1e24"),
    "--bg-nav": ("#f3f5f8", "#15171c"),
    "--bg-raised": ("#ffffff", "#23272f"),
    "--bg-hover": ("#f1f5f9", "#252a32"),
    "--bg-nav-hover": ("#e7ecf2", "#1f232a"),
    "--bg-pressed": ("#e2e8f0", "#2d333c"),
    "--bg-selected": ("#e3eaf4", "#26303f"),
    "--text": ("#0f172a", "#e8ecf2"),
    "--text-secondary": ("#434f63", "#b9c3cf"),
    "--text-caption": ("#566579", "#9aa6b4"),
    "--text-disabled": ("#94a3b8", "#5f6b7a"),
    "--accent": ("#14335c", "#a8c4ee"),
    "--accent-hover": ("#0e2544", "#c3d6f4"),
    "--on-accent": ("#ffffff", "#0e1a2e"),
    "--link": ("#14335c", "#a8c4ee"),
    "--focus": ("#2563eb", "#7fb0ff"),
    "--border": ("#e2e8f0", "#2e343d"),
    "--border-strong": ("#cbd5e1", "#434b57"),
    "--border-input": ("#7d8ea5", "#7a8697"),
    "--st-attention": ("#8a3a0c", "#f2b872"),
    "--st-waiting": ("#1e3a8a", "#a3bff0"),
    "--st-done": ("#05603f", "#7dd8b0"),
    "--st-error": ("#991b1b", "#ffa29b"),
    "--danger": ("#b42318", "#ff9189"),
    "--err-bg": ("#fef2f2", "#3a1d20"),
    "--err-border": ("#fecaca", "#6e2f33"),
    "--err-fg": ("#991b1b", "#ffb8b3"),
    "--warn-bg": ("#fffbeb", "#35290f"),
    "--warn-border": ("#fde68a", "#6b5420"),
    "--warn-fg": ("#7c3a0a", "#f6d08a"),
    "--info-bg": ("#eff6ff", "#1a2940"),
    "--info-border": ("#bfdbfe", "#34507a"),
    "--info-fg": ("#1e3a8a", "#bcd3f7"),
    "--badge-bg": ("#fcd34d", "#fcd34d"),
    "--badge-fg": ("#0e2544", "#0e2544"),
    "--brand": ("#14335c", "#14335c"),
    "--window-light": ("#ffffff", "#ffffff"),
    "--window-dark": ("#1b1e24", "#1b1e24"),
    "--scrim": ("rgba(15, 23, 42, 0.32)", "rgba(0, 0, 0, 0.56)"),
    "--scroll-thumb": ("#8593a6", "#737f8e"),
    "--shadow-overlay": ("0 8px 32px rgba(15, 23, 42, 0.24), 0 2px 8px rgba(15, 23, 42, 0.12)", "0 8px 32px rgba(0, 0, 0, 0.48), 0 2px 8px rgba(0, 0, 0, 0.32)"),
}

#: The three kept "ok" colours the SPEC gives in prose (10.1), in both themes.
OK_LIGHT = {"--ok-bg": "#ecfdf5", "--ok-border": "#a7f3d0", "--ok-fg": "#065f46"}
OK_DARK = {"--ok-bg": "#10291f", "--ok-border": "#1f5a43", "--ok-fg": "#9be3c3"}

CONTRAST = [
    # foreground, background, needs, light, dark: the computed table of SPEC-shell 10.2.
    ("--text", "--bg-page", 7, 17.85, 14.08),
    ("--text", "--bg-nav", 7, 16.35, 15.12),
    ("--text", "--bg-hover", 7, 16.3, 12.17),
    ("--text", "--bg-nav-hover", 7, 15.03, 13.3),
    ("--text", "--bg-selected", 7, 14.74, 11.23),
    ("--text", "--bg-raised", 7, 17.85, 12.63),
    ("--text", "--bg-pressed", 7, 14.48, 10.73),
    ("--text-secondary", "--bg-page", 7, 8.28, 9.36),
    ("--text-secondary", "--bg-hover", 7, 7.56, 8.08),
    ("--text-secondary", "--bg-raised", 7, 8.28, 8.39),
    ("--text-caption", "--bg-page", 4.5, 5.94, 6.75),
    ("--text-caption", "--bg-nav", 4.5, 5.44, 7.25),
    ("--text-caption", "--bg-hover", 4.5, 5.43, 5.83),
    ("--text-caption", "--bg-selected", 4.5, 4.91, 5.38),
    ("--text-caption", "--bg-raised", 4.5, 5.94, 6.05),
    ("--link", "--bg-page", 7, 12.67, 9.38),
    ("--link", "--bg-hover", 7, 11.56, 8.1),
    ("--on-accent", "--accent", 7, 12.67, 9.78),
    ("--on-accent", "--accent-hover", 7, 15.36, 11.81),
    ("--st-attention", "--bg-page", 7, 7.8, 9.44),
    ("--st-attention", "--bg-hover", 4.5, 7.12, 8.16),
    ("--st-waiting", "--bg-page", 7, 10.36, 8.96),
    ("--st-waiting", "--bg-hover", 4.5, 9.45, 7.74),
    ("--st-done", "--bg-page", 7, 7.63, 9.8),
    ("--st-done", "--bg-hover", 4.5, 6.97, 8.46),
    ("--st-error", "--bg-page", 7, 8.31, 8.66),
    ("--st-error", "--bg-nav", 4.5, 7.61, 9.3),
    ("--danger", "--bg-raised", 4.5, 6.57, 6.89),
    ("--danger", "--bg-hover", 4.5, 6.0, 6.64),
    ("--err-fg", "--err-bg", 7, 7.6, 9.27),
    ("--warn-fg", "--warn-bg", 7, 8.21, 9.7),
    ("--info-fg", "--info-bg", 7, 9.52, 9.62),
    ("--badge-fg", "--badge-bg", 7, 10.66, 10.66),
    ("--focus", "--bg-page", 3, 5.17, 7.6),
    ("--focus", "--bg-nav", 3, 4.73, 8.16),
    ("--focus", "--bg-raised", 3, 5.17, 6.81),
    ("--border-input", "--bg-page", 3, 3.34, 4.52),
    ("--border-input", "--bg-raised", 3, 3.34, 4.05),
    ("--accent", "--bg-page", 3, 12.67, 9.38),
    ("--accent", "--bg-selected", 3, 10.46, 7.48),
    ("--scroll-thumb", "--bg-page", 3, 3.12, 4.10),
    ("--ok-fg", "--ok-bg", 7, 7.29, 10.43),
]


def root_blocks() -> tuple[dict[str, str], dict[str, str]]:
    """(light, dark): the declarations of pilot-ui.css's two :root blocks."""
    light = dark = None
    for media, selector, body in blocks(read("pilot-ui.css")):
        if selector.strip() != ":root":
            continue
        if any("prefers-color-scheme: dark" in one for one in media):
            assert dark is None, "one dark block"
            dark = dict(declarations(body))
        else:
            assert light is None, "one light block"
            light = dict(declarations(body))
    assert light is not None and dark is not None
    return light, dark


def resolve(name: str, theme: str) -> str:
    light, dark = root_blocks()
    value = (dark if theme == "dark" and name in dark else light)[name]
    while (match := re.fullmatch(r"var\((--[\w-]+)\)", value.strip())):
        value = (dark if theme == "dark" and match.group(1) in dark else light)[match.group(1)]
    return " ".join(value.split())


def luminance(hex_colour: str) -> float:
    channels = [int(hex_colour[i:i + 2], 16) / 255 for i in (1, 3, 5)]
    lin = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4 for c in channels]
    return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]


def ratio(fg: str, bg: str, theme: str) -> float:
    a, b = luminance(resolve(fg, theme)), luminance(resolve(bg, theme))
    return (max(a, b) + 0.05) / (min(a, b) + 0.05)


def test_every_colour_pair_meets_its_contrast_in_both_themes():
    """SPEC 10.2: text the brief asks to be AAA is held to 7:1, captions and
    states to 4.5:1, marks that are not text to 3:1. The table's own numbers
    are pinned too, so a token that drifts from the SPEC shows here."""
    assert len(CONTRAST) == 42
    for fg, bg, needs, light, dark in CONTRAST:
        for theme, said in (("light", light), ("dark", dark)):
            got = ratio(fg, bg, theme)
            assert got >= needs, f"{fg} on {bg} in {theme}: {got:.2f} < {needs}"
            assert abs(got - said) <= 0.02, f"{fg} on {bg} in {theme}: {got:.2f}, the SPEC says {said}"


def test_every_token_has_the_value_the_spec_lists_in_both_themes():
    for name, (light, dark) in TOKENS.items():
        assert resolve(name, "light") == " ".join(light.split()), name
        assert resolve(name, "dark") == " ".join(dark.split()), name
    for name, value in OK_LIGHT.items():
        assert resolve(name, "light") == value, name
    for name, value in OK_DARK.items():
        assert resolve(name, "dark") == value, name


def test_every_light_token_has_a_dark_value_and_no_other():
    light, dark = root_blocks()
    colours = set(TOKENS) | set(OK_LIGHT)
    assert colours <= set(light) and colours <= set(dark), sorted(colours - set(dark))
    assert set(dark) <= set(light), sorted(set(dark) - set(light))


def test_the_kept_names_are_aliases_of_the_purpose_names():
    """SPEC 10.1: every rule already written picks up the right value in both
    themes because the old names resolve through the new ones."""
    light, dark = root_blocks()
    aliases = {"--bg": "--bg-page", "--card": "--bg-raised", "--muted": "--text-secondary", "--subtle": "--text-caption",
               "--navy": "--accent", "--navy-deep": "--accent-hover", "--blue": "--focus", "--blue-dark": "--focus",
               "--surface-hover": "--bg-hover", "--surface-pressed": "--bg-pressed", "--surface-selected": "--bg-selected",
               "--surface-sunken": "--bg-nav", "--surface-disabled": "--bg-nav"}
    for old, new in aliases.items():
        assert light[old] == f"var({new})", old
        assert old not in dark, f"{old} resolves through {new}; the dark block does not repeat it"


def test_the_window_colours_are_the_pages():
    """SPEC 5.6: main.js reads --window-light and --window-dark; the page
    background is one of them in each theme. (S2 pins main.js's half.)"""
    light, dark = root_blocks()
    assert light["--window-light"] == "#ffffff" and light["--window-dark"] == "#1b1e24"
    assert light["--bg-page"] == "var(--window-light)" and dark["--bg-page"] == "var(--window-dark)"


# ── the grid ──────────────────────────────────────────────────────────────

def test_every_space_is_a_step_of_the_grid():
    seen = 0
    for name in ("shell.css", "pilot-ui.css"):
        for _media, selector, body in blocks(read(name)):
            if selector.strip() == ":root":
                continue
            for prop, value in declarations(body):
                if prop not in GRID_PROPS:
                    continue
                seen += 1
                flat = re.sub(r"calc\(([^()]|\([^()]*\))*\)", "0", value)
                for token in flat.split():
                    assert GRID_TOKEN.match(token), f"{name}: {selector.strip()}: {prop}: {value}"
                for inner in re.findall(r"calc\((.*)\)", value):
                    assert not re.search(r"\d+(?:\.\d+)?px", inner), f"{name}: {selector.strip()}: {prop}: {value}"
    assert seen > 50


def test_every_size_is_a_multiple_of_four():
    light, _dark = root_blocks()
    sizes = {name: value for name, value in light.items() if name.startswith("--size-")}
    assert sizes
    for name, value in sizes.items():
        pixels = int(re.fullmatch(r"(\d+)px", value.strip()).group(1))
        if name == "--size-pill":
            assert pixels == 3, "the selection pill: Fluent's one 3px value"
        elif name == "--size-hair":
            assert pixels == 1, "the hairline"
        else:
            assert pixels % 4 == 0, f"{name}: {value}"
    assert sizes["--size-row"] == "40px" and sizes["--size-side"] == "240px" and sizes["--size-sheet"] == "400px"
    assert sizes["--size-bar"] == "48px" and sizes["--size-sheet-foot"] == "64px" and sizes["--size-find"] == "240px"


def test_every_line_height_lands_on_the_grid():
    """SPEC 3.7: size times line height is a multiple of 4 in each of the five roles."""
    light, _dark = root_blocks()
    roles = re.findall(r"--fs-(\w+)", "\n".join(light))
    assert sorted(roles) == ["body", "caption", "figure", "h1", "h2"]
    for role in roles:
        size = int(light[f"--fs-{role}"].removesuffix("px"))
        top, bottom = re.fullmatch(r"calc\((\d+) / (\d+)\)", light[f"--lh-{role}"]).groups()
        assert int(bottom) == size, role
        assert int(top) % 4 == 0, f"{role}: {top}"


# ── the shell stylesheet keeps the structure pass's rules ─────────────────

def test_the_shells_stylesheet_follows_the_structure_passes_rules():
    css = stripped(read("shell.css"))
    for banned in ("url(", "@import", "@font-face", "blur(", "backdrop-filter", "glass"):
        assert banned not in css.lower(), banned
    seen = 0
    for media, selector, body in blocks(read("shell.css")):
        if "!important" in body:
            assert any("prefers-reduced-motion" in one for one in media), selector.strip()
        for prop, value in declarations(body):
            assert prop != "font", f"{selector.strip()}: the font shorthand hides a size and a weight"
            faults = list(colour_faults(prop, value))
            assert not faults, f"literal colour {faults} in {selector.strip()}: {prop}: {value}"
            for wanted, prefix in (("font-size", "var(--fs-"), ("line-height", "var(--lh-"), ("font-weight", "var(--fw-")):
                if prop == wanted:
                    seen += 1
                    assert value.startswith(prefix), f"{selector.strip()}: {prop}: {value}"
        if [v for p, v in declarations(body) if p == "display" and v != "none"]:
            for one in (part.strip() for part in selector.split(",")):
                assert re.search(r":not\((?:\.hidden|\[hidden\]|:empty)\)", one), f"display without :not(.hidden): {one}"
    assert seen > 10


def test_the_shells_stylesheet_ends_with_its_own_forced_colors_block():
    rules = list(top_level(stripped(read("shell.css"))))
    prelude, inner, end = rules[-1]
    assert prelude == "@media (forced-colors: active)"
    assert sum("forced-colors" in one for one, _b, _e in rules) == 1
    assert not stripped(read("shell.css"))[end:].strip()
    used = {word.lower() for word in re.findall(r"\b[A-Za-z]+\b", inner)}
    assert {"canvas", "canvastext", "highlight", "highlighttext", "graytext"} <= used
    for _media, selector, body in blocks(prelude + " {" + inner + "}"):
        for prop, value in declarations(body):
            for word in colour_faults(prop, value):
                raise AssertionError(f"system colours only: {selector.strip()}: {prop}: {word}")


def test_the_loading_order_is_the_specs_and_the_csp_is_unchanged():
    html = read("index.html")
    styles = [html.index(f'href="{name}"') for name in ("style.css", "pilot-ui.css", "shell.css", "pilot-style.css")]
    assert styles == sorted(styles)
    scripts = [html.index(f'src="{name}"') for name in ("app.js", *FLOATING_UI_SCRIPTS, "tooltip.js", "shell.js", "pilot-content.js", "pilot.js", "tour.js")]
    assert scripts == sorted(scripts)
    # Every script is a file of the app itself: no scheme, no host, no CDN.
    sources = re.findall(r"<script[^>]*\bsrc=\"([^\"]+)\"", html)
    assert len(sources) == len(scripts)
    for source in sources:
        assert not re.match(r"^([a-z][a-z0-9+.-]*:|//|/)", source, re.I), source
        assert (RENDERER / source).is_file(), source
    assert ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'") in html
    assert "<style" not in html and not re.search(r"<script(?![^>]*\bsrc=)", html)


def test_the_vendored_floating_ui_is_the_pinned_bytes_and_nothing_else():
    """Decision P86: placement is Floating UI's, copied unedited. The hashes
    are the published packages' files; an edit, an upgrade or an extra file
    fails here until the README and this table are changed on purpose."""
    found = {path.name for path in FLOATING_UI.iterdir()}
    assert found == {*FLOATING_UI_SHA256, "README.md"}, found
    for name, digest in FLOATING_UI_SHA256.items():
        assert hashlib.sha256((FLOATING_UI / name).read_bytes()).hexdigest() == digest, name
    readme = (FLOATING_UI / "README.md").read_text(encoding="utf-8")
    for digest in FLOATING_UI_SHA256.values():
        assert digest in readme
    for pinned in ("@floating-ui/dom` | 1.8.0", "@floating-ui/core` | 1.8.0", "@floating-ui/utils` | 0.2.12"):
        assert pinned in readme, pinned


def test_the_tooltip_reaches_floating_ui_only_through_its_one_global():
    """Placement is the library's, the rest is ours: one global, no import, no
    hand-rolled edge arithmetic left, and no colour or size typed in the script."""
    js = stripped_js("tooltip.js")
    assert set(re.findall(r"\bFloating[A-Za-z]*", js)) == {"FloatingUIDOM"}
    assert {"computePosition", "offset", "flip", "shift"} <= set(re.findall(r"FloatingUIDOM\.(\w+)", js))
    assert not re.search(r"\b(import|require)\b|getBoundingClientRect|innerWidth|innerHeight", js)
    assert not re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(|\d\s*(px|rem|em)\b", js)
    assert "style.setProperty(" in js and ".style." not in js.replace("style.setProperty(", "")


def test_the_search_box_alone_shows_no_tooltip_on_keyboard_focus():
    """Jason's ruling 2 (SPEC 8.5): every other control shows its tip when the
    keyboard reaches it; the search box does not (hover still does)."""
    js = stripped_js("tooltip.js")
    focus = js[js.index('addEventListener("focusin"'):]
    focus = focus[:focus.index("});")]
    assert ':focus-visible' in focus and 'matches("#find")' in focus
    assert 'matches("input")' not in focus and "textarea" not in focus
    assert '<input id="find"' in read("index.html")


def test_the_skeleton_is_the_specs_and_the_old_screen_is_kept_hidden_not_drawn():
    """SPEC 3.1. Until S4 and S5 take over what each old card showed, its
    markup stays in #legacy, which is never drawn, so app.js still finds its
    elements by id."""
    html = read("index.html")
    for wanted in ('id="shell"', 'id="side"', 'id="side-brand"', 'id="side-sections"', 'id="side-foot"', 'id="last-sort"',
                   'id="main"', 'id="bar"', 'id="crumbs"', 'id="find-wrap"', 'id="find"', 'id="find-list"', 'id="sort"',
                   'id="notices"', 'id="page"', 'id="sheet"', 'id="sheet-scrim"', 'id="tip"', 'id="toast"'):
        assert wanted in html, wanted
    assert html.count('data-section="') == 4
    assert re.search(r'<div id="legacy" class="hidden">', html)
    outside = html[:html.index('<div id="legacy"')]
    for gone in ("topbar", "brand-logo", 'id="eng-select"', "btn-scan", "btn-inbox", "toolbar"):
        assert gone not in outside, gone
    for symbol in ("search", "sort", "stop", "dismiss", "chev", "next", "done", "more", "open"):
        assert f'<symbol id="i-{symbol}"' in html, symbol
    assert 'role="alert" aria-live="polite"' in html[html.index('id="notices"'):html.index('id="notices"') + 120]


def test_every_icon_has_a_name_and_a_tooltip():
    """SPEC 8.5, 14.1: each icon-only button carries data-tip-key, naming a
    vocabulary key; shell.js sets both its accessible name and its tooltip from it."""
    html = read("index.html")
    shell = stripped_js("shell.js")
    keys = re.findall(r'<button[^>]*\bid="(sort|sheet-close)"[^>]*data-tip-key="([\w.]+)"', html)
    assert {name for name, _key in keys} == {"sort", "sheet-close"}
    assert re.search(r'<input[^>]*\bid="find"[^>]*data-tip-key="screen\.find"', html)
    for _name, key in keys:
        assert key.startswith("screen.")
    named = shell[shell.index("function shellNameIcons() {"):]
    named = named[:named.index("\n}\n")]
    assert 'setAttribute("aria-label", words)' in named and "setTip(node, words)" in named


# ── the guards every renderer file keeps ──────────────────────────────────

def stripped_js(name: str) -> str:
    """The file without its comments (no string in these files holds //)."""
    text = read(name)
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$|(?<=[;{}),])\s*//.*$", "", text)


def test_the_renderer_has_no_title_attribute():
    for name in TITLE_FREE:
        text = stripped_js(name) if name.endswith(".js") else read(name)
        assert not re.search(r"\btitle=|\.title\s*=|(?<![\w-])title\s*:\s*[\"'`\w]", text), name


def test_the_new_renderer_files_keep_the_renderers_guards():
    banned = ("innerHTML", "insertAdjacentHTML", "outerHTML", "document.write", "eval(", "new Function", "XMLHttpRequest",
              "WebSocket", "window.open", "openExternal", "startsWith(")
    for name in SHELL_FILES:
        text = stripped_js(name)
        assert not [one for one in banned if one in text], name
        assert not re.search(r"\bfetch\(", text), name
        assert not re.search(r"""\bstyle\s*=|\.style\.cssText|setAttribute\(\s*["']style["']""", text), name
        assert not re.search(r"""\.on[a-z]+\s*=|["'\s]on[a-z]+=["']""", text), name
        # The SVG namespace is an identifier, not an address; nothing else may look like one.
        assert "http:" not in text.replace("http://www.w3.org/2000/svg", "") and "https:" not in text, name


def test_the_new_renderer_files_type_no_words_of_their_own():
    """P63: every word on screen is the API's. A string literal of two or
    more plain words in these files would be one the page typed."""
    # A plain word: letters only. A hyphenated token is a class name or an id, not a word.
    word = re.compile(r"^[A-Za-z][A-Za-z'\u2019]*[.,;:!?\u2026]*$")
    literals = re.compile(r'"(?:[^"\\\n]|\\.)*"|\'(?:[^\'\\\n]|\\.)*\'|`(?:[^`\\]|\\.)*`')
    for name in SHELL_FILES:
        text = re.sub(r"/[^/\n*][^/\n]*/[gimsuy]*(?=[.,;)])", "", stripped_js(name))   # regex literals
        for literal in literals.findall(text):
            inner = re.sub(r"\$\{[^}]*\}", " ", literal[1:-1])
            plain = [t for t in inner.split() if word.match(t)]
            assert len(plain) < 2 or inner == "use strict", f"{name}: {literal}"


def test_every_attribute_the_shell_builds_a_node_with_is_on_its_list():
    """h() throws on an attribute it does not name (the pattern of app.js's
    el(), decision 137). A key used at a call site but missing from the list
    would throw when that node is first drawn - the harness found one."""
    text = stripped_js("shell.js")
    listed = set(re.findall(r'"([\w-]+)"', text[text.index("const H_ATTRIBUTES = new Set(["):text.index("]);")]))
    used = set(re.findall(r'"(aria-[\w-]+)":', text)) | set(re.findall(r"\b(role|tabindex|type|disabled|hidden|value|dataset|className)\s*:", text))
    used |= set(re.findall(r'\{ id: "|, id: "|\bid: ', text)) and {"id"}
    assert used <= listed, sorted(used - listed)


def test_one_keydown_listener_owns_the_keyboard():
    """SPEC 4.3: app.js keeps the document's one keydown listener and hands
    the shell's keys to shellKey(e) first; the new files add none."""
    for name in SHELL_FILES:
        assert 'addEventListener("keydown"' not in read(name), name
    app = read("app.js")
    listener = app[app.index('document.addEventListener("keydown", (e) => {'):]
    assert listener.index("if (shellKey(e)) return;") < listener.index("dialogStack[dialogStack.length - 1]")
    assert app.count('document.addEventListener("keydown"') == 1


def test_the_harness_is_never_loaded_by_the_app():
    for path in (RENDERER / "index.html", REPO / "app" / "main.js", REPO / "app" / "preload.js", REPO / "app" / "package.json"):
        assert "harness" not in path.read_text(encoding="utf-8"), path.name
    for path in RENDERER.iterdir():
        if path.suffix in (".js", ".css", ".html"):
            assert "harness" not in path.read_text(encoding="utf-8"), path.name


# ── the style.css literals that still draw ────────────────────────────────

#: Rules of style.css that write a literal colour and whose elements the
#: shell removes; each needs no dark value because nothing draws it. S4 and
#: S5 delete more of the old screen and shorten this list.
RETIRED = (".topbar", ".brand", ".chip", ".view-", ".eng-picker", ".mode-toggle", ".deck-card", ".review", ".requests",
           ".setup-row", ":root")


def family(prop: str) -> str:
    return prop.split("-")[0]


def test_every_literal_colour_still_in_use_has_a_dark_value():
    """SPEC 10.4: a rule of style.css with a literal colour whose selector
    still matches markup is restated in pilot-ui.css through a token, selector
    for selector, so the dark values reach it."""
    restated: dict[str, set[str]] = {}
    for _media, selector, body in blocks(read("pilot-ui.css")):
        if selector.strip() == ":root":
            continue
        for part in selector.split(","):
            restated.setdefault(" ".join(part.split()), set()).update(family(p) for p, _v in declarations(body))
    checked = 0
    for _media, selector, body in blocks(read("style.css")):
        literal = {family(p) for p, v in declarations(body) if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(", v)}
        if not literal:
            continue
        for part in selector.split(","):
            part = " ".join(part.split())
            if part.startswith(RETIRED):
                continue
            checked += 1
            assert literal <= restated.get(part, set()), f"{part}: style.css writes a literal {sorted(literal)}; pilot-ui.css does not restate it"
    assert checked > 20


# ── node: the shell's own functions ───────────────────────────────────────

NODE = shutil.which("node")


def js_function(name: str) -> str:
    text = read("shell.js")
    start = text.index(f"function {name}(")
    return text[start:text.index("\n}\n", start) + 3]


def run_shell(functions: list[str], setup: str, probe: str, tmp_path: Path):
    """Lift the named functions out of shell.js as they are, put fakes for
    what app.js provides around them, and return what the probe prints."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    lifted = "\n".join(js_function(name) for name in functions)
    script = tmp_path / "probe.js"
    script.write_text(f"{setup}\n{lifted}\nprocess.stdout.write(JSON.stringify((() => {{ {probe} }})()));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


PEOPLE = r"""
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
const vocab = { screen: { counts: { one_return: "1 return", returns: "{n} returns" },
  sections: { overview: "Overview", needs_review: "Needs review", reminders: "Reminders", clients: "Clients" },
  sort: { now: "Sort now", stop: "Stop sorting", firm: "Open a client to sort", locked: "In use elsewhere", stopping: "Stopping" } } };
const households = [
  { name: "Smith Family", path: "h1", returns: [{ rollable: true }] }, { name: "Rivera Design", path: "h2", returns: [] },
  { name: "Ren\u00e9e Okafor", path: "h3", returns: [] }, { name: "Lopez Household", path: "h4", returns: [] },
];
const engagements = [
  { name: "a", path: "r1", household: "h1", year: 2025, return_name: "1040 - John & Jane Smith" },
  { name: "b", path: "r2", household: "h1", year: 2024, return_name: "1040 - John & Jane Smith" },
  { name: "c", path: "r3", household: "h2", year: 2025, return_name: "1120-S - Rivera Design LLC" },
];
let calls = 0; const call = () => { calls += 1; };
"""


def test_search_finds_a_household_by_any_part_of_its_name_without_calling_the_api(tmp_path):
    probe = """
      const names = (q) => findOptions(q).map((o) => o.name);
      return { smith: names("smith"), inner: names("ily"), accent: names("renee"), upper: names("RIVERA"), none: names("zzz"),
               empty: names("  "), notes: findOptions("smith").map((o) => o.note), route: findOptions("rivera")[1].route, calls };
    """
    ran = run_shell(["screenWords", "fold", "shellHousehold", "shellOwnReturns", "findOptions"], PEOPLE, probe, tmp_path)
    assert ran["smith"] == ["Smith Family", "1040 - John & Jane Smith", "1040 - John & Jane Smith"]
    assert ran["inner"] == ["Smith Family"] and ran["accent"] == ["Ren\u00e9e Okafor"]
    assert ran["upper"] == ["Rivera Design", "1120-S - Rivera Design LLC"]
    assert ran["none"] == [] and ran["empty"] == []
    assert ran["notes"] == ["2 returns", "Smith Family 2025", "Smith Family 2024"], "households first; a return says its household and year"
    assert ran["route"] == {"level": "return", "household": "h2", "year": 2025, "ret": "r3"}
    assert ran["calls"] == 0, "the search never calls the API"


def test_the_search_list_shows_at_most_eight_options(tmp_path):
    setup = PEOPLE + "for (let i = 0; i < 30; i++) households.push({ name: `Client ${i}`, path: `x${i}`, returns: [] });"
    probe = 'return findOptions("client").length;'
    assert run_shell(["screenWords", "fold", "shellHousehold", "shellOwnReturns", "findOptions"], setup, probe, tmp_path) == 8


def test_the_path_names_every_level_and_the_year_always_shows(tmp_path):
    setup = PEOPLE + """
      let shellRoute = null;
      const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
      const SCREEN_KEYS = { "needs-review": "needs_review" };
    """
    probe = """
      const path = (route) => { shellRoute = route; return crumbList().map((s) => [s.name, Boolean(s.go)]); };
      return {
        overview: path({ level: "overview" }), review: path({ level: "needs-review" }), setup: path({ level: "setup" }),
        clients: path({ level: "clients" }),
        household: path({ level: "household", household: "h1" }),
        year: path({ level: "year", household: "h1", year: 2025 }),
        ret: path({ level: "return", household: "h1", year: 2025, ret: "r1" }),
      };
    """
    ran = run_shell(["screenWords", "shellHousehold", "shellReturn", "crumbList"], setup, probe, tmp_path)
    assert ran["overview"] == [["Overview", False]] and ran["review"] == [["Needs review", False]] and ran["setup"] == []
    assert ran["clients"] == [["Clients", False]]
    assert ran["household"] == [["Clients", True], ["Smith Family", False]]
    assert ran["year"] == [["Clients", True], ["Smith Family", True], ["2025", False]]
    assert ran["ret"] == [["Clients", True], ["Smith Family", True], ["2025", True], ["1040 - John & Jane Smith", False]], \
        "the year always shows (P61); the last segment is the current level, not a button"


def test_the_sort_icon_is_stop_while_a_sort_runs_and_grey_on_a_firm_page(tmp_path):
    setup = PEOPLE + """
      let shellRoute = null; let scanning = null; let locked = false;
    """
    probe = """
      const at = (route, run, lock) => { shellRoute = route; scanning = run; locked = lock; const s = sortState(); return [s.key, s.icon, s.off, s.words]; };
      return {
        ready: at({ level: "household", household: "h1" }, null, false),
        year: at({ level: "year", household: "h1", year: 2025 }, null, false),
        ret: at({ level: "return", household: "h1", ret: "r1" }, null, false),
        firm: at({ level: "overview" }, null, false),
        setup: at({ level: "setup" }, null, false),
        locked: at({ level: "return", household: "h1", ret: "r1" }, null, true),
        sorting: at({ level: "household", household: "h1" }, { stopping: false }, false),
        stopping: at({ level: "household", household: "h1" }, { stopping: true }, false),
        sortingOnAFirmPage: at({ level: "clients" }, { stopping: false }, false),
      };
    """
    ran = run_shell(["screenWords", "shellHasClient", "sortState"], setup, probe, tmp_path)
    assert ran["ready"] == ["now", "sort", False, "Sort now"]
    assert ran["year"][0] == ran["ret"][0] == "now"
    assert ran["firm"] == ["firm", "sort", True, "Open a client to sort"], "P80: grey on a firm page"
    assert ran["setup"][0] == "firm" and ran["setup"][2] is True
    assert ran["locked"] == ["locked", "sort", True, "In use elsewhere"]
    assert ran["sorting"] == ["stop", "stop", False, "Stop sorting"], "the one Stop is this icon (P70)"
    assert ran["stopping"] == ["stopping", "stop", True, "Stopping"]
    assert ran["sortingOnAFirmPage"][0] == "stop", "a sort that runs can always be stopped"


def test_the_menus_enable_list_follows_the_rules_of_the_template(tmp_path):
    setup = PEOPLE + """
      let shellRoute = null; let shellRootSet = true; let shellPaths = { status: "s" }; let scanning = null; let locked = false;
      let lastState = { household: { shared_on: "" } };
      const $ = () => ({ classList: { contains: () => true } });
    """
    probe = """
      const ids = (route, o = {}) => { shellRoute = route; shellRootSet = o.root ?? true; scanning = o.scan ?? null; locked = o.locked ?? false;
        lastState = { household: { shared_on: o.shared ? "d" : "" } }; return shellEnabled(); };
      const has = (list, ...want) => want.every((id) => list.includes(id));
      const firm = ids({ level: "overview" });
      const home = ids({ level: "household", household: "h1" });
      const ret = ids({ level: "return", household: "h1", ret: "r1" });
      return {
        firmHas: has(firm, "new_household", "overview", "clients", "find", "schedule", "firm_report", "refresh", "about", "tour"),
        firmNot: ["edit_household", "edit_list", "sort_now", "draft_reminder", "open_inbox"].filter((id) => firm.includes(id)),
        homeHas: has(home, "edit_household", "add_return", "roll_forward", "mark_shared", "open_client_folder", "open_inbox", "sort_now"),
        homeNot: ["edit_list", "draft_reminder", "open_working"].filter((id) => home.includes(id)),
        retHas: has(ret, "edit_list", "draft_reminder", "open_working", "edit_household"),
        shared: ids({ level: "household", household: "h1" }, { shared: true }).includes("mark_shared"),
        locked: ["edit_household", "add_return", "edit_list", "sort_now"].filter((id) => ids({ level: "return", household: "h1", ret: "r1" }, { locked: true }).includes(id)),
        lockedKeepsRead: has(ids({ level: "return", household: "h1", ret: "r1" }, { locked: true }), "draft_reminder", "open_inbox"),
        sorting: [ids({ level: "household", household: "h1" }, { scan: {} }).includes("sort_now"), ids({ level: "household", household: "h1" }, { scan: {} }).includes("stop_sorting")],
        noRoot: ids({ level: "setup" }, { root: false }).filter((id) => ["new_household", "open_root", "overview", "find", "schedule"].includes(id)),
        alwaysOn: has(ids({ level: "setup" }, { root: false }), "change_root", "refresh", "tour", "safeguards", "terms", "error_log", "about"),
      };
    """
    ran = run_shell(["shellHasClient", "shellHousehold", "shellEnabled"], setup, probe, tmp_path)
    assert ran["firmHas"] and ran["firmNot"] == []
    assert ran["homeHas"] and ran["homeNot"] == []
    assert ran["retHas"]
    assert ran["shared"] is False, "Mark as shared is offered until it is shared"
    assert ran["locked"] == [] and ran["lockedKeepsRead"], "a locked return greys the writing items and no others"
    assert ran["sorting"] == [False, True]
    assert ran["noRoot"] == [] and ran["alwaysOn"]


def test_changing_the_clients_folder_keeps_the_firms_name_and_phone(tmp_path):
    setup = """
      const vocab = { firm: "Harbor Tax Partners", settings: { phone: "555-0100" } };
      const fields = { "firm-input": { value: "" }, "phone-input": { value: "" } };
      const $ = (id) => fields[id];
      let went = null; const shellGo = (route) => { went = route; };
    """
    probe = 'shellChangeRoot(); return [fields["firm-input"].value, fields["phone-input"].value, went.level];'
    assert run_shell(["shellChangeRoot"], setup, probe, tmp_path) == ["Harbor Tax Partners", "555-0100", "setup"]


def test_a_household_or_return_not_in_the_list_never_shows_its_path_as_a_name(tmp_path):
    setup = PEOPLE + """
      const shellHousehold = () => null; const shellReturn = () => null;
      const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
      const SCREEN_KEYS = { "needs-review": "needs_review" };
      let shellRoute = null; const screenWords = () => vocab.screen;
    """
    probe = """
      shellRoute = { level: "return", household: "/srv/clients/J Park/Gone Family", year: 2025, ret: "/srv/clients/J Park/Gone Family/2025/1040 - X" };
      const names = crumbList().map((s) => s.name);
      shellRoute = { level: "overview" };
      return [names, routeTitle()];
    """
    ran = run_shell(["crumbList", "routeTitle"], setup, probe, tmp_path)
    assert ran == [["Clients", "2025"], ""], "no path as a name, no nameless button, and no H1 on a firm page"


def test_the_contrast_theme_fills_and_rings_follow_spec_10_4():
    css = read("shell.css")
    forced = css[css.index("@media (forced-colors: active)"):]
    for selector in ('.side-section[aria-current="page"]', '.find-option[aria-selected="true"]'):
        line = next(one for one in forced.splitlines() if selector in one and "Highlight" in one)
        assert "forced-color-adjust: none" in line, "Chromium's backplate would hide HighlightText"
    assert ":focus-visible { outline: 2px solid CanvasText; }" in forced
    ring = next(one for one in forced.splitlines() if "#find:focus-visible" in one)
    assert all(part in ring for part in ("#bar #find", "#main #notices", "#main #page .setup", "CanvasText")), \
        "style.css and pilot-ui.css ring inputs and .btn in Highlight; the shell's controls must outrank them"
    counts = next(one for one in forced.splitlines() if ".side-count" in one and ".find-note" in one)
    assert "HighlightText" in counts, "the count and the caption keep their own grey on Highlight otherwise"
    assert "padding-inline: var(--sp-2);" in css[css.index(".side-section:not(.hidden)"):][:400]


def test_folder_names_are_the_last_part_of_the_path_on_either_kind_of_slash(tmp_path):
    probe = 'return [folderName("C:\\\\Clients\\\\Client Files"), folderName("/srv/clients/Client Files/"), folderName("")];'
    assert run_shell(["folderName"], "", probe, tmp_path) == ["Client Files", "Client Files", ""]


def test_every_menu_id_the_page_answers_is_in_the_template_and_the_rest_are_the_rows():
    """SPEC 5.1 and 5.2. The page answers every id but Exit and Open error
    log (main.js's alone, 5.5); the row menus' ids go to pages.js first."""
    template = {"new_household", "change_root", "open_root", "exit", "edit_household", "add_return", "roll_forward", "mark_shared",
                "edit_list", "draft_reminder", "open_client_folder", "open_inbox", "open_working", "overview", "needs_review",
                "reminders", "clients", "find", "refresh", "sort_now", "stop_sorting", "schedule", "repair_schedule", "firm_report",
                "clear_lock", "tour", "safeguards", "terms", "error_log", "about"}
    rows = {"check", "not_requested", "another_return", "put_back", "keep_here", "edit_request", "unfile", "mark_missing"}
    text = read("shell.js")
    table = text[text.index("const MENU_ANSWERS = {"):]
    answered = set(re.findall(r"^  (\w+): ", table[:table.index("\n};\n")], flags=re.M))
    assert answered <= template, sorted(answered - template)
    assert template - answered == {"exit", "error_log"}, sorted(template - answered)
    assert not answered & rows, "the row menus' ids are pages.js's (pagesMenu), asked first"
    assert "pagesMenu(id, message.token)" in text


def test_a_menu_id_the_page_cannot_answer_is_said_and_logged():
    text = stripped_js("shell.js")
    body = text[text.index("function unanswered(id) {"):]
    body = body[:body.index("\n}\n")]
    assert "notice(" in body and "vocab.shell.page_error" in body and "window.tracker.logError(" in body


def test_the_shell_sends_only_the_menu_channels_messages_and_no_path():
    """SPEC 5.4: {enable} and {popup, enable, token, x, y}; the token is a
    key the page made, never a path."""
    text = stripped_js("shell.js")
    sends = re.findall(r"window\.tracker\.menu\.send\(([^;]*)\);", text)
    assert sorted(sends) == sorted(["{ enable: shellEnabled() }", "{ popup: name, enable: shellEnabled(), token, x, y }"])
    assert 'shellPopup(one.popup, `crumb-${one.popup}`' in text, "a segment's token is its own name"
    assert "window.tracker.menu.onCommand(shellMenu)" in text
