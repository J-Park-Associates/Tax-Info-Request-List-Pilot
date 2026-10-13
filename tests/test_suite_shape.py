"""The shape of the suite: tests share helpers through helper modules, never through one another.

A test file that imports another test file (``from tests.test_filer import
drop``) makes an edge the affected-tests gate cannot see - changing
``test_scanner.text_pdf`` changed fifteen files' fixtures and only
``test_scanner.py`` reran - and splitting the owner's file, which every phase
of SPEC-architecture does, breaks every borrower. The helpers live in modules
that are not test files (``tests/samples.py``, ``builders.py``, ``children.py``,
``node_harness.py`` and the rest), so the repository map draws the edge as
"exercised by" and the gate follows it.

These claims read the import statements, not the text, in every form an import
takes, and read the whole of ``tests/`` the way pytest does: the files at its
top level. The tools' imports of ``tests.test_catalog``, ``test_irs_forms`` and
``test_real_corpus`` (decision 70) are not the suite's and are not judged here.
"""

import ast
from pathlib import Path

TESTS = Path(__file__).resolve().parent
#: What pytest loads on its own; not a helper any test imports by name.
NOT_A_HELPER = {"conftest"}


def imported(source: str) -> set[str]:
    """Every module a source file imports, as a dotted name, in every form:
    ``import tests.test_x``, ``from tests.test_x import y``, ``from tests import
    test_x``, the relative forms of those, and a module named to
    ``importlib.import_module`` or ``__import__`` as a literal."""
    found: set[str] = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            base = f"tests.{module}".rstrip(".") if node.level == 1 else module
            found.add(base)
            found |= {f"{base}.{alias.name}" for alias in node.names}
        elif isinstance(node, ast.Call):
            callee = node.func.attr if isinstance(node.func, ast.Attribute) else getattr(node.func, "id", "")
            if callee in ("import_module", "__import__") and node.args:
                argument = node.args[0]
                if isinstance(argument, ast.Constant) and isinstance(argument.value, str):
                    found.add(argument.value)
    return found


def the_test_files() -> list[Path]:
    return sorted(TESTS.glob("test_*.py"))


def the_helper_modules() -> list[Path]:
    return sorted(path for path in TESTS.glob("*.py")
                  if not path.name.startswith("test_") and path.stem not in NOT_A_HELPER)


def borrowed_test_modules(path: Path) -> set[str]:
    return {name for name in imported(path.read_text(encoding="utf-8"))
            if name.startswith("tests.test_") and name.count(".") == 1}


def test_no_test_file_imports_another_test_file():
    borrowed = {path.name: sorted(borrowed_test_modules(path)) for path in the_test_files()}
    assert {name: modules for name, modules in borrowed.items() if modules} == {}


def test_no_helper_module_or_conftest_imports_a_test_file():
    """A helper that imported a test file would carry the same edge through a
    module that is not one: the gate would still not see the owner."""
    holders = [*the_helper_modules(), TESTS / "conftest.py"]
    borrowed = {path.name: sorted(borrowed_test_modules(path)) for path in holders}
    assert {name: modules for name, modules in borrowed.items() if modules} == {}


def test_every_helper_module_is_imported_by_a_test_file():
    """A helper nobody imports is dead code, or a test file that forgot to be
    one."""
    imports = set().union(*(imported(path.read_text(encoding="utf-8")) for path in the_test_files()))
    unused = [path.name for path in the_helper_modules() if f"tests.{path.stem}" not in imports]
    assert unused == []


def test_the_guard_sees_every_form_of_import_a_test_can_borrow_with():
    source = "\n".join([
        "import tests.test_a",
        "import tests.test_b as b",
        "from tests.test_c import thing",
        "from tests import test_d",
        "from tests import test_e as e, samples",
        "from . import test_f",
        "from .test_g import thing",
        "import importlib",
        "importlib.import_module('tests.test_h')",
        "__import__('tests.test_i')",
        "def later():",
        "    from tests.test_j import thing",
        "    from tests import test_k",
    ])
    names = {name for name in imported(source) if name.startswith("tests.test_") and name.count(".") == 1}
    assert names == {f"tests.test_{letter}" for letter in "abcdefghijk"}


def test_the_guard_does_not_take_a_helper_or_a_word_in_a_string_for_a_test_file():
    source = "\n".join([
        "from tests.samples import text_pdf",
        "from tests import builders",
        "from tests.conftest import make_engagement",
        "text = 'from tests.test_core import public'",
        "from tracker import test_like_name",
    ])
    names = {name for name in imported(source) if name.startswith("tests.test_") and name.count(".") == 1}
    assert names == set()
