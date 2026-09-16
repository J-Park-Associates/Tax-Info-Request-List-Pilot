"""Tests for tools/repo_map.py — the map has to stay trustworthy.

A map that drifts from the code is worse than no map, because an agent will
believe it. So what is tested here is the trust contract: derived facts come
from the source, curated judgment survives regeneration, drift is detected,
and an update re-parses only what changed.
"""

import json
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


def test_a_test_file_gets_a_tests_edge_not_an_imports_edge(repo):
    graph = repo_map.build(repo)
    assert edges(graph, **{"from": "tests/test_core.py", "type": "tests"})
    assert not edges(graph, **{"from": "tests/test_core.py", "type": "imports"})


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
    data["edges"].append({"from": "pkg/app.py", "to": "pkg/ghost.py", "type": "imports"})
    curated.write_text(json.dumps(data), encoding="utf-8")

    with pytest.raises(repo_map.MapError, match="pkg/ghost.py"):
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


def test_the_generated_outputs_are_not_mapped(repo):
    """Mapping the map would leave it permanently stale against itself."""
    repo_map.write_outputs(repo_map.build(repo),
                           repo / "docs" / "repo-map.json",
                           repo / "docs" / "repo-map.md")
    subprocess.run(["git", "add", "-A"], cwd=repo, check=True)

    graph = repo_map.build(repo)
    ids = {n["id"] for n in graph["nodes"]}
    assert "docs/repo-map.json" not in ids
    assert "docs/repo-map.md" not in ids
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
    assert "Read this instead of re-scanning the repository" in text
    assert "repo_map.py update" in text
    assert "do not edit by hand" in text


def test_the_markdown_carries_the_curated_pipeline_and_roles(repo):
    text = repo_map.render_markdown(repo_map.build(repo))
    assert "core → app" in text
    assert "the core" in text


# ------------------------------------------------ the real map in this repo ----


def test_the_committed_map_is_current():
    """The map in docs/ must match this repository, or it is misinformation."""
    graph = repo_map.load_map(ROOT / "docs" / "repo-map.json")
    drift = repo_map.stale_files(graph, ROOT)
    assert drift == {"changed": [], "added": [], "removed": []}, (
        "docs/repo-map.json is stale — run `python tools/repo_map.py update`"
    )
