"""Tests for tracker/verify.py - the read-only proof, firm-wide, as a person runs it.

What is claimed here is :func:`tracker.verify.verify`'s own behaviour: that
it changes nothing - not a byte or a time under the clients root, not the
store, not the checkpoint - and names every mismatch by its class and a
path below the root, exiting 1 for any; and that it asks the pass's own
judgment of a record against this machine's checkpoint, so a line the pass
refuses for want of a writer is named by it too (the review's S3). Both
drive the store's command line (``python -m tracker.store ... verify``),
the one way a person runs it, in a process of its own, so no stand-in
crosses into it.

Every test here came from tests/test_store.py with P325
(SPEC-architecture-p3 P3.5), cut and pasted with the two helpers only they
read (``_tree``, ``locate_original``) and under the headings they sat
under, their names kept. The only edits are the classes they assert on,
which they read from ``tracker.verify`` where they read them from the
store. The fixtures and helpers they share with the store's tests are
``tests/store_helpers.py``'s.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests import store_helpers
from tests.builders import drop
from tests.conftest import sort
from tests.store_helpers import A_ROW_ORIGINAL, DAY1, a_row, build, cli, unlinked
from tracker import checkpoint, ledger, store, verify
from tracker.index import read_index

#: The store's fixtures, from ``tests/store_helpers.py``: each named once so
#: that every claim below can ask for it.
root = store_helpers.root
engagement = store_helpers.engagement
by_hand = store_helpers.by_hand
conn = store_helpers.conn


# ------------------------------- decision 159: the record can show it was not altered ----


def _tree(folder: Path) -> dict[str, tuple]:
    """Every file and folder under ``folder``: bytes and modification time."""
    return {str(path.relative_to(folder)): ((path.read_bytes(), path.stat().st_mtime_ns)
                                            if path.is_file() else ("dir",))
            for path in sorted(folder.rglob("*"))}


def test_verify_changes_nothing_and_names_every_mismatch(root, engagement, tmp_path):
    """G-10: a read-only verify, firm-wide. Nothing under the clients root
    changes - not a byte, not a time - and neither the store nor the
    checkpoint is written; every problem is named by class and path below
    the root, and any problem exits 1."""
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    drop(engagement, "1098.pdf", "Form 1098 Mortgage Interest Statement 2025")
    sort(engagement, today=DAY1)
    store.close()
    home = tmp_path / "app"
    kept = {name: (home / name).read_bytes()
            for name in (store.STORE_FILENAME, checkpoint.CHECKPOINT_FILENAME)}

    tree = _tree(root)
    clean = cli(home / store.STORE_FILENAME, "verify", root)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    assert "nothing to report" in clean.stdout
    assert _tree(root) == tree

    entries = read_index(engagement)
    store.close()
    copy = next(entry for entry in entries if entry.prepared_location)
    (engagement / copy.prepared_location).unlink()                          # a working copy gone
    original = locate_original(engagement, entries[-1])
    original.write_bytes(original.read_bytes() + b"changed")                # an original changed
    household_record = ledger.path_for(engagement.parents[1])               # a record cut short
    target = household_record if household_record.is_file() else ledger.path_for(engagement)
    lines = target.read_bytes().splitlines(keepends=True)
    target.write_bytes(b"".join(lines[:-1]))

    tree = _tree(root)
    found = cli(home / store.STORE_FILENAME, "verify", root)
    assert found.returncode == 1
    said_now = found.stdout
    assert verify.V_MISSING in said_now and verify.V_CHANGED in said_now and verify.V_SHORTER in said_now
    assert Path(copy.prepared_location).name in said_now
    assert _tree(root) == tree                                              # nothing moved, nothing made
    assert {name: (home / name).read_bytes() for name in kept} == kept
    assert not (home / store.RECOVERED_DIR).exists()


def locate_original(engagement, entry):
    from tracker.layout import locate

    return locate(engagement, entry.pbc_location)


# ------------------------------------------ decision 159: the part-3 review's fixes ----


def test_verify_names_a_line_with_no_writer_as_the_pass_refuses_it(conn, root, by_hand, tmp_path):
    """S3 (probe Q5b): verify asks the pass's own judgment, so a line with no
    link and no writer after a record from before 159 is named by both."""
    import json as _json

    events = unlinked(ledger.read_events(by_hand))
    store.forget(conn, by_hand)          # a store, and a checkpoint, that never met it
    ledger.path_for(by_hand).write_text(
        "".join(_json.dumps(event, sort_keys=True) + "\n" for event in events), encoding="utf-8")
    build(conn, root, by_hand)
    with ledger.path_for(by_hand).open("a", encoding="utf-8") as handle:
        handle.write(_json.dumps(ledger.new(ledger.PARKED, key=A_ROW_ORIGINAL, row=a_row())) + "\n")
    with pytest.raises(store.StoreError, match="Line 2 .* carries no writer"):
        store.catch_up(conn, root, by_hand)
    conn.close()
    store.close()
    shown = cli(tmp_path / "app" / store.STORE_FILENAME, "verify", root)
    assert shown.returncode == 1 and verify.V_NO_WRITER in shown.stdout and "line 2" in shown.stdout
