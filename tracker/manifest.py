"""Manifest layer for the tracker (component 1, docs/ROADMAP.md).

Owns everything about the manifest workbook (``MANIFEST_FILENAME``): the schema, loading and validating
rows into :class:`RequestItem` dataclasses, and writing scanner status back
with Excel-lock resilience (retry with backoff, then defer updates to a
``PENDING_SUFFIX`` sidecar that is merged on the next write).

It also owns *how* anything beside a workbook is written. Every sidecar, the
content cache and the app's settings file go through
:func:`atomic_replacement` - a uniquely named temp file ending in
``TEMP_SUFFIX``, swapped in whole with ``os.replace`` - so a killed run never
leaves a half-written file where a reader will trust it. And only the
function that is about to rewrite a workbook moves an unreadable sidecar
aside (:func:`quarantine_sidecar`); a reader, and any dry run, leaves the
disk exactly as it found it.

This module never touches client files — only the manifest workbook and its
sidecar. All values are validated on load and fail loudly with row context so
a malformed manifest can never silently produce wrong statuses.

The *records* it loads and writes back - :class:`EngagementInfo`,
:class:`StatusUpdate`, the Engagement sheet's field table and the yes/no
spellings - live in :mod:`tracker.records` since decision 100, and are
imported back here so every existing ``from tracker.manifest import ...``
still reads. :class:`RequestItem` stays: it is the schema of the sheet a
person edits, not a record of what the machine decided, and it means nothing
away from the cells it is parsed from.
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
from dataclasses import asdict, dataclass, fields, replace
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from tracker import ledger
from tracker.locking import lock_is_held

# The records this module loads and writes back live in tracker/records.py
# (decision 100): they are the shapes, this is the workbook. An in-layer
# import, and the only one that way round - nothing in records imports the
# manifest. ENGAGEMENT_HELP is re-exported so that
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

#: Columns the accountant edits; the scanner only ever reads these.
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

#: Columns the scanner writes; the accountant should not hand-edit these.
SCANNER_COLUMNS = (
    COL_STATUS,
    COL_RECEIVED_DATE,
    COL_FILE_COUNT,
    COL_VALIDATION_NOTES,
)

HEADERS = ACCOUNTANT_COLUMNS + SCANNER_COLUMNS

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

#: Sidecars beside a workbook: rows waiting because Excel held it, an
#: unreadable sidecar kept as evidence, and the temp file an atomic save
#: lands in first.
PENDING_SUFFIX = ".pending.json"
CORRUPT_SUFFIX = ".corrupt.json"
TEMP_SUFFIX = ".tmp"

#: How long a locked workbook is retried before rows are deferred to the
#: sidecar; the index uses the same policy.
LOCK_RETRIES = 5
LOCK_RETRY_DELAY = 0.5


class Override:
    """Accountant judgment values that beat the automated rules."""

    ACCEPTED = "Accepted"  # treat as Received despite failed checks
    WAIVED = "Waived"      # item no longer needed

    ALL = (ACCEPTED, WAIVED)


class ManifestError(Exception):
    """A manifest could not be read, parsed, or validated."""


@dataclass(frozen=True, slots=True)
class RequestItem:
    """One row of the Requests sheet, fully parsed and validated."""

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
    status: str = ""                           # "", or a Status.ALL value
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


def _header_map(ws) -> dict[str, int]:
    """Map canonical column names to 1-based column indexes; fail on missing."""
    found: dict[str, int] = {}
    for idx in range(1, (ws.max_column or 0) + 1):
        text = _cell_str(ws.cell(row=1, column=idx).value)
        if text:
            found[text.lower()] = idx
    missing = [h for h in HEADERS if h.lower() not in found]
    if missing:
        raise ManifestError(
            f"Sheet {SHEET_NAME!r} is missing column(s): {', '.join(missing)}"
        )
    return {h: found[h.lower()] for h in HEADERS}


# --------------------------------------------------------------- loading ----


def _open_manifest(path: Path):
    """The workbook, read-only (cached values), or the one sentence for why not."""
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")
    try:
        return load_workbook(path, data_only=True)
    except ManifestError:
        raise
    except Exception as exc:  # zip/corruption errors from openpyxl
        raise ManifestError(f"Could not open {path}: {exc}") from exc


def _requests_sheet(wb, path: Path):
    if SHEET_NAME not in wb.sheetnames:
        raise ManifestError(f"{path.name} has no {SHEET_NAME!r} sheet")
    return wb[SHEET_NAME]


def load_manifest(path: Path | str) -> list[RequestItem]:
    """Load and validate every request row from ``path``.

    The request itself - the identifier, the document, the period, the
    keywords, the extensions, Waived, Manual Override - is the person's, and
    always comes from the workbook. The machine writes none of it and the
    engagement's record holds none of it.

    **The scanner columns are the record's, per identifier.** Where
    ``ledger.LEDGER_FILENAME`` has ever recorded a status for an identifier,
    that status, its Received Date, File Count and Validation Notes are what
    this returns for that row; an identifier the record has never seen keeps
    the workbook's own columns. Two readings side by side, one row at a time:
    the record is the truth for what it has recorded, the workbook for what
    it has not. So an engagement scanned before it kept a record, or one row
    added to the list since, reads exactly as it always did.

    Readers that must also see a status a locked Excel deferred still overlay
    :func:`pending_updates` through :func:`with_pending` on top of this; the
    two agree, because a deferred write is recorded as applied.

    Reads with ``data_only=True`` so formula cells yield their cached values.
    Raises :class:`ManifestError` with row context on any invalid data.
    """
    path = Path(path)
    # The same replacement with_pending() makes, from the record rather than
    # from the sidecar: one owner for what replacing a row's scanner columns
    # means, and one rule for matching an identifier without case.
    return with_pending(load_manifest_from_workbook(path), _recorded_statuses(path))


def _recorded_statuses(manifest_path: Path) -> dict[str, StatusUpdate]:
    """The status the engagement's record holds for each identifier it has
    ever recorded one for; empty where there is no record, no ``scanned``
    event in it, or no reading it.

    A record that does not read as one is said loudly, with the engagement
    and the line, and the workbook's own columns answer instead - the way the
    storage path already reports a sidecar it refuses. Never a silent skip.
    """
    engagement_dir = manifest_path.parent
    try:
        recorded = ledger.statuses(ledger.read_events(engagement_dir))
        return {identifier: _update_from_json(raw) for identifier, raw in recorded.items()}
    except (ledger.LedgerError, KeyError, TypeError, ValueError, AttributeError) as exc:
        log.warning(
            "%s: its record cannot be read (%s) - the scanner columns in %s answer instead; "
            "a person should look",
            engagement_dir.name, exc, manifest_path.name,
        )
        return {}


def load_manifest_from_workbook(path: Path | str) -> list[RequestItem]:
    """Every request row as the workbook alone says it, scanner columns included.

    The reading every reader made before the record was believed, kept public
    under its own name: :func:`load_manifest` layers the record on top of it,
    the record's own bootstrap imports from it, and the suite's agreement
    fixture would be comparing the record with itself without it.
    """
    path = Path(path)
    wb = _open_manifest(path)
    try:
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
            if identifier.lower() in seen:
                raise ManifestError(
                    f"Duplicate identifier {identifier!r} "
                    f"(rows {seen[identifier.lower()]} and {row})"
                )
            seen[identifier.lower()] = row

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
                date_pattern, date_pattern_derived = derived_date_pattern(period), False
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
                    status=_parse_enum(values[COL_STATUS], Status.ALL, COL_STATUS, row),
                    received_date=_parse_date(
                        values[COL_RECEIVED_DATE], COL_RECEIVED_DATE, row
                    ),
                    file_count=(
                        _parse_int(values[COL_FILE_COUNT], -1, COL_FILE_COUNT, row)
                        if _cell_str(values[COL_FILE_COUNT])
                        else None
                    ),
                    validation_notes=_cell_str(values[COL_VALIDATION_NOTES]),
                    row=row,
                )
            )
        # Two issuer rows whose names nest make each other useless and say
        # nothing about it; the one moment a person can be told is now.
        check_narrowing_names(items)
        return items
    finally:
        wb.close()


# ------------------------------------------------------------- write-back ----


def pending_path(workbook_path: Path) -> Path:
    """The sidecar beside ``workbook_path`` that holds rows an Excel lock deferred."""
    return workbook_path.with_name(workbook_path.stem + PENDING_SUFFIX)


def quarantine_sidecar(
    sidecar: Path, exc: Exception, what: str, *, quarantine: bool = True
) -> Path | None:
    """Move an unreadable sidecar aside (kept as evidence) so it is never retried for ever.

    Each quarantine gets its own name (``CORRUPT_SUFFIX``, then ``.2``, ``.3``
    ...): a second unreadable sidecar must never overwrite the first, because
    the first is the only record of rows that were once deferred.

    With ``quarantine=False`` nothing on disk is touched and ``None`` is
    returned: that is the reader's and the dry run's contract. Only the call
    that is about to rewrite the workbook - the one that would otherwise
    retry the same unreadable file for ever - moves it aside.
    """
    if not quarantine:
        log.error(
            "Unreadable %s sidecar %s ignored for this read (%s); "
            "the next real run moves it aside", what, sidecar.name, exc,
        )
        return None
    corrupt = sidecar.with_suffix(CORRUPT_SUFFIX)
    counter = 1
    while corrupt.exists():
        counter += 1
        corrupt = sidecar.with_suffix(f".{counter}{CORRUPT_SUFFIX}")
    sidecar.replace(corrupt)
    log.error("Unreadable %s sidecar moved to %s: %s", what, corrupt.name, exc)
    return corrupt


def _load_pending(manifest_path: Path, *, quarantine: bool = True) -> dict[str, StatusUpdate]:
    sidecar = pending_path(manifest_path)
    if not sidecar.exists():
        return {}
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        return {
            ident: _update_from_json(u)
            for ident, u in raw.items()
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError, AttributeError) as exc:
        quarantine_sidecar(sidecar, exc, "pending", quarantine=quarantine)
        return {}


def pending_updates(
    manifest_path: Path | str, *, quarantine: bool = True
) -> dict[str, StatusUpdate]:
    """Status updates a locked Excel kept out of the workbook, if any.

    Readers that must not act on stale statuses - the reminder above all,
    which would otherwise ask a client for a document the last scan saw
    arrive - overlay these on what :func:`load_manifest` returned. Such
    readers pass ``quarantine=False`` so that looking never moves a file.
    """
    return _load_pending(Path(manifest_path), quarantine=quarantine)


def with_pending(
    items: Iterable[RequestItem], updates: Mapping[str, StatusUpdate]
) -> list[RequestItem]:
    """``items`` with the scanner columns replaced by any deferred update.
    Identifiers match as ``load_manifest`` compares them, without case."""
    by_identifier = {identifier.lower(): update for identifier, update in updates.items()}
    out = []
    for item in items:
        update = by_identifier.get(item.identifier.lower())
        if update is None:
            out.append(item)
        else:
            out.append(replace(
                item,
                status=update.status,
                file_count=update.file_count,
                received_date=update.received_date,
                validation_notes=update.validation_notes,
            ))
    return out


def _update_to_json(update: StatusUpdate) -> dict:
    """A StatusUpdate as the sidecar stores it: its fields, the date as text."""
    payload = asdict(update)
    payload["received_date"] = update.received_date.isoformat() if update.received_date else None
    return payload


def _update_from_json(raw: Mapping) -> StatusUpdate:
    values = {f.name: raw.get(f.name, f.default) for f in fields(StatusUpdate) if f.name != "status"}
    values["received_date"] = dt.date.fromisoformat(raw["received_date"]) if raw.get("received_date") else None
    values["file_count"] = int(values["file_count"] or 0)
    return StatusUpdate(status=raw["status"], **values)


def _save_pending(manifest_path: Path, updates: Mapping[str, StatusUpdate]) -> None:
    payload = {
        ident: _update_to_json(u)
        for ident, u in updates.items()
    }
    write_json_atomically(pending_path(manifest_path), payload)


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
    would leave a manifest that Excel cannot open and ``load_manifest``
    rejects; :func:`atomic_replacement` is what makes it whole or nothing.
    """
    with atomic_replacement(path) as temp:
        wb.save(temp)


def _apply_updates(path: Path, updates: Mapping[str, StatusUpdate]) -> None:
    """Open the workbook for writing and set scanner columns. May raise
    PermissionError if Excel holds the file locked (caller retries)."""
    wb = load_workbook(path)  # NOT data_only: preserves any formulas on save
    try:
        ws = _requests_sheet(wb, path)
        columns = _header_map(ws)

        rows_by_identifier = {
            _cell_str(ws.cell(row=r, column=columns[COL_IDENTIFIER]).value): r
            for r in range(2, (ws.max_row or 1) + 1)
        }

        for identifier, update in updates.items():
            row = rows_by_identifier.get(identifier)
            if row is None:
                # Row was deleted/renamed since the scan; nothing to update.
                log.warning(
                    "Identifier %r not found in %s; update dropped", identifier, path.name
                )
                continue
            ws.cell(row=row, column=columns[COL_STATUS], value=update.status)
            date_cell = ws.cell(
                row=row,
                column=columns[COL_RECEIVED_DATE],
                value=update.received_date,
            )
            if update.received_date is not None:
                date_cell.number_format = DATE_FORMAT
            ws.cell(row=row, column=columns[COL_FILE_COUNT], value=update.file_count)
            # cell(value=None) assigns nothing: a note that is now empty must
            # still replace the one before it, or "request folder not found"
            # outlives the folder and the reminder holds the row back for ever.
            notes = ws.cell(row=row, column=columns[COL_VALIDATION_NOTES])
            notes.value = update.validation_notes or None
            as_text(notes)
        save_workbook_atomically(wb, path)
    finally:
        wb.close()


def statuses_from_workbook(path: Path | str, *, quarantine: bool = False) -> dict[str, dict]:
    """Every identifier's scanner columns as the workbook and its pending
    sidecar alone read them, by the identifier as the workbook spells it.

    The reading every reader made before the record was believed, kept public
    under its own name: it is what the record's own bootstrap imports, and
    what the suite's agreement fixture checks the record against - through
    :func:`load_manifest` it would be checking the record against itself.

    Looking changes nothing by default: an unreadable sidecar is reported and
    left where it is.
    """
    path = Path(path)
    items = with_pending(load_manifest_from_workbook(path), _load_pending(path, quarantine=quarantine))
    return {
        item.identifier: _update_to_json(StatusUpdate(
            status=item.status, file_count=item.file_count,
            received_date=item.received_date, validation_notes=item.validation_notes,
        ))
        for item in items
    }


def _record_scanned(path: Path, updates: Mapping[str, StatusUpdate]) -> None:
    """Append what this write applied to the engagement's own record.

    Only what *changed*: a pass that found the engagement exactly as it left
    it appends nothing, so the record is the list of the moments something
    moved rather than one line per pass for ever.

    Only under the engagement lock, which is what makes this a *pass* - the
    scanner takes it before it reads a thing. Seeding a request list into a
    manifest from a test or a tool is not a pass and writes no event; the
    bootstrap above means the first real pass records where those rows stood
    anyway, so nothing is lost by the silence.
    """
    engagement_dir = path.parent
    if not lock_is_held(engagement_dir):
        return
    applied = {identifier: _update_to_json(update) for identifier, update in updates.items()}
    already = ledger.statuses(ledger.read_events(engagement_dir))
    changed = {i: status for i, status in applied.items() if already.get(i) != status}
    if not changed:
        return
    ledger.append(
        engagement_dir,
        ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: changed}),
        seed=lambda: [ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {
            # A row nothing has scanned yet has no status to import, and a
            # blank one recorded as a status would make the record answer for
            # a row it has never seen anything happen to.
            identifier: status
            for identifier, status in statuses_from_workbook(path).items() if status["status"]
        }})],
    )


def _record_keyword(path: Path, identifier: str, keyword: str) -> None:
    """Append a keyword a person's filing taught a request.

    The filer writes the index row first and the keyword after it, both
    inside its own lock, so by the time this runs the record already carries
    the rows; a caller outside the lock (a tool, a test) writes no event.
    """
    engagement_dir = path.parent
    if not lock_is_held(engagement_dir):
        return
    ledger.append(engagement_dir, ledger.new(
        ledger.KEYWORD_LEARNED, identifier=identifier, keyword=keyword,
    ))


def write_statuses(
    path: Path | str,
    updates: Mapping[str, StatusUpdate],
    *,
    retries: int = LOCK_RETRIES,
    retry_delay: float = LOCK_RETRY_DELAY,
) -> bool:
    """Write scanner columns for the given identifiers, lock-resiliently.

    Any updates deferred by a previous locked write (the pending sidecar) are
    merged first; new updates win for the same identifier. If the workbook is
    still locked after ``retries`` attempts with exponential backoff, the
    merged updates are saved to the sidecar and applied on the next call.

    Returns True if the workbook was written, False if deferred to sidecar.
    """
    path = Path(path)
    merged: dict[str, StatusUpdate] = _load_pending(path)
    merged.update(updates)
    if not merged:
        return True

    delay = retry_delay
    for attempt in range(1, retries + 1):
        try:
            _apply_updates(path, merged)
        except PermissionError as exc:
            log.warning(
                "Manifest locked (attempt %d/%d): %s", attempt, retries, exc
            )
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
            continue
        # The workbook holds every update now. A sidecar something else
        # holds open cannot be deleted, but it must not be mistaken for a
        # locked workbook: saving it again would only re-defer what landed.
        try:
            pending_path(path).unlink(missing_ok=True)
        except PermissionError as exc:
            log.warning("%s was written but %s is held open and stays (%s)", path.name, pending_path(path).name, exc)
        _record_scanned(path, merged)
        return True

    _save_pending(path, merged)
    # Recorded either way: the statuses are applied as far as this system is
    # concerned - every reader overlays the sidecar - and which file they
    # landed in is the workaround, not the fact.
    _record_scanned(path, merged)
    log.error(
        "Manifest still locked after %d attempts; %d update(s) deferred to %s",
        retries,
        len(merged),
        pending_path(path).name,
    )
    return False


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
    job hours later. Problems are the loader's own messages. Warnings are
    rows the rules cannot act on: a request with no keyword or date rule
    never auto-files, a row accepting any file type will count an .exe, and
    statuses still waiting in the pending sidecar are not in the sheet yet.
    """
    path = Path(path)
    problems: list[str] = []
    warnings: list[str] = []
    items: list[RequestItem] = []
    try:
        items = load_manifest(path)
    except ManifestError as exc:
        problems.append(str(exc))
    try:
        load_engagement_info(path)
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
    pending = pending_path(path)
    if pending.exists():
        warnings.append(
            f"{pending.name} is waiting: the last scan could not write into the sheet "
            "(was it open in Excel?); close Excel and re-scan"
        )
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
    """The Engagement sheet of ``path``; all defaults if the sheet is absent."""
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


def add_any_keyword(path: Path | str, identifier: str, keyword: str) -> bool:
    """Append ``keyword`` to a row's Any Keywords so the next such file routes itself.

    Returns False if the row already had it. Raises PermissionError when
    Excel holds the manifest - the caller decides whether that matters.
    """
    path = Path(path)
    keyword = keyword.strip()
    if not keyword:
        return False
    wb = load_workbook(path)
    try:
        ws = wb[SHEET_NAME]
        columns = _header_map(ws)
        for row in range(2, (ws.max_row or 1) + 1):
            if _cell_str(ws.cell(row=row, column=columns[COL_IDENTIFIER]).value) != identifier:
                continue
            cell = ws.cell(row=row, column=columns[COL_ANY_KEYWORDS])
            if cell.data_type == "f":
                raise ManifestError(
                    f"Row {row} ({identifier}): {COL_ANY_KEYWORDS} holds a formula; "
                    f"type the keyword {keyword!r} into it by hand"
                )
            existing = csv_tuple(cell.value)
            if keyword.lower() in (k.lower() for k in existing):
                return False
            cell.value = ", ".join((*existing, keyword))
            as_text(cell)              # a keyword starting with "=" is a keyword, not a formula
            save_workbook_atomically(wb, path)
            _record_keyword(path, identifier, keyword)
            return True
        raise ManifestError(f"No request {identifier!r} in {path.name}")
    finally:
        wb.close()


# --------------------------------------------------------------- template ----

#: How wide each column is drawn, by header. Public because the Requests
#: sheet is drawn twice now - here, and by the view a pass regenerates -
#: and a second copy of these numbers would drift.
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
    COL_STATUS: 17,
    COL_RECEIVED_DATE: 14,
    COL_FILE_COUNT: 11,
    COL_VALIDATION_NOTES: 50,
}


def create_template(
    path: Path | str,
    items: Iterable[RequestItem] = (),
    info: EngagementInfo | None = None,
    *,
    form: str = "",
) -> Path:
    """Create a fresh manifest workbook at ``path``, optionally seeded with rows.

    Always writes the Engagement sheet (defaults when ``info`` is None) so
    the person opening the workbook sees where the client's details go.
    Refuses to overwrite an existing file — a live manifest carries scanner
    state and must never be clobbered by a re-run.

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
