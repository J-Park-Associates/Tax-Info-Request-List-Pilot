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
- :func:`atomic_replacement` - the context manager: write to the temp,
  and ``os.replace`` it over the target when the block ends cleanly.
- :func:`write_text_atomically` / :func:`write_json_atomically` - the two
  writers over it, which is all most callers want.

- :func:`make_new_folders` - the one way a folder the tracker is about to
  fill is made (decision 137): every missing level is made by a ``mkdir``
  that would refuse an existing one, and the levels this call made are
  handed back, so a failure afterwards removes those and nothing else. A
  folder that was already there - a person's own, an old return's - is
  never on that list and never removed.

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
import secrets
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

log = logging.getLogger("tracker.fsio")

#: The temp file an atomic save lands in first. Nothing is deferred and
#: nothing is quarantined: a write lands whole or not at all.
TEMP_SUFFIX = ".tmp"


def temp_path_for(path: Path) -> Path:
    """A temp name beside ``path`` that no other writer can be using.

    It carries this process id and a random tag, so two runs writing the
    same file at once (the app saving settings while the scheduling CLI
    does, say) cannot swap each other's half-written temp into place - and
    a temp a crashed run left behind is never mistaken for a live one. It
    still ends in ``TEMP_SUFFIX``: the validators and the drop walk ignore
    that suffix, so a stranded temp is never read as a document.
    """
    return path.with_name(f"{path.name}.{os.getpid()}.{secrets.token_hex(4)}{TEMP_SUFFIX}")


@contextmanager
def atomic_replacement(path: Path) -> Iterator[Path]:
    """Yield a temp path beside ``path``; swap it in whole when the block ends cleanly.

    Writing beside the file and swapping it in with ``os.replace`` makes an
    update all-or-nothing; the swap is atomic on NTFS and on every POSIX
    filesystem. A crash, a full disk or a killed scheduled task mid-write
    leaves the previous file, never half of the new one. The temp is
    removed whatever happens. A file another program holds open raises
    ``PermissionError`` from the replace, and the caller says so.
    """
    temp = temp_path_for(path)
    try:
        yield temp
        os.replace(temp, path)
    finally:
        # The temp's removal must never replace the error that stopped the
        # write: a writer may leave the half-written file open when it
        # raises, Windows then refuses the delete, and a full disk would
        # read as "held by another program".
        try:
            temp.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("Temporary file %s could not be removed (%s)", temp.name, exc)


def write_text_atomically(
    path: Path, text: str, *, encoding: str = "utf-8", newline: str | None = None
) -> None:
    """Write ``text`` to ``path`` all-or-nothing (see :func:`atomic_replacement`)."""
    with atomic_replacement(path) as temp:
        with temp.open("w", encoding=encoding, newline=newline) as handle:
            handle.write(text)


def write_json_atomically(path: Path, payload: object, *, indent: int = 2) -> None:
    """Write ``payload`` as JSON to ``path`` all-or-nothing; the cache and the settings use this."""
    write_text_atomically(path, json.dumps(payload, indent=indent))


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
