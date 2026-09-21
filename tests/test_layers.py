"""The package's layers, pinned: no load-time import points to a higher layer.

Why a test and not a paragraph: the structural review of 2026-09-18 found
the layering written down in a plan and broken twice in the tree, because
nothing checked it. A rule nobody runs is a wish. This file is the contract;
the table below is the whole of it, and a module that moves layers moves
here in the same commit, with a decision row saying why.

**What an edge is.** A load-time import is an ``import tracker.x`` or
``from tracker.x import ...`` at module level - anything that runs when the
module loads. An import inside a function, a class body or the module's
``if __name__ == "__main__":`` block is a call-time import: it runs when
called, so it can point anywhere, and the map labels it separately. The
one deliberate cycle in the package, ``filer`` <-> ``scanner`` inside
``_rescan()``, is a call-time cycle and is asserted to stay one.

**The layers.** In-layer edges are allowed (``ledger`` and ``manifest``
are both L1, so ``manifest`` reaching ``ledger`` is legal - and wanted,
because decision 104 put the request list's two writes beside its
schema). What is never allowed is an edge from a lower layer to a higher one.
``settings`` sat at L1 only because it borrowed the atomic write from
``manifest``; decision 120 moved that write to ``fsio`` at L0, which takes
``settings`` down with it - it imports ``fsio`` and nothing else of the
package. ``validators`` sits at L1 because ``scaffold`` reads one
helper from it (the placeholder examples the README prints), and its pure
half is not worth a module of its own until that call can move.

**No mail, no network, in code** (decision 115). The fourth standing rule
says nothing is ever sent, and until 115 the only pin was the words "never
sends" in a test. ``FORBIDDEN_MODULES`` names the standard library's mail
and network modules and the one third-party client anyone reaches for, and
the AST walk below finds none of them imported anywhere under ``tracker/``
- at load time or inside a function, plainly or as ``from x.y import``.
``subprocess`` is not on the list: the build and the scheduler use it.

**Rule 7, amended** (from the implementation plan's rules for every step):
``ledger`` and ``locking`` import nothing of the package but each other;
``manifest`` imports ``records`` and nothing else at load time, and
reaches ``store``, ``ledger`` and ``locking`` at call time; ``runner``
never imports ``scheduling`` or ``api``; the package's ``__init__`` imports
nothing at load time (decision 99 removed thirteen re-exports no file
consumed, and with them the one load-time cycle the map used to name).

The manifest's rule got *narrower* with decision 103 and kept that width
with 104, which is worth saying: it used to import ``ledger`` and
``locking`` at load time because it wrote the scanner columns. Decision
104 gave it the request list's writes - ``create_engagement()`` and
``save_rules()`` record a ``rules_changed`` event under the engagement
lock - and they reach ``store``, ``ledger`` and ``locking`` at call time,
as ``load_manifest()`` already did: in-layer edges, closed where an edge
is allowed to close.

``manifest`` -> ``records`` is the in-layer edge decision 100 added: the
record types moved out of the modules that write them, ``records`` imports
nothing of the package at all, and the manifest names the shapes it loads.

``store`` joins L1 with decision 101 and is deliberately narrower than its
layer allows: it imports ``records``, ``ledger`` and ``locking`` and
nothing else of the package, not even the in-layer ``manifest``.
Everything it holds comes out of the journal, so the database that answers
for the readers never depends on the modules that walk folders and move
files; its command line imports the registry at call time, which is where
a cycle is allowed to close.
"""

from __future__ import annotations

import ast
from pathlib import Path

REPO = Path(__file__).resolve().parents[1]
PACKAGE = REPO / "tracker"

#: Layer -> the modules in it. Every file in tracker/ is in exactly one.
LAYERS: dict[int, frozenset[str]] = {
    0: frozenset({"__init__", "reasons", "locking", "page", "fsio", "settings"}),
    1: frozenset({"ledger", "manifest", "records", "scaffold", "store", "templates",
                  "validators"}),
    2: frozenset({"content_check", "router"}),
    3: frozenset({"filer", "scanner", "reminder", "rollover", "view", "registry", "review"}),
    4: frozenset({"runner", "scheduling"}),
    5: frozenset({"api"}),
}
LAYER_OF: dict[str, int] = {module: layer for layer, modules in LAYERS.items() for module in modules}

#: Load-time edges that may point upward. None today; an entry here is a
#: debt with a decision row behind it, removed by the step that pays it.
ALLOWED_UPWARD: frozenset[tuple[str, str]] = frozenset()

#: What "nothing is ever sent" forbids any module under tracker/ to import,
#: at any depth: a name here, or any ``name.sub`` under it.
FORBIDDEN_MODULES: tuple[str, ...] = (
    "smtplib", "email", "imaplib", "poplib", "ftplib", "urllib", "http", "socket", "ssl",
    "requests",
)


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


def test_every_module_is_in_exactly_one_layer():
    modules = _modules()
    listed = [module for layer in LAYERS.values() for module in layer]
    assert sorted(listed) == sorted(set(listed)), "a module is named in two layers"
    assert set(listed) == modules, set(listed) ^ modules


def test_no_load_time_import_points_to_a_higher_layer():
    load, _ = import_edges()
    upward = sorted(
        (module, target)
        for module, targets in load.items()
        for target in targets
        if LAYER_OF[target] > LAYER_OF[module] and (module, target) not in ALLOWED_UPWARD
    )
    assert not upward, [f"{m} (L{LAYER_OF[m]}) imports {t} (L{LAYER_OF[t]}) at load time" for m, t in upward]


def test_every_allowed_upward_edge_is_still_needed():
    """An allowance that nothing uses is a hole in the contract."""
    load, _ = import_edges()
    stale = [edge for edge in ALLOWED_UPWARD if edge[1] not in load.get(edge[0], set())]
    assert not stale, stale


def test_the_bottom_two_import_nothing_of_the_package_but_each_other():
    load, _ = import_edges()
    assert load["locking"] == set(), load["locking"]
    assert load["ledger"] <= {"locking"}, load["ledger"]


def test_the_store_imports_only_the_record_the_journal_and_the_lock():
    """Decision 101: narrower than its layer, on purpose - the store must
    not depend on what opens a workbook, or it cannot replace it."""
    load, _ = import_edges()
    assert load["store"] == {"ledger", "locking", "records"}, load["store"]


def test_the_manifest_imports_the_record_and_nothing_else():
    """Narrower since decision 103, and kept so by 104.

    The manifest used to append to the journal and take the engagement
    lock at load time, because it wrote the scanner columns. Decision 104
    gave it the request list's writes, and they reach the store, the
    journal and the lock at call time - where an in-layer edge is allowed
    to close - so at load time it names the shapes it validates into and
    nothing else.
    """
    load, call = import_edges()
    assert load["manifest"] == {"records"}, load["manifest"]
    assert {"store", "ledger", "locking"} <= call["manifest"], call["manifest"]


def test_the_settings_import_only_the_atomic_write():
    """Decision 120: the one import that held it a layer up is gone.

    ``settings`` borrowed ``write_json_atomically`` from ``manifest``, and
    that single name was the whole of its dependence on L1. The write is
    ``fsio`` now, so the settings file - which the app, the scheduler and
    every command line read before anything else - is written by a module
    that knows nothing of request lists.
    """
    load, _ = import_edges()
    assert load["settings"] == {"fsio"}, load["settings"]


def test_the_atomic_write_imports_nothing_of_the_package():
    """It is the bottom of the package: anything may reach it, it reaches
    nothing, and it holds no policy to reach for."""
    load, call = import_edges()
    assert load["fsio"] == set(), load["fsio"]
    assert call["fsio"] == set(), call["fsio"]


def test_the_package_init_imports_nothing_at_load_time():
    load, _ = import_edges()
    assert load["__init__"] == set(), load["__init__"]


def test_the_runner_never_imports_the_scheduler_or_the_api():
    load, call = import_edges()
    assert not {"scheduling", "api"} & (load["runner"] | call["runner"])


def test_the_filer_and_scanner_cycle_closes_only_at_call_time():
    load, call = import_edges()
    assert "scanner" not in load["filer"] and "filer" not in load["scanner"]
    assert "scanner" in call["filer"] and "filer" in call["scanner"], (call["filer"], call["scanner"])


def _imported_names(tree: ast.AST) -> list[str]:
    """Every dotted module name an import anywhere in ``tree`` reaches:
    ``import x.y`` and ``from x.y import z`` both give ``x.y``; the walk
    covers function bodies, class bodies and the ``__main__`` block alike."""
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names += [alias.name for alias in node.names]
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def test_no_module_under_tracker_imports_a_mail_or_network_module():
    """Decision 115 pins the fourth standing rule in code: no SMTP, no mail
    client, no network call - no module that could make one is imported
    anywhere under tracker/, at load time or at call time."""
    found = []
    for path in sorted(PACKAGE.glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for name in _imported_names(tree):
            top = name.split(".")[0]
            if top in FORBIDDEN_MODULES:
                found.append(f"{path.name} imports {name}")
    assert not found, found
