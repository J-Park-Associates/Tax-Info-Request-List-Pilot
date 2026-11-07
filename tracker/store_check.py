"""The check and the export: the store read whole, by a module that writes neither side.

**What it holds.** :func:`check`, the gate (decision 101: "the check is the
gate", ``docs/storage.md``), which compares the store's tables with
:func:`tracker.ledger.replay` over an engagement's own journal and names
every place they disagree, in sentences - the record's statuses and
taught words read off that replay handed the store's case rule
(``ledger.replay(events, key=identifier_key)``, decision 136, P326); and
:func:`export`, the three spreadsheets a person asks for on demand, with
the spreadsheet-cell rule (:data:`FORMULA_LEADS`, :func:`_as_text`) that
only the export's writer reads.

**Why it is apart from the store** (SPEC-architecture-p3 P3.4, P324). The
store answers questions and applies lines; the check asks what else holds
the same facts and compares. A module that reads the store and the journal
side by side, and writes neither, keeps the gate from being edited as part
of the writer it checks: a change to how a line is applied is a change to
:mod:`tracker.store`, and the rule that holds the result to the journal is
read here, in a file of its own. The export sits with it because it is the
other read-only walk of the whole store - the one a person keeps.

**Why it sits at layer 1.** It reads the store, the admission, the journal
and the record (:mod:`tracker.store`, :mod:`tracker.admission`,
:mod:`tracker.ledger`, :mod:`tracker.records`), which are layer 1, and the
lock's flush (:func:`tracker.locking.full_sync`, layer 0), which
:func:`_write_csv` calls; nothing above them. It writes the export through
:mod:`tracker.fsio` at call time. The store does not import it at load
time: the store's command line asks it at call time, from its ``__main__``
block, and that is the one cycle this module closes
(``tests/test_layers.py``, ``CALL_TIME_CYCLES``).

**What it reads of the store, and why by name.** The column lists, the key
rule (``key_root``, ``engagement_path``), the row reader, the cell forms
both sides are compared in (``_to_sql``, ``_agree``, ``_household_cell``),
the stored taught words and the statuses' view of the keyed fold
(:func:`_recorded_statuses`, which ``_apply`` writes through, decision 138)
stay the store's, because the store writes with them. This module imports
each by name, so the code below
reads them bare exactly as it did in the store, and nothing is re-exported
for a reader: every caller names ``tracker.store_check``.

The code below came from the store byte for byte, with its comments and
docstrings, but for :func:`_write_csv`'s sentence on what this module
imports: where they name :func:`_recorded_statuses`, they mean the store's.
P326 then had :func:`check` hand the journal's own fold the store's key
rather than fold the same lines again itself, and the taught words' copy
of that fold went.
"""

from __future__ import annotations

import csv
import json
import sqlite3
from pathlib import Path

from tracker import ledger
from tracker.admission import KIND_HOUSEHOLD, StoreError, _refuse_a_malformed_line
from tracker.locking import full_sync
from tracker.records import identifier_key
from tracker.store import (
    DOCUMENT_COLUMNS,
    ENGAGEMENT_COLUMNS,
    HOUSEHOLD_COLUMNS,
    HOUSEHOLD_PREFIX,
    JOURNAL_GONE,
    REWRITTEN,
    RULE_COLUMNS,
    STATUS_COLUMNS,
    _agree,
    _engagement_row,
    _household_cell,
    _recorded_statuses,
    _rewritten_from,
    _stored_learned,
    _to_sql,
    engagement_path,
    key_root,
)

# --------------------------------------------------------------- the check ----


def check(conn: sqlite3.Connection, root: Path | str, engagement_dir: Path | str) -> list[str]:
    """Every place the store and the journal disagree, as sentences.

    The gate. An empty list is the claim that these tables say exactly
    what the engagement's own record says - the same index rows in the
    same order, field for field; the same status for every identifier; the
    same rule, where the record carries one; and, since decision 113, the
    same keywords taught to each request, in the same order. Anything else
    is named in a sentence a person can act on: which engagement, which row
    or identifier, which field, what each side says.

    **The other copy is the journal, and it is the only one.** The
    readers answer from these very tables, so asking them would be the
    store compared with itself. This replays the lines and compares the
    fold, which is what a rebuild is made of and what a rebuild must come
    back to - the rules included, always: an engagement with no rules
    event has none on either side.

    **A request is one request whatever its case** (decision 136). The
    journal's own fold keys a status and a taught word by the spelling
    each line carries, because :mod:`tracker.ledger` sits below
    :mod:`tracker.records` and has no case rule; the store keys both by
    ``records.identifier_key``. So for those two the journal's own fold is
    run again over the same lines, handed the store's rule
    (``ledger.replay(events, key=identifier_key)``, P326), and
    :func:`tracker.store._recorded_statuses` reads the statuses out of it -
    otherwise a request the person retyped by case is two requests to the
    check and one to the store, and the gate names a disagreement no
    rebuild can clear. The lines are read once
    (:func:`tracker.ledger.read_with_head`, decision 135) and the same list
    is handed to both replays, so neither can be looking at a different
    moment of the journal from the other.
    """
    name = Path(engagement_dir).name
    rel = engagement_path(key_root(engagement_dir, root), engagement_dir)
    engagement = _engagement_row(conn, engagement_dir, root)
    # A journal that is gone is one sentence, not a list of every row the
    # store holds and the record does not (SPEC-162 ruling 5).
    if engagement is not None and not ledger.path_for(engagement_dir).exists():
        return [JOURNAL_GONE.format(n=engagement["applied_seq"], engagement=rel)]
    events, _head, chain = ledger.read_with_chain(engagement_dir)
    folded = ledger.replay(events)
    if engagement is None:
        return [f"{rel}: the store does not hold this engagement, and its record carries "
                f"{len(folded.rows)} index row(s) and {len(folded.rules)} request row(s)"]
    problems: list[str] = []
    applied = engagement["applied_seq"]
    if applied <= len(events) and ledger.chain_at(chain, applied) != engagement["applied_digest"]:
        # The applied chain (decision 137, A3): the lines the store applied
        # are not the lines the journal holds now.
        problems.append(REWRITTEN.format(
            rel=rel, line=_rewritten_from(conn, engagement["id"], events, applied)))
    problems += _check_documents(conn, engagement["id"], name, folded.rows)
    keyed = ledger.replay(events, key=identifier_key)
    problems += _check_statuses(conn, engagement["id"], name, _recorded_statuses(keyed))
    problems += _check_rules(conn, engagement["id"], name, folded)
    problems += _check_intents(conn, engagement["id"], name, folded.intents)
    problems += _check_learned(conn, engagement["id"], name, keyed.learned)
    problems += _check_household(conn, engagement["id"], name, folded.household)
    # Every line judged again by today's admission (decision 187), so a line
    # an earlier version applied that the rule now refuses is named on the
    # day of the upgrade, without deleting the store to find it.
    for seq, event in enumerate(events, start=1):
        try:
            _refuse_a_malformed_line(event, seq, engagement["path"], kind=engagement["kind"])
        except StoreError as exc:
            problems.append(str(exc))
    return problems


def _check_household(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, object]
) -> list[str]:
    """The household's details, table against journal (decision 125).

    A folder whose journal carries a ``household_changed`` line is a
    household, and the row must say so as well as holding what the line
    said: a row the store still calls a return would be a household
    discovery walks straight past. A folder with no such line is compared
    about nothing, which is every return in the practice.
    """
    if not recorded:
        return []
    row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    problems = []
    if row["kind"] != KIND_HOUSEHOLD:
        problems.append(
            f"{name}: the record carries the household's details and the store holds the "
            f"folder as {row['kind']!r}")
    for field in recorded:
        column = f"{HOUSEHOLD_PREFIX}{field}"
        if column not in HOUSEHOLD_COLUMNS:
            continue
        theirs = _household_cell(field, recorded)
        if row[column] != theirs:
            problems.append(
                f"{name}: household {field}: the store says {row[column]!r}, "
                f"the record says {theirs!r}")
    return problems


def _check_documents(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, dict]
) -> list[str]:
    stored = list(conn.execute(
        'SELECT * FROM documents WHERE engagement_id = ? ORDER BY "position"', (engagement_id,)))
    rows = list(recorded.items())
    problems = []
    if len(stored) != len(rows):
        problems.append(
            f"{name}: the store holds {len(stored)} index row(s), the record carries {len(rows)}")
    for position, (key, row) in enumerate(rows[:len(stored)]):
        held = stored[position]
        if held["key"] != key:
            problems.append(
                f"{name}: index row {position + 1}: the store holds {held['key']!r}, "
                f"the record carries {key!r}")
            continue
        for field in DOCUMENT_COLUMNS:
            theirs = _to_sql(row.get(field))
            if not _agree("documents", field, held[field], theirs):
                problems.append(
                    f"{name}: index row {key!r}, {field}: the store says {held[field]!r}, "
                    f"the record says {theirs!r}")
    for held in stored[len(rows):]:
        problems.append(
            f"{name}: index row {held['key']!r} is in the store and not in the record")
    return problems


def _check_intents(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, dict]
) -> list[str]:
    """The moves this engagement has open, both ways round (decision 119).

    The two folds have to agree about exactly this: a recovery finishes
    what the table says is open, and a table that had kept an intent the
    journal closed would move a file the record has already recorded - the
    one thing this whole decision exists to stop. So the line is compared
    whole, as the documents' fields are.
    """
    stored = {row["key"]: row["payload"] for row in conn.execute(
        'SELECT "key", payload FROM intents WHERE engagement_id = ?', (engagement_id,))}
    problems = []
    for key, event in recorded.items():
        held = stored.get(key)
        theirs = json.dumps(event, ensure_ascii=False, sort_keys=True)
        if held is None:
            problems.append(f"{name}: the move open on {key!r} is in the record and not in the store")
        elif held != theirs:
            problems.append(
                f"{name}: the move open on {key!r}: the store holds {held!r:.120}, "
                f"the record carries {theirs!r:.120}")
    for key in sorted(set(stored) - set(recorded)):
        problems.append(f"{name}: the move open on {key!r} is in the store and not in the record")
    return problems


def _check_statuses(
    conn: sqlite3.Connection, engagement_id: int, name: str,
    recorded: dict[str, tuple[str, dict]],
) -> list[str]:
    stored = {row["identifier"]: row for row in conn.execute(
        "SELECT * FROM statuses WHERE engagement_id = ?", (engagement_id,))}
    problems = []
    for key, (identifier, status) in recorded.items():
        held = stored.get(key)
        if held is None:
            problems.append(f"{name}: request {identifier} has a status in the record and none in the store")
            continue
        for field in STATUS_COLUMNS:
            theirs = _to_sql(status.get(field))
            if not _agree("statuses", field, held[field], theirs):
                problems.append(
                    f"{name}: request {identifier}, {field}: the store says {held[field]!r}, "
                    f"the record says {theirs!r}")
    for key in sorted(set(stored) - set(recorded)):
        problems.append(f"{name}: request {key} has a status in the store and none in the record")
    return problems


def _check_rules(
    conn: sqlite3.Connection, engagement_id: int, name: str, folded: ledger.Folded
) -> list[str]:
    stored = {identifier_key(row["identifier"]): row for row in conn.execute(
        "SELECT * FROM requests WHERE engagement_id = ?", (engagement_id,))}
    problems = []
    if len(stored) != len(folded.rules):
        problems.append(
            f"{name}: the store holds {len(stored)} request row(s), "
            f"the record's edits fold to {len(folded.rules)}")
    seen = set()
    for identifier, rule in folded.rules.items():
        key = identifier_key(identifier)
        seen.add(key)
        held = stored.get(key)
        if held is None:
            problems.append(f"{name}: request {identifier} is in the record and not in the store")
            continue
        for field in RULE_COLUMNS:
            theirs = _to_sql(rule.get(field))
            if held[field] != theirs:
                problems.append(
                    f"{name}: request {identifier}, {field}: the store says {held[field]!r}, "
                    f"the record says {theirs!r}")
    for key in sorted(set(stored) - seen):
        problems.append(
            f"{name}: request {stored[key]['identifier']} is in the store and not in the record")
    row = conn.execute("SELECT * FROM engagements WHERE id = ?", (engagement_id,)).fetchone()
    for field, value in folded.info.items():
        if field in ENGAGEMENT_COLUMNS and row[field] != _to_sql(value):
            problems.append(
                f"{name}: engagement {field}: the store says {row[field]!r}, "
                f"the record says {_to_sql(value)!r}")
    return problems


def _check_learned(
    conn: sqlite3.Connection, engagement_id: int, name: str, recorded: dict[str, tuple[str, ...]]
) -> list[str]:
    """The keywords filings taught, table against journal (decision 113).

    The one thing in this database the record could not vouch for until
    now: the table only ever grew, the journal's fold did not know the
    event, and this function did not exist - so a row planted or dropped
    behind the journal's back was invisible to the gate. One sentence per
    request whose words differ, naming both sides in the order each holds
    them, because the order is part of the answer: a word taught, taken
    back and taught again belongs last on both sides.

    The table keys a request without case and the journal's fold keys it
    exactly as each line spells it (:class:`tracker.ledger.Folded`), so the
    record's side is the journal's fold handed the table's own rule
    (``ledger.replay(events, key=identifier_key)``, decision 136, P326):
    two spellings of one request are one list, in the order the words were
    taught, and a word taken back under either spelling is gone from it.
    """
    stored = _stored_learned(conn, engagement_id)
    return [
        f"{name}: request {key}, the keywords filings taught: the store says "
        f"{list(stored.get(key, ()))!r}, the record says {list(recorded.get(key, ()))!r}"
        for key in sorted(set(stored) | set(recorded))
        if stored.get(key, ()) != recorded.get(key, ())
    ]


# -------------------------------------------------------------- the export ----

#: A cell beginning with one of these is a formula to a spreadsheet opening
#: the CSV, whatever the quoting - so the export prefixes it with an
#: apostrophe, which Excel shows as text and drops.
FORMULA_LEADS = ("=", "+", "-", "@", "\t", "\r")


def _as_text(value: object) -> str:
    """One stored value as a CSV cell: text, always, and an empty one for
    nothing at all. A file name a client chose may begin with anything -
    a name typed like a formula is a name - and quoting does not protect
    it: a spreadsheet evaluates a cell that begins like a formula on the
    way in. So a cell that begins with one of ``FORMULA_LEADS`` is written
    behind an apostrophe, the mark a spreadsheet reads as "text follows"
    and shows without; the name is one character away and never runs."""
    text = "" if value is None else str(value)
    return f"'{text}" if text.startswith(FORMULA_LEADS) else text


#: What :func:`export` writes, in the order it writes them.
DOCUMENTS_CSV = "documents.csv"
REQUESTS_CSV = "requests.csv"
ENGAGEMENTS_CSV = "engagements.csv"


def export(conn: sqlite3.Connection, out_dir: Path | str) -> list[Path]:
    """Write the store out as three spreadsheets. Returns the files written.

    **On demand only, and never by a pass.** Decision 91 settled that staff
    read everything as a page, and decision 104 that they edit the one
    list in the app; a pass that wrote spreadsheets nobody asked for would
    be inventing a second thing to keep in step. This is for the moment
    somebody wants the season's filings in a pivot table.

    Every cell is written as text, with a byte-order mark so that Excel
    opens the file as UTF-8 without being asked, and LF line endings like
    every other file this repository writes. Nothing is in these files that
    is not already in the index and the request list.
    """
    out_dir = Path(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    paths = [out_dir / DOCUMENTS_CSV, out_dir / REQUESTS_CSV, out_dir / ENGAGEMENTS_CSV]
    folders = {row["id"]: row["path"] for row in conn.execute("SELECT id, path FROM engagements")}

    _write_csv(paths[0], ["engagement", "key", *DOCUMENT_COLUMNS, "position", "seq"], (
        [folders[row["engagement_id"]], row["key"],
         *[row[name] for name in DOCUMENT_COLUMNS], row["position"], row["seq"]]
        for row in conn.execute('SELECT * FROM documents ORDER BY engagement_id, "position"')
    ))

    statuses = {(row["engagement_id"], row["identifier"]): row
                for row in conn.execute("SELECT * FROM statuses")}
    _write_csv(paths[1], ["engagement", *RULE_COLUMNS, *STATUS_COLUMNS, "status_seq"], (
        [folders[row["engagement_id"]], *[row[name] for name in RULE_COLUMNS],
         *[(status[name] if status else None) for name in STATUS_COLUMNS],
         (status["seq"] if status else None)]
        for row, status in (
            (row, statuses.get((row["engagement_id"], identifier_key(row["identifier"]))))
            for row in conn.execute('SELECT * FROM requests ORDER BY engagement_id, "row"')
        )
    ))

    engagement_columns = ["path", *ENGAGEMENT_COLUMNS, "ledger_head", "applied_seq", "built_at"]
    _write_csv(paths[2], engagement_columns, (
        [row[name] for name in engagement_columns]
        for row in conn.execute('SELECT * FROM engagements ORDER BY "path"')
    ))
    return paths


def _write_csv(path: Path, header: list[str], rows) -> None:
    """One spreadsheet, whole or not written (decision 155): through the
    one atomic replacement, flushed before it takes the name. Reached at
    call time - the check imports the store, the admission, the journal,
    the record and the lock and nothing else at load time (P324), and this
    is the one file it writes that is not the database."""
    from tracker.fsio import atomic_replacement

    with atomic_replacement(path) as temp:
        with temp.open("w", encoding="utf-8-sig", newline="") as handle:
            writer = csv.writer(handle, lineterminator="\n")
            writer.writerow(header)
            for row in rows:
                writer.writerow([_as_text(value) for value in row])
            handle.flush()
            full_sync(handle.fileno())
