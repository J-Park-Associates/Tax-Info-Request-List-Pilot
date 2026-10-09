"""The one way a file is replaced whole or not at all, and a folder is made.

The tracker writes a handful of small files of its own - the settings file
beside the app, the Task Scheduler XML, the pages a person opens - and
every one of them is read by somebody who has to be able to trust it. A
write that lands half way is worse than a write that never happened: the
reader has no way to tell the two apart, and a scheduled job that was
killed mid-write would leave a file that parses into a lie.

So there is one way to do it, and it is here:

- :data:`TEMP_SUFFIX` - what the temp file ends in. The validators and
  the drop walk ignore that suffix, so a temp a crashed run stranded is
  never read as a client's document.
- :func:`temp_path_for` - a temp name beside the target that no other
  writer can be using, carrying this process id and a random tag.
  :data:`TEMP_NAME` is that shape, named once, and :func:`temp_owner`
  reads a name against it.
- :func:`atomic_replacement` - the context manager: write to the temp,
  ``os.replace`` it over the target when the block ends cleanly, and
  flush the folder where the platform allows.
- :func:`write_text_atomically` / :func:`write_json_atomically` /
  :func:`write_bytes_atomically` / :func:`copy_atomically` - the writers
  over it, each flushing its bytes to the disk before the swap, which is
  all most callers want.
- :func:`stranded_temps` - the temps of that shape a killed write left in
  a folder (decision 155), for the module that owns the folder to remove,
  walked never through a link (:func:`is_link`, the package's one test of
  a symlink or a junction).

- :func:`append_rotating` - the one file the tracker *appends* to rather
  than replaces (the run log, decision 186): an entry is added whole, and
  the file is turned over to ``.1``, ``.2``, ... before it would pass its
  size, so it never grows for ever.
- :func:`make_new_folders` - the one way a folder the tracker is about to
  fill is made (decision 137): every missing level is made by a ``mkdir``
  that would refuse an existing one, and the levels this call made are
  handed back, so a failure afterwards removes those and nothing else. A
  folder that was already there - a person's own, an old return's - is
  never on that list and never removed.

**Every file the tracker writes goes through here, and is whole or not
there** (decision 155). A write killed half way - a power cut, Windows
Update restarting the machine, Task Scheduler ending a pass at its limit -
leaves the temp behind and the target as it was, never half a file under
the proper name. Until decision 155 that was not true of a working copy:
``shutil.copy2`` wrote straight onto the final name, a copy the power cut
in half kept it, and a truncated CSV still passes the rules, so it was
counted. Nor of the weekly draft, whose torn file then read as a person's
edit for good; and the text writer swapped before it flushed, so NTFS,
which journals the rename and not the data, could leave the settings file
empty after a power cut. A stranded temp is the price of a kill, and
:func:`stranded_temps` finds it again by its exact shape, so the next pass
can take it away.

They lived in :mod:`tracker.manifest` until decision 120, because the
manifest was once the workbook they were written for; they are here now
because how a file is replaced is one fact and it should have one home,
and because a module that borrowed the write should not have to borrow
the request list's schema with it (:mod:`tracker.settings` did, and sat a
layer higher than it needed to for that one import).

**It holds no policy.** Nothing here knows what any of those files are
for, which folder they sit in, whether one may be written at all or who
is allowed to write it. It takes a path and bytes and either replaces the
file or raises; the module that owns the file owns every other question
about it. That is why it imports nothing of the package and sits at the
bottom layer, where anything may reach it.
"""

from __future__ import annotations

import json
import logging
import os
import re
import secrets
import shutil
import stat
import time
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("tracker.fsio")

#: The temp file an atomic save lands in first. Nothing is deferred and
#: nothing is quarantined: a write lands whole or not at all.
TEMP_SUFFIX = ".tmp"

#: The whole shape of a temp name :func:`temp_path_for` makes - the
#: target's own name, the writing process's id, eight lower-case hex digits
#: of a random tag, and :data:`TEMP_SUFFIX` - and nothing else (decision
#: 155). A stranded temp is recognised by this shape and only by it: a file
#: that merely ends in ``.tmp`` is somebody's, and never the tracker's to take.
TEMP_NAME = re.compile(r"(?P<target>.+)\.(?P<pid>[0-9]{1,10})\.(?P<tag>[0-9a-f]{8})"
                       + re.escape(TEMP_SUFFIX))


def temp_path_for(path: Path, *, limit: int | None = None) -> Path:
    """A temp name beside ``path`` that no other writer can be using.

    It carries this process id and a random tag, so two runs writing the
    same file at once (the app saving settings while the scheduling CLI
    does, say) cannot swap each other's half-written temp into place - and
    a temp a crashed run left behind is never mistaken for a live one. It
    still ends in ``TEMP_SUFFIX``: the validators and the drop walk ignore
    that suffix, so a stranded temp is never read as a document. Its shape
    is :data:`TEMP_NAME`.

    ``limit`` is the longest path the caller's platform opens, when the
    caller knows its target may sit near it (a working copy, named to fit
    decision 131's room): the target's name inside the temp's is cut from
    its end, down to one character, so the temp's path fits too. The temp
    is up to 24 characters longer than its target otherwise, and a copy
    whose target fits must not fail on its temp (decision 155).
    """
    tail = f".{os.getpid()}.{secrets.token_hex(4)}{TEMP_SUFFIX}"
    name = path.name
    if limit is not None:
        over = len(str(path.with_name(name + tail))) - limit
        if over > 0:
            name = name[:max(1, len(name) - over)]
    return path.with_name(name + tail)


def temp_owner(name: str, *, target: str | None = None) -> int | None:
    """The process id in a name of :data:`TEMP_NAME`'s exact shape, or
    None for any other name.

    ``target`` narrows it to the temps of one file - a README's, say - and
    is compared exactly, case and all: ``notes.txt.123.0a1b2c3d.tmp`` is
    the temp of ``notes.txt``, ``NOTES.TXT.123.0a1b2c3d.tmp`` is not.
    """
    matched = TEMP_NAME.fullmatch(name)
    if matched is None or (target is not None and matched["target"] != target):
        return None
    return int(matched["pid"])


def _fsync_folder(folder: Path) -> None:
    """Flush a folder's entry for a file just renamed into it, where the
    platform allows.

    POSIX can open a folder and fsync it, which makes the rename itself
    durable. Windows cannot open a folder that way and NTFS journals the
    rename on its own, so there it is not attempted. Never raises: the file
    is already whole under its name, and this only makes that sooner.
    """
    if os.name == "nt":
        return
    try:
        handle = os.open(folder, os.O_RDONLY)
    except OSError:
        return
    try:
        os.fsync(handle)
    except OSError:
        pass
    finally:
        os.close(handle)


def _remove_temp(temp: Path) -> None:
    """Take a temp away, clearing a read-only attribute a copy carried onto
    it first if Windows refuses. The temp is this write's own and nothing
    else's."""
    try:
        temp.unlink(missing_ok=True)
    except PermissionError:
        if not temp.exists():
            raise
        make_writable(temp)
        temp.unlink(missing_ok=True)


@contextmanager
def atomic_replacement(path: Path, *, limit: int | None = None) -> Iterator[Path]:
    """Yield a temp path beside ``path``; swap it in whole when the block ends cleanly.

    Writing beside the file and swapping it in with ``os.replace`` makes an
    update all-or-nothing; the swap is atomic on NTFS and on every POSIX
    filesystem. A crash, a full disk or a killed scheduled task mid-write
    leaves the previous file, never half of the new one. The block flushes
    what it wrote to the disk before it ends - every writer here does - and
    the folder is flushed after the swap where the platform allows. The
    temp is removed whatever happens, except when the process is killed,
    which runs no clean-up at all: :func:`stranded_temps` finds that one
    again. A file another program holds open raises ``PermissionError``
    from the replace, and the caller says so. ``limit`` is
    :func:`temp_path_for`'s.
    """
    temp = temp_path_for(path, limit=limit)
    try:
        yield temp
        os.replace(temp, path)
        _fsync_folder(path.parent)
    finally:
        # The temp's removal must never replace the error that stopped the
        # write: a writer may leave the half-written file open when it
        # raises, Windows then refuses the delete, and a full disk would
        # read as "held by another program".
        try:
            _remove_temp(temp)
        except OSError:
            # Neither its words nor its name (a client's file's, with a
            # pid and a tag) are said here (decision 190): fsio imports
            # nothing, so it cannot hand them to errors.keep, and an OS
            # error's words carry the whole path.
            log.warning("A temporary file could not be removed after its write failed")


def write_text_atomically(
    path: Path, text: str, *, encoding: str = "utf-8", newline: str | None = None
) -> None:
    """Write ``text`` to ``path`` all-or-nothing (see :func:`atomic_replacement`).

    Flushed to the disk before the swap (decision 155): NTFS journals the
    rename and not the data, so a swap made before the bytes were down
    could leave the settings file or a README empty after a power cut.
    """
    with atomic_replacement(path) as temp:
        with temp.open("w", encoding=encoding, newline=newline) as handle:
            handle.write(text)
            handle.flush()
            os.fsync(handle.fileno())


def write_bytes_atomically(path: Path, data: bytes) -> None:
    """Write ``data`` to ``path`` all-or-nothing (see :func:`atomic_replacement`).

    Flushed to the disk before the swap: what is written this way is a
    document taken out of a client's email or zip (decision 143), and a
    power cut must leave either the whole file or none of it.
    """
    with atomic_replacement(path) as temp:
        with temp.open("wb") as handle:
            handle.write(data)
            handle.flush()
            os.fsync(handle.fileno())


def make_writable(path: Path) -> None:
    """Clear the read-only attribute of a file the caller made.

    Only ever the tracker's own file - a copy, a temp - and never an
    original: which file that is, is the caller's to know, and this takes
    one path and does nothing else to it.
    """
    mode = os.stat(path).st_mode
    if not mode & stat.S_IWRITE:
        os.chmod(path, stat.S_IMODE(mode) | stat.S_IWRITE)


def copy_atomically(
    source: Path, target: Path, *, prove: Callable[[Path], None] | None = None,
    limit: int | None = None,
) -> None:
    """Copy ``source`` to ``target`` all-or-nothing, as a writable file.

    ``shutil.copy2`` into the temp - the bytes, and the modification time
    the verdict cache's memo keys on - then the temp is made writable,
    flushed to the disk and swapped in. A copy killed half way leaves its
    temp and no file under ``target``'s name (decision 155).

    **The copy is writable** (decision 155): ``copy2`` carries the source's
    read-only attribute across - a file from a CD, or one Explorer took out
    of a zip - and a read-only working copy then refused its own removal
    and jammed the household. The attribute is cleared on the temp, which
    is the copy; ``source`` is only ever read.

    ``prove`` is handed the temp once its bytes are down, before the swap:
    raising there leaves ``target`` as it was, so a copy that did not come
    out as its source never holds the proper name, not even for a moment.
    ``limit`` is :func:`temp_path_for`'s.
    """
    with atomic_replacement(target, limit=limit) as temp:
        shutil.copy2(source, temp)
        make_writable(temp)
        with temp.open("r+b") as handle:
            os.fsync(handle.fileno())
        if prove is not None:
            prove(temp)


#: The alternate data stream Windows reads a file's origin from, and what
#: it holds for a file from the internet (zone 3). Office opens a file
#: carrying it in Protected View, macros off (decision 190).
ZONE_STREAM = ":Zone.Identifier"
ZONE_FROM_INTERNET = "[ZoneTransfer]\r\nZoneId=3\r\n"


def mark_from_internet(path: Path, *, _opener: Callable | None = None) -> bool:
    """Mark ``path`` as a file from the internet, so Office opens it in
    Protected View: True once marked, False where there is no such mark to
    write (anything but Windows).

    **Fails loudly, never quietly** (decision 190). On Windows an error
    writing the stream - a volume that holds no streams, FAT or a network
    share that drops them - is raised, and the caller does not make the
    copy: an unmarked copy of a macro workbook in the review folder is the
    thing this exists to stop. Read ``os.name`` when called, so a test can
    stand in for Windows with ``_opener``, the one thing it touches."""
    if os.name != "nt":
        return False
    opener = _opener or open
    with opener(str(path) + ZONE_STREAM, "w", encoding="ascii", newline="") as stream:
        stream.write(ZONE_FROM_INTERNET)
    return True


def _born(info: os.stat_result) -> float:
    """When a file came to be, as near as the platform says: the later of
    its modification time and its creation (Windows) or change (POSIX)
    time. ``copy2`` sets a temp's modification time back to its source's,
    so that alone would make a temp made a second ago look years old."""
    created = getattr(info, "st_birthtime", None)
    if created is None:
        created = info.st_ctime
    return max(info.st_mtime, created)


#: The reparse tags that make a name a link to somewhere else: a symbolic
#: link and a junction (a mount point). Spelled here too, so the rule reads
#: the same off Windows, where ``lstat`` carries no tag. A cloud sync
#: client's placeholder is a reparse point too (its tag is the client's own)
#: and is a file of the client's, not a link. The one set of them: the
#: sweep's walk, the drop's walk, the firm view's fingerprint and the
#: after-install step's test-cache job all ask this one question.
LINK_TAGS = frozenset({getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
                       getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)})
_LINK_TAGS = LINK_TAGS      # the name tests/test_filer.py reads it by


def is_link(path: Path | str) -> bool:
    """A symlink, or on Windows a junction (a mount point) - the one test of
    a link the package has.

    Read from ``os.lstat``'s reparse tag, which every Python the tracker
    supports reports: ``DirEntry.is_junction()`` exists only from Python
    3.12, and on 3.11 a junction would read as an ordinary folder. A name
    that cannot be looked at is not a link.
    """
    try:
        info = os.lstat(path)
    except OSError:
        return False
    return stat.S_ISLNK(info.st_mode) or getattr(info, "st_reparse_tag", 0) in LINK_TAGS


def stranded_temps(
    folder: Path, *, before: float, recursive: bool = False, target: str | None = None
) -> list[Path]:
    """The temps a killed write left in ``folder``: files whose names have
    :data:`TEMP_NAME`'s exact shape and that came to be before ``before``
    (a ``time.time()``), sorted.

    **It only finds; it removes nothing.** Which folders may be swept, and
    whether the process a temp names may still be writing it, is the
    owner's to say (``tracker.filer.sweep_stranded_temps``). ``recursive``
    walks the folders below too, never through a link or a junction;
    ``target`` narrows it to one file's temps (:func:`temp_owner`). A
    folder that is not there, or cannot be listed, has none.
    """
    found: list[Path] = []
    pending = [Path(folder)]
    while pending:
        here = pending.pop()
        try:
            with os.scandir(here) as listing:
                entries = list(listing)
        except OSError:
            continue
        for entry in entries:
            if is_link(entry.path):
                continue
            try:
                if entry.is_dir(follow_symlinks=False):
                    if recursive:
                        pending.append(Path(entry.path))
                    continue
                if (entry.is_file(follow_symlinks=False)
                        and temp_owner(entry.name, target=target) is not None
                        and _born(entry.stat(follow_symlinks=False)) < before):
                    found.append(Path(entry.path))
            except OSError:
                continue
    return sorted(found)


def write_json_atomically(path: Path, payload: object) -> None:
    """Write ``payload`` as JSON to ``path`` all-or-nothing; the cache and the settings use this."""
    write_text_atomically(path, json.dumps(payload, indent=2))


#: The file a rotation holds while it turns the log over (decision 186's
#: review, S3): made with O_EXCL beside the log, so only one writer rotates
#: at a time, and removed when it is done.
ROTATION_LOCK_SUFFIX = ".rotating"
#: How old a rotation's lock file may be before it is taken for one a
#: killed writer left behind and removed. A rotation is a handful of
#: renames; a minute is far longer than any takes.
ROTATION_LOCK_STALE_SECONDS = 60


def append_rotating(path: Path, text: str, *, max_bytes: int, keep: int) -> Path:
    """Append ``text`` to ``path``, first rotating it (path -> path.1 -> ... ->
    path.<keep>, the oldest dropped) when the append would take it past
    ``max_bytes``. Opened, written and closed each time, so no process holds it
    between entries. **The entry is never lost**: a rotation that fails at any
    step - a rename another process blocks (PermissionError), a file another
    writer has already moved (FileNotFoundError), any other OSError - is
    abandoned with a warning, the entry is appended anyway, and the rotation
    is tried again at the next append; the file overshoots by at most a few
    entries.

    Two writers append to the run log - the scheduled pass and the app's
    own - and both can cross the size at once (decision 186's review, S3).
    So only one rotates at a time: it holds a lock file made with O_EXCL
    beside the log (:data:`ROTATION_LOCK_SUFFIX`), and, holding it, asks
    the size again before renaming anything. A writer that finds the lock
    held appends and leaves the turning-over to the holder, so no rename is
    ever made from a stale view of the files, and older entries are never
    renamed over. A writer that appends while the holder renames writes
    into whichever file the name then points to - the entry lands in
    ``.1`` rather than the log, but it lands. A lock older than
    :data:`ROTATION_LOCK_STALE_SECONDS` is one a killed writer left, and is
    removed; this pass appends, and the next one rotates.

    Hand-rolled rather than ``logging.handlers.RotatingFileHandler``
    (decision 186): a run log takes one whole entry per pass, not a stream
    of records, and two processes write it - the scheduled pass and the
    app's own - which the standard library documents that handler as not
    supporting; on Windows its rollover fails while the other process holds
    the file, and a handler's failure is printed to a console nobody reads
    and swallowed. The text is written as UTF-8, and a character UTF-8
    cannot hold (a lone surrogate) is written as its escape rather than
    losing the entry. The folder must already be there: making it is the
    owner's question.
    """
    path = Path(path)
    data = text.encode("utf-8", errors="backslashreplace")
    if _too_big_for(path, len(data), max_bytes):
        try:
            _rotate(path, len(data), max_bytes=max_bytes, keep=keep)
        except OSError:
            # No words and no class: this module imports nothing of the
            # package, even at call time, so it cannot reach errors.error_class,
            # and a caught error's words never reach a log line (decision 190).
            log.warning("Could not rotate %s; appending and trying again next time", path)
    with path.open("ab") as handle:
        handle.write(data)
    return path


def _too_big_for(path: Path, adding: int, max_bytes: int) -> bool:
    """Whether ``adding`` more bytes would take ``path`` past ``max_bytes``;
    an empty or missing file never is, so one entry larger than the limit
    is still written whole."""
    try:
        size = path.stat().st_size
    except FileNotFoundError:
        return False
    return bool(size) and size + adding > max_bytes


def _rotate(path: Path, adding: int, *, max_bytes: int, keep: int) -> None:
    """Turn ``path`` over under its rotation lock, if it still needs it once
    the lock is held; do nothing when another writer holds the lock."""
    lock = path.with_name(path.name + ROTATION_LOCK_SUFFIX)
    try:
        os.close(os.open(lock, os.O_CREAT | os.O_EXCL | os.O_WRONLY))
    except FileExistsError:
        try:
            if time.time() - lock.stat().st_mtime > ROTATION_LOCK_STALE_SECONDS:
                lock.unlink()
                log.warning("Removed a stale rotation lock %s; rotating at the next append", lock)
        except FileNotFoundError:
            pass
        return
    try:
        if not _too_big_for(path, adding, max_bytes):
            return                      # another writer turned it over first
        older = [path.with_name(f"{path.name}.{n}") for n in range(1, keep + 1)]
        if not older:
            path.unlink()
            return
        for n in range(len(older) - 1, 0, -1):
            if older[n - 1].exists():
                os.replace(older[n - 1], older[n])
        os.replace(path, older[0])
    finally:
        try:
            lock.unlink()
        except FileNotFoundError:
            pass


def make_new_folders(folder: Path) -> list[Path]:
    """Make ``folder`` and every missing folder above it; return the ones
    this call made, outermost first.

    Each level is made with ``exist_ok=False``, so a level is on the list
    only when this call's own ``mkdir`` created it - never because it was
    found there. That list is the whole of what an undo may remove
    (decision 137): a failed create that removed the folder it *found*
    would take a person's folder, or an old return, with it. ``folder``
    itself existing already raises ``FileExistsError`` and makes nothing;
    anything that fails half way removes what it made before raising.
    """
    folder = Path(folder)
    missing: list[Path] = []
    for level in (folder, *folder.parents):
        if level.exists():
            break
        missing.append(level)
    if not missing:
        raise FileExistsError(f"{folder} is already there")
    made: list[Path] = []
    try:
        for level in reversed(missing):
            level.mkdir(exist_ok=False)
            made.append(level)
    except BaseException:
        for level in reversed(made):
            try:
                level.rmdir()
            except OSError:
                pass
        raise
    return made
