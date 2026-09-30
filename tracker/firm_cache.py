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
(:func:`tracker.settings.data_home`), beside the store (``store.STORE_FILENAME``): it holds
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
import threading
import time
from dataclasses import dataclass
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
#: kept until it has been still for this long. The window is measured by
#: this PC's clock: a network share whose clock runs more than this far
#: behind could date a rewrite outside it, which is one more reason the
#: records are judged by their bytes (:class:`Judged`).
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


#: What a household's fingerprint is taken with (P120, and the review's
#: SHOULD-2 and SHOULD-4): which files of each folder are digested by their
#: whole bytes, and which files are left out. The API fills it from the
#: modules that own the names; this module only applies it.
@dataclass(frozen=True)
class Judged:
    #: In the household's private folder, at any depth: the records the
    #: firm view reads (every return's and the household's record, the
    #: reminder drafts). A rewrite that keeps a record's size and time - a
    #: backup restore, a copy that keeps times, a hand edit put back - still
    #: changes its bytes.
    private_whole: frozenset[str] = frozenset()
    #: In the household's client folder, at any depth: the firm's own files
    #: the inbox count opens (its README). A client's documents are never
    #: among them and are never opened.
    client_whole: frozenset[str] = frozenset()
    #: Left out entirely: files the tracker writes from the record and the
    #: firm view never opens (a return's status page, rewritten by every
    #: pass). Leaving one out cannot hide a status: it holds nothing the
    #: record does not.
    left_out: frozenset[str] = frozenset()


#: Every file judged by its size and time, none left out.
NOTHING_JUDGED = Judged()


def fingerprint(private: Path, client: Path | None, judged: Judged = NOTHING_JUDGED) -> str | None:
    """One digest of a household's two folders: every entry's name and
    kind; every file's size and modification time; and the whole bytes of
    the files ``judged`` names. A folder is taken by its name and what it
    holds, never its own time - a folder's time moves when a lock or a
    temporary file comes and goes, and anything added or removed is in the
    listing anyway. ``client`` is ``None`` for a folder whose name no
    client folder can have (the walk makes it a misfit). A folder that is
    not there is said as absent. ``None`` when a folder cannot be listed or
    read, holds a link or junction, or holds a file modified within
    :data:`RACY_SECONDS` of now or later: such a household is read fresh
    and never kept."""
    digest = hashlib.blake2b(digest_size=16)
    settled = time.time_ns() - RACY_SECONDS * 1_000_000_000
    for folder, whole in ((private, judged.private_whole), (client, judged.client_whole)):
        if folder is None:
            digest.update(b"\3none\n")
            continue
        digest.update(f"\1{folder}\n".encode("utf-8", "surrogatepass"))
        if not _listed(Path(folder), digest, settled, whole, judged.left_out):
            return None
    return digest.hexdigest()


#: How many threads list the households' folders at once. Listing a folder
#: waits on the disk, not on Python, so eight listings overlap: on the
#: office PC 750 households took 2.2 s one at a time and 0.7 s eight at a
#: time (sixteen was no faster).
FINGERPRINT_THREADS = 8


def fingerprints(pairs: list[tuple[Path, Path | None]], judged: Judged = NOTHING_JUDGED, *,
                 threads: int = FINGERPRINT_THREADS) -> list[str | None]:
    """:func:`fingerprint` of each ``(private folder, client folder)`` in
    ``pairs``, in order, taken ``threads`` at a time. Each fingerprint is its
    own digest, so the answer is the one a single thread gives; the first
    error any thread met is raised once all have stopped."""
    found: list[str | None] = [None] * len(pairs)
    failures: list[BaseException] = []

    def work(start: int) -> None:
        try:
            for index in range(start, len(pairs), threads):
                found[index] = fingerprint(*pairs[index], judged)
        except BaseException as exc:        # raised below, in the caller's thread
            failures.append(exc)

    workers = [threading.Thread(target=work, args=(start,), daemon=True)
               for start in range(min(threads, len(pairs)))]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    if failures:
        raise failures[0]
    return found


def _listed(folder: Path, digest, settled: int, whole: frozenset[str], left_out: frozenset[str]) -> bool:
    try:
        with os.scandir(folder) as found:
            entries = sorted(found, key=lambda entry: entry.name)
    except FileNotFoundError:
        digest.update(b"\2absent\n")
        return True
    except OSError:
        return False
    for entry in entries:
        if entry.name in left_out:
            continue
        try:
            about = entry.stat(follow_symlinks=False)
        except OSError:
            return False
        if entry.is_symlink() or getattr(about, "st_reparse_tag", 0) in _LINK_TAGS:
            return False
        if stat.S_ISDIR(about.st_mode):
            digest.update(f"{entry.name}\0dir\n".encode("utf-8", "surrogatepass"))
            if not _listed(Path(entry.path), digest, settled, whole, left_out):
                return False
            continue
        if about.st_mtime_ns > settled:
            return False
        digest.update(f"{entry.name}\0{about.st_size}\0{about.st_mtime_ns}\n"
                      .encode("utf-8", "surrogatepass"))
        if entry.name in whole:
            try:
                digest.update(hashlib.blake2b(Path(entry.path).read_bytes(), digest_size=16).digest())
            except OSError:
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


#: Beside the cache: the class of the last surprise the cached path was set
#: aside for, so the error log says each one once when it starts - not on
#: every reply while it lasts (the review's SHOULD-1) - and again whenever
#: it changes. Removed by the first reply the cache answers.
SAID_FILENAME = "firm-view.said"


def first_time_said(path: Path, said: str | None) -> bool:
    """Whether ``said`` - a surprise's class, or ``None`` for a reply the
    cache answered - is not what the note at ``path`` last kept; the note
    then keeps it. A note that cannot be read or written counts as a
    change, so a surprise is never kept quiet because of the note."""
    try:
        before = path.read_text(encoding="utf-8") if path.exists() else None
    except OSError:
        before = ""
    if before == said:
        return False
    try:
        if said is None:
            path.unlink(missing_ok=True)
        else:
            write_text_atomically(path, said)
    except OSError:
        return True
    return True
