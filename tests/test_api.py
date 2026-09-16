"""Tests for tracker/api.py — the JSON command layer the desktop app calls.

The contract under test: every command answers with one JSON object and an
exit code, an error is a JSON object too (never a traceback on stdout), and
the create path refuses a bad request list with a sentence a person can act
on. The demo root is redirected into a temp folder so no test touches the
real demo-marketing tree.
"""

import io
import json

import pytest

import tracker.api as api
from tracker.manifest import ManifestError, load_manifest
from tracker.scaffold import MANIFEST_FILENAME, PREPARED_DIR_NAME, SHARED_DIR_NAME


@pytest.fixture
def demo_root(tmp_path, monkeypatch):
    root = tmp_path / "demo"
    monkeypatch.setattr(api, "DEMO_ROOT", root)
    return root


def run(capsys, *argv, stdin=None):
    """Run one command the way main.js does: argv in, one JSON object out."""
    if stdin is not None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sys.stdin", io.StringIO(json.dumps(stdin)))
            code = api.main(list(argv))
    else:
        code = api.main(list(argv))
    out = capsys.readouterr().out.strip().splitlines()
    assert len(out) == 1, f"expected exactly one JSON line, got {out!r}"
    return code, json.loads(out[0])


# ------------------------------------------------------------- the contract ----


def test_unknown_command_is_a_json_error(capsys):
    code, payload = run(capsys, "frobnicate")
    assert code == 1
    assert payload["error"].startswith("usage:")


def test_a_manifest_problem_is_a_json_error_not_a_traceback(capsys, demo_root):
    demo_root.mkdir()
    code, payload = run(capsys, "state", "--engagement", str(demo_root / "nowhere"))
    assert code == 1
    assert "Manifest not found" in payload["error"]


def test_templates_lists_every_form_with_its_checklist(capsys):
    code, payload = run(capsys, "templates")
    assert code == 0
    assert {f["id"] for f in payload["forms"]} == set(payload["templates"])
    for form, rows in payload["templates"].items():
        identifiers = [r["identifier"] for r in rows]
        assert len(identifiers) == len(set(identifiers)), form
        assert any(r["core"] for r in rows), form


# ------------------------------------------------------------------ create ----


def test_create_builds_manifest_and_folders(capsys, demo_root):
    spec = {
        "name": "Smith Family 2025 Form 1040",
        "form": "1040",
        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]
        + [{"identifier": "X01", "document": "Rental Property Records",
            "extensions": "pdf, xlsx", "required_keywords": "Schedule E"}],
    }
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    engagement = demo_root / payload["created"]
    assert (engagement / MANIFEST_FILENAME).is_file()
    assert (engagement / SHARED_DIR_NAME).is_dir()
    assert any(p.name.startswith("X01") for p in (engagement / PREPARED_DIR_NAME).iterdir())
    assert [i["identifier"] for i in payload["state"]["items"]][-1] == "X01"


def test_create_refuses_an_identifier_that_cannot_name_a_folder(capsys, demo_root):
    spec = {"name": "Bad", "items": [{"identifier": "A:01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert "A:01" in payload["error"] and "folder name" in payload["error"]
    assert not (demo_root / "Bad").exists()  # never leaves a half-built one


def test_create_refuses_a_non_numeric_count_with_a_sentence(capsys, demo_root):
    spec = {"name": "Bad", "items": [
        {"identifier": "A01", "document": "W-2", "expected_count": "two"},
    ]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert payload["error"] == "Expected count for A01 must be a whole number, got 'two'"


def test_create_refuses_a_duplicate_identifier(capsys, demo_root):
    spec = {"name": "Dup", "items": [
        {"identifier": "A01", "document": "One"},
        {"identifier": "a01", "document": "Two"},
    ]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert "Duplicate identifier" in payload["error"]
    assert not (demo_root / "Dup").exists()


def test_create_will_not_overwrite_an_existing_engagement(capsys, demo_root):
    spec = {"name": "Twice", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert "already exists" in payload["error"]


# ------------------------------------------------------------ reset + scan ----


def test_reset_then_scan_plays_the_demo_end_to_end(capsys, demo_root):
    code, payload = run(capsys, "reset")
    assert code == 0 and payload["reset"] is True
    engagement = demo_root / api.ENGAGEMENT_DIRNAME
    samples = demo_root / api.SAMPLES_DIRNAME
    assert samples.is_dir()

    # The client drags every sample into the one folder.
    for sample in samples.iterdir():
        (engagement / SHARED_DIR_NAME / sample.name).write_bytes(sample.read_bytes())

    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    assert code == 0, payload
    assert payload["written"] is True
    assert payload["sorted"]["errors"] == []
    assert payload["sorted"]["index_deferred"] is False
    statuses = {ident: u["status"] for ident, u in payload["updates"].items()}
    assert statuses["A01"] == "Received"       # both 2025 W-2s, duplicate ignored
    assert statuses["A02"] == "Partial"        # 2 of 3
    assert statuses["C01"] == "Received"       # the 1098
    reviewed = {e["name"] for e in payload["unfiled"]}
    assert "W-2 Jane Smith 2024 - old.pdf" in reviewed   # wrong year, never guessed
    assert "vacation photo.jpg" in reviewed
    # What the scanner wrote is what the state command reads back.
    rows = {i.identifier: i for i in load_manifest(engagement / MANIFEST_FILENAME)}
    assert rows["A01"].status == "Received"


def test_item_from_spec_normalizes_extensions():
    item = api.item_from_spec(
        {"identifier": "A01", "document": "W-2", "extensions": ".PDF, Csv"}
    )
    assert item.allowed_extensions == ("pdf", "csv")
    with pytest.raises(ManifestError):
        api.item_from_spec({"identifier": "", "document": "W-2"})


# ------------------------------------------------------- returning clients ----


def test_priors_then_rollover_is_the_desktop_returning_client_path(capsys, demo_root):
    # The wizard's default page: list what is on disk, roll one forward.
    spec = {"name": "Smith Family 2025", "form": "1040",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0

    code, payload = run(capsys, "priors")
    assert code == 0
    assert [p["name"] for p in payload["priors"]] == ["Smith Family 2025"]
    assert payload["priors"][0]["year"] == 2025

    code, payload = run(capsys, "rollover", stdin={
        "prior": "Smith Family 2025", "form": "1040", "year": 2026,
    })
    assert code == 0, payload
    assert payload["created"] == "Smith Family 2025 - 2026"
    assert payload["rollover"]["prior_year"] == 2025
    assert payload["rollover"]["target_year"] == 2026
    carried = {r["identifier"] for r in payload["rollover"]["carried"]}
    offered = {r["identifier"] for r in payload["rollover"]["offered"]}
    assert "A01" in carried and "E01" in offered and not carried & offered
    periods = {i["identifier"]: i["period"] for i in payload["state"]["items"]}
    assert periods["A01"] == "TY2026"          # shifted with the year
    engagement = demo_root / payload["created"]
    assert (engagement / SHARED_DIR_NAME).is_dir()  # scaffolded, ready to share


def test_rollover_refuses_a_missing_prior(capsys, demo_root):
    code, payload = run(capsys, "rollover", stdin={"prior": "Nobody 2020"})
    assert code == 1
    assert "No manifest found" in payload["error"]


def test_a_name_of_only_illegal_characters_falls_back(capsys, demo_root):
    spec = {"name": "///:::", "form": "1040", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == "New Form 1040 Engagement"


def test_state_shows_statuses_a_locked_excel_deferred(capsys, demo_root):
    from tracker.manifest import StatusUpdate, _save_pending

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    _save_pending(demo_root / "Smith" / MANIFEST_FILENAME,
                  {"A01": StatusUpdate(status="Received", file_count=1)})
    code, payload = run(capsys, "state", "--engagement", str(demo_root / "Smith"))
    assert code == 0
    assert payload["pending_statuses"] == 1
    assert payload["items"][0]["status"] == "Received"
