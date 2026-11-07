"""Walk the household's inbox, and say what in it, or in the client's folder
for the year, cannot be sorted or tied to its row.

Every pass reads the household's one inbox and the client's folder for the
year (decision 125) before it decides anything, and this is that reading,
in three parts, each upholding the decision rows it names:

- **The walk** (decisions 147, 179 and 190). :func:`iter_drops` lists the
  drops in the inbox's own order (:func:`_inbox_order`: the top level
  first, then each subfolder, so the file the client put at the top keeps
  its name), leaving out the firm's README by
  :func:`tracker.scaffold.whose_readme` and handing back one it cannot
  tell just now for the pass to name (:data:`README_UNREAD`).
  :func:`_subfolder_of` is the subfolder a drop's row keeps, by the store's
  admission rule; :func:`_storable` refuses only a name the journal cannot
  hold; and :func:`unrecorded_in_pbc` finds what the client put straight
  into the year's folder, against the union of every return's rows.
- **What cannot be sorted is said, never a silence** (decisions 133 and
  190). :func:`unreachable_drops` (a name the machine cannot handle),
  :func:`unlistable_folders` (a folder the run cannot list),
  :func:`unfinished_drops` (a transfer still in progress) and
  :func:`ignored_in_inbox` (how many files are left alone by name - a
  count, never the names) are what the pass reports; the reminder holds
  its letter while any of the first three, or :func:`iter_drops`, names
  anything.
- **An original that is no longer what its row says** (decisions 65, 132,
  143 and 157). :func:`replaced_in_pbc` finds a recorded original whose
  bytes are not the row's (:data:`REPLACED_IN_PBC`);
  :func:`_missing_positions` finds the rows whose original is gone, by
  :func:`_absent`'s rule that only the filesystem's "no such file" is
  gone; :func:`_follow_moved_originals` points such a row at where its
  bytes now are (:data:`MOVED_IN_PBC`, :data:`MOVED_FROM_IN_PBC`) or hands
  it back to be said (:data:`MISSING_IN_PBC`); and
  :func:`_record_missing_digests` ties a row recorded without its bytes to
  them only while its working copy and its original agree
  (:data:`UNTIED_IN_PBC`, :func:`_copy_taken_by_a_later_row`).
  :data:`LEFT_FOR_ANOTHER_RETURN` is what the pass says of an original
  another return's unfinished filing names.

**Why it is its own module** (SPEC-architecture-p4 P4.7, P333; the
architecture audit's A-1, step 4). This code sat in the filer, and none of
it decides where a document goes: it reads the two folders a client can
see and the rows that name what is in them, and answers with paths, rows
and sentences, which the household pass then acts on and says. The
reminder asks four of the walks too, to hold a letter while the client's
drop folder still holds something unsorted (decision 133), and it reaches
them here without reaching the sorter. Nothing here moves, copies, removes
or records a file, and nothing here reads a name the filer defines. The
one place it reads the firm's side is :func:`_record_missing_digests`,
which compares a row's working copy where the row records it - a name in
Prepared itself or the review folder since decision 168, never a folder
per request - with the row's original.

**Why it sits at layer 3.** It reads :mod:`tracker.copies` (layer 2:
:func:`tracker.copies._on_record`, the places the household-year's rows
name, and :func:`tracker.copies._here`, whether a file is on this
machine), the index, the record types, the
scaffold's README names and the validators (layer 1), and the layout, the
door's link check and the disk's link test (layer 0). It may import
nothing above layer 2 and nothing of the filer, at load time or at call
time: the filer imports it, and the reminder asks it at call time. Layer 2
would pass the layer test too; layer 3 keeps it beside the filer and the
reminder it serves, and keeps layer 2 to what a reading, a routing or a
copy needs (SPEC-architecture-p4 section 2.1).

**Every reader asks this module.** The filer imports back from here only
what its own remaining code reads, and offers none of it on; the reminder
imports its four walks from here. A stand-in follows the name's readers
(the audit's A-4): one for a name this module reads as a global is set on
this module, and where the filer reads it too, on both - so
``is_cloud_placeholder``, ``sha256_of`` and ``locate`` are set here beside
the filer, and ``iter_drops``' stays on the filer, whose household pass is
its only caller there.

**One private name of the index crosses into it**: the index's
``_before_the_moved_sentence``, which :func:`_follow_moved_originals` asks
when a row follows its original, as the filer asks it when an original
comes home (P319's one exception; ``tests/test_index.py`` pins the
crossing over the filer's family).

**Why it logs as ``tracker.filer``** (SPEC-architecture-p4 section 2.1).
The run log and the error log print each line's logger name, so a name of
this module's own would change the lines a person and the office read. It
is the same logger object as the filer's, so no handler and no test sees a
difference.

The comments and docstrings below came with the code, word for word. Where
one names the pass, the filer or a function of the filer's, that is the
caller it describes; the code it describes is here.
"""

from __future__ import annotations

import logging
import os
from collections.abc import Sequence
from dataclasses import replace
from pathlib import Path, PurePosixPath

from tracker.copies import _here, _on_record
from tracker.door import through_a_link
from tracker.fsio import is_link

# The index's words and its readers live in tracker/index.py (P319). One
# private name crosses here, as it does into the filer:
# _before_the_moved_sentence, which following a moved original asks when it
# puts the row's sentence before any moved sentence.
from tracker.index import _before_the_moved_sentence, marked_missing
from tracker.layout import locate, location_of, parts_below, recorded_subfolder_part
from tracker.records import IndexEntry
from tracker.scaffold import README_CLIENTS, README_NAME, README_UNKNOWN, whose_readme
from tracker.validators import (
    UNFINISHED_SUFFIXES,
    is_cloud_placeholder,
    is_ignored,
    is_sync_staging,
    iter_candidate_files,
    sha256_of,
)

# The filer's logger, by its name (SPEC-architecture-p4 section 2.1): the run
# log and the error log print each line's logger name, so a name of this
# module's own would change the lines a person and the office read. It is the
# same logger object, so no handler and no test sees a difference.
log = logging.getLogger("tracker.filer")


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
        if not path.is_file() or is_ignored(path) or through_a_link(path, inbox) or not _storable(path):
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
    below = PurePosixPath(*(parts_below(inbox, path) or (path.name,)))
    return tuple(part.casefold() for part in below.parent.parts), below.name.casefold(), below.as_posix()


def _subfolder_of(drop: Path, inbox: Path) -> str:
    """The client's subfolder a drop sits in, below the inbox, the way the
    client sees it in Explorer (``Bank statements\\2025``); ``""`` for a
    drop at the top of the inbox (decision 147, ruling 4)."""
    # As the record keeps it: no invisible or control character and no
    # character Windows keeps out of a folder name (decision 190), each part
    # below the inbox by the layout's one test (decision 188) - the rule the
    # store's admission applies, so the two cannot disagree.
    return "\\".join(recorded_subfolder_part(part) for part in parts_below(inbox, drop.parent) or ())


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


def ignored_in_inbox(inbox: Path) -> int:
    """How many files in the inbox the sort leaves alone by their name as
    system or temporary files (:func:`tracker.validators.is_ignored`) and
    that :func:`unfinished_drops` does not already name: ``desktop.ini``
    and its kin, an Office lock file (``~$...``), anything under a sync
    client's staging folder (decision 190).

    A count, never names: the names are what a client's machine or sync
    client made, and a list of them would put every lock file of every
    household on the practice page. A count is enough for a person to see
    that a file they expected is not being sorted - a client's own
    ``~$W2.pdf`` is left alone like a lock file - and go and look."""
    if not inbox.is_dir():
        return 0
    unfinished = set(unfinished_drops(inbox))
    return sum(1 for path in inbox.rglob("*")
               if path.is_file() and is_ignored(path) and path not in unfinished)


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
        and not through_a_link(path, originals_dir) and _storable(path)
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
        if through_a_link(path, originals_dir):
            continue
        row = by_path.get(path)
        if row is None:
            continue
        if is_cloud_placeholder(path):
            continue
        try:
            if round(path.stat().st_size / 1024, 1) == row.size_kb and sha256_of(path) == row.digest:
                continue
        except OSError:
            continue                 # unreadable now; the next run looks again
        replaced.append((path, row))
    return replaced


#: The sentence a recorded original that has left the year's folder gets. The
#: client can see that folder and Explorer offers Delete, Rename and drag:
#: every other disagreement between the index and the disk is said every
#: pass, and this one was said by nothing at all while the row went on
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
    position: int | None
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


#: What a pass says of the README in a household's inbox that could not be
#: opened just now (decision 179): it is neither sorted nor written over,
#: and it waits where it is, the way a file held open does.
README_UNREAD = ("the README in {household}'s folder could not be read just now; "
                 "it was left where it is and the next pass looks again")
#: What a pass says of an original in the household's year folder that no
#: row of its own names and that another return's unfinished filing names
#: as the source of its move (decision 132, rulings R-1 and R-3). The file
#: is left where it is - never re-sorted, parked or recorded here - and
#: said on the first own return's warnings every pass it happens, so an
#: intent that never finishes is never an original nobody mentions.
LEFT_FOR_ANOTHER_RETURN = ("{name} is left where it is: another return's unfinished filing "
                           "names it, and that return's next pass finishes it")
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
        if not _here(copy):
            continue
        if not _here(original):
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
