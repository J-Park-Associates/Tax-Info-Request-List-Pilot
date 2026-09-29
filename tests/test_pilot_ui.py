"""Build E, the structure pass (pilot SPEC-ui.md, decisions P51-P54).

``app/renderer/pilot-ui.css`` redefines the look by overriding ``style.css``,
so what can be pinned is what the file may and may not contain. These tests
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

# Colour-bearing tokens live in :root and nowhere else.
COLOUR = re.compile(r"#[0-9a-fA-F]{3,8}\b|\brgba?\(")
GRID_TOKEN = re.compile(r"^(?:0|auto|var\(--sp-[a-z0-9-]+\))$")


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
                    assert prop == "--shadow-overlay", f"only the overlay shadow may hold rgba(: {prop}"
            continue
        assert not COLOUR.search(body), f"literal colour in {selector.strip()}"
    assert root_seen


def test_the_structure_pass_uses_only_the_type_ramp():
    wanted = {"font-size": "var(--fs-", "line-height": "var(--lh-", "font-weight": "var(--fw-"}
    seen = 0
    for _media, selector, body in outside_root():
        for prop, value in declarations(body):
            if prop in wanted:
                seen += 1
                assert value.startswith(wanted[prop]), f"{selector.strip()}: {prop}: {value}"
    assert seen


def test_the_structure_pass_uses_only_the_spacing_grid():
    props = {"padding", "margin", "gap", "row-gap", "column-gap"}
    props |= {f"{p}-{side}" for p in ("padding", "margin") for side in ("top", "right", "bottom", "left", "inline", "block")}
    seen = 0
    for _media, selector, body in outside_root():
        for prop, value in declarations(body):
            if prop not in props:
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
    css = read(CSS_NAME)
    block = re.search(r"@media \(forced-colors: active\) \{(.*)\n\}\n?$", css, flags=re.S)
    assert block, "the forced-colors block must be the last rule of pilot-ui.css"
    inner = block.group(1)
    assert "Highlight" in inner and "ButtonText" in inner and "GrayText" in inner
    assert not COLOUR.search(stripped(inner)), "system colours only"


def test_the_structure_pass_adds_no_remote_or_forbidden_thing():
    css = stripped(read(CSS_NAME))
    for banned in ("url(", "@import", "@font-face", "glass", "backdrop-filter"):
        assert banned not in css.lower(), banned
    for media, selector, body in outside_root():
        if "!important" in body:
            assert any("prefers-reduced-motion" in m for m in media), selector.strip()


def test_the_tour_leads_with_next():
    js = read("tour.js")
    assert re.search(r'next\.classList\.add\("btn-primary"\)', js)
