"""Scan orchestrator for the tracker (component 5).

Ties the layers together for one engagement: walk ``PREPARED_DIR_NAME/`` — the
working set :mod:`tracker.filer` built from the client's drop folder — match
the files in it to manifest rows by their names (prefix rule, longest
identifier wins: ``tracker.scaffold.assign_files``, decision 168), run
validation tiers 1-3, resolve each row's status deterministically, and
**record** what it found. A folder inside ``PREPARED_DIR_NAME`` other than
the review folder is a person's: nothing in it is counted, and the scan
names it once (``reasons.PERSONS_FOLDER``).

Recorded, not written back (decision 103). The statuses used to be four
columns of a workbook, written with a lock retry and deferred to a
sidecar when Excel held the file; they are one ``scanned`` event now,
appended to the engagement's journal and folded into the store inside one
transaction (:func:`tracker.store.record`), under the lock this scan
already holds. There is nothing to defer, and nothing a person has open
holds a scan up.

Only what changed is recorded: a pass that finds the engagement exactly as
it left it appends nothing at all, so the record is the list of the
moments something moved rather than one line per pass for ever.

Status policy (docs/ROADMAP.md decision log):

- **Auto-revert** — status always reflects the current scan. A previously
  Received item whose files changed or vanished regresses, keeping its
  original Received Date plus a note.
- **Manual Override wins** — an Accepted row is Received (date stamped
  once, as for any other), a Not Applicable row keeps whatever status it
  has; the
  scanner still refreshes File Count and records what the rules saw in the
  notes, prefixed ``OVERRIDE_NOTE``.
- **Pending Sync** — cloud-only placeholders are never read; if they are
  the reason a row is short of files, the row waits instead of failing.
- Duplicate uploads ("statement (1).pdf") are de-duplicated by content
  hash before counting — only when more than one valid file exists, so the
  common single-file case never pays for hashing.
- **A moved working copy is the record's word, not this scan's** (decision
  109). A file the record says is another row's mislaid copy is not
  counted under the request its name belongs to, and the request whose
  copy has gone reads Missing - truthfully, nothing of it is there - with a
  firm-side note (``reasons.FILE_MOVED``) so no draft asks the client for
  a file the firm moved. The filer's sweep decided it, under the same
  lock, earlier in the pass; this reads the rows and acts.
- **A copy that is not the one the record filed is said, and not
  counted** (decision 3 extended; decision 155): a working copy whose
  bytes disagree with its row's - the original's - is treated as not
  there, so a copy torn in half, or another file put in its place, never
  makes a request Received. The request carries ``reasons.COPY_CHANGED``,
  firm-side, on the row and on the run's warnings, so its Missing is never
  a client ask. Until decision 155 the newcomer was counted and kept
  whatever status it earned.
- **A missing copy is never a client ask by itself** (decision 157). The
  filer's sweep makes a gone working copy again from its original before
  this reads anything; one it could not make this pass reads Missing with
  ``reasons.COPY_MISSING``, one whose original is gone too with
  ``reasons.COPY_AND_ORIGINAL_GONE``, and a request answered by a
  consolidated statement whose own copy is not counted is not counted
  either (``reasons.ANSWER_NOT_COUNTED``). All three are firm-side: only a
  person's Mark missing puts the document back on the letter.

Strictly read-only where the client's files are concerned: the scanner
reads the prepared copies and writes only the record, the verdict cache in
the store (decision 107) and the run-lock. It never touches
the household's inbox at all — the client's originals are the filer's
business, and even there they are only ever moved, never altered. The
engagement lock (:mod:`tracker.locking`, shared with the filer) prevents
overlapping runs; stale locks are replaced.
"""

from __future__ import annotations

import datetime as dt
import logging
import re
from collections.abc import Callable
from contextlib import nullcontext
from dataclasses import dataclass, field
from pathlib import Path

from tracker import ledger, reasons, store
from tracker.content_check import ContentCache, OutOfTime, check_content, open_verdict
from tracker.layout import locate
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
from tracker.records import (
    CANDIDATE_SEP,
    IndexEntry,
    StatusUpdate,
    answer_count,
    as_pattern,
    identifier_key,
    status_to_json,
)
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    assign_files,
    owner_of,
    persons_folders,
)
from tracker.validators import (
    PdfVerdictCache,
    check_files,
    is_cloud_placeholder,
    is_ignored,
    iter_candidate_files,
)

#: The notes the scanner writes that no reason owns: a person's override on
#: the row, how far a multi-file request has got, what was ignored, what is
#: still syncing, and why a Received row is not any more.
OVERRIDE_NOTE = "[override: {override}]"
PARTIAL_NOTE = "{count} of {expected} expected files"
DUPLICATES_NOTE = "{n} duplicate file(s) ignored"
ACCEPTED_NOTE = "{n} file(s) filed here by a person; content rules not applied to them"
MORE_ISSUES_NOTE = "(+{n} more issues)"
SYNCING_MORE_NOTE = "{n} more file(s) still syncing"
SYNCING_NOTE = "{n} file(s) still syncing from the cloud"
REGRESSION_NOTE = "was {status} {date}; {why}"
REGRESSION_COUNT_RAISED = COL_EXPECTED_COUNT + " is now {expected}"
REGRESSION_FILES_CHANGED = "files changed"
#: The run's warning for a file directly in ``PREPARED_DIR_NAME`` whose
#: name begins with no request's identifier (decision 168): it belongs to
#: no request, so nothing counts it. Until 168 every loose file there was
#: said to belong "in a request folder".
UNCLAIMED_FILE = ("{name} is in {prepared}/ and its name begins with no request's identifier, "
                  "so it is not counted")


#: The regression sentence read back off the front of a note (it is always
#: the first fact): REGRESSION_NOTE around either of its two reasons. The
#: pattern comes from the very template that wrote the sentence
#: (:func:`tracker.records.as_pattern`, which moved down to the record with
#: decision 109 so the moved sentence on an index row is read back the same
#: way): the words have one home and a reader never retypes them.
_REGRESSION_SENTENCE = re.compile(as_pattern(
    REGRESSION_NOTE,
    status=re.escape(Status.RECEIVED),
    date=r"\d{4}-\d{2}-\d{2}",
    why="(?P<why>" + as_pattern(REGRESSION_COUNT_RAISED, expected=r"\d+")
        + "|" + re.escape(REGRESSION_FILES_CHANGED) + ")",
) + "(?:; |$)")

log = logging.getLogger("tracker.scanner")

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
    #: How many requests the household's time for this pass did not reach
    #: (decision 189). Not scanned and not recorded: each keeps the status
    #: the record already holds until the next pass scans it.
    unreached: int = 0
    dry_run: bool = False

    @property
    def summary(self):
        """The one count, over the rows as this scan leaves them."""
        return summarize(with_statuses(self.items, self.updates))


# ------------------------------------------------------------- per-item ----


def _the_index(engagement_dir: Path) -> list[IndexEntry]:
    """The engagement's index rows, or none where it cannot be read.

    Read once per scan and handed to everything here that needs it: what a
    person filed, which paths the record claims, and which file is another
    row's mislaid copy. An unreadable index is the filer's problem, not the
    scan's - the firm's folder is still walked and the statuses still
    recorded.
    """
    from tracker.filer import read_index

    try:
        return read_index(engagement_dir)
    except Exception as exc:
        log.warning("Could not read the index: %s", exc)
        return []


def _filed_by_a_person(
    engagement_dir: Path, rows: list[IndexEntry], cache: ContentCache
) -> frozenset[Path]:
    """Working copies the index records as a person's filing decision.

    The newest row for a location is the one that counts (a person's copy
    that was deleted and whose canonical name a later machine-filed drop
    took is not theirs), and the file must still hold the bytes that row
    recorded - the decision was about those bytes, not the name. The bytes
    are read through the cache's memo (decision 109), so a tree that has
    not moved since the last pass is stats and no reads.
    """
    from tracker.filer import ASSIGNED_BY_PERSON, FILED

    newest = {row.prepared_location: row for row in rows if row.prepared_location}
    accepted = set()
    for location, row in newest.items():
        if row.decision != FILED or not row.reason.startswith(ASSIGNED_BY_PERSON):
            continue
        path = locate(engagement_dir, location)
        if is_cloud_placeholder(path):
            continue              # not read: reading would download it; it waits as Pending Sync
        if row.digest and cache.digest_of(path) == row.digest:
            accepted.add(path)
    return frozenset(accepted)


def _claimed_paths(engagement_dir: Path, rows: list[IndexEntry]) -> dict[Path, IndexEntry]:
    """Every working copy the record names, and the row that names it.

    The newest row for a location wins it, as everywhere else: what sits at
    an earlier row's path is the later row's by the index's own word. A row
    recorded without its bytes (decision 65) claims nothing - there is
    nothing to hold a file to.
    """
    claimed: dict[Path, IndexEntry] = {}
    for row in rows:
        if row.digest:
            for location in row.filed_locations:
                claimed[locate(engagement_dir, location)] = row
    return claimed


def _wandered(engagement_dir: Path, rows: list[IndexEntry]) -> frozenset[Path]:
    """Where the record says each mislaid working copy is now.

    A file the record knows is another row's copy is not counted under the
    request its name happens to belong to - that count would be a filing
    nobody made, and the record knows whose the file is. Every other file
    named for a request is counted as it sits: what a request has is what
    ``PREPARED_DIR_NAME`` holds under its name, and a file a person can see
    going uncounted would be a lie in the other direction.
    """
    from tracker.filer import moved_to

    return frozenset(
        locate(engagement_dir, now) for now in (moved_to(row) for row in rows) if now
    )


def _interrupted(engagement_dir: Path, rows: list[IndexEntry]) -> dict[Path, str]:
    """Where an interrupted step was putting a working copy, and what the
    row it parked says about it (decision 119).

    The file at that path is nobody's: a step that died half way left it -
    a copy truncated by the power going out is the shape of it - and the
    row it was for parked with a working copy of its own. Counting it
    would read a request as Failed Validation for a document the client
    sent correctly, which is the thing decision 119 fixes, so it is not
    counted and the request is told in the row's own sentence instead.
    Firm-side, always: no draft asks a client about a power cut here.
    """
    from tracker.filer import interrupted_at, interrupted_note

    found: dict[Path, str] = {}
    for row in rows:
        where = interrupted_at(row)
        if where:
            # Said with the row's own code (decision 190), so the request's
            # note records the cause the row recorded.
            found[locate(engagement_dir, where)] = reasons.Said(interrupted_note(row), row.code)
    return found


#: Why a consolidated statement's answers are not counted (decision 157,
#: ruling B9): what is wrong with the statement's own working copy, said
#: inside ``reasons.ANSWER_NOT_COUNTED`` beside the statement's request.
ANSWER_WHY_MISSING = "its working copy is missing"
ANSWER_WHY_CHANGED = "its working copy is not the one the record filed"
ANSWER_WHY_NOWHERE = "its working copy is nowhere under the firm's folder"
ANSWER_WHY_BOTH_GONE = "its working copy and its original are both gone"
#: How the statement is named in that sentence: its request, and why.
ANSWERED_BY = "{row}'s consolidated statement ({why})"


def _host_not_counted(engagement_dir: Path, row: IndexEntry, cache: ContentCache) -> str:
    """Why this consolidated statement's own working copy is not counted,
    or ``""`` when it is (decision 157, ruling B9, from 146's restack
    review, finding 2): an answer is only as good as the document that gives
    it, so the requests it answers follow it.

    Not counted: the copy is gone (the pass could not make it again), holds
    other bytes (decision 155), is nowhere under the firm's folder, or is
    gone with its original. Counted: here and the row's bytes, still
    syncing (a placeholder is Pending Sync, never gone), or where a person
    dragged it (decision 109 - the firm still holds it, and the row's own
    request says so). A row recorded without its bytes (decision 65) has
    nothing to be proved against, and counts as it always did.
    """
    from tracker.filer import FILE_MOVED, both_gone, moved_to

    if not row.digest or not row.prepared_location:
        return ""
    if row.decision == FILE_MOVED:
        if both_gone(row):
            return ANSWER_WHY_BOTH_GONE
        return "" if moved_to(row) else ANSWER_WHY_NOWHERE
    home = locate(engagement_dir, row.prepared_location)
    if is_cloud_placeholder(home):
        return ""
    if not home.is_file():
        return ANSWER_WHY_MISSING
    return "" if cache.digest_of(home) == row.digest else ANSWER_WHY_CHANGED


def _answered(
    engagement_dir: Path, rows: list[IndexEntry], cache: ContentCache,
) -> dict[str, list[tuple[str, int, str]]]:
    """Which requests a filed consolidated statement answers without a copy
    (decision 146), by request: the request it filed under, how many
    documents it counts for - one per section that answered - and why it
    does not count, ``""`` while it does (decision 157).

    Read off each filed row's Also Answers cell (``IndexEntry.answered``)
    and off nothing else, so the status, the letter (which reads the
    status) and the client's received list (``tracker.filer.received_for``,
    which reads the same cell) cannot disagree. A row counts while the
    record calls it received - Filed, or File Moved, whose own request the
    sweep already tells the firm about (decision 109) - which is the rule
    the received list keeps too, and **while its own working copy is
    counted** (:func:`_host_not_counted`, decision 157): a request answered
    by a statement the firm cannot open is held for a person, never
    Received on it. Keyed without case, as a status is.
    """
    from tracker.filer import FILE_MOVED, FILED

    found: dict[str, list[tuple[str, int, str]]] = {}
    for row in rows:
        if row.decision not in (FILED, FILE_MOVED) or not row.identifier or not row.answered:
            continue
        why = _host_not_counted(engagement_dir, row, cache)
        for answer in row.answered:
            found.setdefault(identifier_key(answer[0]), []).append(
                (row.identifier, answer_count(answer), why))
    return found


def _changed_copy_warnings(
    claimed: dict[Path, IndexEntry], prepared_dir: Path, cache: ContentCache
) -> list[str]:
    """One warning per working copy that is not the one the record filed.

    The request's own note says it too (``_scan_item``); this is what puts
    it on the run and so on the practice page, where a person sees every
    engagement at once. Only the copies directly in ``PREPARED_DIR_NAME``,
    where this scan counts (decision 168): a parked copy is the record's
    business and the app's, not a warning about a request, and nothing in
    a person's folder is counted to be warned about.
    """
    return [
        f"{path.name}: {reasons.COPY_CHANGED.format(listed=path.name)}"
        for path, row in claimed.items()
        if path.parent == prepared_dir and _a_stranger_at(path, row, cache)
    ]


def _a_stranger_at(path: Path, row: IndexEntry, cache: ContentCache) -> bool:
    """Whether a path the record claims holds bytes that are not the row's.

    Decision 3 extended (decision 109): a working copy replaced by a
    different document that still passes the rules kept Received in
    silence, because nothing ever compared the file with the fingerprint
    its own row carries. A placeholder is never read and a file that has
    gone is not a stranger - it is the regression decision 3 already says.
    """
    if not path.is_file() or is_cloud_placeholder(path):
        return False
    return cache.digest_of(path) != row.digest


def _the_rows_copy_is_here(path: Path, row: IndexEntry, cache: ContentCache) -> bool:
    """Whether a path the record claims still holds that row's document.

    Asked of a ``FILE_MOVED`` row, which may have a copy under more than one
    request (decision 94): the note about a copy that has gone belongs to
    the request that lost one, not to the request that still has its own.
    """
    return (path.is_file() and not is_cloud_placeholder(path)
            and cache.digest_of(path) == row.digest)


def _scan_item(
    item: RequestItem,
    files: list[Path],
    cache: ContentCache,
    today: dt.date,
    pdf_cache: PdfVerdictCache | None = None,
    accepted: frozenset[Path] = frozenset(),
    claimed: dict[Path, IndexEntry] | None = None,
    excluded: frozenset[Path] = frozenset(),
    interrupted: dict[Path, str] | None = None,
    answered: list[tuple[str, int, str]] | tuple = (),
    mine: Callable[[Path], bool] = lambda _path: False,
) -> StatusUpdate:
    """Run tiers 1-3 for one manifest row and resolve its status.

    ``files`` are the request's files - the ones directly in
    ``PREPARED_DIR_NAME`` whose names belong to it
    (``tracker.scaffold.assign_files``, decision 168). ``mine`` says the
    same of a path that may not be there any more: a copy the record put
    under this request's name that has gone, or the place an interrupted
    step was putting one.

    ``accepted`` are working copies a person filed here from Needs Review
    (the index says ``ASSIGNED_BY_PERSON``): their decision stands, so the
    content rules are not run on those files - a rule the document does
    not satisfy would otherwise turn the person's decision into a client
    ask for the "right" file.

    ``claimed`` and ``excluded`` are what the record says about these
    files (decision 109). A file in ``excluded`` is another row's mislaid
    working copy and is not this request's, whatever its bytes say:
    counting it here is the corruption the sweep exists to stop. A file
    the record claims whose bytes are not its row's is not counted either,
    and is said (``COPY_CHANGED``, decision 155), and a row whose copy
    under this request's name has gone is said too (``FILE_MOVED``) - both
    firm-side, so no draft asks the client for a file the firm moved.

    ``interrupted`` is where a step that died half way was putting a copy,
    and the sentence the row it parked carries (decision 119). It is not
    counted either - what sits there is the wreck of a step, not a
    document anybody filed - and the sentence goes on the request, so a
    request that has a copy the power cut in half reads Missing with the
    firm's own note rather than Failed Validation for a file the client
    sent correctly.

    ``answered`` is the consolidated statements filed under another
    request that answer this one (decision 146, :func:`_answered`): each
    counts as the documents its sections are, beside whatever this
    request's own files are, and is said on the row
    (``reasons.IN_CONSOLIDATED``). No file of this request's is read for
    it - the statement was read, and accepted by this row's own rules,
    when it was routed. One whose own working copy is not counted counts
    nothing here either, and says so, firm-side
    (``reasons.ANSWER_NOT_COUNTED``, decision 157).

    **A missing copy is never a client ask by itself** (decision 157,
    ruling B9). A copy the record put under this request's name that is
    gone - one the pass could not make again this time, its original still
    syncing or unreadable - leaves the request Missing with
    ``reasons.COPY_MISSING``; one whose original is gone too says
    ``reasons.COPY_AND_ORIGINAL_GONE`` rather than decision 110's
    put-it-back wording. Both are firm-side, so the letter holds off until
    a person marks the document missing.
    """
    from tracker.filer import FILE_MOVED, both_gone, moved_to, prepared_location

    claimed = claimed or {}
    interrupted = interrupted or {}
    # Tier 2's open test is never made in this process (decision 150): it
    # is the file's kept verdict, or made in a reading's child beside the
    # reading the content check below will then use - and, since decision
    # 189, beside the judgment of this row's rules, in the same job, so a
    # working copy costs one trip to the child and no text comes back.
    def open_test(path: Path) -> str:
        return open_verdict(path, cache, item)

    results = check_files(files, item, pdf_cache=pdf_cache, open_test=open_test)
    # A working copy the record claims whose bytes are not its row's - the
    # original's - is not there, as far as the count goes (decision 155): a
    # half copy is never counted, and neither is a file somebody put in its
    # place. It is said (COPY_CHANGED), firm-side, below.
    strangers = [f.path for f in results
                 if f.path in claimed and _a_stranger_at(f.path, claimed[f.path], cache)]
    if excluded or interrupted or strangers:
        results = [f for f in results
                   if f.path not in excluded and f.path not in interrupted
                   and f.path not in strangers]
    pending = [f for f in results if f.pending_sync]
    # A person's decision waives tier 2 as well as tier 3: they looked at
    # the file, whatever its size or type says.
    tier2_failed = [f for f in results if not f.ok and not f.pending_sync and f.path not in accepted]

    valid: list[Path] = []
    content_failed: list[tuple[Path, str, str]] = []
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
            content_failed.append((f.path, verdict.reason, verdict.code))

    # De-duplicate by content hash — but never hash the common 0/1-file
    # case, and hash through the memo when there is one to hash (109).
    duplicates = 0
    if len(valid) > 1:
        seen: set[str] = set()
        distinct: list[Path] = []
        for path in valid:
            digest = cache.digest_of(path)
            if digest is None:
                continue  # vanished since tier 2 ran; it is not a valid file now
            if digest in seen:
                duplicates += 1
            else:
                seen.add(digest)
                distinct.append(path)
        valid = distinct
    count = len(valid) + sum(n for _filed, n, why in answered if not why)

    # Each failure as (note, code): the note names the file, the code says
    # the cause (decision 190), and only the code is ever read.
    failures = [(f"{f.path.name}: {f.reason}", f.code) for f in tier2_failed]
    failures += [(f"{path.name}: {reason}", code) for path, reason, code in content_failed]
    # What is ours to look at comes first: the note lists at most
    # _MAX_LISTED_FAILURES and is cut at _MAX_NOTE_LEN, and a firm-side
    # cause that fell off the end would turn the row into a client ask.
    failures.sort(key=lambda failure: failure[1] not in reasons.FIRM_SIDE)

    facts: list[str] = []
    #: The code of each fact that says a cause, in the facts' order
    #: (decision 190). The facts inserted at the front below (the override,
    #: the count, the regression) say no cause, so the order holds.
    codes: list[str] = []

    def said(sentence: str, code: str) -> None:
        facts.append(sentence)
        codes.append(code)

    if by_person:
        facts.append(ACCEPTED_NOTE.format(n=by_person))
    if duplicates:
        facts.append(DUPLICATES_NOTE.format(n=duplicates))
    for filed in dict.fromkeys(filed for filed, _n, why in answered if not why):
        facts.append(reasons.IN_CONSOLIDATED.format(row=filed))
    for filed, why in dict.fromkeys((filed, why) for filed, _n, why in answered if why):
        said(reasons.ANSWER_NOT_COUNTED.format(listed=ANSWERED_BY.format(row=filed, why=why)),
             reasons.ANSWER_NOT_COUNTED.code)
    # What the record says about this request's own copies, before the
    # failures, so the note's cut can never take a firm-side code off the
    # end and turn the row into a client ask. Neither is a failure: a row
    # whose copy was dragged away leaves the request Missing, truthfully,
    # and a file that passes the rules is counted whoever put it there.
    for path, row in claimed.items():
        if not mine(path):
            continue
        listed = prepared_location(path.parent, path.name)
        if row.decision == FILE_MOVED and not _the_rows_copy_is_here(path, row, cache):
            if both_gone(row):
                said(reasons.COPY_AND_ORIGINAL_GONE.format(listed=f"{row.original_name} ({listed})"),
                     reasons.COPY_AND_ORIGINAL_GONE.code)
                continue
            now = moved_to(row)
            said(reasons.FILE_MOVED.format(listed="{} -> {}".format(
                listed, now or f"nowhere under {PREPARED_DIR_NAME}",
            )), reasons.FILE_MOVED.code)
        elif row.decision != FILE_MOVED and not path.exists():
            # Decision 157, B9: the pass makes it again when it can.
            said(reasons.COPY_MISSING.format(listed=listed), reasons.COPY_MISSING.code)
    for path, sentence in interrupted.items():
        if mine(path) and path.exists():
            said(sentence, reasons.code_of(sentence))
    for path in strangers:
        said(reasons.COPY_CHANGED.format(listed=path.name), reasons.COPY_CHANGED.code)
    for note, code in failures[:_MAX_LISTED_FAILURES]:
        said(note, code)
    if len(failures) > _MAX_LISTED_FAILURES:
        facts.append(MORE_ISSUES_NOTE.format(n=len(failures) - _MAX_LISTED_FAILURES))

    # --- override rows: a person's call beats the rules --------------------
    if item.manual_override:
        facts.insert(0, OVERRIDE_NOTE.format(override=item.manual_override))
        if item.manual_override == Override.ACCEPTED:
            # Accepted means "treat as Received despite the rules" (decision
            # 2), so it IS Received: status, date and every count that reads
            # the status column agree, instead of a row a person signed off
            # on still reading Missing or Failed on the page and in the run.
            return StatusUpdate(
                status=Status.RECEIVED,
                file_count=count,
                received_date=item.received_date or today,
                validation_notes=_join(facts),
                note_codes=_joined_codes(codes),
            )
        return StatusUpdate(
            status=item.status,
            file_count=count,
            received_date=item.received_date,
            validation_notes=_join(facts),
            note_codes=_joined_codes(codes),
        )

    status = _resolve_status(item, count, len(pending), bool(failures), facts)
    received = _received_date(item, status, count, bool(failures), facts, today)
    return StatusUpdate(
        status=status,
        file_count=count,
        received_date=received,
        validation_notes=_join(facts),
        note_codes=_joined_codes(codes),
    )


def _resolve_status(
    item: RequestItem, count: int, pending: int, failed: bool, facts: list[str],
) -> str:
    """The deterministic status for what tiers 1-3 found; adds the note that says why.

    A request with nothing named for it in ``PREPARED_DIR_NAME`` is simply
    Missing, with no note (decision 168): no request has a folder that
    could be missing, so "request folder not found" - which until then
    held a request with no folder back from the letter - has nothing left
    to say."""
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


def _regression_why(previous_note: str) -> str | None:
    """The reason the last note gave for the row leaving Received, read back
    off its first fact - or None when that note holds no regression sentence
    (a row written before decision 108, or one that regressed through a
    Pending Sync note), in which case the caller says REGRESSION_FILES_CHANGED
    and never the count sentence: a person is sent to look for a count edit
    only when a scan saw one."""
    found = _REGRESSION_SENTENCE.match(previous_note)
    return found.group("why") if found else None


def _received_date(
    item: RequestItem, status: str, count: int, failed: bool, facts: list[str], today: dt.date,
) -> dt.date | None:
    """Received Date: stamped on the first Received pass, preserved through
    regressions - and the regression's reason decided once, then carried.

    The sentence says why the row *left* Received. That can only be judged
    on the pass it leaves, when ``item.file_count`` is still the Received
    count: a count no lower than it with more expected and nothing failed
    means somebody raised the Expected Count, anything else means the files
    changed. On every later pass the record's count is the regressed one,
    so the same comparison would call every lost file a raised count
    (decision 108); the reason is read back from the last note instead.
    """
    if status == Status.RECEIVED:
        return item.received_date or today
    if status == Status.PENDING_SYNC:
        # The file is still there, the sync client has just let go of its
        # bytes ("free up space"). Nothing changed; the row waits, dated.
        return item.received_date
    if item.received_date is not None:
        if item.status == Status.RECEIVED:
            # The pass the row leaves Received: it either lost files or was
            # asked for more. Say which; REGRESSION_FILES_CHANGED on a row
            # whose Expected Count somebody raised sends a person hunting
            # for a file that never went anywhere.
            had = item.file_count if item.file_count is not None else 0
            if count >= had and item.expected_count > count and not failed:
                why = REGRESSION_COUNT_RAISED.format(expected=item.expected_count)
            else:
                why = REGRESSION_FILES_CHANGED
        else:
            # Already regressed: the reason it left is the reason it left.
            why = _regression_why(item.validation_notes) or REGRESSION_FILES_CHANGED
        facts.insert(0, REGRESSION_NOTE.format(
            status=Status.RECEIVED, date=item.received_date.isoformat(), why=why))
    return item.received_date


def _joined_codes(codes: list[str]) -> str:
    """The facts' codes as the record keeps them (``StatusUpdate.note_codes``):
    joined as the index joins its candidates, a fact with no code left out."""
    return CANDIDATE_SEP.join(code for code in codes if code)


def _join(facts: list[str]) -> str:
    note = "; ".join(facts)
    return note if len(note) <= _MAX_NOTE_LEN else note[: _MAX_NOTE_LEN - 3] + "..."


# ------------------------------------------------------------- warnings ----


def _prepared_warnings(prepared_dir: Path, identifiers: list[str]) -> list[str]:
    """Things in ``PREPARED_DIR_NAME/`` that no manifest row accounts for.

    A file whose name begins with no request's identifier
    (:data:`UNCLAIMED_FILE`), and every folder other than the review folder
    (``reasons.PERSONS_FOLDER``, decision 168): working copies sit in the
    firm's folder itself, so a folder in it is a person's - or a request
    folder of a return made before 168 - and nothing in it is counted. Each
    folder is named once per pass, however many files it holds, and never
    file by file. Parked documents are NOT listed here: the engagement's
    record holds them, with the reason each was parked, and the app works
    from it. Reporting them twice was how the two disagreed.
    """
    warnings: list[str] = []
    if not prepared_dir.is_dir():
        return warnings
    for child in sorted(prepared_dir.iterdir()):
        if child.is_file() and not is_ignored(child) and owner_of(child.name, identifiers) is None:
            warnings.append(UNCLAIMED_FILE.format(name=child.name, prepared=PREPARED_DIR_NAME))
    for folder in persons_folders(prepared_dir):
        warnings.append(reasons.PERSONS_FOLDER.format(folder=folder.name, prepared=PREPARED_DIR_NAME))
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
    moved. Nothing but the record is written, here or anywhere else in a
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
    deadline: float | None = None,
) -> ScanReport:
    """Scan one engagement and (unless ``dry_run``) record what it found.

    **Kept as it goes, and bounded** (decision 189). The verdicts are
    saved after every request, so a pass killed mid-scan reads again only
    what it was killed on (a save with nothing new is no transaction at
    all). ``deadline`` is a moment on ``ocr.awake_clock``, checked where a
    request would need a new judgment - a cache miss (ruling 2.2,
    :func:`tracker.content_check.before_a_judgment`): a request whose
    verdicts are all kept is scanned whatever the time, and past the
    deadline the first request that would read stops the scan. What was
    scanned is recorded, and the rest keep the status the record holds
    until the next pass (``unreached``).

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

    # The lock comes before the request list is read (see tracker.locking):
    # a sort that finished in between would otherwise be invisible to this scan.
    # The filer and this module are one deliberate cycle, closed at call
    # time and asserted to stay that way (tests/test_layers.py).
    from tracker.filer import ensure

    with nullcontext() if dry_run or lock_held else engagement_lock(engagement_dir):
        # The store is brought up to the journal before a thing is read:
        # the rules this scan works from are the ones the record holds,
        # and recording what it finds needs an engagement the store holds.
        ensure(engagement_dir, root)
        # What the record already says about each row is what this scan
        # compares against: the Received Date it carried forward ("first
        # date all validations passed") and the status a regression is
        # measured from both come from there.
        items = load_manifest(engagement_dir)
        prepared_dir = engagement_dir / PREPARED_DIR_NAME
        cache = ContentCache(engagement_dir)      # the engagement's verdicts, from the store
        pdf_cache = PdfVerdictCache()     # this scan's; a PDF is parsed once, not once per row
        # Each request's files, by their names (decision 168): the one
        # answer the filer, the rename and the app read too.
        identifiers = [i.identifier for i in items]
        assigned = assign_files(prepared_dir, identifiers)

        def belongs_to(identifier: str):
            """Whether a path - there or not - is a place ``identifier``'s
            copies sit: directly in the firm's folder, named for it."""
            return lambda path: (path.parent == prepared_dir
                                 and owner_of(path.name, identifiers) == identifier)

        # The record, read once, for the five things this scan asks of it:
        # which copies a person filed, which paths the record claims, which
        # file is another row's mislaid copy and so nobody's to count
        # (decision 109), and where a step that died half way left one
        # (decision 119), and which requests a consolidated statement filed
        # elsewhere answers (decision 146). The filer's sweep and its recovery decided all of
        # them under the same lock earlier in this pass; the scan reads and
        # acts, and writes no row of its own.
        rows = _the_index(engagement_dir)
        accepted = _filed_by_a_person(engagement_dir, rows, cache)
        claimed = _claimed_paths(engagement_dir, rows)
        excluded = _wandered(engagement_dir, rows)
        interrupted = _interrupted(engagement_dir, rows)
        answered = _answered(engagement_dir, rows, cache)
        updates: dict[str, StatusUpdate] = {}
        unreached = 0
        cache.deadline = deadline         # a miss past it starts no judgment
        for item in items:
            try:
                updates[item.identifier] = _scan_item(
                    item, assigned[item.identifier], cache, today, pdf_cache, accepted=accepted,
                    claimed=claimed, excluded=excluded, interrupted=interrupted,
                    answered=answered.get(identifier_key(item.identifier), ()),
                    mine=belongs_to(item.identifier),
                )
            except OutOfTime:
                unreached = len(items) - len(updates)
                break
            if not dry_run:
                cache.save()      # this request's readings, kept the moment they are made
        cache.deadline = None

        report = ScanReport(
            engagement_dir=engagement_dir,
            items=items,
            updates=updates,
            warnings=_prepared_warnings(prepared_dir, identifiers)
                     + _changed_copy_warnings(claimed, prepared_dir, cache),
            unreached=unreached,
            dry_run=dry_run,
        )
        if dry_run:
            return report

        # Every file in the firm's folder, not only the ones a request
        # claims: a memo dropped here is a parked copy or a stray read
        # again on the next pass, and the verdicts only it referenced
        # forgotten with it (decision 109).
        cache.prune(existing=set(iter_candidate_files(prepared_dir)))
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

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description=f"Scan an engagement's {PREPARED_DIR_NAME}/ tree and record each request's status"
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    parser.add_argument(
        "--dry-run", action="store_true", help="report only; write nothing"
    )
    ns = parser.parse_args()
    # A typed folder is parsed, never trusted: it must be a return's
    # place under the checked clients root (decision 188).
    from tracker import door

    try:
        ns.engagement_dir = door.return_dir(Path(ns.engagement_dir).absolute())
    except ValueError as exc:
        parser.error(str(exc))

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
        print(f"\nREQUEST LIST PROBLEM - nothing was scanned or written:\n  {exc}")
        print("  Fix the request list in the app (the row number is the list's), save, and re-run.")
        raise SystemExit(1) from None
