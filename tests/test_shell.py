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

#: The new renderer scripts. S5 adds sheet.js.
SHELL_FILES = ("shell.js", "tooltip.js", "pages.js", "sheet.js")
#: Files that hold no ``title`` attribute (SPEC 13): every tooltip is setTip().
TITLE_FREE = ("shell.js", "tooltip.js", "pages.js", "sheet.js", "shell.css", "pilot.js", "tour.js", "app.js", "index.html")



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
    scripts = [html.index(f'src="{name}"') for name in ("app.js", "tooltip.js", "pages.js", "sheet.js", "shell.js", "pilot-content.js", "pilot.js", "tour.js")]
    assert scripts == sorted(scripts)
    assert ("default-src 'none'; script-src 'self'; style-src 'self'; img-src 'self' data:; font-src 'self'") in html
    assert "<style" not in html and not re.search(r"<script(?![^>]*\bsrc=)", html)


def test_the_skeleton_is_the_specs_and_the_legacy_box_holds_only_the_three_inputs_saveroot_reads():
    """SPEC 3.1 and 13. The pages took the toolbar, the banners, the request
    table, the household card and the setup card; the side sheet took the
    reminder, moved, review and filed cards; the dialogs took the roll fold
    and the standing rules. What #legacy still holds is the three boxes
    saveRoot() reads."""
    html = read("index.html")
    for wanted in ('id="shell"', 'id="side"', 'id="side-brand"', 'id="side-sections"', 'id="side-foot"', 'id="last-sort"',
                   'id="main"', 'id="bar"', 'id="crumbs"', 'id="find-wrap"', 'id="find"', 'id="find-list"', 'id="sort"',
                   'id="notices"', 'id="page"', 'id="sheet"', 'id="sheet-scrim"', 'id="tip"', 'id="toast"'):
        assert wanted in html, wanted
    assert html.count('data-section="') == 4
    assert re.search(r'<div id="legacy" class="hidden">', html)
    outside = html[:html.index('<div id="legacy"')]
    legacy = html[html.index('<div id="legacy"'):html.index('<div id="household-modal"')]
    for gone in ("topbar", "brand-logo", 'id="eng-select"', "btn-scan", "btn-inbox", 'id="toolbar"', 'class="toolbar"', "eng-form", "view-state",
                 'id="banner"', 'id="reader-warning"', 'id="last-pass"', 'id="machine-warnings"', 'id="after-install"',
                 'id="lock-notice"', 'id="misfits-card"', 'id="room-card"', 'id="setup-card"', 'id="household-card"',
                 'id="rows"', 'id="summary"', 'id="pass-progress"', "btn-unlock", "btn-stop-pass", "household-returns",
                 "review-deck", "review-mode", "mode-toggle", "deck"):
        assert gone not in outside and gone not in legacy, gone
    for kept in ('id="root-input"', 'id="firm-input"', 'id="phone-input"'):
        assert kept in legacy, kept
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
    for symbol in ("search", "sort", "stop", "dismiss", "chev", "next", "done", "more", "open"):
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
    keys = re.findall(r'<button[^>]*\bid="(sort|sheet-close)"[^>]*data-tip-key="([\w.]+)"', html)
    assert {name for name, _key in keys} == {"sort", "sheet-close"}
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
#: shell removes; each needs no dark value because nothing draws it. S4 took
#: the toolbar, the chips, the request table, the household card and the
#: setup card away; S5 deleted the review list, the reminder card, the
#: assurances and their rules: only :root is left.
RETIRED = (":root",)


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


def js_function(name: str, source: str = "shell.js") -> str:
    text = read(source)
    start = text.index(f"function {name}(")
    if text[max(0, start - 6):start] == "async ":
        start -= 6
    return text[start:text.index("\n}\n", start) + 3]


def run_shell(functions: list[str], setup: str, probe: str, tmp_path: Path, source: str = "shell.js"):
    """Lift the named functions out of shell.js (or ``source``) as they are,
    put fakes for what app.js provides around them, and return what the
    probe prints."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    lifted = "\n".join(js_function(name, source if f"function {name}(" in read(source) else "shell.js") for name in functions)
    script = tmp_path / "probe.js"
    script.write_text(f"{setup}\n{lifted}\nPromise.resolve((() => {{ {probe} }})()).then((out) => process.stdout.write(JSON.stringify(out)));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def run_pages(functions: list[str], setup: str, probe: str, tmp_path: Path):
    """The same, lifting the named functions out of pages.js."""
    return run_shell(functions, setup, probe, tmp_path, "pages.js")


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
                "reminders", "clients", "find", "refresh", "sort_now", "stop_sorting", "schedule", "repair_schedule", "firm_report",
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
    """SPEC 5.4: {enable} and {popup, enable, token, x, y}; the token is a
    key the page made, never a path."""
    text = stripped_js("shell.js")
    sends = re.findall(r"window\.tracker\.menu\.send\(([^;]*)\);", text)
    assert sorted(sends) == sorted(["{ enable: shellEnabled() }", "{ popup: name, enable: enable || shellEnabled(), token, x, y }"])
    assert 'shellPopup(one.popup, `crumb-${one.popup}`' in text, "a segment's token is its own name"
    assert "window.tracker.menu.onCommand(shellMenu)" in text


# ── node: the pages (SPEC 6, 3.6, 14.1) ────────────────────────────────────

#: A small DOM, enough for h(), icon() and the pages' own builders: elements
#: with a class list, a dataset, attributes, children and a search by class
#: or role. Its point is to run pages.js's functions as written.
FAKE_DOM = r"""
class Node {}
class Text extends Node { constructor(data) { super(); this.data = data; } }
class Element extends Node {
  constructor(tag) { super(); this.tag = tag; this.className = ""; this.dataset = {}; this.attrs = {}; this.kids = []; this.open = false; this.handlers = {}; }
  get classList() {
    const self = this;
    return { add(one) { if (!self.className.split(" ").includes(one)) self.className = `${self.className} ${one}`.trim(); },
             contains(one) { return self.className.split(" ").includes(one); } };
  }
  setAttribute(key, value) { this.attrs[key] = String(value); }
  getAttribute(key) { return this.attrs[key]; }
  append(...nodes) { for (const one of nodes) this.kids.push(one instanceof Node ? one : new Text(String(one))); }
  replaceChildren(...nodes) { this.kids = []; this.append(...nodes); }
  addEventListener(type, fn) { (this.handlers[type] = this.handlers[type] || []).push(fn); }
  get childNodes() { return this.kids; }
  find(test, out = []) { for (const one of this.kids) if (one instanceof Element) { if (test(one)) out.push(one); one.find(test, out); } return out; }
  querySelector(selector) { return this.byClass(selector.slice(1))[0] || null; }
  byClass(name) { return this.find((one) => one.className.split(" ").includes(name)); }
  get textContent() { return this.kids.map((one) => (one instanceof Text ? one.data : one.textContent)).join(""); }
}
const document = { activeElement: null, createDocumentFragment: () => new Element("fragment"), createElement: (tag) => new Element(tag), createElementNS: (_ns, tag) => new Element(tag) };
const page = (nodes) => { const box = new Element("div"); box.append(...nodes.filter(Boolean)); return box; };
"""

PAGE_WORDS = r"""
const fill = (p, v) => p.replace(/\{(\w+)\}/g, (_, k) => v[k] ?? "");
const isSetAside = (o) => o === "Not Applicable";
const overrideLabel = (o, year) => `Not applicable ${year}`;
let locked = false;
let lastState = null;
const tips = [];
const setTipIfCut = (node, words) => tips.push([node.className, words]);
const setTip = (node, words) => tips.push([node.className, words]);
const opened = []; const went = [];
const openPath = (path, how) => opened.push([path, how]);
const shellGo = (route) => went.push(route);
const shellPopup = (name, token, x, y, enable) => {};
const unanswered = (id) => failures.push(`unanswered ${id}`);
let shellReturn = (path) => ({ return_name: "1040 - John & Jane Smith", household: "h1", year: 2025 });
const PAGES_LINK_WORDS = { file: "show_in_explorer", household: "navigate_client", return: "navigate_return" };
const PAGES_GROUPS = ["needs_you", "waiting", "received", "set_aside"];
const PAGES_TONES = { needs: "is-attention", waiting: "is-waiting", done: "is-done", plain: "is-plain" };
const PAGES_LATE = "9999-99-99";
let pagesUid = 0; const pagesTokens = new Map(); let pagesSetAsideOpen = false; let pagesBroken = []; let pagesDrawn = "";
let pagesFocus = null; let pagesLastLevel = ""; let pagesClientsAll = false;
const notices = []; const failures = [];
let syncNotices = (prefix, wanted) => notices.push([prefix, wanted.map((one) => [one.key, one.failure.sentence, one.detail || ""])]);
const failed = (err) => failures.push(String(err.message));
let shellHousehold = () => null; let households = [];
const vocab = {
  shell: { page_error: "The app hit an error" }, notices: { about: "{label}: {sentence}" },
  decisions: { needs_review: "Needs Review", dismissed: "Not Requested", filed: "Filed", file_moved: "File Moved" },
  labels: { Missing: { label: "Outstanding" }, Received: { label: "Received" }, Partial: { label: "Partly in" }, Rejected: { label: "Could not use" }, NotAsked: { label: "Not asked" } },
  overrides: { not_applicable: "Not Applicable" },
  review_labels: { bucket_order: ["document", "container", "not_a_document"], dismiss: "Not requested",
                   buckets: { document: "Documents", container: "Emails and zips", not_a_document: "Not documents" } },
  reasons: { unmatched: { short: "Could not tell" }, "opened-not-across": { short: "Came in email or zip" } },
  screen: {
    groups: { needs_you: "Needs you", waiting: "Waiting on client", received: "Received", set_aside: "Set aside" },
    steps: { check: "Check", open: "Open", draft: "Draft reminder", edit: "Edit" },
    empty: { received: "Nothing received yet" }, moved: "Moved by hand", due: "Due {date}", partly: "{n} of {total}",
    show_in_explorer: "Show in File Explorer", navigate_client: "Navigate to Client", navigate_return: "Navigate to Return",
    counts: { need: "{n} need you", waiting: "{n} waiting", complete: "Complete", files: "{n} files", one_return: "1 return", returns: "{n} returns" },
  },
};
"""

RETURN_STATE = r"""
const item = (id, group, extra = {}) => ({ identifier: id, document: `Doc ${id}`, short_name: `Doc ${id}`, group, status_key: "Missing", manual_override: "",
  period: "", year: 2025, file_count: 0, expected_count: 1, received_date: null, ...extra });
const parked = (handle, extra = {}) => ({ handle, original_name: `${handle}.pdf`, decision: "Needs Review", group: "needs_you", code: "unmatched", received: "2026-03-03", bucket: "document", ...extra });
const movedRow = (handle, extra = {}) => ({ handle, original_name: `${handle}.pdf`, decision: "File Moved", group: "needs_you", code: "file-moved", received: "2026-03-02", ...extra });
const setAsideRow = (handle, extra = {}) => ({ handle, original_name: `${handle}.pdf`, decision: "Not Requested", group: "set_aside", code: "not-requested", received: "2026-03-01", ...extra });
const stateOf = (items, index = [], moved = []) => ({ paths: { engagement: "r1" }, engagement: { due: "2026-04-15" }, items, index, review: [], moved });
"""


def run_pages_dom(probe: str, tmp_path: Path, setup: str = "", functions=None):
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    wanted = functions or [
        "pagesReturn", "pagesReturnName", "pagesTitle", "pagesCaption", "pagesDue", "pagesDay", "pagesReturnGroups", "pagesItemName",
        "pagesItemStatus", "pagesItemDetail", "pagesByName", "pagesReason", "pagesBlocks", "pagesRow", "pagesStepWords",
        "pagesReturnPlan", "pagesGroup", "pagesGroupStep", "pagesList", "pagesWorkRows", "pagesCounts", "pagesTally",
        "pagesHouseholdNotices", "pagesRoute", "pagesFiles", "h", "icon", "screenWords", "pagesSafe", "pagesEach", "pagesLabel",
        "pagesSafeName", "pagesTitleFor", "pagesReportBroken", "pagesRouteKey", "pagesDraw", "pagesBuild", "pagesYear", "pagesReturnSpecs",
        "pagesClientSpecs", "pagesRemember", "pagesRestore", "pagesFirmReturn", "pagesActivate", "pagesOverview", "pagesNeedsReview",
        "pagesReminders", "pagesClients", "pagesHousehold", "folderName", "pagesLinkWords", "pagesReturnText", "pagesHouseholdPath",
        "pagesPathOf", "pagesFileLink", "pagesRunLink", "pagesLinkNode", "pagesCell", "pagesHeadLink", "pagesRunRowLink", "pagesWhere",
        "pagesSteps", "pagesDrafts", "pagesRunRow", "pagesRunStep", "pagesPopup", "pagesEnableFor", "pagesRowRoute", "pagesKey", "pagesTitle",
    ]
    shell = read("shell.js")
    consts = "\n".join(shell[shell.index(head):shell.index(");\n", shell.index(head)) + 3] if head.endswith("[") else shell[shell.index(head):shell.index("\n", shell.index(head))]
                       for head in ("const H_ATTRIBUTES = new Set([", 'const SVG_NS = '))
    lifted = consts + "\n" + "\n".join(js_function(name, "pages.js" if f"function {name}(" in read("pages.js") else "shell.js") for name in wanted)
    script = tmp_path / "pages_probe.js"
    script.write_text(f"{FAKE_DOM}\n{PAGE_WORDS}\n{RETURN_STATE}\n{setup}\n{lifted}\nprocess.stdout.write(JSON.stringify((() => {{ {probe} }})()));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)



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
      return groups.needs_you.map((one) => [one.name, one.status, one.sub || ""]);
    """, tmp_path)
    assert ran == [["b-old.pdf", "Could not tell", ""], ["a-new.pdf", "Could not tell", ""], ["moved.pdf", "Moved by hand", ""],
                   ["Doc A", "Could not use", ""], ["zip.pdf", "Came in email or zip", "Emails and zips"]]


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


def test_the_overview_puts_each_return_in_one_bucket(tmp_path):
    """SPEC 6.1: a return with anything for a person is Need a person, else
    Waiting on clients, else Complete; the rows are the first two, need-you
    by oldest file and waiting by due date; a return whose record could not
    be read leads, saying so, and is never left out."""
    ran = run_pages_dom("""
      const names = { a: "Alpha", b: "Bravo", c: "Charlie", d: "Delta", e: "Echo", f: "Foxtrot" };
      shellReturn = (path) => ({ return_name: names[path], household: "h", year: 2025 });
      const make = (path, counts, extra = {}) => ({ path, household: "h", counts: { needs_you: 0, waiting: 0, received: 0, set_aside: 0, ...counts }, oldest: null, due: null, problem: "", ...extra });
      const rows = pagesWorkRows([
        make("a", { needs_you: 2, waiting: 1 }, { oldest: "2026-03-04" }), make("b", { waiting: 2 }, { due: "2026-04-15" }),
        make("c", { received: 5 }), make("d", { needs_you: 1 }, { oldest: "2026-03-02" }),
        make("e", {}, { problem: "Record unreadable" }), make("f", { waiting: 1 }, { due: "2026-04-01" }) ]);
      return rows.map((one) => [one.name, one.status, one.tone, one.date, one.step.kind]);
    """, tmp_path)
    assert [one[0] for one in ran] == ["Echo (2025)", "Delta (2025)", "Alpha (2025)", "Foxtrot (2025)", "Bravo (2025)"], "Charlie is complete and is not listed; a return reads with its year (ruling 13)"
    assert ran[0][1:3] == ["Record unreadable", "needs"]
    assert ran[2][1:3] == ["2 need you", "needs"], "a return with both counts is in the first bucket only"
    assert ran[3][2] == "waiting" and all(one[4] == "open" for one in ran)


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


#: The scenarios of the harness's stub that draw notices, and the pages' own functions that draw them.
NOTICE_FUNCTIONS = ["renderMachineNotices", "renderAfterInstall", "renderShortOfRoom", "showLock", "lockStarted", "noticeOf"]


def run_notices(probe: str, tmp_path: Path, vocab_notices: str = "{}"):
    """Run the harness's own stub (pilot/harness/stub.js, with the API's long
    sentences in it) in a vm, get the replies it gives, and hand them to the
    functions of app.js, shell.js and pages.js that draw notices, as written.
    Every notice they draw, and every line they send to the error log, is
    recorded."""
    if NODE is None:
        pytest.skip("node is not on PATH (CI installs it)")
    lifted = "\n".join([js_function(name, "app.js") for name in NOTICE_FUNCTIONS] + [js_function("shortNotice", "shell.js"),
                                                                                       js_function("pagesHouseholdNotices", "pages.js")])
    harness = (REPO / "pilot" / "harness" / "stub.js").read_text(encoding="utf-8")
    mirror = (REPO / "pilot" / "harness" / "vocab-mirror.json").read_text(encoding="utf-8")
    script = tmp_path / "notices_probe.js"
    script.write_text(f"""
const vm = require("vm");
const fill = (p, v) => p.replace(/\\{{(\\w+)\\}}/g, (_, k) => v[k] ?? "");
const stubSource = {json.dumps(harness)};
const mirror = JSON.parse({json.dumps(mirror)});
async function replies(scenario) {{
  const window = {{ __VOCAB__: mirror }};
  vm.runInContext(stubSource, vm.createContext({{ window, location: {{ search: `?scenario=${{scenario}}` }}, URLSearchParams, setTimeout, console, Date, Intl }}));
  const list = await window.tracker.call(["list"]);
  const state = await window.tracker.call(["state", "--engagement", list.engagements[0].path]);
  return {{ list, state }};
}}
let vocab = null; let active = ""; let locked = false; let lockStale = false;
const drawn = []; const logged = [];
window = {{ tracker: {{ logError: (text) => logged.push(text) }} }};
const keyedNotice = (key, failure) => {{ drawn.push([key, failure.sentence]); return true; }};
const clearNotice = () => {{}};
let syncNotices = (prefix, wanted) => {{ for (const one of wanted) {{ drawn.push([`${{prefix}}:${{one.key.slice(0, 8)}}`, one.failure.sentence]); if (one.detail) logged.push(one.detail); }} }};
const stopLockWatch = () => {{}}; const setLocked = () => {{}}; const watchLock = () => {{}};
const acceptFolderName = () => {{}};
{lifted}
(async () => {{
  const out = await (async () => {{ {probe} }})();
  process.stdout.write(JSON.stringify(out));
}})();
""", encoding="utf-8", newline="\n")
    done = subprocess.run([NODE, str(script)], capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


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
    warning (it names C:\\JPA Tracker), each machine warning, the pause, the
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
      const firm = { returns: [
        { path: "a", household: "h", counts: { needs_you: 0, waiting: 1, received: 0, set_aside: 0 }, oldest: null, due: null, draft: { ready: true, stage: 1, held: 0, drafted: null }, problem: "" },
        { path: "b", household: "h", counts: { needs_you: 0, waiting: 1, received: 0, set_aside: 0 }, oldest: null, due: null, draft: { ready: true, stage: 9, held: 0, drafted: null }, problem: "" } ] };
      shellReturn = (path) => ({ return_name: path === "a" ? "Alpha" : "Bravo", household: "h", year: 2025 });
      vocab.reminder = { stages: [{ number: 1, short: "Heads up" }] };
      pagesBroken = [];
      const specs = pagesReminderSpecs(firm);
      return { specs: specs.map((one) => [one.name, one.status]), broken: pagesBroken.map((one) => one.name) };
    """, tmp_path, functions=["pagesReminderSpecs", "pagesStage", "pagesSafe", "pagesEach", "pagesLabel", "pagesSafeName", "pagesReturnName",
                              "pagesByName", "pagesDay", "screenWords", "pagesReturnText", "pagesHouseholdPath"])
    assert ran["specs"] == [["Alpha (2025)", "Heads up"]] and ran["broken"] == ["Bravo"]


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
      let shellDraw = null; let pagesTally = null;
      const shellFirmNow = { data: { returns: [{ path: "r1", counts: {} }] } };
      const shellLoadFirm = () => {};
    """
    assert run_shell(["shellStateArrived"], setup, probe, tmp_path) == [None, ["draw", "tally"]]


def test_the_year_page_leaves_a_gap_under_its_h1_before_its_rows(tmp_path):
    """The mock-up (3.6): a list starts --sp-6 below what precedes it."""
    ran = run_pages_dom("""
      const hh = { name: "Smith Family", returns: [{ path: "r1", year: 2025, return_name: "1040 - John & Jane Smith", active: true }] };
      shellHousehold = () => hh;
      globalThis.shellRoute = { household: "h1" };
      const nodes = pagesYear({ level: "year", household: "h1", year: 2025 });
      return nodes.map((one) => `${one.tag}.${one.className.split(" ")[0]}`);
    """, tmp_path, setup="const shellFirm = () => ({ data: null });")
    assert ran == ["h1.page-title", "div.page-gap", "div.rows"]
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
    ran = run_pages_dom("""
      households = [{ name: "Alpha Family", path: "a" }, { name: "Bravo Family", path: "b" }, { name: "Charlie Family", path: "c" }];
      const make = (household, counts, problem = "") => ({ path: household, household, counts: { needs_you: 0, waiting: 0, received: 0, set_aside: 0, ...counts }, problem });
      const firm = { returns: [make("Alpha Family", {}, "Could not be read"), make("Bravo Family", { needs_you: 2 }), make("Charlie Family", {})] };
      const say = (all) => pagesClientSpecs(firm, all).map((one) => [one.name, one.status, one.tone]);
      return { work: say(false), all: say(true) };
    """, tmp_path)
    assert ran["work"] == [["Alpha Family", "Could not be read", "needs"], ["Bravo Family", "2 need you", "needs"]]
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
        { path: gone, household: "Gone Family", counts: counts(0, 0), files: 0, oldest: null, due: null, draft: { ready: true, stage: 1, held: 2, drafted: null }, problem: "Could not be read" } ],
        files: [{ return: known, name: "scan0012.pdf", code: "unmatched", received: "2026-03-03", suggestion: "W-2 - Acme" },
                { return: gone, name: "IMG_1.jpg", code: "unmatched", received: "2026-03-04", suggestion: "" }],
        totals: { need: 2, waiting: 0, complete: 0, files: 2, drafts: 2 }, next_sort: "18:00" };
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
    """, tmp_path, setup="""
      let shellFirmData = null; const shellFirm = () => ({ data: shellFirmData }); const openNewHousehold = () => {}; const openAddReturn = () => {};
      Object.assign(vocab.screen, {
        figures: { need: "Need a person", waiting: "Waiting on clients", complete: "Complete" }, work: "Work waiting",
        sections: { reminders: "Reminders", clients: "Clients" }, filters: { work: "Work waiting", all: "All" }, held: "Held",
        inactive: "Inactive", rolled: "Rolled forward", contact: "Contact {name}", shared: "Shared", not_shared: "Not shared",
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
    for good in ("Needs Review", "Waiting on Client", "Add a Return…", "Client (Greeting Name)", "Not Opened; It Has Changed", "Belongs To…", "Due Date (Optional)"):
        assert title_case_ok(good), good
    for bad in ("Needs review", "Waiting On Client", "Add A Return", "Due date (optional)", "Look again"):
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
    mirror = json.loads((REPO / "pilot" / "harness" / "vocab-mirror.json").read_text(encoding="utf-8"))
    notices = mirror["screen"]["notices"]
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
        received: groups.received.map((s) => [s.detail, s.detailLink ? s.detailLink.key : null]),
        unfile: groups.received.map((s) => [s.name, s.unfile ? s.unfile.original : null]),
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
    assert ran["unfile"] == [["Doc R", "f"], ["Doc M", None], ["Doc N", "n"], ["Doc Y", None]], "Unfile is offered for the one original filed under a request, not for several"
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
    assert ran["words"] == ["Show in File Explorer", "Navigate to Client", "Navigate to Return"]


def test_a_return_link_reads_its_name_and_its_year_from_the_rows_own_record(tmp_path):
    """Ruling 13: "{Return Name} ({Year})", the name from the list and the
    year from the row (or the list's), never a year the renderer worked out;
    a row with neither year reads as its name alone."""
    ran = run_pages_dom("""
      shellReturn = (path) => (path === "a" ? { return_name: "1120-S - Rivera Design LLC", household: "h", year: 2024 } : null);
      return [pagesReturnText("a", 2025), pagesReturnText("a"), pagesReturnText("gone/2023/1040 - Gone", 0), pagesReturnText("a", 2025, "Named On The Row")];
    """, tmp_path)
    assert ran == ["1120-S - Rivera Design LLC (2025)", "1120-S - Rivera Design LLC (2024)", "1040 - Gone", "Named On The Row (2025)"]


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
        { path: known, household: "Smith Family", year: 2025, label: "Smith Family 2025 1040 - Smith", counts: { needs_you: 2, waiting: 0, received: 0, set_aside: 0 }, oldest: "2026-03-03", due: null,
          draft: { ready: true, stage: 1, held: 0, drafted: "2026-03-03" }, problem: "" }],
        files: [{ return: known, year: 2025, name: "one.pdf", handle: "h1", code: "unmatched", received: "2026-03-03", suggestion: "", open_key: "shown_copy h1" },
                { return: known, year: 2025, name: "two.exe", handle: "h2", code: "unmatched", received: "2026-03-04", suggestion: "", open_key: "" }],
        totals: {}, next_sort: null };
      shellFirm = () => ({ data: firmData });
      const nodes = pagesNeedsReview();
      const head = nodes.find((n) => n.byClass && n.byClass("group-title").length).byClass("group-title")[0];
      const caption = nodes.find((n) => n.byClass && n.byClass("group-count").length).byClass("group-count")[0];
      const rows = nodes.flatMap((n) => (n.byClass ? n.byClass("row") : []));
      pagesBroken = [];
      const overview = pagesWorkRows(firmData.returns)[0] || { broken: pagesBroken.map((b) => String(b.err)) };
      const reminder = pagesReminderSpecs(firmData)[0];
      const link = (n) => n.byClass("row-link").map((l) => [l.textContent, l.dataset.link]);
      return { head: link(head), caption: link(caption), captionText: caption.textContent, rows: rows.map((r) => [r.byClass("row-name")[0].textContent, link(r.byClass("row-name")[0])]),
               overview: [overview.name, overview.nameLink, overview.detailLink], reminder: [reminder.name, reminder.nameLink.kind, reminder.detailLink.kind] };
    """, tmp_path, functions=["pagesNeedsReview", "pagesReviewGroups", "pagesFirm", "pagesFirmReturn", "pagesReturnName", "pagesReturnText", "pagesHouseholdPath",
                              "pagesFileLink", "pagesRow", "pagesCell", "pagesLinkNode", "pagesLinkWords", "pagesHeadLink", "pagesGroup", "pagesGroupStep", "pagesList",
                              "pagesReason", "pagesDay", "pagesSafe", "pagesEach", "pagesLabel", "pagesSafeName", "pagesStepWords", "pagesByName", "pagesEmpty",
                              "pagesNextSort", "pagesWorkRows", "pagesCounts", "pagesRoute", "pagesDue", "pagesReminderSpecs", "pagesStage", "screenWords", "h", "icon",
                              "pagesActivate", "pagesRunRow", "pagesRunRowLink", "pagesRunLink", "pagesRunStep", "pagesPathOf", "pagesPopup", "pagesEnableFor", "pagesRowRoute"])
    assert ran["head"] == [["1040 - Smith (2025)", "return"]] and ran["caption"] == [["Smith Family", "household"]] and ran["captionText"] == "Smith Family · 2"
    assert ran["rows"] == [["one.pdf", [["one.pdf", "file"]]], ["two.exe", []]], "text for the file with no copy"
    assert ran["overview"][0] == "1040 - Smith (2025)" and ran["overview"][1]["kind"] == "return" and ran["overview"][2] == {"kind": "household", "path": "/c/Smith"}
    assert ran["reminder"] == ["1040 - Smith (2025)", "return", "household"]


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
      const on = (fn) => { fn(); };
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
#: itself is the checklist in pilot/handoffs/shell-S5-rebuild-1.md (POPUPS lives on S2's branch).
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
    ran = run_shell(["writeKey", "writeBusy", "writeStart", "writeDone", "unfileDocument", "withdrawAnswer"], """
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
      const PILOT = { edition: { version: "0.2" } };
      let misfits = [{ path: "/abs/Clients/Old Files", where: "Clients/Old Files", sentence: "This folder is not a household and is left alone by the tracker." },
                     { path: "C:\\\\abs\\\\Scans", where: "", sentence: "Also left alone." }];
      const vocab = { product: "Tax Document Tracker", rules: [{ headline: "h", detail: "d", short: "No AI Reads Documents" }, { headline: "h2", detail: "d2", short: "Nothing Is Guessed" }],
        screen: { icons: { dismiss: "Dismiss" }, safeguards: { title: "Safeguards" }, about: { edition: "Pilot {version}" }, misfits: { title: "Folders Skipped" } } };
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
    assert ran["product"] == "Tax Document Tracker" and ran["edition"] == "Pilot 0.2"
    assert ran["folders"] == ["Old Files", "Scans"], "a folder is its own name: the last part of where it is"
    assert ran["opened"] == ["safeguards-modal", "about-modal", "misfits-modal"]
    assert ran["loud"] == "rules.short", "a rule without its short line is a word the vocabulary lacks: loud, not the long sentence"
    assert any("vocab.screen.misfits.reason" in line for line in ran["logged"]), "the missing two-word reason is said in the error log"
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
