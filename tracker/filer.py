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
it was renamed to, and — when it was not filed — why not.

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
import shutil
import time
from contextlib import nullcontext
from dataclasses import asdict, dataclass, field, fields, replace
from pathlib import Path

from openpyxl import Workbook, load_workbook
from openpyxl.utils import get_column_letter

from tracker.content_check import CACHE_FILENAME, ContentCache
from tracker.locking import engagement_lock
from tracker.manifest import (
    COL_IDENTIFIER,
    LOCK_RETRIES,
    LOCK_RETRY_DELAY,
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

#: Reason prefix on index rows a person filed from REVIEW_DIR_NAME.
ASSIGNED_BY_PERSON = "assigned by a person"

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

    @property
    def candidate_list(self) -> list[str]:
        """The router's candidates as the list they were joined from."""
        return [c for c in (part.strip() for part in self.candidates.split(_CANDIDATE_SEP)) if c]

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
}
assert tuple(INDEX_LAYOUT) == tuple(f.name for f in fields(IndexEntry))
INDEX_COLUMNS = tuple(header for header, _ in INDEX_LAYOUT.values())


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
    forgotten over a timestamp), and a person's filing decision
    (``ASSIGNED_BY_PERSON``) on a row the workbook still shows parked,
    which only Excel saving a stale workbook could have undone.

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
    decided = {
        e.pbc_location: e for e in pending.entries
        if e.pbc_location and e.decision == FILED and e.reason.startswith(ASSIGNED_BY_PERSON)
    }
    merged = [
        decided[e.pbc_location]
        if e.decision == NEEDS_REVIEW and e.pbc_location in decided else e
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


def _read_index_workbook(path: Path) -> list[IndexEntry]:
    if not path.exists():
        return []
    wb = load_workbook(path, data_only=True)
    try:
        ws = wb[INDEX_SHEET] if INDEX_SHEET in wb.sheetnames else wb.active
        rows = list(ws.iter_rows(values_only=True))
    finally:
        wb.close()
    if not rows:
        return []
    # By header name, so an index written with columns since dropped (Filed
    # As, Document) or before one was added (Candidates) still reads.
    headers = [str(h or "").strip() for h in rows[0]]
    by_field = {
        name: headers.index(header)
        for name, (header, _) in INDEX_LAYOUT.items()
        if header in headers
    }
    entries = []
    for row in rows[1:]:
        if not row or row[0] is None:
            continue
        values: dict[str, object] = {}
        for name, position in by_field.items():
            raw = row[position] if position < len(row) else None
            values[name] = _as_float(raw) if name == "size_kb" else str(raw or "")
        entries.append(IndexEntry(**values))
    return entries


def _save_index(path: Path, entries: list[IndexEntry]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = INDEX_SHEET
    ws.append(list(INDEX_COLUMNS))
    for entry in entries:
        ws.append(entry.as_row())
        for cell in ws[ws.max_row]:
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
        except PermissionError as exc:
            log.warning("Index locked (attempt %d/%d): %s", attempt, retries, exc)
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
        "%s still locked after %d attempts; a snapshot of all %d row(s) deferred to %s",
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
        if not path.is_file() or is_ignored(path):
            continue
        if path == shared_dir / README_NAME:
            continue
        if pbc in path.parents or path == pbc:
            continue
        drops.append(path)
    return drops


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
        # The row that holds each document's bytes. A Duplicate row only
        # points at another row; letting it shadow the Filed row would hide
        # a working copy that has since been deleted, and a re-send that
        # answers "Missing" would be called a duplicate for ever.
        known = {e.digest: e for e in entries if e.digest and e.decision != DUPLICATE}
        # Rows a locked Excel deferred last time still belong in the workbook -
        # fold them in as soon as it is free, whether or not this run sorts anything.
        sidecar_waiting = _pending_index_path(index_path).exists()

        drops = iter_drops(shared_dir)
        # A file still being written (a sync client's or a browser's
        # ``TEMP_SUFFIX`` name) is not sorted, and is not passed over in
        # silence either: it is reported as waiting, like a placeholder.
        report.waiting.extend(unfinished_drops(shared_dir))
        strays = unrecorded_in_pbc(pbc_dir, engagement_dir, entries) if pbc_dir.is_dir() else []
        # An original replaced under its own name is said loudly, every run,
        # until a person has looked; it is not sorted again and not guessed.
        for path, earlier in replaced_in_pbc(pbc_dir, engagement_dir, entries) if pbc_dir.is_dir() else []:
            report.errors.append(FileError(path.name, REPLACED_IN_PBC.format(
                location=earlier.pbc_location, received=earlier.received,
                prepared=earlier.prepared_location or "(none)",
            ), True))
        if not drops and not strays:
            if not dry_run and sidecar_waiting:
                report.index_deferred = not write_index(index_path, entries)
            return report

        stamp = today.isoformat()
        # Names claimed during this run, so a dry run previews the same numbering
        # a real run would produce (nothing is on disk to collide with yet).
        reserved: dict[Path, set[str]] = {}
        recorded = len(entries)
        if not dry_run:
            pbc_dir.mkdir(parents=True, exist_ok=True)
            prepared_dir.mkdir(parents=True, exist_ok=True)
        # Existing request folders, so a Document renamed in Excel keeps
        # filing into the folder that already holds its earlier files.
        assigned = assign_folders(prepared_dir, [i.identifier for i in items])
        # What the router learns about each document is what the scan will
        # want to know about its working copy (same bytes): the verdicts go
        # into the engagement's content cache, keyed by content. The PDF
        # readability cache is this run's alone.
        run = _SortContext(
            items=items, by_id=by_id, known=known, prepared_dir=prepared_dir,
            review_dir=review_dir, reserved=reserved, assigned=assigned,
            dry_run=dry_run, report=report,
            cache=ContentCache(engagement_dir / CACHE_FILENAME), pdf_cache=PdfVerdictCache(),
        )
        try:
            for drop, already_in_pbc in (
                [(d, False) for d in drops] + [(p, True) for p in strays]
            ):
                # A file the sync client has not downloaded is not a document yet.
                if is_cloud_placeholder(drop):
                    report.waiting.append(drop)
                    continue

                try:
                    digest = sha256_of(drop)
                    size_kb = round(drop.stat().st_size / 1024, 1)
                except OSError as exc:
                    # Still being written, or withdrawn between listing and now.
                    # Nothing has moved, so leaving it is safe; next run retries.
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
                        shutil.move(str(drop), pbc_target)
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
                if entry.decision != DUPLICATE:
                    known[digest] = entry
        finally:
            # Whatever happened above, every original that was moved is on
            # record - and a snapshot waiting from last time is landed even
            # when every drop this time was left in place.
            if not dry_run and (len(entries) > recorded or sidecar_waiting):
                report.index_deferred = not write_index(index_path, entries)
        if not dry_run:
            run.cache.save()
            _prune_empty_dirs(shared_dir, keep=pbc_dir)
    return report


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
    if digest in known:
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
        position = _find_parked(entries, original)
        entry = entries[position]
        source = engagement_dir / entry.pbc_location
        if not source.is_file():
            raise FilingError(
                f"the original {entry.pbc_location} is no longer in {PBC_DIR_NAME}"
            )
        if is_cloud_placeholder(source):
            raise FilingError(f"the original {entry.pbc_location} is still syncing; try again when it is here")
        if entry.digest and sha256_of(source) != entry.digest:
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

        parked = engagement_dir / entry.prepared_location if entry.prepared_location else None
        moved = reused = False
        if parked is not None and parked.is_file():
            shutil.move(str(parked), target)   # keeps any notes a person made on it
            moved = True
        else:
            # The parked copy is gone: a run killed after an earlier attempt
            # moved it, or a person did. A copy with these bytes already in
            # the folder is that attempt's, and is reused rather than doubled.
            existing = _existing_copy(dest_folder, source, entry.digest) if entry.digest else None
            if existing is not None:
                filed_as, target = existing.name, existing
                reused = True
            else:
                _copy_whole(source, target)

        new_entry = replace(
            entry,
            identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            decision=FILED,
            reason=f"{ASSIGNED_BY_PERSON} on {today.isoformat()}; was: {entry.reason}",
            candidates="",
        )
        entries[position] = new_entry
        try:
            deferred = not write_index(index_path, entries)
        except BaseException:
            # Excel holding the index is handled inside write_index (the
            # snapshot). Anything else - disk full, an interrupt - leaves
            # the copy where the index says it is, so a retry files it once
            # rather than copying it twice: back in Review if the index was
            # not written, where it is if the write landed and only the
            # sidecar's removal was interrupted.
            if not _index_records(index_path, new_entry):
                if moved:
                    shutil.move(str(target), parked)
                elif not reused:          # a copy that was already there stays
                    target.unlink(missing_ok=True)
            raise

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
    return AssignResult(
        entry=new_entry, moved_review_copy=moved, keyword=keyword if not note else "",
        keyword_note=note, index_deferred=deferred,
    )


def _index_records(index_path: Path, entry: IndexEntry) -> bool:
    """True when the index on disk already carries ``entry`` as written."""
    try:
        rows = read_index(index_path, quarantine=False)
    except Exception:
        return False
    return entry in rows          # the whole row: an older row for the same location is not it


def _find_parked(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest Needs Review row wins a name."""
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision == NEEDS_REVIEW:
                return position
            if entry.decision == DUPLICATE and entry.original_name == wanted:
                continue          # a re-send under the same name; the parked row is older
            raise FilingError(
                f"{entry.original_name} is not waiting for review (it is {entry.decision}"
                + (f" as {entry.prepared_location}" if entry.prepared_location else "")
                + ")"
            )
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
