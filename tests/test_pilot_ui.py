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

REPO = Path(__file__).resolve().parent.parent
RENDERER = REPO / "app" / "renderer"
CSS_NAME = "pilot-ui.css"

# Colour-bearing tokens live in :root and nowhere else. A literal colour is a
# hex, a colour function, or a bare colour word (red, white, ...): outside :root
# a colour value may only be a var(), transparent, currentColor, inherit or a
# system colour, so the check is on what is allowed rather than a list of names.
COLOUR = re.compile(
    r"#[0-9a-fA-F]{3,8}\b|\b(?:rgba?|hsla?|hwb|lab|lch|oklab|oklch|color|color-mix)\(",
    re.I,
)
COLOUR_PROPS = {
    "color", "background", "background-color", "border", "border-color", "outline", "outline-color",
    "fill", "stroke", "box-shadow", "text-shadow", "text-decoration", "text-decoration-color",
    "caret-color", "accent-color", "column-rule", "column-rule-color",
} | {f"border-{side}{tail}" for side in ("top", "right", "bottom", "left", "inline", "block") for tail in ("", "-color")}
SYSTEM_COLOURS = {
    "highlight", "highlighttext", "buttontext", "buttonface", "buttonborder", "graytext", "canvas",
    "canvastext", "linktext", "visitedtext", "activetext", "field", "fieldtext", "mark", "marktext",
}
# Words that legitimately sit in a colour-bearing shorthand without being a colour.
NOT_A_COLOUR = {
    "transparent", "currentcolor", "inherit", "initial", "unset", "none", "solid", "dashed", "dotted",
    "double", "inset", "outset", "groove", "ridge", "hidden", "underline", "overline", "line-through",
    "no-repeat", "repeat", "center", "cover", "contain", "border-box", "padding-box", "content-box",
    "important",
}
# The grid's steps (SPEC-shell 10.3): 4, 8, 16, 24, 32 and 48. The retired
# --sp-half (2), --sp-3 (12) and --sp-5 (20) are not steps.
SP_STEPS = ("1", "2", "4", "6", "8", "12")
GRID_TOKEN = re.compile(r"^(?:0|auto|var\(--sp-(?:" + "|".join(SP_STEPS) + r")\))$")
# Every property that lays out by a distance: the physical and the logical sides.
_SIDES = ("top", "right", "bottom", "left", "inline", "block", "inline-start", "inline-end", "block-start", "block-end")
GRID_PROPS = {"gap", "row-gap", "column-gap", "inset", "padding", "margin"}
GRID_PROPS |= {f"{p}-{side}" for p in ("padding", "margin") for side in _SIDES}
GRID_PROPS |= {f"inset-{side}" for side in _SIDES}


def read(name: str) -> str:
    return (RENDERER / name).read_text(encoding="utf-8")


def stripped(text: str) -> str:
    return re.sub(r"/\*.*?\*/", "", text, flags=re.S)


def blocks(css: str):
    """Yield (media_stack, selector, body) for every rule, at any depth."""
    css = stripped(css)
    pos = 0
    stack: list[str] = []  # the at-rule preludes we are inside of
    kinds: list[str] = []  # "at" or "rule" per open brace
    heads: list[int] = []
    prelude_start = 0
    while pos < len(css):
        ch = css[pos]
        if ch == "{":
            head = css[prelude_start:pos].strip()
            if head.startswith("@"):
                kinds.append("at")
                stack.append(head)
                heads.append(pos + 1)
            else:
                kinds.append("rule")
                heads.append(pos + 1)
                stack.append(head)
            prelude_start = pos + 1
        elif ch == "}":
            kind = kinds.pop()
            head = stack.pop()
            start = heads.pop()
            if kind == "rule":
                yield tuple(s for s in stack if s.startswith("@")), head, css[start:pos]
            prelude_start = pos + 1
        pos += 1


def top_level(css: str):
    """Yield (prelude, body, end) for each top-level rule of comment-stripped css, by balanced braces."""
    depth, start, prelude_start, prelude = 0, 0, 0, ""
    for pos, ch in enumerate(css):
        if ch == "{":
            if depth == 0:
                prelude, start = css[prelude_start:pos].strip(), pos + 1
            depth += 1
        elif ch == "}":
            depth -= 1
            assert depth >= 0, "unbalanced braces"
            if depth == 0:
                yield prelude, css[start:pos], pos + 1
                prelude_start = pos + 1
    assert depth == 0, "unbalanced braces"


def colour_faults(prop: str, value: str):
    """What in this declaration is a colour that is not a token or a system colour."""
    if COLOUR.search(value):
        yield value
    if prop in COLOUR_PROPS:
        bare = re.sub(r"var\([^)]*\)", " ", value)
        bare = re.sub(r"[-+]?\d*\.?\d+[a-z%]*", " ", bare)  # lengths and numbers
        for word in re.findall(r"[a-zA-Z][a-zA-Z-]*", bare):
            if word.lower() not in SYSTEM_COLOURS | NOT_A_COLOUR:
                yield word


def declarations(body: str):
    for part in body.split(";"):
        if ":" in part:
            prop, _, value = part.partition(":")
            yield prop.strip(), value.strip()


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
    Build E did this to #wi-household ("Change household details" in Add a
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
    """P55: without it .card { overflow: hidden } collapses every card to a
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
