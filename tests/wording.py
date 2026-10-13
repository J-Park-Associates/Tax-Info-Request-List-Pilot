"""The rules about words that more than one suite holds.

Every word the window draws is in Title Case by one rule (Jason, 2026-09-29):
the API's vocabulary, the renderer's own words and the tour are all held to
it. ``test_api`` wrote the rule and ``test_shell`` and ``test_tour`` borrowed it
by importing it from there; it lives here so the borrowing names a module that is not a test file (SPEC-architecture E-4, R2.1). Moved with
its words from ``tests/test_api.py``.
"""

import re

_SMALL = frozenset("a an the and but or nor for of on in to by at as up vs".split())


def title_case(text: str) -> str:
    """The one rule, stdlib only: every word capital except a, an, the, and,
    but, or, nor, for, of, on, in, to, by, at, as, up, vs when neither first
    nor last; each part of a hyphenated word; the first word after a colon or
    semicolon. Placeholders, numbers and ALL-CAPS tokens are left alone."""
    words = text.split(" ")
    out, after_stop = [], True
    for i, word in enumerate(words):
        core = re.sub(r"^\W+|\W+$", "", word)
        forced = i == 0 or i == len(words) - 1 or after_stop
        after_stop = word.endswith((":", ";"))
        if not core or re.search(r"[{}0-9]", word) or (core.isupper() and len(core) > 1):
            out.append(word)
        elif not forced and core.lower() in _SMALL:
            out.append(word[:1].lower() + word[1:])
        else:
            out.append("-".join(re.sub(r"[A-Za-z]", lambda m: m.group().upper(), part, count=1)
                                for part in word.split("-")))
    return " ".join(out)
