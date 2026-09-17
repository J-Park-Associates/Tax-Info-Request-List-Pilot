"""Sort the client's drop folder into a working set (component 7).

The client sees one folder and drops everything into it. This module turns
that pile into two things:

``Shared/PBC/``
    Every document the client provided, moved out of the drop zone but left
    completely untouched — same bytes, same filename. This is the
    provided-by-client record, and the client can still see it.

``Prepared/{Identifier} - {Document}/``
    A renamed copy of each identified document, on the firm's side of the
    engagement, named to one convention so a preparer can work the return
    without opening the client's filing habits.

``_index.xlsx`` maps one to the other: every original, where it went, what
it was renamed to, and — when it was not filed — why not.

Guarantees:

- **Originals are never altered.** Files are moved into ``PBC/`` and copied
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
  same originals and overwrite each other's index rows.
- **Wherever the client put it counts.** ``PBC/`` is visible to the client
  and the README says "drop it anywhere", so a file that lands straight in
  ``PBC/`` is treated as a drop that has already been preserved: it is
  filed and indexed in place, never ignored.
- **A working copy that went missing is replaced.** A re-sent document
  whose earlier copy is no longer in ``Prepared/`` is filed again rather
  than dismissed as a duplicate; the original was always safe in ``PBC/``.
- **One bad file never costs the audit trail.** Each drop is handled on its
  own: a file the sync client still holds open is left in place for the
  next run, a file that fails *after* it was preserved is recorded as
  needing review with the error, and the index is written whatever happens
  to the files after it. If Excel has ``_index.xlsx`` open, the new rows
  wait in ``_index.pending.json`` and are merged into the next write —
  nothing that was moved into ``PBC/`` is ever left unrecorded.
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

from tracker.locking import engagement_lock
from tracker.manifest import (
    COL_IDENTIFIER,
    LOCK_RETRIES,
    LOCK_RETRY_DELAY,
    Override,
    RequestItem,
    add_any_keyword,
    label_for,
    load_manifest,
    pending_path,
    quarantine_sidecar,
    save_workbook_atomically,
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
_MAX_STEM = 110


def numbered(stem: str, counter: int, suffix: str) -> str:
    """``name (2).pdf`` - the one shape a colliding name takes."""
    return f"{stem} ({counter}){suffix}"

#: Decision values written to the index.
FILED = "Filed"
NEEDS_REVIEW = "Needs Review"
DUPLICATE = "Duplicate"

#: Reason prefix on index rows a person filed from 00 - Needs Review.
ASSIGNED_BY_PERSON = "assigned by a person"

#: How candidate identifiers are joined in the Candidates cell.
_CANDIDATE_SEP = ", "


class FilingError(Exception):
    """A person's filing decision could not be carried out as asked."""


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One row of ``_index.xlsx`` — the audit trail for one original file.

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
    left_in_place: bool   # True: untouched in Shared/, retried next run


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
    """Canonical working-copy name: ``{Identifier} - {Document} - {Period}.ext``.

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
    """Where a working copy is, relative to the engagement: ``Prepared/<folder>/<name>``."""
    return f"{PREPARED_DIR_NAME}/{folder.name}/{name}"


def request_folder(item: RequestItem, assigned: dict[str, list[Path]], prepared_dir: Path) -> Path:
    """The folder a request's working copies go in: the one it already has
    (by identifier prefix, so a Document renamed in Excel changes nothing),
    else the canonical name."""
    existing = assigned.get(item.identifier) or []
    return existing[0] if existing else prepared_dir / folder_name_for(item)


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


def _read_pending_index(path: Path) -> list[IndexEntry]:
    sidecar = _pending_index_path(path)
    if not sidecar.exists():
        return []
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        return [IndexEntry(**row) for row in raw]
    except (json.JSONDecodeError, TypeError, ValueError, OSError) as exc:
        quarantine_sidecar(sidecar, exc, "index")
        return []


def _save_pending_index(path: Path, entries: list[IndexEntry]) -> None:
    _pending_index_path(path).write_text(
        json.dumps([asdict(e) for e in entries], indent=2), encoding="utf-8"
    )


def read_index(path: Path) -> list[IndexEntry]:
    """Every index row, oldest first: the workbook plus any rows a locked
    Excel forced into the pending sidecar. Empty if there is no index yet."""
    return _read_index_workbook(path) + _read_pending_index(path)


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
    """Rewrite ``_index.xlsx`` from ``entries`` (oldest first), lock-resiliently.

    The index is the audit trail for originals that have *already been
    moved*, so losing a row is not an option. If Excel holds the workbook
    open, the write is retried with backoff; if it stays locked, every row
    not yet in the workbook is saved to ``_index.pending.json`` and folded
    into the next successful write (``read_index`` already sees them).

    Returns True if the workbook was written, False if rows were deferred.
    """
    retries = LOCK_RETRIES if retries is None else retries
    delay = LOCK_RETRY_DELAY if retry_delay is None else retry_delay
    for attempt in range(1, retries + 1):
        try:
            _save_index(path, entries)
            _pending_index_path(path).unlink(missing_ok=True)
            return True
        except PermissionError as exc:
            log.warning("Index locked (attempt %d/%d): %s", attempt, retries, exc)
            if attempt < retries:
                time.sleep(delay)
                delay *= 2

    already = len(_read_index_workbook(path))
    _save_pending_index(path, entries[already:])
    log.error(
        "%s still locked after %d attempts; %d row(s) deferred to %s",
        path.name, retries, len(entries) - already, INDEX_PENDING_FILENAME,
    )
    return False


# ------------------------------------------------------------------- walk ----


def iter_drops(shared_dir: Path) -> list[Path]:
    """Client-dropped files awaiting sorting.

    Everything under ``Shared/`` except the preserved ``PBC/`` originals,
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


def unrecorded_in_pbc(pbc_dir: Path, engagement_dir: Path, entries: list[IndexEntry]) -> list[Path]:
    """Files sitting in ``PBC/`` that no index row accounts for.

    The client can see ``PBC/`` and has been told to drop things anywhere,
    so some will land here. They are already where an original belongs;
    they just have not been filed or recorded yet.
    """
    recorded = {e.pbc_location for e in entries if e.pbc_location}
    return [
        path for path in iter_candidate_files(pbc_dir)
        if path.relative_to(engagement_dir).as_posix() not in recorded
    ]


def _prune_empty_dirs(shared_dir: Path, keep: Path) -> None:
    """Remove folders the client dragged in that are empty now their files
    have moved to PBC/. Deepest first; anything that is not empty, is the
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
    items = load_manifest(engagement_dir / MANIFEST_FILENAME)
    by_id = {i.identifier: i for i in items}

    shared_dir = engagement_dir / SHARED_DIR_NAME
    pbc_dir = shared_dir / PBC_DIR_NAME
    prepared_dir = engagement_dir / PREPARED_DIR_NAME
    review_dir = prepared_dir / REVIEW_DIR_NAME
    index_path = engagement_dir / INDEX_FILENAME

    report = FileReport(engagement_dir=engagement_dir, dry_run=dry_run)
    entries = read_index(index_path)
    known = {e.digest: e for e in entries if e.digest}

    drops = iter_drops(shared_dir)
    strays = unrecorded_in_pbc(pbc_dir, engagement_dir, entries) if pbc_dir.is_dir() else []
    if not drops and not strays:
        # Nothing new, but rows a locked Excel deferred last time still
        # belong in the workbook - fold them in as soon as it is free.
        if not dry_run and _pending_index_path(index_path).exists():
            report.index_deferred = not write_index(index_path, entries)
        return report

    stamp = today.isoformat()
    # Names claimed during this run, so a dry run previews the same numbering
    # a real run would produce (nothing is on disk to collide with yet).
    reserved: dict[Path, set[str]] = {}
    recorded = len(entries)
    # A sort and a scan must never overlap (see tracker.locking). A dry run
    # writes nothing, so it needs no lock and never blocks a real run.
    with engagement_lock(engagement_dir) if not dry_run else nullcontext():
        if not dry_run:
            pbc_dir.mkdir(parents=True, exist_ok=True)
            prepared_dir.mkdir(parents=True, exist_ok=True)
        # Existing request folders, so a Document renamed in Excel keeps
        # filing into the folder that already holds its earlier files.
        assigned = assign_folders(prepared_dir, [i.identifier for i in items])
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
                    entry = _sort_one(
                        drop, pbc_target, pbc_rel, digest, size_kb, stamp,
                        items, by_id, known, prepared_dir, review_dir, reserved,
                        assigned, dry_run, report,
                    )
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
            # Whatever happened above, every original that was moved is on record.
            if not dry_run and len(entries) > recorded:
                report.index_deferred = not write_index(index_path, entries)
        if not dry_run:
            _prune_empty_dirs(shared_dir, keep=pbc_dir)
    return report


def _sort_one(
    drop: Path,
    pbc_target: Path,
    pbc_rel: str,
    digest: str,
    size_kb: float,
    stamp: str,
    items: list[RequestItem],
    by_id: dict[str, RequestItem],
    known: dict[str, IndexEntry],
    prepared_dir: Path,
    review_dir: Path,
    reserved: dict[Path, set[str]],
    assigned: dict[str, list[Path]],
    dry_run: bool,
    report: FileReport,
) -> IndexEntry:
    """Decide one preserved original's fate and, unless dry-running, copy it."""
    refiled = ""
    if digest in known:
        earlier = known[digest]
        engagement_dir = prepared_dir.parent
        if (
            earlier.decision == FILED
            and earlier.prepared_location
            and not (engagement_dir / earlier.prepared_location).exists()
        ):
            # The same document again, and its working copy is gone from
            # Prepared/ - deleted by hand, most likely. A re-send is the
            # client answering "Missing"; calling it a duplicate would keep
            # the row Missing for ever. File it again.
            refiled = (
                f"re-filed: the earlier copy {earlier.prepared_location} "
                "was no longer in Prepared"
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

    routing = route_file(pbc_target if not dry_run else drop, items)
    item = by_id.get(routing.identifier or "")

    if routing.routed and item is not None:
        dest_folder = request_folder(item, assigned, prepared_dir)
        if dest_folder not in reserved:
            reserved[dest_folder] = (
                {p.name.lower() for p in dest_folder.iterdir()}
                if dest_folder.is_dir()
                else set()
            )
        filed_as = prepared_name_for(item, extension_of(drop), reserved[dest_folder])
        if not dry_run:
            dest_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pbc_target, dest_folder / filed_as)
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
        review_dir.mkdir(parents=True, exist_ok=True)
        review_target = _unique_path(review_dir, drop.name)
        shutil.copy2(pbc_target, review_target)
        review_name = review_target.name
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier="",
        prepared_location=prepared_location(review_dir, review_name),
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
    moved_review_copy: bool      # True: the copy in 00 - Needs Review became the working copy
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
    (``Shared/PBC/scan0012.pdf``) or, failing that, its original name among
    the rows still marked Needs Review. The working copy is created under the
    canonical name in the request's folder - moved from ``00 - Needs
    Review`` when it is still there, copied from ``PBC/`` when it is not -
    and the index row is rewritten as Filed with the decision attributed to
    a person. The original in ``PBC/`` is not touched.

    ``keyword`` is optional: added to the request's Any Keywords so the next
    document like this one routes itself. If Excel holds the manifest the
    filing still happens and the note says the keyword was not saved.

    The rules the filer lives by still hold: nothing is guessed (the person
    chose), the engagement lock is held, and the index is written
    lock-resiliently.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    items = {i.identifier: i for i in load_manifest(engagement_dir / MANIFEST_FILENAME)}
    item = items.get(identifier)
    if item is None:
        raise FilingError(f"no request {identifier!r} in the manifest")
    if item.manual_override == Override.WAIVED:
        raise FilingError(f"{identifier} is waived; clear the override first")

    index_path = engagement_dir / INDEX_FILENAME
    prepared_dir = engagement_dir / PREPARED_DIR_NAME

    with engagement_lock(engagement_dir):
        entries = read_index(index_path)
        position = _find_parked(entries, original)
        entry = entries[position]
        source = engagement_dir / entry.pbc_location
        if not source.is_file():
            raise FilingError(
                f"the original {entry.pbc_location} is no longer in {PBC_DIR_NAME}"
            )

        dest_folder = request_folder(item, assign_folders(prepared_dir, list(items)), prepared_dir)
        dest_folder.mkdir(parents=True, exist_ok=True)
        taken = {p.name.lower() for p in dest_folder.iterdir()}
        filed_as = prepared_name_for(item, extension_of(source), taken)
        target = dest_folder / filed_as

        parked = engagement_dir / entry.prepared_location if entry.prepared_location else None
        moved = False
        if parked is not None and parked.is_file():
            shutil.move(str(parked), target)   # keeps any notes a person made on it
            moved = True
        else:
            shutil.copy2(source, target)

        new_entry = replace(
            entry,
            identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            decision=FILED,
            reason=f"{ASSIGNED_BY_PERSON} on {today.isoformat()}; was: {entry.reason}",
            candidates="",
        )
        entries[position] = new_entry
        deferred = not write_index(index_path, entries)

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


def _find_parked(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest Needs Review row wins a name."""
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision == NEEDS_REVIEW:
                return position
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
