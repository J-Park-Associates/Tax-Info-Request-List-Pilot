"""The practice page's kept rows: each return's read counts and parked files,
kept between passes under the record's own token (P227,
``pilot/SPEC-sort-speed.md``).

**Why.** A Sort & Scan runs one household and then draws the practice page
whole, before its final line (decision 203). Drawing is 0.06 s; what the
page cost was reading, for every return the Sort did not run, its request
list, and for every return its index - about 2 s of a 4.4 s Sort at 2,000
returns, to draw rows that are the same as at the last page whenever those
records have not moved.

**What "not moved" means.** The store's :func:`tracker.store.read_token`:
the record's row id, path, journal head, applied seq and digest, and when
the row was built. Every table the page reads is written only by applying
journal lines, which moves the seq, head and digest, or by deleting the
row, which a rebuild's ``built_at`` says - the proof ``store.held_read``
already rests on within one hold. (``built_at`` is to the second, as every
stamp is, and SQLite may give a rebuilt row its old id: a row rebuilt from
the same journal within the second it was first built keeps its token. It
also keeps its rows - derived from the same lines by the same program,
which the head's program stamp pins.) An entry is used only while the record's
token is the one it was read under, so a kept row is exactly what a fresh
read of the store as the walk left it would return (decision 192): **a cache may never make
a status wrong** (P120). A read is kept only when the token read before it
equals the token read after it, so a record another process wrote while it
was read is never kept under the older token. Two things heal only at
the next page, never on this one: the store's tokens are taken once, at the
start of the report, so a record written after that is drawn from its kept
row as it stood then (as a fresh read at that moment would have drawn it);
and a kept line skips the journal-exists check a fresh read makes, so a
journal removed after this pass's walk found it is left to the next page's
walk.

**Rejected** (the SPEC's options): the firm view's rows (``firm-view.json``)
- built for the Overview, not ``summarize``'s counts, so turning one into
the other would be a second place a status is decided, and judged by folder
size and time, weaker than the record's head; the drawn HTML rows - 1% of
the page; writing the page after the final line - it would no longer land
at once, and a page that could not be written could no longer be said; a
store table - a schema step for what a disposable file does.

**Where it lives.** :data:`ROWS_FILENAME` in the tracker's data folder,
beside the firm view's cache: it holds client file names, so never in a
synced tree (decision 186). Its head is the firm cache's
(:func:`tracker.firm_cache.head`: the program stamp, the clients root, the
data folder, the day and the settings file) plus this file's own
:data:`FORMAT`, so every entry is read afresh at least once a day and after
every upgrade. Missing, damaged, foreign, another day's or another
program's: set aside by :func:`load`, said on the error log by its class or
reason, never a client's words. Deleting it is always safe.

Layer 0: the standard library, ``settings``, ``fsio``, ``errors`` and
``firm_cache``'s head. The runner reads the records and asks the store for
the tokens; this module only keeps what it is handed.
"""

from __future__ import annotations

import datetime as dt
import json
import logging
from pathlib import Path

from tracker import errors, firm_cache, settings

log = logging.getLogger(__name__)

#: The file's name in the data folder.
ROWS_FILENAME = "page-rows.json"

#: The shape of this file; it rises only when the shape changes. Any change
#: to the program changes the head's program stamp anyway.
FORMAT = 1

#: A parked row as kept: the index's received, original name, reason and
#: candidates, each text, in index order.
PARKED_FIELDS = 4


def rows_path() -> Path:
    """Where the kept rows are: the data folder, never a client tree."""
    return settings.data_home() / ROWS_FILENAME


def page_head(root: Path | str, today: dt.date) -> dict:
    """What every kept row depends on beyond its record's token: the firm
    cache's head for ``root`` and ``today``, and this file's format."""
    return {**firm_cache.head(root, today), "rows_format": FORMAT}


_digest = firm_cache.digest_of      # the name tests/test_page_rows.py forges a file with


def _token_is_whole(token: object) -> bool:
    return isinstance(token, list) and all(
        one is None or isinstance(one, (str, int)) and not isinstance(one, bool) for one in token)


def _entry_is_whole(entry: object) -> bool:
    if not isinstance(entry, dict) or "token" not in entry \
            or not set(entry) <= {"token", "statuses", "outstanding", "parked"}:
        return False
    if not _token_is_whole(entry["token"]):
        return False
    if ("statuses" in entry) != ("outstanding" in entry):
        return False
    if "statuses" in entry:
        statuses, outstanding = entry["statuses"], entry["outstanding"]
        if not isinstance(statuses, dict) or not all(
                isinstance(k, str) and isinstance(v, int) and not isinstance(v, bool) for k, v in statuses.items()):
            return False
        if not isinstance(outstanding, int) or isinstance(outstanding, bool):
            return False
    if "parked" in entry:
        parked = entry["parked"]
        if not isinstance(parked, list) or not all(
                isinstance(row, list) and len(row) == PARKED_FIELDS and all(isinstance(one, str) for one in row)
                for row in parked):
            return False
    return True


def load(path: Path, expected: dict) -> dict[str, dict]:
    """The kept entries by return folder, when the file at ``path`` is whole
    and its head is ``expected``; otherwise nothing, so every row is read
    and the file replaced. A missing file, or one with another head (another
    day, program, root or format), is the ordinary way it ends and is not
    said; one that cannot be read or is damaged is said on the error log by
    its class or reason, never its words.

    The file is two lines: the head and the digest of the second, then the
    entries. The digest is of the entries' text as written, so a file
    damaged into other valid JSON is refused without re-encoding 2 MB."""
    text = firm_cache.read_kept(
        path, "The practice page's kept rows could not be read (%s); reading every row")
    if text is None:
        return {}
    first, _, rest = text.partition("\n")
    try:
        top = json.loads(first)
    except json.JSONDecodeError:
        log.warning("The practice page's kept rows are not whole; reading every row")
        return {}
    if not isinstance(top, dict) or top.get("head") != expected:
        return {}
    if top.get("digest") != _digest(rest):
        log.warning("The practice page's kept rows are damaged; reading every row")
        return {}
    try:
        entries = json.loads(rest)
    except json.JSONDecodeError:
        log.warning("The practice page's kept rows are not whole; reading every row")
        return {}
    if not isinstance(entries, dict) or not all(
            isinstance(folder, str) and _entry_is_whole(entry) for folder, entry in entries.items()):
        log.warning("The practice page's kept rows are damaged; reading every row")
        return {}
    return entries


def save(path: Path, expected: dict, entries: dict[str, dict]) -> None:
    """Keep ``entries`` under the head ``expected``, all or nothing. A file
    that cannot be written is said on the error log by its class, and
    nothing else changes: the page already stands, and the next page reads
    what it must."""
    rest = json.dumps(entries, separators=(",", ":"))
    first = json.dumps({"head": expected, "digest": _digest(rest)}, separators=(",", ":"))
    firm_cache.save_kept(path, f"{first}\n{rest}", "The practice page's kept rows could not be written (%s)")


class Kept:
    """One page's kept rows: what was loaded, what this page read, and
    whether anything changed. Handed the record's token by the caller, who
    asks the store; asked by the return's folder as text."""

    def __init__(self, path: Path, head: dict, entries: dict[str, dict]) -> None:
        self.path = path
        self.head = head
        self.entries = entries
        self.changed = False
        #: The store's tokens of every record, by stored path, as this page
        #: first asked them; the runner fills it, once a report, and empties
        #: it before the next (a failed fill's redraw asks again).
        self.tokens: dict[str, tuple] | None = None

    def _entry(self, folder: Path, token: tuple | None) -> dict | None:
        if token is None:
            return None
        entry = self.entries.get(str(folder))
        return entry if entry is not None and entry["token"] == list(token) else None

    def counts(self, folder: Path, token: tuple | None) -> tuple[dict[str, int], int] | None:
        """The statuses and outstanding count kept for ``folder`` under
        ``token``, or ``None``."""
        entry = self._entry(folder, token)
        if entry is None or "statuses" not in entry:
            return None
        return dict(entry["statuses"]), entry["outstanding"]

    def parked(self, folder: Path, token: tuple | None) -> list[list[str]] | None:
        """The parked rows kept for ``folder`` under ``token``, in index
        order, or ``None``."""
        entry = self._entry(folder, token)
        if entry is None or "parked" not in entry:
            return None
        return [list(row) for row in entry["parked"]]

    def _fresh(self, folder: Path, token: tuple) -> dict:
        key = str(folder)
        entry = self.entries.get(key)
        if entry is None or entry["token"] != list(token):
            entry = self.entries[key] = {"token": list(token)}
        self.changed = True
        return entry

    def keep_counts(self, folder: Path, token: tuple, statuses: dict, outstanding: int) -> None:
        """Keep a fresh read's counts under the token it was read under."""
        entry = self._fresh(folder, token)
        entry["statuses"] = {str(status): int(n) for status, n in statuses.items()}
        entry["outstanding"] = int(outstanding)

    def keep_parked(self, folder: Path, token: tuple, rows: list[list[str]]) -> None:
        """Keep a fresh read's parked rows under the token it was read under
        - only when every row is :data:`PARKED_FIELDS` words. A row with a
        field that is not text (an index line with a field left empty as
        ``null``) is drawn from this read and the return is forgotten, read
        afresh every page: kept, it would make :func:`load` refuse the
        whole file as damaged."""
        if not all(len(row) == PARKED_FIELDS and all(isinstance(one, str) for one in row) for row in rows):
            self.forget(folder)
            return
        self._fresh(folder, token)["parked"] = [list(row) for row in rows]

    def forget(self, folder: Path) -> None:
        """Drop whatever is kept for ``folder``: its read failed, or its
        token moved while it was read."""
        if self.entries.pop(str(folder), None) is not None:
            self.changed = True

    def save(self) -> None:
        """Write the file, only when an entry changed."""
        if self.changed:
            save(self.path, self.head, self.entries)
            self.changed = False


def open_kept(root: Path | str, today: dt.date | None = None) -> Kept | None:
    """This page's kept rows for ``root``: ``None`` when there is no data
    folder (said by its class on the error log) - the page then reads every
    row, as before P227 - otherwise whatever :func:`load` keeps, empty on a
    first page."""
    try:
        path = rows_path()
        head = page_head(root, today or dt.date.today())
    except Exception as exc:        # a page without kept rows is the page as it always was
        log.warning("The practice page's kept rows are not used (%s)", errors.error_class(exc))
        return None
    return Kept(path, head, load(path, head))
