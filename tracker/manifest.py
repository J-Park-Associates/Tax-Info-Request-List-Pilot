"""The request list: its schema, its validation, and its reading from and
writing to the record (component 1, docs/ROADMAP.md).

**The manifest is the record's request list** (decision 104). It is the
ten columns an accountant edits (:data:`COLUMNS`, whose headers are
:data:`HEADERS`) and the engagement's own details
(:class:`tracker.records.EngagementInfo`), and it lives in exactly one
place: the engagement's record - the journal beside the client's files
(:mod:`tracker.ledger`) folded into the store on the machine
(:mod:`tracker.store`, ``docs/storage.md``). There is no workbook. Until
this decision the list was a workbook (the file
``registry.LEGACY_MANIFEST_FILENAME`` names), read once a pass and
journalled as it changed; the owner retired it on 2026-09-19 - "I don't
want anything to do with the Excel manifest anymore. I just want it all on
the database." - and the workbook half of this module is set aside,
outside the tree, in ``Retired - Excel manifest``.

So this module does four things with that list:

- **it says what a row is.** :class:`RequestItem`, the column constants,
  :data:`COLUMN_HELP` (the sentence the app's editor shows under each
  heading) and the defaults - the one schema the store's ``requests``
  table, the API's ``edit`` command and the catalog in
  :mod:`tracker.templates` all write against;
- **it validates it, as a function on records.** The checks the sheet's
  loader used to make cell by cell are :func:`item_from_fields` (one row
  from plain values - the editor's JSON, a catalog spec) and
  :func:`validated` (the list: identifiers, duplicates without case, the
  counts, the date pattern compiled or derived from the Period, the
  narrowing names), each refusal naming the row and the column in one
  sentence. Every path that stores rules or routes against a catalog goes
  through them, so the derived year check the harnesses used to get from a
  workbook round trip is the same check, made once, here;
- **it reads it** (:func:`load_manifest`, :func:`load_engagement_info`):
  from the record - the rules as the last edit left them, each row's
  status, and the keywords a filing taught - after
  :func:`tracker.store.follow_the_journal` has brought the store up to
  the journal. A folder with no journal is nobody's engagement and is
  refused by sentence (:data:`NOT_AN_ENGAGEMENT`);
- **it writes it, at two moments and no others**: :func:`create_engagement`
  writes an engagement's first list and details as one ``rules_changed``
  event, and :func:`save_rules` writes a person's edit as one - exactly
  the rows that changed, the identifiers removed, the details that moved,
  and nothing at all when nothing did. Both go through
  :func:`tracker.store.record` under the engagement lock, so the journal
  is written first and the fold is one transaction. The app's editor is
  the only way a rule is entered; there is no import and no export.

Why the writes came back to this module, having left it in decision 103:
they left because a workbook was the person's file and the machine only
read it. The person's file is the record now, and the module that owns
the schema and the validation is the one that must own the two writes,
or the rows in the journal would be shaped by somebody else. It reaches
``store``, ``ledger`` and ``locking`` at call time - an in-layer edge,
closed where an edge is allowed to close (``tests/test_layers.py``) - and
imports :mod:`tracker.records` and nothing else of the package at load
time.

``row`` is the request's 1-based position in the list. It is part of the
rule: a row inserted in the middle moves every row below it, and those
rows are recorded as changed, because a person reordered them and the
record says so.

It also owns *how* the machine's own small files are written. The content
cache and the app's settings file go through :func:`atomic_replacement` -
a uniquely named temp file ending in ``TEMP_SUFFIX``, swapped in whole with
``os.replace`` - so a killed run never leaves a half-written file where a
reader will trust it. These move with ``fsio`` in decision 105.

The *records* this module reads and writes - :class:`EngagementInfo`,
:class:`StatusUpdate`, the details' field table, the serialisation of a
rule row - live in :mod:`tracker.records` since decision 100.
:class:`RequestItem` stays here: it is the schema of the list a person
edits, not a record of what the machine decided.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import secrets
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, replace
from pathlib import Path

# The records this module reads and writes live in tracker/records.py
# (decision 100): they are the shapes, this is the list. An in-layer
# import, and the only one that way round - nothing in records imports
# the manifest.
from tracker.records import (
    COL_IDENTIFIER,
    RULE_FIELDS,
    EngagementInfo,
    StatusUpdate,
    identifier_key,
    info_to_json,
    rule_from_json,
    rule_to_json,
)

log = logging.getLogger("tracker.manifest")

# ---------------------------------------------------------------- schema ----

COL_DOCUMENT = "Document"
COL_PERIOD = "Period"
COL_EXPECTED_COUNT = "Expected Count"
COL_ALLOWED_EXTENSIONS = "Allowed Extensions"
COL_MIN_SIZE_KB = "Min Size KB"
COL_REQUIRED_KEYWORDS = "Required Keywords"
COL_ANY_KEYWORDS = "Any Keywords"
COL_DATE_PATTERN = "Date Pattern"
COL_MANUAL_OVERRIDE = "Manual Override"
COL_STATUS = "Status"
COL_RECEIVED_DATE = "Received Date"
COL_FILE_COUNT = "File Count"
COL_VALIDATION_NOTES = "Validation Notes"

#: Each column's key in the record and the API, beside its header: the ten
#: columns a person edits, in the order the editor shows them. The keys are
#: ``records.RULE_FIELDS`` less the two the person never types (``row`` is
#: the position, ``date_pattern_derived`` is what ``validated()`` decided),
#: and the assertion below holds the two lists together.
COLUMNS: tuple[tuple[str, str], ...] = (
    (COL_IDENTIFIER, "identifier"),
    (COL_DOCUMENT, "document"),
    (COL_PERIOD, "period"),
    (COL_EXPECTED_COUNT, "expected_count"),
    (COL_ALLOWED_EXTENSIONS, "allowed_extensions"),
    (COL_MIN_SIZE_KB, "min_size_kb"),
    (COL_REQUIRED_KEYWORDS, "required_keywords"),
    (COL_ANY_KEYWORDS, "any_keywords"),
    (COL_DATE_PATTERN, "date_pattern"),
    (COL_MANUAL_OVERRIDE, "manual_override"),
)
#: The ten headers, in order. The roadmap's schema table lists exactly
#: these (``tests/test_single_source.py`` holds it to that), the Status
#: Report draws them, and every message that names a column uses one.
HEADERS = tuple(header for header, _ in COLUMNS)
assert tuple(field for _, field in COLUMNS) == tuple(
    f for f in RULE_FIELDS if f not in ("row", "date_pattern_derived")
)

DEFAULT_EXPECTED_COUNT = 1
DEFAULT_MIN_SIZE_KB = 5
#: The bounds ``validated()`` and ``item_from_fields()`` enforce on the
#: two numbers, and where the editor's number inputs take their minimum
#: from - through the API's vocabulary, never typed in the page.
MIN_EXPECTED_COUNT = 1
MIN_SIZE_KB_FLOOR = 0

#: The one sentence the editor shows under each heading, by field. The
#: roadmap's schema table carries the same sentences in its Purpose column
#: on purpose: one text, two places a person reads it.
COLUMN_HELP: dict[str, str] = {
    "identifier": "Names the request and its folder; matched by prefix, so A100 and BS01 both work",
    "document": "What the request is called to people",
    "period": "The period asked for, e.g. TY2025 or Dec 2025; a year in it is the year check",
    "expected_count": "How many files are due; counted over distinct valid files",
    "allowed_extensions": "File types accepted, comma-separated; blank means the safe default, * means any type",
    "min_size_kb": "Files smaller than this are rejected as placeholders",
    "required_keywords": (
        "Every one of these must appear in the document (a keyword may hold alternatives with | "
        "and phrases wanted together with +)"
    ),
    "any_keywords": "At least one of these must appear; a keyword reads the same way",
    "date_pattern": (
        "Blank with a year in Period checks for that year; * turns the year check off; "
        "a typed regex wins"
    ),
    "manual_override": "Accepted counts as Received; Waived takes the request out of every count",
}
assert set(COLUMN_HELP) == {field for _, field in COLUMNS}

#: What a blank Allowed Extensions means. A blank used to mean "accept
#: anything", which is easy to leave by accident and lets an .exe count as a
#: document; accepting anything now has to be said out loud with "*".
DEFAULT_EXTENSIONS = ("pdf", "xlsx", "csv")
ANY_EXTENSION = "*"
#: A blank Date Pattern on a row whose Period names a year checks for that
#: year; "*" says "no year check" out loud. The year was already typed once,
#: in Period - typing it again as a regex was the redundancy, and not typing
#: it was a 2024 form satisfying a TY2025 request.
NO_DATE_CHECK = "*"
#: The years a tax year can be. The pattern below is built from them, the
#: app's year inputs are bounded by them, and every path that takes a year
#: from a person checks it against them through :func:`check_tax_year`.
YEAR_MIN = 1900
YEAR_MAX = 2099
#: What a year outside those bounds is told, wherever it was typed.
YEAR_OUT_OF_RANGE = "Tax year must be between {minimum} and {maximum}, got {year}"
#: A four-digit year standing on its own. The digit guards keep an account
#: number like 120250 from being read as "2025". Used wherever a year is
#: found or shifted: the derived year check, rollover, the catalog.
YEAR_PATTERN = re.compile(
    r"(?<!\d)(?:" + "|".join(str(c) for c in range(YEAR_MIN // 100, YEAR_MAX // 100 + 1))
    + r")\d{2}(?!\d)"
)
_PERIOD_YEAR = YEAR_PATTERN

#: Characters Windows forbids in file and folder names, plus control
#: characters - the one list, for identifiers and for sanitising names.
_ILLEGAL_PUNCTUATION = '\\/:*?"<>|'
WINDOWS_ILLEGAL_CHARS = re.compile("[" + re.escape(_ILLEGAL_PUNCTUATION) + r"\x00-\x1f]")
WINDOWS_ILLEGAL_CHARS_TEXT = " ".join(_ILLEGAL_PUNCTUATION)
#: How a date is asked for on a command line or in the wizard.
ISO_DATE_HINT = "YYYY-MM-DD"

#: Characters an identifier may not contain. The identifier becomes the
#: prefix of a Windows folder name and is matched back by that prefix, so
#: anything the filesystem would alter (``WINDOWS_ILLEGAL_CHARS``) or strip
#: (a trailing dot) would leave the scanner unable to
#: find the folder scaffold just made — a permanent "folder not found".
_ILLEGAL_IDENTIFIER_CHARS = WINDOWS_ILLEGAL_CHARS



class Status:
    """Scanner-resolved status values (plain constants, stored as strings)."""

    MISSING = "Missing"
    PARTIAL = "Partial"
    FAILED = "Failed Validation"
    RECEIVED = "Received"
    PENDING_SYNC = "Pending Sync"

    ALL = (MISSING, PARTIAL, FAILED, RECEIVED, PENDING_SYNC)
    #: The client still owes us something: what the reminder asks for and
    #: what ``summarize`` counts as outstanding, decided once.
    OUTSTANDING = (MISSING, PARTIAL, FAILED)


#: What a row with no status yet is called wherever a count is shown: it
#: has been requested and nothing has been looked at. Not a Status, because
#: the scanner never writes it.
UNSCANNED_LABEL = "Requested"
#: How ``Summary.line`` joins its counts, and what it says with no rows.
SUMMARY_SEPARATOR = " · "
SUMMARY_EMPTY = "no requests"

#: The temp file an atomic save lands in first. Nothing is deferred and
#: nothing is quarantined: a write lands whole or not at all.
TEMP_SUFFIX = ".tmp"


class Override:
    """Accountant judgment values that beat the automated rules."""

    ACCEPTED = "Accepted"  # treat as Received despite failed checks
    WAIVED = "Waived"      # item no longer needed

    ALL = (ACCEPTED, WAIVED)



class ManifestError(Exception):
    """A request list could not be read, parsed, or validated."""


#: What a reader says of a folder that holds no journal: it is not an
#: engagement, whatever else is in it. The journal's file name is filled in
#: at call time by the reader, because this module does not import the
#: ledger at load time.
NOT_AN_ENGAGEMENT = "{name}: no record here ({ledger}); it is not an engagement"


@dataclass(frozen=True, slots=True)
class RequestItem:
    """One request: the person's rule, and what the record says about it.

    ``records.RULE_FIELDS`` names the person's half - the ten columns
    (:data:`COLUMNS`) plus ``row``, the request's 1-based position in the
    list - and that half is what a ``rules_changed`` event and the
    store's ``requests`` table carry. The four status fields are the
    record's: ``validated()`` leaves them at their defaults and
    :func:`load_manifest` fills them from the store's ``statuses``.
    """

    identifier: str
    document: str
    period: str = ""
    expected_count: int = DEFAULT_EXPECTED_COUNT
    allowed_extensions: tuple[str, ...] = ()   # lowercase, no leading dot
    min_size_kb: int = DEFAULT_MIN_SIZE_KB
    required_keywords: tuple[str, ...] = ()
    any_keywords: tuple[str, ...] = ()
    date_pattern: str = ""                     # validated to compile on load
    date_pattern_derived: bool = False         # True: made from Period's year, not typed
    manual_override: str = ""                  # "", Override.ACCEPTED, Override.WAIVED
    status: str = ""                           # the record's, never typed
    received_date: dt.date | None = None
    file_count: int | None = None
    validation_notes: str = ""
    row: int = 0                               # 1-based position in the list

    @property
    def label(self) -> str:
        """``A01 - W-2 Wage Statements (TY2025)`` - how a request is named to people."""
        text = label_for(self.identifier, self.document)
        return f"{text} ({self.period})" if self.period else text

    @property
    def expected_text(self) -> str:
        """``2 files expected`` when more than one file is due, else ``""``."""
        return EXPECTED_PATTERN.format(n=self.expected_count) if self.expected_count > 1 else ""


def shift_years(text: str, delta: int) -> str:
    """Move every four-digit year in ``text`` by ``delta``.

    Shifting rather than substituting one fixed year keeps *relative* periods
    correct: on a 2025 -> 2026 roll, a row asking for the TY2024 prior-year
    return correctly comes to ask for TY2025.
    """
    if not text or not delta:
        return text
    return YEAR_PATTERN.sub(lambda m: str(int(m.group(0)) + delta), text)


def shift_item(item: RequestItem, delta: int) -> RequestItem:
    """``item`` with every year in its document, period and typed date pattern moved.

    A derived year check is left alone: the shifted Period derives it again.
    """
    if not delta:
        return item
    return replace(
        item,
        document=shift_years(item.document, delta),
        period=shift_years(item.period, delta),
        date_pattern="" if item.date_pattern_derived else shift_years(item.date_pattern, delta),
    )


def detect_year(items: Iterable[RequestItem]) -> int | None:
    """The tax year a list of rows is about, inferred from its own rows.

    The most common year across periods and typed date rules wins; ties go
    to the later year. None when nothing carries a year at all.
    """
    from collections import Counter

    years: Counter[int] = Counter()
    for item in items:
        for text in (item.period, "" if item.date_pattern_derived else item.date_pattern):
            for match in YEAR_PATTERN.findall(text or ""):
                years[int(match)] += 1
    if not years:
        return None
    best = max(years.values())
    return max(year for year, count in years.items() if count == best)


#: How a request's parts are joined into one name: the README line, the
#: request folder and the working copy all use it.
LABEL_SEPARATOR = " - "


def label_for(*parts: str) -> str:
    """``A01 - W-2 Wage Statements`` from its parts, blanks dropped."""
    return LABEL_SEPARATOR.join(part for part in parts if part)


#: How a multi-file request says so, everywhere (the README, the reminder,
#: the app's wizard preview).
EXPECTED_PATTERN = "{n} files expected"



# --------------------------------------------------------------- parsing ----


def csv_tuple(value: object) -> tuple[str, ...]:
    """A comma-separated list as typed, or a list the caller already has.

    A typed cell holds one string; a spec typed as JSON holds ``["pdf"]``, and
    stringifying that gave the single extension ``['pdf']``, which no
    document has and every document therefore parked against for ever.
    """
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    text = "" if value is None else str(value).strip()
    return tuple(p.strip() for p in text.split(",") if p.strip())


#: What one keyword may hold beside its words. A keyword cell's commas are
#: the column's own word - every one of them in Required Keywords, any one
#: of them in Any Keywords - and neither column can say "these three
#: words, or this one". A prior-year return row has to: the federal return
#: is known by three lines only it prints, and a standalone state return
#: by its own printed title, which shares none of them (decision 90). So a
#: keyword may name alternatives with ``|``, and join with ``+`` the
#: phrases one alternative wants together:
#:
#:     individual income tax return + filing status + under penalties of
#:     perjury | resident income tax return
#:
#: reads "all of these, or that one", and another state's return is one
#: more ``|``. A keyword holding neither character is one phrase, exactly
#: as every keyword was before, and no shipped keyword held either.
KEYWORD_ANY_OF = "|"
KEYWORD_ALL_OF = "+"


def keyword_alternatives(keyword: str) -> tuple[tuple[str, ...], ...]:
    """One keyword as the alternatives it accepts, each a tuple of phrases
    the document must say together.

    ``"trial balance"`` is ``(("trial balance",),)``; the grammar costs a
    plain keyword nothing. Read here rather than in the matcher because
    this module owns how a keyword cell is read (``csv_tuple``), and the
    catalog writes cells the matcher then reads - one owner for the shape
    of a keyword, whether it was typed into the editor or written in
    :mod:`tracker.templates`.
    """
    alternatives = []
    for alternative in keyword.split(KEYWORD_ANY_OF):
        parts = tuple(p.strip() for p in alternative.split(KEYWORD_ALL_OF) if p.strip())
        if parts:
            alternatives.append(parts)
    return tuple(alternatives)



# ------------------------------------------------- a row per issuer (d93) ----

#: What a keyword cell cannot hold, replaced by the space between words:
#: the comma the cell is split on (:func:`csv_tuple`) and the two
#: characters the keyword grammar reserves (:func:`keyword_alternatives`).
_RESERVED_IN_A_NAME = ",|+"
#: Dropped outright rather than spaced, so "L.P." is one word and not two.
_DROPPED_FROM_A_NAME = "."
_RUN_OF_SPACES = re.compile(r"\s+")


def entity_keyword(name: str) -> str:
    """An entity's name as a keyword cell can hold it.

    An *issuer row* (decision 93, the owner's) is an ordinary request row
    whose Required Keywords cell holds the name of the entity that issued
    the document, so that a person holding several Schedule K-1s gets one
    row per issuing entity instead of one folder with everything in it.
    The name is somebody's typing, and typing carries punctuation a
    keyword cell cannot:

    - **A comma cannot survive.** The cell is comma-separated
      (:func:`csv_tuple`), so "Ashford Holdings, L.P." is not one keyword
      but two - ``Ashford Holdings`` and ``L.P.`` - and Required Keywords
      is an AND over its cells, so the row would quietly start demanding
      both. Nothing warns; the row simply stops being the row that was
      meant.
    - **``|`` and ``+`` are the grammar's** (:data:`KEYWORD_ANY_OF`,
      :data:`KEYWORD_ALL_OF`): a name holding either would be read as
      alternatives rather than as a name.
    - **A period is dropped**, so that the two ways one person writes an
      entity agree with each other: "Ashford Holdings, L.P." and "Ashford
      Holdings LP" are the same row, whichever was typed.

    The consequence is worth saying out loud, because it is what the
    runbook tells a person: the name is then matched against the document
    the way every keyword is - whole tokens, case-insensitive, an
    apostrophe or a dash forgiven (:func:`tracker.content_check.says`) -
    and a legal suffix the K-1 prints as "L.P." is no longer in the
    keyword to be found. So the name to type is the distinctive part
    ("Ashford Holdings"), not the suffix.
    """
    spaced = "".join(
        "" if ch in _DROPPED_FROM_A_NAME else " " if ch in _RESERVED_IN_A_NAME else ch
        for ch in str(name)
    )
    return _RUN_OF_SPACES.sub(" ", spaced).strip()


def _folded(keywords: Iterable[str]) -> set[str]:
    return {k.strip().lower() for k in keywords if k.strip()}


def narrowing_rows(items: Iterable[RequestItem]) -> dict[str, tuple[str, ...]]:
    """Which rows narrow which: the broad row's identifier → the rows that narrow it.

    A row **narrows** another when it asks for the same document and
    something more about it. That is exactly the shape a person makes an
    issuer row in: copy the K-1 row, name it for the entity, and put the
    entity's name in Required Keywords. So:

    - the **broad** row recognises its document on looser words alone -
      Any Keywords, and no Required Keywords, so it can never be the
      strongest evidence for anything (:func:`tracker.router._required_matched`);
    - the **narrowing** row shares at least one of those looser words, so
      it is asking about the same document, and requires something on top.

    One shared word, rather than every one of them, because a keyword a
    person teaches one of the two rows (``add_any_keyword``) must not
    silently unpair them and start filing unnamed K-1s on the broad row
    again. Nothing in any shipped catalog narrows anything - no catalog
    row has Required Keywords where another has none and a looser word in
    common - so this relation is empty until a person adds an issuer row,
    and ``tests/test_catalog.py`` says so by name.
    """
    items = list(items)
    narrowed: dict[str, list[str]] = {}
    for broad in items:
        if broad.required_keywords or not broad.any_keywords:
            continue
        broad_words = _folded(broad.any_keywords)
        for narrow in items:
            if narrow.identifier == broad.identifier or not narrow.required_keywords:
                continue
            if broad_words & _folded(narrow.any_keywords):
                narrowed.setdefault(broad.identifier, []).append(narrow.identifier)
    return {broad: tuple(rows) for broad, rows in narrowed.items()}


def _name_tokens(item: RequestItem) -> frozenset[str]:
    """A narrowing row's required words as whole tokens, normalised."""
    joined = entity_keyword(" ".join(item.required_keywords)).lower()
    return frozenset(t for t in re.split(r"[^a-z0-9]+", joined) if t)


def check_narrowing_names(items: Iterable[RequestItem]) -> None:
    """Refuse a list where one issuer row's name is inside another's.

    "Ashford" and "Ashford Holdings" both accept the Ashford Holdings
    K-1, so every one of them would be contested and park - one row
    quietly making the other useless, with nothing said. The fix is a
    person renaming a row, and the only moment they can be told is when
    the list is validated. Names are compared as whole tokens, normalised
    (:func:`entity_keyword`), and only between rows narrowing the *same*
    broad row: two unrelated requests are allowed to share a word.
    """
    by_identifier = {i.identifier: i for i in items}
    for broad, narrow_identifiers in narrowing_rows(by_identifier.values()).items():
        named = [(i, _name_tokens(by_identifier[i])) for i in narrow_identifiers]
        for inner, inner_words in named:
            for outer, outer_words in named:
                if inner != outer and inner_words and inner_words < outer_words:
                    raise ManifestError(
                        f"Rows {inner} and {outer} both narrow {broad}, and {inner}'s "
                        f"name is inside {outer}'s: a document naming "
                        f"{', '.join(by_identifier[outer].required_keywords)} matches "
                        "both rows, so every one of them would park. Rename one so "
                        "that neither name is part of the other."
                    )



_MONTHS = ("jan", "feb", "mar", "apr", "may", "jun", "jul", "aug", "sep", "oct", "nov", "dec")
_MONTH_NAMES = ("january", "february", "march", "april", "may", "june", "july", "august",
                "september", "october", "november", "december")


def derived_date_pattern(period: str) -> str:
    """The date check a Period like ``TY2025`` or ``Dec 2025`` implies, or "".

    Case-insensitive, whole-token: ``\b2025\b`` matches "Tax Year 2025"
    and "12/31/2025" but not an account number that happens to contain it.
    A Period that names a month asks for that month too - "December 2025",
    "Dec 2025" or a "12/dd/2025" date - so a November statement is not the
    December one a row asks for.
    """
    match = _PERIOD_YEAR.search(period or "")
    if not match:
        return ""
    year = match.group(0)
    month = next((m for m in _MONTHS if (period or "").lower().lstrip().startswith(m)), None)
    if month is None:
        return rf"(?i)\b{year}\b"
    number = _MONTHS.index(month) + 1
    name = rf"(?:{month}|{_MONTH_NAMES[number - 1]})\.?"          # Dec, Dec., December
    return (
        rf"(?i)(?:\b{name}\s[^\n]{{0,20}}\b{year}\b|"
        rf"\b{year}\b[^\n]{{0,20}}\b{name}\b|\b0?{number}/[0-3]?[0-9]/(?:{year}|{year[2:]})\b)"
    )


def check_tax_year(year: int) -> int:
    """``year`` back, or ``ManifestError`` if it is not a year a tax return
    is for. One check, because a year that reaches a list unbounded
    shifts every Period by a few thousand years and the document names
    with them; the wizard's box and the rollover's flag are two doors into
    the same room.
    """
    if not YEAR_MIN <= year <= YEAR_MAX:
        raise ManifestError(YEAR_OUT_OF_RANGE.format(minimum=YEAR_MIN, maximum=YEAR_MAX, year=year))
    return year


def parse_extensions(value: object) -> tuple[str, ...]:
    """Blank → the safe default; ``*`` → anything (empty tuple); else the list."""
    parts = csv_tuple(value)
    if not parts:
        return DEFAULT_EXTENSIONS
    if any(p == ANY_EXTENSION for p in parts):
        return ()
    return tuple(e.lower().lstrip(".") for e in parts)


def identifier_problem(identifier: str) -> str:
    """Why ``identifier`` cannot name a request folder, or "" if it can.

    Shared by :func:`validated` and the desktop app's create path so a
    bad identifier is refused with the same sentence wherever it is typed.
    """
    if _ILLEGAL_IDENTIFIER_CHARS.search(identifier):
        return f"may not contain any of {WINDOWS_ILLEGAL_CHARS_TEXT} (it becomes a folder name)"
    if identifier != identifier.rstrip(". "):
        return "may not end with a dot or a space (Windows drops them from folder names)"
    return ""



# ------------------------------------------------ a row from plain values ----


def _whole_number(value: object, default: int, minimum: int, column: str, where: str) -> int:
    """A count or a size from a typed value: blank is the default, anything
    else a whole number no smaller than ``minimum``, refused with the row
    and the column named."""
    text = "" if value is None else str(value).strip()
    if not text:
        return default
    try:
        number = float(text)
        if number != int(number):
            raise ValueError
    except (TypeError, ValueError, OverflowError):
        raise ManifestError(f"{where}: {column} must be a whole number, got {value!r}") from None
    if int(number) < minimum:
        raise ManifestError(f"{where}: {column} must be at least {minimum}")
    return int(number)


def _override(value: object, where: str) -> str:
    """A Manual Override as typed, folded to the one spelling, or blank."""
    text = "" if value is None else str(value).strip()
    if not text:
        return ""
    for candidate in Override.ALL:
        if text.lower() == candidate.lower():
            return candidate
    raise ManifestError(
        f"{where}: {COL_MANUAL_OVERRIDE} must be one of {', '.join(Override.ALL)} (or blank), "
        f"got {value!r}"
    )


def item_from_fields(fields: Mapping[str, object], *, where: str) -> RequestItem:
    """One request row from plain values: the editor's JSON, a catalog spec,
    a test's dict.

    **The one parser of a row.** The sheet used to be parsed cell by cell;
    the same defaults and the same refusals are made here from a mapping
    keyed by :data:`COLUMNS`' field names, and ``where`` is what every
    refusal begins with (``"Row 3"`` from the API, the identifier from the
    catalog). Strings are stripped; the two numbers take their defaults
    when blank and must be whole and no smaller than the floor; the file
    types go through :func:`parse_extensions` (``"extensions"`` is accepted
    as the key too, as the wizard has always sent it); the keywords through
    :func:`csv_tuple`, a string or a list; the override is folded to its
    one spelling; the date pattern is kept as typed - whether it compiles,
    and what a blank one derives from the Period, is :func:`validated`'s
    to say, because that is a fact about the list and not the row. A row
    that says its pattern was derived (``date_pattern_derived``, as the
    store hands rows back) is read as having none typed, so a list read
    out of the record and sent back in is the same list.

    It defaults **no keyword**: a row with no rule is legal and is warned
    about (:func:`check_rules`), as the sheet allowed. The catalog's
    ``item_from_spec`` adds its own rule on top.
    """
    def text(key: str) -> str:
        value = fields.get(key)
        return "" if value is None else str(value).strip()

    extensions = fields.get("allowed_extensions")
    if extensions in (None, ""):
        extensions = fields.get("extensions")
    return RequestItem(
        identifier=text("identifier"),
        document=text("document"),
        period=text("period"),
        expected_count=_whole_number(fields.get("expected_count"), DEFAULT_EXPECTED_COUNT,
                                     MIN_EXPECTED_COUNT, COL_EXPECTED_COUNT, where),
        allowed_extensions=parse_extensions(extensions),
        min_size_kb=_whole_number(fields.get("min_size_kb"), DEFAULT_MIN_SIZE_KB,
                                  MIN_SIZE_KB_FLOOR, COL_MIN_SIZE_KB, where),
        required_keywords=csv_tuple(fields.get("required_keywords")),
        any_keywords=csv_tuple(fields.get("any_keywords")),
        date_pattern="" if fields.get("date_pattern_derived") else text("date_pattern"),
        manual_override=_override(fields.get("manual_override"), where),
    )


def validated(items: Iterable[RequestItem]) -> list[RequestItem]:
    """The list-level checks the sheet's loader made, on records.

    Every path that stores rules or routes against a catalog goes through
    this - ``create_engagement``, ``save_rules``, the IRS-form and catalog
    harnesses, the vocabulary report - so one list is validated one way:
    an identifier on every row, none the file system would alter
    (:func:`identifier_problem`), no two the same without case (a Windows
    folder name is not case-sensitive); a document on every row; the two
    numbers within their floors; ``NO_DATE_CHECK`` made blank, a typed
    pattern made to compile, and a blank one derived from the Period with
    ``date_pattern_derived`` set; and last, no two issuer rows whose names
    nest (:func:`check_narrowing_names`). Returns new items with ``row``
    set to 1..n - the position is part of the rule (decision 104).

    A row that comes in with a derived pattern already set (one a reader
    gave back) is treated as blank and derived again: a derived check was
    never typed, and re-reading it as typed would turn it into a rule the
    person did not make.
    """
    out: list[RequestItem] = []
    seen: dict[str, int] = {}
    for n, item in enumerate(items, start=1):
        where = f"Row {n}"
        identifier = item.identifier.strip()
        if not identifier:
            raise ManifestError(f"{where}: {COL_IDENTIFIER} is required")
        problem = identifier_problem(identifier)
        if problem:
            raise ManifestError(f"{where}: {COL_IDENTIFIER} {identifier!r} {problem}")
        key = identifier_key(identifier)
        if key in seen:
            raise ManifestError(f"Duplicate identifier {identifier!r} (rows {seen[key]} and {n})")
        seen[key] = n
        document = item.document.strip()
        if not document:
            raise ManifestError(f"{where}: {COL_DOCUMENT} is required")
        if item.expected_count < MIN_EXPECTED_COUNT:
            raise ManifestError(f"{where}: {COL_EXPECTED_COUNT} must be at least {MIN_EXPECTED_COUNT}")
        if item.min_size_kb < MIN_SIZE_KB_FLOOR:
            raise ManifestError(f"{where}: {COL_MIN_SIZE_KB} must be at least {MIN_SIZE_KB_FLOOR}")
        period = item.period.strip()
        date_pattern = "" if item.date_pattern_derived else item.date_pattern.strip()
        derived = False
        if date_pattern == NO_DATE_CHECK:
            date_pattern = ""
        elif date_pattern:
            try:
                re.compile(date_pattern)
            except re.error as exc:
                raise ManifestError(f"{where}: {COL_DATE_PATTERN} is not a valid regex: {exc}") from None
        else:
            date_pattern = derived_date_pattern(period)
            derived = bool(date_pattern)
        out.append(replace(
            item,
            identifier=identifier,
            document=document,
            period=period,
            date_pattern=date_pattern,
            date_pattern_derived=derived,
            manual_override=_override(item.manual_override, where),
            row=n,
        ))
    # Two issuer rows whose names nest make each other useless and say
    # nothing about it; the one moment a person can be told is now.
    check_narrowing_names(out)
    return out


# --------------------------------------------------------------- reading ----


def _the_record(engagement_dir: Path | str):
    """The store's connection, brought up to this engagement's journal.

    Imported here, not at the top: this module owns the list, the store
    owns the tables, and the two sit in the same layer with no load-time
    edge between them (``tests/test_layers.py``). A folder with no journal
    is refused: it has nothing to fold and is nobody's engagement - a
    folder somebody made a moment ago, or one that holds only a workbook
    the tracker no longer reads.
    """
    from tracker import ledger, store

    folder = Path(engagement_dir)
    if not ledger.path_for(folder).exists():
        raise ManifestError(NOT_AN_ENGAGEMENT.format(name=folder.name, ledger=ledger.LEDGER_FILENAME))
    conn = store.connect()
    store.follow_the_journal(conn, store.root_for(folder), folder)
    return conn


def load_manifest(engagement_dir: Path | str) -> list[RequestItem]:
    """Every request, as the record answers it now, in the list's order.

    The rules are the ones the last edit left in the store's ``requests``
    table, each row's Status, Received Date, File Count and Validation
    Notes come from ``statuses``, and a keyword a person's filing taught
    the row is added to its Any Keywords from ``learned_keywords``. The
    store is a derivation of the journal and
    :func:`tracker.store.follow_the_journal` makes it one again first, so
    no reader has to know whether a pass prepared this engagement -
    exactly as ``tracker.filer.read_index`` does for the index.

    Raises :class:`ManifestError` for a folder that holds no record.
    """
    from tracker import store

    folder = Path(engagement_dir)
    conn = _the_record(folder)
    items = [RequestItem(**rule_from_json(row)) for row in store.rules(conn, folder) or []]
    return _with_the_record(
        items, store.statuses(conn, folder), store.learned_keywords(conn, folder)
    )


def _with_the_record(
    items: Iterable[RequestItem],
    statuses: Mapping[str, StatusUpdate],
    learned: Mapping[str, tuple[str, ...]],
) -> list[RequestItem]:
    """The person's rules with what the record holds about each laid on top.

    One place where "what a request is now" is assembled: the status the
    last scan recorded, and the keywords a person's filings taught the row
    added to the ones they typed. Identifiers are matched without case,
    because a folder name on Windows is (``records.identifier_key``).
    """
    out = []
    for item in items:
        key = identifier_key(item.identifier)
        update = statuses.get(key)
        taught = tuple(
            word for word in learned.get(key, ())
            if word.lower() not in {k.lower() for k in item.any_keywords}
        )
        if update is None and not taught:
            out.append(item)
            continue
        out.append(replace(
            item,
            any_keywords=item.any_keywords + taught,
            **({} if update is None else {
                "status": update.status,
                "file_count": update.file_count,
                "received_date": update.received_date,
                "validation_notes": update.validation_notes,
            }),
        ))
    return out


def with_statuses(
    items: Iterable[RequestItem], updates: Mapping[str, StatusUpdate]
) -> list[RequestItem]:
    """``items`` with each row's status replaced by ``updates``, where it has one.

    What a scan shows of itself before the record has been read again: the
    scanner resolves a status per row and counts the rows as it is about to
    leave them (``ScanReport.summary``). Identifiers match without case,
    the way every reading that joins a status to a request does.
    """
    by_identifier = {identifier_key(identifier): update for identifier, update in updates.items()}
    return _with_the_record(items, by_identifier, {})



def load_engagement_info(engagement_dir: Path | str) -> EngagementInfo:
    """The engagement's own details, as the record holds them.

    The one reader that wants this half alone and not the rules: the
    registry, which asks every folder under the clients root who it is
    for; the reminder, for its greeting and sign-off; the scaffold, for
    the README's contact line. Every field is at its default on an
    engagement nothing has recorded details for. Raises
    :class:`ManifestError` for a folder that holds no record.
    """
    from tracker import store

    folder = Path(engagement_dir)
    conn = _the_record(folder)
    return store.engagement_info(conn, folder) or EngagementInfo()


# --------------------------------------------------------------- writing ----


@dataclass(frozen=True, slots=True)
class RulesSaved:
    """What one save of the list recorded: the identifiers of the rows that
    changed or were added, the identifiers removed, the engagement fields
    that moved, and whether anything was written at all."""

    changed: tuple[str, ...]
    removed: tuple[str, ...]
    info_fields: tuple[str, ...]
    recorded: bool


def create_engagement(
    engagement_dir: Path | str,
    items: Iterable[RequestItem],
    info: EngagementInfo | None = None,
    *,
    form: str = "",
) -> None:
    """Write an engagement's first request list and details into its record.

    The folder must exist and hold no journal: a live engagement carries a
    season of somebody's rules and must never be written over by a re-run.
    ``items`` are validated whole before anything is written, so a refusal
    leaves no folder content and no store row; then, under the engagement
    lock, the store is brought up to the (empty) journal and **one**
    ``rules_changed`` event carries the whole list and the whole of
    ``info``. That first event is what every later edit is a difference
    from, and what makes the fold of every event the list.

    ``form`` is the catalog the rows were cut from, recorded in the
    details. A keyword rather than a field of the rows because it is one
    fact about the engagement, not a property of any request. Optional,
    and a blank never clears a form ``info`` already carries.
    """
    from tracker import ledger, store
    from tracker.locking import engagement_lock

    folder = Path(engagement_dir)
    if not folder.is_dir():
        raise ManifestError(f"{folder} is not a folder; make it before creating the engagement")
    if ledger.path_for(folder).exists():
        raise ManifestError(f"Refusing to overwrite an engagement that already has a record: {folder}")
    rows = [rule_to_json(item) for item in validated(items)]
    info = info or EngagementInfo()
    if form:
        info = replace(info, form=form)
    conn = store.connect()
    with engagement_lock(folder):
        # A row the store may still hold for this folder - a name whose
        # folder was deleted by hand and is being set up again - would
        # read the new, shorter journal as truncated; forget it first.
        store.forget(conn, folder)
        store.follow_the_journal(conn, store.root_for(folder), folder)
        store.record(conn, folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: rows,
            ledger.REMOVED_KEY: [],
            ledger.INFO_KEY: info_to_json(info),
        }))


def save_rules(
    engagement_dir: Path | str,
    items: Iterable[RequestItem],
    info: EngagementInfo,
    *,
    lock_held: bool = False,
) -> RulesSaved:
    """Record a person's edit of the list and the details as one event.

    Validated whole first (:func:`validated`), so a refusal records
    nothing. Then, under the engagement lock (taken here unless the caller
    already holds it), the list is diffed against what the store holds:
    ``changed`` is every row whose stored form differs from the held row
    of the same identifier, spelled exactly - whole rows, ``row`` included,
    so a row moved is a row changed - ``removed`` is every held identifier
    no longer present in that exact spelling, and the details are the
    fields that differ from the ones recorded, or all of them when no
    rules event has ever been written. Nothing changed, nothing written:
    a save of the same list is not an event. Otherwise one
    ``rules_changed`` event carries exactly the difference, through
    :func:`tracker.store.record`, journal first.

    **Journalled, not simply written.** The record cannot stop a person
    mistyping a keyword, but it can say when it changed and to what, which
    is the difference between a rule that went wrong and a rule nobody can
    account for - and it is what lets the store be rebuilt from the
    journals alone.
    """
    from contextlib import nullcontext

    from tracker import ledger, store
    from tracker.locking import engagement_lock

    folder = Path(engagement_dir)
    rows = [rule_to_json(item) for item in validated(items)]
    now = info_to_json(info)
    with nullcontext() if lock_held else engagement_lock(folder):
        conn = _the_record(folder)
        held = store.rules(conn, folder) or []
        first = not store.has_rules_event(conn, folder)
        # Diffed by the identifier's exact spelling, because that is how
        # the fold and the store key a rule. A respelling by case is a
        # removal of the old spelling and an addition of the new, in one
        # event; diffing by the folded key here would carry the new
        # spelling and never name the old one, and the record would hold
        # both for good.
        was = {str(row["identifier"]): row for row in held}
        changed = [row for row in rows if was.get(str(row["identifier"])) != row]
        still_there = {str(row["identifier"]) for row in rows}
        removed = [str(row["identifier"]) for row in held if str(row["identifier"]) not in still_there]
        if first:
            moved = dict(now)
        else:
            before = info_to_json(store.engagement_info(conn, folder) or EngagementInfo())
            moved = {name: value for name, value in now.items() if before.get(name) != value}
        if not (changed or removed or moved):
            return RulesSaved(changed=(), removed=(), info_fields=(), recorded=False)
        store.record(conn, folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: changed,
            ledger.REMOVED_KEY: removed,
            ledger.INFO_KEY: moved,
        }))
    return RulesSaved(
        changed=tuple(str(row["identifier"]) for row in changed),
        removed=tuple(removed),
        info_fields=tuple(moved),
        recorded=True,
    )


# -------------------------------------------------- how a file is written ----


def temp_path_for(path: Path) -> Path:
    """A temp name beside ``path`` that no other writer can be using.

    It carries this process id and a random tag, so two runs writing the
    same file at once (the app saving settings while the scheduling CLI
    does, say) cannot swap each other's half-written temp into place - and
    a temp a crashed run left behind is never mistaken for a live one. It
    still ends in ``TEMP_SUFFIX``: the validators and the drop walk ignore
    that suffix, so a stranded temp is never read as a document.
    """
    return path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}{TEMP_SUFFIX}")


@contextmanager
def atomic_replacement(path: Path) -> Iterator[Path]:
    """Yield a temp path beside ``path``; swap it in whole when the block ends cleanly.

    Writing beside the file and swapping it in with ``os.replace`` makes an
    update all-or-nothing; the swap is atomic on NTFS and on every POSIX
    filesystem. A crash, a full disk or a killed scheduled task mid-write
    leaves the previous file, never half of the new one. The temp is
    removed whatever happens. A file another program holds open raises
    ``PermissionError`` from the replace, and the caller says so.
    """
    temp = temp_path_for(path)
    try:
        yield temp
        os.replace(temp, path)
    finally:
        # The temp's removal must never replace the error that stopped the
        # write: a writer may leave the half-written file open when it
        # raises, Windows then refuses the delete, and a full disk would
        # read as "held by another program".
        try:
            temp.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Temporary file %s could not be removed (%s)", temp.name, exc)


def write_text_atomically(
    path: Path, text: str, *, encoding: str = "utf-8", newline: str | None = None
) -> None:
    """Write ``text`` to ``path`` all-or-nothing (see :func:`atomic_replacement`)."""
    with atomic_replacement(path) as temp:
        with temp.open("w", encoding=encoding, newline=newline) as handle:
            handle.write(text)


def write_json_atomically(path: Path, payload: object, *, indent: int = 2) -> None:
    """Write ``payload`` as JSON to ``path`` all-or-nothing; the cache and the settings use this."""
    write_text_atomically(path, json.dumps(payload, indent=indent))



def has_routing_rules(item: RequestItem) -> bool:
    """Can this row recognise a document - by a keyword, or a year check a
    person typed? A year derived from Period is a *check* on a document
    already matched by a keyword, never evidence on its own: "it says 2025"
    describes half of what a client sends."""
    return bool(
        item.required_keywords
        or item.any_keywords
        or (item.date_pattern and not item.date_pattern_derived)
    )


# --------------------------------------------------------------- summary ----


@dataclass(frozen=True, slots=True)
class Summary:
    """Where an engagement stands, counted one way for everyone.

    The runner's log line, the reminder's "N of M are in", the scanner CLI
    and the desktop summary all used to count for themselves, each with a
    slightly different idea of what an override meant. This is the count.
    Waived rows are nobody's to wait on and are outside every figure except
    ``waived``; an Accepted row is Received whatever its status cell says,
    so a signed-off row counts as in even before the next scan writes it.
    """

    counts: dict[str, int]   # status -> rows with it (waived rows excluded)
    total: int               # rows anybody is waiting on (waived excluded)
    received: int
    outstanding: int         # Missing + Partial + Failed Validation
    waived: int
    unscanned: int           # rows with no status yet

    @property
    def line(self) -> str:
        """``Received: 3 · Missing: 2 · Waived: 1`` - the same everywhere."""
        parts = [f"{status}: {n}" for status, n in sorted(self.counts.items())]
        if self.unscanned:
            parts.append(f"{UNSCANNED_LABEL}: {self.unscanned}")
        if self.waived:
            parts.append(f"{Override.WAIVED}: {self.waived}")
        return SUMMARY_SEPARATOR.join(parts) or SUMMARY_EMPTY


def summarize(items: Iterable[RequestItem]) -> Summary:
    """Count ``items`` the one agreed way (see :class:`Summary`)."""
    counts: dict[str, int] = {}
    total = received = outstanding = waived = unscanned = 0
    for item in items:
        if item.manual_override == Override.WAIVED:
            waived += 1
            continue
        total += 1
        status = item.status
        if item.manual_override == Override.ACCEPTED:
            status = Status.RECEIVED
        if not status:
            unscanned += 1
            continue
        counts[status] = counts.get(status, 0) + 1
        if status == Status.RECEIVED:
            received += 1
        elif status in Status.OUTSTANDING:
            outstanding += 1
    return Summary(counts=counts, total=total, received=received,
                   outstanding=outstanding, waived=waived, unscanned=unscanned)



# ----------------------------------------------------------------- check ----

#: Form numbers that name a family, not a form: a keyword of just the number
#: matches none of the family's members (``1099`` does not match ``1099-INT``;
#: see ``tracker.content_check.contains_keyword``), so the check says so.
FORM_FAMILIES = {"1099": "1099-INT", "1095": "1095-A"}
EMPTY_KEYWORD_WARNING = (
    "Row {row} ({identifier}): the keyword '{keyword}' has no letters or digits and "
    "matches nothing; leave the cell blank instead"
)
BARE_FORM_NUMBER_WARNING = (
    "Row {row} ({identifier}): the keyword '{keyword}' matches only that form, not its "
    "variants such as {example}; list the forms this request means"
)


def check_rules(items: Iterable[RequestItem]) -> list[str]:
    """What a person should know about a list the rules will act on: legal,
    but probably not what was meant.

    The warnings half of what the old manifest check said; there is no
    problems half, because a list the record holds has been validated on
    the way in. Rides every ``state`` the app reads and every pass's
    report, so a request that can never auto-file is seen now rather than
    at a deadline: a row with no keyword and no typed date rule, a row
    accepting any file type (an .exe would count), a keyword with no
    letter or digit in it, and a bare family number that matches none of
    the family's forms. A waived row is nobody's to act on and is skipped.
    """
    warnings: list[str] = []
    for item in items:
        if item.manual_override == Override.WAIVED:
            continue
        if not has_routing_rules(item):
            warnings.append(
                f"Row {item.row} ({item.identifier}): no {COL_REQUIRED_KEYWORDS}, {COL_ANY_KEYWORDS} "
                f"or {COL_DATE_PATTERN}, so its documents can never be filed automatically"
            )
        if not item.allowed_extensions:
            warnings.append(
                f"Row {item.row} ({item.identifier}): {COL_ALLOWED_EXTENSIONS} is '{ANY_EXTENSION}', so any "
                "file type counts as this document"
            )
        for keyword in (*item.required_keywords, *item.any_keywords):
            if not any(ch.isalnum() for ch in keyword):
                warnings.append(EMPTY_KEYWORD_WARNING.format(
                    row=item.row, identifier=item.identifier, keyword=keyword.strip()))
            if keyword.strip() in FORM_FAMILIES:
                warnings.append(BARE_FORM_NUMBER_WARNING.format(
                    row=item.row, identifier=item.identifier, keyword=keyword.strip(),
                    example=FORM_FAMILIES[keyword.strip()],
                ))
    return warnings
