"""The app shell's renderer half (pilot SPEC-shell.md, decisions P58-P77).

What can be pinned without a browser: the tokens and their contrast in both
themes, the shell stylesheet's discipline (tokens only, the 4px grid), the
guards every renderer file keeps, the words the new files may not type, and -
run in node against the files' own functions, as the repository's other
renderer tests do - the route, the search, the Sort Now button and the menu's
enable list. The rendered claims (a screenshot of every scenario, light and
dark, at both sizes) come from ``pilot/harness/shoot.mjs``.

This file is S3's part of SPEC section 14.1. S2 adds the menu half (the
template, the ``menu`` channel, the first paint), S4 the pages' node tests and
S5 the sheet's; the lists below that name the files a claim covers
(``SHELL_FILES``, ``TITLE_FREE``) are the ones they extend.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import pytest

import tracker.api as api
from tests.css_rules import GRID_PROPS, GRID_TOKEN, blocks, colour_faults, declarations, stripped, top_level
from tests.node_harness import (
    COLUMN_FUNCTIONS,
    EARLY_FIRM,
    ENGINE_BRIDGE,
    FAKE_DOM,
    NODE,
    RENDERER,
    js_function,
    lift_line,
    read,
    run_firm_load,
    run_firm_page,
    run_last_counts,
    run_lists,
    run_long,
    run_notices,
    run_pages,
    run_pages_dom,
    run_reminder_sheet,
    run_shell,
    run_sort_end,
    run_speed,
    store_functions,
)
from tests.test_api import run, sample_engagement, scan
from tracker import settings as settings_module

REPO = Path(__file__).resolve().parent.parent

#: The new renderer scripts. S5 adds sheet.js.
SHELL_FILES = ("shell.js", "tooltip.js", "pages.js", "sheet.js")
#: Files that hold no ``title`` attribute (SPEC 13): every tooltip is setTip().
TITLE_FREE = ("shell.js", "tooltip.js", "pages.js", "sheet.js", "shell.css", "pilot.js", "tour.js", "app.js", "index.html")
#: Floating UI, vendored (Jason's ruling 5, 2026-09-29), loaded before app.js, core
#: first: the DOM build asks for the core build's global.
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
               "--navy": "--accent", "--blue": "--focus", "--blue-dark": "--focus"}
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
    scripts = [html.index(f'src="{name}"') for name in (*FLOATING_UI_SCRIPTS, "app.js", "tooltip.js", "pages.js", "sheet.js", "shell.js", "pilot-content.js", "pilot.js", "tour.js")]
    assert scripts == sorted(scripts)
    # Every script is a file of the app itself: no scheme, no host, no CDN.
    sources = re.findall(r"""<script[^>]*\bsrc=[\"']?([^\"'\s>]+)""", html, re.I)
    assert len(sources) == len(scripts)
    for source in sources:
        assert not re.match(r"^([a-z][a-z0-9+.-]*:|//|/)", source, re.I), source
        assert (RENDERER / source).is_file(), source
    assert ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'") in html
    assert "<style" not in html and not re.search(r"<script(?![^>]*\bsrc=)", html)


def test_the_vendored_floating_ui_is_the_pinned_bytes_and_nothing_else():
    """Jason's ruling 5: placement is Floating UI's, copied unedited. The hashes
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


def test_a_tip_goes_when_its_element_is_scrolled_out_of_view():
    """Floating UI's hide() marks a reference clipped away; the tip follows
    its element while it is visible and is hidden once it is not."""
    js = stripped_js("tooltip.js")
    assert "FloatingUIDOM.hide(" in js
    then = js[js.index(".then("):js.index("function showTip")]
    assert "middlewareData.hide" in then and "referenceHidden" in then and "hideTip()" in then


def test_the_hover_delay_is_300_ms_and_keyboard_focus_waits_for_nothing():
    """Jason's ruling 7 (2026-09-29): hover shows the tip after 300 ms; focus
    shows it at once."""
    js = stripped_js("tooltip.js")
    assert re.search(r"const TIP_DELAY_MS = 300;", js)
    assert js.count("TIP_DELAY_MS") == 2 and "setTimeout(() => showTip(node), TIP_DELAY_MS)" in js
    focus = js[js.index('addEventListener("focusin"'):]
    focus = focus[:focus.index("});")]
    assert "showTip(node)" in focus and "TIP_DELAY_MS" not in focus


def test_the_search_box_alone_shows_no_tooltip_on_keyboard_focus():
    """Jason's ruling 2 (SPEC 8.5): every other control shows its tip when the
    keyboard reaches it; the search box does not (hover still does)."""
    js = stripped_js("tooltip.js")
    focus = js[js.index('addEventListener("focusin"'):]
    focus = focus[:focus.index("});")]
    assert ':focus-visible' in focus and 'matches("#find")' in focus
    assert 'matches("input")' not in focus and "textarea" not in focus
    assert '<input id="find"' in read("index.html")


def test_escape_hides_a_showing_tip_first_and_leaves_the_key_to_the_page(tmp_path):
    """P130 (the Windows check's F2): a hover tip over the Sort icon while the
    search box has the focus survived Escape, because only the last branch of
    ``shellKey`` hid a tip. ``tooltip.js``'s ``tipKey`` hides the tip and does
    not consume the key, so the same Escape still does the page's own thing
    (clear the search box, close the sheet or a dialog)."""
    setup = """
      let tipFor = null, hidden = 0;
      function hideTip() { hidden += 1; tipFor = null; }
      const key = (k) => { const e = { key: k, stopped: 0, prevented: 0 };
        e.preventDefault = () => { e.prevented += 1; }; e.stopPropagation = () => { e.stopped += 1; };
        e.stopImmediatePropagation = () => { e.stopped += 1; }; return e; };
    """
    probe = """
      const out = [];
      tipFor = { id: "sort" }; let e = key("Escape"); tipKey(e); out.push([hidden, tipFor, e.prevented, e.stopped]);
      e = key("Escape"); tipKey(e); out.push([hidden, e.prevented, e.stopped]);
      tipFor = { id: "sort" }; e = key("Tab"); tipKey(e); out.push([hidden, tipFor === null]);
      return out;
    """
    out = run_shell(["tipKey"], setup, probe, tmp_path, "tooltip.js")
    assert out == [[1, None, 0, 0], [1, 0, 0], [1, False]]


# P202: the whole of tooltip.js, run as it is under a page of fakes - its own
# listeners, a timer the probe fires by hand, and elements a page change can
# take off the page (isConnected false) without ever sending mouseout.
TIP_PAGE = r"""
class Element {
  constructor(words) { this.dataset = words ? { tip: words } : {}; this.isConnected = true; this.attrs = {};
    this.scrollWidth = 10; this.clientWidth = 10; }
  closest() { return this.dataset.tip !== undefined ? this : null; }
  contains(other) { return other === this; }
  matches() { return false; }
  setAttribute(k, v) { this.attrs[k] = v; }
  removeAttribute(k) { delete this.attrs[k]; }
}
const tipBox = { hidden: true, textContent: "", style: { setProperty() {} } };
const handlers = {};
const document = { getElementById: (id) => (id === "tip" ? tipBox : null),
  addEventListener: (type, fn) => { handlers[type] = fn; } };
const window = { addEventListener() {} };
const FloatingUIDOM = { computePosition: () => ({ then() {} }), offset() {}, flip() {}, shift() {}, hide() {} };
const timers = new Map(); let lastTimer = 0;
const setTimeout = (fn) => { lastTimer += 1; timers.set(lastTimer, fn); return lastTimer; };
const clearTimeout = (id) => { timers.delete(id); };
const tick = () => { const due = [...timers.values()]; timers.clear(); due.forEach((fn) => fn()); };
const over = (target) => handlers.mouseover({ target });
const seen = (node) => [tipBox.hidden, tipBox.textContent, node.attrs["aria-describedby"] || null];
"""


def test_a_tip_whose_element_leaves_the_page_is_hidden_at_the_next_mouse_move(tmp_path):
    """P202 R1, the fault as seen: a Taxpayer link's tip showed, the page
    changed under a resting mouse, and the tip stayed over the new page while
    the mouse moved over plain parts of it - a removed element never sends
    mouseout, and a mouseover on an element without a tip returned early."""
    probe = """
      const link = new Element("Navigate to Return (Okafor Family)"), plain = new Element("");
      const out = [];
      over(link); tick(); out.push(seen(link));
      link.isConnected = false; over(plain); out.push(seen(link));
      return out;
    """
    out = run_shell([], TIP_PAGE + read("tooltip.js"), probe, tmp_path)
    assert out == [[False, "Navigate to Return (Okafor Family)", "tip"], [True, "Navigate to Return (Okafor Family)", None]]


def test_a_page_change_hides_a_showing_tip(tmp_path):
    """P202 R2: Ctrl+1-4 and the side panel's links all go through shellGo,
    which hides a showing tip before it draws the new page, so a resting
    mouse leaves no tip behind even for a frame."""
    setup = TIP_PAGE + read("tooltip.js") + """
      const LEVELS = ["overview", "needs-review", "reminders", "clients", "household", "year", "return", "setup"];
      const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"]; const pagesEnter = () => {}; const shellFirmFollow = () => {};
      let shellRoute = { level: "overview" }, shellBack = null, shellRootSet = true, shellPageBusy = false, shellPageFailed = false;
      const hideFound = () => {}, appRouteChanged = () => {}, closeSheet = () => {}, failed = (err) => { throw err; };
      const atDraw = [];
      const shellDraw = () => { atDraw.push(tipBox.hidden); };
      const $ = () => ({ scrollTop: 0, focus() {} });
      const shellOpenState = () => Promise.resolve();
    """
    probe = """
      const link = new Element("Navigate to Return (Okafor Family)");
      over(link); tick(); const before = seen(link);
      return shellGo({ level: "needs-review" }).then(() => [before, seen(link), atDraw]);
    """
    out = run_shell(["shellGo"], setup, probe, tmp_path)
    assert out == [[False, "Navigate to Return (Okafor Family)", "tip"],
                   [True, "Navigate to Return (Okafor Family)", None], [True]]


def test_a_tip_waiting_on_its_delay_is_never_shown_for_an_element_that_left(tmp_path):
    """P202 R3: a hover just before a keyboard page change starts the delay;
    when it ends the element is gone, and no tip shows for it."""
    probe = """
      const link = new Element("Navigate to Return (Okafor Family)");
      over(link); link.isConnected = false; tick();
      return seen(link);
    """
    out = run_shell([], TIP_PAGE + read("tooltip.js"), probe, tmp_path)
    assert out == [True, "", None]


def test_shell_key_hands_escape_to_the_tip_first_wherever_the_focus_is(tmp_path):
    """P130, wired: ``shellKey`` (the one keydown listener's first step, SPEC
    4.3) hands every key to ``tipKey`` before anything else, so the search
    box's own Escape, a dialog's and the side sheet's no longer leave a tip
    showing. Reproduced before the fix: focus in the search box, a hover tip
    on the Sort icon, Escape - the search box was cleared and the tip stayed."""
    setup = """
      let tipFor = null, dialogStack = [], cleared = 0, shellFindTimer = null;
      function hideTip() { tipFor = null; }
      const nodes = { find: { value: "Smi" }, sheet: { hidden: true }, "find-list": { hidden: true } };
      const $ = (id) => nodes[id];
      function hideFound() { cleared += 1; }
      const key = (k, target) => ({ key: k, target, preventDefault() {} });
    """
    probe = """
      const out = [];
      tipFor = { id: "sort" }; out.push([shellKey(key("Escape", nodes.find)), tipFor, cleared, nodes.find.value]);
      tipFor = { id: "sort" }; dialogStack = ["modal"];
      out.push([shellKey(key("Escape", { closest: () => null })), tipFor]);
      return out;
    """
    out = run_shell(["shellKey", "findKey"], setup + js_function("tipKey", "tooltip.js"), probe, tmp_path)
    assert out == [[True, None, 1, ""], [False, None]]
    assert "tipShowing" not in read("tooltip.js") and "hideTip" not in js_function("shellKey")


def test_the_skeleton_is_the_specs_and_no_hidden_box_is_used_as_a_variable():
    """SPEC 3.1 and 13. The pages took the toolbar, the banners, the request
    table, the household card and the setup card; the side sheet took the
    reminder, moved, review and filed cards; the dialogs took the roll fold
    and the standing rules. The three hidden boxes saveRoot() once read are
    one object in app.js (setupDraft)."""
    html = read("index.html")
    for wanted in ('id="shell"', 'id="side"', 'id="side-brand"', 'id="side-sections"', 'id="side-foot"', 'id="last-sort"',
                   'id="main"', 'id="bar"', 'id="crumbs"', 'id="find-wrap"', 'id="find"', 'id="find-list"', 'id="sort"',
                   'id="notices"', 'id="page"', 'id="sheet"', 'id="sheet-scrim"', 'id="tip"', 'id="toast"'):
        assert wanted in html, wanted
    assert html.count('data-section="') == 4
    assert 'id="legacy"' not in html
    outside = html[:html.index('<div id="household-modal"')]
    for gone in ("topbar", "brand-logo", 'id="eng-select"', "btn-scan", "btn-inbox", 'id="toolbar"', 'class="toolbar"', "eng-form", "view-state",
                 'id="banner"', 'id="reader-warning"', 'id="last-pass"', 'id="machine-warnings"', 'id="after-install"',
                 'id="lock-notice"', 'id="misfits-card"', 'id="room-card"', 'id="setup-card"', 'id="household-card"',
                 'id="rows"', 'id="summary"', 'id="pass-progress"', "btn-unlock", "btn-stop-pass", "household-returns",
                 "review-deck", "review-mode", "mode-toggle", "deck"):
        assert gone not in outside, gone
    for gone in ('id="root-input"', 'id="firm-input"', 'id="phone-input"'):
        assert gone not in html, gone
    assert 'let setupDraft = { root: "", firm: "", phone: "" };' in read("app.js")
    for taken in ('id="reminder-card"', 'id="moved-card"', 'id="review-card"', 'id="filed-card"', 'id="assurances"', 'id="household-roll"',
                  'id="dismissed-card"', 'id="btn-open-draft"', 'id="reminder-hint"', 'id="reminder-heading"'):
        assert taken not in html, taken
    # The sheet's frame (SPEC 7): the header's icons, the two bodies, the two footers, and the reminder's parts with the ids drawReminder() draws into.
    for sheet in ('id="sheet-open"', 'id="sheet-more"', 'id="sheet-next"', 'id="sheet-close"', 'id="sheet-check"', 'id="sheet-reminder"',
                  'id="check-actions"', 'id="reminder-actions"', 'id="reminder-status"', 'id="reminder-stages"', 'id="reminder-preview"',
                  'id="btn-copy"', 'id="btn-approve"'):
        assert sheet in html, sheet
    for dialog in ("roll-modal", "safeguards-modal", "about-modal", "misfits-modal"):
        assert f'id="{dialog}" class="modal-overlay hidden"' in html, dialog
    for symbol in ("search", "dismiss", "chev", "next", "done", "more", "open"):
        assert f'<symbol id="i-{symbol}"' in html, symbol
    assert 'role="alert" aria-live="polite"' in html[html.index('id="notices"'):html.index('id="notices"') + 120]


def test_every_element_the_renderer_looks_up_by_id_is_in_the_page_or_built_by_it():
    """A card's markup deleted from index.html while a line of app.js still
    sets its text is a page that fails at start-up, before anything is drawn.
    Every literal id the renderer asks for exists in index.html, or is one a
    renderer file builds itself (the pilot layer's cards, the pages' own)."""
    html = read("index.html")
    present = set(re.findall(r'\bid="([^"]+)"', html))
    built = set()
    for name in ("app.js", "pages.js", "shell.js", "sheet.js", "tooltip.js", "pilot.js", "tour.js", "pilot-content.js"):
        built |= set(re.findall(r'\bid:\s*"([^"]+)"', stripped_js(name)))
    missing = {}
    for name in ("app.js", "pages.js", "shell.js", "sheet.js", "tooltip.js", "pilot.js", "tour.js"):
        for found in re.finditer(r'\$\("([^"]+)"\)|getElementById\("([^"]+)"\)|querySelector\("#([\w-]+)', stripped_js(name)):
            ident = found.group(1) or found.group(2) or found.group(3)
            if ident not in present and ident not in built and not ident.startswith("pilot-"):
                missing.setdefault(name, set()).add(ident)
    assert not missing, missing


def test_every_icon_has_a_name_and_a_tooltip():
    """SPEC 8.5, 14.1: each icon-only button carries data-tip-key, naming a
    vocabulary key; shell.js sets both its accessible name and its tooltip from it."""
    html = read("index.html")
    shell = stripped_js("shell.js")
    keys = re.findall(r'<button[^>]*\bid="(sheet-close)"[^>]*data-tip-key="([\w.]+)"', html)
    assert {name for name, _key in keys} == {"sheet-close"}, "P274: the sort button says its own word, so it is not an icon-only button"
    assert re.search(r'<input[^>]*\bid="find"[^>]*data-tip-key="screen\.find"', html)
    for _name, key in keys:
        assert key.startswith("screen.")
    named = shell[shell.index("function shellNameIcons() {"):]
    named = named[:named.index("\n}\n")]
    assert 'setAttribute("aria-label", words)' in named and "setTip(node, words)" in named
    # The notice's close icon is cloned from a template, so app.js names it when it draws one.
    template = html.split('<template id="notice-buttons">', 1)[1].split("</template>", 1)[0]
    assert re.search(r'<button[^>]*data-act="dismiss"[^>]*data-tip-key="screen\.icons\.dismiss"', template)
    app = read("app.js")
    drawing = app[app.index("function drawNotice(entry) {"):]
    drawing = drawing[:drawing.index("\n}\n")]
    assert "setAttribute(\"aria-label\", vocab.screen.icons.dismiss)" in drawing and "setTip(dismiss, vocab.screen.icons.dismiss)" in drawing


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
    """h() is app.js's el(), which throws on an attribute it does not name
    (decision 137). A key used at a call site but missing from the list
    would throw when that node is first drawn - the harness found one."""
    text = stripped_js("shell.js")
    builder = stripped_js("app.js")
    listed = set(re.findall(r'"([\w-]+)"', builder[builder.index("const EL_ATTRIBUTES = new Set(["):builder.index("]);")]))
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

def test_style_css_writes_no_literal_colour():
    """SPEC 10.4: pilot-ui.css restated every literal colour of style.css
    through a token, selector for selector, so the dark values reach it; once
    each was overridden whole the literals were deleted. A colour written in
    style.css again would be one with no dark value."""
    literal = [(selector.strip(), prop) for _media, selector, body in blocks(read("style.css"))
               for prop, value in declarations(body) if re.search(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(", value)]
    assert literal == []


# ── node: the shell's own functions ───────────────────────────────────────


PEOPLE = r"""
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
const vocab = { screen: { counts: { one_return: "1 return", returns: "{n} returns" },
  sections: { overview: "Overview", needs_review: "Needs review", reminders: "Reminders", clients: "Clients" },
  sort: { now: "Sort now", stop: "Stop sorting", locked: "In use elsewhere", stopping: "Stopping", tip: "Sort this household's inbox" } } };
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
    ran = run_shell(["screenWords", "fold", "foldedName", "shellHousehold", "shellOwnReturns", "findOptions"], PEOPLE, probe, tmp_path)
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
    assert run_shell(["screenWords", "fold", "foldedName", "shellHousehold", "shellOwnReturns", "findOptions"], setup, probe, tmp_path) == 8


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


def test_the_menus_enable_list_follows_the_rules_of_the_template(tmp_path):
    setup = PEOPLE + """
      let shellRoute = null; let shellRootSet = true; let shellPaths = { status: "s" }; let scanning = null; let locked = false;
      let lockStale = false; let lastState = null;
    """
    probe = """
      const ids = (route, o = {}) => { shellRoute = route; shellRootSet = o.root ?? true; scanning = o.scan ?? null; locked = o.locked ?? false;
        lockStale = o.stale ?? false;
        lastState = { household: { path: "h1", shared_on: o.shared ? "d" : "", pause: o.paused ? { sentence: "Folder renamed" } : {} } };
        return shellEnabled(); };
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
        paused: ids({ level: "household", household: "h1" }, { paused: true }).filter((id) => ["add_return", "edit_household"].includes(id)),
        stale: [ids({ level: "return", household: "h1", ret: "r1" }).includes("clear_lock"), ids({ level: "return", household: "h1", ret: "r1" }, { stale: true }).includes("clear_lock")],
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
    assert ran["paused"] == ["edit_household"], "while a household is paused the pause is the work: no Add a return"
    assert ran["stale"] == [False, True], "Clear stuck lock is offered for a lock left behind only"
    assert ran["locked"] == [] and ran["lockedKeepsRead"], "a locked return greys the writing items and no others"
    assert ran["sorting"] == [False, True]
    assert ran["noRoot"] == [] and ran["alwaysOn"]


def test_changing_the_clients_folder_keeps_the_firms_name_and_phone(tmp_path):
    setup = """
      const vocab = { firm: "Harbor Tax Partners", settings: { phone: "555-0100" } };
      const setupDraft = { root: "", firm: "", phone: "" };
      let went = null; const shellGo = (route) => { went = route; };
    """
    probe = 'shellChangeRoot(); return [setupDraft.firm, setupDraft.phone, went.level];'
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
    # The focused row keeps its own colours (forced-color-adjust: none), and the step's link colour
    # (.row-step:not(.hidden), 0,2,0) outranks the inherit above: every part must say HighlightText itself.
    step = next(one for one in forced.splitlines() if ".rows:focus-visible .row.is-active .row-step" in one and "HighlightText" in one)
    assert step.count(".rows:focus-visible .row.is-active") >= 1
    focused = forced[forced.index(".rows:focus-visible .row.is-active .row-name"):]
    focused = focused[:focused.index("}")]
    assert all(part in focused for part in (".row-detail", ".row-status", ".row-date", ".row-step")) and "color: HighlightText" in focused


def test_folder_names_are_the_last_part_of_the_path_on_either_kind_of_slash(tmp_path):
    probe = 'return [folderName("C:\\\\Clients\\\\Client Files"), folderName("/srv/clients/Client Files/"), folderName("")];'
    assert run_shell(["folderName"], "", probe, tmp_path) == ["Client Files", "Client Files", ""]


def test_every_menu_id_the_page_answers_is_in_the_template_and_the_rest_are_the_rows():
    """SPEC 5.1 and 5.2. The page answers every id but Exit and Open error
    log (main.js's alone, 5.5); the row menus' ids go to pages.js first."""
    template = {"new_household", "change_root", "open_root", "exit", "edit_household", "add_return", "roll_forward", "mark_shared",
                "edit_list", "draft_reminder", "open_client_folder", "open_inbox", "open_working", "overview", "needs_review",
                "reminders", "clients", "find", "refresh", "reset_columns", "compact_rows", "show_under_construction", "sort_now", "stop_sorting", "schedule", "repair_schedule", "remove_schedule_here", "firm_report",
                "clear_lock", "tour", "safeguards", "terms", "error_log", "about"}
    rows = {"check", "not_requested", "another_return", "put_back", "keep_here", "edit_request", "unfile", "mark_missing", "show_in_explorer"}
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
    """SPEC 5.4: {enable, checked} (P197) and {popup, enable, token, x, y};
    the token is a key the page made, never a path."""
    text = stripped_js("shell.js")
    sends = re.findall(r"window\.tracker\.menu\.send\(([^;]*)\);", text)
    assert sorted(sends) == sorted(["{ enable: shellEnabled(), checked: shellChecked() }", "{ popup: name, enable: enable || shellEnabled(), token, x, y }"])
    assert 'shellPopup(one.popup, `crumb-${one.popup}`' in text, "a segment's token is its own name"
    assert "window.tracker.menu.onCommand(shellMenu)" in text


# ── node: the pages (SPEC 6, 3.6, 14.1) ────────────────────────────────────


def test_a_return_page_draws_its_groups_in_order_and_leaves_out_empty_ones_but_received(tmp_path):
    """SPEC 6.7: Needs you, Waiting on client, Received, Set aside, each
    from the API's `group`; a group with no rows is left out, but Received,
    which says "Nothing received yet"; Set aside is a closed `details`."""
    ran = run_pages_dom("""
      const full = stateOf([item("A", "set_aside", { status_key: "NotAsked" }), item("B", "received", { status_key: "Received", received_date: "2026-03-01" }),
                            item("C", "waiting"), item("D", "needs_you", { status_key: "Rejected" })], [parked("p1")]);
      const headings = (state) => { lastState = state; const box = page(pagesReturn({ level: "return", ret: "r1", year: 2025 }));
        return { titles: box.byClass("group-title").map((one) => one.textContent), none: box.byClass("group-none").map((one) => one.textContent),
                 folds: box.find((one) => one.tag === "details").map((one) => one.open), h1: box.find((one) => one.tag === "h1").length }; };
      return { full: headings(full), bare: headings(stateOf([item("D", "needs_you")])), quiet: headings(stateOf([])) };
    """, tmp_path)
    assert ran["full"]["titles"] == ["Needs you", "Waiting on client", "Received", "Set aside"]
    assert ran["full"]["folds"] == [False], "Set aside is shut each time the page opens"
    assert ran["bare"]["titles"] == ["Needs you", "Received"] and ran["bare"]["none"] == ["Nothing received yet"]
    assert ran["quiet"]["titles"] == ["Received"] and ran["quiet"]["h1"] == 1


def test_a_returns_needs_you_group_holds_parked_files_then_moved_then_requests_then_the_buckets(tmp_path):
    ran = run_pages_dom("""
      const state = stateOf([item("A", "needs_you", { status_key: "Rejected" })],
        [parked("b-old", { received: "2026-03-01" }), parked("a-new", { received: "2026-03-05" }),
         parked("zip", { bucket: "container", code: "opened-not-across" })],
        [{ handle: "m1", original_name: "moved.pdf", identifier: "A" }]);
      const groups = pagesReturnGroups(state, 2025);
      return groups.needs_you.map((one) => [one.name, one.status, one.sub || "", one.reason || ""]);
    """, tmp_path)
    assert ran == [["b-old.pdf", "Could not tell", "", "unmatched"], ["a-new.pdf", "Could not tell", "", "unmatched"], ["moved.pdf", "Moved by hand", "", ""],
                   ["Doc A", "Could not use", "", ""], ["zip.pdf", "Email or zip", "Emails and zips", "opened-not-across"]]


def test_a_status_that_is_a_tag_always_carries_the_words_it_stands_for_as_its_tooltip(tmp_path):
    """Pilot P116: "Email or Zip" is a tag for "Came in Email or Zip", so its
    tooltip says those words every time, cut or not. Any other status is its
    own tooltip only when it is cut, and a vocabulary with no tip table is a
    loud failure, not a row with no tip."""
    ran = run_pages_dom("""
      const row = (code) => { tips.length = 0; cutTips.length = 0;
        const node = pagesRow({ name: "x.pdf", detail: "", status: pagesReason(code), reason: code, tone: "needs", date: "", menu: "file",
                                step: { kind: "check", ret: "r", name: "x.pdf", handle: "h" } });
        return { tip: tips.filter(([cls]) => cls.startsWith("row-status")).map(([, words]) => words),
                 cut: cutTips.filter((cls) => cls.startsWith("row-status")).length, described: node.getAttribute("aria-description") || "" }; };
      const tagged = row("opened-not-across"); const plain = row("unmatched");
      const saved = vocab.reason_tips; delete vocab.reason_tips;
      let loud = ""; try { row("unmatched"); } catch (err) { loud = err.message; }
      vocab.reason_tips = saved;
      return { tagged, plain, loud };
    """, tmp_path)
    # The keyboard never focuses the status, so the row's description carries the words (review SHOULD-1).
    assert ran["tagged"] == {"tip": ["Came in email or zip"], "cut": 0, "described": "Check, Came in email or zip"}
    assert ran["plain"] == {"tip": ["Could not tell"], "cut": 1, "described": "Check"}
    assert ran["loud"] == "reason_tips"


def test_the_pages_groups_and_the_firms_tally_of_them_cannot_disagree(tmp_path):
    """SPEC 9.1: the Overview's counts and the return page's groups come from
    the same `group`. pagesTally is what shell.js compares with the firm."""
    ran = run_pages_dom("""
      const state = stateOf([item("A", "needs_you"), item("B", "waiting"), item("C", "waiting"), item("D", "received", { status_key: "Received" }),
                             item("E", "set_aside", { status_key: "NotAsked" })],
        [parked("p1"), parked("p2"), setAsideRow("d1"), movedRow("m1")],
        [{ handle: "m1", original_name: "m1.pdf", identifier: "A" }]);
      const groups = pagesReturnGroups(state, 2025);
      return { tally: pagesTally(state), drawn: Object.fromEntries(Object.entries(groups).map(([key, rows]) => [key, rows.length])) };
    """, tmp_path)
    assert ran["tally"] == ran["drawn"] == {"needs_you": 4, "waiting": 2, "received": 1, "set_aside": 2}


def test_the_overview_words_each_row_the_engine_sends_in_the_order_it_sends_them(tmp_path):
    """SPEC 6.1, as P278 moved it: the engine puts each return in one bucket and
    orders them (tests/test_firm_pages.py); the window words each row it is given
    - a paused household, a return needing a person (since when), a return waiting
    on the client (due when), a return whose record could not be read (saying so) -
    and sorts, drops and adds none."""
    ran = run_pages_dom("""
      const names = { a: "Alpha", b: "Bravo", d: "Delta", e: "Echo", f: "Foxtrot" };
      shellReturn = (path) => ({ return_name: names[path], household: "h", year: 2025 });
      const make = (path, bucket, counts, extra = {}) => ({ kind: "return", bucket, path, household: "h", counts: { needs_you: 0, waiting: 0, received: 0, set_aside: 0, ...counts }, oldest: null, due: null, problem: "", ...extra });
      const rows = pagesWorkRows([
        { kind: "paused", household: "Gamma", household_path: "g" },
        make("e", "need", {}, { problem: "Record unreadable" }), make("d", "need", { needs_you: 1 }, { oldest: "2026-03-02" }),
        make("a", "need", { needs_you: 2, waiting: 1 }, { oldest: "2026-03-04" }),
        make("f", "wait", { waiting: 1 }, { due: "2026-04-01" }), make("b", "wait", { waiting: 2 }, { due: "2026-04-15" }) ]);
      return rows.map((one) => [one.name, one.status, one.tone, one.date, one.step.kind]);
    """, tmp_path)
    assert [one[0] for one in ran] == ["Gamma", "Echo", "Delta", "Alpha", "Foxtrot", "Bravo"], "in the order the engine sent them"
    assert ran[0][1:3] == ["Two Years Open; Sorting Paused", "needs"] and ran[1][1:3] == ["Record unreadable", "needs"]
    assert ran[3][1:3] == ["2 need you", "needs"], "a return with both counts is worded by the first"
    assert [one[3] for one in ran[2:]] == ["Since Mar 2", "Since Mar 4", "Due Apr 1", "Due Apr 15"] and ran[4][2] == "waiting"
    assert all(one[4] == "open" for one in ran)


def test_a_row_carries_one_step_and_its_status_word_and_no_sentence(tmp_path):
    """SPEC 3.6 and P63: name, detail, status, and an end column holding the
    date and at most one step; the step is aria-hidden and named by
    aria-description; no title attribute; no sentence anywhere. A live lock
    takes the Edit step away, as the menu's Edit request list goes grey."""
    ran = run_pages_dom("""
      const spec = { name: "scan0012.pdf", detail: "W-2", status: "Could not tell", tone: "needs", date: "Mar 3", menu: "file", step: { kind: "check" } };
      const shape = (node) => ({ cols: node.kids.map((one) => one.className.split(" ")[0]), end: node.kids[3].kids.map((one) => one.className.split(" ")[0]),
        status: node.kids[2].textContent, role: node.attrs.role, hidden: node.byClass("row-step").map((one) => one.attrs["aria-hidden"]),
        described: node.attrs["aria-description"] || "", menu: node.dataset.menu, titles: node.find((one) => "title" in one.attrs).length });
      const edit = { ...spec, step: { kind: "edit", identifier: "A" } };
      const before = shape(pagesRow(edit)); locked = true; const during = shape(pagesRow(edit)); locked = false;
      return { check: shape(pagesRow(spec)), before, during, plain: shape(pagesRow({ ...spec, step: null })) };
    """, tmp_path)
    assert ran["check"]["cols"] == ["row-name", "row-detail", "row-status", "row-end"]
    assert ran["check"]["end"] == ["row-date", "row-step"] and ran["check"]["hidden"] == ["true"]
    assert ran["check"]["status"] == "Could not tell" and ran["check"]["role"] == "option"
    assert ran["check"]["described"] == "Check" and ran["check"]["menu"] == "file" and ran["check"]["titles"] == 0
    assert ran["before"]["end"] == ["row-date", "row-step"] and ran["during"]["end"] == ["row-date"]
    assert ran["plain"]["end"] == ["row-date"] and ran["plain"]["described"] == ""


def test_long_names_are_cut_and_carry_their_full_name_as_the_tooltip(tmp_path):
    """SPEC 6: a household name of 60 characters and a return name of 80 end
    in an ellipsis at their column; the full name is the row's tooltip. The
    ellipsis is CSS on the name column; an H1 wraps, and is never cut."""
    ran = run_pages_dom("""
      const household = "Alexandria Montgomery-Whitfield and Christopher Delacroix".padEnd(60, "x").slice(0, 60);
      const ret = "1040 - Alexandria Montgomery-Whitfield & Christopher Delacroix Family Trust".padEnd(80, "y").slice(0, 80);
      for (const name of [household, ret]) pagesRow({ name, detail: "", status: "", tone: "plain", date: "", menu: "return" });
      return { tips: tips.filter(([cls]) => cls === "row-name").map(([, words]) => words.length), same: tips.filter(([cls]) => cls === "row-name").map(([, words]) => words) };
    """, tmp_path)
    assert ran["tips"] == [60, 80]
    css = read("shell.css")
    name_rule = next(body for _m, selector, body in blocks(css) if selector.strip() == ".row-name" or ".row-name" in selector.split(","))
    assert "text-overflow: ellipsis" in name_rule and "white-space: nowrap" in name_rule
    title_rule = next(body for _m, selector, body in blocks(css) if selector.strip().startswith(".page-title"))
    assert "ellipsis" not in title_rule and "nowrap" not in title_rule, "an H1 wraps to two lines, not one cut line"
    assert "-webkit-line-clamp: 2" in title_rule


def test_only_the_household_year_and_return_pages_draw_an_h1():
    """SPEC 6 and P75: the four firm pages have no H1 (the path and the
    selected section name them); the levels below do."""
    text = stripped_js("pages.js")
    body = lambda name: text[text.index(f"function {name}("):text.index("\n}\n", text.index(f"function {name}("))]  # noqa: E731
    for firm in ("pagesOverview", "pagesNeedsReview", "pagesReminders", "pagesClients"):
        assert "pagesTitle(" not in body(firm) and '"h1"' not in body(firm), firm
    for client in ("pagesHousehold", "pagesYear", "pagesReturn"):
        assert "pagesTitleFor(" in body(client), client
    assert text.count('"h1"') == 1


def test_the_household_pages_notices_are_two_years_folder_renamed_and_feeds(tmp_path):
    """SPEC 6.5 and 11.1: while a household's pages are open its notices show:
    two years open, folder renamed with Accept (only when the pause names a
    scope), a year's pause without it, and the feeds that do not resolve; each
    in its short line, the API's long sentence in the error log; they go with
    the household's pages."""
    ran = run_pages_dom("""
      const seen = [];
      syncNotices = (prefix, wanted) => seen.push([prefix, wanted.map((one) => [one.key.split(":")[0], one.failure.sentence, (one.opts && one.opts.action) ? one.opts.action.label : "", one.detail || ""])]);
      const home = { path: "h1", open_years: [2025, 2024], pause: { sentence: "PAUSED LONG", scope: "household" }, feeds: [{ warning: "FEED LONG" }, {}] };
      lastState = { household: home };
      pagesHouseholdNotices({ level: "household", household: "h1" });
      lastState = { household: { ...home, pause: { sentence: "PAUSED YEAR LONG" }, open_years: [2025], feeds: [] } };
      pagesHouseholdNotices({ level: "return", household: "h1" });
      pagesHouseholdNotices({ level: "clients" });
      lastState = { household: { ...home, path: "h2" } };
      pagesHouseholdNotices({ level: "year", household: "h1" });
      return seen;
    """, tmp_path, setup="""
      vocab.household = { two_open_years: "Two years open; sorting paused", accept_folder_name: "Accept the folder's name" };
      vocab.after_install = { wait: "Setup needs attention" };
      vocab.screen.notices = { renamed: "Folder renamed", paused: "Year folder mismatch", feed: "Feed not resolved" };
      const acceptFolderName = () => {};
    """, functions=["pagesHouseholdNotices", "shortNotice"])
    assert ran[0] == ["household", [["two-years", "Two years open; sorting paused", "", ""],
                                    ["renamed", "Folder renamed", "Accept the folder's name", "PAUSED LONG"],
                                    ["feeds", "Feed not resolved", "", "FEED LONG"]]]
    assert ran[1] == ["household", [["renamed", "Year folder mismatch", "", "PAUSED YEAR LONG"]]], "no Accept when the pause names no scope"
    assert ran[2] == ["household", []] and ran[3] == ["household", []], "another household's state, or a firm page, has none"


def test_a_notice_whose_short_word_the_vocabulary_lacks_falls_back_to_the_setup_line_and_logs_the_sentence(tmp_path):
    """No word is invented: with no `vocab.screen.notices.renamed` (and the
    others) the approved setup line stands in, and the long sentence still
    reaches the error log. The keys asked of S6 are listed in the handoff.
    A missing word is loud: the key it lacks goes to the error log, once per
    key however often the page is drawn (review 2, F1)."""
    ran = run_pages_dom("""
      const seen = [];
      syncNotices = (prefix, wanted) => seen.push(wanted.map((one) => [one.failure.sentence, one.detail || ""]));
      lastState = { household: { path: "h1", open_years: [2025], pause: { sentence: "PAUSED LONG", scope: "household" }, feeds: [{ warning: "FEED LONG" }] } };
      pagesHouseholdNotices({ level: "household", household: "h1" });
      pagesHouseholdNotices({ level: "household", household: "h1" });
      return { seen, logged };
    """, tmp_path, setup="""
      vocab.household = { two_open_years: "Two years open; sorting paused", accept_folder_name: "Accept the folder's name" };
      vocab.after_install = { wait: "Setup needs attention" };
      const acceptFolderName = () => {};
      const logged = [];
      const window = { tracker: { logError: (text) => logged.push(text) } };
    """, functions=["pagesHouseholdNotices", "shortNotice"])
    assert ran["seen"][0] == [["Setup needs attention", "PAUSED LONG"], ["Setup needs attention", "FEED LONG"]]
    assert ran["logged"] == ["vocab.screen.notices.renamed", "vocab.screen.notices.feed"], "each missing key once, never silent"


#: Every notice the shell draws for a loud failure, over the API's real long sentences.
PROBE_EVERY_NOTICE = """
      const seen = [];
      for (const scenario of ["notices", "household-notices", "locked", "stale-lock"]) {
        const { list, state } = await replies(scenario);
        vocab = list.vocab;
        vocab.screen.notices = Object.assign({}, vocab.screen.notices, %s);
        drawn.length = 0; logged.length = 0;
        renderMachineNotices(list);
        renderAfterInstall(noticeOf(list.after_install));
        renderShortOfRoom([{ engagement: "r1", sentences: ["A LONG ROOM SENTENCE"] }]);
        active = state.paths.engagement;
        showLock(state.lock);
        lastState = state;
        pagesHouseholdNotices({ level: "household", household: state.household.path });
        seen.push({ scenario, drawn: drawn.slice(), logged: logged.slice(), reader: list.reader_warning, machine: list.machine_warnings,
                    pause: state.household.pause.sentence || "", lock: state.lock });
      }
      return seen;
"""


def _every_notice(tmp_path, short_words="{}"):
    return run_notices(PROBE_EVERY_NOTICE % short_words, tmp_path)


def test_no_notice_draws_more_than_five_words_or_a_path_even_over_the_apis_long_sentences(tmp_path):
    """SPEC 11.1 (five words, no path of any kind) and 2.2 E28-E31: the reader's
    warning (it names C:\\JPA App), each machine warning, the pause, the
    feed, the lock's `on` and `greyed` sentences are all long in the API, and
    the harness's stub sends them long. The notices show a short line whatever
    the vocabulary holds; the long sentences go to the error log."""
    ran = _every_notice(tmp_path)
    seen_long = set()
    for one in ran:
        for _key, sentence in one["drawn"]:
            assert len(sentence.split()) <= 5, (one["scenario"], sentence)
            assert not re.search(r"[A-Za-z]:\\|\\|/", sentence), (one["scenario"], sentence)
        drawn = " ".join(sentence for _key, sentence in one["drawn"])
        for long in [one["reader"], *(one["machine"] or []), one["pause"]]:
            if long:
                seen_long.add(long)
                assert long[:30] not in drawn, "the API's long sentence is never drawn"
                assert long in "\n".join(one["logged"]), "and it is in the error log"
    assert len(seen_long) == 4, "the stub sent the reader's, both machine warnings and the pause"
    locked = next(one for one in ran if one["scenario"] == "locked")
    assert [sentence for key, sentence in locked["drawn"] if key == "lock"] == ["In Use on OFFICE-PC"], "only the running line, not `on` or `greyed`"


def test_a_notice_shows_the_vocabularys_short_word_when_it_has_one(tmp_path):
    words = '{ reader: "Install Folder Name Too Long", machine: "Machine Needs Attention", renamed: "Folder Renamed", paused: "Two Years Open; Sorting Paused", feed: "Prior Year Data Not Found" }'
    ran = {one["scenario"]: one for one in _every_notice(tmp_path, words)}
    shown = lambda name: [sentence for _key, sentence in ran[name]["drawn"]]  # noqa: E731
    assert "Install Folder Name Too Long" in shown("notices") and "Machine Needs Attention" in shown("notices")
    assert "Folder Renamed" in shown("household-notices") and "Prior Year Data Not Found" in shown("household-notices")
    assert "Setup Needs Attention" not in shown("notices")[:2], "the fallback is only for a word the vocabulary lacks"


def test_a_notice_falls_back_to_the_setup_line_for_a_word_the_vocabulary_lacks(tmp_path):
    lacking = '{ reader: "", machine: "", renamed: "", paused: "", feed: "" }'
    ran = {one["scenario"]: one for one in _every_notice(tmp_path, lacking)}
    shown = [sentence for _key, sentence in ran["notices"]["drawn"]]
    assert shown[0] == "Setup Needs Attention" and shown[1] == "Setup Needs Attention"


def test_one_item_without_a_group_is_named_in_a_notice_and_every_other_row_is_drawn(tmp_path):
    """SPEC 6, 9.1 and the loud-and-safe rule. An item the API sent without a
    `group` is not guessed at: it is drawn in no group, counted in none and
    named in one notice of its own, its detail going to the error log; every
    other row and group of the return page is drawn, and the page is never
    emptied. Nothing throws out of the draw or the firm's tally."""
    ran = run_pages_dom("""
      const bad = { ...item("X", "waiting"), group: undefined, short_name: "Doc X" };
      lastState = stateOf([item("A", "needs_you", { status_key: "Rejected" }), bad, item("C", "waiting"), item("D", "received", { status_key: "Received" })], [parked("p1")]);
      const box = new Element("div");
      let threw = null;
      try { pagesDraw({ level: "return", ret: "r1", year: 2025 }, box); } catch (err) { threw = err.message; }
      const rows = box.byClass("row-name").map((one) => one.textContent);
      return { threw, titles: box.byClass("group-title").map((one) => one.textContent), rows, h1: box.find((one) => one.tag === "h1").length,
               notices: notices[notices.length - 1], failures, tally: pagesTally(lastState) };
    """, tmp_path)
    assert ran["threw"] is None and ran["failures"] == []
    assert ran["titles"] == ["Needs you", "Waiting on client", "Received"] and ran["h1"] == 1
    assert ran["rows"] == ["p1.pdf", "Doc A", "Doc C", "Doc D"], "every other row is drawn, the one without a group is not"
    assert ran["notices"][0] == "rows" and len(ran["notices"][1]) == 1
    _key, sentence, detail = ran["notices"][1][0]
    assert sentence == "Doc X: The app hit an error", "the notice names the one row in the app's own error sentence"
    assert "Error: group" in detail, "the detail is for the error log"
    assert ran["tally"] == {"needs_you": 2, "waiting": 1, "received": 1, "set_aside": 0}, "counted in no group"


def test_a_row_that_cannot_be_built_is_left_out_and_named_on_every_page(tmp_path):
    """The same rule on the pages that list returns: a reason code the table
    lacks, a stage it lacks, one bad household - the other rows are drawn."""
    ran = run_pages_dom("""
      const rows = [
        { path: "a", household: "h", counts: { needs_you: 0, waiting: 1, received: 0, set_aside: 0 }, oldest: null, due: null, draft: { ready: true, stage: 1, held: 0, drafted: null }, problem: "" },
        { path: "b", household: "h", counts: { needs_you: 0, waiting: 1, received: 0, set_aside: 0 }, oldest: null, due: null, draft: { ready: true, stage: 9, held: 0, drafted: null }, problem: "" } ];
      shellReturn = (path) => ({ return_name: path === "a" ? "Alpha" : "Bravo", household: "h", year: 2025 });
      vocab.reminder = { stages: [{ number: 1, short: "Heads up" }] };
      pagesBroken = [];
      const specs = pagesReminderSpecs(rows);
      return { specs: specs.map((one) => [one.name, one.status]), broken: pagesBroken.map((one) => one.name) };
    """, tmp_path, functions=["pagesReminderSpecs", "pagesStage", "pagesSafe", "pagesEach", "pagesLabel", "pagesSafeName", "pagesReturnName",
                              "pagesByName", "pagesDay", "screenWords", "pagesLinkWords", "pagesTaxpayer", "pagesReturnCells"])
    assert ran["specs"] == [["Alpha", "Heads up"]] and ran["broken"] == ["Bravo"]


def test_a_page_that_cannot_be_built_whole_keeps_what_it_held_or_draws_its_frame(tmp_path):
    """SPEC 6, failed read: with something drawn the page keeps it (and its
    rows' tokens); with nothing drawn it draws its frame, the H1. Never
    nothing at all, and the failure is said."""
    ran = run_pages_dom("""
      lastState = stateOf([item("A", "needs_you"), item("C", "waiting")]);
      const route = { level: "return", ret: "r1", year: 2025 };
      const box = new Element("div");
      pagesDraw(route, box);
      const first = box.kids.slice(); const tokens = pagesTokens.size;
      const review = vocab.review_labels; vocab.review_labels = null;      // pagesReturnGroups now throws
      pagesDraw(route, box);
      const kept = box.kids.length === first.length && box.kids.every((one, i) => one === first[i]);
      const afterKept = pagesTokens.size;
      const fresh = new Element("div"); pagesDrawn = "";
      pagesDraw(route, fresh);
      vocab.review_labels = review;
      return { kept, tokens, afterKept, frame: fresh.kids.map((one) => one.tag), failures: failures.length };
    """, tmp_path)
    assert ran["kept"] and ran["afterKept"] == ran["tokens"] > 0
    assert ran["frame"] == ["h1"] and ran["failures"] == 2


def test_an_error_after_the_state_arrives_never_reaches_the_write_that_brought_it(tmp_path):
    """A write whose reply is a state has succeeded; an error of the page's
    own while drawing it is said as an error of the page and is not thrown
    back to the write, which would call the write failed."""
    probe = """
      shellDraw = () => { throw new Error("draw"); };
      let threw = null;
      try { shellStateArrived({ paths: { engagement: "r1" }, items: [] }); } catch (err) { threw = err.message; }
      shellDraw = () => {};
      pagesTally = () => { throw new Error("tally"); };
      try { shellStateArrived({ paths: { engagement: "r1" }, items: [] }); } catch (err) { threw = err.message; }
      return [threw, said];
    """
    setup = """
      const said = []; const failed = (err) => said.push(err.message);
      let shellDraw = null; let pagesTally = null; const sheetStateArrived = () => {};
      const shellFirmNow = { data: { return_counts: [{ path: "r1", counts: {} }] } };
      const shellLoadFirm = () => {};
      const shellFirmSentAt = 0; const shellWroteAt = 0; const shellFirmHeld = new Map();
      const shellRoute = { level: "return" }; const shellPageBusy = false; const FIRM_LEVELS = ["overview"]; const shellChanged = () => {};
    """
    assert run_shell(["shellStateArrived", "shellPageReadsState", "shellCountsDiffer"], setup, probe, tmp_path) == [None, ["draw", "tally"]]


def test_the_year_page_leaves_a_gap_under_its_h1_before_its_rows(tmp_path):
    """The mock-up (3.6): a list starts --sp-6 below what precedes it."""
    ran = run_pages_dom("""
      const hh = { name: "Smith Family", returns: [{ path: "r1", year: 2025, return_name: "1040 - John & Jane Smith", active: true }] };
      shellHousehold = () => hh;
      globalThis.shellRoute = { household: "h1" };
      const nodes = pagesYear({ level: "year", household: "h1", year: 2025 });
      return nodes.map((one) => `${one.tag}.${one.className.split(" ")[0]}`);
    """, tmp_path, setup="const shellFirm = () => ({ data: null });")
    assert ran == ["h1.page-title", "div.page-gap", "div.returns-list"]
    css = read("shell.css")
    assert "height: var(--sp-6)" in next(body for _m, selector, body in blocks(css) if selector.strip() == ".page-gap")


def test_the_set_aside_fold_is_shut_each_time_the_page_opens(tmp_path):
    ran = run_pages_dom("""
      lastState = stateOf([item("A", "set_aside", { status_key: "NotAsked" })]);
      shellHousehold = () => ({ name: "Smith Family", returns: [] });
      const route = { level: "return", ret: "r1", year: 2025 };
      const box = new Element("div");
      const fold = () => box.find((one) => one.tag === "details")[0];
      pagesDraw(route, box);
      const shut = fold().open;
      fold().open = true; fold().handlers.toggle[0]();
      pagesDraw(route, box);
      const kept = fold().open;
      pagesDraw({ level: "year", household: "h1", year: 2025 }, box);
      pagesDraw(route, box);
      return [shut, kept, fold().open];
    """, tmp_path, setup="const shellFirm = () => ({ data: null });")
    assert ran == [False, True, False], "kept across a redraw of the same page, shut when the page is opened again"


def test_a_household_with_an_unreadable_return_is_never_complete_on_the_clients_page(tmp_path):
    """The engine groups the firm's returns by household once and says each
    household's counts and its first return that could not be read; the window
    words them. Only a household with nothing wrong says Complete."""
    ran = run_pages_dom("""
      households = [{ name: "Alpha Family", path: "a" }, { name: "Bravo Family", path: "b" }, { name: "Charlie Family", path: "c" }];
      const make = (household, counts, problem = "") => ({ path: household, household, counts: { needs_you: 0, waiting: 0, received: 0, set_aside: 0, ...counts }, problem,
        files: 0, oldest: null, due: null, draft: { ready: false, stage: 0, held: 0, drafted: null } });
      shellFirmData = { returns: [make("Alpha Family", {}, "Could Not Be Read"), make("Bravo Family", { needs_you: 2 }), make("Charlie Family", {})],
                        files: [], paths: {}, totals: {}, next_sort: null };
      const say = (all) => { pagesClientsAll = all; settle("clients"); return pagesClientSpecs(heldRows("clients")).map((one) => [one.name, one.status, one.tone]); };
      return { work: say(false), all: say(true) };
    """, tmp_path, setup=ENGINE_BRIDGE)
    assert ran["work"] == [["Alpha Family", "Could Not Be Read", "needs"], ["Bravo Family", "2 need you", "needs"]]
    assert ran["all"][2] == ["Charlie Family", "Complete", "done"], "only a household with nothing wrong says Complete"


def test_the_renderer_defines_none_of_the_names_section_13_removes():
    """SPEC 13 and 14.3: the review deck (Cards/List, its stored key and its
    markup) and the old screen's helpers are gone from every renderer file;
    putting one back must fail here, not pass the whole affected set."""
    removed = ("chip", "sideLine", "requestTableRow", "ruleTooltip", "renderEngagements", "returnReminderLine", "renderSharing", "banner",
               "REVIEW_MODE_KEY", "REVIEW_MODE", "storedReviewMode", "setReviewMode", "applyReviewMode", "deckOrder", "renderDeck",
               "deckCard", "acceptCard", "openCardInList", "skipCard", "SCAN_LABEL", "LOCKED_BUTTONS")
    for name in [*SHELL_FILES, "app.js", "tooltip.js"]:
        text = stripped_js(name)
        for one in removed:
            assert not re.search(rf"\b(?:function|const|let|var|class)\s+{one}\b", text), f"{name} defines {one}"
        for one in ("review-deck", "review-mode", "mode-toggle", "reviewMode", "review_mode"):
            assert one not in text, f"{name} mentions {one}"
    for name in ("style.css", "pilot-ui.css", "shell.css"):
        css = read(name)
        assert ".mode-toggle" not in css and ".deck" not in css and "--radius-pill" not in css, name
    assert ".chip" not in read("shell.css")


def test_every_loud_failure_of_the_old_screen_reaches_a_notice():
    """SPEC 2.2: each failure the old screen kept in a banner or a card is a
    notice now, and the call that draws it is still made: the reader's warning
    and the machine warnings, the after-install failure, folders skipped,
    names shortened to fit, the lock, two years open / folder renamed / feeds.
    Dropping the call (which the drawing tests cannot see) fails here."""
    app = stripped_js("app.js")

    def body(text, name):
        start = text.index(f"function {name}(")
        return text[start:text.index("\n}\n", start)]

    assert "renderMachineNotices(listed);" in body(app, "loadEngagements")
    assert "renderAfterInstall(listed.after_install);" in body(app, "loadEngagements")
    assert "renderMisfits();" in body(app, "adoptList")
    assert "renderShortOfRoom(result.short_of_room || []);" in body(app, "saveRoot")
    assert "renderAfterInstall(noticeOf(result.after_install));" in body(app, "saveRoot")
    assert "showLock(state.lock);" in body(app, "renderLock") and "renderLock(state);" in body(app, "render")
    assert 'keyedNotice("reader"' in body(app, "renderMachineNotices") and 'syncNotices("machine"' in body(app, "renderMachineNotices")
    assert 'keyedNotice("after-install"' in body(app, "renderAfterInstall")
    assert 'keyedNotice("misfits"' in body(app, "renderMisfits")
    assert 'keyedNotice("room"' in body(app, "renderShortOfRoom")
    assert 'keyedNotice("lock"' in body(app, "showLock")
    pages = stripped_js("pages.js")
    assert "pagesHouseholdNotices(route);" in body(pages, "pagesDraw") and 'syncNotices("household"' in body(pages, "pagesHouseholdNotices")
    shell = stripped_js("shell.js")
    assert "firm_failed" in shell


def test_no_page_draws_a_path_as_text_or_as_a_tooltip(tmp_path):
    """SPEC 11.1 (no path of any kind) and P63. Every page is drawn from data
    whose paths hold backslashes and slashes - a household's folder, a
    return's folder, one the list does not know - and nothing drawn holds
    either: not a row, a heading, a caption, an attribute or a tooltip."""
    pages_text = read("pages.js")
    functions = re.findall(r"^function (\w+)\(", pages_text, flags=re.M) + ["h", "icon", "screenWords", "folderName"]
    ran = run_pages_dom(r"""
      const clients = "C:\\Clients\\J Park & Associates\\Smith Family";
      const known = clients + "\\2025\\1040 - John & Jane Smith";
      const gone = "/srv/clients/J Park & Associates/Gone Family/2025/1040 - Gone Trust";
      shellReturn = (path) => (path === known ? { return_name: "1040 - John & Jane Smith", household: "Smith Family", year: 2025 } : null);
      const hh = { name: "Smith Family", path: clients, contact: "Jane Smith", returns: [{ path: known, return_name: "1040 - John & Jane Smith", label: "x", year: 2025, active: true }] };
      shellHousehold = (path) => (path === clients ? hh : null);
      households = [{ name: "Smith Family", path: clients }, { name: "Gone Family", path: "/srv/clients/Gone Family" }];
      const counts = (n, w) => ({ needs_you: n, waiting: w, received: 1, set_aside: 0 });
      shellFirmData = { returns: [
        { path: known, household: "Smith Family", counts: counts(2, 1), files: 1, oldest: "2026-03-03", due: "2026-04-15", draft: { ready: true, stage: 1, held: 0, drafted: "2026-03-03" }, problem: "" },
        { path: gone, household: "Gone Family", counts: counts(0, 0), files: 0, oldest: null, due: null, draft: { ready: true, stage: 1, held: 2, drafted: null }, problem: "Could Not Be Read" } ],
        files: [{ return: known, year: 2025, name: "scan0012.pdf", handle: "h1", code: "unmatched", received: "2026-03-03", suggestion: "W-2 - Acme", open_key: "" },
                { return: gone, year: 2025, name: "IMG_1.jpg", handle: "h2", code: "unmatched", received: "2026-03-04", suggestion: "", open_key: "" }],
        paths: {}, totals: { need: 2, waiting: 0, complete: 0, files: 2, drafts: 2 }, next_sort: "18:00" };
      settle("overview", "needs_review", "reminders", "clients");
      lastState = stateOf([item("A", "needs_you"), item("C", "waiting")], [parked("p1")]);
      lastState.paths.engagement = known;
      lastState.household = { path: clients, shared_on: "2026-02-01", open_years: [2025], pause: {}, feeds: [] };
      const routes = [{ level: "overview" }, { level: "needs-review" }, { level: "reminders" }, { level: "clients" },
                      { level: "household", household: clients }, { level: "year", household: clients, year: 2025 },
                      { level: "return", household: clients, year: 2025, ret: known }];
      const seen = []; const drawnBy = {};
      const walk = (node, out) => {
        for (const [key, value] of Object.entries(node.attrs || {})) out.push(`${key}=${value}`);
        for (const [key, value] of Object.entries(node.dataset || {})) out.push(`${key}=${value}`);
        for (const kid of node.kids || []) { if (kid.data !== undefined) out.push(kid.data); else walk(kid, out); }
      };
      for (const route of routes) {
        pagesBroken = []; pagesUid = 0; pagesTokens.clear(); globalThis.shellRoute = route;
        const box = new Element("div");
        box.append(...pagesBuild(route).filter(Boolean));
        const out = []; walk(box, out);
        drawnBy[route.level] = { strings: out.length, broken: pagesBroken.map((one) => one.name) };
        seen.push(...out.map((text) => [route.level, text]));
      }
      for (const [cls, words] of tips) if (words) seen.push(["tip", words]);
      return { drawnBy, hits: seen.filter(([, text]) => /[\\/]/.test(text)), all: seen.map(([, text]) => text) };
    """, tmp_path, setup=ENGINE_BRIDGE + """
      const openNewHousehold = () => {}; const openAddReturn = () => {};
      Object.assign(vocab.screen, {
        figures: { need: "Need a person", waiting: "Waiting on clients", complete: "Complete" }, work: "Work waiting",
        sections: { reminders: "Reminders", clients: "Clients" }, filters: { work: "Work waiting", all: "All" }, held: "Held",
        inactive: "Inactive", rolled: "Rolled forward", shared: "Shared", not_shared: "Not shared",
        household_card: { contact: "Contact", shared_with: "Shared with", inbox_link: "Inbox link", link_saved: "Saved", no_link: "Not saved" },
        empty: { overview: "Nothing is waiting", next_sort: "Next sort {time}", needs_review: "Nothing needs review", reminders: "No drafts ready",
                 clients: "No clients yet", work: "No work waiting", returns: "No returns yet", received: "Nothing received yet" },
      });
      vocab.menu = { new_household: "New household", add_return: "Add a return" };
      vocab.reminder = { stages: [{ number: 1, short: "Heads up" }] };
    """, functions=functions)
    assert ran["hits"] == [], "a path (or a slash) was drawn"
    assert all(one["broken"] == [] and one["strings"] > 3 for one in ran["drawnBy"].values()), json.dumps(ran["drawnBy"])
    for name in ("1040 - John & Jane Smith", "1040 - Gone Trust", "Smith Family", "scan0012.pdf"):
        assert name in ran["all"], f"{name} was not drawn, so the check saw nothing"


def test_a_moved_file_marked_missing_is_set_aside_and_the_tally_equals_the_firms_counts(tmp_path):
    """The engine's `index[].group` decides where a file counts (SPEC 9.1): a
    moved file a person marked missing is Set aside, so the return page draws
    it under Set aside, and the page's tally equals the firm's counts (which
    the engine makes from the same groups) - otherwise the tally is one lower
    and the whole firm reply is read again each time the return opens."""
    ran = run_pages_dom("""
      const state = stateOf([item("A", "needs_you"), item("B", "waiting"), item("E", "set_aside", { status_key: "NotAsked" })],
        [parked("p1"), movedRow("m1"), setAsideRow("d1"), movedRow("lost", { group: "set_aside", received: "2026-02-20" }),
         { handle: "f1", original_name: "filed.pdf", decision: "Filed", group: "received", identifier: "B", answered: [], received: "2026-03-01" }],
        [{ handle: "m1", original_name: "m1.pdf", identifier: "A" }]);
      // what the engine's firm counts hold for this return: items by group, parked and moved-by-hand files in
      // Needs you, files set aside or marked missing in Set aside, filed files in no group of their own.
      const firmCounts = { needs_you: 1 + 1 + 1, waiting: 1, received: 0, set_aside: 1 + 1 + 1 };
      lastState = state;
      const groups = pagesReturnGroups(state, 2025);
      const box = page(pagesReturn({ level: "return", ret: "r1", year: 2025 }));
      return { tally: pagesTally(state), firmCounts, setAside: groups.set_aside.map((one) => [one.name, one.status, one.step ? one.step.kind : null]),
               drawn: Object.fromEntries(Object.entries(groups).map(([key, rows]) => [key, rows.length])), titles: box.byClass("group-title").map((one) => one.textContent),
               broken: pagesBroken.length };
    """, tmp_path)
    assert ran["tally"] == ran["firmCounts"], "one lower than the firm's would re-read the firm each time the return opens"
    assert ran["drawn"] == ran["tally"], "what is drawn and what is counted cannot disagree"
    assert ["lost.pdf", "Moved by hand", None] in ran["setAside"], "a moved file marked missing sits in Set aside, with no step (it has no copy to check)"
    assert ["d1.pdf", "Not requested", "check"] in ran["setAside"] and "Set aside" in ran["titles"] and ran["broken"] == 0


def test_a_file_without_a_group_is_named_and_not_counted(tmp_path):
    ran = run_pages_dom("""
      const bare = { ...parked("p2"), group: undefined };
      const state = stateOf([item("A", "needs_you")], [parked("p1"), bare]);
      const groups = pagesReturnGroups(state, 2025);
      return { names: groups.needs_you.map((one) => one.name), broken: pagesBroken.map((one) => one.name), tally: pagesTally(state) };
    """, tmp_path)
    assert ran["names"] == ["p1.pdf", "Doc A"] and ran["broken"] == ["p2.pdf"] and ran["tally"]["needs_you"] == 2


# ── S5: the links, the side sheet, the right-click menus and the dialogs ───────

#: Jason's ruling 10 as a function (S8a's, tests/test_api.py): capitalise every word but the small ones
#: when they are neither first nor last; each part of a hyphenated word; the word after a colon or semicolon;
#: placeholders, numbers and ALL-CAPS tokens are left alone.
_SMALL = {"a", "an", "the", "and", "but", "or", "nor", "for", "of", "on", "in", "to", "by", "at", "as", "up", "vs"}


def title_case_ok(phrase: str) -> bool:
    words = phrase.split()
    for i, word in enumerate(words):
        core = re.sub(r"^[^\w{]+|[^\w}]+$", "", word)
        if not core or core.startswith("{") or core.isdigit() or (core.isupper() and len(core) > 1):
            continue
        first_or_last = i in (0, len(words) - 1)
        after_colon = i > 0 and words[i - 1].rstrip().endswith((":", ";"))
        parts = core.split("-")
        if core.lower() in _SMALL and not first_or_last and not after_colon:
            if core != core.lower():
                return False
            continue
        if any(part[:1].isalpha() and not part[:1].isupper() for part in parts):
            return False
    return True


def test_the_title_case_rule_says_what_ruling_10_says():
    for good in ("Needs Review", "Waiting on Taxpayer", "Add a Return…", "Taxpayer (Greeting Name)", "Not Opened; It Has Changed", "Belongs To…", "Due Date (Optional)"):
        assert title_case_ok(good), good
    for bad in ("Needs review", "Waiting On Taxpayer", "Add A Return", "Due date (optional)", "Look again"):
        assert not title_case_ok(bad), bad


def test_every_phrase_the_page_and_the_dialogs_draw_from_index_html_and_app_js_is_in_title_case():
    """Ruling 10 (SPEC 11.1): the renderer's own literals - a label, a
    heading, an aria-label, a placeholder - are Title Case. The words that
    come from the API are S8a's; these are the ones the renderer types."""
    html = re.sub(r"<!--.*?-->", "", read("index.html"), flags=re.S)
    html = re.sub(r"<script.*?</script>|<style.*?</style>", "", html, flags=re.S)
    texts = [t.strip() for t in re.findall(r">([^<>]+)<", html) if len(t.split()) >= 2]
    texts += [a for a in re.findall(r'(?:aria-label|placeholder)="([^"]+)"', html) if len(a.split()) >= 2]
    assert len(texts) >= 6, texts
    for phrase in texts:
        assert title_case_ok(phrase), phrase
    app = stripped_js("app.js")
    assert 'const BELONGS_TO = "Belongs To…";' in app and title_case_ok("Belongs To…")
    assert "Belongs to" not in app


def test_the_editor_has_one_advanced_switch_and_no_per_row_routing_toggle(tmp_path):
    """SPEC 2.7 E91: one Advanced switch replaces the per-row routing
    toggles and the show-every-fold button; it shows every row's routing
    rules, the taught keywords, and the paste and rename blocks. A row
    typed or pasted since the editor opened is open regardless, and a
    refused save turns the switch on."""
    app = stripped_js("app.js")
    assert "ed-fold" not in app and "editorFolds" not in app and "routing_all" not in app and not re.search(r"vocab\.editor\.routing(?!_)", app)
    assert app.count('className: "btn btn-small ed-advanced"') == 1 and 'shellWords("editor.advanced")' in app
    html = read("index.html")
    body = html[html.index('<div id="ed-advanced-body" class="hidden">'):html.index('<div id="ed-note"')]
    assert 'id="ed-paste"' in body and 'id="ed-rename-btn"' in body, "paste and rename sit behind the switch"
    ran = run_shell(["editorRowFoldOpen", "editorRowItem", "setAdvanced", "showEveryFold"], """
      let editorAdvanced = false; let editorState = { items: [{ identifier: "A01" }] }; let drawn = 0;
      const renderEditorRows = () => { drawn += 1; };
    """, """
      const known = { identifier: "A01" }; const typed = { identifier: "Z99" };
      const out = { off: [editorRowFoldOpen(known), editorRowFoldOpen(typed)] };
      setAdvanced(true); out.on = editorRowFoldOpen(known);
      setAdvanced(false); out.offAgain = editorRowFoldOpen(known);
      showEveryFold(); out.refused = editorRowFoldOpen(known); out.drawn = drawn;
      return out;
    """, tmp_path, source="app.js")
    assert ran == {"off": [False, True], "on": True, "offAgain": False, "refused": True, "drawn": 3}


def test_the_wizard_keeps_the_first_steps_cancel_only_and_esc_and_the_scrim_still_close_it():
    """SPEC 2.7 E88-E90: step 1 keeps Cancel; the form step and the requests
    step have none (step 3 keeps Back). Escape and the scrim close the one
    `#modal` at every step."""
    html = read("index.html")
    modal = html[html.index('<div id="modal"'):html.index('id="ne-create"') + 40]
    assert modal.count(">Cancel</button>") == 1 and 'id="wh-cancel"' in modal
    app = stripped_js("app.js")
    assert "wf-cancel" not in html + app and "ne-cancel" not in html + app
    assert re.search(r"^\s*modal: \{", app, flags=re.M), "the wizard is still in the dialog registry, so Escape and the scrim close it"


def test_no_toast_types_a_sentence_and_the_words_it_asks_for_are_five_title_case_words_in_the_vocabulary():
    """F6: a toast is the API's word. The renderer types none (no string
    literal in a `toast(` call), and every key `toastWord` is given is in
    vocab.screen.notices as at most five words in Title Case."""
    for name in ("app.js", "pages.js", "shell.js", "sheet.js"):
        text = stripped_js(name)
        assert not re.search(r"\btoast\(\s*[\"'`]", text), f"{name} types a toast"
    notices = api._vocab()["screen"]["notices"]
    keys = set(re.findall(r"toastWord\(\"(\w+)\"\)", stripped_js("app.js")))
    assert keys == {"pick_request", "name_requests"}, keys
    for key in keys | {"no_log"}:
        assert len(notices[key].split()) <= 5 and title_case_ok(notices[key]), key
    assert "toast(said)" in js_function("toastWord", "app.js") and "failed(new Error(" in js_function("toastWord", "app.js")


def test_the_side_sheet_is_a_modal_in_the_one_dialog_registry_and_hides_by_its_attribute():
    """SPEC 7: it joins the dialog stack (focus in, Tab kept, Esc), hides by
    its `hidden` attribute, and gives the scrim and the row back when shut;
    the click on its scrim is the one way behind it."""
    app = read("app.js")
    sheet = read("sheet.js")
    assert 'sheet: { model: null, attr: true, first: () => $("sheet-title"), closed: () => sheetClosed() },' in app
    assert 'openDialog("sheet");' in sheet and "closeDialog(\"sheet\")" in sheet
    assert 'if (id === "sheet") continue;' in app, "the scrim, not the sheet's own box, is the click behind it"
    assert '$("sheet-scrim").addEventListener("click", () => requestClose("sheet"));' in sheet
    closing = js_function("sheetClosed", "sheet.js")
    assert '$("sheet-scrim").hidden = true;' in closing and "pagesFocusAt(now.opener)" in closing and "appRouteChanged(shellRoute)" in closing
    html = read("index.html")
    assert re.search(r'<aside id="sheet" role="dialog" aria-modal="true" aria-labelledby="sheet-title" hidden>', html)


def test_the_cards_the_sheet_and_the_dialogs_took_are_gone_from_the_renderer_and_its_stylesheets():
    """SPEC 13: the moved, review and filed cards, the reminder card, the
    roll fold and the assurances footer are gone with the functions that
    drew them and the rules that styled them."""
    for name in ("app.js", "pages.js", "shell.js", "sheet.js"):
        text = stripped_js(name)
        for one in ("renderMoved", "renderReview", "renderUnfileList", "reviewMoved", "cameFrom", "openCopy", "renderHousehold"):
            assert not re.search(rf"\bfunction {one}\b", text), f"{name} still defines {one}"
        for ident in ("moved-card", "review-card", "filed-card", "reminder-card", "dismissed-card", "household-roll", "assurances",
                      "moved-list", "review-list", "filed-list", "dismissed-list", "btn-open-draft", "reminder-hint", "reminder-heading"):
            assert ident not in text, f"{name} mentions {ident}"
    for name in ("style.css", "pilot-ui.css", "shell.css"):
        css = read(name)
        for gone in (".review", ".dismissed", ".assure", ".reminder-body", ".rem-hint", ".rem-actions", ".rem-quiet", "#reminder-card", "#moved-list"):
            assert gone not in css, f"{name} still styles {gone}"


def test_the_dialogs_help_lines_are_cut():
    """SPEC 2.7 and the audit (E84-E91): no help paragraph or help tooltip
    in the household, schedule, Add a return / New household and editor
    dialogs; the warnings before a risky act stay."""
    html = read("index.html")
    for ident in ("hh-edit-note", "hh-edit-feeds-help", "household-new-intro", "form-note", "tmpl-note", "wp-help", "ep-help", "sc-note",
                  "ed-paste-hint", "ed-rename-hint", "chosen-form", "ed-list-title", "hh-new-head"):
        assert f'id="{ident}"' not in html, ident
    app = stripped_js("app.js")
    for key in ("members_help", "feeds_help", "contact_help", "link_help", "return_name_help", "year_note", "new_intro", "form_step_note",
                "paste_hint", "rename_hint", "routing_help", "ask_the_client_note", "keyword_help", "spellings_help"):
        assert key not in app, key
    assert "words.note" not in app and "words.loading" not in app and "column.help" not in app and "c.help" not in app
    # what stays: the sharing warning, the feed warning, the Active warning
    for kept in ("return_warning", "feed_warning", "${f.label} — ${f.help}"):
        assert kept in app, kept
    assert "templateSummary" not in app and 'className: "tmpl-id"' not in app and 'CUSTOM_COLUMNS = ["document"]' in app


def test_no_sheet_or_dialog_draws_the_sharing_checklist_or_a_path():
    """SPEC 2.4 E45: the household's sharing checklist names folders by their
    paths, and a path is never drawn; the create reply's lines are not put on
    the screen."""
    app = stripped_js("app.js")
    creating = app[app.index("async function createEngagement() {"):]
    creating = creating[:creating.index("\n}\n")]
    assert "checklist.lines" not in creating and "checklist.heading" not in creating and "checklist.note" not in creating


def test_the_link_kinds_are_built_from_the_apis_keys_and_navigate_without_the_engine(tmp_path):
    """SPEC 3.9: a file name is a link when its row names a key (state's
    `shown_key`, `open_key`, `open_keys[0]`), its path looked up in the map
    it came with and never drawn; a household or return name navigates; text
    where there is no key."""
    ran = run_pages_dom("""
      const paths = { engagement: "r1", "shown_copy a": "/secret/a.pdf", "moved_copy m": "/secret/m.pdf", "filed_copy f 0": "/secret/f.pdf" };
      const state = stateOf([item("R", "received", { status_key: "Received" }), item("M", "received", { status_key: "Received" }),
         item("N", "received", { status_key: "Received" }), item("Y", "received", { status_key: "Received" })],
        [parked("a", { shown_key: "shown_copy a" }), parked("b", { shown_key: "" }), setAsideRow("d", { shown_key: "shown_copy a" }),
         { handle: "f", original_name: "f.pdf", decision: "Filed", group: "received", identifier: "R", filed_names: ["f.pdf"], open_keys: ["filed_copy f 0"], answered: [] },
         { handle: "g1", original_name: "g1.pdf", decision: "Filed", group: "received", identifier: "M", filed_names: ["g1.pdf"], open_keys: ["filed_copy g1 0"], answered: [] },
         { handle: "g2", original_name: "g2.pdf", decision: "Filed", group: "received", identifier: "M", filed_names: ["g2.pdf"], open_keys: ["filed_copy g2 0"], answered: [] },
         { handle: "n", original_name: "n.pdf", decision: "Filed", group: "received", identifier: "N", filed_names: ["n.pdf", "n2.pdf"], open_keys: ["filed_copy n 0", "filed_copy n 1"], answered: [] },
         { handle: "s", original_name: "s.pdf", decision: "Filed", group: "received", identifier: "X", filed_names: ["s.pdf"], open_keys: ["filed_copy s 0"], answered: ["Y"] }],
        [{ handle: "m", original_name: "m.pdf", in_request: "", identifier: "", open_key: "moved_copy m" }]);
      state.paths = paths;
      const groups = pagesReturnGroups(state, 2025);
      const link = (spec) => (spec.nameLink ? [spec.nameLink.kind, spec.nameLink.key] : null);
      // Everything the rows draw - text, attributes, data, tips - holds no path.
      const strings = [];
      const walk = (node) => { for (const v of Object.values(node.attrs || {})) strings.push(v); for (const v of Object.values(node.dataset || {})) strings.push(String(v));
        for (const kid of node.kids || []) { if (kid.data !== undefined) strings.push(kid.data); else walk(kid); } };
      tips.length = 0;
      for (const spec of [...groups.needs_you, ...groups.set_aside, ...groups.received]) walk(pagesRow(spec));
      for (const [, words] of tips) if (words) strings.push(words);
      const drawn = strings.some((text) => text.includes("/secret"));
      return {
        strings: strings.length,
        parked: groups.needs_you.filter((s) => s.menu === "file").map((s) => [s.name, link(s)]),
        moved: groups.needs_you.filter((s) => s.menu === "moved").map((s) => [s.name, link(s)]),
        aside: groups.set_aside.map((s) => [s.name, link(s)]),
        received: groups.received.filter((s) => !s.child).map((s) => [s.detail, s.detailLink ? s.detailLink.key : null]),
        unfile: groups.received.filter((s) => !s.child).map((s) => [s.name, s.unfile ? s.unfile.original : null]),
        children: groups.received.filter((s) => s.child).map((s) => [s.name, s.menu, s.nameLink ? s.nameLink.key : null, s.unfile ? s.unfile.original : null, s.unfile ? s.unfile.name : null, s.missing]),
        pathInASpec: drawn,
        resolved: [pagesPathOf(paths, "shown_copy a"), pagesPathOf(paths, "nope"), pagesPathOf({ k: { path: "/x/y", kind: "reveal" } }, "k"), pagesPathOf(null, "k")],
      };
    """, tmp_path)
    assert ran["parked"] == [["a.pdf", ["file", "shown_copy a"]], ["b.pdf", None]]
    assert ran["moved"] == [["m.pdf", ["file", "moved_copy m"]]]
    assert ran["aside"] == [["d.pdf", ["file", "shown_copy a"]]]
    assert ran["received"] == [["f.pdf", "filed_copy f 0"], ["2 files", None], ["n.pdf", "filed_copy n 0"], ["s.pdf", None]], (
        "a count is not a name, so it is not a link; one original filed under two requests (decision 94) links the "
        "first copy, prepared_location, which is the one under its own request; a statement that answers a request "
        "without a copy of its own links nothing there")
    assert ran["unfile"] == [["Doc R", "f"], ["Doc M", None], ["Doc N", "n"], ["Doc Y", None]], "Unfile is offered on the request only for the one original filed under it"
    assert ran["children"] == [["g1.pdf", "received", "filed_copy g1 0", "g1", "g1.pdf", None], ["g2.pdf", "received", "filed_copy g2 0", "g2", "g2.pdf", None]], (
        "ruling 17: a request answered by several files gets one row per file, each with its own link (open_keys[0]) and its own Unfile")
    assert ran["strings"] > 20 and ran["pathInASpec"] is False, "a spec holds the key and the map it came with; nothing it draws holds the path"
    assert ran["resolved"] == ["/secret/a.pdf", "", "/x/y", ""], "a string, or {path, kind}; a missing key or map is no path"


def test_running_a_link_reveals_a_file_and_only_navigates_for_a_household_or_a_return(tmp_path):
    ran = run_pages_dom("""
      shellReturn = (path) => ({ return_name: "1120-S - Rivera Design LLC", household: "hh", year: 2025 });
      pagesRunLink({ kind: "file", key: "k1", paths: { k1: "/abs/one.pdf" } });
      pagesRunLink({ kind: "file", key: "missing", paths: {} });
      pagesRunLink({ kind: "household", path: "hh" });
      pagesRunLink({ kind: "return", path: "r9" });
      return { opened, went, failures, words: ["file", "household", "return"].map(pagesLinkWords) };
    """, tmp_path)
    assert ran["opened"] == [["/abs/one.pdf", "reveal"]], "File Explorer opens for a file name alone, with the reveal option"
    assert ran["went"] == [{"level": "household", "household": "hh"},
                           {"level": "return", "household": "hh", "year": 2025, "ret": "r9"}]
    assert ran["failures"] == ["unanswered show_in_explorer"], "a key with no path says so, loudly"
    assert ran["words"] == ["Show in File Explorer", "Navigate to Household", "Navigate to Return"]


def test_the_taxpayer_is_the_name_without_its_recorded_form_and_never_a_guess(tmp_path):
    """P194, P195: a return's Taxpayer is its name less the "{form} - " the
    naming pattern puts first, only when the record's form is what it begins
    with (a hyphen in the form number and letter case are not differences);
    a return with no recorded form, or a name typed another way, is shown
    whole; a vocabulary without the pattern is a loud failure."""
    ran = run_pages_dom("""
      const out = [pagesTaxpayer("1040 - Chidi & Ada Okafor", "1040"), pagesTaxpayer("1120-S - Rivera Design LLC", "1120S"),
                   pagesTaxpayer("1040 - Gone", ""), pagesTaxpayer("Okafor 1040", "1040"), pagesTaxpayer("1065 - Bravo", "1040"),
                   pagesTaxpayer("1040 - ", "1040"), pagesTaxpayer("990 - Friends - of the Park", "990")];
      vocab.layout = {};
      let loud = "";
      try { pagesTaxpayer("1040 - A", "1040"); } catch (err) { loud = err.message; }
      return { out, loud };
    """, tmp_path)
    assert ran["out"] == ["Chidi & Ada Okafor", "Rivera Design LLC", "1040 - Gone", "Okafor 1040", "1065 - Bravo", "1040 - ", "Friends - of the Park"]
    assert ran["loud"] == "layout.return_name_pattern"


def test_the_firm_pages_rows_link_by_the_firms_keys_and_carry_the_year(tmp_path):
    """Ruling 15: a file name on the Needs Review page is a link from
    `files[].open_key` through the firm reply's `paths`, text when the key
    is empty; a group heading is a return link with its year and its
    caption a household link; Overview and Reminders rows link both."""
    ran = run_pages_dom("""
      const known = "/c/Smith/2025/1040 - Smith";
      vocab.reminder = { stages: [{ number: 1, short: "Heads Up" }] };
      shellReturn = (path) => ({ return_name: "1040 - Smith", household: "/c/Smith", year: 2025 });
      households = [{ name: "Smith Family", path: "/c/Smith" }];
      const firmData = { paths: { "shown_copy h1": "/abs/h1.pdf" }, returns: [
        { path: known, household: "Smith Family", year: 2025, form: "1040", label: "Smith Family 2025 1040 - Smith", counts: { needs_you: 2, waiting: 0, received: 0, set_aside: 0 }, oldest: "2026-03-03", due: null,
          draft: { ready: true, stage: 1, held: 0, drafted: "2026-03-03" }, problem: "" }],
        files: [{ return: known, year: 2025, name: "one.pdf", handle: "h1", code: "unmatched", received: "2026-03-03", suggestion: "", open_key: "shown_copy h1" },
                { return: known, year: 2025, name: "two.exe", handle: "h2", code: "opened-not-across", received: "2026-03-04", suggestion: "", open_key: "" }],
        totals: {}, next_sort: null };
      shellFirmData = firmData;
      settle("needs_review", "overview", "reminders");
      tips.length = 0;
      const nodes = pagesNeedsReview();
      const statusTips = tips.filter(([cls]) => cls.startsWith("row-status") || cls === "pill-word").map(([, words]) => words);
      const head = nodes.find((n) => n.byClass && n.byClass("group-title").length).byClass("group-title")[0];
      const caption = nodes.find((n) => n.byClass && n.byClass("group-count").length).byClass("group-count")[0];
      const rows = nodes.flatMap((n) => (n.byClass ? n.byClass("row") : []));
      pagesBroken = [];
      const overview = pagesWorkRows(heldRows("overview"))[0] || { broken: pagesBroken.map((b) => String(b.err)) };
      const reminder = pagesReminderSpecs(heldRows("reminders"))[0];
      const link = (n) => n.byClass("row-link").map((l) => [l.textContent, l.dataset.link]);
      return { head: link(head), headParts: head.kids.map((k) => [k.className, k.textContent]), caption: link(caption), captionText: caption.textContent,
               rows: rows.map((r) => [r.byClass("row-name")[0].textContent, link(r.byClass("row-name")[0])]),
               overview: [overview.name, overview.nameLink, overview.household, overview.year, overview.form, overview.detailLink || null],
               reminder: [reminder.name, reminder.nameLink.kind, reminder.household, reminder.year, reminder.form], statusTips };
    """, tmp_path, setup=ENGINE_BRIDGE, functions=["pagesNeedsReview", "pagesNameCell", "pagesFirm", "pagesFirmReturn", "pagesReturnName",
                              "pagesFileLink", "pagesRow", "pagesRowNode", "pagesRegister", "pagesIsChild", "pagesCell", "pagesLinkNode", "pagesLinkWords", "pagesHeadLink", "pagesGroup", "pagesGroupStep", "pagesList",
                              "pagesReason", "pagesDay", "pagesSafe", "pagesEach", "pagesLabel", "pagesSafeName", "pagesStepWords", "pagesByName", "pagesEmpty",
                              "pagesNextSort", "pagesWorkRows", "pagesCounts", "pagesRoute", "pagesDue", "pagesSince", "pagesReminderSpecs", "pagesStage", "screenWords", "h", "icon",
                              "pagesActivate", "pagesRunRow", "pagesRunRowLink", "pagesRunLink", "pagesRunStep", "pagesPathOf", "pagesPopup", "pagesEnableFor", "pagesRowRoute",
                              *COLUMN_FUNCTIONS])
    assert ran["head"] == [["Smith", "return"]] and ran["caption"] == [["Smith Family", "household"]]
    assert ran["captionText"] == "Smith Family \u00b7 2 Documents", "the household, then the count in the same caption (P272)"
    assert ran["headParts"] == [["head-year", "2025"], ["row-link", "Smith"], ["form-tag", "1040"]], "the heading says the year, the taxpayer and the form once each (P195)"
    assert ran["rows"] == [["one.pdf", [["one.pdf", "file"]]], ["two.exe", []]], "text for the file with no copy"
    assert ran["overview"] == ["Smith", {"kind": "return", "path": "/c/Smith/2025/1040 - Smith", "tip": "Navigate to Return (Smith Family)"}, "Smith Family", 2025, "1040", None]
    assert ran["reminder"] == ["Smith", "return", "Smith Family", 2025, "1040"]
    # P116: the page hands each file's reason code to its row, so a tag's words are its tooltip.
    assert ran["statusTips"] == ["Could not tell", "Came in email or zip"]


def test_a_cut_name_that_is_a_link_carries_the_links_tooltip_not_its_own(tmp_path):
    """One element, one tooltip (ledger default 2): the link's words win over
    the cut name's; a plain name is still the tip of itself when cut."""
    ran = run_pages_dom("""
      const spec = { name: "a-very-long-file-name.pdf", detail: "Smith Family", status: "Could Not Sort", tone: "needs", date: "", menu: "file",
                     nameLink: { kind: "file", key: "k", paths: {} }, step: { kind: "check", ret: "r", name: "n", handle: "h" } };
      tips.length = 0;
      pagesRow(spec);
      return tips.map(([cls, words]) => [cls, words]);
    """, tmp_path)
    assert ["row-link", "Show in File Explorer"] in ran
    assert not [one for one in ran if one[1] == "a-very-long-file-name.pdf"], "the cut name's own tip is not set on a link"
    assert ["row-detail", "Smith Family"] in ran


def test_the_next_arrows_order_is_the_files_a_person_must_look_at_in_the_order_drawn(tmp_path):
    ran = run_pages_dom("""
      const state = stateOf([item("A", "needs_you")], [parked("p1"), parked("p2"), setAsideRow("d1")], [{ handle: "m1", original_name: "m1.pdf", in_request: "", identifier: "", open_key: "" }]);
      state.index.push({ handle: "m1", original_name: "m1.pdf", decision: "File Moved", group: "needs_you", code: "file-moved", received: "2026-03-02" });
      lastState = state;
      const box = page(pagesReturn({ level: "return", ret: "r1", year: 2025 }));
      return { files: pagesFiles().map((s) => s.name), drafts: pagesDrafts().map((s) => s.ret) };
    """, tmp_path)
    assert ran["files"] == ["p1.pdf", "p2.pdf", "m1.pdf"], "parked, then moved; the set-aside file is opened by hand, not walked to"


def test_a_row_menu_offers_only_what_applies_and_the_page_answers_only_its_own_tokens(tmp_path):
    ran = run_pages_dom("""
      const spec = (menu, extra = {}) => ({ menu, step: { kind: "check", ret: "r", name: "n", handle: "h" }, ...extra });
      const out = {};
      out.parked = pagesEnableFor(spec("file", { fileKind: "parked", nameLink: { kind: "file" } }));
      out.aside = pagesEnableFor(spec("file", { fileKind: "aside" }));
      out.missing = pagesEnableFor({ menu: "file", fileKind: "missing", step: null });
      out.moved = pagesEnableFor(spec("moved", { canKeep: true, nameLink: { kind: "file" } }));
      out.movedNoKeep = pagesEnableFor(spec("moved"));
      out.movedGone = pagesEnableFor(spec("moved", { gone: true, nameLink: { kind: "file" } }));
      out.request = pagesEnableFor({ menu: "request" });
      out.received = pagesEnableFor({ menu: "received", unfile: { original: "h", seq: 1 }, missing: null });
      out.receivedLinked = pagesEnableFor({ menu: "received", unfile: { original: "h", seq: 1 }, missing: { original: "h", identifier: "R", seq: 1 }, detailLink: { kind: "file" } });
      out.receivedPlain = pagesEnableFor({ menu: "received", unfile: null, missing: null });
      busyNow = ["h"];
      out.receivedBusy = pagesEnableFor({ menu: "received", unfile: { original: "h", seq: 1 }, missing: { original: "h", identifier: "R", seq: 1 } });
      busyNow = [];
      // Another Return is offered where the sheet has the button: a document of this return, with a return to hand it to.
      feds = [];
      out.noFed = pagesEnableFor(spec("file", { fileKind: "parked" }));
      feds = [1];
      lastState.index[0].bucket = "x";
      out.notDocument = pagesEnableFor(spec("file", { fileKind: "parked" }));
      lastState.index[0].bucket = "doc";
      lastState.paths.engagement = "elsewhere";
      out.otherReturn = pagesEnableFor(spec("file", { fileKind: "parked" }));
      lastState.paths.engagement = "r";
      locked = true;
      out.lockedParked = pagesEnableFor(spec("file", { fileKind: "parked" }));
      out.lockedRequest = pagesEnableFor({ menu: "request" });
      out.lockedReceived = pagesEnableFor({ menu: "received", unfile: { original: "h", seq: 1 }, missing: { original: "h", identifier: "R", seq: 1 }, detailLink: { kind: "file" } });
      locked = false;
      // The client rows' menus are the shell's ids and never a file's.
      shellIds = ["edit_household", "open_client_folder", "sort_now"];
      out.household = pagesEnableFor({ menu: "household", nameLink: { kind: "household", path: "hh" } });
      out.returnRow = pagesEnableFor({ menu: "return", nameLink: { kind: "return", path: "rr" }, detailLink: { kind: "file" } });
      pagesTokens.set("row-1", spec("file", { fileKind: "parked", nameLink: { kind: "file", key: "k", paths: { k: "/p" } } }));
      out.crumb = pagesMenu("edit_household", "crumb-household");
      out.unknown = pagesMenu("check", "row-99");
      out.own = pagesMenu("show_in_explorer", "row-1");
      return out;
    """, tmp_path, setup="let shellIds = []; let shellEnabled = () => shellIds; let openCheck; const unfileDocument = () => {}; const withdrawAnswer = () => {}; const sheetPress = () => true; let sheetNow = null;\n"
                           "let busyNow = []; const writeBusy = (command, original) => busyNow.indexOf(original) !== -1; let feds = [1]; const fedReturns = () => feds; const notADocument = (e) => e.bucket === 'x';\n"
                           "lastState = { paths: { engagement: 'r' }, index: [{ handle: 'h', bucket: 'doc' }] };\n"
                           + read("pages.js")[read("pages.js").index("const PAGES_ROW_ANSWERS = {"):read("pages.js").index("};\n", read("pages.js").index("const PAGES_ROW_ANSWERS = {")) + 3],
       functions=["pagesEnableFor", "pagesCanHandOver", "pagesMenu", "pagesRowRoute", "pagesRunStep", "pagesRunLink", "pagesCheckThen", "pagesClientMenu", "pagesRoute", "pagesPathOf"])
    assert ran["parked"] == ["check", "not_requested", "another_return", "show_in_explorer"]
    assert ran["aside"] == ["check"] and ran["missing"] == []
    assert ran["moved"] == ["check", "put_back", "keep_here", "show_in_explorer"] and ran["movedNoKeep"] == ["check", "put_back"]
    assert ran["movedGone"] == ["check", "show_in_explorer"], "a copy whose original is gone has no Put Back on the sheet"
    assert ran["request"] == ["edit_request"] and ran["received"] == ["unfile"]
    assert ran["receivedLinked"] == ["unfile", "mark_missing", "show_in_explorer"], "the filed copy's link has a keyboard route (F11)"
    assert ran["receivedPlain"] == [] and ran["receivedBusy"] == [], "a write in flight greys its item"
    assert ran["noFed"] == ["check", "not_requested"], "no return to hand it to: no Another Return"
    assert ran["notDocument"] == ["check", "not_requested"] and ran["otherReturn"] == ["check", "not_requested"]
    assert ran["lockedParked"] == ["check"] and ran["lockedRequest"] == [], "a live lock greys the writing items"
    assert ran["lockedReceived"] == ["show_in_explorer"], "under a live lock Received offers no Unfile or Mark Missing"
    assert ran["household"] == ran["returnRow"] == ["edit_household", "open_client_folder", "sort_now"], "the client rows' menus never carry show_in_explorer"
    assert ran["crumb"] is False and ran["unknown"] is False, "the crumbs' tokens and unknown rows are the shell's"
    assert ran["own"] is True


#: What each right-click template must carry in main.js's POPUPS for the page's row menus to appear (S6's
#: join of S2 and S8a; F13). main.js drops an id its template lacks, so a join that forgets one passes
#: every renderer test and the item silently never shows. The renderer's side is pinned here; the join
#: itself is pinned in tests/test_shell_menu.py against main.js's POPUPS.
JOIN_POPUPS = {
    "file": ["check", "not_requested", "another_return", "show_in_explorer"],
    "moved": ["check", "put_back", "keep_here", "show_in_explorer"],
    "request": ["edit_request"],
    "received": ["unfile", "mark_missing", "show_in_explorer"],
}


def test_the_row_menus_offer_exactly_the_ids_the_join_must_put_in_the_popup_templates(tmp_path):
    """The most each template can offer, on the most permissive row, is the
    join table above; the page answers each of those ids and no other; the
    client rows' templates are the shell's ids and never a file's."""
    ran = run_pages_dom("""
      const step = { kind: "check", ret: "r", name: "n", handle: "h" };
      const link = { kind: "file" };
      const most = { file: { menu: "file", fileKind: "parked", nameLink: link, step },
                     moved: { menu: "moved", canKeep: true, nameLink: link, step },
                     request: { menu: "request" },
                     received: { menu: "received", unfile: { original: "h", seq: 1 }, missing: { original: "h", identifier: "R", seq: 1 }, detailLink: link } };
      const out = {};
      for (const [name, spec] of Object.entries(most)) out[name] = pagesEnableFor(spec);
      return out;
    """, tmp_path, setup="let shellEnabled = () => []; const writeBusy = () => false; const fedReturns = () => [1]; const notADocument = () => false;\n"
                         "lastState = { paths: { engagement: 'r' }, index: [{ handle: 'h' }] };\n",
       functions=["pagesEnableFor", "pagesCanHandOver", "pagesRowRoute"])
    assert ran == JOIN_POPUPS
    text = read("pages.js")
    table = text[text.index("const PAGES_ROW_ANSWERS = {"):]
    answered = set(re.findall(r"^  (\w+): ", table[:table.index("\n};\n")], flags=re.M))
    assert answered == {id for ids in JOIN_POPUPS.values() for id in ids}, "the page answers what the templates carry, no more"


def test_a_client_rows_item_is_answered_only_if_its_rule_holds_on_the_page_it_went_to(tmp_path):
    """Right-click a return a live pass holds, choose Edit Request List: the
    app goes there, and the lock (read on arrival) greys the item, so the
    editor does not open (SPEC 5.2)."""
    ran = run_shell(["pagesClientMenu"], """
      let shellRoute = { level: "overview" }; let locked = false; let ids = ["edit_list"]; const answered = [];
      const there = { level: "return", ret: "r2", household: "h" };
      const pagesRowRoute = () => there; const shellEnabled = () => ids; const openReminder = () => {};
      const shellGo = async (route) => { shellRoute = route; ids = locked ? [] : ["edit_list"]; };
      const shellAnswer = (id) => answered.push(id);
    """, """
      return (async () => {
        locked = true;
        await pagesClientMenu({ menu: "return" }, "edit_list");
        const first = answered.slice();
        shellRoute = { level: "overview" }; locked = false;
        await pagesClientMenu({ menu: "return" }, "edit_list");
        return [first, answered.slice()];
      })();
    """, tmp_path, source="pages.js")
    assert ran == [[], ["edit_list"]]


def test_a_second_unfile_or_mark_missing_before_the_reply_is_not_sent_and_the_menu_greys_it(tmp_path):
    """The item has no button to grey: a second Unfile of the same original
    would carry the seq the first used and be refused, a failure notice for
    a write that worked. It is not sent, its menu id is grey meanwhile, and
    it is free again once the reply (or the refusal) is in."""
    ran = run_shell(["writeKey", "writeBusy", "writeStart", "writeDone", "writeRow", "sayNotes", "unfileDocument", "withdrawAnswer"], """
      const viewGeneration = 1; const writesInFlight = new Set(); const sent = []; const refusals = []; const releases = []; let reject = false;
      const withEng = (c) => c;
      const call = (command, payload) => { sent.push([command, payload.original]); return new Promise((resolve, fail) => { releases.push(() => (reject ? fail(new Error("no")) : resolve({ state: {}, unfiled: { original_name: "a", decision: "d" }, marked_missing: { original_name: "a", reason: "r" } }))); }); };
      const renderFor = () => {}; const outcome = () => {};
      const refused = async (err) => { refusals.push(err.message); };
    """, """
      return (async () => {
        const out = {};
        const first = unfileDocument({ original: "h", seq: 1 });
        const second = unfileDocument({ original: "h", seq: 1 });
        out.busy = writeBusy("unfile", "h");
        out.otherOriginal = writeBusy("unfile", "other");
        releases.splice(0).forEach((go) => go()); await first; await second;
        out.sentOnce = sent.length; out.freeAfter = !writeBusy("unfile", "h");
        const m1 = withdrawAnswer({ original: "h", identifier: "R1", seq: 1 });
        const m2 = withdrawAnswer({ original: "h", identifier: "R1", seq: 1 });
        const m3 = withdrawAnswer({ original: "h", identifier: "R2", seq: 1 });
        out.missingBusy = [writeBusy("mark-missing", "h", "R1"), writeBusy("mark-missing", "h", "R2")];
        reject = true; releases.splice(0).forEach((go) => go()); await m1; await m2; await m3;
        out.sentAfter = sent.map((one) => one.join(":")); out.refusals = refusals;
        out.freeAfterRefusal = !writeBusy("mark-missing", "h", "R1");
        return out;
      })();
    """, tmp_path, source="app.js")
    assert ran["busy"] is True and ran["otherOriginal"] is False
    assert ran["sentOnce"] == 1 and ran["freeAfter"] is True
    assert ran["missingBusy"] == [True, True]
    assert ran["sentAfter"] == ["unfile:h", "mark-missing:h", "mark-missing:h"], "the second identical write is not sent, a different request's is"
    assert ran["freeAfterRefusal"] is True


def test_a_menu_answer_that_fails_is_a_notice_not_an_unhandled_rejection():
    text = stripped_js("pages.js")
    body = text[text.index("function pagesMenu(id, token) {"):]
    body = body[:body.index("\n}\n")]
    assert body.count(".catch((err) => failed(err))") == 2


# ── the sheet's own logic, in node ──────────────────────────────────────────

SHEET_SETUP = r"""
const vocab = { decisions: { needs_review: "Needs Review", dismissed: "Not Requested", file_moved: "File Moved", filed: "Filed" } };
let sheetNow = null; let sheetGeneration = 0; const advanced = []; const closed = [];
const sheetAdvance = () => advanced.push(sheetNow.handle);
"""


def test_the_sheet_finds_a_file_where_it_can_be_checked_and_nowhere_else(tmp_path):
    ran = run_shell(["sheetFind"], SHEET_SETUP, """
      const state = { moved: [{ handle: "m" }], index: [
        { handle: "p", decision: "Needs Review" }, { handle: "d", decision: "Not Requested" },
        { handle: "f", decision: "Filed" }, { handle: "x", decision: "File Moved" }, { handle: "m", decision: "File Moved" }] };
      return ["p", "d", "f", "x", "m", "none"].map((h) => { const found = sheetFind(state, h); return found ? found.kind : null; });
    """, tmp_path, source="sheet.js")
    assert ran == ["parked", "aside", None, None, "moved", None], "filed, marked missing and unknown files are not there to check"


def test_the_sheet_moves_on_only_when_the_file_it_shows_has_been_answered(tmp_path):
    """After a write that works the row leaves the state, or keeps its handle
    in another kind (Not requested rewrites the same row: parked to set aside;
    a Put back that parks a moved copy) or at another record version: the next
    file. A read of the same state, a refusal, another return's state and a
    state that arrives before the file is drawn leave the sheet as it is."""
    ran = run_shell(["sheetFind", "sheetSeen", "sheetStateArrived"], SHEET_SETUP, """
      const at = (extra) => ({ paths: { engagement: "r1" }, moved: [], index: [{ handle: "p", decision: "Needs Review", seq: 1, ...extra }] });
      const gone = { paths: { engagement: "r1" }, moved: [], index: [] };
      const other = { paths: { engagement: "r2" }, moved: [], index: [] };
      const run = (now, state) => { sheetNow = now; advanced.length = 0; sheetStateArrived(state); return advanced.length; };
      const check = (extra = {}) => ({ kind: "check", ret: "r1", handle: "p", ready: true, shown: "parked:1", ...extra });
      const movedNow = { kind: "check", ret: "r1", handle: "m", ready: true, shown: "moved:1" };
      const parkedNow = { paths: { engagement: "r1" }, moved: [], index: [{ handle: "m", decision: "Needs Review", seq: 2 }] };
      return [run(check(), at({})), run(check(), gone), run(check(), other), run(check({ ready: false }), gone), run({ kind: "reminder", ret: "r1", ready: true }, gone), run(null, gone),
              run(check(), at({ decision: "Not Requested" })), run(check(), at({ seq: 2 })), run(movedNow, parkedNow)];
    """, tmp_path, source="sheet.js")
    assert ran == [0, 1, 0, 0, 0, 0, 1, 1, 1]


def test_no_request_code_is_drawn_in_the_picker_the_shortlist_or_mark_missing(tmp_path):
    """SPEC 11.1 (F14b): a request is named, never coded. The option's text
    is the document (its value stays the identifier); a gone copy's button
    says Mark <the request's name> Missing; a request it cannot name is a
    loud failure, never the code."""
    ran = run_shell(["requestOption", "movedRow"], """
      const vocab = { triage: { identifier_separator: " - " }, review_labels: { mark_missing: "Mark {identifier} Missing" } };
      const fill = (p, v) => p.replace(/\\{(\\w+)\\}/g, (_, k) => v[k] ?? "");
      const el = (tag, attrs, ...kids) => ({ tag, attrs, kids: kids.flat().filter(Boolean) });
      const pagesItemName = (item) => item.short_name || item.document;
    """, """
      const items = [{ identifier: "R03", document: "1099-B - Northwind Brokerage", short_name: "Northwind" }];
      const option = requestOption(items[0], "R03");
      const gone = movedRow({ handle: "h", seq: 1, gone: true, identifier: "R03" }, [], items);
      let loud = "";
      try { movedRow({ handle: "h", seq: 1, gone: true, identifier: "R99" }, [], items); } catch (err) { loud = err.message; }
      return { option: [option.attrs.value, option.kids], button: gone.kids[0].kids, key: gone.kids[0].attrs.dataset.identifier, loud };
    """, tmp_path, source="app.js")
    assert ran["option"] == ["R03", ["1099-B - Northwind Brokerage"]]
    assert ran["button"] == ["Mark Northwind Missing"] and ran["key"] == "R03" and ran["loud"] == "items.R99"


def test_the_status_line_of_every_kind_of_file_says_what_and_when_it_was_received(tmp_path):
    """SPEC 7.1: the short reason and the received date. A moved copy's row
    has no date; its index row, by the same handle, does (F14a)."""
    ran = run_shell(["sheetStatus"], """
      const screenWords = () => ({ moved: "Moved by Hand" });
      const vocab = { review_labels: { dismiss: "Not Requested" } };
      const pagesReason = (code) => `reason:${code}`;
      const pagesDay = (iso) => (iso ? `day:${iso}` : "");
      const h = (tag, attrs, ...kids) => kids.filter(Boolean).map((k) => (typeof k === "string" ? k : k.join("")));
    """, """
      const state = { index: [{ handle: "m", received: "2026-03-05" }, { handle: "p", received: "2026-03-03", code: "c" }] };
      return [sheetStatus({ kind: "moved", moved: { handle: "m" } }, state), sheetStatus({ kind: "parked", entry: state.index[1] }, state),
              sheetStatus({ kind: "aside", entry: { received: "2026-01-30" } }, state), sheetStatus({ kind: "moved", moved: { handle: "gone" } }, state)];
    """, tmp_path, source="sheet.js")
    assert ran == [["Moved by Hand", "day:2026-03-05"], ["reason:c", "day:2026-03-03"], ["Not Requested", "day:2026-01-30"], ["Moved by Hand"]]


def test_the_sheets_following_files_are_those_after_it_in_the_order_the_page_was_drawn(tmp_path):
    ran = run_shell(["sheetAfter", "sheetDraftsAfter"], SHEET_SETUP, """
      const order = [{ ret: "a", handle: "1" }, { ret: "a", handle: "2" }, { ret: "b", handle: "3" }];
      return [sheetAfter({ order, ret: "a", handle: "1" }).map((s) => s.handle), sheetAfter({ order, ret: "b", handle: "3" }).length,
              sheetAfter({ order, ret: "z", handle: "9" }).length, sheetDraftsAfter({ order: [{ ret: "a" }, { ret: "b" }], ret: "a" }).map((s) => s.ret)];
    """, tmp_path, source="sheet.js")
    assert ran == [["2", "3"], 0, 0, ["b"]], "a file opened by hand (not in the order) has no Next"


def test_the_footers_buttons_are_the_secondary_then_the_primary_and_leave_the_row(tmp_path):
    ran = run_shell(["sheetFooter"], "", """
      const btn = (name) => ({ tagName: "BUTTON", classList: { contains: (c) => c === name } });
      const li = (names) => { const row = { children: names.map(btn), removeChild(one) { this.children = this.children.filter((c) => c !== one); } }; return row; };
      const parked = li(["r-file", "r-dismiss", "x"].filter((n) => n !== "x"));
      const moved = li(["r-restore", "r-keep"]);
      const a = sheetFooter(parked, false); const b = sheetFooter(moved, true);
      const names = (list) => list.map((one) => ["r-dismiss", "r-file", "r-keep", "r-restore"].find((n) => one.classList.contains(n)));
      return { parked: names(a), moved: names(b), left: parked.children.length + moved.children.length };
    """, tmp_path, source="sheet.js")
    assert ran == {"parked": ["r-dismiss", "r-file"], "moved": ["r-keep", "r-restore"], "left": 0}


def test_sheet_js_draws_the_names_it_is_given_and_types_none_and_uses_the_regions_it_owns():
    text = stripped_js("sheet.js")
    assert 'sheetSet("sheet-check", now.kind === "check");' in text and "screenWords().sheet.reminder" in text
    for state in ("showReturn(", "applyLock();", "pagesReason(entry.code)", "words.moved", "vocab.review_labels.dismiss"):
        assert state in text, state
    assert "innerHTML" not in text and "pagesWhere($(\"page\"))" in text


def test_a_held_reminder_row_draws_its_document_alone_never_a_code_or_the_hold_sentence():
    """The engine's hold sentence is 25 words and the row's identifier is a
    request code: neither is drawn in the sheet (SPEC 7.2, 11.1)."""
    text = stripped_js("app.js")
    start = text.index('show("reminder-held-rows"')
    drawn = text[start:text.index("\n", start)]
    assert "row.document" in drawn and "row.identifier" not in drawn and "row.reason" not in drawn
    assert "rem-hold-id" not in text and "rem-hold-why" not in text


# ── the shell's other side of the window ────────────────────────────────────

def test_a_menu_channel_that_throws_is_a_notice_and_never_stops_a_route_change(tmp_path):
    ran = run_shell(["shellEnable", "shellPopup"], """
      const failures = [];
      const failed = (err) => failures.push(err.message);
      const window = { tracker: { menu: { send: () => { throw new Error("closed"); } } } };
      const shellEnabled = () => [];
      const shellChecked = () => [];
    """, """
      shellEnable(); shellPopup("file", "row-1", 1, 2);
      return failures;
    """, tmp_path)
    assert ran == ["closed", "closed"]
    go = js_function("shellGo")
    assert "try {\n    appRouteChanged(next);" in go and "return shellOpenState();" in go


def test_opening_a_path_says_not_opened_in_the_apis_words_and_logs_the_systems(tmp_path):
    ran = run_shell(["openPath"], """
      const vocab = { shell: { not_opened: "Not Opened; It Has Changed" } };
      const seen = []; const logged = []; const failures = [];
      const notice = (n) => seen.push(n.sentence);
      const failed = (err) => failures.push(err.message);
      let answer = "";
      const window = { tracker: { open: async (p, how) => { seen.push([p, how]); if (answer === "throw") throw new Error("boom"); return answer; }, logError: (t) => logged.push(t) } };
    """, """
      return (async () => {
        await openPath("", "reveal");
        await openPath("/p", "reveal");
        answer = "the operating system said something with a path C:\\\\x";
        await openPath("/q");
        answer = "throw";
        await openPath("/r", "reveal");
        return { seen, logged, failures };
      })();
    """, tmp_path)
    assert ran["seen"] == [["/p", "reveal"], ["/q", None], "Not Opened; It Has Changed", ["/r", "reveal"]]
    assert ran["logged"] == ["the operating system said something with a path C:\\x"] and ran["failures"] == ["boom"]


def test_a_file_the_shell_opened_without_protected_view_is_said_in_the_same_notice_each_time(tmp_path):
    """SPEC-mac R8 (P240): the shell answers such an open with ``{ says }``; the
    page says it as a notice - the place Open's own result appears - each time,
    logs nothing as an error, and waits for nothing."""
    ran = run_shell(["openPath"], """
      const vocab = { shell: { not_opened: "Not Opened; It Has Changed" } };
      const seen = []; const logged = []; const failures = [];
      const notice = (n) => seen.push([n.sentence, n.kind]);
      const failed = (err) => failures.push(err.message);
      let answer = { says: "Protected View does not exist on a Mac." };
      const window = { tracker: { open: async () => answer, logError: (t) => logged.push(t) } };
    """, """
      return (async () => {
        await openPath("/macros.xlsm");
        await openPath("/macros.xlsm");
        answer = "refused";
        await openPath("/gone.xlsm");
        return { seen, logged, failures };
      })();
    """, tmp_path)
    said = ["Protected View does not exist on a Mac.", "warning"]
    assert ran["seen"] == [said, said, ["Not Opened; It Has Changed", "warning"]]
    assert ran["logged"] == ["refused"] and ran["failures"] == []


def test_the_four_dialogs_draw_the_apis_words_and_never_a_path(tmp_path):
    """SPEC 2.7 (E93-E95): Safeguards is one short line per rule, About the
    product and the edition, Folders skipped a folder's own name per row;
    a rule without its short line is a loud failure, and no folder's place is drawn."""
    setup = r"""
      const els = {}; const $ = (id) => (els[id] = els[id] || { textContent: "" });
      const el = (tag, attrs, ...kids) => ({ tag, cls: (attrs || {}).className, text: kids.flat().filter(Boolean).map((k) => (typeof k === "string" ? k : k.text)).join("") });
      const show = (id, nodes) => { $(id).rows = nodes.flat(Infinity).filter(Boolean); };
      const opened = []; const openDialog = (id) => opened.push(id); const logged = [];
      const window = { tracker: { logError: (t) => logged.push(t) } };
      const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
      const PILOT = { edition: { version: "0.4" } };
      let misfits = [{ path: "/abs/Clients/Old Files", where: "Clients/Old Files", sentence: "This folder is not a household and is left alone by the app.", code: "not_a_tree" },
                     { path: "C:\\\\abs\\\\Scans", where: "", sentence: "Also left alone.", code: "not_a_year" }];
      const vocab = { product: "Tax Document Console", rules: [{ headline: "h", detail: "d", short: "No AI Reads Documents" }, { headline: "h2", detail: "d2", short: "Nothing Is Guessed" }],
        screen: { icons: { dismiss: "Dismiss" }, safeguards: { title: "Safeguards" }, about: { edition: "Pilot {version}" }, misfits: { title: "Folders Skipped", reasons: { not_a_tree: "Unknown Folder" } } } };
      const screenWords = () => vocab.screen;
    """
    ran = run_shell(["openSafeguards", "openAbout", "openMisfits", "folderName"], setup, """
      openSafeguards(); openAbout(); openMisfits();
      const said = { rules: els["safeguards-list"].rows.map((r) => r.text), title: els["safeguards-title"].textContent, edition: els["about-edition"].textContent,
                     product: els["about-title"].textContent, folders: els["misfits-list"].rows.map((r) => r.text), opened, logged };
      vocab.rules.push({ headline: "x", detail: "long sentence" });
      let loud = "";
      try { openSafeguards(); } catch (err) { loud = err.message; }
      return { ...said, loud };
    """, tmp_path, source="app.js")
    assert ran["rules"] == ["No AI Reads Documents", "Nothing Is Guessed"] and ran["title"] == "Safeguards"
    assert ran["product"] == "Tax Document Console" and ran["edition"] == "Pilot 0.4"
    assert ran["folders"] == ["Old FilesUnknown Folder", "Scans"], (
        "a folder is its own name (the last part of where it is) and the vocabulary's word for its code; "
        "a code with no word (not_a_year) draws the name alone")
    assert ran["opened"] == ["safeguards-modal", "about-modal", "misfits-modal"]
    assert ran["loud"] == "rules.short", "a rule without its short line is a word the vocabulary lacks: loud, not the long sentence"
    assert not any("vocab.screen" in line for line in ran["logged"]), "a code without a word is not an error"
    assert any("not a household" in line for line in ran["logged"]), "the folder's long sentence goes to the error log"


def test_shift_f10_and_the_menu_key_ask_for_the_native_menu_under_the_active_row():
    text = stripped_js("pages.js")
    keys = text[text.index("function pagesKey(e) {"):]
    keys = keys[:keys.index("\n}\n")]
    assert 'e.key === "ContextMenu" || (e.key === "F10" && e.shiftKey)' in keys and "pagesPopup(rows[at]" in keys
    assert 'list.addEventListener("contextmenu"' in text


def test_the_link_kinds_name_the_apis_three_tooltip_keys():
    """The tests above run the words through a copy of the table; this pins
    the table pages.js really has (rulings 11, 12; S8a's key names)."""
    text = stripped_js("pages.js")
    assert 'const PAGES_LINK_WORDS = { file: "show_in_explorer", household: "navigate_client", return: "navigate_return" };' in text
    assert text.count('openPath(path, "reveal")') == 1 and 'openPath(path, "reveal")' in js_function("pagesRunLink", "pages.js")


def test_unfile_from_the_menu_asks_first_and_sends_the_reason_as_the_writes_note():
    """Ruling 16: the right-click Unfile opens a small confirm box (in the one
    dialog registry, focus on the reason field) and only its confirm writes;
    the reason is the write's `note`, and every word in it is the API's."""
    app = stripped_js("app.js")
    pages = stripped_js("pages.js")
    assert "unfile: (spec) => openUnfile(spec.unfile)," in pages and "unfile: (spec) => unfileDocument" not in pages
    opening = js_function("openUnfile", "app.js")
    for word in ("review_labels", "unfile_note", "vocab.editor.cancel", "words.unfile"):
        assert word in opening, word
    assert 'openDialog("unfile-modal")' in opening
    assert '"unfile-modal": { model: null, first: () => $("uf-note")' in app
    confirming = js_function("confirmUnfile", "app.js")
    assert 'note: $("uf-note").value.trim()' in confirming and "btn.disabled = true;" in confirming and 'closeDialog("unfile-modal")' in confirming
    assert '$("uf-confirm").addEventListener("click", confirmUnfile);' in app
    html = read("index.html")
    box = html[html.index('id="unfile-modal"'):]
    box = box[:box.index("</div>\n  </div>")]
    assert ">Unfile<" not in box and ">Cancel<" not in box and "Reason" not in box, "the renderer types no word in the box"


def test_a_request_answered_by_several_files_draws_a_row_for_each_and_counts_only_requests():
    """Ruling 17: each file its own row under the request (own link, own
    right-click), and the group's count is requests, not file rows."""
    pages = stripped_js("pages.js")
    assert 'if (item.group === "received" && filed.length > 1) {' in pages
    assert "child: true" in pages and 'spec.child ? " row-child" : ""' in pages
    assert 'row.classList.contains("row-child")' in js_function("pagesIsChild", "pages.js") and "pagesIsChild(row)" in js_function("pagesGroup", "pages.js")
    assert 'if (spec.detailLink || spec.nameLink) ids.push("show_in_explorer");' in pages


def test_a_failed_last_sort_is_a_keyed_notice_without_retry_that_clears_when_the_record_says_it_worked(tmp_path):
    """Rulings 20 and 28: the record's last sort failed -> one notice (the
    vocabulary's failed word) with NO Retry and no action, on every page; while
    a sort runs it is left alone; a record that says it worked clears it. The
    shapes are the ones ``list`` really sends (``api._last_pass``): a failed
    scheduled pass, a good one, none yet and an unreadable file (``ok`` false,
    ``when`` null: no notice)."""
    ran = run_shell(["syncSortNotice"], """
      let scanning = null; let shellLastPass = null;
      const seen = [];
      const screenWords = () => ({ last_sort: { failed: "Sort Failed" } });
      const keyedNotice = (key, failure, opts) => seen.push(["show", key, failure.sentence, failure.kind, Object.keys(opts || {}).length]);
      const clearNotice = (key) => seen.push(["clear", key]);
      const runScan = () => {};
    """, """
      const at = (pass, running) => { shellLastPass = pass; scanning = running; seen.length = 0; syncSortNotice(); return seen.map((one) => one.join("|")); };
      const line = { text: "Last Sort Failed", level: "err" };
      return {
        failed: at({ ...line, ok: false, when: "2026-09-30T06:00:00" }, null),
        running: at({ ...line, ok: false, when: "2026-09-30T06:00:00" }, { pass: "p" }),
        worked: at({ text: "Sorted", level: "ok", ok: true, when: "2026-09-30T06:00:00" }, null),
        never: at({ text: "Never", level: "warn", ok: false, when: null }, null),
        unreadable: at({ text: "Could Not Be Read", level: "err", ok: false, when: null }, null),
        none: at(null, null),
        scheduled: at({ ...line, ok: false, running: true, when: "2026-09-30T06:00:00" }, null),
      };
    """, tmp_path)
    assert ran["failed"] == ["show|last-sort|Sort Failed|failed|0"], "no retry, no action"
    assert ran["running"] == [], "left as it is while a sort runs"
    assert ran["scheduled"] == [], "left as it is while a scheduled pass runs (pilot P256)"
    assert ran["worked"] == ["clear|last-sort"] and ran["none"] == ["clear|last-sort"]
    assert ran["never"] == ["clear|last-sort"] and ran["unreadable"] == ["clear|last-sort"]
    assert "syncSortNotice();" in js_function("shellChanged", "shell.js")
    body = js_function("syncSortNotice", "shell.js")
    assert "retry" not in body and "runScan" not in body and "action" not in body


def test_a_household_paused_for_two_open_years_is_marked_and_listed_from_the_firm_replys_paused_field(tmp_path):
    """Ruling 21: `paused: true` on a household's firm.returns[] entries puts
    the vocabulary's words beside its name on Clients (and in Work Waiting)
    and leads Overview's rows with it; an entry without the field draws
    nothing. The engine reads the field (P278) and says it on the rows it
    sends; the window words it."""
    ran = run_pages_dom("""
      households = [{ name: "Alpha Family", path: "a" }, { name: "Bravo Family", path: "b" }];
      const make = (household, extra = {}) => ({ path: household, household, counts: { needs_you: 0, waiting: 1, received: 0, set_aside: 0 }, problem: "", files: 0,
                                                 oldest: null, due: "2026-04-15", draft: { ready: false, stage: 0, held: 0, drafted: null }, ...extra });
      const paused = { returns: [make("Alpha Family", { paused: true }), make("Bravo Family")], files: [], paths: {}, totals: {}, next_sort: null };
      const plain = { returns: [make("Alpha Family"), make("Bravo Family")], files: [], paths: {}, totals: {}, next_sort: null };
      const say = (whole, all) => { shellFirmData = whole; pagesClientsAll = all; settle("clients"); return pagesClientSpecs(heldRows("clients")).map((one) => [one.name, one.mark]); };
      const pausedRows = (whole) => { shellFirmData = whole; settle("overview"); return pagesWorkRows(heldRows("overview").filter((row) => row.kind === "paused")); };
      const cell = pagesNameCell({ name: "Alpha Family", mark: "Two Years Open; Sorting Paused" });
      return { work: say(paused, false), all: say(paused, true), plainAll: say(plain, true),
               rows: pausedRows(paused).map((s) => [s.name, s.status, s.menu, s.step.route.household]), none: pausedRows(plain),
               cell: cell.kids.map((k) => k.className), plainCell: pagesNameCell({ name: "x" }).kids.length };
    """, tmp_path, setup=ENGINE_BRIDGE)
    words = "Two Years Open; Sorting Paused"
    assert ran["work"] == [["Alpha Family", ""], ["Bravo Family", ""]] or ran["work"] == [["Alpha Family", words], ["Bravo Family", ""]]
    assert ran["all"] == [["Alpha Family", words], ["Bravo Family", ""]]
    assert ran["plainAll"] == [["Alpha Family", ""], ["Bravo Family", ""]], "with the field absent nothing is drawn"
    assert ran["rows"] == [["Alpha Family", words, "household", "a"]] and ran["none"] == []
    assert ran["cell"][-1] == "row-mark is-attention" and ran["plainCell"] == 1
    assert "pagesWorkRows(page.rows)" in js_function("pagesOverview", "pages.js"), "Overview words the rows the engine sends: its paused households lead them"


# ── the harness speaks the engine (S6b) ───────────────────────────────────
# The harness stub is the renderer's stand-in for the tracker. Before the join
# it drew on a snapshot of the vocabulary and on shapes written by hand; from
# S6b it reads the API's own vocabulary and is held to the API's own replies.


#: The first page of each firm list, as the window asks it (P278): the filters are the lists' own, whole.
PAGE_ASKS = {"overview": {"tab": "all"}, "needs_review": {"reason": ""}, "reminders": {}, "clients": {"all": True, "type": ""}}


def _stub_replies(scenario: str) -> dict:
    """The stub's ``list``, ``firm``, ``firm-last`` and first three ``state`` replies, run in node
    on the live vocabulary, as the harness serves it."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    stub = (REPO / "pilot" / "harness" / "stub.js").read_text(encoding="utf-8")
    script = f"""
const vm = require("vm");
const window = {{ __VOCAB__: {json.dumps(api._vocab())} }};
vm.runInContext({json.dumps(stub)}, vm.createContext({{ window, location: {{ search: "?scenario={scenario}" }}, URLSearchParams, setTimeout, console, Date, Intl }}));
(async () => {{
  const list = await window.tracker.call(["list"]);
  const firm = await window.tracker.call(["firm"]);
  const firm_last = await window.tracker.call(["firm-last"]);
  const pages = {{}};
  for (const [name, filter] of Object.entries({json.dumps(PAGE_ASKS)})) pages[name] = await window.tracker.call(["firm"], {{ page: {{ list: name, at: 0, order: null, filter }} }});
  const page_last = await window.tracker.call(["firm-last"], {{ page: {{ list: "overview", at: 0, order: null, filter: {{ tab: "all" }} }} }});
  const states = [];
  for (const one of list.engagements.slice(0, 3)) states.push(await window.tracker.call(["state", "--engagement", one.path]));
  console.log(JSON.stringify({{ list, firm, firm_last, pages, page_last, states }}));
}})();
"""
    # From a file, never ``node -e``: the stub alone is longer than Windows'
    # 32,767-character command line (the Windows check's A3, P129).
    with tempfile.TemporaryDirectory() as folder:
        probe = Path(folder) / "stub-replies.js"
        probe.write_text(script, encoding="utf-8", newline="\n")
        done = subprocess.run([NODE, str(probe)], capture_output=True, text=True, encoding="utf-8", timeout=60,
                              check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _stub_code() -> str:
    """The stub with its comments cut, so a word inside one is not read as code."""
    text = (REPO / "pilot" / "harness" / "stub.js").read_text(encoding="utf-8")
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.S)
    return re.sub(r"(?m)^\s*//.*$", "", text)


def test_the_harness_stub_speaks_the_apis_vocabulary(tmp_path):
    """SPEC 14.1 and 14.4. No snapshot: ``make_vocab.py`` dumps
    ``api._vocab()`` of this tree, the stub hands it on unchanged, and every
    word the stub reads by name is a key the API has."""
    assert not (REPO / "pilot" / "harness" / "vocab-mirror.json").exists()
    live = json.loads(json.dumps(api._vocab()))
    dumped = tmp_path / "vocab.json"
    # The child answers the question of the same computer as this process
    # does: the suite's pin of ``settings.host_system`` (tests/conftest.py)
    # is in-process, so on a Mac the child would say "Another Mac Sorting"
    # against this process's "Another PC Sorting". The seam is handed on,
    # never the comparison loosened.
    pinned = (f"import runpy, sys; from tracker import settings; "
              f"settings.host_system = lambda: {settings_module.host_system()!r}; "
              f"sys.argv = sys.argv[1:]; runpy.run_path(sys.argv[0], run_name='__main__')")
    done = subprocess.run([sys.executable, "-c", pinned, str(REPO / "pilot" / "harness" / "make_vocab.py"),
                           str(dumped)],
                          capture_output=True, text=True, encoding="utf-8", timeout=60, check=False, cwd=REPO)
    assert done.returncode == 0, done.stderr
    assert json.loads(dumped.read_text(encoding="utf-8")) == live
    read = set(re.findall(r"\bvocab((?:\.[A-Za-z_]\w*)+)", _stub_code()))
    assert {".screen.moved", ".review_labels.dismiss", ".decisions.filed", ".shell.not_opened"} <= read
    for path in sorted(read):
        here = live
        for part in path[1:].split("."):
            assert isinstance(here, dict) and part in here, f"the stub reads vocab{path}, which the API lacks"
            here = here[part]
    assert _stub_replies("normal")["list"]["vocab"] == live


@pytest.fixture
def scratch_root(short_root, tmp_path, monkeypatch):
    """A small clients root recorded the way the app records it (the fixture
    ``test_api`` uses, spelled here so this file does not import a fixture)."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root, set_firm

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(short_root)
    set_firm("J Park & Associates, CPA")
    return short_root


def _keys(rows: list) -> set[str]:
    return {key for row in rows for key in row}


def test_the_harness_stub_replies_have_the_shape_of_the_engines(capsys, scratch_root, tmp_path):
    """The wire check (S6b): the real ``list``, ``firm`` and ``state`` of a
    small scratch clients tree, and the stub's, name the same keys at every
    level the renderer reads. The stub may add what the engine sends only
    sometimes; it may not miss what it always sends nor invent a key."""
    engagement = sample_engagement(capsys, scratch_root, tmp_path)
    assert scan(capsys, engagement)[0] == 0
    (scratch_root / "Clients" / "Stray Folder").mkdir()
    real = {"list": run(capsys, "list")[1], "firm": run(capsys, "firm")[1],
            "state": run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[1],
            "firm_last": run(capsys, api.FIRM_LAST_COMMAND)[1],
            "pages": {name: run(capsys, "firm", stdin={"page": {"list": name, "at": 0, "order": None, "filter": filter}})[1] for name, filter in PAGE_ASKS.items()}}
    stub = _stub_replies("notices")

    # list
    assert set(stub["list"]) == set(real["list"]) - {"warnings"}
    assert _keys(stub["list"]["engagements"]) == _keys(real["list"]["engagements"])
    assert _keys(stub["list"]["households"]) == _keys(real["list"]["households"])
    optional = {"form", "people", "rollable"}      # only while a roll is offered
    real_returns = _keys(real["list"]["households"][0]["returns"])
    assert real_returns <= _keys(stub["list"]["households"][0]["returns"]) <= real_returns | optional
    assert _keys(stub["list"]["misfits"]) == _keys(real["list"]["misfits"]) == {"path", "sentence", "code", "where"}
    codes = {row["code"] for row in stub["list"]["misfits"]} | {row["code"] for row in real["list"]["misfits"]}
    # The stub sends one code the vocabulary has no word for, on purpose: the page draws the name alone.
    assert codes - set(api._vocab()["screen"]["misfits"]["reasons"]) == {"unwritten_code"}, codes
    assert {row["code"] for row in real["list"]["misfits"]} <= set(api._vocab()["screen"]["misfits"]["reasons"])
    assert set(stub["list"]["paths"]) == set(real["list"]["paths"])

    # firm: paused on every return, an open key on every file, one paths table
    assert set(stub["firm"]) == set(real["firm"]) - {"warnings"}
    assert _keys(stub["firm"]["returns"]) == _keys(real["firm"]["returns"])
    assert all(isinstance(one["paused"], bool) for one in stub["firm"]["returns"] + real["firm"]["returns"])
    assert _keys(stub["firm"]["files"]) == _keys(real["firm"]["files"])
    assert set(stub["firm"]["totals"]) == set(real["firm"]["totals"])
    for reply in (stub["firm"], real["firm"]):
        opened = {one["open_key"] for one in reply["files"]} - {""}
        assert opened and opened <= set(reply["paths"]), "every file's open key is a key of paths"
        assert {key.split(" ")[0] for key in reply["paths"]} <= set(api.PATH_KINDS)

    # firm, a page of a list (P278): the page, the totals, each return's counts, only its rows' paths and, on Needs Review, every file
    for name, real_page in real["pages"].items():
        got = stub["pages"][name]
        assert set(got) == set(real_page) - {"warnings"}, name
        assert isinstance(got["view"], str) and isinstance(real_page["view"], str)
        assert _keys(got["return_counts"]) == _keys(real_page["return_counts"]) == {"path", "household", "year", "form", "counts", "files", "problem", "paused"}
        assert set(got["totals"]) == set(real_page["totals"]) and set(got["page"]) == set(real_page["page"]), name
        assert set(got["page"]["counts"]) == set(real_page["page"]["counts"]) and got["page"]["filter"].keys() == real_page["page"]["filter"].keys(), name
        if name == "reminders":     # the scratch tree has no draft ready: a Reminders row is a return's entry
            assert got["page"]["rows"] and _keys(got["page"]["rows"]) == _keys(real["firm"]["returns"]), name
        else:
            assert got["page"]["rows"] and real_page["page"]["rows"], f"{name}: both hold made-up rows to compare"
            assert _keys(got["page"]["rows"]) == _keys(real_page["page"]["rows"]), name
        if name == "needs_review":
            assert _keys(got["page"]["rows"][0]["files"]) == _keys(real_page["page"]["rows"][0]["files"])
            assert _keys(got["files_found"]) == _keys(real_page["files_found"]) == {"name", "return", "year", "handle"}
            opened = {one["open_key"] for group in got["page"]["rows"] for one in group["files"]} - {""}
            assert opened and opened == set(got["paths"]), "only the page's rows' keys are named"
        else:
            assert "files_found" not in got and got["paths"] == {}, name
    assert set(stub["page_last"]) == {"last", "warnings"} and stub["page_last"]["last"] is None

    # firm-last (P229): the refusal is the API's {last: null, warnings}; the
    # answer is the firm reply's own fields at the top level, plus `last:
    # true` and `as_of` ("HH:MM") - tracker.api's contract, which the
    # renderer's shellLastOf accepts and nothing else.
    assert set(real["firm_last"]) == set(stub["firm_last"]) == {"last", "warnings"}
    assert real["firm_last"]["last"] is None and stub["firm_last"]["last"] is None
    answered = _stub_replies("last-counts")["firm_last"]
    assert set(answered) - {"last", "as_of"} == set(real["firm"]) - {"warnings"}
    assert answered["last"] is True and re.fullmatch(r"\d{2}:\d{2}", answered["as_of"])
    answered_page = _stub_replies("last-counts")["page_last"]
    assert set(answered_page) - {"last", "as_of"} == set(real["pages"]["overview"]) - {"warnings"} and answered_page["view"] is None and answered_page["last"] is True

    # state: the stub is a subset of the engine's, level by level
    for reply in stub["states"]:
        assert set(reply) <= set(real["state"])
        for level in ("index", "review", "items"):
            assert _keys(reply[level]) <= _keys(real["state"][level]), level
        assert {key.split(" ")[0] for key in reply["paths"]} <= set(api.PATH_KINDS)
    moved = [row for reply in stub["states"] for row in reply["moved"]]
    assert moved and set(moved[0]) - {"named"} == {
        "original_name", "pbc_location", "handle", "seq", "home", "now", "in_request", "gone",
        "open_key", "identifier", "group"}


def test_the_three_info_dialogs_close_with_the_apis_close_word():
    """SPEC 2.7 E93-E95 say Close (S5 review F9): the button of Safeguards,
    About and Folders Skipped reads ``screen.close``, and ``icons.dismiss``
    stays the notice icon's and the side sheet's."""
    app = stripped_js("app.js")
    for name in ("safeguards", "about", "misfits"):
        assert f'$("{name}-close").textContent = words.close;' in app, name
    assert "-close\").textContent = words.icons.dismiss" not in app
    screen = api._vocab()["screen"]
    assert screen["close"] == "Close" and screen["icons"]["dismiss"] == "Dismiss"


def test_every_word_index_html_types_is_in_title_case():
    """Ruling 10 (Title Case) for the page's own literals: the text between
    tags, ``aria-label`` and ``placeholder``. The words that come from the
    API are its; these are the few the template types (Retry, Cancel, the
    wizard's field names) and they are cased like them."""
    from tests.test_api import title_case

    html = re.sub(r"<!--.*?-->", "", read("index.html"), flags=re.S)
    html = re.sub(r"<(script|style|svg)\b.*?</\1>", "", html, flags=re.S)
    texts = [t.strip() for t in re.findall(r">([^<>]+)<", html) if t.strip()]
    texts += re.findall(r'(?:aria-label|placeholder)="([^"]+)"', html)
    assert "Retry" in texts and "Add a Custom Request" in texts
    bad = [(t, title_case(t)) for t in texts if len(t.split()) > 1 and title_case(t) != t]
    assert not bad, bad


def test_every_link_key_the_engine_sends_names_a_real_file_main_js_would_reveal(capsys, scratch_root, tmp_path):
    """The wire, engine to window (S6b, ruling 15): each key a row carries
    (``shown_key``, ``open_keys[0]``, a firm file's ``open_key``) is a key of
    the reply's ``paths``; its word is one the API names a kind for
    (``PATH_KINDS``, which ``main.js`` learns from ``list``); the path is a
    file that is really there, so ``open(path, "reveal")`` is answered; and
    only a review copy is a plain-open kind."""
    engagement = sample_engagement(capsys, scratch_root, tmp_path)
    assert scan(capsys, engagement)[0] == 0
    state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[1]
    firm = run(capsys, "firm")[1]
    listed = run(capsys, "list")[1]
    assert listed["vocab"]["path_kinds"] == api.PATH_KINDS
    keys = [(state, row["shown_key"]) for row in state["index"] if row.get("shown_key")]
    keys += [(state, row["open_keys"][0]) for row in state["index"] if row.get("open_keys")]
    keys += [(firm, row["open_key"]) for row in firm["files"] if row["open_key"]]
    assert {key.split(" ")[0] for _reply, key in keys} == {"review_copy", "shown_copy", "filed_copy"}
    for reply, key in keys:
        assert key in reply["paths"], key
        assert Path(reply["paths"][key]).is_file(), key
        assert api.PATH_KINDS[key.split(" ")[0]] in ("file", "reveal"), key
    assert [word for word, kind in api.PATH_KINDS.items() if kind == "file" and word.endswith("_copy")] == ["review_copy"]
    assert not any(one["paused"] for one in firm["returns"])


def test_the_move_schedule_question_carries_its_warning(tmp_path):
    """Final review A finding 1 (SPEC 11.2, P77): the confirm before the
    schedule is moved here says the question and, under it, the warning, each
    with the other computer's name filled in - never the bare question."""
    setup = """
      const vocab = { schedule: { move_confirm: "Move Schedule Here From {host}?", move_warning: "Only If {host} Is Retired" } };
    """
    ran = run_shell(["moveScheduleQuestion"], setup, 'return moveScheduleQuestion("front-desk");', tmp_path, "app.js")
    assert ran == "Move Schedule Here From front-desk?\n\nOnly If front-desk Is Retired"


def test_a_failed_sort_says_a_short_approved_reason_and_never_a_path(tmp_path):
    """Rulings 25 and 29: the return's banner says "Sort Failed" and a short
    reason chosen by the kind of failure the pass reported, from the API's
    vocabulary - at most five words in all, Title Case, no path. A kind the
    engine does not tell apart is "Unexpected Error"."""
    from tests.test_api import title_case

    words = api._vocab()["scan"]
    setup = ("const fill = (p, v) => p.replace(/\\{(\\w+)\\}/g, (_, k) => v[k] ?? '');\n"
             f"const vocab = {{ scan: {json.dumps(words)} }};")
    probe = """
      const kinds = ["lock-held", "household-paused", "client-folder-missing", "folder-missing", "crashed:OSError", "", "unsorted-files"];
      return kinds.map((code) => scanFailed({ code, error: "C:/Clients/Smith Family: it broke" }));
    """
    said = run_shell(["scanFailed"], setup, probe, tmp_path, "app.js")
    assert said == ["Sort Failed: Another PC Sorting", "Sort Failed: Two Years Open", "Sort Failed: Folder Not Found",
                    "Sort Failed: Folder Not Found", "Sort Failed: Unexpected Error", "Sort Failed: Unexpected Error",
                    "Sort Failed: Unexpected Error"]
    for line in said:
        assert len(line.split()) <= 5 and line == title_case(line) and "/" not in line and "Smith" not in line, line
    assert set(words["reasons"]) == {"lock-held", "household-paused", "client-folder-missing", "folder-missing", "other"}


def test_a_sort_asked_for_an_inactive_return_says_why_nothing_was_done(tmp_path, monkeypatch, capsys):
    """P134 (the Windows check, "Added after the check"): a household page
    sorts through its first return, which on the office PC was the prior
    year's, set inactive by a person - and the banner read a bare "Nothing
    Done". With the real engine through ``run-now`` on a household with an
    inactive return, the page's own ``scanSummary`` now says why, in the
    screen's approved word; a kind with no word still says "Nothing Done"
    (P117). Every skip word is Title Case and five words at most in all."""
    from tests.passes import _run_now, build_engagement, edit_details
    from tests.samples import build_samples
    from tests.test_api import title_case
    from tracker.layout import household_of

    samples = tmp_path / "samples"
    samples.mkdir()
    build_samples(samples)
    root = tmp_path / "root"
    current = build_engagement(root, samples, name="Smith TY2025")
    prior = build_engagement(root, samples, name="Smith TY2024", drops=())
    edit_details(prior.path, active=False)
    runs = _run_now(root, household_of(current.path), monkeypatch, capsys)[1][-1]["runs"]
    [skipped] = [one for one in runs if one["path"] == str(prior.path)]
    assert skipped["skipped"] and skipped["code"] == "inactive" and not skipped["error"]

    words = api._vocab()["scan"]
    setup = ("const fill = (p, v) => p.replace(/\\{(\\w+)\\}/g, (_, k) => v[k] ?? '');\n"
             f"const vocab = {{ scan: {json.dumps(words)} }};")
    probe = f"""
      const run = {json.dumps(skipped)};
      return [scanSummary(run, [], '').text, scanSummary({{ ...run, code: "rolled-forward" }}, [], '').text,
              scanSummary({{ ...run, code: "no-room" }}, [], '').text, scanSummary({{ ...run, code: "brand-new" }}, [], '').text];
    """
    said = run_shell(["scanFailed", "scanSummary"], setup, probe, tmp_path, "app.js")
    assert said == ["Nothing Done: Inactive.", "Nothing Done: Rolled Forward.", "Nothing Done: Names Too Long.",
                    "Nothing Done"]
    for line in said:
        assert len(line.split()) <= 5 and title_case(line) == line, line
    assert set(words["skipped"]) == {"inactive", "rolled-forward", "no-room"}
    screen = api._vocab()["screen"]
    assert (words["skipped"]["inactive"], words["skipped"]["rolled-forward"]) == (screen["inactive"], screen["rolled"])


SORT_ANSWERS = r"""
  let shellRoute = { level: "overview" }, synced = [];
  const returns = { "r25": { household: "h1" }, "r24": { household: "h1" }, "o25": { household: "h2" } };
  function shellReturn(path) { return returns[path] || null; }
  function syncNotices(prefix, wanted) { synced.push([prefix, wanted.map((one) => one.failure.sentence)]); }
  const sortAnswers = new Map(), keyedNotices = new Map();
  function clearNotice(key) { keyedNotices.delete(key); }
  const shownAt = (route) => { shellRoute = route; showSortAnswers(); return synced[synced.length - 1][1]; };
"""
SORT_ANSWER_FUNCTIONS = ["keepSortAnswer", "sortKeyPath", "householdOnScreen", "showSortAnswers", "forgetSortLine",
                         "forgetSortAnswers"]


def test_a_sorts_answer_shows_only_on_its_own_clients_pages(tmp_path):
    """P131 (the Windows check's F3; rulings 20 and 28, SPEC-shell 3.5): a
    return's "Sort Failed: {reason}" used to be a window-wide notice, so it
    showed on Overview and Clients too. It is kept under the return it was
    asked for and shown only on that household's pages; a line a person
    dismissed does not come back on the next visit."""
    probe = """
      shellRoute = { level: "return", ret: "r25" };
      keepSortAnswer(["r25", "r24"], "r25", [{ sentence: "Sort Failed: Folder Not Found", kind: "failed" }]);
      const out = { onReturn: synced[synced.length - 1] };
      out.overview = shownAt({ level: "overview" });
      out.clients = shownAt({ level: "clients" });
      out.household = shownAt({ level: "household", household: "h1" });
      out.year = shownAt({ level: "year", household: "h1", year: 2025 });
      out.sibling = shownAt({ level: "return", ret: "r24" });
      out.otherClient = shownAt({ level: "return", ret: "o25" });
      forgetSortLine("sort:" + JSON.stringify(["r25", 0]));
      out.afterDismiss = shownAt({ level: "return", ret: "r25" });
      out.left = [...sortAnswers.keys()];
      return out;
    """
    out = run_shell(SORT_ANSWER_FUNCTIONS, SORT_ANSWERS, probe, tmp_path, "app.js")
    failed = ["Sort Failed: Folder Not Found"]
    assert out["onReturn"] == ["sort", failed]
    assert out["overview"] == [] and out["clients"] == [] and out["otherClient"] == []
    assert out["household"] == failed and out["year"] == failed and out["sibling"] == failed
    assert out["afterDismiss"] == [] and out["left"] == []


def test_a_later_sort_or_f5_takes_a_sorts_answer_away(tmp_path):
    """P131: the next Sort of the household replaces every answer of the
    returns it ran (a good one says nothing), and F5 forgets them all - the
    page is read again from the record, which the app's own Sort does not
    write. It used to go only when the app restarted."""
    probe = """
      shellRoute = { level: "return", ret: "r25" };
      const bad = [{ sentence: "Sort Failed: Folder Not Found", kind: "failed" }];
      keepSortAnswer(["r25", "r24"], "r25", bad);
      const out = { failed: shownAt(shellRoute) };
      keepSortAnswer(["r25", "r24"], "r24", []);          // asked from the household page, all well
      out.afterGoodSort = shownAt(shellRoute);
      keepSortAnswer(["r25"], "r25", bad);
      forgetSortAnswers();
      out.afterF5 = synced[synced.length - 1];
      out.left = sortAnswers.size;
      return out;
    """
    out = run_shell(SORT_ANSWER_FUNCTIONS, SORT_ANSWERS, probe, tmp_path, "app.js")
    assert out["failed"] == ["Sort Failed: Folder Not Found"]
    assert out["afterGoodSort"] == [] and out["afterF5"] == ["sort", []] and out["left"] == 0


def test_a_sorts_answer_is_never_a_window_wide_notice_and_f5_forgets_it():
    """P131, wired: ``passEnded`` keeps its answer through ``keepSortAnswer``
    (no ``outcome`` or ``notice`` of its own), every route change re-shows the
    answers, a dismissed line is forgotten, and F5 forgets them all."""
    ended = js_function("passEnded", "app.js")
    assert "outcome(" not in ended and "notice(" not in ended
    assert ended.count("keepSortAnswer(ran, asked, answer);") == 2
    assert "showSortAnswers();" in js_function("appRouteChanged", "app.js")
    assert "forgetSortLine(entry.key);" in read("app.js")
    assert js_function("shellRefresh").split("\n")[1].strip().startswith("forgetSortAnswers();")
    assert "function forgetSortAnswers() {}" in (REPO / "pilot" / "harness" / "app-stub.js").read_text(encoding="utf-8")


def test_create_return_goes_to_the_new_returns_page(tmp_path):
    """P132 (the Windows check's F4; the review's S3): after Create Return the
    page stayed on the route it was opened from while the new return's state
    arrived, so a return page drew nothing until F5. ``createEngagement``,
    lifted with fakes and started on another household's return, now goes to
    the new return's page - after the dialog closed and the list that names it
    was adopted - and says the return was created after that."""
    setup = js_function("pagesRoute", "pages.js") + r"""
      const said = [];
      let templates = [], customItems = [{ document: "W-2" }], wizardPeople = [], selectedForm = "1040";
      let engagements = [{ path: "/h1/2025/old", household: "/h1", year: 2025 }];
      const nodes = { "tmpl-list": { querySelectorAll: () => [] }, "ne-create": { disabled: false },
        "ne-name": { value: "" }, "ne-client": { value: "" }, "ne-due": { value: "" }, "ne-year": { value: "2024" },
        "ne-note": { textContent: "", classList: { remove() {} } } };
      const $ = (id) => nodes[id];
      const vocab = { household: { return_created: "{label} created ({n})" } };
      const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
      function householdSpec() { return { household_path: "/h2" }; }
      function personSpec(p) { return p; }
      function toastWord() { said.push("toastWord"); }
      function toast() { said.push("toast"); }
      function closeDialog(id) { said.push(["closeDialog", id]); }
      function adoptList() { engagements.push({ path: "/h2/2024/new", household: "/h2", year: 2024 }); said.push("adoptList"); }
      function shellReturn(path) { return engagements.find((one) => one.path === path) || null; }
      function select(path) { said.push(["select", path]); return 7; }
      function renderFor(view) { said.push(["renderFor", view]); return true; }
      function shellGo(route) { said.push(["shellGo", route]); return Promise.resolve(); }
      function outcome(text, cls) { said.push(["outcome", text, cls]); }
      function failed(err) { said.push(["failed", String(err)]); }
      function failureSentence(err) { return String(err); }
      async function call() { return { list: {}, created: "1040 - New", state: { paths: { engagement: "/h2/2024/new" } } }; }
    """
    out = run_shell(["createEngagement"], setup, "return createEngagement().then(() => said);", tmp_path, "app.js")
    steps = [one if isinstance(one, str) else one[0] for one in out]
    assert ["shellGo", {"level": "return", "household": "/h2", "year": 2024, "ret": "/h2/2024/new"}] in out, out
    assert steps.index("closeDialog") < steps.index("adoptList") < steps.index("shellGo") < steps.index("outcome"), out
    assert "failed" not in steps


SORT_NOTICES = r"""
  const notices = [], keyedNotices = new Map(), sortAnswers = new Map(), locks = [];
  let shellRoute = { level: "return", ret: "r25" };
  const returns = { r25: { household: "h1" }, r24: { household: "h1" } };
  function shellReturn(path) { return returns[path] || null; }
  const el = () => ({ removed: false, remove() { this.removed = true; }, contains: () => false });
  const document = { activeElement: null };
  const $ = () => ({ append() {} });
  function drawNotice() {}
  function outlineRefused() {}
  function showLock(lock) { locks.push(lock); }
  const shown = () => notices.map((one) => one.sentence);
  const press = (entry) => { dismissNotice(entry); forgetSortLine(entry.key); };   // the notice's cross or Retry
"""
SORT_NOTICE_FUNCTIONS = ["notice", "keyedNotice", "clearNotice", "syncNotices", "noticeFocusAfter", "dismissNotice"] + SORT_ANSWER_FUNCTIONS


def test_a_sort_that_fails_the_same_way_again_is_said_again(tmp_path):
    """The review's M1: a keyed notice stays silent for a sentence its key
    already holds, even once dismissed - so after Retry (or the cross) a Sort
    that failed the same way again showed nothing. With the real notice
    functions: fail, press Retry, fail again - the failure is back; a failure
    not yet dismissed is not doubled; a good Sort takes it away."""
    probe = """
      const failed = () => [{ sentence: "Sort Failed: Folder Not Found", kind: "failed" }];
      const out = [];
      keepSortAnswer(["r25", "r24"], "r25", failed()); out.push(shown());
      press(notices[0]); out.push(shown());
      keepSortAnswer(["r25", "r24"], "r25", failed()); out.push(shown());
      keepSortAnswer(["r25", "r24"], "r25", failed()); out.push(shown());
      keepSortAnswer(["r25", "r24"], "r24", []); out.push(shown());
      return out;
    """
    out = run_shell(SORT_NOTICE_FUNCTIONS, SORT_NOTICES, probe, tmp_path, "app.js")
    failed = ["Sort Failed: Folder Not Found"]
    assert out == [failed, [], failed, failed, []]


def test_a_locked_sort_still_shows_its_lock_and_outlines_its_row(tmp_path):
    """The review's S1: the pass-level failure is kept whole, so a locked
    pass's ``lock`` reaches ``showLock`` and its ``identifier`` outlines the
    row, as ``notice()`` did before a Sort's answer was kept per return."""
    probe = """
      keepSortAnswer(["r25"], "r25", [{ sentence: "In Use on FRONT-DESK", kind: "locked", identifier: "R01",
        lock: { host: "FRONT-DESK" }, retry: () => 0 }]);
      return { shown: shown(), locks, identifier: notices[0].identifier, retry: typeof notices[0].retry };
    """
    out = run_shell(SORT_NOTICE_FUNCTIONS, SORT_NOTICES, probe, tmp_path, "app.js")
    assert out == {"shown": ["In Use on FRONT-DESK"], "locks": [{"host": "FRONT-DESK"}], "identifier": "R01",
                   "retry": "function"}


def test_the_sorts_answer_is_built_line_by_line_from_the_pass(tmp_path):
    """The review's S4: ``passEnded``, lifted with the real ``scanSummary``.
    A pass that failed as a whole is one line, whole (its lock kept), with
    Retry; a skip names its reason; a summary for a return no longer shown
    carries its label on the first line only; a good Sort says nothing."""
    words = api._vocab()["scan"]
    setup = ("const fill = (p, v) => p.replace(/\\{(\\w+)\\}/g, (_, k) => v[k] ?? '');\n"
             f"const vocab = {{ scan: {json.dumps(words)} }};\n") + r"""
      let scanning = null, active = "r25", viewGeneration = 1, kept = [];
      function scanDone() {}
      function shellWriteLanded() {}
      function shellAskFirmNow() {}
      function warningNotices() {}
      function adoptList() {}
      function withEng(c) { return [c]; }
      function renderFor() { return true; }
      function failed() {}
      function showReturn() {}
      function runScan() {}
      function shellReturn() { return null; }
      async function call(args) { return args[0] === "state" ? { summary: { line: "" } } : {}; }
      function keepSortAnswer(ran, asked, answer) {
        kept.push({ ran, asked, answer: answer.map((one) => ({ ...one, retry: typeof one.retry })) }); }
      const run = (over) => ({ path: "r25", label: "Smith 2025", ok: true, error: "", code: "", skipped: "", filed: 1,
        review: 0, waiting: 0, file_errors: [], warnings: [], cancelled: false, ...over });
      const end = async (asked, reply) => { scanning = { asked }; await passEnded({ reply }); return kept[kept.length - 1]; };
    """
    probe = r"""
      const out = {};
      out.whole = await end("r25", { error: "In use", failure: { sentence: "In Use on FRONT-DESK", kind: "locked",
        lock: { host: "FRONT-DESK" }, identifier: null } });
      out.skipped = await end("r25", { runs: [run({ skipped: "inactive", code: "inactive", ok: false, filed: 0 })] });
      out.away = await end("r24", { runs: [run({ path: "r24", label: "Smith 2024", error: "gone", code: "folder-missing" }),
        run({ path: "r25", error: "gone", code: "folder-missing" })] });
      out.good = await end("r25", { runs: [run({})] });
      return out;
    """
    out = run_shell(["passEnded", "scanSummary", "scanFailed", "sortReturnSaid"], setup, "return (async () => {" + probe + "})();",
                    tmp_path, "app.js")
    assert out["whole"] == {"ran": [], "asked": "r25", "answer": [
        {"sentence": "In Use on FRONT-DESK", "kind": "locked", "lock": {"host": "FRONT-DESK"}, "identifier": None,
         "retry": "function"}]}
    assert out["skipped"]["answer"] == [{"sentence": "Nothing Done: Inactive.", "kind": "warning", "retry": "undefined"}]
    assert [one["sentence"] for one in out["away"]["answer"]] == [
        "Smith 2024: Sort Failed: Folder Not Found", "\u2022 Smith 2025: Sort Failed: Folder Not Found"], "P199: its bullet stays"
    assert out["away"]["ran"] == ["r24", "r25"] and out["away"]["answer"][0]["kind"] == "failed"
    assert out["good"] == {"ran": ["r25"], "asked": "r25", "answer": []}


def test_a_household_page_sorts_through_a_working_return(tmp_path):
    """The review's M2 (the "Added after the check" item): a household page
    sorted through its first return, the inactive 2024 one, and reported
    that nothing was done though the same pass sorted 2025. It now reads the
    active return that has not rolled forward, from the list's household;
    a return a person chose is still the one read."""
    setup = r"""
      let shellRoute = { level: "household", household: "h1" }, lastState = null, active = "", read = [];
      let shellPageBusy = false, shellPageFailed = false;
      const own = [{ path: "r24", household: "h1" }, { path: "r25", household: "h1" }];
      function shellOwnReturns() { return own; }
      function shellHousehold() { return { returns: [{ path: "r24", active: false, superseded_by: "" },
                                                      { path: "r25", active: true, superseded_by: "" }] }; }
      function showReturn(path) { read.push(path); return Promise.resolve(true); }
      function shellDraw() {}
    """
    probe = """
      return shellOpenState().then(() => { active = "r24"; return shellOpenState(); }).then(() => read);
    """
    assert run_shell(["shellOpenState"], setup, probe, tmp_path) == ["r25", "r24"]


def test_a_failed_or_locked_household_sort_draws_no_engine_sentence_and_no_path(tmp_path, monkeypatch, capsys):
    """Final re-review NEW 1 (rulings 25 and 29), with the real engine: a
    household of two returns is sorted through ``run-now``, once with its
    client folder gone (both fail) and once with one return's lock held by a
    live pass (both are skipped). The final line's runs go to the page's own
    ``scanSummary``, and every line it draws is "Sort Failed" with the short
    approved reason, or "Nothing Done: Another PC Sorting" - never the
    engine's long sentence, and never a folder path, for the asked return or
    for the household's other return."""

    from tests.passes import _run_now, build_engagement
    from tests.samples import build_samples
    from tests.test_api import title_case
    from tracker.layout import client_household_dir, household_of
    from tracker.locking import LOCK_FILENAME

    samples = tmp_path / "samples"
    samples.mkdir()
    build_samples(samples)
    root = tmp_path / "root"
    first = build_engagement(root, samples, name="Smith TY2025")
    second = build_engagement(root, samples, name="Other TY2025", drops=())
    household = household_of(first.path)
    _run_now(root, household, monkeypatch, capsys)              # it has had its client folder
    (second.path / LOCK_FILENAME).write_text(f"pid={os.getpid()}", encoding="utf-8")
    held = _run_now(root, household, monkeypatch, capsys)[1][-1]["runs"]
    (second.path / LOCK_FILENAME).unlink()
    shutil.rmtree(client_household_dir(root, household.name))
    failed = _run_now(root, household, monkeypatch, capsys)[1][-1]["runs"]
    assert {one["code"] for one in held} == {"lock-held"} and {one["code"] for one in failed} == {"client-folder-missing"}
    assert all(one["skipped"] for one in held) and all(one["error"] for one in failed), "the engine did say its long sentences"

    words = api._vocab()["scan"]
    setup = ("const fill = (p, v) => p.replace(/\\{(\\w+)\\}/g, (_, k) => v[k] ?? '');\n"
             f"const vocab = {{ scan: {json.dumps(words)} }};\nfunction shellReturn() {{ return null; }}")
    probe = "return scanSummary(runs[0], runs.slice(1), '').text;"
    for name, runs in (("lock held", held), ("client folder gone", failed)):
        text = run_shell(["scanFailed", "scanSummary", "sortReturnSaid"], f"{setup}\nconst runs = {json.dumps(runs)};", probe,
                         tmp_path, "app.js")
        lines = text.split("\n")
        assert len(lines) == 2, (name, text)
        for line in lines:
            assert title_case(line) == line and not re.search(r"[\\/`]|Clients|missing|another run|lock", line), (name, line)
        assert lines[0] in ("Sort Failed: Folder Not Found", "Nothing Done: Another PC Sorting."), lines[0]
        assert lines[1].endswith(("Sort Failed: Folder Not Found", "Another PC Sorting")), lines[1]
        assert lines[1].startswith("\u2022 Test Household 2025 "), lines[1]


def test_the_app_starts_only_after_every_script_has_loaded(tmp_path):
    """Final review B, finding 1: app.js loads before pages.js, sheet.js and
    shell.js, and its bootstrap draws through them, so a quick first reply
    used to hit a name that did not exist yet ("The App Hit an Error"). The
    start waits for DOMContentLoaded while the document is still loading, and
    runs at once when it has finished."""
    setup = """
      let listeners = {}, started = 0;
      const document = { readyState: "loading", addEventListener: (name, fn) => { listeners[name] = fn; } };
      const bootstrap = () => { started += 1; };
    """
    probe = """
      startWhenLoaded(bootstrap);
      const before = started;
      listeners.DOMContentLoaded();
      const loading = [before, started];
      document.readyState = "complete";
      startWhenLoaded(bootstrap);
      return { loading, after: started };
    """
    assert run_shell(["startWhenLoaded"], setup, probe, tmp_path, "app.js") == {"loading": [0, 1], "after": 2}
    html = read("index.html")
    scripts = re.findall(r'<script src="([^"]+)"></script>', html)
    assert scripts.index("app.js") < scripts.index("shell.js"), "the order is why the start must wait"
    js = read("app.js")
    assert js.rstrip().endswith("startWhenLoaded(bootstrap);") and not re.search(r"^bootstrap\(\);", js, re.M)


def test_a_sort_is_never_sent_without_a_return_chosen(tmp_path):
    """Final review C, C2 (ruling 28): on a firm page nothing can send the
    pass with no engagement - the engine would answer in the command line's
    words (a flag, over five). runScan itself refuses when no return is
    active, so a Retry or a key cannot get round the greyed icon."""
    setup = """
      let active = null, scanning = null; const sent = [];
      const vocab = { pass_command: "run-now" };
      const withEng = (name) => (active ? [name, "--engagement", active] : [name]);
      const shellChanged = () => {}; const drawProgress = () => {}; const scanDone = () => {}; const failed = () => {};
      const call = async (args) => { sent.push(args); return { pass: 1 }; };
    """
    probe = """
      await runScan();
      const none = sent.length;
      active = "R1";
      await runScan();
      return { none, sent };
    """
    ran = run_shell(["runScan"], setup, "return (async () => { " + probe + " })();", tmp_path, "app.js")
    assert ran == {"none": 0, "sent": [["run-now", "--engagement", "R1"]]}


def test_a_return_or_household_row_wraps_so_its_year_and_its_paused_words_are_never_cut():
    """Rulings 21 and 27 (final review B, findings 3 and 4): the name
    and status of a return's or household's row (and of a row with a marker)
    wrap instead of ending in an ellipsis, on the token grid; a file's name
    keeps its ellipsis. The rendered claim (the year visible at 1100px on
    every page) is interact.mjs's."""
    wrapped = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            wrapped.setdefault(" ".join(part.split()), dict(declarations(body)))   # the first rule of a selector, not a media block after it
    for cell in (".row-wrap .row-name", ".row-wrap .row-status"):
        rule = wrapped[cell]
        assert rule["white-space"] == "normal" and rule["text-overflow"] == "clip" and rule["overflow-wrap"] == "break-word", cell
    assert wrapped[".row.row-wrap:not(.hidden)"]["padding-block"] == "var(--sp-1)"
    assert wrapped[".row-name"]["text-overflow"] == "ellipsis", "a file's name still ends in an ellipsis"
    pages = read("pages.js")
    assert 'const wraps = !place && Boolean(spec.mark || (spec.nameLink && spec.nameLink.kind !== "file"));' in pages   # a row of a long list is one line (P279)
    assert '" row-wrap"' in pages


def test_a_needs_review_group_that_cannot_be_built_is_named_by_its_return_and_never_its_folder(tmp_path):
    """Final review B, finding 5 (P63): if a group's link words are missing
    (an app and engine that disagree), the notice that names it uses the
    return's label, not the folder path; the notices are scanned for a path as
    the pages are."""
    pages_text = read("pages.js")
    functions = re.findall(r"^function (\w+)\(", pages_text, flags=re.M) + ["h", "icon", "screenWords", "folderName"]
    ran = run_pages_dom(r"""
      const known = "C:\\Clients\\J Park & Associates\\Smith Family\\2025\\1040 - John & Jane Smith";
      shellReturn = (path) => (path === known ? { return_name: "1040 - John & Jane Smith", household: "Smith Family", year: 2025 } : null);
      households = [{ name: "Smith Family", path: "C:\\Clients\\J Park & Associates\\Smith Family" }];
      shellFirmData = { returns: [{ path: known, household: "Smith Family", year: 2025, counts: { needs_you: 1, waiting: 0, received: 0, set_aside: 0 }, files: 1, oldest: "2026-03-03", due: null,
                                    draft: { ready: false, stage: 0, held: 0, drafted: null }, problem: "" }],
        files: [{ return: known, year: 2025, name: "scan0012.pdf", handle: "h1", code: "unmatched", received: "2026-03-03", suggestion: "", open_key: "" }],
        paths: {}, totals: { need: 1, waiting: 0, complete: 0, files: 1, drafts: 0 }, next_sort: "" };
      settle("needs_review");
      delete vocab.screen.navigate_return;            // the group's heading link cannot be built
      pagesBroken = []; pagesUid = 0;
      const nodes = pagesNeedsReview();
      notices.length = 0;

      pagesReportBroken();
      return { drew: nodes.length, broken: pagesBroken.map((one) => one.name), notices: notices.flatMap(([, list]) => list.map((one) => one[1])) };
    """, tmp_path, setup=ENGINE_BRIDGE + """
      Object.assign(vocab.screen, { navigate_client: "Navigate to Household", empty: { needs_review: "Nothing needs review", next_sort: "Next sort {time}" } });
      vocab.shell = { page_error: "The App Hit an Error" }; vocab.notices = { about: "{label}: {sentence}" };
      vocab.reasons = { unmatched: "No Match" };
    """, functions=functions)
    assert ran["broken"] == ["1040 - John & Jane Smith"], ran
    assert ran["notices"] == ["1040 - John & Jane Smith: The App Hit an Error"]
    assert not [text for text in ran["notices"] if re.search(r"[\\/]", text)], "a notice named a folder path"


# ── the lists: column headers, order and width (pilot SPEC-lists) ────────


def test_the_four_firm_lists_draw_a_header_row_of_buttons_in_the_rows_columns(tmp_path):
    """SPEC-lists 1-3: Overview, Needs Review, Reminders and Clients each draw
    one header row - a table of one row of column headers, each a button with
    the vocabulary's word and the tooltip "Sort by {Column}" (P180) - and Clients'
    empty end column has an empty header that orders nothing."""
    ran = run_lists("""
      const out = {};
      for (const level of ["overview", "needs-review", "reminders", "clients"]) {
        tips.length = 0;
        const page = draw(level);
        const tables = page.find((one) => one.attrs.role === "table");
        out[level] = { tables: tables.length, label: tables[0].attrs["aria-label"], rows: tables[0].find((one) => one.attrs.role === "row").length,
                       cells: tables[0].find((one) => one.attrs.role === "columnheader").length,
                       words: tables[0].find((one) => one.tag === "button").map((one) => one.textContent),
                       tips: tips.filter(([cls]) => cls === "col-head").map(([, words]) => words), sorts: sorts(page),
                       grips: tables[0].byClass("col-grip").length };
      }
      return out;
    """, tmp_path)
    assert ran["overview"]["words"] == ["Tax Year", "Taxpayer", "Form Type", "Status", "Date"], "Jason's order (P194, P195)"
    assert ran["needs-review"]["words"] == ["File", "Suggestion", "Reason", "Received"]
    assert ran["reminders"]["words"] == ["Tax Year", "Taxpayer", "Form Type", "Stage", "Drafted"], "the same columns, then its own (P195)"
    assert ran["clients"]["words"] == ["Household Name", "Returns", "Status"], "the Households end column is always empty (P153; P196: Household Name)"
    for level, one in ran.items():
        width = 5 if level in ("overview", "reminders") else 4
        assert one["tables"] == 1 and one["rows"] == 1 and one["cells"] == width and one["grips"] == width, level
        assert one["tips"] == [f"Sort by {word}" for word in one["words"]], level
        assert set(one["sorts"]) <= {"none", ""}, "the usual order: no header orders the list"
    assert ran["needs-review"]["label"] == "Needs Review" and ran["overview"]["label"] == "Overview"


def test_a_header_orders_its_list_then_reverses_then_returns_to_the_usual_order(tmp_path):
    """SPEC-lists 3: the first press orders by the column (aria-sort
    ascending), the second reverses it (descending), the third restores the
    usual order; the order is kept when the page is drawn again while the app
    is open."""
    ran = run_lists("""
      const usual = names(draw("overview"));
      pagesOrderBy("overview", "taxpayer"); const first = [names(box), sorts(box)];
      draw("clients"); const kept = names(draw("overview"));
      pagesOrderBy("overview", "taxpayer"); const second = [names(box), sorts(box)];
      pagesOrderBy("overview", "taxpayer"); const third = [names(box), sorts(box)];
      return { usual, first, kept, second, third };
    """, tmp_path)
    assert ran["usual"] == ["Echo", "Bravo", "Alpha", "Charlie", "Delta"]
    assert ran["first"][0] == ["Alpha", "Bravo", "Charlie", "Delta", "Echo"]
    assert ran["first"][1] == ["none", "ascending", "none", "none", "none"]
    assert ran["kept"] == ran["first"][0], "a list keeps its order while the app is open"
    assert ran["second"][0] == list(reversed(ran["first"][0])) and ran["second"][1][1] == "descending"
    assert ran["third"] == [ran["usual"], ["none", "none", "none", "none", "none"]]


def test_status_orders_by_urgency_not_alphabetically(tmp_path):
    """SPEC-lists 3: a return that cannot be read first, then what needs a
    person (the larger count first), then what waits on the client; on
    Reminders, Held first and then the later stage."""
    ran = run_lists("""
      draw("overview"); pagesOrderBy("overview", "status"); const overview = names(box);
      pagesOrderBy("overview", "status"); const back = names(box);
      draw("reminders"); pagesOrderBy("reminders", "status");
      const reminders = box.byClass("row").map((row) => row.byClass("row-status")[0].textContent);
      return { overview, back, reminders };
    """, tmp_path)
    assert ran["overview"] == ["Echo", "Bravo", "Alpha", "Delta", "Charlie"]
    assert ran["back"] == list(reversed(ran["overview"]))
    assert ran["reminders"] == ["Held", "Final Notice", "Heads Up"]


def test_dates_order_by_the_iso_date_and_blanks_go_last_both_ways(tmp_path):
    ran = run_lists("""
      draw("overview"); pagesOrderBy("overview", "end"); const up = names(box);
      pagesOrderBy("overview", "end"); const down = names(box);
      return { up, down };
    """, tmp_path)
    assert ran["up"] == ["Bravo", "Alpha", "Charlie", "Echo", "Delta"]
    assert ran["down"] == ["Charlie", "Alpha", "Bravo", "Echo", "Delta"]


def test_needs_review_orders_files_in_each_group_and_groups_follow_their_first_file(tmp_path):
    ran = run_lists("""
      const titles = (page) => page.byClass("group-title").map((one) => one.byClass("row-link")[0].textContent);
      const usual = [titles(draw("needs-review")), names(box)];
      pagesOrderBy("needs_review", "end"); pagesOrderBy("needs_review", "end");
      const newest = [titles(box), names(box)];
      pagesOrderBy("needs_review", "status");
      const reason = [titles(box), names(box)];
      return { usual, newest, reason };
    """, tmp_path)
    assert ran["usual"] == [["Bravo", "Alpha"], ["z.pdf", "b.pdf", "a.pdf"]]
    assert ran["newest"] == [["Alpha", "Bravo"], ["a.pdf", "b.pdf", "z.pdf"]]
    assert ran["reason"] == [["Alpha", "Bravo"], ["a.pdf", "b.pdf", "z.pdf"]]


def test_only_the_header_tooltip_says_sort_and_always_by_its_column():
    """P138 and Jason's answer to Q1 (P180): a header's tooltip reads "Sort by
    {Column}" - the "by {Column}" keeps it apart from the filing pass's Sort
    Now - and no column word, width line or menu item of this change says
    Sort; pages.js types none of them (every word is the vocabulary's)."""
    for key, words in api.SCREEN["columns"].items():
        assert "sort" not in words.lower() or key == "sort_by", key
    assert "sort" not in api.MENU["reset_columns"].lower()
    assert api.SCREEN["columns"]["sort_by"] == "Sort by {column}"
    heads = js_function("pagesColumnHeads", "pages.js")
    assert not re.findall(r'"(?:Sort|Order|Return|Client|Status|Date)\b', heads), "a header word typed in pages.js"


def test_a_column_width_is_clamped_saved_and_reset(tmp_path):
    """SPEC-lists 4: a width lands within its column's limits, is kept on this
    PC across a restart, and View › Reset Column Widths forgets every list's.
    Storage that holds something unreadable leaves the usual widths."""
    ran = run_lists("""
      const props = () => ({ ...box.style.props });
      pagesSetWidth("overview", "status", 5000); pagesSetWidth("overview", "year", 10); pagesSaveWidths();
      const set = props(); const stored = JSON.parse(window.localStorage.getItem("tracker.columns"));
      pagesWidths = null; box.style.props = {}; pagesApplyWidths(box, "overview"); const again = props();
      pagesApplyWidths(box, ""); const plain = props();
      pagesApplyWidths(box, "overview"); pagesResetWidths(); const reset = [props(), window.localStorage.getItem("tracker.columns")];
      window.localStorage.setItem("tracker.columns", "not json"); pagesWidths = null; pagesApplyWidths(box, "overview"); const junk = props();
      return { set, stored, again, plain, reset, junk };
    """, tmp_path, extra="""
      const window = { localStorage: { data: {}, getItem(k) { return k in this.data ? this.data[k] : null; }, setItem(k, v) { this.data[k] = String(v); },
                                       removeItem(k) { delete this.data[k]; } } };
    """)
    assert ran["set"] == {"--size-col-status": "320px", "--size-col-year": "64px"}
    assert ran["stored"] == {"overview": {"status": 320, "year": 64}}
    assert ran["again"] == ran["set"], "kept on this PC across a restart"
    assert ran["plain"] == {} and ran["reset"] == [{}, None] and ran["junk"] == {}


def test_needs_review_moves_width_from_suggestion_to_reason_and_still_fits_1100px(tmp_path):
    """SPEC-lists 4: Needs Review's reasons are the longest status words, so its
    usual Reason column is 200px and its Suggestion 160px - the same sum, so
    the 1100px window still has no sideways scroll; a person's own width wins."""
    ran = run_lists("""
      pagesApplyWidths(box, "needs_review"); const usual = { ...box.style.props };
      pagesSetWidth("needs_review", "status", 240); const held = { ...box.style.props };
      pagesApplyWidths(box, "overview"); const other = { ...box.style.props };
      return { usual, held, other };
    """, tmp_path, extra="const window = { localStorage: { getItem() { return null; }, setItem() {}, removeItem() {} } };")
    assert ran["usual"] == {"--size-col-detail": "160px", "--size-col-status": "200px"}
    assert ran["held"] == {"--size-col-detail": "160px", "--size-col-status": "240px"}
    assert ran["other"] == {}
    light, _dark = root_blocks()
    usual = sum(int(light[f"--size-col-{cell}"].removesuffix("px")) for cell in ("detail", "status"))
    assert usual == 160 + 200, "the list's usual sum is the stylesheet's (856 of 860px at 1100px)"


def test_the_keyboard_resizes_a_focused_header_with_ctrl_shift_arrows_only():
    """SPEC-lists 4, P137: shell.js hands a key on a header to pagesColumnKey,
    which acts on Ctrl+Shift+Left or Right alone (never with Alt), steps 16px
    and says the width in the polite live region; the one keydown listener
    stays app.js's."""
    shell = read("shell.js")
    assert 'e.target.closest(".col-head") && typeof pagesColumnKey === "function") return pagesColumnKey(e) === true;' in shell
    key = js_function("pagesColumnKey", "pages.js")
    assert "!e.ctrlKey || !e.shiftKey || e.altKey" in key and '"ArrowLeft"' in key and '"ArrowRight"' in key
    assert '$("page-say").textContent' in key and "columns.width" in key
    assert "const PAGES_WIDTH_STEP = 16;" in read("pages.js")
    assert '<div id="page-say" class="visually-hidden" role="status" aria-live="polite"></div>' in read("index.html")
    assert "keydown" not in read("pages.js")


def test_the_header_row_and_grips_keep_the_rules_of_the_stylesheet():
    """SPEC-lists 3-4: the header row is the rows' own grid; a list is never
    narrower than its columns (so a widened list scrolls the page area); a
    header shows keyboard focus; High Contrast keeps the header words, rule
    and grips in system colours; no typewriter font."""
    first = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            first.setdefault(" ".join(part.split()), dict(declarations(body)))
    assert first[".col-heads:not(.hidden)"]["grid-template-columns"] == first[".row:not(.hidden)"]["grid-template-columns"]
    assert "var(--size-col-end)" in first[".rows"]["min-width"] and first[".rows"]["min-width"] == first[".col-table"]["min-width"]
    assert first[".col-head:focus-visible"]["outline"] == "2px solid var(--focus)"
    assert first[".col-grip:not(.hidden)"]["cursor"] == "col-resize"
    css = read("shell.css")
    forced = css[css.index("@media (forced-colors: active)"):]
    for rule in (".col-head { color: CanvasText; }", ".col-grip::after { background: CanvasText; }", ".group-count .row-link { color: LinkText; }"):
        assert rule in forced, rule
    assert "monospace" not in css.lower()


def test_file_rows_are_ordinary_weight_and_the_household_beside_a_heading_is_secondary(tmp_path):
    """SPEC-lists 5, P136: a file's own name is a regular-weight link; a
    return's row keeps its weight; the household beside a Needs Review
    heading is the secondary text colour (blue on hover), which is AA text on
    the page and on a hovered row in both themes."""
    ran = run_pages_dom("""
      const file = pagesRow({ name: "a.pdf", detail: "", status: "", tone: "needs", date: "", menu: "file", fileKind: "parked", nameLink: null });
      const linked = pagesRow({ name: "b.pdf", detail: "", status: "", tone: "needs", date: "", menu: "file", nameLink: { kind: "file", key: "k", paths: {} } });
      const ret = pagesRow({ name: "1040 - A (2025)", detail: "", status: "", tone: "needs", date: "", menu: "return", nameLink: { kind: "return", path: "r" } });
      return [file, linked, ret].map((row) => row.classList.contains("row-file"));
    """, tmp_path)
    assert ran == [True, True, False]
    first = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            first.setdefault(" ".join(part.split()), dict(declarations(body)))
    assert first[".row-file .row-name"]["font-weight"] == "var(--fw-regular)"
    assert first[".group-count .row-link"]["color"] == "var(--text-secondary)"
    assert first[".group-count .row-link:hover"]["color"] == "var(--link)"
    for theme in ("light", "dark"):
        assert ratio("--text-secondary", "--bg-page", theme) >= 4.5
        assert ratio("--text-secondary", "--bg-hover", theme) >= 4.5
        assert ratio("--border-input", "--bg-page", theme) >= 3, "the grip line is a control's edge"


# ── lane 4b: the raised lists (pilot SPEC-lists 9-17; P141-P155, P170-P178) ──

#: A practice for the lane 4b probes: linked households, forms, a paused one.
LINKED = r"""
  households = [
    { name: "Alpha", path: "c/Alpha", links: [{ name: "Bravo", path: "c/Bravo", kind: "related" }], returns: [{ form: "1040" }] },
    { name: "Bravo", path: "c/Bravo", links: [{ name: "Alpha", path: "c/Alpha", kind: "related" }, { name: "Gone", path: "", kind: "fed_by" }],
      returns: [{ form: "1065" }] },
    { name: "Charlie", path: "c/Charlie", links: [], returns: [{ form: "" }] },
    { name: "Delta", path: "c/Delta", links: [], returns: [{ form: "1040" }] },
    { name: "Echo", path: "c/Echo", links: [], returns: [{ form: "1041" }] },
  ];
  for (const one of shellFirmData.returns) one.links = (households.find((h) => h.name === one.household) || {}).links || [];
  shellFirmData.returns[0].form = "1040";
"""


def test_a_linked_household_carries_the_violet_link_mark_on_the_four_firm_lists(tmp_path):
    """P141, P171: beside the household's name on Overview (Client), Needs
    Review (the household under each return), Reminders (Client) and Clients
    (Client Name); in a row list it is no Tab stop and the row's description
    says Linked Households; on Needs Review it is an ordinary button."""
    ran = run_lists("""
      const out = {};
      for (const level of ["overview", "needs-review", "reminders", "clients"]) {
        const page = draw(level);
        const marks = page.byClass("link-mark");
        out[level] = { marks: marks.length, tabindex: marks.map((m) => m.attrs.tabindex || ""), names: marks.map((m) => m.attrs["aria-label"]),
                       described: page.byClass("row").filter((r) => r.byClass("link-mark").length).map((r) => r.attrs["aria-description"]) };
      }
      return out;
    """, tmp_path, LINKED)
    assert ran["overview"]["marks"] == 2 and set(ran["overview"]["tabindex"]) == {"-1"}
    assert all(one.endswith("Linked Households") for one in ran["overview"]["described"])
    assert ran["clients"]["marks"] == 2 and ran["reminders"]["marks"] == 2
    assert ran["needs-review"]["marks"] == 2 and set(ran["needs-review"]["tabindex"]) == {""}, "a heading's mark is a Tab stop"
    assert {name for one in ran.values() for name in one["names"]} == {"Linked Households"}
    css = read("shell.css")
    assert ".link-mark:not(.hidden) {" in css and "color: var(--st-linked);" in css[css.index(".link-mark:not(.hidden) {"):][:600]
    forced = css[css.index("@media (forced-colors: active)"):]
    assert ".link-mark { color: ButtonText; border-color: CanvasText; }" in forced


def test_the_link_panel_names_each_household_and_its_kind_and_closes_back_to_where_it_opened(tmp_path):
    """P171: the panel lists each linked household with its kind's word, a
    household with a folder as a link to it and one without as text; a
    choice goes to that client; closing returns focus to where it opened."""
    ran = run_pages_dom("""
      Element.prototype.focus = function () { focused.push(this.className || this.attrs.id || this.tag); };
      Element.prototype.remove = function () { this.removed = true; };
      Element.prototype.contains = function () { return false; };
      const focused = []; document.body = new Element("body");
      globalThis.FloatingUIDOM = { computePosition: () => Promise.resolve({ x: 10, y: 20 }), offset: () => 0, flip: () => 0, shift: () => 0 };
      globalThis.TIP_GAP = 4; globalThis.TIP_MARGIN = 8;
      const anchor = new Element("button"); anchor.className = "link-mark"; anchor.isConnected = true;
      pagesShowPanel(anchor, [{ name: "Bravo", path: "c/Bravo", kind: "related" }, { name: "Gone", path: "", kind: "fed_by" },
                              { name: "Delta", path: "c/Delta", kind: "feeds" }], anchor);
      const panel = document.body.kids[0];
      const lines = panel.byClass("link-line").map((l) => [l.kids[0].className, l.kids[0].textContent, l.kids[1].textContent]);
      const open = pagesPanelOpen();
      panel.byClass("link-to")[0].handlers.click[0]();
      const afterChoice = [pagesPanelOpen(), went.slice(-1)[0]];
      pagesShowPanel(anchor, [{ name: "Bravo", path: "c/Bravo", kind: "related" }], anchor);
      pagesClosePanel(true);
      return { role: panel.attrs.role, label: panel.attrs["aria-label"], lines, open, afterChoice, closed: pagesPanelOpen(), focused };
    """, tmp_path)
    assert ran["role"] == "dialog" and ran["label"] == "Linked Households" and ran["open"] is True
    assert ran["lines"] == [["link-to", "Bravo", "Related"], ["link-name", "Gone", "Fed By"], ["link-to", "Delta", "Also Feeds"]]
    assert ran["afterChoice"] == [False, {"level": "household", "household": "c/Bravo"}]
    assert ran["closed"] is False and ran["focused"][-1] == "link-mark", "focus goes back to the icon"


def test_the_firm_lists_divide_the_whole_ordered_list_into_pages_of_fifty(tmp_path):
    """P152, P174: order and tabs act on the whole list, pages divide the
    result; the footer counts in the list's noun; any change returns to
    page 1, and leaving the page forgets it."""
    ran = run_lists("""
      const many = [];
      for (let i = 0; i < 120; i += 1) many.push(line(`1040 - R${String(i).padStart(3, "0")}`, "Alpha", { counts: { ...zero, waiting: 1 }, due: "2026-04-15" }));
      shellFirmData.returns = many;
      const foot = (page) => page.byClass("page-count")[0].textContent;
      const steps = (page) => page.byClass("page-step").map((b) => b.disabled === true);
      const first = draw("overview"); const one = [foot(first), steps(first), names(first).length, names(first)[0]];
      pagesPageAt.overview = 2; const third = draw("overview"); const three = [foot(third), steps(third), names(third).length];
      pagesOrderBy("overview", "taxpayer"); pagesOrderBy("overview", "taxpayer");
      const back = [foot(box), names(box)[0]];
      pagesPageAt.overview = 1; draw("clients"); const again = foot(draw("overview"));
      return { one, three, back, again };
    """, tmp_path)
    assert ran["one"] == ["Showing 1-50 of 120 Returns", [True, False], 50, "R000"]
    assert ran["three"] == ["Showing 101-120 of 120 Returns", [False, True], 20]
    assert ran["back"] == ["Showing 1-50 of 120 Returns", "R119"], "a new order starts at page 1, over the whole list"
    assert ran["again"] == "Showing 1-50 of 120 Returns", "the page is forgotten when the page is left"


def test_needs_review_pages_by_whole_return_groups_and_counts_files(tmp_path):
    """P174: a page takes return groups while their files stay within 50,
    and never splits one; the footer counts files."""
    ran = run_lists("""
      const files = [];
      for (const [ret, n] of [["r/1040 - Alpha", 30], ["r/1065 - Bravo", 30], ["r/1040 - Charlie", 60]]) {
        for (let i = 0; i < n; i += 1) files.push({ return: ret, year: 2025, name: `${ret.slice(2)} ${i}.pdf`, handle: `${ret}${i}`, code: "unmatched",
                                                    received: `2026-03-0${ret.length % 9 + 1}`, suggestion: "", open_key: "" });
      }
      shellFirmData.files = files;
      const counts = (page) => [page.byClass("page-count")[0].textContent,
        page.byClass("group-head").filter((n) => !n.className.includes("page-head")).length, page.byClass("row").length];
      const one = counts(draw("needs-review"));
      pagesPageAt.needs_review = 1; const two = counts(draw("needs-review"));
      pagesPageAt.needs_review = 2; const three = counts(draw("needs-review"));
      return { one, two, three };
    """, tmp_path)
    assert ran["one"][1:] == [1, 30] and ran["two"][1:] == [1, 30] and ran["three"][1:] == [1, 60]
    assert ran["one"][0].endswith("of 120 Files") and ran["three"][0] == "Showing 61-120 of 120 Files"


def test_overviews_tabs_narrow_the_whole_list_and_carry_their_counts(tmp_path):
    """P145: All, Need You (n), Waiting (n) as pressed buttons; a tab narrows
    the list before the order and the pages, and Work Waiting's count is the
    rows it shows."""
    ran = run_lists("""
      const page = draw("overview");
      const tabs = (p) => p.byClass("switch-option").map((b) => [b.textContent, b.attrs["aria-pressed"]]);
      const all = [tabs(page), names(page).length, page.byClass("group-count")[0].textContent];
      pagesTab = "waiting"; const waiting = draw("overview");
      return { all, waiting: [tabs(waiting), names(waiting), waiting.byClass("group-count")[0].textContent] };
    """, tmp_path)
    assert ran["all"] == [[["All", "true"], ["Need You (3)", "false"], ["Waiting (2)", "false"]], 5, "5"]
    assert ran["waiting"][0][2] == ["Waiting (2)", "true"]
    assert ran["waiting"][1] == ["Charlie", "Delta"] and ran["waiting"][2] == "2"


def test_needs_reviews_reason_cards_count_each_reason_and_filter_the_whole_page(tmp_path):
    """P149: a card per reason with its count and icon, and All; a card is a
    pressed filter; the page's count beside its title says the files shown;
    every reason pill is the Need You amber with its reason's icon."""
    ran = run_lists("""
      const page = draw("needs-review");
      const cards = (p) => p.byClass("reason-card").map((c) => [c.byClass("reason-card-word")[0].textContent, c.byClass("reason-card-number")[0].textContent, c.attrs["aria-pressed"]]);
      const pills = page.byClass("row-status").map((s) => [s.className, s.byClass("pill").length, s.byClass("icon").length, s.textContent]);
      const before = [cards(page), page.byClass("list-count")[0].textContent, pills];
      pagesReasonPick = "opened-not-across"; const picked = draw("needs-review");
      return { before, after: [cards(picked), picked.byClass("list-count")[0].textContent, picked.byClass("row").length] };
    """, tmp_path)
    cards, count, pills = ran["before"]
    assert cards == [["All", "3", "true"], ["Could Not Tell", "2", "false"], ["Came in Email or Zip", "1", "false"]]
    assert count == "3 files"
    assert all(cls == "row-status is-attention" and pill == 1 and icons == 1 for cls, pill, icons, _words in pills)
    assert ran["after"] == [[["All", "3", "false"], ["Could Not Tell", "2", "false"], ["Came in Email or Zip", "1", "true"]], "1 file", 1]


def test_a_client_type_narrows_clients_by_the_recorded_form_and_shows_a_removable_chip(tmp_path):
    """P153, SPEC-lists 15.3: a type keeps the households with a return whose
    recorded form is one of its forms (a blank form belongs to none); the
    chip names the type and its dismiss clears it; Work Waiting shows its count."""
    ran = run_lists("""
      pagesClientType = "individuals"; pagesClientsAll = true; pagesLastLevel = "clients";
      const page = draw("clients");
      const chip = page.byClass("type-filter")[0];
      const kept = [names(page), chip.byClass("type-filter-word")[0].textContent, chip.byClass("type-dismiss")[0].attrs["aria-label"],
                    page.byClass("switch-count").map((c) => c.textContent)];
      chip.byClass("type-dismiss")[0].handlers.click[0]();
      return { kept, cleared: [pagesClientType, names(box).length, box.byClass("type-filter").length] };
    """, tmp_path, LINKED)
    assert ran["kept"][0] == ["Alpha", "Delta"]
    assert ran["kept"][1:3] == ["Individuals", "Remove Filter"]
    assert ran["kept"][3] == ["2"], "Work Waiting's count: the individuals with work waiting"
    assert ran["cleared"] == ["", 5, 0]


def test_a_return_pages_three_sections_carry_their_colour_icon_badge_and_edge(tmp_path):
    """P176 (Q8): Needs You amber, Waiting on Client blue, Received green -
    the heading's tone, its icon, a tinted count badge and an edge down its
    rows; Set Aside keeps its plain fold; the heading words stay plain."""
    ran = run_pages_dom("""
      lastState = stateOf([item("B", "received", { status_key: "Received", received_date: "2026-03-01" }), item("C", "waiting"),
                           item("D", "needs_you", { status_key: "Rejected" }), item("A", "set_aside", { status_key: "NotAsked" })], [parked("p1")]);
      const box = page(pagesReturn({ level: "return", ret: "r1", year: 2025 }));
      const heads = box.byClass("group-head").map((h) => [h.className, h.byClass("group-icon").map((i) => i.className).join(),
                                                          h.byClass("group-count")[0].className, h.byClass("group-title")[0].className]);
      const lists = box.find((one) => one.attrs.role === "listbox").map((l) => l.className);
      return { heads, lists };
    """, tmp_path)
    assert ran["heads"][:3] == [
        ["group-head is-first is-section section-needs", "group-icon is-attention", "group-count is-badge is-attention", "group-title"],
        ["group-head is-section section-waiting", "group-icon is-waiting", "group-count is-badge is-waiting", "group-title"],
        ["group-head is-section section-done", "group-icon is-done", "group-count is-badge is-done", "group-title"]]
    assert ran["heads"][3][0] == "group-head" and ran["heads"][3][1] == "", "Set Aside keeps its plain fold"
    assert ran["lists"][:3] == ["rows edge-needs", "rows edge-waiting", "rows edge-done"]
    css = read("shell.css")
    for tone, token in (("needs", "--st-attention"), ("waiting", "--st-waiting"), ("done", "--st-done")):
        assert f".section-{tone}::before {{ background: var({token}); }}" in css
        assert f".rows.edge-{tone} .row::before {{ background: var({token}); }}" in css
    assert ".group-title, .list-title {" in css, "the heading words keep the text colour"


def test_a_firm_lists_status_is_a_pill_with_a_dot_and_the_form_chip_has_its_own_column(tmp_path):
    """P145: on Overview the status is a pill with a dot that keeps its count
    in the app's colours; P195: the recorded form's chip is the Form Type
    cell, read by a screen reader (the taxpayer no longer begins with it), and
    a return with no recorded form has an empty Form Type cell."""
    ran = run_lists("""
      const page = draw("overview");
      const row = page.byClass("row").find((r) => r.textContent.indexOf("Alpha") !== -1);
      const form = row.byClass("row-form")[0];
      shellFirmData.returns[3].form = ""; const again = draw("overview");
      return { dot: row.byClass("pill-dot").length, word: row.byClass("pill-word")[0].textContent,
               chip: form.byClass("form-tag").map((c) => [c.textContent, c.attrs["aria-hidden"] || ""]), inName: row.byClass("row-name")[0].byClass("form-tag").length,
               forms: again.byClass("row").map((r) => r.byClass("row-form")[0].textContent) };
    """, tmp_path, LINKED)
    assert ran == {"dot": 1, "word": "3 need you", "chip": [["1040", ""]], "inName": 0, "forms": ["1041", "1065", "1040", "1040", ""]}
    css = read("shell.css")
    for tone, tint in (("attention", "--warn-bg"), ("waiting", "--info-bg"), ("done", "--ok-bg")):
        assert f".is-{tone} > .pill {{ background: var({tint}); }}" in css
    assert "monospace" not in css.lower() and "monospace" not in read("pilot-ui.css").lower()


def test_the_search_finds_waiting_files_on_needs_review_and_its_placeholder_says_so(tmp_path):
    """P173: the box searches the whole practice; given Needs Review's files
    it finds them first, noted with their return and year, and choosing one
    opens Check; its placeholder is the vocabulary's, per page."""
    probe = """
      const files = [{ return: "r1", year: 2025, name: "Smith W-2.pdf", handle: "h1" }];
      const found = findOptions("smith", files);
      return { names: found.map((o) => o.name), note: found[0].note, check: found[0].check, without: findOptions("smith").length };
    """
    ran = run_shell(["screenWords", "fold", "foldedName", "shellHousehold", "shellOwnReturns", "shellReturn", "findOptions"], PEOPLE, probe, tmp_path)
    assert ran["names"][0] == "Smith W-2.pdf" and ran["note"] == "1040 - John & Jane Smith 2025"
    assert ran["check"] == {"ret": "r1", "name": "Smith W-2.pdf", "handle": "h1"} and ran["without"] == 3
    assert api.SCREEN["find_placeholder"] == "Households and Returns"
    assert api.SCREEN["find_placeholder_files"] == "Files, Households and Returns"
    shell = stripped_js("shell.js")
    assert 'setAttribute("placeholder", shellRoute.level === "needs-review" ? words.find_placeholder_files : words.find_placeholder)' in shell


def test_the_side_panel_is_the_mocks_with_the_products_brand_and_nothing_behind_the_unbuilt_items(tmp_path):
    """P153, P154, P155, P265, P266: the brand band names Tax Document
    Console (the firm's name is the window's title); the four pages keep Ctrl+1..4; five Under Construction items are
    aria-disabled buttons whose click says so and calls nothing else; four
    Client Types open Clients filtered; Settings is the settings the app has."""
    html = read("index.html")
    side = html[html.index('<nav id="side">'):html.index("</nav>", html.index('<nav id="side">'))]
    assert side.count('data-section="') == 4 and side.count('data-type="') == 4
    assert side.count('aria-disabled="true"') == 5 and side.count('class="side-section is-soon"') == 5
    for ident in ("side-brand-product", "side-scroll", "side-types-heading", "side-workspace-heading", "side-settings", "last-sort"):
        assert f'id="{ident}"' in side, ident
    assert side.index('data-soon="family_entities"') < side.index('id="side-types-heading"') < side.index('data-soon="personal_trusts"')
    words = api.SCREEN["side"]
    assert "brand" not in words and words["product"] == "Tax Document Console"
    assert words["under_construction"] == "Under Construction" == api.SCREEN["notices"]["under_construction"]
    assert words["soon"] == {"ready_to_sign": "Ready to Sign", "family_entities": "Family Entities", "personal_trusts": "Personal Trusts",
                             "corporate_entities": "Corporate Entities", "portal_settings": "Portal Settings"}
    assert set(api.SCREEN["client_types"]) == set(api.CLIENT_TYPE_FORMS) and '"client_type_forms": CLIENT_TYPE_FORMS,' in (REPO / "tracker" / "api.py").read_text(encoding="utf-8")
    assert api.CLIENT_TYPE_FORMS == {
        "individuals": ["1040"], "businesses": ["1120", "1120S", "1065"], "trusts": ["1041"], "nonprofits": ["990"]}
    shell = stripped_js("shell.js")
    soon = shell[shell.index('querySelectorAll(".side-section[data-soon]")) {\n  node.addEventListener'):]
    soon = soon[:soon.index("\n}\n")]
    assert 'toastWord("under_construction")' in soon and "call(" not in soon and "shellGo" not in soon
    assert '$("side-settings").addEventListener("click", () => shellAnswer("change_root"));' in shell
    css = read("shell.css")
    assert "#side-scroll { min-height: 0; overflow-y: auto;" in css, "the panel scrolls rather than cut an item"
    assert '.side-section[data-section="needs-review"] .side-count:not(:empty) { background: var(--warn-bg); color: var(--st-attention); }' in css


def test_a_row_made_active_by_the_keyboard_shows_its_status_tooltip_at_once(tmp_path):
    """P178: Up/Down move the active row by aria-activedescendant and show
    the row's status words as its tooltip at once; a click shows none."""
    ran = run_pages_dom("""
      const shown = []; let hidden = 0;
      globalThis.showTipNow = (node) => shown.push(node.textContent);
      globalThis.hideTip = () => { hidden += 1; };
      Element.prototype.querySelectorAll = function (sel) { return sel === ".is-active" ? this.byClass("is-active") : this.find((one) => one.attrs.role === "option"); };
      const oldQuery = Element.prototype.querySelector;
      Element.prototype.querySelector = function (sel) {
        if (sel.indexOf("[data-tip]") !== -1) return this.byClass("pill-word")[0] || null;   // the tip's node (setTipIfCut is faked here)
        return oldQuery.call(this, sel);
      };
      Object.defineProperty(Element.prototype, "classList", { get() {
        const self = this;
        return { add(one) { if (!self.className.split(" ").includes(one)) self.className = `${self.className} ${one}`.trim(); },
                 contains(one) { return self.className.split(" ").includes(one); },
                 remove(one) { self.className = self.className.split(" ").filter((c) => c !== one).join(" "); } };
      } });
      const rows = [pagesRow({ name: "a.pdf", status: "Came in Email or Zip", tone: "needs", pill: true, menu: "file" }),
                    pagesRow({ name: "b.pdf", status: "Could Not Tell", tone: "needs", pill: true, menu: "file" })];
      const list = new Element("div"); list.append(...rows);
      pagesActivate(list, rows[1], true);
      pagesActivate(list, rows[0]);
      return { shown, hidden };
    """, tmp_path)
    assert ran["shown"] == ["Could Not Tell"] and ran["hidden"] == 2
    tip = read("tooltip.js")
    assert "function showTipNow(node) {" in tip and "delete node.dataset.tipCut;" in tip


def test_the_new_tokens_and_every_new_pair_meet_their_contrast_in_both_themes():
    """P177, SPEC-lists 16: the two new tokens have their values in both
    themes, and every new pair meets its figure (text 4.5, non-text 3)."""
    for name, (light, dark) in {"--st-linked": ("#7c3aad", "#c4a0f0"), "--bg-band": ("#f8fafc", "#1f232a")}.items():
        assert resolve(name, "light") == light and resolve(name, "dark") == dark, name
    for fg, bg, needs in (("--st-linked", "--bg-page", 3), ("--st-linked", "--bg-hover", 3), ("--st-linked", "--bg-selected", 3),
                          ("--st-linked", "--bg-band", 3), ("--st-linked", "--bg-raised", 3), ("--st-linked", "--bg-pressed", 3), ("--st-attention", "--warn-bg", 4.5),
                          ("--st-waiting", "--info-bg", 4.5), ("--st-done", "--ok-bg", 4.5), ("--st-attention", "--bg-raised", 3),
                          ("--st-waiting", "--bg-raised", 3), ("--st-done", "--bg-raised", 3), ("--text", "--bg-band", 4.5),
                          ("--text-secondary", "--bg-band", 4.5), ("--text-caption", "--bg-band", 4.5), ("--link", "--bg-band", 4.5),
                          ("--link", "--bg-raised", 4.5), ("--focus", "--bg-band", 3), ("--text-secondary", "--bg-nav", 4.5),
                          ("--text-secondary", "--bg-nav-hover", 4.5), ("--text-secondary", "--bg-pressed", 4.5),
                          ("--window-light", "--brand", 4.5)):
        for theme in ("light", "dark"):
            assert ratio(fg, bg, theme) >= needs, (fg, bg, theme)


# ── lane 4b review fold (S2-S5, N3-N5 of that review) ──

#: What the panel's probes need of a DOM beyond FAKE_DOM: focus, removal, a
#: body, Floating UI's placement, and the two selectors the panel code asks.
PANEL_DOM = r"""
  const focused = [];
  Element.prototype.focus = function () { focused.push(this.attrs.role === "listbox" ? "listbox" : this.className || this.attrs.id || this.tag); };
  Element.prototype.remove = function () { this.removed = true; };
  Element.prototype.contains = function () { return false; };
  Element.prototype.closest = function () { return null; };
  Element.prototype.querySelectorAll = function (sel) { return sel === ".link-mark" ? this.byClass("link-mark") : this.byClass(sel.slice(1)); };
  const oldQuery = Element.prototype.querySelector;
  Element.prototype.querySelector = function (sel) {
    return sel === '[role="listbox"]' ? this.find((one) => one.attrs.role === "listbox")[0] || null : oldQuery.call(this, sel);
  };
  document.body = new Element("body");
  globalThis.FloatingUIDOM = { computePosition: () => Promise.resolve({ x: 0, y: 0 }), offset: () => 0, flip: () => 0, shift: () => 0 };
  globalThis.TIP_GAP = 4; globalThis.TIP_MARGIN = 8;
"""


def test_a_redraw_keeps_the_link_panel_open_on_the_same_household_or_moves_focus_to_the_list(tmp_path):
    """The review's S2: a firm reply redraws the page while the panel is
    open; the panel opens again on the same household's mark, and when that
    household no longer has one, focus goes to the page's list, never lost."""
    ran = run_lists("""
      draw("overview");
      const mark = box.byClass("link-mark").find((one) => one.dataset.owner === "Bravo");
      pagesShowPanel(mark, mark.linked, box);
      draw("overview");
      const kept = [pagesPanelOpen(), pagesPanel && pagesPanel.owner, document.body.kids.filter((one) => !one.removed).length];
      for (const one of shellFirmData.returns) one.links = [];
      focused.length = 0;
      draw("overview");
      return { kept, gone: [pagesPanelOpen(), focused.slice(-1)[0]] };
    """, tmp_path, LINKED + PANEL_DOM)
    assert ran["kept"] == [True, "Bravo", 1]
    assert ran["gone"] == [False, "listbox"]


def test_escape_closes_the_link_panel_and_returns_focus_to_its_icon(tmp_path):
    """The review's S5: Escape, through the shell's one key handler, closes
    an open panel and puts focus back on the icon it was opened from."""
    ran = run_pages_dom("""
      const els = { find: new Element("input"), sheet: { hidden: true }, "find-list": { hidden: true } };
      globalThis.$ = (id) => els[id]; globalThis.dialogStack = [];
      const anchor = new Element("button"); anchor.className = "link-mark"; anchor.isConnected = true;
      pagesShowPanel(anchor, [{ name: "Bravo", path: "c/Bravo", kind: "related" }], anchor);
      let prevented = 0;
      const handled = shellKey({ key: "Escape", target: new Element("button"), preventDefault: () => { prevented += 1; } });
      return { handled, prevented, open: pagesPanelOpen(), focused: focused.slice(-1)[0] };
    """, tmp_path, setup=PANEL_DOM + "let tipFor = null; function hideTip() { tipFor = null; }" + js_function("tipKey", "tooltip.js"), functions=[*re.findall(r"^function (\w+)\(", read("pages.js"), flags=re.M), "h", "icon", "screenWords",
                                               "folderName", "shellKey"])
    assert ran == {"handled": True, "prevented": 1, "open": False, "focused": "link-mark"}


def test_the_link_panel_and_the_pickers_are_named_and_show_their_focus():
    """The review's S3, S4 and N4: every control in the panel shows a focus
    ring (forced colours give it CanvasText); both Edit Household pickers and
    lists are named by their labels; the link icon and More Actions say they
    open a dialog and a menu."""
    css = read("shell.css")
    assert "#link-panel:focus { outline: none; }" not in css
    assert "#link-panel:focus-visible, .link-to:focus-visible { outline: 2px solid var(--focus); outline-offset: 2px; }" in css
    assert ":focus-visible { outline: 2px solid CanvasText; }" in css[css.index("@media (forced-colors: active)"):]
    html = read("index.html")
    for ident, label in (("hh-edit-related-pick", "hh-edit-related-label"), ("hh-edit-related", "hh-edit-related-label"),
                         ("hh-edit-feed-pick", "hh-edit-feeds-label"), ("hh-edit-feeds", "hh-edit-feeds-label")):
        assert re.search(rf'id="{ident}"[^>]*aria-labelledby="{label}"', html), ident
    pages = stripped_js("pages.js")
    assert '"aria-haspopup": "menu"' in pages and '"aria-haspopup": "dialog"' in pages


def test_the_four_lists_fit_1100px_beside_a_windows_scrollbar():
    """The review's N5 (P179): at 1100px the main area is 860px less Windows'
    classic 17px scrollbar, 843px; the columns' usual widths with their gaps
    and the list's padding must fit it, or the page scrolls sideways again.
    (P272: Needs Review's cards are gone, so its rows are the firm list's.)"""
    light, _dark = root_blocks()

    def px(name: str) -> int:
        return int(light[name].strip().removesuffix("px"))

    sp = {step: px(f"--sp-{step}") for step in (4, 8)}
    columns = sum(px(f"--size-col-{cell}") for cell in ("name", "detail", "status", "end")) + 3 * sp[4]
    assert columns + 2 * sp[8] <= 1100 - px("--size-side") - 17
    # P194, P195: Overview's and Reminders' five columns, four gaps and the list's padding.
    returns = sum(px(f"--size-col-{cell}") for cell in ("year", "taxpayer", "form", "status", "end")) + 4 * sp[4]
    assert returns + 2 * sp[8] == 832 <= 1100 - px("--size-side") - 17
    first = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            first.setdefault(" ".join(part.split()), dict(declarations(body)))
    least = first['#page[data-list="overview"] .rows']["min-width"]
    for cell in ("year", "taxpayer", "form", "status", "end"):
        assert f"var(--size-col-{cell})" in least, cell
    assert "4 * var(--sp-4)" in least and least == first['.col-table[data-list="reminders"]']["min-width"]


def test_overview_and_reminders_say_tax_year_taxpayer_and_form_type_once_each_in_their_own_columns(tmp_path):
    """P194, P195: each return row is five cells in Jason's order - Tax Year,
    Taxpayer, Form Type, then the list's status and date - and no cell says
    the form or the year a second time; the household has no column; the
    rows and the header row share one five-column grid."""
    ran = run_lists("""
      const out = {};
      for (const level of ["overview", "reminders"]) {
        const page = draw(level);
        out[level] = page.byClass("row").map((r) => [r.kids.map((k) => k.className.split(" ")[0]), r.byClass("row-year")[0].textContent,
                                                    r.byClass("row-name")[0].textContent, r.byClass("row-form")[0].textContent, r.byClass("row-detail").length]);
      }
      return out;
    """, tmp_path)
    for level, rows in ran.items():
        for cells, year, name, form, detail in rows:
            assert cells == ["row-year", "row-name", "row-form", "row-status", "row-end"], level
            assert year == ("2024" if name == "Charlie" else "2025") and "2025" not in name and not name.startswith(form) and detail == 0, (level, name)
    assert [row[2] for row in ran["reminders"]] == ["Alpha", "Charlie", "Bravo"], "the usual order is unchanged (by the return's name)"
    first = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            first.setdefault(" ".join(part.split()), dict(declarations(body)))
    grid = first[".row-return:not(.hidden)"]["grid-template-columns"]
    assert grid == ("var(--size-col-year) var(--size-col-taxpayer) var(--size-col-form) var(--size-col-status) var(--size-col-end)"), "P199"
    assert first['.col-table[data-list="overview"] .col-heads:not(.hidden)']["grid-template-columns"] == grid
    assert first['.col-table[data-list="reminders"] .col-heads:not(.hidden)']["grid-template-columns"] == grid
    css = read("shell.css")
    tabular = next(body for _m, selector, body in blocks(css) if selector.strip().startswith(".side-count,"))
    selector = next(selector for _m, selector, body in blocks(css) if selector.strip().startswith(".side-count,"))
    assert ".row-year" in selector and ".head-year" in selector and ".row-date" in selector and "tabular-nums" in tabular
    assert "monospace" not in css.lower()


def test_the_household_is_in_the_taxpayer_tooltip_and_the_rows_description(tmp_path):
    """P195 Q1 (Jason: "Take your recommendation"): the household has no
    column; its name is the Taxpayer link's tooltip and part of the row's
    screen-reader description, and its Linked Households mark sits after the
    taxpayer, owned by the household so a redraw finds it again."""
    ran = run_lists("""
      tips.length = 0;
      const page = draw("overview");
      const alpha = page.byClass("row").find((r) => r.byClass("row-name")[0].textContent === "Alpha");
      return { tips: tips.filter(([cls]) => cls === "row-link").map(([, words]) => words), described: alpha.attrs["aria-description"],
               mark: alpha.byClass("row-name")[0].byClass("link-mark").map((m) => m.dataset.owner) };
    """, tmp_path, LINKED)
    assert "Navigate to Return (Alpha)" in ran["tips"] and "Navigate to Return (Bravo)" in ran["tips"]
    assert ran["described"].endswith("Alpha, Linked Households")
    assert ran["mark"] == ["Alpha"]
    assert api.SCREEN["columns"]["taxpayer_tip"] == "{action} ({household})"
    assert "return" not in api.SCREEN["columns"] and "client" not in api.SCREEN["columns"], "no list draws the old Return or Client header"


def test_tax_year_orders_by_number_and_form_type_by_the_apps_form_order(tmp_path):
    """P195: Tax Year orders by its number; Form Type in the order the app
    already lists forms (the Client Types: 1040; 1120, 1120S, 1065; 1041;
    990), any other form after them by its name; a blank goes last both ways."""
    ran = run_lists("""
      const set = { "1040 - Alpha": [2025, "1040"], "1065 - Bravo": [2024, "1065"], "1040 - Charlie": [2023, "990"], "1040 - Delta": ["", ""], "1041 - Echo": [2026, "1041"] };
      for (const one of shellFirmData.returns) [one.year, one.form] = set[one.path.slice(2)];
      shellFirmData.returns.push(line("W9 - Foxtrot", "Alpha", { year: 2022, form: "W9", counts: { ...zero, waiting: 1 } }));
      draw("overview");
      pagesOrderBy("overview", "year"); const years = names(box);
      pagesOrderBy("overview", "year"); const back = names(box);
      pagesOrderBy("overview", "form"); const forms = names(box);
      pagesOrderBy("overview", "form"); const formsBack = names(box);
      return { years, back, forms, formsBack };
    """, tmp_path)
    # Charlie's record says 990 and Delta's no form, so their names are shown whole (never cut by a guess).
    assert ran["years"] == ["Foxtrot", "1040 - Charlie", "Bravo", "Alpha", "Echo", "1040 - Delta"]
    assert ran["back"] == ["Echo", "Alpha", "Bravo", "1040 - Charlie", "Foxtrot", "1040 - Delta"], "a blank year is last both ways"
    assert ran["forms"] == ["Alpha", "Bravo", "Echo", "1040 - Charlie", "Foxtrot", "1040 - Delta"]
    assert ran["formsBack"] == ["Foxtrot", "1040 - Charlie", "Echo", "Bravo", "Alpha", "1040 - Delta"], "a blank form is last both ways"


def test_a_saved_width_of_the_old_return_column_never_reaches_the_new_layout(tmp_path):
    """P195: a width saved for Overview's old Return (name) or Client (detail)
    column is not applied to the new layout and is dropped at the next save;
    Status and Date keep theirs, since they mean the same."""
    ran = run_lists("""
      window.localStorage.setItem("tracker.columns", JSON.stringify({ overview: { name: 500, detail: 300, status: 200 }, clients: { name: 300 } }));
      pagesWidths = null; box.style.props = {};
      pagesApplyWidths(box, "overview"); const shown = { ...box.style.props };
      pagesSetWidth("overview", "taxpayer", 400); pagesSaveWidths();
      return { shown, after: { ...box.style.props }, stored: JSON.parse(window.localStorage.getItem("tracker.columns")) };
    """, tmp_path, extra="""
      const window = { localStorage: { data: {}, getItem(k) { return k in this.data ? this.data[k] : null; }, setItem(k, v) { this.data[k] = String(v); },
                                       removeItem(k) { delete this.data[k]; } } };
    """)
    assert ran["shown"] == {"--size-col-status": "200px"}
    assert ran["after"] == {"--size-col-status": "200px", "--size-col-taxpayer": "400px"}
    assert ran["stored"] == {"overview": {"status": 200, "taxpayer": 400}, "clients": {"name": 300}}


def test_needs_review_household_and_year_pages_say_each_field_once(tmp_path):
    """P195 Q2 (Jason: "yes, apply to all windows"): Needs Review's files keep
    their own columns and each return heading says the year, the taxpayer
    and the form once; on the household and year pages a return is its form
    chip and its taxpayer, the year being the heading or the title above."""
    ran = run_lists("""
      const review = draw("needs-review");
      const heads = review.byClass("group-title").map((t) => t.kids.map((k) => [k.className, k.textContent]));
      const hh = { name: "Alpha", path: "c/Alpha", returns: [{ path: "r/1040 - Alpha", year: 2025, return_name: "1040 - Alpha", form: "1040", active: true },
                                                             { path: "r/old", year: 2024, return_name: "1040 - Alpha", form: "1040", active: true }] };
      shellHousehold = () => hh;
      shellRoute = { level: "household", household: "c/Alpha" };
      const page = pagesHousehold(shellRoute);
      const lists = (n) => (n && n.className && n.className.split(" ").includes("returns-list") ? [n] : n && n.byClass ? n.byClass("returns-list") : []);
      const inList = (nodes) => nodes.flatMap(lists).flatMap((list) => list.byClass("row"));
      const rows = inList(page).map((r) => r.byClass("row-name")[0].kids.map((k) => [k.className, k.textContent]));
      const year = pagesYear({ level: "year", household: "c/Alpha", year: 2025 });
      const yearRows = inList(year).map((r) => r.byClass("row-name")[0].textContent);
      return { heads, rows, yearRows, title: year[0].textContent };
    """, tmp_path)
    assert ran["heads"] == [[["head-year", "2025"], ["row-link", "Bravo"], ["form-tag", "1065"]],
                            [["head-year", "2025"], ["row-link", "Alpha"], ["form-tag", "1040"]]]
    assert ran["rows"] == [[["form-tag", "1040"], ["row-link", "Alpha"]], [["form-tag", "1040"], ["row-link", "Alpha"]]], "the year is the heading above"
    assert ran["title"] == "2025" and ran["yearRows"] == ["1040Alpha"]


def test_the_window_and_its_taskbar_button_carry_the_console_icon():
    """The unpackaged launch has no icon written into an .exe, so the window names
    the file; the app id is set before the window opens so Windows groups the
    running window with its shortcut."""
    main = (REPO / "app" / "main.js").read_text(encoding="utf-8")
    assert 'icon: path.join(__dirname, "assets", "icon.ico"),' in main
    assert (REPO / "app" / "assets" / "icon.ico").is_file()
    set_id = main.index('app.setAppUserModelId("com.jparkassociates.taxdocumentconsole");')
    assert set_id < main.index("app.whenReady()")


# ── View › Show Under Construction (pilot SPEC-hide-under-construction, P197) ──

#: The side panel as index.html lays it out, in a DOM just big enough for
#: drawSoon and shellToggleSoon: the pages list (four pages, two Under
#: Construction), the Taxpayer Types under their heading, and Workspace (three
#: Under Construction items) under its heading.
SOON_PANEL = r"""
class El {
  constructor(tag, attrs, kids) {
    this.tag = tag; this.attrs = attrs || {}; this.kids = kids || []; this.parent = null; this.cls = new Set();
    for (const k of this.kids) k.parent = this;
    this.classList = { toggle: (c, on) => (on ? this.cls.add(c) : this.cls.delete(c)), contains: (c) => this.cls.has(c) };
    if (this.attrs.class) for (const c of this.attrs.class.split(" ")) this.cls.add(c);
  }
  getAttribute(name) { return name in this.attrs ? this.attrs[name] : null; }
  matches(sel) {
    if (sel === "li") return this.tag === "li";
    if (sel === ".side-list") return this.cls.has("side-list");
    if (sel === ".side-section") return this.cls.has("side-section");
    if (sel === ".side-section[data-soon]") return this.cls.has("side-section") && "data-soon" in this.attrs;
    throw new Error(`selector ${sel}`);
  }
  all() { return this.kids.flatMap((k) => [k, ...k.all()]); }
  querySelectorAll(sel) { return this.all().filter((n) => n.matches(sel)); }
  closest(sel) { let n = this; while (n && !n.matches(sel)) n = n.parent; return n || null; }
}
const button = (attrs) => new El("li", {}, [new El("button", { class: "side-section", ...attrs })]);
const soon = (key) => button({ "data-soon": key });
const typesHeading = new El("h2", { id: "side-types-heading", class: "side-heading" });
const workHeading = new El("h2", { id: "side-workspace-heading", class: "side-heading" });
const root = new El("nav", {}, [
  new El("ul", { id: "side-sections" }, [
    button({ "data-section": "overview" }), button({ "data-section": "needs-review" }),
    button({ "data-section": "reminders" }), button({ "data-section": "clients" }),
    soon("ready_to_sign"), soon("family_entities")]),
  typesHeading,
  new El("ul", { class: "side-list", "aria-labelledby": "side-types-heading" }, [
    button({ "data-type": "individuals" }), button({ "data-type": "businesses" }),
    button({ "data-type": "trusts" }), button({ "data-type": "nonprofits" })]),
  workHeading,
  new El("ul", { class: "side-list", "aria-labelledby": "side-workspace-heading" }, [
    soon("personal_trusts"), soon("corporate_entities"), soon("portal_settings")]),
]);
const byId = { "side-types-heading": typesHeading, "side-workspace-heading": workHeading };
const $ = (id) => byId[id] || null;
const document = { activeElement: null, querySelectorAll: (sel) => root.querySelectorAll(sel) };
const store = { data: {}, broken: false,
  getItem(k) { if (this.broken) throw new Error("locked"); return k in this.data ? this.data[k] : null; },
  setItem(k, v) { if (this.broken) throw new Error("locked"); this.data[k] = String(v); },
  removeItem(k) { if (this.broken) throw new Error("locked"); delete this.data[k]; } };
const window = { localStorage: store };
const SOON_KEY = "tracker.underConstruction";
const ROWS_KEY = "tracker.rows";
let shellSoonHidden = null;
let shellCompact = null;
const said = { focus: [], tips: 0, sent: [] };
function focusRegion(name) { said.focus.push(name); }
function hideTip() { said.tips += 1; }
function shellEnable() { said.sent.push(shellChecked()); }
const hiddenNow = () => root.all().filter((n) => n.cls.has("hidden")).map((n) =>
  n.tag === "li" ? n.kids[0].attrs["data-soon"] || n.kids[0].attrs["data-section"] || n.kids[0].attrs["data-type"]
    : n.attrs.id || `list:${n.attrs["aria-labelledby"]}`);
const soonButton = (key) => root.querySelectorAll(".side-section[data-soon]").find((n) => n.attrs["data-soon"] === key);
"""

SOON_FUNCTIONS = ["shellReadSoon", "shellReadCompact", "shellChecked", "drawSoon", "shellToggleSoon"]


def test_hiding_takes_the_five_under_construction_items_and_the_workspace_heading_out_of_the_panel(tmp_path):
    """P197 rulings 1 and 2: a stored "hidden" hides the five items and the
    Workspace heading and list with the .hidden class (display: none, so out
    of the Tab order and the accessibility tree); the pages, the Taxpayer
    Types and their heading stay; the menu's tick is off."""
    ran = run_shell(SOON_FUNCTIONS, SOON_PANEL + store_functions(), """
      store.data[SOON_KEY] = "hidden";
      drawSoon();
      return { hidden: hiddenNow(), checked: shellChecked() };
    """, tmp_path)
    assert sorted(ran["hidden"]) == sorted([
        "ready_to_sign", "family_entities", "side-workspace-heading", "list:side-workspace-heading",
        "personal_trusts", "corporate_entities", "portal_settings"])
    assert ran["checked"] == []


def test_a_new_install_shows_them_and_the_menu_flips_keeps_and_says_the_tick(tmp_path):
    """P197 rulings 3, 5 and 6, Q2: shown with nothing stored; the menu's
    answer hides them, keeps "hidden" on this PC, hides a showing tip, moves
    focus that sat on a hidden item to the side panel's current page (F6's
    place) and tells the menu; choosing it again shows them and forgets the
    key, and focus elsewhere is left where it is."""
    ran = run_shell(SOON_FUNCTIONS, SOON_PANEL + store_functions(), """
      drawSoon();
      const first = { hidden: hiddenNow(), checked: shellChecked() };
      document.activeElement = soonButton("portal_settings");
      shellToggleSoon();
      const off = { hidden: hiddenNow().length, stored: store.data[SOON_KEY], focus: [...said.focus], tips: said.tips };
      document.activeElement = null;
      shellToggleSoon();
      const on = { hidden: hiddenNow(), stored: SOON_KEY in store.data, focus: said.focus };
      return { first, off, on, sent: said.sent };
    """, tmp_path)
    assert ran["first"] == {"hidden": [], "checked": ["show_under_construction"]}
    assert ran["off"] == {"hidden": 7, "stored": "hidden", "focus": ["side"], "tips": 1}
    assert ran["on"] == {"hidden": [], "stored": False, "focus": ["side"]}
    assert ran["sent"] == [[], ["show_under_construction"]]


def test_storage_that_cannot_be_read_shows_them_and_the_choice_holds_while_the_app_is_open(tmp_path):
    """P197 ruling 5: the column widths' fallback - unreadable storage shows
    the items, and a choice it refuses to keep still holds until the app
    closes."""
    ran = run_shell(SOON_FUNCTIONS, SOON_PANEL + store_functions(), """
      store.broken = true;
      drawSoon();
      const first = hiddenNow();
      shellToggleSoon();
      return { first, after: hiddenNow().length, checked: shellChecked() };
    """, tmp_path)
    assert ran == {"first": [], "after": 7, "checked": []}


def test_the_setting_is_this_pcs_and_the_side_panel_draws_it_on_every_draw():
    """P197 rulings 4-6: kept under its own key in this PC's storage (never
    settings.json, never the engine), drawn by drawSide, answered by the menu
    and enabled from the first frame."""
    text = stripped_js("shell.js")
    assert 'const SOON_KEY = "tracker.underConstruction";' in text
    assert "drawSoon();" in js_function("drawSide")
    assert re.search(r"^drawSoon\(\);$", text, flags=re.M), "a stored hidden applies at load, before the words (review S1)"
    assert "show_under_construction: () => shellToggleSoon()," in text
    first = [line for line in js_function("shellEnabled").splitlines() if "const ids = [" in line]
    assert len(first) == 1 and '"show_under_construction"' in first[0] and '"compact_rows"' in first[0]
    assert "under_construction" not in (REPO / "tracker" / "settings.py").read_text(encoding="utf-8")


def test_a_damaged_stored_value_shows_them(tmp_path):
    """P197 ruling 5 (review NIT 2a): only the exact word "hidden" hides; any
    other stored value reads as shown, the new install's default."""
    ran = run_shell(SOON_FUNCTIONS, SOON_PANEL + store_functions(), """
      const seen = [];
      for (const value of ["HIDDEN", "1", "true", ""]) {
        store.data[SOON_KEY] = value; shellSoonHidden = null; drawSoon();
        seen.push([hiddenNow(), shellChecked()]);
      }
      return seen;
    """, tmp_path)
    assert ran == [[[], ["show_under_construction"]]] * 4


def test_hiding_while_focus_is_elsewhere_leaves_focus_where_it_is(tmp_path):
    """P197 ruling 3 (review NIT 2b): focus moves only when it sat on an item
    now hidden; on a page item it stays."""
    ran = run_shell(SOON_FUNCTIONS, SOON_PANEL + store_functions(), """
      document.activeElement = root.querySelectorAll(".side-section")[0];
      shellToggleSoon();
      return { hidden: hiddenNow().length, focus: said.focus, stored: store.data[SOON_KEY] };
    """, tmp_path)
    assert ran == {"hidden": 7, "focus": [], "stored": "hidden"}


# ── the 0.3 Windows check's list and dialog notes (pilot SPEC-check-notes-0.3, P199) ──

def test_a_firm_lists_columns_are_their_own_widths_so_the_date_sits_after_the_status():
    """P199 (L4, N2a): no column of a firm list takes the window's slack - the
    taxpayer's and the name column's 1fr made the Date run to the window's
    right edge, and made a widened column grow to the left as its flexible
    neighbour shrank. Every track is its width, so at any window from 1100px
    up the Date starts 16px after the Status's right edge (656px into the
    list at the usual widths), the date and its header start at the column's
    left edge, and a return's own page keeps its date at the end."""
    first = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            first.setdefault(" ".join(part.split()), dict(declarations(body)))
    five = "var(--size-col-year) var(--size-col-taxpayer) var(--size-col-form) var(--size-col-status) var(--size-col-end)"
    four = "var(--size-col-name) var(--size-col-detail) var(--size-col-status) var(--size-col-end)"
    for selector in (".row-return:not(.hidden)", '.col-table[data-list="overview"] .col-heads:not(.hidden)',
                     '#page[data-list="reminders"] .row-skeleton:not(.hidden)'):
        assert first[selector]["grid-template-columns"] == five, selector
    for selector in ('#page[data-list="needs_review"] .row:not(.hidden)', '#page[data-list="clients"] .row:not(.hidden)',
                     '.col-table[data-list="needs_review"] .col-heads:not(.hidden)', '.col-table[data-list="clients"] .col-heads:not(.hidden)',
                     '#page[data-list="needs_review"] .row-skeleton:not(.hidden)', '#page[data-list="clients"] .row-skeleton:not(.hidden)'):
        assert first[selector]["grid-template-columns"] == four, selector
    assert "1fr" in first[".row:not(.hidden)"]["grid-template-columns"], "a return's own page (no headers) is unchanged"
    for name in ("overview", "needs_review", "reminders", "clients"):
        assert first[f'#page[data-list="{name}"] .row-end:not(.hidden)']["justify-items"] == "start", name
    assert first[".row-end:not(.hidden)"]["justify-items"] == "end"
    assert '.col-cell[data-cell="end"]' not in first, "the Date header's word starts where its dates do"
    light, _dark = root_blocks()

    def px(name: str) -> int:
        return int(light[name].strip().removesuffix("px"))

    date_at = px("--sp-8") + sum(px(f"--size-col-{cell}") for cell in ("year", "taxpayer", "form", "status")) + 4 * px("--sp-4")
    assert date_at == 656 and date_at + px("--size-col-end") + px("--sp-8") <= 1100 - px("--size-side") - 17


def test_the_order_chosen_by_a_header_is_kept_on_this_pc_across_a_restart(tmp_path):
    """P199 (N2b), replacing P139's "while the app is open": a list's order is
    kept per list in this PC's storage, as its widths are, and comes back
    after a restart; the third press forgets it. A damaged value - not JSON,
    a column the list no longer has, Households' wordless end column, a
    direction other than 1 or -1 - leaves the usual order. Reset Column
    Widths does not touch the order."""
    ran = run_lists("""
      const restart = () => { pagesOrder = null; pagesWidths = null; };
      const usual = names(draw("overview"));
      pagesOrderBy("overview", "taxpayer"); pagesOrderBy("overview", "taxpayer");
      draw("reminders"); pagesOrderBy("reminders", "end");
      const stored = JSON.parse(window.localStorage.getItem("tracker.order"));
      restart(); const back = [names(draw("overview")), sorts(box)];
      pagesResetWidths(); restart(); const afterReset = names(draw("overview"));
      const damaged = {};
      for (const [name, value] of [["junk", "not json"], ["old", JSON.stringify({ overview: { cell: "name", dir: 1 } })],
                                   ["wordless", JSON.stringify({ clients: { cell: "end", dir: 1 } })],
                                   ["dir", JSON.stringify({ overview: { cell: "taxpayer", dir: 2 } })],
                                   ["list", JSON.stringify(["overview"])]]) {
        window.localStorage.setItem("tracker.order", value); restart();
        damaged[name] = [names(draw("overview")), sorts(box), pagesStoredOrder()];
      }
      window.localStorage.setItem("tracker.order", JSON.stringify({ overview: { cell: "taxpayer", dir: -1 } })); restart();
      draw("overview"); pagesOrderBy("overview", "taxpayer"); restart();
      const third = [names(draw("overview")), window.localStorage.getItem("tracker.order")];
      return { usual, stored, back, afterReset, damaged, third };
    """, tmp_path, extra="""
      const window = { localStorage: { data: {}, getItem(k) { return k in this.data ? this.data[k] : null; }, setItem(k, v) { this.data[k] = String(v); },
                                       removeItem(k) { delete this.data[k]; } } };
    """)
    assert ran["stored"] == {"overview": {"cell": "taxpayer", "dir": -1}, "reminders": {"cell": "end", "dir": 1}}
    assert ran["back"] == [["Echo", "Delta", "Charlie", "Bravo", "Alpha"], ["none", "descending", "none", "none", "none"]]
    assert ran["afterReset"] == ran["back"][0], "Reset Column Widths leaves the order"
    for name, (shown, sorts, held) in ran["damaged"].items():
        assert shown == ran["usual"] and set(sorts) == {"none"} and held == {}, name
    assert ran["third"] == [ran["usual"], "{}"], "the third press forgets the order on this PC too"


SORT_SAID = r"""
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? '');
const known = { r24: { year: 2024, form: "1040", return_name: "1040 - John A. Smith" },
                r25: { year: 2025, form: "1040", return_name: "1040 - John A. Smith" },
                b24: { year: 2024, form: "", return_name: "Smith Bakery Books" } };
function shellReturn(path) { return known[path] || null; }
const run = (over) => ({ path: "r25", label: "Smith Family 2025 1040 - John A. Smith", ok: true, error: "", code: "", skipped: "", filed: 0,
  review: 0, waiting: 0, file_errors: [], warnings: [], cancelled: false, ...over });
"""


def test_another_returns_line_keeps_its_bullet_and_says_the_return_by_its_fields(tmp_path):
    """P199 (N3): step 13's extra line, "Smith Family 2024 1040 - John A.
    Smith: Sort Failed: Folder Not Found", had lost its bullet, and said the
    household, the form and the year inside the return's long label. It now
    begins with its bullet and says the return as the lists do (P194-P196):
    the year, the taxpayer and the form, each once; the household is the
    page's own. A return the list does not hold keeps its label."""
    words = api._vocab()
    setup = (f"const vocab = {{ scan: {json.dumps(words['scan'])}, layout: {json.dumps(words['layout'])} }};\n"
             + SORT_SAID + js_function("pagesTaxpayer", "pages.js") + r"""
      let scanning = null, active = "r25", viewGeneration = 1, kept = [];
      function scanDone() {}
      function shellWriteLanded() {}
      function shellAskFirmNow() {}
      function warningNotices() {}
      function adoptList() {}
      function withEng(c) { return [c]; }
      function renderFor() { return true; }
      function failed() {}
      function showReturn() {}
      function runScan() {}
      async function call(args) { return args[0] === "state" ? { summary: { line: "" } } : {}; }
      function keepSortAnswer(ran, asked, answer) { kept.push(answer.map((one) => one.sentence)); }
    """)
    probe = r"""
      const gone = { error: "gone", code: "client-folder-missing" };
      scanning = { asked: "r25" };
      await passEnded({ reply: { runs: [run(gone), run({ ...gone, path: "r24", label: "Smith Family 2024 1040 - John A. Smith" }),
                                        run({ ...gone, path: "b24", label: "Smith Family 2024 Smith Bakery Books" }),
                                        run({ ...gone, path: "x", label: "Smith Family 2023 Old Return" })] } });
      active = "r24"; scanning = { asked: "r25" };
      await passEnded({ reply: { runs: [run(gone)] } });
      return kept;
    """
    kept = run_shell(["passEnded", "scanSummary", "scanFailed", "sortReturnSaid"], setup,
                     "return (async () => {" + probe + "})();", tmp_path, "app.js")
    assert kept[0] == ["Sort Failed: Folder Not Found", "• 2024 John A. Smith 1040: Sort Failed: Folder Not Found",
                       "• 2024 Smith Bakery Books: Sort Failed: Folder Not Found",
                       "• Smith Family 2023 Old Return: Sort Failed: Folder Not Found"]
    assert kept[1] == ["2025 John A. Smith 1040: Sort Failed: Folder Not Found"], "the asked return, said while another is shown"
    step = (REPO / "pilot" / "wintest" / "PROMPT-shell.md").read_text(encoding="utf-8")
    assert "the year, the taxpayer and the form" in step


def test_a_sort_that_finds_nothing_to_do_says_nothing_to_sort(tmp_path):
    """P199 Q1 (built as recommended): a Sort that filed nothing, sent nothing
    to review, met no file it could not sort and no warning said nothing at
    all. It now says "Nothing to Sort"; with a file still arriving it says
    "Nothing Done: 1 Still Syncing." in words already approved; a Sort that
    did anything is unchanged."""
    words = api._vocab()["scan"]
    setup = f"const vocab = {{ scan: {json.dumps(words)} }};\n" + SORT_SAID
    probe = """
      return [scanSummary(run({}), [], ""), scanSummary(run({ waiting: 1 }), [], ""), scanSummary(run({ filed: 1 }), [], ""),
              scanSummary(run({ review: 2 }), [], "").cls, scanSummary(run({ file_errors: ["x"] }), [], "").text.split("\\n")[1],
              scanSummary(run({ cancelled: true }), [], "").text.split("\\n")[0]];
    """
    said = run_shell(["scanFailed", "scanSummary", "sortReturnSaid"], setup, probe, tmp_path, "app.js")
    assert said[0] == {"text": "Nothing to Sort", "cls": "warn"}
    assert said[1] == {"text": "Nothing Done: 1 Still Syncing.", "cls": "warn"}
    assert said[2]["cls"] == "ok" and said[3] == "ok", "a Sort that did something still says nothing (P131)"
    assert said[4] == "But 1 Files Not Sorted." and said[5].startswith("Pass complete")
    from tests.test_api import title_case
    for text in (said[0]["text"], said[1]["text"]):
        assert title_case(text) == text and len(text.split()) <= 5


def test_nothing_to_sort_is_said_only_when_no_return_of_the_household_received_anything(tmp_path):
    """The screen review's M1: the pass sorts the household's one inbox
    across every return and counts per return, so a Sort pressed on the
    1065 can file five documents into the 1040. That Sort did something and
    must not say "Nothing to Sort" (it says nothing, as before P199); one
    where no return filed, sent to review, met a file it could not sort or
    was stopped still says it, and a file arriving for another return is
    still the syncing words."""
    words = api._vocab()["scan"]
    setup = f"const vocab = {{ scan: {json.dumps(words)} }};\n" + SORT_SAID
    probe = """
      const other = (over) => run({ path: "r24", label: "Smith Family 2024 1040 - John A. Smith", ...over });
      return [scanSummary(run({}), [other({ filed: 3 })], ""), scanSummary(run({}), [other({ review: 1 })], ""),
              scanSummary(run({}), [other({ file_errors: ["x"] })], ""), scanSummary(run({}), [other({ cancelled: true })], ""),
              scanSummary(run({}), [other({})], ""), scanSummary(run({}), [other({ waiting: 2 })], "")];
    """
    said = run_shell(["scanFailed", "scanSummary", "sortReturnSaid"], setup, probe, tmp_path, "app.js")
    for one in said[:4]:
        assert "Nothing to Sort" not in one["text"] and one["cls"] == "ok", one
    assert said[4] == {"text": "Nothing to Sort", "cls": "warn"}, "no return of the pass received anything"
    assert said[5] == {"text": "Nothing Done: 2 Still Syncing.", "cls": "warn"}


def test_the_schedule_dialog_says_its_next_run_in_the_apps_clock_style(tmp_path):
    """P199 (N5): "First Run At" showed "6:30 AM" (the time box, in this PC's
    style) beside "Next run: today at 22:30" (the engine's HH:MM). The dialog
    and its saved toast now write the time as every other time the app shows
    is (pagesTime, this PC's own style: "10:30 PM" on the office's), and a
    sentence that does not end in a time is left whole."""
    setup = js_function("pagesTime", "pages.js")
    probe = """
      return [scheduleClock("Next run: today at 22:30"), pagesTime("22:30"), scheduleClock("Next run: tomorrow at 06:30"),
              pagesTime("06:30"), scheduleClock(""), scheduleClock("Off")];
    """
    said = run_shell(["scheduleClock"], setup, probe, tmp_path, "app.js")
    assert said[0] == f"Next run: today at {said[1]}" and "22:30" not in said[0]
    assert said[2] == f"Next run: tomorrow at {said[3]}" and said[4:] == ["", "Off"]
    js = read("app.js")
    assert '$("sc-next").textContent = scheduleClock(current.next_run);' in js
    # The time in the sentence lines up as every date and time does (the
    # screen review's N4: tabular-nums, never a typewriter font).
    selector = next(selector for _m, selector, _b in blocks(read("shell.css")) if selector.strip().startswith(".side-count,"))
    assert "#sc-next" in [part.strip() for part in selector.split(",")]
    assert "${scheduleClock(result.next_run)}" in js
    assert 'toLocaleTimeString([], { hour: "numeric", minute: "2-digit" })' in js_function("pagesTime", "pages.js")



# ── the speed round (pilot SPEC-speed-round.md, P213-P222): node probes ─────


def test_the_reminder_sheet_offers_nothing_to_copy_until_its_own_return_is_read(tmp_path):
    """P213 (findings-4 #2): opened from Reminders on another client, the sheet
    held the return on screen's card and showed Copy, so Copy put that
    client's letter on the clipboard while the next was read. Now the card
    is forgotten, the buttons hidden and the sheet busy, with an outline,
    until the return's own state draws its own card."""
    said = run_reminder_sheet("""
      drawReminder(card("A"));
      const before = actions();
      const opening = openReminder("B");
      const waiting = actions();
      await copyReminder();
      const copiedWhileWaiting = clipboard.length;
      reads[0].land();
      await opening;
      await tick();
      const after = actions();
      await copyReminder();
      return { before, waiting, copiedWhileWaiting, after, clipboard };
    """, tmp_path)
    assert said["before"]["card"] == "Letter for A" and said["before"]["shown"]
    assert said["waiting"] == {"card": None, "shown": False, "busy": "true", "outline": 3, "word": "Loading"}
    assert said["copiedWhileWaiting"] == 0, "another client's letter never reaches the clipboard"
    assert said["after"] == {"card": "Letter for B", "shown": True, "busy": None, "outline": 0, "word": ""}
    assert said["clipboard"] == ["Letter for B"]


def test_next_draft_offers_nothing_to_copy_until_its_return_is_read(tmp_path):
    """P213: Next on the reminder sheet had the same window - the last draft's
    card, with Copy, until the next return's state arrived."""
    said = run_reminder_sheet("""
      const opening = openReminder("B");
      reads[0].land();
      await opening;
      const next = sheetNextDraft();
      const waiting = actions();
      const ready = sheetNow.ready;
      await copyReminder();
      await approveReminder();
      const before = [clipboard.length, sent.length];
      reads[1].land();
      await next;
      await copyReminder();
      return { waiting, ready, before, clipboard, ret: sheetNow.ret, nowReady: sheetNow.ready };
    """, tmp_path)
    assert said["waiting"]["card"] is None and not said["waiting"]["shown"] and said["waiting"]["busy"] == "true"
    assert said["ready"] is False and said["before"] == [0, 0], "neither Copy nor Approve acts while the next draft is read"
    assert said["ret"] == "C" and said["nowReady"] is True
    assert said["clipboard"] == ["Letter for C"]


def test_copy_refuses_a_card_drawn_for_another_return(tmp_path):
    """P213, 4: on a reminder sheet, Copy and Approve act only on a card drawn
    for the sheet's own return, once its read is in; off the sheet the card is
    the return on screen's."""
    said = run_reminder_sheet("""
      const out = [];
      const attempt = async (now, drawnFor, ready) => {
        clipboard.length = 0; sent.length = 0;
        active = drawnFor; drawReminder(card(drawnFor));
        sheetNow = now ? { kind: "reminder", ret: now, ready } : null;
        await copyReminder(); await approveReminder();
        out.push([clipboard.length, sent.length]);
      };
      await attempt("B", "A", true);
      await attempt("B", "B", false);
      await attempt("B", "B", true);
      await attempt(null, "A", false);
      return out;
    """, tmp_path)
    assert said == [[0, 0], [0, 0], [1, 1], [1, 1]]


def test_a_check_sheet_waiting_on_its_return_is_an_outline(tmp_path):
    """P213, 5: Next on a check sheet to a file of another return reads that
    return first; the sheet shows an outline meanwhile, not a blank."""
    said = run_reminder_sheet("""
      const now = { kind: "check", ret: "A", handle: "a", order: [], ready: true, row: {} };
      sheetNow = now;
      sheetShow(now, { ret: "B", handle: "b", name: "b.pdf" });
      const body = $("sheet-check");
      return { outline: body.byClass("row-skeleton").length, word: body.byClass("visually-hidden").map((one) => one.textContent), ready: now.ready };
    """, tmp_path)
    assert said == {"outline": 3, "word": ["Loading"], "ready": False}


def test_after_a_sort_one_overview_is_asked_not_two(tmp_path):
    """P218 (findings-3 #2): a Sort's list starts a `firm`; its state then
    arrived and was compared with the old counts, which queued a second whole
    `firm` whose answer could not differ. A state that arrives while a load
    sent after the write runs is remembered and compared with the new counts:
    one more load only if they still differ."""
    said = run_firm_load("""
      shellFirmNow = { status: "ok", data: heldOf(1) };
      const out = [];
      for (const after of [2, 1]) {
        asked.length = 0;
        shellFirmNow = { status: "ok", data: heldOf(1) };
        shellWriteLanded();                 // passEnded
        shellAdopt({ root: "/root" });      // the list the pass ends with
        shellStateArrived(stateOf(2));      // the shown return's state, after the Sort
        const during = firms();
        await land(0, firmOf(after));
        if (asked.length > 1) await land(1, firmOf(2));
        out.push([during, firms(), shellFirmNow.status, shellFirmHeld.size]);
      }
      return out;
    """, tmp_path)
    assert said[0] == [1, 1, "ok", 0], "the list's own load held what the Sort wrote: no second Overview"
    assert said[1] == [1, 2, "ok", 0], "counts that still differ ask once more"


def test_a_write_that_lands_during_a_load_still_asks_again(tmp_path):
    """P218: a load sent before a write cannot hold what it wrote, so a state
    whose counts differ, from a write that landed while it ran, is followed
    by one more load, as before."""
    said = run_firm_load("""
      shellFirmNow = { status: "ok", data: heldOf(1) };
      shellLoadFirm();                      // F5, say
      shellWriteLanded();                   // a write's reply lands while it runs
      shellStateArrived(stateOf(2));
      const during = firms();
      await land(0, firmOf(1));
      const after = firms();
      await land(1, firmOf(2));
      return [during, after, firms(), shellFirmNow.status];
    """, tmp_path)
    assert said == [1, 2, 2, "ok"]


def test_a_firm_page_drawn_from_held_counts_while_they_are_asked_again_says_updating(tmp_path):
    """P222, W1 (findings-4 #1): a firm page redrawn from old counts for 5-9 s
    after a Sort said nothing of it. While held counts are asked again the page
    is busy, says "Updating" (the path row's one status), and its figures,
    statuses and the side counts are marked to be muted; a redraw meanwhile
    keeps one marker."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: heldOf(1) };
      shellDraw();
      const before = looks();
      shellLoadFirm();
      const during = looks();
      drawPage();
      const again = looks();
      await land(0, firmOf(1));
      return { before, during, again };
    """, tmp_path)
    assert said["before"]["busy"] == "false" and not said["before"]["updating"] and said["before"]["said"] == ""
    assert said["before"]["held"] == [False, False]
    for one in (said["during"], said["again"]):
        assert one["busy"] == "true" and one["updating"]
        assert one["said"] == "Updating" and one["inPage"] == 0
        assert one["held"] == [True, True]
    css = read("shell.css")
    assert "#page.is-updating .figure-number, #page.is-updating .row-status" in css
    assert ".side-section .side-count.is-held:not(:empty) { color: var(--text-caption); }" in css


def test_the_rows_stay_put_while_held_counts_are_asked_again(tmp_path):
    """P222 review: "Updating" was put in as the page's first line and taken
    out again, so every row moved under the pointer and a click could open a
    neighbouring client's return. The word is in the path row's one status,
    kept from the start: the page's rows are the same nodes in the same
    places whether a refresh runs or not, and a redraw meanwhile does not set
    the status's words again, so it is not read out again."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: heldOf(1) };
      shellDraw();
      const idle = looks();
      shellLoadFirm();
      const during = looks();
      drawPage();
      drawPage();
      const redrawn = looks();
      await land(0, firmOf(1));
      return { idle, during, redrawn, after: looks() };
    """, tmp_path)
    assert said["idle"]["rows"] == said["during"]["rows"] == said["redrawn"]["rows"] == said["after"]["rows"]
    assert said["idle"]["rows"] == ["figure-number", "row"]
    assert [one["said"] for one in (said["idle"], said["during"], said["redrawn"], said["after"])] == ["", "Updating", "Updating", ""]
    assert said["during"]["saidSet"] == said["redrawn"]["saidSet"], "a redraw sets the status's words no more"
    assert all(one["inPage"] == 0 for one in said.values())
    html = read("index.html")
    bar = html[html.index('<header id="bar">'):html.index("</header>")]
    assert '<p id="page-updating" class="page-updating" role="status" aria-live="polite"></p>' in bar
    assert "page.prepend(" not in js_function("shellMarkUpdating")


def test_the_path_beside_updating_keeps_its_width_when_the_word_comes():
    """Jason, 2026-10-08: a long path was narrowed while "Updating" showed,
    because the word's slot grew from nothing. The slot is a fixed width
    whether the word shows or not, does not grow or shrink, and cuts
    rather than spills - so the path beside it never moves. It is 8 ch, the
    launch's last counts too: their time is on the Overview's own line
    (P229; Jason, 2026-10-08: "Time on Overview page")."""
    css = stripped(read("shell.css"))
    body = css[css.index(".page-updating {"):]
    body = body[:body.index("}")]
    for declaration in ("flex: none;", "inline-size: 8ch;", "overflow: hidden;", "white-space: nowrap;"):
        assert declaration in body, declaration
    from tracker import api

    assert len(api.SCREEN["updating"]) <= 8, "a longer word needs a wider slot in shell.css"


def test_a_household_or_year_page_marks_its_held_statuses_while_they_are_asked_again(tmp_path):
    """P222 review: a household's and a year's pages follow the counts, so
    while held counts are asked again their status pills are muted and the
    page says Updating, as a firm page does; a return page does not."""
    said = run_firm_page("""
      const out = {};
      for (const level of ["household", "year", "return"]) {
        asked.length = 0;
        shellRoute = { level };
        shellFirmNow = { status: "ok", data: heldOf(1) };
        shellDraw();
        shellLoadFirm();
        const started = looks();
        drawPage();
        out[level] = [started, looks()];
        await land(0, firmOf(1));
      }
      return out;
    """, tmp_path)
    for level in ("household", "year"):
        for one in said[level]:
            assert one["updating"] and one["said"] == "Updating" and one["busy"] == "true", level
    for one in said["return"]:
        assert not one["updating"] and one["said"] == "", "a return page shows no held counts"


def test_a_first_list_that_fails_leaves_no_page_busy_for_ever(tmp_path):
    """P222 review: the first paint is the outline, busy; when the first
    `list` failed nothing drew the page again, so it stayed an outline that
    said it was busy for ever. It goes - the page not busy, its frame alone
    - and the failure's notice keeps its Retry; a page drawn from an earlier
    list keeps what it shows."""
    setup = r"""
let vocab = null; let formsUnloaded = null; const viewGeneration = 0; let refuse = true;
const failures = [];
const failed = (err, retry) => failures.push([err.message, typeof retry]);
const failureSentence = () => "";
const shellAskFirmNow = () => {};
const shellAskFirmLast = () => {};
const loadEngagements = async () => { if (refuse) throw new Error("list refused"); return false; };
const loadForms = async () => {};
"""
    said = run_speed(setup, ("bootstrap", "shellStartFailed"), """
      const page = $("page");
      page.setAttribute("aria-busy", "true");
      for (let i = 0; i < 6; i += 1) { const row = new El("div"); row.className = "row-skeleton"; page.append(row); }
      await bootstrap();
      const first = { busy: page.getAttribute("aria-busy"), kids: page.children.length, failures: failures.slice() };
      vocab = { screen: {} };
      const drawn = new El("div"); drawn.className = "row"; page.replaceChildren(drawn);
      await bootstrap();
      return { first, later: { kids: page.children.map((one) => one.className), failures: failures.length } };
    """, tmp_path)
    assert said["first"] == {"busy": "false", "kids": 0, "failures": [["list refused", "function"]]}
    assert said["later"] == {"kids": ["row"], "failures": 2}


def test_updating_goes_when_the_new_counts_are_drawn(tmp_path):
    """P222, W1: all of it goes when the new reply is drawn - and when it fails,
    the pages keep what they had, unmarked, and the notice says so."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: heldOf(1) };
      shellDraw();
      shellLoadFirm();
      await land(0, firmOf(2));
      const landed = looks();
      shellLoadFirm();
      asked[1].resolve({ error: "refused" });
      await tick();
      return { landed, failed: looks(), status: shellFirmNow.status, notices };
    """, tmp_path)
    for one in (said["landed"], said["failed"]):
        assert one["busy"] == "false" and not one["updating"] and one["said"] == "" and one["held"] == [False, False]
    assert said["status"] == "failed" and said["notices"] == ["Counts Not Available"]


def test_a_firm_wait_over_two_seconds_says_how_many_households_are_read(tmp_path):
    """P222, W2 (findings-4 #8): past 2 s, a firm page waiting with no counts
    says "Reading {n} of {total} Households" from `firm`'s count lines, with a
    determinate progress bar named by those words, updated in place; it goes
    when the reply lands."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellLoadFirm();
      drawPage();
      const start = looks();
      shellFirmProgress({ v: 1, event: "households", done: 0, total: 50 });
      const early = looks();
      const clock = waiting();
      passTime();
      const shown = looks();
      const node = $("page").byClass("firm-reading-words")[0];
      shellFirmProgress({ v: 1, event: "households", done: 25, total: 50 });
      const moved = looks();
      const same = $("page").byClass("firm-reading-words")[0] === node;
      await land(0, firmOf(1));
      return { start, early, clock, shown, moved, same, after: looks(), left: waiting() };
    """, tmp_path)
    assert said["start"]["hidden"] == ["Loading"] and said["start"]["reading"] == [] and said["start"]["busy"] == "true"
    assert said["early"] == said["start"], "under 2 s a count line changes nothing on screen"
    assert said["clock"] == [2000]
    assert said["shown"]["reading"] == ["Reading 0 of 50 Households"] and said["shown"]["hidden"] == []
    assert said["shown"]["bars"] == [["0", "50", "firm-reading-words"]]
    assert said["moved"]["reading"] == ["Reading 25 of 50 Households"] and said["moved"]["bars"] == [["25", "50", "firm-reading-words"]]
    assert said["same"], "the count is updated in place, never the page drawn again"
    assert said["after"]["reading"] == [] and said["after"]["bars"] == [] and said["left"] == []
    bar = js_function("shellReadingNodes")
    assert 'role: "progressbar"' in bar and '"aria-valuemin": "0"' in bar and "last-sort-bar" in bar


def test_a_firm_wait_under_two_seconds_shows_only_the_outline(tmp_path):
    """P222, W2: under 2 s, or with no count line, the outline stays as it is;
    a page drawn from held counts keeps "Updating", never the count."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellLoadFirm();
      drawPage();
      shellFirmProgress({ v: 1, event: "households", done: 25, total: 50 });
      const quick = looks();
      await land(0, firmOf(1));
      shellFirmNow = { status: "idle", data: null };
      shellLoadFirm();
      drawPage();
      passTime();
      const silent = looks();
      await land(1, firmOf(1));
      shellLoadFirm();
      shellFirmProgress({ v: 1, event: "households", done: 25, total: 50 });
      passTime();
      const held = looks();
      await land(2, firmOf(1));
      return { quick, silent, held };
    """, tmp_path)
    for one in (said["quick"], said["silent"]):
        assert one["hidden"] == ["Loading"] and one["reading"] == [] and one["bars"] == []
    assert said["held"]["reading"] == [] and said["held"]["said"] == "Updating"


def test_a_count_line_is_never_taken_for_the_passes(tmp_path):
    """P222: `firm`'s count lines come on the pass's progress channel. They go
    to the Overview's wait, never to the last-sort line, whatever is running."""
    said = run_speed(r"""
      const firmSaid = []; const passSaid = []; const ended = [];
      let scanning = { args: ["run-now", "--engagement", "r1"], pass: null };
      const shellFirmProgress = (said) => firmSaid.push(said);
      const shellProgress = (said) => passSaid.push(said);
      const shellChanged = () => {};
      const passEnded = (m) => ended.push(m);
    """, ("onPassMessage", "drawProgress"), """
      const count = { v: 1, event: "households", done: 25, total: 50 };
      onPassMessage({ args: ["firm"], progress: count });
      onPassMessage({ args: ["run-now", "--engagement", "r1"], progress: { n: 1, of: 3, pass: "p1" } });
      scanning = { args: ["firm"], pass: null };
      onPassMessage({ args: ["firm"], progress: count });
      scanning = null;
      onPassMessage({ args: ["firm"], progress: count });
      return { firmSaid, passSaid, ended };
    """, tmp_path)
    assert len(said["firmSaid"]) == 3
    assert said["passSaid"] == [{"n": 1, "of": 3, "pass": "p1"}] and said["ended"] == []


def test_household_and_year_pages_follow_the_counts_when_they_arrive(tmp_path):
    """P222, 3 (findings-4 #3): a household's and a year's rows carry each
    return's status from the firm's counts, so they are drawn again when the
    counts land, as the firm pages are; a return's own page is not."""
    said = run_firm_load("""
      const out = {};
      for (const level of ["household", "year", "return", "overview", "clients"]) {
        drawn.length = 0; asked.length = 0;
        shellRoute = { level };
        shellFirmNow = { status: "idle", data: null };
        shellLoadFirm();
        await land(0, firmOf(1));
        out[level] = drawn.includes(level);
      }
      return out;
    """, tmp_path)
    assert said == {"household": True, "year": True, "return": False, "overview": True, "clients": True}


def test_a_return_row_waiting_for_its_counts_shows_an_outline_never_a_blank(tmp_path):
    """P222, 3: on a household or year page, while the firm's counts are on
    their way with none held, a return row's status is an aria-hidden outline
    bar - never a pill, never a blank; with the counts failed it is empty (the
    notice says why); with them in, it is the status."""
    probe = """
      const one = { path: "r1", return_name: "1040 - John & Jane Smith", form: "1040", year: 2025, active: true };
      const cell = (status, data) => {
        firmNow = { status, data };
        const [spec] = pagesReturnSpecs([one]);
        const node = pagesRow(spec);
        const box = node.byClass("row-status")[0];
        return { waiting: Boolean(spec.waiting), hidden: box.getAttribute("aria-hidden") || "", outline: box.byClass("outline-bar").length,
                 pill: box.byClass("pill").length, text: box.textContent };
      };
      const held = { return_counts: [{ path: "r1", counts: { needs_you: 2, waiting: 0 } }], replies: {} };
      return [cell("loading", null), cell("failed", null), cell("ok", held), cell("loading", held)];
    """
    setup = """
      let firmNow = { status: "idle", data: null };
      const shellFirm = () => firmNow;
      let shellRoute = { level: "household", household: "h1" };
    """
    said = run_pages_dom(probe, tmp_path, setup)
    assert said[0] == {"waiting": True, "hidden": "true", "outline": 1, "pill": 0, "text": ""}
    assert said[1] == {"waiting": False, "hidden": "", "outline": 0, "pill": 0, "text": ""}
    assert said[2]["waiting"] is False and said[2]["outline"] == 0 and said[2]["text"] == "2 need you"
    assert said[3]["text"] == "2 need you", "counts held are drawn while they are asked again"


def test_a_skeleton_stands_in_the_grid_of_its_own_page(tmp_path):
    """P222, 4 (findings-4 #4): the busy page takes its own list's grid (a
    return page none, never the last list's) and its own shape: the
    Overview's three figures and its group head's line, a return page's
    caption line - with no words, numbers or dots but the hidden Loading."""
    said = run_firm_page("""
      const out = {};
      for (const [level, busy] of [["overview", false], ["needs-review", false], ["return", true]]) {
        $("page").dataset.list = "clients";
        shellRoute = { level }; shellPageBusy = busy; shellFirmNow = { status: "loading", data: null };
        drawPage();
        const page = $("page");
        out[level] = { list: page.dataset.list, figures: page.byClass("figure").length, outlines: page.byClass("outline-bar").length,
                       caption: page.byClass("page-caption").length, rows: page.byClass("row-skeleton").length, text: page.textContent,
                       hidden: page.find((one) => one.byClass("outline-bar").length && one.getAttribute("aria-hidden") === "true").length };
      }
      shellPageBusy = false;
      return out;
    """, tmp_path)
    assert said["overview"] == {"list": "overview", "figures": 3, "outlines": 4, "caption": 0, "rows": 6, "text": "Loading", "hidden": 1}
    assert said["needs-review"] == {"list": "needs_review", "figures": 0, "outlines": 0, "caption": 0, "rows": 6, "text": "Loading", "hidden": 0}
    assert said["return"] == {"list": "", "figures": 0, "outlines": 1, "caption": 1, "rows": 6, "text": "Loading", "hidden": 1}


def _forced_colours() -> dict[str, dict[str, str]]:
    """The shell's forced-colors block, selector by selector."""
    prelude, inner, _end = list(top_level(stripped(read("shell.css"))))[-1]
    assert prelude == "@media (forced-colors: active)"
    found = {}
    for _media, selector, body in blocks(inner):
        for part in selector.split(","):
            found.setdefault(" ".join(part.split()), {}).update(dict(declarations(body)))
    return found


def test_skeleton_bars_are_greytext_in_a_contrast_theme():
    """P222, 5 (findings-4 #5): in a Windows contrast theme an outline bar in
    --bg-hover vanished into Canvas; every outline is GrayText, kept so."""
    rules = _forced_colours()
    drawn = {" ".join(part.split()): dict(declarations(body)) for media, selector, body in blocks(read("shell.css"))
             if not media for part in selector.split(",")}
    for selector in (".row-skeleton > i:not(.hidden)", ".outline-bar:not(.hidden)", ".side-name:empty:not(.hidden)::before"):
        assert rules[selector]["background"] == "GrayText", selector
        assert rules[selector]["forced-color-adjust"] == "none", selector
        assert drawn[selector]["background"] == "var(--bg-hover)", f"{selector}: the bar's own rule, no more specific than this one"
    for selector in ("#page.is-updating .figure-number", "#page.is-updating .row-status", ".side-count.is-held"):
        assert rules[selector]["color"] == "GrayText", selector


def test_the_first_paint_is_the_outline_not_a_blank_shell():
    """P222, 6 (findings-4 #6): before the first reply the page is busy and
    holds six outline rows, and the side panel's names are outlines; the
    first draw replaces all of it."""
    html = read("index.html")
    main = html[html.index('<main id="page"'):html.index("</main>")]
    assert main.startswith('<main id="page" tabindex="-1" aria-busy="true">')
    assert main.count('<div class="row-skeleton" aria-hidden="true"><i></i><i></i></div>') == 6
    assert re.sub(r"<!--.*?-->", "", main, flags=re.S).count("<div") == 6, "nothing but the outline"
    side = next(body for _m, selector, body in blocks(read("shell.css")) if selector.strip() == ".side-name:empty:not(.hidden)::before")
    assert dict(declarations(side))["background"] == "var(--bg-hover)"
    draw = js_function("drawPage")
    assert 'page.setAttribute("aria-busy", busy || updating ? "true" : "false")' in draw and "page.replaceChildren(" in draw
    assert "pagesDraw(route, page)" in draw


def test_the_overview_is_asked_beside_the_list_and_drawn_once_the_words_arrive(tmp_path):
    """P221 (A2, findings-4 #7): `firm` is sent before the list is awaited,
    through window.tracker.call itself, so the first Overview no longer waits
    3 s for the list and then 6 s for itself. Nothing is drawn before the
    vocabulary; the load the list starts adopts the early reply - one `firm`,
    not two - and says its warnings and its failure once the words are there."""
    said = run_firm_load("""
      const words = vocab; vocab = null;
      shellRoute = { level: "overview" };
      shellAskFirmNow();
      shellAskFirmNow();                       // a Retry of the start-up: still one
      const before = { sent: sentEarly.length, status: shellFirmNow.status, drawn: drawn.length };
      vocab = words;                             // the list's reply
      shellAdopt({ root: "/root" });
      const payload = sentEarly[0].payload;
      sentEarly[0].resolve({ ...firmOf(3), warnings: ["Read slowly"] });
      await tick();
      const ok = { payload, sent: sentEarly.length, viaCall: firms(), status: shellFirmNow.status, n: shellFirmNow.data.return_counts[0].counts.needs_you,
                   notices: notices.slice(), drawn: drawn.slice(), clock: shellFirmTimer };
      notices.length = 0;
      shellFirmNow = { status: "idle", data: null };
      shellAskFirmNow();
      shellAdopt({ root: "/root" });
      sentEarly[1].resolve({ error: "The store is busy.", failure: { sentence: "The store is busy." }, warnings: [] });
      await tick();
      return { before, ok, failed: { status: shellFirmNow.status, notices } };
    """, tmp_path, EARLY_FIRM)
    assert said["before"] == {"sent": 1, "status": "loading", "drawn": 0}
    assert said["ok"]["sent"] == 1 and said["ok"]["viaCall"] == 0, "the list's load adopts the early reply"
    assert said["ok"]["payload"] == {"page": {"list": "overview", "at": 0, "order": None, "filter": {"tab": "all"}}}, "the Overview's first page, with no view (SPEC 4.6)"
    assert said["ok"]["status"] == "ok" and said["ok"]["n"] == 3 and said["ok"]["drawn"] == ["overview"]
    assert said["ok"]["notices"] == ["Read slowly"] and said["ok"]["clock"] is None
    assert said["failed"] == {"status": "failed", "notices": ["Counts Not Available"]}
    boot = js_function("bootstrap", "app.js")
    assert boot.index("shellAskFirmNow();") < boot.index("await loadEngagements(")
    early = js_function("shellAskFirmNow")
    assert 'window.tracker.call(["firm"], shellFirmAsk("overview"))' in early and "call([" not in early.replace("tracker.call([", "")


def test_an_early_overview_is_dropped_when_the_list_asks_for_a_folder(tmp_path):
    """P221: a list that says needs_root has no Overview to show: the early
    reply is dropped, its clock stopped, and it draws nothing when it lands."""
    said = run_firm_load("""
      shellRoute = { level: "overview" };
      shellAskFirmNow();
      shellAdopt({ needs_root: true, root: "" });
      const dropped = { status: shellFirmNow.status, early: shellFirmEarly === null, clock: shellFirmTimer };
      sentEarly[0].resolve(firmOf(3));
      await tick();
      return { dropped, data: shellFirmNow.data, status: shellFirmNow.status, drawn, viaCall: firms() };
    """, tmp_path, EARLY_FIRM)
    assert said == {"dropped": {"status": "idle", "early": True, "clock": None}, "data": None, "status": "idle", "drawn": [], "viaCall": 0}


def test_after_a_sort_the_return_and_the_overview_are_asked_beside_the_list(tmp_path):
    """P228 (Jason, 2026-10-08: "Yes, ask all at once"): after a Sort the
    window waited for the whole list (2.5-3 s) before it asked the shown
    return's state, and the list's adoption was what started the Overview.
    Neither needs the list, so the state, the list and `firm` are all sent
    before any lands - the state first - and the list is still asked, once."""
    said = run_sort_end("""
      shellRootSet = true;
      shellFirmNow = { status: "ok", data: heldOf(1) };
      scanning = { asked: "r1" };
      const ending = passEnded({ reply: { runs: [{ path: "r1" }] } });
      const before = { sent: sent(), status: shellFirmNow.status };
      await landOf("state", stateOf(2));
      await ending;
      const drawnBeforeList = { rendered: rendered.slice(), kept: kept.length };
      await landOf("list", { root: "/root" });
      sentEarly[0].resolve(firmOf(2));
      await tick();
      return { before, drawnBeforeList, sent: sent(), viaCall: firms(), status: shellFirmNow.status,
               n: shellFirmNow.data.return_counts[0].counts.needs_you, held: shellFirmHeld.size };
    """, tmp_path)
    assert said["before"] == {"sent": ["state", "list", "firm"], "status": "loading"}, "all three before any lands, the state first"
    assert said["drawnBeforeList"] == {"rendered": ["r1"], "kept": 1}, "the sorted return and its answer wait for no list"
    assert said["sent"] == ["state", "list", "firm"] and said["viaCall"] == 0, "the list's adopt takes the Overview asked, never a second"
    assert said["status"] == "ok" and said["n"] == 2 and said["held"] == 0


def test_a_sorts_list_that_lands_last_changes_nothing_the_state_drew(tmp_path):
    """P228: the list, landing after the state, is adopted - and draws no
    return, asks no state again, and leaves the page the state drew as it
    was; the Overview it adopts is the one asked at the Sort's end."""
    said = run_sort_end("""
      shellRootSet = true;
      shellRoute = { level: "return", ret: "r1" };
      shellFirmNow = { status: "ok", data: heldOf(1) };
      scanning = { asked: "r1" };
      const ending = passEnded({ reply: { runs: [{ path: "r1" }] } });
      await landOf("state", stateOf(2));
      await ending;
      const afterState = { rendered: rendered.slice(), drawn: drawn.slice() };
      await landOf("list", { root: "/root", last_pass: { when: "now" } });
      const afterList = { rendered: rendered.slice(), drawn: drawn.slice(), states: asked.filter((one) => one.args[0] === "state").length,
                          lastPass: shellLastPass };
      sentEarly[0].resolve(firmOf(2));
      await tick();
      return { afterState, afterList, firms: sentEarly.length + firms() };
    """, tmp_path)
    assert said["afterList"]["rendered"] == said["afterState"]["rendered"] == ["r1"]
    assert said["afterList"]["drawn"] == said["afterState"]["drawn"], "the list draws nothing over the state's page"
    assert said["afterList"]["states"] == 1 and said["afterList"]["lastPass"] == {"when": "now"}, "the list is still adopted"
    assert said["firms"] == 1


def test_a_return_chosen_during_the_sort_is_the_one_drawn(tmp_path):
    """P228, with the state now sent first: a return chosen while the Sort's
    state was on its way moves the view on, so that state lands on nothing -
    the return chosen is the one drawn - and the Sort's answer is still kept
    under the return it was asked for."""
    said = run_sort_end("""
      shellRootSet = true;
      shellFirmNow = { status: "ok", data: heldOf(1) };
      scanning = { asked: "r1" };
      const ending = passEnded({ reply: { runs: [{ path: "r1" }] } });
      viewGeneration += 1; active = "r2";       // another return chosen meanwhile
      await landOf("state", stateOf(2));
      await ending;
      await landOf("list", { root: "/root" });
      sentEarly[0].resolve(firmOf(1));
      await tick();
      return { rendered, kept };
    """, tmp_path)
    assert said["rendered"] == [], "the Sort's state never draws over the return chosen since"
    assert said["kept"] == [{"ran": ["r1"], "asked": "r1", "answer": 0}]


def test_a_sorts_list_that_fails_still_lets_its_overview_land(tmp_path):
    """P228: the Overview asked at a Sort's end is adopted by the list's load;
    a list that fails starts that load itself, so no page is left saying
    Updating for ever, and the failure is said as before."""
    said = run_sort_end("""
      const failures = [];
      process.on("unhandledRejection", (err) => failures.push(String(err.message)));
      shellRootSet = true;
      shellFirmNow = { status: "ok", data: heldOf(1) };
      scanning = { asked: "r1" };
      const ending = passEnded({ reply: { runs: [{ path: "r1" }] } });
      await landOf("state", stateOf(1));
      await ending;
      ofCommand("list").resolve({ error: "The list could not be read." });
      await tick();
      sentEarly[0].resolve(firmOf(2));
      await tick();
      return { status: shellFirmNow.status, n: shellFirmNow.data.return_counts[0].counts.needs_you, firms: sentEarly.length + firms(), failures };
    """, tmp_path)
    assert said["status"] == "ok" and said["n"] == 2 and said["firms"] == 1
    assert said["failures"] == ["The list could not be read."], "the list's failure is still said (failed())"


def test_the_sorts_end_asks_the_overview_through_the_one_early_ask():
    """P228: passEnded asks the Overview with shellAskFirmNow (P221's early
    ask, renamed now that it is not only early) after it says the write
    landed, and sends the state before the list, without awaiting the list."""
    ended = js_function("passEnded", "app.js")
    assert ended.index("shellWriteLanded();") < ended.index("shellAskFirmNow();")
    assert ended.index('call(withEng("state"))') < ended.index('call(["list"])')
    assert 'await call(["list"])' not in ended and "adoptList(await" not in ended
    assert "shellAskFirmEarly" not in read("app.js") + read("shell.js")


def test_the_last_counts_are_drawn_marked_updating_as_of_their_time(tmp_path):
    """P229 (Jason, 2026-10-08: build it now, "Updating, as of {time}"
    approved; "Time on Overview page"): at launch `firm-last` is asked
    beside the list and `firm`. Its reply - the firm reply's own fields with
    `last: true` and `as_of` - is drawn once the words are here, under
    P222's marker: the page busy, the path row's 8 ch slot saying Updating
    alone, figures, statuses and side counts muted, the rows usable - and
    the Overview's own line says "Updating, as of {time}", the time in the
    app's words. `last` and `as_of` are not taken for counts."""
    said = run_last_counts("""
      launch();
      const sentAtLaunch = sentEarly.map((one) => one.args[0]);
      early("firm-last").resolve(lastOf(4));
      await tick();
      const beforeWords = { drawn: drawn.length, data: shellFirmNow.data };
      listLands();
      return { sentAtLaunch, beforeWords, marked: looks(), n: counts(), status: shellFirmNow.status,
               overview: overviewSays(), want: `Updating, as of ${timeOf("09:14")}`,
               kept: Object.keys(shellFirmNow.data).sort(), asOf: shellFirm().asOf };
    """, tmp_path)
    assert said["sentAtLaunch"] == ["firm", "firm-last"]
    assert said["beforeWords"] == {"drawn": 0, "data": None}, "nothing is drawn before the vocabulary"
    marked = said["marked"]
    assert marked["busy"] == "true" and marked["updating"] and marked["said"] == "Updating", "the slot says the word alone"
    assert said["overview"] == said["want"], "the time in the app's own words (pagesTime)"
    assert said["overview"].startswith("Updating, as of ") and said["asOf"] == "09:14"
    assert said["kept"] == ["next_sort", "replies", "return_counts", "totals", "view"], "the page, the totals and each return's counts (P278)"
    assert marked["held"] == [True, True] and marked["rows"] == ["figure-number", "row"] and marked["hidden"] == []
    assert said["n"] == 4 and said["status"] == "loading", "the fresh reply is still on its way"
    boot = js_function("bootstrap", "app.js")
    assert boot.index("shellAskFirmLast();") < boot.index("await loadEngagements(")
    assert 'window.tracker.call(["firm-last"], shellFirmAsk("overview"))' in js_function("shellAskFirmLast")


def test_the_fresh_counts_replace_the_last_in_place(tmp_path):
    """P229: when the fresh `firm` lands it replaces the last counts as W1's
    refresh does - the same rows in the same places, the marker gone, the
    fresh numbers drawn - and no other `firm` is asked."""
    said = run_last_counts("""
      launch();
      listLands();
      early("firm-last").resolve(lastOf(4));
      await tick();
      const marked = looks();
      const markedLine = overviewSays();
      early("firm").resolve(firmOf(5));
      await tick();
      return { marked, markedLine, fresh: looks(), freshLine: overviewSays(), n: counts(), status: shellFirmNow.status, asOf: shellFirmAsOf, viaCall: firms() };
    """, tmp_path)
    assert said["marked"]["said"] == "Updating", "the last counts landing after the words are drawn at once"
    assert said["markedLine"].startswith("Updating, as of ") and said["freshLine"] == ""
    fresh = said["fresh"]
    assert fresh["rows"] == said["marked"]["rows"], "no row moves under the mouse"
    assert fresh["busy"] == "false" and not fresh["updating"] and fresh["said"] == "" and fresh["held"] == [False, False]
    assert said["n"] == 5 and said["status"] == "ok" and said["asOf"] == "" and said["viaCall"] == 0


def test_last_counts_that_land_after_the_fresh_are_dropped(tmp_path):
    """P229: a `firm-last` reply that lands after the fresh `firm` is never
    drawn: the fresh counts stay, unmarked."""
    said = run_last_counts("""
      launch();
      listLands();
      early("firm").resolve(firmOf(5));
      await tick();
      early("firm-last").resolve(lastOf(4));
      await tick();
      return { looks: looks(), n: counts(), status: shellFirmNow.status };
    """, tmp_path)
    assert said["n"] == 5 and said["status"] == "ok"
    assert not said["looks"]["updating"] and said["looks"]["said"] == "" and said["looks"]["busy"] == "false"


def test_last_counts_that_land_after_an_unadopted_fresh_reply_are_dropped(tmp_path):
    """P229, the SPEC: "if the real one lands first, firm-last's reply is
    dropped" - also when it lands before the list whose load adopts it.
    The early `firm` lands, then `firm-last`, then the list: the Overview is
    drawn once, from the fresh counts, and the last counts' time is never
    set."""
    said = run_last_counts("""
      launch();
      early("firm").resolve(firmOf(5));
      await tick();
      early("firm-last").resolve(lastOf(4));
      await tick();
      listLands();
      const atList = { asOf: shellFirmAsOf, n: counts() };
      await tick();
      return { atList, drawn: drawn.slice(), n: counts(), status: shellFirmNow.status, asOf: shellFirmAsOf, line: overviewSays() };
    """, tmp_path)
    assert said["atList"] == {"asOf": "", "n": None}, "the last counts are never drawn over a fresh reply"
    assert said["drawn"] == ["overview"], "drawn once"
    assert said["n"] == 5 and said["status"] == "ok" and said["asOf"] == "" and said["line"] == ""


def test_a_failed_refresh_takes_the_last_counts_down(tmp_path):
    """P229: held counts never outlive a failed refresh. The fresh `firm`
    fails: the last counts are taken down, the page shows its failed state
    (its frame alone), and the failure is the one notice with Retry, as today."""
    said = run_last_counts("""
      launch();
      early("firm-last").resolve(lastOf(4));
      await tick();
      listLands();
      const marked = looks();
      early("firm").resolve({ error: "The store is busy.", failure: { sentence: "The store is busy." } });
      await tick();
      return { marked, failed: looks(), data: shellFirmNow.data, status: shellFirmNow.status, notices, asOf: shellFirmAsOf, line: overviewSays() };
    """, tmp_path)
    assert said["marked"]["said"] == "Updating" and said["line"] == ""
    assert said["data"] is None and said["status"] == "failed" and said["asOf"] == ""
    assert said["notices"] == ["Counts Not Available"]
    failed = said["failed"]
    assert failed["rows"] == [] and not failed["updating"] and failed["said"] == "" and failed["held"] == [False, False]


def test_a_refused_or_failed_last_count_ask_shows_nothing(tmp_path):
    """P229: the API answers {last: null, warnings} unless the cache is
    today's, this program's, this clients folder's and whole; that, an error
    reply, an ask that failed, and every shape but the API's own show
    nothing - counts without `last: true` or without an "HH:MM" `as_of`,
    or the counts nested under `last` (the shape Lane R first assumed) - and
    the page waits for the fresh reply as it did (its outline, the hidden
    Loading)."""
    said = run_last_counts("""
      const out = [];
      const { last, ...noLast } = lastOf(4);
      const { as_of, ...noTime } = lastOf(4);
      const shapes = [refused, { error: "Unknown command: firm-last" }, "throw", noLast, noTime, { ...lastOf(4), last: 1 },
                      lastOf(4, "9:14 AM"), { last: { ...firmOf(4), as_of: "09:14" } }, { last: true, as_of: "09:14" }];
      for (const reply of shapes) {
        sentEarly.length = 0;
        shellFirmNow = { status: "idle", data: null }; shellFirmEarly = null; shellFirmLast = null;
        launch();
        listLands();
        if (reply === "throw") window.tracker.call = () => { throw new Error("gone"); };
        if (reply === "throw") { shellFirmLast = null; shellAskFirmLast(); }
        else early("firm-last").resolve(reply);
        await tick();
        drawPage();
        out.push({ data: shellFirmNow.data, hidden: looks().hidden, said: looks().said, pending: shellFirmLast });
        window.tracker.call = (args, payload) => new Promise((resolve) => sentEarly.push({ args, payload, resolve }));
        early("firm").resolve(firmOf(5));
        await tick();
      }
      return out;
    """, tmp_path)
    for one in said:
        assert one == {"data": None, "hidden": ["Loading"], "said": "", "pending": None}


def test_a_list_that_asks_for_a_folder_drops_the_last_counts(tmp_path):
    """P229, as P221 drops the early Overview: a list that asks for a clients
    folder drops the last counts, asked or already drawn."""
    said = run_last_counts("""
      launch();
      vocab = words;
      shellAdopt({ needs_root: true, root: "" });
      early("firm-last").resolve(lastOf(4));
      await tick();
      const asked = { data: shellFirmNow.data, status: shellFirmNow.status };
      sentEarly.length = 0; shellFirmNow = { status: "idle", data: null };
      launch();
      listLands();
      early("firm-last").resolve(lastOf(4));
      await tick();
      const drawnN = counts();
      shellAdopt({ needs_root: true, root: "" });
      return { asked, drawnN, shown: { data: shellFirmNow.data, status: shellFirmNow.status, asOf: shellFirmAsOf } };
    """, tmp_path)
    assert said["asked"] == {"data": None, "status": "idle"}
    assert said["drawnN"] == 4
    assert said["shown"] == {"data": None, "status": "idle", "asOf": ""}


def test_the_last_counts_wait_for_their_own_words(tmp_path):
    """P229: the renderer types no word of its own. A vocabulary without
    `updating_as_of` draws no last counts - the key it lacks goes to the
    error log, loud, never a guess - and the page waits for the fresh reply."""
    said = run_last_counts("""
      const logged = [];
      window.tracker.logError = (text) => logged.push(text);
      launch();
      const { updating_as_of, ...rest } = words.screen;
      words.screen = rest;
      listLands();
      early("firm-last").resolve(lastOf(4));
      await tick();
      drawPage();
      return { data: shellFirmNow.data, logged, said: looks().said };
    """, tmp_path)
    assert said == {"data": None, "logged": ["vocab.screen.updating_as_of"], "said": ""}


def test_a_household_page_opened_on_the_last_counts_says_updating_in_its_slot(tmp_path):
    """P229: a household's or a year's page follows the counts (P222), so
    while the last counts stand its slot says Updating, as a firm page's
    does - the time is the Overview's own line alone (Jason, 2026-10-08:
    "Time on Overview page"); a return page shows no counts and no marker."""
    said = run_last_counts("""
      const out = {};
      for (const level of ["household", "return"]) {
        sentEarly.length = 0; shellFirmNow = { status: "idle", data: null }; shellFirmEarly = null; shellFirmLast = null;
        launch();
        shellRoute = { level };
        listLands();
        early("firm-last").resolve(lastOf(4, "08:05"));
        await tick();
        drawPage();
        out[level] = looks().said;
        early("firm").resolve(firmOf(5));
        await tick();
      }
      return out;
    """, tmp_path)
    assert said == {"household": "Updating", "return": ""}


def test_the_overview_says_the_last_counts_time_on_its_own_work_line(tmp_path):
    """Jason, 2026-10-08: "Time on Overview page". While the launch's last
    counts stand, "Updating, as of {time}" is on the Overview itself, after
    the Work line's count - the page's first group-head line, drawn whenever
    it has rows - with the time in the app's own words; an Overview with no
    work says it under its empty line, below which there is no row. Fresh
    counts say nothing."""
    ran = run_lists("""
      vocab.screen.updating_as_of = "Updating, as of {time}";
      const fresh = draw("overview");
      const freshSaid = fresh.byClass("page-as-of").length;
      shellFirmAsOf = "09:14";
      const marked = draw("overview");
      const head = marked.byClass("group-head")[0];
      const out = { freshSaid, said: marked.byClass("page-as-of").map((one) => one.textContent), want: `Updating, as of ${pagesTime("09:14")}`,
                    head: head.kids.filter((one) => one instanceof Element).map((one) => one.className.split(" ")[0]) };
      const rows = shellFirmData.returns;
      shellFirmData = { ...shellFirmData, returns: [] };
      const empty = draw("overview");
      const kids = empty.kids.filter((one) => one instanceof Element);
      const block = kids[kids.length - 1];
      out.empty = { last: block.className, said: block.byClass("page-as-of").map((one) => one.textContent),
                    lastInBlock: block.kids[block.kids.length - 1].className };
      shellFirmData = { ...shellFirmData, returns: rows };
      return out;
    """, tmp_path)
    assert ran["freshSaid"] == 0, "fresh counts say no time"
    assert ran["said"] == [ran["want"]] and ran["want"].startswith("Updating, as of ")
    assert ran["head"] == ["group-title", "group-count", "page-as-of", "switch"], "after the count, before the tabs"
    assert ran["empty"] == {"last": "page-empty", "said": [ran["want"]], "lastInBlock": "page-empty-note page-as-of"}
    assert 'note: asOf ? h("span", { className: "page-as-of" }, asOf) : null' in js_function("pagesOverview", "pages.js")
    assert "screenWords().updating_as_of, { time: pagesTime(asOf) }" in js_function("pagesAsOf", "pages.js")


def test_no_overview_row_moves_when_the_time_comes_or_goes(tmp_path):
    """Jason's rule (2026-10-08), with the time on the Overview: nothing may
    squeeze the path or move a row. The Overview drawn from the last counts
    and from the fresh ones has the same lines in the same order - the time
    is words inside the Work line, never a line of its own - and the words
    are one line of caption type, cut rather than wrapped, on a line the
    heading sets, so the Work line is as tall with them as without them."""
    ran = run_lists("""
      vocab.screen.updating_as_of = "Updating, as of {time}";
      const lines = (page) => page.kids.filter((one) => one instanceof Element).map((one) => one.className);
      shellFirmAsOf = "09:14";
      const last = draw("overview");
      const marked = { lines: lines(last), rows: names(last) };
      shellFirmAsOf = "";
      const fresh = draw("overview");
      return { marked, fresh: { lines: lines(fresh), rows: names(fresh) } };
    """, tmp_path)
    assert ran["marked"] == ran["fresh"]
    assert ran["marked"]["rows"], "the probe has rows to move"
    css = stripped(read("shell.css"))
    body = css[css.index(".page-as-of {"):]
    body = body[:body.index("}")]
    for declaration in ("min-inline-size: 0;", "overflow: hidden;", "text-overflow: ellipsis;", "white-space: nowrap;",
                        "font-size: var(--fs-caption);", "line-height: var(--lh-caption);"):
        assert declaration in body, declaration
    head = css[css.index(".group-head:not(.hidden) {"):]
    head = head[:head.index("}")]
    assert "display: flex;" in head and "min-height: var(--size-control-sm);" in head
    assert "flex-wrap" not in head, "the line never wraps its words onto a second line"


def test_no_action_reads_the_counts_it_was_drawn_from():
    """P229's safeguard, as W1's "Updating" has it: Open reads the return's
    state afresh, Check opens on a fresh state from a firm page and offers no
    file no longer waiting, and the reminder sheet's Copy and Approve act only
    on a card from the return's own fresh read (P213). None of them reads the
    firm's counts, held, last or fresh - so a marked count can make no action
    act on an old number. Every write is judged under the lock in the engine."""
    for name, source in (("showReturn", "app.js"), ("shellGo", "shell.js"), ("shellOpenState", "shell.js"),
                         ("openCheck", "sheet.js"), ("sheetShow", "sheet.js"), ("sheetDrawCheck", "sheet.js"),
                         ("openReminder", "sheet.js"), ("copyReminder", "app.js"), ("approveReminder", "app.js")):
        body = js_function(name, source)
        for counts in ("shellFirm(", "shellFirmNow", "shellFirmAsOf", "shellFirmLast"):
            assert counts not in body, (name, counts)
    check = js_function("openCheck", "sheet.js")
    assert "FIRM_LEVELS.indexOf(shellRoute.level) === -1" in check and "showReturn(ret)" in check
    assert "forgetReminderCard();" in js_function("openReminder", "sheet.js")


# ── a scheduled pass in progress is not a failure (pilot P256) ─────────────

#: A fake last-sort box over the FAKE_DOM elements: classList with remove, and
#: the words the API's ``screen.last_sort`` and ``screen.sort`` carry.
LAST_SORT_FAKES = FAKE_DOM + lift_line("const EL_ATTRIBUTES = new Set([", "app.js") + r"""
class Box extends Element {
  get classList() {
    const self = this;
    return { add(one) { if (!self.className.split(" ").includes(one)) self.className = `${self.className} ${one}`.trim(); },
             remove(one) { self.className = self.className.split(" ").filter((c) => c && c !== one).join(" "); },
             contains(one) { return self.className.split(" ").includes(one); } };
  }
}
const box = new Box("div");
let scanning = null; let shellLastPass = null; let shellProgressNow = null;
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
const $ = () => box;
const screenWords = () => ({
  last_sort: { today: "Sorted {time}", other_day: "Sorted {date}", failed: "Sort Failed", never: "Not Sorted Yet",
               running: "Sorting {n} of {total}", done: "Sorted", scheduled: "Scheduled Sorting WORD" },
  sort: { stopping: "Stopping" } });
const sameDay = () => true; const icon = () => new Element("svg"); const setTip = () => {};
const drawn = (pass, running) => {
  shellLastPass = pass; scanning = running;
  drawLastSort();
  const bars = box.byClass("last-sort-bar");
  return { text: box.byClass("last-sort-text").map((one) => one.textContent), failed: box.classList.contains("is-failed"),
           bars: bars.length, role: bars.length ? bars[0].attrs.role : null, values: bars.length ? Object.keys(bars[0].attrs).filter((k) => k.startsWith("aria-value") && k !== "aria-valuemin") : null,
           fillWidth: bars.length ? bars[0].kids[0].style.props.width || null : null };
};
"""


def test_a_scheduled_pass_still_running_is_drawn_as_sorting_not_as_a_failure(tmp_path):
    """P256: the engine's last-pass file records started, succeeded and
    failed. A pass the schedule is running answers ``ok: false, running:
    true``, and the last-sort line draws the API's ``scheduled`` word with the
    bar and no values - never the failed word, never ``is-failed``. A pass that
    failed (``running: false``) is drawn as before, and the app's own running
    sort still draws its count."""
    ran = run_shell(["el", "h", "drawLastSort"], LAST_SORT_FAKES, """
      const when = "2026-09-30T06:00:00";
      shellProgressNow = { n: 2, total: 5 };
      return {
        scheduled: drawn({ text: "Started", level: "ok", ok: false, running: true, when }, null),
        failed: drawn({ text: "Failed", level: "err", ok: false, running: false, when }, null),
        own: drawn({ text: "Started", level: "ok", ok: false, running: true, when }, { pass: "p" }),
        stopping: drawn(null, { pass: "p", stopping: true }),
      };
    """, tmp_path, "app.js")
    assert ran["scheduled"] == {"text": ["Scheduled Sorting WORD"], "failed": False, "bars": 1,
                                "role": "progressbar", "values": [], "fillWidth": None}
    assert ran["failed"]["text"] == ["Sort Failed"] and ran["failed"]["failed"] is True and ran["failed"]["bars"] == 0
    assert ran["own"]["text"] == ["Sorting 2 of 5"] and ran["own"]["failed"] is False
    assert ran["own"]["values"] == ["aria-valuemax", "aria-valuenow"] and ran["own"]["fillWidth"] == "40%"
    assert ran["stopping"]["text"] == ["Stopping"]
    body = js_function("drawLastSort", "shell.js")
    assert body.index("if (scanning) {") < body.index("last.running") < body.index("words.never"), \
        "after the app's own sort, before the never check"
    assert "scheduled" not in re.sub(r"words\.scheduled", "", stripped_js("shell.js")), "the page types no word of it"


#: What lastPassStep's table says, one claim per row: held, fresh, the answer.
LAST_PASS_STEPS = [
    ("a pass that was running and has ended is read again", {"running": True, "when": "A"}, {"running": False, "when": "A", "ok": True}, "reread"),
    ("a failed ending is read again too", {"running": True, "when": "A"}, {"running": False, "when": "A", "ok": False}, "reread"),
    ("a whole pass that came and went between two asks is read again", {"running": False, "when": "A"}, {"running": False, "when": "B"}, "reread"),
    ("a first ended pass, when none was held, is read again", None, {"running": False, "when": "A"}, "reread"),
    ("a first ended pass, when the held one had no date, is read again", {"running": False, "when": None}, {"running": False, "when": "A"}, "reread"),
    ("a pass that has started since is adopted, not read again", {"running": False, "when": "A"}, {"running": True, "when": "B"}, "adopt"),
    ("a running pass, when none was held, is adopted", None, {"running": True, "when": "A"}, "adopt"),
    ("a second running pass with another start is adopted", {"running": True, "when": "A"}, {"running": True, "when": "B"}, "adopt"),
    ("the same running pass is the same", {"running": True, "when": "A"}, {"running": True, "when": "A"}, "same"),
    ("the same ended pass is the same", {"running": False, "when": "A"}, {"running": False, "when": "A"}, "same"),
    ("no pass held and none to be had is the same", None, {"running": False, "when": None}, "same"),
    ("a file that has gone unreadable ended nothing", {"running": False, "when": "A"}, {"running": False, "when": None}, "same"),
    ("a reply without a last pass is the same", {"running": False, "when": "A"}, None, "same"),
]

LAST_PASS_WATCH_FAKES = r"""
let vocab = {};
let scanning = null; let shellLastPass = null;
let shellLastPassAsking = false; let shellLastPassStopped = false; let shellLastPassAt = 0;
let shellLastPassOwed = false; let shellLastPassAgain = false;
const SHELL_FOCUS_QUIET_MS = 5000; const document = { hidden: false };
const seen = []; let reply = null; let asked = 0;
let listReply = { listed: true }; let during = null;
let shellRoute = { level: "overview" }; let dialogStack = []; let shellReturnStale = false; let throwing = false;
const showReturn = async (path) => { seen.push("showReturn:" + path); if (throwing) throw new Error("boom return"); };
const shellChanged = () => seen.push("changed");
const adoptList = (listed) => seen.push(listed === listReply ? "adopt-list" : "adopt-other");
const failed = (err) => seen.push("failed:" + err.message);
const call = async (args) => {
  asked += 1; seen.push("call:" + args.join(" "));
  if (during) during(args[0]);
  const out = args[0] === "list" ? listReply : reply;
  if (out instanceof Error) throw out;
  return args[0] === "list" ? out : { last_pass: out };
};
const tick = async (held, fresh, running = null) => {
  seen.length = 0; shellLastPass = held; reply = fresh; scanning = running; shellLastPassStopped = false;
  await shellAskLastPass();
  return { seen: seen.slice(), held: shellLastPass };
};
"""


def test_the_shell_asks_list_again_once_a_scheduled_pass_has_ended(tmp_path):
    """P256: ``lastPassStep`` says what a fresh last-pass means to the shell
    (every row of its table by the claim it makes), and an ask (P277: made
    when the file changes) acts on it: a pass that ended asks ``list`` once and adopts it, as F5 and
    ``passEnded`` do (never the start-up path, ``loadEngagements``: it would
    rebuild an open Schedule dialog's interval list and redraw the page); a
    pass that started is adopted and drawn; nothing changed does nothing; the
    app's own pass is not interrupted; a failing ask is said once and stops
    the asking, which the next list adopt starts again."""
    ran = run_shell(["lastPassStep", "shellAskLastPass"], LAST_PASS_WATCH_FAKES, f"""
      const steps = {json.dumps(LAST_PASS_STEPS)}.map(([claim, held, fresh]) => lastPassStep(held, fresh));
      return (async () => {{
        const ended = await tick({{ running: true, when: "A" }}, {{ running: false, when: "A", ok: true }});
        const started = await tick({{ running: false, when: "A" }}, {{ running: true, when: "B" }});
        const same = await tick({{ running: true, when: "A" }}, {{ running: true, when: "A" }});
        const idle = await tick({{ running: false, when: "A" }}, {{ running: false, when: "A" }});
        const own = await tick({{ running: false, when: "A" }}, {{ running: false, when: "B" }}, {{ pass: "p" }});
        const broken = await tick({{ running: true, when: "A" }}, new Error("boom"));
        const stopped = shellLastPassStopped;
        seen.length = 0; await shellAskLastPass(); const stoppedTicks = seen.slice();
        return {{ steps, ended, started, same, idle, own, broken, stoppedTicks, stopped }};
      }})();
    """, tmp_path)
    assert ran["steps"] == [row[3] for row in LAST_PASS_STEPS], [row[0] for row in LAST_PASS_STEPS]
    assert ran["ended"]["seen"] == ["call:last-pass", "call:list", "adopt-list"], "a tick that sees the pass end asks list once and adopts it"
    assert ran["started"]["seen"] == ["call:last-pass", "changed"]
    assert ran["started"]["held"] == {"running": True, "when": "B"}, "and the page draws the new state"
    assert ran["same"]["seen"] == ["call:last-pass"] and ran["idle"]["seen"] == ["call:last-pass"]
    assert ran["own"]["seen"] == [], "an ask during the app's own pass calls nothing"
    assert ran["broken"]["seen"] == ["call:last-pass", "failed:boom"], "a throwing call is handed to failed once"
    assert ran["stoppedTicks"] == [] and ran["stopped"] is True, "no notice per ask once stopped"
    assert "loadEngagements" not in re.sub(r"//.*", "", js_function("shellAskLastPass", "shell.js")), \
        "the reread is the list adopted, never the start-up path"


def test_a_throwing_reread_is_said_once_and_stops_the_watch(tmp_path):
    """P256 (the builder's deviation 2, SPEC 1.2): the ``list`` an ask makes
    when a pass has ended can throw too. It is said once by ``failed`` and
    the asking stops - no loop on a failing ``list`` - until the next list
    adopt starts it again."""
    ran = run_shell(["lastPassStep", "shellAskLastPass"], LAST_PASS_WATCH_FAKES, """
      listReply = new Error("boom list");
      return (async () => {
        const broken = await tick({ running: true, when: "A" }, { running: false, when: "A", ok: true });
        const stopped = shellLastPassStopped;
        seen.length = 0; const before = asked; await shellAskLastPass();
        return { broken, stopped, quiet: seen.slice(), askedAgain: asked - before };
      })();
    """, tmp_path)
    assert ran["broken"]["seen"] == ["call:last-pass", "call:list", "failed:boom list"], "said once, and not adopted"
    assert ran["stopped"] is True, "the asking is stopped"
    assert ran["quiet"] == [] and ran["askedAgain"] == 0, "and a later ask says and asks nothing"


def test_an_ask_before_the_first_list_or_after_a_stop_does_nothing(tmp_path):
    """P256 (the builder's deviation 3): a focus tick before the first list
    has landed (no vocabulary, so the shell has not learned which commands it
    may send) and one after a stop are \"not started\" and \"stopped\", not
    silent errors: nothing is asked, drawn or said."""
    ran = run_shell(["lastPassStep", "shellAskLastPass"], LAST_PASS_WATCH_FAKES, """
      return (async () => {
        vocab = null; shellLastPass = null; reply = { running: false, when: "A" };
        await shellAskLastPass();
        const early = { seen: seen.slice(), asked };
        vocab = {}; shellLastPassStopped = true;
        await shellAskLastPass();
        return { early, late: { seen: seen.slice(), asked } };
      })();
    """, tmp_path)
    assert ran["early"] == {"seen": [], "asked": 0}, "before the first list"
    assert ran["late"] == {"seen": [], "asked": 0}, "after a stop"
    assert re.search(r"if \(shellLastPassAsking \|\| shellLastPassStopped \|\| !vocab\) return;", js_function("shellAskLastPass", "shell.js"))


def test_a_reply_landing_after_the_apps_own_sort_began_does_nothing(tmp_path):
    """P256 (review 1, finding 4): ``scanning`` is checked again when the
    reply lands, not only before the call. A ``last-pass`` reply, or the
    ``list`` a reread asked, that arrives after the app's own Sort started
    adopts, draws and reads nothing - the pass's end asks ``list`` itself."""
    ran = run_shell(["lastPassStep", "shellAskLastPass"], LAST_PASS_WATCH_FAKES, """
      const landed = async (which, held, fresh) => {
        during = (name) => { if (name === which) scanning = { pass: "p" }; };
        const out = await tick(held, fresh);
        during = null;
        return { ...out, scanning: scanning !== null };
      };
      return (async () => {
        const reread = await landed("last-pass", { running: true, when: "A" }, { running: false, when: "A", ok: true });
        const adopt = await landed("last-pass", { running: false, when: "A" }, { running: true, when: "B" });
        const list = await landed("list", { running: true, when: "A" }, { running: false, when: "A", ok: true });
        return { reread, adopt, list };
      })();
    """, tmp_path)
    assert ran["reread"]["seen"] == ["call:last-pass"] and ran["reread"]["held"] == {"running": True, "when": "A"}, "no list asked"
    assert ran["adopt"]["seen"] == ["call:last-pass"] and ran["adopt"]["held"] == {"running": False, "when": "A"}, "nothing adopted or drawn"
    assert ran["list"]["seen"] == ["call:last-pass", "call:list"], "a list landing late is not adopted"
    assert all(ran[name]["scanning"] for name in ran), "the app's own pass was running when each reply landed"


def test_the_harness_stub_answers_last_pass_with_the_pass_its_list_carries(tmp_path):
    """P256 (review 1, finding 5): a window focus or a run past the idle
    cadence asks ``last-pass``; the screenshot tool's stub answers it with a
    not-running pass that is the very object its ``list`` carries (nothing
    new, so no failed notice lands on a screenshot) and the API's
    ``warnings``; ``setup`` has none, as its list has none."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    harness = (REPO / "pilot" / "harness" / "stub.js").read_text(encoding="utf-8")
    script = tmp_path / "stub_probe.js"
    script.write_text(f"""
const vm = require("vm");
const stubSource = {json.dumps(harness)};
const mirror = JSON.parse({json.dumps(json.dumps(api._vocab()))});
(async () => {{
  const out = {{}};
  for (const scenario of ["normal", "failed", "setup"]) {{
    const window = {{ __VOCAB__: mirror }};
    vm.runInContext(stubSource, vm.createContext({{ window, location: {{ search: `?scenario=${{scenario}}` }}, URLSearchParams, setTimeout, console, Date, Intl }}));
    const list = await window.tracker.call(["list"]);
    out[scenario] = {{ list: list.last_pass, asked: await window.tracker.call(["last-pass"]) }};
  }}
  process.stdout.write(JSON.stringify(out));
}})();
""", encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    ran = json.loads(done.stdout)
    for scenario, one in ran.items():
        assert one["asked"] == {"last_pass": one["list"], "warnings": []}, scenario
        assert not (one["list"] or {}).get("running"), scenario
    assert ran["normal"]["list"]["running"] is False and ran["failed"]["list"]["ok"] is False and ran["setup"]["list"] is None


def test_an_ask_never_overlaps_itself_and_a_list_landing_clears_a_stop(tmp_path):
    """P256: one ask at a time (an ``asking`` flag, as the lock watch has);
    ``shellAdopt`` clears a stop whenever a list lands and arms nothing (P277:
    there is no timer); the window's ``focus`` asks once at once."""
    ran = run_shell(["lastPassStep", "shellAskLastPass"], LAST_PASS_WATCH_FAKES, """
      shellLastPass = { running: false, when: "A" }; reply = { running: false, when: "A" }; scanning = null;
      return (async () => {
        const first = shellAskLastPass();
        const second = shellAskLastPass();
        await Promise.all([first, second]);
        return { asked };
      })();
    """, tmp_path)
    assert ran["asked"] == 1, "an ask that arrives while one is on its way is dropped"
    shell = stripped_js("shell.js")
    adopt = js_function("shellAdopt", "shell.js")
    assert "shellLastPassStopped = false;" in adopt and "LastPass(" not in adopt, "a list landing clears a stop and arms nothing"
    assert 'window.addEventListener("focus", shellFocused);' in shell


# ── P277 (SPEC-ui-menu-speed §1): the page asks when the file changes ─────

def test_a_change_of_the_last_pass_file_asks_last_pass_once(tmp_path):
    """P277: the ``last-pass-changed`` message (which carries nothing) makes
    the page ask ``last-pass`` once; a pass that has ended then asks ``list``
    once and adopts it, and a message with nothing new asks nothing more."""
    ran = run_shell(["lastPassStep", "shellAskLastPass", "shellLastPassChanged"], LAST_PASS_WATCH_FAKES, """
      return (async () => {
        const settle = () => new Promise((r) => setImmediate(r));
        shellLastPass = { running: true, when: "A" }; reply = { running: false, when: "A", ok: true };
        seen.length = 0; shellLastPassChanged(); await settle();
        const ended = seen.slice();
        seen.length = 0; reply = { running: false, when: "A", ok: true }; shellLastPass = reply; shellLastPassChanged(); await settle();
        return { ended, quiet: seen.slice(), asked };
      })();
    """, tmp_path)
    assert ran["ended"] == ["call:last-pass", "call:list", "adopt-list"], "one ask, and the list once because a pass ended"
    assert ran["quiet"] == ["call:last-pass"], "nothing new: one ask and nothing more"
    assert ran["asked"] == 3
    assert re.search(r"window\.tracker\.onLastPassChanged\(shellLastPassChanged\);", stripped_js("shell.js"))


def test_a_change_while_hidden_is_asked_when_the_window_is_shown(tmp_path):
    """P277: a hidden window sends nothing; the change is owed, and the window
    being shown asks once (not once per change that came while it was hidden)."""
    ran = run_shell(["lastPassStep", "shellAskLastPass", "shellLastPassChanged", "shellShown"], LAST_PASS_WATCH_FAKES, """
      return (async () => {
        const settle = () => new Promise((r) => setImmediate(r));
        shellLastPass = { running: false, when: "A" }; reply = { running: false, when: "A" };
        document.hidden = true;
        shellLastPassChanged(); shellLastPassChanged(); shellLastPassChanged(); await settle();
        const hidden = { asked, owed: shellLastPassOwed };
        document.hidden = false; shellShown(); await settle();
        return { hidden, shown: { asked, owed: shellLastPassOwed } };
      })();
    """, tmp_path)
    assert ran["hidden"] == {"asked": 0, "owed": True}
    assert ran["shown"] == {"asked": 1, "owed": False}


def test_a_change_during_an_ask_asks_once_more_when_it_lands(tmp_path):
    """P277: a change is never dropped. One that comes while an ask is on its
    way sets a flag, and one more ask follows when that one lands - however
    many changes came - so a sort that starts and ends inside one ask is
    still seen. An ask that fails does not follow itself."""
    ran = run_shell(["lastPassStep", "shellAskLastPass", "shellLastPassChanged"], LAST_PASS_WATCH_FAKES, """
      return (async () => {
        const settle = () => new Promise((r) => setImmediate(r));
        shellLastPass = { running: false, when: "A" }; reply = { running: false, when: "A" };
        let fired = false;
        during = () => { if (!fired) { fired = true; shellLastPassChanged(); shellLastPassChanged(); } };
        shellLastPassChanged(); await settle(); await settle();
        const followed = { asked, again: shellLastPassAgain, asking: shellLastPassAsking };
        during = () => { shellLastPassChanged(); }; reply = new Error("boom"); asked = 0; seen.length = 0;
        shellLastPassChanged(); await settle(); await settle();
        return { followed, failed: { asked, again: shellLastPassAgain, seen: seen.slice() } };
      })();
    """, tmp_path)
    assert ran["followed"] == {"asked": 2, "again": False, "asking": False}, "two changes during one ask: one more ask"
    assert ran["failed"] == {"asked": 1, "again": False, "seen": ["call:last-pass", "failed:boom"]}, "a failed ask does not ask again"


def test_no_timer_asks_last_pass():
    """P277: nothing in the renderer times the last-pass ask (no ``setTimeout``
    reaches ``shellAskLastPass``), the polling watch and its vocabulary are
    gone, and the page is not told where the file is."""
    shell = stripped_js("shell.js")
    ask = js_function("shellAskLastPass", "shell.js")
    assert "setTimeout" not in ask and "setInterval" not in ask
    assert not re.search(r"set(?:Timeout|Interval)\([^)]*(?:AskLastPass|LastPassChanged|shellFocused|shellShown)", shell)
    for gone in ("last_pass_watch", "shellArmLastPass", "shellWatchLastPass", "shellLastPassTimer"):
        assert gone not in shell, gone
    assert "last_pass_watch" not in "".join(read(name) for name in ("app.js", "pages.js", "sheet.js"))
    assert "last_pass_file" not in shell, "the page is not told where the file is"


# ── a notice's Details (pilot P257) ───────────────────────────────────────

NOTICE_DETAIL_FAKES = FAKE_DOM + lift_line("const EL_ATTRIBUTES = new Set([", "app.js") + r"""
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
let vocab = { screen: { notices: { details: "Details" }, icons: { dismiss: "Dismiss" } }, notices: { repeated: "(x{n})" } };
let locked = false;
let shellRoute = { level: "overview" };
const noticeButton = (act) => { const one = new Element("button"); one.dataset.act = act; return one; };
const setTip = () => {};
const draw = (entry) => { entry.node = new Element("div"); drawNotice(entry); return entry.node; };
const shape = (node) => node.kids.map((one) => (one.tag === "details"
  ? ["details", one.className, one.open, one.kids.map((kid) => [kid.tag, kid.className, kid.textContent, kid.kids.filter((line) => line.tag).map((line) => line.textContent)])]
  : [one.tag, one.className, one.textContent]));
"""


def test_a_notice_with_a_detail_keeps_one_line_and_a_closed_details_block(tmp_path):
    """P257: ``detail`` is drawn after the line and before the buttons as a
    closed ``details`` whose summary is the API's word, one block per line;
    the dismiss ends the notice; no detail, no element; a vocabulary without
    the word is a loud failure, never a blank summary."""
    ran = run_shell(["el", "detailOf", "retryOf", "drawNotice"], NOTICE_DETAIL_FAKES, """
      const base = { sentence: "Machine Needs Attention", kind: "warning", count: 1 };
      const withDetail = shape(draw({ ...base, detail: "The app is running from /Volumes/X.\\nDrag it into Applications." }));
      const without = shape(draw({ ...base, detail: "" }));
      const failing = shape(draw({ ...base, kind: "failed", detail: "a\\nb", retry: () => {} }));
      vocab = { screen: { notices: {}, icons: { dismiss: "Dismiss" } } };
      let missing = ""; try { draw({ ...base, detail: "x" }); } catch (err) { missing = err.message; }
      return { withDetail, without, failing, missing };
    """, tmp_path, "app.js")
    assert ran["withDetail"] == [
        ["span", "notice-text", "Machine Needs Attention"],
        ["details", "notice-detail", False, [["summary", "", "Details", []],
                                              ["div", "notice-detail-text", "The app is running from /Volumes/X.Drag it into Applications.",
                                               ["The app is running from /Volumes/X.", "Drag it into Applications."]]]],
        ["button", "", ""]], "the line, the closed Details, then the dismiss"
    assert [one[0] for one in ran["without"]] == ["span", "button"], "no detail, no element"
    assert [one[0] for one in ran["failing"]] == ["span", "details", "button", "button"], "before Retry and the dismiss"
    assert ran["missing"] == "vocab.screen.notices.details"
    app = stripped_js("app.js")
    assert "entry.detail = failure.detail || entry.detail;" in app and "had.detail === detail" in app


def test_machine_warnings_and_setup_findings_reach_the_screen_as_details(tmp_path):
    """P257: the machine warnings and the after-install findings keep their
    one short line and now carry the engine's sentences as the notice's
    detail, lines joined by a newline, and the error log still gets the same
    text."""
    ran = run_shell(["renderMachineNotices", "syncNotices", "renderAfterInstall", "shortNotice"], r"""
      let vocab = { screen: { notices: { machine: "Machine Needs Attention", reader: "Reader" } },
                    after_install: { heading: "Setup Needs Attention", wait: "A household waits." } };
      const keyedNotices = new Map(); const seen = []; const logged = [];
      const window = { tracker: { logError: (text) => logged.push(text) } };
      const keyedNotice = (key, failure) => { seen.push([key.split(":")[0], failure.sentence, failure.kind, failure.detail || ""]); keyedNotices.set(key, 1); return true; };
      const clearNotice = (key) => keyedNotices.delete(key);
    """, """
      renderMachineNotices({ machine_warnings: ["The app is running from /Volumes/X. Drag it into Applications.", "Second warning."] });
      const machine = { seen: seen.slice(), logged: logged.slice() };
      seen.length = 0; logged.length = 0;
      renderAfterInstall({ wait: "A household waits.", findings: ["Finding one"], failed: ["It could not run"] });
      return { machine, setup: { seen, logged } };
    """, tmp_path, "app.js")
    machine = "The app is running from /Volumes/X. Drag it into Applications.\nSecond warning."
    assert ran["machine"]["seen"] == [["machine", "Machine Needs Attention", "warning", machine]]
    assert ran["machine"]["logged"] == [machine], "and the error log has the same text"
    setup = "A household waits.\nIt could not run\nFinding one"
    assert ran["setup"]["seen"] == [["after-install", "Setup Needs Attention", "failed", setup]]
    assert ran["setup"]["logged"] == [setup]


def test_only_the_machine_warnings_the_pause_the_feeds_and_the_setup_findings_put_a_detail_on_the_screen(tmp_path):
    """P257 (review 1, finding 2) and P259 (Q3): a broken row's error and
    stack stay in the error log - never under Details (SPEC-shell E30, 11.1,
    principle 7). Only an entry marked ``shown`` passes its detail to the
    notice: the machine warnings', the household pause's and the prior-year
    feed's."""
    ran = run_pages(["pagesReportBroken", "pagesHouseholdNotices", "shortNotice"], js_function("syncNotices", "app.js") + "\n"
                    + js_function("renderMachineNotices", "app.js") + r"""
      const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
      let vocab = { shell: { page_error: "{kind} while drawing" }, notices: { about: "{label}: {sentence}" },
        household: { two_open_years: "Two years open", accept_folder_name: "Accept" },
        screen: { notices: { machine: "Machine Needs Attention", renamed: "Folder Renamed", feed: "Feed Not Resolved", reader: "Reader" } } };
      const keyedNotices = new Map(); const seen = []; const logged = [];
      const window = { tracker: { logError: (text) => logged.push(text) } };
      const keyedNotice = (key, failure) => { seen.push([key.split(":")[0], failure.sentence, failure.detail || ""]); keyedNotices.set(key, 1); return true; };
      const clearNotice = (key) => keyedNotices.delete(key);
      const acceptFolderName = () => {};
      let pagesBroken = [{ name: "Row A", err: Object.assign(new Error("MESSAGE"), { stack: "STACK at /Users/x/app.js:1" }) }];
      let lastState = null;
    """, """
      pagesReportBroken();
      lastState = { household: { path: "h1", open_years: [2025], pause: { sentence: "PAUSED LONG", scope: "household" }, feeds: [{ warning: "FEED LONG" }] } };
      pagesHouseholdNotices({ level: "household", household: "h1" });
      renderMachineNotices({ machine_warnings: ["MACHINE LONG"] });
      return { seen, logged };
    """, tmp_path)
    assert len(ran["seen"]) == 4, "the row, the renamed folder, the feed, the machine"
    assert ran["seen"][0][2] == "", "a broken row's error and stack are not passed to the notice"
    assert ran["seen"][1:] == [["household", "Folder Renamed", "PAUSED LONG"], ["household", "Feed Not Resolved", "FEED LONG"],
                               ["machine", "Machine Needs Attention", "MACHINE LONG"]], "the pause, the feed and the machine warnings' are"
    logged = "\n".join(ran["logged"])
    assert "STACK at /Users/x/app.js:1" in logged and "PAUSED LONG" in logged and "FEED LONG" in logged and "MACHINE LONG" in logged, \
        "and every one is still in the error log"


def test_details_are_open_on_the_setup_page_and_closed_elsewhere(tmp_path):
    """P259 (Q2, SPEC-mac-check-fixes 4.1): the setup page is where a person
    has come to read what to do, so a Details drawn there is open; drawn on
    any other page it is closed until clicked. The choice is made once, at
    the moment of drawing: a notice stays as the person left it."""
    ran = run_shell(["el", "detailOf", "retryOf", "drawNotice"], NOTICE_DETAIL_FAKES, """
      const base = { sentence: "Machine Needs Attention", kind: "warning", count: 1, detail: "The app is running from /Volumes/X." };
      const opened = (node) => node.kids.find((one) => one.tag === "details").open;
      const out = {};
      shellRoute = { level: "setup" };
      const onSetup = draw({ ...base });
      out.setup = opened(onSetup);
      shellRoute = { level: "overview" };
      out.overview = opened(draw({ ...base }));
      out.setupAfterLeaving = opened(onSetup);
      const onOverview = draw({ ...base });
      shellRoute = { level: "setup" };
      out.overviewAfterArriving = opened(onOverview);
      return out;
    """, tmp_path, "app.js")
    assert ran == {"setup": True, "overview": False, "setupAfterLeaving": True, "overviewAfterArriving": False}
    app = stripped_js("app.js")
    assert 'open: shellRoute.level === "setup"' in app and '"aria-sort", "aria-haspopup", "open",' in app


def test_the_notices_of_a_first_start_are_drawn_after_the_setup_page_takes_the_screen(tmp_path):
    """P259 (Q2, SPEC-mac-check-fixes 4.1, review 1 finding 1): with no clients
    folder chosen, ``loadEngagements`` changes the route to setup before it
    draws the machine's and the step's notices, so their Details are open at
    a first start, at the Mac check's disk-image warning and when the clients
    folder has gone missing. With a clients folder the route is a working page
    and the same notices are closed. Driven through the real
    ``loadEngagements``, ``shellNeedsRoot``, ``notice`` and ``drawNotice``."""
    ran = run_shell(["el", "detailOf", "retryOf", "drawNotice", "notice", "keyedNotice", "clearNotice", "noticeFocusAfter", "dismissNotice", "syncNotices",
                     "renderMachineNotices", "renderAfterInstall", "shortNotice", "shellNeedsRoot", "loadEngagements"],
                    NOTICE_DETAIL_FAKES + r"""
const notices = []; const keyedNotices = new Map(); const logged = [];
const window = { tracker: { logError: (text) => logged.push(text) } };
const host = new Element("div");
const $ = () => host;
Element.prototype.remove = function () { host.kids = host.kids.filter((one) => one !== this); };
const outlineRefused = () => {}; const showLock = () => {};
const hideTip = () => {}; const shellDraw = () => {}; let shellBack = null; let shellRootSet = false;
const screenWords = () => ({ setup: { missing: "Folder Not Found" } });
const applyVocabulary = () => {}; const adoptList = () => {}; const viewGeneration = 0;
let clientsRoot = ""; let setupDraft = null; let engagements = []; let active = ""; const select = () => {};
let call = null;
const shellGo = () => {};
""", """
      return (async () => {
      const listed = (extra) => ({ vocab: { firm: "", settings: { phone: "" }, screen: { notices: { machine: "Machine Needs Attention", reader: "Reader", details: "Details" }, icons: { dismiss: "Dismiss" } },
                                            after_install: { heading: "Setup Needs Attention" }, notices: { repeated: "(x{n})" } },
                                   engagements: [], machine_warnings: ["The app is running from /Volumes/X."], reader_warning: "", after_install: null, ...extra });
      const opened = () => host.kids.filter((one) => one.kids.some((kid) => kid.tag === "details")).map((one) => one.kids.find((kid) => kid.tag === "details").open);
      const out = {};
      call = async () => listed({ needs_root: true, root: "", root_problem: "" });
      shellRoute = { level: "overview" };
      await loadEngagements();
      out.noFolder = { route: shellRoute.level, details: opened() };
      host.kids = []; notices.length = 0; keyedNotices.clear();
      call = async () => listed({ needs_root: false, root: "/Clients" });
      shellRoute = { level: "overview" };
      await loadEngagements();
      out.withFolder = { route: shellRoute.level, details: opened() };
      return out;
      })();
    """, tmp_path, "app.js")
    assert ran["noFolder"] == {"route": "setup", "details": [True]}, "the setup page is the route when the notice is drawn, so its Details are open"
    assert ran["withFolder"]["details"] == [False], "on a working page the same notice is closed"
    load = js_function("loadEngagements", "app.js")
    assert load.index("shellNeedsRoot(true, listed);") < load.index("renderMachineNotices(listed);") < load.index("renderAfterInstall(listed.after_install);")


def test_the_pause_and_feed_sentences_reach_the_screen_as_details(tmp_path):
    """P259 (Q3, SPEC-mac-check-fixes 4.2): the household pause (``renamed``
    with Accept, or a year's ``paused``) and the prior-year feed are entries
    marked ``shown`` whose detail is the API's sentence; the two-open-years
    entry stays without a detail and is not marked."""
    ran = run_pages_dom("""
      const seen = [];
      syncNotices = (prefix, wanted) => seen.push(wanted.map((one) => [one.key.split(":")[0], one.failure.sentence, one.detail || "", one.shown === true]));
      const home = { path: "h1", open_years: [2025, 2024], pause: { sentence: "PAUSED LONG", scope: "household" }, feeds: [{ warning: "FEED ONE" }, { warning: "FEED TWO" }, {}] };
      lastState = { household: home };
      pagesHouseholdNotices({ level: "household", household: "h1" });
      lastState = { household: { ...home, pause: { sentence: "PAUSED YEAR LONG" }, open_years: [2025], feeds: [] } };
      pagesHouseholdNotices({ level: "return", household: "h1" });
      return seen;
    """, tmp_path, setup="""
      vocab.household = { two_open_years: "Two years open; sorting paused", accept_folder_name: "Accept the folder's name" };
      vocab.after_install = { wait: "Setup needs attention" };
      vocab.screen.notices = { renamed: "Folder renamed", paused: "Year folder mismatch", feed: "Feed not resolved" };
      const acceptFolderName = () => {};
    """, functions=["pagesHouseholdNotices", "shortNotice"])
    assert ran[0] == [["two-years", "Two years open; sorting paused", "", False],
                      ["renamed", "Folder renamed", "PAUSED LONG", True],
                      ["feeds", "Feed not resolved", "FEED ONE\nFEED TWO", True]]
    assert ran[1] == [["renamed", "Year folder mismatch", "PAUSED YEAR LONG", True]]
    assert js_function("pagesHouseholdNotices", "pages.js").count("shown: true") == 2, "the pause's entry and the feeds' entry"


def test_the_reader_warning_reaches_the_screen_as_details(tmp_path):
    """P259 (Q4, SPEC-mac-check-fixes 4.3): the reader's ``Install Folder Name
    Too Long`` notice carries the API's sentence as its detail and logs it once
    when it first shows (a second draw of the same sentence is the same
    notice); without a warning the notice is cleared."""
    ran = run_shell(["renderMachineNotices", "syncNotices", "shortNotice"], r"""
      let vocab = { screen: { notices: { machine: "Machine Needs Attention", reader: "Install Folder Name Too Long" } },
                    after_install: { wait: "Setup Needs Attention" } };
      const keyedNotices = new Map(); const seen = []; const logged = []; const cleared = [];
      const window = { tracker: { logError: (text) => logged.push(text) } };
      const keyedNotice = (key, failure) => {
        const same = keyedNotices.get(key) === `${failure.sentence}|${failure.detail || ""}`;
        keyedNotices.set(key, `${failure.sentence}|${failure.detail || ""}`);
        if (!same) seen.push([key, failure.sentence, failure.kind, failure.detail || ""]);
        return !same;
      };
      const clearNotice = (key) => { cleared.push(key); keyedNotices.delete(key); };
    """, """
      const sentence = "Move the app to a shorter folder, for example /Applications/JPA; scans can't be read from here";
      renderMachineNotices({ reader_warning: sentence, machine_warnings: [] });
      renderMachineNotices({ reader_warning: sentence, machine_warnings: [] });
      const shown = { seen: seen.slice(), logged: logged.slice(), cleared: cleared.slice() };
      seen.length = 0; logged.length = 0; cleared.length = 0;
      renderMachineNotices({ reader_warning: "", machine_warnings: [] });
      return { shown, gone: { seen, logged, cleared } };
    """, tmp_path, "app.js")
    sentence = "Move the app to a shorter folder, for example /Applications/JPA; scans can't be read from here"
    assert ran["shown"]["seen"] == [["reader", "Install Folder Name Too Long", "warning", sentence]]
    assert ran["shown"]["logged"] == [sentence], "logged once, when the notice first shows"
    assert ran["gone"]["seen"] == [] and ran["gone"]["logged"] == []
    assert ran["gone"]["cleared"] == ["reader"], "without a warning the notice is cleared"


def test_the_setup_notice_reads_the_same_whichever_reply_drew_it(tmp_path, monkeypatch):
    """P257 (review 1, finding 3): Start, Repair the Schedule and Save
    Schedule key the first-screen notice on the engine's ``wait`` and lines,
    as the ``list`` reply's notice does, so one run is drawn and logged once
    and a notice a person dismissed does not come back for the same sentence
    and detail; a different detail is a different notice."""
    from tracker import after_install

    finding = "Some Household: line 2 of the record is malformed"
    failure = "The daily job could not be registered."
    monkeypatch.setattr(after_install, "read_record", lambda: {"findings": [finding], "failed": [failure], "ran_at": "2026-09-26T08:00:00"})
    from_list = after_install.notice()
    ran_step = after_install.AfterInstall(reason="setup", ran_at="2026-09-26T08:00:00", schedule="no_root", schedule_sentence="S",
                                          check="found", check_sentence="C", findings=(finding,), failed=(failure,))
    from_reply = ran_step.reply()
    assert from_reply["wait"] == from_list["wait"] == after_install.FINDINGS_WAIT
    assert after_install.AfterInstall(reason="setup", ran_at="", schedule="no_root", schedule_sentence="S", check="ok",
                                      check_sentence="C").reply()["wait"] == "", "no findings, no wait"
    ran = run_shell(["renderAfterInstall", "noticeOf", "keyedNotice", "clearNotice"], r"""
      const vocab = { after_install: { heading: "Setup Needs Attention", wait: "Setup Needs Attention" } };
      const notices = []; const keyedNotices = new Map(); const logged = []; let drawn = 0;
      const window = { tracker: { logError: (text) => logged.push(text) } };
      const notice = (failure) => { drawn += 1; const entry = { ...failure }; notices.push(entry); return entry; };
      const dismissNotice = (entry) => { notices.splice(notices.indexOf(entry), 1); };
    """, f"""
      const reply = {json.dumps(from_reply)}; const listed = {json.dumps(from_list)};
      renderAfterInstall(noticeOf(reply));      // Start
      renderAfterInstall(listed);               // the list that follows it
      const once = {{ drawn, logged: logged.length, detail: notices[0].detail }};
      dismissNotice(notices[0]);                // a person dismisses it
      renderAfterInstall(noticeOf(reply)); renderAfterInstall(listed);
      const dismissed = {{ drawn, logged: logged.length, shown: notices.length }};
      renderAfterInstall({{ ...listed, findings: [...listed.findings, "Another finding"] }});
      return {{ once, dismissed, changed: {{ drawn, logged: logged.length, shown: notices.length }} }};
    """, tmp_path, "app.js")
    said = "\n".join([after_install.FINDINGS_WAIT, failure, finding])
    assert ran["once"] == {"drawn": 1, "logged": 1, "detail": said}, "drawn and logged once for one run, the engine's sentence first"
    assert ran["dismissed"] == {"drawn": 1, "logged": 1, "shown": 0}, "a dismissed notice does not come back"
    assert ran["changed"] == {"drawn": 2, "logged": 2, "shown": 1}, "a changed detail is a new notice"
    assert "vocab.after_install.wait" not in re.sub(r"//.*", "", js_function("noticeOf", "app.js")), "the reply's own wait, never the heading word"


def test_the_schedule_sentence_is_toasted_when_the_step_registered_it(tmp_path):
    """P257: Start (``saveRoot``) and the launch door's listener toast the
    engine's ``schedule_sentence`` - in a toast, before the page starts again
    - only when the step ``installed`` the schedule here. The shell forwards
    exactly those two facts, and the preload passes them to the listener."""
    ran = run_shell(["saveRoot"], r"""
      let setupDraft = { root: " /clients ", firm: " Firm ", phone: "" };
      const seen = []; let answer = null;
      const call = async () => answer;
      const noticeOf = (done) => done; const renderAfterInstall = () => seen.push("setup notice");
      const renderShortOfRoom = () => {}; const bootstrap = async () => seen.push("bootstrap");
      const outcome = (text, cls, opts) => seen.push(["outcome", text, cls, opts.toasted]);
      const failed = (err) => seen.push("failed:" + err.message);
      const clearNotice = () => {}; let shellBack = null;
      const window = { tracker: { logError: (text) => seen.push(["log", text]) } };
    """, """
      return (async () => {
        const reply = (installed) => ({ after_install: { installed, schedule_sentence: "This computer (OFFICE) now runs the schedule.", failed: [], findings: [] } });
        answer = reply(true); await saveRoot(); const registered = seen.splice(0);
        answer = reply(false); await saveRoot(); const elsewhere = seen.splice(0);
        return { registered, elsewhere };
      })();
    """, tmp_path, "app.js")
    assert ran["registered"] == ["setup notice", ["outcome", "This computer (OFFICE) now runs the schedule.", "ok", True], "bootstrap"]
    assert ran["elsewhere"] == ["setup notice", "bootstrap"]
    app = read("app.js")
    block = app[app.index("if (window.tracker.onAfterInstallDone) {"):]
    block = block[:block.index("\n}\n") + 3]
    heard = run_shell([], f"""
      const seen = []; let listener = null;
      const outcome = (text, cls, opts) => seen.push(["outcome", text, cls, opts.toasted]);
      const call = async () => ({{ after_install: null }}); const renderAfterInstall = () => seen.push("setup notice");
      const failed = (err) => seen.push("failed:" + err.message);
      const window = {{ tracker: {{ onAfterInstallDone: (fn) => {{ listener = fn; }} }} }};
      {block}
    """, """
      return (async () => {
        await listener({ installed: true, schedule_sentence: "S" }); const a = seen.splice(0);
        await listener({ installed: false, schedule_sentence: "S" }); const b = seen.splice(0);
        await listener(); const c = seen.splice(0);
        return { a, b, c };
      })();
    """, tmp_path)
    assert heard["a"] == [["outcome", "S", "ok", True], "setup notice"], "toasted, then the notice asked as before"
    assert heard["b"] == ["setup notice"] and heard["c"] == ["setup notice"]
    main_js = (REPO / "app" / "main.js").read_text(encoding="utf-8")
    preload = (REPO / "app" / "preload.js").read_text(encoding="utf-8")
    assert "win.webContents.send(LAUNCH_DONE_CHANNEL, {" in main_js
    assert "installed: result.installed === true," in main_js and "schedule_sentence: typeof result.schedule_sentence" in main_js
    assert 'ipcRenderer.on("after-install-done", (_e, done) => listener(done))' in preload



# ── P262: the return page follows a pass; Start goes to the Overview; a refusal is one notice ──

#: The fakes the reread step needs beside LAST_PASS_WATCH_FAKES (SPEC-mac-rerun1-fixes 3.1).
RETURN_FOLLOWS_FAKES = LAST_PASS_WATCH_FAKES + r"""
const ended = async (route, dialogs, running = null) => {
  shellRoute = route; dialogStack = dialogs; shellReturnStale = false; throwing = false;
  const out = await tick({ running: true, when: "A" }, { running: false, when: "A", ok: true }, running);
  return { seen: out.seen, stale: shellReturnStale };
};
"""


def test_a_scheduled_pass_that_ended_redraws_an_open_return_page(tmp_path):
    """P262 (SPEC-mac-rerun1-fixes 3.1): the reread a watch tick asks when a
    pass has ended adopts the list and then draws the open return page again,
    as F5 does - unless a dialog or the side sheet is open, when the page
    waits (``shellReturnStale``) and the last dialog's closing draws it.
    Other pages are not redrawn, nothing is read during the app's own pass,
    and a draw that throws is said once by ``failed``. (The real
    ``showReturn`` says its own read's failure itself and the watch goes on;
    the reread's catch takes only a throw.)"""
    ran = run_shell(["lastPassStep", "shellAskLastPass"], RETURN_FOLLOWS_FAKES, """
      return (async () => {
        const open = await ended({ level: "return", ret: "r1" }, []);
        const dialog = await ended({ level: "return", ret: "r1" }, ["sheet"]);
        const overview = await ended({ level: "overview" }, []);
        const own = await ended({ level: "return", ret: "r1" }, [], { pass: "p" });
        shellRoute = { level: "return", ret: "r1" }; dialogStack = []; throwing = true;
        const broken = await tick({ running: true, when: "A" }, { running: false, when: "A", ok: true });
        return { open, dialog, overview, own, broken: broken.seen };
      })();
    """, tmp_path)
    assert ran["open"]["seen"] == ["call:last-pass", "call:list", "adopt-list", "showReturn:r1"], "once, with the route's own return"
    assert ran["open"]["stale"] is False
    assert ran["dialog"]["seen"] == ["call:last-pass", "call:list", "adopt-list"] and ran["dialog"]["stale"] is True, \
        "an open dialog defers the redraw"
    assert ran["overview"]["seen"] == ["call:last-pass", "call:list", "adopt-list"] and ran["overview"]["stale"] is False
    assert ran["own"]["seen"] == [] and ran["own"]["stale"] is False, "during the app's own pass nothing is called"
    assert ran["broken"] == ["call:last-pass", "call:list", "adopt-list", "showReturn:r1", "failed:boom return"], "said once"


def test_closing_the_last_dialog_redraws_a_stale_return_page(tmp_path):
    """P262 (3.1): ``closeDialog``, once it has popped the last dialog, draws
    the return page a pass left behind; with another dialog still open it
    waits; when the route has moved off a return page it draws nothing and the
    flag is left for the next ``showReturn`` to clear."""
    setup = r"""
      const seen = []; let dialogStack = []; let shellReturnStale = false; let shellRoute = { level: "return", ret: "r9" };
      const DIALOGS = { one: {}, two: {} }; const dialogOpener = {};
      const el = () => ({ classList: { add() {} }, hidden: false });
      const $ = () => el(); const unsavedBar = () => null; const document = { contains: () => false };
      const showReturn = async (path) => { seen.push("showReturn:" + path); shellReturnStale = false; };
      const run = (stack, stale, route, id) => {
        seen.length = 0; dialogStack = stack.slice(); shellReturnStale = stale; shellRoute = route;
        closeDialog(id);
        return { seen: seen.slice(), stale: shellReturnStale, left: dialogStack.slice() };
      };
    """
    ran = run_shell(["closeDialog"], setup, """
      return {
        last: run(["one"], true, { level: "return", ret: "r9" }, "one"),
        two: run(["one", "two"], true, { level: "return", ret: "r9" }, "two"),
        clean: run(["one"], false, { level: "return", ret: "r9" }, "one"),
        moved: run(["one"], true, { level: "overview" }, "one"),
      };
    """, tmp_path, "app.js")
    assert ran["last"] == {"seen": ["showReturn:r9"], "stale": False, "left": []}, "the last dialog's closing draws it once"
    assert ran["two"] == {"seen": [], "stale": True, "left": ["one"]}, "one still open: it waits"
    assert ran["clean"]["seen"] == [], "nothing owed, nothing drawn"
    assert ran["moved"] == {"seen": [], "stale": True, "left": []}, "off a return page nothing is drawn; showReturn clears the flag"
    app = read("app.js")
    assert re.search(r"async function showReturn\(path\) \{\n  shellReturnStale = false;", app), "a navigation's own draw clears the flag"


def test_start_goes_to_the_overview_however_the_setup_page_was_reached(tmp_path):
    """P262 (3.2): a setup page with nothing to go back to goes to the
    Overview once the folder is set, and ``saveRoot`` forgets the route Cancel
    goes back to before the start-up path asks ``shellNeedsRoot`` - so it does
    on the Change clients folder path as on a first run."""
    ran = run_shell(["shellNeedsRoot"], r"""
      const gone = []; let shellRootSet = false; let shellBack = null; let shellRoute = { level: "setup" };
      const shellGo = (route) => gone.push(route.level);
      const screenWords = () => ({ setup: {} }); const notice = () => {}; const hideTip = () => {}; const shellDraw = () => {};
      const reset = (back) => { gone.length = 0; shellRoute = { level: "setup" }; shellBack = back; };
    """, """
      reset(null); shellNeedsRoot(false, { root: "/c" }); const fresh = gone.slice();
      reset({ level: "clients" }); shellNeedsRoot(false, { root: "/c" }); const kept = gone.slice();
      return { fresh, kept };
    """, tmp_path)
    assert ran == {"fresh": ["overview"], "kept": []}
    seen = run_shell(["saveRoot"], r"""
      let setupDraft = { root: "/new", firm: "F", phone: "" }; let shellBack = { level: "clients" };
      const seen = [];
      const call = async () => ({ after_install: { installed: false, schedule_sentence: "S", failed: [], findings: [] } });
      const noticeOf = (done) => done; const renderAfterInstall = () => {}; const renderShortOfRoom = () => {};
      const outcome = () => {}; const clearNotice = () => {};
      const bootstrap = async () => seen.push(["bootstrap", shellBack]);
      const window = { tracker: { logError: () => {} } };
    """, "return saveRoot().then(() => seen);", tmp_path, "app.js")
    assert seen == [["bootstrap", None]], "Cancel's route is forgotten before the start-up path runs"


def test_a_refused_folder_is_one_keyed_notice_that_goes_when_a_folder_is_set(tmp_path):
    """P262 (3.3): a folder the API refuses is the keyed notice ``set-root``
    in the API's own sentence and kind, with a Retry; a second refusal in
    other words replaces it; a folder that is set clears it, and so does
    Cancel on the setup page."""
    ran = run_shell(["saveRoot"], r"""
      let setupDraft = { root: "/new", firm: "F", phone: "" }; let shellBack = null;
      const keyed = new Map(); const seen = []; let answer = null;
      const call = async () => { if (answer instanceof Error) throw answer; return answer; };
      const failureSentence = (err) => "page:" + err.message;
      const keyedNotice = (key, failure, opts) => { keyed.set(key, [failure.sentence, failure.kind, opts.retry === saveRoot]); seen.push("notice:" + failure.sentence); };
      const clearNotice = (key) => { keyed.delete(key); seen.push("clear:" + key); };
      const noticeOf = (done) => done; const renderAfterInstall = () => {}; const renderShortOfRoom = () => {};
      const outcome = () => {}; const bootstrap = async () => seen.push("bootstrap");
      const window = { tracker: { logError: () => {} } };
      const refused = (sentence) => Object.assign(new Error("x"), { failure: { sentence, kind: "refused" } });
    """, """
      return (async () => {
        answer = refused("Not that folder."); await saveRoot(); const first = [...keyed];
        answer = refused("A different folder, please."); await saveRoot(); const second = [...keyed];
        answer = new Error("odd"); await saveRoot(); const own = [...keyed];
        seen.length = 0;
        answer = { after_install: { installed: false, schedule_sentence: "S", failed: [], findings: [] } }; await saveRoot();
        return { first, second, own, set: [...keyed], sawClear: seen.includes("clear:set-root") };
      })();
    """, tmp_path, "app.js")
    assert ran["first"] == [["set-root", ["Not that folder.", "refused", True]]], "the API's sentence and kind, with a Retry"
    assert ran["second"] == [["set-root", ["A different folder, please.", "refused", True]]], "replaced, not added"
    assert ran["own"] == [["set-root", ["page:odd", "failed", True]]], "an error of the page's own is said in its class sentence"
    assert ran["set"] == [] and ran["sawClear"] is True, "a folder that is set clears it"
    cancel = js_function("setupPage", "shell.js")
    assert re.search(r'id: "setup-cancel".*?addEventListener\("click", \(\) => \{\s*clearNotice\("set-root"\);[^\n]*\n\s*shellGo\(shellBack \|\| \{ level: "overview" \}\);', cancel, re.S), \
        "Cancel clears the sentence, then goes back"


def test_the_return_page_is_redrawn_only_on_a_return_route(tmp_path):
    """P262: ``shellRefresh`` (F5) and the watch's reread reach ``showReturn``
    only when the route is a return page."""
    refresh = re.sub(r"//.*", "", js_function("shellRefresh", "shell.js"))
    assert 'if (shellRoute.level === "return") await showReturn(shellRoute.ret);' in refresh
    reread = js_function("shellAskLastPass", "shell.js")
    assert re.search(r'if \(shellRoute\.level === "return"\) \{\s*if \(dialogStack\.length === 0\) await showReturn\(shellRoute\.ret\);\s*else shellReturnStale = true;', reread)
    assert reread.count("showReturn(") == 1


def test_a_navigation_that_closes_the_sheet_does_not_redraw_the_page_it_leaves(tmp_path):
    """P262 (review finding 1): with a pass ended while the side sheet was
    open on a return page, ``shellGo`` drops the owed redraw before it closes
    the sheet, so the sheet's closing (which runs ``closeDialog`` while the
    route is still the old return) draws nothing for the page being left."""
    setup = r"""
      const seen = []; let dialogStack = ["sheet"]; let shellReturnStale = true; let shellRoute = { level: "return", ret: "r9" };
      let shellRootSet = true; let shellBack = null; let shellPageBusy = false; let shellPageFailed = false;
      const LEVELS = ["overview", "return", "setup"]; const FIRM_LEVELS = ["overview"]; const pagesEnter = () => {}; const shellFirmFollow = () => {};
      const DIALOGS = { sheet: { attr: true } }; const dialogOpener = {};
      const el = () => ({ classList: { add() {} }, hidden: false, focus() {}, scrollTop: 0 });
      const $ = () => el(); const unsavedBar = () => null; const document = { contains: () => false };
      const showReturn = async (path) => { seen.push("showReturn:" + path); shellReturnStale = false; };
      const closeSheet = () => closeDialog("sheet");
      const hideFound = () => {}; const hideTip = () => {}; const shellDraw = () => {}; const failed = () => {};
      const appRouteChanged = () => {}; const shellOpenState = () => Promise.resolve();
    """
    ran = run_shell(["shellGo", "closeDialog"], setup, """
      return shellGo({ level: "overview" }).then(() => ({ seen, stale: shellReturnStale, level: shellRoute.level }));
    """, tmp_path, "app.js")
    assert ran == {"seen": [], "stale": False, "level": "overview"}


# ── P264: the UI polish, section 1 (pilot/SPEC-ui-polish.md) ──────────────
# Nothing here changes a word, a column, a token's value or a ruling; every
# claim is a speed or a seam that the pages' own tests could not see.

def test_one_collator_orders_every_name_sort_as_localecompare_did(tmp_path):
    """N1: ``pagesByName`` compares through one module-level collator with the
    options the sorts always used, so a list of mixed names and numbers sorts
    to the same order both ways. (The sensitivity stays the default: "base"
    would make "okafor" and "Okafor" tie and so change an order people have
    seen; the SPEC's sentence says "same order as before".)"""
    ran = run_pages(["pagesByName"], "", """
      const names = ["Client 10", "client 2", "Client 2", "Ren\\u00e9e", "Renee", "okafor", "Okafor", "Smith 1040", "Smith 9", "Smith 10", "\\u00c1lvarez", "Alvarez", "", "Zed"];
      const old = (a, b) => a.localeCompare(b, undefined, { numeric: true });
      return { now: names.slice().sort(pagesByName), before: names.slice().sort(old),
               nowBack: names.slice().reverse().sort(pagesByName), beforeBack: names.slice().reverse().sort(old) };
    """, tmp_path)
    assert ran["now"] == ran["before"] and ran["nowBack"] == ran["beforeBack"]
    pages = stripped_js("pages.js")
    assert pages.count("new Intl.Collator(") == 1 and "const PAGES_COLLATOR = new Intl.Collator(undefined, { numeric: true });" in pages
    for name in ("app.js", "pages.js", "shell.js", "sheet.js"):
        assert not re.search(r"localeCompare\([^)]*numeric", stripped_js(name)), name


def test_a_lookup_by_path_or_name_answers_what_the_scan_answered_and_follows_a_new_list(tmp_path):
    """N2: ``shellReturn``, ``shellHousehold`` and ``pagesFirmReturn`` read an
    index built once for the list or reply on screen. Each answers what a scan
    answered - the first entry of a path, null for none - and an array adopted
    later is indexed afresh. (The household's path by name and the form's place
    are the engine's now, P278: a name is found there once, in the walk.)"""
    setup = r"""
      let engagements = [{ path: "r1", return_name: "one" }, { path: "r2", return_name: "two" }, { path: "r1", return_name: "again" }];
      let households = [{ name: "Smith", path: "h1" }, { name: "Rivera", path: "h2" }, { name: "Smith", path: "h3" }];
      let held = { return_counts: [{ path: "r1", n: 1 }, { path: "r2", n: 2 }, { path: "r1", n: 3 }], replies: {} };
      const shellFirm = () => ({ data: held });
    """
    ran = run_shell(["shellReturn", "shellHousehold"], setup + js_function("pagesFirmReturn", "pages.js"), """
      const scanReturn = (p) => engagements.find((one) => one.path === p) || null;
      const scanHousehold = (p) => households.find((one) => one.path === p) || null;
      const scanFirm = (p) => held.return_counts.find((one) => one.path === p) || null;
      const same = () => ({
        ret: ["r1", "r2", "nope"].map((p) => shellReturn(p) === scanReturn(p)),
        household: ["h1", "h2", "h3", "nope"].map((p) => shellHousehold(p) === scanHousehold(p)),
        firm: ["r1", "r2", "nope"].map((p) => pagesFirmReturn(p) === scanFirm(p)) });
      const first = same();
      engagements = [{ path: "r9", return_name: "nine" }];
      households = [{ name: "Okafor", path: "h9" }];
      held = { return_counts: [{ path: "r9" }], replies: {} };
      const second = same();
      return { first, second, newRet: shellReturn("r9").return_name, goneRet: shellReturn("r1"), goneFirm: pagesFirmReturn("r1") };
    """, tmp_path)
    for answers in (ran["first"], ran["second"]):
        assert all(all(row) for row in answers.values()), answers
    assert ran["newRet"] == "nine" and ran["goneRet"] is None and ran["goneFirm"] is None
    # No comparator or per-row call scans an array any more.
    for name, source in (("shellReturn", "shell.js"), ("shellHousehold", "shell.js"), ("pagesFirmReturn", "pages.js"), ("pagesReturnName", "pages.js")):
        body = js_function(name, source)
        assert ".find(" not in body and ".filter(" not in body, name
    returns = js_function("pagesReturnGroups", "pages.js")
    assert "index.filter(" not in returns.split("const filedBy")[1].split("for (const item of items)")[0] and "filedUnder" in returns


def test_the_files_filed_under_a_request_are_the_same_as_the_scan_found(tmp_path):
    """N2: ``pagesReturnGroups`` reads the files filed under each request from
    a map built once from the index: a file counts under its own identifier and
    under each request it answered, once under each, in index order."""
    ran = run_pages_dom("""
      const filed = (handle, identifier, answered = []) => ({ handle, original_name: `${handle}.pdf`, decision: "Filed", group: "received", identifier, answered, received: "2026-03-01" });
      const index = [filed("a", "W2", ["W2", "1099"]), filed("b", "1099"), { ...filed("c", "W2"), decision: "Needs Review" }, filed("d", "K1", ["1099"])];
      const scan = (identifier) => index.filter((one) => one.decision === "Filed" && (one.identifier === identifier || (one.answered || []).indexOf(identifier) !== -1)).map((one) => one.handle);
      lastState = { ...stateOf([item("W2", "received", { status_key: "Received" }), item("1099", "received", { status_key: "Received" }), item("K1", "received", { status_key: "Received" })], index),
                    review_labels: {} };
      const box = page(pagesReturn({ level: "return", ret: "r1", year: 2025 }));
      const rows = box.byClass("row").map((row) => [row.byClass("row-name")[0].textContent, (row.byClass("row-detail")[0] || { textContent: "" }).textContent]);
      return { rows, scan: ["W2", "1099", "K1"].map(scan) };
    """, tmp_path)
    assert ran["scan"] == [["a"], ["a", "b", "d"], ["d"]]
    details = dict(ran["rows"])
    assert (details["Doc W2"], details["Doc K1"]) == ("a.pdf", "d.pdf") and details["Doc 1099"] == "3 files", ran["rows"]


SHELL_ROUTE_FAKES = r"""
const LEVELS = ["overview", "needs-review", "reminders", "clients", "household", "year", "return", "setup"];
const FIRM_LEVELS = ["overview", "needs-review", "reminders", "clients"];
let shellRoute = { level: "overview" }; let shellBack = null; let shellReturnStale = false; let shellRootSet = true;
let shellPageBusy = false; let shellPageFailed = false; let shellFirmNow = { status: "ok", data: null };
let shellFirmSentAt = 0; let shellWroteAt = 0; const shellFirmHeld = new Map();
let households = [{ name: "Smith Family", path: "h1", returns: [{ path: "r1", active: true }] }, { name: "Rivera", path: "h2", returns: [{ path: "r3", active: true }] }];
let engagements = [{ path: "r1", household: "h1", year: 2025 }, { path: "r2", household: "h1", year: 2024 }, { path: "r3", household: "h2", year: 2025 }];
let lastState = null; let active = "r1"; const drawn = []; const events = [];
const closeSheet = () => {}; const hideFound = () => {}; const hideTip = () => {}; const appRouteChanged = () => {}; const failed = (err) => { throw err; };
const $ = () => ({ focus() {}, scrollTop: 0 });
const shellDraw = () => drawn.push(shellRoute.level); const shellChanged = () => events.push("changed");
const sheetStateArrived = () => events.push("sheet"); const shellLoadFirm = () => {};
const pagesTally = () => ({}); 
const stateFor = (path, household) => ({ paths: { engagement: path }, household: { path: household } });
// As app.js's showReturn does: the state is read, becomes the one on screen, and the shell is told.
const showReturn = async (path) => {
  const owner = engagements.find((one) => one.path === path).household;
  lastState = stateFor(path, owner); active = path;
  shellStateArrived(lastState);
  return true;
};
"""


def test_a_page_is_drawn_once_per_visit_and_a_firm_page_under_the_sheet_is_not_rebuilt(tmp_path):
    """N3: the household page is drawn when the route changes and again only
    if the state that arrives is its own household's (its caption reads it); a
    year page the same; the return page is the outline, then the page (two
    draws, not three); a firm page is not rebuilt when the sheet's state lands,
    though the sheet is told and the shell's controls follow."""
    ran = run_shell(["shellGo", "shellOpenState", "shellStateArrived", "shellPageReadsState", "shellCountsDiffer", "shellHousehold", "shellOwnReturns"],
                    SHELL_ROUTE_FAKES, """
      return (async () => {
      const count = async (route, shown) => {
        lastState = shown; drawn.length = 0; events.length = 0;
        await shellGo(route);
        return drawn.length;
      };
      const out = {};
      out.householdWarm = await count({ level: "household", household: "h1" }, stateFor("r1", "h1"));
      out.householdCold = await count({ level: "household", household: "h1" }, stateFor("r3", "h2"));
      out.yearWarm = await count({ level: "year", household: "h1", year: 2025 }, stateFor("r2", "h1"));
      out.yearCold = await count({ level: "year", household: "h1", year: 2025 }, null);
      out.returnPage = await count({ level: "return", household: "h1", year: 2025, ret: "r1" }, stateFor("r3", "h2"));
      out.returnBusyAtDraws = [];
      shellRoute = { level: "overview" }; drawn.length = 0; events.length = 0;
      shellStateArrived(stateFor("r1", "h1"));
      out.firmDraws = drawn.length; out.firmEvents = events.slice();
      shellRoute = { level: "household", household: "h1" }; drawn.length = 0;
      shellStateArrived(stateFor("r3", "h2"));
      out.otherHouseholdDraws = drawn.length;
      shellStateArrived(stateFor("r1", "h1"));
      out.ownHouseholdDraws = drawn.length;
      shellRoute = { level: "return", ret: "r1" }; drawn.length = 0; shellPageBusy = true;
      shellStateArrived(stateFor("r1", "h1"));
      out.busyDraws = drawn.length;
      shellPageBusy = false; shellStateArrived(stateFor("r1", "h1"));
      out.writeOnAReturnPage = drawn.length;
      return out;
      })();
    """, tmp_path)
    assert (ran["householdWarm"], ran["yearWarm"]) == (1, 1), "a state already on screen is not read again"
    assert ran["householdCold"] == 2 and ran["yearCold"] == 2, "the route's draw, then the one with its household's state (the caption reads it); never a third"
    assert ran["returnPage"] == 2, "the outline, then the page"
    assert ran["firmDraws"] == 0 and ran["firmEvents"] == ["changed", "sheet"], "a firm page is left alone; the sheet and the controls still follow"
    assert ran["otherHouseholdDraws"] == 0 and ran["ownHouseholdDraws"] == 1
    assert ran["busyDraws"] == 0 and ran["writeOnAReturnPage"] == 1, "no outline drawn again while the wait lasts; a write's state redraws the return"


def test_the_hidden_reminder_letter_is_built_only_for_an_open_reminder_sheet(tmp_path):
    """N4: ``render`` builds the letter only while the reminder sheet is open
    or being opened; with the sheet shut (or showing a file) the card held is
    dropped, so the sheet's open path draws the state on screen."""
    setup = r"""
      let sheetNow = null; let paths = null; let lastState = null; let rollChoice = null; let active = "r1";
      let reminderCard = { stale: true }; let reminderCardFor = "r1"; let reminderStage = 2; let reminderFor = "r0";
      const seen = []; const renderLock = () => seen.push("lock"); const renderReminder = (state) => seen.push("reminder:" + state.paths.engagement);
      const shellStateArrived = () => seen.push("shell"); const failed = (err) => seen.push("failed:" + err.message);
    """
    ran = run_shell(["render"], setup, """
      const state = { paths: { engagement: "r1" } };
      const out = {};
      render(state); out.closed = { seen: seen.splice(0), card: reminderCard, stage: reminderStage, forWhom: reminderFor };
      sheetNow = { kind: "check" }; render(state); out.check = seen.splice(0);
      sheetNow = { kind: "reminder", ret: "r1" }; render(state); out.open = seen.splice(0);
      return out;
    """, tmp_path, "app.js")
    assert ran["closed"] == {"seen": ["lock", "shell"], "card": None, "stage": None, "forWhom": "r1"}, "no letter, no held card, no stale pick"
    assert ran["check"] == ["lock", "shell"]
    assert ran["open"] == ["lock", "reminder:r1", "shell"]


def test_search_draws_once_the_typing_pauses_and_folds_each_name_once(tmp_path):
    """N5: three keystrokes inside 80 ms are one draw; emptying the box hides
    the list at once; an arrow or Enter draws what is pending first, so a key
    never acts on the list of the letter before; hiding the list cancels a
    pending draw. ``findOptions`` folds a name the first time it reads it and
    never again for the same list, and a new list is folded afresh."""
    setup = r"""
      let now = 0; let nextTimer = 0; const timers = new Map();
      const setTimeout = (fn, ms) => { nextTimer += 1; timers.set(nextTimer, { fn, at: now + ms }); return nextTimer; };
      const clearTimeout = (id) => { timers.delete(id); };
      const advance = (ms) => { now += ms; for (const [id, one] of [...timers]) if (one.at <= now) { timers.delete(id); one.fn(); } };
      const box = { value: "", attrs: {}, setAttribute(k, v) { this.attrs[k] = v; }, removeAttribute(k) { delete this.attrs[k]; } };
      const list = { hidden: false, replaceChildren() {} };
      const $ = (id) => (id === "find" ? box : list);
      const draws = []; const drawFound = () => { clearTimeout(shellFindTimer); shellFindTimer = null; draws.push(box.value); };
      let shellFound = []; const moves = []; const moveFound = (by) => moves.push([by, draws.length]);
      const openFound = (i) => moves.push(["open", draws.length]); const chosenFound = () => 0;
      const key = (k) => ({ key: k, preventDefault() {} });
    """
    ran = run_shell(["drawFoundSoon", "findKey", "hideFound"], setup + "let shellFindTimer = null; const SHELL_FIND_WAIT_MS = 80;", """
      const out = {};
      for (const v of ["s", "sm", "smi"]) { box.value = v; drawFoundSoon(); advance(20); }
      out.within = draws.length; advance(80); out.after = draws.splice(0);
      box.value = "smith"; drawFoundSoon(); findKey(key("ArrowDown")); out.flushed = [draws.splice(0), moves.splice(0)];
      advance(200); out.noSecond = draws.length;
      box.value = "smi"; drawFoundSoon(); hideFound(); advance(200); out.cancelled = draws.length;
      box.value = "smi"; drawFoundSoon(); findKey(key("Enter")); out.enter = [draws.splice(0), moves.splice(0)];
      box.value = "  "; drawFoundSoon(); out.empty = draws.splice(0).length;
      return out;
    """, tmp_path)
    assert ran["within"] == 0 and ran["after"] == ["smi"], "three keystrokes inside the wait are one draw, of the last"
    assert ran["flushed"] == [["smith"], [[1, 1]]] and ran["noSecond"] == 0, "the arrow draws the pending list first, then moves"
    assert ran["cancelled"] == 0, "a hidden list is not drawn again by a keystroke already waiting"
    assert ran["enter"] == [["smi"], [["open", 1]]]
    assert ran["empty"] == 1, "an empty box hides the list at once"
    shell = stripped_js("shell.js")
    assert '$("find").addEventListener("input", drawFoundSoon);' in shell
    folds = run_shell(["screenWords", "fold", "foldedName", "shellHousehold", "shellOwnReturns", "shellReturn", "findOptions"], PEOPLE.replace("const households", "let households").replace("const engagements", "let engagements"), """
      const real = fold; let count = 0; fold = (text) => { count += 1; return real(text); };
      const names = (q) => findOptions(q).map((o) => o.name);
      const out = {};
      names("smith"); out.firstQuery = count;          // 1 for the needle, then each household and return once
      names("smit"); names("smi"); out.threeQueries = count;
      households = [{ name: "Smith Other", path: "x1", returns: [] }]; engagements = [];
      const before = count; const found = names("smith"); out.newList = [count - before, found];
      return out;
    """, tmp_path)
    assert folds["firstQuery"] == 1 + 4 + 3, "the needle, four households and three returns, once each"
    assert folds["threeQueries"] == folds["firstQuery"] + 2, "later queries fold only the needle"
    assert folds["newList"] == [1 + 1, ["Smith Other"]], "a list adopted later is folded afresh"


def test_the_last_pass_watch_and_the_lock_watch_send_nothing_while_the_window_is_hidden(tmp_path):
    """N6 (P277): a hidden window sends no ``last-pass`` and no ``watch``; a
    change of the last-pass file while it is hidden is owed, and becoming
    visible asks once; each lock tick resumes once; two focus events 2 s apart
    send one ask."""
    ran = run_shell(["lastPassStep", "shellAskLastPass", "shellLastPassChanged", "shellFocused", "shellShown"], LAST_PASS_WATCH_FAKES, """
      shellLastPass = { running: false, when: "A" }; reply = { running: false, when: "A" };
      return (async () => {
      const out = {};
      let clock = 100000; const realNow = Date.now; Date.now = () => clock;
      document.hidden = true;
      await shellAskLastPass(); await shellFocused(); shellLastPassChanged();
      out.hidden = { asked, owed: shellLastPassOwed };
      document.hidden = false; shellShown(); await new Promise((r) => setImmediate(r));
      out.shown = asked; out.owedAfter = shellLastPassOwed;
      clock += 2000; shellFocused(); await new Promise((r) => setImmediate(r));
      out.twoSecondsLater = asked;
      clock += 6000; shellFocused(); await new Promise((r) => setImmediate(r));
      out.eightSecondsLater = asked;
      document.hidden = true; shellShown(); await new Promise((r) => setImmediate(r));
      out.hiddenAgain = asked;
      Date.now = realNow;
      return out;
      })();
    """, tmp_path)
    assert ran["hidden"] == {"asked": 0, "owed": True}, "no ask while hidden, and the change is owed"
    assert ran["shown"] == 1 and ran["owedAfter"] is False, "shown again: one ask pays it"
    assert ran["twoSecondsLater"] == 1 and ran["eightSecondsLater"] == 2 and ran["hiddenAgain"] == 2
    shell = stripped_js("shell.js")
    assert 'window.addEventListener("focus", shellFocused);' in shell and 'document.addEventListener("visibilitychange", shellShown);' in shell

    lock = run_shell(["stopLockWatch", "lockWatchResume", "watchLock"], r"""
      const document = { hidden: false }; let lockWatch = null; let lockWatched = null; let lockTick = null; let active = "A"; let viewGeneration = 0;
      const vocab = { engagement_flag: "--engagement", lock: { watch_seconds: 5, buttons_back: "back" } };
      const intervals = []; const setInterval = (fn) => { intervals.push(fn); return intervals.length; }; const clearInterval = () => {};
      const asked = []; const call = async (args) => { asked.push(args[2]); return { lock: { engagement: "A" } }; };
      const showLock = () => {}; const clearNotice = () => {}; const setLocked = () => {}; const notice = () => {}; const showReturn = () => {}; const failed = () => {};
    """, """
      return (async () => {
      watchLock({ engagement: "A" });
      document.hidden = true;
      await intervals[0](); await intervals[0]();
      const hidden = asked.length;
      lockWatchResume();                       // still hidden: nothing
      document.hidden = false; lockWatchResume(); await new Promise((r) => setImmediate(r));
      const shown = asked.length;
      stopLockWatch(); lockWatchResume();      // no watch running: nothing
      return { hidden, shown, after: asked.length };
      })();
    """, tmp_path, "app.js")
    assert lock == {"hidden": 0, "shown": 1, "after": 1}
    assert 'document.addEventListener("visibilitychange", lockWatchResume);' in stripped_js("app.js")


def test_the_small_hot_paths_do_their_work_once(tmp_path):
    """N7: (a) the column grip writes its width once a frame and the release
    writes the last one; (b) the refused outline looks through the sheet only;
    (c) the Clients page computes its specs once per draw; (d) a scroll with no
    tip showing does nothing."""
    grip = run_shell(["pagesGripStart"], r"""
      const frames = []; const requestAnimationFrame = (fn) => { frames.push(fn); return frames.length; };
      const cancelAnimationFrame = (id) => { if (id) frames[id - 1] = null; };
      const widths = []; const pagesSetWidth = (list, cell, px) => widths.push(px); const pagesSaveWidths = () => widths.push("saved");
      const handlers = {};
      const grip = { parentNode: { getBoundingClientRect: () => ({ width: 100 }) }, classList: { add() {}, remove() {} }, setPointerCapture() {},
                     addEventListener(type, fn) { handlers[type] = fn; }, removeEventListener() {} };
    """, """
      pagesGripStart("list", "cell", grip, { button: 0, clientX: 10, pointerId: 1, preventDefault() {} });
      for (const x of [20, 30, 40]) handlers.pointermove({ clientX: x });
      const queued = frames.filter(Boolean).length;
      frames.filter(Boolean)[0]();                                 // the frame comes: the latest position, once
      const afterFrame = widths.slice();
      handlers.pointermove({ clientX: 50 });                       // moved, then released before the frame
      handlers.pointerup();
      return { queued, afterFrame, final: widths.slice() };
    """, tmp_path, "pages.js")
    assert grip["queued"] == 1 and grip["afterFrame"] == [130]
    assert grip["final"] == [130, 140, "saved"], "the release writes what was waiting, then saves"
    app = stripped_js("app.js")
    assert '$("sheet").querySelectorAll("[data-row]")' in js_function("outlineRefused", "app.js") and 'document.querySelectorAll("[data-row]")' not in app
    clients = run_lists("""
      const real = pagesClientSpecs; let calls = 0; pagesClientSpecs = (...args) => { calls += 1; return real(...args); };
      const out = {};
      for (const all of [false, true]) { pagesClientsAll = all; calls = 0; draw("clients"); out[all ? "all" : "work"] = calls; }
      pagesClientsAll = false;
      return out;
    """, tmp_path)
    assert clients == {"work": 1, "all": 1}
    tip = js_function("replaceTip", "tooltip.js")
    assert tip.index("if (tipFor === null && tipWaitFor === null) return;") < tip.index("placeTip(tipFor")
    ran = run_shell(["replaceTip"], "let tipFor = null; let tipWaitFor = null; const calls = []; const placeTip = () => calls.push('place'); const hideTip = () => calls.push('hide'); const tipNode = () => null;\n",
                    "replaceTip(); tipWaitFor = {}; replaceTip(); return calls;", tmp_path, "tooltip.js")
    assert ran == ["hide"], "nothing showing or waiting: nothing; a tip waiting on its delay is still cancelled by a scroll"


def test_dead_css_is_gone_from_style_css_and_its_restatements_with_it():
    """N8: the spinner's keyframes, the four-column roll grid, the ``.summary``
    colour (and the two lists in pilot-ui.css that restated it), the
    ``.btn-primary`` block the button tokens override whole (and its one-line
    restatement), and the 1100px rule the sheet's own grid made moot."""
    style, ui = stripped(read("style.css")), stripped(read("pilot-ui.css"))
    assert "@keyframes spin" not in style and ".roll-grid.four" not in style and ".summary" not in style and ".btn-primary" not in style
    assert "max-width: 1100px" not in style
    assert ".summary" not in ui and ".btn-primary { color" not in ui
    assert re.search(r"\n\.btn-primary \{\s*--b-fg: var\(--on-accent\);", ui), "the primary's tokens, the one place it is drawn"
    assert "#sheet .rem-stages { grid-template-columns: repeat(2" in read("shell.css"), "the only .rem-stages on screen is the sheet's, two columns always"
    for name in ("index.html", "app.js", "pages.js", "shell.js", "sheet.js"):
        assert "roll-grid four" not in read(name) and 'class="summary' not in read(name) and "animation: spin" not in read(name), name


def test_native_controls_follow_the_theme():
    """N9: ``color-scheme`` is light in the light block and dark in the dark one."""
    ui = stripped(read("pilot-ui.css"))
    light = next(body for _media, selector, body in blocks(ui) if selector.strip() == ":root" and not _media)
    dark = next(body for media, selector, body in blocks(ui) if selector.strip() == ":root" and media == ("@media (prefers-color-scheme: dark)",))
    assert "color-scheme: light;" in light and "color-scheme: dark;" in dark
    assert "color-scheme: dark" not in light and "color-scheme: light" not in dark


def test_a_list_of_one_page_draws_no_pager(tmp_path):
    """N10: Previous and Next are drawn when there is more than one page; the
    "Showing 1-3 of 3 Drafts" line stays either way."""
    ran = run_lists("""
      const buttons = (node) => node.find((one) => one.tag === "button").map((one) => one.textContent);
      const one = pagesFoot("reminders", 1, 3, 3, 0, 1);
      const many = pagesFoot("reminders", 1, 50, 83, 0, 2);
      const last = pagesFoot("reminders", 51, 83, 83, 1, 2);
      const count = (node) => node.byClass("page-count")[0].textContent;
      return { one: [count(one), buttons(one)], many: [count(many), buttons(many)], last: [count(last), buttons(last)] };
    """, tmp_path)
    assert ran["one"][1] == [] and ran["one"][0].startswith("Showing 1-3 of 3")
    assert ran["many"][1] == ["Previous", "Next"] and ran["last"][1] == ["Previous", "Next"]


def test_the_reason_cards_sit_in_a_grid_of_full_rows():
    """N11: three columns up to 1240px of window, six above it."""
    css = stripped(read("shell.css"))
    base = next(body for media, selector, body in blocks(css) if selector.strip() == ".reason-cards:not(.hidden)" and not media)
    wide = next(body for media, selector, body in blocks(css) if selector.strip() == ".reason-cards:not(.hidden)" and media == ("@media (min-width: 1241px)",))
    assert "display: grid;" in base and "grid-template-columns: repeat(3, minmax(0, 1fr));" in base and "flex" not in base
    assert wide.strip() == "grid-template-columns: repeat(6, minmax(0, 1fr));"
    card = next(body for media, selector, body in blocks(css) if selector.strip() == ".reason-card:not(.hidden)")
    assert "min-width: 0;" in card, "a card is as wide as its column, not as wide as its words"


def test_a_notices_closed_details_sits_on_its_line_and_an_open_one_drops_under_it():
    """N12: closed, the summary is an item of the notice's one line (after the
    sentence, before the buttons - the markup order drawNotice builds); open,
    the disclosure takes the next line at the notice's width, its summary kept
    at the right."""
    css = stripped(read("pilot-ui.css"))
    rules = {selector.strip(): body for media, selector, body in blocks(css) if not media}
    closed = rules["#notices .notice-detail"]
    assert "flex: 0 0 auto;" in closed and "order" not in closed and "padding-block" not in closed and "flex: 0 0 100%" not in closed
    opened = rules["#notices .notice-detail[open]"]
    assert "order: 1;" in opened and "flex: 0 0 100%;" in opened
    assert "margin-inline-start: auto;" in rules["#notices .notice-detail[open] > summary"]
    assert "flex-wrap: wrap" in rules["#notices .notice:has(.notice-detail)"]
    assert 'el("span", { className: "notice-text" }, text), ...detailOf(entry), ...buttons, dismiss)' in js_function("drawNotice", "app.js")


# ── P265-P280 (SPEC-ui-menu-small) ───────────────────────────────────────

def _shell_rules() -> tuple[dict[str, dict[str, str]], list[tuple[list[str], dict[str, str]]]]:
    """shell.css outside every at-rule: each selector's declarations merged
    (a later rule's declaration wins, as dict.update does), and every rule with its
    selectors, for the claims about two selectors sharing one rule."""
    merged: dict[str, dict[str, str]] = {}
    each: list[tuple[list[str], dict[str, str]]] = []
    for media, selector, body in blocks(read("shell.css")):
        if media:
            continue
        parts = [" ".join(part.split()) for part in selector.split(",")]
        each.append((parts, dict(declarations(body))))
        for part in parts:
            merged.setdefault(part, {}).update(dict(declarations(body)))
    return merged, each


def test_an_unbuilt_item_is_one_line_its_short_name_and_a_soon_tag_a_screen_reader_does_not_read(tmp_path):
    """P265: each of the five Under Construction items is one 40px row - its
    icon, its short name and a small "Soon" tag at the right. The tag is
    drawn from the vocabulary and is aria-hidden, so a screen reader hears
    the name, "unavailable" and the description "Under Construction", never
    "Ready to Sign Soon"; a missing tag word throws, as every word here does."""
    html = read("index.html")
    soon = re.findall(r'<button[^>]*class="side-section is-soon"[^>]*>.*?</button>', html, flags=re.S)
    assert len(soon) == 5
    for one in soon:
        assert one.count('<span class="side-soon" aria-hidden="true"></span>') == 1, "the tag is empty here: its word is the vocabulary's"
        assert one.index('class="side-name"') < one.index('class="side-soon"')
    setup = """
      const nodes = ["a", "b"].map((key) => { const name = { textContent: "" }; const tag = { textContent: "" };
        return { dataset: { soon: key }, name, tag, attrs: {}, tip: null, querySelector(sel) { return sel === ".side-name" ? name : tag; },
                 setAttribute(k, v) { this.attrs[k] = v; } }; });
      const document = { querySelectorAll: (sel) => (sel === ".side-section[data-soon]" ? nodes : []) };
      const setTip = (node, words) => { node.tip = words; };
      const $ = () => ({ textContent: "", querySelector: () => ({ textContent: "" }) });
      const side = (extra = {}) => ({ product: "P", types: "T", workspace: "W", settings: "S", under_construction: "Under Construction",
                                      soon: { a: "Ready to Sign", b: "Family Entities" }, soon_tag: "Soon", ...extra });
    """
    ran = run_shell(["shellSideWords"], setup, """
      shellSideWords({ side: side() });
      const filled = nodes.map((n) => [n.name.textContent, n.tag.textContent, n.tip, n.attrs["aria-description"]]);
      let missing = "";
      try { shellSideWords({ side: side({ soon_tag: undefined }) }); } catch (err) { missing = err.message; }
      return { filled, missing };
    """, tmp_path)
    assert ran["filled"] == [["Ready to Sign", "Soon", "Under Construction", "Under Construction"],
                             ["Family Entities", "Soon", "Under Construction", "Under Construction"]]
    assert ran["missing"] == "side.soon_tag"
    merged, _each = _shell_rules()
    assert merged[".side-section.is-soon:not(.hidden)"] == {"color": "var(--text-secondary)"}, "no height: auto and no extra padding: the row is the usual 40px"
    assert ".side-section.is-soon .side-name" not in merged, "no wrapping: the name is cut with an ellipsis like every other item"
    tag = merged[".side-soon"]
    assert all(word in ("0", "none") or word.startswith("var(--") for value in tag.values() for word in value.split()), tag
    assert tag["background"] == "var(--bg-pressed)" and tag["color"] == "var(--text-secondary)"
    assert merged[".side-soon:empty"] == {"display": "none"}, "no empty pill at the first paint"
    assert ".side-soon:not(:empty)" in _forced_colours(), "a contrast theme keeps the tag's edge"


def test_the_brand_band_is_the_mark_and_the_products_name_and_never_the_firms_name():
    """P266: the band is 48px, the JP mark 32px and "Tax Document Console"
    beside it on one line. The firm's name is not in the band - not even
    hidden for a screen reader - and nothing loads the old lockup."""
    html = read("index.html")
    band = html[html.index('<div id="side-brand">'):html.index("</div>", html.index('<div id="side-brand">'))]
    assert '<img src="mark.svg" alt="" />' in band and 'id="side-brand-product"' in band
    assert "side-brand-name" not in html and "side-brand-words" not in html
    mark = (RENDERER / "mark.svg").read_text(encoding="utf-8")
    assert 'viewBox="0 0 480 480"' in mark and "<circle" in mark and "<path" in mark
    for banned in ("<text", "<script", "<style"):
        assert banned not in mark, banned
    assert not (RENDERER / "logo.svg").exists()
    for one in RENDERER.rglob("*"):
        if one.is_file() and one.suffix in (".js", ".css", ".html", ".svg", ".json"):
            assert "logo.svg" not in one.read_text(encoding="utf-8"), one.name
    assert "brand" not in api.SCREEN["side"]
    assert "side.brand" not in stripped_js("shell.js")
    merged, _each = _shell_rules()
    assert merged["#side-brand:not(.hidden)"]["height"] == "var(--size-bar)" and merged["#side-brand:not(.hidden)"]["background"] == "var(--brand)"
    assert merged["#side-brand img"]["width"] == merged["#side-brand img"]["height"] == "var(--size-control)"
    assert "#side-brand-words:not(.hidden)" not in merged and "#side-brand-words" not in read("shell.css")
    assert _forced_colours()["#side-brand-product"] == {"color": "CanvasText"}


def test_the_firms_name_is_the_window_titles_alone():
    """P266: the title line is unchanged (the product, then the firm once the
    setup page has it), and "J Park" is in no renderer file but the pilot's
    own terms (P63's exception) and in no word of the screen vocabulary."""
    assert "document.querySelector(\"title\").textContent = vocab.firm ? `${vocab.product} — ${vocab.firm}` : vocab.product;" in read("app.js")
    for one in RENDERER.rglob("*"):
        if one.is_file() and one.suffix in (".js", ".css", ".html", ".svg") and "vendor" not in one.parts and one.name != "pilot-content.js":
            assert "J Park" not in one.read_text(encoding="utf-8"), one.name
    assert "J Park" not in json.dumps(api.SCREEN)


def test_a_name_link_is_underlined_on_hover_on_the_keyboards_active_row_and_always_in_a_contrast_theme():
    """P267 (final review B, finding 6, as P267 changed it): the link colour
    is 1.4 to 1.5 against the text in both themes, so at rest a name is told
    from text by its column, its weight and (for a file) its icon; the
    underline comes back under the pointer and on the keyboard's active row,
    and always in a contrast theme. The status words on a row ("3 Waiting")
    are never underlined and never look pressable."""
    merged, each = _shell_rules()
    link = merged[".row-link"]
    assert link["text-decoration"] == "none" and link["cursor"] == "pointer"
    assert link["text-decoration-thickness"] == "1px" and link["text-underline-offset"] == "var(--sp-1)", "the underline is 1px at 4px, so the hover rules set only the line (the shorthand would reset the thickness to auto)"
    assert any(parts == [".row-link:hover", ".rows:focus-visible .row.is-active .row-link"] and body.get("text-decoration-line") == "underline" for parts, body in each)
    for status in (".is-waiting", ".is-attention", ".is-done", ".is-plain", ".row-status"):
        assert "text-decoration" not in merged[status] and "cursor" not in merged[status], status
    for theme in ("light", "dark"):
        assert ratio("--link", "--text", theme) < 3, "the colour alone would not do: at rest the column, the weight and the icon are the cue"
    assert _forced_colours()[".row-link"] == {"color": "LinkText", "text-decoration-line": "underline"}


def test_the_tax_year_column_shows_only_when_its_list_holds_more_than_one_year(tmp_path):
    """P268: Overview and Reminders draw their Tax Year column - the header
    and each row's year cell - only when the list's rows hold more than one
    year. A blank year (a paused household's row) is not a year."""
    ran = run_lists("""
      const state = () => {
        const out = {};
        for (const level of ["overview", "reminders"]) {
          const page = draw(level);
          out[level] = { heads: page.byClass("col-head").map((one) => one.textContent), rows: page.byClass("row").length,
                         years: page.byClass("row-year").length, yearless: page.classList.contains("is-yearless") };
        }
        return out;
      };
      const two = state();
      shellFirmData.returns.forEach((one) => { one.year = 2025; });
      const one = state();
      shellFirmData.returns[0].paused = true;
      const paused = state();
      return { two, one, paused };
    """, tmp_path)
    for level, words in (("overview", ["Taxpayer", "Form Type", "Status", "Date"]), ("reminders", ["Taxpayer", "Form Type", "Stage", "Drafted"])):
        assert ran["two"][level]["heads"] == ["Tax Year", *words] and ran["two"][level]["years"] == ran["two"][level]["rows"] and not ran["two"][level]["yearless"]
        assert ran["one"][level]["heads"] == words and ran["one"][level]["years"] == 0 and ran["one"][level]["yearless"]
    assert ran["paused"]["overview"]["rows"] == ran["one"]["overview"]["rows"] + 1, "the paused household has its row"
    assert ran["paused"]["overview"]["yearless"] and ran["paused"]["overview"]["years"] == 0, "its blank year is not a year"


def test_a_tab_or_a_page_turn_never_shows_or_hides_the_tax_year_column(tmp_path):
    """P268: the years are counted over the whole list, before its tab and its
    pages, so switching the Overview's tab or turning a page never makes the
    column come or go."""
    ran = run_lists("""
      shellFirmData.returns.push(...Array.from({ length: 60 }, (_, n) => line(`1040 - Zed ${String(n).padStart(2, "0")}`, "Alpha",
        { counts: { ...zero, needs_you: 1 }, oldest: "2026-03-09" })));
      const shape = () => { const page = draw("overview"); return { rows: page.byClass("row").length, years: page.byClass("row-year").length,
                                                                  heads: page.byClass("col-head").length, yearless: page.classList.contains("is-yearless") }; };
      const all = shape();
      pagesTab = "need";
      const need = shape();
      pagesTab = "all"; pagesPageAt.overview = 0;
      const first = shape();
      return { all, need, first };
    """, tmp_path)
    for shape in ran.values():
        assert shape["heads"] == 5 and shape["years"] == shape["rows"] > 0 and not shape["yearless"], shape
    assert ran["first"]["rows"] == 50, "page one is all 2025: the 2024 return is further down the list"


def test_an_order_by_tax_year_waits_while_the_column_is_hidden_and_is_kept(tmp_path):
    """P268: a kept order by Tax Year is not applied while the column is not
    drawn (the usual order, so a paused household still leads), shows no
    arrow on any header, and is kept: it applies again when the column returns."""
    ran = run_lists("""
      shellFirmData.returns[0].paused = true;
      const twoUsual = names(draw("overview"));
      pagesOrderBy("overview", "year");
      const twoOrdered = names(box);
      shellFirmData.returns.forEach((one) => { one.year = 2025; });
      const oneDrawn = names(draw("overview"));
      const oneSorts = sorts(box);
      const kept = JSON.stringify(pagesStoredOrder().overview);
      shellFirmData.returns[2].year = 2024;
      const back = names(draw("overview"));
      return { twoUsual, twoOrdered, oneDrawn, oneSorts, kept, back };
    """, tmp_path)
    assert ran["twoOrdered"][0] == "Charlie", "with two years the order by Tax Year applies (2024 first)"
    assert ran["oneDrawn"] == ["Alpha", "Echo", "Bravo", "Alpha", "Charlie", "Delta"], "the paused household leads, then the usual order"
    assert set(ran["oneSorts"]) <= {"none", ""}, "no header shows an arrow for the waiting order"
    assert json.loads(ran["kept"]) == {"cell": "year", "dir": 1}, "the stored order is left as it was"
    assert ran["back"] == ran["twoOrdered"], "it applies again when the column is back"


def test_a_hidden_tax_year_is_still_said_to_a_screen_reader(tmp_path):
    """P268: with the column left out each return row's description ends with
    its year; with the column shown the year is not repeated there."""
    ran = run_lists("""
      const said = (page) => page.byClass("row-return").map((row) => row.attrs["aria-description"]);
      const two = said(draw("overview"));
      shellFirmData.returns.forEach((one) => { one.year = 2025; });
      const one = said(draw("overview"));
      return { two, one };
    """, tmp_path)
    assert ran["one"] and all(text.endswith(", 2025") for text in ran["one"]), ran["one"]
    assert ran["two"] and not any("2025" in text or "2024" in text for text in ran["two"]), ran["two"]


def test_a_list_without_its_tax_year_draws_four_columns_in_its_rows_and_its_heads():
    """P268: the rows and both header rows share one four-column grid and the
    matching least width, drawn from the same tokens as the five-column grid."""
    _merged, each = _shell_rules()
    four = "var(--size-col-taxpayer) var(--size-col-form) var(--size-col-status) var(--size-col-end)"
    grids = [parts for parts, body in each if body.get("grid-template-columns") == four]
    assert grids == [["#page.is-yearless .row-return:not(.hidden)", '#page.is-yearless .col-table[data-list="overview"] .col-heads:not(.hidden)',
                      '#page.is-yearless .col-table[data-list="reminders"] .col-heads:not(.hidden)']]
    least = [body["min-width"] for parts, body in each if '#page.is-yearless .col-table[data-list="overview"]' in parts]
    assert len(least) == 1
    assert "var(--size-col-year)" not in least[0] and "3 * var(--sp-4)" in least[0] and "2 * var(--sp-8)" in least[0]
    for token in ("taxpayer", "form", "status", "end"):
        assert f"var(--size-col-{token})" in least[0]


def test_an_overview_date_says_whether_it_is_since_or_due(tmp_path):
    """P269 (option c, Jason 2026-10-11: "Say what each cell is instead of
    just saying date"): a return that needs a person says "Since Mar 3" (the
    day its oldest waiting file arrived), a return waiting on the taxpayer
    "Due Apr 15"; the header stays "Date" and the order key stays the ISO day."""
    assert api.SCREEN["since"] == "Since {date}" and api.SCREEN["due"] == "Due {date}" and api.SCREEN["columns"]["date"] == "Date"
    ran = run_lists("""
      const page = draw("overview");
      const dates = page.byClass("row").map((row) => [row.byClass("row-name")[0].textContent, row.byClass("row-date")[0].textContent]);
      pagesOrderBy("overview", "end");
      return { dates, byDate: names(box), heads: page.byClass("col-head").map((one) => one.textContent) };
    """, tmp_path)
    dates = dict(ran["dates"])
    assert dates["Alpha"] == "Since Mar 5" and dates["Bravo"] == "Since Mar 1"
    assert dates["Echo"] == "", "a return that could not be read has no oldest day, so no word"
    assert dates["Charlie"] == "Due Apr 15"
    assert ran["byDate"] == ["Bravo", "Alpha", "Charlie", "Echo", "Delta"], "the engine orders by the ISO day, never the drawn words"
    assert ran["heads"][-1] == "Date"


def test_a_row_with_a_step_shows_a_quiet_chevron_at_rest_and_its_words_on_hover_or_the_keyboards_active_row(tmp_path):
    """P270: a row with a next step shows a chevron at the right edge of its
    end column at rest, in --text-caption; on hover, or on the keyboard's
    active row, the step's words appear before it and both turn --link, in
    place of the date. A row with no step has no chevron."""
    ran = run_pages_dom("""
      const step = { kind: "check", ret: "r1", name: "a.pdf", handle: "h1" };
      const row = pagesRow({ name: "a.pdf", status: "Could Not Tell", tone: "needs", pill: true, menu: "file", step, date: "Mar 3" });
      const end = row.byClass("row-end")[0];
      const mark = end.byClass("row-step")[0];
      const bare = pagesRow({ name: "b.pdf", status: "Could Not Tell", tone: "needs", pill: true, menu: "file", date: "Mar 3" });
      locked = true;
      const edit = pagesRow({ name: "c", status: "x", tone: "needs", menu: "return", date: "", step: { kind: "edit", route: {} } });
      return { ends: end.kids.map((one) => one.className.split(" ")[0]), hidden: mark.attrs["aria-hidden"],
               parts: mark.kids.map((one) => [one.tag, one.className.split(" ")[0]]), words: mark.byClass("row-step-words")[0].textContent,
               described: row.attrs["aria-description"], hasStep: row.className.includes("has-step"),
               bare: bare.byClass("row-end")[0].kids.map((one) => one.className.split(" ")[0]), lockedEdit: edit.byClass("row-end")[0].kids.map((one) => one.className.split(" ")[0]) };
    """, tmp_path)
    assert ran["ends"] == ["row-date", "row-step"] and ran["hidden"] == "true" and ran["hasStep"]
    assert ran["parts"] == [["span", "row-step-words"], ["svg", "icon"]] and ran["words"] == "Check"
    assert ran["described"].startswith("Check"), "the words are in the description, so the hidden step is never read twice"
    assert ran["bare"] == ["row-date"] and ran["lockedEdit"] == ["row-date"], "no step, no chevron (a live lock takes Edit away)"
    merged, each = _shell_rules()
    rest = merged[".row-step:not(.hidden)"]
    assert "visibility" not in rest and rest["color"] == "var(--text-caption)" and rest["justify-self"] == "end"
    assert merged[".row-step-words"] == {"display": "none"}
    assert any(parts == [".row:hover .row-step-words:not(.hidden)", ".rows:focus-visible .row.is-active .row-step-words:not(.hidden)"]
               and body == {"display": "inline"} for parts, body in each)
    assert any(parts == [".row:hover .row-step", ".rows:focus-visible .row.is-active .row-step"] and body == {"color": "var(--link)"} for parts, body in each)
    assert merged[".row.has-step .row-date"]["margin-inline-end"] == "var(--sp-6)"
    assert merged[".row.has-step:hover .row-date"]["visibility"] == "hidden", "the date still gives way to the step's words"


def test_sort_now_is_a_labelled_button_on_a_households_pages_and_absent_from_the_firm_pages(tmp_path):
    """P274, SPEC-shell 8.1 (replaces the sort icon's test): Sort Now is shown
    and enabled on a household's, a year's and a return's page with the tooltip
    that says what it sorts; shown but disabled, still saying Sort Now, when
    the return is locked elsewhere; and on the four firm pages and the setup
    page it is not drawn at all."""
    setup = PEOPLE + """
      let shellRoute = null; let scanning = null; let locked = false;
    """
    probe = """
      const at = (route, run, lock) => { shellRoute = route; scanning = run; locked = lock; const s = sortState();
                                         return [s.key, Boolean(s.hidden), s.off, s.words || null, s.tip]; };
      return {
        household: at({ level: "household", household: "h1" }, null, false),
        year: at({ level: "year", household: "h1", year: 2025 }, null, false),
        ret: at({ level: "return", household: "h1", ret: "r1" }, null, false),
        firm: ["overview", "needs-review", "reminders", "clients", "setup"].map((level) => at({ level }, null, false)),
        locked: at({ level: "return", household: "h1", ret: "r1" }, null, true),
      };
    """
    ran = run_shell(["screenWords", "shellHasClient", "sortState"], setup, probe, tmp_path)
    ready = ["now", False, False, "Sort now", "Sort this household's inbox"]
    assert ran["household"] == ran["year"] == ran["ret"] == ready
    assert ran["firm"] == [["none", True, True, None, ""]] * 5, "a firm page has no sort control (P274)"
    assert ran["locked"] == ["locked", False, True, "Sort now", "In use elsewhere"]


def test_stop_sorting_shows_on_every_page_while_this_apps_sort_runs(tmp_path):
    """P274: while a sort the app started runs, Stop Sorting shows and is
    enabled on every page, firm pages and the setup page included, so a
    running sort can always be stopped; after Stop it says Stopping,
    disabled. A scheduled pass running (P256) alone changes nothing."""
    setup = PEOPLE + """
      let shellRoute = null; let scanning = null; let locked = false; let shellLastPass = null;
    """
    probe = """
      const levels = ["overview", "needs-review", "reminders", "clients", "household", "year", "return", "setup"];
      const at = (level, run) => { shellRoute = { level, household: "h1", ret: "r1", year: 2025 }; scanning = run; const s = sortState();
                                   return [s.key, Boolean(s.hidden), s.off, s.words]; };
      const sorting = levels.map((level) => at(level, { stopping: false }));
      const stopping = levels.map((level) => at(level, { stopping: true }));
      const quiet = [at("overview", null), at("household", null)];
      shellLastPass = { running: true };
      const scheduled = [at("overview", null), at("household", null)];
      return { sorting, stopping, quiet, scheduled };
    """
    ran = run_shell(["screenWords", "shellHasClient", "sortState"], setup, probe, tmp_path)
    assert ran["sorting"] == [["stop", False, False, "Stop sorting"]] * 8
    assert ran["stopping"] == [["stopping", False, True, "Stopping"]] * 8
    assert ran["scheduled"] == ran["quiet"], "a scheduled pass changes nothing about the button"


#: A fake page for drawSort: the element classes the speed round's DOM lacks.
_SORT_BUTTON = """
  Object.defineProperty(Element.prototype, "textContent", {
    get() { return this.kids.map((one) => (one instanceof Text ? one.data : one.textContent)).join(""); },
    set(value) { this.kids = []; this.append(String(value)); } });
  Element.prototype.querySelectorAll = function (sel) { return this.byClass(sel.slice(1)); };
  Element.prototype.removeAttribute = function (key) { delete this.attrs[key]; };
  Element.prototype.focus = function () { document.activeElement = this; };
  const els = {}; const $ = (id) => els[id] || (els[id] = new Element("div"));
  vocab.screen.sort = { now: "Sort now", stop: "Stop sorting", locked: "In use elsewhere", stopping: "Stopping", tip: "Sort this household's inbox" };
  let shellRoute = null; let scanning = null;
"""


def test_the_sort_button_keeps_one_width_whatever_it_says(tmp_path):
    """P274: the button is built once with three words (Sort Now, Stop Sorting,
    Stopping) that share one grid cell, so it is as wide as the longest in
    every state and the search box never moves; in each state exactly one is
    not aria-hidden, and the CSS hides the others with visibility."""
    ran = run_pages_dom("""
      const button = $("sort");
      const at = (route, run, lock) => { shellRoute = route; scanning = run; locked = lock; drawSort();
        const words = button.byClass("sort-word");
        return { words: words.map((one) => one.textContent), shown: words.filter((one) => one.attrs["aria-hidden"] === undefined).map((one) => one.dataset.word),
                 hidden: button.classList.contains("hidden"), disabled: button.disabled, stop: button.classList.contains("is-stop"),
                 state: button.dataset.sortState, tip: tips.at(-1)[1], keys: button.attrs["aria-keyshortcuts"] ?? null }; };
      const now = at({ level: "household", household: "h1" }, null, false);
      const spans = button.byClass("sort-word");
      const stop = at({ level: "overview" }, { stopping: false }, false);
      const same = button.byClass("sort-word").length === 3 && button.byClass("sort-word").every((one, i) => one === spans[i]);
      return { now, same, locked: at({ level: "household", household: "h1" }, null, true), stop,
               stopping: at({ level: "overview" }, { stopping: true }, false), none: at({ level: "overview" }, null, false) };
    """, tmp_path, setup=_SORT_BUTTON, functions=["drawSort", "sortState", "screenWords", "shellHasClient", "focusRegion", "h"])
    assert ran["now"]["words"] == ["Sort now", "Stop sorting", "Stopping"] and ran["same"], "three words, made once"
    assert ran["now"]["shown"] == ["now"] and ran["now"]["keys"] == "F9" and ran["now"]["tip"] == "Sort this household's inbox"
    assert ran["locked"]["shown"] == ["now"] and ran["locked"]["disabled"] and ran["locked"]["tip"] == "In use elsewhere" and ran["locked"]["keys"] is None
    assert ran["stop"]["shown"] == ["stop"] and ran["stop"]["stop"] and not ran["stop"]["disabled"] and not ran["stop"]["hidden"] and ran["stop"]["tip"] == ""
    assert ran["stopping"]["shown"] == ["stopping"] and ran["stopping"]["disabled"]
    assert ran["none"]["hidden"] and ran["none"]["state"] == "none"
    merged, _each = _shell_rules()
    assert merged["#sort:not(.hidden)"]["display"] == "inline-grid"
    assert merged["#sort > .sort-word"]["grid-area"] == "1 / 1"
    assert merged['#sort > .sort-word[aria-hidden="true"]'] == {"visibility": "hidden"}
    assert merged["#sort.is-stop"]["--b-fg"] == "var(--danger)"
    html = read("index.html")
    assert '<button id="sort" class="btn hidden" type="button"></button>' in html and 'id="sort" class="icon-button"' not in html
    assert "i-sort" not in html and "i-stop" not in html


def test_a_focused_sort_button_that_goes_away_hands_focus_to_the_search_box(tmp_path):
    """P274: when the shown route moves to a page with no Sort Now while the
    button holds focus, focus goes to the search box (to the page when the
    search box is disabled, on the setup page), never to the window."""
    ran = run_pages_dom("""
      const button = $("sort"); const find = $("find"); const page = $("page");
      button.matches = (sel) => sel === ":focus-visible";   // a keyboard user: the ring shows
      const focused = () => (document.activeElement === button ? "sort" : document.activeElement === find ? "find" : document.activeElement === page ? "page" : "none");
      shellRoute = { level: "household", household: "h1" }; scanning = null; locked = false; drawSort();
      button.focus();
      const before = focused();
      shellRoute = { level: "overview" }; drawSort();
      const toFind = focused();
      shellRoute = { level: "household", household: "h1" }; drawSort(); button.focus();
      shellRoute = { level: "setup" }; drawSort();
      const toPage = focused();
      return { before, toFind, toPage, hidden: button.classList.contains("hidden") };
    """, tmp_path, setup=_SORT_BUTTON, functions=["drawSort", "sortState", "screenWords", "shellHasClient", "focusRegion", "h"])
    assert ran == {"before": "sort", "toFind": "find", "toPage": "page", "hidden": True}


def test_a_focused_sort_button_hands_focus_on_before_it_is_disabled(tmp_path):
    """P274 (review 1, finding 5): Chromium drops the focus of a button to the
    window the moment it is disabled, so Stop Sorting -> Stopping (and Sort
    Now -> In Use Elsewhere) would lose a keyboard user's place before the
    button is ever hidden. drawSort hands focus to the search box first, as it
    does for a button about to be hidden, and leaves it alone when the button
    stays enabled. A mouse click's focus (no :focus-visible ring) goes to the
    page instead, so no caret jumps into the box (review 2, note 4). The fake
    button drops focus on disabling, as Chromium does."""
    ran = run_pages_dom("""
      const button = $("sort"); const find = $("find"); const window = new Element("div");
      let off = false; let byKey = true;
      button.matches = (sel) => sel === ":focus-visible" && byKey;
      Object.defineProperty(button, "disabled", { get() { return off; },
        set(value) { off = Boolean(value); if (off && document.activeElement === button) document.activeElement = window; } });
      const focused = () => (document.activeElement === button ? "sort" : document.activeElement === find ? "find" : document.activeElement === window ? "window" : document.activeElement === $("page") ? "page" : "none");
      shellRoute = { level: "household", household: "h1" }; scanning = null; locked = false; drawSort();
      button.focus(); scanning = { stopping: false }; drawSort();
      const stop = { focus: focused(), disabled: off };
      scanning = { stopping: true }; drawSort();
      const stopping = { focus: focused(), disabled: off };
      scanning = null; drawSort(); button.focus(); locked = true; drawSort();
      const lockedNow = { focus: focused(), disabled: off };
      locked = false; drawSort(); byKey = false; button.focus(); scanning = { stopping: false }; drawSort(); scanning = { stopping: true }; drawSort();
      const byMouse = { focus: focused(), disabled: off };
      return { stop, stopping, lockedNow, byMouse };
    """, tmp_path, setup=_SORT_BUTTON, functions=["drawSort", "sortState", "screenWords", "shellHasClient", "focusRegion", "h"])
    assert ran["stop"] == {"focus": "sort", "disabled": False}, "an enabled button keeps the focus it has"
    assert ran["stopping"] == {"focus": "find", "disabled": True}, "disabled, it hands focus on first"
    assert ran["lockedNow"] == {"focus": "find", "disabled": True}
    assert ran["byMouse"] == {"focus": "page", "disabled": True}, "a mouse click's focus (no ring) goes to the page, not the search box"


def test_a_mac_is_known_from_the_browsers_own_platform_and_every_other_system_keeps_segoe(tmp_path):
    """P280: app.js tells a Mac from the browser's own platform (no new channel
    from main.js) and puts on-mac on <html> before anything draws; Windows,
    Linux and an empty navigator are not a Mac."""
    ran = run_shell(["appOnMac"], "", """
      return { mac: appOnMac({ platform: "MacIntel" }), macUA: appOnMac({ userAgentData: { platform: "macOS" } }),
               win: appOnMac({ platform: "Win32" }), winUA: appOnMac({ userAgentData: { platform: "Windows" }, platform: "Win32" }),
               linux: appOnMac({ platform: "Linux x86_64" }), none: appOnMac({}) };
    """, tmp_path, source="app.js")
    assert ran == {"mac": True, "macUA": True, "win": False, "winUA": False, "linux": False, "none": False}
    app = read("app.js")
    statement = 'document.documentElement.classList.toggle("on-mac", appOnMac(navigator));'
    assert f"\n{statement}\n" in app, "top level, not inside a function"
    assert app.index(statement) < app.index("function applyVocabulary")


# ── P271-P273, P275 (SPEC-ui-menu-layout) ───────────────────────────────────
# ── L1: View > Compact Rows (P271) ──────────────────────────────────────────

#: A document root with a class list, one active row and the shell's three
#: seams (hideTip, shellEnable, the storage), for the Compact Rows functions.
COMPACT_PANEL = r"""
const store = { data: {}, broken: false,
  getItem(k) { if (this.broken) throw new Error("locked"); return k in this.data ? this.data[k] : null; },
  setItem(k, v) { if (this.broken) throw new Error("locked"); this.data[k] = String(v); },
  removeItem(k) { if (this.broken) throw new Error("locked"); delete this.data[k]; } };
const window = { localStorage: store };
const ROWS_KEY = "tracker.rows";
const SOON_KEY = "tracker.underConstruction";
let shellCompact = null;
let shellSoonHidden = null;
const said = { tips: 0, sent: [], focus: [], scrolled: [], asked: [] };
let activeRow = { scrollIntoView: (o) => said.scrolled.push(o) };
const classes = new Set();
const document = {
  activeElement: null,
  documentElement: { classList: { toggle: (c, on) => (on ? classes.add(c) : classes.delete(c)), contains: (c) => classes.has(c) } },
  querySelector: (sel) => { said.asked.push(sel); return activeRow; },
};
function focusRegion(name) { said.focus.push(name); }
function hideTip() { said.tips += 1; }
function shellEnable() { said.sent.push(shellChecked()); }
const page = { id: "page", querySelectorAll: () => [] };
const $ = (id) => page;
function pagesVirtualMeasure(root) {
  said.measured = (said.measured || 0) + (root === page ? 1 : 0);
  if (said.boom) throw new Error("row_height");
}
function editorDensityChanged() { said.density = (said.density || 0) + 1; }
said.failed = [];
function failed(err) { said.failed.push(err.message); }
""" + js_function("pagesVirtualMeasureSaid", "pages.js")

COMPACT_FUNCTIONS = ["shellReadSoon", "shellReadCompact", "shellChecked", "drawCompact", "shellToggleCompact"]


def test_compact_rows_are_off_until_chosen_and_the_menu_flips_keeps_and_says_the_tick(tmp_path):
    """P271: a new install is Comfortable (no class, no tick); the menu's
    answer adds the class, keeps "compact" under tracker.rows and sends the
    tick; again removes the class, forgets the key and sends no tick."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      drawCompact();
      const first = { cls: classes.has("rows-compact"), checked: shellChecked() };
      shellToggleCompact();
      const on = { cls: classes.has("rows-compact"), stored: store.data[ROWS_KEY], checked: shellChecked() };
      shellToggleCompact();
      const off = { cls: classes.has("rows-compact"), stored: ROWS_KEY in store.data, checked: shellChecked() };
      return { first, on, off, sent: said.sent, focus: said.focus };
    """, tmp_path)
    assert ran["first"] == {"cls": False, "checked": ["show_under_construction"]}
    assert ran["on"] == {"cls": True, "stored": "compact", "checked": ["show_under_construction", "compact_rows"]}
    assert ran["off"] == {"cls": False, "stored": False, "checked": ["show_under_construction"]}
    assert ran["sent"] == [["show_under_construction", "compact_rows"], ["show_under_construction"]]
    assert ran["focus"] == [], "a check item moves no focus"


def test_storage_that_cannot_be_read_keeps_comfortable_rows_and_a_choice_holds_while_the_app_is_open(tmp_path):
    """P271: unreadable storage is Comfortable, and a choice it refuses to keep
    still holds until the app closes."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      store.broken = true;
      drawCompact();
      const first = classes.has("rows-compact");
      shellToggleCompact();
      return { first, after: classes.has("rows-compact"), checked: shellChecked() };
    """, tmp_path)
    assert ran == {"first": False, "after": True, "checked": ["show_under_construction", "compact_rows"]}


def test_a_damaged_stored_density_reads_as_comfortable(tmp_path):
    """P271: only the exact word "compact" is compact (as P197's "hidden")."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      const seen = [];
      for (const value of ["COMPACT", "1", "true", ""]) {
        store.data[ROWS_KEY] = value; shellCompact = null; drawCompact();
        seen.push([classes.has("rows-compact"), shellChecked()]);
      }
      store.data[ROWS_KEY] = "compact"; shellCompact = null; drawCompact();
      seen.push([classes.has("rows-compact"), shellChecked()]);
      return seen;
    """, tmp_path)
    assert ran == [[False, ["show_under_construction"]]] * 4 + [[True, ["show_under_construction", "compact_rows"]]]


def test_a_stored_density_applies_at_load_before_the_words():
    """P271 (as P197's review S1 pinned for drawSoon): a top-level
    drawCompact(); in shell.js, so the first paint's outline rows are the
    chosen height; the key is its own, on this PC; the menu's id is answered
    and enabled from the first frame."""
    text = stripped_js("shell.js")
    assert 'const ROWS_KEY = "tracker.rows";' in text
    assert re.search(r"^drawCompact\(\);$", text, flags=re.M), "a stored compact applies at load, before the words"
    assert "compact_rows: () => shellToggleCompact()," in text
    first = [line for line in js_function("shellEnabled").splitlines() if "const ids = [" in line]
    assert len(first) == 1 and '"compact_rows"' in first[0]
    assert "tracker.rows" not in (REPO / "tracker" / "settings.py").read_text(encoding="utf-8")


def _specificity(selector: str) -> tuple[int, int, int]:
    """(ids, classes/attributes/pseudo-classes, types) of one compound or
    descendant selector; :is() and :not() take their most specific argument,
    as CSS does. Enough for the selectors of the two stylesheets."""
    ids = classes = types = 0
    i = 0
    while i < len(selector):
        c = selector[i]
        if c == "#":
            ids += 1
            i += 1
        elif c == "." or c == "[":
            classes += 1
            i += 1
        elif c == ":":
            end = i + 1
            while end < len(selector) and (selector[end].isalnum() or selector[end] == "-"):
                end += 1
            if end < len(selector) and selector[end] == "(":
                depth, close = 1, end + 1
                while depth:
                    depth += {"(": 1, ")": -1}.get(selector[close], 0)
                    close += 1
                if selector[i + 1:end] in ("is", "not"):
                    inner = max(_specificity(part.strip()) for part in re.split(r",(?![^(]*\))", selector[end + 1:close - 1]))
                    ids, classes, types = ids + inner[0], classes + inner[1], types + inner[2]
                else:
                    classes += 1
                i = close
            else:
                classes += 1
                i = end
        elif c.isalpha():
            if i == 0 or selector[i - 1] in " >+~":
                types += 1
            while i < len(selector) and (selector[i].isalnum() or selector[i] == "-"):
                i += 1
        else:
            i += 1
    return ids, classes, types


def test_a_compact_row_is_32px_on_every_list_page_and_in_the_editor():
    """P271: --size-row-compact is 32px and --size-row is still 40px; the
    compact block covers the rows, their outline and the editor's fields.
    Review 1, finding 1: the compact field rule and the Comfortable 28px rule
    carry the scope of pilot-ui.css's general field rule (whose #page counts
    as an id), so each outranks it - by specificity, not by source order."""
    light, _dark = root_blocks()
    assert light["--size-row-compact"] == "32px" and light["--size-row"] == "40px"
    assert light["--size-control-sm"] == "24px"
    seen = {}
    for _media, selector, body in blocks(read("shell.css")):
        if ".rows-compact" in selector:
            seen[" ".join(selector.split())] = dict(declarations(body))
    rules = list(seen.items())
    row = [s for s, _ in rules if re.search(r"\.row\b(?!-)", s) and ".row-skeleton" in s]
    field = [s for s, _ in rules if ".editor-table" in s]
    assert row and field, sorted(seen)
    assert ".row," in row[0], "the rows and their outline share one rule"
    assert seen[row[0]]["min-height"] == "var(--size-row-compact)"
    assert seen[field[0]]["min-height"] == "var(--size-control-sm)"
    assert seen[".rows-compact .row-year"] == {"font-size": "var(--fs-caption)", "line-height": "var(--lh-caption)"}
    assert "input" in field[0] and "select" in field[0]
    scope = ":is(#page, #sheet, .modal-overlay)"
    assert field[0].startswith(f".rows-compact {scope} .editor-table "), field[0]
    general = comfortable = None
    for _media, selector, body in blocks(read("pilot-ui.css")):
        selector = " ".join(selector.split())
        if selector.startswith(scope) and selector.endswith("textarea)") and "min-height" in dict(declarations(body)):
            general = selector
        if selector.endswith(".editor-table :is(input:not([type=\"checkbox\"]):not([type=\"radio\"]), select)") and dict(declarations(body)).get("min-height") == "28px":
            comfortable = selector
    assert general and comfortable, "the general field rule and the Comfortable 28px rule are in pilot-ui.css"
    assert comfortable.startswith(f"{scope} .editor-table ")
    assert _specificity(comfortable) > _specificity(general), "Comfortable's 28px must beat the general 32px field rule"
    assert _specificity(field[0]) > _specificity(comfortable), "Compact's 24px must beat Comfortable's 28px"


def test_compact_rows_change_heights_and_the_years_size_never_a_column():
    """P271: every rule that names .rows-compact declares only min-height,
    font-size and line-height - no width, no column, no padding - so a kept
    column width means the same in both densities and the 1100px arithmetic
    of SPEC-shell 3.6 stands."""
    found = 0
    for _media, selector, body in blocks(read("shell.css")):
        if ".rows-compact" in selector:
            found += 1
            assert {prop for prop, _ in declarations(body)} <= {"min-height", "font-size", "line-height"}, selector.strip()
    assert found >= 3


def test_switching_density_keeps_the_active_row_in_view_and_hides_a_showing_tip(tmp_path):
    """P271: every row moved, so a showing tip goes and the active row of the
    last-used list is scrolled into view (nearest); with no list on the page
    nothing is scrolled; focus is not moved."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      shellToggleCompact();
      const withRow = { scrolled: [...said.scrolled], tips: said.tips, asked: [...said.asked] };
      activeRow = null;
      shellToggleCompact();
      return { withRow, tips: said.tips, scrolled: said.scrolled.length, focus: said.focus };
    """, tmp_path)
    assert ran["withRow"] == {"scrolled": [{"block": "nearest"}], "tips": 1, "asked": [".rows .row.is-active"]}
    assert ran["tips"] == 2 and ran["scrolled"] == 1 and ran["focus"] == []


def test_switching_density_scrolls_the_focused_lists_active_row_not_the_first_lists(tmp_path):
    """P271 (review 1, finding 2): every list a person has visited keeps its
    own active row, so with two lists on the page and the second holding
    focus, the second's row is the one scrolled into view; with no list
    focused the first active row on the page is."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      const seen = [];
      const list = (name) => ({ querySelector: (sel) => ({ scrollIntoView: (o) => seen.push([name, sel, o.block]) }) });
      const second = list("second");
      document.activeElement = { closest: (sel) => (sel === ".rows" ? second : null) };
      shellToggleCompact();
      document.activeElement = { closest: () => null };
      activeRow = { scrollIntoView: (o) => seen.push(["page", "any", o.block]) };
      shellToggleCompact();
      return { seen };
    """, tmp_path)
    assert ran["seen"] == [["second", ".row.is-active", "nearest"], ["page", "any", "nearest"]]


# ── L2: Needs Review, one flat list (P272) ──────────────────────────────────

def test_needs_review_is_one_flat_list_with_no_card_pill_or_folder_icon(tmp_path):
    """P272: each return with files waiting is an ordinary group, as on a
    return's own page: a heading followed by its rows. No card, no raised
    box, no folder icon, no "2 Documents" pill."""
    ran = run_lists("""
      const page = draw("needs-review");
      const classes = new Set(page.find(() => true).flatMap((n) => n.className.split(" ")));
      const has = (n, c) => n.className.split(" ").includes(c);
      const heads = page.kids.filter((n) => has(n, "group-head") && !has(n, "page-head"));
      const next = heads.map((head) => has(page.kids[page.kids.indexOf(head) + 1], "rows"));
      return { banned: ["return-card", "group-docs", "group-icon"].filter((c) => classes.has(c)), heads: heads.length, next };
    """, tmp_path)
    assert ran == {"banned": [], "heads": 2, "next": [True, True]}


def test_a_needs_review_heading_says_the_return_then_the_household_and_its_count(tmp_path):
    """P272: the heading's caption is the household (a link, with its link
    mark when linked), then " · " and the count; "1 Document" for one; the
    count alone with no household known. The words are the vocabulary's."""
    ran = run_lists("""
      shellFirmData.returns[1].household = "";
      const page = draw("needs-review");
      const link = (n) => n.byClass("row-link").map((l) => [l.textContent, l.dataset.link]);
      return page.byClass("group-head").filter((n) => !n.className.includes("page-head"))
        .map((head) => { const c = head.byClass("group-count")[0]; return [c.textContent, link(c)]; });
    """, tmp_path)
    assert ran == [["1 Document", []], ["Alpha · 2 Documents", [["Alpha", "household"]]]], "the groups follow their first file; Bravo's came first"
    with_household = run_lists("""
      const page = draw("needs-review");
      return page.byClass("group-head").filter((n) => !n.className.includes("page-head")).map((head) => head.byClass("group-count")[0].textContent);
    """, tmp_path)
    assert with_household == ["Bravo · 1 Document", "Alpha · 2 Documents"]


def test_more_actions_follows_the_count_and_opens_the_returns_own_menu(tmp_path):
    """P272: the More Actions button is the heading's last part, after the
    count; a click opens the return's native menu at the button's bottom-left
    with the page's enable list for the group's token; a right-click on the
    heading does the same at the pointer."""
    ran = run_lists("""
      const enabled = []; shellEnabled = (route) => { enabled.push(route.level); return ["open_inbox"]; };
      const page = draw("needs-review");
      const head = page.byClass("group-head").filter((n) => !n.className.includes("page-head"))[0];
      const button = head.byClass("group-more")[0];
      const order = head.kids.map((k) => k.className.split(" ")[0]);
      const attrs = { label: button.attrs["aria-label"], popup: button.attrs["aria-haspopup"], tip: tips.filter(([cls]) => cls.includes("group-more")).map(([, words]) => words) };
      button.handlers.click[0]({});
      head.handlers.contextmenu[0]({ preventDefault() {}, clientX: 70, clientY: 80 });
      return { order, attrs, popups, enabled };
    """, tmp_path)
    assert ran["order"][-2:] == ["group-count", "icon-button"], "the button sits right after the count"
    assert ran["attrs"]["label"] == "More Actions" and ran["attrs"]["popup"] == "menu"
    assert set(ran["attrs"]["tip"]) == {"More Actions"}
    assert [p[0] for p in ran["popups"]] == ["return", "return"] and ran["popups"][0][1] == ran["popups"][1][1]
    assert ran["popups"][0][1].startswith("row-") and ran["popups"][0][4] == ["open_inbox"]
    assert ran["popups"][0][2:4] == [10, 20] and ran["popups"][1][2:4] == [70, 80]
    assert ran["enabled"] == ["return", "return"]


def test_the_first_needs_review_heading_is_the_pages_first_group(tmp_path):
    """P272: the first heading drawn sits 24px under the column headers
    (is-first); the next ones do not. When the first group cannot be built
    and is named in a notice, the next one is the page's first."""
    ran = run_lists("""
      const firsts = (page) => page.byClass("group-head").filter((n) => !n.className.includes("page-head")).map((n) => n.className.split(" ").includes("is-first"));
      const whole = firsts(draw("needs-review"));
      const real = pagesReviewGroup;
      let called = 0;
      pagesReviewGroup = (group, specs, first) => { called += 1; if (called === 1) throw new Error("not built"); return real(group, specs, first); };
      const after = firsts(draw("needs-review"));
      return { whole, after, broken: pagesBroken.length };
    """, tmp_path)
    assert ran == {"whole": [True, False], "after": [True], "broken": 1}, "the group drawn first failed, so the survivor is the page's first"


def test_no_card_rule_remains_and_a_needs_review_row_starts_at_the_keyline():
    """P272: no selector in shell.css names .return-card or .group-docs, and
    no rule overrides a row's padding for Needs Review, so its rows start at
    the page's keyline under their column headers. A return's heading centres
    its chip and its 24px button (:has(.group-more)); the page's title row
    keeps its baseline."""
    css = stripped(read("shell.css"))
    assert ".return-card" not in css and ".group-docs" not in css
    first = {}
    for _media, selector, body in blocks(read("shell.css")):
        for part in selector.split(","):
            first.setdefault(" ".join(part.split()), dict(declarations(body)))
    for selector, body in first.items():
        if "needs_review" in selector or "return-card" in selector:
            assert "padding" not in body and "padding-left" not in body, selector
    assert first[".group-head:has(.group-more):not(.hidden)"] == {"align-items": "center"}
    assert first[".page-head.group-head:not(.hidden)"]["align-items"] == "baseline"
    more = first[".group-more.icon-button:not(.hidden)"]
    assert more["width"] == more["height"] == "var(--size-control-sm)"
    assert more["margin-left"] == "var(--sp-1)" and more["color"] == "var(--text-secondary)"


# ── L3: the notices panel (P273) ────────────────────────────────────────────

PANEL_MEDIA = ("@media (min-width: 1388px)",)


def _panel_rules() -> dict[str, dict[str, str]]:
    """The rules of shell.css's one 1388px block, by selector."""
    return {" ".join(selector.split()): dict(declarations(body))
            for media, selector, body in blocks(read("shell.css")) if media == PANEL_MEDIA}


def test_the_notices_panel_is_a_column_beside_the_page_at_1388px_and_wider():
    """P273: at 1388px and wider #page is column 1 and #notices column 2 under
    the path row, which spans both; the panel is --size-notices (288px) wide,
    --bg-nav with a hairline at its left, and scrolls inside itself."""
    rules = _panel_rules()
    assert rules["#main:not(.hidden)"] == {"grid-template-columns": "minmax(0, 1fr) auto", "grid-template-rows": "var(--size-bar) minmax(0, 1fr)"}
    assert rules["#bar:not(.hidden)"] == {"grid-column": "1 / -1"}
    assert rules["#page"] == {"grid-column": "1", "grid-row": "2"}
    assert rules["#notices"] == {"grid-column": "2", "grid-row": "2"}
    panel = rules["#notices:not(:empty)"]
    assert panel["width"] == "var(--size-notices)" and panel["background"] == "var(--bg-nav)"
    assert panel["border-left"] == "1px solid var(--border)" and panel["overflow-y"] == "auto" and panel["min-height"] == "0"
    light, _dark = root_blocks()
    assert light["--size-notices"] == "288px"
    assert "border-left-color: CanvasText" in " ".join(read("shell.css").split()), "the forced-colours block keeps the panel's edge"
    index = read("index.html")
    assert index.index('id="bar"') < index.index('id="notices"') < index.index('id="page"'), "markup order: path row, notices, page (Tab and F6 agree)"


def test_the_panel_leaves_every_page_the_860px_it_is_designed_for():
    """P273: 1388 = 240 (side panel) + 860 + 288 - the page is never narrower
    than the 860px of a 1100px window the lists are designed for (SPEC-shell
    3.6); the breakpoint is read from the media query, the rest from tokens."""
    light, _dark = root_blocks()

    def px(name: str) -> int:
        return int(light[name].strip().removesuffix("px"))

    queries = {media for media, _selector, _body in blocks(read("shell.css")) if media and "min-width: 13" in media[0]}
    assert queries == {PANEL_MEDIA}
    breakpoint_px = int(re.search(r"min-width: (\d+)px", PANEL_MEDIA[0]).group(1))
    assert breakpoint_px - px("--size-side") - px("--size-notices") == 860 == 1100 - px("--size-side")


def test_a_notices_panel_with_no_notice_takes_no_width():
    """P273: with no notice #notices is display: none (style.css), so the
    column the panel is placed in is `auto` and 0 wide; no rule of the block
    gives #notices a width while it may be empty."""
    assert re.search(r"#notices:empty\s*\{\s*display:\s*none;\s*\}", read("style.css"))
    rules = _panel_rules()
    assert rules["#main:not(.hidden)"]["grid-template-columns"].endswith(" auto")
    for selector, body in rules.items():
        if re.fullmatch(r"#notices(:[^ ]+)*", selector) and ("width" in body or "padding" in body or "border-left" in body):
            assert ":not(:empty)" in selector, selector


def test_a_notice_in_the_panel_keeps_its_sentence_details_action_and_dismiss_in_markup_order(tmp_path):
    """P273: no markup changes - drawNotice's children are the sentence, the
    Details disclosure, the action or Retry, then the dismiss; the panel's
    rules give the sentence the first line, keep an opened summary at the
    start of the second and send the buttons to its end."""
    ran = run_shell(["el", "detailOf", "retryOf", "drawNotice"], NOTICE_DETAIL_FAKES, """
      const kinds = (node) => node.kids.map((one) => one.tag === "details" ? "details" : one.className || one.tag);
      const failing = draw({ sentence: "Sort Failed", kind: "failed", count: 1, detail: "a\\nb", retry: () => {} });
      const plain = draw({ sentence: "Sort Failed", kind: "failed", count: 1, detail: "", retry: () => {} });
      return { withDetail: kinds(failing), plain: kinds(plain) };
    """, tmp_path, "app.js")
    assert ran["withDetail"] == ["notice-text", "details", "button", "button"]
    assert ran["plain"] == ["notice-text", "button", "button"]
    rules = _panel_rules()
    assert rules["#notices .notice-text"] == {"flex": "0 0 100%"}
    assert rules["#notices .notice-detail"] == {"flex": "1 1 auto"}
    assert rules["#notices .notice-detail[open]"] == {"order": "0", "flex": "0 0 100%"}
    assert rules["#notices .notice-detail[open] > summary"] == {"margin-inline-start": "0"}
    assert rules["#notices .notice-text ~ .notice-act:first-of-type"] == {"margin-inline-start": "auto"}
    notice = rules["#notices .notice:not(.hidden)"]
    assert notice["flex-wrap"] == "wrap" and notice["min-height"] == "0" and notice["row-gap"] == "var(--sp-1)"
    assert notice["padding"] == "var(--sp-2) var(--sp-2) var(--sp-2) var(--sp-4)"


def test_below_1388px_the_notices_are_n12s_one_line():
    """P273: under the breakpoint nothing of the panel applies - N12's rules
    (a 40px line, the sentence taking the slack, the Details disclosure at the
    line's end, opened under it) are outside every min-width block."""
    outside = {}
    for media, selector, body in blocks(read("shell.css")):
        if not media:
            outside.setdefault(" ".join(selector.split()), dict(declarations(body)))
    notice = outside["#notices .notice:not(.hidden)"]
    assert notice["min-height"] == "var(--size-row)" and notice["display"] == "flex" and "flex-wrap" not in notice
    assert outside["#notices .notice-text"]["flex"] == "1"
    assert outside["#notices:not(:empty)"]["display"] == "grid" and "width" not in outside["#notices:not(:empty)"]
    ui = {}
    for media, selector, body in blocks(read("pilot-ui.css")):
        assert not [one for one in media if "min-width" in one], selector
        ui.setdefault(" ".join(selector.split()), dict(declarations(body)))
    assert ui["#notices .notice-detail[open]"]["order"] == "1" and ui["#notices .notice:has(.notice-detail)"]["flex-wrap"] == "wrap"
    main = outside["#main:not(.hidden)"]
    assert main["grid-template-rows"] == "var(--size-bar) auto minmax(0, 1fr)" and "grid-template-columns" not in main


NOTICE_FOCUS = r"""
  const notices = [];
  const log = [];
  const button = (name) => ({ focus: () => log.push(name) });
  const make = (name) => ({ node: { name, inside: false, contains() { return this.inside; },
    querySelector: (sel) => (sel === '[data-act="dismiss"]' ? button(`${name} dismiss`) : null), remove() { log.push(`${name} removed`); } } });
  const document = { activeElement: null };
  const $ = (id) => ({ focus: () => log.push(`${id}.focus`), append() {} });
  function outlineRefused() {}
"""


def test_dismissing_a_focused_notice_moves_focus_to_the_next_then_the_previous_then_the_page(tmp_path):
    """P273: a notice holding focus, when dismissed, hands it to the next
    notice's dismiss, else the previous one's, else #page - so the panel
    collapsing never drops focus to the window; a notice not holding focus
    moves nothing."""
    ran = run_shell(["noticeFocusAfter", "dismissNotice"], NOTICE_FOCUS, """
      const out = {};
      const [a, b, c] = [make("a"), make("b"), make("c")];
      notices.push(a, b, c);
      b.node.inside = true; document.activeElement = {}; dismissNotice(b);
      out.middle = [...log]; log.length = 0;
      c.node.inside = true; dismissNotice(c);
      out.last = [...log]; log.length = 0;
      a.node.inside = true; dismissNotice(a);
      out.only = [...log]; log.length = 0;
      const [d, e] = [make("d"), make("e")];
      notices.push(d, e); dismissNotice(d);
      out.elsewhere = [...log];
      return out;
    """, tmp_path, "app.js")
    assert ran == {"middle": ["c dismiss", "b removed"], "last": ["a dismiss", "c removed"], "only": ["page.focus", "a removed"],
                   "elsewhere": ["d removed"]}


F6_FAKES = r"""
  const log = [];
  let shown = true;
  const item = (name, region) => ({ name, closest(sel) { return sel === `#${region}` ? this : null; }, focus() { log.push(name); document.activeElement = this; } });
  const things = { side: item("side item", "side"), bar: item("path", "bar"), notice: item("notice control", "notices"), page: item("page", "page") };
  const $ = (id) => (id === "notices" ? { childElementCount: shown ? 1 : 0, querySelector: () => (shown ? { querySelector: () => things.notice } : null) }
    : id === "find" ? { disabled: false, focus: () => log.push("find") } : id === "side" ? things.side : things.page);
  const document = { activeElement: null, querySelector: (sel) => (sel.startsWith("#crumb-list") ? things.bar : sel.includes("aria-current") ? things.side : null) };
  const tipKey = () => {};
  const press = (shift) => { shellKey({ key: "F6", shiftKey: shift, preventDefault() {}, target: document.activeElement }); };
"""


def test_f6_visits_the_notices_between_the_path_row_and_the_page_only_while_one_shows(tmp_path):
    """P273: F6 cycles side panel, path row, notices, page - the notices only
    while #notices holds one - and Shift+F6 the other way; focusRegion puts
    focus on the first notice's first control; the order is the markup's."""
    ran = run_shell(["regionOf", "f6Regions", "focusRegion", "shellKey"], lift_line("const F6_REGIONS = ", "shell.js") + F6_FAKES, """
      const out = {};
      const cycle = (shift) => { log.length = 0; document.activeElement = things.side; for (let i = 0; i < 4; i += 1) press(shift); return [...log]; };
      out.forward = cycle(false);
      out.backward = cycle(true);
      shown = false;
      out.noneForward = cycle(false);
      out.noneBackward = cycle(true);
      return out;
    """, tmp_path)
    assert ran["forward"] == ["path", "notice control", "page", "side item"]
    assert ran["backward"] == ["page", "notice control", "path", "side item"]
    assert ran["noneForward"] == ["path", "page", "side item", "path"]
    assert ran["noneBackward"] == ["page", "path", "side item", "page"]
    assert 'const F6_REGIONS = ["side", "bar", "notices", "page"];' in stripped_js("shell.js")
    assert '"summary, .notice-act:not(:disabled)"' in js_function("focusRegion"), "the Details summary, else the action, else the dismiss"


def test_a_toast_sits_left_of_the_notices_panel_while_it_shows():
    """P273: while the panel shows (at 1388px and wider) a toast is 24px left
    of it, at the bottom right of the page, and never covers a notice; with no
    panel, and stacked, it is where it was (bottom right of the window)."""
    rules = _panel_rules()
    assert rules["body:has(#notices:not(:empty)) #toast"] == {"inset-inline-end": "calc(var(--size-notices) + var(--sp-6))"}
    toast = {prop: value for media, selector, body in blocks(read("style.css")) if selector.strip() == ".toast" for prop, value in declarations(body)}
    assert toast["right"] == "22px" and toast["bottom"] == "22px" and toast["position"] == "fixed"


def test_escape_never_dismisses_a_notice():
    """P273: failures and warnings stay until a person dismisses them
    (decision 193); Esc keeps SPEC-shell 4.3's order (sheet, search list,
    tooltip) and names no notice function."""
    text = js_function("shellKey")
    escape = text[text.index('e.key === "Escape"'):]
    escape = escape[:escape.index("\n  }\n") + 5]
    assert "otice" not in escape and "dismiss" not in escape.lower()
    assert "otice" not in text


# ── L4: the household page, a card beside the returns (P275) ────────────────

#: A made-up household for the card's probes: a contact, two members, a saved
#: link (a made-up token, never a URL) and returns in two years.
CARD_HOUSEHOLD = r"""
  const LINK = "LINKTOKEN-share-me";
  const hh = { name: "Alpha", path: "c/Alpha", contact: "A Person", members: ["A Person", "Another"], link: LINK,
               returns: [{ path: "r/1040 - Alpha", year: 2025, return_name: "1040 - Alpha", form: "1040", active: true },
                         { path: "r/old", year: 2024, return_name: "1040 - Alpha", form: "1040", active: true }] };
  shellHousehold = () => hh;
  shellRoute = { level: "household", household: "c/Alpha" };
  lastState = { household: { path: "c/Alpha", shared_on: "2026-02-01" } };
  const cls = (n) => n.className.split(" ")[0];
  const facts = (page) => page.byClass("card-fact").map((f) => [f.kids[0].textContent, f.kids.slice(1).map((k) => k.textContent)]);
"""


def test_the_household_page_is_its_h1_then_the_card_and_the_returns_list(tmp_path):
    """P275: pagesHousehold is [H1, .household-body]; the body holds the card
    first (read first, in both forms) and then .returns-list with one group
    per year, newest first."""
    ran = run_lists(CARD_HOUSEHOLD + """
      const page = pagesHousehold(shellRoute);
      const layout = page[1].kids[0];
      return { top: page.map(cls), body: page[1].kids.map(cls), layout: layout.kids.map(cls),
               years: layout.kids[1].byClass("group-title").map((t) => t.textContent), h1: page[0].tag };
    """, tmp_path)
    assert ran == {"top": ["page-title", "household-body"], "body": ["household-layout"], "layout": ["household-card", "returns-list"],
                   "years": ["2025", "2024"], "h1": "h1"}


def test_the_card_says_contact_shared_with_and_whether_the_inbox_link_is_saved(tmp_path):
    """P275: Contact (when there is one), Shared With (the members, then Shared
    or Not Shared when the household's state is on screen) and Inbox Link
    (Saved, or Not Saved), each left out when there is nothing to say - the
    Inbox Link never."""
    ran = run_lists(CARD_HOUSEHOLD + """
      const draw = () => pagesHousehold(shellRoute)[1];
      const full = facts(draw());
      lastState = { household: { path: "c/Alpha", shared_on: "" } };
      const notShared = facts(draw());
      lastState = null; hh.contact = ""; hh.link = "";
      const quiet = facts(draw());
      hh.members = [];
      const bare = facts(draw());
      lastState = { household: { path: "c/Alpha", shared_on: "2026-02-01" } };
      const stateOnly = facts(draw());
      lastState = { household: { path: "elsewhere", shared_on: "2026-02-01" } };
      const otherHousehold = facts(draw());
      return { full, notShared, quiet, bare, stateOnly, otherHousehold };
    """, tmp_path)
    assert ran["full"] == [["Contact", ["A Person"]], ["Shared With", ["A Person, Another", "Shared"]], ["Inbox Link", ["Saved"]]]
    assert ran["notShared"][1] == ["Shared With", ["A Person, Another", "Not Shared"]]
    assert ran["quiet"] == [["Shared With", ["A Person, Another"]], ["Inbox Link", ["Not Saved"]]], "no contact, no state: those lines are left out"
    assert ran["bare"] == [["Inbox Link", ["Not Saved"]]], "the Inbox Link is always there"
    assert ran["stateOnly"] == [["Shared With", ["Shared"]], ["Inbox Link", ["Not Saved"]]], "the state line alone when there are no members"
    assert ran["otherHousehold"] == [["Inbox Link", ["Not Saved"]]], "another household's state is never this one's"


def test_the_card_never_draws_the_inbox_link_itself(tmp_path):
    """P275 (J3): the link is the client's share link, which the letter
    carries; an app that opened it would reach the network. The card says
    only whether it is saved: the link's text is in no text, attribute,
    dataset or tooltip of the page."""
    ran = run_lists(CARD_HOUSEHOLD + """
      const page = pagesHousehold(shellRoute);
      const all = [page[0], ...page[1].find(() => true)];
      const seen = JSON.stringify([page.map((n) => n.textContent), all.map((n) => [n.attrs, n.dataset, n.className]), tips, opened, went]);
      return { leaked: seen.includes(LINK), saved: facts(page[1]).pop() };
    """, tmp_path)
    assert ran == {"leaked": False, "saved": ["Inbox Link", ["Saved"]]}
    text = stripped_js("pages.js")
    body = text[text.index("function pagesHouseholdCard("):text.index("\n}\n", text.index("function pagesHouseholdCard(")) + 3]
    assert "hh.link ?" in body and "openPath" not in body and "href" not in body


def test_more_actions_on_the_card_opens_the_household_menu_with_the_h1s_token(tmp_path):
    """P275: the card's More Actions button opens the household's native menu
    at its bottom-left through the token the H1's own right-click uses
    (crumb-household), so it acts on the page's household with the page's
    enable rules; a right-click anywhere on the card does the same at the
    pointer. Name, tooltip and menu-ness are the vocabulary's."""
    ran = run_lists(CARD_HOUSEHOLD + """
      const card = pagesHousehold(shellRoute)[1].byClass("household-card")[0];
      const button = card.byClass("card-more")[0];
      button.handlers.click[0]({});
      card.handlers.contextmenu[0]({ preventDefault() {}, clientX: 70, clientY: 80 });
      const h1 = pagesHousehold(shellRoute)[0];
      h1.handlers.contextmenu[0]({ preventDefault() {}, clientX: 5, clientY: 6 });
      return { popups, label: button.attrs["aria-label"], popup: button.attrs["aria-haspopup"], tip: [...new Set(tips.filter(([c]) => c.includes("card-more")).map(([, w]) => w))],
               inCard: card.kids.indexOf(button) !== -1 };
    """, tmp_path)
    assert ran["popups"] == [["household", "crumb-household", 10, 20, None], ["household", "crumb-household", 70, 80, None],
                             ["household", "crumb-household", 5, 6, None]], "the card's two ways and the H1's own use one token"
    assert ran["label"] == "More Actions" and ran["popup"] == "menu" and ran["tip"] == ["More Actions"] and ran["inCard"]


def test_a_household_and_a_year_row_put_the_status_right_after_the_name(tmp_path):
    """P275: the household's and the year's rows are name, status, detail, end
    in the markup (so the accessible name reads in the order the eye does);
    statusNext comes only from pagesReturnSpecs, so the firm lists' rows
    (name, detail, status, end; year, name, form, status, end) are unchanged."""
    ran = run_lists(CARD_HOUSEHOLD + """
      const lists = (n) => (n.className && n.className.split(" ").includes("returns-list") ? [n] : n.byClass ? n.byClass("returns-list") : []);
      const order = (nodes) => nodes.flatMap(lists).flatMap((l) => l.byClass("row")).map((r) => r.kids.map(cls));
      const household = order(pagesHousehold(shellRoute));
      const year = order(pagesYear({ level: "year", household: "c/Alpha", year: 2025 }));
      const specs = pagesReturnSpecs(hh.returns).map((s) => s.statusNext);
      const overview = draw("overview").byClass("row")[0].kids.map(cls);
      const review = draw("needs-review").byClass("row")[0].kids.map(cls);
      return { household, year, specs, overview, review, firm: pagesWorkRows(shellFirmData.returns).map((s) => s.statusNext) };
    """, tmp_path)
    cells = ["row-name", "row-status", "row-detail", "row-end"]
    assert ran["household"] == [cells, cells] and ran["year"] == [cells] and ran["specs"] == [True, True]
    assert ran["overview"] == ["row-year", "row-name", "row-form", "row-status", "row-end"]
    assert ran["review"] == ["row-name", "row-detail", "row-status", "row-end"]
    assert not any(ran["firm"]), "the firm lists' rows keep their order"


def test_the_card_sits_beside_the_returns_at_1056px_of_page_and_above_them_below():
    """P275: the page's own width decides, through a container query on
    .household-body: 1056 is the list's least width (32 + 224 + 160 + 96 + 144,
    three 16px gaps, 32 of the row's own right padding: 736) plus the card
    (288) plus the card's right margin (32). A 1100px window's page is 860 and
    a 1400px window's is 1160 - 872 while the notices panel shows - so only
    the second, without a panel, has it beside."""
    light, _dark = root_blocks()

    def px(name: str) -> int:
        return int(light[name].strip().removesuffix("px"))

    least = px("--sp-8") + sum(px(f"--size-col-{cell}") for cell in ("name", "status", "form", "end")) + 3 * px("--sp-4") + px("--sp-8")
    assert least == 736 and px("--size-card") == 288
    assert least + px("--size-card") + px("--sp-8") == 1056
    page = lambda window, panel: window - px("--size-side") - (px("--size-notices") if panel else 0)  # noqa: E731
    assert [page(1100, False), page(1400, False), page(1400, True)] == [860, 1160, 872]
    assert [width >= 1056 for width in (page(1100, False), page(1400, False), page(1400, True))] == [False, True, False]
    rules = {}
    for media, selector, body in blocks(read("shell.css")):
        rules[(media, " ".join(selector.split()))] = dict(declarations(body))
    inside = ("@container (min-width: 1056px)",)
    assert rules[(inside, ".household-layout:not(.hidden)")] == {"grid-template-columns": "minmax(0, 1fr) calc(var(--size-card) + var(--sp-8))", "align-items": "start"}
    assert rules[(inside, ".returns-list")] == {"grid-column": "1", "grid-row": "1"}
    assert rules[(inside, ".household-card:not(.hidden)")] == {"grid-column": "2", "grid-row": "1", "margin": "var(--sp-6) var(--sp-8) 0 0"}
    assert rules[(inside, ".card-facts:not(.hidden)")] == {"grid-template-columns": "minmax(0, 1fr)"}
    assert rules[((), ".household-body")] == {"container-type": "inline-size"}
    assert rules[((), ".household-layout:not(.hidden)")] == {"display": "grid", "grid-template-columns": "minmax(0, 1fr)"}
    stacked = rules[((), ".card-facts:not(.hidden)")]
    assert stacked["grid-template-columns"] == "repeat(3, minmax(0, 1fr))" and stacked["padding-inline-end"] == "var(--sp-6)"
    row = rules[((), ".returns-list .row:not(.hidden)")]["grid-template-columns"]
    assert row == "var(--size-col-name) var(--size-col-status) minmax(var(--size-col-form), 1fr) var(--size-col-end)"
    assert "var(--size-col-detail)" not in rules[((), ".returns-list .rows")]["min-width"]
    card = rules[((), ".household-card:not(.hidden)")]
    assert card["background"] == "var(--bg-raised)" and card["border"] == "1px solid var(--border)" and card["margin"] == "var(--sp-6) var(--sp-8) 0"
    assert ".household-card" in read("shell.css")[read("shell.css").index("@media (forced-colors: active)"):]


def test_a_household_with_no_returns_keeps_add_a_return_beside_the_card(tmp_path):
    """P275: with no returns the returns list holds the empty line and the
    Add a Return button (as before) and the card is still beside or above it."""
    ran = run_lists(CARD_HOUSEHOLD + """
      hh.returns = [];
      const added = []; openAddReturn = (one) => added.push(one.name);
      vocab.menu = { add_return: "Add a Return" };
      const page = pagesHousehold(shellRoute);
      const layout = page[1].kids[0];
      const button = layout.byClass("btn")[0];
      button.handlers.click[0]({});
      return { layout: layout.kids.map(cls), line: layout.byClass("page-empty-line")[0].textContent, button: button.textContent, added };
    """, tmp_path, extra="let openAddReturn = () => {};")
    assert ran == {"layout": ["household-card", "returns-list"], "line": "No Returns Yet", "button": "Add a Return", "added": ["Alpha"]}


def test_the_card_words_are_the_vocabularys(tmp_path):
    """P275: every word the card shows is the vocabulary's - household_card's
    five, screen.shared and not_shared, and icons.more_actions - and a block
    the vocabulary lacks is a loud failure: the card is named in a notice and
    the returns are still drawn."""
    ran = run_lists(CARD_HOUSEHOLD + """
      Object.assign(vocab.screen, { shared: "SHARED-W", not_shared: "NOTSHARED-W", icons: { more_actions: "MORE-W", remove_filter: "x" },
        household_card: { contact: "CONTACT-W", shared_with: "WITH-W", inbox_link: "LINK-W", link_saved: "SAVED-W", no_link: "NOLINK-W" } });
      const words = (page) => page.flatMap((n) => [n, ...n.find(() => true)]).map((n) => n.attrs && n.attrs["aria-label"]).filter(Boolean);
      const page = pagesHousehold(shellRoute);
      const card = page[1].byClass("household-card")[0];
      const said = card.find(() => true).filter((n) => !n.kids.some((k) => k.tag)).map((n) => n.textContent).filter(Boolean);
      const label = words([card]);
      delete vocab.screen.household_card; pagesBroken = [];
      const without = pagesHousehold(shellRoute);
      return { said, label, layout: without[1].kids[0].kids.map(cls), years: without[1].byClass("group-title").map((t) => t.textContent), broken: pagesBroken.map((b) => [b.name, String(b.err.message)]) };
    """, tmp_path)
    assert ran["said"] == ["CONTACT-W", "A Person", "WITH-W", "A Person, Another", "SHARED-W", "LINK-W", "SAVED-W"]
    assert ran["label"] == ["MORE-W"]
    assert ran["layout"] == ["returns-list"] and ran["years"] == ["2025", "2024"]
    assert ran["broken"] == [["Alpha", "vocab.screen.household_card"]]
    text = stripped_js("pages.js")
    for word in ("Shared With", "Inbox Link", "Not Saved", "Contact"):
        assert f'"{word}"' not in text, word



# ── P279 (SPEC-ui-menu-speed §2): long lists draw only the rows in view ───


def test_the_window_holds_the_rows_in_view_and_one_screen_either_side(tmp_path):
    """P279: pagesWindow answers the items the view meets and `over` either
    side, clamped to the list; a list with no rows, or far from the view,
    answers an empty window. The distance either side is a viewport's rows,
    at least fifteen."""
    ran = run_pages(["pagesWindow", "pagesOver"], lift_line("const PAGES_VIRTUAL_OVER_LEAST = ", "pages.js"), """
      const w = (count, listTop, viewTop) => pagesWindow(count, 40, listTop, viewTop, 800, 20);
      return { top: w(1000, 100, 0), middle: w(1000, 100, 20000), end: w(1000, 100, 39300), empty: w(0, 100, 0),
               half_above: w(1000, -400, 0), far_below: w(1000, 5000, 0), just_below: w(1000, 1000, 0), no_height: pagesWindow(1000, 0, 100, 0, 800, 20),
               over: [pagesOver(800, 40), pagesOver(300, 40), pagesOver(800, 0)] };
    """, tmp_path)
    assert ran["top"] == {"first": 0, "last": 37}
    assert ran["middle"] == {"first": 477, "last": 537}
    assert ran["end"] == {"first": 960, "last": 999}, "clamped to the last row"
    assert ran["empty"] == {"first": 0, "last": -1} and ran["no_height"] == {"first": 0, "last": -1}
    assert ran["half_above"] == {"first": 0, "last": 49}, "a list half above the view draws from its first row"
    assert ran["far_below"] == {"first": 0, "last": -1}, "a list a long way below draws nothing"
    assert ran["just_below"] == {"first": 0, "last": 14}, "one just below the view draws the rows a screen away"
    assert ran["over"] == [20, 15, 15]


def test_a_list_of_one_hundred_rows_is_drawn_whole_and_may_wrap(tmp_path):
    """P279, Jason's question A: only a list of more than 100 rows is
    virtual. At 100 every row is in the document at once and a return's
    name may wrap (rulings 21, 27); at 101 the list is virtual and its
    rows are registered, not drawn, until the page measures them."""
    ran = run_pages_dom("""
      const year = (n) => {
        const hh = { name: "Smith Family", returns: Array.from({ length: n }, (_, i) => ({ path: `r${i}`, year: 2025, return_name: `1040 - Person ${i}`, active: true })) };
        shellHousehold = () => hh;
        pagesUid = 0; pagesTokens.clear();
        const list = pagesYear({ level: "year", household: "h1", year: 2025 })[2].kids[0];
        return { virtual: list.className.includes("is-virtual"), drawn: list.byClass("row").length, wrapped: list.byClass("row-wrap").length, registered: pagesTokens.size };
      };
      globalThis.shellRoute = { household: "h1" };
      return { hundred: year(100), more: year(101) };
    """, tmp_path, setup="const shellFirm = () => ({ data: null });")
    assert ran["hundred"] == {"virtual": False, "drawn": 100, "wrapped": 100, "registered": 100}
    assert ran["more"] == {"virtual": True, "drawn": 0, "wrapped": 0, "registered": 101}


def test_a_long_list_draws_only_its_window_and_registers_every_row(tmp_path):
    """P279: a return group of 1,000 files registers every row (the menus,
    Shift+F10 and the sheet's next arrow read pagesTokens), makes only the
    nodes of the window, and the next arrow still walks every Check step in
    the order drawn."""
    ran = run_long("""
      const list = draw(parkedFiles(1000));
      const steps = pagesFiles();
      return { registered: pagesTokens.size, drawn: list.kids.length, items: list.pagesModel.items.length, height: list.style.props.height,
               first: list.kids[0].style.props.top, last: list.kids.at(-1).style.props.top, names: steps.map((s) => s.name),
               tokens: [...pagesTokens.keys()].slice(0, 2), ids: list.pagesModel.ids.slice(0, 2) };
    """, tmp_path)
    assert ran["registered"] == 1000 and ran["items"] == 1000
    assert ran["drawn"] == 38, "the rows in view and one screen either side (over = 20)"
    assert ran["height"] == "40000px" and ran["first"] == "0px" and ran["last"] == "1480px"
    assert ran["names"] == [f"f{i:04d}.pdf" for i in range(1, 1001)], "the next arrow walks every file, drawn or not, in order"
    assert ran["tokens"] == ran["ids"], "a row's id is assigned when the page is drawn"


def test_the_active_row_stays_in_the_document_when_scrolled_out_of_the_window(tmp_path):
    """P279: the active row is pinned, so aria-activedescendant always names
    a node in the document; the rows around it are not."""
    ran = run_long("""
      const list = draw(parkedFiles(1000));
      const model = list.pagesModel;
      pagesActivateAt(list, 5);
      scrollTo(30000);
      const ids = list.kids.map((k) => k.attrs.id);
      const pinned = list.kids.find((k) => k.attrs.id === model.ids[5]);
      return { drawn: list.kids.length, pinned: Boolean(pinned), selected: pinned && pinned.attrs["aria-selected"], active: pinned && pinned.className.includes("is-active"),
               named: list.attrs["aria-activedescendant"] === model.ids[5], neighbours: [4, 6].map((i) => ids.includes(model.ids[i])), top: ids.includes(model.ids[0]),
               at: model.nodes.has(model.slot[750]) };
    """, tmp_path)
    assert ran["pinned"] and ran["selected"] == "true" and ran["active"] and ran["named"]
    assert ran["drawn"] == 62 and ran["neighbours"] == [False, False] and not ran["top"] and ran["at"], "the window (61 rows) and the active row, no more"


def test_every_drawn_row_says_its_place_and_the_lists_size(tmp_path):
    """P279: each drawn row carries aria-posinset (from 1) and aria-setsize,
    and a row under a sub-heading says that sub-heading's words first, so it
    holds when the sub-heading is not drawn; a sub-heading is a presentation
    slot of its own."""
    ran = run_long("""
      const list = draw([...parkedFiles(150), ...Array.from({ length: 5 }, (_, i) => parked(`z${i}`, { bucket: "container", code: "opened-not-across" }))]);
      const rows = (box) => box.kids.filter((k) => k.className.split(" ").includes("row"));
      const top = rows(list).map((r) => [r.attrs["aria-posinset"], r.attrs["aria-setsize"]]);
      scrollTo(5540);   // the end: the list is 156 slots of 40px, 100px down, in an 800px view
      const heads = list.kids.filter((k) => k.className.includes("group-sub"));
      const under = rows(list).filter((r) => r.attrs["aria-description"].startsWith("Emails and zips"));
      return { top: top.slice(0, 3), topSize: [...new Set(top.map((p) => p[1]))], pos: rows(list).map((r) => Number(r.attrs["aria-posinset"])),
               heads: heads.map((h) => [h.textContent, h.attrs.role, h.style.props.height]), under: under.length, last: rows(list).at(-1).attrs["aria-posinset"] };
    """, tmp_path)
    assert ran["top"] == [["1", "155"], ["2", "155"], ["3", "155"]] and ran["topSize"] == ["155"]
    assert ran["pos"] == sorted(ran["pos"]) and ran["last"] == "155"
    assert ran["heads"] == [["Emails and zips", "presentation", "40px"]]
    assert ran["under"] == 5


def test_the_keys_move_through_rows_not_yet_drawn_and_draw_them(tmp_path):
    """P279: End on 1,000 rows makes the last active and draws it, with the
    page scrolled just far enough that it is whole in view; Home, the arrows
    and PageDown (a screen less one row, from H) move the active index, and
    PageUp does not go past the first."""
    ran = run_long("""
      const list = draw(parkedFiles(1000));
      const model = list.pagesModel;
      const press = (key) => { const e = { key, target: { closest: () => list }, preventDefault() {} }; return pagesKey(e); };
      const where = () => ({ active: model.active, drawn: list.kids.some((k) => k.attrs.id === model.ids[model.active]), scroll: pageBox.scrollTop });
      const out = {};
      pagesActivateAt(list, 0);
      out.end = (press("End"), where());
      out.home = (press("Home"), where());
      out.down = (press("ArrowDown"), where());
      out.pagedown = (press("PageDown"), where());
      out.pageup = (press("PageUp"), press("PageUp"), press("PageUp"), where());
      out.handled = press("x");
      return out;
    """, tmp_path)
    assert ran["end"] == {"active": 999, "drawn": True, "scroll": 39300}
    assert ran["home"]["active"] == 0 and ran["home"]["drawn"] and ran["home"]["scroll"] == 100, "the first row's top just inside the view"
    assert ran["down"]["active"] == 1 and ran["pagedown"]["active"] == 20, "a screen of 20 rows less one is 19"
    assert ran["pageup"]["active"] == 0 and ran["pageup"]["drawn"]
    assert ran["handled"] is False


def test_the_row_height_is_a_drawn_rows_own_and_a_list_not_laid_out_is_loud(tmp_path):
    """P279: the height H is read from a drawn row (40, then 32 when the
    density changes and the page measures again); every row sits at i x H
    and the list is as tall as the whole of it; a row that measures nothing
    is a list that was not laid out, a failure, never a guessed height."""
    ran = run_long("""
      const list = draw(parkedFiles(150));
      const model = list.pagesModel;
      const at40 = { H: model.H, height: list.style.props.height, tops: list.kids.slice(0, 3).map((k) => k.style.props.top) };
      H = 32; pagesVirtualMeasure(pageBox);
      const at32 = { H: model.H, height: list.style.props.height, tops: list.kids.slice(0, 3).map((k) => k.style.props.top) };
      H = 0; let said = "";
      try { pagesVirtualMeasure(pageBox); } catch (err) { said = err.message; }
      return { at40, at32, said };
    """, tmp_path)
    assert ran["at40"] == {"H": 40, "height": "6000px", "tops": ["0px", "40px", "80px"]}
    assert ran["at32"] == {"H": 32, "height": "4800px", "tops": ["0px", "32px", "64px"]}
    assert ran["said"] == "row_height"
    assert not re.search(r"\b(?:40|32)\b", re.sub(r"//[^\n]*", "", js_function("pagesVirtualSize", "pages.js"))), "no density is typed in the virtualizer"


def test_a_redraw_restores_the_active_row_by_its_place_in_the_list(tmp_path):
    """P279: pagesWhere names the active row by its index in the model, and
    after the page is drawn again pagesRestore makes that row active, draws
    it and brings it into view - not the row at that place among the drawn
    nodes."""
    ran = run_long("""
      let list = draw(parkedFiles(1000));
      pagesActivateAt(list, 500);
      list.closest = (sel) => (sel === '[role="listbox"]' ? list : null);
      pageBox.contains = () => true;
      document.activeElement = list;
      const where = pagesWhere(pageBox);
      const first = { scroll: pageBox.scrollTop, row: where.row };
      list = draw(parkedFiles(1000));
      const before = { active: list.pagesModel.active, scroll: pageBox.scrollTop };
      pagesFocus = where;
      pagesRestore(pageBox);
      const model = list.pagesModel;
      const node = list.kids.find((k) => k.attrs.id === model.ids[500]);
      return { first, before, active: model.active, drawn: Boolean(node), is: node && node.className.includes("is-active"), scroll: pageBox.scrollTop, cleared: pagesFocus };
    """, tmp_path)
    assert ran["first"] == {"scroll": 19340, "row": 500}
    assert ran["before"] == {"active": -1, "scroll": 0}
    assert ran["active"] == 500 and ran["drawn"] and ran["is"] and ran["scroll"] == 19340 and ran["cleared"] is None


def test_a_row_that_cannot_be_made_on_scroll_is_said_not_skipped(tmp_path):
    """P279: a row whose spec was built but whose node cannot be (here the
    vocabulary lacks the words a status stands for) draws an empty row of
    the same height and is named by the page's notice once - drawing it
    again when it scrolls back adds no second notice."""
    ran = run_long("""
      vocab.reason_tips = null;
      const list = draw(parkedFiles(1000));
      const empty = () => list.kids.filter((k) => k.kids.length === 0).length;
      const said = () => notices.at(-1)[1].length;
      const first = { drawn: list.kids.length, empty: empty(), said: said(), named: notices.at(-1)[1][0][1] };
      scrollTo(20000);
      const away = said();
      scrollTo(0);
      return { first, away, back: said(), failures: failures.length };
    """, tmp_path)
    assert ran["first"]["drawn"] == 38 and ran["first"]["empty"] == 38, "an empty row in each place, never a gap"
    assert ran["first"]["said"] == 38 and "f0001.pdf" in ran["first"]["named"]
    assert ran["away"] == 99 and ran["back"] == 99, "the 38 rows, then the 61 of the other window; the 38 again add none"
    assert ran["failures"] == 0


def test_the_editor_keeps_the_focused_row_and_widens_its_window_at_either_edge(tmp_path):
    """P279: the editor's window is the rows the view meets and a viewport
    either side, widened to the row holding focus and to the pins a focus at
    the first or last drawn row sets (`over` rows that way), so Tab and
    Shift+Tab walk every row's inputs in order."""
    ran = run_shell(["editorSpan", "editorPins"], "", """
      const tops = Array.from({ length: 300 }, (_, i) => i * 40);
      const span = (rel, held = -1, first = Infinity, last = -1) => editorSpan(tops, rel, 800, first, last, held);
      const none = { first: Infinity, last: -1 };
      return { top: span(0), middle: span(4000), held_above: span(4000, 5), held_below: span(4000, 299), pinned: span(4000, -1, 60, 200),
               past_the_end: span(20000), empty: editorSpan([], 0, 800, Infinity, -1, -1),
               at_first: editorPins(80, 80, 139, 15, 300, none), at_last: editorPins(139, 80, 139, 15, 300, none), between: editorPins(100, 80, 139, 15, 300, none),
               at_the_very_first: editorPins(0, 0, 40, 15, 300, none), at_the_end: editorPins(299, 260, 299, 15, 300, { first: 5, last: -1 }),
               near: editorPins(10, 0, 39, 15, 300, { first: 0, last: 20 }), far: editorPins(100, 0, 139, 15, 300, { first: 0, last: 154 }),
               just_far: editorPins(16, 0, 39, 15, 300, { first: 0, last: -1 }), reveal_kept: editorPins(100, 60, 139, 15, 300, { first: 85, last: 115 }),
               walked_on: editorPins(139, 80, 139, 15, 300, { first: 65, last: -1 }) };
    """, tmp_path, "app.js")
    assert ran["top"] == {"first": 0, "last": 39}
    assert ran["middle"] == {"first": 80, "last": 139}
    assert ran["held_above"] == {"first": 5, "last": 139} and ran["held_below"] == {"first": 80, "last": 299}, "the row holding focus is never left out"
    assert ran["pinned"] == {"first": 60, "last": 200}
    assert ran["past_the_end"] == {"first": 299, "last": 299} and ran["empty"] == {"first": 0, "last": -1}
    assert ran["at_first"] == {"first": 65, "last": -1} and ran["at_last"] == {"first": None, "last": 154}, "Infinity does not survive JSON"
    assert ran["between"] == {"first": None, "last": -1}, "a focus inside the window widens nothing"
    assert ran["at_the_very_first"] == {"first": 0, "last": -1}
    assert ran["at_the_end"] == {"first": None, "last": 299}, "the pin left far behind at row 5 is dropped"
    assert ran["near"] == {"first": 0, "last": 20}, "within `over` rows of the focus a pin is kept"
    assert ran["far"] == {"first": None, "last": -1}, "a pin more than `over` rows from the focused row is dropped (a Tab walk keeps no pin behind it)"
    assert ran["just_far"] == {"first": None, "last": -1}, "16 rows from the pin at 0 with over = 15 drops it"
    assert ran["reveal_kept"] == {"first": 85, "last": 115}, "reveal's pins hold while the focus stays within `over` rows of them"
    assert ran["walked_on"] == {"first": None, "last": 154}, "the first pin left behind is dropped; the edge just reached is widened"


def test_a_value_typed_in_a_row_scrolled_out_of_the_editor_is_in_the_saved_list(tmp_path):
    """P279: every input of a row writes to its row object as it is typed (a
    pick the moment it is made), so a row taken out of the document holds
    nothing that is not in editorRows, which is what a save reads."""
    ran = run_shell(["cellInput"], r"""
      const el = (tag, attrs = {}, ...kids) => ({ tag, attrs, kids, handlers: {}, value: attrs.value, classList: { toggle() {} },
        addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); } });
      const vocab = { editor: { minimums: { expected_count: 1 }, maximums: {}, yes_no_fields: ["named"], yes: "yes", no: "no" },
                      overrides: { not_applicable: "Not Applicable" }, override_reasons: ["One"], override_reason_other: "Other" };
      let changes = 0;
    """, """
      const row = { document: "a", expected_count: 1, named: "yes", manual_override: "" };
      const text = cellInput(row, { key: "document", label: "Document" }, () => { changes += 1; });
      text.value = "typed words"; text.handlers.input[0]();
      const number = cellInput(row, { key: "expected_count", label: "Expected" }, () => { changes += 1; });
      number.value = "7"; number.handlers.input[0]();
      const pick = cellInput(row, { key: "named", label: "Named" }, () => { changes += 1; });
      pick.value = "no"; pick.handlers.change[0]();
      return { row, changes, saved: JSON.stringify([row]) };
    """, tmp_path, "app.js")
    assert ran["row"] == {"document": "typed words", "expected_count": "7", "named": "no", "manual_override": ""}
    assert ran["changes"] == 3 and "typed words" in ran["saved"]
    window = js_function("editorWindow", "app.js")
    assert "tbody.removeChild(tr)" in window and "cellInput(" not in window, "the window takes rows out of the document and draws them with the one row component"
    assert "editorRows" not in window, "and keeps nothing of the rows in a node: the save reads editorRows"


def test_focus_editor_row_reaches_a_row_not_drawn(tmp_path):
    """P279: focusEditorRow finds the row in the table's own rows, not among
    the nodes, and has the window draw, scroll to and focus it; a row in a
    shut fold is left alone, as it always was."""
    ran = run_shell(["focusEditorRow"], r"""
      const vocab = { triage: { identifier_separator: " - " } };
      const focused = []; const revealed = [];
      const box = (ids, fold) => ({ closest: () => fold, editorWindow: { rows: ids.map((identifier) => ({ identifier })),
        reveal: (i) => { revealed.push(i); return { querySelector: () => ({ focus: () => focused.push(ids[i]) }) }; } } });
      const boxes = [box(["R1", "R2", "R3"], null), box(["R9"], { open: false })];
      const holder = { querySelectorAll: (sel) => (sel === ".editor-rows" ? boxes : []) };
      const $ = () => holder;
    """, """
      focusEditorRow("R3");
      const drawn = { revealed: [...revealed], focused: [...focused] };
      focusEditorRow("R9");
      return { drawn, afterShut: { revealed, focused } };
    """, tmp_path, "app.js")
    assert ran["drawn"] == {"revealed": [2], "focused": ["R3"]}
    assert ran["afterShut"] == {"revealed": [2], "focused": ["R3"]}, "a row in a shut fold is not revealed"


def test_switching_density_measures_the_long_lists_again(tmp_path):
    """P279: the density moves every row's height, so the Compact Rows
    answer has the page measure its long lists again (P271 does not draw
    the page again), before the active row is brought into view."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      shellToggleCompact();
      shellToggleCompact();
      return { measured: said.measured };
    """, tmp_path)
    assert ran["measured"] == 2
    text = js_function("shellToggleCompact")
    assert text.index("pagesVirtualMeasureSaid($(\"page\"));") < text.index("row.scrollIntoView")


def test_a_density_switch_whose_measure_throws_still_ticks_the_menu_and_says_the_failure(tmp_path):
    """P279 (review 2-1, finding 2): the Compact Rows answer measures the long
    lists outside pagesDraw, so a measure that throws is the page's failure
    notice (decision 193) and the rest of the answer still runs - the active
    row is brought into view and the menu is told its tick."""
    ran = run_shell(COMPACT_FUNCTIONS, COMPACT_PANEL + store_functions(), """
      said.boom = true;
      shellToggleCompact();
      return { sent: said.sent, failed: said.failed, scrolled: said.scrolled.length, density: said.density, cls: classes.has("rows-compact") };
    """, tmp_path)
    assert ran["failed"] == ["row_height"], "the failure notice says it"
    assert ran["sent"] == [["show_under_construction", "compact_rows"]] and ran["scrolled"] == 1, "the menu's tick is sent and the active row is scrolled to"
    assert ran["cls"] is True and ran["density"] == 1


def test_a_measure_that_throws_outside_the_draw_leaves_no_list_naming_a_removed_row(tmp_path):
    """P279 (review 2-1, finding 2): a failed size has taken a list's rows out
    of the document, so the list names none of them (aria-activedescendant),
    and the failure is said - by the fold that opens and by the density."""
    ran = run_long("""
      const list = draw(parkedFiles(1000));
      pagesActivateAt(list, 5);
      const named = list.attrs["aria-activedescendant"];
      H = 0;
      pagesVirtualMeasureSaid(pageBox);
      return { named: Boolean(named), after: list.attrs["aria-activedescendant"] || null, drawn: list.kids.length, failures };
    """, tmp_path)
    assert ran["named"] and ran["after"] is None and ran["drawn"] == 0
    assert ran["failures"] == ["row_height"]
    assert "pagesVirtualMeasureSaid(fold)" in js_function("pagesGroup", "pages.js")


def test_a_row_reached_by_a_key_or_a_restore_that_cannot_be_made_is_named_once(tmp_path):
    """P279 (review 2-1, finding 1): End onto a single bad row raises one
    notice naming it, as a row reached by scrolling does, and a second End
    raises none; a restore onto the row says it once too."""
    ran = run_long("""
      const make = pagesRowNode;
      pagesRowNode = (spec, id, place) => { if (place && place.pos === 1000) throw new Error("bad_row"); return make(spec, id, place); };
      const press = (list, key) => pagesKey({ key, target: { closest: () => list }, preventDefault() {} });
      let list = draw(parkedFiles(1000));
      pagesActivateAt(list, 0);
      const base = notices.length;
      press(list, "End");
      const first = { added: notices.length - base, named: notices.at(-1)[1].map((n) => n[1]), active: list.pagesModel.active };
      press(list, "End");
      press(list, "Home");
      press(list, "End");
      const again = notices.length - base;
      list = draw(parkedFiles(1000));
      const mark = notices.length;
      pagesFocus = { at: 0, row: 999 };
      pagesRestore(pageBox);
      return { first, again, restored: { added: notices.length - mark, named: notices.at(-1)[1].map((n) => n[1]), active: list.pagesModel.active }, failures };
    """, tmp_path)
    assert ran["first"]["added"] == 1 and len(ran["first"]["named"]) == 1 and "f1000.pdf" in ran["first"]["named"][0]
    assert ran["first"]["active"] == 999
    assert ran["again"] == 1, "the same row reached again raises no second notice"
    assert ran["restored"]["added"] == 1 and "f1000.pdf" in ran["restored"]["named"][0] and ran["restored"]["active"] == 999
    assert ran["failures"] == []


def test_a_long_lists_return_and_household_names_keep_their_link_tooltip(tmp_path):
    """P279 (review 2-1, finding 5; P117's ruling O2, SPEC-shell 3.6): in a
    long list a return or household name that is a link ends in an ellipsis
    and keeps its "Navigate to ..." tooltip, cut or not; it takes no tooltip
    of the full name in its place."""
    ran = run_pages_dom("""
      const long = "1040 - Alexandria Montgomery-Whitfield & Christopher Delacroix Family Trust".padEnd(80, "y").slice(0, 80);
      const out = [];
      for (const kind of ["return", "household"]) {
        tips.length = 0;
        pagesRowNode({ name: long, detail: "", status: "", tone: "plain", date: "", menu: "return", nameLink: { kind, key: "k" } }, `x-${kind}`, { pos: 1, size: 120, sub: "" });
        out.push(tips.map(([cls, words]) => [cls, words]));
      }
      return out;
    """, tmp_path)
    assert ["row-link", "Navigate to Return"] in ran[0] and ["row-link", "Navigate to Household"] in ran[1]
    assert not [one for one in ran[0] + ran[1] if one[0] == "row-name"], "the link's tooltip stays; the name box takes none of its own"


# ── P278 (SPEC-ui-menu-speed §4): the engine pages the firm lists ──────────

def test_a_turn_asks_the_engine_for_the_page_with_the_view_and_keeps_the_held_rows_marked_updating(tmp_path):
    """SPEC 4.6: a page turn asks `firm` for that page of the same view - the token the held
    answer carries - and the page keeps the rows it holds, marked Updating (P222's marker),
    until the engine's page lands; then the marker goes, the page held is the new one and what
    waited for it (focus back on the button, the page's top) is done once."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: shellFirmMerge(null, pageOf("overview", 0)) };
      shellDraw();
      const before = looks();
      pagesPageAt.overview = 1;
      let landed = 0;
      shellTurnFirm("overview", () => { landed += 1; });
      const during = { ...looks(), payload: asked[0].payload, command: asked[0].args, turns: shellTurns, held: shellFirmNow.data.replies.overview.page.at, landed };
      await land(0, pageOf("overview", 1));
      return { before, during, after: { ...looks(), held: shellFirmNow.data.replies.overview.page.at, landed, turns: shellTurns, view: shellFirmNow.data.view, status: shellFirmNow.status } };
    """, tmp_path)
    assert said["before"]["busy"] == "false" and not said["before"]["updating"]
    during = said["during"]
    assert during["command"] == ["firm"] and during["payload"] == {"page": {"list": "overview", "at": 1, "order": None, "filter": {"tab": "all"}}, "view": "v1"}
    assert during["busy"] == "true" and during["updating"] and during["said"] == "Updating" and during["turns"] == 1
    assert during["rows"] == said["before"]["rows"] and during["held"] == 0 and during["landed"] == 0, "the held rows stay until the new page lands"
    after = said["after"]
    assert after["busy"] == "false" and not after["updating"] and after["said"] == "" and after["turns"] == 0
    assert after["held"] == 1 and after["landed"] == 1 and after["status"] == "ok" and after["view"] == "v1"


def test_a_header_a_tab_a_reason_card_or_a_client_type_asks_page_one_of_the_new_order(tmp_path):
    """SPEC 4.6: each of these changes what the list is, so the engine is asked for the list's
    first page - from what the window holds (the order kept on this PC, the tab, the card,
    the switch, the Client Type) - and the window sorts, filters and slices nothing itself."""
    ran = run_pages_dom("""
      pagesPageAt.overview = 2; pagesPageAt.needs_review = 3; pagesPageAt.clients = 1;
      pagesOrderBy("overview", "taxpayer");
      pagesOrderBy("overview", "taxpayer");
      pagesPick("overview", () => { pagesTab = "need"; }, "tab-need");
      pagesPick("needs_review", () => { pagesReasonPick = "unmatched"; }, "reason-unmatched");
      pagesPick("clients", () => { pagesClientsAll = true; }, "all");
      pagesPick("clients", () => { pagesClientType = "trusts"; }, "type");
      return asks;
    """, tmp_path, setup="const asks = []; const shellTurnFirm = (list, then) => asks.push({ list, ask: shellFirmAsk(list).page, then: typeof then });")
    assert [one["list"] for one in ran] == ["overview", "overview", "overview", "needs_review", "clients", "clients"]
    assert [one["ask"]["at"] for one in ran] == [0] * 6, "any change of order or filter starts again at page one (P174)"
    assert ran[0]["ask"]["order"] == {"cell": "taxpayer", "dir": 1} and ran[1]["ask"]["order"] == {"cell": "taxpayer", "dir": -1}
    assert ran[2]["ask"]["filter"] == {"tab": "need"} and ran[2]["ask"]["order"] == {"cell": "taxpayer", "dir": -1}
    assert ran[3]["ask"] == {"list": "needs_review", "at": 0, "order": None, "filter": {"reason": "unmatched"}}
    assert ran[4]["ask"]["filter"] == {"all": True, "type": ""} and ran[5]["ask"]["filter"] == {"all": True, "type": "trusts"}
    assert all(one["then"] == "function" for one in ran), "focus goes back to the control when the page lands"


def test_a_page_turn_counts_from_the_page_last_asked_for_and_a_late_page_is_the_last(tmp_path):
    ran = run_pages_dom("""
      shellFirmNow = { status: "ok", data: { replies: { overview: { page: { at: 4 } } } } };
      delete pagesPageAt.overview;                   // nothing asked yet: counted from the page drawn (4)
      pagesTurn("overview", 1, "next");              // asks 5; it has not landed
      pagesTurn("overview", -1, "previous");          // a quick Previous asks 4, the page it started from, not 3
      pagesTurn("overview", -1, "previous");          // and again: 3
      pagesTurn("overview", 1, "next");              // Next: 4
      delete pagesPageAt.overview; shellFirmNow.data.replies.overview.page.at = 0;
      pagesTurn("overview", -1, "previous");          // never below the first
      const adopted = {};
      globalThis.shellRoute = { level: "needs-review" };
      pagesReasonPick = "password"; pagesPageAt.needs_review = 9;
      pagesAdopt({ page: { list: "needs_review", at: 2, pages: 3, filter: { reason: "" }, counts: { reasons: [["unmatched", 4]] } } });
      adopted.nr = [pagesPageAt.needs_review, pagesReasonPick];
      pagesPageAt.needs_review = 1; pagesReasonPick = "unmatched";       // the person turned to page two meanwhile, on a card that is still there
      pagesAdopt({ page: { list: "needs_review", at: 0, pages: 3, filter: { reason: "unmatched" }, counts: { reasons: [["unmatched", 4]] } } });
      adopted.kept = [pagesPageAt.needs_review, pagesReasonPick];
      pagesPageAt.overview = 7; pagesAdopt({ page: { list: "overview", at: 1, pages: 2, filter: { tab: "all" }, counts: {} } });
      adopted.other = pagesPageAt.overview;
      return { asks, adopted };
    """, tmp_path, setup="""
      let shellFirmNow = { data: null }; const shellFirm = () => shellFirmNow; const asks = [];
      const shellTurnFirm = (list, then) => asks.push(shellFirmAsk(list).page.at);
    """)
    assert ran["asks"] == [5, 4, 3, 4, 0], "counted from the page last asked for (Next then a quick Previous asks the page it started from), else from the page drawn; never below the first"
    assert ran["adopted"] == {"nr": [2, ""], "kept": [1, "unmatched"], "other": 7}, (
        "a page past the end is the last; a card whose reason is gone is All; a choice made since is kept; a list left is not touched")


def test_a_refresh_asks_the_page_on_screen_without_a_view(tmp_path):
    """SPEC 4.6: every fresh trigger - launch, a Sort's end, F5, a write that moves a count - asks
    `firm` for the page on screen with no view, so the counts are read afresh; the early ask at
    launch and `firm-last` ask the Overview's."""
    said = run_firm_load("""
      shellRoute = { level: "needs-review" };
      pagesPageAt.needs_review = 1; pagesReasonPick = "unmatched";
      shellFirmNow = { status: "ok", data: shellFirmMerge(null, pageOf("needs_review", 1, "v1", { filter: { reason: "unmatched" } })) };
      shellLoadFirm();
      const refresh = asked[0].payload;
      await land(0, pageOf("needs_review", 1, "v2", { filter: { reason: "unmatched" } }));
      shellRoute = { level: "household", household: "h1" };
      shellLoadFirm();
      const household = asked[1].payload;
      return { refresh, household, view: shellFirmNow.data.view, turns: asked.length };
    """, tmp_path)
    assert said["refresh"] == {"page": {"list": "needs_review", "at": 1, "order": None, "filter": {"reason": "unmatched"}}}, "no view: the engine reads afresh"
    assert said["household"]["page"]["list"] == "overview" and "view" not in said["household"], "a page with no firm list asks the Overview"
    assert said["view"] == "v2" and said["turns"] == 2


def test_a_turn_during_a_fresh_load_follows_it_from_the_new_view(tmp_path):
    """SPEC 4.6: a turn while a fresh load is on its way waits for it and sends nothing; when the
    view lands, one turn follows from the new view if the page wanted is not the one it brought. A
    reply for a page no longer wanted is dropped (decision 193's way). The page refusal the engine
    marks is a notice without Retry, and the page wished for falls back to the page drawn; a failed
    turn keeps Retry and the wish, so Retry asks the same page."""
    said = run_firm_load("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: heldOf(1) };
      shellLoadFirm();                                 // F5: a fresh ask, no view
      pagesPageAt.overview = 1; let done = 0;
      shellTurnFirm("overview", () => { done += 1; });  // the person turns the page meanwhile
      const whileLoading = { asked: asked.length, turns: shellTurns };
      await land(0, pageOf("overview", 0, "v2"));       // the fresh view brings page one; page two is wanted
      const follow = { asked: asked.length, payload: asked[1].payload, turns: shellTurns, done };
      await land(1, pageOf("overview", 1, "v2"));
      const landed = { at: shellFirmNow.data.replies.overview.page.at, view: shellFirmNow.data.view, done, turns: shellTurns, status: shellFirmNow.status };

      // Two turns in a row: the first reply is for a page no longer wanted, and is dropped.
      pagesPageAt.overview = 2; shellTurnFirm("overview");
      pagesPageAt.overview = 0; shellTurnFirm("overview");
      await land(2, pageOf("overview", 2, "v2"));
      const dropped = shellFirmNow.data.replies.overview.page.at;
      await land(3, pageOf("overview", 0, "v2"));
      const second = shellFirmNow.data.replies.overview.page.at;

      // A fresh load that begins while a turn is on its way: the turn's reply is the old view's.
      pagesPageAt.overview = 1; shellTurnFirm("overview");
      shellLoadFirm();
      await land(4, pageOf("overview", 1, "v2"));
      const old = { view: shellFirmNow.data.view, status: shellFirmNow.status };
      await land(5, pageOf("overview", 1, "v3"));

      // The page refusal is a notice with its sentence and no Retry (the same ask would only be refused again), the page keeps what
      // it held, and the page wished for falls back to the one drawn (there is no Retry to keep it for).
      failedAs = [];
      const sentence = "The app asked for a list the engine does not have; nothing was read.";
      pagesPageAt.overview = 2; shellTurnFirm("overview");
      asked[6].resolve({ error: sentence, failure: { sentence, kind: "refused", seq: null, identifier: null, key: @KEY@ } });   // the engine's own envelope
      await tick();
      const refused = { said: failedAs.map((one) => one.sentence), retry: typeof failedAs[0].retry, at: shellFirmNow.data.replies.overview.page.at, turns: shellTurns, wish: pagesPageAt.overview };
      // A turn that failed (kind failed) still offers Retry, the wish stays, and Retry asks the same page again.
      failedAs = [];
      pagesPageAt.overview = 2; shellTurnFirm("overview");
      asked[7].resolve({ error: "Failed (OSError).", failure: { sentence: "Failed (OSError).", kind: "failed", seq: null, identifier: null } });
      await tick();
      const failedTurn = { retry: typeof failedAs[0].retry, wish: pagesPageAt.overview };
      failedAs[0].retry();
      return { whileLoading, follow, landed, dropped, second, old, refused, failedTurn, retried: asked[8].payload };
    """.replace("@KEY@", json.dumps(api.FIRM_PAGE_REFUSED_KEY)), tmp_path)
    assert said["whileLoading"] == {"asked": 1, "turns": 0}, "nothing is sent while the fresh load runs"
    assert said["follow"]["asked"] == 2 and said["follow"]["turns"] == 1 and said["follow"]["done"] == 0
    assert said["follow"]["payload"] == {"page": {"list": "overview", "at": 1, "order": None, "filter": {"tab": "all"}}, "view": "v2"}, "from the new view"
    assert said["landed"] == {"at": 1, "view": "v2", "done": 1, "turns": 0, "status": "ok"}
    assert said["dropped"] == 1 and said["second"] == 0, "only the page last wanted is drawn"
    assert said["old"] == {"view": "v2", "status": "loading"}, "the turn sent before the load began is the old view's: its reply is dropped"
    assert said["refused"] == {"said": ["The app asked for a list the engine does not have; nothing was read."], "retry": "undefined", "at": 1, "turns": 0,
                               "wish": 1}, "no Retry, and the wish falls back to the page drawn"
    assert said["failedTurn"] == {"retry": "function", "wish": 2}, "Retry, and the wish kept for it"
    assert said["retried"]["page"]["at"] == 2 and said["retried"]["view"] == "v3"


def test_a_turn_refused_for_another_reason_offers_retry_and_retry_asks_the_same_page(tmp_path):
    """P278 (review 4-2, finding 1): only the page refusal the engine marks (``key``
    ``firm_page_refused``) loses Retry. A turn refused for any other reason - here the engine's
    own PRACTICE_NOT_WALKED, a clients folder that cannot be walked just now - is one notice in
    the engine's words that the window's own ``retryOf`` gives Retry, as a fresh load's notice
    is, and the page wished for stays, so Retry asks it again."""
    said = run_firm_load("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: shellFirmMerge(null, pageOf("overview", 1)) };
      failedAs = []; noticedAs.length = 0;
      const sentence = @SENTENCE@;
      pagesPageAt.overview = 2; shellTurnFirm("overview");
      asked[0].resolve({ error: sentence, failure: { sentence, kind: "refused", seq: null, identifier: null } });   // the engine's own envelope, unmarked
      await tick();
      const said = [...noticedAs, ...failedAs];
      const offered = said.map((one) => typeof retryOf(one));
      const wish = pagesPageAt.overview; const turns = shellTurns;
      const again = retryOf(said[0]);
      if (again) again();
      return { said: said.map((one) => one.sentence), offered, wish, turns, retried: asked.length > 1 ? asked[1].payload : null };
    """.replace("@SENTENCE@", json.dumps(api.PRACTICE_NOT_WALKED)), tmp_path, functions=("retryOf",))
    assert said["said"] == [api.PRACTICE_NOT_WALKED], "one notice, in the engine's words"
    assert said["offered"] == ["function"], "Retry is offered, as a fresh load's notice offers it"
    assert said["wish"] == 2 and said["turns"] == 0
    assert said["retried"] == {"page": {"list": "overview", "at": 2, "order": None, "filter": {"tab": "all"}}, "view": "v1"}, "Retry asks the same page"


def test_the_household_and_year_pages_read_their_counts_from_return_counts(tmp_path):
    """SPEC 4.6: a return's status on its household's and year's pages, and the comparison of a
    state's tally with the firm's counts, read `return_counts` - the compact list the engine sends
    with every page - never a list of whole returns."""
    ran = run_pages_dom("""
      const one = { path: "r1", return_name: "1040 - John & Jane Smith", form: "1040", year: 2025, active: true };
      globalThis.shellRoute = { level: "household", household: "h1" };
      shellFirmNow = { status: "ok", data: { totals: {}, return_counts: [{ path: "r1", counts: { needs_you: 3, waiting: 0 }, problem: "" }, { path: "r2", counts: { needs_you: 0, waiting: 0 }, problem: "Could Not Be Read" }], replies: {} } };
      const [spec] = pagesReturnSpecs([one]);
      const [broken] = pagesReturnSpecs([{ ...one, path: "r2" }]);
      const differ = (counts) => shellCountsDiffer({ paths: { engagement: "r1" }, counts });
      return { status: spec.status, broken: broken.status, same: differ({ needs_you: 3, waiting: 0 }), moved: differ({ needs_you: 2, waiting: 0 }) };
    """, tmp_path, setup="let shellFirmNow = null; const shellFirm = () => shellFirmNow; const pagesTally = (state) => state.counts;",
        functions=["pagesReturnSpecs", "pagesEach", "pagesSafe", "pagesLabel", "pagesSafeName", "pagesByName", "pagesFirmReturn", "pagesCounts", "pagesTaxpayer",
                   "pagesReturnName", "screenWords", "shellCountsDiffer"])
    assert ran == {"status": "3 need you", "broken": "Could Not Be Read", "same": False, "moved": True}


def test_search_on_needs_review_finds_files_on_every_page(tmp_path):
    """SPEC 4.6: the search box finds households and returns from `list`, which is whole, and on
    Needs Review the waiting files from the reply's `files_found` - every waiting file, not only
    the page's rows - so a file on another page is found."""
    ran = run_pages_dom("""
      const files = [{ name: "Smith W-2.pdf", return: "r1", year: 2025, handle: "h1" }, { name: "Jones 1099.pdf", return: "r2", year: 2025, handle: "h2" },
                     { name: "Smith K-1.pdf", return: "r2", year: 2025, handle: "h3" }];
      shellFirmNow = { status: "ok", data: { replies: { needs_review: { page: { rows: [{ files: [{ name: "Jones 1099.pdf" }] }] }, files_found: files } } } };
      shellReturn = (path) => engagements.find((one) => one.path === path) || null;
      const field = new Element("input"); field.value = "smith";
      const nodes = { find: field, "find-list": new Element("ul") };
      globalThis.$ = (id) => nodes[id];
      const options = () => { drawFound(); return shellFound.map((one) => [one.name, one.note, one.check ? one.check.handle : null]); };
      globalThis.shellRoute = { level: "needs-review" };
      const onReview = options();
      globalThis.shellRoute = { level: "overview" };
      const elsewhere = options();
      return { onReview, elsewhere };
    """, tmp_path, setup="""
      let shellFirmNow = null; let shellFound = []; let shellFindTimer = null; const hideTip = () => {};
      const shellFirm = () => shellFirmNow;
      const engagements = [{ path: "r1", return_name: "1040 - John Smith", household: "h1", year: 2025 }, { path: "r2", return_name: "1040 - Pat Jones", household: "h2", year: 2025 }];
      const shellOwnReturns = () => [];
    """, functions=["drawFound", "fold", "foldedName", "findOptions", "shellFirmHolds", "screenWords", "h"])
    assert [one[0] for one in ran["onReview"]] == ["Smith W-2.pdf", "Smith K-1.pdf", "1040 - John Smith"], "a file that is not on the page shown is found, before the returns"
    assert ran["onReview"][0][1:] == ["1040 - John Smith 2025", "h1"] and ran["onReview"][1][2] == "h3"
    assert [one[0] for one in ran["elsewhere"]] == ["1040 - John Smith"], "on any other page the box finds households and returns only"


def test_the_pages_collator_orders_the_shared_list_as_the_engine_does(tmp_path):
    """SPEC 4.4: the household, year and return pages still order their few rows by name in
    the window, and the engine orders the firm lists by `name_order`; both hold one made-up list
    (tests/samples.py) to the order the collator gives it."""
    from tests.samples import COLLATION_NAMES, COLLATION_ORDER
    from tracker.firm_pages import name_order

    ran = run_pages_dom(f"""
      const names = {json.dumps(COLLATION_NAMES)};
      return names.slice().sort(pagesByName);
    """, tmp_path, functions=["pagesByName"])
    assert ran == COLLATION_ORDER
    assert sorted(COLLATION_NAMES, key=name_order) == COLLATION_ORDER == ran


def test_the_engines_taxpayer_form_and_count_words_are_the_pages(tmp_path):
    """SPEC 4.9: the Python answers for a set of made-up inputs, computed in the test, against the
    window's own `pagesTaxpayer` and `pagesCounts` (the words a row says) and the order of the
    forms the Client Types hold (what the Form Type column orders by)."""
    from tracker import firm_pages

    words = api._firm_words()
    vocab_words = api._vocab()
    names = [("1040 - John & Maria Park", "1040"), ("1120-S - Rivera Design LLC", "1120S"), ("1120S - Rivera Design LLC", "1120-S"), ("1040 - John Park", "1065"),
             ("John Park 1040", "1040"), ("1040 - John Park", ""), ("1040 -", "1040"), ("1040 - 1040 - Twice", "1040"), ("990 - Trust of A - B", "990"), ("", "1040")]
    counts = [({"needs_you": 2, "waiting": 1}, ""), ({"needs_you": 0, "waiting": 4}, ""), ({"needs_you": 0, "waiting": 0}, ""), ({"needs_you": 0, "waiting": 0}, "Could Not Be Read"),
              ({"needs_you": 12, "waiting": 0}, "")]
    forms = ["1040", "1065", "990", "1041", "5500", "", "1120-S"]
    ran = run_pages_dom(f"""
      vocab.screen.counts = {json.dumps({"need": words["need"], "waiting": words["waiting"], "complete": words["complete"]})};
      const known = Object.values(vocab.client_type_forms).flat();
      return {{ taxpayer: {json.dumps(names)}.map(([name, form]) => pagesTaxpayer(name, form)),
                counts: {json.dumps(counts)}.map(([c, problem]) => {{ const said = pagesCounts(c, problem); return [said.text, said.tone]; }}),
                forms: {json.dumps(forms)}.map((f) => (f ? [known.indexOf(f) === -1 ? known.length : known.indexOf(f), f] : "")) }};
    """, tmp_path, functions=["pagesTaxpayer", "pagesCounts", "screenWords"], setup=f"vocab.client_type_forms = {json.dumps(vocab_words['client_type_forms'])};")
    assert ran["taxpayer"] == [firm_pages._taxpayer(name, form) for name, form in names]
    assert ran["counts"] == [list(firm_pages._counts_said(c, problem, words)) for c, problem in counts]
    assert ran["forms"] == [firm_pages._form_key(form, words) for form in forms]


def test_moving_to_a_firm_list_with_no_page_held_shows_its_loading_state_and_asks_its_first_page(tmp_path):
    """SPEC 4.6: moving to another firm list asks its first page with the held view's token; with
    no page held for that list the page shows its loading state (SPEC-shell 6), not another
    list's rows, and the page of the list it left stays held under the same view."""
    said = run_firm_page("""
      shellRoute = { level: "overview" };
      shellFirmNow = { status: "ok", data: shellFirmMerge(null, pageOf("overview", 0)) };
      shellDraw();
      shellRoute = { level: "needs-review" };
      shellFirmFollow();                    // shellGo's step, after pagesEnter has forgotten the Overview's choices
      shellDraw();
      const waiting = { ...looks(), payload: asked[0].payload };
      await land(0, pageOf("needs_review", 0));
      shellDraw();
      const arrived = { ...looks(), lists: Object.keys(shellFirmNow.data.replies).sort(), view: shellFirmNow.data.view };
      shellFirmFollow();                    // coming back to a page that is the one wanted asks nothing
      return { waiting, arrived, asked: asked.length };
    """, tmp_path)
    waiting = said["waiting"]
    assert waiting["payload"] == {"page": {"list": "needs_review", "at": 0, "order": None, "filter": {"reason": ""}}, "view": "v1"}
    assert waiting["busy"] == "true" and "row-skeleton" in waiting["rows"], "the loading state, not the Overview's rows"
    assert said["arrived"]["lists"] == ["needs_review", "overview"] and said["arrived"]["view"] == "v1" and said["arrived"]["busy"] == "false"
    assert said["asked"] == 1


def test_leaving_a_firm_list_forgets_its_choices_and_a_client_type_survives_the_way_to_clients(tmp_path):
    """P174, P145, P149, P153, as P278 moved the moment: the choices of a list (its page, tab,
    card and the Clients switch) are forgotten when it is left, and a Client Type when another
    firm page is opened - at the moment the list is entered, before the engine is asked for its
    first page, not when its rows are drawn."""
    ran = run_pages_dom("""
      const out = [];
      pagesEnter({ level: "overview" });
      pagesPageAt.overview = 2; pagesTab = "need"; pagesEnter({ level: "overview" });
      out.push([pagesPageAt.overview, pagesTab]);                         // entered again: nothing changes
      pagesEnter({ level: "needs-review" }); out.push([pagesPageAt.overview || 0, pagesTab]);
      pagesReasonPick = "unmatched"; pagesClientType = "trusts"; pagesClientsAll = true;
      pagesEnter({ level: "clients" }); out.push([pagesReasonPick, pagesClientType, pagesClientsAll]);   // the Client Type chosen on the way to Clients is kept
      pagesClientsAll = true; pagesEnter({ level: "household" }); out.push([pagesClientType, pagesClientsAll]);
      pagesEnter({ level: "clients" }); out.push([pagesClientType, pagesClientsAll]);
      pagesEnter({ level: "reminders" }); out.push([pagesClientType]);
      return out;
    """, tmp_path)
    assert ran == [[2, "need"], [0, "all"], ["", "trusts", False], ["trusts", True], ["trusts", False], [""]]
