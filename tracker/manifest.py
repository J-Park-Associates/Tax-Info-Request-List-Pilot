"""Manifest layer for the Client Document Tracker (component 1, docs/ROADMAP.md).

Owns everything about ``_manifest.xlsx``: the schema, loading and validating
rows into :class:`RequestItem` dataclasses, and writing scanner status back
with Excel-lock resilience (retry with backoff, then defer updates to a
``_manifest.pending.json`` sidecar that is merged on the next write).

This module never touches client files — only the manifest workbook and its
sidecar. All values are validated on load and fail loudly with row context so
a malformed manifest can never silently produce wrong statuses.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import re
import time
from dataclasses import dataclass, replace
from pathlib import Path
from typing import Iterable, Mapping

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

log = logging.getLogger("tracker.manifest")

SHEET_NAME = "Requests"
#: Who the engagement is for and how it is chased. Lives in the manifest so
#: the folder carries everything the scheduled run needs to know about it -
#: there is no separate registry file for a person to keep in step.
ENGAGEMENT_SHEET_NAME = "Engagement"

# ---------------------------------------------------------------- schema ----

COL_IDENTIFIER = "Identifier"
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
#: The years a tax year can be. The pattern below is built from them, and
#: the app's year inputs are bounded by them.
YEAR_MIN = 1900
YEAR_MAX = 2099
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
WINDOWS_ILLEGAL_CHARS = re.compile(r'[\\/:*?"<>|\x00-\x1f]')
WINDOWS_ILLEGAL_CHARS_TEXT = '\\ / : * ? " < > |'
DATE_FORMAT = "yyyy-mm-dd"

#: Characters an identifier may not contain. The identifier becomes the
#: prefix of a Windows folder name and is matched back by that prefix, so
#: anything the filesystem would alter (\\ / : * ? " < > | and control
#: characters) or strip (a trailing dot) would leave the scanner unable to
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

#: The Engagement sheet's yes/no cells, as written; ``_parse_yes_no`` also
#: reads the usual spellings a person types.
YES = "yes"
NO = "no"

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
        text = f"{self.identifier} - {self.document}"
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


def shift_item(item: "RequestItem", delta: int) -> "RequestItem":
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


def detect_year(items: Iterable["RequestItem"]) -> int | None:
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


@dataclass(frozen=True, slots=True)
class EngagementInfo:
    """The Engagement sheet: who this is for and how the run should treat it.

    Every field is optional. A manifest without the sheet (one made before
    it existed) loads as all defaults and is still processed.
    """

    client: str = ""        # greeting name in the reminder
    name: str = ""          # engagement label; the folder name if blank
    link: str = ""          # share link to the client's drop folder
    due: dt.date | None = None
    sender: str = ""        # who the reminder is from
    firm: str = ""          # sign-off line
    reminders: bool = True  # False: this client is not chased by email
    active: bool = True     # False: the scheduled run skips this folder
    rolled_from: str = ""   # the prior engagement this one was rolled forward from


#: Row labels on the Engagement sheet, in the order they are written.
#: How a multi-file request says so, everywhere (the README, the reminder,
#: the app's wizard preview).
EXPECTED_PATTERN = "{n} files expected"

ENGAGEMENT_FIELDS = (
    ("Client", "client"),
    ("Engagement Name", "name"),
    ("Share Link", "link"),
    ("Due Date", "due"),
    ("Sender", "sender"),
    ("Firm", "firm"),
    ("Reminders", "reminders"),
    ("Active", "active"),
    ("Rolled From", "rolled_from"),
)
#: field name -> the sheet's label, for messages that name a cell.
ENGAGEMENT_LABELS = {field_name: label for label, field_name in ENGAGEMENT_FIELDS}


@dataclass(frozen=True, slots=True)
class StatusUpdate:
    """Scanner output for one identifier, destined for the scanner columns."""

    status: str
    file_count: int = 0
    received_date: dt.date | None = None
    validation_notes: str = ""


# --------------------------------------------------------------- parsing ----


def _cell_str(value: object) -> str:
    return "" if value is None else str(value).strip()


def _csv_tuple(value: object) -> tuple[str, ...]:
    return tuple(p.strip() for p in _cell_str(value).split(",") if p.strip())


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


def derived_date_pattern(period: str) -> str:
    """The year check a Period like ``TY2025`` or ``Dec 2025`` implies, or "".

    Case-insensitive, whole-token: ``\b2025\b`` matches "Tax Year 2025"
    and "12/31/2025" but not an account number that happens to contain it.
    """
    match = _PERIOD_YEAR.search(period or "")
    return rf"(?i)\b{match.group(0)}\b" if match else ""


def parse_extensions(value: object) -> tuple[str, ...]:
    """Blank → the safe default; ``*`` → anything (empty tuple); else the list."""
    parts = _csv_tuple(value)
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


def load_manifest(path: Path | str) -> list[RequestItem]:
    """Load and validate every request row from ``path``.

    Reads with ``data_only=True`` so formula cells yield their cached values.
    Raises :class:`ManifestError` with row context on any invalid data.
    """
    path = Path(path)
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")
    try:
        wb = load_workbook(path, data_only=True)
    except ManifestError:
        raise
    except Exception as exc:  # zip/corruption errors from openpyxl
        raise ManifestError(f"Could not open {path}: {exc}") from exc
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ManifestError(f"{path.name} has no {SHEET_NAME!r} sheet")
        ws = wb[SHEET_NAME]
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
                    required_keywords=_csv_tuple(values[COL_REQUIRED_KEYWORDS]),
                    any_keywords=_csv_tuple(values[COL_ANY_KEYWORDS]),
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
        return items
    finally:
        wb.close()


# ------------------------------------------------------------- write-back ----


def pending_path(manifest_path: Path) -> Path:
    """Sidecar file that holds updates deferred by an Excel lock."""
    return manifest_path.with_name(manifest_path.stem + PENDING_SUFFIX)


def _load_pending(manifest_path: Path) -> dict[str, StatusUpdate]:
    sidecar = pending_path(manifest_path)
    if not sidecar.exists():
        return {}
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        return {
            ident: StatusUpdate(
                status=u["status"],
                file_count=int(u.get("file_count", 0)),
                received_date=(
                    dt.date.fromisoformat(u["received_date"])
                    if u.get("received_date")
                    else None
                ),
                validation_notes=u.get("validation_notes", ""),
            )
            for ident, u in raw.items()
        }
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        # Preserve the evidence rather than retry-looping on garbage forever.
        corrupt = sidecar.with_suffix(CORRUPT_SUFFIX)
        sidecar.replace(corrupt)
        log.error("Unreadable pending sidecar moved to %s: %s", corrupt.name, exc)
        return {}


def pending_updates(manifest_path: Path | str) -> dict[str, StatusUpdate]:
    """Status updates a locked Excel kept out of the workbook, if any.

    Readers that must not act on stale statuses - the reminder above all,
    which would otherwise ask a client for a document the last scan saw
    arrive - overlay these on what :func:`load_manifest` returned.
    """
    return _load_pending(Path(manifest_path))


def with_pending(
    items: Iterable[RequestItem], updates: Mapping[str, StatusUpdate]
) -> list[RequestItem]:
    """``items`` with the scanner columns replaced by any deferred update."""
    out = []
    for item in items:
        update = updates.get(item.identifier)
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


def _save_pending(manifest_path: Path, updates: Mapping[str, StatusUpdate]) -> None:
    payload = {
        ident: {
            "status": u.status,
            "file_count": u.file_count,
            "received_date": u.received_date.isoformat() if u.received_date else None,
            "validation_notes": u.validation_notes,
        }
        for ident, u in updates.items()
    }
    pending_path(manifest_path).write_text(
        json.dumps(payload, indent=2), encoding="utf-8"
    )


def save_workbook_atomically(wb: Workbook, path: Path) -> None:
    """Save ``wb`` to ``path`` without ever leaving a half-written file there.

    openpyxl streams the zip straight into the target, so a crash, a full
    disk or a killed scheduled task mid-save would leave a manifest that
    Excel cannot open and ``load_manifest`` rejects. Writing beside the file
    and swapping it in with ``os.replace`` makes the update all-or-nothing;
    the swap is atomic on NTFS and on every POSIX filesystem.

    A file Excel holds open still raises ``PermissionError`` (from the
    replace rather than the save), so lock-retry callers behave as before.
    """
    temp = path.with_name(path.name + TEMP_SUFFIX)
    try:
        wb.save(temp)
        os.replace(temp, path)
    finally:
        temp.unlink(missing_ok=True)


def _apply_updates(path: Path, updates: Mapping[str, StatusUpdate]) -> None:
    """Open the workbook for writing and set scanner columns. May raise
    PermissionError if Excel holds the file locked (caller retries)."""
    wb = load_workbook(path)  # NOT data_only: preserves any formulas on save
    try:
        if SHEET_NAME not in wb.sheetnames:
            raise ManifestError(f"{path.name} has no {SHEET_NAME!r} sheet")
        ws = wb[SHEET_NAME]
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
            ws.cell(
                row=row,
                column=columns[COL_VALIDATION_NOTES],
                value=update.validation_notes or None,
            )
        save_workbook_atomically(wb, path)
    finally:
        wb.close()


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
            pending_path(path).unlink(missing_ok=True)
            return True
        except PermissionError as exc:
            log.warning(
                "Manifest locked (attempt %d/%d): %s", attempt, retries, exc
            )
            if attempt < retries:
                time.sleep(delay)
                delay *= 2

    _save_pending(path, merged)
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
                f"Row {item.row} ({item.identifier}): no Required Keywords, Any Keywords "
                "or Date Pattern, so its documents can never be filed automatically"
            )
        if not item.allowed_extensions:
            warnings.append(
                f"Row {item.row} ({item.identifier}): Allowed Extensions is '*', so any "
                "file type counts as this document"
            )
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
    if isinstance(value, bool):
        return value
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
    if not path.exists():
        raise ManifestError(f"Manifest not found: {path}")
    try:
        wb = load_workbook(path, data_only=True)
    except Exception as exc:
        raise ManifestError(f"Could not open {path}: {exc}") from exc
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
        ws.cell(row=row, column=2, value=value or None)
    labels = ENGAGEMENT_LABELS
    note = ws.cell(row=len(ENGAGEMENT_FIELDS) + 2, column=1,
                   value=f"{labels['reminders']}: {NO} = this client is not chased by email. "
                         f"{labels['active']}: {NO} = the scheduled run skips this folder. "
                         f"{labels['rolled_from']} is written by the rollover; the engagement it "
                         "names is no longer chased.")
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
            existing = _csv_tuple(cell.value)
            if keyword.lower() in (k.lower() for k in existing):
                return False
            cell.value = ", ".join((*existing, keyword))
            save_workbook_atomically(wb, path)
            return True
        raise ManifestError(f"No request {identifier!r} in {path.name}")
    finally:
        wb.close()


# --------------------------------------------------------------- template ----

_COLUMN_WIDTHS = {
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
) -> Path:
    """Create a fresh manifest workbook at ``path``, optionally seeded with rows.

    Always writes the Engagement sheet (defaults when ``info`` is None) so
    the person opening the workbook sees where the client's details go.
    Refuses to overwrite an existing file — a live manifest carries scanner
    state and must never be clobbered by a re-run.
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
        ws.column_dimensions[get_column_letter(idx)].width = _COLUMN_WIDTHS[header]
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
            ws.cell(row=row, column=column[header], value=value)

    _write_engagement_sheet(wb, info or EngagementInfo())
    wb.active = 0
    path.parent.mkdir(parents=True, exist_ok=True)
    wb.save(path)
    wb.close()
    return path
