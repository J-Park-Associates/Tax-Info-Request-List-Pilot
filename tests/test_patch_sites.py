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
    four; so is a helper called twice with a module and a name."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        from tracker import helpers, sorter

        def _counting(monkeypatch, module, name):
            monkeypatch.setattr(module, name, None)

        def test_one(monkeypatch):
            for module, name in ((sorter, "decide"), (helpers, "kept")):
                monkeypatch.setattr(module, name, None)

        def test_two(monkeypatch):
            _counting(monkeypatch, helpers, "digest")
            _counting(monkeypatch, sorter, "kept")
    """})
    assert _marks(root) == {
        ("tests/test_a.py", 4, "tracker.helpers", "digest"): patch_sites.DEFINED,
        ("tests/test_a.py", 4, "tracker.sorter", "kept"): patch_sites.UNREAD,
        ("tests/test_a.py", 8, "tracker.sorter", "decide"): patch_sites.DEFINED,
        ("tests/test_a.py", 8, "tracker.helpers", "kept"): patch_sites.DEFINED,
    }


def test_a_fixture_s_params_and_a_fixture_that_gives_a_module_are_followed(tmp_path):
    root = _repository(tmp_path, {**SORTER, "tests/conftest.py": """
        import pytest

        from tracker import helpers

        @pytest.fixture
        def helpers_module():
            return helpers
    """, "tests/test_a.py": """
        import importlib

        import pytest

        @pytest.fixture(params=["sorter", "helpers"])
        def either(request, monkeypatch):
            module = importlib.import_module(f"tracker.{request.param}")
            monkeypatch.setattr(module, "digest", None)

        def test_one(monkeypatch, helpers_module):
            monkeypatch.setattr(helpers_module, "kept", None)
    """})
    assert _marks(root) == {
        ("tests/test_a.py", 8, "tracker.sorter", "digest"): patch_sites.IMPORTED,
        ("tests/test_a.py", 8, "tracker.helpers", "digest"): patch_sites.DEFINED,
        ("tests/test_a.py", 11, "tracker.helpers", "kept"): patch_sites.DEFINED,
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
    """A stand-in on ``sys``, on a class, or on an object a known call made
    lands on that object whoever reads it: there is no namespace to miss."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import os
        import sys
        from pathlib import Path

        from tracker import sorter
        from tracker.helpers import Shape

        def test_one(monkeypatch, tmp_path):
            monkeypatch.setattr(sys, "argv", [])
            monkeypatch.setattr("sys.stdin", None)
            monkeypatch.setattr(Path, "home", lambda: tmp_path)
            monkeypatch.setattr(Shape, "size", 1, raising=False)
            monkeypatch.setattr(type(tmp_path), "exists", lambda self: True)
            monkeypatch.setattr(os, "sep", "/")
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
    reads. The plain form and an annotated alias are sites, unread; a module
    stored by an unpacking, a walrus, ``with ... as`` or ``except ... as``, or
    given by a helper of the file or by ``getattr``, is not placed. None is
    taken for no module, so ``check`` names all eight."""
    root = _repository(tmp_path, {**SORTER, "tests/test_a.py": """
        import contextlib
        import types

        import tracker
        from tracker import sorter

        def _the_sorter():
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
    """})
    marked, unplaced = patch_sites.stand_ins(root)
    assert [(site.line, site.module, site.name, site.written, mark) for site, mark in marked] == [
        (12, "tracker.sorter", "kept", "module", patch_sites.UNREAD),
        (39, "tracker.sorter", "kept", "sorter", patch_sites.UNREAD),
    ]
    assert [(one.line, one.written) for one in unplaced] == [
        (16, "module"), (19, "_the_sorter()"), (22, "getattr(tracker, 'sorter')"),
        (26, "module"), (30, "module"), (36, "module"),
    ]
    ok, said = patch_sites.check(root)
    assert not ok and len(said) == 8


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
    return patch_sites.stand_ins(REPO)


def test_every_stand_in_in_the_suite_lands_where_the_code_reads_it(the_suite):
    """R4.2: no stand-in in ``tests/`` is unread, and every ``setattr`` is
    placed. One that fails here is pointed at the module that reads the name."""
    marked, unplaced = the_suite
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
    marked, _unplaced = the_suite
    reported = {(site.file, site.line) for site, _mark in marked if site.module == "tracker.filer"}
    searched = set()
    for path in sorted((REPO / "tests").glob("*.py")):
        for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), start=1):
            if re.search(r"\.setattr\((filer|filer_module), \"", line) or "setattr(\"tracker.filer." in line:
                searched.add((path.relative_to(REPO).as_posix(), number))
    assert searched and searched <= reported, sorted(searched - reported)
    assert len(reported) >= 73


def test_the_command_line_check_passes_on_the_suite():
    """The gate, step 12 of the migration checklist, runs the tool by its path (P233)."""
    done = subprocess.run([sys.executable, str(REPO / "tools" / "patch_sites.py"), "check"],
                          capture_output=True, text=True, cwd=REPO, timeout=300)
    assert done.returncode == 0, done.stdout + done.stderr
    assert done.stdout.rstrip().endswith("each where the code reads the name.")
