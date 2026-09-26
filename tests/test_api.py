"""Tests for tracker/api.py — the JSON command layer the desktop app calls.

The contract under test: every command answers with one JSON object and an
exit code, an error is a JSON object too (never a traceback on stdout), and
the create path refuses a bad request list with a sentence a person can act
on. The clients root is a temp folder recorded through settings, the way
the app records it, so no test touches a real one.
"""

import datetime as dt
import json
import os
import shutil
from pathlib import Path

import pytest

import tracker.api as api
from tests.conftest import TEST_CLIENT, app_stdin, make_engagement
from tests.samples import PRIOR_YEAR, SCRATCH_PEOPLE
from tracker import layout, ledger, reasons, store, view
from tracker.filer import FILED, NEEDS_REVIEW, read_index
from tracker.households import load_household_info
from tracker.layout import PRIVATE_TREE, inbox_of, return_dir_for
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
from tracker.names import propose_spellings
from tracker.records import (
    COUNT_BOUNDS,
    ENGAGEMENT_LABELS,
    MAX_EXPECTED_COUNT,
    MAX_SIZE_KB,
    MIN_EXPECTED_COUNT,
    IndexEntry,
    ledger_key,
)
from tracker.runner import DRAFT_WEEKDAY, LOG_FILENAME, STATUS_PAGE_FILENAME, WEEKDAY_NAMES
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.scheduling import SCHEDULE_XML_ENCODING, TASK_NAME
from tracker.templates import BASE_YEAR, default_tax_year

#: What a count outside the record's bounds is refused with (decision 187).
COUNTS = COUNT_BOUNDS.format(minimum=MIN_EXPECTED_COUNT, maximum=MAX_EXPECTED_COUNT)

#: The one household every spec below names unless the claim is about
#: households. A client folder is a household since decision 125, and a
#: return lives under its year inside it.
HOUSEHOLD = "Test Household"
#: Who every spec below says the return is for, unless the claim is about
#: the people list. A return is refused without one since decision 128.
PEOPLE = [{"kind": "taxpayer", "name": TEST_CLIENT,
           "spellings": list(propose_spellings(TEST_CLIENT, "taxpayer"))}]
#: Who the sample pile's documents are addressed to, as a spec sends them.
SAMPLE_PEOPLE = [{"kind": one.kind, "name": one.name, "spellings": list(one.spellings)}
                 for one in SCRATCH_PEOPLE]


def where(root, return_name, year=None, household=HOUSEHOLD):
    """Where the return a spec named landed.

    The layout's answer, never a name a test typed: the private tree, the
    household, the year, the return (decision 125).
    """
    from tracker.templates import default_tax_year

    return return_dir_for(root, household, year or default_tax_year(), return_name)


@pytest.fixture
def demo_root(short_root, tmp_path, monkeypatch):
    """A clients root recorded the way the app records it: settings.json beside the app.

    Short, because ``create`` refuses a return whose deepest working copy
    would pass what Windows will open (decision 125) and a pytest temporary
    folder spends ninety characters before the layout starts - where the
    office's own root spends twenty-seven. ``short_root`` is walked by the
    agreement fixtures exactly as ``tmp_path`` is.
    """
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root, set_firm

    root = short_root
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(root)
    set_firm("J Park & Associates, CPA")
    return root


def _head_now(argv) -> str:
    """The version of the list ``state`` would hand the editor now (decision
    160), for an ``edit`` or a ``rename`` that does not name its own - blank
    where the command names no engagement, which it then refuses anyway."""
    from tracker.manifest import list_head

    try:
        return list_head(argv[list(argv).index(api.ENGAGEMENT_FLAG) + 1])
    except (ValueError, IndexError, ManifestError):
        return ""


def run(capsys, *argv, stdin=None):
    """Run one command the way main.js does: argv in, one JSON object out.

    A ``create`` spec that names no household, or names the one these
    claims use, is given that one - by its folder once it exists, as the wizard picks it in the list
    (decision 188 refuses a household name typed again): since decision 125 every return belongs to a household, and most
    of what is claimed here is about the API rather than about households.
    The same for the people it is for: since decision 128 a return is
    refused without one, and most of what is claimed here is not about the
    name tier. And an ``edit`` or a ``rename`` carries the version of the
    list it was made from, as the editor's does (decision 160): the current
    one, unless the claim is about a stale one and names it.
    """
    if (stdin is not None and argv and argv[0] == "create"
            and stdin.get("household", HOUSEHOLD) == HOUSEHOLD and "household_path" not in stdin):
        stdin = {key: value for key, value in stdin.items() if key != "household"}
        # Picked in the list once it exists, as the wizard does: since
        # decision 188 a household name typed again is refused.
        from tracker.layout import private_household_dir
        from tracker.settings import clients_root

        root = clients_root()
        known = private_household_dir(root, HOUSEHOLD) if root else None
        stdin = ({"household_path": str(known), **stdin}
                 if known is not None and ledger.path_for(known).is_file()
                 else {"household": HOUSEHOLD, **stdin})
    if stdin is not None and argv and argv[0] == "create" and "people" not in stdin:
        stdin = {"people": PEOPLE, **stdin}
    if stdin is not None and argv and argv[0] in ("edit", "rename") and "head" not in stdin:
        stdin = {**stdin, "head": _head_now(argv)}
    if stdin is not None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sys.stdin", app_stdin(stdin))
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


def test_a_journal_planted_in_the_client_tree_is_never_a_prior(capsys, demo_root):
    # Decision 176: the rollover's prior was checked only for being under
    # the root, and the client tree is under the root. A client can drop
    # any file, so a _ledger.jsonl in the inbox rolled into a return built
    # from the client's own rows and people, and the household's inbox
    # stopped being sorted (two open years).
    from tracker.templates import template_items

    run(capsys, "create", stdin={"return_name": "1040 - Smith", "form": "1040",
                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    planted = make_engagement(inbox_of(where(demo_root, "1040 - Smith")) / "x",
                              template_items("1040", year=2025), scaffold=False)
    before = sorted(p for p in (demo_root / PRIVATE_TREE).rglob("*"))
    for prior in (planted, planted.parent, where(demo_root, "1040 - Smith").parent.parent):
        code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
        assert code == 1
        assert payload["error"] == layout.NOT_A_RETURN.format(name=prior.name, tree=PRIVATE_TREE)
    assert sorted(p for p in (demo_root / PRIVATE_TREE).rglob("*")) == before


def test_a_household_path_must_be_a_household_of_the_private_tree(capsys, demo_root):
    run(capsys, "create", stdin={"return_name": "1040 - Smith", "form": "1040",
                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    engagement = where(demo_root, "1040 - Smith")
    for given in (engagement, engagement.parent, inbox_of(engagement).parent):
        code, payload = run(capsys, "create", stdin={
            "household_path": str(given), "return_name": "Evil", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1
        assert payload["error"] == layout.NOT_A_HOUSEHOLD.format(name=given.name,
                                                              tree=PRIVATE_TREE)
    assert not list((demo_root / PRIVATE_TREE).rglob("Evil"))
    assert not (demo_root / "Clients" / engagement.name).exists()


def test_a_return_named_through_dots_is_the_return_it_resolves_to(capsys, demo_root):
    # Decision 176: the path was checked resolved and used as sent, and
    # every layout helper reads position off the text - so "<return>/2031/.."
    # passed as a return and edit-household wrote a household_changed line
    # into the return's own journal, taking the return for its household.
    run(capsys, "create", stdin={"return_name": "1040 - Smith", "form": "1040",
                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    engagement = where(demo_root, "1040 - Smith")
    dotted = f"{engagement}{os.sep}2031{os.sep}.."
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, dotted)
    assert code == 0, payload
    assert payload["paths"]["engagement"] == str(engagement)
    journal = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, dotted,
                        stdin={"contact": "Mallory"})
    assert code == 0, payload
    assert ledger.path_for(engagement).read_bytes() == journal
    assert load_household_info(engagement.parent.parent).contact == "Mallory"


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
        assert payload["error"] == api.NOT_A_SPEC


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
            api._new_return_dir(demo_root, HOUSEHOLD, 2025, outside)
        with pytest.raises(api.ManifestError, match="is not a household name"):
            api._new_return_dir(demo_root, outside, 2025, "1040 - Smith")


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


def sample_engagement(capsys, demo_root, tmp_path, *names):
    """A 1040 engagement created through the API with sample documents dropped in."""
    from tests.samples import build_samples

    # The pile is addressed to the two people the samples name, so the
    # return lists them (decision 128) exactly as the office's would.
    spec = {"household": HOUSEHOLD, "return_name": "Smith Family 2025", "form": "1040", "client": "John Smith",
            "people": SAMPLE_PEOPLE,
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith Family 2025")
    samples = tmp_path / "samples"
    build_samples(samples)
    for sample in samples.iterdir():
        if not names or sample.name in names:
            (inbox_of(engagement) / sample.name).write_bytes(sample.read_bytes())
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
    assert "vacation photo.bmp" in reviewed
    assert payload["state"]["summary"]["outstanding"] == run_result["outstanding"]
    assert f"{Status.RECEIVED}: 4" in payload["state"]["summary"]["line"]   # A01, B01, C01, D01
    # What the scanner recorded is what the state command reads back.
    rows = {i.identifier: i for i in load_manifest(engagement)}
    assert rows["A01"].status == Status.RECEIVED


def test_the_apps_pass_appends_the_line_the_scheduled_run_appends(capsys, demo_root, tmp_path):
    """A pass made from the app used to leave no trace at all: the log is the
    command line's, and the button makes the same pass, so it writes the same
    line - appended, never replacing what earlier passes wrote."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")

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
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    assert run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Jones Family 2025", "form": "1040",
                                        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert not page.exists()

    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0

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
    from tests.conftest import seed_statuses
    from tracker.manifest import StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    seed_statuses(where(demo_root, "Smith"),
                  {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith")))
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
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"},
                                       {"identifier": "C01", "document": "Form 1098"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
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


def test_rule_two_names_the_inbox_and_the_years_folder_and_is_quoted_everywhere(
        capsys, demo_root, tmp_path):
    """Decision 102, the owner's wording of 2026-09-19, re-rendered for the
    layout of decision 125: the rule used to name the index workbook, and
    then the two folders `Shared` and `PBC`, and none of the three exists
    any more. It says the inbox the client drops into and the client's own
    folder for the year, filled from the one place each is named, and it
    still names no file."""
    from tracker import api
    from tracker.layout import INBOX_DIR_NAME
    from tracker.records import THE_RECORD

    (rule,) = [r for r in api.standing_rules() if r["headline"].startswith("Originals")]

    assert rule["detail"] == (
        f"Files are moved byte for byte under their own names out of {INBOX_DIR_NAME} "
        f"into the client's folder for the year; all work happens on copies, and "
        f"every move is recorded in {THE_RECORD}."
    )
    assert ".xlsx" not in rule["detail"]
    assert "Shared" not in rule["detail"] and "PBC" not in rule["detail"]
    # And nothing in the rendered rule is a placeholder nobody filled.
    assert "{" not in rule["detail"] and "}" not in rule["detail"]


def test_the_state_the_app_reads_carries_no_deferred_index(capsys, demo_root, tmp_path):
    """There is nothing left for Excel to hold the index rows out of, so
    there is no word for it - in the reply, in the pass's own report, or in
    the vocabulary the renderer derives from."""
    from tracker import api
    from tracker.runner import EngagementRun

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    state = api._state(where(demo_root, "Smith 2025"))

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


def test_mark_missing_takes_one_request_off_a_consolidated_statement(capsys, demo_root):
    """d146. The app's button: the filed statement's row names the requests
    it answers, and marking one missing again leaves the statement filed,
    re-scans, and hands back the state with that request outstanding."""
    from tests.test_filer import _consolidated_return

    engagement = _consolidated_return(demo_root)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["identifier"] == "E01" and filed["answered"] == ["A02", "A04"]

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A02",
                               "seq": filed["seq"]})
    assert code == 0, payload
    assert payload["marked_missing"]["identifier"] == "A02"
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["answered"] == ["A04"]
    a02 = next(i for i in payload["state"]["items"] if i["identifier"] == "A02")
    assert a02["status"] == Status.MISSING

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A02",
                               "seq": filed["seq"]})
    assert code == 1 and "does not answer A02" in payload["error"]


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

    spec = {"household": HOUSEHOLD, "return_name": "Reed Property 2025", "client": "Ada Reed", "items": [
        {"identifier": "A01", "document": "Mortgage Interest Statement", "period": "TY2025",
         "required_keywords": "mortgage interest", "min_size_kb": 0, "date_pattern": "*"},
        {"identifier": "A02", "document": "Rental Property Statements", "period": "TY2025",
         "required_keywords": "rental income", "min_size_kb": 0, "date_pattern": "*"},
        *extra,
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Reed Property 2025")
    text_pdf(inbox_of(engagement) / "packet.pdf", "\n".join([
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
    # A bitmap: no request accepts a .bmp, so the record names no candidate
    # and the queue says so rather than nominating the nearest row. A .jpg
    # was the file here until decision 127 made a photo a document; the
    # claim is about a file type nobody takes, and this is one.
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload

    [triaged] = payload["state"]["review"]
    assert triaged["original_name"] == "vacation photo.bmp"
    assert triaged["shortlist"] == [], "no evidence, no suggestion — the person reads it"


def test_the_review_card_has_three_buckets_and_opens_only_a_documents_copy(capsys, demo_root, tmp_path):
    """Decision 190's three buckets, decided here from the row's code and
    its type on disk: each parked row and its triage carry ``bucket`` and
    its true ``extension``; a document's row carries the key its review
    copy is named under in ``paths`` - the only paths the shell opens - and
    a program's carries none, nor, since Open follows 184, a container's."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    (inbox_of(engagement) / "W-2 2025.pdf.exe").write_bytes(b"MZ")
    (inbox_of(engagement) / "scans.zip").write_bytes(b"PK\x03\x04 not really a zip")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]

    rows = {e["original_name"]: e for e in state["index"] if e["decision"] == NEEDS_REVIEW}
    assert {name: (e["bucket"], e["extension"]) for name, e in rows.items()} == {
        "vacation photo.bmp": (api.BUCKET_DOCUMENT, "bmp"),
        "scans.zip": (api.BUCKET_CONTAINER, "zip"),
        "W-2 2025.pdf.exe": (api.BUCKET_NOT_A_DOCUMENT, "exe"),
    }
    assert rows["W-2 2025.pdf.exe"]["open_key"] == "" and rows["scans.zip"]["open_key"] == ""
    opened = Path(state["paths"][rows["vacation photo.bmp"]["open_key"]])
    assert opened.is_file() and opened.parent.name == REVIEW_DIR_NAME
    assert {t["original_name"]: t["bucket"] for t in state["review"]} == {
        name: e["bucket"] for name, e in rows.items()}


def _parked_row(name: str, code: str) -> IndexEntry:
    """A parked row with a review copy, as the filer writes one: fabricated."""
    return IndexEntry(
        received="2026-02-01", original_name=name, size_kb=12.0, digest="7" * 64,
        identifier="", prepared_location=f"{REVIEW_DIR_NAME}/{name}",
        pbc_location=f"pbc/{name}", decision=NEEDS_REVIEW, reason="fabricated", code=code)


@pytest.mark.parametrize("name, code", [
    *(("statement.pdf", code) for code in sorted(api.REFUSED_READING_CODES)),
    *(("mail.eml", code) for code in sorted(api._CONTAINER_CODES)),
    ("scans.zip", reasons.AMBIGUOUS_CODE),
])
def test_a_refused_file_has_no_open_on_the_designated_machine(name, code):
    """Open follows 184 (decision 190): a file whose reading the tracker
    refused, and any email or zip, is opened, if at all, on a machine with
    no Drive sign-in and no client folder - so the API names no copy for
    it to open here, whatever its copy on disk, and the card offers none."""
    row = _parked_row(name, code)
    payload = api._review_payload(row)
    assert payload["open_key"] == "", (name, code, payload)
    assert (payload["bucket"] == api.BUCKET_CONTAINER) == (name != "statement.pdf"), payload


def test_the_refused_codes_are_named_once_and_each_is_a_reason():
    """The list beside the buckets is the ruling's, read from reasons.py:
    every code in it is one a Reason carries, and none is a filing reason."""
    assert api.REFUSED_READING_CODES <= set(reasons.BY_CODE), sorted(api.REFUSED_READING_CODES)
    assert not api.REFUSED_READING_CODES & set(reasons.PLAIN_CODES)
    assert len(api.REFUSED_READING_CODES) == 12, sorted(api.REFUSED_READING_CODES)


@pytest.mark.parametrize("code", [
    reasons.AMBIGUOUS_CODE, reasons.NO_REQUEST_ACCEPTS_CODE, reasons.UNMATCHED_CODE,
    reasons.NAME_NOT_ON_PAGE.code, reasons.CONTESTED_CODE,
])
def test_a_read_and_parked_document_opens_its_marked_copy(code):
    """The other half of the rule: a document the tracker read and parked
    for a filing reason carries the key of its review copy - the firm's
    copy, marked for Protected View - and nothing else opens it."""
    row = _parked_row("statement.pdf", code)
    payload = api._review_payload(row)
    assert payload["bucket"] == api.BUCKET_DOCUMENT
    assert payload["open_key"] == f"review_copy {ledger_key(row)}", payload


def test_every_parked_row_ships_a_unique_handle_and_a_program_from_a_zip_is_answered_by_it(
    capsys, demo_root, tmp_path,
):
    """The review's M3: a program taken from a zip has no location, so the
    row, its triage and every review command travel by ``handle`` - the
    record's key, unique where ``""`` named every such row and the API
    refused it. Setting the first aside by its handle sets aside that row
    and no other; the card also shows a hidden program's type clean (M1)."""
    import io
    import zipfile

    from tracker.filer import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        archive.writestr("invoice.js", b"WScript.Echo(1)")
        archive.writestr("payroll.exe", b"MZ")
    (inbox_of(engagement) / "docs.zip").write_bytes(packed.getvalue())
    (inbox_of(engagement) / "Pay.scr\ufeff").write_bytes(b"MZ another program")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]

    parked = {e["original_name"]: e for e in state["index"] if e["decision"] == NEEDS_REVIEW}
    handles = [e["handle"] for e in parked.values()]
    assert "" not in handles and len(set(handles)) == len(handles)
    assert {t["handle"] for t in state["review"]} == set(handles)
    assert parked["Pay.scr"]["bucket"] == api.BUCKET_NOT_A_DOCUMENT
    assert parked["Pay.scr"]["extension"] == "scr" and parked["Pay.scr"]["open_key"] == ""

    first = parked["invoice.js"]
    assert first["pbc_location"] == ""
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": first["handle"], "note": "", "seq": first["seq"]})
    assert code == 0, payload
    after = {e["original_name"]: e["decision"] for e in payload["state"]["index"]
             if e["original_name"] in ("invoice.js", "payroll.exe")}
    assert after == {"invoice.js": NOT_REQUESTED, "payroll.exe": NEEDS_REVIEW}


def test_dismissing_a_file_takes_it_out_of_the_review_queue(capsys, demo_root, tmp_path):
    from tracker.filer import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
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

    engagement = sample_engagement(capsys, demo_root, tmp_path, "vacation photo.bmp")
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
    (inbox_of(engagement) / original.name).write_bytes(original.read_bytes())
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
    assert [c["key"] for c in vocab["columns"]][-4:] == [
        "override_reason", "named", "asked", "short_title"]
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8"
    )
    for word in (*OVERRIDE_REASONS, OVERRIDE_REASON_OTHER, *Override.ALL, NOT_APPLICABLE_LABEL,
                 SET_ASIDE_NOTE, api.NOT_APPLICABLE_CARRIED, view.NOT_APPLICABLE_SECTION):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word
    for word in (*Override.ALL, OVERRIDE_REASON_OTHER, "Not Applicable in"):
        assert word not in renderer, word
    # Decision 142 (its review, R1): the words it adds reach the page only
    # through this vocabulary, and the renderer types none of them.
    from tracker.manifest import NOT_ASKED_LABEL
    from tracker.rollover import ORIGIN_NEW

    assert vocab["not_asked_label"] == NOT_ASKED_LABEL
    assert vocab["not_asked_key"] == api._slug(NOT_ASKED_LABEL)
    assert vocab["ask_the_client"] == api.ASK_THE_CLIENT
    assert vocab["ask_the_client_note"] == api.ASK_THE_CLIENT_NOTE
    assert vocab["not_asked_table_label"] == api.NOT_ASKED_TABLE_LABEL
    assert vocab["roll_template_label"] == api.ROLL_TEMPLATE_LABEL
    assert vocab["nothing_asked"] == api.NOTHING_ASKED
    assert vocab["origin_new"] == ORIGIN_NEW
    assert vocab["new_not_asked_carried"] == api.NEW_NOT_ASKED_CARRIED
    assert vocab["editor"]["not_asked_heading"] == view.NOT_ASKED_SECTION
    assert vocab["editor"]["yes_no_fields"] == ["named", "asked"]
    html = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "index.html").read_text(
        encoding="utf-8")
    for word in (NOT_ASKED_LABEL, api.ASK_THE_CLIENT, api.ASK_THE_CLIENT_NOTE,
                 api.NOT_ASKED_TABLE_LABEL, api.ROLL_TEMPLATE_LABEL, api.NOTHING_ASKED,
                 api.NEW_NOT_ASKED_CARRIED.split("{n}")[1].split(" - ")[0].strip(),
                 view.NOT_ASKED_SECTION.split("{")[0].strip() + " ("):
        assert word not in renderer and word not in html, word

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098", "period": "TY2025"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "period": "TY2025", "manual_override": Override.NOT_APPLICABLE},
        {"identifier": "A02", "document": "Prior return", "period": "TY2024", "date_pattern": "*"},
        {"identifier": "A03", "document": "Whenever", "period": "quarterly"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    state = payload_of_state(capsys, where(demo_root, "Smith"))
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith Family 2025", "form": "1040", "client": "John Smith",
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

    spec = {"household": HOUSEHOLD, "return_name": "Willow Inc 2025", "form": "1120S", "client": "Willow Inc",
            "items": [t for t in api.FORM_TEMPLATES["1120S"] if t["core"]]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == "1120S"
    assert load_engagement_info(where(demo_root, "Willow Inc 2025")).form == "1120S"


def test_an_engagement_created_without_a_form_says_nothing_rather_than_guessing(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == ""


def test_rollover_carries_the_catalog_the_prior_was_cut_from(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == "1040"


def test_rollover_carries_the_client_but_not_last_years_link_or_due(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/old", "due": "2026-04-15", "sender": "Jason",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    info = payload["state"]["engagement"]
    assert info["client"] == "John Smith" and info["sender"] == "Jason"
    # The inbox is the household's and does not change from one year to the
    # next (decision 125), so the link the household holds is refilled
    # rather than left blank for somebody to paste again.
    assert info["link"] == "https://drive.example/old"
    # Last year's due date does not carry either: what is there is this
    # year's own default (decision 117), never the date twelve months gone.
    assert info["due"] != "2026-04-15"
    assert info["name"] == ""                      # the folder is the name
    assert payload["created"] == f"{HOUSEHOLD} 2026 Smith 2025"


def test_a_bad_due_date_is_a_sentence(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "X", "due": "next friday", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    # The sentence names the field by the label the editor shows, so the
    # two dates are refused in the same words (decision 117).
    assert payload["error"] == f"{ENGAGEMENT_LABELS['due']} must be YYYY-MM-DD, got 'next friday'"
    assert not (where(demo_root, "X")).exists()
    bad = {"household": HOUSEHOLD, "return_name": "X", "form": "1040", "filing_deadline": "april",
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

    spec = {"household": HOUSEHOLD, "return_name": "Willow 2025", "form": "1040", "year": 2025, "client": "Willow",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    deadline = filing_deadline_for("1040", 2025)
    info = payload["state"]["engagement"]
    assert info["filing_deadline"] == deadline.isoformat()
    assert info["due"] == ask_by_for(deadline).isoformat()
    assert load_engagement_info(where(demo_root, "Willow 2025")).filing_deadline == deadline

    # What a person typed wins over the default, and both stay editable.
    typed = {**spec, "return_name": "Typed 2025", "due": "2026-03-01", "filing_deadline": "2026-04-18"}
    code, payload = run(capsys, "create", stdin=typed)
    assert code == 0, payload
    assert payload["state"]["engagement"]["due"] == "2026-03-01"
    assert payload["state"]["engagement"]["filing_deadline"] == "2026-04-18"

    # A form the catalog has no deadline for fills nothing, rather than guessing.
    none = {"household": HOUSEHOLD, "return_name": "No Form 2025", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=none)
    assert code == 0, payload
    assert payload["state"]["engagement"]["filing_deadline"] == ""
    assert payload["state"]["engagement"]["due"] == ""


def test_the_editor_saves_and_clears_the_filing_deadline(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "form": "1040", "year": 2025,
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "year": 2025, "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    prior = load_engagement_info(where(demo_root, "Smith 2025"))
    assert prior.filing_deadline == filing_deadline_for("1040", 2025)

    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    deadline = filing_deadline_for("1040", 2026)
    info = payload["state"]["engagement"]
    assert info["filing_deadline"] == deadline.isoformat() != prior.filing_deadline.isoformat()
    assert info["due"] == ask_by_for(deadline).isoformat()


# ---------------------------------------------------- edit, lock and names ----


def test_an_invalid_row_is_refused_by_the_api_with_the_row_and_column_named_and_nothing_is_recorded(capsys, demo_root):
    from tests.test_manifest import k1_rows
    from tracker.records import rule_to_json

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    before = ledger.path_for(engagement).read_bytes()
    rows = payload_of_state(capsys, engagement)["rules"]

    bad = [dict(rows[0]), {**rows[1], "expected_count": "two"}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": bad, "engagement": {}})
    assert code == 1
    assert payload["error"] == f"Row 2: {COL_EXPECTED_COUNT} {COUNTS}"
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
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "client": "John", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
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
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "client": "John", "link": "https://y", "due": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
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
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "period": "TY2025", "required_keywords": "W-2",
         "date_pattern": "*"},
        {"identifier": "A02", "document": "1098", "period": "TY2025", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
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
        spec = {"household": HOUSEHOLD, "return_name": f"Bad {typed}", "items": [
            {"identifier": "A01", "document": "W-2", "expected_count": typed}]}
        code, payload = run(capsys, "create", stdin=spec)
        assert code == 1 and payload["error"] == f"A01: {COL_EXPECTED_COUNT} {COUNTS}", payload


def test_a_name_whose_folder_was_deleted_by_hand_can_be_created_again(capsys, demo_root):
    """The store still holds the row of a folder someone deleted in
    Explorer; without forgetting it first, the new, shorter journal would
    read as truncated and the create would fail once with that sentence."""
    import shutil

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith")))[0] == 0
    shutil.rmtree(where(demo_root, "Smith"))
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert [r["identifier"] for r in payload["state"]["rules"]] == ["A01"]


def test_a_detail_with_a_line_break_inside_it_is_recorded_on_one_line(capsys, demo_root):
    """A sender pasted with a CRLF inside it would carry that break into
    the reminder draft's headers; every detail is one line, inner
    whitespace folded to a space."""
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "sender": "Jason Park\r\nBcc: x@evil.example", "client": " John\tSmith ",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    details = payload["state"]["engagement"]
    assert details["sender"] == "Jason Park Bcc: x@evil.example" and details["client"] == "John Smith"
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith")),
                        stdin={"items": payload["state"]["rules"], "engagement": {"firm": "J Park\n& Associates"}})
    assert code == 0 and payload["state"]["engagement"]["firm"] == "J Park & Associates"


def test_a_failed_create_leaves_no_folder_and_no_store_row(capsys, demo_root, monkeypatch):
    spec = {"household": HOUSEHOLD, "return_name": "Bad", "items": [
        {"identifier": "A01", "document": "W-2"},
        {"identifier": "A02", "document": "x", "date_pattern": "(unclosed"},
    ]}
    conn = store.connect()
    rows_before = conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"].startswith(f"Row 2: {COL_DATE_PATTERN}")
    assert not (where(demo_root, "Bad")).exists()
    conn = store.connect()
    assert conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0] == rows_before
    assert store.rules(conn, where(demo_root, "Bad")) is None

    # A household the record already knows is adopted, so the only writer
    # the refusal below meets is the undo's own.
    assert run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Good",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0

    # A store that cannot be reached at that moment neither replaces the
    # refusal sentence with its own nor leaves the half-built folder behind.
    def cannot(*a, **k):
        raise store.StoreError("the store is locked")

    monkeypatch.setattr(store, "forget", cannot)
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"].startswith(f"Row 2: {COL_DATE_PATTERN}")
    assert not (where(demo_root, "Bad")).exists()


def test_the_editor_shows_the_persons_rows_and_never_a_taught_keyword_as_a_typed_one(capsys, demo_root, tmp_path):
    from tests.test_scanner import text_pdf

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "any_keywords": "w-2"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    text_pdf(inbox_of(engagement) / "scan0012.pdf", "nothing the rules recognise")
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[1]["lock"] is None

    lock = engagement / LOCK_FILENAME
    # Started this minute: a lock this machine wrote before it last started
    # is dead by the boot rule (decision 189), so a fixed old date would be.
    started = dt.datetime.now().replace(microsecond=0)
    lock.write_text(lock_line(os.getpid(), started), encoding="utf-8")
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert payload["lock"] == {"started": started.isoformat(), "age_minutes": 0, "stale": False,
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
    assert payload["created"].endswith(api.default_return_name("1040", "Smith Family"))
    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()


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

    monkeypatch.setattr(api, "append_log", refused)
    monkeypatch.setattr(api, "write_status_page", refused)

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(asked))

    assert code == 0, payload
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
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    assert [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir()] == [REVIEW_DIR_NAME]
    assert payload["run"]["warnings"] == []

    # A lock held by another run is reported as skipped, not as an error.
    # Another run is another process: a lock naming this one, which it does
    # not hold, is its own leftover and is replaced (decision 171).
    import subprocess
    import sys

    from tracker.locking import LOCK_FILENAME
    other = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])
    try:
        (engagement / LOCK_FILENAME).write_text(lock_line(other.pid, dt.datetime.now()),
                                                encoding="utf-8")
        code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    finally:
        other.kill()
        other.wait()
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


def test_the_app_is_told_at_once_when_it_sits_too_deep_for_its_reader(capsys, tmp_path, monkeypatch):
    """SPEC-169 section 9: ``list``, the app's first call, carries the
    short-path warning (shown in a banner that stays), with a root or
    without one; and nothing when the app's folder is fine."""
    from tracker import ocr
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    assert run(capsys, "list")[1]["reader_warning"] == ""
    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)
    assert run(capsys, "list")[1]["reader_warning"] == ocr.READER_PATH_WARNING
    clients = tmp_path / "Clients"
    clients.mkdir()
    assert run(capsys, "set-root", stdin={"root": str(clients)})[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is False
    assert payload["reader_warning"] == ocr.READER_PATH_WARNING


def test_the_app_state_reports_the_last_pass(capsys, tmp_path, monkeypatch):
    """``list``, the call the main screen is drawn from, carries the one
    line about the scheduled pass (decision 159, E4) in the runner's words
    and colour, with a root or without one: amber before any pass, red
    after a failed one."""
    import datetime as dt

    from tracker import runner
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is True
    assert payload["last_pass"] == {"text": runner.LAST_PASS_NEVER, "level": runner.LEVEL_WARN}

    now = dt.datetime.now()
    runner.write_last_pass(runner.last_pass_path(), started=now, ended=now, root="",
                           result=runner.PASS_FAILED, reason_code=runner.PASS_ROOT_REFUSED)
    clients = tmp_path / "Clients"
    clients.mkdir()
    assert run(capsys, "set-root", stdin={"root": str(clients)})[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["needs_root"] is False
    assert payload["last_pass"]["level"] == runner.LEVEL_ERR
    assert runner.PASS_REASONS[runner.PASS_ROOT_REFUSED] in payload["last_pass"]["text"]


def test_the_short_path_warning_comes_with_the_returns_too(capsys, demo_root, monkeypatch):
    from tracker import ocr

    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)
    spec = {"household": HOUSEHOLD, "return_name": "First", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "list")
    assert code == 0 and payload["engagements"]
    assert payload["reader_warning"] == ocr.READER_PATH_WARNING


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
    spec = {"household": HOUSEHOLD, "return_name": "First", "items": [{"identifier": "A01", "document": "W-2"}]}
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
    # The job reads the root the app reads, from the one settings file
    # (decision 131) - it names the folder of that file, never the root.
    assert payload["settings"] in xml and "T06:30:00" in xml and "PT60M" in xml
    assert calls == [Path(payload["xml"])]


def test_install_schedule_writes_the_job_from_the_apps_own_settings_folder(
    capsys, demo_root, monkeypatch, tmp_path,
):
    """Decision 131: the job's command line names the settings folder this
    app runs with - the one the Electron shell hands it - and no clients
    root, so a root changed in the app is the root the job walks next."""
    import tracker.api as api_module
    from tracker.runner import SETTINGS_FLAG
    from tracker.scheduling import quote_argument
    from tracker.settings import settings_dir

    monkeypatch.setattr(api_module, "install_task", lambda xml, name=TASK_NAME: ["schtasks"])
    code, payload = run(capsys, "install-schedule", stdin={})
    assert code == 0, payload
    assert payload["settings"] == str(settings_dir()) == str(tmp_path / "app")
    xml = Path(payload["xml"]).read_text(encoding=SCHEDULE_XML_ENCODING)
    assert f"{SETTINGS_FLAG} {quote_argument(settings_dir())}" in xml
    assert str(demo_root) not in xml


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
    assert f"<Arguments>{RUNNER_MODE_FLAG} " in xml and LOG_FLAG in xml and payload["settings"] in xml
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
        "came_from": api.CAME_FROM_SUBFOLDER,
        "dismissed_heading": api.DISMISSED_HEADING, "file": api.FILE_LABEL,
        "file_anyway": api.FILE_ANYWAY_LABEL,
        "unfile": api.UNFILE_LABEL, "unfile_note": api.UNFILE_NOTE_HINT,
        "mark_missing": api.MARK_MISSING_LABEL, "also_answers": api.ALSO_ANSWERS_LABEL,
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
        "hand_over": api.HAND_OVER_LABEL,
        "hand_over_return": api.HAND_OVER_RETURN_LABEL,
        "hand_over_request": api.HAND_OVER_REQUEST_LABEL,
        "handed_over": api.HANDED_OVER_LINE,
        "file_where_it_waits": api.FILE_WHERE_IT_WAITS_LABEL,
        "buckets": api.BUCKET_HEADINGS, "bucket_order": list(api.BUCKET_HEADINGS),
        "not_a_document": api.BUCKET_NOT_A_DOCUMENT,
        "open_copy": api.OPEN_COPY_LABEL, "true_type": api.TRUE_TYPE,
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
    # And the maximums, the record's own (decision 187): the page's number
    # boxes stop where the store's gate would refuse.
    assert editor["maximums"] == {"expected_count": MAX_EXPECTED_COUNT, "min_size_kb": MAX_SIZE_KB}
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
        "inbox_held_line": reminder.INBOX_HELD_SUMMARY,
        "heading": reminder.REMINDER_HEADING,
        "stage_group": reminder.STAGE_GROUP_LABEL,
        "subject_prefix": reminder.SUBJECT_PREFIX,
        "copy": reminder.COPY_LABEL,
        "approve": reminder.APPROVE_LABEL,
        "open_draft": reminder.OPEN_DRAFT_LABEL,
        "last_drafted_line": reminder.LAST_DRAFTED_LINE,
        "never_drafted_line": reminder.NEVER_DRAFTED_LINE,
        "approved_line": reminder.APPROVED_LINE,
        "approved_then_edited": reminder.APPROVED_THEN_EDITED,
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
    # The client sent their W-2 with a password on it: nothing in it can
    # be read, so no request accepts it and A01 stays Missing.
    write_pdf(inbox_of(folder) / f"W-2 Jane Smith {PRIOR_YEAR + 1}.pdf",
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

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"},
                                       {"identifier": "C01", "document": "Form 1098"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
    seed_statuses(folder, {
        "A01": StatusUpdate(status=Status.MISSING),
        "C01": StatusUpdate(status=Status.FAILED, file_count=1,
                            validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"),
                            note_codes=reasons.WRONG_DOCUMENT.code),
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
    assert payload["created"].endswith(api.default_return_name("1120S", "Acme"))


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
    # In Prepared itself, renamed by a person under its request's name...
    "renamed under its request's name": (
        lambda eng, home: home.with_name(home.name.split(" - ")[0] + " - the 1098 (final).pdf"), True),
    # ...but not under a name no request's identifier begins.
    "renamed to a name no request begins": (
        lambda eng, home: home.with_name("the 1098 (final).pdf"), False),
    # A folder a person made inside Prepared is theirs (decision 168), even
    # one shaped like a request's...
    "a person's folder": (lambda eng, home: eng / PREPARED_DIR_NAME / "C01 - old" / home.name, False),
    # ...and the review folder belongs to no request.
    "the review folder": (
        lambda eng, home: eng / PREPARED_DIR_NAME / REVIEW_DIR_NAME / home.name, False),
}


@pytest.mark.parametrize("where", list(WANDERED))
def test_the_state_lists_moved_rows_with_home_now_seq_and_the_request_its_name_belongs_to(
    capsys, demo_root, tmp_path, where,
):
    """Decision 110's card is its own list, not a fourth column: the row's
    record version, the home the record put the copy at, where its bytes are
    now, and - only where the copy sits in Prepared itself under a name that
    belongs to a request (decision 168) - which request that is, because
    "keep it where it is" means nothing anywhere else."""
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


def test_keep_it_here_is_offered_by_the_copys_name(capsys, demo_root, tmp_path):
    """Claim 7 (decision 168, ruling 6): a mislaid copy a person renamed
    within Prepared to ``A01 - ...`` - another request's name - is offered
    Keep it here for A01, and keeping it files it there as A01's canonical
    copy, beside the others; one inside a person's folder is offered no
    Keep it here."""
    engagement, filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, lambda eng, home: home.with_name("A01 - the 1098 I renamed.pdf"))
    [moved] = state["moved"]
    assert filed["identifier"] == "C01" and moved["in_request"] == "A01"

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "identifier": moved["in_request"],
                               "seq": moved["seq"]})
    assert code == 0, payload
    [row] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert row["identifier"] == "A01"
    assert row["prepared_location"].startswith(f"{PREPARED_DIR_NAME}/A01 - ")
    assert "/" not in row["prepared_location"][len(PREPARED_DIR_NAME) + 1:]
    assert (engagement / row["prepared_location"]).is_file() and not target.exists()
    assert payload["state"]["moved"] == []
    # One inside a person's folder is offered none: WANDERED's "a person's
    # folder", above, is that half of the claim.


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


def test_the_moved_card_offers_mark_missing_on_a_row_whose_copy_and_original_are_both_gone(
    capsys, demo_root, tmp_path,
):
    """d157, ruling B6. A mislaid copy whose original is gone too has nothing
    to put back, keep or send to review, so the state says so (``gone``,
    with the row's own request) and the card offers the one answer left:
    **Mark ... missing**, the ``mark-missing`` command with the row's own
    identifier. Pressed, the row leaves the card, its request reads Missing
    and the next draft asks the client for it."""
    from tracker.layout import locate
    from tracker.reminder import draft_reminder

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    (engagement / filed["prepared_location"]).unlink()
    locate(engagement, filed["pbc_location"]).unlink()

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [moved] = payload["state"]["moved"]
    assert moved["gone"] is True and moved["now"] is None
    assert moved["identifier"] == filed["identifier"]
    assert filed["identifier"] not in draft_reminder(engagement).asked

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": moved["pbc_location"], "identifier": moved["identifier"],
                               "seq": moved["seq"]})

    assert code == 0, payload
    assert payload["marked_missing"]["identifier"] == filed["identifier"]
    assert payload["state"]["moved"] == []
    status = {i["identifier"]: i["status"] for i in payload["state"]["items"]}
    assert status[filed["identifier"]] == Status.MISSING
    assert filed["identifier"] in draft_reminder(engagement).asked

    # The card draws that answer, and only that answer, on such a row - with
    # the API's own label, wired to the same command as the filed list's.
    js = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8")
    moved_row = js[js.index("function movedRow("):js.index("async function restoreMoved(")]
    gone_branch = moved_row[moved_row.index("if (m.gone)"):moved_row.index("\n  }\n")]
    assert "vocab.review_labels.mark_missing" in gone_branch and "r-withdraw" in gone_branch
    assert "r-restore" not in gone_branch and "r-review" not in gone_branch
    listener = js[js.index('$("moved-list").addEventListener'):]
    assert "withdrawAnswer(" in listener[:listener.index("});")]


# ------------------------------------------------- the reminder card (d118) ----
# The app shows the week's draft, moves it up and down the ladder without
# touching the file, copies it and approves it. Nothing sends.


def chased_engagement(capsys, demo_root, name="Chase", client="John Smith"):
    """One engagement with two documents outstanding and a scan behind them."""
    from tests.conftest import seed_statuses
    from tracker.manifest import StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": name, "client": client, "due": "2026-03-15", "filing_deadline": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2 Wage Statements"},
                      {"identifier": "B01", "document": "Bank Statements"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, name)
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
    # The letter names the return as everything does since decision 125:
    # the household, the year and the return.
    label = f"{HOUSEHOLD} {default_tax_year()} Chase"
    assert card["subject"] == stage_named(4).subject.format(engagement=label, n=2)
    assert card["letter"]["greeting"] and card["letter"]["sections"]
    assert card["html"].startswith("<div") and "<style" not in card["html"]
    assert not (folder / DRAFT_FILENAME).exists(), "reading the card never drafts"

    # The toggle: the same recipients, another stage's words, still no file.
    milder = reminder_card(capsys, folder, stage=1)
    assert milder["stage"] == 1 and milder["asked"] == card["asked"]
    assert milder["subject"] == stage_named(1).subject.format(engagement=label, n=2)
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
        validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"),
        note_codes=reasons.WRONG_DOCUMENT.code)})

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


def test_a_letter_that_only_asks_about_a_program_is_offered_on_the_card(capsys, demo_root):
    """The re-check's S-N1 on this surface: every request is in and a
    program is parked. The card offers the letter that asks about it -
    editable, as the scheduler writes it - at no stage, and a stage asked
    for re-stages nothing, because a file that is not a document is no
    rung."""
    from tests.conftest import seed_index, seed_statuses
    from tracker import reasons
    from tracker.filer import IndexEntry
    from tracker.manifest import StatusUpdate
    from tracker.reminder import SECTION_FAILED, STAGE_4_CONSEQUENCES

    folder = chased_engagement(capsys, demo_root, name="Program")
    seed_statuses(folder, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1),
                           "B01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    seed_index(folder, [IndexEntry(
        received="2026-02-01", original_name="setup.exe", size_kb=0.1, digest="5" * 64,
        identifier="", prepared_location="", pbc_location="pbc/setup.exe",
        decision=NEEDS_REVIEW, reason=reasons.NOT_A_DOCUMENT.format(),
        code=reasons.NOT_A_DOCUMENT.code,
    )])

    for stage in (None, 4):
        card = reminder_card(capsys, folder, stage=stage)
        assert card["held"] == [] and card["editable"] is True
        assert card["asked"] == []
        assert STAGE_4_CONSEQUENCES not in card["text"]
        assert f"{SECTION_FAILED}\n  - setup.exe - " in card["text"]
        assert "still needed" not in card["subject"]


def test_the_card_shows_the_inbox_hold_in_the_apis_words_and_offers_no_approve(capsys, demo_root):
    """Decision 133 on this surface: a file still waiting in the household's
    inbox holds the card as a held row does (118 §9) - the hold line, no
    rows, a dead toggle, no letter and no approval - and every word of it is
    the API's; the renderer types none."""
    from tracker.reminder import INBOX_HELD_SUMMARY, INBOX_HOLD

    folder = chased_engagement(capsys, demo_root, name="Waiting")
    (inbox_of(folder) / "W-2 from the client.pdf").write_bytes(b"%PDF-1.4 not sorted yet")

    card = reminder_card(capsys, folder)
    assert card["held"] == [] and card["unsorted"] == 1
    assert (card["subject"], card["text"], card["html"], card["letter"]) == ("", "", "", {})
    assert card["editable"] is False

    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": card["stage"], "fingerprint": card["fingerprint"]})
    assert code == 1 and payload["error"] == INBOX_HOLD.format(n=1)
    assert list(folder.glob("reminder-draft*")) == []

    # The household card says the same hold beside the return.
    [one] = api._state(folder)["household"]["returns"]
    assert one["reminder"]["unsorted"] == 1

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["reminder"]["inbox_held_line"] == INBOX_HELD_SUMMARY
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8")
    for word in (INBOX_HELD_SUMMARY, INBOX_HELD_SUMMARY.split("{")[0].strip(),
                 INBOX_HOLD.split("{")[0].strip()):
        assert word not in renderer, word
    assert "vocab.reminder.inbox_held_line" in renderer


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
    # Edited after the approval, so the approval lapsed (decision 190).
    assert after["approved"] is None and after["lapsed"] is True
    assert after["letter"] == {} and "ask about the rental" in after["text"]
    assert after["html"].startswith("<div") and "ask about the rental" in after["html"]
    assert EDITED_BY_HAND  # the sentence the card shows beside it, from the vocabulary
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": after["stage"], "fingerprint": after["fingerprint"]})[0] == 0
    assert written.read_bytes() == edited, "an edited draft is approved as it stands"
    again = reminder_card(capsys, folder)
    assert again["approved"] is not None and again["lapsed"] is False


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
        validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format(),
        note_codes=reasons.NO_TEXT_LAYER.code)})
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


# ============ the household, in the app (decision 125) =====================


def test_the_app_lists_misfits_and_households_from_the_same_walk_the_pass_uses(capsys, demo_root):
    """What a person sees and what the scheduled job walks are one list:
    the households with their returns, and every folder left alone with the
    one sentence saying why."""
    from tracker.layout import CLIENTS_TREE, PRIVATE_TREE, client_household_dir, inbox_dir_for, private_household_dir
    from tracker.registry import MISFIT_NOT_A_TREE, MISFIT_NOT_A_YEAR

    assert run(capsys, "create", stdin={
        "household": "Park Family", "members": ["John Park", "Maria Park"],
        "contact": "John & Maria", "link": "https://drive.example/park",
        "return_name": "1040 - John & Maria Park", "form": "1040", "year": 2026,
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping", "year": 2026,
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    (demo_root / "Archive").mkdir()
    (private_household_dir(demo_root, "Park Family") / "Old").mkdir()

    code, payload = run(capsys, "list")
    assert code == 0

    [household] = payload["households"]
    assert household["name"] == "Park Family"
    assert household["path"] == str(private_household_dir(demo_root, "Park Family"))
    assert household["client_folder"] == str(client_household_dir(demo_root, "Park Family"))
    assert household["inbox"] == str(inbox_dir_for(demo_root, "Park Family"))
    assert household["members"] == ["John Park", "Maria Park"]
    assert household["contact"] == "John & Maria" and household["link"] == "https://drive.example/park"
    assert household["open_years"] == [2026]
    assert [r["return_name"] for r in household["returns"]] == [
        "1040 - John & Maria Park", "1120S - Park Landscaping"]
    assert all(r["year"] == 2026 and r["active"] for r in household["returns"])

    # The picker's own list carries the label and the household it is in.
    assert [e["name"] for e in payload["engagements"]] == [
        "Park Family 2026 1040 - John & Maria Park",
        "Park Family 2026 1120S - Park Landscaping"]
    assert {e["household"] for e in payload["engagements"]} == {household["path"]}

    said = {Path(m["path"]).name: m["sentence"] for m in payload["misfits"]}
    assert said["Archive"] == MISFIT_NOT_A_TREE.format(
        clients=CLIENTS_TREE, private=PRIVATE_TREE)
    assert said["Old"] == MISFIT_NOT_A_YEAR


def test_create_makes_a_household_and_its_first_return_and_undoes_both_on_failure(
        capsys, demo_root):
    """The household is written first, so a return never exists under one
    the record does not know - and a create that fails leaves neither."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.records import HouseholdInfo

    spec = {"household": "Park Family", "members": ["John Park", "Maria Park"],
            "contact": "John & Maria", "link": "https://drive.example/park",
            "return_name": "1040 - John & Maria Park", "form": "1040", "year": 2026,
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload

    household_dir = private_household_dir(demo_root, "Park Family")
    assert load_household_info(household_dir) == HouseholdInfo(
        name="Park Family", members=("John Park", "Maria Park"),
        contact="John & Maria", link="https://drive.example/park")
    # The return's greeting and link come from the household.
    assert payload["state"]["engagement"]["client"] == "John & Maria"
    assert payload["state"]["engagement"]["link"] == "https://drive.example/park"

    # And a create that fails leaves no folder, no record, and no household
    # it made itself.
    bad = {**spec, "household": "Vega Landscaping LLC", "return_name": "1120S - Vega",
           "items": [{"identifier": "A01", "document": "W-2"},
                     {"identifier": "A02", "document": "x", "date_pattern": "(unclosed"}]}
    code, payload = run(capsys, "create", stdin=bad)
    assert code == 1 and COL_DATE_PATTERN in payload["error"]
    assert not private_household_dir(demo_root, "Vega Landscaping LLC").exists()
    assert not where(demo_root, "1120S - Vega", year=2026,
                     household="Vega Landscaping LLC").exists()
    # The household this call did not make is untouched.
    assert load_household_info(household_dir).name == "Park Family"


def test_create_adds_a_return_to_an_existing_household_and_leaves_its_record_alone(
        capsys, demo_root):
    """A household's details are edited in ``edit-household`` and never
    written over by a return added to it."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "members": ["John Park"], "contact": "John",
        "link": "https://drive.example/park", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    household_dir = private_household_dir(demo_root, "Park Family")

    code, payload = run(capsys, "create", stdin={
        "household_path": str(household_dir), "members": ["Somebody Else"],
        "contact": "Nobody", "link": "https://drive.example/wrong",
        "return_name": "1120S - Park Landscaping",
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})
    assert code == 0, payload

    held = load_household_info(household_dir)
    assert held.members == ("John Park",) and held.contact == "John"
    assert held.link == "https://drive.example/park"
    assert len(ledger.read_events(household_dir)) == 1        # one event, still
    assert payload["state"]["household"]["returns"][1]["return_name"] == "1120S - Park Landscaping"

    # A household named again by name is refused since decision 188 (R7):
    # it is picked in the list, and the sentence says so and what to add.
    code, payload = run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1065 - Park & Lee LLC",
        "items": [{"identifier": "C01", "document": "K-1"}]})
    assert code == 1 and payload["error"] == api.DUPLICATE_HOUSEHOLD.format(existing="Park Family")
    assert len(ledger.read_events(household_dir)) == 1


def test_create_refuses_a_return_whose_deepest_path_would_pass_the_limit_and_says_the_length(
        capsys, demo_root):
    """A folder made today that cannot hold a filed document in February is
    a failure at a filing deadline, so it is refused now, with the length."""
    from tracker.layout import MAX_PATH_LENGTH

    # Two names of the longest a name may be (decision 188) pass what
    # Windows will open under a root that grew.
    _a_deeper_root(demo_root)
    code, payload = run(capsys, "create", stdin={
        "household": "Park Family " + "h" * 68, "return_name": "1040 - " + "x" * 73, "form": "1040",
        "items": [{"identifier": "A01", "document": "y" * 90}]})

    assert code == 1
    assert str(MAX_PATH_LENGTH) in payload["error"]
    assert "shorten the household or the return name" in payload["error"]
    assert "characters" in payload["error"]
    assert not any(demo_root.rglob(ledger.LEDGER_FILENAME))   # nothing was made


def test_create_refuses_a_household_or_return_name_that_is_not_a_folder_name(capsys, demo_root):
    """A household and a return are each one folder name: the layout puts
    them where they go, so a name carrying a separator is a typo."""
    for field, value in (("household", "../outside"), ("return_name", "sub/child")):
        spec = {"household": "Park Family", "return_name": "1040 - John",
                "items": [{"identifier": "A01", "document": "W-2"}], field: value}
        code, payload = run(capsys, "create", stdin=spec)
        what = "household" if field == "household" else "return"
        assert code == 1 and f"is not a {what} name" in payload["error"], field
    assert not any(demo_root.rglob(ledger.LEDGER_FILENAME))


def test_the_returns_details_carry_household_year_and_return_name_and_the_editor_cannot_change_them(
        capsys, demo_root):
    """The folders are the names, and the record is what wins when somebody
    renames one - so the three are written at creation and never edited."""
    from tracker.records import ENGAGEMENT_EDITABLE, ENGAGEMENT_FIELDS

    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park", "year": 2026,
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - John Park", year=2026, household="Park Family")

    details = api._state(engagement)["engagement"]
    assert details["household"] == "Park Family"
    assert details["tax_year"] == 2026
    assert details["return_name"] == "1040 - John Park"

    rows = api._state(engagement)["rules"]
    for field in ("household", "tax_year", "return_name"):
        assert field in {name for _, name in ENGAGEMENT_FIELDS}
        assert field not in ENGAGEMENT_EDITABLE
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                            stdin={"items": rows, "engagement": {field: "something else"}})
        assert code == 1 and payload["error"] == f"'{field}' is not edited here"
    assert api._state(engagement)["engagement"]["household"] == "Park Family"


def test_edit_household_saves_members_contact_and_link_as_one_event(capsys, demo_root):
    """The household's three editable fields, saved as one recorded event
    carrying exactly what moved - and nothing else is edited here."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - John Park", household="Park Family")
    household_dir = private_household_dir(demo_root, "Park Family")

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": ["John Park", "Maria Park"],
                               "contact": "John & Maria",
                               "link": "https://drive.example/park"})
    assert code == 0, payload
    assert sorted(payload["saved"]["household"]) == ["contact", "link", "members"]
    held = load_household_info(household_dir)
    assert held.members == ("John Park", "Maria Park") and held.contact == "John & Maria"
    assert payload["state"]["household"]["members"] == ["John Park", "Maria Park"]
    assert len(ledger.read_events(household_dir)) == 2

    # Nothing changed, nothing written; and a blank clears.
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": ["John Park", "Maria Park"],
                               "contact": "John & Maria",
                               "link": "https://drive.example/park"})
    assert code == 0 and payload["saved"]["household"] == []
    assert len(ledger.read_events(household_dir)) == 2

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"link": ""})
    assert code == 0 and payload["saved"]["household"] == ["link"]
    assert load_household_info(household_dir).link == ""

    # And a key that is not one of the three is refused by name.
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"name": "Somebody Else"})
    assert code == 1 and "Not a household field: name" in payload["error"]


def test_state_carries_the_household_its_open_years_its_returns_and_the_queue_count(
        capsys, demo_root, tmp_path):
    """The card is drawn from the state and types nothing of its own: the
    household's record, the years still open, its returns, and the one
    queue a person works across it."""
    from tests.samples import build_samples
    from tracker.layout import client_household_dir, private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "members": ["John Park"], "contact": "John",
        "link": "https://drive.example/park", "return_name": "1040 - John Park",
        "form": "1040", "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping",
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    personal = where(demo_root, "1040 - John Park", household="Park Family")
    business = where(demo_root, "1120S - Park Landscaping", household="Park Family")

    samples = tmp_path / "samples"
    build_samples(samples)
    for name in ("vacation photo.bmp", "Mortgage Notes.docx"):
        (inbox_of(personal) / name).write_bytes((samples / name).read_bytes())
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(business))[0] == 0

    state = api._state(personal)
    household = state["household"]
    assert household["name"] == "Park Family"
    assert household["members"] == ["John Park"] and household["contact"] == "John"
    assert household["open_years"] == [default_tax_year()]
    assert [r["path"] for r in household["returns"]] == [str(personal), str(business)]
    assert household["queue"] == sum(
        1 for one in (personal, business)
        for row in read_index(one) if row.decision == NEEDS_REVIEW)
    assert household["queue"] >= 1

    paths = state["paths"]
    assert paths["inbox"] == str(inbox_of(personal))
    assert paths["client_folder"] == str(client_household_dir(demo_root, "Park Family"))
    assert paths["household"] == str(private_household_dir(demo_root, "Park Family"))
    assert paths["originals"] == str(inbox_of(personal).parent / str(default_tax_year()))
    assert "shared" not in paths and "pbc" not in paths


def test_the_scan_command_runs_the_household_pass_and_answers_for_the_return_it_was_asked_about(
        capsys, demo_root, tmp_path):
    """One folder feeds every return of the household, so Run now on one
    return sorts all of it - which is the only honest thing it can do - and
    the reply is about the return that was asked for."""
    from tests.samples import build_samples
    from tests.test_scanner import text_pdf
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park", "form": "1040",
        "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping",
        # A trial balance is a bookkeeping export with no name on it, which
        # is what every catalog's trial-balance row says (decision 128).
        "items": [{"identifier": "B01", "document": "Trial Balance", "min_size_kb": 0,
                   "named": "no", "required_keywords": "trial balance"}]})[0] == 0
    personal = where(demo_root, "1040 - John Park", household="Park Family")
    business = where(demo_root, "1120S - Park Landscaping", household="Park Family")

    samples = tmp_path / "samples"
    build_samples(samples)
    name = f"W-2 John Smith {BASE_YEAR}.pdf"
    (inbox_of(personal) / name).write_bytes((samples / name).read_bytes())
    text_pdf(inbox_of(personal) / "tb.pdf", f"Trial balance as of December 31 {BASE_YEAR}")

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(business))
    assert code == 0, payload

    # The reply is the business return's, and the whole inbox was sorted.
    assert payload["state"]["paths"]["engagement"] == str(business)
    assert payload["run"]["filed"] == 1                       # the trial balance
    assert [row["original_name"] for row in payload["state"]["index"]] == ["tb.pdf"]
    assert [row.original_name for row in read_index(personal)] == [name]
    assert not any(p.suffix == ".pdf" for p in inbox_of(personal).iterdir())


# ---------------- one inbox, the household rollover, the sharing (d126) ----


def a_park_household(capsys, root):
    """Park Family with its three returns for the calendar's default year,
    made through ``create`` exactly as the wizard makes them."""
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John & Maria",
        "link": "https://drive.example/park", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2 Wage Statements",
                   "min_size_kb": 0, "any_keywords": "w-2"}]})[0] == 0
    here = str(private_household_dir(root, "Park Family"))
    for name, row in (("1040 - Sofia Park", "W-2 Wage Statements"),
                      ("1120S - Park Landscaping LLC", "Trial Balance")):
        assert run(capsys, "create", stdin={
            "household_path": here, "return_name": name,
            "items": [{"identifier": "A01", "document": row, "min_size_kb": 0,
                       "any_keywords": "w-2"}]})[0] == 0
    return [where(root, name, household="Park Family") for name in
            ("1040 - John Park", "1040 - Sofia Park", "1120S - Park Landscaping LLC")]


def test_roll_household_returns_the_rolled_and_the_retired_and_the_state_of_the_first_new_return(
    capsys, demo_root,
):
    """One call rolls the household's year: the returns it was given, the
    ones it retired - and the state of the first return it made, which is
    where the app lands. A refusal on any ticked return is the whole call's
    error, naming the return, and nothing is rolled or retired (decision
    159); ``skipped`` stays in the reply and is empty."""
    from tracker.manifest import load_engagement_info

    john, sofia, llc = a_park_household(capsys, demo_root)
    year = default_tax_year() + 1
    # The second plan's target is already there, so the whole roll refuses.
    blocking = where(demo_root, "1040 - Sofia Park", year=year, household="Park Family")
    blocking.mkdir(parents=True)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(llc), stdin={
        "year": year,
        "returns": [{"prior": str(john)}, {"prior": str(sofia)}],
    })
    assert code == 1, payload
    assert payload["error"].startswith("1040 - Sofia Park: ") and "already exists" in payload["error"]
    assert payload["error"].endswith("Nothing was rolled.")
    assert not where(demo_root, "1040 - John Park", year=year, household="Park Family").exists()
    assert load_engagement_info(llc).active is True
    blocking.rmdir()

    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(llc), stdin={
        "year": year,
        "returns": [{"prior": str(john)}, {"prior": str(sofia)}],
    })
    assert code == 0, payload

    assert [one["prior"] for one in payload["rolled"]] == ["1040 - John Park", "1040 - Sofia Park"]
    assert payload["rolled"][0]["label"] == f"Park Family {year} 1040 - John Park"
    assert payload["rolled"][0]["created"] == str(
        where(demo_root, "1040 - John Park", year=year, household="Park Family"))
    assert payload["rolled"][0]["carried"][0]["identifier"] == "A01"
    assert payload["skipped"] == [] and payload["not_retired"] == [] and payload["warning"] == ""
    # The one return nobody ticked is retired, by its label.
    assert payload["retired"] == [f"Park Family {default_tax_year()} 1120S - Park Landscaping LLC"]
    assert load_engagement_info(llc).active is False
    # The state is the first return this call made.
    assert payload["state"]["paths"]["engagement"] == payload["rolled"][0]["created"]
    assert payload["target_year"] == year


def test_roll_household_after_a_failed_retirement_says_what_was_rolled_and_left_open(
    capsys, demo_root, monkeypatch,
):
    """Decision 159, the review's S2. Every ticked return rolled and then a
    retirement failed: the new returns exist, so the reply is not an error.
    It names the return left open and carries the rollover's own sentence,
    which the app shows as its banner, and lands on the first new return."""
    from tracker import rollover
    from tracker.manifest import load_engagement_info

    john, sofia, llc = a_park_household(capsys, demo_root)
    year = default_tax_year() + 1
    real_save = rollover.save_rules

    def llc_fails(folder, *args, **kwargs):
        if folder == llc:
            raise OSError("the disk filled")
        return real_save(folder, *args, **kwargs)

    monkeypatch.setattr(rollover, "save_rules", llc_fails)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(llc), stdin={
        "year": year,
        "returns": [{"prior": str(john)}, {"prior": str(sofia)}],
    })
    assert code == 0, payload
    assert [one["prior"] for one in payload["rolled"]] == ["1040 - John Park", "1040 - Sofia Park"]
    assert payload["retired"] == []
    assert payload["not_retired"] == [f"Park Family {default_tax_year()} 1120S - Park Landscaping LLC"]
    assert payload["warning"].startswith(f"Rolled into {year}: 1040 - John Park, 1040 - Sofia Park.")
    assert "Not retired: 1120S - Park Landscaping LLC (the disk filled)" in payload["warning"]
    assert load_engagement_info(llc).active is True
    assert payload["state"]["paths"]["engagement"] == payload["rolled"][0]["created"]


def test_creating_a_households_first_return_hands_back_the_sharing_checklist_and_a_later_return_does_not(
    capsys, demo_root,
):
    """The two grants are made once, when the household is made (decision
    126). A second return added to it gets no checklist: its inbox was
    shared when the household was, and nothing is ever re-shared."""
    from tracker.layout import client_household_dir, inbox_dir_for, private_household_dir

    code, first = run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2", "min_size_kb": 0,
                   "any_keywords": "w-2"}]})
    assert code == 0, first
    checklist = first["checklist"]
    assert checklist["heading"] == api.SHARING_HEADING
    assert checklist["note"] == api.SHARING_NOTE
    assert str(client_household_dir(demo_root, "Park Family")) in checklist["lines"][0]
    assert "Viewer" in checklist["lines"][0]
    assert str(inbox_dir_for(demo_root, "Park Family")) in checklist["lines"][1]
    assert "Contributor" in checklist["lines"][1]
    assert api.MARK_SHARED_LABEL in checklist["lines"][2]

    code, second = run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1040 - Sofia Park",
        "items": [{"identifier": "A01", "document": "W-2", "min_size_kb": 0,
                   "any_keywords": "w-2"}]})
    assert code == 0, second
    assert "checklist" not in second


def test_mark_shared_refuses_without_a_link_records_one_event_and_the_state_says_the_day(
    capsys, demo_root,
):
    """The firm's word, dated, and nothing else: one event carrying only
    its stamp, folded by nothing. The link is the one part of the
    checklist the tracker can see was done, so it insists on that one."""
    from tracker.households import shared_on
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2", "min_size_kb": 0,
                   "any_keywords": "w-2"}]})[0] == 0
    john = where(demo_root, "1040 - John Park", household="Park Family")
    household = private_household_dir(demo_root, "Park Family")

    code, payload = run(capsys, "mark-shared", api.ENGAGEMENT_FLAG, str(john))
    assert code == 1 and payload["error"] == api.SHARE_LINK_FIRST
    assert shared_on(household) is None

    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(john),
               stdin={"link": "https://drive.example/park"})[0] == 0
    before = len(ledger.read_events(household))
    code, payload = run(capsys, "mark-shared", api.ENGAGEMENT_FLAG, str(john))
    assert code == 0, payload

    today = dt.date.today().isoformat()
    assert payload["shared_on"] == today
    assert payload["state"]["household"]["shared_on"] == today
    # The checklist stops being offered once the word is given.
    assert payload["state"]["household"]["checklist"] is None
    events = ledger.read_events(household)
    assert len(events) == before + 1
    assert events[-1][ledger.EVENT_KEY] == ledger.SHARING_CONFIRMED
    assert set(events[-1]) == {ledger.EVENT_KEY, ledger.AT_KEY} | ledger.LINE_KEYS
    # Folded by nothing: the household reads back exactly as it did.
    assert ledger.replay(events).household == ledger.replay(events[:-1]).household


def test_the_sharing_words_are_the_apis_and_the_renderer_types_none(capsys, demo_root):
    """Every word of the checklist, the two lines about the firm's word and
    the sentence about a return left unticked is Python's; the page shows
    what it is handed and types none of it (decision 126)."""
    from tests.test_single_source import read

    words = api._vocab()["household"]
    assert words["sharing_heading"] == api.SHARING_HEADING
    assert words["sharing_note"] == api.SHARING_NOTE
    assert words["mark_shared"] == api.MARK_SHARED_LABEL
    assert words["shared_on_line"] == api.SHARED_ON_LINE
    assert words["not_yet_shared_line"] == api.NOT_YET_SHARED_LINE
    assert words["rollover_unticked"] == api.ROLLOVER_UNTICKED_NOTE

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    for literal in (*api.SHARING_CHECKLIST, api.SHARING_HEADING, api.SHARING_NOTE,
                    api.MARK_SHARED_LABEL, api.SHARED_ON_LINE, api.NOT_YET_SHARED_LINE,
                    api.SHARE_LINK_FIRST, api.ROLLOVER_UNTICKED_NOTE):
        assert literal not in js, literal
        assert literal not in html, literal


# ------------------------------------------- the name on the page (d128) ----


def test_teaching_a_spelling_from_a_filing_rides_the_filings_transaction_and_a_one_word_spelling_is_refused(
        capsys, demo_root, tmp_path):
    """Decision 128. A filing that teaches a spelling is one decision: the
    row, the move and the return's people are recorded in one transaction,
    exactly as a taught keyword is. A spelling of one word is refused
    before a byte is read - a family name alone would confirm a business -
    and so is a person the return does not list."""
    from tracker.names import ONE_WORD_SPELLING

    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0
    state = api._state(engagement)
    [parked] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW]
    spec = {"original": parked["pbc_location"], "identifier": "A01", "seq": parked["seq"]}

    # One word: refused, and nothing is recorded.
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={**spec, "spelling": {"person": "Jane R. Smith",
                                                    "spelling": "Smith"}})
    assert code == 1 and payload["error"] == ONE_WORD_SPELLING
    # A person the return does not list: refused by name.
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={**spec, "spelling": {"person": "Nobody Here",
                                                    "spelling": "Nobody Here"}})
    assert code == 1 and "Nobody Here is not on this return" in payload["error"]
    assert [e["decision"] for e in api._state(engagement)["index"]] == [NEEDS_REVIEW]

    # And the real thing: one event, in the filing's own transaction.
    before = len(ledger.read_events(engagement))
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={**spec, "spelling": {"person": "Jane R. Smith",
                                                    "spelling": "J. R. Smith"}})
    assert code == 0, payload
    assert payload["assigned"]["spelling"] == "J. R. Smith"
    people = load_engagement_info(engagement).people
    assert "J. R. Smith" in next(p for p in people if p.name == "Jane R. Smith").spellings
    # The filing and the teaching are one decision, so one of the new lines
    # is the row and one is the rules edit - and nothing else.
    added = ledger.read_events(engagement)[before:]
    # The intent, the row and the rules edit - one decision. (The re-scan
    # that follows the filing writes its own `scanned` line, as it always
    # has; the teaching is inside the filing's transaction, not beside it.)
    assert [e[ledger.EVENT_KEY] for e in added if e[ledger.EVENT_KEY] != ledger.SCANNED] == [
        ledger.MOVING, ledger.ASSIGNED_BY_PERSON, ledger.RULES_CHANGED]
    assert next(e for e in added if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED
                )[ledger.INFO_KEY].keys() == {"people"}

    # Teaching the same spelling again is a note, not a second event.
    state = api._state(engagement)
    [again] = [e for e in state["index"] if e["decision"] == NEEDS_REVIEW] or [None]
    assert again is None


def test_create_refuses_a_return_with_no_people_and_the_editor_saves_people_as_one_event(
        capsys, demo_root):
    """A return with nobody on it can never file a named request, so it is
    refused at setup rather than left to park every W-2 that arrives; and
    the people are edited in the one editor, saved in the one event that
    carries every other detail."""
    from tracker.names import NO_PEOPLE, ONE_WORD_SPELLING

    spec = {"return_name": "No People", "form": "1040", "people": [],
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"] == NO_PEOPLE

    code, payload = run(capsys, "create", stdin={
        **spec, "people": [{"kind": "taxpayer", "name": "John Park", "spellings": ["Park"]}]})
    assert code == 1 and payload["error"] == ONE_WORD_SPELLING

    assert run(capsys, "create", stdin={**spec, "people": PEOPLE})[0] == 0
    engagement = where(demo_root, "No People")
    before = len(ledger.read_events(engagement))

    state = api._state(engagement)
    assert state["engagement"]["people"] == list(PEOPLE)
    edited = [*PEOPLE, {"kind": "spouse", "name": "Maria Park",
                        "spellings": ["Maria Park", "Park, Maria"]}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": state["rules"], "engagement": {"people": edited}})
    assert code == 0, payload
    assert payload["saved"]["engagement"] == ["people"]
    assert len(ledger.read_events(engagement)) == before + 1       # one event
    assert [p.name for p in load_engagement_info(engagement).people] == [
        TEST_CLIENT, "Maria Park"]


def test_propose_spellings_is_a_read_and_the_renderer_types_no_kind_label_or_note(
        capsys, demo_root):
    """The twenty-third command proposes and records nothing: what a return
    matches on is what somebody ticked. And every word the People block and
    the card show is the API's - the page types none of them."""
    from tests.test_single_source import read
    from tracker import review
    from tracker.records import PERSON_KIND_LABELS, PERSON_KINDS

    code, payload = run(capsys, "propose-spellings",
                        stdin={"name": "John A. Park", "kind": "taxpayer"})
    assert code == 0
    assert payload == {"spellings": list(propose_spellings("John A. Park", "taxpayer"))}
    assert not list(demo_root.rglob("*_ledger.jsonl"))         # a read: nothing recorded
    assert run(capsys, "propose-spellings", stdin={"name": "x", "kind": "nope"})[0] == 1

    words = run(capsys, "list")[1]["vocab"]["people"]
    assert [k["value"] for k in words["kinds"]] == list(PERSON_KINDS)
    assert [k["label"] for k in words["kinds"]] == [PERSON_KIND_LABELS[k] for k in PERSON_KINDS]

    js = read("app/renderer/app.js")
    html = read("app/renderer/index.html")
    # Every phrase of the block and the card, from its owner. The one-word
    # labels are not pinned here - "Who" and "Name" are English as much as
    # they are labels, and a guard that fails on a comment teaches nobody;
    # the kinds above prove the page reads the list rather than holding one.
    for literal in ("Entity (legal name)", "DBA or abbreviation",
                    "Owner (accounts held so)", "Trust or estate",
                    api.SPELLINGS_LABEL, api.SPELLINGS_HELP, api.ADD_PERSON_LABEL,
                    api.OWN_SPELLING_HINT, api.REVIEW_PEOPLE_LABEL,
                    api.PEOPLE_ROLLED_NOTE, api.TEACH_SPELLING_LABEL,
                    api.TEACH_SPELLING_HINT, words["one_word"], words["none_yet"],
                    review.NAME_CONFIRMED_NOTE, review.NAME_OTHER_NOTE,
                    review.NAME_ABSENT_NOTE):
        assert literal not in js, literal
        assert literal not in html, literal


def test_the_household_card_shows_every_returns_reminder_state(capsys, demo_root):
    """One letter per return, as before - and the household card puts their
    states side by side, in the words the Reminder card already uses, so a
    person can see the household's letters at a glance without a bundle."""
    from tracker import reminder
    from tracker.layout import private_household_dir

    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John", "return_name": "1040 - John Park",
        "form": "1040", "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Park Family")),
        "return_name": "1120S - Park Landscaping", "form": "1120S",
        "items": [{"identifier": "B01", "document": "Trial Balance", "named": "no"}]})[0] == 0
    personal = where(demo_root, "1040 - John Park", household="Park Family")

    returns = api._state(personal)["household"]["returns"]

    assert [one["return_name"] for one in returns] == [
        "1040 - John Park", "1120S - Park Landscaping"]
    for one in returns:
        assert one["reminder"] == {"last": None, "approved": None, "lapsed": False,
                                   "held": 0, "unsorted": 0}
    # The words the card fills those numbers into are the reminder's own.
    words = run(capsys, "list")[1]["vocab"]["reminder"]
    assert words["never_drafted_line"] == reminder.NEVER_DRAFTED_LINE
    assert words["held_line"] == reminder.HELD_SUMMARY


# ============ the household routes: the feed list (decision 129) ===========


def two_households(capsys, root):
    """Park Family with a 1040, Park & Lee LLC with an 1120S, and Park
    Family's drop folder feeding the LLC's return line - made the way the
    app makes them, and extended the way a person extends it."""
    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    assert run(capsys, "create", stdin={
        "household": "Park & Lee LLC", "contact": "John & Sam",
        "return_name": "1120S - Park & Lee LLC",
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    father = where(root, "1040 - John Park", household="Park Family")
    llc = where(root, "1120S - Park & Lee LLC", household="Park & Lee LLC")
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"feeds": [{"household": "Park & Lee LLC",
                                          "return_name": "1120S - Park & Lee LLC"}]})
    assert code == 0, payload
    return father, llc


def test_edit_household_saves_feeds_and_the_state_carries_feeds_and_fed_by_with_the_two_warnings_words(
        capsys, demo_root):
    """The feed list is a household field like the members: saved as one
    recorded event of exactly what moved, resolved for the card into the
    return it names this year, and shown from the other side on the
    household whose return is fed. Both warnings a person reads before
    extending either are the API's words."""
    from tracker.households import load_household_info
    from tracker.layout import private_household_dir
    from tracker.records import Feed

    father, llc = two_households(capsys, demo_root)
    household_dir = private_household_dir(demo_root, "Park Family")
    assert load_household_info(household_dir).feeds == (
        Feed("Park & Lee LLC", "1120S - Park & Lee LLC"),)

    _code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    [feed] = payload["household"]["feeds"]
    assert feed["household"] == "Park & Lee LLC"
    assert feed["return_name"] == "1120S - Park & Lee LLC"
    assert feed["path"] == str(llc) and feed["warning"] == ""
    assert "1120S - Park & Lee LLC" in feed["label"]

    # And from the other side: the household whose return is fed is told
    # whose drop folder feeds it, by household and never by member.
    _code, other = run(capsys, "state", api.ENGAGEMENT_FLAG, str(llc))
    assert [one["name"] for one in other["household"]["fed_by"]] == ["Park Family"]
    assert other["household"]["feeds"] == []

    words = api._vocab()["household"]
    assert words["feed_warning"] == api.FEED_WARNING
    assert words["return_warning"] == api.RETURN_WARNING
    assert "{members}" in words["feed_warning"]

    # A feed the other household has no active return for this year is
    # said rather than resolved to nothing in silence.
    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(father),
               stdin={"feeds": [{"household": "Park & Lee LLC",
                                 "return_name": "1065 - nobody"}]})[0] == 0
    _code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    [gone] = payload["household"]["feeds"]
    assert gone["path"] == "" and "no active return" in gone["warning"]


def test_assign_with_a_target_refuses_an_unfed_return_and_hands_over_to_a_fed_one(
        capsys, demo_root, tmp_path):
    """Nothing routes outside the feed list: a target this drop folder does
    not feed is refused by name, and a target it does feed takes the
    document - the original moving under the household that return lives
    in, and the row here released (decision 132): nothing of it stays."""
    from tracker.layout import originals_of
    father, llc = two_households(capsys, demo_root)
    parked, seq = a_parked_document(capsys, father)

    # A return nobody extended this drop folder to: refused before a byte
    # is read, and the outsider's record is untouched.
    outsider = where(demo_root, "1040 - Sofia Park", household="Sofia Park")
    assert run(capsys, "create", stdin={
        "household": "Sofia Park", "contact": "Sofia", "return_name": "1040 - Sofia Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": parked, "identifier": "A01", "seq": seq,
                               "target": str(outsider)})
    assert code == 1 and payload["error"] == api.NOT_FED.format(label=outsider.name)
    assert read_index(outsider) == []

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": parked, "identifier": "B01", "seq": seq,
                               "target": str(llc)})
    assert code == 0, payload
    assert payload["handed_over"]["moved_original"] is True
    assert payload["handed_over"]["identifier"] == "B01"
    assert read_index(father) == []
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01"
    assert (originals_of(llc) / "notice.pdf").is_file()


def test_run_now_sorts_against_the_feed_list_like_the_scheduled_pass(capsys, demo_root):
    """There is one definition of a pass, and *Run now* is it.

    The button walks the practice and hands it down exactly as the
    scheduled job does, so the same trial balance dropped in the father's
    inbox is judged against the co-owned LLC's list either way - and, since
    decision 204, waits in the father's queue for one click either way,
    rather than parking as a document nothing wants. Without the walk the
    feed list resolves to nothing, which would make the button and the
    schedule disagree about what the household's inbox is for.
    """
    from tests.samples import text_pdf
    from tracker import reasons

    father, llc = two_households(capsys, demo_root)
    text_pdf(inbox_of(father) / "tb.pdf",
             ["Trial balance as of December 31 2025", TEST_CLIENT])

    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(father))

    assert code == 0, payload
    assert read_index(llc) == []                    # the pass files nothing across
    [row] = read_index(father)
    assert row.decision == NEEDS_REVIEW and row.code == reasons.NAMED_ACROSS_HOUSEHOLDS.code
    assert row.waiting_for.identifiers == ("B01",)
    assert payload["run"]["filed"] == 0


def waiting_document(capsys, father):
    """A trial balance naming the LLC's person, dropped in the father's
    inbox and parked by *Run now* for one click (decision 204): its triage
    entry, as the card receives it."""
    from tests.samples import text_pdf

    text_pdf(inbox_of(father) / "tb.pdf", ["Trial balance as of December 31 2025", TEST_CLIENT])
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(father))
    assert code == 0, payload
    [waiting] = payload["state"]["review"]
    return waiting


def test_a_waiting_row_offers_one_click_and_assign_waiting_files_it_with_no_target_from_the_page(
        capsys, demo_root):
    """Decision 204's one click. The card carries what the click will do -
    the return, its label and the requests it files under, as data - and
    the page sends back only the row and its version: ``waiting``, no
    target, no identifier. The API resolves the row's own claim through the
    feed list and hands it over; a second click on the gone row is refused."""
    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    offer = waiting["waits_for"]
    assert offer == {"target": str(llc), "label": "Park & Lee LLC 2025 1120S - Park & Lee LLC",
                     "requests": [{"identifier": "B01", "document": "Trial Balance"}], "answers": []}
    assert waiting["waits_for_refused"] == ""

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["pbc_location"], "seq": waiting["seq"],
                               "waiting": True})

    assert code == 0, payload
    done = payload["handed_over"]
    assert done["identifier"] == "B01" and done["label"] == offer["label"]
    assert done["moved_original"] is True
    assert read_index(father) == [] and payload["state"]["review"] == []
    [taken] = read_index(llc)
    assert taken.decision == FILED and taken.identifier == "B01" and taken.waits_for == ""
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["pbc_location"], "seq": waiting["seq"],
                               "waiting": True})
    assert code == 1


def test_a_waiting_row_whose_feed_was_trimmed_offers_no_click_and_says_not_fed(capsys, demo_root):
    """R-8: a claim that no longer resolves offers nothing. The card says why
    in the words a hand-over is refused with, the click sent anyway is
    refused in them, and the row stays parked for the picker or for filing
    here."""
    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"feeds": []})
    assert code == 0, payload

    _code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))
    [card] = state["review"]
    said = api.NOT_FED.format(label="1120S - Park & Lee LLC")
    assert card["waits_for"] is None and card["waits_for_refused"] == said

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"original": waiting["pbc_location"], "seq": card["seq"],
                               "waiting": True})
    assert code == 1 and payload["error"] == said
    assert [row.decision for row in read_index(father)] == [NEEDS_REVIEW]
    assert read_index(llc) == []


def test_a_claim_is_offered_only_on_the_row_the_click_would_take(capsys, demo_root):
    """The review's S-3: the card offers the click on exactly the rows the
    filer's refusal lets through - still parked, with the named-across
    reason. The same claim on a row a person set aside, or under any other
    reason, draws no button and no sentence."""
    from dataclasses import replace

    father, llc = two_households(capsys, demo_root)
    waiting = waiting_document(capsys, father)
    [row] = read_index(father)
    fed = lambda: {llc: "Park & Lee LLC 2025 1120S - Park & Lee LLC"}  # noqa: E731
    offer, _said = api._waiting_payload(father, row, fed)
    assert offer == waiting["waits_for"]
    for other in (replace(row, decision="Not Requested"), replace(row, reason="a reason of its own")):
        assert api._waiting_payload(father, other, fed) == (None, "")


def test_a_waiting_row_whose_return_has_no_room_offers_no_click_and_says_so_in_that_returns_words(
        capsys, demo_root, monkeypatch):
    """The review's S-1: a click bound to fail on the taking return's room is
    not offered. The card says why in the sentence the click would be
    refused with, naming that return - never "this request's Short name"."""
    import tracker.filer as filer_module

    father, llc = two_households(capsys, demo_root)
    waiting_document(capsys, father)
    monkeypatch.setattr(filer_module, "limit_for", lambda _extension: 10)

    _code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))

    [card] = state["review"]
    assert card["waits_for"] is None
    said = card["waits_for_refused"]
    assert said.startswith("the working copy's path in Park & Lee LLC 2025 1120S - Park & Lee LLC")
    assert "this request" not in said


def a_parked_document(capsys, engagement):
    """One document nothing asks for, dropped in the household's inbox and
    left waiting for a person by a pass - the row a hand-over acts on, with
    the record version the card would have carried out (decision 112)."""
    from tests.samples import text_pdf

    text_pdf(inbox_of(engagement) / "notice.pdf", ["an agency notice nothing asks for"])
    _code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    [row] = [e for e in payload["state"]["index"]
             if e["decision"] == NEEDS_REVIEW]
    return row["pbc_location"], row["seq"]


def test_the_renderer_types_none_of_the_feed_words(capsys, demo_root):
    """Every word the feed list shows is the API's - what a drop folder
    also feeds, who feeds it, the word that adds one, the two warnings and
    the answer that files a document under another return - so the app
    cannot disagree with the tracker about any of them."""
    here = Path(__file__).resolve().parents[1]
    js = (here / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    html = (here / "app" / "renderer" / "index.html").read_text(encoding="utf-8")
    for word in (api.FEEDS_LABEL, api.FEEDS_HELP, api.FEEDS_LINE, api.FED_BY_LINE,
                 api.ADD_FEED_LABEL, api.FEED_WARNING, api.RETURN_WARNING,
                 api.HAND_OVER_LABEL, api.HAND_OVER_RETURN_LABEL, api.HAND_OVER_REQUEST_LABEL,
                 api.NOBODY_TYPED, api.NOT_FED, api.HANDED_OVER_LINE,
                 api.FILE_WHERE_IT_WAITS_LABEL):
        assert f'"{word}"' not in js and f"'{word}'" not in js, word
        assert word not in html, word
    words = api._vocab()
    assert words["household"]["feeds_line"] == api.FEEDS_LINE
    assert words["household"]["fed_by_line"] == api.FED_BY_LINE
    assert words["household"]["add_feed"] == api.ADD_FEED_LABEL
    assert words["household"]["nobody_typed"] == api.NOBODY_TYPED
    assert words["review_labels"]["hand_over"] == api.HAND_OVER_LABEL
    # The two boxes of the hand-over have their own words since Fable's
    # review of decision 129: the page borrowed the household heading and
    # the editor's title, which read nearly right and would have drifted
    # the moment either was reworded for its own screen.
    assert words["review_labels"]["hand_over_return"] == api.HAND_OVER_RETURN_LABEL
    assert words["review_labels"]["hand_over_request"] == api.HAND_OVER_REQUEST_LABEL
    # And what the page says once a document has gone (decision 132): the
    # row here is released, in the API's words, filled with the reply's
    # label and request.
    assert words["review_labels"]["handed_over"] == api.HANDED_OVER_LINE
    assert "vocab.review_labels.handed_over" in js
    # And decision 204's one click, labelled by the API and filled by the
    # page with the label the card carries.
    assert words["review_labels"]["file_where_it_waits"] == api.FILE_WHERE_IT_WAITS_LABEL
    assert "vocab.review_labels.file_where_it_waits" in js


def test_a_pass_cannot_be_run_without_the_practice(capsys, demo_root, monkeypatch):
    """*Run now* on a root that cannot be walked is refused in the runner's
    one sentence, which is the run's ``error`` in the reply - and nothing
    is sorted (decision 132). Before, the pass fed nothing in silence and
    the button and the schedule could disagree about what the inbox was
    for."""
    from tests.samples import text_pdf
    from tracker.registry import RegistryError
    from tracker.runner import NO_PRACTICE

    father, _llc = two_households(capsys, demo_root)
    text_pdf(inbox_of(father) / "tb.pdf", ["Trial balance as of December 31 2025", TEST_CLIENT])

    def unwalkable(root):
        raise RegistryError(f"{root} cannot be walked")

    monkeypatch.setattr(api, "discover_engagements", unwalkable)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(father))

    assert code == 0, payload
    assert payload["run"]["error"] == NO_PRACTICE
    assert payload["run"]["filed"] == 0
    assert (inbox_of(father) / "tb.pdf").is_file()      # nothing was sorted
    assert read_index(father) == []


# ============== what we have received, at once (decision 130) =============
#
# A person's action in the app changes the index between passes, so the
# action refreshes the client README itself: the list is never behind the
# record once an action has run.


def client_readme(engagement) -> str:
    from tracker.scaffold import README_NAME

    return (inbox_of(engagement) / README_NAME).read_text(encoding="utf-8")


def test_filing_a_parked_card_moves_it_from_under_review_to_received_at_once(
        capsys, demo_root, tmp_path):
    from tracker.scaffold import RECEIVED_HEADING, UNDER_REVIEW_HEADING

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    before = client_readme(engagement)
    assert UNDER_REVIEW_HEADING in before and "  1 document received " in before
    d01 = next(i for i in payload["state"]["items"] if i["identifier"] == "D01")
    d01_label = next(item.label for item in load_manifest(engagement) if item.identifier == "D01")
    assert f"  {d01_label}  Received" not in before

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": d01["identifier"],
                               "seq": parked["seq"]})
    assert code == 0, payload

    after = client_readme(engagement)
    assert RECEIVED_HEADING in after
    assert f"  {d01_label}  Received" in after
    assert UNDER_REVIEW_HEADING not in after
    assert "Mortgage Notes" not in after


def test_unfiling_moves_it_back_to_under_review_at_once(capsys, demo_root, tmp_path):
    from tracker.scaffold import UNDER_REVIEW_HEADING

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    label = next(item.label for item in load_manifest(engagement)
                 if item.identifier == filed["identifier"])
    before = client_readme(engagement)
    assert f"  {label}  Received" in before and UNDER_REVIEW_HEADING not in before

    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "seq": filed["seq"]})
    assert code == 0, payload

    after = client_readme(engagement)
    assert f"  {label}  Received" not in after
    assert UNDER_REVIEW_HEADING in after and "  1 document received " in after
    assert filed["original_name"] not in after
# ------------------------------------ decision 131: the room a return has ----


#: How far past the limit ``_a_long_row_return``'s second row's canonical
#: copy is: less than the thirty-six characters a two-character document
#: gives back, so shortening the other row's label is a save that fits.
LONG_ROW_OVER = 10


#: How long :func:`_a_deeper_root` makes the clients root, in characters,
#: whatever the machine's temporary folder spends of it: deep enough that a
#: return of two names at the longest may pass Windows's limit, and shallow
#: enough that a plain return keeps :data:`FITS_MARGIN` to spare.
DEEPER_ROOT_LENGTH = 108
#: What the plain return under that root keeps below the tightest limit
#: that applies to its copies (Excel's, for a spreadsheet), at the least.
FITS_MARGIN = 20


def _a_deeper_root(demo_root):
    """A clients root one long folder below the suite's short one, recorded
    as the app records it. Since decision 188 a name is at most eighty
    characters, so under the short root no return's path can pass what
    Windows will open; a root this deep is where a root that grew leaves
    the firm."""
    from tracker.settings import set_clients_root

    # The same length on every machine, from the real temporary folder: a
    # Windows runner's is longer than Linux's, and a fixed pad left the
    # "fits" return below one character short of Excel's 218 there.
    pad = DEEPER_ROOT_LENGTH - len(str(demo_root / "Clients root "))
    if pad < 1:
        pytest.skip(f"{demo_root} is too long to make a root of {DEEPER_ROOT_LENGTH} characters")
    deeper = demo_root / ("Clients root " + "d" * pad)
    deeper.mkdir()
    set_clients_root(deeper)
    return deeper


def _a_long_row_return(root, household=HOUSEHOLD):
    """A return made the way a test makes one - past creation's refusal - whose
    second row's canonical copy no longer fits under ``root``: the state a
    root that grew leaves behind.

    Its return name is padded so the return folder leaves the second row's
    canonical copy exactly ``LONG_ROW_OVER`` past the limit: since decision
    144 a row's name in the path is its short name - twenty characters at
    most - so the depth is the folder's, as it is when a root grows, not a
    hundred-character label's. Since decision 168 the copy sits in
    Prepared itself, so the depth below the return is one name, not a
    folder and a name."""
    from tests.conftest import TEST_YEAR
    from tracker.layout import MAX_PATH_LENGTH, NAME_MAX_CHARS
    from tracker.manifest import RequestItem

    below = len("/Prepared/B01 - " + "y" * 20 + ".pdf")
    above = len(str(return_dir_for(Path(root), household, TEST_YEAR, "x"))) - len("x")
    pad = MAX_PATH_LENGTH + LONG_ROW_OVER - below - above - len("1040 - Long ")
    if pad < 1:
        pytest.skip(f"{root} is too long to make the long-row return under it")
    # A name is at most NAME_MAX_CHARS (decision 188): what the return's
    # name cannot hold pads the household's.
    in_return = min(pad, NAME_MAX_CHARS - len("1040 - Long "))
    if pad > in_return:
        household = household + "h" * (pad - in_return)
        if len(household) > NAME_MAX_CHARS:
            pytest.skip(f"{root} is too short to make the long-row return under it")
    return_name = "1040 - Long " + "g" * in_return
    engagement = make_engagement(root, [
        RequestItem(identifier="A01", document="W-2", allowed_extensions=("pdf",)),
        RequestItem(identifier="B01", document="y" * 100, allowed_extensions=("pdf",)),
    ], household=household, return_name=return_name)
    assert len(str(engagement)) + below == MAX_PATH_LENGTH + LONG_ROW_OVER
    return engagement


def test_set_root_answers_with_every_return_short_of_room_under_the_new_root(
    capsys, tmp_path, monkeypatch,
):
    """Setting the root is the one moment every move passes through, so its
    reply names every return short of room under the new root, with its
    numbers, in label order - and records the root regardless."""
    from tests.conftest import TEST_YEAR
    from tracker.filer import ROOM_SHORT, room_for
    from tracker.manifest import RequestItem
    from tracker.settings import ENV_SETTINGS_DIR, clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    root = tmp_path / "Clients"
    fits = make_engagement(root, [RequestItem(identifier="A01", document="W-2")],
                           return_name="1040 - Fits")
    short = _a_long_row_return(root)
    room = room_for(short, load_manifest(short))
    assert room.short > 0 and room_for(fits, load_manifest(fits)).short == 0

    code, payload = run(capsys, "set-root", stdin={"root": str(root)})

    assert code == 0, payload
    assert clients_root() == root.resolve()
    [entry] = payload["short_of_room"]
    assert entry["engagement"] == f"{short.parent.parent.name} {TEST_YEAR} {short.name}"
    assert entry["short"] == room.short and entry["parks"] == room.parks
    assert entry["sentences"][0] == ROOM_SHORT.format(short=room.short)


def test_state_carries_the_returns_room_as_information_and_warns_only_what_cannot_receive(
    capsys, demo_root,
):
    """A person opening a return sees its room without waiting for a pass:
    the six numbers, and the figure it is short by as a note on the
    return's page - **not** among the warnings (the lead's L-1: its names
    are cut to fit and everything files). Only requests that cannot
    receive at all are a warning."""
    from tracker.filer import ROOM_PARKS, ROOM_SHORT, room_for
    from tracker.manifest import RequestItem

    root = _a_deeper_root(demo_root)
    engagement = _a_long_row_return(root)
    room = room_for(engagement, load_manifest(engagement))

    state = payload_of_state(capsys, engagement)

    assert state["room"] == {"need": room.need, "least": room.least, "floor": room.floor,
                             "short": room.short, "parks": room.parks, "limit": 260}
    assert room.short > 0
    assert state["room_note"] == ROOM_SHORT.format(short=room.short)
    assert ROOM_SHORT.format(short=room.short) not in state["warnings"]
    assert (ROOM_PARKS.format(count=room.parks) in state["warnings"]) == bool(room.parks)
    assert run(capsys, "list")[1]["vocab"]["room"]["short"] == ROOM_SHORT

    # A return with room: no note at all. It keeps FITS_MARGIN to spare
    # below the tightest limit its copies meet, measured, on any machine.
    from tracker.filer import _extensions_of, prepared_name_for
    from tracker.layout import PREPARED_DIR_NAME, limit_for

    fits = make_engagement(root, [RequestItem(identifier="A01", document="W-2")],
                           return_name="1040 - Fits")
    [item] = load_manifest(fits)
    spare = min(limit_for(ext) - len(str(fits / PREPARED_DIR_NAME / prepared_name_for(item, ext, set())))
                for ext in _extensions_of(item))
    assert spare >= FITS_MARGIN, spare
    assert room_for(fits, load_manifest(fits)).short == 0
    assert payload_of_state(capsys, fits)["room_note"] == ""


def test_saving_a_list_refuses_a_changed_row_whose_path_would_pass_the_limit_and_leaves_an_unchanged_one_alone(
    capsys, demo_root,
):
    """The editor's save keeps creation's standard for the rows it changes:
    a hundred-character label typed into one row - named in the path by its
    twenty-character short name since decision 144 - is refused with
    creation's sentence and nothing is recorded; a row already past the
    limit that the person did not touch never traps a save that shortens
    another."""
    from tracker.layout import PATH_TOO_LONG

    engagement = _a_long_row_return(_a_deeper_root(demo_root))
    rows = payload_of_state(capsys, engagement)["rules"]
    by_id = {row["identifier"]: row for row in rows}

    before = ledger.path_for(engagement).read_bytes()
    typed = [{**by_id["A01"], "document": "z" * 100}, by_id["B01"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": typed, "engagement": {}})
    assert code == 1
    assert payload["error"].startswith(PATH_TOO_LONG.split("{")[0])
    assert "shorten the household or the return name" in payload["error"]
    assert ledger.path_for(engagement).read_bytes() == before

    shortened = [{**by_id["A01"], "document": "W2"}, by_id["B01"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": shortened, "engagement": {}})
    assert code == 0, payload
    assert payload["saved"]["changed"] == ["A01"]


def test_a_persons_filing_and_the_hand_over_are_named_to_fit_and_refuse_only_below_the_floor(
    capsys, tmp_path, monkeypatch,
):
    """The API half: a person's filing into a request with no room for even
    its shortest name comes back as the one error sentence, PATH_NO_ROOM,
    and nothing has moved. Since decision 168 Prepared is the only folder
    a copy is in, and it is shallower than the review folder, so a request
    is left no room only by a period as long as ``Jan 2025 - Dec 2025``."""
    from tests.conftest import named_page, root_for_a_return_of, sort
    from tests.test_scanner import text_pdf
    from tracker.filer import PATH_NO_ROOM
    from tracker.manifest import RequestItem
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    root = root_for_a_return_of(tmp_path, 222)             # Prepared: 231, 28 left for a name
    engagement = make_engagement(root, [RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="Jan 2025 - Dec 2025",
        date_pattern=r"(?i)\b2025\b", allowed_extensions=("pdf",), required_keywords=("W-2",))])
    set_clients_root(root)
    text_pdf(inbox_of(engagement) / "note.pdf", named_page("A letter the list does not ask for"))
    sort(engagement)
    [parked] = [e for e in read_index(engagement) if e.decision == NEEDS_REVIEW]
    seq = next(row["seq"] for row in payload_of_state(capsys, engagement)["index"]
               if row["original_name"] == "note.pdf")
    before = sorted(str(p) for p in root.rglob("*"))

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked.pbc_location, "identifier": "A01", "seq": seq})

    assert code == 1
    assert payload["error"] == PATH_NO_ROOM.format(
        length=231 + 1 + len("A01 - Jan 2025 - Dec 2025.pdf"), limit=260, ext=".pdf")
    assert sorted(str(p) for p in root.rglob("*")) == before


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
    assert payload["error"] == api.HOUSEHOLD_NOT_OURS.format(name="Old Smith")
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
    assert code == 1 and payload["error"] == api.UNEXPECTED_ERROR.format(error="OSError")
    assert not new_year.exists()
    # A second return in the year it did have: the year stays.
    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Smith Trust"})
    assert code == 1 and payload["error"] == api.UNEXPECTED_ERROR.format(error="OSError")
    assert prior.parent.is_dir() and not where(demo_root, "Smith Trust").exists()
    # A rollover into a new year: the same.
    code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
    assert code == 1 and payload["error"] == api.UNEXPECTED_ERROR.format(error="OSError")
    assert not new_year.exists()
    # A new household: it goes, and the private tree it sat in - which was
    # already there - stays.
    code, payload = run(capsys, "create", stdin={**spec, "household": "New Family"})
    assert code == 1 and payload["error"] == api.UNEXPECTED_ERROR.format(error="OSError")
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
    body = js.split("function el(", 1)[1].split("\n}\n", 1)[0]
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
    assert code == 1 and payload["error"] == api.UNEXPECTED_ERROR.format(error="OSError")
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


# --------------------------------------------- decision 142: accepted, not asked ----


def test_the_wizard_sends_every_catalog_row_and_the_tick_is_asked(capsys, demo_root):
    """The wizard sends the whole catalog, each row carrying its tick as
    ``asked``, and the custom rows asked; a list with no asked row is
    refused and nothing is made."""
    catalog = [{**t, "asked": bool(t["core"])} for t in api.FORM_TEMPLATES["1040"]]
    ticked = {t["identifier"] for t in catalog if t["asked"]}
    assert len(ticked) == 5
    custom = {"identifier": "X01", "document": "Home office log", "required_keywords": "home office"}
    spec = {"household": HOUSEHOLD, "return_name": "Everything", "form": "1040",
            "items": [*catalog, custom]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload

    rules = {row["identifier"]: row for row in payload["state"]["rules"]}
    assert set(rules) == {t["identifier"] for t in catalog} | {"X01"}
    assert {i for i, row in rules.items() if row["asked"]} == ticked | {"X01"}
    assert payload["state"]["summary"]["total"] == 6
    assert payload["state"]["summary"]["not_asked"] == len(catalog) - 5

    nothing = {"household": HOUSEHOLD, "return_name": "Nothing Asked", "form": "1040",
               "items": [{**t, "asked": False} for t in api.FORM_TEMPLATES["1040"]]}
    code, payload = run(capsys, "create", stdin=nothing)
    assert code == 1 and payload["error"] == "Select at least one request item"
    assert not where(demo_root, "Nothing Asked").exists()


def test_creation_measures_the_room_of_asked_rows_only(capsys, tmp_path, monkeypatch):
    """A return whose longest *unasked* label would not fit is created: the
    catalog's longest label must not refuse a return the preparer never
    asked it of. The same row asked is refused, as ever. A document for the
    unasked row is measured where it is written - cut to fit, or parked
    with decision 131's sentence. Since decision 144 a label in the path is
    a short name of twenty characters at most, and since decision 168 it is
    in the path once, so the room is the return folder's: 212 characters
    here (205 while each request had a folder)."""
    from tests.conftest import named_page, root_for_a_return_of, sort
    from tests.test_scanner import text_pdf
    from tracker.layout import PATH_TOO_LONG
    from tracker.scaffold import PREPARED_DIR_NAME
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    root = root_for_a_return_of(tmp_path, 212, return_name="Tight")
    root.mkdir(parents=True)
    set_clients_root(root)
    w2 = {"identifier": "A01", "document": "W-2", "period": "TY2025",
          "extensions": "pdf", "required_keywords": "W-2", "min_size_kb": 0}
    long_row = {"identifier": "Z99", "document": "Zebra Ledger " + "x" * 90, "period": "TY2025",
                "short_title": "Zebra Ledger Details", "extensions": "pdf",
                "required_keywords": "zebra ledger", "min_size_kb": 0}

    code, payload = run(capsys, "create", stdin={"return_name": "Tight", "year": 2025,
                                                 "items": [w2, {**long_row, "asked": True}]})
    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0])

    code, payload = run(capsys, "create", stdin={"return_name": "Tight", "year": 2025,
                                                 "items": [w2, {**long_row, "asked": False}]})
    assert code == 0, payload
    engagement = where(root, "Tight", year=2025)
    assert len(str(engagement)) == 212

    text_pdf(inbox_of(engagement) / "zebra.pdf", named_page("Zebra ledger for 2025"))
    report = sort(engagement)
    # Prepared leaves the name thirty-eight characters: the short name is
    # cut from its end, and the copy keeps its identifier, its period and
    # its extension (test_filer's decision-131 claims). Until decision 168
    # the row's own folder took the room and the short name went whole.
    [filed] = report.filed
    assert filed.prepared_location == f"{PREPARED_DIR_NAME}/Z99 - Zebra Ledger Detail - TY2025.pdf"
    assert len(str(engagement)) + 1 + len(filed.prepared_location) <= 260


def test_the_editor_round_trips_asked_and_named(capsys, demo_root):
    """The rows the renderer's ``editorRow`` builds from ``state.rules``,
    saved untouched, change nothing and record nothing - a ``named=no`` row
    and a not-asked row included (the editor dropped ``named`` until
    decision 142, so every save turned it to yes)."""
    spec = {"household": HOUSEHOLD, "return_name": "Round Trip", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "D01", "document": "Donation receipts", "any_keywords": "donation receipt",
         "named": "no"},
        {"identifier": "E01", "document": "1099-R", "any_keywords": "1099-r", "asked": False},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Round Trip")
    state = payload_of_state(capsys, engagement)
    vocab = run(capsys, "list")[1]["vocab"]
    editor = vocab["editor"]
    assert editor["yes_no_fields"] == ["named", "asked"]

    def editor_row(rule):          # app.js editorRow, key for key
        return {
            "identifier": rule["identifier"], "document": rule["document"], "period": rule["period"],
            "expected_count": rule["expected_count"],
            "allowed_extensions": ", ".join(rule["allowed_extensions"]) or editor["any_extension"],
            "min_size_kb": rule["min_size_kb"],
            "required_keywords": ", ".join(rule["required_keywords"]),
            "any_keywords": ", ".join(rule["any_keywords"]),
            "date_pattern": "" if rule["date_pattern_derived"] else (
                rule["date_pattern"] or editor["no_date_check"]),
            "manual_override": rule["manual_override"],
            "override_reason": rule["override_reason"] or "",
            "named": editor["no"] if rule["named"] is False else editor["yes"],
            "asked": editor["no"] if rule["asked"] is False else editor["yes"],
        }

    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [editor_row(r) for r in state["rules"]], "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False, payload
    assert ledger.path_for(engagement).read_bytes() == before
    rules = {r["identifier"]: r for r in payload["state"]["rules"]}
    assert rules["D01"]["named"] is False and rules["E01"]["asked"] is False

    # Asking for it is flipping the pick and saving: one rules_changed.
    flipped = [{**editor_row(r), "asked": editor["yes"]} if r["identifier"] == "E01" else editor_row(r)
               for r in state["rules"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": flipped, "engagement": {}})
    assert code == 0 and payload["saved"]["changed"] == ["E01"]

    js = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    assert 'named: rule.named === false ? vocab.editor.no : vocab.editor.yes' in js
    assert 'asked: rule.asked === false ? vocab.editor.no : vocab.editor.yes' in js
    assert "vocab.editor.yes_no_fields.includes(key)" in js


def test_the_apps_request_table_folds_not_asked_rows_with_no_document_into_a_closed_group(capsys, demo_root):
    """The designer's ruling on the 142 build, the app's half: every state
    item says whether a document is in it and whether it folds, by the one
    rule the Status Report uses - only a row nobody asked for with no
    document at all folds - and the request table draws those rows in a
    closed "Not asked (N)" group headed in the API's words; the editor
    regroups a row live on the same fact."""
    from tests.conftest import seed_statuses
    from tracker.manifest import Status, StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": "Folded", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "B01", "document": "SSA-1099", "required_keywords": "ssa-1099", "asked": False},
        {"identifier": "B02", "document": "W-2G", "required_keywords": "w-2g", "asked": False},
        {"identifier": "B03", "document": "1099-C", "required_keywords": "1099-c", "asked": False},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Folded")
    seed_statuses(engagement, {
        "B01": StatusUpdate(status=Status.RECEIVED, file_count=1),
        "B02": StatusUpdate(status=Status.FAILED, file_count=0, validation_notes="w2g.pdf: refused"),
        "B03": StatusUpdate(status=Status.MISSING, file_count=0),
    })
    items = {i["identifier"]: i for i in payload_of_state(capsys, engagement)["items"]}

    assert {i: (one["has_document"], one["not_asked_idle"]) for i, one in items.items()} == {
        "A01": (False, False), "B01": (True, False), "B02": (True, False), "B03": (False, True)}

    here = Path(__file__).resolve().parent.parent / "app" / "renderer"
    js = (here / "app.js").read_text(encoding="utf-8")
    html = (here / "index.html").read_text(encoding="utf-8")
    assert 'show("rows", state.items.filter((item) => !item.not_asked_idle).map(requestTableRow));' in js
    assert 'show("rows-not-asked", idle.map(requestTableRow));' in js
    assert "fill(vocab.editor.not_asked_heading, { n: idle.length })" in js
    assert "known && known.has_document" in js
    group = html[html.index('<details id="rows-not-asked-group"'):]
    group = group[:group.index(">") + 1]
    assert " open" not in group                                  # closed until a person opens it



def test_the_editor_refuses_a_list_nobody_is_asked_for_in_creations_words(capsys, demo_root):
    """Decision 142's review, R6: a return always asks for at least one
    thing. The editor's save of a list with no asked row is refused with
    creation's own sentence, and nothing is recorded."""
    spec = {"household": HOUSEHOLD, "return_name": "Asks Something", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "B01", "document": "1099-R", "required_keywords": "1099-r", "asked": False},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Asks Something")
    rows = payload_of_state(capsys, engagement)["rules"]
    before = ledger.path_for(engagement).read_bytes()

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [{**row, "asked": False} for row in rows], "engagement": {}})
    assert code == 1 and payload["error"] == api.NOTHING_ASKED
    assert ledger.path_for(engagement).read_bytes() == before

    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Asks Nothing", "items": [
        {**one, "asked": False} for one in spec["items"]]})
    assert code == 1 and payload["error"] == api.NOTHING_ASKED


def test_the_returning_client_page_picks_the_returns_recorded_form_by_default(capsys, demo_root):
    """Decision 142's review, R2: each prior carries the catalog it was cut
    from, and the page's template pick defaults to it, so the catalog rows
    the return never had arrive as not asked without anybody choosing; a
    return that recorded no form defaults to no template."""
    spec = {"household": HOUSEHOLD, "return_name": "Recorded", "form": "1040",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    [prior] = run(capsys, "priors")[1]["priors"]
    assert prior["form"] == "1040"

    js = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    assert "selected: f.id === p.form" in js
    assert "selected: !forms.some((f) => f.id === p.form)" in js


# ------------------------------------------------ decision 144: short names ----


def _editor_rows_by_the_app(rules, vocab, tmp_path):
    """``editorRow`` exactly as ``app.js`` spells it, run by node over
    ``rules``; where node is not on PATH, the line that carries the short
    name is held by its source instead, and the rows are built key for key
    as the function builds them."""
    import re
    import shutil
    import subprocess

    js = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(encoding="utf-8")
    start = js.index("function editorRow(rule) {")
    depth, end = 0, None
    for at in range(js.index("{", start), len(js)):
        depth += {"{": 1, "}": -1}.get(js[at], 0)
        if depth == 0:
            end = at + 1
            break
    source = js[start:end]
    assert re.search(r'^\s+short_title: rule\.short_title \|\| "",$', source, flags=re.MULTILINE)
    node = shutil.which("node")
    if node is None:
        editor = vocab["editor"]
        return [{**{k: rule[k] for k in ("identifier", "document", "period", "expected_count",
                                         "min_size_kb", "manual_override")},
                 "allowed_extensions": ", ".join(rule["allowed_extensions"]) or editor["any_extension"],
                 "required_keywords": ", ".join(rule["required_keywords"]),
                 "any_keywords": ", ".join(rule["any_keywords"]),
                 "date_pattern": "" if rule["date_pattern_derived"] else (
                     rule["date_pattern"] or editor["no_date_check"]),
                 "override_reason": rule["override_reason"] or "",
                 "named": editor["no"] if rule["named"] is False else editor["yes"],
                 "asked": editor["no"] if rule["asked"] is False else editor["yes"],
                 "short_title": rule["short_title"] or ""} for rule in rules]
    script = tmp_path / "editor_row.js"
    script.write_text("const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
                      "const vocab = input.vocab;\n" + source + "\n"
                      "process.stdout.write(JSON.stringify(input.rules.map(editorRow)));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(script)], input=json.dumps({"vocab": vocab, "rules": rules}),
                          capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_short_title_round_trips_through_the_editor_and_the_rollover(capsys, demo_root, tmp_path):
    """Decision 144, claim 5 - the lesson of 142's ``named`` defects, where
    the editor and the rollover each rebuilt a row by hand and dropped a
    column. The short name comes back from ``state``, goes through the
    app's real ``editorRow`` and a save untouched with nothing recorded, is
    changed by one edit of one row, and is carried by the rollover: a typed
    one as typed, a blank one on a catalog row filled from the catalog, a
    blank one on a row a person renamed left blank, to derive its own."""
    from tracker.rollover import roll_forward
    from tracker.templates import FORM_TEMPLATES, template_items

    catalog_w2 = {**FORM_TEMPLATES["1040"][0], "asked": True}
    spec = {"household": HOUSEHOLD, "return_name": "Short Names", "year": 2025, "items": [
        catalog_w2,
        {"identifier": "D01", "document": "Donation receipts", "any_keywords": "donation receipt",
         "short_title": "Donations", "period": "TY2025"},
        {"identifier": "E01", "document": "My own brokerage statements", "any_keywords": "brokerage",
         "period": "TY2025"},
        {"identifier": "X01", "document": "Schedule K-1 - ABC Partners LLC", "any_keywords": "abc partners",
         "period": "TY2025"},
    ]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    engagement = where(demo_root, "Short Names", year=2025)
    state = payload_of_state(capsys, engagement)
    assert {r["identifier"]: r["short_title"] for r in state["rules"]} == {
        "A01": "W-2", "D01": "Donations", "E01": "", "X01": ""}
    assert {i["identifier"]: i["short_name"] for i in state["items"]} == {
        "A01": "W-2", "D01": "Donations", "E01": "My own brokerage", "X01": "K-1 ABC Partners LLC"}
    vocab = run(capsys, "list")[1]["vocab"]
    assert {"key": "short_title", "label": "Short name"}.items() <= next(
        c for c in vocab["columns"] if c["key"] == "short_title").items()

    rows = _editor_rows_by_the_app(state["rules"], vocab, tmp_path)
    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False, payload
    assert ledger.path_for(engagement).read_bytes() == before

    # One row's short name changed, and the catalog row's cleared: one event.
    changed = [{**row, "short_title": {"D01": "Gifts", "A01": ""}.get(row["identifier"], row["short_title"])}
               for row in rows]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": changed, "engagement": {}})
    assert code == 0 and sorted(payload["saved"]["changed"]) == ["A01", "D01"], payload
    assert {r["identifier"]: r["short_title"] for r in payload["state"]["rules"]} == {
        "A01": "", "D01": "Gifts", "E01": "", "X01": ""}
    # A name no folder can have is refused with the column named.
    bad = [{**row, "short_title": "x" * 21} if row["identifier"] == "D01" else row for row in changed]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": bad, "engagement": {}})
    assert code == 1 and "Short name may have at most 20 characters" in payload["error"]

    rolled = {r.item.identifier: r.item for r in roll_forward(
        engagement, template=template_items("1040", year=2025)).rolled}
    assert rolled["A01"].short_title == "W-2"            # a blank, filled from the catalog's own row
    assert rolled["D01"].short_title == "Gifts"          # typed, carried
    assert rolled["E01"].short_title == ""               # renamed by a person: derives its own
    assert rolled["X01"].short_title == ""


# ------------------------------------------------- decision 160: a save keeps ----


def _rows_of(state) -> list[dict]:
    """The rows the editor would send back for ``state``, untouched."""
    return [dict(rule) for rule in state["rules"]]


def _waiting_in(readme: str) -> str:
    """The README's *REQUESTED, NOT YET RECEIVED* section alone."""
    from tracker.scaffold import README_HEADING, RECEIVED_HEADING

    if README_HEADING not in readme:
        return ""
    return readme.split(README_HEADING, 1)[1].split(RECEIVED_HEADING, 1)[0]


def test_a_save_from_a_stale_list_is_refused(capsys, demo_root):
    """Two windows open the editor; the second saves; the first's save,
    made from the list as it was, is refused and records nothing (decision
    160, the audit's B-4). It used to remove the row the second added,
    clear the due date and drop the spelling it taught. A save with no
    version is refused too; a pass run while the editor is open is not a
    change of the list and refuses nothing."""
    from tracker.manifest import LIST_MOVED, NO_LIST_HEAD

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "B01", "document": "1099-INT", "required_keywords": "1099-INT"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    first = payload_of_state(capsys, engagement)
    second = payload_of_state(capsys, engagement)
    assert first["list_head"] == second["list_head"] != ""

    people = [{**person, "spellings": [*person["spellings"], "T CLIENT"]}
              for person in second["engagement"]["people"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": _rows_of(second) + [{"identifier": "F02", "document": "K-1 Example Partners",
                                      "required_keywords": "Schedule K-1"}],
        "engagement": {"due": "2026-03-15", "people": people}, "head": second["list_head"]})
    assert code == 0 and payload["saved"]["changed"] == ["F02"], payload

    before = ledger.path_for(engagement).read_bytes()
    stale = _rows_of(first)
    stale[1]["any_keywords"] = ["interest income"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": stale, "engagement": {"due": "", "people": first["engagement"]["people"]},
        "head": first["list_head"]})
    assert code == 1 and payload["error"] == LIST_MOVED
    assert ledger.path_for(engagement).read_bytes() == before
    now = payload_of_state(capsys, engagement)
    assert [rule["identifier"] for rule in now["rules"]] == ["A01", "B01", "F02"]
    assert now["engagement"]["due"] == "2026-03-15"
    assert "T CLIENT" in now["engagement"]["people"][0]["spellings"]

    for head in ("", None, 7):
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                            stdin={"items": _rows_of(now), "engagement": {}, "head": head})
        assert code == 1 and payload["error"] == NO_LIST_HEAD
    assert ledger.path_for(engagement).read_bytes() == before

    # A pass moves the record's head, not the list's: the editor opened
    # before it saves after it.
    opened = payload_of_state(capsys, engagement)
    journal = ledger.head(engagement)
    assert run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0
    assert ledger.head(engagement) != journal
    assert payload_of_state(capsys, engagement)["list_head"] == opened["list_head"]
    edited = _rows_of(opened)
    edited[0]["any_keywords"] = ["wages"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": edited, "engagement": {}, "head": opened["list_head"]})
    assert code == 0 and payload["saved"]["changed"] == ["A01"], payload
    assert payload["state"]["list_head"] != opened["list_head"]


def _filed_documents(capsys, demo_root, tmp_path):
    """The sample return with both current-year W-2s filed under A01 and the
    1098 under C01, by a real pass."""
    from tests.samples import YEAR

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 John Smith {YEAR}.pdf",
                                   f"W-2 Jane Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    filed = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert sorted(e["identifier"] for e in filed) == ["A01", "A01", "C01"], filed
    return engagement, payload["state"]


def test_respelling_an_identifier_with_documents_is_refused_unless_renamed_with_them(
        capsys, demo_root, tmp_path):
    """A01 holds two filed W-2s. Saving the list with A01 spelled A1 - or
    without A01 at all - used to save as a removal and an addition with no
    warning: the W-2s became "Other document", A1 was missing, and the
    letter and the README asked the client again (decision 160, the audit's
    D-7). The save is refused by name and count, and nothing is recorded;
    the rename action is the way, and it carries the documents."""
    from tracker.filer import OTHER_DOCUMENT

    engagement, state = _filed_documents(capsys, demo_root, tmp_path)
    label = next(i.label for i in load_manifest(engagement) if i.identifier == "A01")
    before = ledger.path_for(engagement).read_bytes()
    respelt = [{**rule, "identifier": "A1"} if rule["identifier"] == "A01" else rule
               for rule in _rows_of(state)]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": respelt, "engagement": {}})
    assert code == 1 and payload["error"] == api.HOLDS_DOCUMENTS.format(identifier="A01", n=2)
    dropped = [rule for rule in _rows_of(state) if rule["identifier"] != "A01"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": dropped, "engagement": {}})
    assert code == 1 and payload["error"] == api.HOLDS_DOCUMENTS.format(identifier="A01", n=2)
    assert ledger.path_for(engagement).read_bytes() == before
    # A row that holds nothing is still removed by a save, as it always was.
    empty = [rule for rule in _rows_of(state) if rule["identifier"] != "B01"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": empty, "engagement": {}})
    assert code == 0 and payload["saved"]["removed"] == ["B01"], payload

    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 0, payload
    assert (payload["renamed"]["old"], payload["renamed"]["new"], payload["renamed"]["moved"]) == \
        ("A01", "A1", 2)
    items = {i["identifier"]: i for i in payload["state"]["items"]}
    assert "A01" not in items and items["A1"]["status"] == Status.RECEIVED
    assert sorted(e["identifier"] for e in payload["state"]["index"] if e["decision"] == FILED) == \
        ["A1", "A1", "C01"]
    readme = client_readme(engagement)
    renamed_label = next(i.label for i in load_manifest(engagement) if i.identifier == "A1")
    assert renamed_label != label and renamed_label not in _waiting_in(readme)
    assert f"  {renamed_label}  Received" in readme and OTHER_DOCUMENT not in readme


def test_a_rename_carries_its_documents(capsys, demo_root, tmp_path):
    """The rename gives every working copy of the request's the new
    identifier at the front of its name, in Prepared itself (decision 168),
    rewrites each row that names them, and records
    it as one act: the list renamed and each row's intent in one write,
    then the moves, then the rows (decision 119's intents). A stale list,
    a case-only change, a name already taken and a request that is not on
    the list are refused, and nothing moves."""
    from tracker.manifest import LIST_MOVED

    engagement, state = _filed_documents(capsys, demo_root, tmp_path)
    prepared = engagement / PREPARED_DIR_NAME
    old_copies = sorted(e["prepared_location"] for e in state["index"]
                        if e["decision"] == FILED and e["identifier"] == "A01")
    assert all((engagement / location).is_file() for location in old_copies)
    assert all("/A01 - " in location for location in old_copies)
    before = ledger.path_for(engagement).read_bytes()

    for spec, said in (({"from": "A01", "to": "a01"}, "differ only in case"),
                       ({"from": "A01", "to": "c01"}, "C01"),
                       ({"from": "Z9", "to": "A1"}, "Z9"),
                       ({"from": "A01", "to": "A1", "head": "stale"}, LIST_MOVED)):
        code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement), stdin=spec)
        assert code == 1 and said in payload["error"], (spec, payload)
    assert ledger.path_for(engagement).read_bytes() == before
    assert all((engagement / location).is_file() for location in old_copies)

    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 0, payload
    assert payload["renamed"]["head"] == payload["state"]["list_head"]
    moved = sorted(e["prepared_location"] for e in payload["state"]["index"]
                   if e["decision"] == FILED and e["identifier"] == "A1")
    assert moved == sorted(location.replace("/A01 - ", "/A1 - ") for location in old_copies)
    for location in moved:
        assert (engagement / location).is_file()
        assert Path(location).name.startswith("A1 - ")
    assert not any((engagement / location).exists() for location in old_copies)
    assert not [child for child in prepared.iterdir() if child.name.startswith("A01")]
    # The record says it once: the list renamed and each row's intent in
    # one write, each row closed by the person's rename, no intent left
    # open - and the store agrees with the journal (the suite's own check
    # runs after every test).
    events = ledger.read_events(engagement)
    added = events[len(before.splitlines()):]
    names = [e[ledger.EVENT_KEY] for e in added]
    assert names[0] == ledger.RULES_CHANGED
    assert added[0][ledger.REMOVED_KEY] == ["A01"]
    assert [row["identifier"] for row in added[0][ledger.RULES_KEY]] == ["A1"]
    intents = [e for e in added if e[ledger.EVENT_KEY] == ledger.MOVING]
    closed = [e for e in added if e[ledger.EVENT_KEY] == ledger.RENAMED_BY_PERSON]
    assert len(intents) == len(closed) >= 2
    assert {e[ledger.KEY_KEY] for e in intents} == {e[ledger.KEY_KEY] for e in closed}
    assert not store.open_intents(store.connect(), engagement)


def test_a_rename_carries_duplicates_and_parked_candidates_that_name_it(
        capsys, demo_root, tmp_path, monkeypatch):
    """Rows with nothing to move still follow a rename (decision 160, the
    review's gap): a Duplicate row that names the request, and a parked
    row with the request among its candidates, name the new identifier
    afterwards - the parked row's evidence cell too, where it round-trips.
    Each gets its own intent in the rename's one write, so a rename a run
    was killed in is finished for them by the next pass as well; and a
    rename that runs through carries them the same way."""
    import tracker.filer as filer
    from tests.samples import PRIOR_YEAR, YEAR
    from tracker.filer import DUPLICATE

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 John Smith {YEAR}.pdf",
                                   f"W-2 John Smith {YEAR} - Copy.pdf",
                                   f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload

    def rows(state):
        return {e["original_name"]: e for e in state["index"]}

    before = rows(payload["state"])
    duplicate = next(e for e in before.values() if e["decision"] == DUPLICATE)
    parked = next(e for e in before.values() if e["decision"] == NEEDS_REVIEW)
    assert duplicate["identifier"] == "A01" and duplicate["prepared_location"] == ""
    assert parked["candidates"] == ["A01"] and list(parked["evidence"]) == ["A01"]

    def follows(state, identifier):
        now = rows(state)
        assert now[duplicate["original_name"]]["identifier"] == identifier
        assert now[parked["original_name"]]["candidates"] == [identifier]
        assert list(now[parked["original_name"]]["evidence"]) == [identifier]
        assert now[parked["original_name"]]["evidence"][identifier] == parked["evidence"]["A01"]
        assert now[parked["original_name"]]["decision"] == NEEDS_REVIEW

    # Killed at its one move: every row's intent is already written.
    real = filer._do_op

    def killed(engagement_dir, op, **kwargs):
        raise PermissionError("held open by another program")

    monkeypatch.setattr(filer, "_do_op", killed)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 1, payload
    open_keys = {intent[ledger.KEY_KEY] for intent in store.open_intents(store.connect(), engagement)}
    assert {duplicate["pbc_location"], parked["pbc_location"]} <= open_keys
    monkeypatch.setattr(filer, "_do_op", real)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    assert not store.open_intents(store.connect(), engagement)
    follows(payload["state"], "A1")

    # And a rename that runs through carries them the same way.
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A1", "to": "A01"})
    assert code == 0, payload
    follows(payload["state"], "A01")
    closed = [e[ledger.KEY_KEY] for e in ledger.read_events(engagement)
              if e[ledger.EVENT_KEY] == ledger.RENAMED_BY_PERSON]
    assert closed.count(duplicate["pbc_location"]) == 2 and closed.count(parked["pbc_location"]) == 2


def test_an_interrupted_rename_is_finished_by_the_next_pass(capsys, demo_root, tmp_path, monkeypatch):
    """A rename whose second move fails is on the record from its first
    write, and the next pass finishes it (decision 119): nothing lost and
    nothing doubled. Since decision 168 it renames the copies only, in
    Prepared itself: no folder is made and none is left to tidy."""
    import tracker.filer as filer
    from tracker.filer import RENAME_UNFINISHED

    engagement, _ = _filed_documents(capsys, demo_root, tmp_path)
    prepared = engagement / PREPARED_DIR_NAME
    real = filer._do_op
    calls = {"n": 0}

    def the_second_move_fails(engagement_dir, op, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise PermissionError("held open by another program")
        return real(engagement_dir, op, **kwargs)

    monkeypatch.setattr(filer, "_do_op", the_second_move_fails)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 1 and payload["error"].startswith(RENAME_UNFINISHED.split("{name}")[0].format(
        old="A01", new="A1"))
    assert store.open_intents(store.connect(), engagement)
    # One copy moved before the failure, one did not: both in Prepared itself.
    assert len([child for child in prepared.iterdir() if child.name.startswith("A01 - ")]) == 1
    assert len([child for child in prepared.iterdir() if child.name.startswith("A1 - ")]) == 1

    monkeypatch.setattr(filer, "_do_op", real)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    assert not store.open_intents(store.connect(), engagement)
    assert not [child for child in prepared.iterdir() if child.name.startswith("A01")]
    assert [child.name for child in prepared.iterdir() if child.is_dir()] == [REVIEW_DIR_NAME]
    assert payload["run"]["warnings"] == []
    filed = [e for e in payload["state"]["index"] if e["decision"] == FILED and e["identifier"] == "A1"]
    assert len(filed) == 2 and all((engagement / e["prepared_location"]).is_file() for e in filed)
    assert len({e["prepared_location"] for e in filed}) == 2                  # nothing doubled
    assert len([child for child in prepared.iterdir() if child.name.startswith("A1 - ")]) == 2


@pytest.mark.parametrize("only_the_cell", [False, True], ids=["as-routed", "only-the-cell"])
def test_a_rename_carries_what_a_consolidated_statement_answers(capsys, demo_root, monkeypatch,
                                                                only_the_cell):
    """d146 over 160, SPEC-146 R-1. The Schwab statement is filed under E01
    and answers A02 through its Also Answers cell, with no copy under A02.
    Renaming A02 to A02X rewrites that cell, sections and all: A02X reads
    Received with the scanner's in-the-statement note, the letter does not
    ask for it, the client README says it is received inside the brokerage
    statement, and marking it missing again takes the new name. A rename
    killed after its one write is finished by the next pass to the same
    result, because the statement's row - linked to A02 by that cell alone -
    has its own intent in the write.

    The router's row also names A02 among its candidates and evidence,
    which 160's rename already carried; so the claim runs a second time
    with the statement's row recorded naming A02 in its Also Answers cell
    alone, through the filer's own writer, and the cell must carry it."""
    from dataclasses import replace

    import tracker.filer as filer
    from tests.test_filer import _consolidated_return
    from tracker.reasons import IN_CONSOLIDATED, IN_CONSOLIDATED_CLIENT
    from tracker.reminder import draft_reminder

    engagement = _consolidated_return(demo_root)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["identifier"] == "E01" and filed["answered"] == ["A02", "A04"]
    if only_the_cell:
        from tracker.locking import engagement_lock
        from tracker.records import entry_to_json, ledger_key

        with engagement_lock(engagement):
            entries = read_index(engagement)
            before = {ledger_key(e): entry_to_json(e) for e in entries}
            entries = [replace(e, candidates="E01", evidence="") if e.decision == FILED else e
                       for e in entries]
            filer._record(engagement, before, entries)
        [row] = [r for r in read_index(engagement) if r.decision == FILED]
        assert row.candidate_list == ["E01"] and row.evidence == "" and "A02" in row.answers

    def carried(state, new):
        [row] = [r for r in read_index(engagement) if r.decision == FILED]
        assert row.identifier == "E01"
        assert row.answers == f"{new} (1099-int, 1099-div); A04 (1099-misc)"
        items = {i.identifier: i for i in load_manifest(engagement)}
        assert "A02" not in items or new == "A02"
        assert items[new].status == Status.RECEIVED, items[new].validation_notes
        assert items[new].file_count == 2
        assert IN_CONSOLIDATED.format(row="E01") in items[new].validation_notes
        assert new not in draft_reminder(engagement).asked
        readme = client_readme(engagement)
        label = items[new].label
        assert label not in _waiting_in(readme)
        [said] = [one for one in readme.splitlines() if one.strip().startswith(label)]
        assert said.endswith(f", {IN_CONSOLIDATED_CLIENT}"), said
        [shown] = [e for e in state["index"] if e["decision"] == FILED]
        assert shown["answered"] == [new, "A04"]

    # Killed after the rename's one write: the list and every row's intent
    # are on the record, and the statement's row is not yet rewritten.
    real = filer._record

    def killed(*args, **kwargs):
        raise PermissionError("the run was stopped")

    monkeypatch.setattr(filer, "_record", killed)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A02", "to": "A02K"})
    assert code == 1, payload
    open_keys = {intent[ledger.KEY_KEY] for intent in store.open_intents(store.connect(), engagement)}
    assert filed["pbc_location"] in open_keys
    monkeypatch.setattr(filer, "_record", real)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    assert not store.open_intents(store.connect(), engagement)
    carried(payload["state"], "A02K")

    # A rename that runs through carries it the same way.
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A02K", "to": "A02X"})
    assert code == 0, payload
    assert payload["renamed"]["moved"] == 0
    carried(payload["state"], "A02X")
    closed = [e[ledger.KEY_KEY] for e in ledger.read_events(engagement)
              if e[ledger.EVENT_KEY] == ledger.RENAMED_BY_PERSON]
    assert closed.count(filed["pbc_location"]) == 2

    # And the person's button takes the new name.
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A02X",
                               "seq": filed["seq"]})
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["answered"] == ["A04"]
    a02x = next(i for i in payload["state"]["items"] if i["identifier"] == "A02X")
    assert a02x["status"] == Status.MISSING


def test_a_request_answered_only_by_a_statement_cannot_be_deleted_by_a_save(capsys, demo_root):
    """d146 over 160, SPEC-146 R-2. A04 holds no copy: the Schwab statement
    filed under E01 answers it through its Also Answers cell. A save that
    takes A04 off the list is refused with decision 160's sentence, and
    nothing is recorded; once a person marks A04 missing again, the same
    save goes through."""
    from tests.test_filer import _consolidated_return

    engagement = _consolidated_return(demo_root)
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]
    [filed] = [e for e in state["index"] if e["decision"] == FILED]
    assert filed["identifier"] == "E01" and "A04" in filed["answered"]
    assert not [e for e in state["index"] if e["identifier"] == "A04"]

    before = ledger.path_for(engagement).read_bytes()
    dropped = [rule for rule in _rows_of(state) if rule["identifier"] != "A04"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": dropped, "engagement": {}})
    assert code == 1 and payload["error"] == api.HOLDS_DOCUMENTS.format(identifier="A04", n=1)
    assert ledger.path_for(engagement).read_bytes() == before

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A04",
                               "seq": filed["seq"]})
    assert code == 0, payload
    state = payload["state"]
    dropped = [rule for rule in _rows_of(state) if rule["identifier"] != "A04"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": dropped, "engagement": {}})
    assert code == 0 and payload["saved"]["removed"] == ["A04"], payload


def test_a_filing_racing_a_save_is_seen_under_the_lock(capsys, demo_root, tmp_path, monkeypatch):
    """The documents-held check runs inside the save's engagement lock, in
    the same critical section as the write (decision 160, the designer's
    ruling on the build). A pass that files the 1098 into C01 after the
    editor sent a list without C01, and before the save takes the lock, is
    seen: the save is refused and C01 stays."""
    from tests.samples import YEAR
    from tracker.locking import lock_is_held

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 John Smith {YEAR}.pdf")
    code, payload = run(capsys, "scan", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    state = payload["state"]
    assert not [e for e in state["index"] if e["identifier"] == "C01"]
    samples = tmp_path / "samples"
    before_the_lock = api._refuse_a_changed_row_past_the_limit

    def a_pass_files_first(folder, items):
        # Outside the lock: the 1098 arrives and the household's sort files it.
        assert not lock_is_held(folder)
        (inbox_of(folder) / "Form 1098 Mortgage Interest.pdf").write_bytes(
            (samples / "Form 1098 Mortgage Interest.pdf").read_bytes())
        from tests.conftest import sort
        sort(folder)
        return before_the_lock(folder, items)

    seen_under = []
    real_check = api._refuse_taking_away_documents

    def the_check(folder, recorded, items):
        seen_under.append(lock_is_held(folder))
        return real_check(folder, recorded, items)

    monkeypatch.setattr(api, "_refuse_a_changed_row_past_the_limit", a_pass_files_first)
    monkeypatch.setattr(api, "_refuse_taking_away_documents", the_check)
    without_c01 = [rule for rule in _rows_of(state) if rule["identifier"] != "C01"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": without_c01, "engagement": {}, "head": state["list_head"]})
    assert code == 1 and payload["error"] == api.HOLDS_DOCUMENTS.format(identifier="C01", n=1)
    assert seen_under == [True]
    assert "C01" in [rule["identifier"] for rule in payload_of_state(capsys, engagement)["rules"]]


def test_a_case_only_change_reads_the_same_in_the_readme_and_the_letter(capsys, demo_root, tmp_path):
    """C01 holds the filed 1098. Respelling it c01 is the same request
    everywhere (decision 160, the audit's D-8): the save needs no rename,
    the status is Received, the letter does not ask for it, and the client
    README lists the 1098 as received under its own label - it used to say
    "not received" beside an "Other document"."""
    from tracker import reminder
    from tracker.filer import OTHER_DOCUMENT, received_for

    engagement, state = _filed_documents(capsys, demo_root, tmp_path)
    respelt = [{**rule, "identifier": "c01"} if rule["identifier"] == "C01" else rule
               for rule in _rows_of(state)]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": respelt, "engagement": {}})
    assert code == 0, payload
    items = {i["identifier"]: i for i in payload["state"]["items"]}
    assert items["c01"]["status"] == Status.RECEIVED
    label = next(i.label for i in load_manifest(engagement) if i.identifier == "c01")

    received = received_for([engagement])
    assert label in {line.label for line in received.lines}
    assert OTHER_DOCUMENT not in {line.label for line in received.lines}
    assert "c01" in {line.identifier for line in received.lines}

    readme = client_readme(engagement)
    assert label not in _waiting_in(readme)
    assert f"  {label}  Received" in readme and OTHER_DOCUMENT not in readme

    letter = reminder.draft_reminder(engagement)
    assert "c01" not in {line.item.identifier.lower() for line in letter.lines}


# ------------------------------------ decision 188: one name rule ----


def test_one_name_rule_gives_one_sentence_wherever_a_name_is_typed(capsys, demo_root):
    """A household or a return name is held to the layout's one rule
    wherever a person types one - the wizard's household and return, a
    rolled return's new name, a feed - and each box answers with the same
    sentence: the name as typed, what it is, and the rule's reason."""
    from tracker import layout

    bad = "Pa​rk"
    reason = layout.segment_problem(bad)
    said_household = layout.NAME_REFUSED.format(typed=bad, what="household", reason=reason)
    said_return = layout.NAME_REFUSED.format(typed=bad, what="return", reason=reason)
    items = [{"identifier": "A01", "document": "W-2"}]

    code, payload = run(capsys, "create", stdin={"household": bad, "return_name": "1040 - Park",
                                                 "items": items})
    assert code == 1 and payload["error"] == said_household
    code, payload = run(capsys, "create", stdin={"household": "Park Family", "return_name": bad,
                                                 "items": items})
    assert code == 1 and payload["error"] == said_return

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": items})[0] == 0
    prior = where(demo_root, "1040 - Park", household="Park Family")
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"year": 2026, "returns": [{"prior": str(prior), "return_name": bad}]})
    assert code == 1 and payload["error"] == said_return
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"feeds": [{"household": bad, "return_name": "1040 - Lee"}]})
    assert code == 1 and payload["error"] == said_household
    assert not (demo_root / layout.PRIVATE_TREE / bad).exists()


def test_a_name_the_walk_would_pass_over_is_never_created(capsys, demo_root):
    """C-7: a household made under a name discovery passes over - a dot, an
    underscore, an office lock's ``~$`` - would never be listed, sorted or
    chased. The rule refuses every one before anything is written."""
    from tracker import layout

    for hidden in (".Park", "_Park", "~$Park"):
        code, payload = run(capsys, "create", stdin={
            "household": hidden, "return_name": "1040 - Park",
            "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1, hidden
        assert payload["error"] == layout.NAME_REFUSED.format(
            typed=hidden, what="household", reason=layout.NAME_FIRST_CHARACTER)
    assert not any(demo_root.rglob(ledger.LEDGER_FILENAME))


# ------------------------------- decision 188: the door, the checked root ----


def _tree_hashes(folder):
    """Every file and folder under ``folder``, with each file's bytes."""
    import hashlib

    return {str(p.relative_to(folder)): (hashlib.sha256(p.read_bytes()).hexdigest()
                                         if p.is_file() else "folder")
            for p in sorted(folder.rglob("*"))}


def test_a_rollover_from_a_client_inbox_fails_closed(capsys, demo_root):
    """T3: a return's place is the parser's, so a folder in the client's
    inbox holding a fabricated ``_ledger.jsonl`` is never a prior and
    never a household - for ``rollover``, ``roll-household`` and ``create``
    by ``household_path`` alike - and both trees are as they were."""
    from tracker.templates import template_items

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "form": "1040",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    real = where(demo_root, "1040 - Park", household="Park Family")
    planted = make_engagement(inbox_of(real) / "X", template_items("1040", year=2025),
                              scaffold=False)
    private, clients = demo_root / PRIVATE_TREE, demo_root / layout.CLIENTS_TREE
    before = (_tree_hashes(private), _tree_hashes(clients))

    code, payload = run(capsys, "rollover", stdin={"prior": str(planted), "year": 2026})
    assert code == 1 and payload["error"] == layout.NOT_A_RETURN.format(name=planted.name,
                                                                        tree=PRIVATE_TREE)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(planted),
                        stdin={"year": 2026, "returns": [{"prior": str(planted)}]})
    assert code == 1 and payload["error"] == layout.NOT_A_RETURN.format(name=planted.name,
                                                                        tree=PRIVATE_TREE)
    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(real),
                        stdin={"year": 2026, "returns": [{"prior": str(planted)}]})
    assert code == 1 and "is not a return's folder" in payload["error"]
    code, payload = run(capsys, "create", stdin={
        "household_path": str(planted), "return_name": "1040 - Evil", "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 1 and payload["error"] == layout.NOT_A_HOUSEHOLD.format(name=planted.name,
                                                                           tree=PRIVATE_TREE)
    assert (_tree_hashes(private), _tree_hashes(clients)) == before


def test_every_command_that_reads_the_root_rechecks_it(capsys, demo_root):
    """E-13: a root saved while it was fine and made one level too deep
    afterwards - the trees moved around it - is refused by every command
    that reads it, with "Clients folder problem: " and the refusal; the
    first call still hands the app its words and asks for the folder."""
    from tracker.settings import ROOT_INSIDE_A_TREE

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - Park", household="Park Family")
    # A person moves the whole root into the firm's tree of a folder that
    # now holds both trees: the saved root is inside a tree of a real root.
    above = demo_root.parent / "Real root"
    (above / layout.CLIENTS_TREE).mkdir(parents=True)
    (above / PRIVATE_TREE).mkdir()
    moved = above / PRIVATE_TREE / demo_root.name
    demo_root.rename(moved)
    from tracker.settings import KEY_CLIENTS_ROOT, settings_path

    settings = json.loads(settings_path().read_text(encoding="utf-8"))
    settings[KEY_CLIENTS_ROOT] = str(moved)
    settings_path().write_text(json.dumps(settings), encoding="utf-8")
    said = "Clients folder problem: " + ROOT_INSIDE_A_TREE.format(
        root=moved.resolve(), tree=PRIVATE_TREE, real=above.resolve())
    engagement = moved / engagement.relative_to(demo_root)
    try:
        for argv, stdin in [
            (["state", api.ENGAGEMENT_FLAG, str(engagement)], None),
            (["edit-household", api.ENGAGEMENT_FLAG, str(engagement)], {"contact": "x"}),
            (["create"], {"household": "Lee Family", "return_name": "1040 - Lee",
                          "items": [{"identifier": "A01", "document": "W-2"}]}),
            (["rollover"], {"prior": str(engagement), "year": 2026}),
            (["priors"], None),
        ]:
            code, payload = run(capsys, *argv, stdin=stdin)
            assert code == 1 and payload["error"] == said, (argv, payload)
        code, payload = run(capsys, "list")
        assert code == 0 and payload["needs_root"] and payload["root_problem"] == said
        assert payload["vocab"]["commands"]
    finally:
        moved.rename(demo_root)
        shutil.rmtree(above, ignore_errors=True)


# ------------------------------- decision 188: the folder is the name ----


def test_typing_an_existing_households_name_is_refused_and_points_at_the_list(capsys, demo_root):
    """T12: a household name typed again - its folder's name or its
    record's claim, in any case or spacing - is refused before anything is
    written, naming the household in the list and what to add to tell two
    households apart: a first name or a middle initial, then the city."""
    items = [{"identifier": "A01", "document": "W-2"}]
    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": items})[0] == 0
    said = api.DUPLICATE_HOUSEHOLD.format(existing="Park Family")
    assert "add a first name or a middle initial" in said and "add the city" in said
    for typed in ("Park Family", "PARK FAMILY", "  park   family "):
        code, payload = run(capsys, "create", stdin={"household": typed, "return_name": "1040 - X",
                                                     "items": items})
        assert code == 1 and payload["error"] == said, typed
    assert sorted(p.name for p in (demo_root / PRIVATE_TREE).iterdir()) == ["Park Family"]


def test_look_alike_spellings_of_one_name_are_refused_as_one_name(capsys, demo_root):
    """T2: once ``Park`` exists, every spelling that reads as it - case, a
    Cyrillic letter or two (a mixed name is refused by the rule), full-width
    letters, a soft hyphen - is refused, by the key or by the rule; and a
    name all in one look-alike script is the name it imitates too."""
    from tracker import layout

    items = [{"identifier": "A01", "document": "W-2"}]
    for made in ("Park", "Cox", "Woo"):
        assert run(capsys, "create", stdin={"household": made, "return_name": "1040 - One",
                                            "items": items})[0] == 0
    for typed in ("PARK", "\u0420\u0430rk", "P\u0430rk", "\uff30\uff41\uff52\uff4b",
                  "Pa\u00adrk", "\u0421\u041e\u0425", "\u051c\u041e\u041e"):
        code, payload = run(capsys, "create", stdin={"household": typed, "return_name": "1040 - Two",
                                                     "items": items})
        assert code == 1, typed
        named = layout.normalised_name(typed)
        assert (payload["error"].startswith(f"'{named}' is not a household name: ")
                or payload["error"].startswith("A household with that name is already in the list")
                ), (typed, payload["error"])
    assert sorted(p.name for p in (demo_root / PRIVATE_TREE).iterdir()) == ["Cox", "Park", "Woo"]


def test_a_client_folder_no_household_owns_is_never_adopted(capsys, demo_root):
    """T12 and C-2: a folder in the client tree no household owns is never
    taken for a new household of that name (or a look-alike of it): the
    wizard says where it is listed, and nothing is written in either tree."""
    stray = demo_root / layout.CLIENTS_TREE / "Lee Family"
    (stray / "2025").mkdir(parents=True)
    (stray / "2025" / "w2.pdf").write_bytes(b"%PDF-1.4 somebody's own file")
    for typed in ("Lee Family", "LEE  FAMILY"):
        code, payload = run(capsys, "create", stdin={
            "household": typed, "return_name": "1040 - Lee",
            "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1 and payload["error"] == api.CLIENT_FOLDER_TAKEN, typed
    assert not (demo_root / PRIVATE_TREE).exists() or not any((demo_root / PRIVATE_TREE).iterdir())
    assert sorted(p.name for p in stray.rglob("*")) == ["2025", "w2.pdf"]


def _a_renamed_household(capsys, demo_root, *, received=False):
    """Park Family with one return, its private folder then renamed in
    Explorer to Park Household: the record still claims Park Family."""
    from tests.conftest import seed_index
    from tracker.filer import FILED
    from tracker.records import IndexEntry

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - Park", household="Park Family")
    if received:
        seed_index(engagement, [IndexEntry(
            received="2026-02-02", original_name="w2.pdf", size_kb=5.0, digest="ab" * 32,
            identifier="A01", prepared_location="Prepared/A01 - W-2.pdf",
            pbc_location=f"../../../../{layout.CLIENTS_TREE}/Park Family/2025/w2.pdf",
            decision=FILED, reason="filed")])
    private = demo_root / PRIVATE_TREE
    (private / "Park Family").rename(private / "Park Household")
    return private / "Park Household" / engagement.parent.name / engagement.name


def test_accepting_the_folders_name_is_one_dated_event_and_lifts_the_pause(capsys, demo_root):
    """T15: the card shows the pause and what to accept; accepting writes
    one household_changed line naming the folder on the household's record
    and one rules_changed line on each return whose claim disagreed, each
    carrying the person's word - and nothing is moved or renamed. The
    pause is lifted, and the pass would run the household again."""
    from tracker.households import HOUSEHOLD_PAUSED, household_pause

    engagement = _a_renamed_household(capsys, demo_root)
    household = engagement.parent.parent
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    pause = payload["household"]["pause"]
    assert pause["sentence"] == HOUSEHOLD_PAUSED and pause["scope"] == "household"
    before = sorted(p.relative_to(demo_root) for p in demo_root.rglob("*")
                    if p.name != ledger.LEDGER_FILENAME)
    lines = (len(ledger.read_events(household)), len(ledger.read_events(engagement)))

    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, pause["engagement"],
                        stdin={"seq": pause["seq"], "scope": "household"})
    assert code == 0, payload
    [named] = ledger.read_events(household)[lines[0]:]
    [claimed] = ledger.read_events(engagement)[lines[1]:]
    assert named[ledger.EVENT_KEY] == ledger.HOUSEHOLD_CHANGED
    assert named[ledger.HOUSEHOLD_KEY] == {"name": "Park Household"}
    assert claimed[ledger.EVENT_KEY] == ledger.RULES_CHANGED
    assert claimed[ledger.INFO_KEY] == {"household": "Park Household"}
    for line in (named, claimed):
        assert line[ledger.ACCEPTED_KEY] == ledger.FOLDER_NAME_ACCEPTED and line[ledger.AT_KEY]
    assert household_pause(household) == ""
    assert payload["state"]["household"]["pause"]["sentence"] == ""
    assert sorted(p.relative_to(demo_root) for p in demo_root.rglob("*")
                  if p.name != ledger.LEDGER_FILENAME) == before


def test_a_stale_seq_is_refused(capsys, demo_root):
    """T15: an accept drawn from a page the household's record has moved on
    from is refused and writes nothing."""
    engagement = _a_renamed_household(capsys, demo_root)
    household = engagement.parent.parent
    lines = len(ledger.read_events(household))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": lines - 1, "scope": "household"})
    assert code == 1 and payload["error"] == api.ACCEPT_STALE
    assert len(ledger.read_events(household)) == lines


def test_a_year_disagreement_is_not_accepted(capsys, demo_root):
    """T15: a return's year is its record's, so a return folder moved under
    another year is never accepted - the folder goes back - and nothing is
    written."""
    from tracker.households import HOUSEHOLD_PAUSED_YEAR

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - Park", household="Park Family")
    moved = engagement.parent.parent / "2019" / engagement.name
    moved.parent.mkdir()
    engagement.rename(moved)
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(moved))
    pause = payload["household"]["pause"]
    assert pause["sentence"] == HOUSEHOLD_PAUSED_YEAR
    # No button (the review's S3): nothing to accept, only to put back.
    assert pause["scope"] == "" and pause["seq"] is None
    assert "retired and made again" in pause["sentence"]
    journal = ledger.path_for(moved).read_bytes()
    seq = len(ledger.read_events(moved.parent.parent))
    for scope in ("household", "return"):
        code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(moved),
                            stdin={"seq": seq, "scope": scope})
        assert code == 1 and payload["error"] == api.YEAR_NOT_ACCEPTED
    assert ledger.path_for(moved).read_bytes() == journal


def test_accepting_a_household_whose_originals_rest_under_the_old_name_is_refused(
        capsys, demo_root):
    """T15: a household that has received a document is not renamed this
    season - accepting would orphan the originals resting under its client
    folder of the old name - so the folder goes back, and nothing is
    written."""
    engagement = _a_renamed_household(capsys, demo_root, received=True)
    household = engagement.parent.parent
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    pause = payload["household"]["pause"]
    lines = len(ledger.read_events(household))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": pause["seq"], "scope": "household"})
    assert code == 1 and payload["error"] == api.ORIGINALS_UNDER_OLD_NAME
    assert len(ledger.read_events(household)) == lines


def test_accepting_one_return_never_renames_a_household_that_has_received_a_document(
        capsys, demo_root):
    """The review's M2 (D-1 by the accept route): an accept of one return
    runs the same originals check before it writes anything, so a household
    whose originals rest under its old client folder is not renamed by a
    return's accept either - and a return's accept never writes the
    household's name, so the household stays paused and the pass red."""
    from tracker.households import HOUSEHOLD_PAUSED, household_pause

    engagement = _a_renamed_household(capsys, demo_root, received=True)
    household = engagement.parent.parent
    lines = (len(ledger.read_events(household)), len(ledger.read_events(engagement)))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": lines[0], "scope": "return"})
    assert code == 1 and payload["error"] == api.ORIGINALS_UNDER_OLD_NAME
    assert (len(ledger.read_events(household)), len(ledger.read_events(engagement))) == lines
    assert household_pause(household) == HOUSEHOLD_PAUSED


def test_a_returns_accept_writes_only_that_returns_line(capsys, demo_root):
    """A return's accept, where nothing has been received, writes that
    return's own two names and nothing on the household's record: a
    household whose own record claims another name is still paused until
    its own accept."""
    from tracker.households import HOUSEHOLD_PAUSED, household_pause

    engagement = _a_renamed_household(capsys, demo_root)
    household = engagement.parent.parent
    lines = len(ledger.read_events(household))
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"seq": lines, "scope": "return"})
    assert code == 0, payload
    assert len(ledger.read_events(household)) == lines
    last = ledger.read_events(engagement)[-1]
    assert last[ledger.INFO_KEY] == {"household": "Park Household", "return_name": engagement.name}
    assert household_pause(household) == HOUSEHOLD_PAUSED
# ------------------------------------------ decision 159: the record's checkpoint ----


def test_a_person_acknowledges_a_line_another_machine_wrote(capsys, demo_root):
    """C-1 (a): the line is accepted and named until a person says they have
    looked; ``acknowledge-foreign`` is that, a writing command under the
    return's lock."""
    from tests.conftest import written_elsewhere

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    written_elsewhere(engagement, ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {}}),
                      host="laptop-2")
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[0] == 0     # accepted
    assert [(one.host) for one in store.foreign_lines()] == ["laptop-2"]

    code, payload = run(capsys, "acknowledge-foreign", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0 and payload["acknowledged"] == 1
    assert store.foreign_lines() == []
    assert "acknowledge-foreign" in api.WRITING_COMMANDS


def test_a_writing_command_refuses_a_root_the_checkpoint_does_not_belong_to(capsys, demo_root, tmp_path):
    """E5: every writing command holds the settings' root to this machine's
    checkpoint first; a copy of the root is refused by name before anything
    is written."""
    from tracker.settings import set_clients_root

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    copy = tmp_path / "Clients copy"
    copy.mkdir()
    set_clients_root(copy)
    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Jones"})
    assert code == 1 and "record checkpoint belongs to" in payload["error"]
    assert "If the clients root really moved" in payload["error"]
    assert not where(copy, "Jones").exists()
    assert run(capsys, "settings")[0] == 0                              # reading is not refused
    set_clients_root(demo_root)


def test_a_writing_command_says_a_busy_checkpoint_as_busy_not_as_another_root(capsys, demo_root,
                                                                              monkeypatch):
    """The rebase review's SF1: the checkpoint held by another run is said
    as busy - try again - never as a root it does not belong to, and
    nothing is written."""
    import sqlite3

    from tracker import checkpoint

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    monkeypatch.setattr(checkpoint, "BUSY_TIMEOUT_MS", 100)
    holder = sqlite3.connect(checkpoint.path_for(store.store_path()), isolation_level=None)
    holder.execute("BEGIN EXCLUSIVE")
    try:
        code, payload = run(capsys, "create", stdin={**spec, "return_name": "Jones"})
    finally:
        holder.execute("ROLLBACK")
        holder.close()
    assert code == 1 and "is busy" in payload["error"] and "belongs to" not in payload["error"]
    assert not where(demo_root, "Jones").exists()


def _writers_in_the_package() -> set[str]:
    """Every function in ``tracker/`` that reaches a write of a record or a
    client's file - ``store.record``, ``ledger.append``, a move
    (``os.rename``) or a copy (``shutil.copy2``) - by name, through the
    package's own calls, to a fixed point. Wide on purpose: a name shared by
    two functions counts as the writer's, so a guard built on it errs toward
    naming a command a writer."""
    import ast
    from pathlib import Path

    roots = {("store", "record"), ("ledger", "append"), ("os", "rename"), ("shutil", "copy2")}
    calls: dict[str, set[str]] = {}
    writes: set[str] = set()
    for path in sorted((Path(__file__).resolve().parents[1] / "tracker").glob("*.py")):
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if not isinstance(node, ast.FunctionDef):
                continue
            named = calls.setdefault(node.name, set())
            for call in (one for one in ast.walk(node) if isinstance(one, ast.Call)):
                func = call.func
                if isinstance(func, ast.Attribute):
                    named.add(func.attr)
                    if isinstance(func.value, ast.Name) and (func.value.id, func.attr) in roots:
                        writes.add(node.name)
                elif isinstance(func, ast.Name):
                    named.add(func.id)
                    if (path.stem, func.id) in roots:
                        writes.add(node.name)
    grew = True
    while grew:
        grew = False
        for name, called in calls.items():
            if name not in writes and called & writes:
                writes.add(name)
                grew = True
    return writes


def test_every_command_that_writes_holds_the_root_to_the_checkpoint_first():
    """Decision 159 (E5) and the port review's M2: every API command whose
    handler reaches a record's append, a move or a copy is in
    ``WRITING_COMMANDS``, so the settings' root is proved against this
    machine's record checkpoint before it writes. The writers are derived
    from the dispatch table and the package's own calls, never listed by
    hand, so a writing command a later decision adds is caught here."""
    writers = _writers_in_the_package()
    derived = {name for name, handler in api.COMMANDS.items() if handler.__name__ in writers}
    assert "accept-folder-name" in derived, "the derivation must see decision 188's accept"
    assert derived <= api.WRITING_COMMANDS, sorted(derived - api.WRITING_COMMANDS)
    assert api.WRITING_COMMANDS <= set(api.COMMANDS)


def test_accepting_a_folders_name_is_refused_on_a_root_the_checkpoint_does_not_belong_to(
        capsys, demo_root, tmp_path):
    """The port review's M2: decision 188's accept writes the household's and
    its returns' records, so it is held to this machine's record checkpoint
    like every writing command - on a copy of the root it is refused by name
    and writes nothing."""
    import shutil

    from tracker.settings import set_clients_root

    engagement = _a_renamed_household(capsys, demo_root)
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0                     # claims demo_root
    copy = tmp_path / "Clients copy"
    shutil.copytree(demo_root, copy)
    set_clients_root(copy)
    try:
        moved = copy / engagement.relative_to(demo_root)
        pause = run(capsys, "state", api.ENGAGEMENT_FLAG, str(moved))[1]["household"]["pause"]
        household = moved.parent.parent
        before = len(ledger.read_events(household))
        code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, pause["engagement"],
                            stdin={"seq": pause["seq"], "scope": "household"})
        assert code == 1 and "record checkpoint belongs to" in payload["error"]
        assert len(ledger.read_events(household)) == before
    finally:
        set_clients_root(demo_root)
