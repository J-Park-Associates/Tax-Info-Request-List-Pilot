"""The value rule's bounds: every limit a value in the record is held to, worded once.

Decision 187 made the record untrusted input. A journal is a synced file,
so a line may have been written by another machine, restored from a copy
or typed by hand - and every value in it is obeyed by something: a count is
stored in a column SQLite bounds, a date is parsed by the readers, a Date
Pattern is run over a client's pages. So each value is held to the bounds
the editor holds a person to, worded here once: the editor
(``tracker.manifest``) refuses a value it would never write with these, and
the store's gate (``tracker.store._refuse_a_malformed_line``) refuses a
line carrying one before a table is touched. Each check returns a fixed
phrase naming the class of problem and never the value, because the value
is whatever the line said, and ``""`` for a value that is fine.

**Why it is its own module** (SPEC-architecture-p2 P2.4; the architecture
audit's B-11). These are the gate's bounds, and none of them holds a
record's shape: a year, a count, a length, a stamp, a digest, a name's
characters, a Date Pattern's cost, each judged as a value on its own, with
the phrase it is refused in. Since decision 187 they sat at the foot of
:mod:`tracker.records`, which made the module of the record's shapes also
the home of an analyser read off the standard library's private parser
(``re._parser``, the one import the type checker excuses by name). Here they
sit at layer 0 and import nothing of the package but the layout's name rule
(decision 188), which reads no file, so any module may ask a bound without
loading the record's shapes. ``Override`` came with them because
``OVERRIDE_BOUNDS`` is worded from its two values.

What stays in records is the row checks - ``rule_row_fault``,
``info_problem``, ``household_problem``, ``entry_problem``,
``status_problem`` and the Waits For cell's - because each reads the
record's own tables (``DATE_FIELDS``, ``RULE_LIST_FIELDS``,
``RULE_FLAG_FIELDS``, the Waits For grammar), and a layer 0 module that
imported them would point up at layer 1, the edge the layer table refuses.
Records imports every name here that it reads; it re-exported the rest
until P2.13 pointed their readers here.
"""

from __future__ import annotations

import datetime as dt
import math
import re
import re._parser as _re_parser  # type: ignore[import-not-found]  # typeshed does not stub the private parser
from typing import TypeGuard

from tracker.layout import (
    NAME_MAX_CHARS,
    file_name_part_problem,
    invisible_problem,
    spoofing_problem,
)

# ------------------------------------------------------------ the value rule ----
#
# Decision 187: the record is untrusted input. A journal is a synced file, so
# a line may have been written by another machine, restored from a copy or
# typed by hand - and every value in it is obeyed by something: a count is
# stored in a column SQLite bounds, a date is parsed by the readers, a Date
# Pattern is run over a client's pages. So each value is held here to the
# bounds the editor holds a person to, worded once: the editor
# (``tracker.manifest``) refuses a value it would never write with these, and
# the store's gate (``tracker.store._refuse_a_malformed_line``) refuses a line
# carrying one before a table is touched. Each check returns a fixed phrase
# naming the class of problem and never the value, because the value is
# whatever the line said, and ``""`` for a value that is fine.

#: The years a tax year can be. ``tracker.manifest.YEAR_PATTERN`` is built from
#: them, the app's year inputs are bounded by them, and every path that takes a
#: year from a person checks it against them (``manifest.check_tax_year``).
YEAR_MIN = 1900
YEAR_MAX = 2099
#: What a year outside those bounds is told, wherever it was typed.
YEAR_OUT_OF_RANGE = "Tax year must be between {minimum} and {maximum}, got {year}"
#: The years a date or a stamp in the record may fall in: a tax year's, and
#: the year after the last one, where its deadlines fall.
DATE_YEAR_MIN = YEAR_MIN
DATE_YEAR_MAX = YEAR_MAX + 1
#: The first year a stamp may fall in: the epoch, before which Windows
#: cannot give a time its local day.
STAMP_YEAR_MIN = 1970

#: Characters Windows forbids in file and folder names, and the names it
#: keeps for devices, are the layout's since decision 188 - the name rule
#: for a household or a return is worded there - and so, since P2.5, are
#: the four checks a file-name part is held to
#: (:func:`tracker.layout.file_name_part_problem`), which the identifier
#: and the short title below each ask in their own place in a file name.


def identifier_problem(identifier: str) -> str:
    """Why ``identifier`` cannot begin a working copy's name, or "" if it can.

    Shared by ``manifest.validated``, the desktop app's create path and the
    store's gate, so a bad identifier is refused with the same sentence
    wherever it is typed or read. A character that changes how a name is
    read - a right-to-left override, a zero-width joiner - is refused by code
    point (P290, :func:`tracker.layout.spoofing_problem`): the identifier
    begins every working copy's name, and the override is the classic
    file-name spoof. The store asks this too, so a stored identifier holding
    one is a refused line - the record is untrusted input (decision 187).
    Only that narrow set: a no-break space or a soft hyphen an ordinary paste
    left in an older record is not a reason to stop its household, and is
    refused only where a person types (:func:`typed_identifier_problem`).
    """
    return file_name_part_problem(identifier, begins=True)


def document_problem(document: str) -> str:
    """Why ``document`` may not be a request's Document title, or "" if it
    may: a character that changes how a name is read - a right-to-left
    override, a zero-width space - is refused by code point (P301,
    :func:`tracker.layout.spoofing_problem`).

    The Document names a working copy whenever the row has no short name of
    its own (``manifest.derived_short_title``), and an issuer row by the
    entity it names, so a spoofing character held there reaches every file
    the pass names - the gate that reads the identifier and the short name
    (P290) must read this too. The whole title is judged, not the derived
    cut: the issuer's entity is a substring of it, and a spoofing character
    anywhere in a title is never legitimate. Only that narrow set, as in
    :func:`identifier_problem`: this is the store's gate, and a no-break
    space or a soft hyphen an ordinary paste left in an older Document is
    not a reason to stop its household. The editor asks it of every row's
    Document, typed or held (``manifest.item_from_fields``).
    """
    return spoofing_problem(document) or ""


#: The most characters a typed identifier may have (P291): the width a
#: household or return folder name has, for the same reason - it begins
#: every file name - and so that bound itself (``layout.NAME_MAX_CHARS``),
#: never typed again (P2.5).
IDENTIFIER_MAX_CHARS = NAME_MAX_CHARS


def typed_identifier_problem(identifier: str) -> str:
    """Why a *typed* identifier is refused: :func:`identifier_problem`, then
    the full invisible-character rule (:func:`tracker.layout.invisible_problem`),
    then :data:`IDENTIFIER_MAX_CHARS`, or "" if it passes.

    The length is a typing limit and not the store's gate, which keeps the
    unbounded :func:`identifier_problem`: a record's identifier is not
    re-judged by what a person may type. Said before the path-room check,
    so a long identifier is told it is long and never to shorten the
    household. Asked of a new or changed identifier only: one the list
    already holds, sent back as it is spelt, is asked
    :func:`identifier_problem` alone (``manifest.item_from_fields``, P291).
    """
    if problem := identifier_problem(identifier):
        return problem
    if (hidden := invisible_problem(identifier)) is not None:
        return hidden
    if len(identifier) > IDENTIFIER_MAX_CHARS:
        return (f"may have at most {IDENTIFIER_MAX_CHARS} characters, got {len(identifier)} "
                f"(it begins a file name)")
    return ""


#: The most characters a short title may have (decision 144). The owner's
#: style: ``A01 - W-2\A01 - W-2 - TY2025.pdf``, a short title of about
#: twenty characters, so a real household's name fits under the real root.
SHORT_TITLE_MAX = 20


def short_title_problem(short_title: str) -> str:
    """Why ``short_title`` cannot name a working copy, or "" if it can.

    Refused rather than sanitised, as an identifier is: the name a person
    types is the name every working copy carries, or they are told why not.
    Only the spoofing characters are refused here (P290), because this is
    also the store's gate; the editor asks :func:`typed_short_title_problem`.
    """
    if len(short_title) > SHORT_TITLE_MAX:
        return f"may have at most {SHORT_TITLE_MAX} characters, got {len(short_title)}"
    return file_name_part_problem(short_title, begins=False)


def typed_short_title_problem(short_title: str) -> str:
    """Why a *typed* short title is refused: :func:`short_title_problem`,
    then the full invisible-character rule, or "" if it passes (P290)."""
    if problem := short_title_problem(short_title):
        return problem
    return invisible_problem(short_title) or ""


class Override:
    """Accountant judgment values that beat the automated rules.

    ``ACCEPTED`` treats the row as Received despite the checks, and carries
    a reason (``manifest.OVERRIDE_REASONS``, decision 116). ``NOT_APPLICABLE``
    says the request does not apply this year - shown to people with the
    row's own year (``manifest.override_label``) - and takes the row out of
    every count, every reminder and the active table.

    ``RETIRED`` is the retired-value rule of decision 104 applied to a
    value: the spelling journals written before decision 116 hold for the
    second value, folded to its successor on every read by
    ``manifest._override`` and never written again.
    """

    ACCEPTED = "Accepted"
    NOT_APPLICABLE = "Not Applicable"

    ALL = (ACCEPTED, NOT_APPLICABLE)
    RETIRED: dict[str, str] = {"Waived": NOT_APPLICABLE}


#: The bounds on a request's two numbers, and where the editor's number
#: inputs take theirs from - through the API's vocabulary, never typed in
#: the page. The maximums are decision 187's: a count no statement reaches
#: and a size past any document, so no value a person typed is refused, and
#: SQLite's own limit (past 2**63) is never met.
MIN_EXPECTED_COUNT = 1
MAX_EXPECTED_COUNT = 9_999
MIN_SIZE_KB_FLOOR = 0
MAX_SIZE_KB = 1_048_576
#: The other numbers the record holds: how many files a request has, the
#: stage of a draft, a request's position in its list.
MAX_FILE_COUNT = 9_999
MAX_STAGE = 9
MAX_ROW = 9_999
#: An original's size as its row records it: any file the inbox can hold.
MAX_ROW_SIZE_KB = 1_073_741_824
#: One line of text (a name, a label, a location) and long text (a reason,
#: a note, the evidence).
TEXT_MAX = 1_000
LONG_TEXT_MAX = 20_000
#: A Date Pattern's shape (decision 187). It is run over every line of a
#: client's page, so a pattern that backtracks without end would hold a pass
#: on one document; the shape rule below admits every pattern the Period
#: derives and every one a person plausibly types, and nothing that can run
#: away. Measured on a 500-character line: three open-ended repetitions take
#: 9.6 s, one open-ended and two bounded to 20 take 0.22 s - and so does one
#: open-ended beside seven ``?``, because an optional is a choice point too
#: (the review's M1): ``\d?`` twenty-four times took 3.3 s on 24 digits.
DATE_PATTERN_MAX = 200
#: Repetitions that can repeat more than once.
DATE_PATTERN_REPEATS_MAX = 3
#: Every variable repetition, ``?`` included (the orchestrator's amendment
#: of SPEC-187 ruling 5).
DATE_PATTERN_VARIABLE_MAX = 8
DATE_PATTERN_OPEN_MAX = 1
DATE_PATTERN_BOUND_MAX = 20
#: How many ways one start of a line may be tried, at most (:func:`_ways`):
#: counted through every repetition - a fixed ``{1}`` included, so wrapping
#: a chain hides nothing - an alternation's branches added, an open-ended
#: repetition counted as the longest line a pattern is run over
#: (``content_check.DATE_LINE_MAX``). The limit is measured on 500-character
#: lines of digits with no literal ending the engine can short-cut (the
#: re-check of decision 187's review, M1b): at 16,384 ways the slowest
#: pattern admitted took about a quarter of a second, where 220,500 ways -
#: one open-ended and two bounded to 20 - took 0.85 s. Every pattern the
#: Period derives is tried at most 176 ways.
DATE_PATTERN_OPEN_WIDTH = 500
DATE_PATTERN_WAYS_MAX = 16_384
#: What a pattern may cost, at most: its ways times the widest match of its
#: bounded parts (:func:`_width`), because every way tried may be followed
#: by that much matching (the second re-check of decision 187's review,
#: M1c: ``(?:\d\d){200}`` adds no way and 400 characters of work to each,
#: 15 s on one line). A fixed ``{n}`` and a lookaround count toward the
#: width; an open-ended part counts one, its length being in the ways
#: already. Every derived pattern costs at most 6,688.
DATE_PATTERN_COST_MAX = 200_000

#: The fixed phrases. Each names the class of problem; none names the value.
COUNT_BOUNDS = "must be a whole number from {minimum} to {maximum}"
NUMBER_BOUNDS = "must be a number from {minimum} to {maximum}"
DATE_BOUNDS = f"must be a date written YYYY-MM-DD, from {DATE_YEAR_MIN} to {DATE_YEAR_MAX}"
STAMP_BOUNDS = f"must be a time written YYYY-MM-DDTHH:MM:SSZ, from {STAMP_YEAR_MIN} to {DATE_YEAR_MAX}"
FLAG_BOUNDS = "must be true or false"
DIGEST_BOUNDS = "must be blank or 64 lowercase hexadecimal characters"
#: The longest writer's name a record line may carry (decision 159): a
#: machine's name, never a sentence.
HOST_MAX = 64
HOST_BOUNDS = (f"must be a machine's name: at most {HOST_MAX} printable characters, with no space "
               "and no path separator")
TEXT_BOUNDS = f"must be one line of text of at most {TEXT_MAX} characters, with no control character"
LONG_TEXT_BOUNDS = f"must be text of at most {LONG_TEXT_MAX} characters, with no NUL"
TEXT_LIST_BOUNDS = "must be a list of text"
NAME_BOUNDS = f"must be text of at most {TEXT_MAX} characters, with no NUL"
OVERRIDE_BOUNDS = f"must be blank, {Override.ACCEPTED} or {Override.NOT_APPLICABLE}"
BLANK_BOUNDS = "may not be blank"
DATE_PATTERN_TOO_LONG = f"may have at most {DATE_PATTERN_MAX} characters"
DATE_PATTERN_NOT_A_REGEX = "is not a valid regex"
DATE_PATTERN_NESTED = "repeats something that itself repeats"
DATE_PATTERN_ALTERNATES = "repeats an alternation (a | inside a repetition)"
DATE_PATTERN_REFERS_BACK = "repeats a back-reference"
DATE_PATTERN_TOO_MANY = f"has more than {DATE_PATTERN_REPEATS_MAX} repetitions"
DATE_PATTERN_TOO_MANY_OPTIONAL = (f"has more than {DATE_PATTERN_VARIABLE_MAX} variable repetitions "
                                  f"(?, *, + or {{m,n}})")
DATE_PATTERN_TOO_MANY_WAYS = "could try too many ways to match one line"
DATE_PATTERN_TOO_COSTLY = "could do too much matching on one line"
DATE_PATTERN_TOO_OPEN = f"has more than {DATE_PATTERN_OPEN_MAX} open-ended repetition (+, * or {{n,}})"
DATE_PATTERN_TOO_WIDE = f"repeats more than {DATE_PATTERN_BOUND_MAX} times in a bounded repetition"

_HEX_DIGEST = re.compile(r"[0-9a-f]{64}")
_ISO_DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
_STAMP = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z")
_ONE_LINE_REFUSED = re.compile(r"[\x00-\x1f\x7f  ]")


def _is_number(value: object) -> TypeGuard[int | float]:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def count_problem(value: object, minimum: int, maximum: int) -> str:
    """:data:`COUNT_BOUNDS` for anything but a whole number from ``minimum``
    to ``maximum`` - a number, never its text, never a boolean."""
    if (not _is_number(value) or not math.isfinite(value) or value != int(value)
            or not minimum <= value <= maximum):
        return COUNT_BOUNDS.format(minimum=minimum, maximum=maximum)
    return ""


def number_problem(value: object, minimum: float, maximum: float) -> str:
    """:data:`NUMBER_BOUNDS` for anything but a finite number in the bounds."""
    if not _is_number(value) or not math.isfinite(value) or not minimum <= value <= maximum:
        return NUMBER_BOUNDS.format(minimum=minimum, maximum=maximum)
    return ""


def date_problem(value: object) -> str:
    """:data:`DATE_BOUNDS` for anything but a real calendar date in the
    record's years, as a date or as its ISO text. Blank is the caller's to
    allow."""
    if isinstance(value, dt.datetime):
        return DATE_BOUNDS
    if isinstance(value, dt.date):
        day = value
    elif isinstance(value, str) and _ISO_DATE.fullmatch(value):
        try:
            day = dt.date.fromisoformat(value)
        except ValueError:
            return DATE_BOUNDS
    else:
        return DATE_BOUNDS
    return "" if DATE_YEAR_MIN <= day.year <= DATE_YEAR_MAX else DATE_BOUNDS


def stamp_problem(value: object) -> str:
    """:data:`STAMP_BOUNDS` for anything but a stamp as ``ledger.stamp``
    writes it - ``YYYY-MM-DDTHH:MM:SSZ``, the one form it has ever written -
    in 1970 to 2100. Not before 1970, because Windows cannot turn a time
    before the epoch into a local day (the review's S1)."""
    if not isinstance(value, str) or not _STAMP.fullmatch(value):
        return STAMP_BOUNDS
    try:
        moment = dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")
    except ValueError:
        return STAMP_BOUNDS
    return "" if STAMP_YEAR_MIN <= moment.year <= DATE_YEAR_MAX else STAMP_BOUNDS


def received_problem(value: object) -> str:
    """:data:`DATE_BOUNDS` for an index row's Received that is neither a
    date nor an ISO date and time. The pass writes the day; a row seeded
    from the index workbook (``ledger.IMPORTED``, decisions 87 and 102) may
    carry the cell's time after it, and a row already moved must not be
    refused for that."""
    if not date_problem(value):
        return ""
    if isinstance(value, str) and len(value) <= 40 and _ISO_DATE.match(value):
        try:
            moment = dt.datetime.fromisoformat(value)
        except ValueError:
            return DATE_BOUNDS
        return "" if DATE_YEAR_MIN <= moment.year <= DATE_YEAR_MAX else DATE_BOUNDS
    return DATE_BOUNDS


def flag_problem(value: object) -> str:
    """:data:`FLAG_BOUNDS` for anything but ``true``, ``false``, 0 or 1. Never
    ``"no"``: the word is truthy, so a reader that asked ``bool()`` would
    read a hand-typed no as yes."""
    if isinstance(value, bool) or (type(value) is int and value in (0, 1)):
        return ""
    return FLAG_BOUNDS


def digest_problem(value: object) -> str:
    """:data:`DIGEST_BOUNDS` for anything but blank or a SHA-256 in hex."""
    if value == "" or (isinstance(value, str) and _HEX_DIGEST.fullmatch(value)):
        return ""
    return DIGEST_BOUNDS


def host_problem(value: object) -> str:
    """:data:`HOST_BOUNDS` for anything but a machine's name as a record line
    carries its writer (decision 159): text, not blank, at most
    :data:`HOST_MAX` characters, printable (no control or direction
    character), no whitespace at all - a machine's name has none, so
    ``"VM "`` cannot pass for ``vm`` as another machine (159's final
    review, SF3) - and no path separator. The one rule of a writer's name:
    the store's gate holds every line to it, and a reader that shows a
    writer without the gate (the view's Summary, recover's difference)
    asks it before showing one."""
    if (isinstance(value, str) and value and len(value) <= HOST_MAX and value.isprintable()
            and not any(ch.isspace() for ch in value) and "/" not in value and "\\" not in value):
        return ""
    return HOST_BOUNDS


def text_problem(value: object, *, long: bool = False) -> str:
    """Why ``value`` is not text the record may hold, or ``""``.

    One line (a name, a label, a location): no line break or control
    character, at most :data:`TEXT_MAX` characters. ``long`` (a reason, a
    note, the evidence): no NUL, at most :data:`LONG_TEXT_MAX`."""
    if long:
        if not isinstance(value, str) or len(value) > LONG_TEXT_MAX or "\x00" in value:
            return LONG_TEXT_BOUNDS
        return ""
    if not isinstance(value, str) or len(value) > TEXT_MAX or _ONE_LINE_REFUSED.search(value):
        return TEXT_BOUNDS
    return ""


def name_problem(value: object) -> str:
    """:data:`NAME_BOUNDS` for anything but a file's own name, a key or a
    location: text of at most :data:`TEXT_MAX` characters with no NUL.

    Wider than one line on purpose (the review's M5): these come from real
    files, and decision 104 files a POSIX name holding a control character.
    They are never joined onto a path as a label is - a location is judged
    by the layout's place rule instead - so refusing one would stop the
    household every pass with an original already moved and no row."""
    if not isinstance(value, str) or len(value) > TEXT_MAX or "\x00" in value:
        return NAME_BOUNDS
    return ""


def text_list_problem(value: object, *, long: bool = False) -> str:
    """:data:`TEXT_LIST_BOUNDS` for anything but a list of text - one-line,
    or ``long``."""
    if not isinstance(value, (list, tuple)) or any(text_problem(one, long=long) for one in value):
        return TEXT_LIST_BOUNDS
    return ""


_REPEATS = frozenset({_re_parser.MAX_REPEAT, _re_parser.MIN_REPEAT, _re_parser.POSSESSIVE_REPEAT})
_REFERS_BACK = frozenset({_re_parser.GROUPREF, _re_parser.GROUPREF_EXISTS})


def _walk(pattern: object):
    """Every ``(op, argument)`` of a parsed pattern, at any depth."""
    if isinstance(pattern, _re_parser.SubPattern):
        for op, argument in pattern:
            yield op, argument
            yield from _walk(argument)
    elif isinstance(pattern, (tuple, list)):
        for one in pattern:
            yield from _walk(one)


def _ways(pattern: object) -> int:
    """How many ways one start of a line may be tried, at most - a
    sequence's parts multiplied, a branch's alternatives added, and every
    repetition counted through what it holds: an optional as skipping it or
    any way through it, a counted ``{m,n}`` as its choice of count times the
    ways through each copy, an open-ended one as the longest line. Nothing
    inside a repetition is left uncounted, ``{1}`` included."""
    if not isinstance(pattern, _re_parser.SubPattern):
        return 1
    total = 1
    for op, argument in pattern:
        if op in _REPEATS:
            low, high, inside = argument
            if high == _re_parser.MAXREPEAT:
                total *= DATE_PATTERN_OPEN_WIDTH
            elif high == 1:
                total *= (1 - low) + _ways(inside)
            else:
                total *= (high - low + 1) * _ways(inside) ** high
        elif op is _re_parser.BRANCH:
            total *= sum(_ways(one) for one in argument[1])
        elif op is _re_parser.GROUPREF_EXISTS:
            total *= max(_ways(argument[1]), _ways(argument[2]))
        elif op is _re_parser.SUBPATTERN:
            total *= _ways(argument[-1])
        elif op in (_re_parser.ASSERT, _re_parser.ASSERT_NOT):
            total *= _ways(argument[1])
        elif op is _re_parser.ATOMIC_GROUP:
            total *= _ways(argument)
    return total


def _width(pattern: object) -> int:
    """The widest match of a pattern's bounded parts - how much matching may
    follow each way it is tried. A fixed ``{n}`` counts n times what it
    holds, a lookaround its own width, a branch its widest alternative, a
    back-reference 20, an open-ended part one, and a zero-width assertion
    one."""
    if not isinstance(pattern, _re_parser.SubPattern):
        return 1
    width = 0
    for op, argument in pattern:
        if op in _REPEATS:
            _low, high, inside = argument
            width += _width(inside) * (1 if high == _re_parser.MAXREPEAT else high)
        elif op is _re_parser.BRANCH:
            width += max(_width(one) for one in argument[1])
        elif op is _re_parser.SUBPATTERN:
            width += _width(argument[-1])
        elif op is _re_parser.ATOMIC_GROUP:
            width += _width(argument)
        elif op in (_re_parser.ASSERT, _re_parser.ASSERT_NOT):
            width += _width(argument[1])
        elif op is _re_parser.GROUPREF_EXISTS:
            width += max(_width(argument[1]), _width(argument[2]))
        elif op is _re_parser.GROUPREF:
            width += DATE_PATTERN_BOUND_MAX
        else:
            # Everything else counts one - a zero-width assertion (\b, \B,
            # ^, $, \A, \Z) included, because it is a test at every step
            # though it matches nothing (the third re-check: a group padded
            # with \B did unbounded work per counted character).
            width += 1
    return width


def date_pattern_problem(pattern: object) -> str:
    """Why a Date Pattern may not be run over a client's page, or ``""``.

    It must be text of at most :data:`DATE_PATTERN_MAX` characters that
    compiles, and pass a shape rule read off the standard library's own
    parser (``re._parser``) - no second engine and no whitelist. A
    repetition is anything that can repeat more than once or can match a
    varying number of times - ``?`` included, because an optional is a
    choice point (the review's M1):

    - a repetition may not contain another or a back-reference, at any
      depth, nor an alternation unless it is a plain optional (``?``), whose
      ways are counted like any other (``(?:Dec|12)?`` is a date pattern);
    - at most :data:`DATE_PATTERN_VARIABLE_MAX` variable repetitions, of
      which at most :data:`DATE_PATTERN_REPEATS_MAX` can repeat more than
      once and at most :data:`DATE_PATTERN_OPEN_MAX` is open-ended (``+``,
      ``*``, ``{n,}``);
    - every bounded one repeats at most :data:`DATE_PATTERN_BOUND_MAX` times;
    - the ways one start of a line may be tried, counted through every
      repetition, stay within :data:`DATE_PATTERN_WAYS_MAX` (:func:`_ways`);
    - and those ways times the widest match of the bounded parts
      (:func:`_width`) stay within :data:`DATE_PATTERN_COST_MAX`.

    The rule bounds the cost by reading the pattern; it is not a clock
    (principle 8). A time bound that needs no analysis comes with the
    judgment in a child the pass can stop.

    It applies to a derived pattern too, and every pattern the Period
    derives passes.
    """
    if not isinstance(pattern, str):
        return TEXT_BOUNDS
    if len(pattern) > DATE_PATTERN_MAX:
        return DATE_PATTERN_TOO_LONG
    try:
        re.compile(pattern)
        parsed = _re_parser.parse(pattern)
    except (re.error, RecursionError, OverflowError):
        return DATE_PATTERN_NOT_A_REGEX

    def repeats(argument) -> bool:
        low, high, _inside = argument
        return low != high or high > 1

    found = [argument for op, argument in _walk(parsed) if op in _REPEATS and repeats(argument)]
    for _low, high, inside in found:
        for op, argument in _walk(inside):
            if op in _REPEATS and repeats(argument):
                return DATE_PATTERN_NESTED
            if op is _re_parser.BRANCH and high > 1:
                return DATE_PATTERN_ALTERNATES
            if op in _REFERS_BACK:
                return DATE_PATTERN_REFERS_BACK
    variable = [(low, high) for low, high, _inside in found if low != high]
    if len(variable) > DATE_PATTERN_VARIABLE_MAX:
        return DATE_PATTERN_TOO_MANY_OPTIONAL
    if sum(high > 1 for _low, high in variable) > DATE_PATTERN_REPEATS_MAX:
        return DATE_PATTERN_TOO_MANY
    if sum(high == _re_parser.MAXREPEAT for _low, high in variable) > DATE_PATTERN_OPEN_MAX:
        return DATE_PATTERN_TOO_OPEN
    if any(high != _re_parser.MAXREPEAT and high > DATE_PATTERN_BOUND_MAX for _low, high in variable):
        return DATE_PATTERN_TOO_WIDE
    ways = _ways(parsed)
    if ways > DATE_PATTERN_WAYS_MAX:
        return DATE_PATTERN_TOO_MANY_WAYS
    if ways * max(1, _width(parsed)) > DATE_PATTERN_COST_MAX:
        return DATE_PATTERN_TOO_COSTLY
    return ""


def _field(name: str, problem: str) -> str:
    return f"'{name}' {problem}" if problem else ""


def _first(*problems: str) -> str:
    return next((one for one in problems if one), "")
