"""Tests for tracker/api.py — the JSON command layer the desktop app calls.

The contract under test: every command answers with one JSON object and an
exit code, an error is a JSON object too (never a traceback on stdout), and
the create path refuses a bad request list with a sentence a person can act
on. The clients root is a temp folder recorded through settings, the way
the app records it, so no test touches a real one.
"""

import datetime as dt
import io
import json
from pathlib import Path

import pytest

import tracker.api as api
from tracker.manifest import ManifestError, load_manifest
from tracker.scaffold import MANIFEST_FILENAME, PREPARED_DIR_NAME, SHARED_DIR_NAME
from tracker.templates import default_tax_year


@pytest.fixture
def demo_root(tmp_path, monkeypatch):
    """A clients root recorded the way the app records it: settings.json beside the app."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    from tracker.settings import set_firm

    root = tmp_path / "Clients"
    root.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(root)
    set_firm("J Park & Associates, CPA")
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


# ----------------------------------------------------------- create + scan ----


def sample_engagement(capsys, demo_root, tmp_path, *names):
    """A 1040 engagement created through the API with sample documents dropped in."""
    from tests.samples import build_samples

    spec = {"name": "Smith Family 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith Family 2025"
    samples = tmp_path / "samples"
    build_samples(samples)
    for sample in samples.iterdir():
        if not names or sample.name in names:
            (engagement / SHARED_DIR_NAME / sample.name).write_bytes(sample.read_bytes())
    return engagement


def test_create_then_scan_plays_a_whole_engagement_end_to_end(capsys, demo_root, tmp_path):
    # The client drags every sample into the one folder.
    engagement = sample_engagement(capsys, demo_root, tmp_path)

    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    assert code == 0, payload
    run_result = payload["run"]
    assert run_result["ok"] and not run_result["skipped"]
    assert run_result["file_errors"] == [] and run_result["index_deferred"] is False
    assert run_result["manifest_deferred"] is False
    statuses = {i["identifier"]: i["status"] for i in payload["state"]["items"]}
    assert statuses["A01"] == "Received"       # both 2025 W-2s, duplicate ignored
    assert statuses["A02"] == "Partial"        # 2 of 3
    assert statuses["C01"] == "Received"       # the 1098
    reviewed = {e["original_name"] for e in payload["state"]["index"] if e["decision"] == "Needs Review"}
    assert "W-2 Jane Smith 2024 - old.pdf" in reviewed   # wrong year, never guessed
    assert "vacation photo.jpg" in reviewed
    assert payload["state"]["summary"]["outstanding"] == run_result["outstanding"]
    assert "Received: 4" in payload["state"]["summary"]["line"]   # A01, B01, C01, D01
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


def test_assign_files_a_parked_document_and_rescans(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
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


def test_assign_refuses_a_bad_request_with_a_sentence(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
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
    from tracker.settings import firm
    assert found.firm == firm() and found.reminders is True
    assert found.name == ""          # the folder is the name; nothing to drift


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
    assert info["name"] == ""                      # the folder is the name
    assert payload["created"] == "Smith 2025 - 2026"


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
    from tracker.locking import STALE_LOCK_SECONDS
    assert payload["lock"] == {"started": "2026-03-14T07:03:00", "age_minutes": 0, "stale": False,
                               "stale_after_minutes": STALE_LOCK_SECONDS // 60}
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
    assert payload["created"] == f"Smith Family TY{default_tax_year()} Form 1040"
    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()


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
    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()
    assert "years" not in payload          # one number, not one per form


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


def test_the_apps_pass_is_the_runners_pass(capsys, demo_root):
    # A row added in Excel gets its folder from Sort & Scan, exactly as the
    # scheduled run would give it: one definition of a pass.
    from openpyxl import load_workbook

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    wb = load_workbook(engagement / MANIFEST_FILENAME)
    wb["Requests"].append(["Z01", "Rental Records", "TY2025", 1, "pdf", 5, None, "schedule e", None, None])
    wb.save(engagement / MANIFEST_FILENAME)
    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    assert code == 0, payload
    assert any(p.name.startswith("Z01") for p in (engagement / PREPARED_DIR_NAME).iterdir())
    assert payload["run"]["warnings"] == []

    # A lock held by another run is reported as skipped, not as an error.
    from tracker.locking import LOCK_FILENAME
    (engagement / LOCK_FILENAME).write_text("pid=999", encoding="utf-8")
    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    assert code == 0 and payload["run"]["skipped"].startswith("another run")
    (engagement / LOCK_FILENAME).unlink()

    # A manifest typo stops the pass with its row, and is a JSON error the app can show.
    wb = load_workbook(engagement / MANIFEST_FILENAME)
    wb["Requests"].cell(row=2, column=9, value="(unclosed")
    wb.save(engagement / MANIFEST_FILENAME)
    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    assert code == 1 and payload["error"].startswith("Row 2: Date Pattern")


# ------------------------------------------------------------------ the root ----


def test_without_a_root_the_app_is_told_to_set_one(capsys, tmp_path, monkeypatch):
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is True and payload["engagements"] == []
    code, payload = run(capsys, "create", stdin={"items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 1 and "where your clients live" in payload["error"]


def test_set_root_records_the_folder_the_job_will_walk(capsys, tmp_path, monkeypatch):
    from tracker.settings import ENV_SETTINGS_DIR, clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    clients = tmp_path / "Clients"
    clients.mkdir()
    code, payload = run(capsys, "set-root", stdin={"root": str(clients)})
    assert code == 0 and payload["root"] == str(clients)
    assert clients_root() == clients
    code, payload = run(capsys, "set-root", stdin={"root": str(tmp_path / "nope")})
    assert code == 1 and "not a folder" in payload["error"]
    code, payload = run(capsys, "settings")
    assert payload["root"] == str(clients) and payload["exists"] is True


def test_the_firm_is_typed_once_in_settings_and_signs_every_engagement(capsys, demo_root):
    from tracker.settings import firm, set_firm

    set_firm("Park & Daughters CPA")
    assert firm() == "Park & Daughters CPA"
    spec = {"name": "First", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0 and payload["state"]["engagement"]["firm"] == "Park & Daughters CPA"
    # set-root can set it too, once, at first launch.
    code, payload = run(capsys, "set-root", stdin={"root": str(demo_root), "firm": "New Name LLP"})
    assert code == 0 and payload["firm"] == "New Name LLP" == firm()
    assert run(capsys, "list")[1]["vocab"]["firm"] == "New Name LLP"


def test_install_schedule_uses_the_same_root_as_the_app(capsys, demo_root, monkeypatch):
    import tracker.api as api_module

    calls = []
    monkeypatch.setattr(api_module, "install_task", lambda xml, name="Tax Document Tracker": (calls.append(xml), ["schtasks", "/create", "/xml", str(xml)])[1])
    code, payload = run(capsys, "install-schedule", stdin={"start": "06:30", "every": 60})
    assert code == 0, payload
    assert payload["root"] == str(demo_root)
    xml = Path(payload["xml"]).read_text(encoding="utf-16")
    assert str(demo_root) in xml and "T06:30:00" in xml and "PT60M" in xml
    assert calls == [Path(payload["xml"])]


# ------------------------------------------------------------- vocabulary ----


def test_the_renderer_gets_its_vocabulary_from_the_api(capsys, demo_root):
    from tracker.filer import DUPLICATE, FILED, NEEDS_REVIEW
    from tracker.locking import STALE_LOCK_SECONDS
    from tracker.manifest import DEFAULT_EXTENSIONS, Override, Status
    from tracker.rollover import CARRIED_SHEET
    from tracker.runner import DRAFT_WEEKDAY, WEEKDAY_NAMES
    from tracker.scheduling import DEFAULT_REPEAT_MINUTES, DEFAULT_START

    code, payload = run(capsys, "list")
    vocab = payload["vocab"]
    assert [s["value"] for s in vocab["statuses"]] == list(Status.ALL)
    assert {s["key"] for s in vocab["statuses"]} == {
        "missing", "partial", "failed-validation", "received", "pending-sync"}
    assert vocab["overrides"] == {"accepted": Override.ACCEPTED, "waived": Override.WAIVED}
    assert vocab["decisions"] == {"filed": FILED, "needs_review": NEEDS_REVIEW, "duplicate": DUPLICATE}
    assert vocab["default_extensions"] == ", ".join(DEFAULT_EXTENSIONS)
    assert vocab["stale_lock_minutes"] == STALE_LOCK_SECONDS // 60
    assert vocab["carried_sheet"] == CARRIED_SHEET
    assert vocab["schedule"] == {"start": DEFAULT_START, "every": DEFAULT_REPEAT_MINUTES,
                                 "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
                                 "task_name": "Tax Document Tracker"}


def test_every_chip_class_the_vocabulary_implies_exists_in_the_stylesheet(capsys, demo_root):
    css = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "style.css").read_text(encoding="utf-8")
    vocab = run(capsys, "list")[1]["vocab"]
    for status in vocab["statuses"]:
        assert f".chip-{status['key']} " in css or f".chip-{status['key']}{{" in css.replace(" ", ""), status


def test_the_new_client_name_rule_lives_in_python_and_uses_the_form_label(capsys, demo_root):
    spec = {"form": "1120S", "client": "Acme", "year": 2026,
            "items": [{"identifier": "A01", "document": "Trial Balance", "any_keywords": "trial balance"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == "Acme TY2026 Form 1120-S"


def test_priors_carry_next_year_and_the_index_carries_candidates(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "W-2 Jane Smith 2024 - old.pdf")
    code, payload = run(capsys, "scan", "--engagement", str(engagement))
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == "Needs Review"]
    assert parked["candidates"] == "A01"
    assert parked["filed_as"] == "W-2 Jane Smith 2024 - old.pdf"
    code, payload = run(capsys, "priors")
    [prior] = payload["priors"]
    assert prior["year"] == 2025 and prior["next_year"] == 2026


def test_install_schedule_defaults_come_from_scheduling(capsys, demo_root, monkeypatch):
    import tracker.api as api_module
    from tracker.scheduling import DEFAULT_REPEAT_MINUTES, DEFAULT_START

    monkeypatch.setattr(api_module, "install_task", lambda xml, name="Tax Document Tracker": ["schtasks"])
    code, payload = run(capsys, "install-schedule", stdin={})
    assert code == 0, payload
    assert payload["start"] == DEFAULT_START and payload["every"] == DEFAULT_REPEAT_MINUTES
    assert payload["draft_day"] == "saturday"
