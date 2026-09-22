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
import os
from pathlib import Path

import pytest

import tracker.api as api
from tests.conftest import make_engagement
from tests.samples import PRIOR_YEAR
from tracker import ledger, store, view
from tracker.filer import FILED, NEEDS_REVIEW
from tracker.locking import STALE_LOCK_SECONDS, lock_line
from tracker.manifest import (
    COL_DATE_PATTERN,
    COL_EXPECTED_COUNT,
    COL_MANUAL_OVERRIDE,
    COL_OVERRIDE_REASON,
    ManifestError,
    Status,
    load_engagement_info,
    load_manifest,
)
from tracker.records import ENGAGEMENT_LABELS
from tracker.runner import DRAFT_WEEKDAY, LOG_FILENAME, STATUS_PAGE_FILENAME, WEEKDAY_NAMES
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME, SHARED_DIR_NAME
from tracker.scheduling import SCHEDULE_XML_ENCODING, TASK_NAME
from tracker.templates import BASE_YEAR, default_tax_year


@pytest.fixture
def demo_root(tmp_path, monkeypatch):
    """A clients root recorded the way the app records it: settings.json beside the app."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root, set_firm

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


def test_a_request_list_problem_is_a_json_error_not_a_traceback(capsys, demo_root):
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(demo_root / "nowhere"))
    assert code == 1
    assert "not an engagement" in payload["error"]


def test_the_engagement_flag_needs_a_folder_under_the_root(capsys, demo_root, tmp_path):
    hint = f"Pick an engagement first ({api.ENGAGEMENT_FLAG} <folder>)"
    assert run(capsys, "state")[1]["error"] == hint
    assert run(capsys, "state", api.ENGAGEMENT_FLAG)[1]["error"] == hint        # was an IndexError
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, "  ")[1]["error"] == hint
    elsewhere = tmp_path / "Elsewhere" / "Smith"
    elsewhere.mkdir(parents=True)
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(elsewhere))
    assert code == 1 and "not under the clients root" in payload["error"]


def test_an_unplugged_clients_root_is_not_a_licence_to_read_anywhere(capsys, demo_root, tmp_path):
    import shutil

    elsewhere = tmp_path / "Elsewhere" / "Smith"
    elsewhere.mkdir(parents=True)
    shutil.rmtree(demo_root)                          # the drive is gone
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(elsewhere))
    assert code == 1 and "not under the clients root" in payload["error"]


def test_a_rollover_takes_its_prior_only_from_under_the_root(capsys, demo_root, tmp_path):
    from tracker.templates import template_items

    elsewhere = make_engagement(tmp_path / "Elsewhere" / "Smith TY2025",
                                template_items("1040", year=2025), scaffold=False)
    code, payload = run(capsys, "rollover", stdin={"prior": str(elsewhere)})
    assert code == 1 and "not under the clients root" in payload["error"]


def test_templates_lists_every_form_with_its_checklist(capsys):
    code, payload = run(capsys, "templates")
    assert code == 0
    assert {f["id"] for f in payload["forms"]} == set(payload["templates"])
    for form, rows in payload["templates"].items():
        identifiers = [r["identifier"] for r in rows]
        assert len(identifiers) == len(set(identifiers)), form
        assert any(r["core"] for r in rows), form


# ------------------------------------------------------------------ create ----


def test_create_builds_the_record_and_folders(capsys, demo_root):
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
    assert ledger.path_for(engagement).is_file()
    assert list(engagement.glob("*.xlsx")) == []
    assert (engagement / SHARED_DIR_NAME).is_dir()
    assert any(p.name.startswith("X01") for p in (engagement / PREPARED_DIR_NAME).iterdir())
    assert [i["identifier"] for i in payload["state"]["items"]][-1] == "X01"
    assert [r["identifier"] for r in payload["state"]["rules"]][-1] == "X01"


def test_create_with_no_name_builds_one_that_stays_under_the_root(capsys, demo_root):
    # The tenth reading: a blank name fell back to the raw client field, and
    # a client called "..\\..\\escaped" wrote the engagement above the root,
    # where discovery never finds it and nobody is chased.
    spec = {"name": "", "client": "..\\..\\escaped", "form": "1040", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    created = demo_root / payload["created"]
    assert created.parent == demo_root and ledger.path_for(created).is_file()
    assert not (demo_root.parent.parent / "escaped TY2025 Form 1040").exists()
    for outside in ("../outside", "sub/child"):          # a separator either platform reads
        with pytest.raises(api.ManifestError, match="not a folder name"):
            api._new_engagement_dir(outside)


def test_the_tax_year_is_within_the_bounds_the_wizard_shows(capsys, demo_root):
    from tracker.manifest import YEAR_MAX, YEAR_MIN

    for year in (1000000000, YEAR_MIN - 1, YEAR_MAX + 1):
        code, payload = run(capsys, "create", stdin={"name": "Bad", "form": "1040", "year": year,
                                                     "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1 and f"between {YEAR_MIN} and {YEAR_MAX}" in payload["error"], year
        assert not (demo_root / "Bad").exists()
    code, payload = run(capsys, "create", stdin={"name": "Prior", "form": "1040",
                                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 0, payload
    code, payload = run(capsys, "rollover", stdin={"prior": payload["created"], "year": "abc"})
    assert code == 1 and "whole number" in payload["error"]


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
    assert payload["error"] == f"A01: {COL_EXPECTED_COUNT} must be a whole number, got 'two'"


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

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    run_result = payload["run"]
    assert run_result["ok"] and not run_result["skipped"]
    assert run_result["file_errors"] == []
    assert "manifest_deferred" not in run_result
    statuses = {i["identifier"]: i["status"] for i in payload["state"]["items"]}
    assert statuses["A01"] == Status.RECEIVED   # both current-year W-2s, duplicate ignored
    assert statuses["A02"] == Status.PARTIAL    # 2 of 3
    assert statuses["C01"] == Status.RECEIVED   # the 1098
    reviewed = {e["original_name"] for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW}
    assert f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf" in reviewed   # wrong year, never guessed
    assert "vacation photo.jpg" in reviewed
    assert payload["state"]["summary"]["outstanding"] == run_result["outstanding"]
    assert f"{Status.RECEIVED}: 4" in payload["state"]["summary"]["line"]   # A01, B01, C01, D01
    # What the scanner recorded is what the state command reads back.
    rows = {i.identifier: i for i in load_manifest(engagement)}
    assert rows["A01"].status == Status.RECEIVED


def test_the_apps_pass_appends_the_line_the_scheduled_run_appends(capsys, demo_root, tmp_path):
    """A pass made from the app used to leave no trace at all: the log is the
    command line's, and the button makes the same pass, so it writes the same
    line - appended, never replacing what earlier passes wrote."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.jpg")

    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0
    first = (demo_root / LOG_FILENAME).read_text(encoding="utf-8")
    assert engagement.name in first

    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0
    second = (demo_root / LOG_FILENAME).read_text(encoding="utf-8")
    assert second.startswith(first)
    assert second.count(engagement.name) == 2


def test_the_apps_pass_regenerates_the_practices_status_page(capsys, demo_root, tmp_path):
    """The page is about the practice, not about the engagement the button was
    pressed on: an engagement nobody scanned is on it too, read rather than run."""
    page = demo_root / STATUS_PAGE_FILENAME
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.jpg")
    assert run(capsys, "create", stdin={"name": "Jones Family 2025", "form": "1040",
                                        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert not page.exists()

    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0

    text = page.read_text(encoding="utf-8")
    assert engagement.name in text and "Jones Family 2025" in text
    assert "vacation photo.jpg" in text          # the review queue, across the practice


def test_state_carries_the_path_of_the_practices_status_page(capsys, demo_root):
    """The shell opens only paths the API has reported, so the page's path is
    one of them; the app's Open Status button is that path and nothing else."""
    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(demo_root / "Smith"))
    assert code == 0
    assert payload["paths"]["status"] == str(demo_root / STATUS_PAGE_FILENAME)


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
    assert payload["priors"][0]["year"] == BASE_YEAR

    code, payload = run(capsys, "rollover", stdin={
        "prior": "Smith Family 2025", "form": "1040", "year": 2026,
    })
    assert code == 0, payload
    assert payload["created"] == "Smith Family 2025 - 2026"
    assert payload["rollover"]["prior_year"] == BASE_YEAR
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
    assert "No record found" in payload["error"]


def test_a_name_of_only_illegal_characters_falls_back(capsys, demo_root):
    spec = {"name": "///:::", "form": "1040", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == api.default_engagement_name("", default_tax_year(), "1040")


def test_state_shows_the_status_the_record_holds(capsys, demo_root):
    """Nothing waits for anything (decision 103): a status is recorded,
    and what the app shows is what the record says."""
    from tests.conftest import seed_statuses
    from tracker.manifest import StatusUpdate

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    seed_statuses(demo_root / "Smith",
                  {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(demo_root / "Smith"))
    assert code == 0
    assert "pending_statuses" not in payload
    assert payload["items"][0]["status"] == Status.RECEIVED


# ------------------------------------------------------------ needs review ----


def test_assign_files_a_parked_document_and_rescans(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0
    parked = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    assert [e["original_name"] for e in parked] == ["Mortgage Notes.docx"]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked[0]["pbc_location"], "identifier": "D01",
                               "keyword": "mortgage notes", "seq": parked[0]["seq"]})
    assert code == 0, payload
    assigned = payload["assigned"]
    assert assigned["identifier"] == "D01" and assigned["moved_review_copy"] is True
    assert assigned["keyword"] == "mortgage notes" and assigned["scan_note"] == ""
    assert not [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    d01 = next(i for i in payload["state"]["items"] if i["identifier"] == "D01")
    assert "mortgage notes" in d01["any_keywords"]
    # The re-scan saw it straight away. D01 accepts pdf/xlsx and this is a
    # .docx, but a person looked at it and filed it: their decision stands,
    # the row is Received, and the note says the rules were not applied.
    from tracker.scanner import ACCEPTED_NOTE

    assert d01["status"] == Status.RECEIVED
    assert ACCEPTED_NOTE.format(n=1) in d01["validation_notes"]


def teach(folder, identifier: str, keyword: str) -> None:
    """A keyword recorded against a request, as a person's filing records it."""
    from tracker.filer import ensure
    from tracker.locking import engagement_lock

    with engagement_lock(folder):
        ensure(folder)
        store.record(store.connect(), folder, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: identifier, ledger.KEYWORD_KEY: keyword,
        }))


def test_unlearn_records_one_event_re_scans_and_the_state_no_longer_lists_the_keyword(
        capsys, demo_root):
    """Decision 113: one event, and the request read again in the same breath.

    The re-scan is what makes the difference visible now rather than on
    Saturday: the engagement has never been scanned when the unlearn
    arrives, and the state that comes back carries a status for every row,
    which only a pass writes.
    """
    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"},
                                       {"identifier": "C01", "document": "Form 1098"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = demo_root / "Smith"
    teach(folder, "A01", "lender")
    state = api._state(folder)
    assert state["learned"] == {"A01": ["lender"]}
    assert not any(item["status"] for item in state["items"])      # nothing has scanned it

    code, payload = run(capsys, "unlearn", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"identifier": "A01", "keyword": "lender"})

    assert code == 0, payload
    assert payload["unlearned"] == {"identifier": "A01", "keyword": "lender", "scan_note": ""}
    assert payload["state"]["learned"] == {}
    a01 = next(i for i in payload["state"]["items"] if i["identifier"] == "A01")
    assert "lender" not in a01["any_keywords"]
    assert a01["status"] == Status.MISSING                         # the re-scan, in the same call
    names = [e[ledger.EVENT_KEY] for e in ledger.read_events(folder)]
    assert names.count(ledger.KEYWORD_UNLEARNED) == 1


def test_unlearn_refuses_a_blank_or_unknown_pair_by_name(capsys, demo_root):
    """A refusal is the usual error sentence, and nothing is recorded."""
    from tracker.manifest import UNLEARN_REFUSED

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = demo_root / "Smith"
    teach(folder, "A01", "lender")
    head = ledger.head(folder)

    for sent in ({"identifier": "", "keyword": "lender"},
                 {"identifier": "A01", "keyword": "  "},
                 {}):
        code, payload = run(capsys, "unlearn", api.ENGAGEMENT_FLAG, str(folder), stdin=sent)
        assert code == 1 and "Pick the request and the keyword" in payload["error"]

    code, payload = run(capsys, "unlearn", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"identifier": "A01", "keyword": "escrow"})
    assert code == 1
    assert payload["error"] == UNLEARN_REFUSED.format(identifier="A01", keyword="escrow")
    assert ledger.head(folder) == head
    assert api._state(folder)["learned"] == {"A01": ["lender"]}


def test_the_renderer_types_no_unlearn_word(capsys, demo_root):
    """The button beside a taught keyword and the sentence after it are the
    API's words, like every other word the editor shows."""
    js = (Path(__file__).resolve().parents[1] / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8")

    between = api.UNLEARNED_NOTE.split("}")[1].split("{")[0].strip()      # "unlearned from"
    tail = api.UNLEARNED_NOTE.split("{identifier}")[1].strip()            # the rest of it

    assert api.UNLEARN_LABEL not in js
    assert between not in js and tail not in js
    assert "vocab.editor.unlearn_label" in js and "vocab.editor.unlearned_note" in js


def test_rule_two_is_rendered_in_the_record_and_names_no_file(capsys, demo_root, tmp_path):
    """Decision 102, the owner's wording of 2026-09-19: the rule used to
    name the index workbook, and there is no such file any more."""
    from tracker import api
    from tracker.records import THE_RECORD

    (rule,) = [r for r in api.standing_rules() if r["headline"].startswith("Originals")]

    assert rule["detail"].endswith(f"every move is recorded in {THE_RECORD}.")
    assert ".xlsx" not in rule["detail"]


def test_the_state_the_app_reads_carries_no_deferred_index(capsys, demo_root, tmp_path):
    """There is nothing left for Excel to hold the index rows out of, so
    there is no word for it - in the reply, in the pass's own report, or in
    the vocabulary the renderer derives from."""
    from tracker import api
    from tracker.runner import EngagementRun

    spec = {"name": "Smith 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    state = api._state(demo_root / "Smith 2025")

    assert "index_deferred" not in state
    assert "index" not in state["paths"] and "manifest" not in state["paths"]
    assert not hasattr(EngagementRun(engagement=None), "index_deferred")
    assert "index_deferred" not in json.dumps(api._vocab())


def test_dismiss_records_that_nothing_asks_for_a_parked_document(capsys, demo_root, tmp_path):
    # The app's other half of Needs Review: a file no request asks for stops
    # being a thing to do without anything being deleted, and the word for it
    # comes from the vocabulary the renderer reads, not from the renderer.
    from tracker.filer import DISMISSED_BY_PERSON, NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]

    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "note": "an IRS notice",
                               "seq": parked["seq"]})
    assert code == 0, payload
    dismissed = payload["dismissed"]
    assert dismissed["decision"] == NOT_REQUESTED
    assert dismissed["reason"].startswith(DISMISSED_BY_PERSON)
    assert "an IRS notice" in dismissed["reason"]
    # The row is rewritten in place and the working copy is still parked.
    assert not [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    [row] = [e for e in payload["state"]["index"] if e["decision"] == NOT_REQUESTED]
    assert (engagement / row["prepared_location"]).is_file()
    assert api._vocab()["decisions"]["dismissed"] == NOT_REQUESTED


def test_unfile_sends_a_filed_document_back_for_review_and_the_status_with_it(capsys, demo_root, tmp_path):
    # The correction people used to make by dragging in Explorer, which the
    # index never learned: the row and the request both follow the file.
    from tracker.filer import UNFILED_BY_PERSON

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    request = next(i for i in payload["state"]["items"] if i["identifier"] == filed["identifier"])
    assert request["status"] == Status.RECEIVED

    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "note": "wrong request",
                               "seq": filed["seq"]})
    assert code == 0, payload
    unfiled = payload["unfiled"]
    assert unfiled["decision"] == NEEDS_REVIEW
    assert unfiled["reason"].startswith(UNFILED_BY_PERSON) and "wrong request" in unfiled["reason"]
    assert unfiled["moved_working_copy"] is True
    assert unfiled["left_filed"] == "" and unfiled["scan_note"] == ""
    # The working copy is parked under the client's own name...
    parked = engagement / unfiled["prepared_location"]
    assert parked.is_file() and parked.name == filed["original_name"]
    assert not (engagement / filed["prepared_location"]).exists()
    # ...and the request it was answering is not Received any more.
    request = next(i for i in payload["state"]["items"] if i["identifier"] == filed["identifier"])
    assert request["status"] != Status.RECEIVED
    assert payload["state"]["summary"]["received"] == 0


def test_unfile_refuses_what_is_not_filed(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "ghost.pdf", "seq": 1})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]
    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement), stdin={})
    assert code == 1 and payload["error"]


def test_dismiss_refuses_a_file_the_index_does_not_know(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "ghost.pdf", "seq": 1})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement), stdin={})
    assert code == 1 and payload["error"]


# ------------------------------------------------- the review queue, triaged ----


def triage_engagement(capsys, demo_root, extra=()):
    """One engagement whose drop folder holds a document two requests want.

    Two rows, each with a plain required keyword, and one document that
    says A02's in its title and A01's far down the page: the router files
    neither (it matches more than one request) and the row is parked
    carrying both keywords, where they were said, through the filer's own
    writers. Nothing here types an evidence string.

    ``extra`` adds rows the document says nothing about, for the claim that
    needs a request off the shortlist to file to.
    """
    from tests.test_scanner import text_pdf

    spec = {"name": "Reed Property 2025", "client": "Ada Reed", "items": [
        {"identifier": "A01", "document": "Mortgage Interest Statement", "period": "TY2025",
         "required_keywords": "mortgage interest", "min_size_kb": 0, "date_pattern": "*"},
        {"identifier": "A02", "document": "Rental Property Statements", "period": "TY2025",
         "required_keywords": "rental income", "min_size_kb": 0, "date_pattern": "*"},
        *extra,
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Reed Property 2025"
    text_pdf(engagement / SHARED_DIR_NAME / "packet.pdf", "\n".join([
        "Rental income summary for the year 2025",
        "Lakeside Property Management",
        *[f"Unit {n:03d} rent collected and expenses paid during the year" for n in range(60)],
        "The mortgage interest paid on the property is shown below.",
    ]))
    return engagement


def test_the_state_triages_each_parked_file_best_first_with_the_reason_behind_each(
    capsys, demo_root,
):
    from tracker.review import IDENTITY_UNKNOWN

    engagement = triage_engagement(capsys, demo_root)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]

    [triaged] = state["review"]
    [parked] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW]
    assert triaged["pbc_location"] == parked["pbc_location"], "the queue joins to the index row"
    # Best first, and best is not the manifest's order: A02 said its
    # keyword in the title, A01 said its own far down the same page.
    assert [s["identifier"] for s in triaged["shortlist"]] == ["A02", "A01"]
    assert [s["rank"] for s in triaged["shortlist"]] == sorted(
        s["rank"] for s in triaged["shortlist"]
    )
    assert all(s["rank"][0] == IDENTITY_UNKNOWN for s in triaged["shortlist"])
    # The sentence behind each, whole, as review.py wrote it: the row's own
    # word and where the document said it.
    first, second = triaged["shortlist"]
    assert first["reason"].startswith("A02") and "'rental income' in the title" in first["reason"]
    assert second["reason"].startswith("A01") and "'mortgage interest'" in second["reason"]


def test_a_parked_file_the_evidence_says_nothing_about_is_offered_nothing(
    capsys, demo_root, tmp_path,
):
    # A photo: no request accepts a .jpg, so the record names no candidate
    # and the queue says so rather than nominating the nearest row.
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.jpg")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload

    [triaged] = payload["state"]["review"]
    assert triaged["original_name"] == "vacation photo.jpg"
    assert triaged["shortlist"] == [], "no evidence, no suggestion — the person reads it"


def test_dismissing_a_file_takes_it_out_of_the_review_queue(capsys, demo_root, tmp_path):
    from tracker.filer import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.jpg")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    [parked] = payload["state"]["index"]
    assert [t["pbc_location"] for t in payload["state"]["review"]] == [parked["pbc_location"]]

    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "note": "a holiday snap",
                               "seq": parked["seq"]})
    assert code == 0, payload

    # The row is still in the index, said out loud; it is not work any more.
    [row] = [e for e in payload["state"]["index"] if e["decision"] == NOT_REQUESTED]
    assert row["pbc_location"] == parked["pbc_location"]
    assert payload["state"]["review"] == [], "a row nobody asks for is not triaged"


def test_a_resend_after_a_dismissal_is_triaged_and_its_row_carries_the_set_aside_sentence(
    capsys, demo_root, tmp_path,
):
    """Decision 111: the client sent it again, so it is somebody's work again.

    The sentence is the filer's and it rides the row, so the card reads it
    out of ``state["index"]`` the way it reads every other reason: nothing
    in tracker/review.py or in the vocabulary knows this decision happened.
    """
    from tracker.filer import NOT_REQUESTED, RESENT_AFTER_SET_ASIDE

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.jpg")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [parked] = payload["state"]["index"]
    # The row's own sequence number, read back out of the state the card was
    # drawn from, the way the app sends it: a review command that does not
    # carry it is refused (decision 112), and on a base without it this is
    # None and ignored.
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "note": "a holiday snap",
                               "seq": parked.get("seq")})
    assert code == 0, payload
    [set_aside] = payload["state"]["index"]

    # The client sends the same photo again.
    original = engagement / set_aside["pbc_location"]
    (engagement / SHARED_DIR_NAME / original.name).write_bytes(original.read_bytes())
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload

    rows = payload["state"]["index"]
    assert [e["decision"] for e in rows] == [NOT_REQUESTED, NEEDS_REVIEW]
    again = rows[1]
    assert again["reason"].startswith(
        RESENT_AFTER_SET_ASIDE.format(earlier=set_aside["reason"])
    )
    # It is work again: the queue has it, joined to that row, with its own
    # copy under its own name.
    [triaged] = payload["state"]["review"]
    assert triaged["pbc_location"] == again["pbc_location"]
    assert triaged["original_name"] == again["original_name"]
    assert again["prepared_location"] != set_aside["prepared_location"]
    assert (engagement / again["prepared_location"]).is_file()
    assert (engagement / set_aside["prepared_location"]).is_file()


def test_assigning_a_shortlisted_request_files_it_and_the_queue_drops_it(capsys, demo_root):
    engagement = triage_engagement(capsys, demo_root)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    [triaged] = payload["state"]["review"]
    best = triaged["shortlist"][0]["identifier"]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": triaged["pbc_location"], "identifier": best,
                               "seq": triaged["seq"]})
    assert code == 0, payload

    assert payload["assigned"]["identifier"] == best
    assert payload["state"]["review"] == [], "filed is not parked"
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["identifier"] == best


def test_the_vocabulary_carries_every_word_the_review_card_shows(capsys, demo_root):
    from tracker.review import (
        IDENTIFIER_SEPARATOR,
        MAX_SUGGESTIONS,
        NOTHING_SUGGESTED,
        PLACE_WORDS,
        SET_ASIDE_NOTE,
    )

    vocab = run(capsys, "list")[1]["vocab"]

    # The card's own buttons and headings...
    labels = vocab["review_labels"]
    assert labels["file"] == api.FILE_LABEL and labels["dismiss"] == api.DISMISS_LABEL
    assert labels["file_anyway"] == api.FILE_ANYWAY_LABEL
    assert labels["suggested"] == api.SUGGESTED_HEADING
    assert labels["other_requests"] == api.OTHER_REQUESTS_HEADING
    # ...its second rendering's three answers and the toggle's two words
    # (decision 114), which head their suggestion with the word above.
    assert labels["accept"] == api.ACCEPT_LABEL and labels["skip"] == api.SKIP_LABEL
    assert labels["open_in_list"] == api.OPEN_IN_LIST_LABEL
    assert labels["card_mode"] == api.CARD_MODE_LABEL
    assert labels["list_mode"] == api.LIST_MODE_LABEL
    assert labels["card_position"] == api.CARD_POSITION
    # ...and every word tracker.review owns, from tracker.review.
    assert vocab["triage"] == {
        "nothing_suggested": NOTHING_SUGGESTED,
        "identifier_separator": IDENTIFIER_SEPARATOR,
        "places": dict(PLACE_WORDS),
        "max_suggestions": MAX_SUGGESTIONS,
        "set_aside_note": SET_ASIDE_NOTE,
    }
    # Nothing the card shows is typed in the renderer: every one of these
    # reaches the screen through vocab, never as a literal of its own.
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8"
    )
    for word in (*labels.values(), NOTHING_SUGGESTED, SET_ASIDE_NOTE, *PLACE_WORDS.values()):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word


def test_the_editor_saves_a_reason_and_the_vocabulary_carries_the_list_and_the_label(capsys, demo_root):
    """Decision 116: every word the editor and the table show about an
    override is the API's - the reasons, the word that opens the box, the
    label pattern, the set-aside sentence and the returning-client line -
    and the reason the editor saves travels in the one rules_changed event
    beside the override."""
    from tracker.manifest import (
        NOT_APPLICABLE_LABEL,
        OVERRIDE_REASON_OTHER,
        OVERRIDE_REASONS,
        Override,
    )
    from tracker.review import SET_ASIDE_NOTE
    from tracker.rollover import ORIGIN_NOT_APPLICABLE

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["override_reasons"] == list(OVERRIDE_REASONS)
    assert vocab["override_reason_other"] == OVERRIDE_REASON_OTHER
    assert vocab["not_applicable_label"] == NOT_APPLICABLE_LABEL
    assert vocab["triage"]["set_aside_note"] == SET_ASIDE_NOTE
    assert vocab["origin_not_applicable"] == ORIGIN_NOT_APPLICABLE
    assert vocab["not_applicable_carried"] == api.NOT_APPLICABLE_CARRIED
    assert [c["key"] for c in vocab["columns"]][-2:] == ["manual_override", "override_reason"]
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8"
    )
    for word in (*OVERRIDE_REASONS, OVERRIDE_REASON_OTHER, *Override.ALL, NOT_APPLICABLE_LABEL,
                 SET_ASIDE_NOTE, api.NOT_APPLICABLE_CARRIED, view.NOT_APPLICABLE_SECTION):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word
    for word in (*Override.ALL, OVERRIDE_REASON_OTHER, "Not Applicable in"):
        assert word not in renderer, word

    spec = {"name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098", "period": "TY2025"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]
    assert all(row["override_reason"] == "" for row in rows)

    # Accepted with no reason is refused, by row and column, and nothing is recorded.
    before = ledger.path_for(engagement).read_bytes()
    refused = [{**rows[0], "manual_override": Override.ACCEPTED}, rows[1]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": refused, "engagement": {}})
    assert code == 1 and payload["error"] == (
        f"Row 1: {COL_OVERRIDE_REASON} is required when {COL_MANUAL_OVERRIDE} is {Override.ACCEPTED}")
    assert ledger.path_for(engagement).read_bytes() == before

    # The word that opens the box is refused; the typed words are the reason.
    typed = [{**rows[0], "manual_override": Override.ACCEPTED, "override_reason": OVERRIDE_REASON_OTHER},
             rows[1]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": typed, "engagement": {}})
    assert code == 1 and "needs the reason typed" in payload["error"]
    edited = [{**rows[0], "manual_override": Override.ACCEPTED, "override_reason": "walked in on Tuesday"},
              {**rows[1], "manual_override": Override.NOT_APPLICABLE}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": edited, "engagement": {}})
    assert code == 0, payload
    assert payload["saved"]["changed"] == ["A01", "A02"]
    [event] = [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED][1:]
    by_id = {row["identifier"]: row for row in event[ledger.RULES_KEY]}
    assert by_id["A01"]["manual_override"] == Override.ACCEPTED
    assert by_id["A01"]["override_reason"] == "walked in on Tuesday"
    assert by_id["A02"]["manual_override"] == Override.NOT_APPLICABLE

    state = payload["state"]
    assert state["rules"][0]["override_reason"] == "walked in on Tuesday"
    assert state["summary"]["not_applicable"] == 1 and state["summary"]["total"] == 1
    # And the same list again records nothing.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": state["rules"], "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False


def test_state_ships_each_rows_year_for_the_label(capsys, demo_root):
    """The renderer labels a set-aside row with the year the API gives the
    row, from its own Period, and reads nothing out of the Period's text."""
    from tracker.manifest import Override

    spec = {"name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "period": "TY2025", "manual_override": Override.NOT_APPLICABLE},
        {"identifier": "A02", "document": "Prior return", "period": "TY2024", "date_pattern": "*"},
        {"identifier": "A03", "document": "Whenever", "period": "quarterly"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    state = payload_of_state(capsys, demo_root / "Smith")
    years = {item["identifier"]: item["year"] for item in state["items"]}
    assert years == {"A01": 2025, "A02": 2024, "A03": None}
    [set_aside] = [item for item in state["items"] if item["manual_override"] == Override.NOT_APPLICABLE]
    assert set_aside["identifier"] == "A01" and set_aside["override_reason"] == ""


def test_assign_refuses_a_bad_request_with_a_sentence(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, "nothing")
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "ghost.pdf", "identifier": "A01", "seq": 1})
    assert code == 1
    assert "nothing in the index is called 'ghost.pdf'" in payload["error"]


# ------------------------------------------------------- engagement details ----


def test_create_records_the_engagement_details_the_scheduled_run_reads(capsys, demo_root):
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


def test_create_records_the_catalog_the_wizard_chose_and_state_carries_it(capsys, demo_root):
    """Decision 86: the engagement says which checklist it was cut from, in
    the record and in the state the app draws from."""

    spec = {"name": "Willow Inc 2025", "form": "1120S", "client": "Willow Inc",
            "items": [t for t in api.FORM_TEMPLATES["1120S"] if t["core"]]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == "1120S"
    assert load_engagement_info(demo_root / "Willow Inc 2025").form == "1120S"


def test_an_engagement_created_without_a_form_says_nothing_rather_than_guessing(capsys, demo_root):
    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == ""


def test_rollover_carries_the_catalog_the_prior_was_cut_from(capsys, demo_root):
    spec = {"name": "Smith 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": "Smith 2025", "year": 2026})
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == "1040"


def test_rollover_carries_the_client_but_not_last_years_link_or_due(capsys, demo_root):
    spec = {"name": "Smith 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/old", "due": "2026-04-15", "sender": "Jason",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": "Smith 2025", "year": 2026})
    assert code == 0, payload
    info = payload["state"]["engagement"]
    assert info["client"] == "John Smith" and info["sender"] == "Jason"
    assert info["link"] == ""
    # Last year's due date does not carry either: what is there is this
    # year's own default (decision 117), never the date twelve months gone.
    assert info["due"] != "2026-04-15"
    assert info["name"] == ""                      # the folder is the name
    assert payload["created"] == api.ROLLOVER_NAME_PATTERN.format(prior="Smith 2025", year=2026)


def test_a_bad_due_date_is_a_sentence(capsys, demo_root):
    spec = {"name": "X", "due": "next friday", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    # The sentence names the field by the label the editor shows, so the
    # two dates are refused in the same words (decision 117).
    assert payload["error"] == f"{ENGAGEMENT_LABELS['due']} must be YYYY-MM-DD, got 'next friday'"
    assert not (demo_root / "X").exists()
    bad = {"name": "X", "form": "1040", "filing_deadline": "april",
           "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=bad)
    assert code == 1
    assert payload["error"] == f"{ENGAGEMENT_LABELS['filing_deadline']} must be YYYY-MM-DD, got 'april'"


def test_create_defaults_both_dates_from_the_form_and_the_year_and_leaves_them_editable(capsys, demo_root):
    """Decision 117: the reminder's ladder is measured against the Due
    Date, so a new engagement has one without anybody typing it - the
    form's own filing deadline, and the firm's ask-by target before it.
    Both are ordinary details afterwards, and a date the wizard was given
    is never written over."""
    from tracker.templates import ask_by_for, filing_deadline_for

    spec = {"name": "Willow 2025", "form": "1040", "year": 2025, "client": "Willow",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    deadline = filing_deadline_for("1040", 2025)
    info = payload["state"]["engagement"]
    assert info["filing_deadline"] == deadline.isoformat()
    assert info["due"] == ask_by_for(deadline).isoformat()
    assert load_engagement_info(demo_root / "Willow 2025").filing_deadline == deadline

    # What a person typed wins over the default, and both stay editable.
    typed = {**spec, "name": "Typed 2025", "due": "2026-03-01", "filing_deadline": "2026-04-18"}
    code, payload = run(capsys, "create", stdin=typed)
    assert code == 0, payload
    assert payload["state"]["engagement"]["due"] == "2026-03-01"
    assert payload["state"]["engagement"]["filing_deadline"] == "2026-04-18"

    # A form the catalog has no deadline for fills nothing, rather than guessing.
    none = {"name": "No Form 2025", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=none)
    assert code == 0, payload
    assert payload["state"]["engagement"]["filing_deadline"] == ""
    assert payload["state"]["engagement"]["due"] == ""


def test_the_editor_saves_and_clears_the_filing_deadline(capsys, demo_root):
    spec = {"name": "Smith", "form": "1040", "year": 2025,
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"filing_deadline": "2026-04-20"}})
    assert code == 0, payload
    assert payload["saved"]["engagement"] == ["filing_deadline"]
    assert payload["state"]["engagement"]["filing_deadline"] == "2026-04-20"

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"filing_deadline": ""}})
    assert code == 0, payload
    assert payload["state"]["engagement"]["filing_deadline"] == ""
    assert load_engagement_info(engagement).filing_deadline is None


def test_rollover_clears_the_filing_deadline_and_redefaults_it_for_the_new_year(capsys, demo_root):
    """A statutory date belongs to its year. Last year's does not carry,
    and the new year's comes from the same table the wizard used."""
    from tracker.templates import ask_by_for, filing_deadline_for

    spec = {"name": "Smith 2025", "form": "1040", "year": 2025, "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    prior = load_engagement_info(demo_root / "Smith 2025")
    assert prior.filing_deadline == filing_deadline_for("1040", 2025)

    code, payload = run(capsys, "rollover", stdin={"prior": "Smith 2025", "year": 2026})
    assert code == 0, payload
    deadline = filing_deadline_for("1040", 2026)
    info = payload["state"]["engagement"]
    assert info["filing_deadline"] == deadline.isoformat() != prior.filing_deadline.isoformat()
    assert info["due"] == ask_by_for(deadline).isoformat()


# ---------------------------------------------------- edit, lock and names ----


def test_an_invalid_row_is_refused_by_the_api_with_the_row_and_column_named_and_nothing_is_recorded(capsys, demo_root):
    from tests.test_manifest import k1_rows
    from tracker.records import rule_to_json

    spec = {"name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    before = ledger.path_for(engagement).read_bytes()
    rows = payload_of_state(capsys, engagement)["rules"]

    bad = [dict(rows[0]), {**rows[1], "expected_count": "two"}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": bad, "engagement": {}})
    assert code == 1
    assert payload["error"] == f"Row 2: {COL_EXPECTED_COUNT} must be a whole number, got 'two'"
    assert ledger.path_for(engagement).read_bytes() == before
    assert payload_of_state(capsys, engagement)["rules"] == rows

    nesting = [rule_to_json(i) for i in k1_rows(("F02", "Ashford"), ("F03", "Ashford Holdings"))]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": nesting, "engagement": {}})
    assert code == 1 and "F02" in payload["error"] and "F03" in payload["error"]
    assert ledger.path_for(engagement).read_bytes() == before

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"rolled_from": "last year"}})
    assert code == 1 and payload["error"] == "'rolled_from' is not edited here"
    assert ledger.path_for(engagement).read_bytes() == before
    assert payload_of_state(capsys, engagement)["rules"] == rows


def test_edit_saves_the_list_and_the_details_as_one_event_and_says_what_moved(capsys, demo_root):
    spec = {"name": "Smith", "client": "John", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]

    # The editor's rows: the file types as a string, a new row typed with
    # nothing but a name and a keyword, and one row gone.
    edited = [
        {**rows[0], "allowed_extensions": "pdf, jpg", "any_keywords": "wage statement"},
        {"identifier": "Z01", "document": "Rental Records", "period": "TY2025", "any_keywords": "schedule e"},
    ]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": edited, "engagement": {"client": "Jane", "reminders": False}})
    assert code == 0, payload
    assert payload["saved"] == {"changed": ["A01", "Z01"], "removed": ["A02"],
                                "engagement": ["client", "reminders"], "recorded": True}
    assert payload["warnings"] == []
    state = payload["state"]
    assert [r["identifier"] for r in state["rules"]] == ["A01", "Z01"]
    assert state["rules"][0]["allowed_extensions"] == ["pdf", "jpg"]
    assert state["rules"][1]["row"] == 2 and state["rules"][1]["date_pattern_derived"] is True
    assert state["engagement"]["client"] == "Jane" and state["engagement"]["reminders"] is False
    events = [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED]
    assert len(events) == 2 and events[-1][ledger.REMOVED_KEY] == ["A02"]

    # The same list again records nothing, and says so.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": state["rules"], "engagement": {"client": "Jane"}})
    assert code == 0 and payload["saved"]["recorded"] is False
    assert len(ledger.read_events(engagement)) == 2


def test_the_editor_clears_a_detail_it_sends_blank_and_keeps_one_it_leaves_out(capsys, demo_root):
    """A person who empties the Link box means the link to go: for ``edit``
    a key present with a blank value clears the recorded value, and a key
    absent keeps it. The wizard's fallback (a blank is nothing typed) is
    the create's and the rollover's, not the editor's."""
    spec = {"name": "Smith", "client": "John", "link": "https://y", "due": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"link": "", "due": ""}})
    assert code == 0, payload
    assert payload["saved"] == {"changed": [], "removed": [], "engagement": ["link", "due"], "recorded": True}
    details = payload["state"]["engagement"]
    assert details["link"] == "" and details["due"] == "" and details["client"] == "John"
    assert load_engagement_info(engagement).due is None

    # Absent keys keep what is recorded: nothing moved, nothing written.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False
    assert payload["state"]["engagement"]["client"] == "John"


def test_a_date_pattern_of_star_survives_an_unchanged_resave(capsys, demo_root):
    """A row whose Date Pattern the person set to ``*`` (no year check) is
    recorded with a blank pattern that is not derived; ``state`` hands it
    back that way, the editor shows and sends it as ``*`` again
    (``vocab.editor.no_date_check``), and a resave of the same list records
    nothing - sent blank instead, ``validated()`` would derive the year
    check and record the row as changed on every Save."""
    spec = {"name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "period": "TY2025", "required_keywords": "W-2",
         "date_pattern": "*"},
        {"identifier": "A02", "document": "1098", "period": "TY2025", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]
    assert rows[0]["date_pattern"] == "" and rows[0]["date_pattern_derived"] is False
    assert rows[1]["date_pattern_derived"] is True

    star = api.NO_DATE_CHECK
    as_the_editor_sends = [{**rows[0], "date_pattern": star}, {**rows[1], "date_pattern": ""}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": as_the_editor_sends, "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False, payload["saved"]
    assert payload["state"]["rules"][0]["date_pattern"] == ""
    js = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    assert "(rule.date_pattern || vocab.editor.no_date_check)" in js


def test_a_count_typed_as_infinity_is_refused_with_the_row_and_column_named(capsys, demo_root):
    for typed in ("inf", "Infinity", "1e400"):
        spec = {"name": f"Bad {typed}", "items": [
            {"identifier": "A01", "document": "W-2", "expected_count": typed}]}
        code, payload = run(capsys, "create", stdin=spec)
        assert code == 1 and f"{COL_EXPECTED_COUNT} must be a whole number, got" in payload["error"], payload


def test_a_name_whose_folder_was_deleted_by_hand_can_be_created_again(capsys, demo_root):
    """The store still holds the row of a folder someone deleted in
    Explorer; without forgetting it first, the new, shorter journal would
    read as truncated and the create would fail once with that sentence."""
    import shutil

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(demo_root / "Smith"))[0] == 0
    shutil.rmtree(demo_root / "Smith")
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert [r["identifier"] for r in payload["state"]["rules"]] == ["A01"]


def test_a_detail_with_a_line_break_inside_it_is_recorded_on_one_line(capsys, demo_root):
    """A sender pasted with a CRLF inside it would carry that break into
    the reminder draft's headers; every detail is one line, inner
    whitespace folded to a space."""
    spec = {"name": "Smith", "sender": "Jason Park\r\nBcc: x@evil.example", "client": " John\tSmith ",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    details = payload["state"]["engagement"]
    assert details["sender"] == "Jason Park Bcc: x@evil.example" and details["client"] == "John Smith"
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(demo_root / "Smith"),
                        stdin={"items": payload["state"]["rules"], "engagement": {"firm": "J Park\n& Associates"}})
    assert code == 0 and payload["state"]["engagement"]["firm"] == "J Park & Associates"


def test_a_failed_create_leaves_no_folder_and_no_store_row(capsys, demo_root, monkeypatch):
    spec = {"name": "Bad", "items": [
        {"identifier": "A01", "document": "W-2"},
        {"identifier": "A02", "document": "x", "date_pattern": "(unclosed"},
    ]}
    conn = store.connect()
    rows_before = conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"].startswith(f"Row 2: {COL_DATE_PATTERN}")
    assert not (demo_root / "Bad").exists()
    conn = store.connect()
    assert conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0] == rows_before
    assert store.rules(conn, demo_root / "Bad") is None

    # A store that cannot be reached at that moment neither replaces the
    # refusal sentence with its own nor leaves the half-built folder behind.
    def cannot(*a, **k):
        raise store.StoreError("the store is locked")

    monkeypatch.setattr(store, "forget", cannot)
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"].startswith(f"Row 2: {COL_DATE_PATTERN}")
    assert not (demo_root / "Bad").exists()


def test_the_editor_shows_the_persons_rows_and_never_a_taught_keyword_as_a_typed_one(capsys, demo_root, tmp_path):
    from tests.test_scanner import text_pdf

    spec = {"name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "any_keywords": "w-2"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    text_pdf(engagement / SHARED_DIR_NAME / "scan0012.pdf", "nothing the rules recognise")
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0
    [parked] = api._state(engagement)["index"]
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "scan0012.pdf", "identifier": "A01",
                               "keyword": "wage statement", "seq": parked["seq"]})
    assert code == 0, payload

    state = payload["state"]
    [rule] = state["rules"]
    assert rule["any_keywords"] == ["w-2"]                       # typed, as stored
    assert state["learned"] == {"A01": ["wage statement"]}      # taught, beside it
    [item] = state["items"]
    assert item["any_keywords"] == ["w-2", "wage statement"]     # both, for the pass


def test_state_carries_the_warnings_the_pass_reports(capsys, demo_root):
    from tracker.registry import engagement_from
    from tracker.runner import REMINDERS_NEVER, run_engagement

    spec = {"name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [*rows, {"identifier": "Z01", "document": "Anything", "allowed_extensions": "pdf"}],
        "engagement": {},
    })
    assert code == 0, payload
    [warning] = payload["warnings"]
    assert warning.startswith("Row 2 (Z01)") and "never be filed automatically" in warning
    assert payload["state"]["warnings"] == [warning]
    run_result = run_engagement(engagement_from(engagement), root=demo_root, reminders=REMINDERS_NEVER)
    assert run_result.warnings == [warning]


def test_state_shows_the_lock_and_unlock_clears_only_a_stale_one(capsys, demo_root):
    import os

    from tracker.locking import LOCK_FILENAME

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[1]["lock"] is None

    lock = engagement / LOCK_FILENAME
    lock.write_text(lock_line(os.getpid(), dt.datetime(2026, 3, 14, 7, 3)), encoding="utf-8")
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert payload["lock"] == {"started": "2026-03-14T07:03:00", "age_minutes": 0, "stale": False,
                               "stale_after_minutes": STALE_LOCK_SECONDS // 60}
    code, payload = run(capsys, "unlock", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 1 and "may still be going" in payload["error"]

    old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
    os.utime(lock, (old, old))
    code, payload = run(capsys, "unlock", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0 and payload["cleared"] and payload["state"]["lock"] is None


def test_a_new_client_engagement_is_named_from_client_year_and_form(capsys, demo_root):
    spec = {"form": "1040", "client": "Smith Family",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == api.default_engagement_name("Smith Family", default_tax_year(), "1040")
    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()


# ------------------------------------------------- the calendar and the prior ----


def test_create_shifts_the_checklist_to_the_engagements_year(capsys, demo_root):
    spec = {"form": "1040", "client": "Smith", "year": 2027,
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"] == api.default_engagement_name("Smith", 2027, "1040")
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
    assert by_name["Smith 2025"]["superseded_by"] == api.ROLLOVER_NAME_PATTERN.format(prior="Smith 2025", year=2026)
    assert by_name[api.ROLLOVER_NAME_PATTERN.format(prior="Smith 2025", year=2026)]["superseded_by"] == ""


def test_the_apps_pass_is_the_runners_pass(capsys, demo_root):
    # A row added in the editor gets its folder from the scan button,
    # exactly as the scheduled run would give it: one definition of a pass.
    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = demo_root / "Smith"
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [*rows, {"identifier": "Z01", "document": "Rental Records", "period": "TY2025",
                           "expected_count": 1, "allowed_extensions": "pdf", "min_size_kb": 5,
                           "any_keywords": "schedule e"}],
        "engagement": {},
    })
    assert code == 0, payload
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    assert any(p.name.startswith("Z01") for p in (engagement / PREPARED_DIR_NAME).iterdir())
    assert payload["run"]["warnings"] == []

    # A lock held by another run is reported as skipped, not as an error.
    from tracker.locking import LOCK_FILENAME
    (engagement / LOCK_FILENAME).write_text(lock_line(os.getpid(), dt.datetime(2026, 3, 14, 7, 3)), encoding="utf-8")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0 and payload["run"]["skipped"].startswith("another run")
    (engagement / LOCK_FILENAME).unlink()

    # A refused edit records nothing, and the pass runs on the last saved
    # list: a typo cannot reach the record (decision 104).
    before = [i["identifier"] for i in payload_of_state(capsys, engagement)["items"]]
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "date_pattern": "(unclosed"}, *rows[1:]], "engagement": {},
    })
    assert code == 1 and payload["error"].startswith(f"Row 1: {COL_DATE_PATTERN}")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0
    assert payload["run"]["ok"] is True
    assert [i["identifier"] for i in payload["state"]["items"]] == before


def payload_of_state(capsys, engagement):
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    return payload


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
    monkeypatch.setattr(api_module, "install_task", lambda xml, name=TASK_NAME: (calls.append(xml), ["schtasks", "/create", "/xml", str(xml)])[1])
    code, payload = run(capsys, "install-schedule", stdin={"start": "06:30", "every": 60})
    assert code == 0, payload
    assert payload["root"] == str(demo_root)
    xml = Path(payload["xml"]).read_text(encoding=SCHEDULE_XML_ENCODING)
    assert str(demo_root) in xml and "T06:30:00" in xml and "PT60M" in xml
    assert calls == [Path(payload["xml"])]


def test_the_packaged_app_installs_a_schedule_against_its_own_executable(capsys, demo_root, monkeypatch, tmp_path):
    import sys

    import tracker.api as api_module
    from tracker.runner import LOG_FLAG, RUNNER_MODE_FLAG

    exe = tmp_path / "package" / "resources" / "api" / "api.exe"
    exe.parent.mkdir(parents=True)
    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(exe))
    monkeypatch.setattr(api_module, "install_task", lambda xml, name=TASK_NAME: ["schtasks"])

    code, payload = run(capsys, "install-schedule", stdin={})
    assert code == 0, payload
    assert payload["frozen"] is True
    xml = Path(payload["xml"]).read_text(encoding=SCHEDULE_XML_ENCODING)
    assert f"<Command>{exe}</Command>" in xml
    assert f"<Arguments>{RUNNER_MODE_FLAG} " in xml and LOG_FLAG in xml and str(demo_root) in xml
    assert f"<WorkingDirectory>{exe.parent}</WorkingDirectory>" in xml
    assert "-m tracker.runner" not in xml


# ------------------------------------------------------------- vocabulary ----


def test_the_renderer_gets_its_vocabulary_from_the_api(capsys, demo_root):
    from tracker import STANDING_RULES
    from tracker.filer import DUPLICATE, FILE_MOVED, FILED, NEEDS_REVIEW, NOT_REQUESTED
    from tracker.manifest import COLUMN_HELP, COLUMNS, DEFAULT_EXTENSIONS, Override, Status
    from tracker.records import DATE_FIELDS, ENGAGEMENT_EDITABLE, ENGAGEMENT_FIELDS
    from tracker.runner import DRAFT_WEEKDAY, WEEKDAY_NAMES
    from tracker.scheduling import DEFAULT_REPEAT_MINUTES, DEFAULT_START

    code, payload = run(capsys, "list")
    vocab = payload["vocab"]
    assert [s["value"] for s in vocab["statuses"]] == list(Status.ALL)
    assert {s["key"] for s in vocab["statuses"]} == {api._slug(s) for s in Status.ALL}
    assert vocab["overrides"] == {"accepted": Override.ACCEPTED,
                                  "not_applicable": Override.NOT_APPLICABLE}
    assert vocab["decisions"] == {"filed": FILED, "needs_review": NEEDS_REVIEW,
                                  "duplicate": DUPLICATE, "dismissed": NOT_REQUESTED,
                                  "file_moved": FILE_MOVED}
    assert vocab["review_labels"] == {
        "dismiss": api.DISMISS_LABEL, "dismiss_note": api.DISMISS_NOTE_HINT,
        "dismissed_heading": api.DISMISSED_HEADING, "file": api.FILE_LABEL,
        "file_anyway": api.FILE_ANYWAY_LABEL,
        "unfile": api.UNFILE_LABEL, "unfile_note": api.UNFILE_NOTE_HINT,
        "filed_heading": api.FILED_HEADING,
        "suggested": api.SUGGESTED_HEADING, "other_requests": api.OTHER_REQUESTS_HEADING,
        "restore": api.RESTORE_LABEL, "keep": api.KEEP_LABEL,
        "send_to_review": api.SEND_TO_REVIEW_LABEL,
        "moved_heading": api.MOVED_HEADING, "moved_summary": api.MOVED_SUMMARY,
        "moved_nowhere": api.MOVED_NOWHERE,
        "accept": api.ACCEPT_LABEL, "skip": api.SKIP_LABEL,
        "open_in_list": api.OPEN_IN_LIST_LABEL,
        "card_mode": api.CARD_MODE_LABEL, "list_mode": api.LIST_MODE_LABEL,
        "card_position": api.CARD_POSITION,
    }
    assert vocab["default_extensions"] == ", ".join(DEFAULT_EXTENSIONS)
    assert "carried_sheet" not in vocab
    # The editor's every word, and the request list's schema.
    assert vocab["columns"] == [{"key": f, "label": h, "help": COLUMN_HELP[f]} for h, f in COLUMNS]
    editor = vocab["editor"]
    assert editor["open"] == api.EDITOR_OPEN_LABEL and editor["title"] == api.EDITOR_TITLE
    assert editor["engagement_title"] == api.EDITOR_ENGAGEMENT_TITLE
    assert editor["save"] == api.EDITOR_SAVE_LABEL and editor["cancel"] == api.EDITOR_CANCEL_LABEL
    assert editor["add_row"] == api.EDITOR_ADD_LABEL and editor["remove_row"] == api.EDITOR_REMOVE_LABEL
    assert editor["paste"] == api.EDITOR_PASTE_LABEL and editor["paste_hint"] == api.EDITOR_PASTE_HINT
    assert editor["warnings_heading"] == api.EDITOR_WARNINGS_HEADING
    assert editor["saved"] == api.RULES_SAVED and editor["nothing_changed"] == api.NOTHING_CHANGED
    assert editor["learned_note"] == api.LEARNED_NOTE
    assert editor["unlearn_label"] == api.UNLEARN_LABEL
    assert editor["unlearned_note"] == api.UNLEARNED_NOTE
    assert [f["key"] for f in editor["engagement_fields"]] == [f for _, f in ENGAGEMENT_FIELDS]
    assert {f["key"] for f in editor["engagement_fields"] if f["editable"]} == set(ENGAGEMENT_EDITABLE)
    # Which details take a date box is the record's answer, not the page's.
    assert editor["date_fields"] == list(DATE_FIELDS)
    assert editor["minimums"] == {"expected_count": 1, "min_size_kb": 0}
    assert editor["any_extension"] == "*" and editor["no_date_check"] == "*"
    assert editor["set_aside_heading"] == view.NOT_APPLICABLE_SECTION
    assert vocab["unscanned_key"] == api._slug(vocab["unscanned_label"])
    assert vocab["commands"] == sorted(api.COMMANDS)
    assert [r["headline"] for r in vocab["rules"]] == [h for h, _ in STANDING_RULES]
    assert vocab["schedule"] == {"start": DEFAULT_START, "every": DEFAULT_REPEAT_MINUTES,
                                 "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
                                 "task_name": TASK_NAME}
    # The settings page's phone box: its label, its sentence and the
    # number as recorded (decision 117).
    assert vocab["settings"] == {"phone_label": api.FIRM_PHONE_LABEL,
                                 "phone_help": api.FIRM_PHONE_HELP, "phone": ""}
    # And every word and colour the Reminder card shows (decision 118).
    _the_reminder_card_words_are_all_pythons(vocab["reminder"])


def _the_reminder_card_words_are_all_pythons(words):
    """The vocabulary pin for decision 118's card: every word from the
    module that owns the draft, the four rungs with the palette key each
    carries and where each spends its emphasis, and the palette those keys
    name. A hex reaches the app only through this map."""
    from dataclasses import asdict

    from tracker import reminder
    from tracker.page import PALETTE
    from tracker.runner import NOTHING_OUTSTANDING

    assert words == {
        "held_line": reminder.HELD_SUMMARY,
        "heading": reminder.REMINDER_HEADING,
        "stage_group": reminder.STAGE_GROUP_LABEL,
        "subject_prefix": reminder.SUBJECT_PREFIX,
        "copy": reminder.COPY_LABEL,
        "approve": reminder.APPROVE_LABEL,
        "open_draft": reminder.OPEN_DRAFT_LABEL,
        "last_drafted_line": reminder.LAST_DRAFTED_LINE,
        "never_drafted_line": reminder.NEVER_DRAFTED_LINE,
        "approved_line": reminder.APPROVED_LINE,
        "edited_by_hand": reminder.EDITED_BY_HAND,
        "stage_toggle_hint": reminder.STAGE_TOGGLE_HINT,
        "copied": reminder.COPIED_NOTE,
        "set_aside_line": reminder.SET_ASIDE_LINE,
        "nothing_to_send": NOTHING_OUTSTANDING,
        "stages": [{"number": stage.number, "name": stage.name,
                    "colour": reminder.STAGE_COLOURS[stage.number],
                    "emphasis": asdict(reminder.STAGE_EMPHASIS[stage.number])}
                   for stage in reminder.STAGES],
        "palette": dict(PALETTE),
        "hold_colour": reminder.HOLD_COLOUR,
        "letter_ink": dict(reminder.LETTER_INK),
    }
    # Nothing the card shows is typed in the renderer, and no colour of any
    # kind reaches it: every hex it draws with is looked up in this palette.
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8"
    )
    for word in (words["heading"], words["stage_group"], words["copy"], words["approve"],
                 words["open_draft"], words["edited_by_hand"], words["stage_toggle_hint"],
                 words["copied"], words["nothing_to_send"], words["subject_prefix"],
                 *(stage["name"] for stage in words["stages"])):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word


def test_the_settings_carry_the_firm_phone_and_the_vocabulary_names_its_box(capsys, demo_root):
    """Decision 117: the firm's telephone number is a firm-wide setting
    beside its name, said only by the final-notice reminder. The app shows
    a box for it and types neither its label nor its sentence."""
    from tracker.settings import firm_phone

    code, payload = run(capsys, "settings")
    assert code == 0 and payload["phone"] == ""

    code, payload = run(capsys, "set-root", stdin={"root": str(demo_root), "phone": "(555) 010-2020"})
    assert code == 0, payload
    assert payload["phone"] == "(555) 010-2020" and firm_phone() == "(555) 010-2020"
    assert payload["firm"] == "J Park & Associates, CPA", "a key not sent leaves what is recorded"
    assert run(capsys, "settings")[1]["phone"] == "(555) 010-2020"

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["settings"]["phone"] == "(555) 010-2020"
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8"
    )
    html = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "index.html").read_text(
        encoding="utf-8"
    )
    for word in (api.FIRM_PHONE_LABEL, api.FIRM_PHONE_HELP):
        assert word not in renderer and word not in html, word
    assert "vocab.settings.phone_label" in renderer and "vocab.settings.phone_help" in renderer


def test_the_reminder_payload_holds_on_a_parked_client_side_file(capsys, demo_root, tmp_path):
    """Decision 117: a parked file the client could fix holds the request
    the review card offers it for, and the card and the draft day agree -
    both read the shortlist, from the index rows ``state`` already has."""
    from tests.test_validators import write_pdf
    from tracker import reasons
    from tracker.reminder import PARKED_HOLD

    spec = {"name": "Smith", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = demo_root / "Smith"
    # The client sent their W-2 with a password on it: nothing in it can
    # be read, so no request accepts it and A01 stays Missing.
    write_pdf(folder / SHARED_DIR_NAME / f"W-2 Jane Smith {PRIOR_YEAR + 1}.pdf",
              pages=60, password="secret123")     # over the row's size floor
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(folder))[0] == 0

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(folder))
    assert code == 0, payload
    [parked] = [row for row in payload["index"] if row["decision"] == NEEDS_REVIEW]
    assert parked["candidates"] == [], "a name is no candidate"
    assert [s["identifier"] for s in payload["review"][0]["shortlist"]] == ["A01"]
    held = payload["reminder"]["held"]
    assert [row["identifier"] for row in held] == ["A01"]
    assert held[0]["reason"] == PARKED_HOLD.format(ask=reasons.PASSWORD_PROTECTED.client_ask)


def test_state_carries_the_held_rows_and_every_word_is_the_vocabularys(capsys, demo_root):
    """Decision 115: the app shows one line for a held reminder. The rows
    come from the reminder's own triage over the rows state already loaded,
    the sentence from the module that holds the draft, and the renderer
    types neither - it reads ``vocab.reminder`` and counts."""
    from tests.conftest import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.reminder import AMBIGUOUS_HOLD, HELD_SUMMARY

    spec = {"name": "Smith", "items": [{"identifier": "A01", "document": "W-2"},
                                       {"identifier": "C01", "document": "Form 1098"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = demo_root / "Smith"
    seed_statuses(folder, {
        "A01": StatusUpdate(status=Status.MISSING),
        "C01": StatusUpdate(status=Status.FAILED, file_count=1,
                            validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'")),
    })
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(folder))
    assert code == 0
    held = payload["reminder"]["held"]
    assert [row["identifier"] for row in held] == ["C01"]
    assert held[0]["label"].startswith("C01") and held[0]["reason"].startswith(AMBIGUOUS_HOLD)
    assert payload["reminder"]["last_drafted"] is None      # never drafted
    assert not (folder / "reminder-draft.txt").exists(), "state never drafts (decision 12)"

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["reminder"]["held_line"] == HELD_SUMMARY
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8"
    )
    for word in (HELD_SUMMARY, HELD_SUMMARY.split("{")[0].strip(), AMBIGUOUS_HOLD):
        assert word not in renderer, word
    assert "vocab.reminder.held_line" in renderer


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
    assert payload["created"] == api.default_engagement_name("Acme", 2026, "1120S")


def test_priors_carry_next_year_and_the_index_carries_candidates(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    assert parked["candidates"] == ["A01"]
    assert parked["filed_as"] == f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf"
    code, payload = run(capsys, "priors")
    [prior] = payload["priors"]
    assert prior["year"] == BASE_YEAR and prior["next_year"] == BASE_YEAR + 1


def test_the_state_carries_each_rows_evidence_as_data_not_as_a_string(capsys, demo_root, tmp_path):
    from tracker.content_check import EVIDENCE_PLACES, EVIDENCE_RULES, RULE_REQUIRED, WHERE_TITLE

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    # Parsed by the tracker, never split by the renderer: a record keyed by
    # candidate, each entry naming its rule, its term and where it was said.
    assert [(e["rule"], e["term"], e["where"]) for e in parked["evidence"]["A01"]][:1] == [
        (RULE_REQUIRED, "W-2", WHERE_TITLE),
    ]
    assert all(e["rule"] in EVIDENCE_RULES for e in parked["evidence"]["A01"])
    code, listed = run(capsys, "list")
    vocab = listed["vocab"]["evidence"]
    assert vocab["rules"] == list(EVIDENCE_RULES) and vocab["places"] == list(EVIDENCE_PLACES)
    assert RULE_REQUIRED in vocab["rules"] and WHERE_TITLE in vocab["places"]


def test_install_schedule_defaults_come_from_scheduling(capsys, demo_root, monkeypatch):
    import tracker.api as api_module
    from tracker.scheduling import DEFAULT_REPEAT_MINUTES, DEFAULT_START

    monkeypatch.setattr(api_module, "install_task", lambda xml, name=TASK_NAME: ["schtasks"])
    code, payload = run(capsys, "install-schedule", stdin={})
    assert code == 0, payload
    assert payload["start"] == DEFAULT_START and payload["every"] == DEFAULT_REPEAT_MINUTES
    assert payload["draft_day"] == WEEKDAY_NAMES[DRAFT_WEEKDAY]


# ----------- a person's action is judged against the record (d112) ----


def test_the_state_ships_each_rows_seq_on_the_index_and_on_the_review_list(
    capsys, demo_root, tmp_path,
):
    """The handle the card carries out. It rides beside the row and never in
    it: the index row itself is unchanged, and what is added is the record's
    own bookkeeping - the journal line that last wrote that row."""
    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]

    held = store.document_seqs(store.connect(), engagement)
    assert held, "the rows this pass wrote"
    assert {e["pbc_location"]: e["seq"] for e in state["index"]} == held
    assert {t["pbc_location"]: t["seq"] for t in state["review"]} == {
        e["pbc_location"]: held[e["pbc_location"]]
        for e in state["index"] if e["decision"] == NEEDS_REVIEW
    }


def test_a_review_command_with_no_seq_is_refused_and_a_stale_one_names_the_newer_decision(
    capsys, demo_root, tmp_path,
):
    """The app is drawn from ``state``, so it always has one; a spec without
    it is a caller with no view and is refused rather than acted on. And the
    card a person was called away from is refused with what the record now
    says, in the filer's own sentence."""
    from tracker.filer import NOT_REQUESTED, STALE_ROW

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": "D01"})
    assert code == 1 and payload["error"] == api.NO_SEQ

    # Somebody else sets the row aside while this card is open. It is still
    # parked, so the by-name refusal has nothing to say about it.
    code, after = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                      stdin={"original": parked["pbc_location"], "note": "an IRS notice",
                             "seq": parked["seq"]})
    assert code == 0, after
    [now] = [e for e in after["state"]["index"] if e["decision"] == NOT_REQUESTED]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": "D01",
                               "seq": parked["seq"]})
    assert code == 1
    assert payload["error"] == STALE_ROW.format(
        name=now["original_name"], decision=now["decision"], reason=now["reason"])


def test_assign_records_the_override_against_the_shortlist_the_api_computed(capsys, demo_root):
    """Decision 84 lets a person file to any row on the engagement; the
    record now says when they filed against the evidence, and the shortlist
    it says they overruled is the one this command computed from the row the
    filer then acted on."""
    from tracker.filer import OVERRODE_SHORTLIST

    engagement = triage_engagement(capsys, demo_root, extra=[
        {"identifier": "A03", "document": "Prior Year Return", "period": "TY2025",
         "required_keywords": "prior year return", "min_size_kb": 0, "date_pattern": "*"},
    ])
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [triaged] = payload["state"]["review"]
    suggested = [s["identifier"] for s in triaged["shortlist"]]
    assert suggested == ["A02", "A01"], "the document says nothing about A03"

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": triaged["pbc_location"], "identifier": "A03",
                               "seq": triaged["seq"]})
    assert code == 0, payload
    said = OVERRODE_SHORTLIST.format(listed=", ".join(suggested))
    assert payload["assigned"]["overrode_shortlist"] == said
    [row] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert said in row["reason"] and row["identifier"] == "A03"

    # The same document filed to the first of its suggestions instead:
    # nothing was overruled, so nothing is said.
    code, back = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                     stdin={"original": row["pbc_location"], "seq": row["seq"]})
    assert code == 0, back
    [again] = back["state"]["review"]
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": again["pbc_location"], "identifier": suggested[0],
                               "seq": again["seq"]})
    assert code == 0, payload
    assert payload["assigned"]["overrode_shortlist"] == ""

def test_the_state_carries_a_file_moved_row_in_the_index_and_in_no_list(capsys, demo_root, tmp_path):
    """Decision 109. A row whose working copy somebody dragged is in the
    index, where every column of it is readable, and in none of the lists
    the app draws: it is not waiting for review and it is not filed where
    the record says, and what to do about it is decision 110's card."""
    from tracker.filer import FILE_MOVED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    home = engagement / filed["prepared_location"]
    review_dir = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review_dir.mkdir(parents=True, exist_ok=True)
    home.rename(review_dir / home.name)                 # dragged by hand

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]
    [moved] = [e for e in state["index"] if e["decision"] == FILE_MOVED]
    assert moved["pbc_location"] == filed["pbc_location"]
    assert moved["prepared_location"] == filed["prepared_location"]   # home stays the column
    assert moved["pbc_location"] not in [t["pbc_location"] for t in state["review"]]
    assert not [e for e in state["index"]
                if e["decision"] == FILED and e["pbc_location"] == moved["pbc_location"]]
    assert api._vocab()["decisions"]["file_moved"] == FILE_MOVED
    # And the request it left is the firm's to sort out, not an ask.
    assert payload["run"]["warnings"]


# --------------- recovery is the person's: the moved card (d110) ----


def a_moved_row(capsys, demo_root, tmp_path, drag_to):
    """One filed document dragged by hand, and the state the pass leaves.

    ``drag_to`` is given the engagement and the copy's home and answers with
    where the hand put it. Comes back with the engagement, the row as it was
    filed (its own sequence number included) and the state that now holds it
    in ``moved``.
    """
    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    home = engagement / filed["prepared_location"]
    target = drag_to(engagement, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    home.rename(target)

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    return engagement, filed, target, payload["state"]


WANDERED = {
    # Inside the request's own folder, under a name a person gave it...
    "renamed in its own folder": (lambda eng, home: home.with_name("the 1098 (final).pdf"), True),
    # ...and in a folder somebody made inside it.
    "a subfolder of its own folder": (lambda eng, home: home.parent / "old" / home.name, True),
    # Nobody's folder: the review folder belongs to no request...
    "the review folder": (
        lambda eng, home: eng / PREPARED_DIR_NAME / REVIEW_DIR_NAME / home.name, False),
    # ...and a file loose at the root of Prepared/ is in no folder at all.
    "loose under Prepared": (lambda eng, home: eng / PREPARED_DIR_NAME / home.name, False),
}


@pytest.mark.parametrize("where", list(WANDERED))
def test_the_state_lists_moved_rows_with_home_now_seq_and_the_request_whose_folder_holds_them(
    capsys, demo_root, tmp_path, where,
):
    """Decision 110's card is its own list, not a fourth column: the row's
    record version, the home the record put the copy at, where its bytes are
    now, and - only where the copy sits inside some request's folder - which
    request that is, because "keep it where it is" means nothing anywhere
    else."""
    from tracker.filer import FILE_MOVED

    drag_to, in_a_request = WANDERED[where]
    engagement, filed, target, state = a_moved_row(capsys, demo_root, tmp_path, drag_to)

    [moved] = state["moved"]
    [row] = [e for e in state["index"] if e["decision"] == FILE_MOVED]
    assert moved["pbc_location"] == filed["pbc_location"]
    assert moved["original_name"] == filed["original_name"]
    assert moved["home"] == filed["prepared_location"]
    assert moved["now"] == target.relative_to(engagement).as_posix()
    assert moved["seq"] == row["seq"] and moved["seq"] != filed["seq"]
    assert moved["in_request"] == (filed["identifier"] if in_a_request else "")
    # And it is in none of the other lists: it is not waiting for review and
    # it is not filed where the record says.
    assert state["review"] == []
    assert not [e for e in state["index"] if e["decision"] == FILED]


def test_restore_is_a_command_that_re_scans_and_the_moved_list_empties(
    capsys, demo_root, tmp_path,
):
    """The put-back is one command, and the request has its file back before
    the answer is printed: the filer re-scans inside it, so the status the
    app shows next is the one the copy earns."""
    from tracker.manifest import Status

    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, WANDERED["the review folder"][0])
    [moved] = state["moved"]
    was_missing = {i["identifier"]: i["status"] for i in state["items"]}
    assert was_missing[filed["identifier"]] == Status.MISSING

    code, payload = run(capsys, "restore", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "seq": moved["seq"]})

    assert code == 0, payload
    restored = payload["restored"]
    assert restored["moved_home"] and not restored["copied_from_original"]
    assert not restored["already_home"] and restored["parked_as"] == ""
    assert restored["decision"] == FILED and restored["scan_note"] == ""
    assert restored["prepared_location"] == filed["prepared_location"]
    assert not target.exists() and (engagement / filed["prepared_location"]).is_file()
    assert payload["state"]["moved"] == []
    now = {i["identifier"]: i["status"] for i in payload["state"]["items"]}
    assert now[filed["identifier"]] == Status.RECEIVED
    assert "restore" in api._vocab()["commands"]


def test_restore_refuses_without_a_seq_and_with_a_stale_one(capsys, demo_root, tmp_path):
    """Decision 112's rule over decision 110's command: the app is drawn from
    state and every row there carries its version, so a spec without one is a
    caller acting on no view, and an older one is a caller acting on a view
    the record has moved past."""
    from tracker.filer import FILE_MOVED, STALE_ROW

    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, WANDERED["the review folder"][0])
    [moved] = state["moved"]

    code, payload = run(capsys, "restore", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"]})
    assert code == 1 and payload["error"] == api.NO_SEQ

    code, payload = run(capsys, "restore", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "seq": filed["seq"]})
    assert code == 1
    assert payload["error"] == STALE_ROW.format(
        name=moved["original_name"], decision=FILE_MOVED,
        reason=[e for e in state["index"] if e["decision"] == FILE_MOVED][0]["reason"])
    assert target.is_file()                       # and nothing was touched


def test_the_renderer_types_none_of_the_moved_cards_words(capsys, demo_root):
    """Every word of decision 110's card is the API's - the three answers,
    the heading, the line under it and the word for a copy that is nowhere -
    and the page shows them without holding one of its own."""
    vocab = run(capsys, "list")[1]["vocab"]
    labels = vocab["review_labels"]
    assert labels["restore"] == api.RESTORE_LABEL
    assert labels["keep"] == api.KEEP_LABEL
    assert labels["send_to_review"] == api.SEND_TO_REVIEW_LABEL
    assert labels["moved_heading"] == api.MOVED_HEADING
    assert labels["moved_summary"] == api.MOVED_SUMMARY
    assert labels["moved_nowhere"] == api.MOVED_NOWHERE

    renderer = Path(__file__).resolve().parent.parent / "app" / "renderer"
    for rel in ("app.js", "index.html"):
        text = (renderer / rel).read_text(encoding="utf-8")
        for word in (api.RESTORE_LABEL, api.KEEP_LABEL, api.SEND_TO_REVIEW_LABEL,
                     api.MOVED_HEADING, api.MOVED_SUMMARY, api.MOVED_NOWHERE):
            assert word not in text, (rel, word)


# ------------------------------------------------- the reminder card (d118) ----
# The app shows the week's draft, moves it up and down the ladder without
# touching the file, copies it and approves it. Nothing sends.


def chased_engagement(capsys, demo_root, name="Chase", client="John Smith"):
    """One engagement with two documents outstanding and a scan behind them."""
    from tests.conftest import seed_statuses
    from tracker.manifest import StatusUpdate

    spec = {"name": name, "client": client, "due": "2026-03-15", "filing_deadline": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2 Wage Statements"},
                      {"identifier": "B01", "document": "Bank Statements"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = demo_root / name
    seed_statuses(folder, {"A01": StatusUpdate(status=Status.MISSING),
                           "B01": StatusUpdate(status=Status.MISSING)})
    return folder


def reminder_card(capsys, folder, stage=None):
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": stage})
    assert code == 0, payload
    return payload["reminder"]


def test_the_reminder_command_reads_the_record_and_the_file_and_renders_on_demand(capsys, demo_root):
    """The card is the record's answer and the letter as it will read, at
    whatever rung the toggle stands on - and not one byte is written."""
    from tracker.reminder import DRAFT_FILENAME, STAGES, stage_named

    folder = chased_engagement(capsys, demo_root)
    card = reminder_card(capsys, folder)

    assert card["held"] == [] and card["editable"] is True
    assert card["last"] is None and card["approved"] is None
    assert card["asked"] == ["A01", "B01"]
    assert card["file"] == {"name": DRAFT_FILENAME, "exists": False, "edited": False,
                            "path": str(folder / DRAFT_FILENAME)}
    assert [s["number"] for s in card["stages"]] == [s.number for s in STAGES]
    assert card["stage"] == 4, "the Due Date has gone by, so the day gives the final notice"
    assert card["subject"] == stage_named(4).subject.format(engagement="Chase", n=2)
    assert card["letter"]["greeting"] and card["letter"]["sections"]
    assert card["html"].startswith("<div") and "<style" not in card["html"]
    assert not (folder / DRAFT_FILENAME).exists(), "reading the card never drafts"

    # The toggle: the same recipients, another stage's words, still no file.
    milder = reminder_card(capsys, folder, stage=1)
    assert milder["stage"] == 1 and milder["asked"] == card["asked"]
    assert milder["subject"] == stage_named(1).subject.format(engagement="Chase", n=2)
    assert milder["letter"]["deadline"] == [], "stage one carries no deadline paragraph"
    assert not (folder / DRAFT_FILENAME).exists()

    # A stage that is not one of the four is refused by name.
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={"stage": 9})
    assert code == 1 and "stage 9" in payload["error"]


def test_the_letter_travels_as_a_shape_with_the_emphasis_already_decided(capsys, demo_root):
    """The page is built from data, never from markup, so the preview is the
    letter's own shape - and which run of the deadline paragraph is marked
    is Python's answer, not the renderer's."""
    folder = chased_engagement(capsys, demo_root)
    letter = reminder_card(capsys, folder, stage=4)["letter"]
    runs = letter["deadline"]
    assert "".join(part["text"] for part in runs)
    assert [part["kind"] for part in runs if part["kind"]] == ["target", "deadline_date",
                                                              "consequences"]
    assert all(part["bold"] for part in runs if part["kind"])
    assert [part["colour"] for part in runs] == [False] * len(runs), "stage four colours the whole paragraph"

    two = reminder_card(capsys, folder, stage=2)["letter"]["deadline"]
    marked = [part for part in two if part["colour"]]
    assert [part["kind"] for part in marked] == ["target"], "stage two marks the date alone"
    assert not any(part["bold"] for part in two)


def test_a_held_reminder_shows_no_letter_and_offers_no_action(capsys, demo_root):
    """Decision 115's rule on this surface: a held client's composed text
    would ask for the clean rows alone, and the card is something a person
    can copy from. The hold, the rows, the toggle - and nothing else."""
    from tests.conftest import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.reminder import stage_for

    folder = chased_engagement(capsys, demo_root, name="Held")
    seed_statuses(folder, {"B01": StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"))})

    card = reminder_card(capsys, folder)
    assert [row["identifier"] for row in card["held"]] == ["B01"]
    assert card["held"][0]["document"] == "Bank Statements"
    assert (card["subject"], card["text"], card["html"], card["letter"]) == ("", "", "", {})
    assert card["editable"] is False
    assert card["stage"] == stage_for(load_engagement_info(folder).due, dt.date.today())
    # A stage asked for while held is ignored: there is nothing to re-stage.
    assert reminder_card(capsys, folder, stage=1)["stage"] == card["stage"]

    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": card["stage"], "fingerprint": card["fingerprint"]})
    assert code == 1 and "the reminder is held" in payload["error"]
    assert list(folder.glob("reminder-draft*")) == []


def test_approve_writes_the_shown_text_records_the_event_and_sets_the_other_draft_aside(
        capsys, demo_root):
    """What you see is what you approve: the file carries the text the card
    showed, one event carries the stage and the fingerprint, and the draft
    standing beside it is renamed and never deleted."""
    from tracker.reminder import (
        DRAFT_FILENAME,
        NEW_DRAFT_FILENAME,
        SET_ASIDE_DRAFT_PATTERN,
        recorded_fingerprint,
    )

    folder = chased_engagement(capsys, demo_root, name="Approve")
    (folder / NEW_DRAFT_FILENAME).write_bytes(b"an older draft\r\n")
    before = len(list(folder.iterdir()))
    card = reminder_card(capsys, folder, stage=3)

    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 3, "fingerprint": card["fingerprint"]})
    assert code == 0, payload
    written = folder / DRAFT_FILENAME
    assert card["text"] in written.read_text(encoding="utf-8")
    assert card["subject"] in written.read_text(encoding="utf-8")

    [event] = [e for e in ledger.read_events(folder)
               if e[ledger.EVENT_KEY] == ledger.DRAFT_APPROVED]
    assert event["stage"] == 3
    assert event[ledger.FILE_KEY] == DRAFT_FILENAME
    assert event[ledger.FINGERPRINT_KEY] == recorded_fingerprint(written)
    assert event[ledger.ASKED_KEY] == ["A01", "B01"]

    assert payload["set_aside"] == SET_ASIDE_DRAFT_PATTERN.format(date=dt.date.today().isoformat())
    assert (folder / payload["set_aside"]).read_bytes() == b"an older draft\r\n"
    assert not (folder / NEW_DRAFT_FILENAME).exists()
    assert len(list(folder.iterdir())) == before + 1, "one draft written, one renamed, none deleted"
    assert payload["reminder"]["approved"] == {"date": dt.date.today().isoformat(), "stage": 3,
                                               "file": DRAFT_FILENAME}


def test_approve_refuses_a_stale_fingerprint(capsys, demo_root):
    """A panel the record has moved under is refused before a file is
    touched, the way a review card is refused by its row's version."""
    from tracker.reminder import DRAFT_FILENAME

    folder = chased_engagement(capsys, demo_root, name="Stale")
    card = reminder_card(capsys, folder, stage=2)
    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 2, "fingerprint": card["fingerprint"] + "x"})
    assert code == 1 and payload["error"] == api.DRAFT_MOVED
    assert not (folder / DRAFT_FILENAME).exists()
    # The same click at another stage is a different text, and is refused too.
    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 4, "fingerprint": card["fingerprint"]})
    assert code == 1 and payload["error"] == api.DRAFT_MOVED
    assert not (folder / DRAFT_FILENAME).exists()


def test_an_edited_file_is_approved_as_it_stands_and_the_toggle_is_disabled(capsys, demo_root):
    """Their words, not the machine's: the card shows what they wrote, the
    ladder has nothing to say about it, and approve writes nothing."""
    from tracker.reminder import DRAFT_FILENAME, EDITED_BY_HAND

    folder = chased_engagement(capsys, demo_root, name="Edited")
    card = reminder_card(capsys, folder, stage=2)
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": 2, "fingerprint": card["fingerprint"]})[0] == 0
    written = folder / DRAFT_FILENAME
    edited = written.read_bytes() + b"\r\nPS: ask about the rental.\r\n"
    written.write_bytes(edited)

    after = reminder_card(capsys, folder)
    assert after["file"]["edited"] is True and after["editable"] is False
    assert after["letter"] == {} and "ask about the rental" in after["text"]
    assert after["html"].startswith("<div") and "ask about the rental" in after["html"]
    assert EDITED_BY_HAND  # the sentence the card shows beside it, from the vocabulary
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": after["stage"], "fingerprint": after["fingerprint"]})[0] == 0
    assert written.read_bytes() == edited, "an edited draft is approved as it stands"


def test_approve_never_sends(capsys, demo_root, monkeypatch):
    """The fourth standing rule, on the one command that writes a letter:
    no socket is opened, and the AST guard over the package still holds."""
    import socket

    from tracker.reminder import DRAFT_FILENAME

    folder = chased_engagement(capsys, demo_root, name="Quiet")
    card = reminder_card(capsys, folder, stage=1)

    def refuse(*args, **kwargs):
        raise AssertionError("the reminder path opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 1, "fingerprint": card["fingerprint"]})
    assert code == 0, payload
    assert (folder / DRAFT_FILENAME).exists()


def test_an_edited_drafts_footer_is_neither_shown_nor_copied(capsys, demo_root):
    """The staff footer is the machine's note to the person, as the header is.

    A draft written with a row that is ours rather than the client's, and
    with a file nobody has identified yet, ends with sentences naming both.
    They are fenced off by a rule of their own and have never been part of
    the email - so the card must not show them and Copy for Outlook must
    not put them one paste from a client.
    """
    from tests.conftest import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.reminder import (
        DRAFT_FILENAME,
        FOOTER_RULE,
        HELD_BACK_HEADING,
        REVIEW_ADVICE,
        REVIEW_WARNING,
    )

    folder = chased_engagement(capsys, demo_root, name="Footer")
    # B01 is ours to fix, not the client's to resend, so the draft reports
    # it under the footer instead of asking for it...
    seed_statuses(folder, {"B01": StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format())})
    # ...and a file nobody has identified yet puts the warning there too.
    review = folder / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review.mkdir(parents=True, exist_ok=True)
    (review / "scan0012.pdf").write_bytes(b"x" * 4096)

    card = reminder_card(capsys, folder)
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": card["stage"], "fingerprint": card["fingerprint"]})[0] == 0
    written = folder / DRAFT_FILENAME
    on_disk = written.read_text(encoding="utf-8")
    # The warning opens with its count, so the sentence after it is what a
    # test may look for without retyping a word of it.
    warning = REVIEW_WARNING.split("}", 1)[1]
    assert HELD_BACK_HEADING in on_disk and warning in on_disk

    # A person adds a line to the letter, which is above the footer's rule.
    edited = on_disk.replace(f"\n{FOOTER_RULE}",
                             f"PS: ask about the rental.\n\n{FOOTER_RULE}", 1)
    written.write_text(edited, encoding="utf-8", newline="\r\n")
    kept = written.read_bytes()

    after = reminder_card(capsys, folder)
    assert after["file"]["edited"] is True
    assert "PS: ask about the rental." in after["text"]
    assert "PS: ask about the rental." in after["html"]
    for firm_side in (HELD_BACK_HEADING, warning, REVIEW_ADVICE, FOOTER_RULE):
        assert firm_side not in after["text"], firm_side
        assert firm_side not in after["html"], firm_side
    assert written.read_bytes() == kept, "reading the card never touches the file"
