"""Sort the client's drop folder into a working set (component 7).

The client sees one folder and drops everything into it. This module turns
that pile into two things:

The year's folder, in the tree a client is shared
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

- **Originals are never altered.** Files are moved into the year's folder and copied
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
- **Wherever the client put it counts.** The year's folder is visible to the client
  and the README says "drop it anywhere", so a file that lands straight in
  the year's folder is treated as a drop that has already been preserved: it is
  filed and indexed in place, never ignored.
- **A re-send is judged by the earlier row's decision** (decision 111). The
  content hash says *which* row already holds those bytes; what the re-send
  becomes is that row's decision to say. A filed row whose working copy is no
  longer in ``PREPARED_DIR_NAME/`` is filed again rather than dismissed as a
  duplicate - the original was always safe in the year's folder. A filed row
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
- **A person puts a moved copy back, keeps it, or sends it to review - on
  the record.** ``restore_working_copy()`` returns the bytes to where the
  record put them; ``assign_review_file()`` files the wanderer where it now
  sits (or under another request the person picks); ``unfile_document()``
  sends it back to ``REVIEW_DIR_NAME``. Each is one event of the person's
  own, each checks the row's sequence number first and every byte it is
  about to move second, and a home holding a different file is never
  overwritten - that file stays and this document's copy goes to review.
- **An interrupted move is finished from the record, never guessed**
  (decision 119). Before the first file operation of any decision - a
  pass's copy, a person's filing, unfiling or put-back - what it is about
  to do is written down: the operations in order with the bytes each
  expects, the row it will record, the event that will complete it and who
  decided. A run killed in between is finished at the start of the next
  pass (:func:`_finish_interrupted_moves`), by bytes, before anything else
  looks - and the row is recorded as the intent said, a person's as theirs
  and dated their day. **The fingerprint identifies; the record decides:**
  where a destination holds a different file nothing there is touched, the
  row parks and says so; where the bytes are at neither end the row parks
  and says that. A person's action refuses while a move is open here, and
  the next pass - or Run now - clears it.
- **An original that leaves the client's own folder is said out loud.**
  The year's folder is the provided-by-client record and the client can see
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
  the year's folder is ever left unrecorded, and nothing a person decided
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
from dataclasses import dataclass, field, replace
from pathlib import Path

from tracker import ledger, reasons, store
from tracker.content_check import RETIRED_CACHE_FILENAME, ContentCache
from tracker.fsio import TEMP_SUFFIX
from tracker.layout import (
    MAX_PATH_LENGTH,
    PATH_TOO_LONG,
    deepest_path_length,
    household_name_of,
    inbox_of,
    locate,
    location_of,
    originals_of,
    year_of,
)
from tracker.layout import (
    label_for as label_for_return,
)
from tracker.locking import engagement_lock, lock_is_held
from tracker.manifest import (
    ANY_EXTENSION,
    DEFAULT_EXTENSIONS,
    ManifestError,
    Override,
    RequestItem,
    label_for,
    load_engagement_info,
    load_manifest,
    override_label,
)
from tracker.names import (
    NAME_CONFIRMED,
    NAME_VETOED,
    ONE_WORD_SPELLING,
    NameVerdict,
    check_name,
)

# The records themselves live in tracker/records.py (decision 100). The two
# names this module no longer uses are re-exported from here so that every
# `from tracker.filer import ...` still resolves to the same object; they are
# kept for one release; import from tracker.records.
from tracker.records import (
    CANDIDATE_SEP,
    RULE_NAME,
    EngagementInfo,
    Evidence,
    IndexEntry,
    Person,
    as_pattern,
    entry_from_json,
    entry_to_json,
    format_evidence,
    is_a_spelling,
    ledger_key,
    name_words,
    parse_evidence,  # noqa: F401
    person_to_json,
)
from tracker.router import read_once, route_file
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
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
#: client sent is ever deleted) and the original in the year's folder is
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
#: be, and the answer to that is its own (decision 110's three buttons),
#: which the two lookups take as ``accepting`` from the action that offers
#: them - keep it here and send it to review - and which ``dismiss`` does
#: not, because setting a request aside says nothing about a file nobody
#: can find (decision 76).
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
    left_in_place: bool   # True: untouched in the inbox, retried next run


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


def refuse_a_path_past_the_limit(engagement_dir: Path, items: Sequence[RequestItem]) -> None:
    """Refuse a return whose deepest working copy would not fit in a path
    Windows will open.

    The deepest thing the tracker ever writes under a return is a working
    copy this module writes: ``PREPARED_DIR_NAME/<request folder>/<canonical
    name>``, over every active row of the list the call is about to record
    and the longest extension each row allows. The client's own file names
    are not measured - they are the client's, and :func:`unreachable_drops`
    already says a name the index cannot hold - and neither are the ``..``
    locations that cross the trees, because Windows normalises them away
    before the limit applies and :func:`tracker.layout.locate` normalises
    them first too.

    Decision 125 put this refusal on creation; decision 126 gave the
    household rollover the same one, and it lives here rather than in
    ``tracker.api`` because a rollover at layer 3 cannot reach the API at
    layer 5 - and because the file it measures is the one this module
    writes.
    """
    subpaths = []
    for item in items:
        if getattr(item, "manual_override", "") == Override.NOT_APPLICABLE:
            continue
        extensions = [e for e in (item.allowed_extensions or DEFAULT_EXTENSIONS)
                      if e and e != ANY_EXTENSION] or list(DEFAULT_EXTENSIONS)
        longest = max(extensions, key=len)
        name = prepared_name_for(item, longest, set())
        subpaths.append(f"{PREPARED_DIR_NAME}/{folder_name_for(item)}/{name}")
    length = deepest_path_length(engagement_dir, subpaths)
    if length > MAX_PATH_LENGTH:
        raise ManifestError(PATH_TOO_LONG.format(
            folder=engagement_dir, length=length, limit=MAX_PATH_LENGTH))


def request_folder(item: RequestItem, assigned: dict[str, list[Path]], prepared_dir: Path) -> Path:
    """The folder a request's working copies go in: the one it already has
    (by identifier prefix, so a Document renamed in the editor changes
    nothing), else the canonical name."""
    existing = assigned.get(item.identifier) or []
    return existing[0] if existing else prepared_dir / folder_name_for(item)


def _existing_copy(
    folder: Path, original: Path, digest: str, *, ignore: Path | None = None
) -> Path | None:
    """A file already in ``folder`` holding ``original``'s bytes, or None.

    A run that was killed after copying a working copy but before the
    index recorded it (Task Scheduler's limit, the app's timeout, a power
    cut) leaves the copy behind with no row naming it. The next run sees
    the original as unrecorded and would copy it again as ``(2)``; the
    copy that is already there is reused instead. Sizes are compared
    first, so only a same-sized neighbour is hashed.

    ``ignore`` is the copy the caller is about to move, where the caller
    knows of one. It matters for exactly one case, and that case is
    decision 110's keep-it-here: the wanderer sits *in* the folder it is
    being filed into, and without this it would answer as its own earlier
    attempt - reused under the name a person dragged it in with and then
    removed as the copy it stood in for.
    """
    if not folder.is_dir():
        return None
    try:
        size = original.stat().st_size
    except OSError:
        return None
    for candidate in sorted(folder.iterdir()):
        if is_cloud_placeholder(candidate) or (ignore is not None and candidate == ignore):
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
    original in the year's folder is the record; a copy is disposable.

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


# ------------------------------------------------------------------ intent ----

#: What a person is told while a run that was interrupted here has a move
#: still open. The next pass finishes it from the record, and the app's own
#: Run now is a pass, so the remedy is one click and needs no explaining of
#: what a half-made move is.
OPEN_INTENT_REFUSAL = ("a run was interrupted here; the next pass finishes it first "
                       "(or press Run now)")


def _op(engagement_dir: Path, kind: str, source: Path,
        target: Path | None = None, digest: str = "") -> dict:
    """One file operation of a decision, as the record carries it.

    Paths relative to the engagement folder and POSIX, as every path the
    record holds is, so an intent written on one machine reads on another;
    the digest is what the bytes are expected to be at both ends, which is
    the whole of how a recovery tells a step that happened from one that
    did not.
    """
    op = {ledger.OP_KEY: kind, ledger.FROM_KEY: location_of(engagement_dir, source),
          ledger.DIGEST_KEY: digest}
    if target is not None:
        op[ledger.TO_KEY] = location_of(engagement_dir, target)
    return op


def _do_op(engagement_dir: Path, op: dict, *, cache: ContentCache | None = None) -> None:
    """Carry out one operation of an intent.

    The one place the plan an intent wrote down and the work it stands for
    meet: the pass and the person's actions hand their operations here, and
    so does the recovery that finishes them, so a move a recovery makes is
    the move the decision would have made and not a second implementation
    of it. A copy is proved against the digest the intent recorded
    (decision 109); a move is a rename and nothing else (the caller has
    checked the destination by bytes).
    """
    kind = op[ledger.OP_KEY]
    source = locate(engagement_dir, op[ledger.FROM_KEY])
    if kind == ledger.OP_REMOVE:
        source.unlink(missing_ok=True)
        return
    target = locate(engagement_dir, op[ledger.TO_KEY])
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == ledger.OP_MOVE:
        _move_whole(source, target)
    else:
        _copy_whole(source, target, expect=op.get(ledger.DIGEST_KEY, ""), cache=cache)


def _intend(
    engagement_dir: Path,
    key: str,
    ops: list[dict],
    *,
    by: str,
    row: dict | None = None,
    then: str = "",
    also: list[dict] | None = None,
) -> None:
    """Write down what this decision is about to do, before it does it.

    **The intent is the decision** (decision 119). The record was already
    all-or-nothing and the disk was already atomic step by step; what sat
    between them was a run killed after a file had moved and before the
    row that explains it was written. So the operations go down first,
    keyed by the row's own identity, with the row the decision will record
    and the event that will complete it - and the next pass finishes from
    the record what the fingerprints say is still undone.

    Its own call, before the operations, which is the one place decision
    102's "one decision, one call, one transaction" is deliberately two:
    the second call is the decision's existing one, and it closes this.
    A decision that moves nothing writes none of this - there is nothing to
    finish - which is why ``dismiss`` never appears here.

    **Every intent carries a row** since decision 125. A pass's move of a
    drop out of the inbox wrote one without one until then; that intent is
    retired with the inbox it belonged to - it belonged to the one
    engagement whose folder the inbox was in, and the inbox is the
    household's now - and what it bought is stated where it went: a drop a
    killed run had already moved is sorted as a stray on the next pass,
    dated that day.
    """
    if not ops:
        return
    event = ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: key, ledger.OPS_KEY: ops, ledger.DECIDED_BY_KEY: by,
    })
    if row is not None:
        event[ledger.ROW_KEY] = row
    if then:
        event[ledger.EVENT_KEY_AFTER] = then
    if also:
        event[ledger.ALSO_KEY] = list(also)
    store.record(store.connect(), engagement_dir, event)


def _abandon(engagement_dir: Path, key: str) -> None:
    """Say the move this key had open is not to be finished forward.

    Written by the rollback on a *refused* record, which puts the files
    back: without it the next pass would finish a move the record would
    not take. A refusal is not a crash, and this is how the two are told
    apart. Best effort by design - the append can itself fail, and the
    answer to that is in the recovery: the intent stays open, the next
    pass finishes the move forward and records the row the intent carried,
    which is the row the person decided.
    """
    try:
        store.record(store.connect(), engagement_dir, ledger.new(
            ledger.MOVE_ABANDONED, **{ledger.KEY_KEY: key}))
    except Exception as exc:          # the real error is the one the caller is raising
        log.error("Could not record that the move of %s was abandoned: %s", key, exc)


def _refuse_if_a_move_is_open(engagement_dir: Path) -> None:
    """Refuse a person's action while a run that was interrupted here has
    a move still open (decision 119).

    Asked before the row is found and so before 112's freshness check: the
    record is in the middle of a decision about this folder, and a click
    made on what the app last drew is a click made on a row that may be
    about to be rewritten by the recovery. Finishing the move is a pass's
    work, the pass runs it first thing, and the app's Run now is a pass -
    which is simpler and safer than five recovery paths, one per action.
    """
    if store.open_intents(store.connect(), engagement_dir):
        raise FilingError(OPEN_INTENT_REFUSAL)


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


def iter_drops(inbox: Path) -> list[Path]:
    """Client-dropped files awaiting sorting.

    Everything in the household's inbox except the generated README and
    OS/sync junk. Subfolders are included — a client who drags a whole
    folder in still gets it sorted. Since decision 125 the originals rest
    in the year's folder in the client tree, not inside this one, so there
    is nothing here to exclude but the note the firm wrote.
    """
    if not inbox.is_dir():
        return []
    drops = []
    for path in sorted(inbox.rglob("*")):
        if not path.is_file() or is_ignored(path) or _through_a_link(path, inbox) or not _storable(path):
            continue
        if path == inbox / README_NAME:
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


def unreachable_drops(inbox: Path) -> list[Path]:
    """Names in the inbox that are listed but cannot be handled under that
    name: on Windows a name ending in a dot or a space, or a device name
    (``nul``), which a Mac or a sync client can deliver; anywhere, a name
    the index cannot hold (``_storable``). Reported, so a document that can
    never be sorted is not a silence."""
    if not inbox.is_dir():
        return []
    return sorted(
        path for path in inbox.rglob("*")
        if not _storable(path)
        or (not path.is_file() and not path.is_dir() and not _is_link(path))
    )


def unlistable_folders(inbox: Path) -> list[Path]:
    """Folders in the inbox the run cannot list (an ACL that denies the
    run's account; a folder moved in from elsewhere keeps its own).
    ``rglob`` passes over them without a word, and every document inside
    would be invisible to every list; these are reported instead."""
    if not inbox.is_dir():
        return []
    failed: list[Path] = []

    def onerror(exc: OSError) -> None:
        if exc.filename:
            failed.append(Path(exc.filename))

    # The same ground the other walks cover: not behind a link (os.walk
    # descends a junction), not a sync client's staging folder.
    for folder, subfolders, _files in os.walk(inbox, onerror=onerror):
        subfolders[:] = [
            name for name in subfolders
            if not _is_link(Path(folder) / name) and not is_sync_staging(name)
        ]
    return sorted(failed)


def unfinished_drops(inbox: Path) -> list[Path]:
    """Files in the inbox named as a transfer still in progress
    (``UNFINISHED_SUFFIXES``): left alone until it finishes, and named in
    the report, so one that never finishes is not a silence."""
    if not inbox.is_dir():
        return []
    return sorted(
        path for path in inbox.rglob("*")
        if path.is_file() and path.name.lower().endswith(UNFINISHED_SUFFIXES)
        and not any(is_sync_staging(part) for part in path.parts)
    )


def unrecorded_in_pbc(
    originals_dir: Path, engagements: Sequence[tuple[Path, list[IndexEntry]]]
) -> list[Path]:
    """Files in the year's folder of originals that no row of any return in
    the household accounts for.

    The client can see that folder and has been told to drop things
    anywhere, so some will land there. They are already where an original
    belongs; they just have not been filed or recorded yet.

    **Against the union** (decision 125). One folder of originals serves
    every return of the household-year, and each row names its original
    relative to its own return, so a file one return's row holds must
    never look like another return's stray. Each return's rows are located
    from that return and what is left over is a stray for the household -
    sorted like a drop, where it lies, exactly as decision 23 has always
    sorted one.
    """
    recorded = {
        locate(engagement_dir, entry.pbc_location)
        for engagement_dir, entries in engagements
        for entry in entries if entry.pbc_location
    }
    return [
        path for path in iter_candidate_files(originals_dir)
        if path not in recorded
        and not _through_a_link(path, originals_dir) and _storable(path)
    ]


#: The sentence a replaced original gets. It is a file error, not a new
#: drop: the working copy was made from bytes that are gone, and which of
#: the two the client meant is not the filer's to guess.
REPLACED_IN_PBC = (
    "{location} no longer holds the bytes recorded on {received}; its working copy "
    "{prepared} was made from the earlier file - a person should look"
)


def replaced_in_pbc(
    originals_dir: Path, engagement_dir: Path, entries: list[IndexEntry]
) -> list[tuple[Path, IndexEntry]]:
    """Recorded originals in the year's folder whose bytes no longer match
    their row.

    The client can see the folder and Explorer offers "Replace", so a
    corrected document can land over the one already filed. Matching on
    the path alone would call that file recorded and never look at it
    again, while the working copy under ``PREPARED_DIR_NAME`` stayed the
    old one. A same-size edit (one number in a CSV) with a preserved
    modification time is the common shape of it, so nothing but the bytes
    decides: the size first, then the digest. A cloud placeholder is not
    read - hashing it would download it - and is looked at when it is back.

    Per return over that return's own rows: the folder is the household's,
    and a file another return's row holds is that return's to answer for.
    """
    by_path: dict[Path, IndexEntry] = {}
    for entry in entries:            # the newest row for a location wins
        if entry.pbc_location and entry.digest:
            by_path[locate(engagement_dir, entry.pbc_location)] = entry
    replaced = []
    for path in iter_candidate_files(originals_dir):
        if _through_a_link(path, originals_dir):
            continue
        entry = by_path.get(path)
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


#: The sentence a recorded original that has left the year's folder gets. The
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
#: The sentence a row whose original turned up elsewhere in the year's folder
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
    return [position for location, position in newest.items() if _absent(locate(engagement_dir, location))]


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
    """Point the rows of originals the client moved inside the year's folder at
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
            pbc_location=location_of(engagement_dir, path),
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
    in the year's folder still agree. The original alone is no evidence
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
        copy = locate(engagement_dir, entry.prepared_location)
        original = locate(engagement_dir, entry.pbc_location)
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
            path = locate(engagement_dir, location)
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
        location = location_of(engagement_dir, path)
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
        path = locate(engagement_dir, location)
        if any(folder == path.parent or folder in path.parents for folder in watched):
            attention.append(FileError(path.name, UNRECORDED_COPY.format(location=location), True))
    return attention, swept


def _prune_empty_dirs(inbox: Path) -> None:
    """Remove folders the client dragged into the inbox that are empty now
    their files have moved into the year's folder. Deepest first; anything
    that is not empty or is a sync client's staging folder is left alone.

    The inbox holds nothing of the firm's to keep since decision 125: the
    originals rest in the other tree, so there is no folder here to step
    around."""
    candidates = sorted(
        (p for p in inbox.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for folder in candidates:
        if any(is_sync_staging(part) for part in folder.parts):
            continue
        if _through_a_link(folder, inbox):
            continue        # rmdir on a junction removes the junction, whatever it points at
        try:
            folder.rmdir()  # only succeeds when empty
        except OSError:
            continue


# --------------------------------------------------- an interrupted move ----

#: What the row says when the place an interrupted step was putting its
#: working copy holds a different file. The detail of
#: :data:`tracker.reasons.INTERRUPTED_MOVE`, composed here because the
#: filer is what knows the paths; each name is said once, so the reader
#: below can be derived from this very template.
INTERRUPTED_MOVE_DETAIL = ("{name} at {to}, which now holds a different file ({size} KB) - "
                           "the original is safe in {pbc}")
#: And when neither end of the step holds those bytes any more. Nothing is
#: guessed from that: what the sentence adds is whether the client's own
#: original is still where the record says.
INTERRUPTED_MOVE_LOST_DETAIL = ("{name} from {source} to {to} and neither holds it now; "
                                "the original {pbc} {held}")
INTERRUPTED_ORIGINAL_HELD = "is still there"
INTERRUPTED_ORIGINAL_GONE = "is not there either"
#: Attention, for an interrupted step whose file is a cloud placeholder:
#: reading one would make the sync client download it, so nothing is
#: touched and nothing is decided, and the move stays open for the pass
#: after the sync has finished.
INTERRUPTED_SYNCING = ("an interrupted step was moving {name} and {location} is still "
                       "syncing; nothing was touched and the next pass finishes it")
_INTERRUPTED_TAIL = re.compile(
    "^(?P<base>.*); " + as_pattern(
        reasons.INTERRUPTED_MOVE.template,
        listed=as_pattern(INTERRUPTED_MOVE_DETAIL, name=r".+?", to=r"(?P<to>.+?)",
                          size=r"[\d.]+", pbc=r".+?"),
    ) + "$",
    re.DOTALL,
)


def interrupted_at(entry: IndexEntry) -> str | None:
    """The path an interrupted step was putting this row's copy at, or None.

    The file there is not this row's - that is the whole of why the row
    parked - and it is not the request's either: nothing on the record
    filed it, and counting it would be the corruption decision 109's sweep
    exists to stop, with a truncated copy standing in for the document the
    client sent. So the scanner keeps it out of the count and says the
    firm-side sentence instead, exactly as it does for a copy somebody
    dragged (:func:`moved_to`).

    Only while the row is still parked. Once a person has filed it, set it
    aside or sent it back, what sits in that folder is a file they have
    seen, and the sweep goes on naming it until they take it out.
    """
    if entry.decision != NEEDS_REVIEW:
        return None
    found = _INTERRUPTED_TAIL.match(entry.reason)
    return found.group("to") if found else None


def interrupted_note(entry: IndexEntry) -> str:
    """The interrupted-step sentence this row ends with, or ``""``.

    Read off the row rather than written again, so the request's note and
    the row's Reason are one sentence: the filer wrote it when it could not
    finish the step, and the scanner puts it in front of the request whose
    folder the file was going into.
    """
    found = _INTERRUPTED_TAIL.match(entry.reason) if entry.decision == NEEDS_REVIEW else None
    return entry.reason[len(found.group("base")) + 2:] if found else ""


#: What :func:`_finish_the_ops` found: every step is done, a file at one
#: end is still syncing, the destination holds somebody else's bytes, or
#: neither end holds the bytes the step was moving.
_FINISHED = "finished"
_SYNCING = "syncing"
_TAKEN = "taken"
_LOST = "lost"


def _waiting_on_sync(path: Path) -> bool:
    """Whether this path is a placeholder the sync client has not brought
    down. Never read: hashing one downloads it."""
    return path.is_file() and is_cloud_placeholder(path)


def _the_bytes(path: Path) -> str | None:
    """What this file holds, or None where there is nothing to read - no
    file, a placeholder, or a file this host cannot read now."""
    if not path.is_file() or is_cloud_placeholder(path):
        return None
    return _digest_or_none(path)


def _finish_the_ops(
    engagement_dir: Path, ops: list[dict], cache: ContentCache | None
) -> tuple[str, dict | None]:
    """Finish the steps of one intent that reality says are not done.

    Each step is checked by bytes and only then acted on, in the order the
    decision wrote them - a step may stand on the one before it. Four
    answers, and only these:

    - the destination holds the digest: done, and nothing is touched;
    - the destination is not there and the source holds the digest: the
      move or the copy is made now, which is what the record decided;
    - a stand-down whose file is gone is done, and one that still holds the
      digest is made now (the row says those bytes live elsewhere);
    - anything else stops this intent where it stands and is answered by
      the caller - never by moving something.

    A destination that holds *other* bytes is the contradiction, and a
    destination this host cannot read is treated as one: it is somebody's
    file either way, and the machine never overwrites and never deletes
    what it finds. A step whose row carried no digest (decision 65) can be
    proved by nothing, so the file has only to be there for the step to be
    made and any file at the destination stops it.
    """
    for op in ops:
        kind = op[ledger.OP_KEY]
        source = locate(engagement_dir, op[ledger.FROM_KEY])
        digest = op.get(ledger.DIGEST_KEY, "")
        if _waiting_on_sync(source):
            return _SYNCING, op
        if kind == ledger.OP_REMOVE:
            if digest and _the_bytes(source) == digest:
                source.unlink(missing_ok=True)
            continue                 # gone already, or not provably the row's to take
        target = locate(engagement_dir, op[ledger.TO_KEY])
        if target.exists():
            if _waiting_on_sync(target):
                return _SYNCING, op
            # With a digest, the bytes say whether this step happened.
            # Without one - a drop nobody has hashed yet, a row recorded
            # without its bytes - a move that has happened is a source that
            # is gone, and anything else at a destination this decision
            # chose because it was free is somebody's.
            if (_the_bytes(target) == digest) if digest else not source.exists():
                continue             # this step happened
            return _TAKEN, op
        if not source.is_file() or (digest and _the_bytes(source) != digest):
            return _LOST, op
        _do_op(engagement_dir, op, cache=cache)
    return _FINISHED, None


def _a_copy_to_act_on(
    engagement_dir: Path, entry: IndexEntry, cache: ContentCache | None
) -> str:
    """Where the person's copy of this document is, making one if there is
    none this row can prove.

    A row the recovery parks has to have a working copy a person can open
    and file, and the one the interrupted step was making is not there -
    the place it was going holds somebody else's file. The original in
    The year's folder is the record, so the copy comes from it, into
    ``REVIEW_DIR_NAME`` under the client's own name, never over anything.
    A copy that cannot be made leaves the row naming what it named: the
    pass says the trouble out loud either way, and inventing a path would
    be worse than an honest one that is empty.
    """
    for location in entry.filed_locations:
        if entry.digest and _the_bytes(locate(engagement_dir, location)) == entry.digest:
            return location
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    source = locate(engagement_dir, entry.pbc_location)
    # The copy the interrupted step was about to carry out of review is
    # still there when the step never happened: it is these bytes and it
    # is the copy a person may have written on, so it is used rather than
    # doubled (:func:`_existing_copy`, as everywhere else).
    waiting = _existing_copy(review_dir, source, entry.digest) if entry.digest else None
    if waiting is not None:
        return prepared_location(review_dir, waiting.name)
    try:
        review_dir.mkdir(parents=True, exist_ok=True)
        parked = _unique_path(review_dir, entry.original_name)
        _copy_whole(source, parked, expect=entry.digest, cache=cache)
    except (OSError, FilingError) as exc:
        log.error("Could not park a copy of %s from %s: %s",
                  entry.original_name, entry.pbc_location, exc)
        return entry.prepared_location
    return prepared_location(review_dir, parked.name)


def _finish_interrupted_moves(
    engagement_dir: Path,
    entries: list[IndexEntry],
    before: dict[str, dict],
    cache: ContentCache | None,
) -> list[FileError]:
    """Finish, from the record, every move a killed run left half made.

    **The fingerprint identifies; the record decides** (decision 119). What
    is finished here is a decision the record already holds - the intent a
    pass or a person wrote before touching a file - and the fingerprint
    says only which half of it happened. Where it cannot say, nothing moves
    and a person decides: a destination holding another file is never
    touched, and bytes that are at neither end are never guessed at. It is
    the same line decision 109 draws (the sweep identifies a moved copy and
    a person decides), 110 (the person acts) and 111 (the earlier row's
    decision decides a re-send).

    Runs at the start of every pass, under the lock, before anything else
    looks: before the digests of rows recorded without them are filled in,
    before the client's folder is read for strays, and before the sweep -
    so an interrupted person's filing is finished and recorded as theirs
    rather than swept up as a copy somebody dragged.

    The row each intent carries is recorded as the intent recorded it - the
    event it named, the row it named, dated the day the person made the
    decision - in one call with the events that travelled with it, so a
    filing recovered is a filing, and the keyword it taught is taught.
    Every intent carries one: the move of a drop out of the inbox wrote one
    without a row until decision 125 retired it, and what that costs is
    stated there - a drop a killed run had already moved is sorted as a
    stray on the next pass, dated that day rather than the day it arrived.

    Mutates ``entries`` and ``before`` to what the record holds after it,
    so the pass that follows reads the rows this finished. Returns the
    attention lines.
    """
    conn = store.connect()
    intents = store.open_intents(conn, engagement_dir)
    if not intents:
        return []
    attention: list[FileError] = []
    rows_recorded = False
    for intent in intents:
        key = str(intent.get(ledger.KEY_KEY) or "")
        row = intent.get(ledger.ROW_KEY)
        outcome, op = _finish_the_ops(engagement_dir, intent.get(ledger.OPS_KEY) or [], cache)
        if outcome == _SYNCING:
            attention.append(FileError(Path(op[ledger.FROM_KEY]).name, INTERRUPTED_SYNCING.format(
                name=Path(op[ledger.FROM_KEY]).name,
                location=op.get(ledger.TO_KEY) or op[ledger.FROM_KEY],
            ), True))
            continue                 # the move stays open; the next pass looks again
        entry = entry_from_json(row)
        if outcome == _FINISHED:
            events = [ledger.new(str(intent.get(ledger.EVENT_KEY_AFTER) or ledger.PARKED),
                                 **{ledger.KEY_KEY: key, ledger.ROW_KEY: row})]
            events += list(intent.get(ledger.ALSO_KEY) or [])
            store.record(conn, engagement_dir, *events)
            rows_recorded = True
            log.warning("Finished the interrupted %s of %s from the record",
                        intent.get(ledger.EVENT_KEY_AFTER), entry.original_name)
            continue
        sentence = _the_trouble(engagement_dir, entry, op, outcome)
        parked = _a_copy_to_act_on(engagement_dir, entry, cache)
        new_entry = replace(
            entry, decision=NEEDS_REVIEW, identifier="", also_filed="",
            prepared_location=parked,
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
        )
        store.record(conn, engagement_dir, _ledger_event(ledger.PARKED, new_entry))
        rows_recorded = True
        attention.append(FileError(
            Path(op.get(ledger.TO_KEY) or entry.original_name).name, sentence, True))
        log.warning("An interrupted step on %s could not be finished: %s",
                    entry.original_name, sentence)
    if rows_recorded:
        fresh = read_index(engagement_dir)
        entries[:] = fresh
        before.clear()
        before.update({ledger_key(one): entry_to_json(one) for one in fresh})
    return attention


def _the_trouble(engagement_dir: Path, entry: IndexEntry, op: dict, outcome: str) -> str:
    """The sentence a row gets when its step could not be finished: the
    destination holds a different file, or neither end holds the bytes."""
    if outcome == _TAKEN:
        where = op[ledger.TO_KEY]
        try:
            size = round(locate(engagement_dir, where).stat().st_size / 1024, 1)
        except OSError:
            size = 0.0
        return reasons.INTERRUPTED_MOVE.format(listed=INTERRUPTED_MOVE_DETAIL.format(
            name=entry.original_name, to=where, size=size, pbc=entry.pbc_location))
    held = (INTERRUPTED_ORIGINAL_HELD
            if _the_bytes(locate(engagement_dir, entry.pbc_location)) == entry.digest
            else INTERRUPTED_ORIGINAL_GONE)
    return reasons.INTERRUPTED_MOVE_LOST.format(listed=INTERRUPTED_MOVE_LOST_DETAIL.format(
        name=entry.original_name, source=op[ledger.FROM_KEY],
        to=op.get(ledger.TO_KEY, ""), pbc=entry.pbc_location, held=held))


# ------------------------------------------------------------------- file ----

#: What a drop several of the household's returns accept is parked with: a
#: person chooses, because filing it under one of them would be a guess and
#: filing it under both would be two documents where the client sent one.
#: Composed here rather than in the router because it is made of several
#: routings, one per return, and the router decides one at a time.
CONTESTED_BETWEEN_RETURNS = "accepted by requests in more than one return ({listed}); a person should choose"


@dataclass(slots=True)
class _ReturnRun:
    """One return's half of a household's pass: what it was read as, what it
    decided, and what has to be recorded for it at the end.

    One inbox feeds every return of the household's open year (decision
    125), so the pass reads each return once, judges every drop against
    all of them, and records one transaction per return - which is what
    decision 102 said and has not changed.
    """

    engagement_dir: Path
    label: str
    entries: list[IndexEntry]
    before: dict[str, dict]
    cache: ContentCache
    report: FileReport
    context: _SortContext
    #: Who this return is for (decision 128), off its own record. Empty
    #: for a return nobody has listed yet **and** for one whose record this
    #: pass could not read - and both park every named request, which is
    #: the strict rule: a return the pass cannot say the people of is not a
    #: return a document may be filed into on keywords alone.
    people: tuple[Person, ...] = ()
    moved_keys: dict[str, str] = field(default_factory=dict)
    swept: dict[str, str] = field(default_factory=dict)

    @property
    def items(self) -> list[RequestItem]:
        return self.context.items

    @property
    def known(self) -> dict[str, IndexEntry]:
        return self.context.known

    @property
    def spellings(self) -> tuple[str, ...]:
        """Every spelling of every person on this return, in the list's
        order: what a page is asked whether it says."""
        return tuple(one for person in self.people for one in person.spellings)


def file_household_drops(
    inbox: Path | str,
    originals_dir: Path | str,
    returns: Sequence[Path],
    *,
    today: dt.date | None = None,
    dry_run: bool = False,
) -> dict[Path, FileReport]:
    """Sort one household's inbox across every return of its open year.
    Returns what was done, per return.

    **One inbox, several returns** (decision 125). A household with a
    business and its owner's 1040 has one folder to drop into, so the sort
    judges each drop against every open-year return's request list and
    files it where **exactly one** accepts it - the third standing rule,
    widened from one return's requests to the household's. A drop several
    accept parks in the first accepting return naming them all; a drop
    none accepts parks in the first return by order.

    **The caller holds the locks.** ``tracker.runner.run_household`` takes
    every return's lock, in folder-name order, before anything is read,
    and this asserts that it has them. A dry run decides everything, moves
    nothing and takes no lock, so it can never block a real run.

    **One transaction per return.** Everything each return decided is
    recorded in one call at the end, in the same locked section as the
    moves it records, exactly as decision 102 left it.

    Every pass also proves the working copies each record names against
    their rows and identifies the files it does not name
    (:func:`_prove_working_copies`, decision 109), whether or not there is
    anything to sort - a copy somebody dragged is the one disagreement
    between the record and the folder nothing used to notice.
    """
    inbox, originals_dir = Path(inbox), Path(originals_dir)
    today = today or dt.date.today()
    stamp = today.isoformat()
    runs = [_prepare_return(Path(folder), stamp, dry_run=dry_run) for folder in returns]
    if not runs:
        return {}
    first = runs[0]

    # 2. The originals folder is read once, against the union of every
    # return's rows: a file one return's row holds is never another
    # return's stray. What is left over is a stray for the household.
    strays = (unrecorded_in_pbc(originals_dir, [(r.engagement_dir, r.entries) for r in runs])
              if originals_dir.is_dir() else [])
    for run in runs:
        strays = _follow_and_say(run, strays, originals_dir, stamp)

    # 3. The inbox is read once. What it says about itself - a transfer
    # still in flight, a name Windows refuses, a folder this run cannot
    # list - is the household's, and rides the first return's report,
    # which is where the practice page reads it from.
    drops = iter_drops(inbox)
    first.report.waiting.extend(unfinished_drops(inbox))
    for path in unreachable_drops(inbox):
        first.report.errors.append(FileError(
            path.name, "cannot be handled under this name (a name Windows refuses, or the index cannot hold); rename it", True
        ))
        log.warning("Left %s in place: the name cannot be handled", path.name)
    for folder in unlistable_folders(inbox):
        first.report.errors.append(FileError(
            folder.name, "is a folder this run cannot list (its permissions deny it); whatever is inside is not sorted", True
        ))
        log.warning("Could not list %s: its permissions deny it", folder)

    try:
        if drops or strays:
            if not dry_run:
                originals_dir.mkdir(parents=True, exist_ok=True)
                for run in runs:
                    run.context.prepared_dir.mkdir(parents=True, exist_ok=True)
            _sort_all(drops, strays, originals_dir, stamp, runs)
    finally:
        # Whatever happened above, every original that was moved is on
        # record: one call and one transaction per return, in the same
        # locked section as the moves it records. A return that decided
        # nothing writes nothing - the diff against what its record
        # already said is what decides, not a count of rows.
        if not dry_run:
            for run in runs:
                _record(run.engagement_dir, run.before, run.entries,
                        moved=run.moved_keys, decided=run.swept)
    if not dry_run:
        for run in runs:
            run.cache.save()
            for name in _remove_the_retired_cache(run.engagement_dir):
                run.report.attention.append(FileError(name, RETIRED_CACHE_REMOVED, False))
        # The tidy-up is owed to every pass, not only one that sorted
        # something: an empty folder the client dragged in outlives the
        # files that were in it, and a pass that found nothing to do used
        # to leave it there for ever. The inbox holds no folder of the
        # firm's to keep.
        _prune_empty_dirs(inbox)
    return {run.engagement_dir: run.report for run in runs}


def _prepare_return(engagement_dir: Path, stamp: str, *, dry_run: bool) -> _ReturnRun:
    """Everything one return is read as, before the household's inbox is
    touched: its record brought up to date, its interrupted moves finished,
    its digests filled in, its working copies proved.

    Exactly what the sort did for the one engagement it belonged to before
    an inbox was the household's, once per return (decision 125). The lock
    is the caller's: this
    asserts it rather than taking it, because the household's locks are
    taken together, in one order, before anything is read.
    """
    if not dry_run and not lock_is_held(engagement_dir):
        raise FilingError(
            f"{engagement_dir.name}: the household's returns are sorted only while this run holds "
            f"their locks; nothing was touched"
        )
    report = FileReport(engagement_dir=engagement_dir, dry_run=dry_run)
    # Before anything is read: the store is brought up to the record. A dry
    # run builds the store's own rows and moves nothing of the client's.
    ensure(engagement_dir)
    items = load_manifest(engagement_dir)
    entries = read_index(engagement_dir)
    # What the record already says, taken before anything in this pass
    # touches a row, so what this pass wrote is what gets recorded.
    before = {ledger_key(entry): entry_to_json(entry) for entry in entries}
    # What the router learns about each document is what the scan will want
    # to know about its working copy (same bytes): the verdicts go into the
    # return's verdict cache in the store, keyed by content (decision 107).
    cache = ContentCache(engagement_dir)
    details = _details_of(engagement_dir)
    run = _ReturnRun(
        engagement_dir=engagement_dir,
        label=_label_of(engagement_dir, details),
        people=() if details is None else details.people,
        entries=entries, before=before, cache=cache, report=report,
        context=_SortContext(
            engagement_dir=engagement_dir,
            items=items, by_id={i.identifier: i for i in items}, known={},
            prepared_dir=engagement_dir / PREPARED_DIR_NAME,
            review_dir=engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME,
            reserved={}, assigned={}, dry_run=dry_run, report=report,
            cache=cache, pdf_cache=PdfVerdictCache(),
        ),
    )
    # A run killed between one of its moves and the record of it left the
    # disk ahead of the record. What it was about to do is written down
    # (decision 119), so it is finished here - before the digests below are
    # filled in from copies that may still be in flight, before the
    # client's folder is read for strays, and before the sweep, which would
    # otherwise call a person's interrupted filing a copy somebody dragged.
    # A dry run finishes nothing, like everything else here.
    if not dry_run:
        report.attention.extend(_finish_interrupted_moves(engagement_dir, entries, before, cache))
    # An original preserved by a pass that could not read it back has no
    # digest (decision 65). While it has none, a replacement is never
    # noticed and a person's filing of it is never honoured; a later pass
    # records the bytes where its copy and the original still agree, and
    # says so where they do not.
    _filled, untied = (0, []) if dry_run else _record_missing_digests(engagement_dir, entries)
    for path, earlier in untied:
        report.attention.append(FileError(path.name, UNTIED_IN_PBC.format(
            location=earlier.pbc_location, received=earlier.received,
            prepared=earlier.prepared_location,
        ), True))
    # Existing request folders, so a Document renamed in the editor keeps
    # filing into the folder that already holds its earlier files - and so
    # the sweep below knows which folders a request claims, the same
    # reading the scanner's warnings are drawn from.
    run.context.assigned = assign_folders(run.context.prepared_dir, [i.identifier for i in items])
    # Every working copy the record names, proved against the row's own
    # fingerprint, and every file the record does not name, identified by
    # it (decision 109). It runs before the rows below are read, so what
    # follows sees the rows as this sweep leaves them; a dry run reads all
    # of it and records none of it, like everything else.
    sweep, swept = _prove_working_copies(
        engagement_dir, run.context.prepared_dir, entries, cache, stamp,
        {folder for folders in run.context.assigned.values() for folder in folders},
    )
    report.attention.extend(sweep)
    run.swept = swept
    # The row that holds each document's bytes. A Duplicate row only points
    # at another row; letting it shadow the Filed row would hide a working
    # copy that has since been deleted, and a re-send that answers
    # "Missing" would be called a duplicate for ever (decision 58). Every
    # other decision holds its bytes, a person's ``NOT_REQUESTED``
    # included - so that a re-send of what somebody set aside is
    # *recognised* as those bytes. What is then done with it is the earlier
    # row's decision to say, in ``_sort_one``, and for a set-aside row that
    # is a fresh look, not a duplicate: decision 76 said it once and
    # decision 111 amended it.
    run.context.known.update({e.digest: e for e in entries if e.digest and e.decision != DUPLICATE})
    return run


def _details_of(engagement_dir: Path) -> EngagementInfo | None:
    """The return's own details, or None for a record this pass has already
    said is unreadable. Read once per return per pass: the label and the
    people list are both drawn from it."""
    try:
        return load_engagement_info(engagement_dir)
    except Exception:
        return None


def _label_of(engagement_dir: Path, info: EngagementInfo | None) -> str:
    """How one return is named in a sentence a person reads - the household,
    the year and the return - from its own record, falling back to the
    folders when the record carries none of the three."""
    if info is None:
        return engagement_dir.name
    return label_for_return(
        info.household or household_name_of(engagement_dir),
        info.tax_year if info.tax_year is not None else year_of(engagement_dir),
        info.return_name or engagement_dir.name,
    )


def _follow_and_say(
    run: _ReturnRun, strays: list[Path], originals_dir: Path, stamp: str
) -> list[Path]:
    """One return's reading of the household's year folder: the rows whose
    original the client moved follow their bytes, the rows whose original
    is gone are said, and an original replaced under its own name is said.

    Returns the strays that are still strays after this return has claimed
    what is its - so the next return looks at what is left and a file that
    belongs to one return's row is never another return's stray.
    """
    engagement_dir = run.engagement_dir
    # An original the client deleted, renamed or moved after it was
    # recorded is a row naming a path that holds nothing. Where a stray
    # carries the row's bytes the row follows the file (and is not adopted
    # a second time); the rest are said, every pass.
    strays, moved, gone = _follow_moved_originals(engagement_dir, run.entries, strays, stamp)
    # Where a row's identity in the record moved to, and from.
    run.moved_keys.update({
        location_of(engagement_dir, path): ledger_key(earlier) for path, earlier in moved
    })
    for path, earlier in moved:
        run.report.attention.append(FileError(path.name, MOVED_IN_PBC.format(
            location=earlier.pbc_location, now=location_of(engagement_dir, path),
        ), True))
    for earlier in gone:
        run.report.attention.append(FileError(earlier.original_name, MISSING_IN_PBC.format(
            location=earlier.pbc_location, received=earlier.received,
        ), True))
    # An original replaced under its own name is said loudly, every run,
    # until a person has looked; it is not sorted again and not guessed.
    for path, earlier in (replaced_in_pbc(originals_dir, engagement_dir, run.entries)
                          if originals_dir.is_dir() else []):
        run.report.attention.append(FileError(path.name, REPLACED_IN_PBC.format(
            location=earlier.pbc_location, received=earlier.received,
            prepared=earlier.prepared_location or "(none)",
        ), True))
    return strays


def _remove_the_retired_cache(engagement_dir: Path) -> list[str]:
    """Take the verdict cache's old file out of the engagement folder.
    Returns the names removed, for the report to say once.

    Until decision 107 the cache was a JSON file here that every pass
    rewrote; it lives in the store now and **nothing reads the file** -
    the owner's rule is that nothing the machine can derive stays in the
    synced folder, and reading it once would keep its loader alive for a
    release to save one cold pass. So the first real pass after the
    upgrade removes it, and any temp file the atomic write it used to go
    through left beside it (``fsio.temp_path_for`` put the process id
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
    originals_dir: Path,
    stamp: str,
    runs: list[_ReturnRun],
) -> None:
    """Decide and record every drop and every stray, one at a time, across
    the household's returns.

    Each file is handled on its own: a file the sync client still holds
    open is left in place for the next run, and one that fails *after* it
    was preserved is recorded as needing review with the error, so no one
    bad file costs the rest of the pass or the audit trail. The caller
    writes each return's record whatever happens in here.
    """
    first = runs[0]
    dry_run = first.context.dry_run
    for drop, already_filed in (
        [(d, False) for d in drops] + [(p, True) for p in strays]
    ):
        # A file the sync client has not downloaded is not a document yet.
        if is_cloud_placeholder(drop):
            first.report.waiting.append(drop)
            continue

        try:
            drop.stat()          # still there, and readable: a file mid-write is left
        except OSError as exc:
            first.report.errors.append(FileError(
                drop.name, f"could not read it ({exc}); left in place", True
            ))
            log.warning("Left %s in place: %s", drop.name, exc)
            continue

        # The original moves once, out of the inbox into the folder the
        # client can see for the year, and never again (decision 125): its
        # resting place is the record's identity for the document. The move
        # is a rename and decision 23 finishes it whichever side of a kill
        # it falls on - an original in that folder with no row is sorted
        # where it lies - so no intent is written for it.
        if already_filed or dry_run:
            original = drop if already_filed else originals_dir / drop.name
        else:
            try:
                original = _unique_path(originals_dir, drop.name)
                _move_whole(drop, original)
            except OSError as exc:
                first.report.errors.append(FileError(
                    drop.name,
                    f"could not move it into {originals_dir.name} ({exc}); left in place",
                    True,
                ))
                log.warning("Left %s in place: %s", drop.name, exc)
                continue
        # The record is of the bytes that were preserved: hashed where they
        # now are, after the move, so a sync client landing a newer version
        # in between can never leave the index describing one file and the
        # folder holding another.
        recorded_at = drop if dry_run and not already_filed else original
        try:
            digest = sha256_of(recorded_at)
            size_kb = round(recorded_at.stat().st_size / 1024, 1)
        except OSError as exc:
            if already_filed or dry_run:
                first.report.errors.append(FileError(
                    drop.name, f"could not read it ({exc}); left in place", True
                ))
                log.warning("Left %s in place: %s", drop.name, exc)
                continue
            digest, size_kb = "", 0.0     # moved, unreadable now: recorded anyway
            log.warning("Preserved %s but could not read it back: %s", drop.name, exc)

        try:
            run, entry = _decide_across(drop, original, digest, size_kb, stamp, runs)
        except Exception as exc:  # the original is safe; say so and go on
            log.exception("Could not file %s", drop.name)
            run = first
            entry = IndexEntry(
                received=stamp, original_name=drop.name, size_kb=size_kb,
                digest=digest, identifier="",
                prepared_location="", pbc_location=location_of(run.engagement_dir, original),
                decision=NEEDS_REVIEW,
                reason=(
                    f"could not be filed ({exc.__class__.__name__}: {exc}); "
                    f"original preserved in {location_of(run.engagement_dir, original)} - "
                    f"file it by hand"
                ),
            )
            run.report.errors.append(FileError(drop.name, entry.reason, False))
            run.report.review.append(entry)

        run.entries.append(entry)
        if entry.decision != DUPLICATE and digest:
            run.known[digest] = entry


#: What a filed row's Reason gains when the name on the page confirmed it
#: (decision 128). The firm's own spelling, never a word of the document -
#: which is the same line :class:`tracker.records.Evidence` draws.
NAME_CONFIRMED_NOTE = "name confirmed ({spelling})"

#: The order a parked document's name reason is chosen in when the
#: household's returns dropped it for different ones. The most useful
#: first: "the page names nobody here" is the one a person can act on with
#: a spelling, "it names somebody there" tells them where to look, and
#: "this return lists nobody" is a setup step somebody skipped.
_NAME_REASONS = (reasons.NAME_NOT_ON_PAGE, reasons.NAMES_ANOTHER_RETURN, reasons.NO_PEOPLE_ON_FILE)


def _is_named(run: _ReturnRun, routing) -> bool:
    """Whether the request this return accepted the document under carries a
    name (decision 128).

    A page decision 94 split across several requests is named when **any**
    of them is: a sheet holding a W-2 and a 1099-INT is two documents and
    both are addressed to somebody, so the strict rule applies to the whole
    page rather than to whichever request happened to be named first.
    """
    return any(item.named for identifier in routing.filed_to
               if (item := run.context.by_id.get(identifier)) is not None)


def _with_the_name(routing, verdict: NameVerdict):
    """``routing`` with the name's own evidence added to every candidate it
    names (decision 128, :data:`tracker.records.RULE_NAME`).

    A confirmed or vetoed verdict leaves the spelling that decided it and
    where on the page it was said; an absent one leaves nothing, because
    there is nothing to say. The term is the firm's own spelling either
    way - it is a term the firm typed, exactly as a keyword is - and no
    word of the document travels with it.
    """
    term = verdict.matched or verdict.other
    if not term:
        return routing
    found = Evidence(RULE_NAME, term, verdict.where, verdict.page)
    return replace(routing, evidence_record={
        identifier: (*said, found) for identifier, said in routing.evidence_record.items()
    })


@dataclass(slots=True)
class _NameStage:
    """What the name tier made of one drop across the household's returns.

    ``kept`` is what is still accepting, each routing carrying the name's
    evidence; ``graded`` is every accepting return's routing with that
    evidence on it, by the return's identity, so a document that parks in
    the home return still keeps what the name said there; ``met`` is the
    reasons met, in the order they were met; ``confirmed`` is the note each
    kept return's Reason gains when it files.
    """

    kept: list[tuple[_ReturnRun, object]] = field(default_factory=list)
    graded: dict[int, object] = field(default_factory=dict)
    met: list[tuple[object, str]] = field(default_factory=list)
    confirmed: dict[int, str] = field(default_factory=dict)

    @property
    def reason(self) -> str:
        """The one sentence a document the name tier emptied the list for
        carries: the first of :data:`_NAME_REASONS` any return met, filled
        with what that return said."""
        for reason in _NAME_REASONS:
            for one, listed in self.met:
                if one is reason:
                    return reason.format(listed=listed)
        return ""


def _by_the_name(
    text: str, accepting: list[tuple[_ReturnRun, object]], runs: list[_ReturnRun]
) -> _NameStage:
    """The name tier (decision 128), run over what the request lists accepted.

    For each accepting return, in order, the page is asked whether it names
    one of that return's people, somebody on another return the drop may
    feed, or nobody (:func:`tracker.names.check_name`). Then the table the
    owner settled:

    ====================  =========  ======================  ===================
    the accepted item is  confirmed  absent                  another return's
    ====================  =========  ======================  ===================
    **named**             stays      dropped, and it parks   dropped
    **unnamed**           stays      stays (today's rule)    dropped
    ====================  =========  ======================  ===================

    A return with no people at all treats every named acceptance as absent
    and says so differently: nobody has listed anybody yet, and the fix is
    one edit rather than one spelling.
    """
    stage = _NameStage()
    for run, routing in accepting:
        others = {other.label: other.spellings for other in runs if other is not run}
        verdict = check_name(text, run.spellings, others)
        routing = _with_the_name(routing, verdict)
        stage.graded[id(run)] = routing
        if verdict.outcome == NAME_CONFIRMED:
            stage.confirmed[id(run)] = NAME_CONFIRMED_NOTE.format(spelling=verdict.matched)
            stage.kept.append((run, routing))
        elif verdict.outcome == NAME_VETOED:
            stage.met.append((reasons.NAMES_ANOTHER_RETURN, reasons.NAME_AND_RETURN.format(
                spelling=verdict.other, label=verdict.other_label)))
        elif not _is_named(run, routing):
            stage.kept.append((run, routing))   # a receipt, a log, a headerless export
        elif run.people:
            stage.met.append((reasons.NAME_NOT_ON_PAGE, run.label))
        else:
            stage.met.append((reasons.NO_PEOPLE_ON_FILE, run.label))
    return stage


def _decide_across(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str, runs: list[_ReturnRun]
) -> tuple[_ReturnRun, IndexEntry]:
    """Which of the household's returns this one preserved original belongs
    to, and the row that says so.

    In order (decisions 125 and 128):

    - **the bytes first.** Every return's record is asked whether it
      already holds them, in order, and the first that does decides - by
      decision 111's rule, in its own record. The content hash identifies;
      the earlier decision decides;
    - **then the requests.** The document is read **once**
      (:func:`tracker.router.read_once`) and that one reading is routed
      against every return's list, in order, so a two-return household
      costs one reading and never OCRs a photo twice;
    - **then the name.** Whose document this is is asked of the same
      reading, against each accepting return's own people list
      (:func:`_by_the_name`): two 1040s share every row of their lists, so
      the keywords cannot say whose W-2 this is and the name can;
    - **then exactly one.** Exactly one return left files it; several park
      it in the first accepting return naming them all; none parks it in
      the first return that accepted it - the first by order where nothing
      did (decision 125's home) - with the name's reason where the name is
      what emptied the list. That is the third standing rule - nothing is
      guessed - read across the household instead of across one list.
    """
    if digest:
        for run in runs:
            if digest in run.known:
                return run, _sort_one(drop, original, digest, size_kb, stamp, run, runs)

    # One reading, however many returns judge it (decision 128). A dry run
    # judges the drop where it lies, as it always has.
    judged = drop if runs[0].context.dry_run else original
    reading = read_once(judged)
    routed = [(run, route_file(judged, run.items, reading=reading,
                               digest=digest, cache=run.cache, pdf_cache=run.context.pdf_cache))
              for run in runs]
    accepting = [(run, routing) for run, routing in routed if routing.routed]

    # The name check runs on the same reading. With no words at all the
    # router has already parked the document (UNREADABLE) and nothing
    # accepted it, so the stage has nothing to judge.
    text = "" if reading.needs_ocr else (reading.text or "")
    stage = _by_the_name(text, accepting, runs)
    kept = stage.kept

    if len(kept) == 1:
        run, routing = kept[0]
        item = run.context.by_id.get(routing.identifier or "")
        if item is not None:
            return run, _file_it(drop, original, digest, size_kb, stamp, run, routing, item,
                                 confirmed=stage.confirmed.get(id(run), ""))

    if len(kept) > 1:
        # Two returns of one household ask for the same row - two 1040s
        # share every row of their lists - and the name did not tell them
        # apart either, which since decision 128 means a page naming both
        # spouses. The sentence names every return that accepted it and the
        # requests each accepted it under, so the person choosing is
        # choosing from what the tracker saw.
        home, routing = kept[0]
        listed = "; ".join(f"{run.label}: {', '.join(one.filed_to)}" for run, one in kept)
        return home, _park_it(
            drop, original, digest, size_kb, stamp, home,
            reason=CONTESTED_BETWEEN_RETURNS.format(listed=listed),
            candidates=routing.candidates, evidence=format_evidence(routing.evidence_record),
        )

    # Nothing left. The home is decision 125's: the return of the first
    # request that accepted the document, and only where nothing accepted
    # it at all the first return by folder order. A bank statement only the
    # 1120S's list asks for, naming nobody, parks in the 1120S's queue -
    # where the row that wanted it is and where a person can file it by
    # hand - rather than in a 1040 that never asked for it and has nothing
    # to take it. Where the name is what emptied the list, the row says so
    # in the name's own words rather than the router's "matched no
    # request", which would be a lie about a W-2 the list plainly wanted.
    home, routing = (accepting or routed)[0]
    routing = stage.graded.get(id(home), routing)   # with the name's evidence, where it judged
    return home, _park_it(
        drop, original, digest, size_kb, stamp, home,
        reason=stage.reason or routing.reason, candidates=routing.candidates,
        evidence=format_evidence(routing.evidence_record),
    )


@dataclass(slots=True)
class _SortContext:
    """What every drop in one return is sorted against: the return folder,
    the manifest, the index so far, the folders, the names claimed, and the
    run's caches. Built once per return in :func:`_prepare_return`;
    :func:`_sort_one` reads it. Sixteen positional arguments - three of
    them strings, two of them dicts - was how an argument-order slip could
    stay silent."""

    #: The return folder every location this run writes is relative to
    #: (``layout.location_of``). Named rather than derived from the
    #: prepared folder's parent: a path the record holds crosses the two
    #: trees now, and what it is relative to is a fact worth stating.
    engagement_dir: Path
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


def _plan_working_copy(
    item: RequestItem, drop: Path, original: Path, digest: str, run: _SortContext
) -> tuple[str, dict | None]:
    """Where one working copy of a preserved original goes in one request's
    folder, and the copy that will put it there.

    The copy is made from ``original`` - the file in the client's folder
    for the year, never the drop - under the canonical name for that row,
    and a copy already there holding these bytes is reused rather than
    doubled (:func:`_existing_copy`: a killed run's), which is what
    ``None`` says. A dry run decides all of it and writes nothing, which
    is why the names claimed are kept in ``run.reserved`` rather than read
    back off the disk.

    Deciding and copying are two steps since decision 119: what the copies
    will be is written down before any of them is made, so a run killed
    between them is finished from the record rather than guessed at.

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
    if run.dry_run:
        return prepared_location(dest_folder, filed_as), None
    dest_folder.mkdir(parents=True, exist_ok=True)
    existing = _existing_copy(dest_folder, original, digest)
    if existing is not None:
        return prepared_location(dest_folder, existing.name), None
    return (prepared_location(dest_folder, filed_as),
            _op(run.engagement_dir, ledger.OP_COPY, original, dest_folder / filed_as, digest))


def _carry_out(entry: IndexEntry, ops: list[dict], then: str, run: _SortContext) -> None:
    """Write down what this drop's copies will be, then make them.

    The intent carries the row this pass will record at the end of it and
    the event it will be recorded as, so a pass killed between the copy and
    the batch record is finished from the record: the copies that are
    already there are left alone, the ones that are not are made, and the
    row is recorded as it was decided (decision 119). A dry run writes
    nothing, here as everywhere.
    """
    if run.dry_run or not ops:
        return
    _intend(run.engagement_dir, ledger_key(entry), ops, by=ledger.BY_PASS,
            row=entry_to_json(entry), then=then)
    for op in ops:
        _do_op(run.engagement_dir, op, cache=run.cache)


def _file_it(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str,
    run: _ReturnRun, routing, item: RequestItem, *, refiled: str = "", resent: str = "",
    confirmed: str = "",
) -> IndexEntry:
    """File one preserved original under the request that accepted it.

    One row per request the router named (decision 94 names more than one
    where a page carried more than one form), and one working copy per
    row. The original is preserved once, under its own name, in the
    client's folder for the year, and the index keeps one row for it: the
    copies are this row's, not rows of their own.

    ``confirmed`` is what the name on the page said (decision 128), added
    last to the Reason: the firm's own spelling that matched, so a person
    reading the row a year later sees both that the keywords placed it and
    that the name agreed.
    """
    context = run.context
    wanted = [item] + [context.by_id[i] for i in routing.also if i in context.by_id]
    planned = [_plan_working_copy(one, drop, original, digest, context) for one in wanted]
    locations = [location for location, _op_for_it in planned]
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier=item.identifier,
        prepared_location=locations[0],
        pbc_location=location_of(run.engagement_dir, original), decision=FILED,
        reason="; ".join(part for part in (routing.reason, refiled, resent, confirmed) if part),
        candidates=_CANDIDATE_SEP.join(routing.candidates),
        evidence=format_evidence(routing.evidence_record),
        also_filed=_CANDIDATE_SEP.join(locations[1:]),
    )
    _carry_out(entry, [op for _location, op in planned if op is not None], ledger.FILED, context)
    run.report.filed.append(entry)
    return entry


def _park_it(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str,
    run: _ReturnRun, *, reason: str, candidates, evidence: str, resent: str = "",
) -> IndexEntry:
    """Park one preserved original in this return's Needs Review, with a
    working copy a person can open and the sentence that says why."""
    context = run.context
    review_name = drop.name
    parking: list[dict] = []
    if not context.dry_run:
        context.review_dir.mkdir(parents=True, exist_ok=True)
        # One row, one working copy. The copy already there holding these
        # bytes is the *set-aside* row's, and two rows naming one file would
        # let filing either of them carry the other's copy away, so a re-send
        # of set-aside bytes takes a fresh copy of its own. The person may
        # end with two identical files in review, which is the truthful
        # state: two arrivals, two decisions to make.
        review_target = None if resent else _existing_copy(context.review_dir, original, digest)
        if review_target is None:
            review_target = _unique_path(context.review_dir, drop.name)
            parking.append(_op(run.engagement_dir, ledger.OP_COPY,
                               original, review_target, digest))
        review_name = review_target.name
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier="",
        prepared_location=prepared_location(context.review_dir, review_name),
        pbc_location=location_of(run.engagement_dir, original), decision=NEEDS_REVIEW,
        # The flag first: what a person opening the card should read before
        # the reason for parking it.
        reason=f"{resent}; {reason}" if resent else reason,
        candidates=_CANDIDATE_SEP.join(candidates),
        evidence=evidence,
    )
    _carry_out(entry, parking, ledger.PARKED, context)
    run.report.review.append(entry)
    return entry


def _sort_one(
    drop: Path,
    original: Path,
    digest: str,
    size_kb: float,
    stamp: str,
    run: _ReturnRun,
    runs: list[_ReturnRun],
) -> IndexEntry:
    """Decide one preserved original's fate inside the one return whose
    record already holds its bytes, and, unless dry-running, copy it.

    The road decision 111 laid: the content hash says *which* row already
    holds these bytes, and that row's decision says what this arrival is.
    A re-send whose earlier row was filed and whose copy is gone is filed
    again; one a person set aside is routed afresh against that return's
    list; anything else is a duplicate of the row that holds it.

    Both roads that route afresh are name-checked before they file
    (decision 128): a W-2 set aside the day the list had no row for it and
    re-sent once the row was added would otherwise file on its keywords
    alone, whoever the page named - which is the one failure the name tier
    exists to stop, arriving by the back door. ``runs`` is the household's
    returns, so the other returns' spellings can veto here exactly as they
    do in the household pass; the reading is taken once and handed to the
    router, as it is there.
    """
    context = run.context
    refiled = resent = ""
    earlier = run.known[digest]
    if (
        earlier.decision == FILED
        and earlier.prepared_location
        and not locate(run.engagement_dir, earlier.prepared_location).exists()
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
            pbc_location=location_of(run.engagement_dir, original), decision=DUPLICATE,
            reason=words.format(name=earlier.original_name, copy=earlier.filed_as),
        )
        run.report.duplicates.append(entry)
        return entry

    judged = drop if context.dry_run else original
    reading = read_once(judged)
    routing = route_file(
        judged, context.items, reading=reading,
        digest=digest, cache=context.cache, pdf_cache=context.pdf_cache,
    )
    item = context.by_id.get(routing.identifier or "")
    if routing.routed and item is not None:
        # The same name tier the household pass runs, over the one return
        # this arrival belongs to: the page confirms it, another return's
        # person vetoes it, and on a named request a page naming nobody
        # parks it.
        text = "" if reading.needs_ocr else (reading.text or "")
        stage = _by_the_name(text, [(run, routing)], runs)
        if stage.kept:
            _kept, routing = stage.kept[0]
            return _file_it(drop, original, digest, size_kb, stamp, run, routing, item,
                            refiled=refiled, resent=resent,
                            confirmed=stage.confirmed.get(id(run), ""))
        routing = stage.graded.get(id(run), routing)
        return _park_it(drop, original, digest, size_kb, stamp, run,
                        reason=stage.reason or routing.reason, candidates=routing.candidates,
                        evidence=format_evidence(routing.evidence_record), resent=resent)
    return _park_it(drop, original, digest, size_kb, stamp, run,
                    reason=routing.reason, candidates=routing.candidates,
                    evidence=format_evidence(routing.evidence_record), resent=resent)


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


#: What a filing refuses a spelling for a person the return does not list
#: with, and the note when the person already had it. Both are said once
#: here, and the app shows them as it shows the keyword's.
PERSON_NOT_ON_RETURN = "{person} is not on this return"
ALREADY_SPELLED = "{person} already had the spelling {spelling!r}"


@dataclass(frozen=True, slots=True)
class Spelling:
    """One spelling a person taught while filing (decision 128): whose name
    it is, as the return lists it, and the form the page printed it in."""

    person: str
    spelling: str


@dataclass(frozen=True, slots=True)
class AssignResult:
    """What filing one parked document by hand did."""

    entry: IndexEntry            # the rewritten index row
    moved_review_copy: bool      # True: the parked copy (REVIEW_DIR_NAME) became the working copy
    keyword: str = ""            # keyword added to the row's Any Keywords, if any
    keyword_note: str = ""       # why it was not added, when it was not
    left_in_review: str = ""     # a parked copy that no longer held the row's bytes, and stayed
    overrode_shortlist: str = ""  # the sentence written when the pick was off the shortlist
    spelling: str = ""           # spelling added to one of the return's people, if any
    spelling_note: str = ""      # why it was not added, when it was not


def _taught_spelling(
    engagement_dir: Path, taught: Spelling | None
) -> tuple[list[dict], str, str]:
    """The one ``rules_changed`` event a spelling taught from the queue is,
    or nothing at all (decision 128).

    The return's whole people list travels, with the spelling added to the
    one person it names, because that is the shape the details are
    recorded in and a line the record can be rebuilt from must mean
    something on its own. A spelling of one word is refused - a family name
    alone would confirm a business's statement - and so is a person this
    return does not list; a person who already has the spelling is a note
    and not an event, exactly as a keyword the row already had is.
    """
    if taught is None or not taught.spelling.strip():
        return [], "", ""
    spelling = " ".join(taught.spelling.split())
    if not is_a_spelling(spelling):
        raise FilingError(ONE_WORD_SPELLING)
    people = load_engagement_info(engagement_dir).people
    wanted = name_words(taught.person)
    found = next((one for one in people if name_words(one.name) == wanted), None)
    if found is None:
        raise FilingError(PERSON_NOT_ON_RETURN.format(person=taught.person))
    if any(name_words(one) == name_words(spelling) for one in found.spellings):
        return [], "", ALREADY_SPELLED.format(person=found.name, spelling=spelling)
    grown = replace(found, spellings=(*found.spellings, spelling))
    listed = [grown if one is found else one for one in people]
    return [ledger.new(ledger.RULES_CHANGED, **{
        ledger.INFO_KEY: {"people": [person_to_json(one) for one in listed]},
    })], spelling, ""


def assign_review_file(
    engagement_dir: Path | str,
    original: str,
    identifier: str,
    *,
    keyword: str = "",
    spelling: Spelling | None = None,
    today: dt.date | None = None,
    seq: int | None = None,
    shortlist: Sequence[str] | None = None,
) -> AssignResult:
    """File a parked document under a request, the way the filer would have.

    ``original`` is the index row to act on: its PBC location
    (the year's folder and the original's name) or, failing that, its original name among
    the rows still marked Needs Review. The working copy is created under the
    canonical name in the request's folder - moved from ``REVIEW_DIR_NAME`` when it is still there, copied from the year's folder when it is not -
    and the index row is rewritten as Filed with the decision attributed to
    a person. The original in the year's folder is not touched.

    ``keyword`` is optional: recorded against the request so the next
    document like this one routes itself, and laid over the row's typed
    Any Keywords by every reader (``manifest.load_manifest``). It is
    recorded, never typed into the row (decision 103): the one note left
    is that the request already had the word.

    ``spelling`` is optional too, and rides the same transaction
    (decision 128): a spelling the page printed, added to one of the
    return's people, so the next document that prints it confirms itself.
    A spelling of one word and a person the return does not list are both
    refused before a byte is read. Unfiling never takes a spelling back,
    exactly as it never takes a keyword back (decision 77); a spelling is
    removed in the editor.

    A ``FILE_MOVED`` row is filed from here too - decision 110's "keep it
    here", the answer to a copy somebody dragged into a request's folder
    on purpose. The copy that moves is then the wanderer the row's reason
    names (:func:`moved_to`), which takes the canonical name in the folder
    it already sits in, or in another request's folder when the person
    picks one instead: the picker is the same picker, so keeping the file
    and correcting the request is one click. A page decision 94 filed
    under several requests is refused here (``SEVERAL_COPIES_REFUSAL``) and
    put back with :func:`restore_working_copy` first.

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
        _refuse_if_a_move_is_open(engagement_dir)
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
        position = find_parked(entries, original, accepting=(FILE_MOVED,))
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        if entry.decision == FILE_MOVED and entry.also_filed:
            # Decision 110: a page decision 94 filed under several requests
            # has a copy in each, and which of them the person means by
            # "keep it here" is not the machine's to guess. Put it back
            # answers for every copy, and unfiling starts from there.
            raise FilingError(SEVERAL_COPIES_REFUSAL.format(name=entry.original_name))
        source = locate(engagement_dir, entry.pbc_location)
        if not source.is_file():
            raise FilingError(
                f"the original {entry.pbc_location} is no longer there"
            )
        if is_cloud_placeholder(source):
            raise FilingError(f"the original {entry.pbc_location} is still syncing; try again when it is here")
        digest, size_kb = entry.digest, entry.size_kb
        # The copy to move is the one the record says this row's bytes are
        # at. For nearly every row that is the Prepared Location column;
        # for a ``FILE_MOVED`` row it is the wanderer the reason names
        # (decision 110's keep-it-here), and a row whose bytes are nowhere
        # under the firm's folder has none, so the copy comes from the
        # client's original exactly as it does for a parked copy that went.
        here = moved_to(entry) if entry.decision == FILE_MOVED else entry.prepared_location
        parked = locate(engagement_dir, here) if here else None
        # The parked copy is only ever read when it is here, hydrated
        # (hashing a dehydrated one would make the sync client download
        # it), and still this row's - a later row at the same path means
        # this row's copy is gone and what sits there is the later row's.
        # A later row can only take a path the index *names*, which is the
        # Prepared Location column; a wanderer is by definition a path no
        # row names, so that question is not asked of one - and its bytes
        # are checked below either way, which is the stronger test.
        parked_here = (
            parked is not None and parked.is_file() and not is_cloud_placeholder(parked)
            and (entry.decision == FILE_MOVED
                 or not _copy_taken_by_a_later_row(entries, position))
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
        ops: list[dict] = []
        # A copy with these bytes already in the folder is a killed earlier
        # attempt's, and is reused rather than doubled. Otherwise the parked
        # copy is moved, but only while it holds the row's bytes: its name
        # is the client's, and a freed name is taken by the next drop called
        # the same, so a person filing row A would carry document B into the
        # request folder under A's canonical name (the eleventh reading); a
        # copy a reviewer's app re-saved is not the row's bytes either and
        # is left where it is, said so, for the person to keep or discard.
        # What will move is decided here and written down before any of it
        # happens (decision 119), so a kill in between is finished from the
        # record rather than left for another person to notice.
        existing = _existing_copy(dest_folder, source, digest,
                                  ignore=parked if parked_here else None)
        if existing is not None:
            filed_as, target = existing.name, existing
            reused = True
            if parked_here and sha256_of(parked) == digest:
                # The attempt's copy stands in for it, byte for byte.
                parked_stood_in = True
                ops.append(_op(engagement_dir, ledger.OP_REMOVE, parked, digest=digest))
        elif parked_here and sha256_of(parked) == digest:
            moved = True                  # keeps any notes a person made on it
            ops.append(_op(engagement_dir, ledger.OP_MOVE, parked, target, digest))
        else:
            if parked_here:
                left_in_review = (
                    f"the parked copy {here} no longer holds the bytes this row "
                    f"recorded (annotated, or re-saved) and was left there; {filed_as} was copied from the original"
                )
            ops.append(_op(engagement_dir, ledger.OP_COPY, source, target, digest))

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
        # A spelling taught here rides the same transaction, for the same
        # reason the keyword does: a filing that teaches is one decision,
        # and half of it would be a return that never learned the name.
        spelled, said, spelling_note = _taught_spelling(engagement_dir, spelling)
        taught += spelled
        # The intent carries the keyword too: a filing recovered from the
        # record is the whole of the decision the person made, and half of
        # it would be a request that never learned the word.
        _intend(engagement_dir, ledger_key(new_entry), ops, by=ledger.BY_PERSON,
                row=entry_to_json(new_entry), then=ledger.ASSIGNED_BY_PERSON, also=taught)
        for op in ops:
            _do_op(engagement_dir, op)
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
                # The files are back where the record says, so the move is
                # not to be finished forward by the next pass (decision 119).
                _abandon(engagement_dir, ledger_key(new_entry))
            raise
    return AssignResult(
        entry=new_entry, moved_review_copy=moved, keyword=keyword if not note else "",
        keyword_note=note, left_in_review=left_in_review, overrode_shortlist=overrode,
        spelling=said, spelling_note=spelling_note,
    )


def find_parked(
    entries: list[IndexEntry], original: str, *, accepting: Sequence[str] = ()
) -> int:
    """Index of the row ``original`` names; the newest parked row wins a name.

    A row a person has already said is ``NOT_REQUESTED`` is parked too: its
    working copy is still in ``REVIEW_DIR_NAME``, nothing was moved, and
    filing it is how that decision is undone. Only the two parked decisions
    are a person's to act on; anything else names itself in the refusal.

    ``accepting`` is the decisions the *action* will take beyond those two,
    named by the action rather than assumed here (decision 110): filing a
    moved copy where it now sits is a decision a person may make and
    setting a request aside for it is not, so keep-it-here passes
    ``FILE_MOVED`` and ``dismiss`` passes nothing and refuses it by name.

    Public since decision 112, because the caller that draws the card has
    to find the same row this module will act on to say what the evidence
    pointed at; the underscored name is kept for one release.
    """
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision in _PARKED or entry.decision in accepting:
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
    original in the year's folder is untouched, because a document the client
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
        _refuse_if_a_move_is_open(engagement_dir)
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
    guessing. A person who wants one back says which, in the app's editor,
    where each taught word has its own button (decision 113,
    ``manifest.unlearn_keyword``); unfiling takes nothing back.
    Refiling is unfiling and then filing.

    A ``FILE_MOVED`` row comes back from here too - decision 110's "send
    it to review", for a copy that was moved by mistake and belongs under
    nothing in particular: the copy that goes back is then the wanderer the
    row's reason names, and a row whose bytes are nowhere under
    ``PREPARED_DIR_NAME`` is copied from the original, exactly as this
    already does for a row whose working copy is no longer its own. A page
    decision 94 filed under several requests is refused
    (``SEVERAL_COPIES_REFUSAL``) and put back with
    :func:`restore_working_copy` first.

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
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_filed(entries, original, accepting=(FILE_MOVED,))
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        if entry.decision == FILE_MOVED and entry.also_filed:
            # As for keep-it-here: which of a decision-94 page's copies is
            # meant is not guessable, and put-it-back answers for all of them.
            raise FilingError(SEVERAL_COPIES_REFUSAL.format(name=entry.original_name))
        source = locate(engagement_dir, entry.pbc_location)
        # Every working copy this row has: one, or one per request where
        # decision 94 filed the page under several. A copy is only this
        # row's while it is here, hydrated, not claimed by a later row,
        # and still the bytes the row recorded. Any other file at that
        # path is somebody else's document and is not carried back to
        # review under this row's name. The path check is the first copy's
        # (the index's own column is what a later row can take); for the
        # rest the bytes are the whole test, and they are the stronger one.
        taken = _copy_taken_by_a_later_row(entries, position)
        # Where to look, and which of those paths the index itself can say
        # is somebody else's. On a ``FILE_MOVED`` row (decision 110's "send
        # it to review") the copy that goes back is the wanderer, and it is
        # looked at first; a row whose bytes are nowhere has none, and the
        # copy comes from the original exactly as it does for any row whose
        # working copy is no longer its own.
        candidates: list[tuple[str, bool]] = [
            (location, index == 0) for index, location in enumerate(entry.filed_locations)
        ]
        if entry.decision == FILE_MOVED:
            now = moved_to(entry)
            if now:
                candidates.insert(0, (now, False))
        mine: list[Path] = []
        strangers: list[str] = []
        for location, is_the_named_copy in candidates:
            copy = locate(engagement_dir, location)
            if not copy.is_file() or is_cloud_placeholder(copy):
                continue
            if is_the_named_copy and taken:
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
                    f"{entry.pbc_location} is no longer there; there is nothing to put back"
                )
            if is_cloud_placeholder(source):
                raise FilingError(f"the original {entry.pbc_location} is still syncing; try again when it is here")

        review_dir.mkdir(parents=True, exist_ok=True)
        parked = _unique_path(review_dir, entry.original_name)
        left_filed = "; ".join(
            LEFT_FILED.format(location=location, parked=parked.name) for location in strangers
        )
        # A page decision 94 filed under several requests has a copy in
        # each, and every one of them has to leave its request folder or
        # the scan goes on counting the document this row no longer
        # claims. One goes back under the client's name; the rest are
        # these same bytes over again, and a copy is disposable - the
        # original in the year's folder is the record, and the copy that
        # went back is byte for byte the one removed here.
        stood_down: list[Path] = list(mine[1:]) if still_the_rows else []
        if still_the_rows:
            # The move keeps any notes a person made on the copy.
            ops = [_op(engagement_dir, ledger.OP_MOVE, working, parked, entry.digest)]
            ops += [_op(engagement_dir, ledger.OP_REMOVE, copy, digest=entry.digest)
                    for copy in stood_down]
        else:
            ops = [_op(engagement_dir, ledger.OP_COPY, source, parked, entry.digest)]

        new_entry = replace(
            entry,
            identifier="",
            prepared_location=prepared_location(review_dir, parked.name),
            decision=NEEDS_REVIEW,
            reason=f"{UNFILED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}",
            also_filed="",
        )
        entries[position] = new_entry
        _intend(engagement_dir, ledger_key(new_entry), ops, by=ledger.BY_PERSON,
                row=entry_to_json(new_entry), then=ledger.UNFILED_BY_PERSON)
        for op in ops:
            _do_op(engagement_dir, op)
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
                _abandon(engagement_dir, ledger_key(new_entry))
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


def find_filed(
    entries: list[IndexEntry], original: str, *, accepting: Sequence[str] = ()
) -> int:
    """Index of the row ``original`` names; the newest ``FILED`` row wins a name.

    :func:`find_parked`'s shape over the other decision: what a person may
    unfile is what the index says is filed, whoever filed it. A row that is
    anything else names what it is in the refusal, because the answer to
    "this is in the wrong place" is different for each of them.
    ``accepting`` widens it exactly as it widens the other (decision 110):
    send-to-review passes ``FILE_MOVED``, because a copy nobody meant to
    move is a copy that may go back to review.

    Public since decision 112, beside :func:`find_parked`; the underscored
    name is kept for one release.
    """
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision == FILED or entry.decision in accepting:
                return position
            if entry.decision == DUPLICATE and entry.original_name == wanted:
                continue          # a re-send under the same name; the filed row is older
            raise FilingError(f"{entry.original_name} is not filed (it is {entry.decision})")
    raise FilingError(f"nothing in the index is called {original!r}")


#: The name this lookup had while it was the filer's alone; kept for one
#: release, as the module does elsewhere.
_find_filed = find_filed


# --------------------------------------------------------------- recovery ----


#: What a put-back says when the wanderer itself went home. The row keeps
#: the history it had (109's sentence is taken off and this one appended in
#: its place), so what a person reads is where the copy is now and what it
#: was before it wandered.
PUT_BACK = "put back at {home} on {date} from {now}"
#: The same, for a row whose copy is nowhere in the firm's folder any more:
#: a working copy is a copy of the original, and the original is the record.
PUT_BACK_FROM_ORIGINAL = ("put back at {home} on {date} from the original {pbc}; "
                          "nothing under {prepared} held it")
#: The row when the bytes were already home. Nothing is moved and nothing
#: is deleted - the machine never deletes - so the wanderer stays where it
#: is and the sweep goes on naming it until a person removes it by hand.
PUT_BACK_ALREADY = ("already back at {home} on {date}; {now} holds the same bytes and was "
                    "left for a person to remove")
#: The owner's rule, 2026-09-19: nothing is overwritten. A file at home
#: that is not this document is somebody's - the sweep says every pass that
#: nothing on the record put it there - so it stays, this document's copy
#: goes to review under the client's own name, and the row parks naming
#: both, so a person answers it with File it or Not requested.
PUT_BACK_REFUSED = ("put back refused on {date}: {home} holds a different file, which was left; "
                    "this document's copy went to review as {parked}")
#: Why keep-it-here and send-to-review refuse a page decision 94 filed under
#: several requests: which of its copies the person means is not the
#: machine's to guess, and put-it-back answers for every one of them.
SEVERAL_COPIES_REFUSAL = "{name} has copies under several requests; put it back, then unfile it"


@dataclass(frozen=True, slots=True)
class RestoreResult:
    """What putting one moved working copy back did."""

    entry: IndexEntry            # the rewritten index row
    moved_home: bool             # the wanderer itself was moved to the home path
    copied_from_original: bool   # nothing under Prepared/ held the bytes; the year's folder did
    already_home: bool           # home held the bytes; the wanderer was left alone
    parked_as: str = ""          # the refusal: where this document's copy went instead
    scan_note: str = ""          # why the re-scan did not land, when it did not


def find_moved(entries: list[IndexEntry], original: str) -> int:
    """Index of the row ``original`` names; the newest ``FILE_MOVED`` row wins.

    :func:`find_parked`'s shape over the decision the sweep writes. A row
    that is anything else names what it is in the refusal: put-it-back is an
    answer to "the copy is not where the record put it", and a row nobody
    said that about has nothing to put back.
    """
    wanted = original.replace("\\", "/").strip()
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if entry.pbc_location == wanted or entry.original_name == wanted:
            if entry.decision == FILE_MOVED:
                return position
            if entry.decision == DUPLICATE and entry.original_name == wanted:
                continue          # a re-send under the same name; the moved row is older
            raise FilingError(f"{entry.original_name} is not a moved copy (it is {entry.decision})")
    raise FilingError(f"nothing in the index is called {original!r}")


def _holds_the_row(path: Path, digest: str) -> bool:
    """Whether this file is here, readable now, and the row's own bytes.

    A person's click, not the unchanged-tree path: the file is read rather
    than remembered, because what is about to be moved is proved in the
    moment it is moved. A placeholder is never read (hashing one would make
    the sync client download it) and is not here as far as this is
    concerned - the caller refuses first, so it never reaches this.
    """
    return path.is_file() and not is_cloud_placeholder(path) and sha256_of(path) == digest


def restore_working_copy(
    engagement_dir: Path | str,
    original: str,
    *,
    seq: int | None = None,
    today: dt.date | None = None,
) -> RestoreResult:
    """Put one moved working copy back where the record put it.

    The first of decision 110's three answers to a ``FILE_MOVED`` row, and
    the only one that needs no other place for the file to go: the bytes
    return to the path the row's Prepared Location names - the wanderer
    moved home when it still holds them, a fresh copy made from the
    client's original when nothing under ``PREPARED_DIR_NAME`` does - and
    the row goes back to what it was before it wandered, ``FILED`` when it
    names a request and ``NEEDS_REVIEW`` when it does not (109's rule for a
    copy dragged back by hand).

    Three things it will not do, each one the owner's, 2026-09-19:

    - **It never overwrites.** A file already at home that is *not* this
      document is somebody's, and it stays exactly where it is; this
      document's copy goes to ``REVIEW_DIR_NAME`` under the client's own
      name instead and the row parks naming both, so both files are on
      disk and a person decides with the card.
    - **It never deletes.** Where home already holds these bytes there is
      nothing to move: the row is restored and the wanderer is left, and
      the sweep goes on saying it is unrecorded until a person removes it.
    - **It never guesses.** ``seq`` is checked first (decision 112), every
      byte it is about to move is read second, and only then does anything
      move; a record that refuses the decision puts the file back.

    A page decision 94 filed under several requests has a copy in each, and
    every one of them is put back - which is why keep-it-here and
    send-to-review refuse such a row and point here.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    stamp = today.isoformat()
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_moved(entries, original)
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        if not entry.digest:
            # Decision 65: a row preserved without its bytes is tied to
            # nothing, so there is nothing to prove a copy against and
            # nothing this may safely move. It is said out loud every pass.
            raise FilingError(
                f"{entry.original_name} was recorded without its bytes, so nothing can be proved "
                "to be its working copy; the pass says so every run"
            )
        source = locate(engagement_dir, entry.pbc_location)
        now = moved_to(entry)
        wanderer = locate(engagement_dir, now) if now else None

        # Every location this row claims - one for nearly every row, one per
        # request for a page decision 94 filed under several - sorted into
        # what is already right, what is not there, and what is somebody
        # else's file. A placeholder is not read and not overwritten either:
        # the sync client has not finished, and the answer is to wait.
        absent: list[str] = []
        different: list[str] = []
        for location in entry.filed_locations:
            path = locate(engagement_dir, location)
            if not path.is_file():
                absent.append(location)
            elif is_cloud_placeholder(path):
                raise FilingError(f"{location} is still syncing; try again when it is here")
            elif sha256_of(path) != entry.digest:
                different.append(location)

        def the_original() -> Path:
            """The client's original, proved, or the refusal that names why."""
            looked = f"the copy at {now}" if now else f"nothing under {PREPARED_DIR_NAME}"
            if not source.is_file():
                raise FilingError(
                    f"{looked} holds this row's bytes and the original {entry.pbc_location} is no "
                    f"longer there; there is nothing to put back"
                )
            if is_cloud_placeholder(source):
                raise FilingError(
                    f"the original {entry.pbc_location} is still syncing; try again when it is here"
                )
            if sha256_of(source) != entry.digest:
                raise FilingError(
                    f"neither {looked} nor the original {entry.pbc_location} holds the bytes this "
                    "row recorded; look at the files first"
                )
            return source

        moved_home = copied_from_original = wanderer_moved = False
        parked: Path | None = None
        filled: list[Path] = []
        ops: list[dict] = []
        if different:
            # Refused, and nothing is touched at home. This document's copy
            # goes to review under the client's own name - the wanderer
            # itself when it still holds the bytes, a fresh one from the
            # original when nothing does - so the person has a working copy
            # to act on and both files are still on disk.
            review_dir.mkdir(parents=True, exist_ok=True)
            parked = _unique_path(review_dir, entry.original_name)
            if wanderer is not None and _holds_the_row(wanderer, entry.digest):
                ops.append(_op(engagement_dir, ledger.OP_MOVE, wanderer, parked, entry.digest))
                wanderer_moved = True
            else:
                ops.append(_op(engagement_dir, ledger.OP_COPY, the_original(), parked,
                               entry.digest))
                copied_from_original = True
            sentence = PUT_BACK_REFUSED.format(
                date=stamp, home=different[0],
                parked=prepared_location(review_dir, parked.name))
            new_entry = replace(
                entry, decision=NEEDS_REVIEW, identifier="", also_filed="",
                prepared_location=prepared_location(review_dir, parked.name),
                reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
            )
        elif not absent:
            # Already home: no file operation at all, and the wanderer -
            # a copy of the same document, by its bytes - is left for a
            # person to remove. A row that says its bytes are nowhere and
            # has them home again is the sweep's own sentence, worded once.
            sentence = (PUT_BACK_ALREADY.format(home=entry.prepared_location, date=stamp, now=now)
                        if now else MOVED_BACK_SENTENCE.format(
                            home=entry.prepared_location, date=stamp))
            new_entry = replace(
                entry, decision=FILED if entry.identifier else NEEDS_REVIEW,
                reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
            )
        else:
            home = locate(engagement_dir, absent[0])
            if wanderer is not None and _holds_the_row(wanderer, entry.digest):
                ops.append(_op(engagement_dir, ledger.OP_MOVE, wanderer, home, entry.digest))
                moved_home = wanderer_moved = True
                sentence = PUT_BACK.format(home=absent[0], date=stamp, now=now)
            else:
                ops.append(_op(engagement_dir, ledger.OP_COPY, the_original(), home,
                               entry.digest))
                copied_from_original = True
                sentence = PUT_BACK_FROM_ORIGINAL.format(
                    home=absent[0], date=stamp, pbc=entry.pbc_location,
                    prepared=PREPARED_DIR_NAME)
            filled.append(home)
            # Decision 94's other copies, if this row has any: each is these
            # same bytes over again, and the one just put back is them - so
            # each is copied from it, in the order the intent says, and a
            # recovery that finishes this finds them in that order too.
            for location in absent[1:]:
                other = locate(engagement_dir, location)
                ops.append(_op(engagement_dir, ledger.OP_COPY, home, other, entry.digest))
                filled.append(other)
            new_entry = replace(
                entry, decision=FILED if entry.identifier else NEEDS_REVIEW,
                reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
            )

        entries[position] = new_entry
        _intend(engagement_dir, ledger_key(new_entry), ops, by=ledger.BY_PERSON,
                row=entry_to_json(new_entry), then=ledger.RESTORED_BY_PERSON)
        for op in ops:
            _do_op(engagement_dir, op)
        try:
            _record(engagement_dir, before, entries,
                    decided={ledger_key(new_entry): ledger.RESTORED_BY_PERSON})
        except BaseException:
            # The same rule as every other person's decision: the record
            # took it or it did not, so exactly what moved goes back and a
            # retry does this once rather than twice.
            if not _the_record_holds(engagement_dir, new_entry):
                try:
                    if parked is not None:
                        if wanderer_moved:
                            _move_whole(parked, wanderer)
                        else:
                            parked.unlink(missing_ok=True)
                    else:
                        for copy in filled[1:]:
                            copy.unlink(missing_ok=True)
                        if wanderer_moved and filled:
                            _move_whole(filled[0], wanderer)
                        elif filled:
                            filled[0].unlink(missing_ok=True)
                except (OSError, FilingError) as undo:
                    log.error("Could not put %s back after the record refused it: %s",
                              entry.original_name, undo)
                _abandon(engagement_dir, ledger_key(new_entry))
            raise

    # Outside the lock, as the unfiling's is: the request this row answers
    # has its file again (or has lost it to review), and the status says so
    # now rather than at the next scheduled pass.
    return RestoreResult(
        entry=new_entry, moved_home=moved_home, copied_from_original=copied_from_original,
        already_home=not different and not absent,
        parked_as=prepared_location(review_dir, parked.name) if parked is not None else "",
        scan_note=_rescan(engagement_dir, today),
    )


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    from contextlib import ExitStack
    from contextlib import nullcontext as _nothing

    from tracker.households import household_returns
    from tracker.layout import household_of

    parser = argparse.ArgumentParser(
        description="Sort the household's inbox into the year's folder of originals and "
                    f"each return's {PREPARED_DIR_NAME}/"
    )
    parser.add_argument("engagement_dir", help="a return folder of the household")
    parser.add_argument(
        "--dry-run", action="store_true", help="decide everything, move nothing"
    )
    ns = parser.parse_args()

    # One inbox feeds every return of the household (decision 125), so a
    # command line pointed at one return sorts the whole inbox and takes
    # every return's lock, in folder-name order, before anything is read -
    # the same order the scheduled pass takes them in.
    asked = Path(ns.engagement_dir)
    every = household_returns(household_of(asked)) or [asked]
    with ExitStack() as locks:
        if not ns.dry_run:
            for folder in every:
                locks.enter_context(engagement_lock(folder))
        else:
            locks.enter_context(_nothing())
        reports = file_household_drops(inbox_of(asked), originals_of(asked), every,
                                       dry_run=ns.dry_run)
    head = "Would sort" if ns.dry_run else "Sorted"
    failed = False
    for engagement_dir, result in reports.items():
        print(f"{head} {result.handled} file(s) for {engagement_dir}\n")
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
        failed = failed or bool(result.errors)
        if not ns.dry_run and result.handled:
            print(f"\n  Recorded in {ledger.LEDGER_FILENAME} and the store")
    if failed:
        raise SystemExit(1)
