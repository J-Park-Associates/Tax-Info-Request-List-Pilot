"""The firm view's cache: the file, its head and the households' fingerprints
(P120, ``pilot/SPEC-firm-cache.md``).

**Why a cache at all.** ``api firm`` answers Overview and every firm page
with one line per return: 750 returns took 53 s on the office PC, against a
budget of 3 s (SPEC-shell 9.2). Asking each machine question once per reply
(P118) and removing four quadratic loops (P119) brought it to about 8 s, of
which starting Python is one and walking the practice and reading 750
records the rest. Reading a record is the part that cannot be made cheaper
without changing what it proves, so a household that has not changed since
the last reply is not read again: its rows come from here.

**Why a household is the unit, and what "changed" means.** Everything a
return's firm row reads lies in two folders of its household - the private
folder (the household's record, each return's record, index, working
copies, drafts and approvals) and the client folder (the inbox) - or is
derived from them (the store is rebuilt from the journals by their head
digest), or is a fact of the whole reply (the day, the root, the settings,
the program), which this file's head carries. So a household's
:func:`fingerprint` is every entry under those two folders - name, kind,
size and modification time, from one directory listing per folder; no file
is opened and nothing is read from a document - and a household whose
fingerprint is the one kept is a household whose rows are the ones kept.
Equality is compared, never order, so a sync client that sets an older
time still reads as a change. The practice-wide facts - which prior a Roll
Forward retired, which household has two open years - are not kept here as
answers: the API recomputes them every time from the facts kept here.

**Rejected:** one digest for the whole practice (any drop into any inbox
would make the next reply read all 750 households); folder times alone
(Windows changes a folder's time when an entry is added or removed, not
when a file inside is rewritten); a watcher (it misses whatever happens
while it is not running, which is when the scheduled pass writes); the
cache in the client folders (decision 186: nothing derived from a client
sits in a synced tree); ``pickle`` (loading one runs code).

**Where it lives.** :data:`CACHE_FILENAME` in the tracker's data folder
(:func:`tracker.settings.data_home`), beside ``tracker.db``: it holds
household names, return folders and the names of files waiting for a
person, as the store does. It is disposable: missing, damaged, from another
format or program, for another root or another day, it is set aside by
:func:`load` - said on the error log by its class, never its words - and
rebuilt by the next reply.

Layer 0: the standard library, ``settings``, ``fsio`` and ``errors``; the API does the
reading and decides what is kept.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import logging
import os
import stat
import sys
import time
from pathlib import Path

from tracker import errors, settings
from tracker.fsio import write_text_atomically

log = logging.getLogger(__name__)

#: The file's name in the data folder.
CACHE_FILENAME = "firm-view.json"

#: The shape of this file: the head's keys, a household entry's keys and a
#: return's facts. It rises only when that shape changes. A field added to
#: a firm row does not change it - rows are kept as the JSON the API built
#: them as - and any change to the program changes :func:`program_stamp`,
#: so the first reply after an upgrade rebuilds every row with its fields.
FORMAT = 1

#: A household's kind, as the practice walk reads it: a household with its
#: record, one whose record is gone while its returns hold theirs, or a
#: folder at the household position that yields no return at all.
KINDS = frozenset({"household", "record_missing", "none"})

#: The facts kept for each return, and their types. ``shown`` is the firm
#: row, its files and its paths as the API built them, or ``None`` when the
#: return was not shown (a retired prior, an inactive return).
RETURN_FACTS = {"path": str, "household": str, "problem": str, "active": bool,
                "rolled_from": str}

#: How recent an entry's modification time may be and its household still
#: be kept. A file rewritten twice within one tick of the file system's
#: clock, at the same size, would keep one fingerprint (the "racily clean"
#: case ``git`` guards the same way), and a synced drive's clock may be
#: coarser than the disk's; so a household with anything this new - or
#: dated in the future, by a clock ahead of this one - is read fresh and not
#: kept until it has been still for this long.
RACY_SECONDS = 5

#: A link or junction inside a household's folders: the practice walk may
#: follow it where this walk does not look, so such a household is never
#: kept and is read fresh on every reply.
_LINK_TAGS = frozenset({getattr(stat, "IO_REPARSE_TAG_SYMLINK", 0xA000000C),
                        getattr(stat, "IO_REPARSE_TAG_MOUNT_POINT", 0xA0000003)})


def cache_path() -> Path:
    """Where the cache is: the data folder, never a client tree (decision 186)."""
    return settings.data_home() / CACHE_FILENAME


def program_stamp() -> str:
    """Which program built the rows: on the packaged app its executable's
    size and time; from source every ``tracker/*.py`` file's name, size and
    time; and the Python version. Any upgrade or edit changes it."""
    parts: list[str] = [sys.version]
    if getattr(sys, "frozen", False):
        found = [Path(sys.executable)]
    else:
        found = sorted(Path(__file__).resolve().parent.glob("*.py"))
    for one in found:
        size = one.stat()
        parts.append(f"{one.name}\0{size.st_size}\0{size.st_mtime_ns}")
    return hashlib.blake2b("\n".join(parts).encode("utf-8"), digest_size=16).hexdigest()


def head(root: Path | str, today: dt.date) -> dict:
    """What every kept row depends on beyond its household's folders: this
    file's format, the program, the clients root, the data folder, the day
    (a draft's week and a request's stage are the day's) and the settings
    file as it stands. A cache with another head is not used."""
    try:
        said = settings.settings_path().stat()
        spelled = [said.st_size, said.st_mtime_ns]
    except FileNotFoundError:
        spelled = None
    return {"format": FORMAT, "program": program_stamp(), "root": str(root),
            "data_home": str(settings.data_home()), "day": today.isoformat(), "settings": spelled}


def fingerprint(*folders: Path) -> str | None:
    """One digest of every entry under each of ``folders`` - each name, and
    whether it is a folder, its size and its modification time - from one
    ``os.scandir`` listing per folder, in name order. Nothing is opened. A
    folder that is not there is said as absent. ``None`` when a folder
    cannot be listed, holds a link or junction, or holds anything modified
    within :data:`RACY_SECONDS` of now or later: such a household is read
    fresh and never kept."""
    digest = hashlib.blake2b(digest_size=16)
    settled = time.time_ns() - RACY_SECONDS * 1_000_000_000
    for folder in folders:
        digest.update(f"\1{folder}\n".encode("utf-8", "surrogatepass"))
        if not _listed(Path(folder), digest, settled):
            return None
    return digest.hexdigest()


def _listed(folder: Path, digest, settled: int) -> bool:
    try:
        with os.scandir(folder) as found:
            entries = sorted(found, key=lambda entry: entry.name)
    except FileNotFoundError:
        digest.update(b"\2absent\n")
        return True
    except OSError:
        return False
    for entry in entries:
        try:
            about = entry.stat(follow_symlinks=False)
        except OSError:
            return False
        if entry.is_symlink() or getattr(about, "st_reparse_tag", 0) in _LINK_TAGS:
            return False
        if about.st_mtime_ns > settled:
            return False
        is_folder = stat.S_ISDIR(about.st_mode)
        digest.update(f"{entry.name}\0{int(is_folder)}\0{about.st_size}\0{about.st_mtime_ns}\n"
                      .encode("utf-8", "surrogatepass"))
        if is_folder and not _listed(Path(entry.path), digest, settled):
            return False
    return True


def _households_digest(households: dict) -> str:
    """A digest of the kept households, stored with them and checked on
    every load, so a file damaged into other valid JSON is still refused."""
    text = json.dumps(households, sort_keys=True, separators=(",", ":"))
    return hashlib.blake2b(text.encode("utf-8"), digest_size=16).hexdigest()


def load(path: Path, expected: dict) -> dict[str, dict]:
    """The kept households by folder name, when the file at ``path`` is
    whole and its head is ``expected``; otherwise nothing, said on the error
    log by its reason (never a client's words), so the reply reads every
    household and the file is replaced. A missing file is the ordinary
    first reply and is not said."""
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        return {}
    except (OSError, UnicodeDecodeError) as exc:
        log.warning("The firm view's cache could not be read (%s); rebuilding it", errors.error_class(exc))
        return {}
    try:
        kept = json.loads(text)
    except json.JSONDecodeError:
        log.warning("The firm view's cache is not whole JSON; rebuilding it")
        return {}
    if not isinstance(kept, dict) or kept.get("head") != expected:
        # Another day, program, root or format: the ordinary way a cache ends.
        return {}
    households = kept.get("households")
    if not isinstance(households, dict) or kept.get("digest") != _households_digest(households) \
            or not all(isinstance(name, str) and _entry_is_whole(entry) for name, entry in households.items()):
        log.warning("The firm view's cache is damaged; rebuilding it")
        return {}
    return households


def _entry_is_whole(entry: object) -> bool:
    if not isinstance(entry, dict) or set(entry) != {"fingerprint", "kind", "name", "returns"}:
        return False
    if not isinstance(entry["fingerprint"], str) or entry["kind"] not in KINDS \
            or not isinstance(entry["name"], str) or not isinstance(entry["returns"], list):
        return False
    return all(_return_is_whole(one) for one in entry["returns"])


def _return_is_whole(one: object) -> bool:
    if not isinstance(one, dict) or set(one) != {*RETURN_FACTS, "tax_year", "shown"}:
        return False
    if not all(isinstance(one[key], kind) for key, kind in RETURN_FACTS.items()):
        return False
    if one["tax_year"] is not None and (isinstance(one["tax_year"], bool) or not isinstance(one["tax_year"], int)):
        return False
    shown = one["shown"]
    return shown is None or (isinstance(shown, dict) and set(shown) == {"row", "files", "paths"}
                             and isinstance(shown["row"], dict) and isinstance(shown["files"], list)
                             and isinstance(shown["paths"], dict))


def save(path: Path, expected: dict, households: dict[str, dict]) -> None:
    """Keep ``households`` under the head ``expected``, all or nothing
    (``fsio.write_text_atomically``). A file that cannot be written is said
    on the error log by its class and the reply goes on: the cache only
    makes the next reply faster, and two replies racing each write a whole
    file whose every entry is true for its fingerprint."""
    payload = {"head": expected, "digest": _households_digest(households), "households": households}
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomically(path, json.dumps(payload, separators=(",", ":")))
    except OSError as exc:
        log.warning("The firm view's cache could not be written (%s)", errors.error_class(exc))
