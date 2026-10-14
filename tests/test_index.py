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
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.import_graph import import_edges
from tracker import filer, index

#: The private names the filer imports by those names (SPEC-architecture-p2
#: R2.9.1): each reads only the moved tail's grammar, so it lives beside it.
PRIVATE_CROSSING = frozenset({"_before_the_moved_sentence", "_says_it_is_nowhere", "_without_moved_sentence"})


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
