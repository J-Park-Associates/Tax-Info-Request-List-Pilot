"""Tests for tools/repo_map.py — the map has to stay trustworthy.

A map that drifts from the code is worse than no map, because an agent will
believe it. So what is tested here is the trust contract: derived facts come
from the source, curated judgment survives regeneration, drift is detected,
and an update re-parses only what changed.
"""

import ast
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))

import repo_map  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def repo(tmp_path, monkeypatch):
    """A tiny git repo with two modules, a test and a curated overlay."""
    (tmp_path / "pkg").mkdir()
    (tmp_path / "tests").mkdir()
    (tmp_path / "docs").mkdir()
    (tmp_path / "pkg" / "core.py").write_text(
        "CONSTANT = 1\n\n\ndef public():\n    pass\n\n\ndef _private():\n    pass\n",
        encoding="utf-8",
    )
    (tmp_path / "pkg" / "app.py").write_text(
        'import json\n\nfrom pkg.core import public\n\n\n'
        'def run():\n    return public()\n\n\n'
        'if __name__ == "__main__":\n    run()\n',
        encoding="utf-8",
    )
    (tmp_path / "tests" / "test_core.py").write_text(
        "from pkg.core import public\n\n\ndef test_it():\n    assert public() is None\n",
        encoding="utf-8",
    )
    (tmp_path / "docs" / "repo-map.curated.json").write_text(
        json.dumps({
            "pipeline": ["core", "app"],
            "nodes": {
                "pkg/core.py": {"role": "the core", "notes": "hand-written"},
                "artifact:output.txt": {"type": "artifact", "layer": "runtime",
                                        "role": "what it writes"},
            },
            "edges": [{"from": "pkg/app.py", "to": "artifact:output.txt",
                       "type": "writes"}],
        }),
        encoding="utf-8",
    )

    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)

    monkeypatch.setattr(repo_map, "ROOT", tmp_path)
    monkeypatch.setattr(repo_map, "CURATED_PATH", tmp_path / "docs" / "repo-map.curated.json")
    monkeypatch.setattr(repo_map, "MAP_PATH", tmp_path / "docs" / "repo-map.json")
    monkeypatch.setattr(repo_map, "MARKDOWN_PATH", tmp_path / "docs" / "repo-map.md")
    return tmp_path


def node(graph, node_id):
    return next(n for n in graph["nodes"] if n["id"] == node_id)


def edges(graph, **match):
    return [e for e in graph["edges"]
            if all(e.get(k) == v for k, v in match.items())]


# ----------------------------------------------------------------- derived ----


def test_imports_between_internal_modules_become_edges(repo):
    graph = repo_map.build(repo)
    assert edges(graph, **{"from": "pkg/app.py", "to": "pkg/core.py", "type": "imports"})


def test_the_test_file_that_owns_a_module_by_name_gets_a_tests_edge(repo):
    graph = repo_map.build(repo)
    assert edges(graph, **{"from": "tests/test_core.py", "to": "pkg/core.py",
                           "type": "tests"})
    assert not edges(graph, **{"from": "tests/test_core.py", "type": "imports"})


def test_any_other_test_importing_a_module_only_exercises_it(repo):
    """Borrowing a fixture is not coverage, and must not read as coverage."""
    (repo / "tests" / "test_other.py").write_text(
        "from pkg.core import public\n\n\ndef test_something_else():\n    assert True\n",
        encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)

    assert edges(graph, **{"from": "tests/test_other.py", "to": "pkg/core.py",
                           "type": "exercises"})
    assert not edges(graph, **{"from": "tests/test_other.py", "to": "pkg/core.py",
                               "type": "tests"})


def test_a_test_importing_another_test_is_not_coverage_of_it(repo):
    """A shared fixture helper is an import, nothing more."""
    (repo / "tests" / "test_helper_user.py").write_text(
        "from tests.test_core import public\n\n\ndef test_x():\n    assert True\n",
        encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)

    assert edges(graph, **{"from": "tests/test_helper_user.py",
                           "to": "tests/test_core.py", "type": "imports"})
    assert not edges(graph, to="tests/test_core.py", type="tests")
    assert not edges(graph, to="tests/test_core.py", type="exercises")


@pytest.mark.parametrize("module, expected", [
    ("tracker/filer.py", "tests/test_filer.py"),
    ("tools/repo_map.py", "tests/test_repo_map.py"),
])
def test_the_owning_test_file_is_found_by_name(module, expected):
    assert repo_map.dedicated_test_for(module) == expected


def test_a_bare_import_of_a_repo_file_is_not_an_external_package(repo):
    """`import repo_map` after a sys.path insert is ours, not a dependency."""
    (repo / "tests" / "test_tooling.py").write_text(
        "import core\n\n\ndef test_x():\n    assert True\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)

    assert not edges(graph, to="pkg:core")
    assert edges(graph, **{"from": "tests/test_tooling.py", "to": "pkg/core.py"})


def test_an_ambiguous_bare_name_is_not_guessed_at(repo):
    """Two files share the stem, so neither is assumed — guessing is how a map lies."""
    (repo / "pkg" / "dup.py").write_text("x = 1\n", encoding="utf-8")
    (repo / "tests" / "dup.py").write_text("y = 2\n", encoding="utf-8")
    (repo / "pkg" / "uses.py").write_text("import dup\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)

    assert not edges(graph, **{"from": "pkg/uses.py", "to": "pkg/dup.py"})
    assert not edges(graph, **{"from": "pkg/uses.py", "to": "tests/dup.py"})


def test_public_names_are_exported_and_private_ones_are_not(repo):
    exports = node(repo_map.build(repo), "pkg/core.py")["exports"]
    assert exports == ["CONSTANT", "public"]


def test_a_main_block_is_recorded_as_a_cli(repo):
    graph = repo_map.build(repo)
    assert node(graph, "pkg/app.py")["cli"] == "python -m pkg.app"
    assert "cli" not in node(graph, "pkg/core.py")


def test_standard_library_imports_are_not_dependencies(repo):
    """Otherwise every module would list json, pathlib and datetime."""
    assert not edges(repo_map.build(repo), to="pkg:json")


def test_third_party_imports_become_dependency_nodes(repo):
    (repo / "pkg" / "extra.py").write_text("import openpyxl\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    graph = repo_map.build(repo)
    assert edges(graph, to="pkg:openpyxl", type="depends_on")
    assert node(graph, "pkg:openpyxl")["type"] == "package"


# ----------------------------------------------------------------- curated ----


def test_curated_descriptions_are_merged_onto_derived_nodes(repo):
    core = node(repo_map.build(repo), "pkg/core.py")
    assert core["role"] == "the core"
    assert core["notes"] == "hand-written"
    assert core["exports"] == ["CONSTANT", "public"], "derived facts survive too"


def test_curated_nodes_that_are_not_files_are_added(repo):
    artifact = node(repo_map.build(repo), "artifact:output.txt")
    assert artifact["type"] == "artifact"
    assert artifact["role"] == "what it writes"


def test_every_edge_says_where_it_came_from(repo):
    graph = repo_map.build(repo)
    assert {e["source"] for e in graph["edges"]} <= {"derived", "curated"}
    assert edges(graph, **{"from": "pkg/app.py", "to": "artifact:output.txt",
                           "source": "curated"})


def test_a_curated_edge_to_a_nonexistent_node_fails_loudly(repo):
    """A typo in the curated file must not quietly produce a broken graph."""
    curated = repo / "docs" / "repo-map.curated.json"
    data = json.loads(curated.read_text())
    data["edges"].append({"from": "pkg/app.py", "to": "pkg/ghost.py", "type": "writes"})
    curated.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(repo_map.MapError, match="pkg/ghost.py"):
        repo_map.build(repo)


def _curated(repo, mutate):
    path = repo / "docs" / "repo-map.curated.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    mutate(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_a_curated_annotation_for_a_file_that_is_not_tracked_is_refused(repo):
    """Before: it became a phantom concept node rendered among the rules, with no error."""
    _curated(repo, lambda d: d["nodes"].update({"pkg/ghost.py": {"role": "gone"}}))
    with pytest.raises(repo_map.MapError, match="pkg/ghost.py.*not tracked"):
        repo_map.build(repo)


def test_a_misspelled_curated_type_is_refused(repo):
    """Before: the node stayed in the JSON and silently dropped off the page."""
    _curated(repo, lambda d: d["nodes"]["artifact:output.txt"].update({"type": "artefact"}))
    with pytest.raises(repo_map.MapError, match="type must be"):
        repo_map.build(repo)


def test_an_unknown_curated_key_is_refused(repo):
    """Before: a `note` key was ignored and the note lost."""
    _curated(repo, lambda d: d["nodes"]["pkg/core.py"].update({"note": "lost"}))
    with pytest.raises(repo_map.MapError, match="unknown key"):
        repo_map.build(repo)


def test_a_curated_edge_may_not_claim_a_derived_type(repo):
    """A hand-written `tests` edge would render as coverage the source never showed."""
    _curated(repo, lambda d: d["edges"].append(
        {"from": "tests/test_core.py", "to": "pkg/app.py", "type": "tests"}))
    with pytest.raises(repo_map.MapError, match="derived"):
        repo_map.build(repo)


def test_an_unknown_edge_type_and_a_self_edge_are_refused(repo):
    _curated(repo, lambda d: d["edges"].append(
        {"from": "pkg/app.py", "to": "artifact:output.txt", "type": "write"}))
    with pytest.raises(repo_map.MapError, match="unknown type"):
        repo_map.build(repo)
    _curated(repo, lambda d: d["edges"].__setitem__(
        -1, {"from": "pkg/app.py", "to": "pkg/app.py", "type": "writes"}))
    with pytest.raises(repo_map.MapError, match="itself"):
        repo_map.build(repo)


def test_malformed_curated_json_fails_loudly(repo):
    (repo / "docs" / "repo-map.curated.json").write_text("{not json", encoding="utf-8")
    with pytest.raises(repo_map.MapError, match="not valid JSON"):
        repo_map.build(repo)


# ------------------------------------------------------------- incremental ----


def test_an_unchanged_file_is_reused_rather_than_reparsed(repo):
    first = repo_map.build(repo)
    (repo / "pkg" / "core.py").write_text(
        "CONSTANT = 1\nNEW = 2\n\n\ndef public():\n    pass\n", encoding="utf-8")

    second = repo_map.build(repo, previous=first)

    assert second["counts"]["reused"] == len(
        [n for n in first["nodes"] if "sha256" in n]) - 1, "only the edited file re-parsed"
    assert node(second, "pkg/core.py")["exports"] == ["CONSTANT", "NEW", "public"]


def test_changing_the_generator_invalidates_every_cached_edge(repo):
    """New derivation rules must not leave edges typed by the old ones."""
    first = repo_map.build(repo)
    assert first["generator_sha256"] == repo_map.generator_fingerprint()

    stale = {**first, "generator_sha256": "0000000000000000"}
    stale["edges"] = [{"from": "pkg/app.py", "to": "pkg/core.py",
                       "type": "a-rule-we-no-longer-use", "source": "derived"}]

    second = repo_map.build(repo, previous=stale)

    assert not edges(second, type="a-rule-we-no-longer-use")
    assert second["counts"]["reused"] == 0, "a changed generator rebuilds everything"
    assert edges(second, **{"from": "pkg/app.py", "to": "pkg/core.py",
                            "type": "imports"})


def test_a_reused_node_keeps_its_derived_detail(repo):
    first = repo_map.build(repo)
    second = repo_map.build(repo, previous=first)
    assert node(second, "pkg/app.py") == node(first, "pkg/app.py")


def test_a_new_edge_replaces_the_old_one_for_a_changed_file(repo):
    """Stale edges from a previous version must not linger."""
    first = repo_map.build(repo)
    assert edges(first, **{"from": "pkg/app.py", "to": "pkg/core.py"})

    (repo / "pkg" / "app.py").write_text("def run():\n    pass\n", encoding="utf-8")
    second = repo_map.build(repo, previous=first)

    assert not edges(second, **{"from": "pkg/app.py", "to": "pkg/core.py"})


def test_a_deleted_file_drops_out_of_the_map(repo):
    first = repo_map.build(repo)
    assert edges(first, **{"from": "tests/test_core.py", "type": "tests"})

    (repo / "tests" / "test_core.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    second = repo_map.build(repo, previous=first)

    assert not [n for n in second["nodes"] if n["id"] == "tests/test_core.py"]
    assert not edges(second, **{"from": "tests/test_core.py"})


def test_deleting_a_file_the_curated_layer_describes_fails_loudly(repo):
    """Better a loud error than a map quietly pointing at a file that is gone."""
    (repo / "pkg" / "app.py").unlink()          # a curated edge starts here
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    with pytest.raises(repo_map.MapError, match="pkg/app.py"):
        repo_map.build(repo)


# ------------------------------------------------------------------- drift ----


def test_a_fresh_map_reports_no_drift(repo):
    assert repo_map.stale_files(repo_map.build(repo), repo) == {
        "changed": [], "added": [], "removed": []}


def test_an_edited_file_is_reported_as_changed(repo):
    graph = repo_map.build(repo)
    (repo / "pkg" / "core.py").write_text("CONSTANT = 99\n", encoding="utf-8")
    assert repo_map.stale_files(graph, repo)["changed"] == ["pkg/core.py"]


def test_a_new_file_is_reported_as_added(repo):
    graph = repo_map.build(repo)
    (repo / "pkg" / "later.py").write_text("x = 1\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert repo_map.stale_files(graph, repo)["added"] == ["pkg/later.py"]


def test_a_removed_file_is_reported_as_removed(repo):
    graph = repo_map.build(repo)
    (repo / "pkg" / "app.py").unlink()
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)
    assert repo_map.stale_files(graph, repo)["removed"] == ["pkg/app.py"]


def test_ci_config_is_mapped(repo):
    """A workflow is part of how the repo works, so the map must know it exists."""
    (repo / ".github" / "workflows").mkdir(parents=True)
    (repo / ".github" / "workflows" / "ci.yml").write_text(
        "name: CI\non: [push]\n", encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)
    ci = node(graph, ".github/workflows/ci.yml")

    assert ci["type"] == "workflow"
    assert ci["layer"] == "ci"


def test_the_generated_outputs_are_not_mapped(repo):
    """Mapping the map would leave it permanently stale against itself."""
    repo_map.write_outputs(repo_map.build(repo),
                           repo / "docs" / "repo-map.json",
                           repo / "docs" / "repo-map.md")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)
    ids = {n["id"] for n in graph["nodes"]}
    for excluded in repo_map.EXCLUDED:
        assert excluded not in ids
    assert repo_map.stale_files(graph, repo) == {"changed": [], "added": [], "removed": []}


def test_the_curated_file_is_mapped_so_editing_it_shows_as_drift(repo):
    """Its edits must trigger a rebuild, unlike the generated outputs."""
    graph = repo_map.build(repo)
    assert "docs/repo-map.curated.json" in {n["id"] for n in graph["nodes"]}

    curated = repo / "docs" / "repo-map.curated.json"
    data = json.loads(curated.read_text())
    data["nodes"]["pkg/core.py"]["role"] = "a better description"
    curated.write_text(json.dumps(data), encoding="utf-8")

    assert repo_map.stale_files(graph, repo)["changed"] == ["docs/repo-map.curated.json"]


# --------------------------------------------------------------- rendering ----


def test_the_markdown_leads_with_how_to_use_and_refresh_it(repo):
    text = repo_map.render_markdown(repo_map.build(repo))
    assert repo_map.MAP_INTRO in text
    assert "repo_map.py update" in text
    assert "do not edit by hand" in text


def test_the_markdown_carries_the_curated_pipeline_and_roles(repo):
    text = repo_map.render_markdown(repo_map.build(repo))
    assert "core → app" in text
    assert "the core" in text


# ------------------------------------------------ the real map in this repo ----


def test_the_committed_map_is_current():
    """The map in docs/ must match this repository, or it is misinformation.

    Hashes first, then every derived fact against a fresh build, then the
    rendered page against the JSON: a hand-edited field, a forged edge or a
    stale repo-map.md each used to pass on the hashes alone.
    """
    graph = repo_map.load_map(ROOT / "docs" / "repo-map.json")
    drift = repo_map.stale_files(graph, ROOT)
    assert drift == {"changed": [], "added": [], "removed": []}, (
        "docs/repo-map.json is stale — run `python tools/repo_map.py update`"
    )
    assert repo_map.semantic_drift(graph, ROOT) == [], (
        "docs/repo-map.json does not match a fresh build — run `python tools/repo_map.py update`"
    )
    assert repo_map.markdown_is_current(graph, ROOT / "docs" / "repo-map.md"), (
        "docs/repo-map.md does not match docs/repo-map.json — run `python tools/repo_map.py update`"
    )


# ------------------------------------------------- resolution and scope ----


def add(repo, rel: str, text: str) -> None:
    path = repo / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)


def test_from_package_import_module_draws_the_module_and_the_package(repo):
    """`from pkg import core` names core and executes pkg/__init__.py: two real edges.

    Before, both collapsed onto the package, and a module imported only that
    way showed no importer at all.
    """
    add(repo, "pkg/__init__.py", "")
    add(repo, "pkg/user.py", "from pkg import core\n\n\ndef go():\n    return core\n")

    graph = repo_map.build(repo)

    assert edges(graph, **{"from": "pkg/user.py", "to": "pkg/core.py", "type": "imports"})
    assert edges(graph, **{"from": "pkg/user.py", "to": "pkg/__init__.py", "type": "imports"})


def test_a_test_written_from_package_import_module_owns_the_module(repo):
    add(repo, "pkg/__init__.py", "")
    add(repo, "tests/test_app.py", "from pkg import app\n\n\ndef test_x():\n    assert app\n")

    graph = repo_map.build(repo)

    assert edges(graph, **{"from": "tests/test_app.py", "to": "pkg/app.py", "type": "tests"})
    assert edges(graph, **{"from": "tests/test_app.py", "to": "pkg/__init__.py",
                           "type": "exercises"})


def test_an_imported_name_that_is_not_a_module_is_not_a_dependency(repo):
    add(repo, "pkg/user.py", "from pkg.core import public\n")
    graph = repo_map.build(repo)
    assert not edges(graph, **{"from": "pkg/user.py", "type": "depends_on"})
    assert edges(graph, **{"from": "pkg/user.py", "to": "pkg/core.py", "type": "imports"})


def test_an_import_inside_a_function_or_a_main_block_is_at_call_time(repo):
    """It runs when called, not when loaded: a different claim, and a different edge."""
    add(repo, "pkg/late.py",
        'def run():\n    from pkg import core\n    return core\n\n\n'
        'if __name__ == "__main__":\n    from pkg.app import run as go\n    go()\n')

    graph = repo_map.build(repo)

    assert edges(graph, **{"from": "pkg/late.py", "to": "pkg/core.py", "type": "imports_at_call"})
    assert not edges(graph, **{"from": "pkg/late.py", "to": "pkg/core.py", "type": "imports"})
    assert edges(graph, **{"from": "pkg/late.py", "to": "pkg/app.py", "type": "imports_at_call"})


def test_a_module_loaded_and_also_imported_inside_a_function_is_one_dependency(repo):
    add(repo, "pkg/late.py",
        "from pkg.core import public\n\n\ndef run():\n    from pkg import core\n    return core, public\n")
    graph = repo_map.build(repo)
    assert edges(graph, **{"from": "pkg/late.py", "to": "pkg/core.py", "type": "imports"})
    assert not edges(graph, **{"from": "pkg/late.py", "to": "pkg/core.py", "type": "imports_at_call"})


def test_the_owner_test_is_found_by_name_even_without_an_import(repo):
    """A test driving its module through runpy or a subprocess is still its coverage."""
    add(repo, "tests/test_app.py",
        "import runpy\n\n\ndef test_x():\n    runpy.run_path('pkg/app.py')\n")
    graph = repo_map.build(repo)
    assert edges(graph, **{"from": "tests/test_app.py", "to": "pkg/app.py", "type": "tests"})


def test_a_dotted_third_party_import_depends_on_its_package(repo):
    add(repo, "pkg/extra.py", "from openpyxl.styles import Font\n")
    graph = repo_map.build(repo)
    assert edges(graph, **{"from": "pkg/extra.py", "to": "pkg:openpyxl", "type": "depends_on"})


def test_node_builtins_are_not_dependencies_of_the_shell(repo):
    add(repo, "app/main.js",
        'const fs = require("fs");\nconst path = require("node:path");\n'
        'const { app } = require("electron");\n')
    graph = repo_map.build(repo)
    assert edges(graph, to="pkg:electron", type="depends_on")
    assert not edges(graph, to="pkg:fs")
    assert not edges(graph, to="pkg:path")


@pytest.mark.parametrize("path, expected", [
    ("app/package.json", ("file", "desktop-app")),
    ("app/package-lock.json", ("file", "desktop-app")),
    ("app/renderer/app.js", ("module", "desktop-app")),
    ("app/renderer/index.html", ("ui", "desktop-app")),
    (".github/workflows/ci.yml", ("workflow", "ci")),
    ("tests/test_x.py", ("test", "tests")),
    ("tools/x.py", ("tool", "tooling")),
    ("tracker/x.py", ("module", "core")),
    ("README.md", ("doc", "docs")),
    ("requirements.txt", ("doc", "docs")),
    ("Build App.bat", ("script", "root")),
    ("pyproject.toml", ("file", "root")),
    ("api_entry.spec", ("file", "root")),
    ("pilot/installer/setup.iss", ("file", "root")),
])
def test_type_comes_from_the_suffix_and_layer_from_the_directory(path, expected):
    """A lockfile under app/ is a file, not an untested module."""
    assert repo_map.classify(path) == expected


def test_private_upper_case_names_are_not_exported_and_line_counts_are_exact(repo):
    add(repo, "pkg/core.py", "CONSTANT = 1\n_PRIVATE = 2\n\n\ndef public():\n    pass\n")
    core = node(repo_map.build(repo), "pkg/core.py")
    assert core["exports"] == ["CONSTANT", "public"]
    assert core["constants"] == {"CONSTANT": "1"}
    assert core["lines"] == 6


def test_packages_say_whether_a_requirements_file_pins_them(repo):
    add(repo, "requirements.txt", "openpyxl==3.1.5\n")
    add(repo, "pkg/extra.py", "import openpyxl\nimport pdfplumber\n")
    graph = repo_map.build(repo)
    assert node(graph, "pkg:openpyxl")["pin"] == "3.1.5 (requirements.txt)"
    assert "pin" not in node(graph, "pkg:pdfplumber")


# ------------------------------------------------------ check semantics ----


def test_a_hand_edited_derived_fact_is_drift_though_every_hash_matches(repo):
    graph = repo_map.build(repo)
    assert repo_map.semantic_drift(graph, repo) == []

    forged = json.loads(json.dumps(graph))
    node(forged, "pkg/core.py")["exports"] = []
    assert repo_map.stale_files(forged, repo) == {"changed": [], "added": [], "removed": []}
    drift = repo_map.semantic_drift(forged, repo)
    assert drift and all("pkg/core.py" in line for line in drift)


def test_a_forged_edge_is_drift(repo):
    graph = repo_map.build(repo)
    forged = json.loads(json.dumps(graph))
    forged["edges"].append({"from": "tests/test_core.py", "to": "pkg/app.py",
                            "type": "tests", "source": "derived"})
    drift = repo_map.semantic_drift(forged, repo)
    assert drift == ["edge tests/test_core.py --tests--> pkg/app.py (derived) is in the map "
                     "but not the source"]


def test_an_incremental_update_never_differs_from_a_fresh_build(repo):
    first = repo_map.build(repo)
    add(repo, "pkg/core.py", "CONSTANT = 1\nNEW = 2\n\n\ndef public():\n    pass\n")
    second = repo_map.build(repo, previous=first)
    assert second["counts"]["reused"] > 0
    assert repo_map.semantic_drift(second, repo) == []


def test_a_file_that_makes_a_stem_ambiguous_rebuilds_every_cached_edge(repo):
    """A bare `import core` resolved against one set of files is only as good as that set."""
    add(repo, "pkg/uses.py", "import core\n")
    first = repo_map.build(repo)
    assert edges(first, **{"from": "pkg/uses.py", "to": "pkg/core.py"})

    add(repo, "tests/core.py", "y = 2\n")
    second = repo_map.build(repo, previous=first)

    assert not edges(second, **{"from": "pkg/uses.py", "to": "pkg/core.py"})
    assert second["counts"]["reused"] == 0, "the module table changed, so nothing is trusted"
    assert second["module_table_sha256"] != first["module_table_sha256"]


def test_outputs_are_written_lf_on_every_os(repo):
    graph = repo_map.build(repo)
    repo_map.write_outputs(graph, repo / "docs" / "repo-map.json", repo / "docs" / "repo-map.md")
    assert b"\r\n" not in (repo / "docs" / "repo-map.json").read_bytes()
    assert b"\r\n" not in (repo / "docs" / "repo-map.md").read_bytes()


def test_the_markdown_is_checked_against_the_json(repo):
    graph = repo_map.build(repo)
    markdown = repo / "docs" / "repo-map.md"
    repo_map.write_outputs(graph, repo / "docs" / "repo-map.json", markdown)
    assert repo_map.markdown_is_current(graph, markdown)
    markdown.write_bytes(markdown.read_bytes().replace(b"\n", b"\r\n"))
    assert repo_map.markdown_is_current(graph, markdown), "line endings are not a difference"
    markdown.write_bytes(b"# stale\n")
    assert not repo_map.markdown_is_current(graph, markdown)


def test_a_source_file_git_does_not_track_is_named(repo):
    (repo / "pkg" / "new_module.py").write_text("x = 1\n", encoding="utf-8")
    assert repo_map.untracked_sources(repo) == ["pkg/new_module.py"]
    assert repo_map.stale_files(repo_map.build(repo), repo)["added"] == [], (
        "the hashes cannot see it; only the untracked check can")


def test_a_map_of_an_older_schema_is_refused(repo):
    graph = repo_map.build(repo)
    path = repo / "docs" / "repo-map.json"
    path.write_text(json.dumps({**graph, "schema": 1}), encoding="utf-8")
    with pytest.raises(repo_map.MapError, match="schema"):
        repo_map.load_map(path)


def test_every_curated_edge_type_renders(repo):
    """25 of 73 curated edges never reached the page before the generic renderer."""
    add(repo, "docs/how.md", "# how\n")
    _curated(repo, lambda d: d["edges"].extend([
        {"from": "docs/how.md", "to": "pkg/app.py", "type": "documents"},
        {"from": "pkg/app.py", "to": "pkg/core.py", "type": "precedes"},
    ]))
    _curated(repo, lambda d: d["nodes"].update({"docs/how.md": {"role": "the manual"}}))
    text = repo_map.render_markdown(repo_map.build(repo))
    assert "documented in: `docs/how.md`" in text
    assert "precedes: `pkg/core.py`" in text
    assert "the manual" in text, "a document with a role renders"


# ------------------------------- what Git commits, and a half-done merge ----


def _git(repo, *args, check=True):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.invalid",
                           *args], cwd=repo, capture_output=True, check=check)


def _staged(repo, rel: str) -> bytes:
    """The blob Git staged for ``rel``: what a commit, and so CI, holds."""
    return _git(repo, "cat-file", "blob", f":{rel}").stdout


def test_a_crlf_working_copy_hashes_as_the_lf_file_git_commits(repo):
    """#90 went red on CI with a map current where it was built: four CRLF working copies."""
    (repo / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    (repo / "docs" / "crlf.md").write_bytes(b"# notes\r\n\r\nline\r\n")
    (repo / "docs" / "lf.md").write_bytes(b"# notes\n\nline\n")
    (repo / "docs" / "zero.txt").write_bytes(b"a\x00b\r\nc\r\n")
    (repo / "docs" / "late-zero.txt").write_bytes(b"x" * 9000 + b"\r\n\x00\r\n")
    (repo / "docs" / "lone-cr.txt").write_bytes(b"a\rb\r\nc\r\n")
    _git(repo, "add", "-A")

    assert repo_map.hash_file(repo / "docs" / "crlf.md") == repo_map.hash_file(repo / "docs" / "lf.md")
    for rel in ("docs/crlf.md", "docs/zero.txt", "docs/late-zero.txt", "docs/lone-cr.txt"):
        raw = (repo / rel).read_bytes()
        assert repo_map.git_text_auto_eol_lf(raw) == _staged(repo, rel), (
            f"{rel}: the map must hash the bytes Git commits")
    zero = (repo / "docs" / "zero.txt").read_bytes()
    assert repo_map.git_text_auto_eol_lf(zero) == zero, "a file with a NUL byte keeps its CR bytes"
    graph = repo_map.build(repo)
    assert node(graph, "docs/crlf.md")["sha256"] == node(graph, "docs/lf.md")["sha256"]


def test_check_names_a_crlf_working_copy_and_still_passes(repo, capsys):
    (repo / ".gitattributes").write_bytes(b"* text=auto eol=lf\n")
    core = repo / "pkg" / "core.py"
    lf = core.read_bytes().replace(b"\r\n", b"\n")   # write_text wrote CRLF on Windows
    core.write_bytes(lf)
    _git(repo, "add", "-A")
    repo_map.write_outputs(repo_map.build(repo))
    core.write_bytes(lf.replace(b"\n", b"\r\n"))
    assert _git(repo, "diff", "--exit-code", "--", "pkg/core.py", check=False).returncode == 0, (
        "Git sees no change: it commits the LF bytes")

    assert repo_map.main(["check"]) == 0
    out = capsys.readouterr().out
    assert "pkg/core.py: the working copy has CRLF; Git commits LF; the map hashes LF" in out
    assert "Map is current" in out


def test_update_refuses_while_a_file_is_unmerged(repo, capsys):
    """Handoff 007's rebases: an unmerged path is listed once per stage, so three nodes."""
    add(repo, "docs/notes.md", "# notes\n\nbase\n")
    _git(repo, "commit", "-q", "-m", "base")
    first = _git(repo, "rev-parse", "--abbrev-ref", "HEAD").stdout.decode().strip()
    _git(repo, "checkout", "-q", "-b", "other")
    add(repo, "docs/notes.md", "# notes\n\nother\n")
    _git(repo, "commit", "-q", "-am", "other")
    _git(repo, "checkout", "-q", first)
    add(repo, "docs/notes.md", "# notes\n\nours\n")
    _git(repo, "commit", "-q", "-am", "ours")
    assert _git(repo, "merge", "other", check=False).returncode != 0, "the merge must conflict"
    assert repo_map.unmerged_files(repo) == ["docs/notes.md"]

    for command in ("update", "build", "check"):
        assert repo_map.main([command]) == 1, command
        out = capsys.readouterr().out
        assert "unmerged docs/notes.md" in out and repo_map.UNMERGED_ADVICE in out, command
    assert not (repo / "docs" / "repo-map.json").exists(), "no node is written"
    with pytest.raises(repo_map.MapError, match="docs/notes.md"):
        repo_map.build(repo)

    _git(repo, "checkout", "--theirs", "docs/notes.md")
    _git(repo, "add", "docs/notes.md")
    assert repo_map.main(["update"]) == 0, "resolved and added, it maps again"
    graph = repo_map.load_map()
    assert [n["id"] for n in graph["nodes"]].count("docs/notes.md") == 1


def test_the_text_rule_matches_gitattributes():
    """``git_text_auto_eol_lf`` copies one line of .gitattributes; if it changes, so must the copy."""
    rules = [line.split() for line in (ROOT / ".gitattributes").read_text(encoding="utf-8").splitlines()
             if line.strip() and not line.lstrip().startswith("#")]
    assert ["*", "text=auto", "eol=lf"] in rules, (
        ".gitattributes no longer says `* text=auto eol=lf`. tools/repo_map.py's "
        "git_text_auto_eol_lf() copies that rule so the map hashes what Git commits; "
        "change it to follow the new rule, or the map goes stale on every CI checkout.")
    text_rules = [r for r in rules if any(a.split("=")[0] in ("text", "-text", "eol", "binary")
                                          for a in r[1:])]
    # The one other rule (decision 209, R7): batch files check out CRLF. It
    # changes only the working copy - ``text`` still commits LF - so the hash
    # rule is theirs too, and the CRLF warning passes them over by suffix.
    crlf = [["*" + suffix, "text", "eol=crlf"] for suffix in repo_map.CRLF_CHECKOUT_SUFFIXES]
    assert text_rules == [["*", "text=auto", "eol=lf"], *crlf], (
        f"another line sets text or eol: {text_rules}. The hash rule is one rule for every "
        "path; follow it in git_text_auto_eol_lf() before adding one.")


# ---------------------------------------- the real map's curated layer ----


def real_map():
    return repo_map.load_map(ROOT / "docs" / "repo-map.json")


def test_a_module_is_tested_by_its_own_test_file_if_and_only_if_that_file_exists():
    """The line "no dedicated test file" is a to-do; it must never be false."""
    graph = real_map()
    tracked = set(repo_map.tracked_files(ROOT))
    wrong = []
    for n in graph["nodes"]:
        if not n.get("sha256") or n["type"] not in ("module", "tool", "workflow", "script"):
            continue
        owner = repo_map.dedicated_test_for(n["id"])
        tested = edges(graph, to=n["id"], type="tests")
        if (owner in tracked) != bool(tested):
            wrong.append((n["id"], owner, [e["from"] for e in tested]))
    assert not wrong, wrong


def test_curated_prose_names_constants_rather_than_quoting_their_values():
    """A present-tense value in prose is a second copy that drifts (CACHE_VERSION did, twice).

    A note may record history ("decision 85: CACHE_VERSION 8, because ...");
    that stays true. "CACHE_VERSION is 9" and "(7 since decision 82)" do not.
    """
    graph = real_map()
    constants = {name for n in graph["nodes"] for name in n.get("constants", {})}
    hits = []
    for n in graph["nodes"]:
        prose = f"{n.get('role', '')} {n.get('notes', '')}"
        for name, value in re.findall(
                r"\b([A-Z][A-Z0-9_]{2,})\s+(?:is|=|stays|remains|is now|is still)\s+(\d+)\b", prose):
            if name in constants:
                hits.append((n["id"], name, value))
        if re.search(r"\(\d+ since decision", prose):
            hits.append((n["id"], "(N since decision", ""))
    assert not hits, hits


def _defined_names() -> set[str]:
    """Every def, class and assigned name in tracked Python; every function, const and property key in tracked JS."""
    names: set[str] = set()
    for rel in repo_map.tracked_files(ROOT):
        text = (ROOT / rel).read_text(encoding="utf-8")
        if rel.endswith(".py"):
            for item in ast.walk(ast.parse(text)):
                if isinstance(item, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)):
                    names.add(item.name)
                elif isinstance(item, ast.Name) and isinstance(item.ctx, ast.Store):
                    names.add(item.id)
                elif isinstance(item, ast.Attribute):
                    names.add(item.attr)
        elif rel.endswith(".js"):
            names.update(re.findall(r"\bfunction\s+(\w+)", text))
            names.update(re.findall(r"\b(?:const|let|var)\s+(\w+)", text))
            names.update(re.findall(r"\b(\w+)\s*[:(]", text))
    return names


#: Standard-library callables curated prose may name as `name()`.
STANDARD_LIBRARY_NAMES = {"asdict"}


def test_every_function_a_curated_note_names_exists_in_the_tree():
    """A note naming a deleted function (the runner's `_retire_stale_drafts()`) is a lie an agent will chase."""
    graph = real_map()
    defined = _defined_names() | STANDARD_LIBRARY_NAMES
    missing = set()
    for n in graph["nodes"]:
        prose = f"{n.get('role', '')} {n.get('notes', '')}"
        for name in re.findall(r"\b([A-Za-z_]\w*)\(\)", prose):
            if name not in defined:
                missing.add((n["id"], name))
    assert not missing, sorted(missing)


#: Which modules uphold each standing rule. A rule losing an enforcer, or a
#: module joining one, is a decision, and this is where it is recorded.
ENFORCERS = {
    "rule:no-AI-on-client-documents": {"tracker/content_check.py", "tracker/validators.py"},
    "rule:originals-are-never-altered": {"tracker/filer.py"},
    "rule:nothing-is-guessed": {"tracker/router.py", "tracker/filer.py", "tracker/review.py"},
    "rule:nothing-is-ever-sent": {"tracker/reminder.py", "tracker/runner.py",
                                  "tracker/scheduling.py"},
}


def test_the_set_of_modules_enforcing_each_standing_rule_is_pinned():
    graph = real_map()
    rules = {n["id"] for n in graph["nodes"] if n["type"] == "concept"}
    assert rules == set(ENFORCERS)
    for rule, expected in ENFORCERS.items():
        assert {e["from"] for e in edges(graph, to=rule, type="enforces")} == expected, rule


def test_every_artifact_has_a_writer_and_a_reader_or_says_it_is_write_only():
    """"Who reads this sidecar?" must never be answered with silence."""
    graph = real_map()
    for n in graph["nodes"]:
        if n["type"] != "artifact":
            continue
        assert edges(graph, to=n["id"], type="writes"), n["id"]
        assert edges(graph, to=n["id"], type="reads") or n.get("write_only"), n["id"]


def test_the_pipeline_ends_with_the_view_every_pass_writes():
    graph = real_map()
    assert any(stage.startswith("tracker.view") for stage in graph["pipeline"])
    assert edges(graph, **{"from": "tracker/reminder.py", "to": "tracker/view.py", "type": "precedes"})


def test_the_deliberate_cycle_is_stated_and_no_load_time_one_remains():
    graph = real_map()
    assert edges(graph, **{"from": "tracker/filer.py", "to": "tracker/scanner.py",
                           "type": "deliberate_cycle"})
    assert "no load-time cycle" in node(graph, "tracker/__init__.py")["notes"]
    assert edges(graph, **{"from": "tracker/filer.py", "to": "tracker/scanner.py",
                           "type": "imports_at_call"}), "the cycle closes at call time, not load"
    assert not edges(graph, **{"from": "tracker/filer.py", "to": "tracker/scanner.py",
                               "type": "imports"})
