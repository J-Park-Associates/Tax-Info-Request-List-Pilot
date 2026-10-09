"""Build and maintain the repository knowledge graph in ``docs/repo-map.json``.

The map exists so an agent starting a session can read one file instead of
re-reading the repository. That only works if the map is trustworthy, so it is
*derived* from the source rather than written by hand:

- **Derived** facts come from parsing the files — imports, exported names, line
  counts, which modules have a CLI, which tests cover what. They are recomputed
  and must never be hand-edited; the next update overwrites them.
- **Curated** facts are the things no parser can know: what a module is *for*,
  the artifacts that flow through the pipeline (``_ledger.jsonl``,
  ``reminder-draft.txt``), the order of the stages, and the cross-language
  hops. They live in ``docs/repo-map.curated.json`` and are merged on top.

Because the two layers are separate files, regenerating never destroys
judgment, and editing judgment never invalidates the derived half.

**Updating is incremental.** Every file node carries a SHA-256 of its content.
``update`` re-parses only the files whose hash changed, plus anything new, and
drops nodes whose file is gone. Everything else is copied forward untouched, so
updating after a one-file change costs one parse, not a full rebuild.

**The hash is of what Git commits** (decision 151). ``.gitattributes`` says
``text=auto eol=lf``, so a CRLF working copy is committed as LF and ``git
diff`` shows no change; ``git_text_auto_eol_lf`` copies that rule, so the map
agrees with a CI checkout whatever line endings an editor left, and ``check``
names such a working copy as a warning. And the map is never built over a
half-resolved merge: ``git ls-files`` lists an unmerged path once per stage,
so ``build``, ``update`` and ``check`` refuse and name the paths instead.

**Checking is not.** ``check`` compares hashes first, then rebuilds the derived
layer from scratch and compares it fact for fact with the committed map, and
finally renders the markdown and compares that too. A hash says a file did not
change; only the rebuild says the map still tells the truth about it - a
hand-edited derived field, a forged edge or a stale ``repo-map.md`` passes the
hashes and fails here. The rebuild is cheap because the module table (which
path answers to which import) is computed once per build, not once per file.

**What an import edge claims.** ``from tracker import ledger`` draws two
edges: one to ``tracker/ledger.py`` (the module the statement names) and one
to ``tracker/__init__.py`` (the package the statement executes). Dropping
either would hide a real dependency; before this both collapsed onto the
package, and a module imported only that way showed no importer at all. An
import inside a function or a ``__main__`` block is ``imports_at_call``, not
``imports``: it runs when called, not when loaded, so a cycle that closes
through one is a cycle only at call time.

::

    python tools/repo_map.py build      # from scratch (rarely needed)
    python tools/repo_map.py update     # incremental — the normal path
    python tools/repo_map.py check      # is the map current and true? exit 1 if not
    python tools/repo_map.py show tracker/runner.py    # one node and its edges

Standard library only, so it runs anywhere the repo does.
"""

from __future__ import annotations

import argparse
import ast
import hashlib
import json
import re
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MAP_PATH = ROOT / "docs" / "repo-map.json"
CURATED_PATH = ROOT / "docs" / "repo-map.curated.json"
MARKDOWN_PATH = ROOT / "docs" / "repo-map.md"

#: Bumped when a node or edge field changes meaning. ``load_map`` refuses an
#: older map rather than comparing it against rules it was not built by.
SCHEMA_VERSION = 2

#: The test edges the map draws, the import edge that is not a load-time
#: dependency, and what the map says when there is no owner test. CLAUDE.md
#: explains them by these names; tests/test_single_source.py pins it.
MAP_INTRO = "Read this instead of re-scanning the repository."
TESTED_BY = "tested by"
EXERCISED_BY = "exercised by"
NO_TEST_FILE = "no dedicated test file"
IMPORTS_AT_CALL = "imports at call time"

#: What ``build``, ``update`` and ``check`` say while a merge is half-resolved.
UNMERGED_ADVICE = "Resolve these and `git add` them first"

#: Extensions worth a node. Everything else is noise in a code map.
#: ``.yml``/``.yaml`` earns its place because CI config is part of how the repo
#: works, not decoration around it — and an agent reading the map should know a
#: workflow exists. Only tracked files are mapped, so gitignored runtime files
#: (settings.json, drafts, logs) never appear.
SOURCE_SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".bat",
                   ".json", ".txt", ".svg", ".yml", ".yaml"}

#: The map's own output. Writing the map changes these files, so mapping them
#: would leave the map permanently stale against itself. The curated file is
#: deliberately NOT excluded: it is an input, and editing it must show up as
#: drift so `update` rebuilds the descriptions.
EXCLUDED = {p.relative_to(ROOT).as_posix() for p in (MAP_PATH, MARKDOWN_PATH)}

#: Directory → layer. First match wins; order matters. The *type* of a node is
#: decided by its suffix (``classify``), so a lockfile under app/ is a file
#: and not an untested module.
LAYERS: tuple[tuple[str, str], ...] = (
    (".github/", "ci"),
    ("tracker/", "core"),
    ("tests/", "tests"),
    ("tools/", "tooling"),
    ("docs/", "docs"),
    ("app/", "desktop-app"),
)

#: Files that pin a package version. Read at build time so the External
#: dependencies section can say which packages are pinned and which are
#: optional, instead of listing ten names flat.
REQUIREMENTS_FILES = ("requirements.txt", "requirements-build.txt")

#: What the derivation may say, and what only the curated file may say. A
#: curated edge typed like a derived one would be rendered as coverage or as a
#: dependency the source does not show, which is the lie the split exists to
#: prevent - so it is refused.
DERIVED_EDGE_TYPES = frozenset({"imports", "imports_at_call", "tests", "exercises",
                                "depends_on"})
#: The node types a ``tests/test_<stem>.py`` can own (the owner edge).
OWNED_TYPES = frozenset({"module", "tool", "workflow", "script"})
CURATED_EDGE_TYPES = frozenset({"writes", "reads", "precedes", "runs", "documents",
                                "spawns", "loads", "schedules", "calls", "freezes",
                                "launches", "enforces", "deliberate_cycle"})
#: Every edge type, and how it renders from either end (None: not rendered as
#: a per-node line; the test edges and dependencies have their own wording).
EDGE_LABELS: dict[str, tuple[str | None, str | None]] = {
    "imports": ("imports", "used by"),
    "imports_at_call": (IMPORTS_AT_CALL, "used at call time by"),
    "tests": (None, TESTED_BY),
    "exercises": (None, EXERCISED_BY),
    "depends_on": (None, None),
    "writes": ("writes", "written by"),
    "reads": ("reads", "read by"),
    "precedes": ("precedes", "follows"),
    "runs": ("runs", "run by"),
    "documents": ("documents", "documented in"),
    "spawns": ("spawns", "spawned by"),
    "loads": ("loads", "loaded by"),
    "schedules": ("schedules", "scheduled by"),
    "calls": ("calls", "called by"),
    "freezes": ("freezes", "frozen by"),
    "launches": ("launches", "launched by"),
    "enforces": ("enforces", "enforced in"),
    "deliberate_cycle": ("deliberate cycle with", "deliberate cycle with"),
}
assert set(EDGE_LABELS) == DERIVED_EDGE_TYPES | CURATED_EDGE_TYPES

#: The curated file's vocabulary. A key or value outside it is refused when
#: the map is built, so a misspelled ``note`` cannot drop a note on the floor
#: and a misspelled ``artefact`` cannot drop an artifact off the page.
CURATED_TOP_KEYS = frozenset({"_comment", "pipeline", "nodes", "edges"})
CURATED_NODE_KEYS = frozenset({"role", "notes", "tags", "type", "layer", "write_only"})
CURATED_NODE_TYPES = frozenset({"artifact", "concept"})
CURATED_LAYERS = frozenset({"runtime", "constraint"})
NODE_PREFIXES = ("artifact:", "rule:")

#: Node's own modules are not dependencies of the desktop app; the shell
#: requires them the way Python imports ``json``.
NODE_BUILTINS = frozenset({"fs", "path", "child_process", "os", "url", "util",
                           "events", "http", "https", "crypto", "readline",
                           "process", "stream", "buffer"})

_REQUIRE = re.compile(r"""require\(\s*["']([^"']+)["']\s*\)""")
_SPAWN = re.compile(r"""spawn\(\s*["']([^"']+)["']""")
_PIN = re.compile(r"^([A-Za-z0-9_.-]+)==(\S+)", re.M)


class MapError(Exception):
    """The map could not be built, read or updated."""


@dataclass
class Node:
    id: str
    type: str
    layer: str
    sha256: str = ""
    lines: int = 0
    exports: list[str] = field(default_factory=list)
    constants: dict[str, str] = field(default_factory=dict)   # UPPER_CASE = literal, derived
    cli: str = ""
    pin: str = ""             # derived, packages only: "3.1.5 (requirements.txt)"
    role: str = ""            # curated
    notes: str = ""           # curated
    tags: list[str] = field(default_factory=list)
    write_only: bool = False  # curated, artifacts only: nothing reads it by design

    def to_json(self) -> dict:
        out = {"id": self.id, "type": self.type, "layer": self.layer}
        if self.sha256:
            out["sha256"] = self.sha256
        if self.lines:
            out["lines"] = self.lines
        if self.cli:
            out["cli"] = self.cli
        if self.exports:
            out["exports"] = self.exports
        if self.constants:
            out["constants"] = self.constants
        if self.pin:
            out["pin"] = self.pin
        if self.role:
            out["role"] = self.role
        if self.notes:
            out["notes"] = self.notes
        if self.tags:
            out["tags"] = sorted(self.tags)
        if self.write_only:
            out["write_only"] = True
        return out


# ------------------------------------------------------------- collecting ----


def _git_files(root: Path, *args: str) -> list[str]:
    try:
        return subprocess.run(
            ["git", "ls-files", *args], cwd=root, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise MapError(f"could not list tracked files: {exc}") from None


def _mappable(root: Path, listed: list[str]) -> list[str]:
    return sorted(
        path for path in listed
        if Path(path).suffix in SOURCE_SUFFIXES
        and path not in EXCLUDED
        and (root / path).is_file()
    )


def tracked_files(root: Path | None = None) -> list[str]:
    """Every file git tracks, so the map follows .gitignore for free."""
    return _mappable(root or ROOT, _git_files(root or ROOT))


def untracked_sources(root: Path | None = None) -> list[str]:
    """Source files on disk that git does not track yet.

    ``check`` names them: a new module that was never ``git add``-ed is
    invisible to ``tracked_files`` and would otherwise leave the map "current"
    while the tree has code the map has never seen.
    """
    root = root or ROOT
    return _mappable(root, _git_files(root, "--others", "--exclude-standard"))


def unmerged_files(root: Path | None = None) -> list[str]:
    """The paths a conflicted merge or rebase has left unresolved, once each.

    ``git ls-files`` lists an unmerged path once per stage (1, 2 and 3), and
    the file on disk still carries the conflict markers, so mapping it would
    write three nodes of a file nobody meant. ``build`` refuses instead, and
    the commands name the paths to resolve and ``git add`` (decision 151).
    """
    root = root or ROOT
    return sorted({line.split("\t", 1)[1]
                   for line in _git_files(root, "--unmerged") if "\t" in line})


#: What Git's ``gather_stats()`` counts as a non-printable byte: the control
#: bytes other than backspace, tab, escape and form feed (which it counts as
#: printable) and CR and LF (line endings, counted as neither), plus DEL.
_GIT_NONPRINTABLE = bytes(c for c in range(32) if c not in b"\b\t\x1b\x0c\r\n") + b"\x7f"
_NOT_GIT_NONPRINTABLE = bytes(c for c in range(256) if c not in _GIT_NONPRINTABLE)


def git_text_auto_eol_lf(raw: bytes) -> bytes:
    """The bytes Git commits for ``raw`` under ``* text=auto eol=lf``.

    A copy of the rule in ``.gitattributes`` that decides what a commit holds,
    so the map hashes what CI checks out rather than what an editor left in
    the working copy. ``git diff`` shows no change in a CRLF working copy
    because Git turns its CRLF into LF on the way in; a map that hashed the CRLF bytes
    was current on the machine that built it and stale on every checkout
    (decision 151). ``tests/test_repo_map.py`` fails if ``.gitattributes``
    stops saying ``text=auto eol=lf``: this function must follow it.

    Text or binary is decided the way Git's ``convert_is_binary()`` decides it
    for ``text=auto``, over the whole file: a NUL byte, a CR that does not
    begin a CRLF, or more than one non-printable byte per 128 printable ones
    makes it binary, and a binary file (the IRS PDFs) is committed as it is.
    A text file has every CRLF turned to LF.
    """
    if b"\0" in raw:
        return raw
    crlf = raw.count(b"\r\n")
    if not crlf or raw.count(b"\r") != crlf:
        return raw      # nothing to turn, or a lone CR: Git calls it binary
    nonprintable = len(raw.translate(None, _NOT_GIT_NONPRINTABLE))
    printable = len(raw) - crlf - raw.count(b"\n") - nonprintable
    if raw.endswith(b"\x1a"):
        nonprintable -= 1       # Git does not count a trailing DOS end-of-file
    if (printable >> 7) < nonprintable:
        return raw
    return raw.replace(b"\r\n", b"\n")


def hash_file(path: Path) -> str:
    """The SHA-256 of the file as Git commits it (``git_text_auto_eol_lf``)."""
    return hashlib.sha256(git_text_auto_eol_lf(path.read_bytes())).hexdigest()[:16]


#: The files ``.gitattributes`` checks out CRLF on purpose (decision 209,
#: R7: cmd loses its place in an LF batch file). Git still commits them as
#: LF - the ``text`` attribute normalises on the way in - so the hash rule
#: above is theirs too; only the working copy differs, by design.
CRLF_CHECKOUT_SUFFIXES = (".bat",)


def crlf_working_copies(root: Path | None = None) -> list[str]:
    """Tracked text files whose working copy has CRLF where Git commits LF.

    Not staleness: the hash is of the LF bytes, so the map is right about
    them. ``check`` names them so the agent whose editor wrote CRLF knows -
    all but the batch files, which check out CRLF by rule.
    """
    root = root or ROOT
    return [path for path in tracked_files(root)
            if not path.endswith(CRLF_CHECKOUT_SUFFIXES)
            and git_text_auto_eol_lf(raw := (root / path).read_bytes()) != raw]


def classify(path: str) -> tuple[str, str]:
    """(type, layer): the layer from the directory, the type from the suffix."""
    layer = next((layer for prefix, layer in LAYERS if path.startswith(prefix)), "root")
    suffix = Path(path).suffix
    if suffix == ".py":
        node_type = {"tests": "test", "tooling": "tool"}.get(layer, "module")
    elif suffix == ".js":
        node_type = "module"
    elif suffix in (".html", ".css", ".svg"):
        node_type = "ui"
    elif suffix == ".bat":
        node_type = "script"
    elif suffix in (".yml", ".yaml"):
        node_type = "workflow"
    elif suffix in (".md", ".txt"):
        node_type = "doc"
        if layer == "root":
            layer = "docs"
    else:
        node_type = "file"
    return node_type, layer


def module_name(path: str) -> str:
    """``tracker/manifest.py`` → ``tracker.manifest``."""
    stem = path[:-3].replace("/", ".")
    return stem[: -len(".__init__")] if stem.endswith(".__init__") else stem


def dedicated_test_for(path: str) -> str:
    """The test file that *owns* a module: ``tracker/filer.py`` → ``tests/test_filer.py``."""
    return f"tests/test_{Path(path).stem}.py"


def test_edge_kind(test_path: str, target: str) -> str:
    """How strong a claim a test file's import of ``target`` actually supports.

    One import can mean two very different things, and collapsing them
    overstates coverage — the failure the map exists to prevent:

    - ``tests``     — the test file that owns this module by name. This is
      coverage, and renders as "tested by".
    - ``exercises`` — any other test importing it. Real and worth knowing
      (many test files import manifest.py, so its schema is load-bearing
      across the suite) but it is not that module's coverage. A test
      borrowing a fixture from tests/samples.py to build an engagement asserts
      nothing whatsoever about tracker/api.py.
    - ``imports``   — a test importing another *test* for a shared helper.
      Not coverage in any sense; a fixture builder being reused.
    """
    if target.startswith("tests/"):
        return "imports"
    return "tests" if test_path == dedicated_test_for(target) else "exercises"


def _unambiguous_stems(paths: list[str]) -> dict[str, str]:
    """Stem → path, but only for stems belonging to exactly one file.

    Used to resolve a bare `import repo_map`, and to decide which file a
    ``tests/test_<stem>.py`` owns. A stem shared by two files is left out
    entirely: guessing which one was meant is how a map starts lying.
    """
    counts: dict[str, list[str]] = {}
    for path in paths:
        counts.setdefault(Path(path).stem, []).append(path)
    return {stem: found[0] for stem, found in counts.items() if len(found) == 1}


@dataclass(frozen=True)
class ModuleTable:
    """Which tracked file answers to which import, computed once per build.

    ``sha256`` is part of the cache key: an edge resolved against one set of
    files is only as good as that set, so adding a file that makes a stem
    ambiguous, or a module a bare import previously missed, rebuilds every
    cached edge instead of carrying the old resolution forward.
    """
    internal: dict[str, str]     # module name → path
    by_stem: dict[str, str]      # unambiguous stem → path, .py only
    sha256: str

    @classmethod
    def of(cls, files: list[str]) -> ModuleTable:
        python_files = [p for p in files if p.endswith(".py")]
        code_files = [p for p in files if p.endswith((".py", ".js"))]
        digest = hashlib.sha256("\n".join(sorted(code_files)).encode("utf-8")).hexdigest()[:16]
        return cls(
            internal={module_name(p): p for p in python_files},
            by_stem=_unambiguous_stems(python_files),
            sha256=digest,
        )

    def resolve(self, name: str) -> str:
        return self.internal.get(name) or self.by_stem.get(name) or ""


# ---------------------------------------------------------------- parsing ----


def parse_python_full(
    text: str, path: str
) -> tuple[list[str], list[tuple[str, str, str]], bool, dict[str, str]]:
    """Exported names, imports with their scope, whether it has a CLI, and
    the module's literal constants.

    Imports are ``(name, kind, scope)``. ``kind`` is ``import``, ``from`` (the
    module a from-import names) or ``from-name`` (that module joined to one
    imported name, so ``from tracker import ledger`` also yields
    ``tracker.ledger`` - resolved only if it is a module of ours, never a
    dependency). ``scope`` is ``load`` for a statement that runs when the
    module is imported and ``call`` for one inside a function or a
    ``__main__`` block.

    A constant is a top-level ``UPPER_CASE = <literal>`` (strings, numbers,
    booleans, tuples of those). They are rendered into the map so a doc can
    cite ``MAX_PAGES`` and a reader can see its value without the source -
    and so a value never has to be restated in prose to be findable.
    """
    try:
        tree = ast.parse(text)
    except SyntaxError as exc:
        raise MapError(f"{path}: {exc}") from None

    exports: list[str] = []
    imports: list[tuple[str, str, str]] = []
    has_cli = any(_is_main_guard(node) for node in ast.walk(tree) if isinstance(node, ast.If))
    _collect_imports(tree.body, "load", imports)

    constants: dict[str, str] = {}
    for node in tree.body:  # top level only — nested defs are not the API
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if (isinstance(target, ast.Name) and target.id.isupper()
                        and not target.id.startswith("_")):
                    exports.append(target.id)
                    literal = _literal_text(node.value)
                    if literal is not None:
                        constants[target.id] = literal

    return exports, imports, has_cli, constants


def _is_main_guard(node: ast.If) -> bool:
    test = node.test
    return (isinstance(test, ast.Compare)
            and isinstance(test.left, ast.Name)
            and test.left.id == "__name__")


def _collect_imports(statements: list[ast.stmt], scope: str,
                     found: list[tuple[str, str, str]]) -> None:
    """Every import under ``statements``, tagged with when it runs."""
    for node in statements:
        if isinstance(node, ast.Import):
            for alias in node.names:
                found.append((alias.name, "import", scope))
        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.level:
                found.append((node.module, "from", scope))
                for alias in node.names:
                    if alias.name != "*":
                        found.append((f"{node.module}.{alias.name}", "from-name", scope))
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            _collect_imports(node.body, "call", found)
        elif isinstance(node, ast.ClassDef):
            _collect_imports(node.body, scope, found)
        elif isinstance(node, ast.If):
            inner = "call" if _is_main_guard(node) else scope
            _collect_imports(node.body, inner, found)
            _collect_imports(node.orelse, scope, found)
        elif isinstance(node, ast.Try):
            _collect_imports(node.body, scope, found)
            for handler in node.handlers:
                _collect_imports(handler.body, scope, found)
            _collect_imports(node.orelse, scope, found)
            _collect_imports(node.finalbody, scope, found)
        elif isinstance(node, (ast.With, ast.AsyncWith, ast.For, ast.AsyncFor, ast.While)):
            _collect_imports(node.body, scope, found)
            _collect_imports(getattr(node, "orelse", []), scope, found)


def _literal_text(value: ast.expr) -> str | None:
    """A short rendering of a literal constant, or None if it is not one."""
    if isinstance(value, ast.Constant):
        return repr(value.value)
    if isinstance(value, ast.Tuple) and all(isinstance(e, ast.Constant) for e in value.elts):
        rendered = ", ".join(repr(e.value) for e in value.elts)
        return f"({rendered},)" if len(value.elts) == 1 else f"({rendered})"
    return None


def parse_js(text: str) -> list[str]:
    return sorted({*_REQUIRE.findall(text), *_SPAWN.findall(text)})


# ----------------------------------------------------------------- graph ----


def derive_node(path: str, root: Path, table: ModuleTable | None = None) -> tuple[Node, list[dict]]:
    """Parse one file into its node and the edges that start at it."""
    node_type, layer = classify(path)
    full = root / path
    node = Node(id=path, type=node_type, layer=layer, sha256=hash_file(full))
    edges: list[dict] = []

    if path.endswith(".py"):
        text = full.read_text(encoding="utf-8")
        node.lines = len(text.splitlines())
        exports, imports, has_cli, constants = parse_python_full(text, path)
        node.exports = sorted(set(exports))
        node.constants = constants
        if has_cli:
            node.cli = f"python -m {module_name(path)}" if "/" in path else f"python {path}"

        table = table or ModuleTable.of(tracked_files(root))
        seen: set[tuple[str, str]] = set()
        for name, kind, scope in imports:
            # A bare name can still be ours: tests reach tools/repo_map.py as
            # `import repo_map` after a sys.path insert. Without this it would
            # be filed as an external package the project does not depend on.
            target = table.resolve(name)
            if target and target != path:
                if node_type == "test":
                    edge_type = test_edge_kind(path, target)
                else:
                    edge_type = "imports" if scope == "load" else "imports_at_call"
                key = (target, edge_type)
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": path, "to": target, "type": edge_type,
                                  "source": "derived"})
            elif not target and kind != "from-name":
                package = name.split(".")[0]
                if table.resolve(package) or _is_stdlib(package):
                    continue
                key = (f"pkg:{package}", "depends_on")
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": path, "to": f"pkg:{package}",
                                  "type": "depends_on", "source": "derived"})
        # Loaded is loaded: a module imported at load time and again inside
        # a function is one dependency, not two.
        loaded = {e["to"] for e in edges if e["type"] == "imports"}
        edges = [e for e in edges if not (e["type"] == "imports_at_call" and e["to"] in loaded)]

    elif path.endswith(".js"):
        text = full.read_text(encoding="utf-8")
        node.lines = len(text.splitlines())
        for required in parse_js(text):
            if required.startswith("."):
                resolved = _resolve_relative(path, required, root)
                if resolved:
                    edges.append({"from": path, "to": resolved, "type": "imports",
                                  "source": "derived"})
            else:
                package = required.removeprefix("node:")
                if package not in NODE_BUILTINS and package != "python":
                    edges.append({"from": path, "to": f"pkg:{package}",
                                  "type": "depends_on", "source": "derived"})
    else:
        try:
            node.lines = len(full.read_text(encoding="utf-8").splitlines())
        except UnicodeDecodeError:
            node.lines = 0

    return node, edges


_STDLIB = set(sys.stdlib_module_names)


def _is_stdlib(name: str) -> bool:
    return name in _STDLIB


def _resolve_relative(path: str, required: str, root: Path) -> str:
    base = (Path(path).parent / required).as_posix()
    for candidate in (base, f"{base}.js", f"{base}/index.js"):
        if (root / candidate).is_file():
            return candidate
    return ""


def read_pins(root: Path, files: list[str]) -> dict[str, str]:
    """Package name (lower case) → "version (file)" from the requirements files."""
    pins: dict[str, str] = {}
    for name in REQUIREMENTS_FILES:
        if name not in files:
            continue
        for package, version in _PIN.findall((root / name).read_text(encoding="utf-8")):
            pins.setdefault(package.lower(), f"{version} ({name})")
    return pins


def load_curated(path: Path | None = None) -> dict:
    path = path or CURATED_PATH
    if not path.is_file():
        return {"nodes": {}, "edges": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MapError(f"{path} is not valid JSON: {exc}") from None
    data.setdefault("nodes", {})
    data.setdefault("edges", [])
    return data


def validate_curated(curated: dict, file_ids: set[str]) -> None:
    """Refuse a curated file the generator would otherwise misread.

    Every failure here used to be silent: an unknown key dropped a note, an
    annotation for a file that no longer exists became a phantom concept node
    rendered among the rules, a misspelled type dropped an artifact off the
    page, and a curated edge typed like a derived one rendered as coverage
    the source never showed.
    """
    problems: list[str] = []
    unknown = sorted(set(curated) - CURATED_TOP_KEYS)
    if unknown:
        problems.append("unknown top-level key(s): " + ", ".join(unknown))
    for node_id, extra in curated.get("nodes", {}).items():
        if not isinstance(extra, dict):
            problems.append(f"node {node_id!r} is not an object")
            continue
        keys = sorted(set(extra) - CURATED_NODE_KEYS)
        if keys:
            problems.append(f"node {node_id!r} has unknown key(s): " + ", ".join(keys))
        if node_id in file_ids:
            for key in ("type", "layer"):
                if key in extra:
                    problems.append(f"node {node_id!r} is a tracked file; its {key} is derived")
            continue
        if not node_id.startswith(NODE_PREFIXES):
            problems.append(
                f"curated node {node_id!r} describes a file that is not tracked "
                f"(a typed node starts with one of {', '.join(NODE_PREFIXES)})")
            continue
        if extra.get("type") not in CURATED_NODE_TYPES:
            problems.append(f"node {node_id!r}: type must be one of "
                            f"{', '.join(sorted(CURATED_NODE_TYPES))}, not {extra.get('type')!r}")
        if extra.get("layer") not in CURATED_LAYERS:
            problems.append(f"node {node_id!r}: layer must be one of "
                            f"{', '.join(sorted(CURATED_LAYERS))}, not {extra.get('layer')!r}")
        if not extra.get("role"):
            problems.append(f"node {node_id!r} has no role")
    for edge in curated.get("edges", []):
        keys = sorted(set(edge) - {"from", "to", "type"})
        missing = sorted({"from", "to", "type"} - set(edge))
        if keys or missing:
            problems.append(f"edge {edge!r}: unknown key(s) {keys}, missing {missing}")
            continue
        if edge["type"] in DERIVED_EDGE_TYPES:
            problems.append(f"edge {edge['from']} -> {edge['to']}: {edge['type']!r} is derived "
                            "from the source and may not be asserted by hand")
        elif edge["type"] not in CURATED_EDGE_TYPES:
            problems.append(f"edge {edge['from']} -> {edge['to']}: unknown type {edge['type']!r}")
        if edge["from"] == edge["to"]:
            problems.append(f"edge {edge['from']} -> {edge['to']} points at itself")
    if problems:
        raise MapError("the curated file is malformed:\n  " + "\n  ".join(problems))


def generator_fingerprint() -> str:
    """Hash of this file — the cache key for everything it derives."""
    return hash_file(Path(__file__))


def _dedupe(edges: list[dict]) -> list[dict]:
    seen: set[tuple] = set()
    kept: list[dict] = []
    for edge in edges:
        key = (edge["from"], edge["to"], edge["type"], edge.get("source"))
        if key not in seen:
            seen.add(key)
            kept.append(edge)
    return kept


def _owner_edges(nodes: list[Node], edges: list[dict]) -> list[dict]:
    """A ``tests/test_<stem>.py`` owns ``<stem>`` whether or not it imports it.

    tests/test_api_entry.py drives api_entry.py through ``runpy`` and
    tests/test_build.py runs build.yml through a subprocess; neither has an
    import statement, and both used to render as "no dedicated test file".
    The owner edge is a fact about the file names, so it is derived from them.

    Only the kinds of file a test can own compete for a stem, so a stylesheet
    and a script that share one stem do not hide each other's owner test.
    """
    by_id = {node.id for node in nodes}
    owned = _unambiguous_stems([n.id for n in nodes if n.sha256 and n.type in OWNED_TYPES])
    for stem, target in owned.items():
        test_path = f"tests/test_{stem}.py"
        if test_path not in by_id or test_path == target:
            continue
        edges = [e for e in edges
                 if not (e["from"] == test_path and e["to"] == target
                         and e["type"] == "exercises")]
        if not any(e["from"] == test_path and e["to"] == target and e["type"] == "tests"
                   for e in edges):
            edges.append({"from": test_path, "to": target, "type": "tests",
                          "source": "derived"})
    return edges


def build(root: Path | None = None, previous: dict | None = None) -> dict:
    """Build the graph, reusing unchanged nodes from ``previous`` when given.

    Reuse is keyed on file content, on this generator's own hash and on the
    module table's. When the derivation logic changes, every cached node and
    edge is suspect even though not one source file moved; when the set of
    modules changes, every cached *edge* is, because an import resolves
    against that set. Either way a mismatch forces a full rebuild. Skipping
    that would leave edges typed by rules the tool no longer follows, which
    is precisely the silent lie the map exists to avoid.
    """
    root = root or ROOT
    if unmerged := unmerged_files(root):
        raise MapError(UNMERGED_ADVICE + ": " + ", ".join(unmerged))
    curated = load_curated()
    files = tracked_files(root)
    table = ModuleTable.of(files)

    fingerprint = generator_fingerprint()
    if previous and (previous.get("generator_sha256") != fingerprint
                     or previous.get("module_table_sha256") != table.sha256):
        previous = None
    old_nodes = {n["id"]: n for n in (previous or {}).get("nodes", [])}
    old_edges = (previous or {}).get("edges", [])
    edges_by_source: dict[str, list[dict]] = {}
    for edge in old_edges:
        if edge.get("source") == "derived":
            edges_by_source.setdefault(edge["from"], []).append(edge)

    nodes: list[Node] = []
    edges: list[dict] = []
    reused = 0

    for path in files:
        digest = hash_file(root / path)
        cached = old_nodes.get(path)
        if cached and cached.get("sha256") == digest:
            node = Node(
                id=path, type=cached["type"], layer=cached["layer"],
                sha256=digest, lines=cached.get("lines", 0),
                exports=cached.get("exports", []), constants=cached.get("constants", {}),
                cli=cached.get("cli", ""),
            )
            edges.extend(edges_by_source.get(path, []))
            reused += 1
        else:
            node, file_edges = derive_node(path, root, table)
            edges.extend(file_edges)
        nodes.append(node)

    edges = _owner_edges(nodes, edges)

    # Curated layer on top: annotations onto file nodes, plus nodes of its own.
    by_id = {node.id: node for node in nodes}
    validate_curated(curated, set(by_id))
    for node_id, extra in curated["nodes"].items():
        target = by_id.get(node_id)
        if target is None:
            target = Node(id=node_id, type=extra["type"], layer=extra["layer"])
            nodes.append(target)
            by_id[node_id] = target
        target.role = extra.get("role", target.role)
        target.notes = extra.get("notes", target.notes)
        target.tags = sorted(set(target.tags) | set(extra.get("tags", [])))
        target.write_only = bool(extra.get("write_only", False))

    for edge in curated["edges"]:
        edges.append({**edge, "source": "curated"})

    # External package nodes, so every edge lands somewhere real.
    pins = read_pins(root, files)
    for edge in edges:
        if edge["to"].startswith("pkg:") and edge["to"] not in by_id:
            package = Node(id=edge["to"], type="package", layer="external",
                           pin=pins.get(edge["to"][4:].lower(), ""))
            nodes.append(package)
            by_id[package.id] = package

    referenced = {e["to"] for e in edges} | {e["from"] for e in edges}
    dangling = sorted(referenced - set(by_id))
    if dangling:
        raise MapError(
            "curated edges point at nodes that do not exist: " + ", ".join(dangling)
        )

    nodes.sort(key=lambda n: (n.layer, n.id))
    edges = _dedupe(edges)
    edges.sort(key=lambda e: (e["from"], e["type"], e["to"]))

    return {
        "schema": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "generator": f"{Path(__file__).resolve().parent.name}/{Path(__file__).name}",
        "generator_sha256": fingerprint,
        "module_table_sha256": table.sha256,
        "pipeline": curated.get("pipeline", []),
        "counts": {"nodes": len(nodes), "edges": len(edges), "reused": reused},
        "node_types": sorted({n.type for n in nodes}),
        "edge_types": sorted({e["type"] for e in edges}),
        "nodes": [n.to_json() for n in nodes],
        "edges": edges,
    }


def load_map(path: Path | None = None) -> dict:
    path = path or MAP_PATH
    if not path.is_file():
        raise MapError(f"no map at {path}; run `python tools/repo_map.py build`")
    try:
        graph = json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MapError(f"{path} is not valid JSON: {exc}") from None
    if graph.get("schema") != SCHEMA_VERSION:
        raise MapError(f"{path} is schema {graph.get('schema')!r}; this tool writes "
                       f"{SCHEMA_VERSION}. Rebuild it: python tools/repo_map.py build")
    return graph


def stale_files(graph: dict, root: Path | None = None) -> dict[str, list[str]]:
    """What the map no longer matches: changed, added or deleted files."""
    root = root or ROOT
    mapped = {n["id"]: n.get("sha256", "") for n in graph["nodes"] if "sha256" in n}
    on_disk = set(tracked_files(root))

    changed = sorted(p for p in on_disk & set(mapped)
                     if hash_file(root / p) != mapped[p])
    return {
        "changed": changed,
        "added": sorted(on_disk - set(mapped)),
        "removed": sorted(set(mapped) - on_disk),
    }


#: The header fields a fresh build may legitimately differ on: the date, and
#: how much of the previous map an incremental update reused.
_VOLATILE = ("generated", "counts")


def semantic_drift(graph: dict, root: Path | None = None) -> list[str]:
    """Every fact on which the committed map and a fresh build disagree.

    Empty when the map is true. The hashes say whether the *files* changed;
    this says whether the *facts* did - a derived field edited by hand, an
    edge that no import statement produces, a curated change that was never
    followed by ``update``.
    """
    fresh = build(root, previous=None)
    drift: list[str] = []
    for key in fresh:
        if key in _VOLATILE or key in ("nodes", "edges"):
            continue
        if graph.get(key) != fresh[key]:
            drift.append(f"{key}: {graph.get(key)!r} in the map, {fresh[key]!r} fresh")
    old_nodes = {n["id"]: n for n in graph.get("nodes", [])}
    new_nodes = {n["id"]: n for n in fresh["nodes"]}
    for node_id in sorted(set(old_nodes) | set(new_nodes)):
        old, new = old_nodes.get(node_id), new_nodes.get(node_id)
        if old != new:
            fields = sorted(k for k in set(old or {}) | set(new or {})
                            if (old or {}).get(k) != (new or {}).get(k))
            drift.append(f"node {node_id}: " + (", ".join(fields) if old and new
                                               else "missing from the map" if new
                                               else "not in a fresh build"))
    def key(edge: dict) -> tuple:
        return (edge["from"], edge["type"], edge["to"], edge.get("source"))
    old_edges = {key(e) for e in graph.get("edges", [])}
    new_edges = {key(e) for e in fresh["edges"]}
    for src, kind, dst, source in sorted(old_edges - new_edges):
        drift.append(f"edge {src} --{kind}--> {dst} ({source}) is in the map but not the source")
    for src, kind, dst, source in sorted(new_edges - old_edges):
        drift.append(f"edge {src} --{kind}--> {dst} ({source}) is in the source but not the map")
    return drift


def markdown_is_current(graph: dict, markdown_path: Path | None = None) -> bool:
    """Whether the committed markdown is what this map renders to."""
    markdown_path = markdown_path or MARKDOWN_PATH
    if not markdown_path.is_file():
        return False
    on_disk = markdown_path.read_bytes().replace(b"\r\n", b"\n")
    return on_disk == render_markdown(graph).encode("utf-8")


# --------------------------------------------------------------- rendering ----


def _curated_label() -> str:
    """The curated file as the map names it: relative to the root when it is under it."""
    try:
        return CURATED_PATH.relative_to(ROOT).as_posix()
    except ValueError:
        return f"{CURATED_PATH.parent.name}/{CURATED_PATH.name}"


def _tick(ids: list[str]) -> str:
    return ", ".join(f"`{i}`" for i in ids)


def _relation_lines(node: dict, out_edges: dict, in_edges: dict,
                    skip: tuple[str, ...]) -> list[str]:
    """One line per edge type the node has, out then in, for the generic types."""
    lines: list[str] = []
    for edge_type, (out_label, in_label) in EDGE_LABELS.items():
        if edge_type in skip:
            continue
        if out_label:
            targets = sorted({e["to"] for e in out_edges.get(node["id"], [])
                              if e["type"] == edge_type and not e["to"].startswith("pkg:")})
            if targets:
                lines.append(f"  - {out_label}: {_tick(targets)}")
        if in_label:
            sources = sorted({e["from"] for e in in_edges.get(node["id"], [])
                              if e["type"] == edge_type})
            if sources:
                lines.append(f"  - {in_label}: {_tick(sources)}")
    return lines


def render_markdown(graph: dict) -> str:
    """The agent-facing rendering: what each part is, and what it talks to."""
    out_edges: dict[str, list[dict]] = {}
    in_edges: dict[str, list[dict]] = {}
    for edge in graph["edges"]:
        out_edges.setdefault(edge["from"], []).append(edge)
        in_edges.setdefault(edge["to"], []).append(edge)

    lines = [
        "# Repository map",
        "",
        "<!-- GENERATED by tools/repo_map.py — do not edit by hand. -->",
        f"<!-- Curated descriptions live in {_curated_label()}. -->",
        "",
        f"Generated {graph['generated']} · {graph['counts']['nodes']} nodes · "
        f"{graph['counts']['edges']} edges · schema v{graph['schema']}",
        "",
        f"**{MAP_INTRO}** Check it is current "
        "with `python tools/repo_map.py check`, and refresh it after changing code "
        "with `python tools/repo_map.py update` (incremental — only re-parses what "
        "changed).",
        "",
    ]

    pipeline = graph.get("pipeline") or []
    if pipeline:
        lines += ["## The pipeline", "", "```", " → ".join(pipeline), "```", ""]

    rendered: set[str] = set()
    lines += ["## Modules", ""]
    for layer in ("core", "tooling", "ci", "desktop-app", "root"):
        members = [n for n in graph["nodes"]
                   if n["layer"] == layer and n["type"] in ("module", "tool", "ui",
                                                            "script", "workflow", "file")]
        if not members:
            continue
        lines += [f"### {layer}", ""]
        for node in members:
            rendered.add(node["id"])
            role = node.get("role", "")
            lines.append(f"- **`{node['id']}`**{' — ' + role if role else ''}")
            if node.get("cli"):
                lines.append(f"  - CLI: `{node['cli']}`")
            if node.get("constants"):
                constants = ", ".join(f"`{k}` = {v}" for k, v in node["constants"].items())
                lines.append(f"  - constants: {constants}")
            lines += _relation_lines(node, out_edges, in_edges,
                                     skip=("tests", "exercises", "depends_on"))
            covered_by = sorted({e["from"] for e in in_edges.get(node["id"], [])
                                 if e["type"] == "tests"})
            if covered_by:
                lines.append(f"  - {TESTED_BY}: {_tick(covered_by)}")
            elif node["type"] in ("module", "tool"):
                lines.append(f"  - {TESTED_BY}: **{NO_TEST_FILE}**")
            exercised_by = sorted({e["from"] for e in in_edges.get(node["id"], [])
                                   if e["type"] == "exercises"})
            if exercised_by:
                lines.append(f"  - {EXERCISED_BY} (imported, not its coverage): "
                             + _tick(exercised_by))
            if node.get("notes"):
                lines.append(f"  - note: {node['notes']}")
        lines.append("")

    described = [n for n in graph["nodes"]
                 if n.get("sha256") and n["id"] not in rendered and n.get("role")]
    if described:
        lines += ["## Tests, documents and data files with a stated purpose", ""]
        for node in described:
            lines.append(f"- **`{node['id']}`** — {node['role']}")
            lines += _relation_lines(node, out_edges, in_edges,
                                     skip=("tests", "exercises", "depends_on"))
            if node.get("notes"):
                lines.append(f"  - note: {node['notes']}")
        lines.append("")

    artifacts = [n for n in graph["nodes"] if n["type"] == "artifact"]
    if artifacts:
        lines += ["## Artifacts (files the system reads and writes at runtime)", ""]
        for node in artifacts:
            suffix = " *(write-only by design: nothing reads it back)*" if node.get("write_only") else ""
            lines.append(f"- **`{node['id']}`** — {node.get('role', '')}{suffix}")
            lines += _relation_lines(node, out_edges, in_edges,
                                     skip=("tests", "exercises", "depends_on"))
        lines.append("")

    concepts = [n for n in graph["nodes"] if n["type"] == "concept"]
    if concepts:
        lines += ["## Rules that cut across the code", ""]
        for node in concepts:
            lines.append(f"- **{node['id']}** — {node.get('role', '')}")
            holders = sorted({e["from"] for e in in_edges.get(node["id"], [])})
            if holders:
                lines.append(f"  - enforced in: {_tick(holders)}")
        lines.append("")

    externals = [n for n in graph["nodes"] if n["type"] == "package"]
    if externals:
        lines += ["## External dependencies", "",
                  "Python packages are pinned in the requirements files (a Python package "
                  "with no pin is an optional import, such as the OCR fallback); the "
                  "desktop shell's packages are pinned in `app/package.json`.", ""]
        for node in sorted(externals, key=lambda n: n["id"]):
            pin = (f"pinned {node['pin']}" if node.get("pin")
                   else "not pinned by a requirements file")
            users = sorted({e["from"] for e in in_edges.get(node["id"], [])})
            lines.append(f"- `{node['id'][4:]}` — {pin}; used by {_tick(users)}")
        lines.append("")

    lines += [
        "## Updating this map",
        "",
        "```",
        "python tools/repo_map.py update    # after any code change (incremental)",
        "python tools/repo_map.py check     # verify it matches the working tree",
        "```",
        "",
        "Derived facts (imports, exports, CLIs, tests, hashes) are parsed from the "
        "source — never hand-edit them. Descriptions, artifacts and cross-language "
        f"hops are curated in `{_curated_label()}`; edit that file and re-run "
        "`update`.",
        "",
    ]
    return "\n".join(lines)


def write_outputs(graph: dict, map_path: Path | None = None,
                  markdown_path: Path | None = None) -> None:
    """Write both outputs with LF line endings on every OS.

    The repository pins LF (.gitattributes) and the map hashes every tracked
    file; an output written with the platform's newline would be the one
    CRLF blob in the index and a whole-file diff on the next OS.
    """
    map_path = map_path or MAP_PATH
    markdown_path = markdown_path or MARKDOWN_PATH
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_bytes((json.dumps(graph, indent=2) + "\n").encode("utf-8"))
    markdown_path.write_bytes(render_markdown(graph).encode("utf-8"))


# --------------------------------------------------------------------- CLI ----


def _refuse_unmerged() -> bool:
    """Name every unmerged path and say so; False when there is none."""
    unmerged = unmerged_files()
    if unmerged:
        print(f"{len(unmerged)} file(s) are unmerged, so the map is not built over them:")
        for path in unmerged:
            print(f"  unmerged {path}")
        print(f"\n{UNMERGED_ADVICE}, then run the command again.")
    return bool(unmerged)


def _cmd_build(_ns: argparse.Namespace) -> int:
    if _refuse_unmerged():
        return 1
    graph = build()
    write_outputs(graph)
    print(f"Built {MAP_PATH.relative_to(ROOT)}: "
          f"{graph['counts']['nodes']} nodes, {graph['counts']['edges']} edges")
    return 0


def _cmd_update(_ns: argparse.Namespace) -> int:
    if _refuse_unmerged():
        return 1
    try:
        previous = load_map()
    except MapError as exc:
        print(f"{exc}\nBuilding from scratch.")
        previous = None

    if previous:
        drift = stale_files(previous)
        touched = drift["changed"] + drift["added"] + drift["removed"]
        for label in ("changed", "added", "removed"):
            for path in drift[label]:
                print(f"  {label:8} {path}")
        if not touched and not semantic_drift(previous) and markdown_is_current(previous):
            print("Map is already current; nothing to update.")
            return 0

    graph = build(previous=previous)
    write_outputs(graph)
    reused = graph["counts"]["reused"]
    print(f"Updated {MAP_PATH.relative_to(ROOT)}: {graph['counts']['nodes']} nodes, "
          f"{graph['counts']['edges']} edges ({reused} node(s) reused unchanged)")
    return 0


def _cmd_check(_ns: argparse.Namespace) -> int:
    if _refuse_unmerged():
        return 1
    for path in crlf_working_copies():
        print(f"warning: {path}: the working copy has CRLF; Git commits LF; the map hashes LF")
    graph = load_map()
    drift = stale_files(graph)
    total = sum(len(v) for v in drift.values())
    if total:
        print(f"Map is STALE — {total} file(s) differ from it:")
        for label in ("changed", "added", "removed"):
            for path in drift[label]:
                print(f"  {label:8} {path}")
        print("\nRefresh it with: python tools/repo_map.py update")
        return 1
    untracked = untracked_sources()
    if untracked:
        print(f"Map is STALE — {len(untracked)} source file(s) are not tracked by git, "
              "so the map has never seen them:")
        for path in untracked:
            print(f"  untracked {path}")
        print("\nStage them (git add), then: python tools/repo_map.py update")
        return 1
    facts = semantic_drift(graph)
    if facts:
        print(f"Map is STALE — the hashes match but {len(facts)} fact(s) differ from a fresh build:")
        for line in facts[:40]:
            print(f"  {line}")
        if len(facts) > 40:
            print(f"  … and {len(facts) - 40} more")
        print("\nRefresh it with: python tools/repo_map.py update")
        return 1
    if not markdown_is_current(graph):
        print(f"Map is STALE — {MARKDOWN_PATH.relative_to(ROOT)} does not match "
              f"{MAP_PATH.relative_to(ROOT)}.\n\nRefresh it with: python tools/repo_map.py update")
        return 1
    print(f"Map is current ({graph['counts']['nodes']} nodes, "
          f"generated {graph['generated']}).")
    return 0


def _cmd_show(ns: argparse.Namespace) -> int:
    graph = load_map()
    node = next((n for n in graph["nodes"] if n["id"] == ns.node), None)
    if node is None:
        matches = [n["id"] for n in graph["nodes"] if ns.node in n["id"]]
        print(f"No node {ns.node!r}." + (f" Did you mean: {', '.join(matches[:5])}"
                                         if matches else ""))
        return 1
    print(json.dumps(node, indent=2))
    print("\nout:")
    for edge in graph["edges"]:
        if edge["from"] == node["id"]:
            print(f"  --{edge['type']}--> {edge['to']}")
    print("in:")
    for edge in graph["edges"]:
        if edge["to"] == node["id"]:
            print(f"  <--{edge['type']}-- {edge['from']}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("build", help="rebuild the whole map from scratch")
    sub.add_parser("update", help="incremental refresh (the normal path)")
    sub.add_parser("check", help="verify the map matches the tree, fact for fact; exit 1 if not")
    show = sub.add_parser("show", help="print one node and its edges")
    show.add_argument("node", help="a node id, e.g. tracker/runner.py")

    ns = parser.parse_args(argv)
    commands = {"build": _cmd_build, "update": _cmd_update,
                "check": _cmd_check, "show": _cmd_show}
    try:
        return commands[ns.command](ns)
    except MapError as exc:
        print(f"repo_map: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
