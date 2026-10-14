"""Tests for tools/patch_sites.py: a stand-in that lands where no code looks is found.

The tool's claim is narrow and has to be exact: for every ``setattr`` in the
suite aimed at a module of the repository, whether the module defines the
patched name, reads it after importing it, or never reads it at all. The cases
below build made-up repositories (a ``tracker/`` of two or three invented
modules and a ``tests/`` that patches them) and hold the tool to each form a
test writes a stand-in in and each way a module can or cannot read a name.
The last cases run it on the real suite, where ``check`` must pass (R4.2).
"""

from __future__ import annotations

import ast
import re
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from tools import patch_sites

REPO = Path(__file__).resolve().parent.parent


def _repository(root: Path, files: dict[str, str]) -> Path:
    """A made-up repository under ``root``: each file written as given."""
    for relative, text in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(textwrap.dedent(text).lstrip(), encoding="utf-8")
    return root


#: Two invented modules: ``sorter`` defines ``decide`` and imports three
#: helpers, calling one, re-exporting one and reading one only in an annotation.
SORTER = {
    "tracker/__init__.py": "",
    "tracker/helpers.py": """
        def digest(path):
            return "d"

        def kept(path):
            return path

        class Shape:
            pass
    """,
    "tracker/sorter.py": """
        from tracker.helpers import Shape, digest, kept

        __all__ = ["kept"]

        def decide(path: Shape) -> Shape:
            return digest(path)
    """,
}

#: A third invented module that holds values: an alias of ``sorter``, an
#: object an outside call made, a constant, a name a function rebinds, and a
#: class with a module in it.
HOLDERS = {
    "tracker/holders.py": """
        import logging

        from tracker import sorter

        THE = sorter
        LOG = logging.getLogger("made-up")
        NOTHING = None
        LATER = None

        class Holder:
            module = sorter

        def later():
            global LATER
            LATER = sorter
    """,
}


def _marks(root: Path) -> dict[tuple[str, int, str, str], str]:
    marked, unplaced = patch_sites.stand_ins(root)
    assert not unplaced, unplaced
    return {(site.file, site.line, site.module, site.name): mark for site, mark in marked}


# ------------------------------------------------------------ the three marks ----


def test_a_name_the_module_defines_is_defined_and_one_it_imports_and_calls_is_imported(tmp_path):
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import sorter

        def test_one(monkeypatch):
            monkeypatch.setattr(sorter, "decide", lambda path: "x")
            monkeypatch.setattr(sorter, "digest", lambda path: "x")
    """})
    assert _marks(root) == {("tests/test_a.py", 4, "tracker.sorter", "decide"): patch_sites.DEFINED,
                            ("tests/test_a.py", 5, "tracker.sorter", "digest"): patch_sites.IMPORTED}
    assert patch_sites.check(root)[0]


def test_a_name_the_module_only_re_exports_is_unread_and_fails_the_check(tmp_path):
    """``sorter`` imports ``kept`` and lists it in ``__all__`` but calls
    nothing by it: the stand-in replaces a binding no code looks up."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import sorter

        def test_one(monkeypatch):
            monkeypatch.setattr(sorter, "kept", lambda path: "x")
    """})
    assert _marks(root) == {("tests/test_a.py", 4, "tracker.sorter", "kept"): patch_sites.UNREAD}
    ok, said = patch_sites.check(root)
    assert not ok
    assert said == ["tests/test_a.py:4: tracker.sorter.kept is unread there: tracker/sorter.py never reads it "
                    "outside its import or definition. Point the stand-in at the module that reads it."]


def test_a_name_read_only_in_an_annotation_is_unread(tmp_path):
    """``Shape`` appears in ``decide``'s signature and nowhere else. No call
    reaches an annotation, and the interpreters scope annotations differently,
    so an annotation is never a read."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import tracker.sorter

        def test_one(monkeypatch):
            monkeypatch.setattr(tracker.sorter, "Shape", object)
    """})
    assert _marks(root) == {("tests/test_a.py", 4, "tracker.sorter", "Shape"): patch_sites.UNREAD}


def test_a_name_every_function_shadows_with_a_local_of_its_own_is_unread(tmp_path):
    """A parameter, a local import and a comprehension's variable of the same
    name are each read where they are bound, not from the module; a method
    does not see its class's names, while the class body does."""
    root = _repository(tmp_path, {
        "tracker/__init__.py": "",
        "tracker/helpers.py": "def digest(path):\n    return 'd'\n",
        "tracker/shadows.py": """
            from tracker.helpers import digest

            def by_parameter(digest):
                return digest("p")

            def by_local_import():
                from tracker.helpers import digest
                return digest("p")

            def by_comprehension(paths):
                return [digest for digest in paths]

            class Holder:
                limit = 3
                wide = limit * 2

                def method(self):
                    return limit
        """,
        "tests/test_a.py": """
            from tracker import shadows

            def test_one(monkeypatch):
                monkeypatch.setattr(shadows, "digest", lambda path: "x")
                monkeypatch.setattr(shadows, "limit", 9, raising=False)
        """,
    })
    marks = _marks(root)
    assert marks[("tests/test_a.py", 4, "tracker.shadows", "digest")] == patch_sites.UNREAD
    # The method's ``limit`` is a global read (the class's own is out of its reach).
    assert marks[("tests/test_a.py", 5, "tracker.shadows", "limit")] == patch_sites.IMPORTED


def test_a_read_in_a_module_level_comprehension_is_a_read_on_every_interpreter(tmp_path):
    """3.12 and later inline a comprehension into its scope (PEP 709), and
    ``symtable`` then loses its reads at module level: the tool's own scope
    rules see them on 3.11 and 3.14 alike."""
    root = _repository(tmp_path, {
        "tracker/__init__.py": "",
        "tracker/helpers.py": "AFFINITIES = {'a': 'TEXT'}\nFIELDS = ('a',)\n",
        "tracker/columns.py": """
            from tracker.helpers import AFFINITIES, FIELDS

            COLUMNS = {name: AFFINITIES[name] for name in FIELDS}
        """,
        "tests/test_a.py": """
            from tracker import columns

            def test_one(monkeypatch):
                monkeypatch.setattr(columns, "AFFINITIES", {})
        """,
    })
    assert _marks(root) == {("tests/test_a.py", 4, "tracker.columns", "AFFINITIES"): patch_sites.IMPORTED}


def test_a_name_kept_through_globals_is_defined_and_read_there(tmp_path):
    """A module that imports a reader late and keeps it as its own global
    (``validators.PdfReader``, pilot P219) defines and reads it through
    ``globals()``: a stand-in there is met."""
    root = _repository(tmp_path, {
        "tracker/__init__.py": "",
        "tracker/late.py": """
            def _reader():
                reader = globals().get("Reader")
                if reader is None:
                    from json import loads as reader

                    globals()["Reader"] = reader
                return reader
        """,
        "tests/test_a.py": """
            from tracker import late

            def test_one(monkeypatch):
                monkeypatch.setattr(late, "Reader", object, raising=False)
        """,
    })
    assert _marks(root) == {("tests/test_a.py", 4, "tracker.late", "Reader"): patch_sites.DEFINED}


# ------------------------------------------------------ how a test names it ----


def test_the_module_is_found_under_an_alias_a_local_name_and_a_string(tmp_path):
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import tracker.sorter as sorter_module

        def test_one(monkeypatch):
            here = sorter_module
            monkeypatch.setattr(sorter_module, "decide", None)
            monkeypatch.setattr(here, "digest", None)
            monkeypatch.setattr("tracker.sorter.kept", None)
    """})
    marked, _unplaced = patch_sites.stand_ins(root)
    assert [(site.line, site.module, site.name, site.written, mark) for site, mark in marked] == [
        (5, "tracker.sorter", "decide", "sorter_module", patch_sites.DEFINED),
        (6, "tracker.sorter", "digest", "here", patch_sites.IMPORTED),
        (7, "tracker.sorter", "kept", "'tracker.sorter.kept'", patch_sites.UNREAD),
    ]


def test_any_monkeypatch_counts_not_only_the_fixture_of_that_name(tmp_path):
    """A fixture that hands its monkeypatch on, and ``MonkeyPatch.context()``,
    place stand-ins as ``monkeypatch`` does."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def in_a_child(monkeypatch):
            return monkeypatch

        def test_one(in_a_child):
            in_a_child.setattr(sorter, "decide", None)
            with pytest.MonkeyPatch.context() as mp:
                mp.setattr(sorter, "digest", None)
    """})
    assert set(_marks(root)) == {("tests/test_a.py", 10, "tracker.sorter", "decide"),
                                 ("tests/test_a.py", 12, "tracker.sorter", "digest")}


def test_a_loop_over_literal_names_is_one_site_per_name(tmp_path):
    """The stand-ins worth checking most: a test that forbids reads sets
    each forbidden name in a loop, and one that misses passes for nothing."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import sorter

        FORBIDDEN = ("decide", "kept")

        def test_one(monkeypatch):
            for name in ("decide", "digest"):
                monkeypatch.setattr(sorter, name, None)
            for name in FORBIDDEN:
                monkeypatch.setattr(sorter, name, None)
            counts = {"digest": 0}
            for name in counts:
                monkeypatch.setattr(sorter, name, None)
    """})
    assert _marks(root) == {
        ("tests/test_a.py", 7, "tracker.sorter", "decide"): patch_sites.DEFINED,
        ("tests/test_a.py", 7, "tracker.sorter", "digest"): patch_sites.IMPORTED,
        ("tests/test_a.py", 9, "tracker.sorter", "decide"): patch_sites.DEFINED,
        ("tests/test_a.py", 9, "tracker.sorter", "kept"): patch_sites.UNREAD,
        ("tests/test_a.py", 12, "tracker.sorter", "digest"): patch_sites.IMPORTED,
    }


def test_values_bound_together_stay_together(tmp_path):
    """``for module, name in ((a, "x"), (b, "y"))`` is two stand-ins, not
    four."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import helpers, sorter

        def test_one(monkeypatch):
            for module, name in ((sorter, "decide"), (helpers, "kept")):
                monkeypatch.setattr(module, name, None)
    """})
    assert _marks(root) == {
        ("tests/test_a.py", 5, "tracker.sorter", "decide"): patch_sites.DEFINED,
        ("tests/test_a.py", 5, "tracker.helpers", "kept"): patch_sites.DEFINED,
    }


def test_a_loop_fixes_its_names_only_where_nothing_else_binds_them(tmp_path):
    """A name a loop binds holds the loop's values inside its body, and after
    the loop where every binding of the name is a loop's. Bound some other
    way as well - assigned after the loop, or again inside its body - it may
    hold either, so the first two stand-ins below are placed on both modules,
    and ``sorter``'s unread ``kept`` fails the check. The tool before ruling
    015 of J4 fixed the name by the loop alone, and placed each on
    ``helpers`` only."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import helpers, sorter

        def test_assigned_after_the_loop(monkeypatch):
            for module in (helpers,):
                pass
            module = sorter
            monkeypatch.setattr(module, "kept", None)

        def test_bound_again_in_the_body(monkeypatch):
            for module in (helpers,):
                module = sorter
                monkeypatch.setattr(module, "kept", None)

        def test_loops_alone(monkeypatch):
            for module in (helpers,):
                monkeypatch.setattr(module, "kept", None)
            for module in (helpers,):
                pass
            monkeypatch.setattr(module, "digest", None)
    """})
    assert _marks(root) == {
        ("tests/test_a.py", 7, "tracker.helpers", "kept"): patch_sites.DEFINED,
        ("tests/test_a.py", 7, "tracker.sorter", "kept"): patch_sites.UNREAD,
        ("tests/test_a.py", 12, "tracker.helpers", "kept"): patch_sites.DEFINED,
        ("tests/test_a.py", 12, "tracker.sorter", "kept"): patch_sites.UNREAD,
        ("tests/test_a.py", 16, "tracker.helpers", "kept"): patch_sites.DEFINED,
        ("tests/test_a.py", 19, "tracker.helpers", "digest"): patch_sites.DEFINED,
    }


def test_nothing_that_reaches_a_stand_in_through_a_parameter_is_placed(tmp_path):
    """Ruling 015 of J4: what a parameter holds is settled by whoever calls
    the function - for a test or a fixture, pytest, from the test that runs -
    so the tool does not follow it. Each stand-in below can land on
    ``sorter.kept``, which ``sorter`` never reads, and each is not placed.

    Review 5's forms, each of which the tool before the ruling placed on
    ``helpers`` alone, with the check passing: a conftest fixture's
    parameter that the test's own file overrides, or that a mark on the test
    gives (both at ``conftest.py:11``); a fixture that ``pytest_generate_tests``
    overrides; an inherited test whose subclass overrides its fixture; and a
    helper module's function, called from another file or through another
    name. The forms it followed before them: a ``parametrize`` mark's values,
    in pairs, in ``pytest.param``, held in a name or on the test's class; a
    mark that hands its fixture values (``indirect``), into a fixture with no
    ``params``, one with ``params`` of its own, or one that places the
    stand-in on ``request.param``; ``importlib`` given ``request.param``; a
    fixture imported from a helper module; a helper's argument in its own
    file; and review 4's nearest conftest, whose fixture shadows the root's.
    And three it never placed: pytest's own ``tmp_path``, a lambda's
    parameter, and a parameter a loop may rebind, which is not placed for
    the parameter and is a site on ``helpers`` for the loop."""
    root = _repository(tmp_path, {**SORTER, "tests/conftest.py": """
        import pytest

        from tracker import helpers

        @pytest.fixture
        def mod():
            return helpers

        @pytest.fixture
        def patched(monkeypatch, mod):
            monkeypatch.setattr(mod, "kept", None)

        @pytest.fixture
        def thing():
            return None
    """, "tests/test_override.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def mod():
            return sorter

        def test_a_file_overrides_a_conftest_fixtures_parameter(patched):
            pass
    """, "tests/test_direct.py": """
        import pytest

        from tracker import sorter

        @pytest.mark.parametrize("mod", [sorter])
        def test_a_mark_overrides_a_conftest_fixtures_parameter(patched):
            pass
    """, "tests/test_gen.py": """
        import pytest

        from tracker import helpers, sorter

        @pytest.fixture
        def target():
            return helpers

        def pytest_generate_tests(metafunc):
            if "target" in metafunc.fixturenames:
                metafunc.parametrize("target", [sorter])

        def test_generated(monkeypatch, target):
            monkeypatch.setattr(target, "kept", None)
    """, "tests/test_inherit.py": """
        import pytest

        from tracker import helpers, sorter

        class Base:
            @pytest.fixture
            def target(self):
                return helpers

            def test_inherited(self, monkeypatch, target):
                monkeypatch.setattr(target, "kept", None)

        class TestChild(Base):
            @pytest.fixture
            def target(self):
                return sorter
    """, "tests/patching.py": """
        from tracker import helpers, sorter

        def forbid(mp, module):
            mp.setattr(module, "kept", None)

        def forbid_in_helpers(mp):
            forbid(mp, helpers)

        def forbid_through_a_name(mp, module):
            mp.setattr(module, "kept", None)

        def forbid_both(mp):
            forbid_through_a_name(mp, helpers)
            put = forbid_through_a_name
            put(mp, sorter)
    """, "tests/test_cross.py": """
        from tests import patching
        from tracker import sorter

        def test_a_helper_called_from_another_file(monkeypatch):
            patching.forbid(monkeypatch, sorter)
    """, "tests/helping.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def given():
            return sorter
    """, "tests/sub/conftest.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def thing():
            return sorter
    """, "tests/sub/test_d.py": """
        def test_the_nearest_conftest_gives_the_fixture(monkeypatch, thing):
            monkeypatch.setattr(thing, "kept", None)
    """, "tests/test_a.py": """
        import importlib

        import pytest

        from tests.helping import given
        from tracker import helpers, sorter

        MODULES = [sorter]

        @pytest.fixture
        def chosen(request):
            return request.param

        @pytest.fixture(params=[helpers])
        def picked(request):
            return request.param

        @pytest.fixture(params=[helpers])
        def placing(request, monkeypatch):
            monkeypatch.setattr(request.param, "kept", None)

        @pytest.fixture(params=["sorter"])
        def by_name(request, monkeypatch):
            monkeypatch.setattr(importlib.import_module(f"tracker.{request.param}"), "kept", None)

        @pytest.mark.parametrize("module, name", [(sorter, "kept"), pytest.param(helpers, "kept", id="h")])
        def test_pairs(monkeypatch, module, name):
            monkeypatch.setattr(module, name, None)

        @pytest.mark.parametrize("module", MODULES)
        def test_held_in_a_name(monkeypatch, module):
            monkeypatch.setattr(module, "kept", None)

        @pytest.mark.parametrize("module", [sorter])
        class TestMarked:
            def test_on_the_class(self, monkeypatch, module):
                monkeypatch.setattr(module, "kept", None)

        @pytest.mark.parametrize("chosen", [sorter], indirect=True)
        def test_indirect(monkeypatch, chosen):
            monkeypatch.setattr(chosen, "kept", None)

        @pytest.mark.parametrize("picked", [sorter], indirect=True)
        def test_indirect_over_params(monkeypatch, picked):
            monkeypatch.setattr(picked, "kept", None)

        @pytest.mark.parametrize("placing", [sorter], indirect=True)
        def test_indirect_into_a_fixture_that_places_a_stand_in(placing):
            pass

        def test_a_fixture_imported_from_a_helper(monkeypatch, given):
            monkeypatch.setattr(given, "kept", None)

        def _counting(monkeypatch, module, name):
            monkeypatch.setattr(module, name, None)

        def test_a_helpers_argument(monkeypatch):
            _counting(monkeypatch, sorter, "kept")

        def test_pytests_own_fixture(monkeypatch, tmp_path):
            monkeypatch.setattr(tmp_path, "size", 1, raising=False)

        def test_a_lambdas_parameter(monkeypatch):
            (lambda module: monkeypatch.setattr(module, "kept", None))(sorter)

        def _forbid(monkeypatch, module, rebind):
            if rebind:
                for module in (helpers,):
                    pass
            monkeypatch.setattr(module, "kept", None)

        def test_a_parameter_a_loop_may_rebind(monkeypatch):
            _forbid(monkeypatch, sorter, False)
    """})
    marked, unplaced = patch_sites.stand_ins(root)
    assert [(site.file, site.line, site.module, site.name, mark) for site, mark in marked] == [
        ("tests/test_a.py", 70, "tracker.helpers", "kept", patch_sites.DEFINED),
    ]
    assert [(one.file, one.line, one.written) for one in unplaced] == [
        ("tests/conftest.py", 11, "mod"),
        ("tests/patching.py", 4, "module"), ("tests/patching.py", 10, "module"),
        ("tests/sub/test_d.py", 2, "thing"),
        ("tests/test_a.py", 20, "request.param"), ("tests/test_a.py", 24, "importlib.import_module(f'tracker.{request.param}')"),
        ("tests/test_a.py", 28, "module"), ("tests/test_a.py", 32, "module"), ("tests/test_a.py", 37, "module"),
        ("tests/test_a.py", 41, "chosen"), ("tests/test_a.py", 45, "picked"), ("tests/test_a.py", 52, "given"),
        ("tests/test_a.py", 55, "module"), ("tests/test_a.py", 61, "tmp_path"), ("tests/test_a.py", 64, "module"),
        ("tests/test_a.py", 70, "module"),
        ("tests/test_gen.py", 14, "target"), ("tests/test_inherit.py", 11, "target"),
    ]
    assert patch_sites.check(root)[0] is False


def test_a_module_picked_in_a_loop_over_literals_is_placed(tmp_path):
    """The remedy for a fixture or a helper that chooses between modules
    (ruling 015 of J4): pick one in a ``for`` over the modules, named as
    imports, or name the module in the helper itself, as
    ``tests/test_fsio.py``'s ``flusher`` and ``tests/test_store.py``'s
    ``_counting_keys`` do. A module an import call names with a literal is
    followed too."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import importlib

        import pytest

        @pytest.fixture(params=["helpers", "sorter"])
        def either(request, monkeypatch):
            import tracker.helpers as helpers_module
            import tracker.sorter as sorter_module

            for module in (helpers_module, sorter_module):
                if module.__name__ == f"tracker.{request.param}":
                    break
            monkeypatch.setattr(module, "digest", None)
            return module

        def _counting(monkeypatch):
            from tracker import sorter

            monkeypatch.setattr(sorter, "decide", None)

        def test_one(either, monkeypatch):
            _counting(monkeypatch)
            monkeypatch.setattr(importlib.import_module("tracker.helpers"), "kept", None)
    """})
    assert _marks(root) == {
        ("tests/test_a.py", 13, "tracker.helpers", "digest"): patch_sites.DEFINED,
        ("tests/test_a.py", 13, "tracker.sorter", "digest"): patch_sites.IMPORTED,
        ("tests/test_a.py", 19, "tracker.sorter", "decide"): patch_sites.DEFINED,
        ("tests/test_a.py", 23, "tracker.helpers", "kept"): patch_sites.DEFINED,
    }


def test_a_tool_imported_by_its_bare_name_is_reported_by_its_dotted_one(tmp_path):
    root = _repository(tmp_path, {"tools/mapper.py": "ROOT = '.'\n", "tests/test_mapper.py": """
        import sys
        from pathlib import Path

        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

        import mapper  # noqa: E402

        def test_one(monkeypatch, tmp_path):
            monkeypatch.setattr(mapper, "ROOT", tmp_path)
    """})
    assert _marks(root) == {("tests/test_mapper.py", 9, "tools.mapper", "ROOT"): patch_sites.DEFINED}


def test_stand_ins_on_things_outside_the_repository_or_on_no_module_are_not_listed(tmp_path):
    """A stand-in on ``sys``, on a class or an instance of one, on an object
    a builtin or an outside call made, or on a constant that is not a string
    written at the call lands on that object whoever reads it: there is no
    namespace to miss. What one of pytest's own fixtures gives reaches the
    test through a parameter, and is not placed (ruling 015 of J4)."""
    root = _repository(tmp_path, {**SORTER, **HOLDERS, "tests/test_a.py": """
        import os
        import sys
        from pathlib import Path

        from tracker import holders
        from tracker.helpers import Shape

        class Local:
            pass

        def test_one(monkeypatch, tmp_path):
            monkeypatch.setattr(sys, "argv", [])
            monkeypatch.setattr("sys.stdin", None)
            monkeypatch.setattr(Path, "home", lambda: tmp_path)
            monkeypatch.setattr(Shape, "size", 1, raising=False)
            monkeypatch.setattr(type(tmp_path), "exists", lambda self: True)
            monkeypatch.setattr(os, "sep", "/")
            monkeypatch.setattr(holders.Holder, "module", None)
            monkeypatch.setattr("tracker.holders.Holder.module", None)
            monkeypatch.setattr(holders.Holder(), "module", None)
            monkeypatch.setattr(Local(), "size", 1, raising=False)
            monkeypatch.setattr(holders.LOG, "level", 10)
            monkeypatch.setattr(None, "size", 1, raising=False)
    """})
    assert patch_sites.stand_ins(root) == ([], [])


def test_a_target_the_tool_cannot_work_out_fails_the_check_as_not_placed(tmp_path):
    """A module picked out of a list, or a name made at run time, is not
    followed, and is said rather than skipped."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import helpers, sorter

        def test_one(monkeypatch):
            modules = [sorter, helpers]
            monkeypatch.setattr(modules[0], "decide", None)
            monkeypatch.setattr(sorter, "dec" + "ide", None)
            monkeypatch.setattr(made_somewhere(), "decide", None)
    """})
    marked, unplaced = patch_sites.stand_ins(root)
    assert marked == []
    assert [(one.line, one.written) for one in unplaced] == [(5, "modules[0]"), (6, "sorter"), (7, "made_somewhere()")]
    ok, said = patch_sites.check(root)
    assert not ok and len(said) == 3
    assert said[1] == ("tests/test_a.py:6: setattr(sorter, ...) cannot be placed: which name of tracker.sorter it "
                       "replaces is not written out. Name the module and the name as an import, an alias or a literal.")


def test_no_way_of_writing_a_module_drops_a_stand_in_out_of_the_check(tmp_path):
    """Each stand-in below lands on ``sorter.kept``, which ``sorter`` never
    reads. These are sites, unread: the plain form, an annotated alias,
    ``sys.modules.get``, a helper module's alias read through it or imported
    from it, and the string form held in a name, in a helper module's
    constant, in a loop over literals or made by an f-string. These are not
    placed: a module stored by an unpacking, a walrus, ``with ... as`` or
    ``except ... as``, or given by a call to a function of the file or of a
    helper module, to a lambda, to a class's method or to ``getattr``, and a
    class's attribute. None is taken for no module, so ``check`` names all
    twenty in ``test_a``.

    ``test_b`` holds review 3's forms, and none is placed: a module a
    ``parametrize`` mark gives, alone or together with its name, or a fixture
    gives, where the fixture is imported from a helper module, assigned from
    one, defined in the test's class or defined nowhere (each reaches the
    stand-in through a parameter, which the tool does not follow: ruling 015
    of J4, which made the first five of these sites not placed); a top-level
    name that something rebinds (a test file's own name a fixture rebinds
    with ``global``, a helper module's name a conftest assigns, whether its
    own value is ``None`` or a module, and one a fixture's stand-in
    replaces); and a ``setattr`` not called where it is written (bound to a
    name, or handed to ``functools.partial``).

    ``test_c`` and ``sub/test_d`` hold review 4's, in a repository whose
    ``tests/`` and ``tools/`` have no ``__init__.py``, as the real one's do.
    These are sites, unread: a module reached through the folder
    (``tests.wired`` after ``import tests.wired``, and ``tools.mapper``).
    These are not placed: the folder itself, and a name in it that is none
    of its modules; a helper module's name that a conftest rebinds through
    the folder, read through the folder or through the module; a local that
    a nested function rebinds with ``nonlocal``, read in either function; a
    fixture, whether the nearest conftest on the test's own path gives it
    (the one in ``tests/`` gives ``None`` under the same name) or only a
    conftest off that path does; and a ``setattr`` called on a class
    (``MonkeyPatch``, ``pytest.MonkeyPatch``, or a class of the file), whose
    first argument is the instance, and on one the tool does not see as a
    class (``type(patcher)``, ``patcher.__class__``), whose target then sits
    where a name should be. The tool before review 4 passed
    thirteen of these unlisted: the five reached through the folder, which
    it took for something outside the repository; the name rebound through
    it, which it placed on its first value; the nonlocal read in the outer
    function and the nearest conftest's fixture, which it took for
    ``None``; and the five called on a class, whose instance it took for the
    target."""
    root = _repository(tmp_path, {**SORTER, "tests/aliases.py": """
        from tracker import sorter

        THE_SORTER = sorter
        TARGET = "tracker.sorter.kept"

        def the_sorter():
            return sorter
    """, "tests/test_a.py": """
        import contextlib
        import sys
        import types

        import tracker
        from tests import aliases
        from tests.aliases import THE_SORTER, the_sorter
        from tracker import sorter

        TARGET = "tracker.sorter.kept"
        get = lambda: sorter

        def _the_sorter():
            return sorter

        class Holder:
            module = sorter

            @staticmethod
            def give():
                return sorter

        def test_annotated(monkeypatch):
            module: types.ModuleType = sorter
            monkeypatch.setattr(module, "kept", None)

        def test_unpacked(monkeypatch):
            module, name = sorter, "kept"
            monkeypatch.setattr(module, name, None)

        def test_helper(monkeypatch):
            monkeypatch.setattr(_the_sorter(), "kept", None)

        def test_getattr(monkeypatch):
            monkeypatch.setattr(getattr(tracker, "sorter"), "kept", None)

        def test_walrus(monkeypatch):
            if (module := sorter):
                monkeypatch.setattr(module, "kept", None)

        def test_with(monkeypatch):
            with contextlib.nullcontext(sorter) as module:
                monkeypatch.setattr(module, "kept", None)

        def test_except(monkeypatch):
            try:
                raise LookupError
            except LookupError as module:
                monkeypatch.setattr(module, "kept", None)

        def test_plain(monkeypatch):
            monkeypatch.setattr(sorter, "kept", None)

        def test_string_by_name(monkeypatch):
            monkeypatch.setattr(TARGET, None)

        def test_string_in_a_loop(monkeypatch):
            for target in ("tracker.sorter.kept",):
                monkeypatch.setattr(target, None)

        def test_string_made_by_an_f_string(monkeypatch):
            monkeypatch.setattr(f"tracker.{'sorter'}.kept", None)

        def test_helper_module_alias(monkeypatch):
            monkeypatch.setattr(aliases.THE_SORTER, "kept", None)

        def test_helper_module_alias_imported(monkeypatch):
            monkeypatch.setattr(THE_SORTER, "kept", None)

        def test_helper_module_function(monkeypatch):
            monkeypatch.setattr(the_sorter(), "kept", None)

        def test_helper_module_function_through_it(monkeypatch):
            monkeypatch.setattr(aliases.the_sorter(), "kept", None)

        def test_helper_module_string(monkeypatch):
            monkeypatch.setattr(aliases.TARGET, None)

        def test_lambda(monkeypatch):
            monkeypatch.setattr(get(), "kept", None)

        def test_sys_modules_get(monkeypatch):
            monkeypatch.setattr(sys.modules.get("tracker.sorter"), "kept", None)

        def test_class_attribute(monkeypatch):
            monkeypatch.setattr(Holder.module, "kept", None)

        def test_static_method(monkeypatch):
            monkeypatch.setattr(Holder.give(), "kept", None)
    """, "tests/fixtures.py": """
        import pytest

        from tracker import helpers, sorter

        THE = None
        FILLED = helpers

        @pytest.fixture
        def the_module():
            return sorter

        @pytest.fixture
        def other_module():
            return sorter
    """, "tests/seams.py": """
        ENGINE = None
    """, "tests/conftest.py": """
        import pytest

        import tests.wired
        from tests import fixtures
        from tracker import sorter

        fixtures.THE = sorter
        fixtures.FILLED = sorter

        @pytest.fixture(autouse=True)
        def wire():
            tests.wired.ENGINE = sorter

        @pytest.fixture
        def thing():
            return None
    """, "tests/wired.py": """
        from tracker import helpers, sorter

        ENGINE = helpers
    """, "tools/mapper.py": """
        ROOT = "."
    """, "tests/sub/conftest.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def thing():
            return sorter
    """, "tests/elsewhere/conftest.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def beside():
            return sorter
    """, "tests/sub/test_d.py": """
        def test_the_nearest_conftest_gives_the_fixture(monkeypatch, thing):
            monkeypatch.setattr(thing, "kept", None)

        def test_a_conftest_off_the_path_gives_nothing(monkeypatch, beside):
            monkeypatch.setattr(beside, "kept", None)
    """, "tests/test_c.py": """
        import pytest
        from pytest import MonkeyPatch

        import tests.wired
        import tools.mapper
        from tests import wired
        from tracker import sorter

        class Patcher:
            def setattr(self, *args):
                return args

        def test_through_the_folder(monkeypatch):
            monkeypatch.setattr(tests.wired, "sorter", None)

        def test_through_the_tools_folder(monkeypatch):
            monkeypatch.setattr(tools.mapper, "nothing_reads_this", None, raising=False)

        def test_the_folder_itself(monkeypatch):
            monkeypatch.setattr(tests, "nothing_here", None, raising=False)

        def test_a_name_in_the_folder_that_is_no_module_of_it(monkeypatch):
            monkeypatch.setattr(tests.nothing, "kept", None, raising=False)

        def test_through_the_folder_to_a_name_rebound_through_it(monkeypatch):
            monkeypatch.setattr(tests.wired.ENGINE, "kept", None)

        def test_a_name_rebound_through_the_folder(monkeypatch):
            monkeypatch.setattr(wired.ENGINE, "kept", None)

        def test_a_local_a_nested_function_rebinds(monkeypatch):
            module = None

            def fill():
                nonlocal module
                module = sorter

            fill()
            monkeypatch.setattr(module, "kept", None)

        def test_a_local_rebound_in_the_function_that_declares_it(monkeypatch):
            module = None

            def fill():
                nonlocal module
                module = sorter
                monkeypatch.setattr(module, "kept", None)

            fill()

        def test_called_on_the_class(monkeypatch):
            MonkeyPatch.setattr(monkeypatch, sorter, "kept", None)

        def test_called_on_the_class_through_pytest(monkeypatch):
            pytest.MonkeyPatch.setattr(monkeypatch, sorter, "kept", None)

        def test_called_on_a_class_of_the_file(monkeypatch):
            Patcher.setattr(monkeypatch, sorter, "kept", None)

        def test_called_on_a_class_the_tool_does_not_see_as_one():
            patcher = pytest.MonkeyPatch()
            type(patcher).setattr(patcher, sorter, "kept", None)
            patcher.__class__.setattr(patcher, "tracker.sorter.kept", None)
    """, "tests/test_b.py": """
        import functools

        import pytest

        from tests import fixtures, seams
        from tests.fixtures import the_module
        from tracker import sorter

        other_module = fixtures.other_module
        MOD = None

        @pytest.fixture(autouse=True)
        def bind(monkeypatch):
            global MOD
            MOD = sorter
            monkeypatch.setattr(seams, "ENGINE", sorter)

        @pytest.mark.parametrize("module", [sorter])
        def test_parametrize(monkeypatch, module):
            monkeypatch.setattr(module, "kept", None)

        @pytest.mark.parametrize("module, name", [(sorter, "kept")])
        def test_parametrize_together(monkeypatch, module, name):
            monkeypatch.setattr(module, name, None)

        def test_fixture_imported_from_a_helper(monkeypatch, the_module):
            monkeypatch.setattr(the_module, "kept", None)

        def test_fixture_assigned_from_a_helper(monkeypatch, other_module):
            monkeypatch.setattr(other_module, "kept", None)

        class TestInAClass:
            @pytest.fixture
            def held(self):
                return sorter

            def test_fixture_in_a_class(self, monkeypatch, held):
                monkeypatch.setattr(held, "kept", None)

        def test_fixture_nobody_defines(monkeypatch, unheard_of):
            monkeypatch.setattr(unheard_of, "kept", None)

        def test_own_name_rebound_by_global(monkeypatch):
            monkeypatch.setattr(MOD, "kept", None)

        def test_helper_placeholder_stored_from_outside(monkeypatch):
            monkeypatch.setattr(fixtures.THE, "kept", None)

        def test_helper_alias_stored_from_outside(monkeypatch):
            monkeypatch.setattr(fixtures.FILLED, "kept", None)

        def test_helper_placeholder_replaced_by_a_stand_in(monkeypatch):
            monkeypatch.setattr(seams.ENGINE, "kept", None)

        def test_setattr_called_through_a_name(monkeypatch):
            put = monkeypatch.setattr
            put(sorter, "kept", None)

        def test_setattr_in_a_partial(monkeypatch):
            functools.partial(monkeypatch.setattr, sorter)("kept", None)
    """})
    marked, unplaced = patch_sites.stand_ins(root)
    assert [(site.line, site.module, site.name, site.written, mark) for site, mark in marked
            if site.file == "tests/test_a.py"] == [
        (25, "tracker.sorter", "kept", "module", patch_sites.UNREAD),
        (52, "tracker.sorter", "kept", "sorter", patch_sites.UNREAD),
        (55, "tracker.sorter", "kept", "TARGET", patch_sites.UNREAD),
        (59, "tracker.sorter", "kept", "target", patch_sites.UNREAD),
        (62, "tracker.sorter", "kept", "f\"tracker.{'sorter'}.kept\"", patch_sites.UNREAD),
        (65, "tracker.sorter", "kept", "aliases.THE_SORTER", patch_sites.UNREAD),
        (68, "tracker.sorter", "kept", "THE_SORTER", patch_sites.UNREAD),
        (77, "tracker.sorter", "kept", "aliases.TARGET", patch_sites.UNREAD),
        (83, "tracker.sorter", "kept", "sys.modules.get('tracker.sorter')", patch_sites.UNREAD),
    ]
    assert [(one.line, one.written) for one in unplaced if one.file == "tests/test_a.py"] == [
        (29, "module"), (32, "_the_sorter()"), (35, "getattr(tracker, 'sorter')"),
        (39, "module"), (43, "module"), (49, "module"),
        (71, "the_sorter()"), (74, "aliases.the_sorter()"), (80, "get()"),
        (86, "Holder.module"), (89, "Holder.give()"),
    ]
    assert [(site.line, site.module, site.name, site.written, mark) for site, mark in marked
            if site.file == "tests/test_b.py"] == [
        (16, "tests.seams", "ENGINE", "seams", patch_sites.DEFINED),
    ]
    assert [(one.line, one.written, one.called) for one in unplaced if one.file == "tests/test_b.py"] == [
        (20, "module", True), (24, "module", True), (27, "the_module", True), (30, "other_module", True),
        (38, "held", True), (41, "unheard_of", True),
        (44, "MOD", True), (47, "fixtures.THE", True), (50, "fixtures.FILLED", True),
        (53, "seams.ENGINE", True), (56, "monkeypatch.setattr", False), (60, "monkeypatch.setattr", False),
    ]
    assert [(site.file, site.line, site.module, site.name, site.written, mark) for site, mark in marked
            if site.file not in ("tests/test_a.py", "tests/test_b.py")] == [
        ("tests/test_c.py", 14, "tests.wired", "sorter", "tests.wired", patch_sites.UNREAD),
        ("tests/test_c.py", 17, "tools.mapper", "nothing_reads_this", "tools.mapper", patch_sites.UNREAD),
    ]
    assert [(one.file, one.line, one.written) for one in unplaced
            if one.file not in ("tests/test_a.py", "tests/test_b.py")] == [
        ("tests/sub/test_d.py", 2, "thing"), ("tests/sub/test_d.py", 5, "beside"),
        ("tests/test_c.py", 20, "tests"), ("tests/test_c.py", 23, "tests.nothing"),
        ("tests/test_c.py", 26, "tests.wired.ENGINE"), ("tests/test_c.py", 29, "wired.ENGINE"),
        ("tests/test_c.py", 39, "module"), ("tests/test_c.py", 47, "module"),
        ("tests/test_c.py", 52, "MonkeyPatch.setattr"), ("tests/test_c.py", 55, "pytest.MonkeyPatch.setattr"),
        ("tests/test_c.py", 58, "Patcher.setattr"), ("tests/test_c.py", 62, "type(patcher).setattr"),
        ("tests/test_c.py", 63, "patcher.__class__.setattr"),
    ]
    ok, said = patch_sites.check(root)
    assert not ok and len(said) == 47
    assert ("tests/test_c.py:20: setattr(tests, ...) cannot be placed: tests is a folder with no __init__.py, not a "
            "module. Name the module and the name as an import, an alias or a literal.") in said
    assert ("tests/test_b.py:60: monkeypatch.setattr cannot be placed: it is not called where it is written, so what "
            "it replaces is not written out. Call it where it is written.") in said
    assert ("tests/test_c.py:58: Patcher.setattr cannot be placed: it is called on a class, so its first argument "
            "is the instance and what it replaces comes after. Call it on the instance.") in said
    assert said[-1] == ("tests/test_c.py:63: patcher.__class__.setattr cannot be placed: what it replaces is not "
                        "an attribute name the tool reads, so it may be called on a class, with the instance first "
                        "and the target in the name's place. Call it on the instance, with the name as a string.")


def test_a_submodule_something_stores_over_is_not_followed_through_its_package(tmp_path):
    """F5.3 of review 5: ``import a.b as c``, ``from a import b``, ``a.b``
    and the string ``"a.b.name"`` each reach ``b`` as an attribute of ``a``,
    so a file that stores over that attribute, or a package that binds the
    name itself, decides what they hold. Each stand-in on ``kept`` below but
    the last three lands on ``sorter.kept``, which ``sorter`` never reads,
    and each is not placed; the tool before the review placed each on the
    submodule, which reads ``kept``, and passed it. A stand-in on the
    package's attribute stores over it too, and is a site on the package. A
    submodule nothing stores over is still followed, in each of the three
    forms."""
    module = """
        def kept(path):
            return path

        def decide(path):
            return kept(path)
    """
    root = _repository(tmp_path, {**SORTER, "tracker/other.py": module, "tracker/third.py": module,
                                  "tracker/fourth.py": module, "tracker/untouched.py": module,
                                  "tests/wired.py": module, "tracker/pkg/inner.py": module,
                                  "tracker/pkg/__init__.py": "from tracker import sorter as inner\n",
                                  "tests/test_a.py": """
        import tests
        import tracker
        import tracker.third
        from tracker import sorter

        tracker.other = sorter
        tracker.third = sorter
        tests.wired = sorter

        import tracker.other as again  # noqa: E402
        from tests import wired  # noqa: E402
        from tracker import other, untouched  # noqa: E402
        from tracker.pkg import inner  # noqa: E402

        def test_import_as_after_a_store(monkeypatch):
            monkeypatch.setattr(again, "kept", None)

        def test_from_import_after_a_store(monkeypatch):
            monkeypatch.setattr(other, "kept", None)

        def test_the_attribute_after_a_store(monkeypatch):
            monkeypatch.setattr(tracker.third, "kept", None)

        def test_the_string_form_after_a_store(monkeypatch):
            monkeypatch.setattr("tracker.third.kept", None)

        def test_a_folders_module_stored_over(monkeypatch):
            monkeypatch.setattr(wired, "kept", None)

        def test_a_package_that_binds_its_submodules_name(monkeypatch):
            monkeypatch.setattr(inner, "kept", None)

        def test_a_stand_in_on_the_package_attribute(monkeypatch):
            monkeypatch.setattr(tracker, "fourth", sorter)
            monkeypatch.setattr(tracker.fourth, "kept", None)

        def test_a_submodule_nothing_stores_over(monkeypatch):
            monkeypatch.setattr(untouched, "kept", None)
            monkeypatch.setattr(tracker.untouched, "kept", None)
            monkeypatch.setattr("tracker.untouched.kept", None)
    """})
    marked, unplaced = patch_sites.stand_ins(root)
    assert [(site.line, site.module, site.name, mark) for site, mark in marked] == [
        (34, "tracker", "fourth", patch_sites.UNREAD),
        (38, "tracker.untouched", "kept", patch_sites.DEFINED),
        (39, "tracker.untouched", "kept", patch_sites.DEFINED),
        (40, "tracker.untouched", "kept", patch_sites.DEFINED),
    ]
    assert [(one.line, one.written) for one in unplaced] == [
        (16, "again"), (19, "other"), (22, "tracker.third"), (25, "'tracker.third.kept'"),
        (28, "wired"), (31, "inner"), (35, "tracker.fourth"),
    ]


def test_a_value_is_taken_for_no_module_only_where_the_tool_proves_it_is_none(tmp_path):
    """No module is something the tool proves, never its fallback. Each
    stand-in below but the last two can land on ``sorter.kept``. A repository
    module's alias, followed into that module, is a site, and so is the object
    form with ``value=``. These are not placed: an operand of ``or``, an
    instance's or a class's attribute, an attribute of what an outside call
    made, what a method gives, a string form built at run time, what ``next``,
    ``eval`` or ``globals()`` gives, a lambda called where it is written, a
    name the module rebinds in a function or never binds, or binds to a
    constant other than a string (a placeholder another module may fill);
    ``x.__class__`` and a function, which a property or a decorator can make
    anything; and a string in the three-argument form, which names no module
    there."""
    root = _repository(tmp_path, {**SORTER, **HOLDERS, "tests/test_a.py": """
        from types import SimpleNamespace

        from tracker import helpers, holders, sorter

        class Local:
            module = sorter

        def test_one(monkeypatch, request):
            monkeypatch.setattr(holders.THE, "kept", None)
            monkeypatch.setattr("tracker.holders.THE.kept", None)
            monkeypatch.setattr(sorter, "kept", value=None)
            monkeypatch.setattr(sorter or helpers, "kept", None)
            monkeypatch.setattr(Local().module, "kept", None)
            monkeypatch.setattr(holders.Holder.module, "kept", None)
            monkeypatch.setattr(SimpleNamespace(module=sorter).module, "kept", None)
            monkeypatch.setattr({"s": sorter}.get("s"), "kept", None)
            monkeypatch.setattr(request.getfixturevalue("sorter_module"), "kept", None)
            monkeypatch.setattr("tracker.sorter." + "kept", None)
            monkeypatch.setattr("tracker.{}.kept".format("sorter"), None)
            monkeypatch.setattr(next(iter((sorter,))), "kept", None)
            monkeypatch.setattr(eval("sorter"), "kept", None)
            monkeypatch.setattr(globals().get("sorter"), "kept", None)
            monkeypatch.setattr((lambda: sorter)(), "kept", None)
            monkeypatch.setattr(holders.LATER, "kept", None)
            monkeypatch.setattr(holders.missing, "kept", None)
            monkeypatch.setattr(holders.NOTHING, "kept", None)
            monkeypatch.setattr(Local().__class__, "size", 1, raising=False)
            monkeypatch.setattr(helpers.digest, "__defaults__", None)
            monkeypatch.setattr("tracker.sorter", "kept", None)
    """})
    marked, unplaced = patch_sites.stand_ins(root)
    assert [(site.line, site.module, site.name, site.written, mark) for site, mark in marked] == [
        (9, "tracker.sorter", "kept", "holders.THE", patch_sites.UNREAD),
        (10, "tracker.sorter", "kept", "'tracker.holders.THE.kept'", patch_sites.UNREAD),
        (11, "tracker.sorter", "kept", "sorter", patch_sites.UNREAD),
    ]
    assert [one.line for one in unplaced] == list(range(12, 30))
    assert unplaced[-1].why == 'a string names a module only in the form setattr("module.name", value)'
    ok, said = patch_sites.check(root)
    assert not ok and len(said) == 21


#: The kinds of value that pass a stand-in unlisted as no module, and the
#: one value of the first.
NO_MODULE_KINDS = {"THING", "CLASS", "INSTANCE", "_A_THING"}


#: The one kind of value a lookup of a dotted name may take for outside
#: the repository, which passes a stand-in unlisted too.
OUTSIDE_KIND = ({"OUTSIDE"}, ("outside",), ("outside",))


def _built(source: str, kinds=NO_MODULE_KINDS, spelled=("thing", "instance"),
           written=("thing", "class", "instance")) -> tuple[set[str | None], list[str], list[int]]:
    """Where ``source`` builds a value of one of ``kinds``: the functions that
    use one of the kinds' names other than to compare against it (None for
    the top level, outside the lines that name the kinds and ``_NO_MODULE``),
    the strings of ``spelled`` wherever they are spelled outside the lines
    that name the kinds, and the lines of any value tuple written with a
    string of ``written`` in place of a kind's name."""
    tree = ast.parse(source)
    parent = {child: node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    naming = {id(node) for statement in tree.body if isinstance(statement, ast.Assign)
              and any(isinstance(target, ast.Name) and target.id in ("_A_THING", "_NO_MODULE")
                      or isinstance(target, ast.Tuple) and {"THING", "CLASS"} & {one.id for one in target.elts}
                      for target in statement.targets)
              for node in ast.walk(statement)}
    functions: set[str | None] = set()
    for node in ast.walk(tree):
        if (isinstance(node, ast.Name) and node.id in kinds and isinstance(node.ctx, ast.Load)
                and id(node) not in naming and not isinstance(parent[node], ast.Compare)):
            holder = parent[node]
            while holder in parent and not isinstance(holder, (ast.FunctionDef, ast.AsyncFunctionDef)):
                holder = parent[holder]
            functions.add(getattr(holder, "name", None))
    found = [node.value for node in ast.walk(tree) if isinstance(node, ast.Constant)
             and node.value in spelled and id(node) not in naming]
    tuples = [node.lineno for node in ast.walk(tree) if isinstance(node, ast.Tuple) and node.elts
              and isinstance(node.elts[0], ast.Constant) and node.elts[0].value in written
              and id(node) not in naming]
    return functions, found, tuples


def test_only_one_function_of_the_tool_concludes_that_a_value_is_no_module():
    """Ruling 009 of J4: "no module" has one producer, ``_no_module``, so no
    other path can reach it by a fallback. Everywhere else a no-module kind
    is only compared against, or listed in ``_NO_MODULE``, and no value is
    written with a kind's string in place of its name."""
    source = Path(patch_sites.__file__).read_text(encoding="utf-8")
    assert _built(source) == ({"_no_module"}, [], [])
    # The pin sees each way back to a second producer.
    assert _built(source + "\ndef elsewhere():\n    return [_A_THING]\n")[0] == {"_no_module", "elsewhere"}
    assert _built(source + "\nNOTHING = ('thing', None)\n")[1:] == (["thing"], [source.count("\n") + 2])


def test_only_the_lookup_of_a_dotted_name_takes_a_value_for_outside_the_repository(tmp_path):
    """F4.1 of review 4: outside the repository passes a stand-in unlisted, so
    it has one producer too, ``_Suite.module``, which looks in the index and
    its folders first. ``tests`` and ``tools`` have no ``__init__.py``, and
    the tool before review 4 took ``import tests.wired`` for outside, which
    passed a stand-in on a module of the suite unlisted. Neither folder has
    an ``__init__.py`` in the made-up repository below either: no dotted name
    of its index, and no folder of one, is taken for outside."""
    source = Path(patch_sites.__file__).read_text(encoding="utf-8")
    assert _built(source, *OUTSIDE_KIND) == ({"module"}, [], [])
    assert _built(source + "\ndef elsewhere(dotted):\n    return (OUTSIDE, dotted)\n",
                  *OUTSIDE_KIND)[0] == {"module", "elsewhere"}
    assert _built(source + "\nFAR = ('outside', None)\n", *OUTSIDE_KIND)[1:] == (
        ["outside"], [source.count("\n") + 2])
    root = _repository(tmp_path, {**SORTER, "tests/children.py": "SEAM = None\n",
                                  "tests/sub/deeper.py": "", "tools/mapper.py": "", "tests/test_a.py": ""})
    assert not (root / "tests" / "__init__.py").exists() and not (root / "tools" / "__init__.py").exists()
    suite = patch_sites._Suite(root)
    assert suite.packages == {"tests", "tests.sub", "tools"}
    assert [dotted for dotted in [*suite.index, *suite.packages]
            if suite.module(dotted)[0] == patch_sites.OUTSIDE] == []
    assert suite.module("tests") == (patch_sites.PACKAGE, "tests")
    assert suite.attribute(suite.module("tests"), "children", "tests.children") == [
        (patch_sites.MODULE, "tests.children")]
    assert suite.attribute(suite.module("tests"), "nothing", "tests.nothing") == [
        (patch_sites.UNKNOWN, "tests.nothing")]
    assert suite.module("pytest") == (patch_sites.OUTSIDE, "pytest")


# -------------------------------------------------------------- the backstop ----


def test_a_stand_in_written_in_a_form_the_tool_does_not_read_fails_the_check(tmp_path):
    """Ruling 012 of J4: the forms the tool reads are a list, and a test can
    write a stand-in in one off it. Each below replaces ``sorter.kept``, and
    none is a ``<x>.setattr`` under ``tests/``: one in the root conftest
    (which pytest loads, but the survey does not walk), one through a
    fixture named ``setattr`` that gives the monkeypatch's method by a
    string, and one through a local of that name. The survey sees nothing,
    and the tool before ruling 012 passed this repository; the backstop
    holds every ``setattr`` in the suite's text to a form it accounts for,
    so each fails the check with its file and line. A parameter or a local
    of the name binds it as surely as a ``def`` does, but no form the tool
    reads needs one, so each is a line too."""
    root = _repository(tmp_path, {**SORTER, "conftest.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture(autouse=True)
        def quiet(monkeypatch):
            monkeypatch.setattr(sorter, "kept", None)
    """, "tests/test_a.py": """
        import pytest

        from tracker import sorter

        @pytest.fixture
        def setattr(monkeypatch):
            return getattr(monkeypatch, "setattr")

        def test_one(setattr):
            setattr(sorter, "kept", None)

        def test_two(monkeypatch):
            setattr = getattr(monkeypatch, "setattr")
            setattr(sorter, "kept", None)
    """})
    assert patch_sites.stand_ins(root) == ([], [])
    assert patch_sites.unaccounted(root) == [patch_sites.Unaccounted("conftest.py", 7),
                                             patch_sites.Unaccounted("tests/test_a.py", 9),
                                             patch_sites.Unaccounted("tests/test_a.py", 10),
                                             patch_sites.Unaccounted("tests/test_a.py", 13),
                                             patch_sites.Unaccounted("tests/test_a.py", 14)]
    ok, said = patch_sites.check(root)
    assert not ok
    assert said[0] == ("conftest.py:7: setattr is written here in a form the tool does not read, so a stand-in "
                       "made through it is not checked. Write the stand-in as <x>.setattr(...) in a file under "
                       "tests/, called where it is written.")
    assert [line.split(": ")[0] for line in said] == [
        "conftest.py:7", "tests/test_a.py:9", "tests/test_a.py:10", "tests/test_a.py:13", "tests/test_a.py:14"]


def test_every_form_the_backstop_accounts_for_passes_it(tmp_path):
    """What the backstop lets through is a list too: a ``<x>.setattr`` the
    survey read (a site, a stand-in on no module, one it cannot place), a
    call of the builtin ``setattr``, which nothing undoes, the name of a
    ``def`` or a ``class``, and the name in an import. A ``setattr`` in a
    string or a comment is not Python, so it is no token. The syntax tree
    counts a column in bytes and tokenize in characters, so a line with an
    ``é`` before its ``setattr`` is matched on both."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import builtins

        from tracker import sorter

        class Patcher:
            def setattr(self, *args):
                return args

        def test_one(monkeypatch):
            monkeypatch.setattr(sorter, "decide", None)
            done = ("\u00e9", monkeypatch.setattr(sorter, "digest", None))
            monkeypatch.setattr(builtins, "open", None)
            setattr(Patcher, "size", 1)
            # monkeypatch.setattr(sorter, "kept", None) is not written here
            said = "monkeypatch.setattr(sorter, 'kept', None)"
            assert done and said
    """, "tests/test_b.py": """
        from builtins import (
            setattr,
        )

        def test_two(monkeypatch):
            put = monkeypatch.setattr
            assert put
    """})
    assert "\u00e9" in (root / "tests" / "test_a.py").read_text(encoding="utf-8")
    assert patch_sites.unaccounted(root) == []
    marked, unplaced = patch_sites.stand_ins(root)
    assert [(site.line, site.name) for site, _mark in marked] == [(10, "decide"), (11, "digest")]
    assert [(one.file, one.line) for one in unplaced] == [("tests/test_b.py", 6)]


# ---------------------------------------------------------------- the report ----


def test_the_report_names_one_module_by_its_dotted_name_or_its_path(tmp_path, monkeypatch, capsys):
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import helpers, sorter

        def test_one(monkeypatch):
            monkeypatch.setattr(sorter, "decide", None)
            monkeypatch.setattr(sorter, "digest", None)
            monkeypatch.setattr(helpers, "digest", None)
    """})
    expected = ["tracker.sorter: 2 stand-ins in 1 file (1 defined, 1 imported, 0 unread)",
                "  tests/test_a.py:4  defined   decide  (sorter)",
                "  tests/test_a.py:5  imported  digest  (sorter)"]
    assert patch_sites.report("tracker.sorter", root) == expected
    monkeypatch.setattr(patch_sites, "ROOT", root)
    assert patch_sites.main(["report", "tracker/sorter.py"]) == 0
    assert capsys.readouterr().out.splitlines() == expected
    with pytest.raises(SystemExit, match="no module 'tracker.nothing'"):
        patch_sites.main(["report", "tracker.nothing"])


def test_the_command_line_check_exits_1_on_an_unread_stand_in(tmp_path, monkeypatch, capsys):
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import sorter

        def test_one(monkeypatch):
            monkeypatch.setattr(sorter, "kept", None)
    """})
    monkeypatch.setattr(patch_sites, "ROOT", root)
    assert patch_sites.main(["check"]) == 1
    assert "tracker.sorter.kept is unread there" in capsys.readouterr().out


def test_the_tool_uses_the_standard_library_alone_and_imports_nothing_of_the_suite():
    """R4.1: it reads the suite and the code and runs neither."""
    tree = ast.parse((REPO / "tools" / "patch_sites.py").read_text(encoding="utf-8"))
    imported = {alias.name.split(".")[0] for node in ast.walk(tree) if isinstance(node, ast.Import)
                for alias in node.names}
    imported |= {node.module.split(".")[0] for node in ast.walk(tree)
                 if isinstance(node, ast.ImportFrom) and node.module}
    assert imported - {"__future__"} <= sys.stdlib_module_names, imported


# ------------------------------------------------------------- the real suite ----


@pytest.fixture(scope="module")
def the_suite():
    """The stand-ins of the real suite, each with its mark; the ``setattr``
    calls the tool cannot place; and the ``setattr`` tokens of the suite's
    text it does not account for, from one survey."""
    suite = patch_sites._Suite(REPO)
    sites, unplaced, read = patch_sites._survey(suite)
    return patch_sites._marked(suite, sites), sorted(unplaced), patch_sites._unaccounted(suite, read)


def test_every_stand_in_in_the_suite_lands_where_the_code_reads_it(the_suite):
    """R4.2: no stand-in in ``tests/`` is unread, and every ``setattr`` is
    placed. One that fails here is pointed at the module that reads the name."""
    marked, unplaced, _unaccounted = the_suite
    assert not unplaced, unplaced
    assert [site.where() + " " + site.module + "." + site.name for site, mark in marked
            if mark == patch_sites.UNREAD] == []
    # The helper modules patch too (tests/children.py's seams are read there).
    assert {site.file for site, _mark in marked} >= {"tests/conftest.py", "tests/test_filer.py"}
    assert any(site.module == "tests.children" for site, _mark in marked)


def test_the_report_on_filer_holds_every_filer_site_a_plain_search_finds(the_suite):
    """The accept line names filer's stand-ins (73 when the audit counted).
    A plain search of the suite for ``setattr(filer, "...")`` and its
    alias finds fewer than the tool, which also follows loops and strings;
    every line the search finds is a site of the report."""
    marked, _unplaced, _unaccounted = the_suite
    reported = {(site.file, site.line) for site, _mark in marked if site.module == "tracker.filer"}
    searched = set()
    for path in sorted((REPO / "tests").glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"\.setattr\((filer|filer_module), \"", line) or "setattr(\"tracker.filer." in line:
                searched.add((path.relative_to(REPO).as_posix(), number))
    assert searched and searched <= reported, sorted(searched - reported)
    assert len(reported) >= 73


def test_every_setattr_in_the_suite_s_text_is_one_the_tool_accounts_for(the_suite):
    """Ruling 012 of J4: no ``setattr`` in the suite's Python is written in a
    form the tool does not read, so no stand-in of the suite is left out of
    the check."""
    _marked, _unplaced, unaccounted = the_suite
    assert [one.said() for one in unaccounted] == []


def test_the_command_line_check_passes_on_the_suite():
    """The gate, step 12 of the migration checklist, runs the tool by its path (P233)."""
    done = subprocess.run([sys.executable, str(REPO / "tools" / "patch_sites.py"), "check"],
                          capture_output=True, text=True, cwd=REPO, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.rstrip().endswith("each where the code reads the name.")
