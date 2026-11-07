"""How the sorter names, measures, copies and moves a file.

Every file the filer writes or moves passes through here, and each part
upholds one of the guarantees the filer's docstring states:

- **Names** (decisions 131, 144, 147 and 168). A working copy is named by
  :func:`prepared_name_for` - the request's identifier, short name and
  period - and a request's further copies number in one series
  (:func:`numbered`, the one shape a colliding name takes). Every other
  name the sorter gives - an original out of the inbox, a person's
  hand-over, a review copy, what is taken out of an email or a zip - comes
  from :func:`_unique_path`, the one numbering function, and a review copy
  is placed by :func:`_review_copy_path`, which never names a program
  (decision 190). :func:`_on_record` and :func:`_year_on_record` say which
  names a household-year's rows already hold, so a name one row holds is
  never handed to another file.
- **Room** (decision 131). :func:`room_for` measures, from the request list
  alone, how much room a return has under its folder;
  :func:`refuse_a_path_past_the_limit` refuses at creation and at the
  rollover a return whose deepest working copy would not fit; a name longer
  than its room is cut to fit, the document part alone; and where not even
  the shortest name fits, :class:`NoRoom` says so with both numbers.
- **The byte-proved copy** (decisions 155, 187 and 190). :func:`_copy_whole`
  copies through a temp beside its home, proves the temp against the bytes
  the record holds before it takes the proper name, and refuses a copy with
  nothing to prove it against before a byte is read. A review copy that can
  carry code is marked as from the internet so that Office opens it in
  Protected View, or it is not made.
- **The rename-only move** (decision 137). :func:`_move_whole` moves by
  rename and only by rename, and asks again, immediately before the rename,
  whether any folder on the way is now a link.
- **The client README's lock and the stranded-temp sweep** (decisions 130
  and 155). :func:`_readme_lock` keeps one refresh of a household's README
  from writing over another's; :func:`sweep_stranded_temps` takes away, at
  the start of a household pass, the temps a killed write left - only ever
  the tracker's own, and never an original.

**A working copy is whole or not there, and writable** (decision 155).
It is copied to a temp name beside its home, proved against the bytes
it was made from, flushed and renamed into place
(:func:`tracker.fsio.copy_atomically`), so a copy the power cut in half
never holds the proper name - its temp is left, and
:func:`sweep_stranded_temps` takes that away at the start of the next
household pass. A copy of a read-only original is made writable; the
original is only ever read.

**Why it is its own module** (SPEC-architecture-p4 P4.4, P331; the
architecture audit's A-1, step 2). This code sat in the filer, and every
part of it is about one file and the folder it goes to, not about which
request a document is for: nothing here routes, and nothing here reads a
name the filer defines. Moved out, the filer loses nearly a thousand
lines that a reader of the routing never needed. The README lock came
with the rest because the sweep takes it: a README temp in the client's
inbox is taken only under :func:`_readme_lock`, which is what every
README write holds, so the lock and its file name
(:data:`README_LOCK_FILENAME`) live beside the sweep that needs them.

**Why it sits at layer 2.** It reads the record, the request list, the
scaffold, the validators and the index (layer 1) and the layout, the door,
the disk writes, the engagement lock and the errors (layer 0), and in its
own layer ``containers`` (an email or a zip is marked for Protected View)
and :class:`tracker.content_check.ContentCache` (a proved copy's digest is
remembered for the pass). It may import nothing above layer 2 - not the
filer, the scanner or anything that drives a pass - and nothing of the
filer at all, at load time or at call time: the filer imports it, and so
do the API, the runner, the view, the rollover and the reminder, each for
the names it reads.

**Every reader asks this module.** The filer imports back from here only
what its own remaining code reads, and offers none of it on; every other
reader imports each name from here. A stand-in follows the name's readers
(the audit's A-4): one for a name this module reads as a global is set on
this module, and where the filer reads it too, on both.

**Why it logs as ``tracker.filer``** (SPEC-architecture-p4 section 2.1).
The run log and the error log print each line's logger name, so a name of
this module's own would change the lines a person and the office read. It
is the same logger object as the filer's, so no handler and no test sees a
difference.

The comments and docstrings below came with the code, word for word. Where
one names the pass, a person's filing or a function of the filer's, that is
the caller it describes; the code it describes is here.
"""

from __future__ import annotations

import logging
import os
import re
import time
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import cast

from tracker import containers, door, errors, ledger, store
from tracker.content_check import ContentCache
from tracker.door import through_a_link
from tracker.fsio import (
    copy_atomically,
    is_link,
    make_writable,
    mark_from_internet,
    stranded_temps,
    temp_owner,
)
from tracker.households import household_returns
from tracker.index import read_index
from tracker.layout import (
    MAX_PATH_LENGTH,
    PATH_TOO_LONG,
    deepest_path_length,
    folder_need,
    household_name_of,
    household_of,
    inbox_of,
    limit_for,
    local_limit,
    locate,
    measured_length,
    opened_dir_of,
    path_limit,
    recorded_name,
    room_root,
    root_of,
)
from tracker.locking import (
    EngagementLockedError,
    acquire_lock,
    pid_alive,
    release_lock,
)
from tracker.manifest import (
    ANY_EXTENSION,
    DEFAULT_EXTENSIONS,
    ManifestError,
    Override,
    RequestItem,
    is_reserved_name,
    label_for,
)
from tracker.records import IndexEntry
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    README_FIRMS,
    README_FIRST_LINE,
    README_NAME,
    REVIEW_DIR_NAME,
    assign_files,
    sanitize_component,
    whose_readme,
)
from tracker.validators import (
    bears_macros,
    extension_of,
    is_cloud_placeholder,
    is_program,
    sha256_of,
)

# The filer's logger, by its name (SPEC-architecture-p4 section 2.1): the run
# log and the error log print each line's logger name, so a name of this
# module's own would change the lines a person and the office read. It is the
# same logger object, so no handler and no test sees a difference.
log = logging.getLogger("tracker.filer")

_MAX_STEM = 110


def numbered(stem: str, counter: int, suffix: str) -> str:
    """``name (2).pdf`` - the one shape a colliding name takes."""
    return f"{stem} ({counter}){suffix}"


class FilingError(Exception):
    """A person's filing decision could not be carried out as asked."""

# A person's refusals, named once (SPEC-architecture-p4 P4.5, A-10): the
# sentences a filing action refuses with when the file it needs is not on this
# machine. Each was written inline at every action that said it; named here,
# the actions cannot drift apart and a guard can find the sentence by its name.

#: Refuses assigning a review file to a request and handing a file over, when the
#: original recorded for the row is not in the client's folder any more.
ORIGINAL_GONE = "the original {original} is no longer there"
#: Refuses those two, taking a filed document back out, and putting a moved copy
#: back, when the original is a cloud placeholder still syncing.
ORIGINAL_SYNCING = "the original {original} is still syncing; try again when it is here"
#: Refuses putting a moved copy back, and renaming a request, when a filed copy is
#: still syncing (it was ``RENAME_COPY_SYNCING`` in the filer).
COPY_SYNCING = "{location} is still syncing; try again when it is here"


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


def prepared_name_for(item: RequestItem, extension: str, taken: set[str], *,
                      room: int | None = None) -> str:
    """Canonical working-copy name: ``label_for(identifier, short name, period)`` plus the extension.

    ``taken`` holds names already used in ``PREPARED_DIR_NAME`` - every
    request's copies share it since decision 168, and two requests' names
    can never collide because they differ at the identifier; collisions
    get ``(2)``, ``(3)``… so a request expecting several files keeps them in
    one predictable series, sorted together.

    ``room`` is how many characters the whole file name may take - the
    caller's ``limit_for(extension)`` less the folder as room measures it and one - and
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
        # The ``counter``-th name cut to ``room``. Only the **document part**
        # is cut, from its end (decision 131): the identifier the copy is
        # found by, the period that says which year, the numbered suffix
        # that keeps a series one series and the extension a program opens
        # it by are never cut. ``None`` for ``room`` is no limit: the
        # canonical name, exactly as it was before there was a room.
        candidate = None
        for keep in range(len(document), -1, -1):
            cut = document if keep == len(document) else document[:keep].rstrip(". -")
            name = _named(_stem_of(identifier, cut, period), counter, suffix)
            if room is None or len(name) <= room:
                candidate = name
                break
        if candidate is None:
            shortest = _named(_stem_of(identifier, "", period), counter, suffix)
            limit = limit_for(extension)
            # Reached only when a room was measured: with ``None`` the first name is kept.
            raise NoRoom(limit - cast(int, room) + len(shortest), limit, extension)
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
#: The same, when the request that accepted the document is in another
#: return than the one the person is looking at: another of this
#: household's returns, where the document parks in the home return
#: (decision 131's review, deviation 5), or the return a hand-over files
#: into (decision 204) - so "this request" would name a list the person is
#: not looking at.
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
#: A review copy of a program is never named (decision 190's review, M1):
#: nobody here opens a program, so the one function that names a review
#: copy refuses one - whatever road asked for it, and whatever its row
#: says it was when it was recorded.
REVIEW_OF_A_PROGRAM = ("no review copy of {name} was made: it is a program, not a document, and "
                       "nobody here opens it")
#: A review copy that could not be made for any other reason (a disk that
#: refused, a copy that did not come out as the original).
REVIEW_COPY_FAILED = "no review copy of {name} could be made ({problem})"
#: A review copy of a workbook fitted to Windows's 260 because a reader's
#: shorter limit left no room: it exists, and a spreadsheet program may not
#: open it where it is (decision 131's review, deviation 4).
REVIEW_COPY_PAST_READER = ("the review copy's path is longer than a spreadsheet program may open; "
                           "open it from a shorter folder")
#: The warning, when some request cannot receive at all.
ROOM_PARKS = ("{count} request(s) have no room for a working copy under this root; a document for "
              "them parks for a person until the clients root is shorter")


def _kind_of(extension: str) -> str:
    """How a sentence names a kind of copy: ``.xlsx``, or ``working``."""
    extension = extension.lower().lstrip(".")
    return f".{extension}" if extension else "working"


#: The tracker's own errors a filing meets: sentences the firm wrote about
#: the firm's own files, said whole on a row as the app says them, where
#: anything else is named by its class (decision 190, the review's S3).
FIRM_WRITTEN = (FilingError, ManifestError, store.StoreError, ledger.LedgerError, EngagementLockedError)


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
    is ``need - limit``. ``limit`` is Windows's own (``layout.path_limit``).

    Where long paths are off, ``floor`` also holds the review folder as
    Windows measures a folder it makes (``layout.folder_need``): the pass
    makes that folder, and one Windows will not make is a return with no
    room for a review copy, said with the room's sentence rather than
    ``WinError 206`` (pilot decision P29). ``need`` stays the rows' own
    figure, so the editor's save still measures only the rows it changes.
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
    root = room_root(engagement_dir)
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
        least = max(least, measured_length(prepared / shortest_name_for(item, longest), root))
        parked = False
        for extension in extensions:
            limit = limit_for(extension)
            short = max(short, measured_length(
                prepared / prepared_name_for(item, extension, set()), root) - limit)
            parked = parked or measured_length(
                prepared / shortest_name_for(item, extension), root) > limit
        parks += parked
    # The floor at the longest extension the list allows; a list with no
    # active row still parks everything, at the defaults' longest.
    longest_of_all = longest_of_all or max(DEFAULT_EXTENSIONS, key=len)
    review = prepared / REVIEW_DIR_NAME / numbered("x", _ROOM_COUNTER, f".{longest_of_all}")
    return Room(need=deepest_path_length(engagement_dir, canonical), least=least,
                floor=max(measured_length(review, root), folder_need(review.parent, root)),
                parks=parks,
                short=max(0, short), limit=path_limit())


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

    Creation, the household rollover and the editor's save all refuse
    through this one (decisions 125, 126 and 131). It lives here rather
    than in ``tracker.api`` because a rollover at layer 3 cannot reach the
    API at layer 5 - and because the file it measures is the one this
    module writes.

    Where long paths are off the review folder is measured too, as Windows
    measures a folder it makes (``layout.folder_need``): the scaffold makes
    it at creation, and a return whose review folder Windows will not make
    is refused here with this sentence, not by the scaffold's
    ``WinError 206`` (pilot decision P29). Elsewhere that adds nothing.
    """
    limit = path_limit()
    need = max(room_for(engagement_dir, items).need,
               folder_need(Path(engagement_dir) / PREPARED_DIR_NAME / REVIEW_DIR_NAME,
                           room_root(engagement_dir)))
    if need > limit:
        raise ManifestError(PATH_TOO_LONG.format(
            folder=engagement_dir, length=need, limit=limit))


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


#: What a copy with no fingerprint to prove it against is refused with
#: (decision 187). Every copy is of bytes this system has already recorded,
#: so a copy that names none was not written by it, and one that is copied
#: unproved could be anything the line pointed at.
COPY_UNPROVED = ("{source} would be copied to {target} with no fingerprint to prove the copy "
                 "against; nothing was copied. A person checks the record")


#: What a copy whose source is there but cannot be read just now is refused
#: with before anything is recorded (decision 187's review, S6): the
#: original stays where it is, and nothing is copied unproved.
COPY_UNREAD = ("{source} could not be read just now (still syncing, or held by another "
               "program), so no copy was made")


class CopyMismatchError(FilingError):
    """A copy was made and the target did not hold the original's bytes."""


def _copy_whole(
    source: Path, target: Path, *, root: Path, expect: str = "",
    cache: ContentCache | None = None,
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
    loud elsewhere - and, since decision 187, its caller fingerprints the
    source first, because ``expect`` is never blank here: a copy with
    nothing to prove it against is refused (:data:`COPY_UNPROVED`) before a
    byte is read.

    The temp's name is cut to fit Windows's limit where the target sits
    near it (``limit``): the target was named to fit decision 131's room,
    and its temp must not be what refuses the copy. On a Mac the limit is
    taken in its own characters (``layout.local_limit`` under ``root``, the
    clients root) so the temp is cut by the Windows measure too (SPEC-mac
    R9); ``root`` is required, so no caller measures the temp by the Mac's
    own longer path without saying so.

    ``cache`` is the pass's, where the caller has one: the copy keeps the
    modification time and the rename keeps the size, so the digest proved
    on the temp is remembered for ``target`` and the proof costs one read,
    once.
    """
    if not expect:
        raise FilingError(COPY_UNPROVED.format(
            source=recorded_name(source.name), target=recorded_name(target.name)))
    mark = target.parent.name == REVIEW_DIR_NAME and _may_carry_code(source)

    def prove(temp: Path) -> None:
        digest = _digest_or_none(temp)
        if digest != expect:
            raise CopyMismatchError(COPY_MISMATCH.format(
                source=recorded_name(source.name), target=recorded_name(target.name),
                expected=expect[:_DIGEST_SHOWN],
                found=(digest or "")[:_DIGEST_SHOWN] or "nothing",
            ))
        if mark:
            # Marked on the temp, before the swap, so the name never holds
            # an unmarked copy: a mark refused is a copy not made (fail
            # closed), and the drop is a "could not be filed" row the pass
            # report names (decision 190).
            _mark_for_review(temp, name=target.name)

    copy_atomically(source, target, prove=prove,
                    limit=local_limit(target, root))
    if cache is not None:
        cache.remember_digest(target, expect)


#: What a review copy that could not be marked for Protected View says: it
#: was not made (decision 190).
MARK_REFUSED = ("no review copy of {name} was made: it can carry macros, and it could not be "
                "marked as from the internet so that Office opens it in Protected View ({problem})")


#: What the person does with a drop whose review copy was refused its mark
#: - the tail of its "could not be filed" row, in place of "file it by
#: hand", which would send them to the unmarked original (decision 190's
#: re-check, N-N1). No pass makes the copy later: the row keeps none.
MARK_REFUSED_STEP = ("never open the original; ask the client for it as a PDF, and set this row "
                     "aside in the app")


class MarkRefusedError(FilingError):
    """A review copy that must be marked for Protected View could not be."""


def _may_carry_code(source: Path) -> bool:
    """Whether the firm's review copy of ``source`` is marked as from the
    internet (decision 190): an Office file that can carry macros, and an
    email or a zip - what it holds is not known until a person opens it,
    and Windows carries the mark to whatever is taken out of it. Asked of
    the recorded name as well as the raw one, because the copy is named by
    the recorded one: ``book.xlsm<U+200B>`` is copied as ``book.xlsm``."""
    return (bears_macros(source) or containers.is_container(source.name)
            or containers.is_container(recorded_name(source.name, fallback="")))


def _here(path: Path) -> bool:
    """The file is on this machine: there, and not a cloud placeholder still syncing.

    ``is_file()`` is tested first and short-circuits, so ``is_cloud_placeholder``
    is never called on a path that is not a file - the same calls, in the same
    order, as each site made when it wrote the pair out. ``not _here(x)`` is the
    refusal's test: absent, or present but still syncing.
    """
    return path.is_file() and not is_cloud_placeholder(path)


def _shown(location: str) -> str:
    """A client's path or name as a sentence quotes it: with the characters
    :func:`~tracker.layout.recorded_name` drops dropped (decision 190's
    review, S4), so no invisible or control character reaches a row's
    reason through a quoted location. The row's ``pbc_location`` keeps the
    raw path, which is what finds the file; ``""`` stays ``""``."""
    return recorded_name(location, fallback="") if location else ""


def _mark_for_review(path: Path, *, name: str) -> None:
    """Mark ``path`` as from the internet, or raise :class:`MarkRefusedError`
    naming the review copy (``name``) that was therefore not put there -
    **the one marking path** (decision 190): a copy made into the review
    folder is marked on its temp (:func:`_copy_whole`), and a working copy
    moved into it is marked before the rename
    (:func:`tracker.intents._do_op`), so no copy lands in review unmarked,
    made or moved, and a mark refused is a copy that never got there (fail
    closed)."""
    try:
        mark_from_internet(path)
    except OSError as exc:
        errors.keep("filer: marking a review copy", exc, name=name)
        raise MarkRefusedError(MARK_REFUSED.format(
            name=name, problem=errors.error_class(exc))) from exc


def _digest_or_none(path: Path) -> str | None:
    """The file's bytes, or None where they could not be read."""
    try:
        return sha256_of(path)
    except OSError:
        return None


#: What a move refuses when the folder it would take a file out of is now
#: reached through a link (decision 137, L2) - and, since decision 187, what
#: any step of an intent refuses when either of its ends is.
MOVE_THROUGH_A_LINK = ("{name} is now reached through a link (a junction or a shortcut folder) "
                       "below {within}; nothing was moved, copied or removed")


class MovedThroughALinkError(OSError):
    """An end of a step is reached through a link now: nothing moved,
    copied or removed.

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
    if is_link(source) or through_a_link(source.parent, within):
        raise MovedThroughALinkError(MOVE_THROUGH_A_LINK.format(name=source.name, within=within))
    os.rename(source, target)


#: What a file name's suffix must look like to be kept whole when a review
#: copy's name is cut: a dot and a short run of letters and digits.
_AN_EXTENSION = re.compile(r"\.[A-Za-z0-9]{1,10}")


def _room_in(folder: Path, extension: str, root: Path) -> int:
    """How many characters a working copy's file name may take in ``folder``:
    the limit that applies to its ``extension`` less the folder as room
    measures it (``layout.measured_length`` under ``root``, the clients
    root) and one separator (decision 131; SPEC-mac R9). The one spelling of
    that arithmetic, so no writer counts the folder by ``len(str(...))``."""
    return limit_for(extension) - measured_length(folder, root) - 1


def _unique_path(
    folder: Path, name: str, *, room: int | None = None, spare: int = 0,
    recorded: Mapping[Path, str] | None = None, digest: str | Callable[[], str | None] = "",
    reuse: bool = False, claimed: set[Path] | None = None, root: Path | None = None,
) -> Path:
    """A free path in ``folder`` for ``name``, never overwriting anything -
    **the one numbering function** (decision 147): an original out of the
    inbox, a person's hand-over into another household (the only move
    across households since decision 204), a review copy and what is taken out of an email or a
    zip (:func:`_take_out`) are all named here.

    ``room`` is how many characters the file name may take (decision 131):
    the stem is cut from its end to fit, keeping the extension and the
    numbered suffix, down to one character; below that, :class:`NoRoom`
    with :data:`REVIEW_NO_ROOM` - every caller that passes a room is naming
    a copy. ``None`` is no limit. Only ever a copy's name - an original is
    moved under its own name, uncut, always. ``spare`` is room kept beside
    the name for the temporary name an atomic write passes through; it is
    taken off ``room`` and counted in what :class:`NoRoom` reports. The
    figures it reports are counted as room is (``layout.measured_length``
    under ``root``, the clients root, which a caller that passes a ``room``
    passes too), so a Mac's refusal quotes Windows's numbers.

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
    will still write to, with none (:func:`_taken_in_the_year`). A client who deletes ``W2.pdf``
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
    if room is not None and root is None:
        raise TypeError("a room is counted from the clients root; pass root with it")
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
        fitted = _named(stem, counter, suffix)
        if fits is not None and len(fitted) > fits:
            cuts = (stem[:keep].rstrip(". ") for keep in range(len(stem) - 1, 0, -1))
            cut_to_fit = next((_named(cut, counter, suffix) for cut in cuts
                               if cut and len(_named(cut, counter, suffix)) <= fits), None)
            if cut_to_fit is None:
                # ``fits`` is set only with a room, and a room only with a root (refused above otherwise).
                length = measured_length(folder / _named(stem[:1], counter, suffix), cast(Path, root)) + spare
                limit = measured_length(folder, cast(Path, root)) + 1 + cast(int, room)
                raise NoRoom(length, limit, suffix, sentence=REVIEW_NO_ROOM.format(
                    name=name, length=length, limit=limit, ext=_kind_of(suffix)))
            fitted = cut_to_fit
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


def _review_copy_path(review_dir: Path, name: str, root: Path) -> tuple[Path, str]:
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

    A program is never named here (:data:`REVIEW_OF_A_PROGRAM`, a
    :class:`FilingError`): asked of the recorded name, which an invisible
    character after the suffix cannot hide it from (decision 190's review,
    M1), whatever road asked for the copy.
    """
    # The copy is the firm's, so its name is the recorded one: a direction
    # override never dresses a program as a PDF in the review folder, and
    # a row recorded before decision 190 gets the same name (decision 190).
    name = recorded_name(name)
    if is_program(name):
        raise FilingError(REVIEW_OF_A_PROGRAM.format(name=name))
    folder = measured_length(review_dir, root) + 1
    limit = limit_for(extension_of(Path(name)))
    try:
        return _unique_path(review_dir, name, room=limit - folder, root=root), ""
    except NoRoom:
        if limit >= path_limit():
            raise
    return (_unique_path(review_dir, name, room=path_limit() - folder, root=root),
            REVIEW_COPY_PAST_READER)


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


def _year_on_record(engagement_dir: Path, held: Mapping[Path, list[IndexEntry]]) -> dict[Path, str]:
    """:func:`_on_record` for every return of ``engagement_dir``'s
    household-year: the rows in ``held`` for the returns the caller holds
    them for, the record's own for the rest - so a return the caller does
    not hold, one left out of the pass as inactive or one in a household
    the caller is not sorting, still counts. For every name a row could
    hold: the inbox move and what is taken out of a zip
    (:func:`_taken_in_the_year`) and a person's hand-over (decision 132),
    which since decision 204 is the only filing that moves an original
    across households. Read only; no lock is taken, and a
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
            errors.keep("filer", exc, name=folder.name)
            log.warning("Could not read %s's rows (%s)", folder.name, errors.error_class(exc))
    return _on_record(pairs)


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


#: What a sweep says when some leftover temps stay (decision 193): a count,
#: never a name.
TEMPS_NOT_SWEPT = ("{n} leftover temporary file(s) could not be swept this pass; "
                   "the next pass tries again")


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


def _holds_the_firms_readme_text(path: Path) -> bool:
    """Whether a README temp in the client's inbox holds nothing but the
    firm's text, so that taking it takes nothing of the client's.

    Either it reads as the firm's README by the README's own test
    (:func:`tracker.scaffold.whose_readme`), or its bytes are a start of
    the firm's README text - empty, or cut inside the first line by a kill
    before the rest reached the disk (the review's S5). Every README the
    firm writes opens with :data:`tracker.scaffold.README_FIRST_LINE`, so a
    file no longer than that line is a start of the current text exactly
    when it is a start of that line, and one longer is the README's own
    test's to judge; the text need not be rebuilt to ask. Such a file,
    left, sat in the client's shared inbox for good and was counted every
    pass as a file still arriving. Anything else is not the firm's to
    delete. A file that cannot be read now is left, and asked again next
    pass."""
    first = README_FIRST_LINE.encode("ascii")
    try:
        if path.stat().st_size <= len(first):
            with path.open("rb") as handle:
                return first.startswith(handle.read(len(first) + 1))
    except OSError:
        return False
    return whose_readme(path) == README_FIRMS


def _remove_a_stranded_temp(path: Path, missed: list[Path] | None = None) -> bool:
    """Take one stranded temp away; False, with a log line, where Windows
    refuses - and then it is counted in ``missed``. A temp ``copy2``
    carried a read-only attribute onto before the kill is made writable
    first - it is the copy, never an original."""
    try:
        try:
            path.unlink()
        except PermissionError:
            make_writable(path)
            path.unlink()
    except FileNotFoundError:
        return False
    except OSError as exc:
        errors.keep("filer", exc, name=path.name)
        log.warning("A temporary file a killed write left could not be removed (%s); "
                    "the next pass tries again", errors.error_class(exc))
        if missed is not None:
            missed.append(path)
        return False
    return True


def sweep_stranded_temps(household_dir: Path | str, returns: Sequence[Path], *,
                         started: float, said: list[str] | None = None) -> list[Path]:
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
      every README write holds;
    - in the inbox, it also holds the firm's text
      (:func:`_holds_the_firms_readme_text`): it reads as the firm's README
      by the README's own test, or it is empty or a start of the README's
      first line - the temp a kill left before the firm's first bytes were
      all on the disk. The inbox is the client's, and a client file can
      carry any name, that shape included; one that holds anything else is
      left where it is and, ending in ``.tmp``, counted in the report with
      the files still arriving (decision 190, revising 179's accepted
      residual; the review's S5).

    Nothing in the client's year folders is ever looked at: the originals
    rest there, and nothing the tracker writes goes through a temp there.
    A temp that cannot be removed now is a log line and waits for the next
    pass, and - with a return whose rows could not be read - is counted in
    ``said`` (:data:`TEMPS_NOT_SWEPT`, decision 193), never named. **Never raises**: a sweep that failed the household would be a
    leftover jamming the pass it exists to protect.
    """
    household_dir = Path(household_dir)
    taken: list[Path] = []
    missed: list[Path] = []
    unread: set[Path] = set()
    try:
        # Every path any row names, in any of these returns, compared as
        # Windows compares them. A parked working copy keeps the client's own
        # name, and an attachment rests under _Opened under its own: either
        # may happen to have the temp shape, and a row naming it makes it a
        # document, never a leftover (decision 155's review).
        named: set[str] = set()
        swept: list[Path] = []
        for folder in map(Path, returns):
            try:
                rows = read_index(folder)
            except Exception as exc:
                errors.keep("filer: the temporary-file sweep", exc, name=folder.name)
                log.warning("The rows of %s could not be read (%s); neither it nor its "
                            "household's _Opened folder is swept this pass",
                            folder.name, errors.error_class(exc))
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
            if _a_stranded_temp_to_take(path) and _remove_a_stranded_temp(path, missed):
                taken.append(path)
        if returns:
            lock = _readme_lock(household_dir)
            if lock is None:
                log.warning("The README of %s is being written by another run; its "
                            "leftover temps are swept on a later pass", household_dir.name)
            else:
                try:
                    first = Path(returns[0])
                    for path in stranded_temps(inbox_of(first), before=started,
                                               target=README_NAME):
                        # A removal in the client's inbox goes through the one
                        # door into the client tree (decision 188).
                        door.client_write(root_of(first), household_name_of(first), path)
                        if (_a_stranded_temp_to_take(path)
                                and _holds_the_firms_readme_text(path)
                                and _remove_a_stranded_temp(path, missed)):
                            taken.append(path)
                finally:
                    release_lock(lock)
    except Exception as exc:
        errors.keep("filer: the temporary-file sweep", exc, name=household_dir.name)
        log.warning("The sweep of %s's leftover temporary files stopped (%s); carrying on",
                    household_dir.name, errors.error_class(exc))
    if said is not None and (missed or unread):
        # A count - the temps that stayed, and a return whose rows could not
        # be read counted as one - never a name (decision 193).
        said.append(TEMPS_NOT_SWEPT.format(n=len(missed) + len(unread)))
    for path in taken:
        log.info("Removed %s, a temporary file a killed write left", path.name)
    return taken
