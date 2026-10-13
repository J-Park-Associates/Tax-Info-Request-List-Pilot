"""The renderer's stylesheets read as text: rules, declarations, colours and the grid.

``app/renderer/pilot-ui.css`` redefines the look by overriding ``style.css``, so
what a test can pin is what the file may and may not contain. These are the
readers of that text: the rules at any depth (``blocks``), the top-level rules
by balanced braces (``top_level``), a declaration's property and value
(``declarations``), what in a value is a colour that is not a token
(``colour_faults``) and the grid's steps. ``test_pilot_ui`` wrote them and
``test_shell`` imported them from it; they live here so the borrowing names a module that is not a test file
(SPEC-architecture E-4, R2.1). Moved with their words.
"""

import re

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
