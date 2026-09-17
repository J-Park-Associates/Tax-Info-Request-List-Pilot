"""Build and maintain the repository knowledge graph in ``docs/repo-map.json``.

The map exists so an agent starting a session can read one file instead of
re-reading the repository. That only works if the map is trustworthy, so it is
*derived* from the source rather than written by hand:

- **Derived** facts come from parsing the files — imports, exported names, line
  counts, which modules have a CLI, which tests cover what. They are recomputed
  and must never be hand-edited; the next update overwrites them.
- **Curated** facts are the things no parser can know: what a module is *for*,
  the artifacts that flow through the pipeline (``_manifest.xlsx``,
  ``reminder-draft.txt``), the order of the stages, and the cross-language
  hops. They live in ``docs/repo-map.curated.json`` and are merged on top.

Because the two layers are separate files, regenerating never destroys
judgment, and editing judgment never invalidates the derived half.

**Updating is incremental.** Every file node carries a SHA-256 of its content.
``update`` re-parses only the files whose hash changed, plus anything new, and
drops nodes whose file is gone. Everything else is copied forward untouched, so
updating after a one-file change costs one parse, not a full rebuild.

::

    python tools/repo_map.py build      # from scratch (rarely needed)
    python tools/repo_map.py update     # incremental — the normal path
    python tools/repo_map.py check      # is the map current? exit 1 if not
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

SCHEMA_VERSION = 1

#: Extensions worth a node. Everything else is noise in a code map.
#: ``.yml``/``.yaml`` earns its place because CI config is part of how the repo
#: works, not decoration around it — and an agent reading the map should know a
#: workflow exists. Only tracked files are mapped, so gitignored runtime files
#: (settings.json, drafts, logs) never appear.
#: The two test edges the map draws, and what it says when there is none.
#: CLAUDE.md explains them by these names; tests/test_single_source.py pins it.
MAP_INTRO = "Read this instead of re-scanning the repository."
TESTED_BY = "tested by"
EXERCISED_BY = "exercised by"
NO_TEST_FILE = "no dedicated test file"

SOURCE_SUFFIXES = {".py", ".js", ".html", ".css", ".md", ".bat",
                   ".json", ".txt", ".svg", ".yml", ".yaml"}

#: The map's own output. Writing the map changes these files, so mapping them
#: would leave the map permanently stale against itself. The curated file is
#: deliberately NOT excluded: it is an input, and editing it must show up as
#: drift so `update` rebuilds the descriptions.
EXCLUDED = {p.relative_to(ROOT).as_posix() for p in (MAP_PATH, MARKDOWN_PATH)}

#: Directory → (node type, layer). First match wins; order matters.
LAYERS: tuple[tuple[str, str, str], ...] = (
    (".github/", "workflow", "ci"),
    ("tracker/", "module", "core"),
    ("tests/", "test", "tests"),
    ("tools/", "tool", "tooling"),
    ("docs/", "doc", "docs"),
    ("app/renderer/", "ui", "desktop-app"),
    ("app/", "module", "desktop-app"),
)

_REQUIRE = re.compile(r"""require\(\s*["']([^"']+)["']\s*\)""")
_SPAWN = re.compile(r"""spawn\(\s*["']([^"']+)["']""")


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
    role: str = ""            # curated
    notes: str = ""           # curated
    tags: list[str] = field(default_factory=list)

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
        if self.role:
            out["role"] = self.role
        if self.notes:
            out["notes"] = self.notes
        if self.tags:
            out["tags"] = sorted(self.tags)
        return out


# ------------------------------------------------------------- collecting ----


def tracked_files(root: Path | None = None) -> list[str]:
    """Every file git tracks, so the map follows .gitignore for free."""
    root = root or ROOT
    try:
        listed = subprocess.run(
            ["git", "ls-files"], cwd=root, capture_output=True, text=True, check=True
        ).stdout.splitlines()
    except (subprocess.CalledProcessError, FileNotFoundError) as exc:
        raise MapError(f"could not list tracked files: {exc}") from None
    return sorted(
        path for path in listed
        if Path(path).suffix in SOURCE_SUFFIXES
        and path not in EXCLUDED
        and (root / path).is_file()
    )


def hash_file(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()[:16]


def classify(path: str) -> tuple[str, str]:
    for prefix, node_type, layer in LAYERS:
        if path.startswith(prefix):
            return node_type, layer
    suffix = Path(path).suffix
    if suffix == ".py":
        return "module", "root"
    if suffix == ".bat":
        return "script", "root"
    if suffix in (".md", ".txt"):
        return "doc", "docs"
    return "file", "root"


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

    Used to resolve a bare `import repo_map`. A stem shared by two files is
    left out entirely: guessing which one was meant is how a map starts
    lying.
    """
    counts: dict[str, list[str]] = {}
    for path in paths:
        counts.setdefault(Path(path).stem, []).append(path)
    return {stem: found[0] for stem, found in counts.items() if len(found) == 1}


# ---------------------------------------------------------------- parsing ----


def parse_python(text: str, path: str) -> tuple[list[str], list[tuple[str, str]], bool]:
    """Exported names, (module, kind) imports, and whether it has a CLI."""
    exports, imports, has_cli, _ = parse_python_full(text, path)
    return exports, imports, has_cli


def parse_python_full(
    text: str, path: str
) -> tuple[list[str], list[tuple[str, str]], bool, dict[str, str]]:
    """As parse_python, plus the module's literal constants.

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
    imports: list[tuple[str, str]] = []
    has_cli = False

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append((alias.name, "import"))
        elif isinstance(node, ast.ImportFrom):
            if node.module and not node.level:
                imports.append((node.module, "from"))
        elif isinstance(node, ast.If):
            # if __name__ == "__main__":
            test = node.test
            if (isinstance(test, ast.Compare)
                    and isinstance(test.left, ast.Name)
                    and test.left.id == "__name__"):
                has_cli = True

    constants: dict[str, str] = {}
    for node in tree.body:  # top level only — nested defs are not the API
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
            if not node.name.startswith("_"):
                exports.append(node.name)
        elif isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id.isupper():
                    exports.append(target.id)
                    literal = _literal_text(node.value)
                    if literal is not None and not target.id.startswith("_"):
                        constants[target.id] = literal

    return exports, imports, has_cli, constants


def _literal_text(value: ast.expr) -> str | None:
    """A short rendering of a literal constant, or None if it is not one."""
    if isinstance(value, ast.Constant):
        return repr(value.value)
    if isinstance(value, ast.Tuple) and all(isinstance(e, ast.Constant) for e in value.elts):
        rendered = ", ".join(repr(e.value) for e in value.elts)
        return f"({rendered},)" if len(value.elts) == 1 else f"({rendered})"
    if isinstance(value, ast.JoinedStr):
        return None
    return None


def parse_js(text: str) -> list[str]:
    return sorted({*_REQUIRE.findall(text), *_SPAWN.findall(text)})


# ----------------------------------------------------------------- graph ----


def derive_node(path: str, root: Path) -> tuple[Node, list[dict]]:
    """Parse one file into its node and the edges that start at it."""
    node_type, layer = classify(path)
    full = root / path
    node = Node(id=path, type=node_type, layer=layer, sha256=hash_file(full))
    edges: list[dict] = []

    if path.endswith(".py"):
        text = full.read_text(encoding="utf-8")
        node.lines = text.count("\n") + 1
        exports, imports, has_cli, constants = parse_python_full(text, path)
        node.exports = sorted(set(exports))
        node.constants = constants
        if has_cli:
            node.cli = f"python -m {module_name(path)}" if "/" in path else f"python {path}"

        python_files = [p for p in tracked_files(root) if p.endswith(".py")]
        internal = {module_name(p): p for p in python_files}
        by_stem = _unambiguous_stems(python_files)

        seen: set[tuple[str, str]] = set()
        for name, _kind in imports:
            # A bare name can still be ours: tests reach tools/repo_map.py as
            # `import repo_map` after a sys.path insert. Without this it would
            # be filed as an external package the project does not depend on.
            target = internal.get(name) or by_stem.get(name)
            if target and target != path:
                kind = test_edge_kind(path, target) if node_type == "test" else "imports"
                key = (target, kind)
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": path, "to": target, "type": kind,
                                  "source": "derived"})
            elif not target and "." not in name and not _is_stdlib(name):
                key = (f"pkg:{name}", "depends_on")
                if key not in seen:
                    seen.add(key)
                    edges.append({"from": path, "to": f"pkg:{name}",
                                  "type": "depends_on", "source": "derived"})

    elif path.endswith(".js"):
        text = full.read_text(encoding="utf-8")
        node.lines = text.count("\n") + 1
        for required in parse_js(text):
            if required.startswith("."):
                resolved = _resolve_relative(path, required, root)
                if resolved:
                    edges.append({"from": path, "to": resolved, "type": "imports",
                                  "source": "derived"})
            elif required not in ("python",):
                edges.append({"from": path, "to": f"pkg:{required}",
                              "type": "depends_on", "source": "derived"})
    else:
        try:
            node.lines = full.read_text(encoding="utf-8").count("\n") + 1
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


def generator_fingerprint() -> str:
    """Hash of this file — the cache key for everything it derives."""
    return hash_file(Path(__file__))


def build(root: Path | None = None, previous: dict | None = None) -> dict:
    """Build the graph, reusing unchanged nodes from ``previous`` when given.

    Reuse is keyed on file content *and* on this generator's own hash. When the
    derivation logic changes, every cached node and edge is suspect even though
    not one source file moved — so a changed generator forces a full rebuild.
    Skipping that would leave edges typed by rules the tool no longer follows,
    which is precisely the silent lie the map exists to avoid.
    """
    root = root or ROOT
    curated = load_curated()

    fingerprint = generator_fingerprint()
    if previous and previous.get("generator_sha256") != fingerprint:
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

    for path in tracked_files(root):
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
            node, file_edges = derive_node(path, root)
            edges.extend(file_edges)
        nodes.append(node)

    # Curated layer on top: annotations onto file nodes, plus nodes of its own.
    by_id = {node.id: node for node in nodes}
    for node_id, extra in curated["nodes"].items():
        target = by_id.get(node_id)
        if target is None:
            target = Node(
                id=node_id,
                type=extra.get("type", "concept"),
                layer=extra.get("layer", "concept"),
            )
            nodes.append(target)
            by_id[node_id] = target
        target.role = extra.get("role", target.role)
        target.notes = extra.get("notes", target.notes)
        target.tags = sorted(set(target.tags) | set(extra.get("tags", [])))

    for edge in curated["edges"]:
        edges.append({**edge, "source": "curated"})

    # External package nodes, so every edge lands somewhere real.
    for edge in edges:
        if edge["to"].startswith("pkg:") and edge["to"] not in by_id:
            package = Node(id=edge["to"], type="package", layer="external")
            nodes.append(package)
            by_id[package.id] = package

    referenced = {e["to"] for e in edges} | {e["from"] for e in edges}
    dangling = sorted(referenced - set(by_id))
    if dangling:
        raise MapError(
            "curated edges point at nodes that do not exist: " + ", ".join(dangling)
        )

    nodes.sort(key=lambda n: (n.layer, n.id))
    edges.sort(key=lambda e: (e["from"], e["type"], e["to"]))

    return {
        "schema": SCHEMA_VERSION,
        "generated": date.today().isoformat(),
        "generator": f"{Path(__file__).resolve().parent.name}/{Path(__file__).name}",
        "generator_sha256": fingerprint,
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
        return json.loads(path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise MapError(f"{path} is not valid JSON: {exc}") from None


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


# --------------------------------------------------------------- rendering ----


def _curated_label() -> str:
    """The curated file as the map names it: relative to the root when it is under it."""
    try:
        return CURATED_PATH.relative_to(ROOT).as_posix()
    except ValueError:
        return f"{CURATED_PATH.parent.name}/{CURATED_PATH.name}"


def render_markdown(graph: dict) -> str:
    """The agent-facing rendering: what each part is, and what it talks to."""
    nodes = {n["id"]: n for n in graph["nodes"]}
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

    lines += ["## Modules", ""]
    for layer in ("core", "tooling", "ci", "desktop-app", "root"):
        members = [n for n in graph["nodes"]
                   if n["layer"] == layer and n["type"] in ("module", "tool", "ui",
                                                            "script", "workflow")]
        if not members:
            continue
        lines += [f"### {layer}", ""]
        for node in members:
            role = node.get("role", "")
            lines.append(f"- **`{node['id']}`**{' — ' + role if role else ''}")
            if node.get("cli"):
                lines.append(f"  - CLI: `{node['cli']}`")
            if node.get("constants"):
                rendered = ", ".join(f"`{k}` = {v}" for k, v in node["constants"].items())
                lines.append(f"  - constants: {rendered}")
            imports = sorted({e["to"] for e in out_edges.get(node["id"], [])
                              if e["type"] == "imports" and not e["to"].startswith("pkg:")})
            if imports:
                lines.append(f"  - imports: {', '.join(f'`{i}`' for i in imports)}")
            used_by = sorted({e["from"] for e in in_edges.get(node["id"], [])
                              if e["type"] == "imports"})
            if used_by:
                lines.append(f"  - used by: {', '.join(f'`{u}`' for u in used_by)}")
            covered_by = sorted({e["from"] for e in in_edges.get(node["id"], [])
                                 if e["type"] == "tests"})
            if covered_by:
                lines.append(f"  - {TESTED_BY}: {', '.join(f'`{c}`' for c in covered_by)}")
            elif node["type"] in ("module", "tool"):
                lines.append(f"  - {TESTED_BY}: **{NO_TEST_FILE}**")
            exercised_by = sorted({e["from"] for e in in_edges.get(node["id"], [])
                                   if e["type"] == "exercises"})
            if exercised_by:
                lines.append(f"  - {EXERCISED_BY} (imported, not its coverage): "
                             + ", ".join(f"`{x}`" for x in exercised_by))
            writes = sorted({e["to"] for e in out_edges.get(node["id"], [])
                             if e["type"] == "writes"})
            if writes:
                lines.append(f"  - writes: {', '.join(f'`{w}`' for w in writes)}")
            reads = sorted({e["to"] for e in out_edges.get(node["id"], [])
                            if e["type"] == "reads"})
            if reads:
                lines.append(f"  - reads: {', '.join(f'`{r}`' for r in reads)}")
            if node.get("notes"):
                lines.append(f"  - note: {node['notes']}")
        lines.append("")

    artifacts = [n for n in graph["nodes"] if n["type"] == "artifact"]
    if artifacts:
        lines += ["## Artifacts (files the system reads and writes at runtime)", ""]
        for node in artifacts:
            lines.append(f"- **`{node['id']}`** — {node.get('role', '')}")
            writers = sorted({e["from"] for e in in_edges.get(node["id"], [])
                              if e["type"] == "writes"})
            readers = sorted({e["from"] for e in in_edges.get(node["id"], [])
                              if e["type"] == "reads"})
            if writers:
                lines.append(f"  - written by: {', '.join(f'`{w}`' for w in writers)}")
            if readers:
                lines.append(f"  - read by: {', '.join(f'`{r}`' for r in readers)}")
        lines.append("")

    concepts = [n for n in graph["nodes"] if n["type"] == "concept"]
    if concepts:
        lines += ["## Rules that cut across the code", ""]
        for node in concepts:
            lines.append(f"- **{node['id']}** — {node.get('role', '')}")
            holders = sorted({e["from"] for e in in_edges.get(node["id"], [])})
            if holders:
                lines.append(f"  - enforced in: {', '.join(f'`{h}`' for h in holders)}")
        lines.append("")

    externals = sorted(n["id"][4:] for n in graph["nodes"] if n["type"] == "package")
    if externals:
        lines += ["## External dependencies", "",
                  ", ".join(f"`{e}`" for e in externals), ""]

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
    map_path = map_path or MAP_PATH
    markdown_path = markdown_path or MARKDOWN_PATH
    map_path.parent.mkdir(parents=True, exist_ok=True)
    map_path.write_text(json.dumps(graph, indent=2) + "\n", encoding="utf-8")
    markdown_path.write_text(render_markdown(graph), encoding="utf-8")


# --------------------------------------------------------------------- CLI ----


def _cmd_build(_ns: argparse.Namespace) -> int:
    graph = build()
    write_outputs(graph)
    print(f"Built {MAP_PATH.relative_to(ROOT)}: "
          f"{graph['counts']['nodes']} nodes, {graph['counts']['edges']} edges")
    return 0


def _cmd_update(_ns: argparse.Namespace) -> int:
    try:
        previous = load_map()
    except MapError:
        print("No existing map — building from scratch.")
        previous = None

    if previous:
        drift = stale_files(previous)
        touched = drift["changed"] + drift["added"] + drift["removed"]
        if not touched:
            print("Map is already current; nothing to update.")
            return 0
        for label in ("changed", "added", "removed"):
            for path in drift[label]:
                print(f"  {label:8} {path}")

    graph = build(previous=previous)
    write_outputs(graph)
    reused = graph["counts"]["reused"]
    print(f"Updated {MAP_PATH.relative_to(ROOT)}: {graph['counts']['nodes']} nodes, "
          f"{graph['counts']['edges']} edges ({reused} node(s) reused unchanged)")
    return 0


def _cmd_check(_ns: argparse.Namespace) -> int:
    graph = load_map()
    drift = stale_files(graph)
    total = sum(len(v) for v in drift.values())
    if not total:
        print(f"Map is current ({graph['counts']['nodes']} nodes, "
              f"generated {graph['generated']}).")
        return 0
    print(f"Map is STALE — {total} file(s) differ from it:")
    for label in ("changed", "added", "removed"):
        for path in drift[label]:
            print(f"  {label:8} {path}")
    print("\nRefresh it with: python tools/repo_map.py update")
    return 1


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
    sub.add_parser("check", help="verify the map matches the tree; exit 1 if stale")
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
