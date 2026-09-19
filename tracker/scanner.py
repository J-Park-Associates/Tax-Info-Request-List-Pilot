"""Scan orchestrator for the tracker (component 5).

Ties the layers together for one engagement: walk ``PREPARED_DIR_NAME/`` — the
working set :mod:`tracker.filer` built from the client's drop folder — match
folders to manifest rows (prefix rule, longest identifier wins), run
validation tiers 1-3, resolve each row's status deterministically, and
**record** what it found.

Recorded, not written back (decision 103). The statuses used to be four
columns of ``MANIFEST_FILENAME``, written with a lock retry and deferred to
a sidecar when Excel held the file; they are one ``scanned`` event now,
appended to the engagement's journal and folded into the store inside one
transaction (:func:`tracker.store.record`), under the lock this scan
already holds. So a scan never touches the workbook - its bytes are the
same before and after a pass - there is nothing to defer, and a person
with the request list open in Excel no longer holds a scan up.

Only what changed is recorded: a pass that finds the engagement exactly as
it left it appends nothing at all, so the record is the list of the
moments something moved rather than one line per pass for ever.

Status policy (docs/ROADMAP.md decision log):

- **Auto-revert** — status always reflects the current scan. A previously
  Received item whose files changed or vanished regresses, keeping its
  original Received Date plus a note.
- **Manual Override wins** — an Accepted row is Received (date stamped
  once, as for any other), a Waived row keeps whatever status it has; the
  scanner still refreshes File Count and records what the rules saw in the
  notes, prefixed ``OVERRIDE_NOTE``.
- **Pending Sync** — cloud-only placeholders are never read; if they are
  the reason a row is short of files, the row waits instead of failing.
- Duplicate uploads ("statement (1).pdf") are de-duplicated by content
  hash before counting — only when more than one valid file exists, so the
  common single-file case never pays for hashing.

Strictly read-only where the client's files are concerned: the scanner
reads the prepared copies and writes only the record, the content cache and
the run-lock. It never touches ``SHARED_DIR_NAME/`` at all — the client's
originals are the filer's business, and even there they are only ever
moved, never altered. The engagement lock (:mod:`tracker.locking`, shared
with the filer) prevents overlapping runs; stale locks are replaced.
"""

from __future__ import annotations

import datetime as dt
import logging
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from tracker import ledger, reasons, store
from tracker.content_check import CACHE_FILENAME, ContentCache, check_content
from tracker.locking import EngagementLockedError, engagement_lock
from tracker.manifest import (
    COL_EXPECTED_COUNT,
    Override,
    RequestItem,
    Status,
    load_manifest,
    summarize,
    with_statuses,
)
from tracker.records import StatusUpdate, identifier_key, status_to_json
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    assign_folders,
)
from tracker.validators import (
    PdfVerdictCache,
    check_folder,
    is_cloud_placeholder,
    is_ignored,
    iter_candidate_files,
    sha256_of,
)

#: The notes the scanner writes that no reason owns: a person's override on
#: the row, how far a multi-file request has got, what was ignored, what is
#: still syncing, and why a Received row is not any more.
OVERRIDE_NOTE = "[override: {override}]"
PARTIAL_NOTE = "{count} of {expected} expected files"
DUPLICATES_NOTE = "{n} duplicate file(s) ignored"
ACCEPTED_NOTE = "{n} file(s) filed here by a person; content rules not applied to them"
FOLDERS_NOTE = "{n} folders match this identifier"
MORE_ISSUES_NOTE = "(+{n} more issues)"
SYNCING_MORE_NOTE = "{n} more file(s) still syncing"
SYNCING_NOTE = "{n} file(s) still syncing from the cloud"
REGRESSION_NOTE = "was {status} {date}; {why}"
REGRESSION_COUNT_RAISED = COL_EXPECTED_COUNT + " is now {expected}"
REGRESSION_FILES_CHANGED = "files changed"

log = logging.getLogger("tracker.scanner")

#: CACHE_FILENAME is tracker.content_check's (the filer writes the cache too);
#: it stays importable from here for anyone's scripts.
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
    warnings: list[str] = field(default_factory=list)   # things in PREPARED_DIR_NAME no row accounts for
    #: How many statuses this scan appended to the record. Zero on a pass
    #: that found the engagement exactly as it left it, and on a dry run.
    recorded: int = 0
    dry_run: bool = False

    @property
    def summary(self):
        """The one count, over the rows as this scan leaves them."""
        return summarize(with_statuses(self.items, self.updates))


# ------------------------------------------------------------- per-item ----


def _filed_by_a_person(engagement_dir: Path) -> frozenset[Path]:
    """Working copies the index records as a person's filing decision.

    The newest row for a location is the one that counts (a person's copy
    that was deleted and whose canonical name a later machine-filed drop
    took is not theirs), and the file must still hold the bytes that row
    recorded - the decision was about those bytes, not the name.
    """
    from tracker.filer import ASSIGNED_BY_PERSON, FILED, read_index

    try:
        rows = read_index(engagement_dir)
    except Exception as exc:   # an unreadable index is the filer's problem, not the scan's
        log.warning("Could not read the index for a person's decisions: %s", exc)
        return frozenset()
    newest = {row.prepared_location: row for row in rows if row.prepared_location}
    accepted = set()
    for location, row in newest.items():
        if row.decision != FILED or not row.reason.startswith(ASSIGNED_BY_PERSON):
            continue
        path = engagement_dir / location
        if is_cloud_placeholder(path):
            continue              # not read: reading would download it; it waits as Pending Sync
        try:
            if row.digest and sha256_of(path) == row.digest:
                accepted.add(path)
        except OSError:
            continue
    return frozenset(accepted)



def _scan_item(
    item: RequestItem,
    folders: list[Path],
    cache: ContentCache,
    today: dt.date,
    pdf_cache: PdfVerdictCache | None = None,
    accepted: frozenset[Path] = frozenset(),
) -> StatusUpdate:
    """Run tiers 1-3 for one manifest row and resolve its status.

    ``accepted`` are working copies a person filed here from Needs Review
    (the index says ``ASSIGNED_BY_PERSON``): their decision stands, so the
    content rules are not run on those files - a rule the document does
    not satisfy would otherwise turn the person's decision into a client
    ask for the "right" file.
    """
    results = [
        fr for folder in folders for fr in check_folder(folder, item, pdf_cache=pdf_cache).files
    ]
    pending = [f for f in results if f.pending_sync]
    # A person's decision waives tier 2 as well as tier 3: they looked at
    # the file, whatever its size or type says.
    tier2_failed = [f for f in results if not f.ok and not f.pending_sync and f.path not in accepted]

    valid: list[Path] = []
    content_failed: list[tuple[Path, str]] = []
    by_person = 0
    for f in (f for f in results if f.ok or f.path in accepted):
        if f.path in accepted:
            valid.append(f.path)
            by_person += 1
            continue
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
    # What is ours to look at comes first: the note lists at most
    # _MAX_LISTED_FAILURES and is cut at _MAX_NOTE_LEN, and a firm-side
    # marker that fell off the end would turn the row into a client ask.
    failures.sort(key=lambda note: not any(r.matches(note) for r in reasons.FIRM_SIDE))

    facts: list[str] = []
    if by_person:
        facts.append(ACCEPTED_NOTE.format(n=by_person))
    if duplicates:
        facts.append(DUPLICATES_NOTE.format(n=duplicates))
    if len(folders) > 1:
        facts.append(FOLDERS_NOTE.format(n=len(folders)))
    facts.extend(failures[:_MAX_LISTED_FAILURES])
    if len(failures) > _MAX_LISTED_FAILURES:
        facts.append(MORE_ISSUES_NOTE.format(n=len(failures) - _MAX_LISTED_FAILURES))

    # --- override rows: a person's call beats the rules --------------------
    if item.manual_override:
        facts.insert(0, OVERRIDE_NOTE.format(override=item.manual_override))
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

    status = _resolve_status(item, folders, count, len(pending), bool(failures), facts)
    received = _received_date(item, status, count, bool(failures), facts, today)
    return StatusUpdate(
        status=status,
        file_count=count,
        received_date=received,
        validation_notes=_join(facts),
    )


def _resolve_status(
    item: RequestItem, folders: list[Path], count: int, pending: int, failed: bool, facts: list[str],
) -> str:
    """The deterministic status for what tiers 1-3 found; adds the note that says why."""
    if not folders:
        facts.insert(0, reasons.NO_REQUEST_FOLDER.format())
        return Status.MISSING
    if count >= item.expected_count:
        if pending:
            facts.append(SYNCING_MORE_NOTE.format(n=pending))
        return Status.RECEIVED
    if pending:
        facts.insert(0, SYNCING_NOTE.format(n=pending))
        return Status.PENDING_SYNC
    if count > 0:
        facts.insert(0, PARTIAL_NOTE.format(count=count, expected=item.expected_count))
        return Status.PARTIAL
    return Status.FAILED if failed else Status.MISSING


def _received_date(
    item: RequestItem, status: str, count: int, failed: bool, facts: list[str], today: dt.date,
) -> dt.date | None:
    """Received Date: stamped on the first Received pass, preserved through regressions."""
    if status == Status.RECEIVED:
        return item.received_date or today
    if status == Status.PENDING_SYNC:
        # The file is still there, the sync client has just let go of its
        # bytes ("free up space"). Nothing changed; the row waits, dated.
        return item.received_date
    if item.received_date is not None:
        # A row that was Received and is not any more either lost files
        # or was asked for more. Say which; REGRESSION_FILES_CHANGED on a row
        # whose Expected Count somebody raised sends a person hunting
        # for a file that never went anywhere.
        had = item.file_count if item.file_count is not None else 0
        if count >= had and item.expected_count > count and not failed:
            why = REGRESSION_COUNT_RAISED.format(expected=item.expected_count)
        else:
            why = REGRESSION_FILES_CHANGED
        facts.insert(0, REGRESSION_NOTE.format(
            status=Status.RECEIVED, date=item.received_date.isoformat(), why=why))
    return item.received_date


def _join(facts: list[str]) -> str:
    note = "; ".join(facts)
    return note if len(note) <= _MAX_NOTE_LEN else note[: _MAX_NOTE_LEN - 3] + "..."


# ------------------------------------------------------------- warnings ----


def _prepared_warnings(prepared_dir: Path, claimed: set[Path]) -> list[str]:
    """Things in ``PREPARED_DIR_NAME/`` that no manifest row accounts for.

    Loose files in the root and folders matching no identifier - somebody
    dragged something in by hand. Parked documents are NOT listed here:
    the engagement's record holds them, with the reason each was parked,
    and the app works from it. Reporting them twice was how the two
    disagreed.
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


def _record_the_statuses(engagement_dir: Path, updates: dict[str, StatusUpdate]) -> int:
    """Append what this scan changed, as one ``scanned`` event. Returns how many.

    **One call, one transaction, under the lock this scan already holds.**
    :func:`tracker.store.record` appends the line to the journal and folds
    it into the store, so either the whole of what this scan decided is on
    the record or none of it is.

    Only what *changed*: the record already holds the statuses of the last
    pass, so a pass that found the engagement exactly as it left it
    appends nothing and the journal stays the list of moments something
    moved. Nothing is written to the workbook, here or anywhere else in a
    pass (decision 103).
    """
    conn = store.connect()
    already = {identifier: status_to_json(update)
               for identifier, update in store.statuses(conn, engagement_dir).items()}
    applied = {identifier: status_to_json(update) for identifier, update in updates.items()}
    changed = {i: s for i, s in applied.items() if already.get(identifier_key(i)) != s}
    if not changed:
        return 0
    store.record(conn, engagement_dir,
                 ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: changed}))
    return len(changed)


def scan_engagement(
    engagement_dir: Path | str,
    *,
    root: Path | None = None,
    today: dt.date | None = None,
    dry_run: bool = False,
    lock_held: bool = False,
) -> ScanReport:
    """Scan one engagement and (unless ``dry_run``) record what it found.

    Dry runs read everything but write nothing — no event, no cache save,
    no lock file — safe to run alongside a real scan.

    ``lock_held`` says the caller already holds this engagement's lock and
    this call must not take it again: that is
    :func:`tracker.runner.run_engagement`, which since decision 102 holds
    one lock across sort, scan and view rather than one per step, so that
    nothing can slip into the gap between two of them.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()

    # The lock comes before the manifest is read (see tracker.locking): a
    # sort that finished in between would otherwise be invisible to this scan.
    # The filer and this module are one deliberate cycle, closed at call
    # time and asserted to stay that way (tests/test_layers.py).
    from tracker.filer import ensure

    with nullcontext() if dry_run or lock_held else engagement_lock(engagement_dir):
        # The store is brought up to the person's sheet and the journal
        # before a thing is read: the rules this scan works from are the
        # imported ones, and recording what it finds needs an engagement
        # the store holds. A dry run migrates and imports nothing, and
        # reads the rules the record already has.
        ensure(engagement_dir, root, migrate=not dry_run)
        # What the record already says about each row is what this scan
        # compares against: the Received Date it carried forward ("first
        # date all validations passed") and the status a regression is
        # measured from both come from there.
        items = load_manifest(engagement_dir)
        prepared_dir = engagement_dir / PREPARED_DIR_NAME
        cache = ContentCache(engagement_dir / CACHE_FILENAME)
        pdf_cache = PdfVerdictCache()     # this scan's; a PDF is parsed once, not once per row
        assigned = assign_folders(prepared_dir, [i.identifier for i in items])

        accepted = _filed_by_a_person(engagement_dir)
        updates = {
            item.identifier: _scan_item(
                item, assigned[item.identifier], cache, today, pdf_cache, accepted=accepted,
            )
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
        report.recorded = _record_the_statuses(engagement_dir, updates)
        cache.save()
        return report


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
    elif report.recorded:
        print(f"  {report.recorded} status(es) recorded")
    else:
        print("  Nothing changed since the last scan")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(
        description=f"Scan an engagement's {PREPARED_DIR_NAME}/ tree and update {MANIFEST_FILENAME}"
    )
    parser.add_argument("engagement_dir", help=f"folder containing {MANIFEST_FILENAME}")
    parser.add_argument(
        "--dry-run", action="store_true", help="report only; write nothing"
    )
    ns = parser.parse_args()

    engagement = Path(ns.engagement_dir)
    # One log for the system - the runner's LOG_FILENAME. A hand-run scan just talks.
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    )

    from tracker.manifest import ManifestError

    try:
        _print_report(scan_engagement(engagement, dry_run=ns.dry_run))
    except ScanLockedError as exc:
        print(f"Scan skipped: {exc}")
        raise SystemExit(2) from None
    except ManifestError as exc:
        print(f"\nMANIFEST PROBLEM - nothing was scanned or written:\n  {exc}")
        print(f"  Fix {MANIFEST_FILENAME} in Excel (row numbers match Excel rows), save, and re-run.")
        raise SystemExit(1) from None
