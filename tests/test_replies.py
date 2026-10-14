"""The written shape of every reply, held to what the program prints and the screen reads.

``tracker/replies.py`` writes down each reply's keys as a ``TypedDict``
(SPEC-architecture 5.1 (6); P2.3). A contract nothing checks is a comment,
so this file holds three things to it:

- **The recordings.** Each of the nine replies ``tests/golden/`` records has
  every key its type requires and no key its type does not name. The
  recordings are read, no command is run, so this costs nothing next to
  ``tests/test_golden.py``, which holds the program to the recordings.
- **The envelope.** :func:`tracker.progress.failure_reply` is the one builder
  of the error envelope (decision 193; ``api._envelope_of`` returns what it
  builds, whole), and its keys are :class:`~tracker.replies.Envelope`'s and
  :class:`~tracker.replies.Failure`'s for every kind. The main process's own
  ``shellFailure`` (``app/main.js``), the envelope the window gets when no
  engine answered, is held to the same keys.
- **The failure kinds the screen names.** A kind the screen tests for or
  raises that the engine never sends is a branch that never runs, or a
  notice drawn in no style; one the engine sends and the screen spells
  differently is a failure drawn wrong. C-4's other answer, a vocabulary key,
  would have changed ``tests/golden/vocab.keys.json``; this guard changes no
  reply. Every kind literal it collects must be in
  :data:`tracker.progress.FAILURE_KINDS`, or be a notice kind the screen
  raises itself (:data:`NOTICE_KINDS`).

**Why the collector is five named patterns, not every ``kind``.** The
renderer says ``kind`` for many vocabularies that are not failures - sheet
kinds, link kinds, Open kinds, step kinds - so a guard over every ``kind``
literal would need an exclusion table that rots. It reads a double-quoted
literal only in a failure's context: the ``kind`` of an object that has a
``sentence`` or spreads a ``failure``; a literal compared with
``failure.kind`` or ``entry.kind``; one compared with the local ``kind`` a
function took from ``failure.kind``; the default after ``failure.kind ||``;
and ``shellFailure``'s second argument. :data:`MUST_FIND` pins that each
pattern still sees the sites it was written for, so a pattern that stops
matching fails here rather than going quiet, and :data:`MUST_NOT_FIND` pins
the failure-shaped sites that are not failures, so a pattern widened past
them fails too. A literal it catches that is not a failure kind is never
excluded by name: the pattern is narrowed.

The scripts are read through :func:`tests.node_harness.stripped_js`, so a
comment can neither hide a site nor add one; the lexer here also skips any
comment the strip left, strings, template text and regular expressions, so a
bracket or a quote inside one never moves an object's edge.
"""

from __future__ import annotations

import ast
import json
import re
from collections import Counter
from functools import cache
from typing import NamedTuple

import pytest

from tests.node_harness import RENDERER_SCRIPTS, REPO, read, stripped_js
from tracker import progress, replies

GOLDEN = REPO / "tests" / "golden"
MAIN_JS = REPO / "app" / "main.js"

#: Each command ``tests/golden/`` records a reply of, and the type that reply is held to.
REPLY_TYPES: dict[str, type] = {
    "assign": replies.AssignReply,
    "create": replies.CreateReply,
    "edit-household": replies.EditHouseholdReply,
    "edit": replies.EditReply,
    "firm-last": replies.FirmLastReply,
    "firm": replies.FirmReply,
    "list": replies.ListReply,
    "reminder": replies.ReminderReply,
    "state": replies.StateReply,
}


def _keys_problem(shape: type, keys: set[str]) -> str:
    """Why ``keys`` is not a set ``shape`` allows, or ``""``: every required
    key there, and no key the type does not name."""
    required, optional = set(shape.__required_keys__), set(shape.__optional_keys__)
    missing, unnamed = required - keys, keys - required - optional
    return (f"{shape.__name__}: missing {sorted(missing)}, not named {sorted(unnamed)}"
            if missing or unnamed else "")


# ------------------------------------------------------------ the recordings ----

def test_every_recorded_reply_has_a_type():
    recorded = {path.name for path in GOLDEN.glob("replies.*.keys.json")}
    assert recorded == {f"replies.{command}.keys.json" for command in REPLY_TYPES}


@pytest.mark.parametrize("command", sorted(REPLY_TYPES))
def test_each_recorded_reply_has_its_types_required_keys_and_none_it_does_not_name(command):
    recorded = set(json.loads((GOLDEN / f"replies.{command}.keys.json").read_text(encoding="utf-8")))
    assert not _keys_problem(REPLY_TYPES[command], recorded)


def test_the_reply_shapes_import_typing_and_nothing_else():
    """R2.3.1, and never ``from __future__ import annotations``: written as
    strings, ``NotRequired[...]`` is not seen when a class is made, so every
    key would read as required."""
    tree = ast.parse((REPO / "tracker" / "replies.py").read_text(encoding="utf-8"))
    imported = {node.module if isinstance(node, ast.ImportFrom) else alias.name
                for node in ast.walk(tree) if isinstance(node, (ast.Import, ast.ImportFrom))
                for alias in node.names}
    assert imported == {"typing"}


def test_every_success_reply_carries_the_envelopes_warnings():
    """``main`` adds ``warnings`` to every reply after its handler returns
    (decision 193), so every type says so, and none may leave it out."""
    for shape in REPLY_TYPES.values():
        assert "warnings" in shape.__required_keys__, shape.__name__


# -------------------------------------------------------------- the envelope ----

@pytest.mark.parametrize("kind", progress.FAILURE_KINDS)
def test_the_one_envelope_has_the_envelope_and_failure_keys_for_every_kind(kind):
    reply = progress.failure_reply("s", kind)
    assert not _keys_problem(replies.Failure, set(reply["failure"]))
    assert set(reply) == replies.Envelope.__required_keys__ | replies.Envelope.__optional_keys__


def test_what_a_failure_may_carry_beside_its_four_keys_is_the_lock_and_the_key():
    """The two extras ``api._envelope_of`` hands ``failure_reply``: a
    ``locked`` failure's lock, and the firm page refusal's ``key`` (P278)."""
    assert replies.Failure.__optional_keys__ == {"lock", "key"}
    for extra in ({"lock": None}, {"key": "firm_page_refused"}):
        failure = progress.failure_reply("s", "refused", **extra)["failure"]
        assert not _keys_problem(replies.Failure, set(failure)), extra


# --------------------------------------------- reading the scripts' structure ----

#: Where a ``/`` starts a regular expression rather than a division: after
#: one of these, or at the start.
_REGEX_AFTER_PUNCTUATION = set("(,=:[!&|?{};+-*%<>~^")
_REGEX_AFTER_WORDS = {"return", "typeof", "case", "do", "else", "in", "of", "new", "delete", "void",
                      "throw", "yield", "await"}
_WORD = re.compile(r"[\w$]+")


class _Script(NamedTuple):
    """One script, read: its text; the same text as ``code``, where what is
    inside a string or a template's text is ``x`` (so a bracket, a quote or a
    word inside one is never seen, and a literal still stands where it
    stood), and a regular expression, a comment, and a template's ``${``
    and its ``}`` are blank; each double-quoted literal by where it starts
    (start -> (end, value)); and each bracket's partner."""

    name: str
    text: str
    code: str
    literals: dict[int, tuple[int, str]]
    pairs: dict[int, int]

    def line(self, at: int) -> int:
        return self.text.count("\n", 0, at) + 1

    def line_text(self, number: int) -> str:
        return self.text.split("\n")[number - 1]


def _read(name: str, text: str) -> _Script:
    """``text`` read as :class:`_Script` says, in one pass. Anything it cannot
    read - a string, template, expression or bracket left open - fails at
    once, so a script this cannot follow is never half-checked."""
    code = list(text)
    literals: dict[int, tuple[int, str]] = {}
    pairs: dict[int, int] = {}
    opened: list[tuple[str, int]] = []     # ("(" | "[" | "{" | "${", where)
    last: tuple[str, str] | None = None    # the last code token: ("word" | "punct" | "value", it)
    n = len(text)

    def blank(start: int, end: int, filler: str = " ") -> None:
        for k in range(start, end):
            if code[k] != "\n":
                code[k] = filler

    def template_text(at: int) -> int:
        """From inside a template's text, to just past its end or its next ``${``."""
        k = at
        while k < n:
            if text[k] == "\\":
                k += 2
            elif text[k] == "`":
                blank(at, k, "x")
                return k + 1
            elif text.startswith("${", k):
                blank(at, k, "x")
                blank(k, k + 2)
                opened.append(("${", k))
                return k + 2
            else:
                k += 1
        raise AssertionError(f"{name}: a template literal is not closed")

    i = 0
    while i < n:
        c = text[i]
        if c in "\"'":
            k = i + 1
            while text[k] != c:
                if text[k] == "\n":
                    raise AssertionError(f"{name}:{text.count(chr(10), 0, i) + 1}: a string is not closed")
                k += 2 if text[k] == "\\" else 1
            if c == '"':
                literals[i] = (k + 1, text[i + 1:k])
            blank(i + 1, k, "x")
            i, last = k + 1, ("value", "")
        elif c == "`":
            i, last = template_text(i + 1), ("value", "")
        elif text.startswith("//", i):
            end = text.find("\n", i)
            end = n if end == -1 else end
            blank(i, end)
            i = end
        elif text.startswith("/*", i):
            end = text.index("*/", i) + 2
            blank(i, end)
            i = end
        elif c == "/" and (last is None or (last[0] == "punct" and last[1] in _REGEX_AFTER_PUNCTUATION)
                           or (last[0] == "word" and last[1] in _REGEX_AFTER_WORDS)):
            k, in_class = i + 1, False
            while in_class or text[k] != "/":
                if text[k] == "\n":
                    raise AssertionError(f"{name}:{text.count(chr(10), 0, i) + 1}: a regular expression is not closed")
                in_class = (in_class or text[k] == "[") and text[k] != "]"
                k += 2 if text[k] == "\\" else 1
            k += 1
            while k < n and text[k].isalpha():
                k += 1
            blank(i, k)
            i, last = k, ("value", "")
        elif c.isspace():
            i += 1
        elif (word := _WORD.match(text, i)):
            i, last = word.end(), ("word", word.group())
        else:
            if c in "([{":
                opened.append((c, i))
            elif c in ")]}":
                kind, at = opened.pop()
                if kind == "${":
                    blank(i, i + 1)
                    i, last = template_text(i + 1), ("value", "")
                    continue
                assert {"(": ")", "[": "]", "{": "}"}[kind] == c, f"{name}: {kind} at {at} closed by {c} at {i}"
                pairs[at] = i
            i, last = i + 1, ("punct", c)
    assert not opened, f"{name}: {len(opened)} brackets are not closed"
    return _Script(name, text, "".join(code), literals, pairs)


def _strip(script: _Script, start: int, end: int) -> tuple[int, int]:
    while start < end and script.code[start].isspace():
        start += 1
    while end > start and script.code[end - 1].isspace():
        end -= 1
    return start, end


def _literal(script: _Script, start: int, end: int) -> int | None:
    """Where the one double-quoted literal ``[start, end)`` is, or ``None``."""
    start, end = _strip(script, start, end)
    held = script.literals.get(start)
    return start if held and held[0] == end else None


def _top_level(script: _Script, start: int, end: int):
    """Each position in ``[start, end)`` outside any bracket opened inside it."""
    k = start
    while k < end:
        yield k
        k = script.pairs[k] + 1 if k in script.pairs else k + 1


def _split(script: _Script, start: int, end: int, on: str = ",") -> list[tuple[int, int]]:
    parts, at = [], start
    for k in _top_level(script, start, end):
        if script.code[k] == on:
            parts.append((at, k))
            at = k + 1
    parts.append((at, end))
    return [part for part in parts if _strip(script, *part)[0] < _strip(script, *part)[1]]


def _value_literals(script: _Script, start: int, end: int) -> list[int]:
    """The literals a value can be: itself, both arms of a ternary (never its
    condition), or the right side of ``||``."""
    tops = list(_top_level(script, start, end))
    asked = next((k for k in tops if script.code[k] == "?" and script.code[k + 1] not in "?."
                  and script.code[k - 1] != "?"), None)
    if asked is not None:
        depth = 0
        for k in tops:
            if k <= asked:
                continue
            if script.code[k] == "?" and script.code[k + 1] not in "?." and script.code[k - 1] != "?":
                depth += 1
            elif script.code[k] == ":":
                if depth == 0:
                    return _value_literals(script, asked + 1, k) + _value_literals(script, k + 1, end)
                depth -= 1
    either = [k for k in tops if script.code.startswith("||", k)]
    if either:
        return _value_literals(script, either[-1] + 2, end)
    found = _literal(script, start, end)
    return [] if found is None else [found]


_KEY = re.compile(r"\s*([A-Za-z_$][\w$]*)\s*:(?!:)")
_SHORTHAND = re.compile(r"\s*([A-Za-z_$][\w$]*)\s*$")
_SPREAD = re.compile(r"\s*\.\.\.\s*((?:[\w$]+\s*\.\s*)*[\w$]+)\s*$")


def _properties(script: _Script, opening: int) -> list[tuple[str, int | None, int]]:
    """The object at ``opening``'s top-level properties: (key, where its value
    starts or ``None`` for a shorthand, where it ends); a spread is
    ``("...<what is spread>", None, end)``."""
    said = []
    for start, end in _split(script, opening + 1, script.pairs[opening]):
        part = script.code[start:end]
        quoted = _strip(script, start, end)[0]
        if quoted in script.literals and script.code[script.literals[quoted][0]:end].lstrip().startswith(":"):
            colon = script.code.index(":", script.literals[quoted][0])
            said.append((script.literals[quoted][1], colon + 1, end))
        elif (key := _KEY.match(part)):
            said.append((key.group(1), start + key.end(), end))
        elif (spread := _SPREAD.match(part)):
            said.append(("..." + re.sub(r"\s", "", spread.group(1)), None, end))
        elif (shorthand := _SHORTHAND.match(part)):
            said.append((shorthand.group(1), None, end))
    return said


def _is_an_object(script: _Script, opening: int) -> bool:
    """Whether the ``{`` at ``opening`` starts an object literal, not a block."""
    k = opening - 1
    while k >= 0 and script.code[k].isspace():
        k -= 1
    if k < 0:
        return False
    if script.code[k] in "(,=:[?|&!":
        return True
    word = re.search(r"[\w$]+$", script.code[:k + 1])
    return bool(word) and word.group() in {"return", "yield"}


def _enclosing_braces(script: _Script, at: int) -> tuple[int, int]:
    """The innermost ``{ }`` around ``at``: the scope a ``const`` there has."""
    around = [(opening, closing) for opening, closing in script.pairs.items()
              if script.code[opening] == "{" and opening < at < closing]
    return max(around)


# ------------------------------------------------------ the five patterns ----

class Kind(NamedTuple):
    """A kind literal the collector caught: where, by which pattern, and the
    line it is on as the stripped script numbers and holds it (``line``,
    ``text``)."""

    file: str
    pattern: str
    literal: str
    line: int
    text: str


_COMPARE = r"\s*(?:===|!==|==|!=)\s*"
_COMPARED_ON_THE_RIGHT = re.compile(_COMPARE)
_COMPARED_ON_THE_LEFT = re.compile(_COMPARE + r"$")
_FAILURE_KIND = re.compile(r"(?<![\w$])(?:failure|entry)\.kind(?![\w$])")
_LOCAL_KIND = re.compile(r"(?<![\w$.])kind(?![\w$])")
_TAKES_THE_FAILURES_KIND = re.compile(r"\bconst\s+kind\s*=\s*failure\.kind\s*\|\|\s*")
_DEFAULT_KIND = re.compile(r"(?<![\w$])failure\.kind\s*\|\|\s*")
_SHELL_FAILURE = re.compile(r"(?<![\w$.])shellFailure\s*\(")


def _compared(script: _Script, name: re.Pattern, start: int = 0, end: int | None = None) -> list[int]:
    """Each literal compared, on either side, with what ``name`` matches."""
    end = len(script.code) if end is None else end
    ends = {held[0]: at for at, held in script.literals.items()}
    found = []
    for hit in name.finditer(script.code, start, end):
        right = _COMPARED_ON_THE_RIGHT.match(script.code, hit.end())
        if right and right.end() in script.literals:
            found.append(right.end())
        left = _COMPARED_ON_THE_LEFT.search(script.code[max(0, hit.start() - 40):hit.start()])
        if left:
            before = hit.start() - len(left.group())
            if before in ends:
                found.append(ends[before])
    return found


def _collect(script: _Script, *, shell_failure: bool) -> list[Kind]:
    caught: list[tuple[str, int]] = []
    # 1. The kind of an object that has a sentence or spreads a failure.
    for opening in script.pairs:
        if script.code[opening] != "{" or not _is_an_object(script, opening):
            continue
        properties = _properties(script, opening)
        keys = {key for key, _, _ in properties}
        if "sentence" in keys or any(re.fullmatch(r"\.\.\.(?:[\w$]+\.)*failure", key) for key in keys):
            for key, start, end in properties:
                if key == "kind" and start is not None:
                    caught += [("sentence_object", at) for at in _value_literals(script, start, end)]
    # 2. A literal compared with failure.kind or entry.kind, any dotted prefix.
    caught += [("kind_compared", at) for at in _compared(script, _FAILURE_KIND)]
    # 3. A literal compared with the local kind a function took from failure.kind.
    for taken in _TAKES_THE_FAILURES_KIND.finditer(script.code):
        if taken.end() in script.literals:
            opening, closing = _enclosing_braces(script, taken.start())
            caught += [("local_kind_compared", at) for at in _compared(script, _LOCAL_KIND, opening, closing)]
    # 4. The default after failure.kind ||.
    caught += [("kind_default", hit.end()) for hit in _DEFAULT_KIND.finditer(script.code)
               if hit.end() in script.literals]
    # 5. shellFailure's second argument, when it is a literal.
    if shell_failure:
        for call in _SHELL_FAILURE.finditer(script.code):
            arguments = _split(script, call.end(), script.pairs[call.end() - 1])
            if len(arguments) >= 2 and (at := _literal(script, *arguments[1])) is not None:
                caught.append(("shell_failure", at))
    return [Kind(script.name, pattern, script.literals[at][1], script.line(at), script.line_text(script.line(at)))
            for pattern, at in caught]


@cache
def _scripts() -> tuple[_Script, ...]:
    """Every script the guard reads: the renderer's, in the page's order, and
    the main process's."""
    return (*(_read(name, stripped_js(name)) for name in RENDERER_SCRIPTS), _read("main.js", stripped_js(MAIN_JS)))


@cache
def collected() -> tuple[Kind, ...]:
    """Every kind literal the five patterns catch; ``shellFailure`` is the
    main process's alone."""
    return tuple(kind for script in _scripts() for kind in _collect(script, shell_failure=script.name == "main.js"))


#: A kind the screen raises on its own that is never a failure, with why.
NOTICE_KINDS: dict[str, str] = {
    "warning": "a notice the screen raises itself, never a failure (app.js 380, 2542)",
}

#: (file, pattern, literal, a piece of the site's own line): each must be
#: caught. A line listed twice (app.js's two ``notice`` and ``keyedNotice``
#: defaults) must be caught on as many lines.
MUST_FIND: tuple[tuple[str, str, str, str], ...] = (
    ("app.js", "sentence_object", "failed", 'sentence: result.error, kind: "failed"'),
    ("app.js", "sentence_object", "failed", 'notice({ sentence: said, kind: cls === "err" ?'),
    ("app.js", "sentence_object", "warning", 'notice({ sentence: said, kind: cls === "err" ?'),
    ("app.js", "sentence_object", "failed", 'notice({ sentence, kind: "failed", seq: null'),
    ("app.js", "sentence_object", "locked", 'keyedNotice("lock", { sentence: said, kind: "locked" })'),
    ("app.js", "sentence_object", "failed", '{ sentence: failureSentence(err), kind: "failed" }'),
    ("app.js", "sentence_object", "failed", '{ sentence: vocab.after_install.heading, kind: "failed"'),
    ("app.js", "sentence_object", "failed", '{ sentence: ended.error, kind: "failed" }'),
    ("app.js", "sentence_object", "failed", '{ ...failure, kind: failure.kind || "failed", retry: runScan }'),
    ("app.js", "sentence_object", "failed", 'kind: said.cls === "err" ? "failed" : "warning"'),
    ("app.js", "sentence_object", "warning", 'kind: said.cls === "err" ? "failed" : "warning"'),
    ("shell.js", "sentence_object", "failed", 'notice({ ...failure, kind: "failed" }, { retry: again })'),
    ("shell.js", "sentence_object", "failed", 'notice({ sentence: screenWords().notices.firm_failed, kind: "failed" }'),
    ("shell.js", "sentence_object", "failed",
     'keyedNotice("last-sort", { sentence: screenWords().last_sort.failed, kind: "failed" })'),
    ("shell.js", "sentence_object", "failed", 'notice({ sentence: screenWords().setup.missing, kind: "failed" })'),
    ("shell.js", "sentence_object", "failed",
     'notice({ sentence: fill(vocab.shell.page_error, { kind: id }), kind: "failed" })'),
    ("pages.js", "sentence_object", "failed", '{ label: one.name, sentence: said }) : said, kind: "failed" }'),
    ("app.js", "kind_compared", "stale", 'if (entry.kind === "stale") return entry.retry'),
    ("app.js", "kind_compared", "failed", 'return entry.kind === "failed" ? entry.retry : null'),
    ("app.js", "kind_compared", "refused", 'err.failure && err.failure.kind === "refused"'),
    ("shell.js", "kind_compared", "refused", 'else if (failure && failure.kind === "refused")'),
    ("app.js", "local_kind_compared", "locked", 'if (kind === "locked" && failure.lock) showLock(failure.lock)'),
    ("app.js", "kind_default", "failed", 'const kind = failure.kind || "failed";'),
    ("app.js", "kind_default", "failed", 'const kind = failure.kind || "failed";'),
    ("app.js", "kind_default", "failed", '{ ...failure, kind: failure.kind || "failed", retry: runScan }'),
    ("main.js", "shell_failure", "refused", 'if (problem) return Promise.resolve(shellFailure(problem, "refused"))'),
    ("main.js", "shell_failure", "refused", '{ kind: err.name || "Error" }), "refused")'),
    ("main.js", "shell_failure", "refused", 'NOT_SET_UP_MAC : NOT_SET_UP, "refused")'),
    ("main.js", "shell_failure", "failed", 'shellFailure(said + where, "failed", { progress: last, killed: true })'),
    ("main.js", "shell_failure", "failed", 'shellFailure(fill(shellSays.no_reply, { code }), "failed", { progress: last })'),
    ("main.js", "shell_failure", "failed", 'const out = shellFailure(said, "failed", { progress: last })'),
    ("main.js", "shell_failure", "failed",
     'shellFailure(fill(shellSays.could_not_start, { code: (err && err.code) || "?" }), "failed")'),
    ("main.js", "shell_failure", "refused", 'return shellFailure(NOT_FROM_THE_WINDOW, "refused")'),
)

#: (file, literal, a piece of the line): failure-shaped by word, not a
#: failure. The piece must still be in the script, and that literal must not
#: be caught on its line - another literal on the same line may be.
MUST_NOT_FIND: tuple[tuple[str, str, str], ...] = (
    ("sheet.js", "check", 'sheetNow.kind === "check"'),
    ("sheet.js", "moved", '{ kind: "moved", moved }'),
    ("main.js", "folder", 'kind === "folder"'),
    ("main.js", "reveal", 'kind === "reveal" && !reveal'),
    ("main.js", "Error", '{ kind: err.name || "Error" }'),
    ("app.js", "refused", 'classList.toggle("refused"'),
    ("app.js", "reminder", 'sheetNow.kind === "reminder"'),
    ("app.js", "related", 'one.kind === "related"'),
    ("pages.js", "file", '{ kind: "file", key, paths: map }'),
    ("pages.js", "household", 'link.kind === "household"'),
    ("pages.js", "edit", 'spec.step.kind === "edit"'),
    ("shell.js", "failed", 'status !== "failed"'),
    ("shell.js", "failed", 'status: "failed"'),
    ("shell.js", "locked", 'key: "locked"'),
)


def _where(kinds) -> list[str]:
    """Each kind as a person finds it: by the script's own line numbers, which
    the stripped text (its block comments gone) does not keep."""
    said = []
    for one in kinds:
        own = (MAIN_JS.read_text(encoding="utf-8") if one.file == "main.js" else read(one.file)).split("\n")
        lines = ",".join(str(n) for n, text in enumerate(own, start=1) if one.text.strip() in text)
        said.append(f"{one.file}:{lines} ({one.pattern}) {one.literal!r}: {one.text.strip()}")
    return said


def test_every_failure_kind_the_screen_names_is_the_engines():
    kinds = collected()
    named = set(progress.FAILURE_KINDS) | set(NOTICE_KINDS)
    strangers = [one for one in kinds if one.literal not in named]
    assert not strangers, _where(strangers)


def test_each_pattern_still_catches_the_sites_it_was_written_for():
    kinds = collected()
    wanted = Counter(MUST_FIND)
    short = [f"{entry} caught on {found} of {count} lines"
             for entry, count in wanted.items()
             if (found := sum(1 for one in kinds if (one.file, one.pattern, one.literal) == entry[:3]
                              and entry[3] in one.text)) < count]
    assert not short, short


def test_no_pattern_catches_a_failure_shaped_site_that_is_not_a_failure():
    kinds = collected()
    texts = {script.name: script.text.split("\n") for script in _scripts()}
    for file, literal, anchor in MUST_NOT_FIND:
        lines = [n for n, text in enumerate(texts[file], start=1) if anchor in text]
        assert lines, f"{file}: {anchor!r} is no longer in the script; the entry has rotted"
        caught = [one for one in kinds if one.file == file and one.line in lines and one.literal == literal]
        assert not caught, _where(caught)


def test_every_notice_kind_is_one_the_engine_never_sends():
    assert not set(NOTICE_KINDS) & set(progress.FAILURE_KINDS)


def test_the_main_processs_own_envelope_has_the_envelope_and_failure_keys():
    """``shellFailure`` (``app/main.js``) is the envelope the window gets when
    no engine answered - a refused message, an engine that could not start
    or stopped mid-reply - so it carries exactly the required keys of the one
    the engine prints; its ``extra`` spread is the progress a pass had shown."""
    [script] = [one for one in _scripts() if one.name == "main.js"]
    [defined] = re.finditer(r"\bfunction\s+shellFailure\s*\(", script.code)
    body = script.pairs[defined.end() - 1] + 1
    while script.code[body].isspace():
        body += 1
    returned = re.compile(r"\s*return\s*").match(script.code, body + 1)
    assert script.code[body] == "{" and returned, "shellFailure no longer returns one object literal"
    envelope = _properties(script, returned.end())
    assert {key for key, _, _ in envelope if not key.startswith("...")} == replies.Envelope.__required_keys__
    [(start, end)] = [(start, end) for key, start, end in envelope if key == "failure"]
    opening = _strip(script, start, end)[0]
    assert script.code[opening] == "{"
    assert {key for key, _, _ in _properties(script, opening)} == replies.Failure.__required_keys__
