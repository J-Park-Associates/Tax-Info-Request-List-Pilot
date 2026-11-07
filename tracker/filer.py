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
- **A document no request asks for is said so, never erased.**
  ``tracker.actions.dismiss_review_file()`` rewrites the row as
  ``NOT_REQUESTED`` and moves nothing: an agency notice or an extra
  statement stays where the client's copy of it is. The weekly draft stops
  counting it, and filing it later (``tracker.actions.assign_review_file()``)
  is how the decision is undone. It is a decision
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
decision 100; what is here is every reading and writing of the record. A
reader imports the row from there, and the index's words from
:mod:`tracker.index`, never through this module (P322).

How a file is named, measured, copied and moved - the names, the room, the
byte-proved copy, the rename-only move, the Protected View mark, the client
README's lock and the stranded-temp sweep - lives in :mod:`tracker.copies`
since P331.

The write-ahead intents a decision writes before it touches a file, the
record's one write, and finishing an interrupted move from the record live in
:mod:`tracker.intents` since P332.

Walking the inbox, and finding what in it or in the year's folder cannot be
sorted or tied to its row - the drops in the inbox's own order, the names,
folders and transfers that cannot be read, listed or finished, a replaced,
moved or missing original and a row recorded without its bytes - live in
:mod:`tracker.inbox` since P333.

What the client README says has arrived - the received list a pass, the
rollover and every app action render through the one refresh - and the
refresh itself live in :mod:`tracker.readme_ack` since P334.

A person's actions on the record - filing by hand, setting aside, unfiling,
Mark missing, putting a copy back and renaming a request - and the re-scan
after them live in :mod:`tracker.actions` since P335. The pieces they share
with the hand-over stay here, and this module imports neither that one nor
the scanner.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
import math
from collections.abc import Callable, Iterable, Mapping, Sequence
from contextlib import ExitStack
from dataclasses import dataclass, field, replace
from pathlib import Path
from typing import cast

from tracker import containers, door, errors, ledger, ocr, reasons, store
from tracker.content_check import (
    ContentCache,
    Judgment,
    NameQuestion,
    OutOfTime,
    before_a_judgment,
)

# Naming, room, the byte-proved copy, the rename-only move, the client
# README's lock and the stranded-temp sweep live in tracker/copies.py (P331).
# The filer imports what its own code reads; every reader in tracker/ imports
# them from tracker.copies.
from tracker.copies import (
    _AN_EXTENSION,
    FIRM_WRITTEN,
    MARK_REFUSED_STEP,
    ORIGINAL_GONE,
    ORIGINAL_SYNCING,
    PATH_NO_ROOM_IN,
    FilingError,
    MarkRefusedError,
    NoRoom,
    _digest_or_none,
    _existing_copy,
    _here,
    _kind_of,
    _move_whole,
    _named,
    _on_record,
    _review_copy_path,
    _room_in,
    _shown,
    _unique_path,
    _year_on_record,
    copies_of,
    prepared_name_for,
)
from tracker.door import through_a_link
from tracker.fsio import (
    TEMP_SUFFIX,
    write_bytes_atomically,
)
from tracker.households import household_returns

# Walking the inbox, and the drops that cannot be read, listed or tied to a
# row, live in tracker/inbox.py (P333). The filer imports what its own code
# reads; every reader in tracker/ imports them from tracker.inbox.
from tracker.inbox import (
    LEFT_FOR_ANOTHER_RETURN,
    MISSING_IN_PBC,
    MOVED_IN_PBC,
    README_UNREAD,
    REPLACED_IN_PBC,
    UNTIED_IN_PBC,
    _absent,
    _follow_moved_originals,
    _missing_positions,
    _record_missing_digests,
    _subfolder_of,
    ignored_in_inbox,
    iter_drops,
    replaced_in_pbc,
    unfinished_drops,
    unlistable_folders,
    unreachable_drops,
    unrecorded_in_pbc,
)

# The index's words and their readers live in tracker/index.py (P319). The
# filer imports what it reads itself - the three private readers of the moved
# tail among them, the one place a private name crosses that boundary - and
# offers none of them on: every reader imports them from tracker.index (P322).
from tracker.index import (
    BOTH_GONE_SENTENCE,
    DUPLICATE,
    FILE_MOVED,
    FILED,
    MOVED_GONE_SENTENCE,
    MOVED_SENTENCE,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    OPENED,
    _before_the_moved_sentence,
    _says_it_is_nowhere,
    _without_moved_sentence,
    both_gone,
    ensure,
    marked_missing,
    moved_to,
    prepared_location,
    read_index,
)

# The write-ahead intents, the record's one write and finishing an interrupted
# move live in tracker/intents.py (P332). The filer imports what its own code
# reads; every reader in tracker/ imports them from tracker.intents.
from tracker.intents import (
    FileError,
    _abandon,
    _do_op,
    _door_for,
    _finish_interrupted_moves,
    _intend,
    _ledger_event,
    _op,
    _record,
    _refuse_a_step_outside,
    _refuse_if_a_move_is_open,
    _the_bytes,
)
from tracker.layout import (
    folder_need,
    household_name_of,
    household_of,
    inbox_of,
    locate,
    location_of,
    lock_order_key,
    name_key,
    opened_dir_of,
    originals_of,
    parts_below,
    path_limit,
    place_of,
    private_tree_of,
    recorded_name,
    room_root,
    root_of,
    year_of,
)
from tracker.layout import (
    label_for as label_for_return,
)
from tracker.locking import (
    engagement_lock,
    lock_is_held,
)
from tracker.manifest import (
    Override,
    RequestItem,
    load_engagement_info,
    load_manifest,
    override_label,
)
from tracker.names import (
    NAME_CONFIRMED,
    NAME_VETOED,
    NameVerdict,
)
from tracker.progress import Watch

# The records themselves live in tracker/records.py (decision 100). The filer
# imports the shapes it writes and reads back - the index row and the cells it
# is written in, the evidence, the engagement's details, the people and their
# spellings - because a row is written in the record's shape, not the filer's.
# It offers none of them on (P322).
from tracker.records import (
    CANDIDATE_SEP,
    ONE_WORD_SPELLING,
    RULE_NAME,
    EngagementInfo,
    Evidence,
    IndexEntry,
    Person,
    Routing,
    WaitsFor,
    entry_to_json,
    format_answers,
    format_evidence,
    format_waits_for,
    is_a_spelling,
    ledger_key,
    name_words,
    parse_answers,
    person_to_json,
)
from tracker.router import questions_for, read_once, route_file
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
    assign_files,
)
from tracker.validators import (
    PdfVerdictCache,
    extension_of,
    is_cloud_placeholder,
    is_program,
    is_sync_staging,
    iter_candidate_files,
    sha256_of,
    too_large_reason,
)

log = logging.getLogger("tracker.filer")

#: How many of a run's slowest readings the report keeps (decision 127).
#: Five, because the number is read to answer "is the pass getting slow?",
#: which one outlier cannot answer and a whole list nobody reads.
SLOWEST_READINGS = 5

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


class StaleRowError(FilingError):
    """The row was rewritten after the person last saw it (decision 112).

    A :class:`FilingError` so the API's one ``except`` turns it into the
    sentence the app toasts: the refusal is not a different kind of
    failure, it is the ordinary one with a different cause.

    ``seq`` is the record's line for the row now and ``identifier`` the
    row's key in the state (its ``pbc_location``, which a card sends back
    as ``original``), so the app can outline
    the row a person clicked (decision 193).
    """

    def __init__(self, message: str, *, seq: int | None = None,
                 identifier: str | None = None) -> None:
        super().__init__(message)
        self.seq = seq
        self.identifier = identifier


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
    #: How many files in the inbox were left alone as system or temporary
    #: files by name (:func:`ignored_in_inbox`, decision 190) - a count,
    #: never names. On the household's first return's report only.
    ignored: int = 0
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
    #: How many files the household's time for this pass did not reach
    #: (decision 189): left where they were, unrecorded, for the next pass.
    #: On the first own return's report, where the inbox's notes ride.
    unreached: int = 0
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


def _taken_in_the_year(first: _ReturnRun, runs: list[_ReturnRun]) -> dict[Path, str]:
    """Every name the pass's own household-year holds (decision 147, ruling
    9 and the review's N-1): the rows of **every** return of that year -
    the pass's own rows as they stand now, and the record's for a return
    the pass left out, one marked inactive while another of the same year
    is still worked - and every path an open intent will write to, as a
    name no bytes can claim back."""
    held = {run.engagement_dir: run.entries for run in runs}
    return {**_year_on_record(first.engagement_dir, held), **dict.fromkeys(first.context.intended, "")}


# ----------------------------------------------------- the working copies ----


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
                   "match it; it is counted as it sits - open it and confirm whose it is first: "
                   "a document goes in through the app or a firm-side folder a person controls, "
                   "never a client's folder; anything else, a broken or partial copy included, "
                   "is deleted by hand")


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
    sentence = REMADE_SENTENCE.format(home=PLACES_JOINED.join(locations), pbc=_shown(entry.pbc_location),
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
    _do_all_or_take_back(engagement_dir, key, ops, cache)


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
                _make_again(engagement_dir, entry, remade, cast(Path, source), absent,   # proved: a path
                            by=ledger.BY_PASS, then=ledger.COPY_REMADE, cache=cache)
            except (OSError, FilingError) as exc:
                problem = REMAKE_FAILED.format(home=PLACES_JOINED.join(absent), pbc=_shown(entry.pbc_location),
                                               problem=errors.said(exc, FIRM_WRITTEN))
                errors.keep("filer: remaking a copy", exc, name=entry.original_name)
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
                                         pbc=_shown(entry.pbc_location) or "(none)", date=stamp)
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
                home=home, prepared=PREPARED_DIR_NAME, pbc=_shown(entry.pbc_location), date=stamp)
        else:
            # "The original is safe" would be false (decision 157, B5).
            sentence = BOTH_GONE_SENTENCE.format(
                home=home, prepared=PREPARED_DIR_NAME, pbc=_shown(entry.pbc_location) or "(none)",
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


def _prune_empty_dirs(inbox: Path, root: Path, household: str) -> None:
    """Remove folders the client dragged into the inbox that are empty now
    their files have moved into the year's folder. Deepest first; anything
    that is not empty or is a sync client's staging folder is left alone.

    The inbox holds nothing of the firm's to keep since decision 125: the
    originals rest in the other tree, so there is no folder here to step
    around. Each removal goes through the one door into the client tree
    (``door.client_write``, decision 188's review, S2): a folder it refuses
    is left where it is."""
    candidates = sorted(
        (p for p in inbox.rglob("*") if p.is_dir()),
        key=lambda p: len(p.parts),
        reverse=True,
    )
    for folder in candidates:
        if any(is_sync_staging(part) for part in folder.parts):
            continue
        if through_a_link(folder, inbox):
            continue        # rmdir on a junction removes the junction, whatever it points at
        try:
            door.client_write(root, household, folder).rmdir()  # only succeeds when empty
        except (OSError, door.DoorError):
            continue


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
    #: return, and since decision 204 the pass only ever **files** into
    #: one: the original rests under the household it was dropped in, and
    #: only a person's hand-over moves it into another.
    home: bool = True
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
    deadline: float | None = None,
    watch: Watch | None = None,
) -> dict[Path, FileReport]:
    """Sort one household's inbox across every return it feeds. Returns
    what was done, per return.

    ``watch`` (decision 193) is told each file before it is taken, and a
    stop a person asked for through it brings ``deadline`` to now at the
    next file (:func:`_sort_all`).

    **Bounded, and kept as it goes** (decision 189). ``deadline`` is a
    moment on ``ocr.awake_clock``: past it the sort takes no file that
    would need a new judgment (ruling 2.2; one whose bytes are on record
    is still decided from the record) - what it did is recorded as always,
    and the files it did not reach wait for the next pass (``unreached`` on
    the first own return's report). And each drop's verdicts are saved as soon as the
    next drop is taken, so a pass killed half way keeps every reading it
    finished.

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
    records in, because the record closest to the drop decides. **The pass
    never files across households** (decision 204, revising 132): a
    document only a fed return is left with parks at home - for one click
    where the page names that return's person
    (``reasons.NAMED_ACROSS_HOUSEHOLDS``, its row's ``waits_for`` saying
    what the other list accepted), for the picker where it names nobody.
    The original rests under the household it was dropped in until a
    person hands it over (:func:`hand_over`), because a folder another
    household's people can open is reached on a person's say, never on a
    printed name alone. A document that parks parks at home, because the
    dropping household is where it was dropped and where a person can act
    on it.

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
    # Which of them are this household's own - the list each came from
    # (decision 129). The pass files only into those (decision 204); a fed
    # return's list is read so a document only it wants can wait at home
    # for a person. The household is the client folder's own name -
    # ``<root>/<clients tree>/<household>/<year>`` - so a sentence can name
    # the folder the document was dropped in with nothing carried down.
    dropped_in = originals_dir.parent.name
    for position, run in enumerate(runs):
        run.home = position < len(own)
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
            name = "/".join(parts_below(originals_dir, path) or (path.name,))
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
    first.report.ignored = ignored_in_inbox(inbox)
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
                # Through the one door into the client tree (decision 188).
                _door_for(root_of(runs[0].engagement_dir), household_name_of(runs[0].engagement_dir),
                          Path(originals_dir))
                originals_dir.mkdir(parents=True, exist_ok=True)
                for run in runs:
                    run.context.prepared_dir.mkdir(parents=True, exist_ok=True)
            _sort_all(drops, strays, originals_dir, stamp, runs, first, deadline=deadline,
                      watch=watch)
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
        # The verdicts are kept whatever happened too (decision 189): after
        # the rows, so a store that refuses them cannot cost the record.
        try:
            if not dry_run:
                for run in reversed(runs):
                    _record(run.engagement_dir, run.before, run.entries,
                            moved=run.moved_keys, decided=run.swept, extra=run.opened)
        finally:
            if not dry_run:
                for run in runs:
                    run.cache.save()
    if not dry_run:
        # The tidy-up is owed to every pass, not only one that sorted
        # something: an empty folder the client dragged in outlives the
        # files that were in it, and a pass that found nothing to do used
        # to leave it there for ever. The inbox holds no folder of the
        # firm's to keep.
        _prune_empty_dirs(inbox, root_of(runs[0].engagement_dir),
                           household_name_of(runs[0].engagement_dir))
    return {run.engagement_dir: run.report for run in runs}


def _spoken_for_by_an_open_intent(
    runs: list[_ReturnRun], ends: tuple[str, ...] = (ledger.FROM_KEY, ledger.TO_KEY),
) -> set[Path]:
    """Every file a move this pass could not finish still names, at either
    end (or only at the ``ends`` asked for), across all the returns it holds.

    A cross-household filing moves the original a second time - a
    person's hand-over (decision 132), and the pass's own before decision
    204 - and between the two halves of that move the file is in the
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
    private = private_tree_of(root)
    for household in sorted(private.iterdir()) if private.is_dir() else []:
        if not household.is_dir():
            continue
        for folder in household_returns(household):
            if folder in own:
                continue
            try:
                store.follow_the_journal(conn, store.root_for(folder), folder)
                intents = store.open_intents(conn, folder)
            except Exception as exc:      # a record nobody can read names nothing it can prove
                errors.keep("filer", exc, name=folder.name)
                log.warning("Could not read %s's open intents (%s)", folder.name, errors.error_class(exc))
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
            location=_shown(earlier.pbc_location), received=earlier.received,
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
    except Exception as exc:
        # The sort goes on with no people - nothing is guessed - but a race
        # with the runner's own read of the record shows in the log (P297).
        errors.keep("filer: the return's details", exc, name=engagement_dir.name)
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
            location=_shown(earlier.pbc_location), now=location_of(engagement_dir, path),
        ), True))
    for earlier in gone:
        line = FileError(earlier.original_name, MISSING_IN_PBC.format(
            location=_shown(earlier.pbc_location), received=earlier.received,
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
                location=_shown(earlier.pbc_location), received=earlier.received,
                prepared=earlier.prepared_location or "(none)",
            ), True))
    return strays


def _sort_all(
    drops: list[Path],
    strays: list[Path],
    originals_dir: Path,
    stamp: str,
    runs: list[_ReturnRun],
    first: _ReturnRun,
    *,
    deadline: float | None = None,
    watch: Watch | None = None,
) -> None:
    """Decide and record every drop and every stray, one at a time, across
    the household's returns.

    **Watched, and stopped between files** (decision 193). ``watch`` is
    told each file before it is taken; when a person has asked the pass to
    stop, the deadline becomes now - ``-inf`` - and the check below does
    the rest, exactly as when the household's time runs out: a file whose
    bytes are on record is still taken, the first that would need a
    judgment stops the sort before it is moved, and what was done is
    recorded by the caller. Nothing is left half-moved (decision 119).

    **Each verdict is kept the moment the next file is taken** (decision
    189): the returns' caches are saved before every file - one small
    transaction, and none when nothing changed - so a pass killed mid-sort
    reads again only the file it was killed on. **And the household's time
    stops only a new judgment** (ruling 2.2): past ``deadline``
    (``ocr.awake_clock``) a file whose bytes a return's record already
    holds is still decided from that record, which reads nothing, and the
    first file that would need a judgment stops the sort before it is
    moved - it and the rest stay where they are, in the inbox or the
    year's folder, unrecorded, for the next pass. One whose bytes are on
    record but must be routed afresh (a re-file, a re-send after a set
    aside) stops at the judgment itself (:class:`OutOfTime`), after its
    move: it rests in the year's folder with no row, a stray the next pass
    sorts where it lies (decision 23).

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
    pending = [(d, False) for d in drops] + [(p, True) for p in strays]
    for run in runs:
        run.cache.deadline = deadline      # a judgment past it is not started
    try:
        for taken, (drop, already_filed) in enumerate(pending):
            if not dry_run:
                for run in runs:
                    run.cache.save()          # the file before this one's verdicts
            if watch is not None:
                watch.say("file", step="sort", name=drop.name)
                if watch.stop_asked():
                    # A person's stop is the household's deadline, now.
                    deadline = -math.inf
                    for run in runs:
                        run.cache.deadline = deadline
            # A file the sync client has not downloaded is not a document yet.
            if is_cloud_placeholder(drop):
                first.report.waiting.append(drop)
                continue

            try:
                drop.stat()          # still there, and readable: a file mid-write is left
            except OSError as exc:
                first.report.errors.append(FileError(
                    drop.name, f"could not read it ({errors.error_class(exc)}); left in place", True
                ))
                errors.keep("filer: left in place", exc, name=drop.name)
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

            # Past the household's time (decision 189, ruling 2.2), a file is
            # taken only when its bytes are on some return's record, so the
            # record decides it and nothing is read. Anything else would need a
            # new judgment: it and the rest wait where they are.
            if deadline is not None and ocr.awake_clock() >= deadline:
                held = _digest_or_none(drop)
                if not held or not any(held in run.known for run in runs):
                    _out_of_time(first, len(pending) - taken)
                    break

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
                    # Through the one door into the client tree (decision 188).
                    _door_for(root_of(first.engagement_dir),
                              household_name_of(first.engagement_dir), original)
                    _move_whole(drop, original, within=inbox)
                except (OSError, FilingError) as exc:
                    first.report.errors.append(FileError(
                        drop.name,
                        f"could not move it into {originals_dir.name} ({errors.error_class(exc)}); left in place",
                        True,
                    ))
                    errors.keep("filer: left in place", exc, name=drop.name)
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
                        drop.name, f"could not read it ({errors.error_class(exc)}); left in place", True
                    ))
                    errors.keep("filer: left in place", exc, name=drop.name)
                    continue
                digest, size_kb = "", 0.0     # moved, unreadable now: recorded anyway
                errors.keep("filer: preserved but could not read it back", exc, name=drop.name)

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
            for run in runs:
                run.context.subfolder = subfolder
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
            except OutOfTime:
                # A drop on record that must be routed afresh, or an email or a
                # zip an attachment of which would need a judgment, past the
                # time: moved, unrecorded, a stray for the next pass (decision
                # 23), and the household is out of time.
                _out_of_time(first, len(pending) - taken)
                break
            except Exception as exc:  # the original is safe; say so and go on
                errors.keep("filer: could not file", exc, name=drop.name)
                # A refused mark's step never points at the unmarked original.
                step = MARK_REFUSED_STEP if isinstance(exc, MarkRefusedError) else "file it by hand"
                run = first
                entry = IndexEntry(
                    received=stamp, original_name=recorded_name(drop.name), size_kb=size_kb,
                    digest=digest, identifier="",
                    prepared_location="", pbc_location=location_of(run.engagement_dir, original),
                    decision=NEEDS_REVIEW,
                    reason=(f"could not be filed ({errors.said(exc, FIRM_WRITTEN)}); "
                            f"original preserved in {location_of(run.engagement_dir, original)} - "
                            f"{step}"),
                    code=reasons.COULD_NOT_FILE_CODE, subfolder=subfolder,
                )
                run.report.errors.append(FileError(drop.name, entry.reason, False))
                run.report.review.append(entry)
            finally:
                for one in runs:
                    one.context.subfolder = ""

            run.entries.append(entry)
            if entry.decision != DUPLICATE and digest:
                run.known[digest] = entry
    finally:
        for run in runs:
            run.cache.deadline = None      # the sort's own, never a later caller's (the review's N8)


def _out_of_time(first: _ReturnRun, left: int) -> None:
    """Say that the household's time ran out with ``left`` files not taken."""
    first.report.unreached = left
    log.warning("The household's time ran out; %d file(s) wait for the next pass", left)


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
    arrived = "/".join(parts_below(inbox, drop) or (drop.name,))
    said = RETURNED_SENTENCE.format(drop=_shown(arrived), date=stamp, pbc=_shown(entry.pbc_location))
    copies = ([location for location in entry.filed_locations
               if _absent(locate(engagement_dir, location))] if both_gone(entry) else [])
    if copies:
        remade = REMADE_SENTENCE.format(home=PLACES_JOINED.join(copies), pbc=_shown(entry.pbc_location),
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
        try:
            _do_all_or_take_back(engagement_dir, key, ops, run.cache)
        except (OSError, FilingError) as exc:
            first.report.errors.append(FileError(
                drop.name,
                f"could not be moved back to {_shown(entry.pbc_location)} ({errors.error_class(exc)}); left in place",
                True))
            errors.keep("filer: moving it back failed", exc, name=drop.name)
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


def _do_all_or_take_back(engagement_dir: Path, key: str, ops: list[ledger.IntentOp],
                         cache: ContentCache | None = None) -> None:
    """Do every operation of an intent already written, all or nothing: a
    step that fails (an ``OSError`` or a :class:`FilingError`) takes back
    what this call already did (:func:`_take_back`), abandons the intent
    (:func:`_abandon`) and raises for the caller to say. A kill is not a
    failure: nothing is taken back, and the next pass finishes the intent."""
    done: list[ledger.IntentOp] = []
    try:
        for op in ops:
            _do_op(engagement_dir, op, cache=cache)
            done.append(op)
    except (OSError, FilingError):
        _take_back(engagement_dir, done)
        _abandon(engagement_dir, key)
        raise


def _take_back(engagement_dir: Path, done: list[ledger.IntentOp]) -> None:
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
                # Put back where it was recorded, through the one door when
                # that is the client tree (decision 188).
                _door_for(root, place_of(root, source).household or household_name_of(engagement_dir),
                          source)
                _move_whole(target, source, within=root)
            elif _the_bytes(target) == op.get(ledger.DIGEST_KEY):
                target.unlink()
        except (OSError, FilingError) as exc:
            errors.keep("filer", exc, name=target.name)
            log.error("Could not undo a %s after a later step failed (%s)",
                      op[ledger.OP_KEY], errors.error_class(exc))


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
        # A Windows with long paths off will not make the folder, or write
        # into it, past its limit: the stem is cut until it fits (pilot
        # decision P29, the review's finding 3). Elsewhere folder_need is 0.
        while folder_need(folder, room_root(home.engagement_dir)) > path_limit() and len(stem) > 1:
            stem = stem[:-1].rstrip(". ") or _OPENED_FALLBACK[:1]
            folder = base / _named(stem, counter, "")
        if folder not in elsewhere:
            return folder
        counter += 1


def _take_out(folder: Path, attachment: containers.Attachment, claimed: set[Path], *,
              root: Path, recorded: Mapping[Path, str] | None = None) -> tuple[Path, str]:
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
    row holds is never handed back. ``root`` is the clients root room is
    counted from (SPEC-mac R9).
    """
    data = attachment.data
    digest = hashlib.sha256(data).hexdigest()
    suffix = Path(attachment.name).suffix
    if suffix and not _AN_EXTENSION.fullmatch(suffix):
        suffix = ""
    folder.mkdir(parents=True, exist_ok=True)
    target = _unique_path(folder, attachment.name, room=_room_in(folder, suffix, root),
                          spare=_TEMP_ROOM, recorded=recorded, digest=digest, reuse=True,
                          claimed=claimed, root=root)
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
                             reason=exc.sentence, code=exc.code, candidates=(), evidence=""),
              digest)
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
    subfolder = home.context.subfolder
    at = {id(run): location_of(run.engagement_dir, original) for run in runs}
    folder = _opened_folder(home, original, runs)
    claimed: set[Path] = set()
    taken: list[tuple[containers.Attachment, Path, str]] = []
    in_the_year = {} if dry_run else _taken_in_the_year(home, runs)
    for one in opened.attachments:
        if dry_run or is_program(one.name):
            # A program inside is never written out of it (decision 190):
            # its row parks as not a document, naming no file.
            taken.append((one, folder / one.name, hashlib.sha256(one.data).hexdigest()))
        else:
            taken.append((one, *_take_out(folder, one, claimed, recorded=in_the_year,
                                          root=room_root(home.engagement_dir))))
    entry = IndexEntry(
        received=stamp, original_name=recorded_name(drop.name), size_kb=size_kb, digest=digest,
        identifier="", prepared_location="", pbc_location=at[id(home)], decision=OPENED,
        reason=_opened_sentence(opened), subfolder=subfolder,
    )
    home.opened[ledger_key(entry)] = {
        ledger.ATTACHMENTS_KEY: [
            {"name": one.name, "size": len(one.data), "digest": sha,
             "location": ("" if dry_run or is_program(one.name)
                          else location_of(home.engagement_dir, path))}
            for one, path, sha in taken
        ],
        ledger.SKIPPED_KEY: [{"name": one.name, "why": one.why} for one in opened.skipped],
    }
    if dry_run:
        home.report.opened.append(entry)
        _keep(home, entry, digest)
        return
    named = _on_record((run.engagement_dir, run.entries) for run in runs)
    waiting: list[str] = []
    out_of_time = False
    for one, path, sha in taken:
        if path in named:
            continue
        try:
            if not _decide_attachment(one, path, sha, stamp, runs, first, at):
                waiting.append(one.name)
        except OutOfTime:
            # The household's time ran out before this attachment's
            # judgment (decision 189, ruling 2.2; the review's M2): it and
            # the rest wait, and the household is out of time exactly as
            # when a drop is left unreached - said, and no draft is made.
            out_of_time = True
            break
    if waiting or out_of_time:
        # An attachment that waits - its reader could not start (decision
        # 150), or the time ran out before it - gets no row, and neither
        # does the container, or the next pass would know its bytes and
        # never open it again. It rests in the year's folder as a stray;
        # the next pass reopens it, reuses each file it finds by its bytes,
        # skips each attachment a row already names, and reads the ones
        # that waited. The pass's one warning says how many wait.
        home.opened.pop(ledger_key(entry), None)
        home.reopen.add(folder)
        if waiting:
            log.warning("Left %s for the next pass: the reader could not start on %s",
                        drop.name, ", ".join(waiting))
        if out_of_time:
            raise OutOfTime   # the sort says it and stops (_sort_all)
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
    150's :func:`_not_read`), True otherwise. Past the household's time it
    raises :class:`OutOfTime` with nothing recorded (decision 189, ruling
    2.2): a wait for time is not a reader that could not start, and
    :func:`_open_container` says the difference.

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
    outer = {id(run): run.context.subfolder for run in runs}
    for run in runs:
        run.context.container = at[id(run)]
        run.context.subfolder = ""
    try:
        known = any(digest in run.known and _may_hold(run) for run in runs)
        if is_program(attachment.name):
            # Never written out of its container, so there is no file for
            # decision 111's bytes-first road to act on: it parks, every
            # time it arrives (decision 190).
            run, entry = _park_a_program(named, path, digest, size_kb, stamp, [first], first,
                                         kept_at="")
        elif attachment.parks and not known:
            run, entry = first, _park_it(named, path, digest, size_kb, stamp, first,
                                         reason=attachment.parks, code=attachment.code,
                                         candidates=(), evidence="")
        else:
            decided = _decide_across(named, path, digest, size_kb, stamp, runs, first)
            if decided is None:
                return False
            run, entry = decided
    except OutOfTime:
        raise                         # a wait, not a failure: the container says it
    except Exception as exc:          # the file is safe where it was written; say so and go on
        errors.keep("filer: could not file an attachment", exc, name=attachment.name)
        run = first
        where = location_of(run.engagement_dir, path)
        entry = IndexEntry(
            received=stamp, original_name=attachment.name, size_kb=size_kb, digest=digest,
            identifier="", prepared_location="", pbc_location=where, decision=NEEDS_REVIEW,
            reason=(f"could not be filed ({errors.said(exc, FIRM_WRITTEN)}); "
                    f"taken out to {where} - file it by hand"),
            container=at[id(run)], code=reasons.COULD_NOT_FILE_CODE,
        )
        run.report.errors.append(FileError(attachment.name, entry.reason, False))
        run.report.review.append(entry)
    finally:
        for one in runs:
            one.context.container = ""
            one.context.subfolder = outer[id(one)]
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


def _with_the_name(routing: Routing, verdict: NameVerdict) -> Routing:
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
    kept return's Reason gains when it files, and ``spelling`` the firm's
    own spelling that confirmed it - what a row waiting for another
    household quotes (decision 204), never a word of the page.
    """

    kept: list[tuple[_ReturnRun, Routing]] = field(default_factory=list)
    graded: dict[int, Routing] = field(default_factory=dict)
    met: list[tuple[object, str]] = field(default_factory=list)
    confirmed: dict[int, str] = field(default_factory=dict)
    spelling: dict[int, str] = field(default_factory=dict)

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


def _name_question(run: _ReturnRun, runs: list[_ReturnRun]) -> NameQuestion:
    """Whose document this is, asked for ``run`` (decision 128): its own
    spellings, and every other return the drop may feed with theirs."""
    return NameQuestion(
        own=run.spellings,
        others=tuple((other.label, other.spellings) for other in runs if other is not run),
    )


def _by_the_name(
    judgment: Judgment, accepting: list[tuple[_ReturnRun, Routing]], runs: list[_ReturnRun]
) -> _NameStage:
    """The name tier (decision 128), run over what the request lists accepted.

    For each accepting return, in order, the page is asked whether it names
    one of that return's people, somebody on another return the drop may
    feed, or nobody (:func:`tracker.names.check_name`, asked in the reader
    child with the rules since decision 189 and read here off the
    ``judgment``). Then the table the owner settled:

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
        verdict = judgment.name(_name_question(run, runs))
        routing = _with_the_name(routing, verdict)
        stage.graded[id(run)] = routing
        if verdict.outcome == NAME_CONFIRMED:
            stage.confirmed[id(run)] = NAME_CONFIRMED_NOTE.format(spelling=verdict.matched)
            stage.spelling[id(run)] = verdict.matched
            stage.kept.append((run, routing))
        elif verdict.outcome == NAME_VETOED:
            stage.met.append((reasons.NAMES_ANOTHER_RETURN, reasons.NAME_AND_RETURN.format(
                spelling=verdict.other, label=verdict.other_label)))
        elif not any(item.named for identifier in routing.filed_to      # decision 128: a page split across
                     if (item := run.context.by_id.get(identifier)) is not None):   # requests is named if any is
            stage.kept.append((run, routing))   # a receipt, a log, a headerless export
        elif run.people:
            stage.met.append((reasons.NAME_NOT_ON_PAGE, run.label))
        else:
            stage.met.append((reasons.NO_PEOPLE_ON_FILE, run.label))
    return stage


def _park_a_program(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str, runs: list[_ReturnRun],
    first: _ReturnRun, *, kept_at: str | None = None, resent: str = "",
) -> tuple[_ReturnRun, IndexEntry]:
    """Park a program (``validators.is_program``) in the dropping
    household's own return, as ``reasons.NOT_A_DOCUMENT``, with no review
    copy (decision 190). ``resent`` is the set-aside sentence a program
    sent again after a person set it aside carries, as any re-send does."""
    home = next((one for one in runs if one.home), first)
    return home, _park_it(drop, original, digest, size_kb, stamp, home,
                          reason=reasons.NOT_A_DOCUMENT.format(), code=reasons.NOT_A_DOCUMENT.code,
                          candidates=(), evidence="", copy=False, kept_at=kept_at, resent=resent)


def _settle(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str, runs: list[_ReturnRun],
    judgment: Judgment, routed: list[tuple[_ReturnRun, Routing]], *,
    shortlist_across: bool, refiled: str = "", resent: str = "",
) -> tuple[_ReturnRun, IndexEntry]:
    """Settle one preserved original once the router has answered for it:
    the return it belongs to, and the row that says so. The one place the
    sequence after routing is written, and both roads reach it with what
    they routed from one reading: the household pass
    (:func:`_decide_across`) with every return in ``runs``, and a re-send
    routed afresh (:func:`_sort_one`, decision 111) with the one return
    whose record holds the bytes.

    In order (decisions 128, 129, 131, 137, 143 and 204): the name tier over
    the returns that accepted it (:func:`_by_the_name`); exactly one left
    files it where it is one of the household's own, and where that one
    lives in another household it parks at home instead - out of an email
    or a zip, naming nobody, or naming that return's person; no room even
    for the request's shortest name parks it; several left park it
    contested; none parks it, in the name's words where the name is what
    emptied the list. Every park but the one across households lands in
    :func:`_the_home` over ``routed``, which on the re-send road is always
    the return that holds the bytes.

    ``shortlist_across`` is Q-B, Jason's and open (P313): what the park
    across households carries and where it lands - the shortlist, the
    home's evidence, the return, and the name's evidence on the wanting
    return - chosen together. ``True`` is the household road's: the home
    :func:`_the_home` chose, its list's shortlist and evidence, then the
    wanting return's evidence as the name tier left it, ``RULE_NAME`` entry
    and all. ``False`` is the re-send road's, as it has always parked: the
    household's first own return, no shortlist and none of the home's
    evidence - the re-send road routes only the return decision 132's rule
    found holding the bytes, never the home's own - and the wanting
    return's evidence as the router gave it, before the name tier. It is
    keyword-only with no default, so each caller says which answer it
    builds; Jason's answer, when he gives it, changes the re-send road's
    call - what it routes, and this argument - and nothing in this sequence.

    ``refiled`` and ``resent`` are the re-send road's sentences (decision
    111): ``refiled`` on its filing, ``resent`` on its filing and on every
    park. The household road gives neither.
    """
    accepting = [(run, routing) for run, routing in routed if routing.routed]

    # The name check was asked of the same reading, in the same judgment.
    # With no words at all the router has already parked the document
    # (UNREADABLE) and nothing accepted it, so the stage has nothing to judge.
    stage = _by_the_name(judgment, accepting, runs)
    kept = stage.kept

    no_room: NoRoom | None = None
    unnamed_across = opened_across = named_across = False
    if len(kept) == 1:
        run, routing = kept[0]
        item = run.context.by_id.get(routing.identifier or "")
        # Out of an email or a zip (decision 143): the attachment's original
        # is the firm's copy of a part of the client's file, and it never
        # moves into another household's folder. It waits at home, named
        # or not, for a person to file it by hand.
        if item is not None and not run.home and run.context.container:
            opened_across, item = True, None
        # Across households, filing needs a confirmed name (decision 137,
        # B2; the owner's Q-2). A document the name tier kept only because
        # its request is unnamed would otherwise move into another
        # household's folder, which that household's people can open, on
        # the strength of its keywords alone. It waits at home for a person.
        if item is not None and not run.home and id(run) not in stage.confirmed:
            unnamed_across, item = True, None
        # And with the name confirmed, it still waits (decision 204, the
        # owner's lane-B ruling, revising 132): a printed name is the
        # client's word, and a client's word alone never places a document
        # in a folder another household's people can open. The confirmed
        # name was the pass's last road across, so the pass now never files
        # there at all; the row keeps what that return's list accepted, and
        # a person's one click hands it over.
        if item is not None and not run.home:
            named_across, item = True, None
        if item is not None:
            try:
                return run, _file_it(drop, original, digest, size_kb, stamp, run, routing, item,
                                     refiled=refiled, resent=resent,
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
    # is, the household that was dropped in is the one that has it. (On
    # the re-send road ``routed`` is the one return whose record holds the
    # bytes, and that return is the home here: decision 111's row decides
    # in its own record.)
    home, home_routing = _the_home(accepting, routed)
    home_routing = stage.graded.get(id(home), home_routing)

    if no_room is not None:
        said = routing if home is run else home_routing
        # A request in another of this household's returns is named by that
        # return's label (decision 131's review, deviation 5): a page naming
        # that return's person, whose room ran out, parks in the home
        # return the name vetoed it from, where "this request" would be a
        # list the person reading it is not looking at. (Since decision 204
        # a return in another household never files on the pass, so the
        # one no room reaches here for is always this household's.)
        reason = str(no_room) if home is run else PATH_NO_ROOM_IN.format(
            label=run.label, length=no_room.length, limit=no_room.limit,
            ext=_kind_of(no_room.extension))
        return home, _park_it(
            drop, original, digest, size_kb, stamp, home,
            reason=reason, code=reasons.NO_ROOM_CODE, candidates=said.candidates,
            evidence=format_evidence(said.evidence_record), resent=resent,
        )

    if opened_across or unnamed_across or named_across:
        # The park across households (decisions 137, 143 and 204), in the
        # words of whichever of the three it is - and carrying what Q-B's
        # answer says (P313; ``shortlist_across`` above).
        across: _ReturnRun
        shortlist: Routing | _NoRouting
        candidates: tuple[str, ...]
        if shortlist_across:
            across, shortlist, candidates, wanting = home, home_routing, home_routing.candidates, routing
        else:
            across = next((one for one in runs if one.home), run)
            shortlist, candidates, wanting = _NO_ROUTING, (), routed[0][1]
        if opened_across:
            reason, code = reasons.OPENED_NOT_ACROSS.format(), reasons.OPENED_NOT_ACROSS.code
        elif unnamed_across:
            reason, code = reasons.UNNAMED_ACROSS_HOUSEHOLDS.format(), reasons.UNNAMED_ACROSS_HOUSEHOLDS.code
        else:
            reason, code = _named_across(stage, run), reasons.NAMED_ACROSS_HOUSEHOLDS.code
        return across, _park_it(
            drop, original, digest, size_kb, stamp, across,
            reason=reason, code=code, candidates=candidates,
            evidence=_with_the_wanting_return(shortlist, run, wanting), resent=resent,
            waits_for=_waits_for(run, wanting) if named_across else "",
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
            code=reasons.CONTESTED_BETWEEN_RETURNS_CODE,
            candidates=home_routing.candidates,
            evidence=format_evidence(home_routing.evidence_record), resent=resent,
        )

    # Nothing left at all. Where the name is what emptied the list, the row
    # says so in the name's own words rather than the router's "matched no
    # request", which would be a lie about a W-2 the list plainly wanted.
    return home, _park_it(
        drop, original, digest, size_kb, stamp, home,
        reason=stage.reason or home_routing.reason,
        code=reasons.code_of(stage.reason) or home_routing.code,
        candidates=home_routing.candidates,
        evidence=format_evidence(home_routing.evidence_record), resent=resent,
    )


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
    - **then exactly one.** Exactly one return left files it where it is
      one of the household's own; several park it naming them all; none
      parks it. Where the one left lives in another household the pass
      never files (decision 204, revising 132): it parks, and the reason
      says why - out of an email or a zip (143), naming nobody (137 B2),
      or naming that return's person, when the row keeps what that
      return's list accepted (``waits_for``) so a person's one click can
      hand it over. A park always lands in the dropping household's own
      home return (:func:`_the_home`), with the name's reason where the
      name is what emptied the list. That is the third standing rule -
      nothing is guessed - read across the feed list instead of across
      one list, with a person's say on top of it wherever it crosses.
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
                                  code=reasons.OPENED_NOT_ACROSS.code,
                                  candidates=(), evidence="")

    # A program is not a document (decision 190): parked before any
    # reading, routing or shortlist, so nothing its name says reaches a
    # request, and with no review copy, because nobody here opens it. Its
    # original rests where it was moved, byte for byte.
    if is_program(drop.name):
        return _park_a_program(drop, original, digest, size_kb, stamp, runs, first)

    # One reading, however many returns judge it (decision 128). A dry run
    # judges the drop where it lies, as it always has.
    judged = drop if runs[0].context.dry_run else original
    # The drop is judged once, in the reader child, against every row it may
    # be routed on and whose it is for every return in ``runs`` (decision
    # 189): the rules and the name run under the document's stop, and no word
    # of it comes back.
    names = tuple(_name_question(run, runs) for run in runs)
    before_a_judgment(runs[0].cache)      # the household's time (ruling 2.2)
    judgment = read_once(judged, questions_for([item for run in runs for item in run.items], names=names))
    reading = judgment.extraction
    if _not_read(reading):
        return None
    # What the reading cost, kept for the run's summary (decision 127). One
    # reading serves every return that judges it (decision 128), so it is
    # recorded once, against the pass's first own return (``first``, the
    # run the inbox's own notes ride) - the run that already speaks for
    # this household's inbox. It is recorded after the fact and changes
    # nothing: a slow document is read to the end, and then said.
    first.report.timed(drop.name, reading.seconds)
    routed = [(run, route_file(judged, run.items, judgment=judgment,
                               digest=digest, cache=run.cache, pdf_cache=run.context.pdf_cache))
              for run in runs]
    # What happens to it now is the one sequence the re-send road settles
    # by too, with this road's answer to Q-B (P313).
    return _settle(drop, original, digest, size_kb, stamp, runs, judgment, routed, shortlist_across=True)


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
    return bool(reading.transient) and reading.code == reasons.READER_UNAVAILABLE.code


def _may_hold(run: _ReturnRun) -> bool:
    """Whether ``run``'s record may answer for the bytes of the document
    being decided (decision 143's review, B1): any return for a loose drop
    (decision 132), and only the dropping household's own for an
    attachment, whose name and ``_Opened`` path never enter another
    household's record. ``context.container`` is set on every run around
    one attachment's decision, so the run itself says which it is."""
    return not (run.context.container and not run.home)


def _with_the_wanting_return(home_routing: Routing | _NoRouting, run: _ReturnRun, routing: Routing) -> str:
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


def _named_across(stage: _NameStage, run: _ReturnRun) -> str:
    """The Reason of a document that names the person of a return in
    another household (decision 204): the firm's own spelling that matched
    and that return's label - both the firm's words, never the page's."""
    return reasons.NAMED_ACROSS_HOUSEHOLDS.format(spelling=stage.spelling[id(run)], label=run.label)


def _waits_for(run: _ReturnRun, routing: Routing) -> str:
    """The Waits For cell of a document parked because it names another
    household's person (decision 204): that return's line and what its
    list accepted - the requests in the order the page names their forms
    (decision 94) and the Also Answers a consolidated statement carries
    (decision 146), each filtered to that list as :func:`_file_it` filters
    them - so the one click files exactly what the pass would have."""
    return format_waits_for(WaitsFor(
        household=household_name_of(run.engagement_dir),
        return_name=run.engagement_dir.name,
        identifiers=tuple(i for i in routing.filed_to if i in run.context.by_id),
        answers=format_answers([one for one in routing.answers if one[0] in run.context.by_id]),
    ))


def _the_home(accepting: list[tuple[_ReturnRun, Routing]], routed) -> tuple[_ReturnRun, Routing]:
    """The return a document nobody may file parks in, and what its own
    request list made of it (decisions 125 and 129): the **dropping
    household's own** return of the first request that accepted it, else its
    first return by order - a document only a fed return accepted parks at
    home all the same, because the household that has the original is the
    one that was dropped in.
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
    #: The client's subfolder of the inbox a drop came out of (decision 147),
    #: as the path below the inbox, and ``""`` for any other. Set on every
    #: run around that drop's decision and cleared after it, as
    #: ``container`` is, so the row every road writes - filed, parked, a
    #: duplicate or the container's own - carries it in its ``subfolder``
    #: column (decision 190: a column, never a clause of the Reason), and so
    #: does the intent written before it. Cleared around an attachment's
    #: decision: what came out of a zip did not come out of the subfolder,
    #: the zip did. **Accepted limit** (decision 119): the inbox move writes
    #: no intent, so a pass killed between the move and the row leaves a
    #: stray the next pass files where it lies, with no subfolder.
    subfolder: str = ""
    #: Every path an open intent of the household's pass will still write
    #: to (decision 147, the designer's ruling on deviation 3), read once
    #: per pass after recovery and set on every run: a name taken as a
    #: row's resting place is, for :func:`_taken_in_the_year`.
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
                                 room=_room_in(dest_folder, extension,
                                               room_root(run.engagement_dir)))
    if run.dry_run:
        return prepared_location(dest_folder, filed_as), None
    return prepared_location(dest_folder, filed_as), dest_folder / filed_as


def _intend_and_do(
    engagement_dir: Path, entry: IndexEntry, ops: list[ledger.IntentOp], *, by: str, then: str,
    cache: ContentCache | None, dry_run: bool, also: Sequence[dict] = (),
) -> None:
    """Write down what ``entry`` will be, then do ``ops``: the pass's park
    and a filing's one shape of "intend, then act".

    The intent carries the row the caller will record and the event it will
    be recorded as, so a pass killed between the copy and the record is
    finished from the record: the copies that are already there are left
    alone, the ones that are not are made, and the row is recorded as it was
    decided (decision 119). A dry run, or no operation, writes nothing.
    """
    if dry_run or not ops:
        return
    _intend(engagement_dir, ledger_key(entry), ops, by=by, row=entry_to_json(entry), then=then,
            also=list(also))
    for op in ops:
        _do_op(engagement_dir, op, cache=cache)


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
    _intend_and_do(target, row, ops, by=by, then=then, cache=cache, dry_run=dry_run, also=also)


def _file_it(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str,
    run: _ReturnRun, routing: Routing, item: RequestItem, *, refiled: str = "", resent: str = "",
    confirmed: str = "",
) -> IndexEntry:
    """File one preserved original under the request that accepted it.

    One row per request the router named (decision 94 names more than one
    where a page carried more than one form), and one working copy per
    row. The original is preserved once, under its own name, in the
    client's folder for the year, and the index keeps one row for it: the
    copies are this row's, not rows of their own.

    Only ever into one of the household's own returns (decision 204): a
    return in another household is reached by a person's
    :func:`hand_over`, which moves the original and says where it was
    dropped (:data:`DROPPED_ELSEWHERE`); the pass never does either.

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
    # The original rests where the inbox move left it: the pass files only
    # into the household's own returns (decision 204), and an original
    # moves once within a household (decision 125).
    resting = original
    locations = [location for location, _copy in planned]
    entry = IndexEntry(
        received=stamp, original_name=recorded_name(drop.name), size_kb=size_kb,
        digest=digest, identifier=item.identifier,
        prepared_location=locations[0],
        pbc_location=location_of(run.engagement_dir, resting), decision=FILED,
        reason="; ".join(part for part in
                         (routing.reason, refiled, resent, confirmed) if part),
        candidates=CANDIDATE_SEP.join(routing.candidates),
        evidence=format_evidence(routing.evidence_record),
        also_filed=CANDIDATE_SEP.join(locations[1:]),
        container=context.container,
        # Decision 146: the asked requests a consolidated statement answers
        # without a copy, as the routing named them - each still on this
        # return's list, since the routing was this list's.
        answers=format_answers([one for one in routing.answers if one[0] in context.by_id]),
        code=routing.code, subfolder=context.subfolder,
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


def _park_it(
    drop: Path, original: Path, digest: str, size_kb: float, stamp: str,
    run: _ReturnRun, *, reason: str, code: str, candidates: tuple[str, ...], evidence: str, resent: str = "",
    copy: bool = True, kept_at: str | None = None, waits_for: str = "",
) -> IndexEntry:
    """Park one preserved original in this return's Needs Review, with a
    working copy a person can open, the sentence that says why and the code
    of the cause that sentence says (decision 190) - required, because a
    parked row's code is what the letter and the card read - and, for a
    document naming another household's person, what it waits for
    (``waits_for``, decision 204).

    ``copy=False`` parks a program (decision 190): no review copy, so the
    row's ``prepared_location`` is empty and nothing of it reaches the
    review folder. ``kept_at`` is where the row says its original rests
    when that is not ``original`` - ``""`` for a program inside an email
    or a zip, which is never written out of it."""
    context = run.context
    review_name = drop.name
    parking: list[ledger.IntentOp] = []
    past_reader = ""
    if copy and not context.dry_run:
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
            review_target, past_reader = _review_copy_path(
                context.review_dir, drop.name, room_root(run.engagement_dir))
            parking.append(_op(run.engagement_dir, ledger.OP_COPY,
                               original, review_target, digest))
        context.review_dir.mkdir(parents=True, exist_ok=True)
        review_name = review_target.name
    reason = "; ".join(part for part in (resent, reason, past_reader) if part)
    entry = IndexEntry(
        received=stamp, original_name=recorded_name(drop.name), size_kb=size_kb,
        digest=digest, identifier="",
        prepared_location=prepared_location(context.review_dir, review_name) if copy else "",
        pbc_location=(location_of(run.engagement_dir, original) if kept_at is None else kept_at),
        decision=NEEDS_REVIEW,
        # The flag first: what a person opening the card should read before
        # the reason for parking it; a copy past a reader's limit, last. The
        # subfolder it came from (decision 147) is its own column.
        reason=reason,
        candidates=CANDIDATE_SEP.join(candidates),
        evidence=evidence,
        container=context.container,
        waits_for=waits_for,
        code=code, subfolder=context.subfolder,
    )
    _intend_and_do(context.engagement_dir, entry, parking, by=ledger.BY_PASS, then=ledger.PARKED,
                   cache=context.cache, dry_run=context.dry_run)
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
        # ``tracker.actions.dismiss_review_file`` wrote them - so the card,
        # the Index and the files-waiting warning all say the client sent
        # it again.
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
            received=stamp, original_name=recorded_name(drop.name), size_kb=size_kb,
            digest=digest, identifier=earlier.identifier,
            prepared_location="",
            pbc_location=location_of(run.engagement_dir, original), decision=DUPLICATE,
            reason=said,
            container=context.container, subfolder=context.subfolder,
        )
        run.report.duplicates.append(entry)
        return run, entry

    # A program is not a document on this road either (decision 190's
    # review, M2): a program a person set aside, or one whose filed copy
    # went, arriving again is asked before it is read, so its name never
    # reaches a request and it gets no review copy - the same park as its
    # first arrival, saying it was sent again.
    if is_program(drop.name):
        return _park_a_program(drop, original, digest, size_kb, stamp, runs, run, resent=resent)

    judged = drop if context.dry_run else original
    # Judged against this return's rows, and whose it is for this one
    # return: the name tier below asks about no other (decision 189).
    before_a_judgment(context.cache)      # the household's time (ruling 2.2)
    judgment = read_once(judged, questions_for(
        context.items, names=(_name_question(run, runs),)))
    reading = judgment.extraction
    if _not_read(reading):
        return None
    # What the reading cost, for the run's summary (decision 127).
    run.report.timed(drop.name, reading.seconds)
    routing = route_file(
        judged, context.items, judgment=judgment,
        digest=digest, cache=context.cache, pdf_cache=context.pdf_cache,
    )
    # The same sequence the household pass settles a drop by, over the one
    # return this arrival belongs to: the name tier confirms it, another
    # return's person vetoes it, and on a named request a page naming nobody
    # parks it. A re-send whose bytes a return in another household already
    # holds is held to the same rule as a first arrival (decision 137's
    # review, B #5, the owner's "never"; decision 204): it is not filed
    # there, named or not, and parks in the drop's own household - naming
    # nobody, for the picker; naming that return's person, for one click -
    # carrying what this road's answer to Q-B says (P313).
    return _settle(drop, original, digest, size_kb, stamp, runs, judgment, [(run, routing)],
                   shortlist_across=False, refiled=refiled, resent=resent)


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
            name=entry.original_name, decision=entry.decision, reason=entry.reason),
            seq=held, identifier=entry.pbc_location)


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
    also: Sequence[str] = (),
    answers: str = "",
    waiting: bool = False,
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
    both used exactly as :func:`tracker.actions.assign_review_file` uses them.

    **The one click** (decision 204). The pass never files across
    households; a document naming the person of a return in another
    household parks here with ``reasons.NAMED_ACROSS_HOUSEHOLDS`` and a
    ``waits_for`` cell saying what that return's list accepted. ``waiting``
    is a person agreeing to it: the caller passes what the cell says -
    ``identifier`` and ``also``, decision 94's other forms, one copy each;
    ``answers``, decision 146's Also Answers - and, under both locks, the
    row is read again and the hand-over is refused unless it is still that
    parked row, its cell still names this return and these requests, and
    each is still on this return's list and not marked N/A. So the click
    carries out the pass's verdict whole, and a click on a row that changed
    since it was shown does nothing. ``also`` and ``answers`` are the
    ordinary picker's too, which passes neither.
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
        wanted = requests_taking(items, [identifier, *also])
        item = wanted[0]

        entries = read_index(home_return)
        position = find_parked(entries, original)
        entry = entries[position]
        _refuse_if_stale(home_return, entry, seq)
        if waiting:
            _refuse_unless_it_waits_for(entry, target_return, [one.identifier for one in wanted],
                                        answers)
        # Out of an email or a zip (decision 143): the file is the firm's
        # copy of a part of the client's file, and never moves into another
        # household's folder - the pass parks it at home in these words,
        # and a person's hand-over refuses it in the same ones.
        if entry.container and household_of(target_return) != household_of(home_return):
            raise FilingError(reasons.OPENED_NOT_ACROSS.format())
        source = locate(home_return, entry.pbc_location)
        if not source.is_file():
            raise FilingError(ORIGINAL_GONE.format(original=_shown(entry.pbc_location)))
        if is_cloud_placeholder(source):
            raise FilingError(ORIGINAL_SYNCING.format(original=_shown(entry.pbc_location)))
        digest = entry.digest
        if not digest:
            raise FilingError(
                f"the original {_shown(entry.pbc_location)} has no fingerprint on this row; the next pass "
                f"records one, and a document can only be handed over once it has one"
            )
        if sha256_of(source) != digest:
            raise FilingError(
                f"the original {_shown(entry.pbc_location)} no longer holds the bytes this row "
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
        # (decision 168), and reusing only that request's own copy - one
        # copy per request, as the pass makes them (decision 94).
        dest_folder = target_return / PREPARED_DIR_NAME
        names, to_make = hand_over_copies(target_return, wanted, items, source, digest)
        filed_as = names[0]
        dest_folder.mkdir(parents=True, exist_ok=True)

        # The parked copy here goes: the document is the other return's
        # now, and two copies of it in two queues would be two documents
        # where the client sent one. One a person annotated is not this
        # row's bytes and is left where it is, said so, exactly as a
        # filing leaves one.
        parked = locate(home_return, entry.prepared_location) if entry.prepared_location else None
        left_in_review = ""
        releasing: list[ledger.IntentOp] = []
        if parked is not None and _here(parked):
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
            code=reasons.ASSIGNED_BY_PERSON_CODE,
            # The candidates and the evidence were this return's request
            # list judging the page; they name identifiers the taking
            # return does not have, so they do not travel with the row.
            # The other copies and the Also Answers are the taking list's
            # own (decisions 94 and 146), filtered to it as the pass
            # filters them; what the row waited for is done.
            candidates="", evidence="",
            also_filed=CANDIDATE_SEP.join(prepared_location(dest_folder, name) for name in names[1:]),
            answers=format_answers([one for one in parse_answers(answers) if one[0] in items]),
            waits_for="",
        )
        released = RELEASED_TO.format(label=label, identifier=item.identifier)
        # The taking return's steps are held to its places before this
        # return's release is written (decision 180): a release recorded
        # for a filing that is then refused would take the document off
        # every queue.
        for op in ([_op(target_return, ledger.OP_MOVE, source, resting, digest)]
                   if resting != source else []) + [
                _op(target_return, ledger.OP_COPY, resting, copy, digest) for copy in to_make]:
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
                   copies=to_make,
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


def hand_over_copies(
    target_return: Path, wanted: Sequence[RequestItem], items: Mapping[str, RequestItem],
    source: Path, digest: str,
) -> tuple[list[str], list[Path]]:
    """The working copies a hand-over makes in the taking return's
    ``Prepared`` folder: one name per request of ``wanted`` (decision 94),
    in order, reusing only that request's own copy already holding these
    bytes (decision 168) - and the files still to make. Read only.

    Named to fit, before anything is made (decision 131). No room even for
    the shortest name refuses with :data:`PATH_NO_ROOM_IN`, naming the
    taking return by its label (decision 131's review, deviation 5): the
    person reads it on the dropping return's page, where "this request"
    would name a list they are not looking at. The card that offers the
    one click (decision 204) asks this too, so it never offers a click
    bound to fail.
    """
    dest_folder = target_return / PREPARED_DIR_NAME
    taken = {p.name.lower() for p in dest_folder.iterdir()} if dest_folder.is_dir() else set()
    extension = extension_of(source)
    names: list[str] = []
    to_make: list[Path] = []
    for one in wanted:
        existing = _existing_copy(dest_folder, source, digest,
                                  among=copies_of(one, list(items.values()), dest_folder))
        if existing is not None:
            names.append(existing.name)
            continue
        try:
            name = prepared_name_for(one, extension, taken,
                                     room=_room_in(dest_folder, extension,
                                                   room_root(target_return)))
        except NoRoom as exc:
            label = _label_of(target_return, _details_of(target_return))
            raise NoRoom(exc.length, exc.limit, exc.extension, sentence=PATH_NO_ROOM_IN.format(
                label=label, length=exc.length, limit=exc.limit,
                ext=_kind_of(exc.extension))) from None
        names.append(name)
        to_make.append(dest_folder / name)
    return names, to_make


def requests_taking(items: Mapping[str, RequestItem], identifiers: Sequence[str]) -> list[RequestItem]:
    """The requests of the taking return's list a hand-over files under, in
    the order given - or :class:`FilingError`, in the words a person reads,
    for one that is not on the list or is marked N/A. One place, because
    the card that offers the one click (decision 204) must refuse in the
    same words the click itself would."""
    wanted: list[RequestItem] = []
    for one in dict.fromkeys(identifiers):
        item = items.get(one)
        if item is None:
            raise FilingError(f"no request {one!r} in the request list")
        if item.manual_override == Override.NOT_APPLICABLE:
            raise FilingError(f"{one} is {override_label(item)}; clear the override first")
        wanted.append(item)
    return wanted


def waiting_target(claim: WaitsFor, returns: Iterable[Path]) -> Path | None:
    """The return of ``returns`` a Waits For claim names (decision 204), by
    the layout's one comparison of household and return names (decision
    188), or ``None`` where no return of them is it - the feed trimmed, the
    fed year moved on."""
    return next((path for path in returns
                 if name_key(household_name_of(path)) == name_key(claim.household)
                 and name_key(Path(path).name) == name_key(claim.return_name)), None)


#: What the one click (decision 204) is refused with on a row that is not
#: waiting for another household: the card offers it on no other row, so
#: this is a row rewritten since the card was drawn.
NOT_WAITING = "{name} is not waiting for a return in another household; file it with the picker"


def _refuse_unless_it_waits_for(
    entry: IndexEntry, target_return: Path, identifiers: Sequence[str], answers: str,
) -> None:
    """Refuse the one click (decision 204) unless ``entry`` is still a row
    parked because it names another household's person, and its Waits For
    cell names ``target_return`` - household and return, by the layout's
    one comparison (``name_key``, decision 188) - and exactly these
    requests and Also Answers. Read under both locks, after the row's
    version was checked, so the click can only ever do what the card said
    it would; anything else is a person's picker to decide."""
    claim = entry.waiting_for
    if (entry.decision != NEEDS_REVIEW or claim is None
            or entry.code != reasons.NAMED_ACROSS_HOUSEHOLDS.code):
        raise FilingError(NOT_WAITING.format(name=entry.original_name))
    if (waiting_target(claim, [target_return]) is None
            or tuple(claim.identifiers) != tuple(identifiers)
            or claim.answers != answers):
        raise FilingError(
            f"{entry.original_name} waits for {claim.household} / {claim.return_name}, "
            f"not what this click named; look at the row again")


#: What a review command given no handle says (decision 190's review,
#: M3/N3): an empty handle would name every row recorded as ``unnamed``,
#: or every program taken from an email or a zip, so it names none.
NO_HANDLE = "no file was named; pick the row again"


def _wanted(original: str) -> str:
    """The handle a review command was given, as a location compares it -
    refused when empty (:data:`NO_HANDLE`), never read as "the first row
    with no location"."""
    wanted = (original or "").replace("\\", "/").strip()
    if not wanted:
        raise FilingError(NO_HANDLE)
    return wanted


def _names_row(entry: IndexEntry, original: str, wanted: str, *, recorded: bool = True) -> bool:
    """Whether a review command's handle names this row: its original's
    location, its record key (:func:`ledger_key` - the handle a row with no
    location travels by, decision 190's review, M3), or its name - the
    recorded one too where ``recorded``. Asked by every lookup a review
    command makes, so a handle the API ships reaches the row it was drawn
    from."""
    if entry.pbc_location == wanted or (not entry.pbc_location and ledger_key(entry) == original.strip()):
        return True
    return entry.original_name in ((wanted, recorded_name(wanted)) if recorded else (wanted,))


def _find_row(
    entries: list[IndexEntry], original: str, decisions: Sequence[str],
    refusal: Callable[[IndexEntry], str],
) -> int:
    """Index of the newest row ``original`` names whose decision is one of
    ``decisions``: the one scan behind :func:`find_parked`,
    :func:`tracker.actions.find_filed` and :func:`tracker.actions.find_moved`,
    which differ only in the decisions a person may
    act on and in the sentence for a row that is something else
    (``refusal``). A same-name ``DUPLICATE`` is a re-send, so the older row
    it repeats is the one named.
    """
    wanted = _wanted(original)
    for position in range(len(entries) - 1, -1, -1):
        entry = entries[position]
        if _names_row(entry, original, wanted):
            if entry.decision in decisions:
                return position
            if entry.decision == DUPLICATE and entry.original_name in (wanted, recorded_name(wanted)):
                continue          # a re-send under the same name; the older row is the one named
            raise FilingError(refusal(entry))
    raise FilingError(f"nothing in the index is called {original!r}")


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
    pointed at.
    """
    return _find_row(entries, original, (*_PARKED, *accepting), lambda entry: (
        f"{entry.original_name} is not waiting for review (it is {entry.decision}"
        + (f" as {entry.prepared_location}" if entry.prepared_location else "")
        + ")"
    ))


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
    # A typed folder is parsed, never trusted (decision 188).
    ns.engagement_dir = door.typed_return(parser, ns.engagement_dir)

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
