"""Finding a function of the package by its name, wherever it sits.

A pin on the package's own source used to find its code by where it was: it
cut a body out of one file by its exact first line
(``runner.index("def _pass(ns, parser, reached: dict)")``), counted a name's
call sites in one module's text, or sliced ``def this_host`` out of
``locking.py`` up to the next ``def``. Each of those fails when a signature
gains a parameter, and some would quietly stop checking anything when the
function moves to another module - which is what the refactor does to most of
them (SPEC-architecture E-1, R3.1). These read the syntax tree of every module
under ``tracker/``, at any depth, so a pin says *which function* it means and
finds it where it is:

- :func:`py_function` is one function's source, from its first decorator to
  its last line, asserting that exactly one function has that name. A nested
  ``def`` or a method of the same name counts as a second, so a pin never
  lands on a function it did not mean; where two modules define the name on
  purpose (``full_sync``, decision R22), the pin names the module.
- :func:`calls_of` is every call of a name, with the function it sits in.

The rejected alternative was ``inspect.getsource`` on the imported function.
It follows a re-export to the moved code as well, but it can only answer for
a function the test can import by its old address, it cannot list where a
name is called, and a pin that only reads the source would import modules to
do it. The trees are parsed once per process.
"""

import ast
from functools import cache
from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
PACKAGE = REPO / "tracker"

_FUNCTIONS = (ast.FunctionDef, ast.AsyncFunctionDef)


@cache
def _modules() -> dict[str, tuple[str, ast.Module]]:
    """Every module under ``tracker/``, at any depth: its path from the
    repository root, to its text and its tree."""
    found = {}
    for path in sorted(PACKAGE.rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        found[path.relative_to(REPO).as_posix()] = (text, ast.parse(text, filename=str(path)))
    return found


def _searched(module: str | None) -> dict[str, tuple[str, ast.Module]]:
    """The whole package, or the one module named as ``from tracker import``
    names it (``"locking"``, or ``"sub.name"`` below a folder)."""
    modules = _modules()
    if module is None:
        return modules
    rel = f"tracker/{module.replace('.', '/')}.py"
    assert rel in modules, f"there is no module {module} under tracker/"
    return {rel: modules[rel]}


def py_function(name: str, module: str | None = None) -> str:
    """The source of the one function called ``name`` in ``tracker/`` (or in
    ``module``), exactly as written: its whole lines from its first decorator
    (or its ``def``) to its last, as ``inspect.getsource`` gives them."""
    found = [(rel, text, node) for rel, (text, tree) in _searched(module).items()
             for node in ast.walk(tree) if isinstance(node, _FUNCTIONS) and node.name == name]
    where = [f"{rel}:{node.lineno}" for rel, _text, node in found]
    assert len(found) == 1, f"{name} is defined {len(found)} times in {module or 'tracker/'}: {where}"
    _rel, text, node = found[0]
    first = min([node.lineno, *(one.lineno for one in node.decorator_list)])
    return "".join(text.splitlines(keepends=True)[first - 1:node.end_lineno])


def calls_of(name: str) -> list[tuple[str, str]]:
    """Every call of ``name`` in ``tracker/``, at any depth - ``name(...)``
    or ``anything.name(...)`` - as ``(file, function)``: the module's path
    from the repository root and the innermost function the call sits in
    (``"<module>"`` at a module's top level), in the order the tree walks
    them. A name passed along without being called is not a call."""
    calls = []

    def visit(node: ast.AST, rel: str, inside: str) -> None:
        for child in ast.iter_child_nodes(node):
            if isinstance(child, ast.Call):
                func = child.func
                if (isinstance(func, ast.Name) and func.id == name) or \
                        (isinstance(func, ast.Attribute) and func.attr == name):
                    calls.append((rel, inside))
            visit(child, rel, child.name if isinstance(child, _FUNCTIONS) else inside)

    for rel, (_text, tree) in _modules().items():
        visit(tree, rel, "<module>")
    return calls
