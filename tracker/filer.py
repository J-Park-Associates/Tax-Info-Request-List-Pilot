"""Sort the client's drop folder into a working set (component 7).

The client sees one folder and drops everything into it. This module turns
that pile into two things:

The year's folder, in the tree a client is shared
    Every document the client provided, moved out of the drop zone but left
    completely untouched — same bytes, same filename. This is the
    provided-by-client record, and the client can still see it.

``PREPARED_DIR_NAME/``
    A renamed copy of each identified document, on the firm's side of the
    engagement, named to one convention so a preparer can work the return
    without opening the client's filing habits: the request's identifier,
    its short name and its period (``A01 - W-2 - TY2025.pdf``, decision
    144). **The copies sit side by side in the one folder** (decision 168):
    the name already says which request a copy is for, and a request's
    copies sort together by it, so the folder per request that held them
    until then was a second copy of the name's first half. Which request a
    file belongs to is its name's - the longest identifier it starts with
    (``tracker.scaffold.assign_files``) - and nothing is ever filed into a
    folder inside ``PREPARED_DIR_NAME`` other than the review folder.

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
- **A file from a subfolder of the drop keeps its name, and its row keeps
  the subfolder** (decision 147). The year's folder is flat (decision 125): a file from a
  subfolder moves in under its own name, and its row says which subfolder
  it came from. It is numbered ``(n)`` only where another file has that
  name - on the disk, or on a row that still names it - and the inbox is
  read top level first, so the file the client put at the top keeps it.
  A name a deleted original left is never handed to a different file.
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
- **A working copy that is simply gone is made again, never asked for
  again** (decision 157). A copy gone from where the record put it, whose
  bytes are nowhere else under ``PREPARED_DIR_NAME``, is copied again from
  the row's own original, proved against the row's fingerprint, and the
  row says so; the request's status does not move and the client is never
  asked. Where the original is gone too, the row says both are gone, the
  request is held for a person, and only that person's Mark missing asks
  the client again. An original that comes back into the inbox - the one
  row whose recorded original is gone holds its bytes - goes back to that
  place with no new row, and no new original ever takes a place a row
  names.
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
- **A working copy is whole or not there, and writable** (decision 155).
  It is copied to a temp name beside its home, proved against the bytes
  it was made from, flushed and renamed into place
  (:func:`tracker.fsio.copy_atomically`), so a copy the power cut in half
  never holds the proper name - its temp is left, and
  :func:`sweep_stranded_temps` takes that away at the start of the next
  household pass. A copy of a read-only original is made writable; the
  original is only ever read.
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
import hashlib
import logging
import ntpath
import os
import posixpath
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path

from tracker import containers, ledger, reasons, store
from tracker.content_check import RETIRED_CACHE_FILENAME, ContentCache
from tracker.fsio import (
    TEMP_SUFFIX,
    copy_atomically,
    is_link,
    make_writable,
    stranded_temps,
    temp_owner,
    write_bytes_atomically,
)
from tracker.households import household_returns
from tracker.layout import (
    CLIENTS_TREE,
    INBOX_DIR_NAME,
    MAX_PATH_LENGTH,
    OPENED_DIR_NAME,
    PATH_TOO_LONG,
    PRIVATE_TREE,
    deepest_path_length,
    household_name_of,
    household_of,
    inbox_of,
    is_year_folder,
    limit_for,
    locate,
    location_of,
    lock_order_key,
    opened_dir_of,
    originals_of,
    root_of,
    year_of,
)
from tracker.layout import (
    label_for as label_for_return,
)
from tracker.locking import (
    EngagementLockedError,
    acquire_lock,
    engagement_lock,
    lock_is_held,
    pid_alive,
    release_lock,
)
from tracker.manifest import (
    ANY_EXTENSION,
    DEFAULT_EXTENSIONS,
    LABEL_SEPARATOR,
    ManifestError,
    Override,
    RequestItem,
    is_reserved_name,
    label_for,
    list_head,
    load_engagement_info,
    load_manifest,
    override_label,
    refuse_a_stale_list,
    renamed_rules,
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
    Received,
    ReceivedLine,
    UnderReview,
    as_pattern,
    entry_from_json,
    entry_to_json,
    format_answers,
    format_evidence,
    identifier_key,
    is_a_spelling,
    ledger_key,
    name_words,
    parse_evidence,  # noqa: F401
    person_to_json,
)
from tracker.router import read_once, route_file
from tracker.scaffold import (
    OTHER_DOCUMENT,
    PREPARED_DIR_NAME,
    README_CLIENTS,
    README_NAME,
    README_UNKNOWN,
    REVIEW_DIR_NAME,
    assign_files,
    matches_identifier,
    owner_of,
    readme_returns,
    sanitize_component,
    whose_readme,
    write_readme,
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
    too_large_reason,
)

log = logging.getLogger("tracker.filer")

#: What the index's section is called wherever it is shown - the word a
#: person knows it by and the Status Report's own section heading
#: (:mod:`tracker.view`).
INDEX_HEADING = "Index"
_MAX_STEM = 110
#: How many of a run's slowest readings the report keeps (decision 127).
#: Five, because the number is read to answer "is the pass getting slow?",
#: which one outlier cannot answer and a whole list nobody reads.
SLOWEST_READINGS = 5


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
#: 2026-09-19): what the scanner says about a request is what Prepared
#: holds under its name, and "the copy is not where I put it" is a fact about the
#: document. The row keeps its home in ``prepared_location`` and says where
#: the bytes are now in its Reason (:func:`moved_to` reads it back);
#: nothing is moved, and a person decides. A copy dragged back is filed
#: again on the next pass.
FILE_MOVED = "File Moved"
#: An email or a zip the pass opened (decision 143): each attachment was
#: taken out into the household-year's hidden folder in the private tree
#: (``layout.OPENED_DIR_NAME``) and sorted as a document of its own, with a
#: row that names this one as its ``container``. The container's row
#: belongs to no request and counts in no request's figures; its Reason
#: says how many documents came out (:data:`OPENED_SENTENCE`), and the
#: journal line (``ledger.OPENED``) names each of them and each part left.
#: The container itself rests in the client's folder for the year like any
#: original, untouched.
OPENED = "Opened"
#: What an opened container's row says, once, on the Index and the Status
#: Report: how many documents came out, and how many parts were left (the
#: message's text, an inline picture, an attachment by reference).
OPENED_SENTENCE = "opened: {n} {documents}"
OPENED_SKIPPED = "{m} part(s) left inside (named in the record)"

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
#: And of an email or a zip already opened (decision 143): its attachments
#: are rows of their own already, so nothing is taken out again.
DUPLICATE_OF_OPENED = "identical to {name}; already opened, and each attachment sorted"
#: A re-send of bytes a person set aside: the earlier decision, quoted whole
#: (it carries the date and the note), and the fact. Decision 76 amended.
RESENT_AFTER_SET_ASIDE = "set aside as not requested ({earlier}); the client sent it again"

#: Reason prefix on index rows a person filed from REVIEW_DIR_NAME.
ASSIGNED_BY_PERSON = "assigned by a person"
#: Reason prefix on index rows a person said no request asks for.
DISMISSED_BY_PERSON = "not requested, by a person"
#: Reason prefix on index rows a person sent back to REVIEW_DIR_NAME.
UNFILED_BY_PERSON = "unfiled by a person"
#: What a consolidated statement's row says when a person marks one of the
#: requests it answered missing again (decision 146): appended to the
#: Reason, so the row keeps why it was filed and says what the person took
#: back, when, and why if they said.
MARKED_MISSING = "{identifier} marked missing again by a person on {date}{note}"
#: What the journal line that releases a row says (decision 132): which
#: return took the document, by its label, and under which request. A
#: label, never a member of any household - the record names folders and
#: returns and no person outside the firm. The row itself is gone from the
#: index; this sentence is the ``reason`` of the ``released`` line, and the
#: runner's log says it when a recovery finishes a release.
RELEASED_TO = "released to {label} ({identifier}) by a person"

#: The decisions that leave a document waiting in ``REVIEW_DIR_NAME`` for a
#: person, and which a person may therefore act on: one nobody has looked at
#: yet, and one somebody has said no request asks for. A ``FILE_MOVED`` row
#: is deliberately not among them: its copy is somewhere nobody meant it to
#: be, and the answer to that is its own (decision 110's three buttons),
#: which the two lookups take as ``accepting`` from the action that offers
#: them - keep it here and send it to review - and which ``dismiss`` does
#: not, because setting a request aside says nothing about a file nobody
#: can find (decision 76). A document a person filed under another return
#: leaves no row here at all (decision 132), so there is nothing of it
#: left in this queue to act on.
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
    #: The emails and zips this run opened (decision 143): the container
    #: rows. What came out of each is in ``filed``, ``review`` and
    #: ``duplicates`` like any drop.
    opened: list[IndexEntry] = field(default_factory=list)
    waiting: list[Path] = field(default_factory=list)   # cloud-only, left alone
    errors: list[FileError] = field(default_factory=list)
    #: Originals already sorted whose record no longer fits what is on disk
    #: (replaced under their name; recorded without bytes and now untied).
    #: Said every pass for a person, but nothing was left unsorted, so the
    #: pass is not a failure.
    attention: list[FileError] = field(default_factory=list)
    #: The run's slowest readings, longest first, at most
    #: :data:`SLOWEST_READINGS` of them: (the document's own name, seconds).
    #: Decision 127 - a reading is timed and said, never cut short, and the
    #: run's summary names one of these when it passed the run's threshold.
    slowest: list[tuple[str, float]] = field(default_factory=list)
    dry_run: bool = False

    @property
    def handled(self) -> int:
        return len(self.filed) + len(self.review) + len(self.duplicates) + len(self.opened)

    def timed(self, name: str, seconds: float) -> None:
        """Record how long one document's reading took, keeping the slowest."""
        if seconds <= 0:
            return
        self.slowest.append((name, seconds))
        self.slowest.sort(key=lambda reading: -reading[1])
        del self.slowest[SLOWEST_READINGS:]


# ------------------------------------------------------------------ names ----


#: The numbered suffix a shortest name leaves room for: two digits, so a
#: request expecting a dozen files still fits the room it was measured in.
_ROOM_COUNTER = 99


def _parts_of(item: RequestItem) -> tuple[str, str, str]:
    """A request's identifier, short name and period as a file name spells
    them. The short name stands where the document title stood until
    decision 144 (``RequestItem.short_name``), so everything below that
    says "the document part" cuts the short name, first and alone."""
    return (sanitize_component(item.identifier), sanitize_component(item.short_name),
            sanitize_component(item.period) if item.period else "")


def _stem_of(identifier: str, document: str, period: str) -> str:
    """``label_for(identifier, document, period)`` capped at ``_MAX_STEM``.

    The cap cuts the **document part**, never the period (decision 131's
    review): a long label once lost the year from the end of the name,
    which is the one part that says which year a copy belongs to. Only an
    identifier and a period that are themselves past the cap are cut whole.
    """
    stem = label_for(identifier, document, period)
    for keep in range(len(document) - 1, -1, -1):
        if len(stem) <= _MAX_STEM:
            break
        stem = label_for(identifier, document[:keep].rstrip(". -"), period)
    return stem[:_MAX_STEM].rstrip(". ")


def _named(stem: str, counter: int, suffix: str) -> str:
    """The first name of a series, or its ``counter``-th (:func:`numbered`)."""
    return f"{stem}{suffix}" if counter == 1 else numbered(stem, counter, suffix)


def _fitted(identifier: str, document: str, period: str, counter: int, suffix: str,
            room: int | None) -> str | None:
    """The ``counter``-th name of a request's series cut to ``room``
    characters, or None when not even its shortest form fits.

    Only the **document part** is cut, from its end (decision 131): the
    identifier the copy is found by, the period that says which year,
    the numbered suffix that keeps a series one series and the extension a
    program opens it by are never cut. ``None`` for ``room`` is no limit:
    the canonical name, exactly as it was before there was a room.
    """
    name = _named(_stem_of(identifier, document, period), counter, suffix)
    if room is None or len(name) <= room:
        return name
    for keep in range(len(document) - 1, -1, -1):
        name = _named(_stem_of(identifier, document[:keep].rstrip(". -"), period), counter, suffix)
        if len(name) <= room:
            return name
    return None


def prepared_name_for(item: RequestItem, extension: str, taken: set[str], *,
                      room: int | None = None) -> str:
    """Canonical working-copy name: ``label_for(identifier, short name, period)`` plus the extension.

    ``taken`` holds names already used in ``PREPARED_DIR_NAME`` - every
    request's copies share it since decision 168, and two requests' names
    can never collide because they differ at the identifier; collisions
    get ``(2)``, ``(3)``… so a request expecting several files keeps them in
    one predictable series, sorted together.

    ``room`` is how many characters the whole file name may take - the
    caller's ``limit_for(extension) - len(str(prepared_dir)) - 1`` - and
    ``None`` is the canonical name exactly (creation's measure passes none;
    every writer passes one). A name longer than its room is **cut to fit**
    (decision 131): the document part alone, from its end, with the
    numbered suffix counted, because the suffix is chosen in the same
    loop - the ``n``-th copy of a series is the ``n``-th whatever its cut.
    When not even the identifier, the period, the suffix and the extension
    fit, :class:`NoRoom` says so with both numbers, and the caller decides:
    the pass parks the document, a person is refused.
    """
    identifier, document, period = _parts_of(item)
    suffix = f".{extension}" if extension else ""
    counter = 1
    while True:
        candidate = _fitted(identifier, document, period, counter, suffix, room)
        if candidate is None:
            shortest = _named(_stem_of(identifier, "", period), counter, suffix)
            limit = limit_for(extension)
            raise NoRoom(limit - room + len(shortest), limit, extension)
        if candidate.lower() not in taken:
            taken.add(candidate.lower())
            return candidate
        counter += 1


def shortest_name_for(item: RequestItem, extension: str) -> str:
    """The shortest name a working copy of ``item`` can take: the identifier,
    the period, room for a two-digit numbered suffix and the extension
    (decision 131). What :func:`room_for` measures a request's floor by."""
    identifier, _document, period = _parts_of(item)
    return numbered(_stem_of(identifier, "", period), _ROOM_COUNTER,
                    f".{extension}" if extension else "")


def prepared_location(folder: Path, name: str) -> str:
    """Where a working copy is, relative to the engagement:
    ``PREPARED_DIR_NAME/<name>`` for a copy in the firm's folder itself
    (decision 168), ``PREPARED_DIR_NAME/<folder>/<name>`` for one in a
    folder inside it - the review folder, or a person's (one a person
    named ``Prepared`` too is still inside it)."""
    if folder.name == PREPARED_DIR_NAME and folder.parent.name != PREPARED_DIR_NAME:
        return f"{PREPARED_DIR_NAME}/{name}"
    return f"{PREPARED_DIR_NAME}/{folder.name}/{name}"


#: A request whose folder leaves no room for even the shortest working-copy
#: name: the document parks, and this is the row's reason (a firm-side
#: reason; it carries no ask, like the three of decision 128). A person's
#: filing and a hand-over are refused with the same sentence.
#: Every sentence names the limit as the limit **of that kind of copy**
#: (``{ext}`` is ``.xlsx``, or ``working`` for a file with no extension),
#: never as what Windows allows: since the owner's Q-A a spreadsheet's
#: limit is a reader's 218, not Windows's 260 (decision 131's review, F2).
PATH_NO_ROOM = ("the working copy's path would be {length} characters at its shortest, past the "
                "{limit} characters a {ext} copy may have; shorten the clients root, or this "
                "request's Short name in the editor")
#: The same, when the request that accepted the document is in a return
#: this household's drop folder feeds (decision 129): the document parks at
#: home, so "this request" would name a list the person is not looking at.
PATH_NO_ROOM_IN = ("the working copy's path in {label} would be {length} characters at its shortest, "
                   "past the {limit} characters a {ext} copy may have; shorten the clients root, or "
                   "that request's Short name in {label}'s list in the editor")
#: A return whose review folder leaves no room for a copy at all: nothing
#: in its household is sorted this pass. The household's skip sentence.
HOUSEHOLD_NO_ROOM = ("no room under {label} for even a review copy ({length} characters at its shortest, "
                     "past the {limit} characters any copy may have); nothing in this household is "
                     "sorted until the clients root is shorter")
#: A review copy that cannot be named to fit even cut to one character -
#: a drop whose suffix is a real extension and whose folder leaves almost
#: nothing. Said as a *review copy*, never as a request's label: no request
#: is involved (decision 131's review, F4).
REVIEW_NO_ROOM = ("no review copy of {name} could be made: its path would be {length} characters at "
                  "its shortest, past the {limit} characters a {ext} copy may have; shorten the "
                  "clients root")
#: A review copy that could not be made for any other reason (a disk that
#: refused, a copy that did not come out as the original).
REVIEW_COPY_FAILED = "no review copy of {name} could be made ({problem})"
#: A review copy of a workbook fitted to Windows's 260 because a reader's
#: shorter limit left no room: it exists, and a spreadsheet program may not
#: open it where it is (decision 131's review, deviation 4).
REVIEW_COPY_PAST_READER = ("the review copy's path is longer than a spreadsheet program may open; "
                           "open it from a shorter folder")
#: What the return's page and the reply to setting the root say of a return
#: whose canonical copies no longer fit: the number, and the three levers a
#: person has. **Information, not a warning** (the lead's L-1): the names
#: are cut to fit and everything still files, and a warning that is on
#: every pass is a warning nobody reads.
ROOM_SHORT = ("{short} characters short of the room its working copies need, so their names are cut "
              "to fit; a shorter clients root, a request's Short name shortened in the editor, or a "
              "shorter return name at the next rollover gives it back")
#: The warning, when some request cannot receive at all.
ROOM_PARKS = ("{count} request(s) have no room for a working copy under this root; a document for "
              "them parks for a person until the clients root is shorter")


def _kind_of(extension: str) -> str:
    """How a sentence names a kind of copy: ``.xlsx``, or ``working``."""
    extension = extension.lower().lstrip(".")
    return f".{extension}" if extension else "working"


class NoRoom(FilingError):
    """Not even the shortest name fits the room left under its folder
    (decision 131). Carries both numbers and the extension; its sentence is
    :data:`PATH_NO_ROOM` unless the caller names another (a review copy's
    is :data:`REVIEW_NO_ROOM`), so a person's refusal needs no second
    wording."""

    def __init__(self, length: int, limit: int, extension: str = "", *,
                 sentence: str = "") -> None:
        self.length = length
        self.limit = limit
        self.extension = extension
        super().__init__(sentence or PATH_NO_ROOM.format(length=length, limit=limit,
                                                         ext=_kind_of(extension)))


@dataclass(frozen=True, slots=True)
class Room:
    """How much room a return's request list has under its folder, in
    characters, from the list alone (decision 131).

    ``need`` is creation's figure - the deepest canonical working copy over
    the active rows, at each row's longest extension - and what the refusal
    at creation and at the rollover still measures. ``least`` is the same
    at the shortest name each row can take (:func:`shortest_name_for`);
    ``floor`` is the review folder plus the shortest review-copy name at
    the longest extension the list allows. ``parks`` counts the rows whose
    shortest name does not fit the limit of one of their extensions.
    ``short`` is how far the deepest canonical copy passes the limit that
    applies to it - its own extension's (``layout.limit_for``), so a
    workbook measured against the 218 characters a reader allows is short
    where a PDF at the same depth is not; with no reader's limit in play it
    is ``need - limit``. ``limit`` is Windows's own.
    """

    need: int
    least: int
    floor: int
    parks: int
    short: int
    limit: int = MAX_PATH_LENGTH


def _extensions_of(item: RequestItem) -> list[str]:
    """The extensions a row's copies can have, as creation measures them."""
    return [e for e in (item.allowed_extensions or DEFAULT_EXTENSIONS)
            if e and e != ANY_EXTENSION] or list(DEFAULT_EXTENSIONS)


def room_for(engagement_dir: Path, items: Sequence[RequestItem]) -> Room:
    """The room one return's list has under its folder: one measure, one
    function (decision 131).

    **From the list alone** - no disk, no store, no lock - so the pass,
    the app's banner, the reply to setting the root and the editor's save
    all ask the same question and get the same answer, and a folder that
    does not exist yet is measured as readily as one that does. A row set
    Not Applicable is not measured, as creation does not measure it, and
    neither is a row nobody asked for (decision 142): the whole catalog's
    longest label must not refuse a return the preparer never asked that
    label of. Such a row is measured where its write happens - its name is
    cut to fit at filing time, or the document parks with this decision's
    room sentence.
    """
    engagement_dir = Path(engagement_dir)
    prepared = engagement_dir / PREPARED_DIR_NAME
    canonical: list[str] = []
    least = short = parks = 0
    longest_of_all = ""
    for item in items:
        if getattr(item, "manual_override", "") == Override.NOT_APPLICABLE:
            continue
        if not getattr(item, "asked", True):
            continue
        extensions = _extensions_of(item)
        longest = max(extensions, key=len)
        longest_of_all = max((longest_of_all, longest), key=len)
        # A working copy sits in the firm's folder itself (decision 168):
        # the path measured is PREPARED_DIR_NAME/<name>, one folder shorter
        # than it was while each request had a folder of its own.
        canonical.append(f"{PREPARED_DIR_NAME}/{prepared_name_for(item, longest, set())}")
        least = max(least, len(str(prepared / shortest_name_for(item, longest))))
        parked = False
        for extension in extensions:
            limit = limit_for(extension)
            short = max(short, len(str(prepared / prepared_name_for(item, extension, set()))) - limit)
            parked = parked or len(str(prepared / shortest_name_for(item, extension))) > limit
        parks += parked
    # The floor at the longest extension the list allows; a list with no
    # active row still parks everything, at the defaults' longest.
    longest_of_all = longest_of_all or max(DEFAULT_EXTENSIONS, key=len)
    review = prepared / REVIEW_DIR_NAME / numbered("x", _ROOM_COUNTER, f".{longest_of_all}")
    return Room(need=deepest_path_length(engagement_dir, canonical), least=least,
                floor=len(str(review)), parks=parks, short=max(0, short))


def refuse_a_path_past_the_limit(engagement_dir: Path, items: Sequence[RequestItem]) -> None:
    """Refuse a return whose deepest working copy would not fit in a path
    Windows will open.

    The deepest thing the tracker ever writes under a return is a working
    copy this module writes: ``PREPARED_DIR_NAME/<canonical name>`` (no
    folder per request since decision 168), over every active row of the
    list the call is about to record
    and the longest extension each row allows - :func:`room_for`'s
    ``need``. The client's own file names are not measured - they are the
    client's, and :func:`unreachable_drops` already says a name the index
    cannot hold - and neither are the ``..`` locations that cross the
    trees, because Windows normalises them away before the limit applies
    and :func:`tracker.layout.locate` normalises them first too.

    Decision 125 put this refusal on creation; decision 126 gave the
    household rollover the same one, and it lives here rather than in
    ``tracker.api`` because a rollover at layer 3 cannot reach the API at
    layer 5 - and because the file it measures is the one this module
    writes. Decision 131 gave the editor's save the same standard for the
    rows it changes, and measured every later write where it happens.
    """
    need = room_for(engagement_dir, items).need
    if need > MAX_PATH_LENGTH:
        raise ManifestError(PATH_TOO_LONG.format(
            folder=engagement_dir, length=need, limit=MAX_PATH_LENGTH))


def copies_of(item: RequestItem, items: Sequence[RequestItem], prepared_dir: Path) -> list[Path]:
    """The files in ``prepared_dir`` whose names belong to ``item``
    (decision 168): :func:`tracker.scaffold.assign_files` over the whole
    list, so a longer identifier keeps its own files - ``A01-B - Loan.pdf``
    is never ``A01``'s. Read live, because a filing is looking for a copy
    an earlier attempt made."""
    return assign_files(prepared_dir, [one.identifier for one in items]).get(item.identifier) or []


def _existing_copy(
    folder: Path, original: Path, digest: str, *, ignore: Path | None = None,
    among: Sequence[Path] | None = None,
) -> Path | None:
    """A file already in ``folder`` holding ``original``'s bytes, or None.

    ``among`` narrows the files looked at to these - a request's own copies
    (:func:`copies_of`), since every request's copies share
    ``PREPARED_DIR_NAME`` (decision 168): a page decision 94 filed under
    two requests has the same bytes under both names, and A01's copy is
    never the copy A02's filing reuses. Left out, every file in ``folder``
    is looked at, which is right for the review folder.

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
    for candidate in sorted(folder.iterdir()) if among is None else sorted(among):
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


def _copy_whole(
    source: Path, target: Path, *, expect: str = "", cache: ContentCache | None = None
) -> None:
    """Copy whole or not at all, proved against the bytes it was made from
    before it takes the proper name, and writable (decision 155).

    :func:`tracker.fsio.copy_atomically` does the copy: into a temp beside
    ``target``, flushed, renamed into place. A copy that stops part-way -
    disk full, a virus scanner holding the new file, **the power going out**
    - leaves no file under ``target``'s name. Until decision 155 it wrote
    straight onto the name, and a copy the power cut in half kept it: a
    truncated CSV passes the rules, so a request read Received on half a
    statement. A kill leaves the temp, which no walk reads and the next
    household pass sweeps (:func:`sweep_stranded_temps`). The original in
    the year's folder is the record; a copy is disposable.

    ``expect`` is the digest the copy must hold - the caller always knows
    it, because a copy is only ever made of bytes this system has already
    recorded. It is proved on the temp, before the rename: a copy that came
    out as something else never holds the proper name, not even for the
    moment a removal might be refused, and :class:`CopyMismatchError` says
    so, naming both files, so the drop is recorded as decision 17's "could
    not be filed" row rather than trusted and counted. A row recorded
    without its bytes (decision 65) has no digest to expect, and passes
    ``""``: there is nothing to prove it against, and that row is said out
    loud elsewhere.

    The temp's name is cut to fit Windows's limit where the target sits
    near it (``limit``): the target was named to fit decision 131's room,
    and its temp must not be what refuses the copy.

    ``cache`` is the pass's, where the caller has one: the copy keeps the
    modification time and the rename keeps the size, so the digest proved
    on the temp is remembered for ``target`` and the proof costs one read,
    once.
    """
    def prove(temp: Path) -> None:
        if not expect:
            return
        digest = _digest_or_none(temp)
        if digest != expect:
            raise CopyMismatchError(COPY_MISMATCH.format(
                source=source.name, target=target.name,
                expected=expect[:_DIGEST_SHOWN],
                found=(digest or "")[:_DIGEST_SHOWN] or "nothing",
            ))

    copy_atomically(source, target, prove=prove, limit=MAX_PATH_LENGTH)
    if expect and cache is not None:
        cache.remember_digest(target, expect)


def _digest_or_none(path: Path) -> str | None:
    """The file's bytes, or None where they could not be read."""
    try:
        return sha256_of(path)
    except OSError:
        return None


#: What a move refuses when the folder it would take a file out of is now
#: reached through a link (decision 137, L2).
MOVE_THROUGH_A_LINK = ("{name} is now reached through a link (a junction or a shortcut folder) "
                       "below {within}; nothing was moved")


class MovedThroughALinkError(OSError):
    """The source of a move is reached through a link now: nothing moved.

    An ``OSError``, because every caller of a move already treats one as
    "left in place" - which is exactly what happened."""


def _move_whole(source: Path, target: Path, *, within: Path) -> None:
    """Move by rename, and only by rename.

    ``shutil.move`` falls back to copy-and-delete when the rename is
    refused, and on Windows a file another program holds open (a scanner
    utility still writing it, a download in progress) refuses the rename
    but not the copy: the copy lands - truncated to whatever has been
    written so far - and the delete fails, so the caller hears "left in
    place" while a phantom sits in the target folder under the client's
    own name. A rename moves the whole file or nothing; the folders this
    moves between are in one engagement, on one volume.

    **The link check is made again here, immediately before the rename**
    (decision 137, L2). The walk that listed the file refused anything
    behind a junction, but the move comes later, and a folder of the drop
    swapped for a junction in between would have the rename fetch a file
    from wherever the junction points. ``within`` is the folder the walk
    started from (the inbox for a drop, the clients root for a recorded
    operation, the return for a rollback); every folder from the source up
    to it is asked again, and a link anywhere on that path moves nothing.
    """
    if is_link(source) or _through_a_link(source.parent, within):
        raise MovedThroughALinkError(MOVE_THROUGH_A_LINK.format(name=source.name, within=within))
    os.rename(source, target)


#: What a file name's suffix must look like to be kept whole when a review
#: copy's name is cut: a dot and a short run of letters and digits.
_AN_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,10}")


def _unique_path(
    folder: Path, name: str, *, room: int | None = None, spare: int = 0,
    recorded: Mapping[Path, str] | None = None, digest: str | Callable[[], str | None] = "",
    reuse: bool = False, claimed: set[Path] | None = None,
) -> Path:
    """A free path in ``folder`` for ``name``, never overwriting anything -
    **the one numbering function** (decision 147): an original out of the
    inbox, its second move into another household (:func:`_rests_at`), a
    person's hand-over, a review copy and what is taken out of an email or a
    zip (:func:`_take_out`) are all named here.

    ``room`` is how many characters the file name may take (decision 131):
    the stem is cut from its end to fit, keeping the extension and the
    numbered suffix, down to one character; below that, :class:`NoRoom`
    with :data:`REVIEW_NO_ROOM` - every caller that passes a room is naming
    a copy. ``None`` is no limit. Only ever a copy's name - an original is
    moved under its own name, uncut, always. ``spare`` is room kept beside
    the name for the temporary name an atomic write passes through; it is
    taken off ``room`` and counted in what :class:`NoRoom` reports.

    A suffix that is not an extension - ``Scan 2026.01.15 from the phone``
    has ``.15 from the phone`` for one - is no promise the pass's floor
    made, and keeping it whole could leave no room at all: with a room, such
    a name is cut as one stem, whatever its dots (decision 131's review, F4).
    A cut or a number never makes a device's name (decision 137, L6); the
    name as given is the caller's, and is never refused for being one.

    **A name is taken if the disk holds it, or a row still names it**
    (decision 147, ruling 9; audit F-1). ``recorded`` is every place the
    household-year's rows name as an original's resting place, each with
    that row's bytes (:func:`_on_record`), and every path an open intent
    will still write to, with none (:func:`_taken_names`). A client who deletes ``W2.pdf``
    from the year's folder and drops a corrected ``W2.pdf`` would otherwise
    have the new file take the old row's identity, and the old row would
    vanish from every reader.

    **No exception since decision 157.** Until then the row's own bytes
    coming back rested under its own name here - and were then sorted as a
    new arrival whose row, keyed by that very place, replaced the row it
    came back to (audit C5; 147's review, N-4). A name a row names is now
    taken whatever the bytes: the one road by which an original goes back
    to its row's recorded place is :func:`_put_back_home`, which writes no
    new row, and a same-bytes drop it does not take - two rows would answer,
    or the row's own original is still where it was - rests under a name of
    its own and is the Duplicate it always was, with a key of its own.

    ``reuse`` is decision 143's: a file already at a name holding these
    very bytes is that name (a pass killed after writing it). ``digest`` is
    what it compares, and may be a function, asked only when such a file is
    met. ``claimed`` is the names this caller has handed out already,
    skipped.
    """
    stem, suffix = Path(name).stem, Path(name).suffix
    if room is not None and suffix and not _AN_EXTENSION.fullmatch(suffix):
        stem, suffix = name, ""
    fits = None if room is None else room - spare
    asked: list[str | None] = []

    def incoming() -> str | None:
        if not asked:
            asked.append(digest() if callable(digest) else digest)
        return asked[0]

    counter = 1
    while True:
        fitted: str | None = _named(stem, counter, suffix)
        if fits is not None and len(fitted) > fits:
            cuts = (stem[:keep].rstrip(". ") for keep in range(len(stem) - 1, 0, -1))
            fitted = next((_named(cut, counter, suffix) for cut in cuts
                           if cut and len(_named(cut, counter, suffix)) <= fits), None)
            if fitted is None:
                length = len(str(folder / _named(stem[:1], counter, suffix))) + spare
                limit = len(str(folder)) + 1 + room
                raise NoRoom(length, limit, suffix, sentence=REVIEW_NO_ROOM.format(
                    name=name, length=length, limit=limit, ext=_kind_of(suffix)))
        target = folder / fitted
        counter += 1
        if (claimed is not None and target in claimed) or (fitted != name and is_reserved_name(fitted)):
            continue
        if target.exists():
            if reuse and target.is_file() and _digest_or_none(target) == incoming():
                return target
            continue
        if recorded and target in recorded:
            continue
        return target


def _on_record(engagements: Iterable[tuple[Path, Iterable[IndexEntry]]]) -> dict[Path, str]:
    """Every place these returns' rows name as an original's resting place
    (``pbc_location``), with that row's bytes - **the union** the pass
    reads the year's folder against (decision 125): a file one return's row
    holds is never another return's stray, and a name one return's row
    holds is never another file's (decision 147, ruling 9)."""
    return {
        locate(engagement_dir, entry.pbc_location): entry.digest
        for engagement_dir, entries in engagements
        for entry in entries if entry.pbc_location
    }


def _taken_names(recorded: dict[Path, str], intended: Iterable[Path]) -> dict[Path, str]:
    """``recorded`` with every path an open intent will write to added, as
    a name no bytes can claim back (decision 147): the one union
    :func:`_unique_path` is handed, rows and open intents together."""
    return {**recorded, **dict.fromkeys(intended, "")}


def _taken_in_the_year(first: _ReturnRun, runs: list[_ReturnRun]) -> dict[Path, str]:
    """Every name the pass's own household-year holds (decision 147, ruling
    9 and the review's N-1): the rows of **every** return of that year -
    the pass's own rows as they stand now, and the record's for a return
    the pass left out, one marked inactive while another of the same year
    is still worked - and every path an open intent will write to."""
    held = {run.engagement_dir: run.entries for run in runs}
    return _taken_names(_year_on_record(first.engagement_dir, held), first.context.intended)


def _year_on_record(engagement_dir: Path, held: Mapping[Path, list[IndexEntry]]) -> dict[Path, str]:
    """:func:`_on_record` for every return of ``engagement_dir``'s
    household-year: the rows in ``held`` for the returns the caller holds
    them for, the record's own for the rest - so a return the caller does
    not hold, one left out of the pass as inactive or one in a household
    the caller is not sorting, still counts. For every name a row could
    hold: the inbox move and what is taken out of a zip
    (:func:`_taken_in_the_year`), a filing's second move (decision 129) and
    a person's hand-over (decision 132). Read only; no lock is taken, and a
    return whose record cannot be read names nothing.
    """
    engagement_dir = Path(engagement_dir)
    year = engagement_dir.parent
    returns = [folder for folder in household_returns(household_of(engagement_dir))
               if folder.parent == year]
    pairs: list[tuple[Path, Iterable[IndexEntry]]] = []
    for folder in dict.fromkeys([*returns, *held]):
        if folder in held:
            pairs.append((folder, held[folder]))
            continue
        try:
            pairs.append((folder, read_index(folder)))
        except Exception as exc:      # a record nobody can read names nothing it can prove
            log.warning("Could not read %s's rows: %s", folder.name, exc)
    return _on_record(pairs)


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


# ------------------------------------------------- what the client is told ----
# Decision 130. The client README acknowledges what has arrived. The index
# is the one source of it: nothing new is stored, no counter and no copy,
# so the README is a rendering of the record and cannot drift from it.


#: The decisions a client is told a document was **Received** under: it was
#: confirmed into its request. A working copy moving afterwards
#: (``FILE_MOVED``) is the firm's business, not the client's.
_RECEIVED_DECISIONS = (FILED, FILE_MOVED)


def _day_of(stamp: str) -> dt.date | None:
    """The date part of a row's received stamp, or ``None`` where the stamp
    does not read as one - never a guessed day."""
    try:
        return dt.date.fromisoformat(str(stamp)[:10])
    except ValueError:
        return None


def _request_of_copy(name: str, items: Sequence[RequestItem]) -> str:
    """The request an ``also_filed`` copy's own name names, or ``""``.

    Read from the copy's file name since decision 168, by the test decision
    130 applied to its request folder until then, and only what the name
    can prove (130, the review's F1): it begins with the request's
    identifier followed by ``LABEL_SEPARATOR`` - which the canonical prefix
    (``A01 - W-2``, the identifier and the short name) always does, and is
    the one shape a working copy is made in and a person renames within.
    Or its stem is the identifier alone, or the identifier followed by
    `` (`` - ``A01.pdf``, ``A01 (2).pdf``: a copy whose short name decision
    131's room cut away whole on a row with no period (the review of 168,
    N-4). A bare prefix proves nothing: once ``A01-B`` is deleted from the
    list, ``A01-B - Loan - TY2025.pdf`` starts with ``A01`` too, and the
    README would tell the client their W-2 arrived. The longest identifier
    that fits wins, as it does for every file (``tracker.scaffold.owner_of``).
    Without case, as Windows compares names.
    """
    name = name.strip().casefold()
    stem = Path(name).stem if _AN_EXTENSION.fullmatch(Path(name).suffix) else name
    separator = LABEL_SEPARATOR.casefold()
    best = ""
    for item in items:
        identifier = sanitize_component(item.identifier).casefold()
        if not identifier or len(item.identifier) <= len(best):
            continue
        if (name.startswith(identifier + separator) or stem == identifier
                or stem.startswith(identifier + " (")):
            best = item.identifier
    return best


def _requests_of(entry: IndexEntry, items: Sequence[RequestItem]) -> list[str]:
    """Every request a filed row satisfied: its identifier, then one per
    ``also_filed`` copy (decision 94).

    ``also_filed`` holds the copies' locations, not their requests, so each
    is read back from the copy's own file name by :func:`_request_of_copy`
    (decision 168; from the request folder it sat in until then). A name
    no request of today's list provably names answers ``""``, which the
    README says as :data:`OTHER_DOCUMENT` - never a guessed request. A copy
    recorded in a request folder before 168 is read by its name too, and
    its name was always made in the same shape.
    """
    found = [entry.identifier]
    for location in entry.filed_locations[1:]:
        found.append(_request_of_copy(location.rsplit("/", 1)[-1], items))
    return found


def received_for(returns: Sequence) -> Received:
    """What has arrived for these returns, as the client README says it
    (decision 130): one index read and one request-list read per return,
    plain data out.

    Each of ``returns`` is a return folder, or a return as
    :func:`tracker.scaffold.readme_returns` read it (its ``path`` and
    ``items``), whose list is then not read a second time.

    - ``Filed`` and ``File Moved`` are **Received**, once per request the
      document satisfied, under the request's own label - the words the
      client read under *REQUESTED, NOT YET RECEIVED* - and never the
      client's file name or the firm's working name. A request no longer on
      the list reads :data:`OTHER_DOCUMENT`. Each request the row's Also
      Answers cell names (decision 146) is Received too, with the
      statement's own request as its ``inside``; the client's README says it
      as included in their consolidated brokerage statement
      (``reasons.IN_CONSOLIDATED_CLIENT``, Jason's Q-L), naming no request.
    - ``Needs Review`` is **Under Review**, counted by the day it arrived and
      never named: its only name is the client's own.
    - ``Duplicate``, ``Not Requested`` and anything else is not shown, and
      neither is a row a person marked missing because its working copy and
      its original were both gone (decision 157, :func:`marked_missing`):
      the letter asks for that document again, and the README agrees.

    A document this household's inbox fed into another household's return
    is in that return's index and so on that household's list, never on
    this one (decision 132's F-4 ruling).
    """
    lines: list[ReceivedLine] = []
    waiting: dict[dt.date | None, int] = {}
    for one in returns:
        if isinstance(one, (str, Path)):
            folder, items = Path(one), None
        else:
            folder, items = Path(one.path), one.items
        entries = read_index(folder)
        if not entries:
            continue
        if items is None:
            items = load_manifest(folder)
        # Without case, as the status and the letter join a row to its
        # request (``records.identifier_key``), and under the list's own
        # spelling: a request respelt C01 -> c01 is the same request here
        # too, and the README no longer says "not received" of what the
        # letter counts as received (decision 160, the audit's D-8).
        requests = {identifier_key(item.identifier): item for item in items}
        for entry in entries:
            day = _day_of(entry.received)
            if _counts_as_received(entry):
                for identifier in _requests_of(entry, items):
                    item = requests.get(identifier_key(identifier))
                    lines.append(ReceivedLine(return_path=folder,
                                              label=item.label if item else OTHER_DOCUMENT,
                                              day=day,
                                              identifier=item.identifier if item else ""))
                # A consolidated statement answers other asked requests
                # without a copy (decision 146): each is received, said as
                # inside the statement's own request. A request no longer
                # on the list is not said at all - "Other document" would be
                # a second line for the one document the line above names.
                # Joined without case, as the line above (decision 160).
                host = requests.get(identifier_key(entry.identifier))
                for identifier, _sections in entry.answered:
                    item = requests.get(identifier_key(identifier))
                    if item is not None:
                        lines.append(ReceivedLine(return_path=folder, label=item.label,
                                                  day=day, identifier=item.identifier,
                                                  inside=host.label if host else OTHER_DOCUMENT))
            elif entry.decision == NEEDS_REVIEW:
                waiting[day] = waiting.get(day, 0) + 1
    return Received(
        lines=tuple(lines),
        under_review=tuple(UnderReview(day=day, count=n) for day, n in waiting.items()),
    )


#: The household README's own lock (decision 130, the review's F2), in the
#: household's folder in the **private** tree - never the client's, where
#: a sync client would carry it to the client. Held only around one
#: refresh's read, render and write, so a refresh that read an older record
#: can never write its text over a newer refresh's.
README_LOCK_FILENAME = "_readme.lock"
#: How long a refresh waits for another refresh of the same household to
#: let go before it skips. A refresh holds the lock for one read of the
#: household's returns and one small write, so this is generous.
README_LOCK_WAIT_SECONDS = 5.0
_README_LOCK_POLL_SECONDS = 0.1


def _readme_lock(household_dir: Path):
    """Take the household README's lock, waiting briefly; ``None`` if it
    stayed busy."""
    deadline = time.monotonic() + README_LOCK_WAIT_SECONDS
    while True:
        try:
            return acquire_lock(household_dir, README_LOCK_FILENAME)
        except EngagementLockedError:
            if time.monotonic() >= deadline:
                return None
            time.sleep(_README_LOCK_POLL_SECONDS)


def refresh_household_readme(household_dir: Path | str) -> Path | None:
    """Rewrite one household's client README from the record - **the one
    call every caller makes** (decision 130): the household pass once after
    its sort, the rollover after it rolls a household, and the app after
    every action that creates or edits a return or changes a document's row.

    The README speaks for the active returns of the household's one open
    year, read once (:func:`tracker.scaffold.readme_returns`) and handed to
    :func:`received_for` and :func:`tracker.scaffold.write_readme` both
    (the review's F3); ``write_readme`` renders and writes only when the
    text changed. With two open years it is left as it is.

    **Under the household README's lock** (:data:`README_LOCK_FILENAME`,
    the review's F2), from the read to the write: two refreshes of one
    household - the pass and an app action, or two app actions - would
    otherwise interleave, and the one that read the older record could
    write last. A refresh waits up to :data:`README_LOCK_WAIT_SECONDS` for
    the other to let go, then reads the record itself; one still busy
    after that skips with a log line, and the holder writes.

    **Never raises.** The README is client-visible and cosmetic; a failure
    is a log line and the caller goes on.
    """
    household_dir = Path(household_dir)
    try:
        lock = _readme_lock(household_dir)
        if lock is None:
            log.warning("The README of %s is being refreshed by another run, which "
                        "writes it; this refresh is skipped", household_dir.name)
            return None
        try:
            returns = readme_returns(household_dir)
            if returns is None:
                return None
            return write_readme(household_dir, received_for(returns), returns=returns)
        finally:
            release_lock(lock)
    except Exception as exc:
        log.warning("Could not refresh the README of %s (%s: %s); carrying on",
                    household_dir.name, exc.__class__.__name__, exc)
        return None


# ------------------------------------------------ what a killed write left ----


def _a_stranded_temp_to_take(path: Path) -> bool:
    """Whether a temp of the tracker's own shape was left by a writer that
    is gone: this process (which has no write open at a pass's start) or
    one that is no longer running. A live owner is still writing it, and
    one that cannot be asked is left too - it is taken on a later pass."""
    owner = temp_owner(path.name)
    if owner is None:
        return False
    return owner == os.getpid() or pid_alive(owner) is False


def _remove_a_stranded_temp(path: Path) -> bool:
    """Take one stranded temp away; False, with a log line, where Windows
    refuses. A temp ``copy2`` carried a read-only attribute onto before the
    kill is made writable first - it is the copy, never an original."""
    try:
        try:
            path.unlink()
        except PermissionError:
            make_writable(path)
            path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        log.warning("A temporary file a killed write left, %s, could not be removed (%s); "
                    "the next pass tries again", path.name, exc)
        return False
    return True


def sweep_stranded_temps(household_dir: Path | str, returns: Sequence[Path], *,
                         started: float) -> list[Path]:
    """Take away the temps a killed write left in this household's firm
    folders and its README's, and return what was taken (decision 155).

    Every file the tracker writes goes through a temp beside it
    (:mod:`tracker.fsio`), and a kill - a power cut, a restart, Task
    Scheduler's limit - leaves that temp for ever: a whole client
    attachment under ``_Opened``, a half working copy, and in the client's
    own ``Drop files here`` the README's, which the client could see and
    every pass counted as a file still syncing. The household pass calls
    this first, under every return's lock, before anything is read.

    **Only ever the tracker's own temps, and never an original.** A file is
    taken only when all of these hold:

    - its name has :data:`tracker.fsio.TEMP_NAME`'s exact shape - a file
      that merely ends in ``.tmp`` is somebody's;
    - it came to be before ``started``, this pass's start;
    - the process its name carries is this one or is no longer running;
    - it is **not** a path any row names: a parked working copy keeps the
      client's own name, and what came out of an email or a zip rests
      under ``_Opened`` as an original rests in the year's folder, so one
      whose own name has that shape is a client's document (a return whose
      rows cannot be read is not swept at all, nor its ``_Opened``);
    - it is in one of three places: under a return's own folder (working
      copies, the review folder, the Status Report, the draft); under the
      household-year's ``_Opened``; or in the inbox, beside the README and
      named after it, and only under the README's lock, which is what
      every README write holds.

    Nothing in the client's year folders is ever looked at: the originals
    rest there, and nothing the tracker writes goes through a temp there.
    A temp that cannot be removed now is a log line and waits for the next
    pass. **Never raises**: a sweep that failed the household would be a
    leftover jamming the pass it exists to protect.
    """
    household_dir = Path(household_dir)
    taken: list[Path] = []
    try:
        # Every path any row names, in any of these returns, compared as
        # Windows compares them. A parked working copy keeps the client's own
        # name, and an attachment rests under _Opened under its own: either
        # may happen to have the temp shape, and a row naming it makes it a
        # document, never a leftover (decision 155's review).
        named: set[str] = set()
        swept: list[Path] = []
        unread: set[Path] = set()
        for folder in map(Path, returns):
            try:
                rows = read_index(folder)
            except Exception as exc:
                log.warning("The rows of %s could not be read (%s: %s); neither it nor its "
                            "household's _Opened folder is swept this pass",
                            folder.name, exc.__class__.__name__, exc)
                unread.add(opened_dir_of(folder))
                continue
            swept.append(folder)
            for entry in rows:
                for location in (entry.pbc_location, entry.container, *entry.filed_locations):
                    if location:
                        named.add(os.path.normcase(locate(folder, location)))
        places = [*swept, *dict.fromkeys(opened_dir_of(folder) for folder in swept
                                         if opened_dir_of(folder) not in unread)]
        candidates = [path for place in places
                      for path in stranded_temps(place, before=started, recursive=True)
                      if os.path.normcase(path) not in named]
        for path in candidates:
            if _a_stranded_temp_to_take(path) and _remove_a_stranded_temp(path):
                taken.append(path)
        if returns:
            lock = _readme_lock(household_dir)
            if lock is None:
                log.warning("The README of %s is being written by another run; its "
                            "leftover temps are swept on a later pass", household_dir.name)
            else:
                try:
                    for path in stranded_temps(inbox_of(Path(returns[0])), before=started,
                                               target=README_NAME):
                        if _a_stranded_temp_to_take(path) and _remove_a_stranded_temp(path):
                            taken.append(path)
                finally:
                    release_lock(lock)
    except Exception as exc:
        log.warning("The sweep of %s's leftover temporary files stopped (%s: %s); carrying on",
                    household_dir.name, exc.__class__.__name__, exc)
    for path in taken:
        log.info("Removed %s, a temporary file a killed write left", path.name)
    return taken


# ----------------------------------------------------------------- ensure ----


def ensure(engagement_dir: Path | str, root: Path | None = None) -> str:
    """Make the store describe this engagement, and say which of the three
    words it is in (:data:`tracker.records.CURRENT` and its two siblings).

    Run at the start of every pass and by every command that names an
    engagement, before anything reads the index or the request list: an
    engagement the store has never seen is built from its record, and one
    the store is behind on has the lines it has not applied replayed
    (:func:`tracker.store.catch_up`). Nothing is written in the
    engagement folder - the store is the machine's own derivation and
    building it moves nothing of the client's - so a dry run, the Status
    Report and the app showing an engagement another run is holding all
    call it as freely as a pass does. Until decision 104 this is also
    where a folder that still kept facts in a workbook was migrated and
    where the request list was imported; both left with the workbook.

    **By count, not by head** (decision 135). The readers trust a stored
    head that matches the journal's and parse nothing; this compares the
    number of lines applied with the number the journal holds, every
    time. So a store an earlier version left with a head naming a line it
    never applied - current by its head, refusing every writer by its
    count - is repaired by the next pass, with no rebuild. A pass parses
    the journal anyway, so the cost is one parse per engagement per pass,
    and a store with nothing to apply is answered without the store's
    write lock, so the app's views and the Status Report never queue a
    pass's ``record()`` behind them.
    """
    folder = Path(engagement_dir)
    root = Path(root) if root is not None else clients_root_of(folder)
    conn = store.connect()
    store.catch_up(conn, root, folder)
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
    OPENED: ledger.OPENED,
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
    extra: dict[str, dict] | None = None,
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
    write. ``extra`` is what an event carries beside its row, by the row's
    key: what an opened email or zip held (decision 143), which the journal
    keeps and the fold does not.
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
        event = _ledger_event(name, entry, was=was)
        # What an opened email or zip held travels on its own line, beside
        # the row (decision 143): the journal keeps it, the fold does not.
        event.update((extra or {}).get(key, {}))
        events.append(event)
    return events


def _record(
    engagement_dir: Path,
    before: dict[str, dict],
    entries: list[IndexEntry],
    *,
    moved: dict[str, str] | None = None,
    decided: dict[str, str] | None = None,
    also: list[dict] | None = None,
    extra: dict[str, dict] | None = None,
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
    events = _rows_changed(before, entries, moved or {}, decided or {}, extra) + list(also or [])
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


#: What an operation naming a place outside its return's own is refused
#: with (decision 180).
OP_OUTSIDE = ("the record of {name} names {location} for a step, which is outside the places "
              "a step of this return may touch; nothing was moved, copied or removed. "
              "A person checks the record")


def _may_touch(engagement_dir: Path, location: str, *, writes: bool) -> bool:
    """Whether a location an operation names lands where a step of this
    return may act (decision 180).

    Every step a decision writes is relative to the return whose record
    holds it, and every one stays in these places, read off the layout:
    under the return itself; under its household's ``_Opened`` of a year -
    its own year's where the step writes, any year's where it reads,
    because a person may hand an attachment parked in one open year to a
    return of the next (decision 129); and in the client tree only under
    some household's inbox or year folder - **this** return's household
    where the step writes (a move's or a copy's destination), any
    household where it reads, because a return a drop folder feeds takes
    its original out of another household's inbox. Nothing else - not an absolute path, a drive, a share,
    another return, the private tree's own files or anything above the
    clients root - is a place a step goes, so a line the record did not get
    from this code, however it got there, moves nothing. Lexical, as
    :func:`tracker.layout.locate` is: the link check guards what lies
    behind a junction, and this guards what a line says.
    """
    if not location or any(isabs(location) for isabs in (ntpath.isabs, posixpath.isabs)) \
            or ntpath.splitdrive(location)[0]:
        return False

    def parts(path) -> tuple[str, ...]:
        return Path(os.path.normcase(os.path.normpath(str(path)))).parts

    root = parts(root_of(engagement_dir))
    here = parts(locate(engagement_dir, location))
    if here[:len(root)] != root:
        return False
    below = here[len(root):]
    own = parts(engagement_dir)[len(root):]           # (private tree, household, year, return)
    if len(below) > len(own) and below[:len(own)] == own:
        return True
    if (len(below) > 4 and below[:2] == own[:2] and is_year_folder(below[2])
            and below[3] == os.path.normcase(OPENED_DIR_NAME) and (below[2] == own[2] or not writes)):
        return True
    return (len(below) >= 4 and below[0] == os.path.normcase(CLIENTS_TREE)
            and (is_year_folder(below[2]) or below[2] == os.path.normcase(INBOX_DIR_NAME))
            and (not writes or below[1] == own[1]))


def _refuse_a_step_outside(engagement_dir: Path, op: dict) -> None:
    """:data:`OP_OUTSIDE` for the first place in ``op`` a step of this
    return may not touch, before any of it is done."""
    reads = [op.get(ledger.FROM_KEY, "")]
    writes = [op[ledger.TO_KEY]] if ledger.TO_KEY in op else []
    if op[ledger.OP_KEY] == ledger.OP_REMOVE:
        reads, writes = [], reads
    for location, write in [*((one, False) for one in reads), *((one, True) for one in writes)]:
        if not _may_touch(engagement_dir, str(location), writes=write):
            raise FilingError(OP_OUTSIDE.format(name=Path(engagement_dir).name, location=location))


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
    _refuse_a_step_outside(engagement_dir, op)
    kind = op[ledger.OP_KEY]
    source = locate(engagement_dir, op[ledger.FROM_KEY])
    if kind == ledger.OP_REMOVE:
        source.unlink(missing_ok=True)
        return
    target = locate(engagement_dir, op[ledger.TO_KEY])
    target.parent.mkdir(parents=True, exist_ok=True)
    if kind == ledger.OP_MOVE:
        _move_whole(source, target, within=root_of(engagement_dir))
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
    was: str = "",
    also: list[dict] | None = None,
    reason: str = "",
) -> None:
    """Write down what this decision is about to do, before it does it -
    once every step is known to stay in its return's places (decision
    180), so a step refused is never an intent left open.

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

    ``was`` is the identity the row is leaving, where a decision re-keys
    the row. It travels here for the reason the row does: a recovery has
    to write the row event the decision would have written, and one
    without it would leave the record holding the row twice. No writer
    passes one since decision 132 took the hand-over's re-key away; the
    shape and the recovery's reading of it stay.

    **A release is written even with nothing to move** (decision 132). A
    hand-over is two intents in two records, and the one here - ``then``
    :data:`tracker.ledger.RELEASED` - is what lets this household's own
    pass finish its half after a kill, whether or not there was a parked
    copy to remove. ``reason`` is the sentence the release will say.
    Nothing here ever writes into another return's record: each record's
    half of a decision is that record's own intent.
    """
    for op in ops:
        _refuse_a_step_outside(engagement_dir, op)
    if not ops and then != ledger.RELEASED:
        return
    event = ledger.new(ledger.MOVING, **{
        ledger.KEY_KEY: key, ledger.OPS_KEY: ops, ledger.DECIDED_BY_KEY: by,
    })
    if row is not None:
        event[ledger.ROW_KEY] = row
    if was and was != key:
        event[ledger.WAS_KEY] = was
    if then:
        event[ledger.EVENT_KEY_AFTER] = then
    if also:
        event[ledger.ALSO_KEY] = list(also)
    if reason:
        event[ledger.REASON_KEY] = reason
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


def iter_drops(inbox: Path, *, unread: list[Path] | None = None) -> list[Path]:
    """Client-dropped files awaiting sorting.

    Everything in the household's inbox except the generated README and
    OS/sync junk. A file at the README's name is a drop when it is the
    client's (decision 179, :func:`tracker.scaffold.whose_readme`); one
    that cannot be told just now is left where it is and added to
    ``unread``, when given, for the pass to name in its warnings. Subfolders are included — a client who drags a whole
    folder in still gets it sorted. Since decision 125 the originals rest
    in the year's folder in the client tree, not inside this one, so there
    is nothing here to exclude but the note the firm wrote.

    **In the inbox's own order** (decision 147, ruling 3): the files at the
    top first, then each subfolder in name order, a folder's own files
    before its subfolders'. The year's folder is flat (decision 125), so
    two files of one name from two places meet there, and the one moved
    second is the one numbered. A plain sort of the paths made that the
    sort's accident - on Windows a path compares case-folded, and
    ``Scans/W2.pdf`` came before ``W2.pdf`` - so the file the client put
    at the top lost its name to one from a subfolder. Names are compared
    case-folded, the same on Windows and POSIX, with the exact path last
    so two names differing only in case still come in one order.
    """
    if not inbox.is_dir():
        return []
    drops = []
    for path in inbox.rglob("*"):
        if not path.is_file() or is_ignored(path) or _through_a_link(path, inbox) or not _storable(path):
            continue
        if path == inbox / README_NAME:
            whose = whose_readme(path)
            if whose == README_UNKNOWN and unread is not None:
                unread.append(path)
            if whose != README_CLIENTS:
                continue        # a client's own file of that name is a drop (decision 179)
        drops.append(path)
    return sorted(drops, key=lambda path: _inbox_order(path, inbox))


def _inbox_order(path: Path, inbox: Path) -> tuple[tuple[str, ...], str, str]:
    """Where a drop comes in :func:`iter_drops`' order: by the folders
    below the inbox it sits in - none first, and a folder before its own
    subfolders, since a tuple sorts before every tuple it begins - then by
    its name."""
    below = path.relative_to(inbox)
    return tuple(part.casefold() for part in below.parent.parts), below.name.casefold(), below.as_posix()


def _subfolder_of(drop: Path, inbox: Path) -> str:
    """The client's subfolder a drop sits in, below the inbox, the way the
    client sees it in Explorer (``Bank statements\\2025``); ``""`` for a
    drop at the top of the inbox (decision 147, ruling 4)."""
    try:
        below = drop.parent.relative_to(inbox)
    except ValueError:
        return ""
    return "\\".join(below.parts)


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


def _through_a_link(path: Path, root: Path) -> bool:
    """True when ``path`` is reached through a link below ``root``.

    ``rglob`` follows a junction, and a junction a client (or a sync
    client) leaves in the drop folder points anywhere: at a folder outside
    the engagement whose files would then be *moved* into PBC as the
    client's originals. What lies behind a link is not a drop.
    """
    # Only what lies between the root and the path is judged (decision
    # 137's review, F5): the clients root may itself sit under a folder
    # that is a link - ``G:\\Shared drives`` is Drive for desktop's own -
    # and that must never refuse a move. A path that is not under the root
    # at all is not a path this walk was asked about, and is refused.
    base = os.path.normcase(os.path.normpath(str(root)))
    here = os.path.normcase(os.path.normpath(str(path)))
    if here != base and not here.startswith(base.rstrip(os.sep) + os.sep):
        return True
    for part in (path, *path.parents):
        if os.path.normcase(os.path.normpath(str(part))) == base:
            return False
        if is_link(part):
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
        or (not path.is_file() and not path.is_dir() and not is_link(path))
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
            if not is_link(Path(folder) / name) and not is_sync_staging(name)
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
    recorded = _on_record(engagements)
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
    The pass asks it of the year's folder and of ``_Opened`` (decision
    143's review, B2), where an attachment's row locates the file taken out.
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
    """Where in ``entries`` the rows sit whose recorded original is gone.

    Not a row a person marked missing (decision 157, :func:`marked_missing`):
    they have looked, the client is asked for it again, and the same bytes
    turning up anywhere are a new arrival rather than this row's to follow.
    """
    newest: dict[str, int] = {}
    for position, entry in enumerate(entries):
        if entry.pbc_location:
            newest[entry.pbc_location] = position     # the newest row for a location wins
    return [position for location, position in newest.items()
            if not marked_missing(entries[position]) and _absent(locate(engagement_dir, location))]


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
        # Before any moved sentence the row ends with (decision 157), so a
        # File Moved row still reads where its copy is, or that its copy and
        # original were both gone, once its original has been found again.
        entries[position] = replace(
            was,
            pbc_location=location_of(engagement_dir, path),
            reason=_before_the_moved_sentence(
                was.reason, MOVED_FROM_IN_PBC.format(location=was.pbc_location, found=found)),
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
#: What a pass says of an original in the household's year folder that no
#: row of its own names and that another return's unfinished filing names
#: as the source of its move (decision 132, rulings R-1 and R-3). The file
#: is left where it is - never re-sorted, parked or recorded here - and
#: said on the first own return's warnings every pass it happens, so an
#: intent that never finishes is never an original nobody mentions.
#: What a pass says of the README in a household's inbox that could not be
#: opened just now (decision 179): it is neither sorted nor written over,
#: and it waits where it is, the way a file held open does.
README_UNREAD = ("the README in {household}'s folder could not be read just now; "
                 "it was left where it is and the next pass looks again")
LEFT_FOR_ANOTHER_RETURN = ("{name} is left where it is: another return's unfinished filing "
                           "names it, and that return's next pass finishes it")
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
#: Decision 157: a working copy that is gone, whose bytes are nowhere else
#: under the firm's folder, is made again from the row's own original,
#: proved against the row's fingerprint - by the pass, or by a person's Put
#: it back. Appended to the row's Reason and said once on the pass; the
#: request's status does not move and the client is never asked. ``{home}``
#: is every place made again, joined by ``PLACES_JOINED``.
REMADE_SENTENCE = ("the working copy was made again at {home} from the original {pbc} on {date}; "
                   "nothing under {prepared} held it")
#: How ``REMADE_SENTENCE`` names more than one place (decision 94's page,
#: filed under several requests, can lose every copy at once).
PLACES_JOINED = " and "
#: And when it cannot be: the copy is gone, nothing under the firm's folder
#: holds its bytes, and the original is gone too or holds other bytes
#: (decision 157, ruling B5). The row is ``FILE_MOVED`` with this sentence,
#: said once, and the request is held firm-side until a person looks
#: (``reasons.COPY_AND_ORIGINAL_GONE``); only their Mark missing asks the
#: client again. Read back by :func:`both_gone`, from this very template.
BOTH_GONE_SENTENCE = ("{home} no longer holds this row's bytes, nothing under {prepared} does, and "
                      "the original {pbc} is gone or holds other bytes (found {date})")
#: The pass's line when a copy it set out to make again could not be made
#: (a full disk, a path past the limit, an original that changed while it
#: was read). Nothing made is left behind and nothing is recorded; the
#: scan holds the request firm-side (``reasons.COPY_MISSING``).
REMAKE_FAILED = ("the working copy {home} could not be made again from the original {pbc} "
                 "({problem}); the next pass tries again")
#: What Put it back, Keep it here and Send to review say of a row whose
#: copy and original are both gone (decision 157, ruling B5): there is
#: nothing to put back, and the one answer left is the person's.
NOTHING_TO_PUT_BACK = ("nothing under {prepared} holds this row's bytes and the original {pbc} is "
                       "gone or holds other bytes; there is nothing to put back - mark it missing "
                       "if the client should send it again")
#: What Put it back says of a row a person has already marked missing
#: (decision 157, ruling B6): it names no copy any more, on purpose.
MARKED_REFUSAL = ("{name} was marked missing by a person: the client is asked for it again, "
                  "and there is nothing to put back")
#: Decision 157, ruling B7: a drop that is a row's own original coming
#: back - the one row whose recorded original is gone holds these very
#: bytes - is moved back to where the row says, under the recorded name,
#: and the row says so. No new row is written. ``{drop}`` is where it
#: arrived, below the inbox, the way the client sees it.
RETURNED_SENTENCE = "the original came back as {drop} on {date} and was moved back to {pbc}"
#: Decision 111's re-file, over decision 157: a re-send whose earlier row
#: has neither its working copy nor its original any more - both gone, or a
#: person marked it missing - is the client answering, and is filed again.
REFILED_AFTER_GONE = "re-filed: {name} had neither its working copy nor its original any more"
#: Attention, every pass, for a file named for a request (decision 168;
#: under a request folder until then) or in the review folder that no row
#: names and whose bytes match no row. It is counted
#: where it sits, because what a request holds is what the scanner says it
#: has; what nothing knows is who put it there. Since decision 155 no copy
#: the tracker makes is ever half there under a name - a failed or killed
#: copy leaves only its temp, which the next pass sweeps - so the advice
#: no longer assumes a document the client sent (the audit's E8): one that
#: is not a whole document is ours to delete, and is never the client's to
#: send again.
UNRECORDED_COPY = ("{location} is not on the record: nothing filed it there and no row's bytes "
                   "match it; it is counted as it sits - open it: a document goes in through the "
                   "app or the client's folder, so the record knows it; anything else, a broken "
                   "or partial copy included, is deleted by hand")

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
_BOTH_GONE_TAIL = _moved_tail(BOTH_GONE_SENTENCE)
#: A person's mark (decision 146's MARKED_MISSING) at the end of a Reason.
#: Decision 146 lets a person mark an answer missing on a ``FILE_MOVED``
#: row too, and the mark is appended after whatever the row said, so the
#: moved sentence is looked for behind any such marks (:func:`_moved_part`).
#: The note is read up to its own closing bracket and no further: the
#: moved sentences end in brackets too, and a mark made *before* one must
#: never be read as swallowing it. A note that itself holds brackets is not
#: read as a mark, and the row is read as it always was.
_MARKED_TAIL = re.compile(
    "^(?P<base>.*); " + as_pattern(
        MARKED_MISSING, identifier=r"[^;]+?", date=_MOVED_DATE, note=r"(?: \([^()]*\))?",
    ) + "$",
    re.DOTALL,
)


def _moved_part(reason: str) -> tuple[str, re.Pattern[str] | None, str, str]:
    """A Reason split round the moved sentence it ends with: what came
    before it, which of the three it is (``None`` where there is none),
    the sentence itself, and any person's marks after it (decision 157).

    Each of the three patterns comes from the template that writes the
    sentence (:func:`_moved_tail`), so rewording a sentence moves this
    reader with it.
    """
    rest, marks = reason, ""
    while (found := _MARKED_TAIL.match(rest)) is not None:
        marks = rest[len(found.group("base")):] + marks
        rest = found.group("base")
    for pattern in (_MOVED_TAIL, _MOVED_GONE_TAIL, _BOTH_GONE_TAIL):
        found = pattern.match(rest)
        if found:
            return found.group("base"), pattern, rest[len(found.group("base")) + 2:], marks
    return reason, None, "", ""


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
    "no longer holds" after another for the same copy. A person's mark
    after it (decision 146) stays, after what came before (decision 157).
    """
    base, pattern, _sentence, marks = _moved_part(reason)
    return f"{base}{marks}" if pattern is not None else reason


def _before_the_moved_sentence(reason: str, sentence: str) -> str:
    """``sentence`` added to a Reason, before the moved sentence it ends
    with where it ends with one (decision 157), so :func:`moved_to` and
    :func:`both_gone` read that row as they did: a sentence appended after
    it would hide where the copy is from both."""
    base, pattern, moved, marks = _moved_part(reason)
    if pattern is None:
        return f"{reason}; {sentence}"
    return f"{base}; {sentence}; {moved}{marks}"


def _says_it_is_nowhere(entry: IndexEntry) -> bool:
    """Whether this row already says its bytes are nowhere in the folder -
    the original safe (decision 109) or gone too (decision 157)."""
    if entry.decision != FILE_MOVED:
        return False
    return _moved_part(entry.reason)[1] in (_MOVED_GONE_TAIL, _BOTH_GONE_TAIL)


def both_gone(entry: IndexEntry) -> bool:
    """Whether this row says its working copy and its original are both
    gone (decision 157, ruling B5), and a person has not yet marked it
    missing.

    The scanner reads it to hold the request firm-side with
    ``reasons.COPY_AND_ORIGINAL_GONE`` rather than decision 110's
    put-it-back wording, the app to offer Mark missing, and Mark missing to
    accept the row's own request. Read off the row's own sentence
    (:data:`BOTH_GONE_SENTENCE`), behind any marks a person added.
    """
    return (entry.decision == FILE_MOVED and bool(entry.prepared_location)
            and _moved_part(entry.reason)[1] is _BOTH_GONE_TAIL)


def marked_missing(entry: IndexEntry) -> bool:
    """Whether a person marked this row's own request missing (decision 157,
    ruling B6): a ``FILE_MOVED`` row that names no working copy.

    Mark missing takes the row's claim on its copies away - its Prepared
    Location, its other copies and what it answered - and appends the
    person's sentence, so the row stays on the record and counts for
    nothing: the sweep never makes its copy again or flags it again, the
    scanner reads no copy of it, the client README leaves it out, and the
    same bytes sent again are filed as a new arrival. Nothing else ever
    writes a ``FILE_MOVED`` row without a copy - the sweep moves only rows
    that name one - so the shape is the mark.
    """
    return entry.decision == FILE_MOVED and not entry.prepared_location


def _counts_as_received(entry: IndexEntry) -> bool:
    """Whether a row is one the client README and a save of the list count
    as a document the client sent: Filed or File Moved (decision 130), and
    not a row a person has marked missing (decision 157)."""
    return entry.decision in _RECEIVED_DECISIONS and not marked_missing(entry)


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


#: What a row's original is when its working copy has to be made again,
#: read in the moment (decision 157, ruling B3): proved (here, readable,
#: the row's own bytes), not read (a placeholder, or a read refused - look
#: again next pass), or gone (absent, or holding other bytes).
_ORIGINAL_PROVED = "proved"
_ORIGINAL_UNREAD = "unread"
_ORIGINAL_GONE = "gone"


def _the_original_now(engagement_dir: Path, entry: IndexEntry) -> tuple[str, Path | None]:
    """Whether this row's original can be copied from, read now and never
    remembered: the copy made from it is proved against the same digest
    on its way in (:func:`_copy_whole`), so what is proved here is what is
    copied. A placeholder is never read - hashing one would make the sync
    client download it - and a read refused is not an absence
    (:func:`_absent`'s rule): both are "not this pass", never "gone"."""
    if not entry.pbc_location:
        return _ORIGINAL_GONE, None
    path = locate(engagement_dir, entry.pbc_location)
    if _absent(path) or path.is_dir():
        return _ORIGINAL_GONE, path
    if is_cloud_placeholder(path):
        return _ORIGINAL_UNREAD, path
    digest = _digest_or_none(path)
    if digest is None:
        return _ORIGINAL_UNREAD, path
    return (_ORIGINAL_PROVED if digest == entry.digest else _ORIGINAL_GONE), path


def _may_be_made_again(entry: IndexEntry, every_one_absent: bool) -> bool:
    """Whether the sweep makes this row's gone copies again (decision 157,
    ruling B2): a Filed row and a parked one (Needs Review, Not Requested -
    so a ``Prepared`` folder deleted whole comes back whole), and a File
    Moved row that already says its bytes are nowhere, when every place it
    claims is simply gone - a place holding some other file is somebody's
    and is never written over. A File Moved row whose wanderer has just
    gone is said nowhere first, as it always was, and is made again on the
    pass after (the row is a person's question, decision 110)."""
    if entry.decision in (FILED, *_PARKED):
        return True
    return entry.decision == FILE_MOVED and every_one_absent and _says_it_is_nowhere(entry)


def _remade(entry: IndexEntry, locations: Sequence[str], stamp: str) -> tuple[IndexEntry, str]:
    """The row once its copies at ``locations`` are made again, and the
    sentence it gains (decision 157, ruling B4): a Filed row stays Filed, a
    parked row keeps its decision, and a File Moved row that said nowhere
    is what it was before it went - Filed, or Needs Review where it names no
    request, :data:`MOVED_BACK_SENTENCE`'s rule - with its nowhere sentence
    taken off, as a copy dragged back has its moved sentence taken off."""
    sentence = REMADE_SENTENCE.format(home=PLACES_JOINED.join(locations), pbc=entry.pbc_location,
                                      date=stamp, prepared=PREPARED_DIR_NAME)
    if entry.decision == FILE_MOVED:
        return replace(entry, decision=FILED if entry.identifier else NEEDS_REVIEW,
                       reason=f"{_without_moved_sentence(entry.reason)}; {sentence}"), sentence
    return replace(entry, reason=f"{entry.reason}; {sentence}"), sentence


def _make_again(
    engagement_dir: Path, entry: IndexEntry, remade: IndexEntry, source: Path,
    locations: Sequence[str], *, by: str, then: str, cache: ContentCache | None,
) -> None:
    """Write down, then make, a working copy at each of ``locations`` from
    the row's proved original - **the one function** the pass's sweep and a
    person's Put it back both make a gone copy through (decision 157,
    rulings B1 and B8).

    The intent comes first (decision 119), carrying the row as it will be
    (``remade``) and the event that completes it, so a run killed after a
    copy is finished from the record. Each copy is decision 155's whole
    copy, proved against the row's digest before it takes its name. All or
    nothing: a copy that fails leaves no file under its name, the copies
    this call already made are taken back by their bytes, the intent is
    abandoned, and the failure is raised for the caller to say. A kill is
    not a failure: nothing is taken back, and the next pass finishes it.
    """
    key = ledger_key(entry)
    ops = [_op(engagement_dir, ledger.OP_COPY, source, locate(engagement_dir, location), entry.digest)
           for location in locations]
    _intend(engagement_dir, key, ops, by=by, row=entry_to_json(remade), then=then)
    done: list[dict] = []
    try:
        for op in ops:
            _do_op(engagement_dir, op, cache=cache)
            done.append(op)
    except (OSError, FilingError):
        _take_back(engagement_dir, done)
        _abandon(engagement_dir, key)
        raise


def _make_again_or_hold(
    engagement_dir: Path, entries: list[IndexEntry], position: int, absent: list[str], home: str,
    cache: ContentCache, stamp: str, swept: dict[str, str], *, dry_run: bool,
) -> FileError | None:
    """The sweep's answer to a row whose copy is gone and whose bytes are
    nowhere else under the firm's folder (decision 157): made again from a
    proved original, said as both gone where the original is gone too, and
    nothing at all where the original cannot be read now. Mutates
    ``entries`` and ``swept``; returns the pass's line, or None."""
    entry = entries[position]
    outcome, source = _the_original_now(engagement_dir, entry)
    if outcome == _ORIGINAL_UNREAD:
        log.info("The working copy recorded at %s is gone and its original %s cannot be read "
                 "this pass; nothing is made", home, entry.pbc_location)
        return None
    key = ledger_key(entry)
    if outcome == _ORIGINAL_PROVED:
        remade, sentence = _remade(entry, absent, stamp)
        if not dry_run:
            try:
                _make_again(engagement_dir, entry, remade, source, absent,
                            by=ledger.BY_PASS, then=ledger.COPY_REMADE, cache=cache)
            except (OSError, FilingError) as exc:
                problem = REMAKE_FAILED.format(home=PLACES_JOINED.join(absent),
                                               pbc=entry.pbc_location, problem=exc)
                log.warning("%s", problem)
                return FileError(Path(absent[0]).name, problem, True)
        entries[position] = remade
        swept[key] = ledger.COPY_REMADE
        log.warning("The working copy recorded at %s was gone; made again from %s",
                    PLACES_JOINED.join(absent), entry.pbc_location)
        return FileError(Path(absent[0]).name, sentence, True)
    if both_gone(entry):
        return None                  # said once already, and both are gone still
    sentence = BOTH_GONE_SENTENCE.format(home=home, prepared=PREPARED_DIR_NAME,
                                         pbc=entry.pbc_location or "(none)", date=stamp)
    entries[position] = replace(entry, decision=FILE_MOVED,
                                reason=f"{_without_moved_sentence(entry.reason)}; {sentence}")
    swept[key] = ledger.COPY_MOVED
    log.warning("The working copy recorded at %s is gone and so is its original %s",
                home, entry.pbc_location)
    return FileError(Path(home).name, sentence, True)


def _prove_working_copies(
    engagement_dir: Path,
    prepared_dir: Path,
    entries: list[IndexEntry],
    cache: ContentCache,
    stamp: str,
    request_files: set[Path],
    *,
    dry_run: bool = False,
) -> tuple[list[FileError], dict[str, str], dict[str, FileError]]:
    """One walk of the firm's folder: prove every copy the record names,
    identify every file it does not. Mutates ``entries``; returns the
    attention lines, ``{ledger_key: event}`` for every row it rewrote
    (``ledger.COPY_MOVED``, or ``ledger.COPY_REMADE`` for a copy it made
    again), and the line it said of each row whose copy and original are
    both gone, by key, for :func:`_put_back_home` to take back.

    ``request_files`` are the files whose names belong to a request
    (``tracker.scaffold.assign_files``, decision 168): an unrecorded one
    of them is counted where it sits, and so is said here. The walk itself
    goes everywhere under the firm's folder, a person's folder included,
    so a recorded copy dragged into one is found by its bytes.

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

    **A copy that is simply gone is made again** (decision 157). Until then
    a row whose copy was gone with its bytes nowhere else was skipped here
    ("decision 3's regression says this"), so the scan read the request
    Missing and the weekly letter asked the client again for a document
    whose original sat untouched in their own folder - after a colleague
    trashed a copy on Drive's web, a cache cleared, a copy deleted by hand,
    or the whole ``Prepared`` folder deleted. Now, for every row that
    claims a copy (:func:`_may_be_made_again`: Filed, parked, and a File
    Moved row that already says nowhere), each claimed place that is
    absent is made again from the row's original, proved against the
    row's fingerprint at the moment it is copied, through decision 155's
    whole copy and under decision 119's intent (:func:`_make_again_or_hold`).
    The request's status does not move and the pass says it once. Where the
    original is gone too, or holds other bytes, nothing is made and the row
    is said once as ``FILE_MOVED`` with :data:`BOTH_GONE_SENTENCE`; where
    it cannot be read now - still syncing, or refused - nothing is written
    at all and the scan holds the request (``reasons.COPY_MISSING``). The
    working copy is the firm's and disposable; the original is only read.
    A dry run decides all of it and makes nothing.
    """
    attention: list[FileError] = []
    swept: dict[str, str] = {}
    said: dict[str, FileError] = {}

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
        if entry.decision in (DUPLICATE, OPENED):
            continue                 # a Duplicate row only points at another row
        home = failed[position][0]
        now = _spend_a_stray(strays, entry.digest, moved_to(entry))
        if now is None:
            # Nothing under the firm's folder holds its bytes. Where the
            # copy is simply gone, it is made again from the original, or
            # held for a person when the original is gone too (decision
            # 157) - never a letter to the client.
            absent = [location for location in failed[position]
                      if _absent(locate(engagement_dir, location))]
            if absent and _may_be_made_again(entry, len(absent) == len(failed[position])):
                line = _make_again_or_hold(engagement_dir, entries, position, absent, home,
                                           cache, stamp, swept, dry_run=dry_run)
                if line is not None:
                    attention.append(line)
                    if both_gone(entries[position]):
                        said[ledger_key(entry)] = line
                continue
        if now is None and entry.decision != FILE_MOVED:
            continue                 # a copy that holds other bytes: the scan says so (decision 155)
        if now is not None and moved_to(entry) == now:
            continue                 # the same wanderer as last pass: nothing new to say
        if now is None and _says_it_is_nowhere(entry):
            continue                 # said nowhere already, and it is nowhere still
        if now is not None:
            sentence = MOVED_SENTENCE.format(home=home, now=now, date=stamp)
        elif entry.pbc_location and not _absent(locate(engagement_dir, entry.pbc_location)):
            sentence = MOVED_GONE_SENTENCE.format(
                home=home, prepared=PREPARED_DIR_NAME, pbc=entry.pbc_location, date=stamp)
        else:
            # "The original is safe" would be false (decision 157, B5).
            sentence = BOTH_GONE_SENTENCE.format(
                home=home, prepared=PREPARED_DIR_NAME, pbc=entry.pbc_location or "(none)",
                date=stamp)
        entries[position] = replace(
            entry, decision=FILE_MOVED,
            reason=f"{_without_moved_sentence(entry.reason)}; {sentence}",
        )
        swept[ledger_key(entries[position])] = ledger.COPY_MOVED
        line = FileError(Path(now or home).name, sentence, True)
        attention.append(line)
        if both_gone(entries[position]):
            said[ledger_key(entry)] = line
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
    # or files it in the app: a file named for a request, which is counted
    # where it sits, and anything in the review folder. A file whose name
    # begins with no request's identifier and a person's folder (decision
    # 168) are the scanner's warnings already, and one warning per thing
    # is the rule - a person's folder is named once, never file by file.
    review = prepared_dir / REVIEW_DIR_NAME
    for location in strays:
        path = locate(engagement_dir, location)
        if path in request_files or review == path.parent or review in path.parents:
            attention.append(FileError(path.name, UNRECORDED_COPY.format(location=location), True))
    return attention, swept, said


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
    # Every step is held to its return's places before any is looked at
    # (decision 180): a recovery acts on lines another machine or a
    # restored copy may have written, and a step outside them is the
    # record's problem for a person, never a move.
    for op in ops:
        _refuse_a_step_outside(engagement_dir, op)
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
) -> tuple[str, str]:
    """Where the person's copy of this document is, making one if there is
    none this row can prove.

    A row the recovery parks has to have a working copy a person can open
    and file, and the one the interrupted step was making is not there -
    the place it was going holds somebody else's file. The original in
    The year's folder is the record, so the copy comes from it, into
    ``REVIEW_DIR_NAME`` under the client's own name, never over anything.
    The copy is named as every review copy is (:func:`_review_copy_path`,
    decision 131): cut to the room the review folder leaves. A copy that
    cannot be made leaves the row naming **no** copy - never the one the
    interrupted step was making, which is not there (decision 131's review,
    F1) - and the second value is the sentence its reason gains; so is a
    copy fitted past a reader's limit. Inventing a path would be worse than
    an honest one that is empty.
    """
    for location in entry.filed_locations:
        if (entry.digest and _may_touch(engagement_dir, location, writes=False)
                and _the_bytes(locate(engagement_dir, location)) == entry.digest):
            return location, ""
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    # The original is read from where the row says only where a step of
    # this return may read (decision 180): a row another machine or a
    # restored copy wrote is held to the same places as its steps.
    if not _may_touch(engagement_dir, entry.pbc_location, writes=False):
        return "", OP_OUTSIDE.format(name=engagement_dir.name, location=entry.pbc_location)
    source = locate(engagement_dir, entry.pbc_location)
    # The copy the interrupted step was about to carry out of review is
    # still there when the step never happened: it is these bytes and it
    # is the copy a person may have written on, so it is used rather than
    # doubled (:func:`_existing_copy`, as everywhere else).
    waiting = _existing_copy(review_dir, source, entry.digest) if entry.digest else None
    if waiting is not None:
        return prepared_location(review_dir, waiting.name), ""
    try:
        parked, past_reader = _review_copy_path(review_dir, entry.original_name)
        review_dir.mkdir(parents=True, exist_ok=True)
        _copy_whole(source, parked, expect=entry.digest, cache=cache)
    except NoRoom as exc:
        log.error("Could not park a copy of %s from %s: %s",
                  entry.original_name, entry.pbc_location, exc)
        return "", str(exc)
    except (OSError, FilingError) as exc:
        log.error("Could not park a copy of %s from %s: %s",
                  entry.original_name, entry.pbc_location, exc)
        return "", REVIEW_COPY_FAILED.format(name=entry.original_name, problem=exc)
    return prepared_location(review_dir, parked.name), past_reader


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
        if outcome == _FINISHED and intent.get(ledger.EVENT_KEY_AFTER) == ledger.RELEASED:
            # This record's half of a hand-over (decision 132): the parked
            # copy is gone - removed now, or already - so the row is
            # released, in the words the person's click would have written.
            # Nothing of the other record is read or written here: its half
            # is its own intent, finished by its own pass.
            store.record(conn, engagement_dir, ledger.new(ledger.RELEASED, **{
                ledger.KEY_KEY: key,
                ledger.REASON_KEY: str(intent.get(ledger.REASON_KEY) or ""),
            }))
            rows_recorded = True
            log.warning("Finished the interrupted release of %s from the record",
                        entry.original_name)
            continue
        if outcome == _FINISHED:
            # The identity the row is leaving travels with the intent
            # where a decision re-keyed the row, so the row the recovery
            # writes re-keys exactly as the decision's own would have and
            # the record does not end holding it twice.
            leaving = str(intent.get(ledger.WAS_KEY) or "")
            events = [ledger.new(str(intent.get(ledger.EVENT_KEY_AFTER) or ledger.PARKED),
                                 **{ledger.KEY_KEY: key, ledger.ROW_KEY: row,
                                    **({ledger.WAS_KEY: leaving} if leaving else {})})]
            events += list(intent.get(ledger.ALSO_KEY) or [])
            store.record(conn, engagement_dir, *events)
            rows_recorded = True
            log.warning("Finished the interrupted %s of %s from the record",
                        intent.get(ledger.EVENT_KEY_AFTER), entry.original_name)
            continue
        sentence = _the_trouble(engagement_dir, entry, op, outcome)
        parked, copy_said = _a_copy_to_act_on(engagement_dir, entry, cache)
        new_entry = replace(
            entry, decision=NEEDS_REVIEW, identifier="", also_filed="", answers="",
            prepared_location=parked,
            reason="; ".join(part for part in (
                _without_moved_sentence(entry.reason), sentence, copy_said) if part),
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
            if _may_touch(engagement_dir, entry.pbc_location, writes=False)
            and _the_bytes(locate(engagement_dir, entry.pbc_location)) == entry.digest
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

#: What the destination's row says about a document that was dropped in
#: another household's folder (decision 129). The household, never a
#: person: the record names labels and folders and no member of anybody's
#: family, and the Status Report of the return that took the document says
#: where it came from in exactly those words.
DROPPED_ELSEWHERE = "dropped in {household}"

#: What a row says about a file the client dropped inside a subfolder of
#: the inbox (decision 147, ruling 4): the year's folder is flat (decision
#: 125), so the subfolder is gone from the file's resting name, and the
#: record keeps it here - the path below the inbox, the way the client sees
#: it in Explorer. Firm-side: the record's, never a sentence put to the
#: client. **Accepted limit** (decision 119): the inbox move writes no
#: intent, so a pass killed between the move and the row leaves a stray the
#: next pass files where it lies, without this sentence.
CAME_FROM_SUBFOLDER = "came from the client's subfolder '{folder}'"


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
    #: Whether this return belongs to the household whose inbox is being
    #: sorted (decision 129). A document only ever **parks** in a home
    #: return: the original rests under the household its return lives in,
    #: so a drop nobody can place rests where it was dropped and waits for
    #: a person there.
    home: bool = True
    #: What a filing into this return says about where the document was
    #: dropped - empty for a home return, the dropping household's name for
    #: one this drop folder feeds. It is also what says the original has a
    #: second move to make, into this return's own household-year folder.
    dropped_in: str = ""
    moved_keys: dict[str, str] = field(default_factory=dict)
    swept: dict[str, str] = field(default_factory=dict)
    #: What each opened email or zip held, by its row's key (decision
    #: 143): written on the row's own journal line, beside it.
    opened: dict[str, dict] = field(default_factory=dict)
    #: The folders of opened emails and zips left unrecorded for the next
    #: pass because the reader could not start on an attachment (decision
    #: 150 over 143): what waits in them is not said as unaccounted.
    reopen: set[Path] = field(default_factory=set)
    #: What this pass said about a row's original or working copy being
    #: gone, by the row's key (decision 157): ``MISSING_IN_PBC`` and the
    #: both-gone line. Taken back off the report when the same pass puts
    #: the original back (:func:`_put_back_home`), so a pass never ends
    #: saying something is missing that it has just put back.
    absence_said: dict[str, list[FileError]] = field(default_factory=dict)

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
    *,
    own: Sequence[Path],
    fed: Sequence[Path] = (),
    today: dt.date | None = None,
    dry_run: bool = False,
) -> dict[Path, FileReport]:
    """Sort one household's inbox across every return it feeds. Returns
    what was done, per return.

    **One inbox, several returns** (decision 125). A household with a
    business and its owner's 1040 has one folder to drop into, so the sort
    judges each drop against every open-year return's request list and
    files it where **exactly one** accepts it - the third standing rule,
    widened from one return's requests to the household's. A drop several
    accept parks in the first accepting return naming them all; a drop
    none accepts parks in the first return by order.

    **The feed list** (decisions 129 and 132). What this drop folder feeds
    is two named lists: ``own``, the household's own open-year returns, and
    ``fed``, the return lines a person extended it to in other households.
    One fact said once - a caller cannot hand in a "home" that is not part
    of what is fed. Nothing routes outside the two lists, and nothing is
    ever inferred into them. The returns are judged in the order they are
    handed in, own first: that is the order the bytes are asked of the
    records in, because the record closest to the drop decides. A document filed to a fed return **moves a second time**, out
    of this household's year folder into that return's, as the first step
    of the filing: the original rests under the household its return lives
    in, seen by exactly that folder's sharing. A document that parks parks
    at home, because the dropping household is where it was dropped and
    where a person can act on it.

    **The caller holds the locks.** ``tracker.runner.run_household`` takes
    every return's lock - its own and every fed one - in the one global
    order (``layout.lock_order_key``) before anything is read, and this
    asserts that it has them. A dry run decides everything, moves nothing
    and takes no lock, so it can never block a real run.

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
    runs = [_prepare_return(Path(folder), stamp, dry_run=dry_run) for folder in [*own, *fed]]
    if not runs:
        return {}
    # Which of them are this household's own - the list each came from -
    # and what a filing into one of the others says (decision 129). The
    # household is the client folder's own name -
    # ``<root>/<clients tree>/<household>/<year>`` - so the sentence names
    # the folder the document was dropped in and nothing has to be carried
    # down for it.
    dropped_in = originals_dir.parent.name
    for position, run in enumerate(runs):
        run.home = position < len(own)
        run.dropped_in = "" if run.home else DROPPED_ELSEWHERE.format(household=dropped_in)
    first = next((run for run in runs if run.home), runs[0])

    # 2. The originals folder is read once, against the union of every
    # return's rows: a file one return's row holds is never another
    # return's stray. What is left over is a stray for the household.
    strays = (unrecorded_in_pbc(originals_dir, [(r.engagement_dir, r.entries) for r in runs])
              if originals_dir.is_dir() else [])
    spoken_for = _spoken_for_by_an_open_intent(runs)
    intended = frozenset(_spoken_for_by_an_open_intent(runs, ends=(ledger.TO_KEY,)))
    for run in runs:
        run.context.intended = intended
    strays = [path for path in strays if path not in spoken_for]
    if strays:
        left = [path for path in strays if _named_by_another_records_intent(path, runs)]
        strays = [path for path in strays if path not in left]
        # Left alone, and said - every pass it happens (the lead's ruling
        # R-3): an intent that never finishes must not leave an original
        # unrecorded in silence. On the first own return, where the inbox's
        # own notes ride.
        for path in left:
            name = Path(os.path.relpath(path, originals_dir)).as_posix()
            first.report.attention.append(FileError(
                name, LEFT_FOR_ANOTHER_RETURN.format(name=name), True))
    for run in runs:
        strays = _follow_and_say(run, strays, originals_dir, stamp)

    # 3. The inbox is read once. What it says about itself - a transfer
    # still in flight, a name Windows refuses, a folder this run cannot
    # list - is the household's, and rides the first return's report,
    # which is where the practice page reads it from.
    unread: list[Path] = []
    drops = iter_drops(inbox, unread=unread)
    for path in unread:
        first.report.attention.append(FileError(
            path.name, README_UNREAD.format(household=dropped_in), True))
        log.warning("Left %s in place: it could not be read just now", path.name)
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
            _sort_all(drops, strays, originals_dir, stamp, runs, first)
        # What was taken out of emails and zips and no row names (decision
        # 143) - after the sort, so what this pass took out is named.
        first.report.attention.extend(_unaccounted_in_opened(first, runs))
    finally:
        # Whatever happened above, every original that was moved is on
        # record: one call and one transaction per return, in the same
        # locked section as the moves it records. A return that decided
        # nothing writes nothing - the diff against what its record
        # already said is what decides, not a count of rows.
        # The first own return last (decision 143): an opened email or zip's
        # row is in it, and recorded after the rows of what came out of it
        # wherever those went - so a pass killed between two returns'
        # transactions leaves the container unrecorded, a stray the next
        # pass opens again, rather than a container on record whose
        # attachments are not.
        if not dry_run:
            for run in reversed(runs):
                _record(run.engagement_dir, run.before, run.entries,
                        moved=run.moved_keys, decided=run.swept, extra=run.opened)
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


def _spoken_for_by_an_open_intent(
    runs: list[_ReturnRun], ends: tuple[str, ...] = (ledger.FROM_KEY, ledger.TO_KEY),
) -> set[Path]:
    """Every file a move this pass could not finish still names, at either
    end (or only at the ``ends`` asked for), across all the returns it holds.

    A cross-household filing moves the original a second time (decision
    129), and between the two halves of that move the file is in the
    dropping household's year folder while the row that names it belongs
    to the destination's record. Recovery runs first and nearly always
    closes it; a step waiting on the sync client does not close, and the
    file would then look like a stray of the household it is still sitting
    in and be sorted a second time. It is not a stray: it is spoken for,
    by a decision the record already holds.

    Its targets alone (``ends=(TO_KEY,)``) are names an open intent will
    write to, and no new file is given one (decision 147): a drop resting
    there would carry the waiting filing's key, and its row would close
    that filing with a different document's.
    """
    conn = store.connect()
    held: set[Path] = set()
    for run in runs:
        for intent in store.open_intents(conn, run.engagement_dir):
            for op in intent.get(ledger.OPS_KEY) or []:
                for key in ends:
                    location = op.get(key)
                    if location:
                        held.add(locate(run.engagement_dir, str(location)))
    return held


def _named_by_another_records_intent(path: Path, runs: list[_ReturnRun]) -> bool:
    """Whether an open intent in **any other** record of the practice
    names this file, with these bytes, as the source of a step it has not
    finished (decision 132, the lead's ruling R-1).

    A person's hand-over is two intents in two records: the dropping
    household's release, then the taking return's filing, whose first step
    moves the original out of this household's year folder. A kill between
    them, a feed trimmed and this household's own pass run first leaves
    exactly that: the release finished here, the row gone, and the original
    still where it was dropped - named by no row of this household, and
    by the other record's open intent. It is not a stray. It is spoken for
    by a decision another record already holds, and the pass leaves it
    alone - never re-sorts, parks or records it - so the taking return's
    own pass always finishes the move. That is why each half of a
    hand-over can be finished by its own household's pass.

    **The whole practice, read only when there is a stray** (which is
    rare): every return under the clients root this return sits under, the
    same positional walk discovery makes, each brought up to its journal
    before its open intents are read, so a store rebuilt on another machine
    answers as the journals do. No lock is taken and nothing is written.
    Monotone under a running pass: a filing intent is written before its
    move and closed only after it, and a hand-over holds this household's
    lock while it writes both intents, so no new one can appear while this
    pass holds it.
    """
    own = {run.engagement_dir for run in runs}
    root = root_of(runs[0].engagement_dir)
    conn = store.connect()
    digest = None
    for household in sorted((root / PRIVATE_TREE).iterdir()) if (root / PRIVATE_TREE).is_dir() else []:
        if not household.is_dir():
            continue
        for folder in household_returns(household):
            if folder in own:
                continue
            try:
                store.follow_the_journal(conn, clients_root_of(folder), folder)
                intents = store.open_intents(conn, folder)
            except Exception as exc:      # a record nobody can read names nothing it can prove
                log.warning("Could not read %s's open intents: %s", folder.name, exc)
                continue
            for intent in intents:
                for op in intent.get(ledger.OPS_KEY) or []:
                    if op.get(ledger.OP_KEY) == ledger.OP_REMOVE:
                        continue
                    if locate(folder, str(op.get(ledger.FROM_KEY) or "")) != path:
                        continue
                    expected = str(op.get(ledger.DIGEST_KEY) or "")
                    if digest is None:
                        digest = _the_bytes(path) or ""
                    if not expected or expected == digest:
                        return True
    return False


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
            reserved={}, dry_run=dry_run, report=report,
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
    # Every working copy the record names, proved against the row's own
    # fingerprint, and every file the record does not name, identified by
    # it (decision 109). It runs before the rows below are read, so what
    # follows sees the rows as this sweep leaves them; a dry run reads all
    # of it and records none of it, like everything else. Which files are a
    # request's is their names' to say (decision 168), the same reading
    # the scanner counts by.
    assigned = assign_files(run.context.prepared_dir, [i.identifier for i in items])
    sweep, swept, said = _prove_working_copies(
        engagement_dir, run.context.prepared_dir, entries, cache, stamp,
        {path for paths in assigned.values() for path in paths}, dry_run=dry_run,
    )
    report.attention.extend(sweep)
    run.swept = swept
    run.absence_said = {key: [line] for key, line in said.items()}
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
        line = FileError(earlier.original_name, MISSING_IN_PBC.format(
            location=earlier.pbc_location, received=earlier.received,
        ), True)
        run.report.attention.append(line)
        # Kept by the row's key, so the same pass can take it back if the
        # original comes home through the inbox (decision 157, ruling B7).
        run.absence_said.setdefault(ledger_key(earlier), []).append(line)
    # An original replaced under its own name is said loudly, every run,
    # until a person has looked; it is not sorted again and not guessed.
    # An attachment taken out of an email or a zip rests under _Opened, and
    # a file replaced there is said the same way (decision 143's review,
    # B2): the row's location is the file taken out, like any original's.
    for folder in (originals_dir, opened_dir_of(engagement_dir)):
        for path, earlier in (replaced_in_pbc(folder, engagement_dir, run.entries)
                              if folder.is_dir() else []):
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
    first: _ReturnRun,
) -> None:
    """Decide and record every drop and every stray, one at a time, across
    the household's returns.

    Each file is handled on its own: a file the sync client still holds
    open is left in place for the next run, and one that fails *after* it
    was preserved is recorded as needing review with the error, so no one
    bad file costs the rest of the pass or the audit trail. The caller
    writes each return's record whatever happens in here.

    ``first`` is the first of the **dropping household's own** returns
    (decision 129): whatever the inbox says about itself, and whatever
    could not be handled at all, is the household's and belongs where a
    person looking at that household will read it - never in a return
    another household's person works.

    **A row's own original coming back goes home first** (decision 157,
    ruling B7): before a drop is moved or decided, a drop whose bytes are
    those of exactly one row whose recorded original is gone is that
    original, and :func:`_put_back_home` moves it back to the recorded
    place - no new row, no Duplicate replacing the row it came back to.
    """
    dry_run = first.context.dry_run
    inbox = inbox_of(first.engagement_dir)
    away = _originals_away(runs)
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

        # A row's own original, back in the inbox (decision 157, ruling B7):
        # its bytes are the one row's whose recorded original is gone. Asked
        # only while some row's original is gone, so an ordinary pass hashes
        # no drop twice. Two rows answering is a guess, and takes the
        # ordinary road below.
        if not already_filed and away:
            coming_back = _digest_or_none(drop)
            if coming_back and len(away.get(coming_back, ())) == 1:
                [(home_run, position)] = away.pop(coming_back)
                if _put_back_home(drop, coming_back, home_run, position, stamp, inbox, first):
                    continue

        # The original moves once, out of the inbox into the folder the
        # client can see for the year, and never again (decision 125): its
        # resting place is the record's identity for the document. The move
        # is a rename and decision 23 finishes it whichever side of a kill
        # it falls on - an original in that folder with no row is sorted
        # where it lies - so no intent is written for it.
        #
        # It keeps its own name unless another file has it - on the disk, or
        # on a row of any of the household's returns (decision 147): a name
        # a deleted original left is still that row's, whatever the bytes
        # (decision 157) - the row's own coming back went home above.
        if already_filed or dry_run:
            original = drop if already_filed else originals_dir / drop.name
        else:
            try:
                original = _unique_path(
                    originals_dir, drop.name,
                    recorded=_taken_in_the_year(first, runs))
                _move_whole(drop, original, within=inbox)
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

        # An email or a zip is opened, and each attachment decided as a
        # document of its own (decision 143) - after the move and the
        # fingerprint, so the container is first an ordinary original with
        # a row of its own, and a re-send of the same bytes is a plain
        # duplicate that is never opened again. The extension alone says
        # what is a container; one past the size ceiling is never read and
        # parks unread like any drop.
        opening = (containers.is_container(drop.name) and bool(digest)
                   and not any(digest in run.known for run in runs)
                   and not too_large_reason(recorded_at))
        subfolder = "" if already_filed else _subfolder_of(drop, inbox)
        came_from = CAME_FROM_SUBFOLDER.format(folder=subfolder) if subfolder else ""
        for run in runs:
            run.context.came_from = came_from
        try:
            if opening:
                _open_container(drop, original, recorded_at, digest, size_kb, stamp, runs, first)
                continue
            decided = _decide_across(drop, original, digest, size_kb, stamp, runs, first)
            if decided is None:
                # The reader could not start (decision 150): the machine's
                # fault, not the file's, so nothing is decided and nothing
                # recorded. A drop already moved rests in the year's folder
                # with no row - a stray - and the next pass routes it where
                # it lies; the pass's one warning says how many wait.
                log.warning("Left %s for the next pass: the reader could not start", drop.name)
                continue
            run, entry = decided
        except Exception as exc:  # the original is safe; say so and go on
            log.exception("Could not file %s", drop.name)
            run = first
            entry = IndexEntry(
                received=stamp, original_name=drop.name, size_kb=size_kb,
                digest=digest, identifier="",
                prepared_location="", pbc_location=location_of(run.engagement_dir, original),
                decision=NEEDS_REVIEW,
                reason="; ".join(part for part in (
                    f"could not be filed ({exc.__class__.__name__}: {exc}); "
                    f"original preserved in {location_of(run.engagement_dir, original)} - "
                    f"file it by hand", came_from) if part),
            )
            run.report.errors.append(FileError(drop.name, entry.reason, False))
            run.report.review.append(entry)
        finally:
            for one in runs:
                one.context.came_from = ""

        run.entries.append(entry)
        if entry.decision != DUPLICATE and digest:
            run.known[digest] = entry


def _originals_away(runs: list[_ReturnRun]) -> dict[str, list[tuple[_ReturnRun, int]]]:
    """Every row of these returns whose recorded original is gone, by its
    bytes: what a drop may be coming back to (decision 157, ruling B7).

    Read once per sort, after the rows that followed an original the client
    moved have followed it. Left out: a row with no fingerprint (decision
    65, nobody's), a document taken out of an email or a zip (its original
    rests in the private ``_Opened`` folder, which no client drop goes
    back into), a row a person marked missing (:func:`marked_missing` - the
    client was asked again, so the same bytes are a new arrival), a row a
    person set aside (``NOT_REQUESTED``: decision 111 routes the same bytes
    sent again afresh, because the list may have gained their request since;
    the review's S-2), and a place an open intent will still write to
    (decision 147's ``intended``).
    """
    away: dict[str, list[tuple[_ReturnRun, int]]] = {}
    for run in runs:
        for position in _missing_positions(run.engagement_dir, run.entries):
            entry = run.entries[position]
            if not entry.digest or entry.container or entry.decision == NOT_REQUESTED:
                continue
            if locate(run.engagement_dir, entry.pbc_location) in run.context.intended:
                continue
            away.setdefault(entry.digest, []).append((run, position))
    return away


def _put_back_home(
    drop: Path, digest: str, run: _ReturnRun, position: int, stamp: str, inbox: Path,
    first: _ReturnRun,
) -> bool:
    """Move a row's own original, dropped back into the inbox, to the place
    its row names, under the recorded name (decision 157, ruling B7; audit
    C5; 147's review, N-4). True when the drop is dealt with, here or left
    in place; False where the recorded place is no longer free, and the
    drop takes the ordinary road.

    **No new row.** Until this decision the drop rested under its own name
    (:func:`_unique_path`'s old exception) and was then sorted as a new
    arrival: a Duplicate row, keyed by that very place, replaced the Filed
    row it came back to, and the client's README said the document never
    arrived. Here the row it came back to gets one sentence
    (:data:`RETURNED_SENTENCE`) and one row event
    (``ledger.ORIGINAL_RETURNED``), and the move is one intent (decision
    119), so a pass killed half way is finished from the record.

    Where the row's working copy and original were both gone (ruling B5),
    the copy is made again from the original in the same intent (ruling
    B4) and the row is filed again, so the pass that brings the original
    back does not end saying the row has neither. And whatever this pass
    already said about the row being gone - ``MISSING_IN_PBC``, the
    both-gone line - is taken back: a pass that puts an original back must
    not end with a warning that it is missing. A dry run says it and moves
    nothing.
    """
    engagement_dir = run.engagement_dir
    entry = run.entries[position]
    home = locate(engagement_dir, entry.pbc_location)
    if not _absent(home):
        return False                 # somebody's file is there now: never over it
    key = ledger_key(entry)
    arrived = Path(os.path.relpath(drop, inbox)).as_posix()
    said = RETURNED_SENTENCE.format(drop=arrived, date=stamp, pbc=entry.pbc_location)
    copies = ([location for location in entry.filed_locations
               if _absent(locate(engagement_dir, location))] if both_gone(entry) else [])
    if copies:
        remade = REMADE_SENTENCE.format(home=PLACES_JOINED.join(copies), pbc=entry.pbc_location,
                                        date=stamp, prepared=PREPARED_DIR_NAME)
        new = replace(entry, decision=FILED if entry.identifier else NEEDS_REVIEW,
                      reason=f"{_without_moved_sentence(entry.reason)}; {said}; {remade}")
        said = f"{said}; {remade}"
    else:
        new = replace(entry, reason=_before_the_moved_sentence(entry.reason, said))
    if not run.context.dry_run:
        ops = [_op(engagement_dir, ledger.OP_MOVE, drop, home, digest)]
        ops += [_op(engagement_dir, ledger.OP_COPY, home, locate(engagement_dir, location), digest)
                for location in copies]
        _intend(engagement_dir, key, ops, by=ledger.BY_PASS, row=entry_to_json(new),
                then=ledger.ORIGINAL_RETURNED)
        done: list[dict] = []
        try:
            for op in ops:
                _do_op(engagement_dir, op, cache=run.cache)
                done.append(op)
        except (OSError, FilingError) as exc:
            _take_back(engagement_dir, done)
            _abandon(engagement_dir, key)
            first.report.errors.append(FileError(
                drop.name, f"could not be moved back to {entry.pbc_location} ({exc}); left in place",
                True))
            log.warning("Left %s in place: moving it back to %s failed: %s",
                        drop.name, entry.pbc_location, exc)
            return True
        run.entries[position] = new
        run.swept[key] = ledger.ORIGINAL_RETURNED
    for line in run.absence_said.pop(key, []):
        if line in run.report.attention:
            run.report.attention.remove(line)
    run.report.attention.append(FileError(drop.name, said, True))
    log.warning("%s is the original recorded at %s, back in the inbox; moved back",
                arrived, entry.pbc_location)
    return True


def _take_back(engagement_dir: Path, done: list[dict]) -> None:
    """Undo the operations of an intent this call made before one failed,
    newest first: a copy it made is removed while it still holds the bytes
    it was made with, and a move is moved back. Never anything else - the
    machine deletes only a copy it has just made, and only by its bytes."""
    root = root_of(engagement_dir)
    for op in reversed(done):
        source = locate(engagement_dir, op[ledger.FROM_KEY])
        target = locate(engagement_dir, op[ledger.TO_KEY])
        try:
            if op[ledger.OP_KEY] == ledger.OP_MOVE:
                _move_whole(target, source, within=root)
            elif _the_bytes(target) == op.get(ledger.DIGEST_KEY):
                target.unlink()
        except OSError as exc:
            log.error("Could not undo %s of %s after a later step failed: %s",
                      op[ledger.OP_KEY], target.name, exc)


# ------------------------------------------------------ an email or a zip ----

#: The longest stem an opened container's folder takes, so the names of
#: what came out of it keep their room under the path limit (decision 131).
_OPENED_STEM = 40
#: What a container's folder is called when its own name leaves nothing.
_OPENED_FALLBACK = "container"
#: Room kept, in an attachment's name, for the temporary name its atomic
#: write passes through beside it (``fsio.temp_path_for``: a process id, a
#: tag and the suffix).
_TEMP_ROOM = 24

#: What a pass says of a file under the hidden folder of what was taken out
#: of emails and zips (``layout.OPENED_DIR_NAME``) that no row names, and of
#: a folder there whose container has no row (decision 143). Said every
#: pass, as an unrecorded working copy is; nothing there is re-sorted, and
#: nothing is ever deleted.
UNRECORDED_OPENED = ("{location} came out of an email or zip and no row names it; it is left "
                     "where it is - a person should look")
OPENED_CONTAINER_GONE = ("{location} holds what was taken out of an email or zip whose own row "
                         "is gone; it is left where it is - a person should look")


def _opened_sentence(opened: containers.Opened) -> str:
    """The container row's Reason: how many documents came out, and how many
    parts were left inside."""
    n = len(opened.attachments)
    said = OPENED_SENTENCE.format(n=n, documents="document" if n == 1 else "documents")
    if opened.skipped:
        said = f"{said}; {OPENED_SKIPPED.format(m=len(opened.skipped))}"
    return said


def _keep(run: _ReturnRun, entry: IndexEntry, digest: str) -> None:
    """One decided row into its return's index, and its bytes into what the
    return is known to hold - exactly what the sort's own loop does."""
    run.entries.append(entry)
    if entry.decision != DUPLICATE and digest:
        run.known[digest] = entry


def _opened_folder(home: _ReturnRun, original: Path, runs: list[_ReturnRun]) -> Path:
    """The folder what comes out of ``original`` is written into: the
    container's own name without its extension, cut to fit, under the
    household-year's hidden folder in the private tree - numbered ``(n)``
    where another container's documents already rest under that name.

    Whose a folder is, is read off the rows: a folder is another
    container's when a row rests inside it naming a different container.
    One that holds only files no row names is this container's - a pass
    killed after writing them and before recording anything left it, and
    reopening reuses what it finds there by its bytes.
    """
    base = opened_dir_of(home.engagement_dir)
    stem = original.stem[:_OPENED_STEM].rstrip(". ") or _OPENED_FALLBACK
    elsewhere: set[Path] = set()
    for run in runs:
        for entry in run.entries:
            if not entry.container or not entry.pbc_location:
                continue
            if locate(run.engagement_dir, entry.container) != original:
                elsewhere.add(locate(run.engagement_dir, entry.pbc_location).parent)
    counter = 1
    while True:
        folder = base / _named(stem, counter, "")
        if folder not in elsewhere:
            return folder
        counter += 1


def _take_out(folder: Path, attachment: containers.Attachment, claimed: set[Path], *,
              recorded: Mapping[Path, str] | None = None) -> tuple[Path, str]:
    """Write one attachment into its container's folder, whole or not at
    all, and say where and what bytes (decision 143).

    Its own name, cut to the room the folder leaves for its extension
    (decision 131), numbered ``(n)`` past a name this container already
    used. A file already there holding these very bytes is reused - a pass
    killed after writing it opens the container again - and one holding
    other bytes is kept, the new one taking the next number: nothing found
    there is ever overwritten. Named by the one numbering function
    (:func:`_unique_path`, decision 147), so a name a row still names
    (``recorded``) is taken here too - whatever the bytes, since decision
    157: a file on the disk holding these bytes is reused, a name only a
    row holds is never handed back.
    """
    data = attachment.data
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(attachment.name).suffix
    if suffix and not _AN_EXTENSION.fullmatch(suffix):
        suffix = ""
    folder.mkdir(parents=True, exist_ok=True)
    target = _unique_path(folder, attachment.name, room=limit_for(suffix) - len(str(folder)) - 1,
                          spare=_TEMP_ROOM, recorded=recorded, digest=digest, reuse=True,
                          claimed=claimed)
    if not target.exists():
        write_bytes_atomically(target, data)
    claimed.add(target)
    return target, digest


def _open_container(
    drop: Path, original: Path, recorded_at: Path, digest: str, size_kb: float, stamp: str,
    runs: list[_ReturnRun], first: _ReturnRun,
) -> None:
    """Open one email or zip, take each attachment out, and decide each as a
    document of its own (decision 143). Every row it makes goes into its
    return's index here; nothing is returned.

    In order - and the order is the crash story:

    1. **opened in memory**, in the reading's child the pass can stop
       (:func:`tracker.containers.open_bounded`, decision 154).
       One that will not open - locked, damaged, past a limit, or with
       nothing attached - parks whole, with the sentence that says which,
       in the dropping household's own first return.
    2. **every attachment written**, atomically, into the container's
       folder under the household-year's hidden folder in the private tree
       - never into the tree the client is shared - **before** the
       container's row exists. A dry run opens in memory and writes nothing.
    3. **the container's row**, ``OPENED``, in the first own return: it
       belongs to no request, its Reason says how many documents came out,
       and its journal line names each of them and each part left inside.
    4. **each attachment decided** exactly as a drop is - the bytes first,
       then one reading judged against every return, then the name, then
       exactly one - with its row naming the container, and its copy made
       under the intent that comes first (decision 119). An attachment
       whose file a row already names was recorded by the recovery of a
       killed pass, and is not decided twice.

    A pass killed before the record leaves the container with no row: the
    next pass finds it as a stray in the year's folder and opens it again,
    reusing each file it finds by its bytes. Anything raised before step 3
    is the sort loop's to catch: the container parks as a drop that could
    not be filed, with nothing of its own yet in any index.
    """
    home = first
    try:
        opened = containers.open_bounded(recorded_at)
    except containers.NotOpened as exc:
        _keep(home, _park_it(drop, original, digest, size_kb, stamp, home,
                             reason=exc.sentence, candidates=(), evidence=""), digest)
        return
    if opened is None:
        # The opener's child could not start (decision 154, 150's rule):
        # the machine's fault, not the file's. Nothing was written and
        # nothing is recorded; the container rests in the year's folder as
        # a stray and is opened next pass. The pass's one warning names it.
        home.reopen.add(_opened_folder(home, original, runs))
        log.warning("Left %s for the next pass: the opener could not start", drop.name)
        return
    dry_run = home.context.dry_run
    # The container's own row says the subfolder it came from (decision
    # 147); the attachments' rows do not - each attachment's decision
    # clears it, so it is read here, before any of them.
    came_from = home.context.came_from
    at = {id(run): location_of(run.engagement_dir, original) for run in runs}
    folder = _opened_folder(home, original, runs)
    claimed: set[Path] = set()
    taken: list[tuple[containers.Attachment, Path, str]] = []
    in_the_year = {} if dry_run else _taken_in_the_year(home, runs)
    for one in opened.attachments:
        if dry_run:
            taken.append((one, folder / one.name, hashlib.sha256(one.data).hexdigest()))
        else:
            taken.append((one, *_take_out(folder, one, claimed, recorded=in_the_year)))
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb, digest=digest,
        identifier="", prepared_location="", pbc_location=at[id(home)], decision=OPENED,
        reason="; ".join(part for part in (_opened_sentence(opened), came_from) if part),
    )
    home.opened[ledger_key(entry)] = {
        ledger.ATTACHMENTS_KEY: [
            {"name": one.name, "size": len(one.data), "digest": sha,
             "location": "" if dry_run else location_of(home.engagement_dir, path)}
            for one, path, sha in taken
        ],
        ledger.SKIPPED_KEY: [{"name": one.name, "why": one.why} for one in opened.skipped],
    }
    if dry_run:
        home.report.opened.append(entry)
        _keep(home, entry, digest)
        return
    named = _on_record((run.engagement_dir, run.entries) for run in runs)
    waiting = [one.name for one, path, sha in taken
               if path not in named
               and not _decide_attachment(one, path, sha, stamp, runs, first, at)]
    if waiting:
        # The reader could not start on an attachment (decision 150): the
        # machine's fault, not the file's, so that attachment gets no row -
        # and neither does the container, or the next pass would know its
        # bytes and never open it again. It rests in the year's folder as
        # a stray; the next pass reopens it, reuses each file it finds by
        # its bytes, skips each attachment a row already names, and reads
        # the one that waited. The pass's one warning says how many wait.
        home.opened.pop(ledger_key(entry), None)
        home.reopen.add(folder)
        log.warning("Left %s for the next pass: the reader could not start on %s",
                    drop.name, ", ".join(waiting))
        return
    home.report.opened.append(entry)
    _keep(home, entry, digest)


def _decide_attachment(
    attachment: containers.Attachment, path: Path, digest: str, stamp: str,
    runs: list[_ReturnRun], first: _ReturnRun, at: dict[int, str],
) -> bool:
    """Decide one attachment, already written at ``path``, as a drop is
    decided, with every row it writes naming its container - False, with
    nothing recorded, where the reader could not start on it (decision
    150's :func:`_not_read`), True otherwise.

    It is read exactly as a drop is, through :func:`_decide_across` and so
    through :func:`tracker.router.read_once`: the open test and the whole
    reading run in decision 150's child, under the safety stop, and a
    reading that stopped or crashed parks the attachment as it parks a drop.

    It is judged under its own name - ``drop`` carries the attachment's
    name, ``original`` is the file taken out - so the row, the review copy
    and the timing all say what the client called it. One handed back with
    a sentence of its own (a container nested too deep, or one that would
    not open) parks with it, unless its bytes are already on record. A
    failure is caught here, per attachment, as the sort's own loop catches
    one per drop: the file is safe where it was written, and the row says
    so.
    """
    size_kb = round(len(attachment.data) / 1024, 1)
    named = path.with_name(attachment.name)
    outer = {id(run): run.context.came_from for run in runs}
    for run in runs:
        run.context.container = at[id(run)]
        run.context.came_from = ""
    try:
        if attachment.parks and not any(digest in run.known and _may_hold(run) for run in runs):
            run, entry = first, _park_it(named, path, digest, size_kb, stamp, first,
                                         reason=attachment.parks, candidates=(), evidence="")
        else:
            decided = _decide_across(named, path, digest, size_kb, stamp, runs, first)
            if decided is None:
                return False
            run, entry = decided
    except Exception as exc:          # the file is safe where it was written; say so and go on
        log.exception("Could not file %s", attachment.name)
        run = first
        where = location_of(run.engagement_dir, path)
        entry = IndexEntry(
            received=stamp, original_name=attachment.name, size_kb=size_kb, digest=digest,
            identifier="", prepared_location="", pbc_location=where, decision=NEEDS_REVIEW,
            reason=(f"could not be filed ({exc.__class__.__name__}: {exc}); "
                    f"taken out to {where} - file it by hand"),
            container=at[id(run)],
        )
        run.report.errors.append(FileError(attachment.name, entry.reason, False))
        run.report.review.append(entry)
    finally:
        for one in runs:
            one.context.container = ""
            one.context.came_from = outer[id(one)]
    _keep(run, entry, digest)
    return True


def _unaccounted_in_opened(first: _ReturnRun, runs: list[_ReturnRun]) -> list[FileError]:
    """What sits in the household-year's hidden folder of opened emails and
    zips that the record does not account for (decision 143).

    A file no row names, and a container's folder whose container has no
    row, are said the way an unrecorded working copy is - a warning with
    its path, every pass - and nothing is re-sorted or deleted: a person
    looks. Read against the union of every return's rows, as the year's
    folder of originals is.
    """
    base = opened_dir_of(first.engagement_dir)
    if not base.is_dir():
        return []
    named: set[Path] = set()
    came_from: dict[Path, set[Path]] = {}
    for run in runs:
        for entry in run.entries:
            if not entry.pbc_location:
                continue
            path = locate(run.engagement_dir, entry.pbc_location)
            named.add(path)
            if entry.container:
                came_from.setdefault(path.parent, set()).add(
                    locate(run.engagement_dir, entry.container))
    said: list[FileError] = []
    for path in sorted(base.rglob("*")):
        if (not path.is_file() or path.name.endswith(TEMP_SUFFIX) or path in named
                or path.parent in first.reopen):
            continue
        where = location_of(first.engagement_dir, path)
        said.append(FileError(path.name, UNRECORDED_OPENED.format(location=where), True))
    for folder, sources in sorted(came_from.items()):
        # A container this pass left unrecorded because the reader could
        # not start on an attachment (decision 150) is not gone: it is a
        # stray the next pass opens again.
        if (folder.parent != base or folder in first.reopen
                or all(one in named for one in sources)):
            continue
        where = location_of(first.engagement_dir, folder)
        said.append(FileError(folder.name, OPENED_CONTAINER_GONE.format(location=where), True))
    return said


class _NoRouting:
    """A routing that said nothing: no evidence of its own."""

    evidence_record: dict = {}


_NO_ROUTING = _NoRouting()

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
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str, runs: list[_ReturnRun],
    first: _ReturnRun,
) -> tuple[_ReturnRun, IndexEntry] | None:
    """Which of the household's returns this one preserved original belongs
    to, and the row that says so - or None where the reader could not
    start on it (:func:`_not_read`), which decides nothing and records
    nothing.

    In order (decisions 125 and 128):

    - **the bytes first.** Every return's record is asked whether it
      already holds them, in the order the runs were handed in - own
      returns first, then fed - and the first that does decides, by
      decision 111's rule, in its own record: the record closest to the
      drop decides. The content hash identifies; the earlier decision
      decides. There is no exception (decision 132): a document a person
      filed under another return leaves no row here, so a record holding
      the bytes holds the document;
    - **then the requests.** The document is read **once**
      (:func:`tracker.router.read_once`) and that one reading is routed
      against every return's list, in order, so a two-return household
      costs one reading and never OCRs a photo twice;
    - **then the name.** Whose document this is is asked of the same
      reading, against each accepting return's own people list
      (:func:`_by_the_name`): two 1040s share every row of their lists, so
      the keywords cannot say whose W-2 this is and the name can;
    - **then exactly one.** Exactly one return left files it - moving the
      original a second time where that return lives in another household
      (decision 129); several park it naming them all; none parks it. A
      park always lands in the dropping household's own home return
      (:func:`_the_home`), with the name's reason where the name is what
      emptied the list. That is the third standing rule - nothing is
      guessed - read across the feed list instead of across one list.
    """
    if digest:
        holders = [run for run in runs if digest in run.known]
        # Out of an email or a zip (decision 143, ruling 7 and the review's
        # B1): a return in another household is not asked. Its record would
        # otherwise take a Duplicate row naming this household's attachment
        # and the private _Opened path it rests under - the other
        # household's record reached by the bytes, where the requests may
        # never reach it. A loose drop is asked as decision 132 says.
        mine = [run for run in holders if _may_hold(run)]
        if mine:
            # Own returns first, as they are handed in (decision 132's
            # second order; the locks were taken in the global one).
            run = mine[0]
            return _sort_one(drop, original, digest, size_kb, stamp, run, runs)
        if holders:
            # Only another household holds these bytes: the attachment
            # waits at home, in the words a first arrival gets, and nothing
            # is written in that household's record.
            home = next((one for one in runs if one.home), first)
            return home, _park_it(drop, original, digest, size_kb, stamp, home,
                                  reason=reasons.OPENED_NOT_ACROSS.format(),
                                  candidates=(), evidence="")

    # One reading, however many returns judge it (decision 128). A dry run
    # judges the drop where it lies, as it always has.
    judged = drop if runs[0].context.dry_run else original
    reading = read_once(judged)
    if _not_read(reading):
        return None
    # What the reading cost, kept for the run's summary (decision 127). One
    # reading serves every return that judges it (decision 128), so it is
    # recorded once, against the pass's first own return (``first``, the
    # run the inbox's own notes ride) - the run that already speaks for
    # this household's inbox. It is recorded after the fact and changes
    # nothing: a slow document is read to the end, and then said.
    first.report.timed(drop.name, reading.seconds)
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

    no_room: NoRoom | None = None
    unnamed_across = opened_across = False
    if len(kept) == 1:
        run, routing = kept[0]
        item = run.context.by_id.get(routing.identifier or "")
        # Out of an email or a zip (decision 143): the attachment's original
        # is the firm's copy of a part of the client's file, and it never
        # moves into another household's folder. It waits at home, named
        # or not, for a person to file it by hand.
        if item is not None and _across_households(run) and run.context.container:
            opened_across, item = True, None
        # Across households, filing needs a confirmed name (decision 137,
        # B2; the owner's Q-2). A document the name tier kept only because
        # its request is unnamed would otherwise move into another
        # household's folder, which that household's people can open, on
        # the strength of its keywords alone. It waits at home for a person.
        if item is not None and _across_households(run) and id(run) not in stage.confirmed:
            unnamed_across, item = True, None
        if item is not None:
            try:
                return run, _file_it(drop, original, digest, size_kb, stamp, run, routing, item,
                                     confirmed=stage.confirmed.get(id(run), ""))
            except NoRoom as exc:
                # Every rule accepted it and Prepared has no room for even
                # the request's shortest name (decision 131): the last
                # reason the filing branch can give. It parks, and the
                # request that accepted it is its candidate.
                no_room = exc

    # Nothing may be filed, so the document waits where it was dropped
    # (decision 129): the original rests under the household the return
    # that takes it lives in, and until a person says which return that
    # is, the household that was dropped in is the one that has it.
    home, home_routing = _the_home(accepting, routed, runs)
    home_routing = stage.graded.get(id(home), home_routing)

    if no_room is not None:
        said = routing if home is run else home_routing
        # A request in a return this drop folder feeds is named by that
        # return's label (decision 131's review, deviation 5): the row
        # parks at home, where "this request" would be a list the person
        # reading it is not looking at.
        reason = str(no_room) if home is run else PATH_NO_ROOM_IN.format(
            label=run.label, length=no_room.length, limit=no_room.limit,
            ext=_kind_of(no_room.extension))
        return home, _park_it(
            drop, original, digest, size_kb, stamp, home,
            reason=reason, candidates=said.candidates,
            evidence=format_evidence(said.evidence_record),
        )

    if opened_across:
        return home, _park_it(
            drop, original, digest, size_kb, stamp, home,
            reason=reasons.OPENED_NOT_ACROSS.format(),
            candidates=home_routing.candidates,
            evidence=_with_the_wanting_return(home_routing, run, routing),
        )

    if unnamed_across:
        return home, _park_it(
            drop, original, digest, size_kb, stamp, home,
            reason=reasons.UNNAMED_ACROSS_HOUSEHOLDS.format(),
            candidates=home_routing.candidates,
            evidence=_with_the_wanting_return(home_routing, run, routing),
        )

    if len(kept) > 1:
        # Two returns ask for the same row - two 1040s share every row of
        # their lists - and the name did not tell them apart either, which
        # since decision 128 means a page naming both spouses. The sentence
        # names every return that accepted it, by its label, and the
        # requests each accepted it under, so the person choosing is
        # choosing from what the tracker saw; since decision 129 one of
        # them may live in another household, and its label is how the row
        # names it - never who is shared on it.
        listed = "; ".join(f"{run.label}: {', '.join(one.filed_to)}" for run, one in kept)
        return home, _park_it(
            drop, original, digest, size_kb, stamp, home,
            reason=CONTESTED_BETWEEN_RETURNS.format(listed=listed),
            candidates=home_routing.candidates,
            evidence=format_evidence(home_routing.evidence_record),
        )

    # Nothing left at all. Where the name is what emptied the list, the row
    # says so in the name's own words rather than the router's "matched no
    # request", which would be a lie about a W-2 the list plainly wanted.
    return home, _park_it(
        drop, original, digest, size_kb, stamp, home,
        reason=stage.reason or home_routing.reason, candidates=home_routing.candidates,
        evidence=format_evidence(home_routing.evidence_record),
    )


def _not_read(reading) -> bool:
    """Whether the reader could not start on this document at all
    (decision 150, the designer's ruling on the re-review).

    That is the machine's fault - antivirus refusing the second process, a
    build missing a module, memory - and never the file's, so it must leave
    nothing permanent, and a routing decision is as permanent as a kept
    verdict: a Needs Review row makes the original a non-stray for ever,
    and a good W-2 would wait for a person after the machine was fixed. So
    the drop is not decided and not recorded, the shape of
    :func:`unfinished_drops`: what was not yet moved stays in the inbox,
    what was moved rests in the year's folder with no row, and the next
    pass reads it again as a stray. The reader that started and then died
    is the file's (``READING_CRASHED``) and is decided as before.
    """
    return bool(reading.transient) and reasons.READER_UNAVAILABLE.matches(reading.reason)


def _across_households(run: _ReturnRun) -> bool:
    """Whether ``run`` lives in another household than the one the drop was
    made in, so filing there would move the original into a folder other
    people are shared on (decision 129's feeds).

    Read off the run itself: ``home`` marks the dropping household's own
    returns, and every other run is one its drop folder feeds. Never
    against a "first" run, which falls back to a fed return when a
    household has none of its own (decision 137's review, B #4)."""
    return not run.home


def _may_hold(run: _ReturnRun) -> bool:
    """Whether ``run``'s record may answer for the bytes of the document
    being decided (decision 143's review, B1): any return for a loose drop
    (decision 132), and only the dropping household's own for an
    attachment, whose name and ``_Opened`` path never enter another
    household's record. ``context.container`` is set on every run around
    one attachment's decision, so the run itself says which it is."""
    return not (run.context.container and _across_households(run))


def _with_the_wanting_return(home_routing, run: _ReturnRun, routing) -> str:
    """The Evidence cell of a document B2 parked at home (decision 137's
    review, B #3): the home list's own evidence, then what the return in
    the other household accepted it under - keyed by that return's label
    and the request's identifier, so a person knows where **File it**
    goes. Only the firm's words travel: labels, identifiers and the
    keywords the row asked for, never a word of the document. The key is
    qualified by the label, so it can never be offered as a request of the
    home list's own that happens to share the identifier."""
    wanted = {f"{run.label} / {identifier}": found
              for identifier, found in routing.evidence_record.items()
              if identifier in routing.filed_to}
    return "; ".join(part for part in (format_evidence(home_routing.evidence_record),
                                       format_evidence(wanted)) if part)


def _the_home(accepting, routed, runs: list[_ReturnRun]) -> tuple[_ReturnRun, object]:
    """The return a document nobody may file parks in, and what its own
    request list made of it.

    Decision 125's home return, read across the feed list (decision 129):
    the **dropping household's own** return of the first request that
    accepted the document, and where none of its own did, its first return
    by order. A bank statement only the 1120S's list asks for, naming
    nobody, parks in the 1120S's queue - where the row that wanted it is -
    rather than in a 1040 that never asked for it; and a document only a
    **fed** return accepted parks at home all the same, because the
    original has not moved and the household that has it is the one that
    was dropped in.
    """
    for run, routing in [*accepting, *routed]:
        if run.home:
            return run, routing
    return routed[0]        # no own return at all: the caller's list is the household's


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
    dry_run: bool
    report: FileReport
    cache: ContentCache
    pdf_cache: PdfVerdictCache
    #: Where the email or zip the document being decided came out of rests,
    #: relative to this return (decision 143), and ``""`` for a document
    #: that arrived on its own. Set around one attachment's decision and
    #: cleared after it, so every row that decision writes - filed, parked
    #: or a duplicate, and the intent written before it - names its
    #: container, and a recovery records the row the decision would have.
    container: str = ""
    #: :data:`CAME_FROM_SUBFOLDER`, said, for a drop that came out of a
    #: subfolder of the inbox (decision 147), and ``""`` for any other. Set
    #: on every run around that drop's decision and cleared after it, as
    #: ``container`` is, so the row every road writes - filed, parked, a
    #: duplicate or the container's own - carries it, and so does the intent
    #: written before it. Cleared around an attachment's decision: what came
    #: out of a zip did not come out of the subfolder, the zip did.
    came_from: str = ""
    #: Every path an open intent of the household's pass will still write
    #: to (decision 147, the designer's ruling on deviation 3), read once
    #: per pass after recovery and set on every run: a name taken as a
    #: row's resting place is, for :func:`_taken_names`.
    intended: frozenset[Path] = frozenset()


def _plan_working_copy(
    item: RequestItem, drop: Path, original: Path, digest: str, run: _SortContext,
) -> tuple[str, Path | None]:
    """Where one working copy of a preserved original goes - in
    ``PREPARED_DIR_NAME`` itself, named by its request (decision 168) -
    and the file the copy will make there.

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
    forms under each of them, and each request numbers its own names - they
    share one folder, and differ at the identifier. The
    copy itself is :func:`_file_into`'s to write down and make, from where
    the original will rest - which, for a return in another household, is
    not where it is now (decision 129) - while the reuse check here reads
    the file that is there.
    """
    dest_folder = run.prepared_dir
    if dest_folder not in run.reserved:
        # The names taken are Prepared's own (decision 168, ruling 3): every
        # request's copies share it, and so does every name an open intent
        # will still write there (decision 147's ``intended``) - a copy
        # given one would be the copy a waiting filing lands on.
        run.reserved[dest_folder] = (
            {p.name.lower() for p in dest_folder.iterdir()}
            if dest_folder.is_dir()
            else set()
        ) | {path.name.lower() for path in run.intended if path.parent == dest_folder}
    # A copy already there is found before any name is measured (decision
    # 131's review, F5, as the hand-over does): a killed run's copy is
    # reused under the name it has, and a folder with no room for a new
    # name does not park a document whose copy is already in it. Only
    # among this request's own copies (decision 168): another request's
    # copy of the same page is that request's.
    if not run.dry_run:
        existing = _existing_copy(dest_folder, original, digest,
                                  among=copies_of(item, run.items, dest_folder))
        if existing is not None:
            return prepared_location(dest_folder, existing.name), None
    # Named to fit the room the folder leaves (decision 131): the exact
    # path about to be written is what is measured, so a root that grew,
    # a label the editor lengthened and the numbered suffix are all
    # counted. No room for even the shortest name raises NoRoom, and the
    # caller parks the document instead, with nothing made.
    extension = extension_of(drop)
    filed_as = prepared_name_for(item, extension, run.reserved[dest_folder],
                                 room=limit_for(extension) - len(str(dest_folder)) - 1)
    if run.dry_run:
        return prepared_location(dest_folder, filed_as), None
    return prepared_location(dest_folder, filed_as), dest_folder / filed_as


def _carry_out(entry: IndexEntry, ops: list[dict], then: str, run: _SortContext) -> None:
    """Write down what this drop's parked copy will be, then make it.

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


def _rests_at(run: _ReturnRun, original: Path, digest: str) -> Path:
    """Where this return's filing leaves the original.

    Where it is, for the household's own returns: an original moves once,
    out of the inbox into the year's folder the client can see, and never
    again (decision 125). For a return this drop folder **feeds**, one
    folder further (decision 129): the original must rest under the
    household its return lives in, seen by exactly that folder's sharing,
    so it moves a second time - and that move is the first step of the
    filing, written down before it happens like every other. Its name
    there is chosen as the inbox move's is: a name the disk holds, or a row
    of that household-year still names, is taken (decision 147, ruling 9) -
    whatever the bytes, since decision 157.
    """
    if not run.dropped_in:
        return original
    folder = originals_of(run.engagement_dir)
    if run.context.dry_run:
        return folder / original.name
    return _unique_path(folder, original.name, digest=digest, recorded=_taken_names(
        _year_on_record(run.engagement_dir, {run.engagement_dir: run.entries}), run.context.intended))


def _file_into(
    target: Path,
    original: Path,
    digest: str,
    *,
    resting: Path,
    copies: Sequence[Path],
    row: IndexEntry,
    then: str,
    by: str,
    also: Sequence[dict] = (),
    cache: ContentCache | None = None,
    dry_run: bool = False,
) -> None:
    """File one original into ``target`` - the one shape of a filing, the
    pass's and a person's alike (decision 132).

    Given the return that takes the document, the original where it is now,
    where it must rest (``originals_of(target)/<a unique name>`` where the
    household differs, the same place where it does not), the working
    copies still to be made and the row the caller composed, it writes the
    intent in **the target's own record**, keyed on the row's final
    location, with the operations ``[move original -> resting]`` (absent
    where the original already rests there) ``+ [copy resting -> each
    working copy]``, the event that will complete it (``then``:
    ``filed`` for the pass, ``assigned_by_person`` for a person) and the
    same-record events that travel with it (``also``: the keyword and the
    spelling a person's filing teaches) - and then does the operations.

    **Nothing here knows about a home return.** That is the point: a
    filing into a return in another household is that return's filing,
    finished from its record by any pass that holds its lock, whoever
    decided it. Nothing writes into another return's record, ever. The row
    itself is the caller's to record - the pass in the target run's one
    transaction, a person's call at once - and :func:`_existing_copy` and
    :func:`_unique_path` have already chosen the names. A name a vanished
    original left behind is still its row's (decision 147, ruling 9), so a
    different document never lands on it and never becomes that row's next
    version; that row's own bytes coming back go home through
    :func:`_put_back_home`, with no new row (decision 157).
    """
    ops = ([] if resting == original
           else [_op(target, ledger.OP_MOVE, original, resting, digest)])
    ops += [_op(target, ledger.OP_COPY, resting, copy, digest) for copy in copies]
    if dry_run or not ops:
        return
    _intend(target, ledger_key(row), ops, by=by, row=entry_to_json(row), then=then,
            also=list(also))
    for op in ops:
        _do_op(target, op, cache=cache)


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

    **Where the return lives in another household** (decision 129) the
    original moves a second time first, into that household's own folder
    for the year, and the row's Reason says which folder the document was
    dropped in (:data:`DROPPED_ELSEWHERE`) - so the destination's Status
    Report says where it came from, without naming a person.

    ``confirmed`` is what the name on the page said (decision 128), added
    last to the Reason: the firm's own spelling that matched, so a person
    reading the row a year later sees both that the keywords placed it and
    that the name agreed.
    """
    context = run.context
    wanted = [item] + [context.by_id[i] for i in routing.also if i in context.by_id]
    # Every copy is named before anything is written (decision 131): a
    # request with no room for even its shortest name raises NoRoom here,
    # the names this filing had claimed are handed back, and the caller
    # parks the document - nothing has moved yet.
    claimed = {folder: set(names) for folder, names in context.reserved.items()}
    try:
        planned = [_plan_working_copy(one, drop, original, digest, context) for one in wanted]
    except NoRoom:
        context.reserved.clear()
        context.reserved.update(claimed)
        raise
    resting = _rests_at(run, original, digest)
    locations = [location for location, _copy in planned]
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier=item.identifier,
        prepared_location=locations[0],
        pbc_location=location_of(run.engagement_dir, resting), decision=FILED,
        reason="; ".join(part for part in
                         (routing.reason, refiled, resent, confirmed, run.dropped_in,
                          context.came_from) if part),
        candidates=_CANDIDATE_SEP.join(routing.candidates),
        evidence=format_evidence(routing.evidence_record),
        also_filed=_CANDIDATE_SEP.join(locations[1:]),
        container=context.container,
        # Decision 146: the asked requests a consolidated statement answers
        # without a copy, as the routing named them - each still on this
        # return's list, since the routing was this list's.
        answers=format_answers([one for one in routing.answers if one[0] in context.by_id]),
    )
    # The move first, then the copies from where it will have moved to:
    # a step may stand on the one before it, and the recovery finishes
    # them in this order by bytes (decision 119).
    _file_into(run.engagement_dir, original, digest, resting=resting,
               copies=[copy for _location, copy in planned if copy is not None],
               row=entry, then=ledger.FILED, by=ledger.BY_PASS,
               cache=run.cache, dry_run=context.dry_run)
    run.report.filed.append(entry)
    return entry


def _review_copy_path(review_dir: Path, name: str) -> tuple[Path, str]:
    """Where a review copy goes, and what its row must say about it: the
    client's own name, cut to the room the review folder leaves (decision
    131). Every review copy is named here - the pass's park, the recovery's
    copy to act on, a person's unfiling and a refused put-back - so no copy
    anywhere is written past its limit.

    The row's ``original_name`` keeps the client's name whole - it is the
    record's, and the queue reads the row, not the copy. The room is the
    extension's (a reader's shorter limit cuts a workbook's name), but a
    reader's limit never stops a park: where it leaves no room, the copy is
    fitted to Windows's own and the second value is
    :data:`REVIEW_COPY_PAST_READER` for the row's reason, so the person is
    told the copy is there and may not open where it is. Where not even
    Windows's own leaves room, :class:`NoRoom` says a review copy could not
    be made (:data:`REVIEW_NO_ROOM`) - the pass's floor proves room for a
    short extension, not for every suffix a client's file can carry.
    """
    folder = len(str(review_dir)) + 1
    limit = limit_for(extension_of(Path(name)))
    try:
        return _unique_path(review_dir, name, room=limit - folder), ""
    except NoRoom:
        if limit >= MAX_PATH_LENGTH:
            raise
    return _unique_path(review_dir, name, room=MAX_PATH_LENGTH - folder), REVIEW_COPY_PAST_READER


def _park_it(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str,
    run: _ReturnRun, *, reason: str, candidates, evidence: str, resent: str = "",
) -> IndexEntry:
    """Park one preserved original in this return's Needs Review, with a
    working copy a person can open and the sentence that says why."""
    context = run.context
    review_name = drop.name
    parking: list[dict] = []
    past_reader = ""
    if not context.dry_run:
        # One row, one working copy. The copy already there holding these
        # bytes is the *set-aside* row's, and two rows naming one file would
        # let filing either of them carry the other's copy away, so a re-send
        # of set-aside bytes takes a fresh copy of its own. The person may
        # end with two identical files in review, which is the truthful
        # state: two arrivals, two decisions to make.
        review_target = None if resent else _existing_copy(context.review_dir, original, digest)
        if review_target is None:
            # Named before the folder is made: a name that cannot fit
            # (NoRoom, a review copy's sentence) leaves no empty folder, and
            # the pass records the drop as one that could not be filed.
            review_target, past_reader = _review_copy_path(context.review_dir, drop.name)
            parking.append(_op(run.engagement_dir, ledger.OP_COPY,
                               original, review_target, digest))
        context.review_dir.mkdir(parents=True, exist_ok=True)
        review_name = review_target.name
    reason = "; ".join(part for part in (resent, reason, context.came_from, past_reader) if part)
    entry = IndexEntry(
        received=stamp, original_name=drop.name, size_kb=size_kb,
        digest=digest, identifier="",
        prepared_location=prepared_location(context.review_dir, review_name),
        pbc_location=location_of(run.engagement_dir, original), decision=NEEDS_REVIEW,
        # The flag first: what a person opening the card should read before
        # the reason for parking it; the subfolder it came from (decision
        # 147) after it; a copy past a reader's limit, last.
        reason=reason,
        candidates=_CANDIDATE_SEP.join(candidates),
        evidence=evidence,
        container=context.container,
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
) -> tuple[_ReturnRun, IndexEntry] | None:
    """Decide one preserved original's fate inside the one return whose
    record already holds its bytes, and, unless dry-running, copy it - or
    None where it must be read afresh and the reader could not start
    (:func:`_not_read`).

    The road decision 111 laid: the content hash says *which* row already
    holds these bytes, and that row's decision says what this arrival is.
    A re-send whose earlier row was filed and whose copy is gone is filed
    again - and so is one whose earlier row has neither its copy nor its
    original, or was marked missing by a person (decision 157); one a
    person set aside is routed afresh against that return's list; anything
    else is a duplicate of the row that holds it.

    An attachment (decision 143) never arrives here with a return in
    another household: :func:`_decide_across` asks only the returns
    :func:`_may_hold` allows, so every road below - the duplicate row, the
    re-file and the set-aside re-route - stays in the dropping household.

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
        # Since decision 157 the pass makes such a copy again from the
        # original before it sorts, so this is the copy whose original
        # could not be read to make it (still syncing, or refused).
        refiled = (
            f"re-filed: the earlier copy {earlier.prepared_location} "
            f"was no longer in {PREPARED_DIR_NAME}"
        )
    elif both_gone(earlier) or marked_missing(earlier):
        # Decision 157: the earlier row has neither its copy nor its
        # original - said so by the sweep, or marked missing by a person, who
        # asked the client again. The same bytes arriving are the answer:
        # filed again, never a Duplicate of a row that holds nothing. (Where
        # the original was simply gone, the drop went home to its row before
        # it was sorted - ``_put_back_home``; this is the original that holds
        # other bytes now, and the row a person marked.)
        refiled = REFILED_AFTER_GONE.format(name=earlier.original_name)
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
            DUPLICATE_OF_OPENED if earlier.decision == OPENED else
            DUPLICATE_OF_UNCOPIED if not earlier.filed_as else
            {FILED: DUPLICATE_OF_FILED, NEEDS_REVIEW: DUPLICATE_OF_PARKED,
             FILE_MOVED: DUPLICATE_OF_MOVED}[earlier.decision]
        )
        said = words.format(name=earlier.original_name, copy=earlier.filed_as)
        entry = IndexEntry(
            received=stamp, original_name=drop.name, size_kb=size_kb,
            digest=digest, identifier=earlier.identifier,
            prepared_location="",
            pbc_location=location_of(run.engagement_dir, original), decision=DUPLICATE,
            reason="; ".join(part for part in (said, context.came_from) if part),
            container=context.container,
        )
        run.report.duplicates.append(entry)
        return run, entry

    judged = drop if context.dry_run else original
    reading = read_once(judged)
    if _not_read(reading):
        return None
    # What the reading cost, for the run's summary (decision 127).
    run.report.timed(drop.name, reading.seconds)
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
        if stage.kept and _across_households(run) and id(run) not in stage.confirmed:
            # A re-send whose bytes a return in another household already
            # holds is held to the same rule as a first arrival (decision
            # 137's review, B #5, the owner's "never"): unnamed, it is not
            # filed there, and parks in the drop's own household.
            home = next((one for one in runs if one.home), run)
            return home, _park_it(drop, original, digest, size_kb, stamp, home,
                                  reason=reasons.UNNAMED_ACROSS_HOUSEHOLDS.format(),
                                  candidates="",
                                  evidence=_with_the_wanting_return(_NO_ROUTING, run, routing),
                                  resent=resent)
        if stage.kept:
            _kept, routing = stage.kept[0]
            try:
                return run, _file_it(drop, original, digest, size_kb, stamp, run, routing, item,
                                     refiled=refiled, resent=resent,
                                     confirmed=stage.confirmed.get(id(run), ""))
            except NoRoom as exc:        # decision 131: no room even for the shortest name
                return run, _park_it(drop, original, digest, size_kb, stamp, run,
                                     reason=str(exc), candidates=routing.candidates,
                                     evidence=format_evidence(routing.evidence_record), resent=resent)
        routing = stage.graded.get(id(run), routing)
        return run, _park_it(drop, original, digest, size_kb, stamp, run,
                             reason=stage.reason or routing.reason, candidates=routing.candidates,
                             evidence=format_evidence(routing.evidence_record), resent=resent)
    return run, _park_it(drop, original, digest, size_kb, stamp, run,
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
    canonical name in ``PREPARED_DIR_NAME`` (decision 168) - moved from ``REVIEW_DIR_NAME`` when it is still there, copied from the year's folder when it is not -
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
    here", the answer to a copy somebody renamed under a request's name on
    purpose (decision 168; dragged into a request's folder until then). The
    copy that moves is then the wanderer the row's reason names
    (:func:`moved_to`), which takes the request's canonical name beside
    where it sits, or another request's when the person picks one instead:
    the picker is the same picker, so keeping the file
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
        if both_gone(entry) and _the_original_now(engagement_dir, entry)[0] != _ORIGINAL_PROVED:
            # Decision 157, B5: nothing to keep - the copy and the original
            # are both gone - in the one sentence the three answers share.
            raise FilingError(NOTHING_TO_PUT_BACK.format(
                prepared=PREPARED_DIR_NAME, pbc=entry.pbc_location))
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

        # The copy goes in the firm's folder itself, named by its request
        # (decision 168) - and so does a mislaid copy a person keeps where
        # it is, which only ever sits there (the app offers Keep it here
        # for nothing else): it takes the request's canonical name beside it.
        dest_folder = prepared_dir
        # Named to fit the room the folder leaves, before anything is made
        # (decision 131): no room even for the shortest name refuses with
        # PATH_NO_ROOM, and nothing has moved.
        taken = {p.name.lower() for p in dest_folder.iterdir()} if dest_folder.is_dir() else set()
        # A copy with these bytes already there is found before a name is
        # measured (decision 131's review, F5): it is reused under its own
        # name, so a folder short of room never refuses a filing it holds.
        # Only this request's own copies are looked at (decision 168).
        existing = _existing_copy(dest_folder, source, digest,
                                  ignore=parked if parked_here else None,
                                  among=copies_of(item, list(items.values()), dest_folder))
        extension = extension_of(source)
        filed_as = existing.name if existing is not None else prepared_name_for(
            item, extension, taken, room=limit_for(extension) - len(str(dest_folder)) - 1)
        dest_folder.mkdir(parents=True, exist_ok=True)
        target = dest_folder / filed_as

        moved = reused = parked_stood_in = False
        left_in_review = ""
        ops: list[dict] = []
        # A copy with these bytes already in the folder is a killed earlier
        # attempt's, and is reused rather than doubled. Otherwise the parked
        # copy is moved, but only while it holds the row's bytes: its name
        # is the client's, and a freed name is taken by the next drop called
        # the same, so a person filing row A would carry document B into
        # Prepared under A's canonical name (the eleventh reading); a
        # copy a reviewer's app re-saved is not the row's bytes either and
        # is left where it is, said so, for the person to keep or discard.
        # What will move is decided here and written down before any of it
        # happens (decision 119), so a kill in between is finished from the
        # record rather than left for another person to notice.
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
                        _move_whole(target, parked, within=engagement_dir)
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


# ------------------------------------------------------------- hand over ----


@dataclass(frozen=True, slots=True)
class HandedOver:
    """What handing one parked document to another return did (decisions 129
    and 132)."""

    entry: IndexEntry            # the row this return held, as it was; released now
    target_entry: IndexEntry     # the row the return that took it now holds
    target: Path                 # that return's folder
    label: str                   # and how it is named to a person
    moved_original: bool         # True: the original moved into the other household's year folder
    keyword: str = ""            # keyword added to the target's request, if any
    keyword_note: str = ""       # why it was not added, when it was not
    spelling: str = ""           # spelling added to one of the target's people, if any
    spelling_note: str = ""      # why it was not added, when it was not
    left_in_review: str = ""     # a parked copy that no longer held the row's bytes, and stayed
    overrode_shortlist: str = ""  # the sentence written when the pick was off the shortlist


def hand_over(
    home_return: Path | str,
    original: str,
    target_return: Path | str,
    identifier: str,
    *,
    seq: int | None = None,
    keyword: str = "",
    spelling: Spelling | None = None,
    shortlist: Sequence[str] | None = None,
    today: dt.date | None = None,
    lock_held: bool = False,
) -> HandedOver:
    """Hand one parked document to a return this drop folder feeds - two
    intents in two records, each finished by its own household's pass
    (decision 132, reshaping decision 129's queue half).

    A household's inbox feeds its own returns and the return lines a person
    extended it to, and a parked row can be filed under a request of **any**
    of them, own or fed. Under both locks, taken in the one global order
    (``layout.lock_order_key``; ``lock_held`` is for a caller that already
    has both), in the order that costs least under a kill:

    1. **the release intent, in this record**: remove the parked copy
       (only where it is there and still holds the row's bytes - otherwise
       it is left and said, ``left_in_review``), then release the row. It
       carries the row unchanged so a recovery can name the document, and
       the sentence the release will say; never the original, never the
       other record's half;
    2. **the filing intent, in the taking return's record**, through
       :func:`_file_into` - the pass's own shape: the original moves where
       it must rest (under the household the taking return lives in; not at
       all within one household) and the working copy is made there;
    3. the taking return's row, the person's own filing dated their day,
       with the keyword and the spelling it taught - closing step 2;
    4. the parked copy here goes, and the row is **released**: it leaves
       the index, and the journal line says which return took it
       (:data:`RELEASED_TO`) - closing step 1.

    **Why the release is written first.** A kill after step 1 alone leaves
    one open intent, here, that this household's own pass finishes with no
    other lock: the row is released and the original, still in this
    household's year folder and named by no row, is a stray the pass sorts
    again - one click is the whole cost. The other way round, a kill
    between the two would leave a parked row here whose original the taking
    return's recovery moves away.

    ``keyword`` and ``spelling`` teach the **taking** return, because that
    is the return the document is being filed in and the one that will see
    the next document like it. ``seq`` is this row's version as the person
    saw it (decision 112) and ``shortlist`` what the evidence pointed at,
    both used exactly as :func:`assign_review_file` uses them.
    """
    home_return, target_return = Path(home_return), Path(target_return)
    today = today or dt.date.today()
    if target_return == home_return:
        raise FilingError(f"{target_return.name} is the return this document is already in")
    with ExitStack() as locks:
        if not lock_held:
            for folder in sorted({home_return, target_return}, key=lock_order_key):
                locks.enter_context(engagement_lock(folder))
        ensure(home_return)
        ensure(target_return)
        _refuse_if_a_move_is_open(home_return)
        _refuse_if_a_move_is_open(target_return)

        items = {i.identifier: i for i in load_manifest(target_return)}
        item = items.get(identifier)
        if item is None:
            raise FilingError(f"no request {identifier!r} in the request list")
        if item.manual_override == Override.NOT_APPLICABLE:
            raise FilingError(f"{identifier} is {override_label(item)}; clear the override first")

        entries = read_index(home_return)
        position = find_parked(entries, original)
        entry = entries[position]
        _refuse_if_stale(home_return, entry, seq)
        # Out of an email or a zip (decision 143): the file is the firm's
        # copy of a part of the client's file, and never moves into another
        # household's folder - the pass parks it at home in these words,
        # and a person's hand-over refuses it in the same ones.
        if entry.container and household_of(target_return) != household_of(home_return):
            raise FilingError(reasons.OPENED_NOT_ACROSS.format())
        source = locate(home_return, entry.pbc_location)
        if not source.is_file():
            raise FilingError(f"the original {entry.pbc_location} is no longer there")
        if is_cloud_placeholder(source):
            raise FilingError(
                f"the original {entry.pbc_location} is still syncing; try again when it is here")
        digest = entry.digest
        if not digest:
            raise FilingError(
                f"the original {entry.pbc_location} has no fingerprint on this row; the next pass "
                f"records one, and a document can only be handed over once it has one"
            )
        if sha256_of(source) != digest:
            raise FilingError(
                f"the original {entry.pbc_location} no longer holds the bytes this row "
                "recorded - it was replaced after it arrived; look at the file first"
            )

        # Where the original will rest: under the household the taking
        # return lives in. Inside one household it is already there and
        # does not move - decision 125's "an original moves once" holds
        # for every filing within a household.
        moving_it = household_of(target_return) != household_of(home_return)
        # Named as the pass names it (decision 147, ruling 9): a name a row
        # of the taking household-year still names is taken.
        resting = (_unique_path(originals_of(target_return), source.name, digest=digest,
                                recorded=_year_on_record(target_return, {}))
                   if moving_it else source)

        # In the taking return's firm folder itself, named by the request
        # (decision 168), and reusing only that request's own copy.
        dest_folder = target_return / PREPARED_DIR_NAME
        taken = {p.name.lower() for p in dest_folder.iterdir()} if dest_folder.is_dir() else set()
        existing = _existing_copy(dest_folder, source, digest,
                                  among=copies_of(item, list(items.values()), dest_folder))
        # Named to fit, before anything is made (decision 131): no room even
        # for the shortest name refuses with PATH_NO_ROOM, nothing moved.
        extension = extension_of(source)
        filed_as = existing.name if existing is not None else prepared_name_for(
            item, extension, taken, room=limit_for(extension) - len(str(dest_folder)) - 1)
        dest_folder.mkdir(parents=True, exist_ok=True)

        # The parked copy here goes: the document is the other return's
        # now, and two copies of it in two queues would be two documents
        # where the client sent one. One a person annotated is not this
        # row's bytes and is left where it is, said so, exactly as a
        # filing leaves one.
        parked = locate(home_return, entry.prepared_location) if entry.prepared_location else None
        left_in_review = ""
        releasing: list[dict] = []
        if parked is not None and parked.is_file() and not is_cloud_placeholder(parked):
            if sha256_of(parked) == digest:
                releasing.append(_op(home_return, ledger.OP_REMOVE, parked, digest=digest))
            else:
                left_in_review = (
                    f"the parked copy {entry.prepared_location} no longer holds the bytes this "
                    f"row recorded (annotated, or re-saved) and was left there"
                )

        overrode = (OVERRODE_SHORTLIST.format(listed=", ".join(shortlist))
                    if shortlist and identifier not in shortlist else "")
        label = _label_of(target_return, _details_of(target_return))
        attributed = f"{ASSIGNED_BY_PERSON} on {today.isoformat()}"
        if overrode:
            attributed = f"{attributed}; {overrode}"
        dropped = ("" if not moving_it
                   else DROPPED_ELSEWHERE.format(household=household_of(home_return).name))
        target_entry = replace(
            entry,
            identifier=item.identifier,
            prepared_location=prepared_location(dest_folder, filed_as),
            pbc_location=location_of(target_return, resting),
            decision=FILED,
            reason="; ".join(part for part in (attributed, dropped, f"was: {entry.reason}") if part),
            # The candidates and the evidence were this return's request
            # list judging the page; they name identifiers the taking
            # return does not have, so they do not travel with the row.
            candidates="", evidence="", also_filed="", answers="",
        )
        released = RELEASED_TO.format(label=label, identifier=item.identifier)
        # The taking return's steps are held to its places before this
        # return's release is written (decision 180): a release recorded
        # for a filing that is then refused would take the document off
        # every queue.
        for op in ([_op(target_return, ledger.OP_MOVE, source, resting, digest)]
                   if resting != source else []) + [
                _op(target_return, ledger.OP_COPY, resting, dest_folder / filed_as, digest)]:
            _refuse_a_step_outside(target_return, op)

        keyword = keyword.strip()
        note = ""
        if keyword and keyword.lower() in {k.lower() for k in item.any_keywords}:
            note = f"{identifier} already had the keyword {keyword!r}"
        taught = [] if note or not keyword else [ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: item.identifier, ledger.KEYWORD_KEY: keyword,
        })]
        spelled, said, spelling_note = _taught_spelling(target_return, spelling)
        taught += spelled

        # 1. This record's half, written down first: the release.
        home_key = ledger_key(entry)
        _intend(home_return, home_key, releasing, by=ledger.BY_PERSON,
                row=entry_to_json(entry), then=ledger.RELEASED, reason=released)
        # 2. The taking return's half, in its own record, in the pass's
        # own shape - and its operations.
        _file_into(target_return, source, digest, resting=resting,
                   copies=[] if existing is not None else [dest_folder / filed_as],
                   row=target_entry, then=ledger.ASSIGNED_BY_PERSON, by=ledger.BY_PERSON,
                   also=taught)
        # 3. The taking return's row, which closes its intent.
        conn = store.connect()
        store.record(conn, target_return,
                     _ledger_event(ledger.ASSIGNED_BY_PERSON, target_entry), *taught)
        # 4. This return's operation, then the release, which closes its own.
        for op in releasing:
            _do_op(home_return, op)
        store.record(conn, home_return, ledger.new(ledger.RELEASED, **{
            ledger.KEY_KEY: home_key, ledger.REASON_KEY: released,
        }))
    return HandedOver(
        entry=entry, target_entry=target_entry, target=target_return, label=label,
        moved_original=moving_it, keyword=keyword if not note else "", keyword_note=note,
        spelling=said, spelling_note=spelling_note, left_in_review=left_in_review,
        overrode_shortlist=overrode,
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
#: the firm wants is not the filer's to decide: the copy stays where it
#: is, a fresh one goes back to review, and a person is told so
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
    has a copy in each and **every one of them leaves its place in Prepared**:
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
            # A row whose copy and original are both gone (decision 157,
            # B5) is refused in the one sentence all three answers use.
            if both_gone(entry) and _the_original_now(engagement_dir, entry)[0] != _ORIGINAL_PROVED:
                raise FilingError(NOTHING_TO_PUT_BACK.format(
                    prepared=PREPARED_DIR_NAME, pbc=entry.pbc_location))
            if not source.is_file():
                raise FilingError(
                    f"the working copy is not the one this row recorded and the original "
                    f"{entry.pbc_location} is no longer there; there is nothing to put back"
                )
            if is_cloud_placeholder(source):
                raise FilingError(f"the original {entry.pbc_location} is still syncing; try again when it is here")
            if entry.digest and _digest_or_none(source) != entry.digest:
                # Proved before the intent is written, not by the copy after
                # it: a copy of other bytes would fail half way through a
                # decision the record already holds (decision 157).
                raise FilingError(NOTHING_TO_PUT_BACK.format(
                    prepared=PREPARED_DIR_NAME, pbc=entry.pbc_location))

        # Named as every review copy is, to fit (decision 131): no room
        # refuses with the review copy's sentence, and nothing has moved.
        parked, past_reader = _review_copy_path(review_dir, entry.original_name)
        review_dir.mkdir(parents=True, exist_ok=True)
        left_filed = "; ".join(
            LEFT_FILED.format(location=location, parked=parked.name) for location in strangers
        )
        # A page decision 94 filed under several requests has a copy in
        # each, and every one of them has to leave Prepared or
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
            reason=(f"{UNFILED_BY_PERSON} on {today.isoformat()}{_said(note)}; was: {entry.reason}"
                    + (f"; {past_reader}" if past_reader else "")),
            also_filed="", answers="",
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
                        _move_whole(parked, working, within=engagement_dir)
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


@dataclass(frozen=True, slots=True)
class MarkedMissingResult:
    """What marking one answered request missing again did."""

    entry: IndexEntry            # the statement's row, rewritten
    identifier: str              # the request marked missing again
    scan_note: str = ""          # why the re-scan did not land, when it did not


def mark_missing_again(
    engagement_dir: Path | str,
    original: str,
    identifier: str,
    note: str = "",
    *,
    today: dt.date | None = None,
    seq: int | None = None,
) -> MarkedMissingResult:
    """Take one request off what a consolidated statement answers (decision
    146, the owner's answer to 146-Q: "a person can still mark it missing").

    ``original`` names the statement's row the way :func:`unfile_document`
    takes it, and ``identifier`` the request on its Also Answers cell that
    the statement does not in fact answer - a consolidated statement whose
    interest section lacks what the preparer needs, say. The row keeps its
    filing, its copy and every other answer; only that request comes off,
    and the Reason says who took it off and when. Nothing moves on disk,
    because nothing was ever copied for an answer.

    One ``answer_withdrawn_by_person`` line, a row event, so the store
    rebuilt from the journal and ``store check`` agree with the person.
    Then the re-scan, as unfiling does it, so the request reads what its
    own folder holds - Missing, most often, with the regression note that
    says it was Received - and the letter asks for it again from the next
    draft on. A request the row does not answer is refused by name, and so
    is a row somebody re-filed since the person saw it (``seq``, decision
    112).

    **A row's own request, on a row whose copy and original are both gone**
    (decision 157, ruling B6). The pass holds such a request for a person
    rather than asking the client (:func:`both_gone`); this is the person's
    answer. The row stays on the record with the person's sentence, and its
    claim on any working copy and every answer it gave come off
    (:func:`marked_missing`): it counts for nothing, holds nothing
    firm-side, leaves the client README, and the pass never makes it again
    or flags it again - so the request reads Missing and the letter asks.
    On any other row its own request is refused, as it always was. One
    ``answer_withdrawn_by_person`` line records it, the event decision 146
    gave a request taken off a row.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    wanted = identifier.strip()
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = find_filed(entries, original, accepting=(FILE_MOVED,))
        entry = entries[position]
        _refuse_if_stale(engagement_dir, entry, seq)
        answered = entry.answered
        kept = [one for one in answered if identifier_key(one[0]) != identifier_key(wanted)]
        own = bool(entry.identifier) and identifier_key(wanted) == identifier_key(entry.identifier)
        if own and both_gone(entry):
            new_entry = replace(
                entry, prepared_location="", also_filed="", answers="",
                reason="; ".join(part for part in (entry.reason, MARKED_MISSING.format(
                    identifier=entry.identifier, date=today.isoformat(), note=_said(note))) if part),
            )
            wanted = entry.identifier
        elif len(kept) == len(answered):
            raise FilingError(f"{entry.original_name} does not answer {wanted}")
        else:
            new_entry = replace(
                entry,
                answers=format_answers(kept),
                reason="; ".join(part for part in (entry.reason, MARKED_MISSING.format(
                    identifier=wanted, date=today.isoformat(), note=_said(note))) if part),
            )
        entries[position] = new_entry
        _record(engagement_dir, before, entries,
                decided={ledger_key(new_entry): ledger.ANSWER_WITHDRAWN_BY_PERSON})
    return MarkedMissingResult(entry=new_entry, identifier=wanted,
                               scan_note=_rescan(engagement_dir, today))


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


def _gone_copies(engagement_dir: Path, entries: list[IndexEntry], position: int) -> list[str]:
    """The places this row names as its working copies that are simply gone
    and that no later row names instead (a later row's claim on a place is
    the newest, as everywhere else) - what Put it back makes again on a row
    that did not move (decision 157, ruling B8)."""
    entry = entries[position]
    later = {location for one in entries[position + 1:] for location in one.filed_locations}
    return [location for location in entry.filed_locations
            if location not in later and _absent(locate(engagement_dir, location))]


def _find_to_put_back(engagement_dir: Path, entries: list[IndexEntry], original: str) -> int:
    """:func:`find_moved`, widened by decision 157 (ruling B8): a Filed or
    parked row with a fingerprint one of whose own working copies is simply
    gone is Put it back's too. Anything else is refused exactly as
    :func:`find_moved` refuses it - a Filed row whose copy is where the
    record put it has nothing to put back."""
    try:
        return find_moved(entries, original)
    except FilingError:
        wanted = original.replace("\\", "/").strip()
        for position in range(len(entries) - 1, -1, -1):
            entry = entries[position]
            if entry.pbc_location != wanted and entry.original_name != wanted:
                continue
            if entry.decision == DUPLICATE and entry.original_name == wanted:
                continue
            if (entry.decision in (FILED, *_PARKED) and entry.digest
                    and _gone_copies(engagement_dir, entries, position)):
                return position
            break
        raise


def _make_a_gone_copy_again(
    engagement_dir: Path, entries: list[IndexEntry], before: dict[str, dict], position: int,
    stamp: str,
) -> RestoreResult:
    """Put it back on a Filed or parked row whose copy was deleted (decision
    157, ruling B8), under the lock :func:`restore_working_copy` holds: the
    copy made again from the proved original, through the pass's own
    :func:`_make_again`, with the pass's sentence and event, decided by the
    person. Refused before anything is written where the original cannot
    be copied from - still syncing, unreadable, or gone (naming both, as
    :data:`NOTHING_TO_PUT_BACK` does). A record that refuses the decision
    takes the copies back. Mutates ``entries``; the caller re-scans."""
    entry = entries[position]
    gone = _gone_copies(engagement_dir, entries, position)
    outcome, source = _the_original_now(engagement_dir, entry)
    if outcome == _ORIGINAL_GONE:
        raise FilingError(NOTHING_TO_PUT_BACK.format(prepared=PREPARED_DIR_NAME,
                                                     pbc=entry.pbc_location))
    if outcome == _ORIGINAL_UNREAD:
        raise FilingError(f"the original {entry.pbc_location} is still syncing or cannot be read "
                          "now; try again when it can")
    remade, _sentence = _remade(entry, gone, stamp)
    entries[position] = remade
    _make_again(engagement_dir, entry, remade, source, gone,
                by=ledger.BY_PERSON, then=ledger.COPY_REMADE, cache=None)
    try:
        _record(engagement_dir, before, entries, decided={ledger_key(remade): ledger.COPY_REMADE})
    except BaseException:
        # The record took it or it did not: a copy it did not take is
        # removed by its bytes, so a retry makes it once.
        if not _the_record_holds(engagement_dir, remade):
            for location in gone:
                made = locate(engagement_dir, location)
                if _the_bytes(made) == entry.digest:
                    made.unlink(missing_ok=True)
            _abandon(engagement_dir, ledger_key(remade))
        raise
    return RestoreResult(entry=remade, moved_home=False, copied_from_original=True,
                         already_home=False)


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

    **And a copy that was simply deleted** (decision 157, ruling B8; the
    audit's D-3, which found this refusing "not a moved copy (it is
    Filed)"). A Filed or parked row one of whose own copies is gone is
    accepted too, and the copy is made again from the row's proved original
    through the very function the pass uses (:func:`_make_again`), with the
    same sentence (:data:`REMADE_SENTENCE`) and the same event
    (``ledger.COPY_REMADE``), decided by the person. A row whose copy and
    original are both gone is refused naming both
    (:data:`NOTHING_TO_PUT_BACK`); its one answer is Mark missing.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    stamp = today.isoformat()

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}
        position = _find_to_put_back(engagement_dir, entries, original)
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
        if marked_missing(entry):
            raise FilingError(MARKED_REFUSAL.format(name=entry.original_name))
        if entry.decision == FILE_MOVED:
            done = _put_back_a_moved_copy(engagement_dir, entries, before, position, stamp)
        else:
            done = _make_a_gone_copy_again(engagement_dir, entries, before, position, stamp)

    # Outside the lock, as the unfiling's is: the request this row answers
    # has its file again (or has lost it to review), and the status says so
    # now rather than at the next scheduled pass.
    return replace(done, scan_note=_rescan(engagement_dir, today))


def _put_back_a_moved_copy(
    engagement_dir: Path, entries: list[IndexEntry], before: dict[str, dict], position: int,
    stamp: str,
) -> RestoreResult:
    """Decision 110's put-it-back of a ``FILE_MOVED`` row, under the lock
    :func:`restore_working_copy` holds: the wanderer home, a copy from the
    original, already home, or refused and parked. Mutates ``entries``
    and records the person's decision; the caller re-scans."""
    review_dir = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    entry = entries[position]
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
        if not now and _the_original_now(engagement_dir, entry)[0] == _ORIGINAL_GONE:
            # Nothing under the firm's folder and not the original either
            # (decision 157, B5): the one sentence, naming both.
            raise FilingError(NOTHING_TO_PUT_BACK.format(
                prepared=PREPARED_DIR_NAME, pbc=entry.pbc_location))
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
        # Named as every review copy is, to fit (decision 131): no room
        # refuses with the review copy's sentence, nothing touched.
        parked, past_reader = _review_copy_path(review_dir, entry.original_name)
        review_dir.mkdir(parents=True, exist_ok=True)
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
        if past_reader:
            sentence = f"{sentence}; {past_reader}"
        new_entry = replace(
            entry, decision=NEEDS_REVIEW, identifier="", also_filed="", answers="",
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
                        _move_whole(parked, wanderer, within=engagement_dir)
                    else:
                        parked.unlink(missing_ok=True)
                else:
                    for copy in filled[1:]:
                        copy.unlink(missing_ok=True)
                    if wanderer_moved and filled:
                        _move_whole(filled[0], wanderer, within=engagement_dir)
                    elif filled:
                        filled[0].unlink(missing_ok=True)
            except (OSError, FilingError) as undo:
                log.error("Could not put %s back after the record refused it: %s",
                          entry.original_name, undo)
            _abandon(engagement_dir, ledger_key(new_entry))
        raise
    return RestoreResult(
        entry=new_entry, moved_home=moved_home, copied_from_original=copied_from_original,
        already_home=not different and not absent,
        parked_as=prepared_location(review_dir, parked.name) if parked is not None else "",
    )


# ------------------------------------------------------------------ rename ----


def documents_by_request(engagement_dir: Path | str,
                         items: Sequence[RequestItem] | None = None) -> dict[str, int]:
    """How many filed documents each request holds, keyed without case
    (``records.identifier_key``): every Filed and File Moved row, once per
    request it satisfied - its own, and one per copy decision 94 filed
    under another - read as the client README reads them
    (:func:`_requests_of`).

    What a save of the list asks before it takes a request off the list or
    gives it another identifier (decision 160, the audit's D-7): the
    index, not the status, because the index is the record of what was
    filed and a status is only as fresh as the last scan.

    A request a consolidated statement answers through its Also Answers
    cell (decision 146) holds that statement too, once per statement, even
    with no copy of its own (SPEC-146 R-2): the client has sent it, so a
    save may not drop it - a person marks it missing again first. A row a
    person marked missing because its copy and its original were both gone
    holds nothing (decision 157): the client is being asked for it again.
    """
    folder = Path(engagement_dir)
    items = load_manifest(folder) if items is None else list(items)
    held: dict[str, int] = {}
    for entry in read_index(folder):
        if _counts_as_received(entry):
            for identifier in _requests_of(entry, items):
                if identifier:
                    key = identifier_key(identifier)
                    held[key] = held.get(key, 0) + 1
            for key in dict.fromkeys(identifier_key(one) for one, _sections in entry.answered):
                held[key] = held.get(key, 0) + 1
    return held


RENAME_CASE_ONLY = ("{old} and {new} differ only in case; change it in the list and save - "
                    "a change of case needs no rename")
RENAME_NOTHING = "Pick the request to rename and type its new identifier"
RENAME_COPY_TAKEN = "{location} is already there; move it or rename it first"
RENAME_COPY_MOVED = ("{name} is not where the record put it; put it back or send it to review "
                     "before renaming {old}")
RENAME_COPY_MISSING = ("{location} is not there, so it cannot move with {old}; the next pass says "
                       "where it went - rename after it")
RENAME_COPY_CHANGED = ("{location} no longer holds the file the record filed there; look at it "
                       "before renaming {old}")
RENAME_COPY_SYNCING = "{location} is still syncing; try again when it is here"
RENAME_PATH_TOO_LONG = ("{location} would be {length} characters, past what Windows opens "
                        "({limit}); choose a shorter identifier")
#: What a rename says when the record took it and a file would not move
#: yet: the rename is the record's from its first write (decision 119's
#: intent), so it is finished forward - by the next pass - never undone.
RENAME_UNFINISHED = ("{old} is renamed {new} on the record, but {name} could not be moved yet "
                     "({problem}); the next pass finishes it (or press Run now)")


@dataclass(frozen=True, slots=True)
class RenameResult:
    """What one rename did: the two identifiers, how many working copies
    moved, how many index rows now name the new identifier, the files
    named for the old identifier left as they are because no row names
    them, the list's new version (``manifest.list_head``) and the re-scan's
    note."""

    old: str
    new: str
    moved: int
    rows: int
    left: tuple[str, ...]
    head: str
    scan_note: str


def _renamed(name: str, old: str, new: str) -> str:
    """``name`` with the request's identifier at its front given as ``new``,
    where it begins with ``old`` at a word boundary (the one shape a
    working copy is made in); otherwise as it is."""
    if not matches_identifier(name, old):
        return name
    rest = name.strip()[len(old.strip()):]
    return sanitize_component(new) + rest


def rename_request(
    engagement_dir: Path | str,
    old: str,
    new: str,
    *,
    head: object,
    today: dt.date | None = None,
) -> RenameResult:
    """Give a request another identifier, and move its documents with it.

    A save of the list may not take a request that holds documents off the
    list, and a respelt identifier is exactly that to a save: the old one
    removed, a new one added, the documents orphaned under a folder no
    request names and the letter and the README asking the client again
    (decision 160, the audit's D-7). This is the other way, and the only
    one: every working copy the record names whose name belongs to the
    request (directly in ``PREPARED_DIR_NAME``, by
    ``tracker.scaffold.owner_of`` - the rule ``assign_files`` applies)
    takes the new identifier at the front of its name, beside where it was,
    and every index row that names the request, or one of those copies,
    names the new one - in its Also Answers cell too, where a consolidated statement
    filed under another request answers this one (decision 146, SPEC-146
    R-1), so the answer and its sections carry and a killed rename finishes
    it from the row its intent holds.

    **One act, finished forward** (decision 119). Checked first, under the
    lock: no move open, the list the version the person's editor was
    opened on (``head``, decision 160's freshness check), the new
    identifier legal and free (the list's own validation), every copy that
    is to move there and holding the row's bytes, no destination taken and
    none past what Windows opens. Then one write carries the list renamed
    - with the keywords a filing taught it - and one intent per row that
    changes, so a run killed after it is finished by the next pass from
    the record, as any person's decision is; then the moves; then each
    row, recorded as :data:`tracker.ledger.RENAMED_BY_PERSON`, which closes
    its intent. A move that fails after the write is not undone: the
    record has decided, and the refusal says the next pass finishes it.

    A change of case only is refused: it is the same request everywhere
    (``records.identifier_key``), and the editor saves it. A row whose copy
    is not where the record put it (File Moved) is refused by name, as
    every other action on such a copy is. A file named for the request
    that no row names is left where it is and named in the result, never
    moved and never deleted.

    **No folder moves** (decision 168): a request has none, so there is
    nothing to rename and no emptied folder to take away - the copies are
    renamed in place, each one an ordinary move in the intent, and a run
    killed half way is finished by the next pass from those moves exactly
    as any interrupted filing is (:func:`_finish_interrupted_moves`),
    nothing lost and nothing doubled. An intent written before 168 names
    folder-shaped paths (``PREPARED_DIR_NAME/A01 - W-2/...`` to ``PREPARED_DIR_NAME/B01 -
    W-2/...``); it is finished as written, because the record decided it -
    the copy lands in the folder the intent names, which is then a
    person's folder of a return made before 168 (decision 168's ruling 10),
    and the emptied old folder stays, empty, until a person takes it away.
    A copy recorded in such a folder is never renamed by a rename made
    after 168: it is not in ``PREPARED_DIR_NAME`` itself, and its row
    takes the new identifier all the same.
    """
    engagement_dir = Path(engagement_dir)
    today = today or dt.date.today()
    old = str(old or "").strip()
    new = str(new or "").strip()
    if not old or not new:
        raise FilingError(RENAME_NOTHING)
    if identifier_key(old) == identifier_key(new):
        raise FilingError(RENAME_CASE_ONLY.format(old=old, new=new))
    prepared = engagement_dir / PREPARED_DIR_NAME

    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        _refuse_if_a_move_is_open(engagement_dir)
        conn = store.connect()
        refuse_a_stale_list(conn, engagement_dir, head)
        list_events = renamed_rules(engagement_dir, old, new)
        items = load_manifest(engagement_dir)
        entries = read_index(engagement_dir)
        before = {ledger_key(e): entry_to_json(e) for e in entries}

        # Which copies are the request's is their names' to say (decision
        # 168): a copy directly in the firm's folder whose name belongs to
        # the old identifier - the longest that fits, so renaming A01 never
        # touches A01-B's - takes the new one at its front, beside where it
        # is. Asked of the name, not of the disk, so a copy the record put
        # there that has gone is refused below rather than passed over.
        identifiers = [item.identifier for item in items]

        def belongs_to_old(path: Path) -> bool:
            owner = owner_of(path.name, identifiers)
            return path.parent == prepared and owner is not None \
                and identifier_key(owner) == identifier_key(old)

        def moved_to_new(location: str) -> str | None:
            path = locate(engagement_dir, location)
            if not belongs_to_old(path):
                return None
            return location_of(engagement_dir, prepared / _renamed(path.name, old, new))

        # Every file named for the request now, recorded or not - what is
        # not moved below is named in the result.
        spelled = next((one for one in identifiers if identifier_key(one) == identifier_key(old)), old)
        owned = [location_of(engagement_dir, path)
                 for path in assign_files(prepared, identifiers).get(spelled, [])]

        renamed_entries: list[IndexEntry] = []
        ops_for: dict[str, list[dict]] = {}
        destinations: set[str] = set()
        for position, entry in enumerate(entries):
            locations = entry.filed_locations
            mapped = {location: moved_to_new(location) for location in locations}
            mapped = {was: now for was, now in mapped.items() if now}
            names_it = bool(entry.identifier) and identifier_key(entry.identifier) == identifier_key(old)
            candidates = [new if identifier_key(one) == identifier_key(old) else one
                          for one in entry.candidate_list]
            evidence = entry.evidence
            record = entry.evidence_record
            if any(identifier_key(one) == identifier_key(old) for one in record) \
                    and format_evidence(record) == entry.evidence:
                evidence = format_evidence({new if identifier_key(one) == identifier_key(old) else one: found
                                            for one, found in record.items()})
            # The Also Answers cell names the request too (decision 146 over
            # 160, SPEC-146 R-1): a consolidated statement filed under another
            # request that answers this one answers it under its new name,
            # each answer keeping its sections - or the request reads Missing
            # again and the letter asks for what the client already sent.
            answered = entry.answered
            answers = entry.answers
            if any(identifier_key(one) == identifier_key(old) for one, _sections in answered):
                answers = format_answers([(new if identifier_key(one) == identifier_key(old) else one,
                                           sections) for one, sections in answered])
            if not (mapped or names_it or candidates != entry.candidate_list
                    or evidence != entry.evidence or answers != entry.answers):
                continue
            if mapped and entry.decision == FILE_MOVED:
                raise FilingError(RENAME_COPY_MOVED.format(name=entry.original_name, old=old))
            ops = []
            for was, now in mapped.items():
                source, target = locate(engagement_dir, was), locate(engagement_dir, now)
                if not source.is_file():
                    raise FilingError(RENAME_COPY_MISSING.format(location=was, old=old))
                if is_cloud_placeholder(source):
                    raise FilingError(RENAME_COPY_SYNCING.format(location=was))
                if entry.digest and sha256_of(source) != entry.digest:
                    raise FilingError(RENAME_COPY_CHANGED.format(location=was, old=old))
                if target.exists() or now.casefold() in destinations:
                    raise FilingError(RENAME_COPY_TAKEN.format(location=now))
                if len(str(target)) > MAX_PATH_LENGTH:
                    raise FilingError(RENAME_PATH_TOO_LONG.format(
                        location=now, length=len(str(target)), limit=MAX_PATH_LENGTH))
                destinations.add(now.casefold())
                ops.append(_op(engagement_dir, ledger.OP_MOVE, source, target, entry.digest))
            now_locations = [mapped.get(location, location) for location in locations]
            renamed = replace(
                entry,
                identifier=new if names_it else entry.identifier,
                prepared_location=now_locations[0] if now_locations else entry.prepared_location,
                also_filed=_CANDIDATE_SEP.join(now_locations[1:]) if mapped else entry.also_filed,
                candidates=_CANDIDATE_SEP.join(candidates) if candidates != entry.candidate_list
                else entry.candidates,
                evidence=evidence,
                answers=answers,
            )
            entries[position] = renamed
            renamed_entries.append(renamed)
            ops_for[ledger_key(renamed)] = ops

        # One write: the list renamed and every row's intent. The intents
        # are written whole here rather than through _intend(), because a
        # row whose only change is the identifier it names has nothing to
        # move and still has to be finished with the rest.
        intents = []
        for renamed in renamed_entries:
            key = ledger_key(renamed)
            intents.append(ledger.new(ledger.MOVING, **{
                ledger.KEY_KEY: key, ledger.OPS_KEY: ops_for[key], ledger.DECIDED_BY_KEY: ledger.BY_PERSON,
                ledger.ROW_KEY: entry_to_json(renamed), ledger.EVENT_KEY_AFTER: ledger.RENAMED_BY_PERSON,
            }))
        store.record(conn, engagement_dir, *list_events, *intents)

        moved = 0
        for renamed in renamed_entries:
            for op in ops_for[ledger_key(renamed)]:
                try:
                    _do_op(engagement_dir, op)
                except (OSError, FilingError) as exc:
                    raise FilingError(RENAME_UNFINISHED.format(
                        old=old, new=new, name=Path(op[ledger.FROM_KEY]).name, problem=exc)) from exc
                moved += 1
        _record(engagement_dir, before, entries,
                decided={ledger_key(one): ledger.RENAMED_BY_PERSON for one in renamed_entries})

        # A file named for the old identifier that no row names stays as it
        # is, and is named: it is somebody's, and nothing proves whose.
        moving = {op[ledger.FROM_KEY].casefold() for ops in ops_for.values() for op in ops}
        left = [location for location in owned if location.casefold() not in moving]
        now_head = list_head(engagement_dir)
        rows = sum(1 for entry in entries
                   if entry.identifier and identifier_key(entry.identifier) == identifier_key(new))

    return RenameResult(old=old, new=new, moved=moved, rows=rows, left=tuple(left),
                        head=now_head, scan_note=_rescan(engagement_dir, today))


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
        reports = file_household_drops(inbox_of(asked), originals_of(asked), own=every,
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
