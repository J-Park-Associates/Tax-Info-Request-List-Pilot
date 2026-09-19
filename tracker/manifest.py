"""Manifest layer for the tracker (component 1, docs/ROADMAP.md).

``MANIFEST_FILENAME`` is **the person's file**, and since decision 103 that
is the whole of what it is. Its Requests sheet holds the ten columns an
accountant edits (:data:`ACCOUNTANT_COLUMNS`, which is now all of
:data:`HEADERS`) and nothing the machine decided: Status, Received Date,
File Count and Validation Notes left the sheet, and the statuses, the
keywords a person's filing taught and every index row live in the record
(:mod:`tracker.ledger` and :mod:`tracker.store`, ``docs/storage.md``).

So this module does three things with that workbook:

- **it reads it, every pass.** :func:`load_rules` opens it once - read-only,
  the way Excel's own share mode allows, with a short retry for the moment
  Excel saves by replacing the file - and gives back the rules and the
  Engagement sheet, validated, failing loudly with the row a person has to
  fix. The pass compares its digest with the one the record holds and
  journals every difference (``tracker.filer.ensure``);
- **it writes it at three moments and no others**: when an engagement is
  created (:func:`create_template`), when a year is rolled forward, and
  once, to slim an old workbook that still carries the four scanner
  columns. Never in a pass. That is why there is no lock retry on a write,
  no deferred-update sidecar and nothing to merge: the thirteen defensive
  decisions those cost are gone with the writes that needed them;
- **it answers what a request is now** (:func:`load_manifest`), from the
  record - the rules as the last import read them, each row's status, and
  the keywords a filing taught - never by reading the sheet for a status
  again.

Why the import journals every change rather than simply overwriting the
store: the workbook is a file Excel holds open, silently re-types, validates
nothing at entry and keeps no history of (the owner said so on 2026-09-18).
The record cannot stop a person mistyping a keyword, but it can say when it
changed and to what, which is the difference between a rule that went wrong
and a rule nobody can account for. The app's own rules editor, after season
one, replaces the import.

It also owns *how* anything beside a workbook is written. Every sidecar, the
content cache and the app's settings file go through
:func:`atomic_replacement` - a uniquely named temp file ending in
``TEMP_SUFFIX``, swapped in whole with ``os.replace`` - so a killed run never
leaves a half-written file where a reader will trust it.

This module never touches client files — only the manifest workbook. All
values are validated on load and fail loudly with row context, so a
malformed manifest can never silently produce wrong rules.

The *records* it loads - :class:`EngagementInfo`, :class:`StatusUpdate`, the
Engagement sheet's field table, the rules-only serialisation of a request
row and the yes/no spellings - live in :mod:`tracker.records` since decision
100, and are imported back here so every existing ``from tracker.manifest
import ...`` still reads. :class:`RequestItem` stays: it is the schema of the
sheet a person edits, not a record of what the machine decided, and it means
nothing away from the cells it is parsed from.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import secrets
import time
from collections.abc import Iterable, Iterator, Mapping
from contextlib import contextmanager
from dataclasses import dataclass, field, replace
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

# The records this module loads live in tracker/records.py (decision 100):
# they are the shapes, this is the workbook. An in-layer import, and the
# only one that way round - nothing in records imports the manifest.
# ENGAGEMENT_HELP is re-exported so that
# `from tracker.manifest import ENGAGEMENT_HELP` still resolves to the same
# dict; kept for one release; import from tracker.records.
from tracker.records import (
    COL_IDENTIFIER,
    ENGAGEMENT_FIELDS,
    ENGAGEMENT_HELP,  # noqa: F401
    ENGAGEMENT_LABELS,
    ENGAGEMENT_NOTES,
    NO,
    YES,
    EngagementInfo,
    StatusUpdate,
    identifier_key,
    rule_from_json,
    status_from_json,  # noqa: F401  (re-exported for one release)
)

log = logging.getLogger("tracker.manifest")

SHEET_NAME = "Requests"
#: Who the engagement is for and how it is chased. Lives in the manifest so
#: the folder carries everything the scheduled run needs to know about it -
#: there is no separate registry file for a person to keep in step.
ENGAGEMENT_SHEET_NAME = "Engagement"

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

#: Columns the accountant edits. Since decision 103 they are the whole
#: sheet: the machine reads these and writes none of them.
ACCOUNTANT_COLUMNS = (
    COL_IDENTIFIER,
    COL_DOCUMENT,
    COL_PERIOD,
    COL_EXPECTED_COUNT,
    COL_ALLOWED_EXTENSIONS,
    COL_MIN_SIZE_KB,
    COL_REQUIRED_KEYWORDS,
    COL_ANY_KEYWORDS,
    COL_DATE_PATTERN,
    COL_MANUAL_OVERRIDE,
)

#: The four columns the scanner used to write into the sheet. They are not
#: part of the schema any more - :data:`HEADERS` is the accountant's ten -
#: and these names survive for exactly two readers: the loader, which
#: ignores them where an old workbook still carries them, and the migration
#: that deletes them from such a workbook once. What they held is in the
#: record (``statuses`` in :mod:`tracker.store`) and on the Status Report.
LEGACY_SCANNER_COLUMNS = (
    COL_STATUS,
    COL_RECEIVED_DATE,
    COL_FILE_COUNT,
    COL_VALIDATION_NOTES,
)

#: The Requests sheet, whole. ``create_template()`` and the rollover write
#: exactly these, the loader requires exactly these, and the roadmap's
#: schema table lists exactly these
#: (``tests/test_single_source.py`` holds it to that).
HEADERS = ACCOUNTANT_COLUMNS

DEFAULT_EXPECTED_COUNT = 1
DEFAULT_MIN_SIZE_KB = 5
#: What a blank Allowed Extensions cell means. A blank used to mean "accept
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
DATE_FORMAT = "yyyy-mm-dd"
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

#: The temp file an atomic save lands in first. The two sidecar suffixes
#: that used to stand beside it went with the deferred writes (decision
#: 103): nothing is deferred any more, so there is nothing to keep beside
#: a workbook and nothing to quarantine.
TEMP_SUFFIX = ".tmp"

#: How often a *read* of the workbook is retried, and how long it waits the
#: first time (doubling). Not a lock retry - Excel's share mode lets a
#: reader in, and decision 103 took every write out of the pass. What this
#: covers is the fraction of a second in which Excel saves by writing a new
#: file beside the old one and renaming it over the top: a reader that
#: happened to open in that window sees the file vanish, and the honest
#: answer is to look again rather than to tell a person their manifest is
#: missing.
READ_RETRIES = 3
READ_RETRY_DELAY = 0.2


class Override:
    """Accountant judgment values that beat the automated rules."""

    ACCEPTED = "Accepted"  # treat as Received despite failed checks
    WAIVED = "Waived"      # item no longer needed

    ALL = (ACCEPTED, WAIVED)


class ManifestError(Exception):
    """A manifest could not be read, parsed, or validated."""


@dataclass(frozen=True, slots=True)
class RequestItem:
    """One request: the person's rule, and what the record says about it.

    ``records.RULE_FIELDS`` names the person's half - the ten columns of
    the sheet plus ``row``, which is where on it the rule was read - and
    that half is what the workbook, a ``rules_imported`` event and the
    store's ``requests`` table all carry. The four status fields are the
    record's: they are not on the sheet any more (decision 103), so
    :func:`load_rules` leaves them at their defaults and
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
    status: str = ""                           # the record's, not the sheet's
    received_date: dt.date | None = None
    file_count: int | None = None
    validation_notes: str = ""
    row: int = 0                               # Excel row this item came from

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


def engagement_sheet_note() -> str:
    """The italic line under the Engagement sheet, built from the notes."""
    return ". ".join(
        f"{ENGAGEMENT_LABELS[field]}: {note}" if field != "rolled_from"
        else f"{ENGAGEMENT_LABELS[field]} is {note}"
        for field, note in ENGAGEMENT_NOTES.items()
    ) + "."


# --------------------------------------------------------------- parsing ----


def _cell_str(value: object) -> str:
    return "" if value is None else str(value).strip()


def csv_tuple(value: object) -> tuple[str, ...]:
    """A cell's comma-separated list, or a list the caller already has.

    A cell holds one string; a spec typed as JSON holds ``["pdf"]``, and
    stringifying that gave the single extension ``['pdf']``, which no
    document has and every document therefore parked against for ever.
    """
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    return tuple(p.strip() for p in _cell_str(value).split(",") if p.strip())


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
    of a keyword, whether it was typed into Excel or written in
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
    the manifest is read. Names are compared as whole tokens, normalised
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


def _parse_int(value: object, default: int, column: str, row: int) -> int:
    text = _cell_str(value)
    if not text:
        return default
    try:
        number = float(text)
        if number != int(number):
            raise ValueError
        return int(number)
    except ValueError:
        raise ManifestError(
            f"Row {row}: {column} must be a whole number, got {value!r}"
        ) from None


def _parse_date(value: object, column: str, row: int) -> dt.date | None:
    if isinstance(value, dt.datetime):
        return value.date()
    if isinstance(value, dt.date):
        return value
    text = _cell_str(value)
    if not text:
        return None
    try:
        return dt.date.fromisoformat(text)
    except ValueError:
        raise ManifestError(
            f"Row {row}: {column} must be a date, got {value!r}"
        ) from None


def _parse_enum(value: object, allowed: tuple[str, ...], column: str, row: int) -> str:
    text = _cell_str(value)
    if not text:
        return ""
    for candidate in allowed:
        if text.lower() == candidate.lower():
            return candidate
    raise ManifestError(
        f"Row {row}: {column} must be one of {', '.join(allowed)} (or blank), got {value!r}"
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
    is for. One check, because a year that reaches a manifest unbounded
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

    Shared by :func:`load_manifest` and the desktop app's create path so a
    bad identifier is refused with the same sentence wherever it is typed.
    """
    if _ILLEGAL_IDENTIFIER_CHARS.search(identifier):
        return f"may not contain any of {WINDOWS_ILLEGAL_CHARS_TEXT} (it becomes a folder name)"
    if identifier != identifier.rstrip(". "):
        return "may not end with a dot or a space (Windows drops them from folder names)"
    return ""


def _header_map(ws, wanted: tuple[str, ...] = HEADERS) -> dict[str, int]:
    """Map canonical column names to 1-based column indexes; fail on missing.

    Only ``wanted`` has to be there. An older workbook still carrying the
    four columns the scanner used to write (:data:`LEGACY_SCANNER_COLUMNS`)
    loads exactly the same way and those cells are simply not read: nothing
    refuses a file a person has been using all season because the machine
    stopped writing part of it.
    """
    found: dict[str, int] = {}
    for idx in range(1, (ws.max_column or 0) + 1):
        text = _cell_str(ws.cell(row=1, column=idx).value)
        if text:
            found[text.lower()] = idx
    missing = [h for h in wanted if h.lower() not in found]
    if missing:
        raise ManifestError(
            f"Sheet {SHEET_NAME!r} is missing column(s): {', '.join(missing)}"
        )
    return {h: found[h.lower()] for h in wanted}


def legacy_scanner_columns(ws) -> dict[str, int]:
    """The scanner columns an old Requests sheet still carries, by 1-based
    column index; empty on a sheet already slimmed.

    The one reader of :data:`LEGACY_SCANNER_COLUMNS`, shared by the
    migration that imports those cells into the record and the one that
    deletes them from the sheet, so the two cannot disagree about which
    columns they are looking at.
    """
    found: dict[str, int] = {}
    for idx in range(1, (ws.max_column or 0) + 1):
        text = _cell_str(ws.cell(row=1, column=idx).value).lower()
        for header in LEGACY_SCANNER_COLUMNS:
            if text == header.lower():
                found[header] = idx
    return found


# --------------------------------------------------------------- loading ----


def _open_manifest(path: Path):
    """The workbook, read-only (cached values), or the one sentence for why not.

    A file that is not there is said so at once - nothing is being saved
    over a path that does not exist. A file that *is* there and will not
    open is tried :data:`READ_RETRIES` times with a doubling wait, because
    Excel saves a workbook by writing a new one beside it and renaming it
    over the top: for a fraction of a second the bytes at that path are the
    half-written new file's, and a reader that gave up there would tell a
    person their manifest was corrupt. Excel's own share mode lets a reader
    open the file it is holding, so nothing else here waits on Excel -
    since decision 103 the machine has no write of its own to retry.
    """
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")
    delay = READ_RETRY_DELAY
    for attempt in range(1, READ_RETRIES + 1):
        try:
            return load_workbook(path, data_only=True)
        except Exception as exc:  # zip/corruption errors from openpyxl
            if attempt == READ_RETRIES:
                raise ManifestError(f"Could not open {path}: {exc}") from exc
            log.debug("%s could not be read (attempt %d/%d): %s",
                      path.name, attempt, READ_RETRIES, exc)
            time.sleep(delay)
            delay *= 2
    raise ManifestError(f"Could not open {path}")   # unreachable; the loop raises


def _requests_sheet(wb, path: Path):
    if SHEET_NAME not in wb.sheetnames:
        raise ManifestError(f"{path.name} has no {SHEET_NAME!r} sheet")
    return wb[SHEET_NAME]


def _the_folder_and_the_workbook(path_or_dir: Path | str) -> tuple[Path, Path]:
    """The engagement folder and its manifest, whichever of the two was named.

    Every reader here has always been handed the workbook's own path,
    because that is the file it read. Since decision 103 the answer comes
    from the record, which belongs to the folder, so both spellings are
    accepted and resolved here rather than at a dozen call sites.

    ``MANIFEST_FILENAME`` is the scaffold's, and the scaffold imports this
    module: the name is fetched at call time so the edge stays one-way at
    load time (``tests/test_layers.py``).
    """
    from tracker.scaffold import MANIFEST_FILENAME

    path = Path(path_or_dir)
    if path.suffix.lower() == ".xlsx":
        return path.parent, path
    return path, path / MANIFEST_FILENAME


def load_manifest(path_or_dir: Path | str) -> list[RequestItem]:
    """Every request, as the record answers it now. Rows in the sheet's order.

    **This does not read the workbook** (decision 103). The rules are the
    ones the last import read into the store's ``requests`` table, each
    row's Status, Received Date, File Count and Validation Notes come from
    ``statuses``, and a keyword a person's filing taught the row is added to
    its Any Keywords from ``learned_keywords``. The store is a derivation of
    the journal and :func:`tracker.store.follow_the_journal` makes it one
    again first, so no reader has to know whether a pass prepared this
    engagement - exactly as ``tracker.filer.read_index`` does for the index.

    The one time the sheet is read here is the reading that has never
    happened: an engagement no import has spoken for yet (a manifest just
    created, a folder nothing has passed over) answers from
    :func:`load_rules`, which is the same first reading the store's own
    build takes. After a pass there is always an import, and after a
    workbook that will not validate the last good rules stay in force -
    nothing is imported from a sheet that does not load.

    Raises :class:`ManifestError` with row context when that first reading
    is the one that fails.
    """
    # Imported here, not at the top: this module is the workbook's, the
    # store is the record's, and the two sit in the same layer with no
    # load-time edge between them (``tests/test_layers.py``). A call-time
    # import is where that edge is allowed to close.
    from tracker import ledger, store

    folder, workbook = _the_folder_and_the_workbook(path_or_dir)
    conn = store.connect()
    if ledger.path_for(folder).exists():
        # A folder with a journal is an engagement something has decided
        # about, and the store is a derivation of that journal: bring it
        # up before reading, exactly as ``filer.read_index`` does. A
        # folder with none has nothing to fold and is left unknown to the
        # store - a workbook somebody made a moment ago, or a catalog in a
        # temporary directory, is not an engagement yet.
        store.follow_the_journal(conn, store.root_for(folder), folder)
    stored = store.rules(conn, folder)
    items = (load_rules(workbook).items if stored is None
             else [RequestItem(**rule_from_json(row)) for row in stored])
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


@dataclass(frozen=True, slots=True)
class RulesReading:
    """One reading of the workbook: the person's rules and their engagement.

    A pair, because both come out of one open of the file
    (:func:`load_rules`) and every caller wants both - the pass that imports
    them, the store's first build, the check a person runs before a pass.
    Three opens of one workbook was what this replaced.
    """

    items: list[RequestItem] = field(default_factory=list)
    info: EngagementInfo = field(default_factory=EngagementInfo)


def load_rules(path: Path | str) -> RulesReading:
    """The person's request list and Engagement sheet, from one open of ``path``.

    **The only reading of the workbook there is.** The rows come back as
    :class:`RequestItem`s with their status fields at the defaults: the
    sheet holds no status to read (decision 103), and an older sheet that
    still carries the four columns is read for its rules with those cells
    ignored - so nothing refuses a workbook a person has been using all
    season.

    Reads with ``data_only=True`` so formula cells yield their cached
    values, and raises :class:`ManifestError` with the Excel row on any
    invalid data. A workbook that raises here is a workbook nothing is
    imported from: the engagement's pass records the problem and the rules
    the record already holds stay in force.
    """
    path = Path(path)
    wb = _open_manifest(path)
    try:
        info = (_engagement_from_sheet(wb[ENGAGEMENT_SHEET_NAME])
                if ENGAGEMENT_SHEET_NAME in wb.sheetnames else EngagementInfo())
        return RulesReading(items=_requests_from_sheet(wb, path), info=info)
    finally:
        wb.close()


def _requests_from_sheet(wb, path: Path) -> list[RequestItem]:
    """Every rule on the Requests sheet, parsed and validated, in sheet order.

    The status fields of each :class:`RequestItem` are left at their
    defaults: there is nothing on the sheet to read them from, and a row
    that has never been scanned and a row whose status is in the record
    read the same here. What the record says is laid on in
    :func:`load_manifest`.
    """
    ws = _requests_sheet(wb, path)
    columns = _header_map(ws)

    items: list[RequestItem] = []
    seen: dict[str, int] = {}
    for row in range(2, (ws.max_row or 1) + 1):
        values = {
            name: ws.cell(row=row, column=idx).value
            for name, idx in columns.items()
        }
        if all(_cell_str(v) == "" for v in values.values()):
            continue  # blank spacer row

        identifier = _cell_str(values[COL_IDENTIFIER])
        if not identifier:
            raise ManifestError(f"Row {row}: {COL_IDENTIFIER} is required")
        problem = identifier_problem(identifier)
        if problem:
            raise ManifestError(f"Row {row}: {COL_IDENTIFIER} {identifier!r} {problem}")
        # Windows folder names are case-insensitive, so "A01" and "a01"
        # would claim the same folder; treat them as the same identifier.
        if identifier_key(identifier) in seen:
            raise ManifestError(
                f"Duplicate identifier {identifier!r} "
                f"(rows {seen[identifier_key(identifier)]} and {row})"
            )
        seen[identifier_key(identifier)] = row

        document = _cell_str(values[COL_DOCUMENT])
        if not document:
            raise ManifestError(f"Row {row}: {COL_DOCUMENT} is required")

        expected_count = _parse_int(
            values[COL_EXPECTED_COUNT], DEFAULT_EXPECTED_COUNT, COL_EXPECTED_COUNT, row
        )
        if expected_count < 1:
            raise ManifestError(f"Row {row}: {COL_EXPECTED_COUNT} must be >= 1")

        min_size_kb = _parse_int(
            values[COL_MIN_SIZE_KB], DEFAULT_MIN_SIZE_KB, COL_MIN_SIZE_KB, row
        )
        if min_size_kb < 0:
            raise ManifestError(f"Row {row}: {COL_MIN_SIZE_KB} must be >= 0")

        period = _cell_str(values[COL_PERIOD])
        date_pattern = _cell_str(values[COL_DATE_PATTERN])
        date_pattern_derived = False
        if date_pattern == NO_DATE_CHECK:
            date_pattern = ""
        elif date_pattern:
            try:
                re.compile(date_pattern)
            except re.error as exc:
                raise ManifestError(
                    f"Row {row}: {COL_DATE_PATTERN} is not a valid regex: {exc}"
                ) from None
        else:
            date_pattern = derived_date_pattern(period)
            date_pattern_derived = bool(date_pattern)

        items.append(
            RequestItem(
                identifier=identifier,
                document=document,
                period=period,
                expected_count=expected_count,
                allowed_extensions=parse_extensions(values[COL_ALLOWED_EXTENSIONS]),
                min_size_kb=min_size_kb,
                required_keywords=csv_tuple(values[COL_REQUIRED_KEYWORDS]),
                any_keywords=csv_tuple(values[COL_ANY_KEYWORDS]),
                date_pattern=date_pattern,
                date_pattern_derived=date_pattern_derived,
                manual_override=_parse_enum(
                    values[COL_MANUAL_OVERRIDE], Override.ALL, COL_MANUAL_OVERRIDE, row
                ),
                row=row,
            )
        )
    # Two issuer rows whose names nest make each other useless and say
    # nothing about it; the one moment a person can be told is now.
    check_narrowing_names(items)
    return items


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
    removed whatever happens. A file Excel holds open raises
    ``PermissionError`` from the replace, so lock-retry callers see the
    same exception they always did.
    """
    temp = temp_path_for(path)
    try:
        yield temp
        os.replace(temp, path)
    finally:
        # The temp's removal must never replace the error that stopped the
        # write: openpyxl leaves the half-written zip open when save()
        # raises, Windows then refuses the delete, and a full disk would
        # read as "open in Excel" and be retried five times.
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
    """Write ``payload`` as JSON to ``path`` all-or-nothing; every sidecar uses this."""
    write_text_atomically(path, json.dumps(payload, indent=indent))


def as_text(cell):
    """Keep a value the tracker wrote from data a string, whatever it starts with.

    openpyxl reads a string beginning with ``=`` as a formula. A client file
    called ``=SUM scan.pdf`` would then be written into the index as a
    formula, read back as an empty cell, and shown by Excel as an error.
    A person's own formulas in the manifest are not touched: this is
    applied only to cells the tracker fills from data.
    """
    if isinstance(cell.value, str) and cell.data_type == "f":
        cell.data_type = "s"
    return cell


def save_workbook_atomically(wb: Workbook, path: Path) -> None:
    """Save ``wb`` to ``path`` without ever leaving a half-written file there.

    openpyxl streams the zip straight into the target, so a crash mid-save
    would leave a manifest that Excel cannot open and :func:`load_rules`
    rejects; :func:`atomic_replacement` is what makes it whole or nothing.

    Three callers, and there will never be a fourth in a pass: creating an
    engagement, rolling a year forward, and the one-time slimming of a
    workbook that still carries the scanner columns. If Excel holds the
    file the replace raises ``PermissionError`` and the caller says so
    loudly - there is nothing to defer and nothing to merge (decision 103).
    """
    with atomic_replacement(path) as temp:
        wb.save(temp)


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


@dataclass(frozen=True, slots=True)
class ManifestCheck:
    """What a person should know about a manifest before the run relies on it."""

    problems: list[str]   # the manifest cannot be used until these are fixed
    warnings: list[str]   # legal, but probably not what was meant

    @property
    def ok(self) -> bool:
        return not self.problems


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


def check_manifest(path: Path | str) -> ManifestCheck:
    """Everything load-time validation would say, plus what it would let slide.

    Meant for a button in the app and the top of the scheduled run, so a
    typo made in Excel is reported with its row now rather than as a failed
    job hours later. **It reads the workbook**, not the record: the
    question is what the next import would make of the sheet as it stands,
    and the record holds the last sheet that loaded. Problems are the
    loader's own messages; warnings are rows the rules cannot act on - a
    request with no keyword or date rule never auto-files, a row accepting
    any file type will count an .exe.
    """
    path = Path(path)
    problems: list[str] = []
    warnings: list[str] = []
    items: list[RequestItem] = []
    try:
        items = load_rules(path).items
    except ManifestError as exc:
        problems.append(str(exc))
    if not items and not problems:
        warnings.append(f"{SHEET_NAME} sheet has no request rows")
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
    return ManifestCheck(problems=problems, warnings=warnings)


# ------------------------------------------------------------ engagement ----


def _parse_yes_no(value: object, label: str, default: bool) -> bool:
    text = _cell_str(value).lower()
    if not text:
        return default
    if text in (YES, "y", "true", "1"):
        return True
    if text in (NO, "n", "false", "0"):
        return False
    raise ManifestError(
        f"{ENGAGEMENT_SHEET_NAME} sheet: {label} must be {YES} or {NO}, got {value!r}"
    )


def _engagement_from_sheet(ws) -> EngagementInfo:
    raw: dict[str, object] = {}
    for row in ws.iter_rows(min_row=1, max_col=2, values_only=True):
        if not row or not _cell_str(row[0]):
            continue
        raw[_cell_str(row[0]).lower()] = row[1] if len(row) > 1 else None
    values: dict[str, object] = {}
    for label, field_name in ENGAGEMENT_FIELDS:
        value = raw.get(label.lower())
        if field_name == "due":
            values[field_name] = _parse_date(value, label, 0)
        elif field_name in ("reminders", "active"):
            values[field_name] = _parse_yes_no(value, label, True)
        else:
            values[field_name] = _cell_str(value)
    return EngagementInfo(**values)


def load_engagement_info(path: Path | str) -> EngagementInfo:
    """The Engagement sheet of ``path``; all defaults if the sheet is absent.

    The one caller that wants this half alone and not the rules: the
    registry, which asks every folder under the clients root who it is for
    and must not pay for parsing a request list to find out. Everything
    that wants both takes :func:`load_rules`, which is one open.
    """
    path = Path(path)
    wb = _open_manifest(path)
    try:
        if ENGAGEMENT_SHEET_NAME not in wb.sheetnames:
            return EngagementInfo()
        return _engagement_from_sheet(wb[ENGAGEMENT_SHEET_NAME])
    finally:
        wb.close()


def _write_engagement_sheet(wb: Workbook, info: EngagementInfo) -> None:
    if ENGAGEMENT_SHEET_NAME in wb.sheetnames:
        del wb[ENGAGEMENT_SHEET_NAME]
    ws = wb.create_sheet(ENGAGEMENT_SHEET_NAME)
    ws.column_dimensions["A"].width = 18
    ws.column_dimensions["B"].width = 60
    for row, (label, field_name) in enumerate(ENGAGEMENT_FIELDS, start=1):
        ws.cell(row=row, column=1, value=label).font = Font(bold=True)
        value = getattr(info, field_name)
        if isinstance(value, bool):
            value = YES if value else NO
        elif isinstance(value, dt.date):
            cell = ws.cell(row=row, column=2, value=value)
            cell.number_format = DATE_FORMAT
            continue
        as_text(ws.cell(row=row, column=2, value=value or None))   # a client called "=1+1" is a name (decision 58)
    note = ws.cell(row=len(ENGAGEMENT_FIELDS) + 2, column=1, value=engagement_sheet_note())
    note.font = Font(italic=True, color="666666")


def write_engagement_info(path: Path | str, info: EngagementInfo) -> None:
    """Replace the Engagement sheet. Raises PermissionError if Excel has the file."""
    path = Path(path)
    wb = load_workbook(path)
    try:
        _write_engagement_sheet(wb, info)
        save_workbook_atomically(wb, path)
    finally:
        wb.close()


# ---------------------------------------------------------------- slimming ----

#: What the statuses that used to sit in the sheet are read from now,
#: said to the person who goes looking for them. One sentence, used by the
#: migration's log line and by ``docs/runbook.md``.
STATUSES_ARE_ON_THE_REPORT = (
    "each request's status, Received Date, File Count and Validation Notes are in the "
    "engagement's record and on its Status Report"
)


def carries_scanner_columns(path: Path | str) -> bool:
    """Whether this workbook's Requests sheet still has the four columns the
    scanner used to write. What the migration looks for, and nothing else."""
    path = Path(path)
    wb = _open_manifest(path)
    try:
        if SHEET_NAME not in wb.sheetnames:
            return False
        return bool(legacy_scanner_columns(wb[SHEET_NAME]))
    finally:
        wb.close()


def read_scanner_columns(path: Path | str) -> dict[str, StatusUpdate]:
    """Every identifier's scanner columns as an old workbook still holds
    them, by the identifier as the sheet spells it.

    The migration's reader and nothing else's: the one and only pass that
    will ever read those cells, before they are deleted. A row with no
    status at all is left out - a blank cell is not a status, and recording
    one would make the record answer for a row nothing has looked at.
    """
    path = Path(path)
    wb = _open_manifest(path)
    try:
        if SHEET_NAME not in wb.sheetnames:
            return {}
        ws = wb[SHEET_NAME]
        columns = legacy_scanner_columns(ws)
        if not columns:
            return {}
        identifier_at = _header_map(ws, (COL_IDENTIFIER,))[COL_IDENTIFIER]
        out: dict[str, StatusUpdate] = {}
        for row in range(2, (ws.max_row or 1) + 1):
            identifier = _cell_str(ws.cell(row=row, column=identifier_at).value)
            if not identifier:
                continue
            status = _parse_enum(
                ws.cell(row=row, column=columns[COL_STATUS]).value, Status.ALL, COL_STATUS, row
            ) if COL_STATUS in columns else ""
            if not status:
                continue
            count_cell = (ws.cell(row=row, column=columns[COL_FILE_COUNT]).value
                          if COL_FILE_COUNT in columns else None)
            out[identifier] = StatusUpdate(
                status=status,
                file_count=_parse_int(count_cell, 0, COL_FILE_COUNT, row),
                received_date=(_parse_date(ws.cell(row=row, column=columns[COL_RECEIVED_DATE]).value,
                                           COL_RECEIVED_DATE, row)
                               if COL_RECEIVED_DATE in columns else None),
                validation_notes=(_cell_str(ws.cell(row=row, column=columns[COL_VALIDATION_NOTES]).value)
                                  if COL_VALIDATION_NOTES in columns else ""),
            )
        return out
    finally:
        wb.close()


def slim_the_workbook(path: Path | str) -> list[str]:
    """Delete the scanner columns from an old Requests sheet. Returns their names.

    The **one** write this module makes to a workbook that already exists
    and is not being created or rolled forward, and it happens once per
    engagement, ever. Loaded without ``data_only`` so a person's own
    formulas survive, and saved through :func:`save_workbook_atomically` so
    the file is the old one or the new one and never half of each - which
    is what makes a migration that Excel interrupts safe to run again.

    ``delete_cols`` moves the cells left with their formatting, so the
    column widths a person set, the Engagement sheet, a Carried Forward
    sheet and any sheet of their own are all still there afterwards.
    Raises ``PermissionError`` if Excel holds the file; the caller says so
    and the next pass tries again.
    """
    path = Path(path)
    wb = load_workbook(path)        # NOT data_only: a person's formulas survive
    try:
        if SHEET_NAME not in wb.sheetnames:
            return []
        ws = wb[SHEET_NAME]
        columns = legacy_scanner_columns(ws)
        if not columns:
            return []
        # Right to left, so deleting one does not move the next.
        for header in sorted(columns, key=lambda h: columns[h], reverse=True):
            ws.delete_cols(columns[header])
        save_workbook_atomically(wb, path)
        return [h for h in LEGACY_SCANNER_COLUMNS if h in columns]
    finally:
        wb.close()


# --------------------------------------------------------------- template ----

#: How wide each column of the Requests sheet is drawn, by header - the ten
#: a person edits, which is all of them since decision 103.
COLUMN_WIDTHS = {
    COL_IDENTIFIER: 11,
    COL_DOCUMENT: 38,
    COL_PERIOD: 12,
    COL_EXPECTED_COUNT: 15,
    COL_ALLOWED_EXTENSIONS: 19,
    COL_MIN_SIZE_KB: 12,
    COL_REQUIRED_KEYWORDS: 24,
    COL_ANY_KEYWORDS: 24,
    COL_DATE_PATTERN: 28,
    COL_MANUAL_OVERRIDE: 16,
}


def create_template(
    path: Path | str,
    items: Iterable[RequestItem] = (),
    info: EngagementInfo | None = None,
    *,
    form: str = "",
) -> Path:
    """Create a fresh manifest workbook at ``path``, optionally seeded with rows.

    Writes the ten columns a person edits and nothing else: the four the
    scanner used to fill are not part of the sheet any more (decision 103),
    and what they held is in the record and on the Status Report.

    Always writes the Engagement sheet (defaults when ``info`` is None) so
    the person opening the workbook sees where the client's details go.
    Refuses to overwrite an existing file — a live manifest carries a
    season of somebody's rules and must never be clobbered by a re-run.

    ``form`` is the catalog the rows were cut from, recorded on the
    Engagement sheet. It is a keyword rather than something carried by the
    rows because it is one fact about the engagement, not a property of any
    request: putting it on every row would be a copy per row and a column on
    the Requests sheet nobody edits. Optional, so every caller that hands
    over rows alone - the suite, the rollover, and the reports that build a
    catalog the way an engagement gets it, ``create_template(path,
    template_items(form, year=year))`` - is unchanged and records a blank.
    A blank never clears a form ``info`` already carries.
    """
    path = Path(path)
    if path.exists():
        raise ManifestError(f"Refusing to overwrite existing manifest: {path}")

    wb = Workbook()
    ws = wb.active
    ws.title = SHEET_NAME
    for idx, header in enumerate(HEADERS, start=1):
        cell = ws.cell(row=1, column=idx, value=header)
        cell.font = Font(bold=True)
        ws.column_dimensions[get_column_letter(idx)].width = COLUMN_WIDTHS[header]
    ws.freeze_panes = "A2"

    column = {header: index for index, header in enumerate(HEADERS, start=1)}
    for row, item in enumerate(items, start=2):
        cells = {
            COL_IDENTIFIER: item.identifier,
            COL_DOCUMENT: item.document,
            COL_PERIOD: item.period or None,
            COL_EXPECTED_COUNT: item.expected_count,
            # An item built in code with no extensions means "anything"; say
            # so, or the loader would read the blank back as the safe default.
            COL_ALLOWED_EXTENSIONS: ", ".join(item.allowed_extensions) or ANY_EXTENSION,
            COL_MIN_SIZE_KB: item.min_size_kb,
            COL_REQUIRED_KEYWORDS: ", ".join(item.required_keywords) or None,
            COL_ANY_KEYWORDS: ", ".join(item.any_keywords) or None,
            COL_DATE_PATTERN: None if item.date_pattern_derived else (item.date_pattern or None),
            COL_MANUAL_OVERRIDE: item.manual_override or None,
        }
        for header, value in cells.items():
            as_text(ws.cell(row=row, column=column[header], value=value))

    info = info or EngagementInfo()
    _write_engagement_sheet(wb, replace(info, form=form) if form else info)
    wb.active = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    save_workbook_atomically(wb, path)
    wb.close()
    return path
