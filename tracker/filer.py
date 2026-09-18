"""Sort the client's drop folder into a working set (component 7).

The client sees one folder and drops everything into it. This module turns
that pile into two things:

``SHARED_DIR_NAME/PBC_DIR_NAME/``
    Every document the client provided, moved out of the drop zone but left
    completely untouched — same bytes, same filename. This is the
    provided-by-client record, and the client can still see it.

``PREPARED_DIR_NAME/<folder_name_for(item)>/``
    A renamed copy of each identified document, on the firm's side of the
    engagement, named to one convention so a preparer can work the return
    without opening the client's filing habits.

``INDEX_FILENAME`` maps one to the other: every original, where it went, what
it was renamed to, and — when it was not filed — why not. Its Evidence
column carries the *why* behind the verdict: which of the manifest row's
own keywords matched, and where in the document they were said. Catalog
words and file names only, never a word of the client's document, which is
the same line the content cache draws.

Guarantees:

- **Originals are never altered.** Files are moved into ``PBC_DIR_NAME/`` and copied
  from there; nothing is renamed in place, edited, or deleted. Ever.
- **Nothing is guessed.** Routing is :mod:`tracker.router`'s deterministic
  decision; anything ambiguous lands in ``REVIEW_DIR_NAME`` for a person.
- **Re-running is safe.** Every original is recorded by content hash, so a
  file the client drops twice is preserved but filed once.
- **Cloud-only files are left alone** until the sync client has them, so a
  placeholder is never moved as if it were the document.
- **One run at a time.** The filer holds the engagement lock
  (:mod:`tracker.locking`, the same one the scanner takes) while it works,
  so a scheduled run and a click in the desktop app cannot both move the
  same originals and overwrite each other's index rows. The lock is taken
  before the manifest, the index or the drop folder is read, so what a run
  decides from cannot change under it.
- **Wherever the client put it counts.** ``PBC_DIR_NAME/`` is visible to the client
  and the README says "drop it anywhere", so a file that lands straight in
  ``PBC_DIR_NAME/`` is treated as a drop that has already been preserved: it is
  filed and indexed in place, never ignored.
- **A working copy that went missing is replaced.** A re-sent document
  whose earlier copy is no longer in ``PREPARED_DIR_NAME/`` is filed again rather
  than dismissed as a duplicate; the original was always safe in ``PBC_DIR_NAME/``.
- **A filed document can go back for review, on the record.**
  ``unfile_document()`` moves the working copy back to ``REVIEW_DIR_NAME``
  under the client's own name and rewrites the row, so the correction people
  used to make by dragging in Explorer - which the index never learned - is
  one the index knows about. The request is re-scanned straight after, and
  goes back to what it is without the document.
- **A document no request asks for is said so, never erased.**
  ``dismiss_review_file()`` rewrites the row as ``NOT_REQUESTED`` and moves
  nothing: an agency notice or an extra statement stays where the client's
  copy of it is. The weekly draft stops counting it, and filing it later
  (``assign_review_file()``) is how the decision is undone.
- **An original that leaves the client's own folder is said out loud.**
  ``PBC_DIR_NAME/`` is the provided-by-client record and the client can see
  it, so Explorer will delete, rename and drag what is already there. A row
  whose original is no longer where it says is reported every pass
  (``MISSING_IN_PBC``); where the bytes turn up elsewhere in the folder the
  row follows the file rather than the file being filed a second time
  (``MOVED_IN_PBC``). Neither touches the working copy.
- **One bad file never costs the audit trail.** Each drop is handled on its
  own: a file the sync client still holds open is left in place for the
  next run, a file that fails *after* it was preserved is recorded as
  needing review with the error, and the index is written whatever happens
  to the files after it. If Excel has ``INDEX_FILENAME`` open, the whole
  index as it should now read waits in ``INDEX_PENDING_FILENAME`` - a
  snapshot, not just the new rows, because a row a person rewrote (a
  parked file they filed) is as much at stake as a row that was added -
  and ``read_index`` returns that snapshot until the workbook can be
  rewritten from it. Nothing that was moved into ``PBC_DIR_NAME/`` is ever
  left unrecorded, and nothing a person decided is ever forgotten.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import shutil
import stat
import time
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.cell.cell import ILLEGAL_CHARACTERS_RE
from openpyxl.utils import get_column_letter

from tracker import ledger
from tracker.content_check import (
    CACHE_FILENAME,
    ContentCache,
    Evidence,
    format_evidence,
    parse_evidence,
)
from tracker.locking import engagement_lock
from tracker.manifest import (
    COL_IDENTIFIER,
    LOCK_RETRIES,
    LOCK_RETRY_DELAY,
    ManifestError,
    Override,
    RequestItem,
    add_any_keyword,
    as_text,
    label_for,
    load_manifest,
    pending_path,
    quarantine_sidecar,
    save_workbook_atomically,
    write_json_atomically,
)
from tracker.router import route_file
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
    SHARED_DIR_NAME,
    assign_folders,
    folder_name_for,
    sanitize_component,
)
from tracker.validators import (
    UNFINISHED_SUFFIXES,
    PdfVerdictCache,
    extension_of,
    is_cloud_placeholder,
    is_ignored,
    is_sync_staging,
    iter_candidate_files,
    sha256_of,
)

log = logging.getLogger("tracker.filer")

INDEX_FILENAME = "_index.xlsx"
INDEX_SHEET = "Index"
#: Rows that could not be written because Excel had the index open; named
#: by the manifest's one sidecar rule.
INDEX_PENDING_FILENAME = pending_path(Path(INDEX_FILENAME)).name
#: The sidecar's shape. Version 2 is a snapshot of the whole index (``entries``
#: is every row, edits included) that stands in for the workbook until Excel
#: lets go. A sidecar with no version key - a bare list, written before this
#: - holds only rows to append after the workbook's, and is folded in once.
INDEX_SIDECAR_VERSION = 2
_SIDECAR_VERSION_KEY = "version"
_SIDECAR_ENTRIES_KEY = "entries"
_MAX_STEM = 110


def numbered(stem: str, counter: int, suffix: str) -> str:
    """``name (2).pdf`` - the one shape a colliding name takes."""
    return f"{stem} ({counter}){suffix}"

#: Decision values written to the index.
FILED = "Filed"
NEEDS_REVIEW = "Needs Review"
DUPLICATE = "Duplicate"
#: A parked document no request asks for - an agency notice, an extra
#: statement. The working copy stays in ``REVIEW_DIR_NAME`` (nothing a
#: client sent is ever deleted) and the original in ``PBC_DIR_NAME/`` is
#: untouched; what changes is that the draft stops counting it and a
#: re-send of the same bytes is a duplicate rather than a second review
#: item. Filing it is how the decision is undone.
NOT_REQUESTED = "Not Requested"

#: Reason prefix on index rows a person filed from REVIEW_DIR_NAME.
ASSIGNED_BY_PERSON = "assigned by a person"
#: Reason prefix on index rows a person said no request asks for.
DISMISSED_BY_PERSON = "not requested, by a person"
#: Reason prefix on index rows a person sent back to REVIEW_DIR_NAME.
UNFILED_BY_PERSON = "unfiled by a person"

#: Every decision a person makes on a row by hand, with the reason prefix it
#: is written under. A snapshot's row wins over a workbook that still shows
#: the row as it was before the decision when it carries one of these: only
#: Excel saving a stale workbook could have undone it.
_PERSONS_DECISIONS = (
    (FILED, ASSIGNED_BY_PERSON),
    (NOT_REQUESTED, DISMISSED_BY_PERSON),
    (NEEDS_REVIEW, UNFILED_BY_PERSON),
)

#: The decisions that leave a document waiting in ``REVIEW_DIR_NAME`` for a
#: person, and which a person may therefore act on: one nobody has looked at
#: yet, and one somebody has said no request asks for.
_PARKED = (NEEDS_REVIEW, NOT_REQUESTED)

#: How candidate identifiers are joined in the Candidates cell.
_CANDIDATE_SEP = ", "


class FilingError(Exception):
    """A person's filing decision could not be carried out as asked."""


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One row of ``INDEX_FILENAME`` — the audit trail for one original file.

    The fields ARE the columns: their order is the column order, the
    ``INDEX_LAYOUT`` table below gives each its header and width, and the
    workbook is read back by header name, so a column added here is one
    edit and an older index (with columns since dropped) still reads.
    Nothing stored here is a copy of something stored elsewhere: the
    working copy's name is the basename of its location, and the request's
    Document lives in the manifest, joined by Identifier.
    """

    received: str
    original_name: str
    size_kb: float
    digest: str
    identifier: str
    prepared_location: str
    pbc_location: str
    decision: str
    reason: str
    candidates: str = ""     # identifiers the router named, for a person to choose from
    #: Why each candidate was one: the keywords that matched and where they
    #: were said, written as content_check.format_evidence() writes it. The
    #: Reason sentence says what was decided; this says what it was decided
    #: on, and a parked row carries it as much as a filed one, because the
    #: parked row is the one a person has to work out.
    evidence: str = ""

    @property
    def candidate_list(self) -> list[str]:
        """The router's candidates as the list they were joined from."""
        return [c for c in (part.strip() for part in self.candidates.split(_CANDIDATE_SEP)) if c]

    @property
    def evidence_record(self) -> dict[str, tuple[Evidence, ...]]:
        """The Evidence cell read back, by candidate identifier."""
        return parse_evidence(self.evidence)

    @property
    def filed_as(self) -> str:
        """The working copy's file name - the basename of where it went."""
        return self.prepared_location.rsplit("/", 1)[-1] if self.prepared_location else ""

    def as_row(self) -> list[object]:
        return [getattr(self, f.name) for f in fields(IndexEntry)]


#: field name -> (column header, Excel width). One table, in field order.
INDEX_LAYOUT: dict[str, tuple[str, int]] = {
    "received": ("Received", 12),
    "original_name": ("Original Name", 40),
    "size_kb": ("Size KB", 9),
    "digest": ("SHA-256", 18),
    "identifier": (COL_IDENTIFIER, 10),
    "prepared_location": ("Prepared Location", 40),
    "pbc_location": ("PBC Location", 26),
    "decision": ("Decision", 14),
    "reason": ("Reason", 60),
    "candidates": ("Candidates", 14),
    "evidence": ("Evidence", 50),
}
assert tuple(INDEX_LAYOUT) == tuple(f.name for f in fields(IndexEntry))
INDEX_COLUMNS = tuple(header for header, _ in INDEX_LAYOUT.values())
#: The columns a header row must carry to be the index's (every version
#: of the index has had them), and how far down a header row is looked for.
_MANDATORY_COLUMNS = ("original_name", "pbc_location", "decision")
_HEADER_WITHIN = 10


@dataclass(frozen=True, slots=True)
class FileError:
    """One drop the run could not deal with, and what became of it."""

    name: str
    error: str
    left_in_place: bool   # True: untouched in SHARED_DIR_NAME, retried next run


@dataclass(slots=True)
class FileReport:
    """Everything one filing run did."""

    engagement_dir: Path
    filed: list[IndexEntry] = field(default_factory=list)
    review: list[IndexEntry] = field(default_factory=list)
    duplicates: list[IndexEntry] = field(default_factory=list)
    waiting: list[Path] = field(default_factory=list)   # cloud-only, left alone
    errors: list[FileError] = field(default_factory=list)
    #: Originals already sorted whose record no longer fits what is on disk
    #: (replaced under their name; recorded without bytes and now untied).
    #: Said every pass for a person, but nothing was left unsorted, so the
    #: pass is not a failure.
    attention: list[FileError] = field(default_factory=list)
    index_deferred: bool = False   # index was locked; rows wait in the sidecar
    dry_run: bool = False

    @property
    def handled(self) -> int:
        return len(self.filed) + len(self.review) + len(self.duplicates)


# ------------------------------------------------------------------ names ----


def prepared_name_for(item: RequestItem, extension: str, taken: set[str]) -> str:
    """Canonical working-copy name: ``label_for(identifier, document, period)`` plus the extension.

    ``taken`` holds names already used in the destination folder; collisions
    get ``(2)``, ``(3)``… so a request expecting several files keeps them in
    one predictable series.
    """
    parts = [sanitize_component(item.identifier), sanitize_component(item.document)]
    if item.period:
        parts.append(sanitize_component(item.period))
    stem = label_for(*parts)[:_MAX_STEM].rstrip(". ")
    suffix = f".{extension}" if extension else ""

    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate.lower() in taken:
        candidate = numbered(stem, counter, suffix)
        counter += 1
    taken.add(candidate.lower())
    return candidate


def prepared_location(folder: Path, name: str) -> str:
    """Where a working copy is, relative to the engagement: ``PREPARED_DIR_NAME/<folder>/<name>``."""
    return f"{PREPARED_DIR_NAME}/{folder.name}/{name}"


def request_folder(item: RequestItem, assigned: dict[str, list[Path]], prepared_dir: Path) -> Path:
    """The folder a request's working copies go in: the one it already has
    (by identifier prefix, so a Document renamed in Excel changes nothing),
    else the canonical name."""
    existing = assigned.get(item.identifier) or []
    return existing[0] if existing else prepared_dir / folder_name_for(item)


def _existing_copy(folder: Path, original: Path, digest: str) -> Path | None:
    """A file already in ``folder`` holding ``original``'s bytes, or None.

    A run that was killed after copying a working copy but before the
    index recorded it (Task Scheduler's limit, the app's timeout, a power
    cut) leaves the copy behind with no row naming it. The next run sees
    the original as unrecorded and would copy it again as ``(2)``; the
    copy that is already there is reused instead. Sizes are compared
    first, so only a same-sized neighbour is hashed.
    """
    if not folder.is_dir():
        return None
    try:
        size = original.stat().st_size
    except OSError:
        return None
    for candidate in sorted(folder.iterdir()):
        if is_cloud_placeholder(candidate):
            continue
        try:
            if candidate.is_file() and candidate.stat().st_size == size and sha256_of(candidate) == digest:
                log.warning("Reusing %s: a working copy with these bytes was already there", candidate.name)
                return candidate
        except OSError:
            continue
    return None


def _copy_whole(source: Path, target: Path) -> None:
    """``copy2``, with nothing left behind when it fails half-way.

    A copy that stops part-way (disk full, a virus scanner holding the new
    file) would leave a truncated working copy that the next scan reads as
    a corrupt document and the reminder then asks the client for. The
    original in ``PBC_DIR_NAME/`` is the record; a copy is disposable.
    """
    try:
        shutil.copy2(source, target)
    except BaseException:
        try:
            target.unlink(missing_ok=True)
        except OSError as exc:      # held by a scanner: say so, keep the real error
            log.warning("Half-written %s could not be removed (%s)", target.name, exc)
        raise


def _move_whole(source: Path, target: Path) -> None:
    """Move by rename, and only by rename.

    ``shutil.move`` falls back to copy-and-delete when the rename is
    refused, and on Windows a file another program holds open (a scanner
    utility still writing it, a download in progress) refuses the rename
    but not the copy: the copy lands - truncated to whatever has been
    written so far - and the delete fails, so the caller hears "left in
    place" while a phantom sits in the target folder under the client's
    own name. A rename moves the whole file or nothing; the folders this
    moves between are in one engagement, on one volume.
    """
    os.rename(source, target)


def _unique_path(folder: Path, name: str) -> Path:
    """A free path in ``folder`` for ``name``, never overwriting anything."""
    target = folder / name
    if not target.exists():
        return target
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while True:
        target = folder / numbered(stem, counter, suffix)
        if not target.exists():
            return target
        counter += 1


# ------------------------------------------------------------------ index ----


def _pending_index_path(path: Path) -> Path:
    return pending_path(path)


@dataclass(frozen=True, slots=True)
class _PendingIndex:
    """What the sidecar holds: the whole index (a snapshot) or, from an
    older sidecar, only rows to append after the workbook's."""

    entries: list[IndexEntry]
    snapshot: bool


def _entry_from_json(row: object) -> IndexEntry:
    """An IndexEntry from a sidecar row, ignoring keys a later version may add:
    a row for an original already moved must never be thrown away over a
    field this version does not know."""
    if not isinstance(row, dict):
        raise TypeError(f"index sidecar row is {type(row).__name__}, not an object")
    known = {f.name for f in fields(IndexEntry)}
    return IndexEntry(**{key: value for key, value in row.items() if key in known})


def _read_pending_index(path: Path, *, quarantine: bool = True) -> _PendingIndex | None:
    sidecar = _pending_index_path(path)
    if not sidecar.exists():
        return None
    try:
        text = sidecar.read_text(encoding="utf-8")
    except OSError as exc:
        # Not corruption: a sharing violation, a dehydrated placeholder, a
        # disk that is not there. The snapshot may be the only current copy
        # of the index, so it is neither moved nor guessed past.
        raise OSError(f"could not read {sidecar.name}: {exc}") from exc
    try:
        raw = json.loads(text)
        if isinstance(raw, list):                       # before INDEX_SIDECAR_VERSION
            return _PendingIndex([_entry_from_json(row) for row in raw], snapshot=False)
        if not isinstance(raw, dict):
            raise TypeError(f"index sidecar is {type(raw).__name__}, not an object")
        version = raw.get(_SIDECAR_VERSION_KEY)
        if version != INDEX_SIDECAR_VERSION:
            # Refused loudly rather than read half-right: nothing is guessed.
            raise ValueError(f"index sidecar version {version!r}; this version reads {INDEX_SIDECAR_VERSION}")
        rows = [_entry_from_json(row) for row in raw[_SIDECAR_ENTRIES_KEY]]
        return _PendingIndex(rows, snapshot=True)
    except (json.JSONDecodeError, KeyError, TypeError, ValueError) as exc:
        quarantine_sidecar(sidecar, exc, "index", quarantine=quarantine)
        return None


def _discard_pending_index(path: Path) -> bool:
    """Remove the snapshot a successful workbook write has just superseded.

    True if it is gone. False if something holds it open (Windows refuses
    the delete): the workbook is the newer of the two now, and
    ``read_index`` prefers the newer, so a snapshot that outlives its
    landing is inert until the next write removes it. What must not happen
    is the write being reported as deferred - that would replace the
    snapshot with an older one still.
    """
    sidecar = _pending_index_path(path)
    try:
        sidecar.unlink(missing_ok=True)
        return True
    except PermissionError as exc:
        log.warning("%s was written but %s is held open and stays (%s)", path.name, sidecar.name, exc)
        return False


def _snapshot_is_stale(path: Path) -> bool:
    """True when the workbook was written after the snapshot beside it.

    A snapshot is saved only when the workbook could not be; a workbook
    newer than the snapshot was therefore written by a later run (which
    folded the snapshot in first) or saved by a person in Excel. Either
    way the snapshot is not the index any more.
    """
    try:
        return path.stat().st_mtime > _pending_index_path(path).stat().st_mtime
    except OSError:
        return False


def _save_pending_index(path: Path, entries: list[IndexEntry]) -> None:
    """The whole index, as ``write_index`` would have written it."""
    write_json_atomically(_pending_index_path(path), {
        _SIDECAR_VERSION_KEY: INDEX_SIDECAR_VERSION,
        _SIDECAR_ENTRIES_KEY: [asdict(e) for e in entries],
    })


# ------------------------------------------------------------------ record ----


def ledger_key(entry: IndexEntry) -> str:
    """The identity the engagement's record keeps this row under.

    The index's own: where the client's preserved original is, which is what
    the snapshot merge keys on and what the app joins a review card back by.
    A row that names no original (only a workbook somebody built by hand has
    one) falls back to what else the row says about the document, so two such
    rows are not folded into one.
    """
    return entry.pbc_location or f"{entry.received}|{entry.original_name}|{entry.digest}"


#: Which event a row's decision is recorded as, when a pass reaches it. The
#: decisions a person makes are recorded under their own names, at the call
#: that makes them, so the record says who decided and not only what.
_LEDGER_EVENT_FOR = {
    FILED: ledger.FILED,
    NEEDS_REVIEW: ledger.PARKED,
    DUPLICATE: ledger.DUPLICATE,
    NOT_REQUESTED: ledger.PARKED,
}


def _ledger_row(entry: IndexEntry) -> dict:
    """The row as the record stores it - the shape the index's own sidecar
    writes and ``_entry_from_json`` reads back, so there is one owner for it."""
    return asdict(entry)


def _ledger_event(name: str, entry: IndexEntry, *, was: str = "") -> dict:
    event = ledger.new(name, **{ledger.KEY_KEY: ledger_key(entry), ledger.ROW_KEY: _ledger_row(entry)})
    if was and was != event[ledger.KEY_KEY]:
        event[ledger.WAS_KEY] = was
    return event


def _seed_from_index(index_path: Path):
    """The bootstrap for an engagement whose index has rows and whose record
    has none: every row as it now stands, imported. Called at most once, by
    the first writer that appends - never by a reader, so looking at a folder
    still changes nothing."""
    def seed() -> list[dict]:
        return [_ledger_event(ledger.IMPORTED, entry) for entry in read_index(index_path, quarantine=False)]
    return seed


def _index_as_recorded(engagement_dir: Path) -> dict[str, dict]:
    """What the engagement's record says its index rows are, by identity."""
    return ledger.fold(ledger.read_events(engagement_dir))


def _rows_changed(
    before: dict[str, dict],
    entries: list[IndexEntry],
    moved: dict[str, str],
    decided: dict[str, str],
) -> list[dict]:
    """One event per row the index now holds that ``before`` does not already say.

    Read off the rows themselves rather than collected as the caller goes,
    so every road a row travels - a drop sorted, bytes recorded on a row
    preserved without them, a row that followed an original the client moved,
    a row a person rewrote - is recorded by the one rule and none of them can
    be forgotten by a later edit somewhere else.

    ``moved`` maps a row's new identity to the one it is leaving; ``decided``
    names the event for the row this call decided itself, so a person's
    decision is recorded as theirs and not as the decision it happens to
    write.
    """
    events = []
    for entry in entries:
        key = ledger_key(entry)
        was = moved.get(key, "")
        row = _ledger_row(entry)
        earlier = before.get(was or key)
        if earlier == row:
            continue
        if key in decided:
            name = decided[key]
        elif was:
            name = ledger.PRESERVED          # the original is elsewhere; the row followed it
        elif earlier is not None and not earlier["digest"] and row["digest"]:
            name = ledger.BYTES_RECORDED
        else:
            name = _LEDGER_EVENT_FOR.get(entry.decision, ledger.PARKED)
        events.append(_ledger_event(name, entry, was=was))
    return events


def _record_write(
    engagement_dir: Path,
    index_path: Path,
    before: dict[str, dict],
    entries: list[IndexEntry],
    *,
    moved: dict[str, str] | None = None,
    decided: dict[str, str] | None = None,
) -> None:
    """Append what the index now says and the record does not, under the lock.

    ``before`` is the index as this call found it. Where the record already
    carries rows it is the record, not that reading, that is compared
    against: a row can reach the index by a road no writer took - an older
    version's sidecar folded in, a cell somebody typed over in Excel, a write
    whose process was killed between the workbook landing and this line - and
    the next write through here learns it rather than leaving the two
    disagreeing for ever.
    """
    recorded = _index_as_recorded(engagement_dir)
    bootstrap = None if recorded or not before else _seed_from_index(index_path)
    for event in _rows_changed(recorded or before, entries, moved or {}, decided or {}):
        ledger.append(engagement_dir, event, seed=bootstrap)


def _by_a_person(entry: IndexEntry) -> bool:
    """Whether this row records a decision a person made, not one a pass made.

    Both halves are read: a pass can write the same decision value, and only
    the reason says who decided. The reason is a prefix, not the whole cell,
    because what the row said before is kept after it.
    """
    return any(
        entry.decision == decision and entry.reason.startswith(prefix)
        for decision, prefix in _PERSONS_DECISIONS
    )


def _the_later_row(snapshot: IndexEntry, workbook: IndexEntry) -> IndexEntry:
    """Of two rows for one original, the one written last.

    A row rewritten after another keeps what it said before it - a person's
    decision puts it after "was:", a pass that followed a moved original
    appends its own note - so a row carrying the other's whole Reason inside
    its own was written after it. Where neither carries the other, the
    snapshot is the later: it is written only because the workbook could not
    be, and a workbook that has since outlived it was saved from Excel over a
    row the snapshot already knew about.
    """
    if workbook.reason != snapshot.reason and snapshot.reason in workbook.reason:
        return workbook
    return snapshot


def read_index(path: Path, *, quarantine: bool = True) -> list[IndexEntry]:
    """Every index row, oldest first. Empty if there is no index yet.

    While Excel holds the workbook, ``INDEX_PENDING_FILENAME`` is the index:
    the snapshot the last run could not write replaces what the workbook
    says, because the workbook is the *older* of the two. A sidecar from
    before ``INDEX_SIDECAR_VERSION`` holds only new rows, appended after
    the workbook's.

    A snapshot the workbook has since outlived (the write landed but the
    sidecar could not be deleted, or a person saved the workbook in Excel)
    is the *older* of the two: the workbook's rows win, with two
    exceptions that never lose what only the snapshot knows - a row for an
    original the workbook does not list (it has been moved; it is never
    forgotten over a timestamp), and a decision a person made
    (``_PERSONS_DECISIONS``) on a row the workbook still shows as it was
    before them, which only Excel saving a stale workbook could have undone.
    Which of the two is the later is read from the rows themselves
    (``_the_later_row``), never from the file times: the rows are in one file.

    ``quarantine=False`` is for readers and dry runs: an unreadable sidecar
    is reported and skipped, never moved - looking changes nothing. A
    sidecar that cannot be *read* (I/O) raises: it may be the only current
    copy of the index, and nothing is guessed past it.
    """
    pending = _read_pending_index(path, quarantine=quarantine)
    if pending is not None and pending.snapshot and not _snapshot_is_stale(path):
        return list(pending.entries)
    workbook = _read_index_workbook(path)
    if pending is None:
        return workbook
    if not pending.snapshot:
        # A bare-list sidecar holds rows to append once. If it could not be
        # deleted after they landed, they are in the workbook already.
        recorded = {e.pbc_location for e in workbook if e.pbc_location}
        return workbook + [e for e in pending.entries if e.pbc_location not in recorded]
    decided = {e.pbc_location: e for e in pending.entries if e.pbc_location and _by_a_person(e)}
    merged = [
        _the_later_row(decided[e.pbc_location], e) if e.pbc_location in decided else e
        for e in workbook
    ]
    recorded = {e.pbc_location for e in workbook if e.pbc_location}
    unknown = [e for e in pending.entries if e.pbc_location and e.pbc_location not in recorded]
    kept = sum(1 for a, b in zip(merged, workbook, strict=True) if a is not b) + len(unknown)
    if kept:
        log.warning(
            "%s is newer than its snapshot; keeping %d row(s) only the snapshot had right",
            path.name, kept,
        )
    return merged + unknown


def _as_float(value: object) -> float:
    """A number from an index cell, or 0.0 if somebody typed over it in Excel."""
    try:
        return float(value or 0)
    except (TypeError, ValueError):
        return 0.0


def _header_at(rows) -> int | None:
    """Where the index's header row sits among ``rows``, or None.

    Found, not assumed: a person who typed a title above it, or sorted the
    sheet with "my data has headers" unchecked, moved it. The columns every
    version of the index has had (``_MANDATORY_COLUMNS``) are what name it,
    and it is looked for no further down than ``_HEADER_WITHIN``.
    """
    for position, row in enumerate(rows):
        if position >= _HEADER_WITHIN:
            return None
        cells = {str(cell or "").strip() for cell in row}
        if all(INDEX_LAYOUT[name][0] in cells for name in _MANDATORY_COLUMNS):
            return position
    return None


def _sheet_with_the_header(wb: Workbook):
    """The worksheet the index is on, or None if no sheet carries its header.

    ``wb.active`` is whatever tab a person left selected when they saved,
    which is how a renamed index tab and a notes tab of their own read as
    an empty index: nothing was there to refuse, and the next write rebuilt
    the workbook over both. The sheet is chosen by the header instead, with
    the one the tracker writes preferred when more than one carries it.
    """
    carrying = [ws for ws in wb.worksheets if _header_at(ws.iter_rows(values_only=True)) is not None]
    for ws in carrying:
        if ws.title == INDEX_SHEET:
            return ws
    return carrying[0] if carrying else None


def _holds_anything(ws) -> bool:
    return any(cell not in (None, "") for row in ws.iter_rows(values_only=True) for cell in row)


def _blank(row, positions) -> bool:
    """A row none of ``positions`` holds anything in.

    A row is blank by the columns the index knows - not by its first
    physical cell, which a column somebody inserted at A, or a cleared
    Received cell, would make of every row; read as [] the next write
    would then drop a person's filing with everything else (the eleventh
    reading).
    """
    return not row or all(
        (row[position] if position < len(row) else None) in (None, "") for position in positions
    )


def _read_index_workbook(path: Path) -> list[IndexEntry]:
    if not path.exists():
        return []
    wb = load_workbook(path, data_only=True)
    try:
        ws = _sheet_with_the_header(wb)
        if ws is None:
            # No header row in a workbook that holds something is an index
            # the tracker must not touch (the twelfth reading).
            if any(_holds_anything(sheet) for sheet in wb.worksheets):
                raise FilingError(
                    f"{path.name} has no header row the tracker knows ({', '.join(INDEX_LAYOUT[n][0] for n in _MANDATORY_COLUMNS)}) "
                    f"within the first {_HEADER_WITHIN} rows of any of its sheets ({', '.join(wb.sheetnames)}); "
                    "it was edited by hand - restore it before the next run"
                )
            return []
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    header_at = _header_at(rows)
    # By header name, so an index written with columns since dropped (Filed
    # As, Document) or before one was added (Candidates) still reads.
    headers = [str(h or "").strip() for h in rows[header_at]]
    by_field = {
        name: headers.index(header)
        for name, (header, _) in INDEX_LAYOUT.items()
        if header in headers
    }
    # Above the header is data too. A sort with "my data has headers"
    # unchecked leaves the header wherever its own text sorts - last when
    # the sheet is sorted on Received, in the middle when it is sorted on
    # Original Name - and everything above it was dropped in silence, a
    # person's filing included (the thirteenth reading). Only a row with
    # none of the mandatory columns filled is a title somebody typed.
    mandatory = [by_field[name] for name in _MANDATORY_COLUMNS if name in by_field]
    above = [row for row in rows[:header_at] if not _blank(row, mandatory)]
    if above:
        log.warning(
            "%s holds %d row(s) above its header row - the sheet was sorted with the header "
            "among the data; they are read, and the next write puts the header back on top",
            path.name, len(above),
        )
    entries = []
    for row in above + [r for r in rows[header_at + 1:] if not _blank(r, by_field.values())]:
        values: dict[str, object] = {}
        for name, position in by_field.items():
            raw = row[position] if position < len(row) else None
            values[name] = _as_float(raw) if name == "size_kb" else str(raw or "")
        entries.append(IndexEntry(**values))
    return entries


def _index_workbook(path: Path) -> tuple[Workbook, object]:
    """The workbook to write the index into, and the empty sheet for its rows.

    A rewrite built from nothing destroyed whatever else the workbook held
    - a sheet a person added beside the index, and the name they gave the
    index's own tab. The workbook already there is reopened and only the
    index's sheet is replaced, in place and under its own name; everything
    else is left as it was. Excel holding the file is passed up so the
    write is retried and then snapshotted; anything that is not a workbook
    any more is written from nothing, since every row is in ``entries``.
    """
    if path.exists():
        try:
            wb = load_workbook(path)
        except OSError:
            raise                      # held open: write_index retries, then snapshots
        except Exception as exc:       # not a workbook any more; every row is still in hand
            log.warning("%s could not be reopened (%s); it is written afresh", path.name, exc)
        else:
            ours = _sheet_with_the_header(wb)
            if ours is None and INDEX_SHEET in wb.sheetnames:
                ours = wb[INDEX_SHEET]
            title, at = (ours.title, wb.sheetnames.index(ours.title)) if ours is not None else (INDEX_SHEET, 0)
            if ours is not None:
                wb.remove(ours)        # replaced, not appended to: the rows start at 1 again
            return wb, wb.create_sheet(title, at)
    wb = Workbook()
    ws = wb.active
    ws.title = INDEX_SHEET
    return wb, ws


def _save_index(path: Path, entries: list[IndexEntry]) -> None:
    wb, ws = _index_workbook(path)
    ws.append(list(INDEX_COLUMNS))
    # The row is counted, not asked for: openpyxl finds max_row by walking
    # every cell, which made writing the index quadratic in its rows.
    for row_number, entry in enumerate(entries, start=2):
        ws.append(entry.as_row())
        for cell in ws[row_number]:
            as_text(cell)             # a file called "=SUM scan.pdf" is a name, not a formula
    for index, (_, width) in enumerate(INDEX_LAYOUT.values(), start=1):
        ws.column_dimensions[get_column_letter(index)].width = width
    ws.freeze_panes = "A2"
    save_workbook_atomically(wb, path)


def write_index(
    path: Path,
    entries: list[IndexEntry],
    *,
    retries: int | None = None,
    retry_delay: float | None = None,
) -> bool:
    """Rewrite ``INDEX_FILENAME`` from ``entries`` (oldest first), lock-resiliently.

    The index is the audit trail for originals that have *already been
    moved* and for decisions a person has *already made*, so losing a row,
    or an edit to one, is not an option. If Excel holds the workbook open,
    the write is retried with backoff; if it stays locked, ``entries`` -
    all of it, exactly what the workbook should now say - is saved to
    ``INDEX_PENDING_FILENAME``. ``read_index`` returns that snapshot in the
    workbook's place until a later write lands it. Saving only the rows
    past the workbook's end used to drop a row that had been rewritten
    (a parked file a person filed) while the file itself had already moved.

    A snapshot written while Excel holds the workbook wins over cells typed
    into it during that window; that was always so, since every write
    rebuilds the workbook from ``entries``. Nobody edits the index by hand.

    Returns True if the workbook was written, False if the snapshot was deferred.
    """
    retries = LOCK_RETRIES if retries is None else retries
    delay = LOCK_RETRY_DELAY if retry_delay is None else retry_delay
    for attempt in range(1, retries + 1):
        try:
            _save_index(path, entries)
        except OSError as exc:
            # Excel holding the file is the usual reason; a network share
            # blinking or a disk with no room are the others, and a row for
            # an original already moved must reach the snapshot either way.
            log.warning("Index not written (attempt %d/%d): %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2
            continue
        # The workbook is written. A sidecar that cannot be deleted now is
        # older than it and is read as such; it is not a reason to defer.
        _discard_pending_index(path)
        return True

    _save_pending_index(path, entries)
    log.error(
        "%s still not written after %d attempts; a snapshot of all %d row(s) deferred to %s",
        path.name, retries, len(entries), INDEX_PENDING_FILENAME,
    )
    return False


# ------------------------------------------------------------------- walk ----


def iter_drops(shared_dir: Path) -> list[Path]:
    """Client-dropped files awaiting sorting.

    Everything under ``SHARED_DIR_NAME/`` except the preserved ``PBC_DIR_NAME/`` originals,
    the generated README, and OS/sync junk. Subfolders are included — a
    client who drags a whole folder in still gets it sorted.
    """
    if not shared_dir.is_dir():
        return []
    pbc = shared_dir / PBC_DIR_NAME
    drops = []
    for path in sorted(shared_dir.rglob("*")):
        if not path.is_file() or is_ignored(path) or _through_a_link(path, shared_dir) or not _storable(path):
            continue
        if path == shared_dir / README_NAME:
            continue
        if pbc in path.parents or path == pbc:
            continue
        drops.append(path)
    return drops


def _storable(path: Path) -> bool:
    """Whether the name can be written into the index at all. NTFS holds
    names as UTF-16 and takes an unpaired surrogate (a truncated emoji, a
    Mac's or a NAS's name in a broken code page); the workbook and the
    snapshot sidecar are UTF-8 and cannot hold it. A control character is
    the same wound from the other side: a POSIX filesystem takes one in a
    name, and a workbook is XML, which cannot hold it - openpyxl refuses
    the cell (``ILLEGAL_CHARACTERS_RE``, its own list), and the refusal is
    a ValueError, so the write is not even retried. Either name once took
    the whole index down, every pass, with the pass's originals moved."""
    try:
        path.name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return ILLEGAL_CHARACTERS_RE.search(path.name) is None


#: The reparse tags that make a name a link to somewhere else. A cloud
#: sync client's placeholder is a reparse point too (its tag is the
#: client's own) and is a file of the client's, not a link.
_LINK_TAGS = frozenset(
    tag for tag in (getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", None), getattr(stat, "IO_REPARSE_TAG_SYMLINK", None))
    if tag is not None
)


def _is_link(path: Path) -> bool:
    """A symlink, or on Windows a junction (a mount point)."""
    try:
        st = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(st.st_mode) or getattr(st, "st_reparse_tag", 0) in _LINK_TAGS


def _through_a_link(path: Path, root: Path) -> bool:
    """True when ``path`` is reached through a link below ``root``.

    ``rglob`` follows a junction, and a junction a client (or a sync
    client) leaves in the drop folder points anywhere: at a folder outside
    the engagement whose files would then be *moved* into PBC as the
    client's originals. What lies behind a link is not a drop.
    """
    for part in (path, *path.parents):
        if part == root:
            return False
        if _is_link(part):
            return True
    return False


def unreachable_drops(shared_dir: Path) -> list[Path]:
    """Names under ``SHARED_DIR_NAME/`` that are listed but cannot be
    handled under that name: on Windows a name ending in a dot or a space,
    or a device name (``nul``), which a Mac or a sync client can deliver;
    anywhere, a name the index cannot hold (``_storable``), inside
    ``PBC_DIR_NAME/`` too, where it would otherwise be sorted as a stray
    every pass. Reported, so a document that can never be sorted is not
    a silence."""
    if not shared_dir.is_dir():
        return []
    pbc = shared_dir / PBC_DIR_NAME
    return sorted(
        path for path in shared_dir.rglob("*")
        if not _storable(path)
        or (not path.is_file() and not path.is_dir() and not _is_link(path)
            and pbc not in path.parents and path != pbc)
    )


def unlistable_folders(shared_dir: Path) -> list[Path]:
    """Folders under ``SHARED_DIR_NAME/`` the run cannot list (an ACL that
    denies the run's account; a folder moved in from elsewhere keeps its
    own). ``rglob`` passes over them without a word, and every document
    inside would be invisible to every list; these are reported instead."""
    if not shared_dir.is_dir():
        return []
    failed: list[Path] = []

    def onerror(exc: OSError) -> None:
        if exc.filename:
            failed.append(Path(exc.filename))

    # The same ground the other walks cover: not behind a link (os.walk
    # descends a junction), not a sync client's staging folder. PBC is
    # walked - a client drops there too, and unrecorded_in_pbc() reads it.
    for folder, subfolders, _files in os.walk(shared_dir, onerror=onerror):
        subfolders[:] = [
            name for name in subfolders
            if not _is_link(Path(folder) / name) and not is_sync_staging(name)
        ]
    return sorted(failed)


def unfinished_drops(shared_dir: Path) -> list[Path]:
    """Files under ``SHARED_DIR_NAME/`` named as a transfer still in
    progress (``UNFINISHED_SUFFIXES``): left alone until it finishes, and
    named in the report, so one that never finishes is not a silence."""
    if not shared_dir.is_dir():
        return []
    pbc = shared_dir / PBC_DIR_NAME
    return sorted(
        path for path in shared_dir.rglob("*")
        if path.is_file() and path.name.lower().endswith(UNFINISHED_SUFFIXES)
        and pbc not in path.parents
        and not any(is_sync_staging(part) for part in path.parts)
    )


def unrecorded_in_pbc(pbc_dir: Path, engagement_dir: Path, entries: list[IndexEntry]) -> list[Path]:
    """Files sitting in ``PBC_DIR_NAME/`` that no index row accounts for.

    The client can see ``PBC_DIR_NAME/`` and has been told to drop things anywhere,
    so some will land here. They are already where an original belongs;
    they just have not been filed or recorded yet.
    """
    recorded = {e.pbc_location for e in entries if e.pbc_location}
    return [
        path for path in iter_candidate_files(pbc_dir)
        if path.relative_to(engagement_dir).as_posix() not in recorded
        and not _through_a_link(path, pbc_dir) and _storable(path)
    ]


#: The sentence a replaced original gets. It is a file error, not a new
#: drop: the working copy was made from bytes that are gone, and which of
#: the two the client meant is not the filer's to guess.
REPLACED_IN_PBC = (
    "{location} no longer holds the bytes recorded on {received}; its working copy "
    "{prepared} was made from the earlier file - a person should look"
)


def replaced_in_pbc(
    pbc_dir: Path, engagement_dir: Path, entries: list[IndexEntry]
) -> list[tuple[Path, IndexEntry]]:
    """Recorded originals in ``PBC_DIR_NAME/`` whose bytes no longer match their row.

    The client can see the folder and Explorer offers "Replace", so a
    corrected document can land over the one already filed. Matching on
    the path alone would call that file recorded and never look at it
    again, while the working copy under ``PREPARED_DIR_NAME`` stayed the
    old one. A same-size edit (one number in a CSV) with a preserved
    modification time is the common shape of it, so nothing but the bytes
    decides: the size first, then the digest. A cloud placeholder is not
    read - hashing it would download it - and is looked at when it is back.
    """
    by_location: dict[str, IndexEntry] = {}
    for entry in entries:            # the newest row for a location wins
        if entry.pbc_location and entry.digest:
            by_location[entry.pbc_location] = entry
    replaced = []
    for path in iter_candidate_files(pbc_dir):
        if _through_a_link(path, pbc_dir):
            continue
        entry = by_location.get(path.relative_to(engagement_dir).as_posix())
        if entry is None:
            continue
        if is_cloud_placeholder(path):
            continue
        try:
            if round(path.stat().st_size / 1024, 1) == entry.size_kb and sha256_of(path) == entry.digest:
                continue
        except OSError:
            continue                 # unreadable now; the next run looks again
        replaced.append((path, entry))
    return replaced


#: The sentence a recorded original that has left PBC_DIR_NAME gets. The
#: client can see that folder and Explorer offers Delete, Rename and drag:
#: every other disagreement between the index and the disk is said every
#: pass, and this one was said by nothing at all while the row went on
#: naming a path that holds no file. Said every pass until it is back or a
#: person has looked; the working copy is not touched over it.
MISSING_IN_PBC = (
    "the original recorded at {location} on {received} is no longer there - deleted, "
    "renamed or moved after it was preserved; a person should look"
)
#: The sentence a row whose original turned up elsewhere in PBC_DIR_NAME
#: gets. Bytes are what tie a row to a document, so a stray carrying a
#: missing row's digest is that original under a new name or in a new
#: folder, not a second copy to file: the row follows the file rather than
#: a Duplicate row being written and the old row left naming nothing.
MOVED_IN_PBC = (
    "the original recorded at {location} is now at {now} - the client renamed or moved "
    "it and the bytes are the same, so the row follows it"
)
#: What that row's Reason keeps, so the path it arrived at is not lost.
MOVED_FROM_IN_PBC = "the client moved it from {location}, noticed on {found}"


def _absent(path: Path) -> bool:
    """True only where the filesystem says there is no such file.

    Not "could not be read": a permission, a share that blinked or a name
    this host cannot open is a thing to look again at next pass, never a
    reason to tell a person their client's original is gone. A cloud
    placeholder is a file - the sync client has not brought it down, which
    is not the same as the client having deleted it.
    """
    try:
        path.stat()
    except FileNotFoundError:
        return True
    except (OSError, ValueError):
        return False
    return False


def _missing_positions(engagement_dir: Path, entries: list[IndexEntry]) -> list[int]:
    """Where in ``entries`` the rows sit whose recorded original is gone."""
    newest: dict[str, int] = {}
    for position, entry in enumerate(entries):
        if entry.pbc_location:
            newest[entry.pbc_location] = position     # the newest row for a location wins
    return [position for location, position in newest.items() if _absent(engagement_dir / location)]


def missing_in_pbc(engagement_dir: Path, entries: list[IndexEntry]) -> list[IndexEntry]:
    """Recorded originals that are no longer where their row says they are.

    Every row that names a location is looked at - filed, parked and
    duplicate alike - because each is a promise that the client's own file
    is still in the folder they can see. Nothing else in a pass would
    notice: an untouched row is not a drop, not a stray and not a
    replacement, so the record could empty out while the scan went on
    reading the working copies and calling every request Received.
    """
    return [entries[position] for position in _missing_positions(engagement_dir, entries)]


def _row_these_bytes_left(path: Path, waiting: dict[str, list[int]]) -> int | None:
    """The missing row ``path`` holds the bytes of, if any; each row once."""
    if not waiting or is_cloud_placeholder(path):
        return None
    try:
        digest = sha256_of(path)
    except OSError:
        return None                  # unreadable now; the next run looks again
    positions = waiting.get(digest)
    if not positions:
        return None
    position = positions.pop(0)
    if not positions:
        del waiting[digest]
    return position


def _follow_moved_originals(
    engagement_dir: Path, entries: list[IndexEntry], strays: list[Path], found: str
) -> tuple[list[Path], list[tuple[Path, IndexEntry]], list[IndexEntry]]:
    """Point the rows of originals the client moved inside PBC_DIR_NAME at
    where their bytes now are, and name the rows that are simply gone.

    A rename or a drag inside the folder the client can see leaves two
    halves of one document: a row naming a path that holds nothing, and a
    file no row accounts for. Sorting that file as a new drop writes a
    Duplicate row for a document already filed and leaves the old row
    pointing at nothing for ever, so the bytes decide: they are the same
    original and the row follows the file. Nothing else moves - the
    working copy the earlier pass made is still the working copy, and what
    the scanner sees is unchanged. A row recorded without its bytes
    (decision 65) is nobody's and is never relocated, only said.

    Returns the strays that are still strays, the moves recorded (the file
    and the row as it was), and the rows whose original nothing holds.
    """
    gone = _missing_positions(engagement_dir, entries)
    if not gone:
        return strays, [], []
    waiting: dict[str, list[int]] = {}
    for position in gone:
        if entries[position].digest:
            waiting.setdefault(entries[position].digest, []).append(position)
    kept: list[Path] = []
    moved: list[tuple[Path, IndexEntry]] = []
    followed: set[int] = set()
    for path in strays:
        position = _row_these_bytes_left(path, waiting)
        if position is None:
            kept.append(path)
            continue
        was = entries[position]
        entries[position] = replace(
            was,
            pbc_location=path.relative_to(engagement_dir).as_posix(),
            reason=f"{was.reason}; {MOVED_FROM_IN_PBC.format(location=was.pbc_location, found=found)}",
        )
        moved.append((path, was))
        followed.add(position)
        log.warning("The original recorded at %s is now at %s", was.pbc_location, path.name)
    return kept, moved, [entries[position] for position in gone if position not in followed]


#: The sentence a row recorded without its bytes gets when its working
#: copy and its original no longer agree. Which is the client's document
#: is not the filer's to guess: the copy may have been annotated, or its
#: name taken by a later drop called the same; the original may have been
#: replaced. Said every pass until a person has looked.
UNTIED_IN_PBC = (
    "{location} was recorded without its bytes on {received} and its working copy "
    "{prepared} no longer matches it - a person should look"
)


def _copy_taken_by_a_later_row(entries: list[IndexEntry], position: int) -> bool:
    """Whether a row written after ``entries[position]`` records a working
    copy at the same path. A parked name is the client's, and a freed one
    is taken by the next drop called the same: the index itself then says
    the earlier row's copy is gone, and what sits there is the later row's."""
    location = entries[position].prepared_location
    return bool(location) and any(
        later.prepared_location == location for later in entries[position + 1:]
    )


def _record_missing_digests(
    engagement_dir: Path, entries: list[IndexEntry]
) -> tuple[int, list[tuple[Path, IndexEntry]]]:
    """Fill in the digest and size of every row that has none, where the
    bytes can be tied to the row. Returns how many, and the rows that
    could not be.

    A row with no digest (decision 65) is tied to its bytes only when its
    working copy - what the pass made from the original - and the original
    in ``PBC_DIR_NAME/`` still agree. The original alone is no evidence
    (the client may have replaced it since; the tenth reading); the copy
    alone is no evidence either (its name is the client's and a freed name
    is taken by the next drop called the same, and a reviewer's PDF app
    may have re-saved it; the eleventh reading). Where the two disagree,
    nothing is adopted and the row is said out loud (``UNTIED_IN_PBC``).
    A row with no working copy left stays nobody's.
    """
    filled = 0
    untied: list[tuple[Path, IndexEntry]] = []
    for position, entry in enumerate(entries):
        if entry.digest or not entry.prepared_location or not entry.pbc_location:
            continue
        if _copy_taken_by_a_later_row(entries, position):
            continue                 # the row's copy is gone; what sits at its path is another row's
        copy = engagement_dir / entry.prepared_location
        original = engagement_dir / entry.pbc_location
        if not copy.is_file() or is_cloud_placeholder(copy):
            continue
        if not original.is_file() or is_cloud_placeholder(original):
            continue
        try:
            digest = sha256_of(copy)
            if sha256_of(original) != digest:
                untied.append((original, entry))
                continue
            size_kb = round(original.stat().st_size / 1024, 1)
        except OSError:
            continue                 # unreadable now; the next run looks again
        entries[position] = replace(entry, digest=digest, size_kb=size_kb)
        filled += 1
        log.info("Recorded the bytes of %s, preserved earlier but unread", entry.pbc_location)
    return filled, untied


def _prune_empty_dirs(shared_dir: Path, keep: Path) -> None:
    """Remove folders the client dragged in that are empty now their files
    have moved to PBC_DIR_NAME/. Deepest first; anything that is not empty, is the
    PBC folder, or is a sync client's staging folder is left alone."""
    candidates = sorted(
        (p for p in shared_dir.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for folder in candidates:
        if folder == keep or keep in folder.parents:
            continue
        if any(is_sync_staging(part) for part in folder.parts):
            continue
        if _through_a_link(folder, shared_dir):
            continue        # rmdir on a junction removes the junction, whatever it points at
        try:
            folder.rmdir()  # only succeeds when empty
        except OSError:
            continue


# ------------------------------------------------------------------- file ----


def file_drops(
    engagement_dir: Path | str,
    *,
    today: dt.date | None = None,
    dry_run: bool = False,
) -> FileReport:
    """Sort one engagement's drop folder. Returns what was done.

    A dry run decides everything and moves nothing — use it to preview
    where files would land before letting the scheduled job do it.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()

    shared_dir = engagement_dir / SHARED_DIR_NAME
    pbc_dir = shared_dir / PBC_DIR_NAME
    prepared_dir = engagement_dir / PREPARED_DIR_NAME
    review_dir = prepared_dir / REVIEW_DIR_NAME
    index_path = engagement_dir / INDEX_FILENAME

    report = FileReport(engagement_dir=engagement_dir, dry_run=dry_run)
    # A sort and a scan must never overlap (see tracker.locking), and the
    # lock comes before anything is read: the manifest, the index and the
    # drop folder are what this run decides from, and a run that finished
    # in between must not be invisible to it. A dry run writes nothing, so
    # it needs no lock and never blocks a real run.
    with engagement_lock(engagement_dir) if not dry_run else nullcontext():
        items = load_manifest(engagement_dir / MANIFEST_FILENAME)
        by_id = {i.identifier: i for i in items}
        entries = read_index(index_path, quarantine=not dry_run)
        # What the record already says, taken before anything in this pass
        # touches a row, so what this pass wrote is what gets recorded.
        before = {ledger_key(entry): _ledger_row(entry) for entry in entries}
        # An original preserved by a pass that could not read it back has no
        # digest (decision 65). While it has none, a replacement is never
        # noticed and a person's filing of it is never honoured; a later
        # pass records the bytes where its copy and the original still agree,
        # and says so where they do not.
        recorded_digests, untied = (0, []) if dry_run else _record_missing_digests(engagement_dir, entries)
        for path, earlier in untied:
            report.attention.append(FileError(path.name, UNTIED_IN_PBC.format(
                location=earlier.pbc_location, received=earlier.received,
                prepared=earlier.prepared_location,
            ), True))
        stamp = today.isoformat()
        drops = iter_drops(shared_dir)
        # A file still being written (a sync client's or a browser's
        # ``TEMP_SUFFIX`` name) is not sorted, and is not passed over in
        # silence either: it is reported as waiting, like a placeholder.
        report.waiting.extend(unfinished_drops(shared_dir))
        for path in unreachable_drops(shared_dir):
            report.errors.append(FileError(
                path.name, "cannot be handled under this name (a name Windows refuses, or the index cannot hold); rename it", True
            ))
            log.warning("Left %s in place: the name cannot be handled", path.name)
        for folder in unlistable_folders(shared_dir):
            report.errors.append(FileError(
                folder.name, "is a folder this run cannot list (its permissions deny it); whatever is inside is not sorted", True
            ))
            log.warning("Could not list %s: its permissions deny it", folder)
        strays = unrecorded_in_pbc(pbc_dir, engagement_dir, entries) if pbc_dir.is_dir() else []
        # An original the client deleted, renamed or moved after it was
        # recorded is a row naming a path that holds nothing. Where a stray
        # carries the row's bytes the row follows the file (and is not
        # adopted a second time); the rest are said, every pass.
        strays, moved, gone = _follow_moved_originals(engagement_dir, entries, strays, stamp)
        # Where a row's identity in the record moved to, and from.
        moved_keys = {
            path.relative_to(engagement_dir).as_posix(): ledger_key(earlier)
            for path, earlier in moved
        }
        for path, earlier in moved:
            report.attention.append(FileError(path.name, MOVED_IN_PBC.format(
                location=earlier.pbc_location,
                now=path.relative_to(engagement_dir).as_posix(),
            ), True))
        for earlier in gone:
            report.attention.append(FileError(earlier.original_name, MISSING_IN_PBC.format(
                location=earlier.pbc_location, received=earlier.received,
            ), True))
        # An original replaced under its own name is said loudly, every run,
        # until a person has looked; it is not sorted again and not guessed.
        for path, earlier in replaced_in_pbc(pbc_dir, engagement_dir, entries) if pbc_dir.is_dir() else []:
            report.attention.append(FileError(path.name, REPLACED_IN_PBC.format(
                location=earlier.pbc_location, received=earlier.received,
                prepared=earlier.prepared_location or "(none)",
            ), True))
        # The row that holds each document's bytes. A Duplicate row only
        # points at another row; letting it shadow the Filed row would hide
        # a working copy that has since been deleted, and a re-send that
        # answers "Missing" would be called a duplicate for ever. Every other
        # decision holds its bytes, a person's ``NOT_REQUESTED`` included:
        # the same document sent again is that same document, and parking it
        # a second time would put back the warning they just cleared.
        known = {e.digest: e for e in entries if e.digest and e.decision != DUPLICATE}
        # Rows a locked Excel deferred last time still belong in the workbook -
        # fold them in as soon as it is free, whether or not this run sorts
        # anything; so does a row that has just followed its original.
        sidecar_waiting = (
            _pending_index_path(index_path).exists() or recorded_digests > 0 or bool(moved)
        )
        # What the router learns about each document is what the scan will
        # want to know about its working copy (same bytes): the verdicts go
        # into the engagement's content cache, keyed by content. It is made
        # whether or not there is anything to sort, because the tidy-up at
        # the end of a pass is owed to a pass that sorted nothing too.
        cache = ContentCache(engagement_dir / CACHE_FILENAME)
        # Names claimed during this run, so a dry run previews the same numbering
        # a real run would produce (nothing is on disk to collide with yet).
        reserved: dict[Path, set[str]] = {}
        recorded = len(entries)
        try:
            if drops or strays:
                if not dry_run:
                    pbc_dir.mkdir(parents=True, exist_ok=True)
                    prepared_dir.mkdir(parents=True, exist_ok=True)
                # Existing request folders, so a Document renamed in Excel keeps
                # filing into the folder that already holds its earlier files.
                assigned = assign_folders(prepared_dir, [i.identifier for i in items])
                _sort_all(drops, strays, pbc_dir, entries, stamp, _SortContext(
                    items=items, by_id=by_id, known=known, prepared_dir=prepared_dir,
                    review_dir=review_dir, reserved=reserved, assigned=assigned,
                    dry_run=dry_run, report=report,
                    cache=cache, pdf_cache=PdfVerdictCache(),
                ))
        finally:
            # Whatever happened above, every original that was moved is on
            # record - and a snapshot waiting from last time is landed even
            # when every drop this time was left in place, or there was
            # nothing to sort at all.
            if not dry_run and (len(entries) > recorded or sidecar_waiting):
                report.index_deferred = not write_index(index_path, entries)
                # The record goes after the write it records, in the same
                # locked section - whether the workbook took the rows or the
                # snapshot did, because the sidecar is the workaround and
                # this is the record.
                _record_write(engagement_dir, index_path, before, entries, moved=moved_keys)
        # The tidy-up is owed to every pass, not only one that sorted
        # something: an empty folder the client dragged in outlives the
        # files that were in it, and a pass that found nothing to do used
        # to leave it there for ever.
        if not dry_run:
            cache.save()
            _prune_empty_dirs(shared_dir, keep=pbc_dir)
    return report


def _sort_all(
    drops: list[Path],
    strays: list[Path],
    pbc_dir: Path,
    entries: list[IndexEntry],
    stamp: str,
    run: _SortContext,
) -> None:
    """Decide and record every drop and every stray, one at a time.

    Each file is handled on its own: a file the sync client still holds
    open is left in place for the next run, and one that fails *after* it
    was preserved is recorded as needing review with the error, so no one
    bad file costs the rest of the pass or the audit trail. The caller
    writes the index whatever happens in here.
    """
    report, dry_run, known = run.report, run.dry_run, run.known
    engagement_dir = run.prepared_dir.parent
    for drop, already_in_pbc in (
        [(d, False) for d in drops] + [(p, True) for p in strays]
    ):
        # A file the sync client has not downloaded is not a document yet.
        if is_cloud_placeholder(drop):
            report.waiting.append(drop)
            continue

        try:
            drop.stat()          # still there, and readable: a file mid-write is left
        except OSError as exc:
            report.errors.append(FileError(
                drop.name, f"could not read it ({exc}); left in place", True
            ))
            log.warning("Left %s in place: %s", drop.name, exc)
            continue

        # Preserve the original first: it is the record, whatever happens next.
        if already_in_pbc or dry_run:
            pbc_target = drop if already_in_pbc else pbc_dir / drop.name
        else:
            try:
                pbc_target = _unique_path(pbc_dir, drop.name)
                _move_whole(drop, pbc_target)
            except OSError as exc:
                report.errors.append(FileError(
                    drop.name,
                    f"could not move it into {PBC_DIR_NAME} ({exc}); "
                    "left in place",
                    True,
                ))
                log.warning("Left %s in place: %s", drop.name, exc)
                continue
        pbc_rel = pbc_target.relative_to(engagement_dir).as_posix()
        # The record is of the bytes that were preserved: hashed where
        # they now are, after the move, so a sync client landing a newer
        # version in between can never leave the index describing one
        # file and the folder holding another.
        recorded_at = drop if dry_run and not already_in_pbc else pbc_target
        try:
            digest = sha256_of(recorded_at)
            size_kb = round(recorded_at.stat().st_size / 1024, 1)
        except OSError as exc:
            if already_in_pbc or dry_run:
                report.errors.append(FileError(
                    drop.name, f"could not read it ({exc}); left in place", True
                ))
                log.warning("Left %s in place: %s", drop.name, exc)
                continue
            digest, size_kb = "", 0.0     # moved, unreadable now: recorded anyway
            log.warning("Preserved %s but could not read it back: %s", drop.name, exc)

        try:
            entry = _sort_one(drop, pbc_target, pbc_rel, digest, size_kb, stamp, run)
        except Exception as exc:  # the original is safe; say so and go on
            log.exception("Could not file %s", drop.name)
            entry = IndexEntry(
                received=stamp, original_name=drop.name, size_kb=size_kb,
                digest=digest, identifier="",
                prepared_location="", pbc_location=pbc_rel,
                decision=NEEDS_REVIEW,
                reason=(
                    f"could not be filed ({exc.__class__.__name__}: {exc}); "
                    f"original preserved in {pbc_rel} - file it by hand"
                ),
            )
            report.errors.append(FileError(drop.name, entry.reason, False))
            report.review.append(entry)

        entries.append(entry)
        if entry.decision != DUPLICATE and digest:
            known[digest] = entry


@dataclass(frozen=True, slots=True)
class _SortContext:
    """What every drop in one run is sorted against: the manifest, the index
    so far, the folders, the names claimed, and the run's caches. Built once
    in :func:`file_drops`; :func:`_sort_one` reads it. Sixteen positional
    arguments - three of them strings, two of them dicts - was how an
    argument-order slip could stay silent."""

    items: list[RequestItem]
    by_id: dict[str, RequestItem]
    known: dict[str, IndexEntry]           # digest -> the row that already holds it
    prepared_dir: Path
    review_dir: Path
    reserved: dict[Path, set[str]]         # names claimed this run, per folder
    assigned: dict[str, list[Path]]        # identifier -> its existing folders
    dry_run: bool
    report: FileReport
    cache: ContentCache
    pdf_cache: PdfVerdictCache


def _sort_one(
    drop: Path,
    pbc_target: Path,
    pbc_rel: str,
    digest: str,
    size_kb: float,
    stamp: str,
    run: _SortContext,
) -> IndexEntry:
    """Decide one preserved original's fate and, unless dry-running, copy it."""
    known, report, dry_run = run.known, run.report, run.dry_run
    refiled = ""
    if digest and digest in known:
        earlier = known[digest]
        engagement_dir = run.prepared_dir.parent
        if (
            earlier.decision == FILED
            and earlier.prepared_location
            and not (engagement_dir / earlier.prepared_location).exists()
        ):
            # The same document again, and its working copy is gone from
            # PREPARED_DIR_NAME - deleted by hand, most likely. A re-send is the
            # client answering "Missing"; calling it a duplicate would keep
            # the row Missing for ever. File it again.
            refiled = (
                f"re-filed: the earlier copy {earlier.prepared_location} "
                f"was no longer in {PREPARED_DIR_NAME}"
            )
        else:
            entry = IndexEntry(
                received=stamp, original_name=drop.name, size_kb=size_kb,
                digest=digest, identifier=earlier.identifier,
                prepared_location="",
                pbc_location=pbc_rel, decision=DUPLICATE,
                reason=(
                    f"identical to {earlier.original_name}"
                    + (f"; already filed as {earlier.filed_as}" if earlier.filed_as else "")
                ),
            )
            report.duplicates.append(entry)
            return entry

    routing = route_file(
        pbc_target if not dry_run else drop, run.items,
        digest=digest, cache=run.cache, pdf_cache=run.pdf_cache,
    )
    item = run.by_id.get(routing.identifier or "")

    if routing.routed and item is not None:
        dest_folder = request_folder(item, run.assigned, run.prepared_dir)
        if dest_folder not in run.reserved:
            run.reserved[dest_folder] = (
                {p.name.lower() for p in dest_folder.iterdir()}
                if dest_folder.is_dir()
                else set()
            )
        filed_as = prepared_name_for(item, extension_of(drop), run.reserved[dest_folder])
        if not dry_run:
            dest_folder.mkdir(parents=True, exist_ok=True)
            existing = _existing_copy(dest_folder, pbc_target, digest)
            if existing is not None:
                filed_as = existing.name
            else:
                _copy_whole(pbc_target, dest_folder / filed_as)
        entry = IndexEntry(
            received=stamp, original_name=drop.name, size_kb=size_kb,
            digest=digest, identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            pbc_location=pbc_rel, decision=FILED,
            reason=f"{routing.reason}; {refiled}" if refiled else routing.reason,
            candidates=_CANDIDATE_SEP.join(routing.candidates),
            evidence=format_evidence(routing.evidence_record),
        )
        report.filed.append(entry)
        return entry

    review_name = drop.name
    if not dry_run:
        run.review_dir.mkdir(parents=True, exist_ok=True)
        review_target = _existing_copy(run.review_dir, pbc_target, digest)
        if review_target is None:
            review_target = _unique_path(run.review_dir, drop.name)
            _copy_whole(pbc_target, review_target)
        review_name = review_target.name
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier="",
        prepared_location=prepared_location(run.review_dir, review_name),
        pbc_location=pbc_rel, decision=NEEDS_REVIEW, reason=routing.reason,
        candidates=_CANDIDATE_SEP.join(routing.candidates),
        evidence=format_evidence(routing.evidence_record),
    )
    report.review.append(entry)
    return entry


# ----------------------------------------------------------------- assign ----


@dataclass(frozen=True, slots=True)
class AssignResult:
    """What filing one parked document by hand did."""

    entry: IndexEntry            # the rewritten index row
    moved_review_copy: bool      # True: the parked copy (REVIEW_DIR_NAME) became the working copy
    keyword: str = ""            # keyword added to the row's Any Keywords, if any
    keyword_note: str = ""       # why it was not added, when it was not
    index_deferred: bool = False
    left_in_review: str = ""     # a parked copy that no longer held the row's bytes, and stayed


def assign_review_file(
    engagement_dir: Path | str,
    original: str,
    identifier: str,
    *,
    keyword: str = "",
    today: dt.date | None = None,
) -> AssignResult:
    """File a parked document under a request, the way the filer would have.

    ``original`` is the index row to act on: its PBC location
    (``SHARED_DIR_NAME/PBC_DIR_NAME/<original name>``) or, failing that, its original name among
    the rows still marked Needs Review. The working copy is created under the
    canonical name in the request's folder - moved from ``REVIEW_DIR_NAME`` when it is still there, copied from ``PBC_DIR_NAME/`` when it is not -
    and the index row is rewritten as Filed with the decision attributed to
    a person. The original in ``PBC_DIR_NAME/`` is not touched.

    ``keyword`` is optional: added to the request's Any Keywords so the next
    document like this one routes itself. If Excel holds the manifest the
    filing still happens and the note says the keyword was not saved.

    The rules the filer lives by still hold: nothing is guessed (the person
    chose), the engagement lock is held, and the index is written
    lock-resiliently.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    index_path = engagement_dir / INDEX_FILENAME
    prepared_dir = engagement_dir / PREPARED_DIR_NAME

    # Everything - the manifest, the index, the keyword written back - under
    # the one lock, so a scheduled pass cannot slip in between.
    with engagement_lock(engagement_dir):
        items = {i.identifier: i for i in load_manifest(engagement_dir / MANIFEST_FILENAME)}
        item = items.get(identifier)
        if item is None:
            raise FilingError(f"no request {identifier!r} in the manifest")
        if item.manual_override == Override.WAIVED:
            raise FilingError(f"{identifier} is waived; clear the override first")

        entries = read_index(index_path)
        before = {ledger_key(e): _ledger_row(e) for e in entries}
        position = _find_parked(entries, original)
        entry = entries[position]
        source = engagement_dir / entry.pbc_location
        if not source.is_file():
            raise FilingError(
                f"the original {entry.pbc_location} is no longer in {PBC_DIR_NAME}"
            )
        if is_cloud_placeholder(source):
            raise FilingError(f"the original {entry.pbc_location} is still syncing; try again when it is here")
        digest, size_kb = entry.digest, entry.size_kb
        parked = engagement_dir / entry.prepared_location if entry.prepared_location else None
        # The parked copy is only ever read when it is here, hydrated
        # (hashing a dehydrated one would make the sync client download
        # it), and still this row's - a later row at the same path means
        # this row's copy is gone and what sits there is the later row's.
        parked_here = (
            parked is not None and parked.is_file() and not is_cloud_placeholder(parked)
            and not _copy_taken_by_a_later_row(entries, position)
        )
        if not digest:
            # The pass that preserved this original could not read it back
            # (decision 65) and recorded no digest. A row a person files
            # must carry one: the scanner honours the person's filing only
            # while the copy holds the bytes the row recorded, and a row
            # with none is honoured never. The bytes are the parked copy's
            # - what the pass handled - and the original must still hold
            # them; the original alone is trusted only when no copy is
            # left to check it against.
            evidence = parked if parked_here else source
            try:
                digest = sha256_of(evidence)
                size_kb = round(evidence.stat().st_size / 1024, 1)
                replaced = evidence is not source and sha256_of(source) != digest
            except OSError as exc:
                raise FilingError(
                    f"the original {entry.pbc_location} could not be read ({exc}); try again when it can"
                ) from exc
            if replaced:
                raise FilingError(
                    f"the original {entry.pbc_location} and its parked copy no longer hold the same "
                    "bytes, and the row recorded none - one of them changed after it arrived; "
                    "look at both files first"
                )
        elif sha256_of(source) != entry.digest:
            # The client replaced the original after it was parked (the pass
            # reports it as REPLACED_IN_PBC). Filing the new bytes under the
            # old row's record would be a lie in the audit trail; a person
            # decides which document this is now.
            raise FilingError(
                f"the original {entry.pbc_location} no longer holds the bytes this row "
                "recorded - it was replaced after it arrived; look at the file first"
            )

        dest_folder = request_folder(item, assign_folders(prepared_dir, list(items)), prepared_dir)
        dest_folder.mkdir(parents=True, exist_ok=True)
        taken = {p.name.lower() for p in dest_folder.iterdir()}
        filed_as = prepared_name_for(item, extension_of(source), taken)
        target = dest_folder / filed_as

        moved = reused = parked_stood_in = False
        left_in_review = ""
        # A copy with these bytes already in the folder is a killed earlier
        # attempt's, and is reused rather than doubled. Otherwise the parked
        # copy is moved, but only while it holds the row's bytes: its name
        # is the client's, and a freed name is taken by the next drop called
        # the same, so a person filing row A would carry document B into the
        # request folder under A's canonical name (the eleventh reading); a
        # copy a reviewer's app re-saved is not the row's bytes either and
        # is left where it is, said so, for the person to keep or discard.
        existing = _existing_copy(dest_folder, source, digest)
        if existing is not None:
            filed_as, target = existing.name, existing
            reused = True
            if parked_here and sha256_of(parked) == digest:
                parked.unlink()           # the attempt's copy stands in for it, byte for byte
                parked_stood_in = True
        elif parked_here and sha256_of(parked) == digest:
            _move_whole(parked, target)   # keeps any notes a person made on it
            moved = True
        else:
            if parked_here:
                left_in_review = (
                    f"the parked copy {entry.prepared_location} no longer holds the bytes this row "
                    f"recorded (annotated, or re-saved) and was left there; {filed_as} was copied from the original"
                )
            _copy_whole(source, target)

        new_entry = replace(
            entry,
            digest=digest,
            size_kb=size_kb,
            identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            decision=FILED,
            reason=f"{ASSIGNED_BY_PERSON} on {today.isoformat()}; was: {entry.reason}",
            candidates="",
        )
        entries[position] = new_entry
        landed = True
        try:
            deferred = not write_index(index_path, entries)
        except BaseException:
            # Excel holding the index is handled inside write_index (the
            # snapshot). Anything else - disk full, an interrupt - leaves
            # the copy where the index says it is, so a retry files it once
            # rather than copying it twice: back in Review if the index was
            # not written, where it is if the write landed and only the
            # sidecar's removal was interrupted. A killed attempt's copy
            # that stood in for the parked one leaves the row still naming
            # a parked copy that is no longer there, so it is put back -
            # from the copy that stood in for it, which is it byte for byte.
            landed = _index_records(index_path, new_entry)
            if not landed:
                try:
                    if moved:
                        _move_whole(target, parked)
                    elif parked_stood_in:
                        _copy_whole(target, parked)
                    elif not reused:          # a copy that was already there stays
                        target.unlink(missing_ok=True)
                except OSError as undo:       # the copy stays where it is; the real error is the one to hear
                    log.error("Could not put %s back after the index write failed: %s", target.name, undo)
            raise
        finally:
            # The record follows the index wherever the index went: an
            # interrupt between the workbook landing and this line would
            # otherwise leave the one decision a person made unrecorded.
            if landed:
                _record_write(engagement_dir, index_path, before, entries,
                              decided={ledger_key(new_entry): ledger.ASSIGNED_BY_PERSON})

        keyword = keyword.strip()
        note = ""
        if keyword:
            try:
                if not add_any_keyword(engagement_dir / MANIFEST_FILENAME, identifier, keyword):
                    note = f"{identifier} already had the keyword {keyword!r}"
            except PermissionError:
                note = (
                    f"keyword {keyword!r} not saved: the manifest is open in Excel; "
                    f"add it to {identifier}'s Any Keywords by hand or close Excel and try again"
                )
            except ManifestError as exc:       # the cell holds a formula: the filing stands, the keyword does not
                note = f"keyword {keyword!r} not saved: {exc}"
    return AssignResult(
        entry=new_entry, moved_review_copy=moved, keyword=keyword if not note else "",
        keyword_note=note, index_deferred=deferred, left_in_review=left_in_review,
    )


def _index_records(index_path: Path, entry: IndexEntry) -> bool:
    """True when the index on disk already carries ``entry`` as written."""
    try:
        rows = read_index(index_path, quarantine=False)
    except Exception:
        return False
    return entry in rows          # the whole row: an older row for the same location is not it


def _find_parked(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest parked row wins a name.

    A row a person has already said is ``NOT_REQUESTED`` is parked too: its
    working copy is still in ``REVIEW_DIR_NAME``, nothing was moved, and
    filing it is how that decision is undone. Only the two parked decisions
    are a person's to act on; anything else names itself in the refusal.
    """
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision in _PARKED:
                return position
            if entry.decision == DUPLICATE and entry.original_name == wanted:
                continue          # a re-send under the same name; the parked row is older
            raise FilingError(
                f"{entry.original_name} is not waiting for review (it is {entry.decision}"
                + (f" as {entry.prepared_location}" if entry.prepared_location else "")
                + ")"
            )
    raise FilingError(f"nothing in the index is called {original!r}")


# ---------------------------------------------------------- not requested ----


def _said(note: str) -> str:
    """A person's note, in the one shape a rewritten Reason carries it."""
    note = note.strip()
    return f" ({note})" if note else ""


@dataclass(frozen=True, slots=True)
class DismissResult:
    """What saying one parked document is not requested did."""

    entry: IndexEntry            # the rewritten index row
    index_deferred: bool = False


def dismiss_review_file(
    engagement_dir: Path | str,
    original: str,
    note: str = "",
    *,
    today: dt.date | None = None,
) -> DismissResult:
    """Record that no request asks for one parked document.

    ``original`` names the index row the way :func:`assign_review_file` takes
    it: its PBC location, or failing that its original name among the rows
    still parked. The row is rewritten as ``NOT_REQUESTED`` with the decision
    attributed to a person and what the row said before kept after it.

    Nothing moves. The working copy stays in ``REVIEW_DIR_NAME`` and the
    original in ``PBC_DIR_NAME/`` is untouched, because a document the client
    sent is never deleted over a decision about a *request*: an agency notice
    or an extra statement is still theirs, and a person who was wrong files it
    afterwards with :func:`assign_review_file`. What changes is what the
    system says about it - the weekly draft stops warning about a file
    somebody has already looked at, and the same bytes sent again are a
    duplicate rather than a second thing to look at.

    Because nothing moves, nothing is checked against the bytes: this is a
    statement about the request list, not about the file. The engagement lock
    is held and the index written lock-resiliently, as everywhere else.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    index_path = engagement_dir / INDEX_FILENAME

    with engagement_lock(engagement_dir):
        entries = read_index(index_path)
        before = {ledger_key(e): _ledger_row(e) for e in entries}
        position = _find_parked(entries, original)
        entry = entries[position]
        new_entry = replace(
            entry,
            decision=NOT_REQUESTED,
            reason=f"{DISMISSED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}",
        )
        entries[position] = new_entry
        # Nothing was moved, so there is nothing to put back: a write that
        # fails for a reason Excel is not leaves the folder as it was and
        # the row as the index on disk still has it.
        landed = True
        try:
            deferred = not write_index(index_path, entries)
        except BaseException:
            landed = _index_records(index_path, new_entry)
            raise
        finally:
            if landed:
                _record_write(engagement_dir, index_path, before, entries,
                              decided={ledger_key(new_entry): ledger.DISMISSED_BY_PERSON})
    return DismissResult(entry=new_entry, index_deferred=deferred)


# ----------------------------------------------------------------- unfile ----


#: What an unfiling says about a working copy whose bytes are not the ones
#: the row recorded. A reviewer's notes are work, and which of the two files
#: the firm wants is not the filer's to decide: the copy stays in the
#: request folder, a fresh one goes back to review, and a person is told so
#: they can keep or discard it - and knows the row is still counted until
#: they do.
LEFT_FILED = (
    "the working copy {location} no longer holds the bytes this row recorded (annotated, "
    "or re-saved) and was left there; {parked} went back to review from the original"
)
#: What an unfiling says when the re-scan could not write the manifest. The
#: row is rewritten and the file is back in review either way; it is the
#: request's status that waits.
RESCAN_DEFERRED = "the manifest is open in Excel; the status went to the sidecar and lands on the next pass"
RESCAN_REFUSED = "the status was not put back now ({why}); the next pass does it"


@dataclass(frozen=True, slots=True)
class UnfileResult:
    """What taking one filed document back for review did."""

    entry: IndexEntry            # the rewritten index row
    moved_working_copy: bool     # True: the working copy itself went back to REVIEW_DIR_NAME
    left_filed: str = ""         # a working copy that was not the row's bytes, and stayed
    index_deferred: bool = False
    scan_note: str = ""          # why the re-scan did not land, when it did not


def unfile_document(
    engagement_dir: Path | str,
    original: str,
    note: str = "",
    *,
    today: dt.date | None = None,
) -> UnfileResult:
    """Take one filed document back to ``REVIEW_DIR_NAME``, on the record.

    ``original`` names the index row the way :func:`assign_review_file` takes
    it: its PBC location, or failing that its original name among the rows
    the index says are ``FILED`` - whether a pass filed it or a person did.

    The working copy goes back under the client's own name, the name a parked
    copy has always had, and the row is rewritten ``NEEDS_REVIEW`` with no
    identifier, the reason attributed to a person and what the row said
    before kept after it. Then the engagement is re-scanned, so the request
    the document was answering goes back to what it is without it, with the
    regression note that pass would have written; nothing else waits for the
    scheduled run to notice.

    This is the correction that had no home. A document the router filed
    under the wrong request, or a person filed in a hurry, was put right by
    dragging it in Explorer - which the index never learns, so it went on
    saying Filed at a path that holds nothing and the scan went on counting a
    file that had moved. The keyword a person taught the request when they
    filed it is *not* unlearned: it is a rule about documents, the request
    still wants it, and guessing which keyword to take back would be
    guessing. Refiling is unfiling and then filing.

    The engagement lock is held for the move and the row, as everywhere else;
    the re-scan takes it again on its own, exactly as the app's filing does.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    index_path = engagement_dir / INDEX_FILENAME
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME

    with engagement_lock(engagement_dir):
        entries = read_index(index_path)
        before = {ledger_key(e): _ledger_row(e) for e in entries}
        position = _find_filed(entries, original)
        entry = entries[position]
        source = engagement_dir / entry.pbc_location
        working = engagement_dir / entry.prepared_location if entry.prepared_location else None
        # The working copy is only this row's while it is here, hydrated, not
        # claimed by a later row, and still the bytes the row recorded. Any
        # other file at that path is somebody else's document and is not
        # carried back to review under this row's name.
        here = (
            working is not None and working.is_file() and not is_cloud_placeholder(working)
            and not _copy_taken_by_a_later_row(entries, position)
        )
        still_the_rows = here and bool(entry.digest) and sha256_of(working) == entry.digest
        if not still_the_rows:
            # Nothing else can be parked but a copy of the original, so the
            # original has to be here before anything is moved or written.
            if not source.is_file():
                raise FilingError(
                    f"the working copy is not the one this row recorded and the original "
                    f"{entry.pbc_location} is no longer in {PBC_DIR_NAME}; there is nothing to put back"
                )
            if is_cloud_placeholder(source):
                raise FilingError(f"the original {entry.pbc_location} is still syncing; try again when it is here")

        review_dir.mkdir(parents=True, exist_ok=True)
        parked = _unique_path(review_dir, entry.original_name)
        left_filed = ""
        if still_the_rows:
            _move_whole(working, parked)      # keeps any notes a person made on it
        else:
            if here:
                left_filed = LEFT_FILED.format(location=entry.prepared_location, parked=parked.name)
            _copy_whole(source, parked)

        new_entry = replace(
            entry,
            identifier="",
            prepared_location=prepared_location(review_dir, parked.name),
            decision=NEEDS_REVIEW,
            reason=f"{UNFILED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}",
        )
        entries[position] = new_entry
        landed = True
        try:
            deferred = not write_index(index_path, entries)
        except BaseException:
            # The same rule as filing: leave the file where the index on disk
            # says it is, so a retry does this once rather than twice.
            landed = _index_records(index_path, new_entry)
            if not landed:
                try:
                    if still_the_rows:
                        _move_whole(parked, working)
                    else:
                        parked.unlink(missing_ok=True)
                except OSError as undo:
                    log.error("Could not put %s back after the index write failed: %s", parked.name, undo)
            raise
        finally:
            if landed:
                _record_write(engagement_dir, index_path, before, entries,
                              decided={ledger_key(new_entry): ledger.UNFILED_BY_PERSON})

    # Outside the lock: the scan takes it for itself. A pass that slips in
    # between reads the index this one has already written, so it sees the
    # document in review, as this scan will.
    return UnfileResult(
        entry=new_entry, moved_working_copy=still_the_rows, left_filed=left_filed,
        index_deferred=deferred, scan_note=_rescan(engagement_dir, today),
    )


def _rescan(engagement_dir: Path, today: dt.date) -> str:
    """Put the request's status back now, and say so if it could not be."""
    # The scan reads the index this module writes and this module asks for
    # the scan: the cycle is deliberate and is imported where it is used, so
    # neither module has to exist before the other at import time.
    from tracker.scanner import ScanLockedError, scan_engagement

    try:
        if not scan_engagement(engagement_dir, today=today).written:
            return RESCAN_DEFERRED
    except ScanLockedError as exc:
        return RESCAN_REFUSED.format(why=exc)
    return ""


def _find_filed(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest ``FILED`` row wins a name.

    ``_find_parked``'s shape over the other decision: what a person may
    unfile is what the index says is filed, whoever filed it. A row that is
    anything else names what it is in the refusal, because the answer to
    "this is in the wrong place" is different for each of them.
    """
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision == FILED:
                return position
            if entry.decision == DUPLICATE and entry.original_name == wanted:
                continue          # a re-send under the same name; the filed row is older
            raise FilingError(f"{entry.original_name} is not filed (it is {entry.decision})")
    raise FilingError(f"nothing in the index is called {original!r}")


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=f"Sort the client's drop folder into {PBC_DIR_NAME}/ and {PREPARED_DIR_NAME}/"
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    parser.add_argument(
        "--dry-run", action="store_true", help="decide everything, move nothing"
    )
    ns = parser.parse_args()

    result = file_drops(ns.engagement_dir, dry_run=ns.dry_run)
    head = "Would sort" if ns.dry_run else "Sorted"
    print(f"{head} {result.handled} file(s) from {result.engagement_dir}\n")
    for e in result.filed:
        print(f"  FILED   {e.original_name}")
        print(f"          -> {e.prepared_location}")
    for e in result.duplicates:
        print(f"  DUP     {e.original_name}  ({e.reason})")
    for e in result.review:
        print(f"  REVIEW  {e.original_name}  ({e.reason})")
    for p in result.waiting:
        print(f"  WAIT    {p.name}  (still syncing; left in place)")
    for err in result.errors:
        print(f"  ERROR   {err.name}  ({err.error})")
    if not ns.dry_run and result.handled:
        if result.index_deferred:
            print(f"\n  {INDEX_FILENAME} is LOCKED (open in Excel?) - new rows saved to "
                  f"{INDEX_PENDING_FILENAME} and merged on the next run")
        else:
            print(f"\n  Index updated: {INDEX_FILENAME}")
    if result.errors:
        raise SystemExit(1)
