"""Tests for tracker/hold.py - the per-reply memo, out of the settings.

The claims are the module's whole debt. The hold reaches for nothing in the
package, at load time or at call time: it is layer 0's, so any module may
keep an answer for one reply or one household. The settings module, which
held it until P2.6, offered every public name as the very object defined
here, and P2.13 pointed their readers here; every reader now asks the hold
itself. It never offered ``_HELD`` or ``_HOLDING``: ``hold._holding``
rebinds both, and a copy taken at import would read ``None`` for ever.

The hold's own tests came with it from ``tests/test_settings.py``: those
whose bodies name only the hold's names, reading ``hold.`` where they read
the settings module. The hold tests that also ask the settings module
something of its own - its data folder, its program folder, its file -
stay there.
"""

from __future__ import annotations

import pytest

from tests.import_graph import import_edges
from tracker import hold


def test_the_hold_imports_nothing_of_the_package():
    """A layer 0 module: the life of an answer needs nothing of the package,
    so the settings module and the store may both keep theirs in it. The
    settings module imports it at load time and reads it through the
    module."""
    load, call = import_edges()

    assert load["hold"] == set(), load["hold"]
    assert call["hold"] == set(), call["hold"]
    assert "hold" in load["settings"], "the settings read the hold through the module"


# ------------------------------------------------ one reading (P118) ----

def test_one_reading_holds_what_a_path_resolves_to_but_never_an_error(monkeypatch, tmp_path):
    from pathlib import Path

    calls, real = [], Path.resolve

    def counted(self, strict=False):
        calls.append(str(self))
        if self.name == "refuses":
            raise OSError("cannot be resolved")
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", counted)
    with hold.one_reading():
        for _ in range(3):
            assert hold.resolved(tmp_path / "a") == real(tmp_path / "a")
            with pytest.raises(OSError):
                hold.resolved(tmp_path / "refuses")
    assert calls.count(str(tmp_path / "a")) == 1
    assert calls.count(str(tmp_path / "refuses")) == 3
    hold.resolved(tmp_path / "a")
    assert calls.count(str(tmp_path / "a")) == 2, "outside a reading nothing is held"


# --------------------------------------------- one household (P207) ----

def test_one_household_lets_the_pass_write_its_records_and_the_store():
    """The pass writes the store and the records while it holds; the store
    asks ``refuse_a_write_while_reading``, and only a read-only reply
    refuses (P118's SHOULD-3 is the reading's)."""
    with hold.one_household():
        hold.refuse_a_write_while_reading("the store")


def test_one_household_holds_a_path_only_once_it_is_there(monkeypatch, tmp_path):
    """A folder the pass makes later is resolved again: a path resolves
    differently once it exists (Windows gives the folder's own case, a link
    is followed), and a store key from before it existed would be another
    return's key."""
    from pathlib import Path

    calls, real = [], Path.resolve

    def counted(self, strict=False):
        calls.append(str(self))
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", counted)
    later = tmp_path / "made later"
    with hold.one_household():
        for _ in range(3):
            assert hold.resolved(tmp_path) == real(tmp_path)
            assert hold.resolved(later) == real(later)
        assert calls.count(str(tmp_path)) == 1, "a folder that is there is resolved once"
        assert calls.count(str(later)) == 3, "a folder that is not there yet is never held"
        later.mkdir()
        hold.resolved(later)
        hold.resolved(later)
        assert calls.count(str(later)) == 4, "once it is there, it is held"


def test_one_household_never_holds_an_error(monkeypatch, tmp_path):
    from pathlib import Path

    calls, real = [], Path.resolve

    def refusing(self, strict=False):
        calls.append(str(self))
        if self.name == "refuses":
            raise OSError("cannot be resolved")
        return real(self, strict)

    monkeypatch.setattr(Path, "resolve", refusing)
    with hold.one_household():
        for _ in range(3):
            with pytest.raises(OSError):
                hold.resolved(tmp_path / "refuses")
    assert calls.count(str(tmp_path / "refuses")) == 3


# ----------------------------------------------- the one hold memo (P215) ----

def test_held_keeps_an_answer_for_the_hold_and_only_once_its_path_is_there(tmp_path):
    """P215: outside a hold every ask is answered afresh; inside a reading
    the first answer stands; inside a household's hold an answer about a
    folder is kept only once the folder is there, so a folder the pass makes
    later is never answered from before it existed."""
    asked = []

    def answer():
        asked.append(1)
        return len(asked)

    assert hold.held(("a question",), answer) == 1
    assert hold.held(("a question",), answer) == 2            # nothing kept outside a hold
    with hold.one_reading():
        assert hold.held(("a question",), answer) == 3
        assert hold.held(("a question",), answer) == 3
    assert hold.held(("a question",), answer) == 4            # dropped with the hold

    later = tmp_path / "made later"
    asked.clear()
    with hold.one_household():
        assert hold.held(("about", str(later)), answer, there=later) == 1
        assert hold.held(("about", str(later)), answer, there=later) == 2   # not there: asked again
        later.mkdir()
        assert hold.held(("about", str(later)), answer, there=later) == 3
        assert hold.held(("about", str(later)), answer, there=later) == 3   # there: kept
        assert hold.held(("no folder",), answer) == 4
        assert hold.held(("no folder",), answer) == 4
    with hold.one_reading():
        gone = tmp_path / "never made"
        assert hold.held(("about", str(gone)), answer, there=gone) == 5
        assert hold.held(("about", str(gone)), answer, there=gone) == 5     # a reading keeps it


def test_held_never_keeps_an_error():
    calls = []

    def failing():
        calls.append(1)
        if len(calls) == 1:
            raise OSError("fabricated")
        return "answered"

    with hold.one_reading():
        with pytest.raises(OSError):
            hold.held(("flaky",), failing)
        assert hold.held(("flaky",), failing) == "answered"
        assert hold.held(("flaky",), failing) == "answered"
    assert len(calls) == 2
