"""The read-only firm-wide proof: every record under a root, and every file it records, held to what it should be.

**What it holds.** :func:`verify`, decision 159's read-only proof (G-10),
and the classes of problem it names, each with a path below the root and
never a word of a document (:data:`V_RECORD` to :data:`V_CHANGED`, and
:data:`V_BY_KIND`, which says the checkpoint's judgments in those words).
For every folder with a record it asks whether the record reads, whether
every line is inside the admission (decision 187), whether it extends what
this machine's checkpoint vouches for and whether the store has applied a
prefix of it; for every row, whether its original and each working copy it
claims are there and hold the row's bytes. It writes nothing, takes no lock
and creates nothing.

**Why it is apart from the store** (SPEC-architecture-p3 P3.5, P325). It
walks every record under a root - the registry's walk - and proves each
file's bytes by the index's own proof of a row
(:func:`tracker.index.holds_the_row`), and the store must never import
either: the store is the database the readers answer from, and it sits low
so that it never depends on what walks folders or reads files. While it
lived in the store those two imports sat inside the function, and
``tests/test_store.py`` had to exempt it from the claim that the store
names no reader; here they are this module's own, and the store names none.

**Why it sits at layer 3.** It asks the registry, which is layer 3. Its
load-time imports are layer 1 and below - the store, the admission, the
journal and the record (layer 1) and the checkpoint (layer 0) - but its
place is set by what it asks, not by what it loads. The registry, the
index's proof, the layout and the validators' placeholder test are imported
inside :func:`verify`, at call time, as they were in the store, so loading
this module pulls in nothing that walks a folder, and they run only when a
person runs it.

**Who asks it.** The store's command line (``python -m tracker.store
<the app folder> verify <clients root>``, the runbook's step), at call time
from its ``__main__`` block - the one cycle this module closes
(``tests/test_layers.py``, ``CALL_TIME_CYCLES``). Nothing else imports it.

**What it reads of the store, and why by name.** The checkpoint's judgment
(``_judge``, and the kinds it returns: ``_SHORTER``, ``_REWRITTEN``,
``_CLAIMS``, ``_NO_WRITER``, ``_FOREIGN`` and ``_MALFORMED``), the key rule
(``key_root``, ``engagement_path``) and the row reader (``_engagement_row``)
stay the store's, because every catch-up and ``record()`` asks the same
judgment - the pass's and this proof's alike, so neither has a copy of the
rule (the review's S3). This module imports each by name, so the code below
reads them bare exactly as it did in the store, and nothing is re-exported
for a reader.

The code below came from the store byte for byte, with its comments and
docstrings.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import cast

from tracker import checkpoint, ledger, records
from tracker.admission import KIND_RETURN, StoreError, _refuse_a_malformed_line
from tracker.store import (
    _CLAIMS,
    _FOREIGN,
    _MALFORMED,
    _NO_WRITER,
    _REWRITTEN,
    _SHORTER,
    _engagement_row,
    _judge,
    engagement_path,
    key_root,
)

# ------------------------------------------------------------- verify ----

#: The classes of problem ``verify`` names, one per line with a path below
#: the root and never a word of a document.
V_RECORD = "the record does not read"
V_SHORTER = "the record is shorter than this machine last saw"
V_REWRITTEN = "the record no longer matches what this machine last saw"
V_CLAIMS = "a line says it was written on this machine and was not"
V_NO_WRITER = "a line past what this machine saw carries no writer"
V_FOREIGN = "a line was written on another machine, which is refused"
#: A line the store's admission refuses (decision 187), named by the gate's
#: own sentence - which names the field and the class, never the value.
V_MALFORMED = "a line is outside the record's rule"
V_STORE = "the store has applied lines the record does not hold"
V_MISSING = "a recorded file is missing"
V_CHANGED = "a recorded file holds other bytes"
V_BY_KIND = {_CLAIMS: V_CLAIMS, _NO_WRITER: V_NO_WRITER, _FOREIGN: V_FOREIGN, _MALFORMED: V_MALFORMED}


def verify(conn: sqlite3.Connection, held: sqlite3.Connection | None, root: Path | str) -> list[str]:
    """Every problem, firm-wide, as ``class: path below the root``
    (decision 159, G-10). Read-only: ``conn`` and ``held`` are opened
    read-only by the caller, no lock is taken, nothing is seeded, copied,
    moved or created, and a cloud placeholder is never read (reading one
    downloads it).

    For every folder with a record: the record reads (links, format);
    every line is inside the store's admission (decision 187); it extends
    what the checkpoint vouches for; the store has applied a prefix of it. For every row: its original and each working copy it claims are
    there and hold the row's bytes - proved by the index's own proof of a
    row's bytes (``index.holds_the_row``, decision 109's reading), not a
    second one.
    """
    from tracker import layout, registry
    from tracker.index import FILE_MOVED, holds_the_row
    from tracker.layout import locate
    from tracker.validators import is_cloud_placeholder

    root = Path(root)

    def below(path: Path) -> str:
        # The layout's one question of a path under another (decision 188).
        parts = layout.parts_below(root, path)
        return str(path) if parts is None else "/".join(parts) or "."

    problems: list[str] = []
    for folder in registry.record_dirs(root):
        try:
            events, _head, chain = ledger.read_with_chain(folder)
        except ledger.LedgerError as exc:
            problems.append(f"{V_RECORD}: {below(folder)} ({exc})")
            continue
        row = _engagement_row(conn, folder, root)
        key = row["path"] if row is not None else engagement_path(key_root(folder, root), folder)
        # Every line held to the one admission first (decision 187), as
        # ``check`` holds it: no place a line names is looked at, and no
        # writer judged, before the line's values are inside the rule.
        refused = ""
        for seq, event in enumerate(events, start=1):
            try:
                _refuse_a_malformed_line(event, seq, key,
                                         kind=row["kind"] if row is not None else KIND_RETURN)
            except StoreError as exc:
                refused = str(exc)
                break
        if refused:
            problems.append(f"{V_MALFORMED}: {below(folder)} ({refused})")
            continue
        vouched = checkpoint.vouched(held, key) if held is not None else None
        if vouched is not None:
            # The pass's own judgment, not a copy of it (the review's S3).
            # held is not None: vouched came from it
            judged = _judge(vouched, checkpoint.intent(cast(sqlite3.Connection, held), key), events, chain)
            if judged.kind == _SHORTER:
                problems.append(f"{V_SHORTER}: {below(folder)} ({len(events)} of {judged.seq})")
            elif judged.kind == _REWRITTEN:
                problems.append(f"{V_REWRITTEN}: {below(folder)}")
            elif judged.kind:
                problems.append(f"{V_BY_KIND[judged.kind]}: {below(folder)} line {judged.seq}")
        if row is not None and (row["applied_seq"] > len(events) or
                                ledger.chain_at(chain, row["applied_seq"]) != row["applied_digest"]):
            problems.append(f"{V_STORE}: {below(folder)}")
        entries = [records.entry_from_json(one) for one in ledger.replay(events).rows.values()]
        claims: dict[str, int] = {}
        for position, entry in enumerate(entries):
            if entry.digest and entry.decision != FILE_MOVED:
                for location in entry.filed_locations:
                    claims[location] = position
        for position, entry in enumerate(entries):
            if not entry.digest:
                continue
            places = [location for location in entry.filed_locations if claims.get(location) == position]
            if entry.pbc_location:
                places.insert(0, entry.pbc_location)
            for location in places:
                path = locate(folder, location)
                if not path.is_file():
                    problems.append(f"{V_MISSING}: {below(path)}")
                elif is_cloud_placeholder(path):
                    continue
                elif not holds_the_row(path, entry.digest):
                    problems.append(f"{V_CHANGED}: {below(path)}")
    return problems
