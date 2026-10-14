"""Tests for tracker/index.py - the index's words and their readers, out of the filer.

The claims are the module's whole debt. The index reads the store, the
journal, the record types and the validators, all layer 1, and the layout
and the reasons, layer 0, and nothing at call time: every module that reads
a row by its words can read it here without importing the sorter, which is
what lets the scanner stop importing the filer (P2.10). The filer, which
held these words until P2.9, still offers every public name, and each is
the very object defined here - so ``filer.read_index`` and
``index.read_index`` are one reader, and a stand-in on the filer's still
reaches the filer's own callers - until P2.14 points their readers here.
Three private names cross from here to the filer, the readers of the moved
tail the filer's writer asks, and no other private name does.

The index's own tests came with it from ``tests/test_filer.py``: those
whose bodies drive only the moved readers - a new engagement's index, the
moved and both-gone sentences read back, and the index read without
following the journal - reading ``tracker.index`` where they read the
filer. No test there drives only :func:`tracker.index.interrupted` or
:func:`tracker.index.holds_the_row`: each is reached through a pass or a
person's action, and those tests stay with the filer.
"""

from __future__ import annotations

import ast
from dataclasses import replace
from pathlib import Path

from tests.builders import DAY1, DAY2, ITEMS, engagement_fixture
from tests.conftest import make_engagement
from tests.import_graph import import_edges
from tracker import filer, index, ledger, store
from tracker.index import FILED, NEEDS_REVIEW, ensure, read_index
from tracker.layout import PREPARED_DIR_NAME, REVIEW_DIR_NAME

#: The private names the filer imports by those names (SPEC-architecture-p2
#: R2.9.1): each reads only the moved tail's grammar, so it lives beside it.
PRIVATE_CROSSING = frozenset({"_before_the_moved_sentence", "_says_it_is_nowhere", "_without_moved_sentence"})

engagement = engagement_fixture(ITEMS)


def _own_names() -> set[str]:
    """The names index binds itself, at module level: read off its source,
    so a name it only imports is not counted as its own."""
    tree = ast.parse(Path(index.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {one.id for target in node.targets for one in ast.walk(target) if isinstance(one, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return names


def test_the_index_imports_layer_one_and_below_and_nothing_at_call_time():
    """A layer 1 module: the store, the journal, the record types and the
    validators (layer 1), the layout and the reasons (layer 0). The
    prepared folder's name comes from the layout, where it is defined, so
    the index has no edge to the scaffold; and nothing that sorts, moves or
    reads a document. The filer imports it at load time."""
    load, call = import_edges()

    assert load["index"] == {"layout", "ledger", "reasons", "records", "store", "validators"}, load["index"]
    assert call["index"] == set(), call["index"]
    assert "index" in load["filer"], "the filer reads the index's words from it"


def test_the_filers_re_export_is_the_indexs_own():
    """Every public name index defines resolves from the filer to this
    module's object - the same object, so a reader that still imports it
    from the filer reads the index's words and runs the index's reader. Of
    its private names exactly the three readers of the moved tail are the
    filer's too, the one place a private name crosses this boundary; the
    tail's grammar itself stays here. The facade goes in P2.14."""
    own = _own_names()
    public = {name for name in own if not name.startswith("_")}

    assert public, "the index defines no public name; the pin reads nothing"
    for name in sorted(public):
        assert getattr(filer, name) is getattr(index, name), name
    crossing = {name for name in own if name.startswith("_") and hasattr(filer, name)}
    assert crossing == PRIVATE_CROSSING, sorted(crossing ^ PRIVATE_CROSSING)
    for name in PRIVATE_CROSSING:
        assert getattr(filer, name) is getattr(index, name), name


# ------------------------------- the index moves into the record (d102) ----


def test_a_new_engagement_is_simply_current(engagement):
    """A brand new folder is nothing but its create: no index rows, no
    files moved, and the store describes it from its first day."""
    assert ensure(engagement) == store.CURRENT
    assert read_index(engagement) == []
    assert [e[ledger.EVENT_KEY] for e in ledger.read_events(engagement)] == [
        ledger.RULES_CHANGED]


def test_an_index_read_without_following_is_the_store_as_it_stands(tmp_path):
    """Decision 192: the practice page reads each return's index as the
    walk left the store, without reading its journal again. A line behind
    the store is not seen that way and is seen by every other reader; a
    return the store does not hold is followed either way."""
    from tests.conftest import seed_index, written_elsewhere
    from tracker.records import IndexEntry, entry_to_json, ledger_key

    engagement = make_engagement(tmp_path / "Clients", ITEMS, scaffold=False)

    def parked(name):
        return IndexEntry(received="2026-02-02", original_name=name, size_kb=5.0, digest="ef" * 32,
                          identifier="", prepared_location="", pbc_location=name,
                          decision=NEEDS_REVIEW, reason="no request matched")

    seed_index(engagement, [parked("first.pdf")])
    behind = parked("second.pdf")
    # A line behind the store is one another machine wrote: every line this
    # machine writes goes through the store (decision 159's checkpoint).
    written_elsewhere(engagement, ledger.new(ledger.IMPORTED, **{
        ledger.KEY_KEY: ledger_key(behind), ledger.ROW_KEY: entry_to_json(behind)}))

    assert [one.original_name for one in read_index(engagement, follow=False)] == ["first.pdf"]
    assert [one.original_name for one in read_index(engagement)] == ["first.pdf", "second.pdf"]

    assert store.forget(store.connect(), engagement)
    assert [one.original_name for one in read_index(engagement, follow=False)] == [
        "first.pdf", "second.pdf"]


# ---------------------------------------- the moved sentences read back ----


def test_the_moved_sentence_is_read_back_from_any_path():
    """The pattern is derived from the template that wrote the sentence, so a
    client's own file name - spaces, brackets, the (2) a collision makes, a
    semicolon, a name that is not ASCII at all - comes back exactly as it
    went in, and the base the next sentence is appended to is the reason as
    it stood."""
    from tracker.index import (
        FILE_MOVED,
        MOVED_GONE_SENTENCE,
        MOVED_SENTENCE,
        _without_moved_sentence,
        moved_to,
    )
    from tracker.records import IndexEntry

    base = "the file's own words matched A01; assigned by a person on 2026-07-01"
    home = f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements/A01 - W-2 Wage Statements - TY2025.pdf"
    row = IndexEntry(
        received=DAY1.isoformat(), original_name="w2.pdf", size_kb=1.0, digest="a" * 64,
        identifier="A01", prepared_location=home,
        # A location across the two trees, as every row holds one since
        # decision 125: nothing here reads it, and it is written the way
        # the record writes it.
        pbc_location="../../../../Clients/Smith Family/2025/w2.pdf",
        decision=FILE_MOVED, reason=base,
    )
    for now in (
        f"{PREPARED_DIR_NAME}/C01 - Mortgage Interest/w2 (2).pdf",
        f"{PREPARED_DIR_NAME}/C01 - Mortgage Interest/impots; recus (2026) été.pdf",
        f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/scan 0012 - copy.pdf",
    ):
        sentence = MOVED_SENTENCE.format(home=home, now=now, date=DAY2.isoformat())
        moved = replace(row, reason=f"{base}; {sentence}")
        assert moved_to(moved) == now
        assert _without_moved_sentence(moved.reason) == base
        # The same row once the bytes are nowhere: no path to read back.
        gone = replace(row, reason="{}; {}".format(base, MOVED_GONE_SENTENCE.format(
            home=home, prepared=PREPARED_DIR_NAME, pbc=row.pbc_location,
            date=DAY2.isoformat())))
        assert moved_to(gone) is None
        assert _without_moved_sentence(gone.reason) == base
        # And a row that is not File Moved says nothing about where it is.
        assert moved_to(replace(moved, decision=FILED)) is None
    assert _without_moved_sentence(base) == base             # any other reason is left alone


def test_the_both_gone_sentence_is_read_behind_a_persons_marks_and_never_swallowed_by_one():
    """d157. The both-gone sentence is read off the row the way decision
    109's moved sentences are, from its own template. A person's mark
    (decision 146) may sit after it or before it: after it, the sentence is
    read behind the mark; before it, the mark's note in brackets never
    swallows the sentence's own bracket. A sentence added to such a row goes
    before the moved sentence, so the row still reads as it did."""
    from tracker.index import (
        BOTH_GONE_SENTENCE,
        FILE_MOVED,
        MARKED_MISSING,
        _before_the_moved_sentence,
        _without_moved_sentence,
        both_gone,
    )
    from tracker.records import IndexEntry

    gone = BOTH_GONE_SENTENCE.format(home=f"{PREPARED_DIR_NAME}/E01 - Brokerage - TY2025.pdf",
                                     prepared=PREPARED_DIR_NAME, pbc="../../2025/schwab.pdf",
                                     date=DAY2.isoformat())
    mark = MARKED_MISSING.format(identifier="A02", date=DAY1.isoformat(), note=" (no interest detail)")
    row = IndexEntry(received=DAY1.isoformat(), original_name="schwab.pdf", size_kb=1.0,
                     digest="a" * 64, identifier="E01",
                     prepared_location=f"{PREPARED_DIR_NAME}/E01 - Brokerage - TY2025.pdf",
                     pbc_location="../../2025/schwab.pdf", decision=FILE_MOVED,
                     reason=f"filed whole; {mark}; {gone}")
    assert both_gone(row)
    assert _without_moved_sentence(row.reason) == f"filed whole; {mark}"

    after = replace(row, reason=f"filed whole; {gone}; {mark}")
    assert both_gone(after)
    assert _without_moved_sentence(after.reason) == f"filed whole; {mark}"
    assert _before_the_moved_sentence(after.reason, "said") == f"filed whole; said; {gone}; {mark}"
    assert not both_gone(replace(after, prepared_location=""))          # marked missing
    assert not both_gone(replace(after, decision=FILED))
