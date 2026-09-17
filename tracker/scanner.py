"""Scan orchestrator for the Client Document Tracker (component 5).

Ties the layers together for one engagement: walk ``Prepared/`` — the
working set :mod:`tracker.filer` built from the client's drop folder — match
folders to manifest rows (prefix rule, longest identifier wins), run
validation tiers 1-3, resolve each row's status deterministically, and write
results back to ``_manifest.xlsx`` (lock-resiliently, via the manifest layer).

Status policy (docs/ROADMAP.md decision log):

- **Auto-revert** — status always reflects the current scan. A previously
  Received item whose files changed or vanished regresses, keeping its
  original Received Date plus a note.
- **Manual Override wins** — an Accepted row is Received (date stamped
  once, as for any other), a Waived row keeps whatever status it has; the
  scanner still refreshes File Count and records what the rules saw in the
  notes, prefixed ``[override: ...]``.
- **Pending Sync** — cloud-only placeholders are never read; if they are
  the reason a row is short of files, the row waits instead of failing.
- Duplicate uploads ("statement (1).pdf") are de-duplicated by content
  hash before counting — only when more than one valid file exists, so the
  common single-file case never pays for hashing.

Strictly read-only: the scanner reads the prepared copies and writes only
the manifest, content cache and run-lock. It never touches ``Shared/`` at
all — the client's originals are the filer's business, and even there they
are only ever moved, never altered. The engagement lock (:mod:`tracker.locking`,
shared with the filer) prevents overlapping runs; stale locks (>1 h) are replaced.
"""

from __future__ import annotations

import datetime as dt
import logging
from dataclasses import dataclass, field
from pathlib import Path

from tracker import reasons
from tracker.content_check import ContentCache, check_content
from tracker.locking import (
    LOCK_FILENAME,
    STALE_LOCK_SECONDS,
    EngagementLockedError,
    acquire_lock,
)
from tracker.manifest import (
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    load_manifest,
    summarize,
    with_pending,
    write_statuses,
)
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
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
_MAX_NOTE_LEN = 500
_MAX_LISTED_FAILURES = 3

#: The lock is the engagement's, not the scanner's: tracker.filer takes the
#: same one, so a sort and a scan can never overlap. The old name stays
#: importable for the runner, the API and anyone's scripts.
ScanLockedError = EngagementLockedError


@dataclass(slots=True)
class ScanReport:
    """Everything one scan found and did."""

    engagement_dir: Path
    items: list[RequestItem] = field(default_factory=list)   # the rows as loaded
    updates: dict[str, StatusUpdate] = field(default_factory=dict)
    warnings: list[str] = field(default_factory=list)   # things in Prepared/ no row accounts for
    written: bool = False    # manifest updated on disk
    deferred: bool = False   # manifest was locked; updates went to sidecar
    dry_run: bool = False

    @property
    def summary(self):
        """The one count, over the rows as this scan leaves them."""
        return summarize(with_pending(self.items, self.updates))


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
            try:
                digest = sha256_of(path)
            except OSError:
                continue  # vanished since tier 2 ran; it is not a valid file now
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

    # --- override rows: a person's call beats the rules --------------------
    if item.manual_override:
        facts.insert(0, f"[override: {item.manual_override}]")
        if item.manual_override == Override.ACCEPTED:
            # Accepted means "treat as Received despite the rules" (decision
            # 2), so it IS Received: status, date and every count that reads
            # the status column agree, instead of a row a person signed off
            # on still reading Missing or Failed in the sheet and the run.
            return StatusUpdate(
                status=Status.RECEIVED,
                file_count=count,
                received_date=item.received_date or today,
                validation_notes=_join(facts),
            )
        return StatusUpdate(
            status=item.status,
            file_count=count,
            received_date=item.received_date,
            validation_notes=_join(facts),
        )

    # --- deterministic status resolution -----------------------------------
    if not folders:
        status = Status.MISSING
        facts.insert(0, reasons.NO_REQUEST_FOLDER.format())
    elif count >= item.expected_count:
        status = Status.RECEIVED
        if pending:
            facts.append(f"{len(pending)} more file(s) still syncing")
    elif pending:
        status = Status.PENDING_SYNC
        facts.insert(0, f"{len(pending)} file(s) still syncing from the cloud")
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
            # A row that was Received and is not any more either lost files
            # or was asked for more. Say which; "files changed" on a row
            # whose Expected Count somebody raised sends a person hunting
            # for a file that never went anywhere.
            had = item.file_count if item.file_count is not None else 0
            if count >= had and item.expected_count > count and not failures:
                why = f"Expected Count is now {item.expected_count}"
            else:
                why = "files changed"
            facts.insert(0, f"was Received {item.received_date.isoformat()}; {why}")

    return StatusUpdate(
        status=status,
        file_count=count,
        received_date=received,
        validation_notes=_join(facts),
    )


def _join(facts: list[str]) -> str:
    note = "; ".join(facts)
    return note if len(note) <= _MAX_NOTE_LEN else note[: _MAX_NOTE_LEN - 3] + "..."


# ------------------------------------------------------------- warnings ----


def _prepared_warnings(prepared_dir: Path, claimed: set[Path]) -> list[str]:
    """Things in ``Prepared/`` that no manifest row accounts for.

    Loose files in the root and folders matching no identifier - somebody
    dragged something in by hand. Parked documents are NOT listed here:
    ``_index.xlsx`` is their record, with the reason each was parked, and
    the app works from it. Reporting them twice was how the two disagreed.
    """
    warnings: list[str] = []
    if not prepared_dir.is_dir():
        return warnings
    for child in sorted(prepared_dir.iterdir()):
        if child.is_file():
            if not is_ignored(child):
                warnings.append(
                    f"{child.name} is loose in {PREPARED_DIR_NAME}/; it belongs in a request folder"
                )
        elif child.is_dir() and child.name != REVIEW_DIR_NAME and child not in claimed:
            n = len(iter_candidate_files(child))
            warnings.append(
                f"folder {child.name!r} in {PREPARED_DIR_NAME}/ matches no request "
                f"({n} file(s) inside)"
            )
    return warnings


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
        lock = acquire_lock(engagement_dir)
    try:
        prepared_dir = engagement_dir / PREPARED_DIR_NAME
        cache = ContentCache(engagement_dir / CACHE_FILENAME)
        assigned = assign_folders(prepared_dir, [i.identifier for i in items])

        updates = {
            item.identifier: _scan_item(item, assigned[item.identifier], cache, today)
            for item in items
        }

        claimed = {folder for folders in assigned.values() for folder in folders}

        report = ScanReport(
            engagement_dir=engagement_dir,
            items=items,
            updates=updates,
            warnings=_prepared_warnings(prepared_dir, claimed),
            dry_run=dry_run,
        )
        if dry_run:
            return report

        cache.prune(
            existing={
                path for folder in claimed for path in iter_candidate_files(folder)
            }
        )
        report.written = write_statuses(engagement_dir / MANIFEST_FILENAME, updates)
        report.deferred = not report.written
        cache.save()
        return report
    finally:
        if lock is not None:
            lock.unlink(missing_ok=True)


# ------------------------------------------------------------------- CLI ----

def _print_report(report: ScanReport) -> None:
    print(f"\nScan of {report.engagement_dir / PREPARED_DIR_NAME}")
    print(f"  {'ID':<8} {'Status':<18} {'Files':<6} Notes")
    print(f"  {'-'*8} {'-'*18} {'-'*6} {'-'*40}")
    for identifier, update in report.updates.items():
        note = update.validation_notes
        if len(note) > 70:
            note = note[:67] + "..."
        print(f"  {identifier:<8} {update.status or '-':<18} {update.file_count:<6} {note}")
    for warning in report.warnings:
        print(f"    ! {warning}")
    print(f"\n  {report.summary.line}")
    if report.dry_run:
        print("  DRY RUN - nothing was written")
    elif report.written:
        print("  Manifest updated")
    else:
        print("  Manifest LOCKED (open in Excel?) - updates deferred to sidecar")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description="Scan an engagement's Prepared/ tree and update _manifest.xlsx"
    )
    parser.add_argument("engagement_dir", help="folder containing _manifest.xlsx")
    parser.add_argument(
        "--dry-run", action="store_true", help="report only; write nothing"
    )
    ns = parser.parse_args()

    engagement = Path(ns.engagement_dir)
    # One log for the system - the runner's runs.log. A hand-run scan just talks.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
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
