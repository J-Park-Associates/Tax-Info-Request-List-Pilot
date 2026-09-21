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

**The index** maps one to the other: **one row per original**, where it
went, what it was renamed to, and — when it was not filed — why not. One
original can have more than one working copy: a page that prints two
forms' own names is two documents, and decision 94 files a copy under each
request that asked for one of them. It stays one row all the same — one
client file, one preserved original, one identity in the engagement's
record — with ``prepared_location`` naming the first copy, ``also_filed``
the rest, and the Reason naming the requests. Its Evidence
column carries the *why* behind the verdict: which of the manifest row's
own keywords matched, and where in the document they were said. Catalog
words and file names only, never a word of the client's document, which is
the same line the verdict cache - in the store since decision 107 - draws.

**The index is not a workbook any more** (decision 102). It was a
workbook rewritten whole on every pass, and thirteen readings of the
decision log are the record of what that cost: a sheet sorted with the
header among the data, a renamed tab, a cell typed over, a snapshot that
outlived its workbook, a row lost because the only place it lived was a
file Excel could rewrite. What the index *is* now is
:mod:`tracker.ledger`, the engagement's own append-only record, folded
into :mod:`tracker.store`; :func:`read_index` answers from the store and
:func:`_record` is the one write. One call per decision, one transaction,
nothing deferred, no sidecar, no retry, and no second copy for Excel to
argue with. The migration that once read a legacy folder's index workbook
into the record left with decision 104 (it is set aside outside the tree,
in ``Retired - Excel manifest``); :func:`ensure` is now only the store's
top-up, and a folder that holds no record is nobody's engagement.

**And the request list is in the record too** (decisions 103 and 104):
the rules a pass works from are the ones the app's editor last saved,
read through :func:`tracker.manifest.load_manifest`, and what a person's
filing teaches a request is recorded in the same call as the filing.

Guarantees:

- **Originals are never altered.** Files are moved into ``PBC_DIR_NAME/`` and copied
  from there; nothing is renamed in place, edited, or deleted. Ever.
- **Nothing is guessed.** Routing is :mod:`tracker.router`'s deterministic
  decision; anything ambiguous lands in ``REVIEW_DIR_NAME`` for a person.
- **Re-running is safe.** Every original is recorded by content hash, so a
  file the client drops twice is preserved but filed once.
- **Cloud-only files are left alone** until the sync client has them, so a
  placeholder is never moved as if it were the document.
- **One run at a time.** The engagement lock (:mod:`tracker.locking`, the
  same one the scanner takes) is held while this works, so a scheduled run
  and a click in the desktop app cannot both move the same originals.
  :func:`tracker.runner.run_engagement` holds one across the whole pass and
  says so with ``lock_held``; run alone, this takes its own. Either way it
  is taken before the request list, the record or the drop folder is read,
  so what a run decides from cannot change under it.
- **Wherever the client put it counts.** ``PBC_DIR_NAME/`` is visible to the client
  and the README says "drop it anywhere", so a file that lands straight in
  ``PBC_DIR_NAME/`` is treated as a drop that has already been preserved: it is
  filed and indexed in place, never ignored.
- **A re-send is judged by the earlier row's decision** (decision 111). The
  content hash says *which* row already holds those bytes; what the re-send
  becomes is that row's decision to say. A filed row whose working copy is no
  longer in ``PREPARED_DIR_NAME/`` is filed again rather than dismissed as a
  duplicate - the original was always safe in ``PBC_DIR_NAME/``. A filed row
  whose copy is there, a row still parked for a person, and a row whose copy
  is not where the record put it all make it a duplicate, and the sentence
  says which of the three it is; so does a row that has no working copy at
  all. Bytes a person set aside are the case below.
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
  (``assign_review_file()``) is how the decision is undone. It is a decision
  about one document on one day, never a standing rule that silences that
  document: the same bytes sent again are looked at afresh - routed as any
  drop is, filed where exactly one request now accepts them and parked with a
  working copy of their own where none does - and the row says it was set
  aside before (decision 111).
- **A working copy that is not where the record put it is said, not moved.**
  Every pass proves each working copy the record names against the row's
  own fingerprint and identifies by fingerprint every file under
  ``PREPARED_DIR_NAME/`` the record does not name
  (:func:`_prove_working_copies`). A copy whose bytes turn up at a path no
  row names makes its row ``FILE_MOVED`` - a decision on the document, not
  a status of a request - and a copy dragged back is filed again. Nothing
  moves either way: the fingerprint identifies and a person decides.
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
  needing review with the error, and the record is written whatever
  happens to the files after it. Nothing that was moved into
  ``PBC_DIR_NAME/`` is ever left unrecorded, and nothing a person decided
  is ever forgotten — there is nothing left between the decision and the
  record that a person with Excel open can hold.

The index *row* itself - :class:`tracker.records.IndexEntry`, its column
table and the shape it is stored in - lives in :mod:`tracker.records` since
decision 100; what is here is every reading and writing of the record. The
old names are re-exported below for one release.
"""

from __future__ import annotations

import datetime as dt
import logging
import os
import re
import shutil
import stat
from collections.abc import Sequence
from contextlib import nullcontext
from dataclasses import dataclass, field, replace
from pathlib import Path

from tracker import ledger, store
from tracker.content_check import RETIRED_CACHE_FILENAME, ContentCache
from tracker.locking import engagement_lock
from tracker.manifest import TEMP_SUFFIX, Override, RequestItem, label_for, load_manifest, override_label

# The records themselves live in tracker/records.py (decision 100). The two
# names this module no longer uses are re-exported from here so that every
# `from tracker.filer import ...` still resolves to the same object; they are
# kept for one release; import from tracker.records.
from tracker.records import (
    CANDIDATE_SEP,
    Evidence,  # noqa: F401
    IndexEntry,
    as_pattern,
    entry_from_json,
    entry_to_json,
    format_evidence,
    ledger_key,
    parse_evidence,  # noqa: F401
)
from tracker.router import route_file
from tracker.scaffold import (
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

#: What the index's section is called wherever it is shown - the word a
#: person knows it by and the Status Report's own section heading
#: (:mod:`tracker.view`).
INDEX_HEADING = "Index"
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
#: untouched; what changes is that the draft stops counting it. It says
#: nobody asked for this document *that day*, not that these bytes are
#: settled for ever: the same bytes sent again are routed afresh and the
#: new row names this decision (decision 111). Filing it is how the
#: decision is undone.
NOT_REQUESTED = "Not Requested"
#: A document whose working copy is not where the record put it, and whose
#: bytes a pass found at a path no row names (decision 109). A decision on
#: the document and never a status of a request (the owner's rule,
#: 2026-09-19): what the scanner says about a request is what its folder
#: holds, and "the copy is not where I put it" is a fact about the
#: document. The row keeps its home in ``prepared_location`` and says where
#: the bytes are now in its Reason (:func:`moved_to` reads it back);
#: nothing is moved, and a person decides. A copy dragged back is filed
#: again on the next pass.
FILE_MOVED = "File Moved"

#: What a Duplicate row says, by what the earlier row holding the bytes is.
#: A parked document has a working copy with a name, so saying "already
#: filed" of one told a person on the Index that a document waiting for
#: them had been dealt with.
DUPLICATE_OF_FILED = "identical to {name}; already filed as {copy}"
DUPLICATE_OF_PARKED = "identical to {name}; parked as {copy}"
DUPLICATE_OF_MOVED = "identical to {name}; its working copy {copy} is not where the record put it"
#: And of a row that never got one: the failure row decision 17 writes when
#: a drop could not be filed after it was preserved has no copy to name, and
#: a sentence ending "as" with nothing after it would be the Index's word
#: for a file nobody can find. Chosen by the absence of the name, whatever
#: the row's decision.
DUPLICATE_OF_UNCOPIED = "identical to {name}; that row has no working copy"
#: A re-send of bytes a person set aside: the earlier decision, quoted whole
#: (it carries the date and the note), and the fact. Decision 76 amended.
RESENT_AFTER_SET_ASIDE = "set aside as not requested ({earlier}); the client sent it again"

#: Reason prefix on index rows a person filed from REVIEW_DIR_NAME.
ASSIGNED_BY_PERSON = "assigned by a person"
#: Reason prefix on index rows a person said no request asks for.
DISMISSED_BY_PERSON = "not requested, by a person"
#: Reason prefix on index rows a person sent back to REVIEW_DIR_NAME.
UNFILED_BY_PERSON = "unfiled by a person"

#: The decisions that leave a document waiting in ``REVIEW_DIR_NAME`` for a
#: person, and which a person may therefore act on: one nobody has looked at
#: yet, and one somebody has said no request asks for. A ``FILE_MOVED`` row
#: is deliberately not among them: its copy is somewhere nobody meant it to
#: be, and the answer to that is its own (decision 110's three buttons), so
#: until then the refusal names what the row is and a person puts the file
#: back first.
_PARKED = (NEEDS_REVIEW, NOT_REQUESTED)

#: How candidate identifiers are joined in the Candidates cell. The record
#: owns it now (``records.CANDIDATE_SEP``); this name is kept for one
#: release.
_CANDIDATE_SEP = CANDIDATE_SEP


class FilingError(Exception):
    """A person's filing decision could not be carried out as asked."""


class StaleRowError(FilingError):
    """The row was rewritten after the person last saw it (decision 112).

    A :class:`FilingError` so the API's one ``except`` turns it into the
    sentence the app toasts: the refusal is not a different kind of
    failure, it is the ordinary one with a different cause.
    """


#: What a person is told when the row they acted on is not the row the
#: record now holds: what it is now, and what it says about itself, so the
#: sentence answers "what happened to it" and not only "no". A check, never
#: a lock - nothing is frozen, nothing is held, and looking again is the
#: whole of the remedy.
STALE_ROW = ("{name} is not as you saw it: the record now says {decision} - {reason}; "
             "look again before acting")

#: What a filing records when the person picked a request the evidence did
#: not point at and the evidence pointed somewhere. Decision 84 lets a
#: person file to any row on the engagement; this is the record saying they
#: did so against what was suggested, with the shortlist it overruled.
OVERRODE_SHORTLIST = "overrode the shortlist ({listed})"



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
    (by identifier prefix, so a Document renamed in the editor changes
    nothing), else the canonical name."""
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


#: What a copy that did not come out as the original says. The digests are
#: cut to their first characters: it is a person reading this, and the
#: first few are enough to tell two documents apart.
COPY_MISMATCH = (
    "{source} was copied to {target} and the copy does not hold the original's bytes "
    "({expected} in, {found} out); the copy was removed"
)
_DIGEST_SHOWN = 12


class CopyMismatchError(FilingError):
    """A copy was made and the target did not hold the original's bytes."""


def _remove_a_failed_copy(target: Path) -> None:
    """Take away a copy that is not the document, whatever went wrong."""
    try:
        target.unlink(missing_ok=True)
    except OSError as exc:          # held by a scanner: say so, keep the real error
        log.warning("Half-written %s could not be removed (%s)", target.name, exc)


def _copy_whole(
    source: Path, target: Path, *, expect: str = "", cache: ContentCache | None = None
) -> None:
    """``copy2``, with nothing left behind when it fails half-way, and the
    copy proved against the bytes it was made from.

    A copy that stops part-way (disk full, a virus scanner holding the new
    file) would leave a truncated working copy that the next scan reads as
    a corrupt document and the reminder then asks the client for. The
    original in ``PBC_DIR_NAME/`` is the record; a copy is disposable.

    ``expect`` is the digest the target must hold - the caller always knows
    it, because a copy is only ever made of bytes this system has already
    recorded. A copy that came out as something else is not the document:
    it is removed and :class:`CopyMismatchError` says so, naming both
    files, so the drop is recorded as decision 17's "could not be filed"
    row rather than trusted and counted. A row recorded without its bytes
    (decision 65) has no digest to expect, and passes ``""``: there is
    nothing to prove it against, and that row is said out loud elsewhere.

    ``cache`` is the pass's, where the caller has one: ``copy2`` keeps the
    modification time, so the memo this leaves for the target is the hit
    the next reader gets and the proof costs one read, once.
    """
    try:
        shutil.copy2(source, target)
    except BaseException:
        _remove_a_failed_copy(target)
        raise
    if not expect:
        return
    digest = cache.digest_of(target) if cache is not None else _digest_or_none(target)
    if digest == expect:
        return
    _remove_a_failed_copy(target)
    raise CopyMismatchError(COPY_MISMATCH.format(
        source=source.name, target=target.name,
        expected=expect[:_DIGEST_SHOWN], found=(digest or "")[:_DIGEST_SHOWN] or "nothing",
    ))


def _digest_or_none(path: Path) -> str | None:
    """The file's bytes, or None where they could not be read."""
    try:
        return sha256_of(path)
    except OSError:
        return None


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


def clients_root_of(engagement_dir: Path | str) -> Path:
    """The clients root the store keys this engagement's rows under.

    :func:`tracker.store.root_for` is the rule; this is the name it has
    always had here, kept because the readers in this module and the
    commands that drive them call it. The rule moved down to the store
    with decision 103, because the manifest's own reader needs the same
    answer and may not import this module.
    """
    return store.root_for(engagement_dir)


def read_index(engagement: Path | str) -> list[IndexEntry]:
    """Every index row, oldest first. Empty where nothing is recorded yet.

    **The record answers this, and there is no workbook behind it**
    (decision 102). The rows come from the store's ``documents`` table in
    the index's own order, which is the order
    :func:`tracker.ledger.fold` puts the journal's events in; the store is
    a derivation of the journal and :func:`tracker.store.follow_the_journal`
    makes it one again before every read, building the engagement's rows
    from the journal where the database has none and replaying the lines
    it has not applied where it is behind. That costs one digest of the
    journal file when nothing has happened, which is nearly always.

    So no reader has to know whether anybody prepared this engagement
    first: the pass, the app's state, the triage, the reminder, the
    rollover and the Status Report all come through here and all get the
    same rows.
    """
    folder = Path(engagement)
    conn = store.connect()
    store.follow_the_journal(conn, clients_root_of(folder), folder)
    return [entry_from_json(row) for row in store.documents(conn, folder)]


# ----------------------------------------------------------------- ensure ----


def ensure(engagement_dir: Path | str, root: Path | None = None) -> str:
    """Make the store describe this engagement, and say which of the three
    words it is in (:data:`tracker.records.CURRENT` and its two siblings).

    Run at the start of every pass and by every command that names an
    engagement, before anything reads the index or the request list: an
    engagement the store has never seen is built from its record, and one
    the store is behind on has the lines it has not applied replayed
    (:func:`tracker.store.follow_the_journal`). Nothing is written in the
    engagement folder - the store is the machine's own derivation and
    building it moves nothing of the client's - so a dry run, the Status
    Report and the app showing an engagement another run is holding all
    call it as freely as a pass does. Until decision 104 this is also
    where a folder that still kept facts in a workbook was migrated and
    where the request list was imported; both left with the workbook.
    """
    folder = Path(engagement_dir)
    root = Path(root) if root is not None else clients_root_of(folder)
    conn = store.connect()
    store.follow_the_journal(conn, root, folder)
    return store.state(conn, folder, ledger_head_now=ledger.head(folder))


# ------------------------------------------------------------------ record ----


#: Which event a row's decision is recorded as, when a pass reaches it. The
#: decisions a person makes are recorded under their own names, at the call
#: that makes them, so the record says who decided and not only what.
_LEDGER_EVENT_FOR = {
    FILED: ledger.FILED,
    NEEDS_REVIEW: ledger.PARKED,
    DUPLICATE: ledger.DUPLICATE,
    NOT_REQUESTED: ledger.PARKED,
    FILE_MOVED: ledger.COPY_MOVED,
}


def _ledger_event(name: str, entry: IndexEntry, *, was: str = "") -> dict:
    event = ledger.new(name, **{ledger.KEY_KEY: ledger_key(entry), ledger.ROW_KEY: entry_to_json(entry)})
    if was and was != event[ledger.KEY_KEY]:
        event[ledger.WAS_KEY] = was
    return event


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
        row = entry_to_json(entry)
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


def _record(
    engagement_dir: Path,
    before: dict[str, dict],
    entries: list[IndexEntry],
    *,
    moved: dict[str, str] | None = None,
    decided: dict[str, str] | None = None,
    also: list[dict] | None = None,
) -> None:
    """Write what the index now says and the record does not - in one call.

    **One decision, one call, one transaction.**
    :func:`tracker.store.record` appends every event to the journal, under
    the lock this caller already holds, and then folds them all into the
    store inside a single immediate transaction: either the whole of what
    this call decided is recorded or none of it is. There is no second
    copy to keep in step and nothing to defer, which is the whole of what
    decision 102 took away.

    ``before`` is the engagement's rows as this call found them, which is
    the store's own answer, because that is what :func:`read_index` gave
    the caller. A call that changed nothing writes nothing at all.

    ``also`` is for the events a decision produces that are not index
    rows - today the one keyword a person's filing teaches a request
    (decision 103). They go in this call, not a call of their own,
    because the filing and what it taught are one decision and the
    rollback that puts a moved file back asks exactly that question.
    """
    events = _rows_changed(before, entries, moved or {}, decided or {}) + list(also or [])
    if events:
        store.record(store.connect(), engagement_dir, *events)


def _the_record_holds(engagement_dir: Path, entry: IndexEntry) -> bool:
    """True when the engagement's record already carries ``entry`` as written.

    Asked in the moment after a failed :func:`_record`, to decide whether
    the file this call moved has to go back. A transaction either
    committed or it did not, so the answer is never half a write - and the
    whole row is compared, because an older row for the same original is
    not it.
    """
    try:
        return entry in read_index(engagement_dir)
    except Exception:
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
    """Whether the name can be written into the record at all. NTFS holds
    names as UTF-16 and takes an unpaired surrogate (a truncated emoji, a
    Mac's or a NAS's name in a broken code page); the journal is UTF-8
    JSON and cannot hold it, and such a name once took the whole index
    down, every pass, with the pass's originals moved. That is the one
    refusal left: a control character in a POSIX name files again since
    decision 104, because the refusal of one existed only because a
    workbook is XML, and there is no workbook."""
    try:
        path.name.encode("utf-8")
    except UnicodeEncodeError:
        return False
    return True


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
#: The verdict cache's old file, found in the engagement folder and removed
#: by a real pass (decision 107: the cache lives in the store and nothing
#: reads the file). Said once, on the pass that removed it - on the console,
#: in the app's warnings, and counted on the practice page - one line per
#: file removed; the next pass finds nothing and says nothing.
RETIRED_CACHE_REMOVED = (
    "removed from the engagement folder: the verdict cache lives in the store since "
    "decision 107 and nothing reads the file"
)
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


# ----------------------------------------------------- the working copies ----


#: The moved sentence on a ``FILE_MOVED`` row: the row keeps its home in
#: the Prepared Location column and says here where its bytes are now.
#: Read back by :func:`moved_to`, from this very template.
MOVED_SENTENCE = "{home} no longer holds this row's bytes; they are at {now} (found {date})"
#: The same row when the bytes are nowhere in the firm's folder any more.
#: The original is untouched wherever the client put it, which is the
#: sentence's whole comfort: a working copy is disposable.
MOVED_GONE_SENTENCE = ("{home} no longer holds this row's bytes and nothing under {prepared} does; "
                       "the original is safe in {pbc} (found {date})")
#: The row when its copy is back where the record put it. Appended like the
#: others and never taken off again: a copy that moves twice carries where
#: it has been, which is what the person reading the row wants.
MOVED_BACK_SENTENCE = "the working copy is back at {home} ({date})"
#: Attention, every pass, for a file under a request folder or the review
#: folder that no row names and whose bytes match no row. It is counted
#: where it sits, because what a request holds is what the scanner says it
#: has; what nothing knows is who put it there.
UNRECORDED_COPY = ("{location} is not on the record: nothing filed it there and no row's bytes "
                   "match it; it is counted as it sits - file it in the app, or drop it in the "
                   "client's folder, so the record knows it")

_MOVED_DATE = r"\d{4}-\d{2}-\d{2}"


def _moved_tail(template: str) -> re.Pattern[str]:
    """One of the moved sentences, where a row's Reason ends with it.

    The pattern is derived from the template that wrote the sentence, so
    rewording the sentence moves its reader with it (decision 108's
    precedent, :func:`tracker.records.as_pattern`). ``base`` is greedy, so
    what matches is the *last* such sentence on the row: a copy that has
    moved before carries its history and only the sentence this pass
    replaces comes off.
    """
    return re.compile(
        "^(?P<base>.*); " + as_pattern(
            template, home=r".+?", now=r"(?P<now>.+?)", prepared=r".+?", pbc=r".+?",
            date=_MOVED_DATE,
        ) + "$",
        re.DOTALL,
    )


_MOVED_TAIL = _moved_tail(MOVED_SENTENCE)
_MOVED_GONE_TAIL = _moved_tail(MOVED_GONE_SENTENCE)


def moved_to(entry: IndexEntry) -> str | None:
    """Where this row's working copy is now, or None.

    The row's home stays in ``prepared_location`` - every reader treats
    that column as "where this row's copy belongs", from the re-file rule
    to the app's filed list, and rewriting it to the path somebody dragged
    the copy to would make each of them read a drag as a filing. So where
    the bytes *are* is a sentence on the row, and this is its reader: the
    scanner keeps the wanderer out of the count of whatever request it
    happens to sit in, and the app's answer to it reads the same sentence.
    None for a row that is not ``FILE_MOVED``, and for one whose bytes are
    nowhere in the firm's folder at all.
    """
    if entry.decision != FILE_MOVED:
        return None
    found = _MOVED_TAIL.match(entry.reason)
    return found.group("now") if found else None


def _without_moved_sentence(reason: str) -> str:
    """The Reason without the moved sentence this pass is replacing.

    What a row said before it moved - the routing reason, a person's own
    sentence, whatever it was - is what the next moved sentence is appended
    to, so a row that has been dragged about does not accumulate one
    "no longer holds" after another for the same copy.
    """
    for pattern in (_MOVED_TAIL, _MOVED_GONE_TAIL):
        found = pattern.match(reason)
        if found:
            return found.group("base")
    return reason


def _says_it_is_nowhere(entry: IndexEntry) -> bool:
    """Whether this row already says its bytes are nowhere in the folder."""
    return entry.decision == FILE_MOVED and _MOVED_GONE_TAIL.match(entry.reason) is not None


def _spend_a_stray(strays: dict[str, str], digest: str, preferred: str | None = None) -> str | None:
    """A file no row names holding ``digest``, spent once.

    Once is the whole of it: two rows whose copies were both dragged into
    one folder are two wanderers, and a file that answered for one row is
    not the other's as well.

    ``preferred`` is the wanderer the row already names, and it wins while
    it is still there holding the bytes. A document can be in the firm's
    folder twice over - a copy somebody took before dragging the first, a
    ``(2)`` name, a subfolder - and the one that sorts first is not the one
    a person moved: pointing the row at it would append an event nothing
    happened for, rewrite the sentence to name a file nobody touched, and
    send decision 110's put-it-back after the wrong file. Anything else is
    the first match in the order the walk found them, which is the folder's
    own.
    """
    if not digest:
        return None                  # decision 65: a row without its bytes is nobody's
    if preferred and strays.get(preferred) == digest:
        del strays[preferred]
        return preferred
    for location, found in strays.items():
        if found == digest:
            del strays[location]
            return location
    return None


def _prove_working_copies(
    engagement_dir: Path,
    prepared_dir: Path,
    entries: list[IndexEntry],
    cache: ContentCache,
    stamp: str,
    request_folders: set[Path],
) -> tuple[list[FileError], dict[str, str]]:
    """One walk of the firm's folder: prove every copy the record names,
    identify every file it does not. Mutates ``entries``; returns the
    attention lines and ``{ledger_key: ledger.COPY_MOVED}`` for every row
    it rewrote.

    The client's own folder has been swept since decision 68 and this one
    was swept by nothing at all: a Filed copy dragged out of its request
    folder read Missing and the weekly draft asked the client for a file
    the firm had mislaid, and a copy dragged *into* another request's
    folder was counted there, a filing nobody made. Four answers, and only
    these: a copy where the record put it holding the record's bytes is
    proved and nothing is written; a copy that is not there whose bytes
    turn up at a path no row names makes its row ``FILE_MOVED``; a
    ``FILE_MOVED`` row whose copy is back is what it was before; and a file
    no row names is said, every pass, and counted where it sits.

    **Nothing moves.** The fingerprint identifies and never decides: every
    outcome that is not "proved" ends in a person being told. And nothing
    is written when nothing moved - a quiet pass appends no event, and
    costs stats rather than reads, because every hash here goes through the
    cache's memo.

    A placeholder is never read: hashing one would make the sync client
    download it, so a dehydrated home is "not looked at this pass" rather
    than absent, and a dehydrated file no row names is passed over.
    """
    attention: list[FileError] = []
    swept: dict[str, str] = {}

    # Every location the record claims, and which row claims it. Where two
    # rows name one location the newest wins - the rule the index is read
    # by everywhere else - and the older row's copy there is gone by the
    # index's own word (_copy_taken_by_a_later_row's reading). A row
    # recorded without its bytes claims nothing (decision 65): there is no
    # fingerprint to hold a file to. It still *names* its copy, though, so
    # that copy is not a file nothing on the record knows about - it is a
    # row said out loud by UNTIED_IN_PBC, and one warning per thing.
    named: set[str] = set()
    claims: dict[str, int] = {}
    for position, entry in enumerate(entries):
        named.update(entry.filed_locations)
        if entry.digest:
            for location in entry.filed_locations:
                claims[location] = position
    mine = {
        position: [location for location in entries[position].filed_locations
                   if claims.get(location) == position]
        for position in set(claims.values())
    }

    # Prove each claim, and hash every file no row names once, so the pass
    # after this one stats them and reads nothing.
    failed: dict[int, list[str]] = {}
    proved: dict[int, list[str]] = {}
    for position, locations in mine.items():
        digest = entries[position].digest
        for location in locations:
            path = engagement_dir / location
            if not path.is_file():
                failed.setdefault(position, []).append(location)
            elif is_cloud_placeholder(path):
                continue
            elif cache.digest_of(path) == digest:
                proved.setdefault(position, []).append(location)
            else:
                failed.setdefault(position, []).append(location)
    strays: dict[str, str] = {}
    for path in iter_candidate_files(prepared_dir):
        location = path.relative_to(engagement_dir).as_posix()
        if location in named or is_cloud_placeholder(path):
            continue
        found = cache.digest_of(path)
        if found is not None:        # unreadable now; the next pass looks again
            strays[location] = found

    # Where a row's copy is not, its bytes may be - and where the row
    # already names one, that is the file a person moved and the file
    # decision 110 will put back, whatever else holds the same bytes.
    for position in sorted(failed):
        entry = entries[position]
        if entry.decision == DUPLICATE:
            continue                 # a Duplicate row only points at another row
        home = failed[position][0]
        now = _spend_a_stray(strays, entry.digest, moved_to(entry))
        if now is None and entry.decision != FILE_MOVED:
            continue                 # decision 3's regression says this, as it always has
        if now is not None and moved_to(entry) == now:
            continue                 # the same wanderer as last pass: nothing new to say
        if now is None and _says_it_is_nowhere(entry):
            continue                 # said nowhere already, and it is nowhere still
        sentence = (
            MOVED_SENTENCE.format(home=home, now=now, date=stamp) if now is not None
            else MOVED_GONE_SENTENCE.format(
                home=home, prepared=PREPARED_DIR_NAME,
                pbc=entry.pbc_location or "(none)", date=stamp)
        )
        entries[position] = replace(
            entry, decision=FILE_MOVED,
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
        )
        swept[ledger_key(entries[position])] = ledger.COPY_MOVED
        attention.append(FileError(Path(now or home).name, sentence, True))
        log.warning("The working copy recorded at %s is not there; it is at %s", home, now or "nothing")

    # And a copy somebody dragged back is what it was before it went. Which
    # of the two parked decisions a copy with no request was is not
    # guessable, so a parked one comes back waiting for review and a person
    # says it is not requested again in one click.
    for position in sorted(mine):
        entry = entries[position]
        if entry.decision != FILE_MOVED or position in failed or not proved.get(position):
            continue
        home = proved[position][0]
        sentence = MOVED_BACK_SENTENCE.format(home=home, date=stamp)
        entries[position] = replace(
            entry,
            decision=FILED if entry.identifier else NEEDS_REVIEW,
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
        )
        swept[ledger_key(entries[position])] = ledger.COPY_MOVED
        attention.append(FileError(Path(home).name, sentence, True))
        log.info("The working copy recorded at %s is back", home)

    # What is left is a file nothing filed and no row's bytes answer for.
    # Said every pass until a person routes it through the client's folder
    # or files it in the app. A loose file at the root of the firm's folder
    # and a folder matching no request are the scanner's warnings already,
    # and one warning per thing is the rule.
    watched = set(request_folders) | {prepared_dir / REVIEW_DIR_NAME}
    for location in strays:
        path = engagement_dir / location
        if any(folder == path.parent or folder in path.parents for folder in watched):
            attention.append(FileError(path.name, UNRECORDED_COPY.format(location=location), True))
    return attention, swept


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
    lock_held: bool = False,
) -> FileReport:
    """Sort one engagement's drop folder. Returns what was done.

    A dry run decides everything and moves nothing — use it to preview
    where files would land before letting the scheduled job do it.

    ``lock_held`` says the caller is already holding this engagement's
    lock and this call must not take it again: that is
    :func:`tracker.runner.run_engagement`, which since decision 102 holds
    one lock across the whole pass rather than one per step.

    Every pass also proves the working copies the record names against
    their rows and identifies the files it does not name
    (:func:`_prove_working_copies`, decision 109), whether or not there is
    anything to sort - a copy somebody dragged is the one disagreement
    between the record and the folder nothing used to notice.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()

    shared_dir = engagement_dir / SHARED_DIR_NAME
    pbc_dir = shared_dir / PBC_DIR_NAME
    prepared_dir = engagement_dir / PREPARED_DIR_NAME
    review_dir = prepared_dir / REVIEW_DIR_NAME

    report = FileReport(engagement_dir=engagement_dir, dry_run=dry_run)
    # A sort and a scan must never overlap (see tracker.locking), and the
    # lock comes before anything is read: the manifest, the index and the
    # drop folder are what this run decides from, and a run that finished
    # in between must not be invisible to it. A dry run writes nothing, so
    # it needs no lock and never blocks a real run.
    with nullcontext() if dry_run or lock_held else engagement_lock(engagement_dir):
        # Before anything is read: the store is brought up to the record.
        # A dry run builds the store's own rows and moves nothing of the
        # client's.
        ensure(engagement_dir)
        items = load_manifest(engagement_dir)
        by_id = {i.identifier: i for i in items}
        entries = read_index(engagement_dir)
        # What the record already says, taken before anything in this pass
        # touches a row, so what this pass wrote is what gets recorded.
        before = {ledger_key(entry): entry_to_json(entry) for entry in entries}
        # What the router learns about each document is what the scan will
        # want to know about its working copy (same bytes): the verdicts go
        # into the engagement's verdict cache in the store, keyed by content
        # (decision 107). It is made whether or not there is anything to
        # sort, because the tidy-up at the end of a pass is owed to a pass
        # that sorted nothing too - and because every hash of a file in the
        # firm's folder goes through its memo (decision 109), so an
        # unchanged tree costs stats and not reads.
        cache = ContentCache(engagement_dir)
        # An original preserved by a pass that could not read it back has no
        # digest (decision 65). While it has none, a replacement is never
        # noticed and a person's filing of it is never honoured; a later
        # pass records the bytes where its copy and the original still agree,
        # and says so where they do not.
        _filled, untied = (0, []) if dry_run else _record_missing_digests(engagement_dir, entries)
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
        # Existing request folders, so a Document renamed in the editor
        # keeps filing into the folder that already holds its earlier
        # files - and so the sweep below knows which folders a request
        # claims, the same reading the scanner's warnings are drawn from.
        assigned = assign_folders(prepared_dir, [i.identifier for i in items])
        # Every working copy the record names, proved against the row's own
        # fingerprint, and every file the record does not name, identified
        # by it (decision 109). It runs before the rows below are read, so
        # what follows sees the rows as this sweep leaves them; a dry run
        # reads all of it and records none of it, like everything else.
        sweep, swept = _prove_working_copies(
            engagement_dir, prepared_dir, entries, cache, stamp,
            {folder for folders in assigned.values() for folder in folders},
        )
        report.attention.extend(sweep)
        # The row that holds each document's bytes. A Duplicate row only
        # points at another row; letting it shadow the Filed row would hide
        # a working copy that has since been deleted, and a re-send that
        # answers "Missing" would be called a duplicate for ever (decision
        # 58). Every other decision holds its bytes, a person's
        # ``NOT_REQUESTED`` included - so that a re-send of what somebody
        # set aside is *recognised* as those bytes. What is then done with
        # it is the earlier row's decision to say, in ``_sort_one``, and for
        # a set-aside row that is a fresh look, not a duplicate: decision 76
        # said it once and decision 111 amended it.
        known = {e.digest: e for e in entries if e.digest and e.decision != DUPLICATE}
        # Names claimed during this run, so a dry run previews the same numbering
        # a real run would produce (nothing is on disk to collide with yet).
        reserved: dict[Path, set[str]] = {}
        try:
            if drops or strays:
                if not dry_run:
                    pbc_dir.mkdir(parents=True, exist_ok=True)
                    prepared_dir.mkdir(parents=True, exist_ok=True)
                _sort_all(drops, strays, pbc_dir, entries, stamp, _SortContext(
                    items=items, by_id=by_id, known=known, prepared_dir=prepared_dir,
                    review_dir=review_dir, reserved=reserved, assigned=assigned,
                    dry_run=dry_run, report=report,
                    cache=cache, pdf_cache=PdfVerdictCache(),
                ))
        finally:
            # Whatever happened above, every original that was moved is on
            # record: one call, one transaction, in the same locked section
            # as the moves it records. A pass that changed nothing writes
            # nothing - the diff against what the record already said is
            # what decides, not a count of rows.
            if not dry_run:
                _record(engagement_dir, before, entries, moved=moved_keys, decided=swept)
        # The tidy-up is owed to every pass, not only one that sorted
        # something: an empty folder the client dragged in outlives the
        # files that were in it, and a pass that found nothing to do used
        # to leave it there for ever.
        if not dry_run:
            cache.save()
            for name in _remove_the_retired_cache(engagement_dir):
                report.attention.append(FileError(name, RETIRED_CACHE_REMOVED, False))
            _prune_empty_dirs(shared_dir, keep=pbc_dir)
    return report


def _remove_the_retired_cache(engagement_dir: Path) -> list[str]:
    """Take the verdict cache's old file out of the engagement folder.
    Returns the names removed, for the report to say once.

    Until decision 107 the cache was a JSON file here that every pass
    rewrote; it lives in the store now and **nothing reads the file** -
    the owner's rule is that nothing the machine can derive stays in the
    synced folder, and reading it once would keep its loader alive for a
    release to save one cold pass. So the first real pass after the
    upgrade removes it, and any temp file the atomic write it used to go
    through left beside it (``manifest.temp_path_for`` put the process id
    and a token between the name and ``TEMP_SUFFIX``), and the report says
    so on ``FileReport.attention`` for that one pass, as ``MOVED_IN_PBC``
    is said - on the console, in the app's warnings, and counted on the
    practice page. A dry run leaves it where it is, like everything else.
    """
    leftovers = [engagement_dir / RETIRED_CACHE_FILENAME,
                 *engagement_dir.glob(f"{RETIRED_CACHE_FILENAME}*{TEMP_SUFFIX}")]
    removed: list[str] = []
    for path in leftovers:
        try:
            path.unlink()
        except FileNotFoundError:
            continue
        except OSError as exc:
            log.warning("Could not remove the retired verdict cache file %s: %s", path.name, exc)
            continue
        removed.append(path.name)
    return removed


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


def _working_copy(
    item: RequestItem, drop: Path, pbc_target: Path, digest: str, run: _SortContext
) -> str:
    """Put one working copy of a preserved original in one request's folder,
    and say where it went.

    The copy is made from ``pbc_target`` - the preserved original, never
    the drop - under the canonical name for that row, and a copy already
    there holding these bytes is reused rather than doubled
    (:func:`_existing_copy`: a killed run's). A dry run decides all of it
    and writes nothing, which is why the names claimed are kept in
    ``run.reserved`` rather than read back off the disk.

    One call per request: decision 94 files a page that carries several
    forms under each of them, and each folder numbers its own names.
    """
    dest_folder = request_folder(item, run.assigned, run.prepared_dir)
    if dest_folder not in run.reserved:
        run.reserved[dest_folder] = (
            {p.name.lower() for p in dest_folder.iterdir()}
            if dest_folder.is_dir()
            else set()
        )
    filed_as = prepared_name_for(item, extension_of(drop), run.reserved[dest_folder])
    if not run.dry_run:
        dest_folder.mkdir(parents=True, exist_ok=True)
        existing = _existing_copy(dest_folder, pbc_target, digest)
        if existing is not None:
            filed_as = existing.name
        else:
            _copy_whole(pbc_target, dest_folder / filed_as, expect=digest, cache=run.cache)
    return prepared_location(dest_folder, filed_as)


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
    refiled = resent = ""
    if digest and digest in known:
        # These bytes are already in the record, and the row that holds them
        # says what this drop is: the content hash identifies, the earlier
        # decision decides (decision 111).
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
        elif earlier.decision == NOT_REQUESTED:
            # Somebody said no request asked for this - that day. The client
            # sending it again is a new fact about it, and the request list
            # may have gained the row or the keyword that takes it since, so
            # it is routed below like any other drop and parked only where
            # the router would park it. Either way the row quotes the earlier
            # decision whole - it carries the date and the person's note as
            # ``dismiss_review_file`` wrote them - so the card, the Index and
            # the files-waiting warning all say the client sent it again.
            resent = RESENT_AFTER_SET_ASIDE.format(earlier=earlier.reason)
        else:
            # A filed row with its copy in place, a row still parked for a
            # person, or a row whose copy is not where the record put it
            # (decision 109's, which a second copy would not help anybody
            # resolve): the queue holds a document once, and the sentence
            # names which of the three the earlier row is. A row that has no
            # working copy to name at all - decision 17's failure row - says
            # that instead, whatever its decision, rather than ending on the
            # word "as" with nothing after it.
            words = (
                DUPLICATE_OF_UNCOPIED if not earlier.filed_as else
                {FILED: DUPLICATE_OF_FILED, NEEDS_REVIEW: DUPLICATE_OF_PARKED,
                 FILE_MOVED: DUPLICATE_OF_MOVED}[earlier.decision]
            )
            entry = IndexEntry(
                received=stamp, original_name=drop.name, size_kb=size_kb,
                digest=digest, identifier=earlier.identifier,
                prepared_location="",
                pbc_location=pbc_rel, decision=DUPLICATE,
                reason=words.format(name=earlier.original_name, copy=earlier.filed_as),
            )
            report.duplicates.append(entry)
            return entry

    routing = route_file(
        pbc_target if not dry_run else drop, run.items,
        digest=digest, cache=run.cache, pdf_cache=run.pdf_cache,
    )
    item = run.by_id.get(routing.identifier or "")

    if routing.routed and item is not None:
        # One row per request the router named (decision 94 names more
        # than one where a page carried more than one form), and one
        # working copy per row. The original is preserved once, under its
        # own name, and the index keeps one row for it: the copies are
        # this row's, not rows of their own.
        wanted = [item] + [run.by_id[i] for i in routing.also if i in run.by_id]
        locations = [_working_copy(it, drop, pbc_target, digest, run) for it in wanted]
        entry = IndexEntry(
            received=stamp, original_name=drop.name, size_kb=size_kb,
            digest=digest, identifier=item.identifier,
            prepared_location=locations[0],
            pbc_location=pbc_rel, decision=FILED,
            reason="; ".join(part for part in (routing.reason, refiled, resent) if part),
            candidates=_CANDIDATE_SEP.join(routing.candidates),
            evidence=format_evidence(routing.evidence_record),
            also_filed=_CANDIDATE_SEP.join(locations[1:]),
        )
        report.filed.append(entry)
        return entry

    review_name = drop.name
    if not dry_run:
        run.review_dir.mkdir(parents=True, exist_ok=True)
        # One row, one working copy. The copy already there holding these
        # bytes is the *set-aside* row's, and two rows naming one file would
        # let filing either of them carry the other's copy away, so a re-send
        # of set-aside bytes takes a fresh copy of its own. The person may
        # end with two identical files in review, which is the truthful
        # state: two arrivals, two decisions to make.
        review_target = None if resent else _existing_copy(run.review_dir, pbc_target, digest)
        if review_target is None:
            review_target = _unique_path(run.review_dir, drop.name)
            _copy_whole(pbc_target, review_target, expect=digest, cache=run.cache)
        review_name = review_target.name
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier="",
        prepared_location=prepared_location(run.review_dir, review_name),
        pbc_location=pbc_rel, decision=NEEDS_REVIEW,
        # The flag first: what a person opening the card should read before
        # the router's own reason for parking it.
        reason=f"{resent}; {routing.reason}" if resent else routing.reason,
        candidates=_CANDIDATE_SEP.join(routing.candidates),
        evidence=format_evidence(routing.evidence_record),
    )
    report.review.append(entry)
    return entry


# ------------------------------------------------------------- freshness ----


def _refuse_if_stale(engagement_dir: Path, entry: IndexEntry, seq: int | None) -> None:
    """Refuse when the row is not the one the person acted on (decision 112).

    ``seq`` is the row's own sequence number as the person saw it - the
    journal line that last wrote it, which travelled out with the state
    the card was drawn from and came back with the click. The store's is
    read under the lock the caller already holds, after the row has been
    found and **before any byte is read or any file touched**, so a
    refusal leaves the folder exactly as it was.

    ``None`` is a caller with no view to be stale against - a script, a
    test seeding a folder by hand - and skips the check; the app is
    refused without one by the API, which is the only place that draws the
    card. The by-name refusal every action already makes ("it is Filed
    as ...") is a different question and still asked first: this one
    catches the row that changed and is *still* parked - dismissed while
    the card was open, unfiled and back, a note rewritten.
    """
    if seq is None:
        return
    held = store.document_seqs(store.connect(), engagement_dir).get(ledger_key(entry))
    if held != seq:
        raise StaleRowError(STALE_ROW.format(
            name=entry.original_name, decision=entry.decision, reason=entry.reason))


# ----------------------------------------------------------------- assign ----


@dataclass(frozen=True, slots=True)
class AssignResult:
    """What filing one parked document by hand did."""

    entry: IndexEntry            # the rewritten index row
    moved_review_copy: bool      # True: the parked copy (REVIEW_DIR_NAME) became the working copy
    keyword: str = ""            # keyword added to the row's Any Keywords, if any
    keyword_note: str = ""       # why it was not added, when it was not
    left_in_review: str = ""     # a parked copy that no longer held the row's bytes, and stayed
    overrode_shortlist: str = ""  # the sentence written when the pick was off the shortlist


def assign_review_file(
    engagement_dir: Path | str,
    original: str,
    identifier: str,
    *,
    keyword: str = "",
    today: dt.date | None = None,
    seq: int | None = None,
    shortlist: Sequence[str] | None = None,
) -> AssignResult:
    """File a parked document under a request, the way the filer would have.

    ``original`` is the index row to act on: its PBC location
    (``SHARED_DIR_NAME/PBC_DIR_NAME/<original name>``) or, failing that, its original name among
    the rows still marked Needs Review. The working copy is created under the
    canonical name in the request's folder - moved from ``REVIEW_DIR_NAME`` when it is still there, copied from ``PBC_DIR_NAME/`` when it is not -
    and the index row is rewritten as Filed with the decision attributed to
    a person. The original in ``PBC_DIR_NAME/`` is not touched.

    ``keyword`` is optional: recorded against the request so the next
    document like this one routes itself, and laid over the row's typed
    Any Keywords by every reader (``manifest.load_manifest``). It is
    recorded, never typed into the row (decision 103): the one note left
    is that the request already had the word.

    ``seq`` is the row's sequence number as the person saw it and ``shortlist``
    the identifiers the evidence pointed at when they were shown the card,
    both from the caller that drew it (decision 112). A ``seq`` that is not
    the record's refuses before a byte is read (:func:`_refuse_if_stale`); a
    pick that is not on a **non-empty** shortlist is recorded on the row as
    the person's override, with the identifiers it overruled. Neither is
    computed here: the shortlist is :mod:`tracker.review`'s answer and this
    module does not import it, so the caller that shows the suggestions is
    the caller that says what was overruled. A caller with no view - a
    script, a test - passes neither and is checked against nothing.

    The rules the filer lives by still hold: nothing is guessed (the person
    chose), the engagement lock is held, and the row, the move and the
    keyword are recorded in one transaction.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    prepared_dir = engagement_dir / PREPARED_DIR_NAME

    # Everything - the request list, the row, the keyword recorded - under
    # the one lock, so a scheduled pass cannot slip in between.
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        items = {i.identifier: i for i in load_manifest(engagement_dir)}
        item = items.get(identifier)
        if item is None:
            raise FilingError(f"no request {identifier!r} in the request list")
        if item.manual_override == Override.NOT_APPLICABLE:
            # A row a person set aside does not take a filing: the person
            # clears the override in the editor and files, or leaves it.
            raise FilingError(f"{identifier} is {override_label(item)}; clear the override first")

        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_parked(entries, original)
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
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
            _copy_whole(source, target, expect=digest)

        # A pick the evidence did not point at, when the evidence pointed
        # somewhere, is the person overruling the shortlist, and the row
        # says so in words (decision 112). An empty shortlist is never an
        # override: with nothing suggested there is nothing to overrule
        # (decision 83's "no need prior"). ASSIGNED_BY_PERSON stays the
        # prefix either way - the scanner honours a person's filing by
        # what the reason starts with.
        overrode = (OVERRODE_SHORTLIST.format(listed=", ".join(shortlist))
                    if shortlist and identifier not in shortlist else "")
        attributed = f"{ASSIGNED_BY_PERSON} on {today.isoformat()}"
        if overrode:
            attributed = f"{attributed}; {overrode}"
        new_entry = replace(
            entry,
            digest=digest,
            size_kb=size_kb,
            identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            decision=FILED,
            reason=f"{attributed}; was: {entry.reason}",
            candidates="",
        )
        entries[position] = new_entry
        # The keyword travels with the filing, in the same call and so in
        # the same transaction: a filing that teaches a keyword is one
        # decision, and the rollback below asks whether that decision
        # landed, not whether half of it did. It is recorded, never typed
        # into the row, and load_manifest() lays the taught keywords over
        # the typed ones.
        keyword = keyword.strip()
        note = ""
        if keyword and keyword.lower() in {k.lower() for k in item.any_keywords}:
            note = f"{identifier} already had the keyword {keyword!r}"
        taught = [] if note or not keyword else [ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: item.identifier, ledger.KEYWORD_KEY: keyword,
        })]
        try:
            _record(engagement_dir, before, entries,
                    decided={ledger_key(new_entry): ledger.ASSIGNED_BY_PERSON},
                    also=taught)
        except BaseException:
            # The record either took the decision or it did not - one
            # transaction, no third state - so the file goes back where the
            # record says it is, and a retry files it once rather than
            # copying it twice. A killed attempt's copy that stood in for
            # the parked one leaves the row still naming a parked copy that
            # is no longer there, so it is put back from the copy that
            # stood in for it, which is it byte for byte.
            if not _the_record_holds(engagement_dir, new_entry):
                try:
                    if moved:
                        _move_whole(target, parked)
                    elif parked_stood_in:
                        _copy_whole(target, parked, expect=digest)
                    elif not reused:          # a copy that was already there stays
                        target.unlink(missing_ok=True)
                except (OSError, FilingError) as undo:  # the copy stays where it is; the real error is the one to hear
                    log.error("Could not put %s back after the record refused it: %s", target.name, undo)
            raise
    return AssignResult(
        entry=new_entry, moved_review_copy=moved, keyword=keyword if not note else "",
        keyword_note=note, left_in_review=left_in_review, overrode_shortlist=overrode,
    )


def find_parked(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest parked row wins a name.

    A row a person has already said is ``NOT_REQUESTED`` is parked too: its
    working copy is still in ``REVIEW_DIR_NAME``, nothing was moved, and
    filing it is how that decision is undone. Only the two parked decisions
    are a person's to act on; anything else names itself in the refusal.

    Public since decision 112, because the caller that draws the card has
    to find the same row this module will act on to say what the evidence
    pointed at; the underscored name is kept for one release.
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


#: The name this lookup had while it was the filer's alone; kept for one
#: release, as the module does elsewhere.
_find_parked = find_parked


# ---------------------------------------------------------- not requested ----


def _said(note: str) -> str:
    """A person's note, in the one shape a rewritten Reason carries it."""
    note = note.strip()
    return f" ({note})" if note else ""


@dataclass(frozen=True, slots=True)
class DismissResult:
    """What saying one parked document is not requested did."""

    entry: IndexEntry            # the rewritten index row


def dismiss_review_file(
    engagement_dir: Path | str,
    original: str,
    note: str = "",
    *,
    today: dt.date | None = None,
    seq: int | None = None,
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
    somebody has already looked at, and the same bytes sent again come back
    for a fresh look, naming this decision (decision 111): it is a decision
    about one document on one day, not a standing rule that silences that
    document for the rest of the engagement.

    Because nothing moves, nothing is checked against the bytes: this is a
    statement about the request list, not about the file. The engagement lock
    is held and the row is recorded in one transaction, as everywhere else.

    ``seq`` is the row's sequence number as the person saw it (decision
    112): a row rewritten since is refused by name before anything is
    written, and a caller with no view passes none.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_parked(entries, original)
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        new_entry = replace(
            entry,
            decision=NOT_REQUESTED,
            reason=f"{DISMISSED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}",
        )
        entries[position] = new_entry
        # Nothing was moved, so there is nothing to put back: a record that
        # refuses the decision leaves the folder as it was and the row as
        # the record still has it.
        _record(engagement_dir, before, entries,
                decided={ledger_key(new_entry): ledger.DISMISSED_BY_PERSON})
    return DismissResult(entry=new_entry)


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
#: What an unfiling says when the re-scan did not happen. The row is
#: rewritten and the file is back in review either way; it is the request's
#: status that waits. There is one reason left - another run holds the
#: engagement - because since decision 103 no scan writes anything but
#: the record.
RESCAN_REFUSED = "the status was not put back now ({why}); the next pass does it"


@dataclass(frozen=True, slots=True)
class UnfileResult:
    """What taking one filed document back for review did."""

    entry: IndexEntry            # the rewritten index row
    moved_working_copy: bool     # True: the working copy itself went back to REVIEW_DIR_NAME
    left_filed: str = ""         # a working copy that was not the row's bytes, and stayed
    scan_note: str = ""          # why the re-scan did not land, when it did not


def unfile_document(
    engagement_dir: Path | str,
    original: str,
    note: str = "",
    *,
    today: dt.date | None = None,
    seq: int | None = None,
) -> UnfileResult:
    """Take one filed document back to ``REVIEW_DIR_NAME``, on the record.

    ``original`` names the index row the way :func:`assign_review_file` takes
    it: its PBC location, or failing that its original name among the rows
    the index says are ``FILED`` - whether a pass filed it or a person did.

    The working copy goes back under the client's own name, the name a parked
    copy has always had, and the row is rewritten ``NEEDS_REVIEW`` with no
    identifier, the reason attributed to a person and what the row said
    before kept after it. A page decision 94 filed under several requests
    has a copy in each and **every one of them leaves its request folder**:
    one goes back to ``REVIEW_DIR_NAME`` under the client's name and the
    rest, being those same bytes again, stand down. Then the engagement is re-scanned, so the request
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

    ``seq`` is the row's sequence number as the person saw it (decision
    112). A row somebody re-filed between the card being drawn and the
    click is a newer filing, and unfiling it would undo a decision this
    person never saw; the refusal names what the record now says and
    nothing is moved. A caller with no view passes none.

    The engagement lock is held for the move and the row, as everywhere else;
    the re-scan takes it again on its own, exactly as the app's filing does.
    Every copy this makes is proved against the bytes the row recorded
    before it is trusted (decision 109) - except on a row recorded without
    them (decision 65), which has no bytes to be proved against and is said
    out loud by the pass instead.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_filed(entries, original)
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        source = engagement_dir / entry.pbc_location
        # Every working copy this row has: one, or one per request where
        # decision 94 filed the page under several. A copy is only this
        # row's while it is here, hydrated, not claimed by a later row,
        # and still the bytes the row recorded. Any other file at that
        # path is somebody else's document and is not carried back to
        # review under this row's name. The path check is the first copy's
        # (the index's own column is what a later row can take); for the
        # rest the bytes are the whole test, and they are the stronger one.
        taken = _copy_taken_by_a_later_row(entries, position)
        mine: list[Path] = []
        strangers: list[str] = []
        for position_in_row, location in enumerate(entry.filed_locations):
            copy = engagement_dir / location
            if not copy.is_file() or is_cloud_placeholder(copy):
                continue
            if position_in_row == 0 and taken:
                continue
            if entry.digest and sha256_of(copy) == entry.digest:
                mine.append(copy)
            else:
                strangers.append(location)
        working = mine[0] if mine else None
        still_the_rows = working is not None
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
        left_filed = "; ".join(
            LEFT_FILED.format(location=location, parked=parked.name) for location in strangers
        )
        stood_down: list[Path] = []
        if still_the_rows:
            _move_whole(working, parked)      # keeps any notes a person made on it
            # A page decision 94 filed under several requests has a copy in
            # each, and every one of them has to leave its request folder or
            # the scan goes on counting the document this row no longer
            # claims. One goes back under the client's name; the rest are
            # these same bytes over again, and a copy is disposable - the
            # original in PBC_DIR_NAME/ is the record, and the copy that
            # went back is byte for byte the one removed here.
            for copy in mine[1:]:
                copy.unlink()
                stood_down.append(copy)
        else:
            _copy_whole(source, parked, expect=entry.digest)

        new_entry = replace(
            entry,
            identifier="",
            prepared_location=prepared_location(review_dir, parked.name),
            decision=NEEDS_REVIEW,
            reason=f"{UNFILED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}",
            also_filed="",
        )
        entries[position] = new_entry
        try:
            _record(engagement_dir, before, entries,
                    decided={ledger_key(new_entry): ledger.UNFILED_BY_PERSON})
        except BaseException:
            # The same rule as filing: leave the file where the record says
            # it is, so a retry does this once rather than twice.
            if not _the_record_holds(engagement_dir, new_entry):
                try:
                    if still_the_rows:
                        _move_whole(parked, working)
                    else:
                        parked.unlink(missing_ok=True)
                    # The copies that stood down with it come back from the
                    # one that went back, which is them byte for byte.
                    for copy in stood_down:
                        _copy_whole(working or source, copy, expect=entry.digest)
                except (OSError, FilingError) as undo:
                    log.error("Could not put %s back after the record refused it: %s", parked.name, undo)
            raise

    # Outside the lock: the scan takes it for itself. A pass that slips in
    # between reads the rows this one has already recorded, so it sees the
    # document in review, as this scan will.
    return UnfileResult(
        entry=new_entry, moved_working_copy=still_the_rows, left_filed=left_filed,
        scan_note=_rescan(engagement_dir, today),
    )


def _rescan(engagement_dir: Path, today: dt.date) -> str:
    """Put the request's status back now, and say so if it could not be."""
    # The scan reads the index this module writes and this module asks for
    # the scan: the cycle is deliberate and is imported where it is used, so
    # neither module has to exist before the other at import time.
    from tracker.scanner import ScanLockedError, scan_engagement

    try:
        scan_engagement(engagement_dir, today=today)
    except ScanLockedError as exc:
        return RESCAN_REFUSED.format(why=exc)
    return ""


def find_filed(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest ``FILED`` row wins a name.

    :func:`find_parked`'s shape over the other decision: what a person may
    unfile is what the index says is filed, whoever filed it. A row that is
    anything else names what it is in the refusal, because the answer to
    "this is in the wrong place" is different for each of them.

    Public since decision 112, beside :func:`find_parked`; the underscored
    name is kept for one release.
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


#: The name this lookup had while it was the filer's alone; kept for one
#: release, as the module does elsewhere.
_find_filed = find_filed


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description=f"Sort the client's drop folder into {PBC_DIR_NAME}/ and {PREPARED_DIR_NAME}/"
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
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
        print(f"\n  Recorded in {ledger.LEDGER_FILENAME} and the store")
    if result.errors:
        raise SystemExit(1)
