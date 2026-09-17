"""Tests for tracker/api.py — the JSON command layer the desktop app calls.

The contract under test: every command answers with one JSON object and an
exit code, an error is a JSON object too (never a traceback on stdout), and
the create path refuses a bad request list with a sentence a person can act
on. The demo root is redirected into a temp folder so no test touches the
real demo-marketing tree.
"""

import datetime as dt
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
    assert payload["created"] == "New TY2025 Form 1040"


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


# ------------------------------------------------------------ needs review ----


def test_assign_files_a_parked_document_and_rescans(capsys, demo_root):
    assert run(capsys, "reset")[0] == 0
    engagement = demo_root / api.ENGAGEMENT_DIRNAME
    samples = demo_root / api.SAMPLES_DIRNAME
    for name in ("Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf"):
        (engagement / SHARED_DIR_NAME / name).write_bytes((samples / name).read_bytes())
    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    assert code == 0
    parked = [e for e in payload["state"]["index"] if e["decision"] == "Needs Review"]
    assert [e["original_name"] for e in parked] == ["Mortgage Notes.docx"]

    code, payload = run(capsys, "assign", "--engagement", str(engagement),
                        stdin={"original": parked[0]["pbc_location"], "identifier": "D01",
                               "keyword": "mortgage notes"})
    assert code == 0, payload
    assigned = payload["assigned"]
    assert assigned["identifier"] == "D01" and assigned["moved_review_copy"] is True
    assert assigned["keyword"] == "mortgage notes" and assigned["scan_note"] == ""
    assert not [e for e in payload["state"]["index"] if e["decision"] == "Needs Review"]
    d01 = next(i for i in payload["state"]["items"] if i["identifier"] == "D01")
    assert "mortgage notes" in d01["any_keywords"]
    # The re-scan saw it straight away. D01 accepts pdf/xlsx, so a .docx is
    # Failed Validation with the reason - the person's filing is recorded,
    # the rules still say what is wrong with it.
    assert d01["status"] == "Failed Validation"
    assert ".docx not allowed" in d01["validation_notes"]


def test_assign_refuses_a_bad_request_with_a_sentence(capsys, demo_root):
    assert run(capsys, "reset")[0] == 0
    engagement = demo_root / api.ENGAGEMENT_DIRNAME
    code, payload = run(capsys, "assign", "--engagement", str(engagement),
                        stdin={"original": "ghost.pdf", "identifier": "A01"})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]


# --------------------------------------------------------- engagement sheet ----


def test_create_writes_the_engagement_sheet_the_scheduled_run_reads(capsys, demo_root):
    from tracker.registry import discover_engagements

    spec = {"name": "Smith Family 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/abc", "due": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["client"] == "John Smith"
    assert payload["state"]["engagement"]["due"] == "2026-04-15"
    [found] = discover_engagements(demo_root).engagements
    assert found.client == "John Smith" and found.link == "https://drive.example/abc"
    assert found.firm == api.CONTACT and found.reminders is True


def test_rollover_carries_the_client_but_not_last_years_link_or_due(capsys, demo_root):
    spec = {"name": "Smith 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/old", "due": "2026-04-15", "sender": "Jason",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": "Smith 2025", "year": 2026})
    assert code == 0, payload
    info = payload["state"]["engagement"]
    assert info["client"] == "John Smith" and info["sender"] == "Jason"
    assert info["link"] == "" and info["due"] == ""
    assert info["name"] == "Smith 2025 - 2026"


def test_a_bad_due_date_is_a_sentence(capsys, demo_root):
    spec = {"name": "X", "due": "next friday", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert payload["error"] == "Due date must be YYYY-MM-DD, got 'next friday'"
    assert not (demo_root / "X").exists()


# ---------------------------------------------------- check, lock and names ----


def test_check_reports_problems_and_warnings_with_rows(capsys, demo_root):
    from openpyxl import load_workbook

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    manifest = demo_root / "Smith" / MANIFEST_FILENAME
    code, payload = run(capsys, "check", "--engagement", str(demo_root / "Smith"))
    assert code == 0 and payload["ok"] and payload["warnings"] == []

    wb = load_workbook(manifest)
    wb["Requests"].cell(row=2, column=4, value="two")
    wb.save(manifest)
    code, payload = run(capsys, "check", "--engagement", str(demo_root / "Smith"))
    assert code == 0 and payload["ok"] is False
    assert payload["problems"] == ["Row 2: Expected Count must be a whole number, got 'two'"]


def test_state_shows_the_lock_and_unlock_clears_only_a_stale_one(capsys, demo_root):
    import os
    from tracker.locking import LOCK_FILENAME

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    assert run(capsys, "state", "--engagement", str(engagement))[1]["lock"] is None

    lock = engagement / LOCK_FILENAME
    lock.write_text("pid=999 started=2026-03-14T07:03:00", encoding="utf-8")
    code, payload = run(capsys, "state", "--engagement", str(engagement))
    assert payload["lock"] == {"started": "2026-03-14T07:03:00", "age_minutes": 0, "stale": False}
    code, payload = run(capsys, "unlock", "--engagement", str(engagement))
    assert code == 1 and "may still be going" in payload["error"]

    old = (dt.datetime.now() - dt.timedelta(hours=2)).timestamp()
    os.utime(lock, (old, old))
    code, payload = run(capsys, "unlock", "--engagement", str(engagement))
    assert code == 0 and payload["cleared"] and payload["state"]["lock"] is None


def test_a_new_client_engagement_is_named_from_client_year_and_form(capsys, demo_root):
    spec = {"form": "1040", "client": "Smith Family",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == "Smith Family TY2025 Form 1040"
    code, payload = run(capsys, "templates")
    assert payload["years"]["1040"] == 2025


# ------------------------------------------------- the calendar and the prior ----


def test_create_shifts_the_checklist_to_the_engagements_year(capsys, demo_root):
    spec = {"form": "1040", "client": "Smith", "year": 2027,
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == "Smith TY2027 Form 1040"
    periods = {i["identifier"]: i["period"] for i in payload["state"]["items"]}
    assert periods["A01"] == "TY2027" and periods["B01"] == "TY2026"


def test_templates_carries_the_calendars_default_year(capsys):
    from tracker.templates import default_tax_year

    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()
    assert set(payload["years"].values()) == {default_tax_year()}


def test_rollover_retires_the_prior_in_the_priors_list(capsys, demo_root):
    spec = {"name": "Smith 2025", "form": "1040", "client": "John",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": "Smith 2025", "year": 2026})
    assert code == 0, payload
    assert payload["state"]["engagement"]["rolled_from"].endswith("Smith 2025")
    code, payload = run(capsys, "priors")
    by_name = {p["name"]: p for p in payload["priors"]}
    assert by_name["Smith 2025"]["superseded_by"] == "Smith 2025 - 2026"
    assert by_name["Smith 2025 - 2026"]["superseded_by"] == ""
