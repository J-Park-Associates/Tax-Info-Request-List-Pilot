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
  decision; anything ambiguous lands in ``00 - Needs Review`` for a person.
- **Re-running is safe.** Every original is recorded by content hash, so a
  file the client drops twice is preserved but filed once.
- **Cloud-only files are left alone** until the sync client has them, so a
  placeholder is never moved as if it were the document.
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
from dataclasses import asdict, dataclass, field
from pathlib import Path

from openpyxl import Workbook, load_workbook

from tracker.manifest import RequestItem, load_manifest, save_workbook_atomically
from tracker.router import route_file
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PBC_DIR_NAME,
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
    SHARED_DIR_NAME,
    folder_name_for,
    sanitize_component,
)
from tracker.validators import is_cloud_placeholder, is_ignored, sha256_of

log = logging.getLogger("tracker.filer")

INDEX_FILENAME = "_index.xlsx"
INDEX_SHEET = "Index"
#: Rows that could not be written because Excel had the index open.
INDEX_PENDING_FILENAME = "_index.pending.json"
INDEX_RETRIES = 5
INDEX_RETRY_DELAY = 0.5
_MAX_STEM = 110

INDEX_COLUMNS = (
    "Received",
    "Original Name",
    "Size KB",
    "SHA-256",
    "Identifier",
    "Document",
    "Filed As",
    "Prepared Location",
    "PBC Location",
    "Decision",
    "Reason",
)

#: Decision values written to the index.
FILED = "Filed"
NEEDS_REVIEW = "Needs Review"
DUPLICATE = "Duplicate"


@dataclass(frozen=True, slots=True)
class IndexEntry:
    """One row of ``_index.xlsx`` — the audit trail for one original file."""

    received: str
    original_name: str
    size_kb: float
    digest: str
    identifier: str
    document: str
    filed_as: str
    prepared_location: str
    pbc_location: str
    decision: str
    reason: str

    def as_row(self) -> list[object]:
        return [
            self.received, self.original_name, self.size_kb, self.digest,
            self.identifier, self.document, self.filed_as,
            self.prepared_location, self.pbc_location, self.decision, self.reason,
        ]


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
    stem = " - ".join(p for p in parts if p)[:_MAX_STEM].rstrip(". ")
    suffix = f".{extension}" if extension else ""

    candidate = f"{stem}{suffix}"
    counter = 2
    while candidate.lower() in taken:
        candidate = f"{stem} ({counter}){suffix}"
        counter += 1
    taken.add(candidate.lower())
    return candidate


def _unique_path(folder: Path, name: str) -> Path:
    """A free path in ``folder`` for ``name``, never overwriting anything."""
    target = folder / name
    if not target.exists():
        return target
    stem, suffix = Path(name).stem, Path(name).suffix
    counter = 2
    while True:
        target = folder / f"{stem} ({counter}){suffix}"
        if not target.exists():
            return target
        counter += 1


# ------------------------------------------------------------------ index ----


def _pending_index_path(path: Path) -> Path:
    return path.with_name(INDEX_PENDING_FILENAME)


def _read_pending_index(path: Path) -> list[IndexEntry]:
    sidecar = _pending_index_path(path)
    if not sidecar.exists():
        return []
    try:
        raw = json.loads(sidecar.read_text(encoding="utf-8"))
        return [IndexEntry(**row) for row in raw]
    except (json.JSONDecodeError, TypeError, ValueError, OSError) as exc:
        # Keep the evidence; an unreadable sidecar must not be retried forever.
        corrupt = sidecar.with_suffix(".corrupt.json")
        sidecar.replace(corrupt)
        log.error("Unreadable index sidecar moved to %s: %s", corrupt.name, exc)
        return []


def _save_pending_index(path: Path, entries: list[IndexEntry]) -> None:
    _pending_index_path(path).write_text(
        json.dumps([asdict(e) for e in entries], indent=2), encoding="utf-8"
    )


def read_index(path: Path) -> list[IndexEntry]:
    """Every index row, oldest first: the workbook plus any rows a locked
    Excel forced into the pending sidecar. Empty if there is no index yet."""
    return _read_index_workbook(path) + _read_pending_index(path)


def _read_index_workbook(path: Path) -> list[IndexEntry]:
    if not path.exists():
        return []
    wb = load_workbook(path, data_only=True)
    try:
        ws = wb[INDEX_SHEET] if INDEX_SHEET in wb.sheetnames else wb.active
        rows = list(ws.iter_rows(min_row=2, values_only=True))
    finally:
        wb.close()
    entries = []
    for row in rows:
        if not row or row[0] is None:
            continue
        padded = list(row) + [None] * (len(INDEX_COLUMNS) - len(row))
        entries.append(
            IndexEntry(
                received=str(padded[0] or ""),
                original_name=str(padded[1] or ""),
                size_kb=float(padded[2] or 0),
                digest=str(padded[3] or ""),
                identifier=str(padded[4] or ""),
                document=str(padded[5] or ""),
                filed_as=str(padded[6] or ""),
                prepared_location=str(padded[7] or ""),
                pbc_location=str(padded[8] or ""),
                decision=str(padded[9] or ""),
                reason=str(padded[10] or ""),
            )
        )
    return entries


def _save_index(path: Path, entries: list[IndexEntry]) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = INDEX_SHEET
    ws.append(list(INDEX_COLUMNS))
    for entry in entries:
        ws.append(entry.as_row())

    widths = (12, 40, 9, 18, 10, 34, 40, 34, 26, 14, 60)
    for column, width in zip(ws.column_dimensions, widths):
        ws.column_dimensions[column].width = width
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
    retries = INDEX_RETRIES if retries is None else retries
    delay = INDEX_RETRY_DELAY if retry_delay is None else retry_delay
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
    if not drops:
        # Nothing new, but rows a locked Excel deferred last time still
        # belong in the workbook - fold them in as soon as it is free.
        if not dry_run and _pending_index_path(index_path).exists():
            report.index_deferred = not write_index(index_path, entries)
        return report

    if not dry_run:
        pbc_dir.mkdir(parents=True, exist_ok=True)
        prepared_dir.mkdir(parents=True, exist_ok=True)

    stamp = today.isoformat()
    # Names claimed during this run, so a dry run previews the same numbering
    # a real run would produce (nothing is on disk to collide with yet).
    reserved: dict[Path, set[str]] = {}
    recorded = len(entries)
    try:
        for drop in drops:
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
            if dry_run:
                pbc_target = pbc_dir / drop.name
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
                    dry_run, report,
                )
            except Exception as exc:  # the original is safe; say so and go on
                log.exception("Could not file %s", drop.name)
                entry = IndexEntry(
                    received=stamp, original_name=drop.name, size_kb=size_kb,
                    digest=digest, identifier="", document="", filed_as="",
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
    dry_run: bool,
    report: FileReport,
) -> IndexEntry:
    """Decide one preserved original's fate and, unless dry-running, copy it."""
    if digest in known:
        earlier = known[digest]
        entry = IndexEntry(
            received=stamp, original_name=drop.name, size_kb=size_kb,
            digest=digest, identifier=earlier.identifier,
            document=earlier.document, filed_as="", prepared_location="",
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
        dest_folder = prepared_dir / folder_name_for(item)
        if dest_folder not in reserved:
            reserved[dest_folder] = (
                {p.name.lower() for p in dest_folder.iterdir()}
                if dest_folder.is_dir()
                else set()
            )
        filed_as = prepared_name_for(
            item, drop.suffix.lower().lstrip("."), reserved[dest_folder]
        )
        if not dry_run:
            dest_folder.mkdir(parents=True, exist_ok=True)
            shutil.copy2(pbc_target, dest_folder / filed_as)
        entry = IndexEntry(
            received=stamp, original_name=drop.name, size_kb=size_kb,
            digest=digest, identifier=item.identifier, document=item.document,
            filed_as=filed_as,
            prepared_location=f"{PREPARED_DIR_NAME}/{dest_folder.name}/{filed_as}",
            pbc_location=pbc_rel, decision=FILED, reason=routing.reason,
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
        digest=digest, identifier="", document="", filed_as=review_name,
        prepared_location=f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/{review_name}",
        pbc_location=pbc_rel, decision=NEEDS_REVIEW, reason=routing.reason,
    )
    report.review.append(entry)
    return entry


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Sort the client's drop folder into PBC/ and Prepared/"
    )
    parser.add_argument("engagement_dir", help="folder containing _manifest.xlsx")
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
