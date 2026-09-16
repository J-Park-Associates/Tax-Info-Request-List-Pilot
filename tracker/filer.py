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
"""

from __future__ import annotations

import datetime as dt
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from openpyxl import Workbook, load_workbook

from tracker.manifest import RequestItem, load_manifest
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


@dataclass(slots=True)
class FileReport:
    """Everything one filing run did."""

    engagement_dir: Path
    filed: list[IndexEntry] = field(default_factory=list)
    review: list[IndexEntry] = field(default_factory=list)
    duplicates: list[IndexEntry] = field(default_factory=list)
    waiting: list[Path] = field(default_factory=list)   # cloud-only, left alone
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


def read_index(path: Path) -> list[IndexEntry]:
    """Existing index rows, or an empty list if there is no index yet."""
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


def write_index(path: Path, entries: list[IndexEntry]) -> Path:
    """Rewrite ``_index.xlsx`` from ``entries`` (oldest first)."""
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
    wb.save(path)
    return path


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
        return report

    if not dry_run:
        pbc_dir.mkdir(parents=True, exist_ok=True)
        prepared_dir.mkdir(parents=True, exist_ok=True)

    stamp = today.isoformat()
    # Names claimed during this run, so a dry run previews the same numbering
    # a real run would produce (nothing is on disk to collide with yet).
    reserved: dict[Path, set[str]] = {}
    for drop in drops:
        # A file the sync client has not downloaded is not a document yet.
        if is_cloud_placeholder(drop):
            report.waiting.append(drop)
            continue

        digest = sha256_of(drop)
        size_kb = round(drop.stat().st_size / 1024, 1)

        # Preserve the original first: it is the record, whatever happens next.
        if dry_run:
            pbc_target = pbc_dir / drop.name
        else:
            pbc_target = _unique_path(pbc_dir, drop.name)
            shutil.move(str(drop), pbc_target)
        pbc_rel = pbc_target.relative_to(engagement_dir).as_posix()

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
            entries.append(entry)
            continue

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
        else:
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

        entries.append(entry)
        known[digest] = entry

    if not dry_run:
        write_index(index_path, entries)
    return report


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
    if not ns.dry_run and result.handled:
        print(f"\n  Index updated: {INDEX_FILENAME}")
