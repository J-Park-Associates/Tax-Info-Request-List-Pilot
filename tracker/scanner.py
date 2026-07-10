"""Scan orchestrator for the Client Document Tracker (component 5).

Ties the layers together for one engagement: walk ``Shared/``, match folders
to manifest rows (prefix rule, longest identifier wins), run validation
tiers 1-3, resolve each row's status deterministically, and write results
back to ``_manifest.xlsx`` (lock-resiliently, via the manifest layer).

Status policy (docs/ROADMAP.md decision log):

- **Auto-revert** — status always reflects the current scan. A previously
  Received item whose files changed or vanished regresses, keeping its
  original Received Date plus a note.
- **Manual Override wins** — rows marked Accepted/Waived keep whatever
  Status they have; the scanner still refreshes File Count and records
  what the rules saw in the notes, prefixed ``[override: ...]``.
- **Pending Sync** — cloud-only placeholders are never read; if they are
  the reason a row is short of files, the row waits instead of failing.
- Duplicate uploads ("statement (1).pdf") are de-duplicated by content
  hash before counting — only when more than one valid file exists, so the
  common single-file case never pays for hashing.

Strictly read-only against client files. The only writes are to the
accountant-side manifest, content cache, and run-lock — all outside
``Shared/``. A per-engagement lock file prevents overlapping scheduled runs;
stale locks (>1 h) are replaced.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import time
from dataclasses import dataclass, field
from pathlib import Path

from tracker.content_check import ContentCache, check_content
from tracker.manifest import (
    RequestItem,
    Status,
    StatusUpdate,
    UnfiledEntry,
    load_manifest,
    write_statuses,
)
from tracker.scaffold import (
    MANIFEST_FILENAME,
    README_NAME,
    SHARED_DIR_NAME,
    assign_folders,
)
from tracker.validators import (
    check_folder,
    is_ignored,
    iter_candidate_files,
    sha256_of,
)

log = logging.getLogger("tracker.scanner")

CACHE_FILENAME = "_content_cache.json"
LOCK_FILENAME = "_scan.lock"
STALE_LOCK_SECONDS = 3600
_MAX_NOTE_LEN = 500
_MAX_LISTED_FAILURES = 3


class ScanLockedError(RuntimeError):
    """Another scan of this engagement appears to be running."""


@dataclass(slots=True)
class ScanReport:
    """Everything one scan found and did."""

    engagement_dir: Path
    updates: dict[str, StatusUpdate] = field(default_factory=dict)
    unfiled: list[UnfiledEntry] = field(default_factory=list)
    written: bool = False    # manifest updated on disk
    deferred: bool = False   # manifest was locked; updates went to sidecar
    dry_run: bool = False


# ------------------------------------------------------------- per-item ----


def _scan_item(
    item: RequestItem,
    folders: list[Path],
    cache: ContentCache,
    today: dt.date,
) -> StatusUpdate:
    """Run tiers 1-3 for one manifest row and resolve its status."""
    results = [fr for folder in folders for fr in check_folder(folder, item).files]
    pending = [f for f in results if f.pending_sync]
    tier2_failed = [f for f in results if not f.ok and not f.pending_sync]

    valid: list[Path] = []
    content_failed: list[tuple[Path, str]] = []
    for f in (f for f in results if f.ok):
        verdict = check_content(f.path, item, cache)
        if verdict.ok:
            valid.append(f.path)
        else:
            content_failed.append((f.path, verdict.reason))

    # De-duplicate by content hash — but never hash the common 0/1-file case.
    duplicates = 0
    if len(valid) > 1:
        seen: set[str] = set()
        distinct: list[Path] = []
        for path in valid:
            digest = sha256_of(path)
            if digest in seen:
                duplicates += 1
            else:
                seen.add(digest)
                distinct.append(path)
        valid = distinct
    count = len(valid)

    failures = [f"{f.path.name}: {f.reason}" for f in tier2_failed]
    failures += [f"{path.name}: {reason}" for path, reason in content_failed]

    facts: list[str] = []
    if duplicates:
        facts.append(f"{duplicates} duplicate file(s) ignored")
    if len(folders) > 1:
        facts.append(f"{len(folders)} folders match this identifier")
    facts.extend(failures[:_MAX_LISTED_FAILURES])
    if len(failures) > _MAX_LISTED_FAILURES:
        facts.append(f"(+{len(failures) - _MAX_LISTED_FAILURES} more issues)")

    # --- override rows: facts only, status untouched -----------------------
    if item.manual_override:
        facts.insert(0, f"[override: {item.manual_override}]")
        return StatusUpdate(
            status=item.status,
            file_count=count,
            received_date=item.received_date,
            validation_notes=_join(facts),
        )

    # --- deterministic status resolution -----------------------------------
    if not folders:
        status = Status.MISSING
        facts.insert(0, "request folder not found; re-run scaffold")
    elif count >= item.expected_count:
        status = Status.RECEIVED
        if pending:
            facts.append(f"{len(pending)} more file(s) still syncing")
    elif pending:
        status = Status.PENDING_SYNC
        facts.insert(0, f"{len(pending)} file(s) still syncing from OneDrive")
    elif count > 0:
        status = Status.PARTIAL
        facts.insert(0, f"{count} of {item.expected_count} expected files")
    elif failures:
        status = Status.FAILED
    else:
        status = Status.MISSING

    # --- Received Date: first-pass stamp, preserved through regressions ----
    if status == Status.RECEIVED:
        received = item.received_date or today
    else:
        received = item.received_date
        if item.received_date is not None:
            facts.insert(
                0, f"was Received {item.received_date.isoformat()}; files changed"
            )

    return StatusUpdate(
        status=status,
        file_count=count,
        received_date=received,
        validation_notes=_join(facts),
    )


def _join(facts: list[str]) -> str:
    note = "; ".join(facts)
    return note if len(note) <= _MAX_NOTE_LEN else note[: _MAX_NOTE_LEN - 3] + "..."


# -------------------------------------------------------------- unfiled ----


def _find_unfiled(
    shared_dir: Path, claimed: set[Path], today: dt.date
) -> list[UnfiledEntry]:
    """Loose files in the Shared root and folders matching no identifier."""
    entries: list[UnfiledEntry] = []
    if not shared_dir.is_dir():
        return entries
    for child in sorted(shared_dir.iterdir()):
        if child.is_file():
            if is_ignored(child) or child.name == README_NAME:
                continue
            entries.append(
                UnfiledEntry(
                    name=child.name,
                    kind="loose file in Shared root",
                    size_kb=round(child.stat().st_size / 1024, 1),
                    seen=today.isoformat(),
                )
            )
        elif child.is_dir() and child not in claimed:
            n = len(iter_candidate_files(child))
            entries.append(
                UnfiledEntry(
                    name=child.name,
                    kind=f"unrecognized folder ({n} file(s))",
                    seen=today.isoformat(),
                )
            )
    return entries


# ------------------------------------------------------------- run lock ----


def _acquire_lock(engagement_dir: Path) -> Path:
    lock = engagement_dir / LOCK_FILENAME
    for attempt in (1, 2):
        try:
            fd = os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            with os.fdopen(fd, "w") as fh:
                fh.write(f"pid={os.getpid()} started={dt.datetime.now().isoformat()}")
            return lock
        except FileExistsError:
            try:
                age = time.time() - lock.stat().st_mtime
            except OSError:
                continue  # lock vanished between checks; retry
            if age < STALE_LOCK_SECONDS:
                raise ScanLockedError(
                    f"another scan appears to be running ({lock.name} is "
                    f"{age:.0f}s old); if not, delete the lock file"
                ) from None
            log.warning("Replacing stale scan lock (%.0f s old)", age)
            lock.unlink(missing_ok=True)
    raise ScanLockedError(f"could not acquire {lock.name}")


# ----------------------------------------------------------------- scan ----


def scan_engagement(
    engagement_dir: Path | str,
    *,
    today: dt.date | None = None,
    dry_run: bool = False,
) -> ScanReport:
    """Scan one engagement and (unless ``dry_run``) write the manifest back.

    Dry runs read everything but write nothing — no manifest update, no
    cache save, no lock file — safe to run alongside a real scan.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    items = load_manifest(engagement_dir / MANIFEST_FILENAME)

    lock: Path | None = None
    if not dry_run:
        lock = _acquire_lock(engagement_dir)
    try:
        shared_dir = engagement_dir / SHARED_DIR_NAME
        cache = ContentCache(engagement_dir / CACHE_FILENAME)
        assigned = assign_folders(shared_dir, [i.identifier for i in items])

        updates = {
            item.identifier: _scan_item(item, assigned[item.identifier], cache, today)
            for item in items
        }

        claimed = {folder for folders in assigned.values() for folder in folders}
        unfiled = _find_unfiled(shared_dir, claimed, today)

        report = ScanReport(
            engagement_dir=engagement_dir,
            updates=updates,
            unfiled=unfiled,
            dry_run=dry_run,
        )
        if dry_run:
            return report

        cache.prune(
            existing={
                path for folder in claimed for path in iter_candidate_files(folder)
            }
        )
        report.written = write_statuses(
            engagement_dir / MANIFEST_FILENAME, updates, unfiled=unfiled
        )
        report.deferred = not report.written
        cache.save()
        return report
    finally:
        if lock is not None:
            lock.unlink(missing_ok=True)


# ------------------------------------------------------------------- CLI ----

def _print_report(report: ScanReport) -> None:
    counts: dict[str, int] = {}
    print(f"\nScan of {report.engagement_dir / SHARED_DIR_NAME}")
    print(f"  {'ID':<8} {'Status':<18} {'Files':<6} Notes")
    print(f"  {'-'*8} {'-'*18} {'-'*6} {'-'*40}")
    for identifier, update in report.updates.items():
        counts[update.status or "(none)"] = counts.get(update.status or "(none)", 0) + 1
        note = update.validation_notes
        if len(note) > 70:
            note = note[:67] + "..."
        print(f"  {identifier:<8} {update.status or '-':<18} {update.file_count:<6} {note}")
    if report.unfiled:
        print("\n  Unfiled (needs your attention; nothing was moved):")
        for entry in report.unfiled:
            print(f"    ? {entry.name}  ({entry.kind})")
    summary = " | ".join(f"{status}: {n}" for status, n in sorted(counts.items()))
    print(f"\n  {summary}")
    if report.dry_run:
        print("  DRY RUN - nothing was written")
    elif report.written:
        print("  Manifest updated")
    else:
        print("  Manifest LOCKED (open in Excel?) - updates deferred to sidecar")


if __name__ == "__main__":
    import argparse
    from logging.handlers import RotatingFileHandler

    parser = argparse.ArgumentParser(
        description="Scan an engagement's Shared/ tree and update _manifest.xlsx"
    )
    parser.add_argument("engagement_dir", help="folder containing _manifest.xlsx")
    parser.add_argument(
        "--dry-run", action="store_true", help="report only; write nothing"
    )
    ns = parser.parse_args()

    engagement = Path(ns.engagement_dir)
    handlers: list[logging.Handler] = [logging.StreamHandler()]
    if not ns.dry_run and engagement.is_dir():
        handlers.append(
            RotatingFileHandler(
                engagement / "_scan.log", maxBytes=512_000, backupCount=2,
                encoding="utf-8",
            )
        )
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        handlers=handlers,
    )

    from tracker.manifest import ManifestError

    try:
        _print_report(scan_engagement(engagement, dry_run=ns.dry_run))
    except ScanLockedError as exc:
        print(f"Scan skipped: {exc}")
        raise SystemExit(2)
    except ManifestError as exc:
        print(f"\nMANIFEST PROBLEM - nothing was scanned or written:\n  {exc}")
        print(f"  Fix {MANIFEST_FILENAME} in Excel (row numbers match Excel rows), save, and re-run.")
        raise SystemExit(1)
