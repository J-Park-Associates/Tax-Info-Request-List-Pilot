"""Tests for tracker/hold.py - the per-reply memo, out of the settings.

The claims are the module's whole debt. The hold reaches for nothing in the
package, at load time or at call time: it is layer 0's, so any module may
keep an answer for one reply or one household. The settings module, which
held it until P2.6, still offers every public name, and each is the very
object defined here - so ``settings.one_reading`` and ``hold.one_reading``
are one hold, not two - until P2.13 points their readers here. It never
offers ``_HELD`` or ``_HOLDING``: ``hold._holding`` rebinds both, and a copy
taken at import would read ``None`` for ever.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.import_graph import import_edges
from tracker import hold, settings

#: The public names the settings module re-exports until P2.13
#: (SPEC-architecture-p2 R2.6.2).
RE_EXPORTED = frozenset({"HOLD_HOUSEHOLD", "HOLD_READING", "WRITE_WHILE_HOLDING", "WRITE_WHILE_READING",
                         "held", "one_household", "one_reading", "refuse_a_write_while_reading",
                         "resolved"})


def _public_names() -> set[str]:
    """The names hold binds itself, at module level, without an underscore:
    read off its source, so a name it only imports is not counted as its
    own."""
    tree = ast.parse(Path(hold.__file__).read_text(encoding="utf-8"))
    names: set[str] = set()
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.add(node.name)
        elif isinstance(node, ast.Assign):
            names |= {one.id for target in node.targets for one in ast.walk(target) if isinstance(one, ast.Name)}
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.add(node.target.id)
    return {name for name in names if not name.startswith("_")}


def test_the_hold_imports_nothing_of_the_package():
    """A layer 0 module: the life of an answer needs nothing of the package,
    so the settings module and the store may both keep theirs in it. The
    settings module imports it at load time and reads it through the
    module."""
    load, call = import_edges()

    assert load["hold"] == set(), load["hold"]
    assert call["hold"] == set(), call["hold"]
    assert "hold" in load["settings"], "the settings read the hold through the module"


def test_the_settings_re_export_is_the_holds_own():
    """Every public name hold defines resolves from the settings module to
    this module's object - the same object, so a hold entered through
    either is the one hold, and a held answer is kept in one memo. ``T`` is
    the type variable ``held``'s signature names, not a name a reader asks
    for, and is not re-exported. ``_HELD`` and ``_HOLDING`` are never
    re-exported: a copy would keep the ``None`` it found at import while
    ``_holding`` rebinds the original. The facade goes in P2.13."""
    public = _public_names()

    assert public - {"T"} == RE_EXPORTED, sorted((public - {"T"}) ^ RE_EXPORTED)
    for name in RE_EXPORTED:
        assert getattr(settings, name) is getattr(hold, name), name
    assert not hasattr(settings, "_HELD") and not hasattr(settings, "_HOLDING")
