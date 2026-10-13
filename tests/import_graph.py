"""The package's imports as the layer table reads them.

``import_edges()`` walks ``tracker/*.py`` and says, for every module, which
modules it imports at load time and which only when a function runs or a
``__main__`` block does (decision 99: an import inside a function may point
anywhere). ``test_layers`` wrote it to pin the layer table, and
``test_records`` and ``test_single_source`` imported it from there; it lives here so the borrowing names
a module that is not a test file (SPEC-architecture E-4, R2.1). Moved with its
words from ``tests/test_layers.py``.
"""

import ast
from pathlib import Path

PACKAGE = Path(__file__).resolve().parents[1] / "tracker"


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Compare) and isinstance(test.left, ast.Name)
            and test.left.id == "__name__")


def _modules() -> set[str]:
    return {path.stem for path in PACKAGE.glob("*.py")}


def _target(name: str, modules: set[str]) -> str:
    """Which module a ``from tracker import name`` reaches: the submodule of
    that name, or the package itself when the name is something it defines."""
    return name if name in modules else "__init__"


def _collect(body: list[ast.stmt], modules: set[str], load: set[str], call: set[str], *, in_call: bool) -> None:
    for node in body:
        into = call if in_call else load
        if isinstance(node, ast.If) and _is_main_guard(node):
            _collect(node.body, modules, load, call, in_call=True)
            _collect(node.orelse, modules, load, call, in_call=in_call)
            continue
        if isinstance(node, ast.ImportFrom) and node.module and node.module.split(".")[0] == "tracker":
            parts = node.module.split(".")
            if len(parts) == 1:
                into.update(_target(alias.name, modules) for alias in node.names)
            else:
                into.add(parts[1])
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "tracker":
                    into.add("__init__")
                elif alias.name.startswith("tracker."):
                    into.add(alias.name.split(".")[1])
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            _collect(node.body, modules, load, call, in_call=True)
        else:
            for field in ("body", "orelse", "finalbody"):
                child = getattr(node, field, None)
                if isinstance(child, list):
                    _collect(child, modules, load, call, in_call=in_call)
            for handler in getattr(node, "handlers", None) or []:
                _collect(handler.body, modules, load, call, in_call=in_call)


def import_edges() -> tuple[dict[str, set[str]], dict[str, set[str]]]:
    """(load-time edges, call-time edges) for every module in the package."""
    modules = _modules()
    load: dict[str, set[str]] = {}
    call: dict[str, set[str]] = {}
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        load[path.stem], call[path.stem] = set(), set()
        _collect(tree.body, modules, load[path.stem], call[path.stem], in_call=False)
        load[path.stem].discard(path.stem)
        call[path.stem] -= load[path.stem] | {path.stem}
    return load, call
