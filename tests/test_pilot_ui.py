"""Build E, the structure pass (pilot SPEC-ui.md, decisions P51-P54), and the
shell's tokens (pilot SPEC-shell.md section 10, decisions P72-P73).

``app/renderer/pilot-ui.css`` redefines the look by overriding ``style.css``,
so what can be pinned is what the file may and may not contain. Its colours
are written twice, light and dark; ``tests/test_shell.py`` checks the pairs. These tests
read it as text, the way ``test_pilot.py`` reads the pilot's other renderer
files: the window is sandboxed and there is no browser in the gate. Each one
is a claim of the SPEC's; the rendered claims (every button 32px or 24px, every
size on the ramp, contrast) are checked in a browser and reported in
``pilot/HANDOFF.md``.
"""

import re
from pathlib import Path

from tests.css_rules import (
    _SIDES,
    COLOUR,
    GRID_PROPS,
    GRID_TOKEN,
    SP_STEPS,
    blocks,
    colour_faults,
    declarations,
    stripped,
    top_level,
)
from tests.node_harness import read

REPO = Path(__file__).resolve().parent.parent


CSS_NAME = "pilot-ui.css"


GRID_PROPS |= {f"{p}-{side}" for p in ("padding", "margin") for side in _SIDES}
GRID_PROPS |= {f"inset-{side}" for side in _SIDES}


def outside_root():
    for media, selector, body in blocks(read(CSS_NAME)):
        if selector.strip() != ":root":
            yield media, selector, body


def test_the_structure_pass_loads_between_the_app_and_the_pilot():
    html = read("index.html")
    app, ui, pilot = (html.index(f'href="{n}"') for n in ("style.css", CSS_NAME, "pilot-style.css"))
    assert app < ui < pilot


def test_the_structure_pass_writes_no_literal_colour_outside_its_tokens():
    root_seen = False
    for _media, selector, body in blocks(read(CSS_NAME)):
        if selector.strip() == ":root":
            root_seen = True
            for prop, value in declarations(body):
                assert prop.startswith("--") or not COLOUR.search(value), f":root: {prop}"
                if "rgba(" in value:
                    assert prop in ("--shadow-overlay", "--scrim"), f"only the overlay shadow and the scrim may hold rgba(: {prop}"
            continue
        for prop, value in declarations(body):
            faults = list(colour_faults(prop, value))
            assert not faults, f"literal colour {faults} in {selector.strip()}: {prop}: {value}"
    assert root_seen


def test_the_structure_pass_uses_only_the_type_ramp():
    wanted = {"font-size": "var(--fs-", "line-height": "var(--lh-", "font-weight": "var(--fw-"}
    seen = 0
    for _media, selector, body in outside_root():
        for prop, value in declarations(body):
            assert prop != "font", f"{selector.strip()}: the font shorthand hides a size and a weight; write the three"
            if prop in wanted:
                seen += 1
                assert value.startswith(wanted[prop]), f"{selector.strip()}: {prop}: {value}"
    assert seen


def test_the_structure_pass_uses_only_the_spacing_grid():
    seen = 0
    for _media, selector, body in outside_root():
        for prop, value in declarations(body):
            if prop not in GRID_PROPS:
                continue
            seen += 1
            flat = re.sub(r"calc\(([^()]|\([^()]*\))*\)", "0", value)
            for token in flat.split():
                assert GRID_TOKEN.match(token), f"{selector.strip()}: {prop}: {value}"
            for inner in re.findall(r"calc\((.*)\)", value):
                assert not re.search(r"\d+(?:\.\d+)?px", inner), f"{selector.strip()}: {prop}: {value}"
    assert seen


def test_the_structure_pass_leaves_the_letter_alone():
    for _media, selector, _body in blocks(read(CSS_NAME)):
        assert ".rem-preview" not in selector, selector


def test_the_structure_pass_honours_contrast_themes_last():
    css = stripped(read(CSS_NAME))
    rules = list(top_level(css))
    prelude, inner, end = rules[-1]
    assert prelude == "@media (forced-colors: active)", f"the last rule of pilot-ui.css must be the forced-colors block, not {prelude!r}"
    assert sum("forced-colors" in p for p, _b, _e in rules) == 1, "one forced-colors block, and it is the last rule"
    assert not css[end:].strip(), "nothing may follow the forced-colors block"
    used = {w.lower() for w in re.findall(r"\b[A-Za-z]+\b", inner)}
    assert {"highlight", "buttontext", "graytext"} <= used
    for _media, selector, body in blocks(prelude + " {" + inner + "}"):
        for prop, value in declarations(body):
            for word in colour_faults(prop, value):
                raise AssertionError(f"system colours only: {selector.strip()}: {prop}: {word}")


def test_the_structure_pass_adds_no_remote_or_forbidden_thing():
    css = stripped(read(CSS_NAME))
    for banned in ("url(", "@import", "@font-face", "glass", "backdrop-filter"):
        assert banned not in css.lower(), banned
    for media, selector, body in blocks(read(CSS_NAME)):  # :root included
        if "!important" in body:
            assert any("prefers-reduced-motion" in m for m in media), selector.strip()


# Rules whose element the page never hides with .hidden.
NEVER_HIDDEN: dict[str, str] = {}


def test_the_structure_pass_never_unhides_a_hidden_element():
    """A `display` in a later stylesheet out-ranks style.css's `.hidden`
    (same specificity, later source), so an element app.js hides comes back:
    Build E did this to #wi-household ("Change Household Details" in Add a
    return). Every display other than none is declared under :not(.hidden)."""
    seen = 0
    for name in (CSS_NAME, "pilot-style.css"):
        for _media, selector, body in blocks(read(name)):
            if selector.strip() == ":root":
                continue
            if not [v for p, v in declarations(body) if p == "display" and v != "none"]:
                continue
            for one in (part.strip() for part in selector.split(",")):
                seen += 1
                if ":not(.hidden)" in one or one in NEVER_HIDDEN:
                    continue
                # The pilot's own overlays, cards and chips are built and removed by pilot.js and
                # tour.js, which never toggle .hidden (asserted below), so they cannot be unhidden.
                assert name == "pilot-style.css" and ".pilot-" in one, f"{name}: {one} sets display without :not(.hidden)"
    assert seen
    for script in ("pilot.js", "tour.js", "pilot-content.js"):
        assert not re.search(r"""["'`]hidden["'`]|\.hidden\b""", read(script)), f"{script} toggles .hidden: the exemption above is void"


def test_the_tour_leads_with_next():
    js = read("tour.js")
    assert re.search(r'next\.classList\.add\("btn-primary"\)', js)


def test_cards_never_shrink_inside_the_scrolling_column():
    """P55: without it a flex child with overflow: hidden collapses to a
    sliver when notices fill the window, instead of #page scrolling."""
    rules = {sel.strip(): dict(declarations(body)) for _m, sel, body in blocks(read(CSS_NAME))}
    assert rules["#page > *"]["flex-shrink"] == "0"


def test_the_grids_retired_steps_are_gone_from_every_pilot_stylesheet():
    """SPEC-shell 10.3: --sp-half, --sp-3 and --sp-5 are deleted, and every
    use moved to a step that keeps the component on the 4px grid."""
    for name in (CSS_NAME, "shell.css", "pilot-style.css"):
        css = stripped(read(name))
        assert not re.search(r"--sp-(?:half|3|5)\b", css), name
    defined = set(re.findall(r"--sp-(\w+):", stripped(read(CSS_NAME))))
    assert defined == set(SP_STEPS)


# ── P265-P280 (SPEC-ui-menu-small) ───────────────────────────────────────

def test_the_face_is_chosen_once_per_platform_in_the_token_block_and_no_rule_names_a_face():
    """P280: the light :root keeps Segoe UI Variable for Windows; one
    :root.on-mac block, outside every @media and before the forced-colors
    block, gives a Mac the system face; and every other font-family in the
    three stylesheets is one of the two tokens or inherit."""
    css = stripped(read(CSS_NAME))
    rules = list(top_level(css))
    roots = [dict(declarations(body)) for prelude, body, _end in rules if prelude.strip() == ":root"]
    assert len(roots) == 1 and roots[0]["--font-ui"].startswith('"Segoe UI Variable Text"')
    assert roots[0]["--font-display"].startswith('"Segoe UI Variable Display"')
    macs = [(at, dict(declarations(body))) for at, (prelude, body, _end) in enumerate(rules) if prelude.strip() == ":root.on-mac"]
    assert len(macs) == 1, "one block, outside every @media (top_level yields only top-level rules)"
    at, mac = macs[0]
    assert mac["--font-ui"].startswith("-apple-system") and mac["--font-display"] == "var(--font-ui)" and set(mac) == {"--font-ui", "--font-display"}
    forced = next(i for i, (prelude, _body, _end) in enumerate(rules) if prelude.strip().startswith("@media (forced-colors"))
    assert at < forced and forced == len(rules) - 1, "the forced-colors block stays the file's last rule"
    for name in (CSS_NAME, "shell.css", "pilot-style.css"):
        for _media, selector, body in blocks(read(name)):
            for prop, value in declarations(body):
                if prop == "font-family":
                    assert value in ("var(--font-ui)", "var(--font-display)", "inherit"), f"{name}: {selector.strip()}: {value}"


# ── P279 (SPEC-ui-menu-speed §2): long lists draw only the rows in view ───

def test_a_long_lists_rows_are_absolute_one_line_and_set_no_height_of_their_own():
    """P279: `.rows.is-virtual > .row` places each drawn row (absolute, left
    and right 0) on one line (nowrap, its name and status cut with an
    ellipsis) and declares no height, so the row's own min-height - the
    density's (--size-row, or P271's compact one) - is what the script
    measures; no selector of the block names .rows-compact, so P271's rule
    that a .rows-compact rule sets only min-height, font-size and line-height
    still holds; the editor's spacer rows carry no padding or border."""
    shell = [(" ".join(sel.split()), dict(declarations(body))) for _m, sel, body in blocks(read("shell.css")) if "is-virtual" in sel]
    assert shell, "the long-list rules are in shell.css"
    for selector, rule in shell:
        assert ".rows-compact" not in selector, selector
        assert not {prop for prop in rule if "height" in prop}, f"{selector}: the density's height is the row's own"
    row = next(rule for selector, rule in shell if selector.startswith(".rows.is-virtual > .row:not(.hidden),"))
    assert row["position"] == "absolute" and row["left"] == "0" and row["right"] == "0" and row["white-space"] == "nowrap"
    cut = next(rule for selector, rule in shell if ".row-name" in selector and ".row-status" in selector)
    assert cut["overflow"] == "hidden" and cut["text-overflow"] == "ellipsis" and cut["white-space"] == "nowrap"
    assert not any("row-wrap" in selector for selector, _ in shell), "a long list's rows never wrap"
    spacer = {" ".join(sel.split()): dict(declarations(body)) for _m, sel, body in blocks(read("style.css"))}[".editor-table .ed-spacer td"]
    assert spacer["padding"] == "0" and spacer["border"] == "0"
