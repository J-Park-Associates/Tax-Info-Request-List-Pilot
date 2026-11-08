"""Tests for tracker/api.py: creating a return, scanning, and what a returning client carries over.

The commands that make a return (``create``, ``create`` then Sort & Scan), the returning client's prior year and the
calendar a year on, and decision 137's security review of the create path.

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
from pathlib import Path

import pytest

import tracker.api as api
import tracker.creation as creation
import tracker.screen_words as screen_words
from tests import api_driver
from tests.api_driver import (
    COUNTS,
    HOUSEHOLD,
    _raw,
    _tree_hashes,
    chased_engagement,
    one_reply,
    payload_of_state,
    reminder_card,
    run,
    said_by_class,
    sample_engagement,
    scan,
    where,
)
from tests.builders import make_engagement
from tests.node_harness import js_function
from tests.samples import PRIOR_YEAR
from tracker import ledger, store
from tracker.index import NEEDS_REVIEW
from tracker.layout import inbox_of
from tracker.locking import lock_line
from tracker.manifest import (
    COL_DATE_PATTERN,
    COL_EXPECTED_COUNT,
    ManifestError,
    Status,
    load_engagement_info,
    load_manifest,
)
from tracker.names import propose_spellings
from tracker.run_log import LOG_FILENAME
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.status_page import STATUS_PAGE_FILENAME
from tracker.templates import BASE_YEAR, default_tax_year

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ------------------------------------------------------------------ create ----


def test_create_builds_the_record_and_folders(capsys, demo_root):
    spec = {
        "return_name": "1040 - Smith Family",
        "form": "1040",
        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]
        + [{"identifier": "X01", "document": "Rental Property Records",
            "extensions": "pdf, xlsx", "required_keywords": "Schedule E"}],
    }
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    # The label the app shows names the household, the year and the return
    # (decision 125); where it landed is the layout's answer.
    assert payload["created"] == f"{HOUSEHOLD} {default_tax_year()} 1040 - Smith Family"
    engagement = where(demo_root, "1040 - Smith Family")
    assert Path(payload["state"]["paths"]["engagement"]) == engagement
    assert ledger.path_for(engagement).is_file()
    assert list(engagement.glob("*.xlsx")) == []
    assert inbox_of(engagement).is_dir()
    # No folder per request (decision 168): Prepared holds the review folder.
    assert [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir()] == [REVIEW_DIR_NAME]
    assert [i["identifier"] for i in payload["state"]["items"]][-1] == "X01"
    assert [r["identifier"] for r in payload["state"]["rules"]][-1] == "X01"


def test_a_name_outside_ascii_reaches_both_trees_as_it_was_typed(capsys, demo_root):
    # Decision 176: the app writes UTF-8 and Windows reads a pipe in its
    # ANSI code page, so "Muñoz" became "MuÃ±oz" in the folder the client
    # is shared, and "Á" (0x81 in UTF-8's second byte) was refused whole.
    for household, client in (("Muñoz", "José Muñoz"), ("Álvarez", "Ana Álvarez")):
        spec = {"household": household, "client": client, "form": "1040",
                "return_name": f"1040 - {client}",
                "people": [{"kind": "taxpayer", "name": client,
                            "spellings": propose_spellings(client, "taxpayer")}],
                "items": [{"identifier": "A01", "document": "W-2"}]}
        code, payload = run(capsys, "create", stdin=spec)
        assert code == 0, payload
        engagement = where(demo_root, f"1040 - {client}", household=household)
        assert ledger.path_for(engagement).is_file()
        assert inbox_of(engagement).parent.name == household
        assert load_engagement_info(engagement).client == client


def test_a_payload_that_is_not_one_object_is_refused_before_anything_is_read(capsys, demo_root):
    for spec in ([], "1040", 7):
        code, payload = run(capsys, "rollover", stdin=spec)
        assert code == 1
        assert payload["error"] == screen_words.NOT_A_SPEC


def test_create_with_no_name_builds_one_that_stays_under_the_root(capsys, demo_root):
    # The tenth reading: a blank name fell back to the raw client field, and
    # a client called "..\\..\\escaped" wrote the engagement above the root,
    # where discovery never finds it and nobody is chased.
    spec = {"household": HOUSEHOLD, "client": "..\\..\\escaped", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    created = Path(payload["state"]["paths"]["engagement"])
    assert ledger.path_for(created).is_file()
    # The return sits under its household and its year, and the client
    # field that would have been a path is one folder name.
    assert created.parent.parent.parent == demo_root / "J Park & Associates"
    assert created.name == api.default_return_name("1040", spec["client"])
    assert not (demo_root.parent.parent / "escaped TY2025 Form 1040").exists()
    # And a household or a return that is not one folder name is refused
    # by name, whichever separator a platform reads.
    for outside in ("../outside", "sub/child"):
        with pytest.raises(api.ManifestError, match="is not a return name"):
            creation._new_return_dir(demo_root, HOUSEHOLD, 2025, outside)
        with pytest.raises(api.ManifestError, match="is not a household name"):
            creation._new_return_dir(demo_root, outside, 2025, "1040 - Smith")


def test_the_tax_year_is_within_the_bounds_the_wizard_shows(capsys, demo_root):
    from tracker.manifest import YEAR_MAX, YEAR_MIN

    for year in (1000000000, YEAR_MIN - 1, YEAR_MAX + 1):
        code, payload = run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Bad", "form": "1040", "year": year,
                                                     "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1 and f"between {YEAR_MIN} and {YEAR_MAX}" in payload["error"], year
        assert not (where(demo_root, "Bad")).exists()
    code, payload = run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Prior", "form": "1040",
                                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 0, payload
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Prior")), "year": "abc"})
    assert code == 1 and "whole number" in payload["error"]


def test_create_refuses_an_identifier_that_cannot_begin_a_file_name(capsys, demo_root):
    """Since decision 168 an identifier begins every working copy's file
    name, and names no folder: the refusal says so (the review's N-1)."""
    spec = {"household": HOUSEHOLD, "return_name": "Bad", "items": [{"identifier": "A:01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert "A:01" in payload["error"] and "(it begins a file name)" in payload["error"]
    assert "folder name" not in payload["error"]
    assert not (where(demo_root, "Bad")).exists()  # never leaves a half-built one


def test_create_refuses_a_non_numeric_count_with_a_sentence(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Bad", "items": [
        {"identifier": "A01", "document": "W-2", "expected_count": "two"},
    ]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert payload["error"] == f"A01: {COL_EXPECTED_COUNT} {COUNTS}"


def test_create_refuses_a_duplicate_identifier(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Dup", "items": [
        {"identifier": "A01", "document": "One"},
        {"identifier": "a01", "document": "Two"},
    ]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert "Duplicate identifier" in payload["error"]
    assert not (where(demo_root, "Dup")).exists()


def test_create_will_not_overwrite_an_existing_engagement(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Twice", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    assert "already exists" in payload["error"]


# ----------------------------------------------------------- create + scan ----


def test_create_then_scan_plays_a_whole_engagement_end_to_end(capsys, demo_root, tmp_path):
    # The client drags every sample into the one folder.
    engagement = sample_engagement(capsys, demo_root, tmp_path)

    code, payload = scan(capsys, engagement)
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
    assert "vacation photo.bmp" in reviewed
    assert payload["state"]["summary"]["outstanding"] == run_result["outstanding"]
    assert f"{Status.RECEIVED}: 4" in payload["state"]["summary"]["line"]   # A01, B01, C01, D01
    # What the scanner recorded is what the state command reads back.
    rows = {i.identifier: i for i in load_manifest(engagement)}
    assert rows["A01"].status == Status.RECEIVED


def test_the_apps_pass_appends_the_line_the_scheduled_run_appends(capsys, demo_root, tmp_path):
    """A pass made from the app used to leave no trace at all: the log is the
    command line's, and the button makes the same pass, so it writes the same
    line - appended, never replacing what earlier passes wrote. Since
    decision 186 it is the data home's run log, and it names no client."""
    from tracker.run_log import log_path

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")

    assert scan(capsys, engagement)[0] == 0
    first = log_path().read_text(encoding="utf-8")
    assert engagement.name not in first and "    counts returns=" in first
    assert not (demo_root / LOG_FILENAME).exists()

    assert scan(capsys, engagement)[0] == 0
    second = log_path().read_text(encoding="utf-8")
    assert second.startswith(first)
    assert engagement.name not in second
    # Each pass is the runner's (decision 203): its ``pass started`` line,
    # then its summary line.
    stamped = [line for line in second.splitlines() if line.startswith("[")]
    assert len(stamped) == 4 and sum(line.endswith("] pass started") for line in stamped) == 2


def test_the_apps_pass_regenerates_the_practices_status_page(capsys, demo_root, tmp_path):
    """The page is about the practice, not about the engagement the button was
    pressed on: an engagement nobody scanned is on it too, read rather than run."""
    page = demo_root / STATUS_PAGE_FILENAME
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    assert run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Jones Family 2025", "form": "1040",
                                        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert not page.exists()

    assert scan(capsys, engagement)[0] == 0

    text = page.read_text(encoding="utf-8")
    assert engagement.name in text and "Jones Family 2025" in text
    assert "vacation photo.bmp" in text          # the review queue, across the practice


def test_state_carries_the_path_of_the_practices_status_page(capsys, demo_root):
    """The shell opens only paths the API has reported, so the page's path is
    one of them; the app's Open Status button is that path and nothing else."""
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith")))
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
    spec = {"household": HOUSEHOLD, "return_name": "Smith Family 2025", "form": "1040",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0

    code, payload = run(capsys, "priors")
    assert code == 0
    assert [p["name"] for p in payload["priors"]] == ["Smith Family 2025"]
    assert payload["priors"][0]["year"] == BASE_YEAR

    code, payload = run(capsys, "rollover", stdin={
        "prior": str(where(demo_root, "Smith Family 2025")), "form": "1040", "year": 2026,
    })
    assert code == 0, payload
    # A return keeps its name every year under the same household, so
    # what is new about the roll is the year (decision 125).
    assert payload["created"] == f"{HOUSEHOLD} 2026 Smith Family 2025"
    assert payload["rollover"]["prior_year"] == BASE_YEAR
    assert payload["rollover"]["target_year"] == 2026
    carried = {r["identifier"] for r in payload["rollover"]["carried"]}
    # Decision 142: the catalog rows the client never had are added as not
    # asked, not offered.
    added = {r["identifier"] for r in payload["rollover"]["carried"] if not r["asked"]}
    assert "A01" in carried and "E01" in added and "A01" not in added
    assert "offered" not in payload["rollover"]
    periods = {i["identifier"]: i["period"] for i in payload["state"]["items"]}
    assert periods["A01"] == "TY2026"          # shifted with the year
    engagement = where(demo_root, "Smith Family 2025", year=2026)
    assert Path(payload["state"]["paths"]["engagement"]) == engagement
    assert inbox_of(engagement).is_dir()  # scaffolded, ready to share


def test_rollover_refuses_a_missing_prior(capsys, demo_root):
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Nobody 2020"))})
    assert code == 1
    assert "No record found" in payload["error"]


def test_rollover_refuses_a_legacy_return_with_the_legacy_sentence_and_writes_nothing(
        capsys, demo_root):
    """Section 18 (S1): the app's Roll Forward on a return whose record reads
    and holds no request list, with the old workbook beside it, is refused
    with the rollover's legacy sentence - it used to roll into the next year
    with zero rows and say nothing - and nothing is written, in either tree."""
    from tracker.manifest import EngagementInfo
    from tracker.registry import LEGACY_MANIFEST_FILENAME
    from tracker.rollover import ROLLOVER_LEGACY_FOLDER

    legacy = make_engagement(demo_root, [], EngagementInfo(active=True), household=HOUSEHOLD,
                             year=2026, return_name="1040 - Old Smith")
    (legacy / LEGACY_MANIFEST_FILENAME).write_bytes(b"PK any bytes at all")

    before = _tree_hashes(demo_root)
    code, payload = run(capsys, "rollover", stdin={"prior": str(legacy), "year": 2027})

    assert code == 1
    assert payload["error"] == ROLLOVER_LEGACY_FOLDER.format(
        prior=legacy.name, name=LEGACY_MANIFEST_FILENAME)
    assert not where(demo_root, legacy.name, year=2027).exists()
    assert _tree_hashes(demo_root) == before


def test_a_client_of_only_illegal_characters_still_makes_one_folder_name(capsys, demo_root):
    """The return's folder name is the form and the client, sanitised: a
    client typed as nothing a folder may hold still makes one name, under
    the household and the year, and never a path of its own."""
    spec = {"household": HOUSEHOLD, "form": "1040", "client": "///:::",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    created = Path(payload["state"]["paths"]["engagement"])
    assert created.name == api.default_return_name("1040", "///:::")
    assert created.parent.name == str(default_tax_year())
    assert payload["created"].endswith(created.name)


def test_state_shows_the_status_the_record_holds(capsys, demo_root):
    """Nothing waits for anything (decision 103): a status is recorded,
    and what the app shows is what the record says."""
    from tests.builders import seed_statuses
    from tracker.manifest import StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    seed_statuses(where(demo_root, "Smith"),
                  {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith")))
    assert code == 0
    assert "pending_statuses" not in payload
    assert payload["items"][0]["status"] == Status.RECEIVED


# ------------------------------------------------- the calendar and the prior ----


def test_create_shifts_the_checklist_to_the_engagements_year(capsys, demo_root):
    spec = {"form": "1040", "client": "Smith", "year": 2027,
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"].endswith(api.default_return_name("1040", "Smith"))
    periods = {i["identifier"]: i["period"] for i in payload["state"]["items"]}
    assert periods["A01"] == "TY2027" and periods["B01"] == "TY2026"


def test_templates_carries_the_calendars_default_year(capsys):
    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()
    assert "years" not in payload          # one number, not one per form


def test_rollover_retires_the_prior_in_the_priors_list(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    assert payload["state"]["engagement"]["rolled_from"].endswith("Smith 2025")
    code, payload = run(capsys, "priors")
    # A return keeps its name every year, so the priors are told apart by
    # their labels: the household, the year and the return (decision 125).
    by_label = {p["label"]: p for p in payload["priors"]}
    assert by_label[f"{HOUSEHOLD} 2025 Smith 2025"]["superseded_by"] == f"{HOUSEHOLD} 2026 Smith 2025"
    assert by_label[f"{HOUSEHOLD} 2026 Smith 2025"]["superseded_by"] == ""


def test_run_now_reply_carries_the_households_other_returns_and_the_pass_warnings(
    capsys, demo_root, monkeypatch,
):
    """E-11 (decision 189): Run now on one return answers for the pass. The
    household's other return's warnings, the reader's path, and a run log
    and a page that could not be written are in the reply - not on stderr,
    which the app discards when the reply parses."""
    import tracker.runner as runner
    from tracker import ocr
    from tracker.registry import engagement_from
    from tracker.runner import LOG_NOT_WRITTEN, PAGE_NOT_WRITTEN

    for name, row in (("Smith", "A01"), ("Jones", "B01")):
        spec = {"household": HOUSEHOLD, "return_name": name,
                "items": [{"identifier": row, "document": "W-2"}]}
        assert run(capsys, "create", stdin=spec)[0] == 0
    asked = where(demo_root, "Smith")
    other = where(demo_root, "Jones")

    real_check = runner.check_rules
    said_of_the_other = "a sentence about the other return's rows"
    monkeypatch.setattr(runner, "check_rules", lambda items: (
        [said_of_the_other] if items and items[0].identifier == "B01" else real_check(items)))
    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)

    def refused(*args, **kwargs):
        raise PermissionError("a sync client holds it")

    # The runner's own log and page since decision 203: Run now is its pass.
    monkeypatch.setattr(runner, "append_log", refused)
    monkeypatch.setattr(runner, "write_status_page", refused)

    code, payload = scan(capsys, asked)

    assert code == 1, payload          # a log or page not written is a red pass, as scheduled
    assert said_of_the_other not in payload["run"]["warnings"]
    [theirs] = payload["household"]
    assert theirs["label"] == engagement_from(other).label
    assert theirs["ok"] and theirs["warnings"] == [said_of_the_other]
    assert payload["pass_warnings"] == [
        ocr.READER_PATH_WARNING,
        LOG_NOT_WRITTEN.format(kind="PermissionError"),
        PAGE_NOT_WRITTEN.format(kind="PermissionError"),
    ]


def test_the_apps_pass_is_the_runners_pass(capsys, demo_root):
    # A row added in the editor gets its folder from the scan button,
    # exactly as the scheduled run would give it: one definition of a pass.
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [*rows, {"identifier": "Z01", "document": "Rental Records", "period": "TY2025",
                           "expected_count": 1, "allowed_extensions": "pdf", "min_size_kb": 5,
                           "any_keywords": "schedule e"}],
        "engagement": {},
    })
    assert code == 0, payload
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    assert [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir()] == [REVIEW_DIR_NAME]
    assert payload["run"]["warnings"] == []

    # A lock held by another run: test_run_now_on_a_locked_household_starts_nothing
    # (decision 203 - Run now asks the lock before it starts).

    # A refused edit records nothing, and the pass runs on the last saved
    # list: a typo cannot reach the record (decision 104).
    before = [i["identifier"] for i in payload_of_state(capsys, engagement)["items"]]
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "date_pattern": "(unclosed"}, *rows[1:]], "engagement": {},
    })
    assert code == 1 and payload["error"].startswith(f"Row 1: {COL_DATE_PATTERN}")
    code, payload = scan(capsys, engagement)
    assert code == 0
    assert payload["run"]["ok"] is True
    assert [i["identifier"] for i in payload["state"]["items"]] == before


def test_run_now_hands_the_door_checked_household_to_the_runner_and_nothing_else(
        capsys, demo_root, monkeypatch):
    """Decision 203, R1 and R2: ``run-now`` checks the return through the
    door, finds its household by the layout, and hands the runner the
    schedule's arguments plus Run now's three - and nothing of its own. A
    path outside the root is refused before the runner is reached."""
    import tracker.runner as runner
    from tracker.layout import household_of
    from tracker.settings import settings_dir

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    handed: list[list[str]] = []
    monkeypatch.setattr(runner, "main", lambda argv: handed.append(list(argv)) or 0)

    assert api.main([api.PASS_COMMAND, api.ENGAGEMENT_FLAG, str(engagement)]) == 0
    assert handed == [runner.run_now_arguments(settings_dir(), household_of(engagement))]
    assert capsys.readouterr().out == "", "the API prints nothing of its own before the pass"

    outside = demo_root.parent / "elsewhere" / HOUSEHOLD / "2025" / "1040 - Smith"
    code, out = _raw(capsys, api.PASS_COMMAND, api.ENGAGEMENT_FLAG, str(outside))
    reply = one_reply(out)
    assert code == 1 and reply["failure"]["kind"] == "refused"
    assert len(handed) == 1, "a refused return never reaches the runner"


def test_run_now_on_a_locked_household_starts_nothing(capsys, demo_root, tmp_path):
    """Decision 203, R3: a live lock on any return of the household - the
    schedule's, or another Run now's - is 193's lock notice, and no pass
    starts: no line in the run log, and the inbox as it was."""
    import subprocess
    import sys

    from tracker.locking import LOCK_FILENAME

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    waiting = sorted(p.name for p in inbox_of(engagement).iterdir())
    log_before = (demo_root / LOG_FILENAME).read_bytes() if (demo_root / LOG_FILENAME).exists() else b""
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        (engagement / LOCK_FILENAME).write_text(lock_line(other.pid, dt.datetime.now()), encoding="utf-8")
        code, payload = scan(capsys, engagement)
    finally:
        other.kill()
        other.wait()
    assert code == 1, payload
    assert payload["failure"]["kind"] == "locked"
    assert payload["failure"]["lock"]["engagement"] == str(engagement)
    assert payload["failure"]["lock"]["stale"] is False
    assert sorted(p.name for p in inbox_of(engagement).iterdir()) == waiting
    after = (demo_root / LOG_FILENAME).read_bytes() if (demo_root / LOG_FILENAME).exists() else b""
    assert after == log_before, "no pass started, so the run log has no new line"
    (engagement / LOCK_FILENAME).unlink()


def test_scan_is_no_longer_a_command():
    """Decision 203, R7: an allowlisted command the app no longer sends is
    a door left open and a second definition of Run now."""
    assert "scan" not in api.COMMANDS
    assert api.PASS_COMMAND in api.COMMANDS
    assert api.vocab()["pass_command"] == api.PASS_COMMAND


# ---------------------------------------------- decision 137: the security review ----


def test_a_household_folder_the_tracker_did_not_make_is_refused_and_left_whole(capsys, demo_root):
    """Decision 137 (M1): a household folder that is already there and holds
    no record is a misfit - the tracker did not make it - and the misfit
    rule is that it is left alone. Creating a household of that name is
    refused before anything is written, in the one sentence that says what
    to do; the folder and everything in it stay exactly as they were."""
    from tracker.layout import private_household_dir

    theirs = private_household_dir(demo_root, "Old Smith")
    (theirs / "2019").mkdir(parents=True)
    (theirs / "2019" / "notes.txt").write_text("a person's own notes", encoding="utf-8")
    before = sorted(p.relative_to(theirs) for p in theirs.rglob("*"))

    code, payload = run(capsys, "create", stdin={
        "household": "Old Smith", "return_name": "1040 - Old Smith", "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})

    assert code == 1
    assert payload["error"] == screen_words.HOUSEHOLD_NOT_OURS.format(name="Old Smith")
    assert payload["error"].endswith("Nothing was changed.")
    assert sorted(p.relative_to(theirs) for p in theirs.rglob("*")) == before
    assert (theirs / "2019" / "notes.txt").read_text(encoding="utf-8") == "a person's own notes"
    assert not ledger.path_for(theirs).exists()


def test_a_failed_create_removes_only_the_folders_it_made(capsys, demo_root, monkeypatch):
    """Decision 137 (M1): a create or a rollover that fails part way removes
    the folders its own mkdir made - the return, a year folder it had to
    make, a new household - and nothing it found there. A year the
    household already had, the household's record and its other returns
    stay."""
    from tracker.layout import PRIVATE_TREE, private_household_dir

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    prior = where(demo_root, "Smith 2025")
    household = private_household_dir(demo_root, HOUSEHOLD)
    new_year = household / "2026"
    assert not new_year.exists()

    def the_scaffold_fails(*_args, **_kwargs):
        raise OSError("the scaffold failed half way")

    monkeypatch.setattr(api, "scaffold_engagement", the_scaffold_fails)

    # A second return in a year the household did not have: the year goes too.
    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Smith 2026", "year": 2026})
    assert code == 1 and said_by_class(payload, "OSError")
    assert not new_year.exists()
    # A second return in the year it did have: the year stays.
    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Smith Trust"})
    assert code == 1 and said_by_class(payload, "OSError")
    assert prior.parent.is_dir() and not where(demo_root, "Smith Trust").exists()
    # A rollover into a new year: the same.
    code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
    assert code == 1 and said_by_class(payload, "OSError")
    assert not new_year.exists()
    # A new household: it goes, and the private tree it sat in - which was
    # already there - stays.
    code, payload = run(capsys, "create", stdin={**spec, "household": "New Family"})
    assert code == 1 and said_by_class(payload, "OSError")
    assert not private_household_dir(demo_root, "New Family").exists()
    assert (demo_root / PRIVATE_TREE).is_dir()

    # Nothing that was there before was touched.
    assert ledger.path_for(prior).is_file() and ledger.path_for(household).is_file()
    assert sorted(p.name for p in household.iterdir() if p.is_dir()) == [prior.parent.name]
    assert [p.name for p in prior.parent.iterdir()] == ["Smith 2025"]


def test_a_command_names_a_return_by_its_place_under_a_clients_root_that_is_set(
        capsys, demo_root, tmp_path, monkeypatch):
    """Decision 137 (L1): with no clients root set, no folder is under it,
    so a command naming one is refused rather than let read anywhere; and a
    year or a household folder - which holds a record of its own - is
    refused by where it sits, not read as a return one level too high."""
    from tracker.layout import private_household_dir
    from tracker.settings import ENV_SETTINGS_DIR

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith 2025")
    household = private_household_dir(demo_root, HOUSEHOLD)

    assert run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0
    for too_high in (household, engagement.parent, demo_root):
        code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(too_high))
        assert code == 1, too_high
        assert "is not a return's folder" in payload["error"], payload

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "unconfigured"))
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 1
    assert payload["error"].startswith("Tell the app where your clients live first")


def test_the_renderer_sets_only_the_attributes_its_allowlist_names():
    """Decision 137 (info): ``el()`` - the one builder of every node - sets
    only the attribute names its allowlist holds and throws on any other,
    so no handler, address or style can reach a node through it. Every
    call in the renderer passes names on the list."""
    import re

    js = (Path(__file__).resolve().parents[1] / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8")
    listed = re.search(r"const EL_ATTRIBUTES = new Set\(\[(.*?)\]\);", js, re.S).group(1)
    allowed = set(re.findall(r'"([^"]+)"', listed))
    assert not {name for name in allowed if name.lower().startswith("on")}
    assert not allowed & {"href", "src", "style", "srcdoc", "action", "formaction", "innerHTML"}
    body = js_function("el", "app.js")
    assert "if (!EL_ATTRIBUTES.has(key)) throw" in body

    used: set[str] = set()
    for call in re.finditer(r"\bel\(\s*(?:\"[^\"]*\"|'[^']*'|`[^`]*`|\w+)\s*,\s*\{", js):
        depth, end = 1, call.end()
        while depth:
            depth += {"{": 1, "}": -1}.get(js[end], 0)
            end += 1
        top, level = [], 0
        for ch in js[call.end():end - 1]:
            level += {"{": 1, "[": 1, "(": 1, "}": -1, "]": -1, ")": -1}.get(ch, 0)
            top.append(ch if level == 0 else " ")
        used |= {a or b for a, b in re.findall(
            r'(?:^|,)\s*(?:"([^"]+)"|([A-Za-z_$][\w$-]*))\s*(?=[:,]|$)', "".join(top))}
    assert used and used <= allowed, used - allowed


def test_a_rollover_drops_a_link_that_is_not_a_web_address_and_says_why(capsys, demo_root):
    """Decision 137 (L5, the owner's ruling on phase 1): a household link
    recorded before the rule that is not a web address does not refuse the
    rollover. The new return starts without it, and the reason rides back to
    the app beside the return it is about - for the one-return rollover and
    for the household's."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.locking import engagement_lock
    from tracker.manifest import load_engagement_info
    from tracker.rollover import LINK_NOT_CARRIED

    bad = "file:///C:/Users/firm/inbox"
    said = LINK_NOT_CARRIED.format(link=bad)
    for household in (HOUSEHOLD, "Other Household"):
        assert run(capsys, "create", stdin={
            "household": household, "return_name": "Smith 2025", "form": "1040",
            "link": "https://drive.example/inbox",
            "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
        folder = private_household_dir(demo_root, household)
        with engagement_lock(folder):                     # written before the rule existed
            store.record(store.connect(), folder, ledger.new(
                ledger.HOUSEHOLD_CHANGED, **{ledger.HOUSEHOLD_KEY: {"link": bad}}))
        assert load_household_info(folder).link == bad

    code, payload = run(capsys, "rollover", stdin={
        "prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    assert payload["rollover"]["link_dropped"] == said
    assert load_engagement_info(where(demo_root, "Smith 2025", year=2026)).link == ""

    prior = where(demo_root, "Smith 2025", household="Other Household")
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"year": 2026, "returns": [{"prior": str(prior)}]})
    assert code == 0, payload
    [rolled] = payload["rolled"]
    assert rolled["link_dropped"] == said and payload["skipped"] == []
    assert load_engagement_info(
        where(demo_root, "Smith 2025", year=2026, household="Other Household")).link == ""


def test_a_failed_create_removes_a_year_folder_only_when_it_is_empty(capsys, demo_root, monkeypatch):
    """Decision 137's review (F4): a create that fails removes the return
    it made whole, and a year folder it made only if nothing else is in it -
    a second create running at the same moment may have put its own return
    there, and that return is not this call's to take."""
    from tracker.layout import private_household_dir

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    new_year = private_household_dir(demo_root, HOUSEHOLD) / "2026"
    theirs = new_year / "1040 - Somebody Else"

    def another_create_lands_then_the_scaffold_fails(*_args, **_kwargs):
        theirs.mkdir()
        (theirs / "their file.txt").write_text("theirs", encoding="utf-8")
        raise OSError("the scaffold failed half way")

    monkeypatch.setattr(api, "scaffold_engagement", another_create_lands_then_the_scaffold_fails)
    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Smith 2026", "year": 2026})
    assert code == 1 and said_by_class(payload, "OSError")
    assert not where(demo_root, "Smith 2026", year=2026).exists()        # its own return: gone
    assert (theirs / "their file.txt").read_text(encoding="utf-8") == "theirs"   # theirs: kept
    assert new_year.is_dir()                                             # and the year with it


def test_a_new_return_drops_a_households_old_link_with_the_reason_not_a_refusal(capsys, demo_root):
    """Decision 137's review (F2): a household link recorded before the rule
    that is not a web address does not refuse the next return created in
    that household. The return starts without it and the reply says why, as
    a rollover does; a link the create itself sends is still refused."""
    from tracker.layout import private_household_dir
    from tracker.locking import engagement_lock
    from tracker.manifest import load_engagement_info
    from tracker.rollover import LINK_NOT_CARRIED

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040",
            "link": "https://drive.example/inbox",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    household = private_household_dir(demo_root, HOUSEHOLD)
    bad = "S:\\Clients\\Inbox"
    with engagement_lock(household):
        store.record(store.connect(), household, ledger.new(
            ledger.HOUSEHOLD_CHANGED, **{ledger.HOUSEHOLD_KEY: {"link": bad}}))

    second = {"household": HOUSEHOLD, "return_name": "Smith Trust", "form": "1040",
              "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=second)
    assert code == 0, payload
    assert payload["link_dropped"] == LINK_NOT_CARRIED.format(link=bad)
    assert load_engagement_info(where(demo_root, "Smith Trust")).link == ""

    code, payload = run(capsys, "create", stdin={**second, "return_name": "Smith Estate",
                                                 "link": "file:///C:/x"})
    assert code == 1 and "is not a web address" in payload["error"]


def test_the_reminder_card_says_why_a_link_was_left_out(capsys, demo_root):
    """Decision 137's review (F3): the reminder card carries the sentence
    the draft file and the command line give when the record's link is not
    a web address, so the person reading the letter in the app knows why
    it has no link. A card with a good link says nothing."""
    from tracker.locking import engagement_lock
    from tracker.reminder import LINK_DROPPED

    folder = chased_engagement(capsys, demo_root)
    assert reminder_card(capsys, folder)["link_dropped"] == ""
    bad = "file:///C:/Users/firm/inbox"
    with engagement_lock(folder):
        store.record(store.connect(), folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [], ledger.REMOVED_KEY: [], ledger.INFO_KEY: {"link": bad}}))
    card = reminder_card(capsys, folder)
    assert card["link_dropped"] == LINK_DROPPED.format(link=bad)
    assert bad not in card["text"]
    js = (Path(__file__).resolve().parents[1] / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8")
    assert "card.link_dropped" in js
