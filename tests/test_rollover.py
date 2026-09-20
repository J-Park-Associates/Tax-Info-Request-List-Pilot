"""Tests for tracker/rollover.py — last year beats the generic checklist.

The rule under test throughout: for a returning client, prior-year data wins.
The form template may fill a blank, never overwrite a value, and never
silently drop something the client actually had.
"""

import datetime as dt

import pytest

from tests.conftest import ensure, make_engagement, seed_statuses
from tracker import ledger
from tracker.manifest import (
    EngagementInfo,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    create_engagement,
    load_manifest,
)
from tracker.rollover import (
    ORIGIN_NEW,
    ORIGIN_PRIOR,
    ORIGIN_WAIVED,
    detect_year,
    roll_forward,
    shift_years,
)
from tracker.router import UNMATCHED
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME

# Last year's engagement: a 2025 individual return.
PRIOR = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        expected_count=2, allowed_extensions=("pdf",), min_size_kb=0,
        required_keywords=("W-2",), date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="B01", document="2024 Form 1040 Tax Return", period="TY2024",
        allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("form 1040",),
    ),
    RequestItem(
        identifier="C01", document="Rental Property Records", period="TY2025",
        allowed_extensions=("pdf", "xlsx"), min_size_kb=0,
        any_keywords=("rental",),
    ),
    RequestItem(
        identifier="D01", document="Marketplace Health Insurance", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0,
        manual_override=Override.WAIVED,
    ),
]

# This year's generic checklist — deliberately disagrees with the prior year.
TEMPLATE = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements - All Employers",
        period="TY2025", expected_count=1, allowed_extensions=("pdf", "jpg"),
        required_keywords=("wage statement",), date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="E01", document="1099-R Retirement Distributions",
        period="TY2025", allowed_extensions=("pdf",), any_keywords=("1099-r",),
    ),
]


@pytest.fixture
def prior(tmp_path):
    """Last year's engagement, scanned: A01 received 3 files, C01 never came."""
    eng = make_engagement(tmp_path / "Smith Family 2025", PRIOR, scaffold=False)
    seed_statuses(eng, {
        "A01": StatusUpdate(status=Status.RECEIVED, file_count=3,
                            received_date=dt.date(2026, 3, 1)),
        "B01": StatusUpdate(status=Status.RECEIVED, file_count=1,
                            received_date=dt.date(2026, 3, 2)),
        "C01": StatusUpdate(status=Status.MISSING, file_count=0),
    })
    return eng


def rolled_by_id(report):
    return {r.item.identifier: r for r in report.rolled}


def next_year(tmp_path, report, name="Smith Family 2026"):
    """Next year's engagement, created from the rollover's rows the way the
    API and the command line create it: into the record, no scaffold."""
    folder = tmp_path / name
    folder.mkdir(parents=True, exist_ok=True)
    create_engagement(folder, report.items)
    return folder


# ------------------------------------------------------------- year shifting ----


def test_shift_years_moves_every_year():
    assert shift_years("TY2025", 1) == "TY2026"
    assert shift_years("2024 Form 1040 Tax Return", 1) == "2025 Form 1040 Tax Return"
    assert shift_years(r"(?i)\b2025\b", 1) == r"(?i)\b2026\b"
    assert shift_years("Dec 2025 - Jan 2026", 1) == "Dec 2026 - Jan 2027"


def test_shift_years_leaves_form_numbers_alone():
    """1099 and 1040 are not years and must never be incremented."""
    assert shift_years("Form 1099-INT and Form 1040", 1) == "Form 1099-INT and Form 1040"


def test_detect_year_picks_the_engagement_year():
    # Three rows say 2025, one says 2024: the engagement is a 2025 one.
    assert detect_year(PRIOR) == 2025
    assert detect_year([]) is None


# ------------------------------------------------------------------ carrying ----


def test_prior_year_beats_the_template(prior):
    """Every field the prior year specifies survives the template's version."""
    report = roll_forward(prior, template=TEMPLATE)
    a01 = rolled_by_id(report)["A01"].item

    assert a01.document == "W-2 Wage Statements"          # not the template's name
    assert a01.allowed_extensions == ("pdf",)             # template's jpg rejected
    assert a01.required_keywords == ("W-2",)              # template's wording rejected
    assert a01.period == "TY2026"                         # rolled, not reset
    assert a01.date_pattern == r"(?i)\b2026\b"


def test_relative_periods_roll_too(prior):
    """The row asking for the TY2024 return now asks for the TY2025 one."""
    b01 = rolled_by_id(roll_forward(prior, template=TEMPLATE))["B01"].item
    assert b01.period == "TY2025"
    assert b01.document == "2025 Form 1040 Tax Return"


def test_counts_learn_from_what_arrived(prior):
    """Expected 2, received 3 — so ask for 3."""
    a01 = rolled_by_id(roll_forward(prior))["A01"]
    assert a01.item.expected_count == 3
    assert "asking for 3 this year" in a01.note


def test_counts_are_never_lowered(prior):
    """A client who under-delivered still owes what was asked."""
    eng = prior
    seed_statuses(eng,
                   {"A01": StatusUpdate(status=Status.PARTIAL, file_count=1)})
    a01 = rolled_by_id(roll_forward(eng))["A01"]
    assert a01.item.expected_count == 2
    assert "confirm it still applies" in a01.note


def test_template_only_fills_blanks(prior):
    """A blank has nothing to override, so the template may fill it."""
    sparse = [RequestItem(identifier="A01", document="W-2s", period="TY2025",
                          min_size_kb=0)]
    eng = make_engagement(prior.parent / "Sparse 2025", sparse, scaffold=False)

    a01 = rolled_by_id(roll_forward(eng, template=TEMPLATE))["A01"].item
    assert a01.document == "W-2s"                          # prior still wins
    assert a01.allowed_extensions == ("pdf", "jpg")        # blank filled
    assert a01.required_keywords == ("wage statement",)    # blank filled
    assert a01.date_pattern == r"(?i)\b2026\b"             # filled and rolled


def test_custom_rows_survive(prior):
    """A request the accountant added by hand is prior-year data too."""
    c01 = rolled_by_id(roll_forward(prior, template=TEMPLATE))["C01"].item
    assert c01.document == "Rental Property Records"
    assert c01.any_keywords == ("rental",)


# ------------------------------------------------------------------ decisions ----


def test_waived_stays_waived(prior):
    """Don't ask again for something we decided this client doesn't have."""
    d01 = rolled_by_id(roll_forward(prior, template=TEMPLATE))["D01"]
    assert d01.item.manual_override == Override.WAIVED
    assert d01.origin == ORIGIN_WAIVED
    assert "clear the override" in d01.note


def test_accepted_does_not_carry(prior):
    """Accepted judged one year's files; it must not pre-approve the next."""
    from dataclasses import replace

    from tracker.manifest import load_engagement_info, save_rules

    eng = prior
    seed_statuses(eng,
                   {"C01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    rows = [replace(row, manual_override=Override.ACCEPTED) if row.identifier == "C01" else row
            for row in load_manifest(eng)]
    save_rules(eng, rows, load_engagement_info(eng))       # the edit, saved in the app
    ensure(eng)

    c01 = rolled_by_id(roll_forward(eng))["C01"].item
    assert c01.manual_override == ""


def test_unreceived_rows_are_carried_with_a_flag(prior):
    c01 = rolled_by_id(roll_forward(prior))["C01"]
    assert c01.origin == ORIGIN_PRIOR
    assert Status.MISSING in c01.note and "confirm it still applies" in c01.note


# -------------------------------------------------------------- new requests ----


def test_unknown_template_rows_are_offered_not_added(prior):
    """The standard checklist does not get to pad a returning client's list."""
    report = roll_forward(prior, template=TEMPLATE)

    assert [r.item.identifier for r in report.rolled] == ["A01", "B01", "C01", "D01"]
    (offer,) = report.offered
    assert offer.item.identifier == "E01"
    assert offer.origin == ORIGIN_NEW
    assert "confirm it applies" in offer.note
    assert offer.item.period == "TY2026"


def test_include_new_adds_the_offers(prior):
    report = roll_forward(prior, template=TEMPLATE, include_new=True)
    assert [r.item.identifier for r in report.rolled] == ["A01", "B01", "C01", "D01", "E01"]
    assert report.offered == []
    assert rolled_by_id(report)["E01"].origin == ORIGIN_NEW


def test_a_template_row_differing_from_a_priors_only_in_case_is_the_same_row(prior, tmp_path):
    # The tenth reading: both were written, and the new list was refused as
    # a duplicate until a person edited it.
    from dataclasses import replace

    lowered = [replace(spec, identifier=spec.identifier.lower()) if spec.identifier == "A01" else spec for spec in TEMPLATE]
    report = roll_forward(prior, template=lowered, include_new=True)
    assert [r.item.identifier for r in report.rolled] == ["A01", "B01", "C01", "D01", "E01"]
    out = next_year(tmp_path, report)
    assert [i.identifier for i in load_manifest(out)] == ["A01", "B01", "C01", "D01", "E01"]


def test_offers_are_reported_without_becoming_requests(prior, tmp_path):
    """A person sees what was withheld in the reply and the command line,
    once; the created list holds none of it, and an offer they want is
    added in the editor."""
    report = roll_forward(prior, template=TEMPLATE)
    out = next_year(tmp_path, report)

    assert "E01" not in {i.identifier for i in load_manifest(out)}
    assert [o.item.identifier for o in report.offered] == ["E01"]
    assert report.offered[0].origin == ORIGIN_NEW


def test_unfiled_documents_from_last_year_are_surfaced(prior, tmp_path):
    """What arrived and fitted nowhere is exactly next year's gap."""
    from tests.conftest import seed_index
    from tracker.filer import NEEDS_REVIEW, IndexEntry

    seed_index(prior, [
        IndexEntry(received="2026-03-01", original_name="K-1 Redwood LP.pdf",
                   size_kb=12.0, digest="abc", identifier="",
                   prepared_location=f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/K-1 Redwood LP.pdf",
                   pbc_location="", decision=NEEDS_REVIEW,
                   reason=UNMATCHED),
    ])
    report = roll_forward(prior)
    assert any("K-1 Redwood LP.pdf" in s for s in report.unfiled_last_year)


def test_rollover_without_a_template_still_works(prior):
    report = roll_forward(prior)
    assert [r.item.identifier for r in report.rolled] == ["A01", "B01", "C01", "D01"]
    assert report.prior_year == 2025 and report.target_year == 2026


def test_explicit_target_year_wins(prior):
    report = roll_forward(prior, target_year=2030)
    assert rolled_by_id(report)["A01"].item.period == "TY2030"


def test_a_roll_into_the_same_or_an_earlier_year_is_refused(prior):
    # The twelfth reading: a roll into the prior's own year retired the
    # live engagement in favour of a copy of itself; an earlier one shifted
    # every period backwards.
    from tracker.manifest import ManifestError

    for year in (2025, 2024):
        with pytest.raises(ManifestError, match="after 2025"):
            roll_forward(prior, target_year=year)


def test_a_target_year_outside_the_bounds_is_refused_here_as_in_the_wizard(prior):
    # The thirteenth reading: decision 68 bounded the year the wizard takes
    # and left the rollover's flag unbounded, so --year 20265 shifted every
    # Period and every document name by eighteen thousand years and wrote
    # the folders under those names.
    from tracker.manifest import YEAR_MAX, YEAR_MIN, ManifestError

    for year in (YEAR_MIN - 1, YEAR_MAX + 1, 20265):
        with pytest.raises(ManifestError, match=f"between {YEAR_MIN} and {YEAR_MAX}"):
            roll_forward(prior, target_year=year)
    assert rolled_by_id(roll_forward(prior, target_year=YEAR_MAX))["A01"].item.period == f"TY{YEAR_MAX}"


# --------------------------------------------------------------- the workbook ----


def test_the_created_engagement_loads_back_from_the_record_and_the_report_explains_itself(prior, tmp_path):
    report = roll_forward(prior, template=TEMPLATE)
    out = next_year(tmp_path, report)

    items = {i.identifier: i for i in load_manifest(out)}
    assert items["A01"].period == "TY2026"
    assert items["A01"].expected_count == 3
    assert items["D01"].manual_override == Override.WAIVED
    # Fresh year: no scanner state carried over.
    assert items["A01"].status == "" and items["A01"].received_date is None

    origins = {r.item.identifier: r.origin for r in [*report.rolled, *report.offered]}
    assert origins["A01"] == ORIGIN_PRIOR
    assert origins["D01"] == ORIGIN_WAIVED
    assert origins["E01"] == ORIGIN_NEW


def test_prior_engagement_is_never_written_to(prior):
    """The prior year is read, never written: its record's bytes and its
    folder are as they were, because last year is finished with."""
    before = ledger.path_for(prior).read_bytes()
    listing = sorted(p.name for p in prior.iterdir())
    roll_forward(prior, template=TEMPLATE)
    assert ledger.path_for(prior).read_bytes() == before
    assert sorted(p.name for p in prior.iterdir()) == listing


def test_shift_years_leaves_digits_inside_longer_numbers_alone():
    # An account number is not a year, even when four of its digits look
    # like one.
    assert shift_years("Account 120250 statement TY2025", 1) == "Account 120250 statement TY2026"
    assert shift_years("Policy 2025-1234 for 2025", 1) == "Policy 2026-1234 for 2026"


def test_a_derived_year_check_is_not_carried_as_text(prior, tmp_path):
    # The prior's TY2025 rows had their year check derived from Period; the
    # rolled list gets TY2026 and derives again. The rolled row carries no
    # pattern of its own rather than last year's regex.
    report = roll_forward(prior)
    built = {r.item.identifier: r.item for r in report.rolled}
    assert built["C01"].date_pattern == "" and not built["C01"].date_pattern_derived
    assert built["A01"].date_pattern == r"(?i)\b2026\b"   # A01 typed its own pattern; it shifts and stays

    rows = {i.identifier: i for i in load_manifest(next_year(tmp_path, report))}
    assert rows["C01"].period == "TY2026"
    assert rows["C01"].date_pattern == r"(?i)\b2026\b" and rows["C01"].date_pattern_derived
    assert rows["A01"].date_pattern == r"(?i)\b2026\b" and not rows["A01"].date_pattern_derived


def test_a_keyword_the_prior_year_was_taught_is_carried_as_an_ordinary_one(prior, tmp_path):
    """The one moment a taught keyword becomes something typed.

    Last year somebody filed a parked document and typed "home lending";
    it lived in that engagement's record and nowhere else (decision 103).
    Next year's list is last year's list, so it comes forward as an
    ordinary Any Keyword - in next year's record, where the editor shows
    it and a person can edit it.
    """
    from tracker import store
    from tracker.locking import engagement_lock

    with engagement_lock(prior):
        ensure(prior)
        store.record(store.connect(), prior, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: "C01", ledger.KEYWORD_KEY: "home lending",
        }))
    assert {i.identifier: i.any_keywords
            for i in load_manifest(prior)}["C01"] == ("rental", "home lending")

    report = roll_forward(prior)
    assert rolled_by_id(report)["C01"].item.any_keywords == ("rental", "home lending")

    new = next_year(tmp_path, report)
    written = {row["identifier"]: tuple(row["any_keywords"])
               for row in store.rules(store.connect(), new)}          # typed, as stored
    assert written["C01"] == ("rental", "home lending")
    assert store.learned_keywords(store.connect(), new) == {}


def test_the_rollover_command_line_records_where_the_prior_year_really_is(prior):
    """A relative prior on the command line is resolved before it is written
    as Rolled From; the scheduled run's working folder is not this one."""
    import subprocess
    import sys
    from pathlib import Path

    from tracker.manifest import load_engagement_info

    repo = Path(__file__).resolve().parent.parent
    subprocess.run(
        [sys.executable, "-m", "tracker.rollover", prior.name, "Smith TY2026"],
        cwd=prior.parent, check=True, capture_output=True,
        env={**__import__("os").environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"},
    )
    info = load_engagement_info(prior.parent / "Smith TY2026")
    assert Path(info.rolled_from).is_absolute() and Path(info.rolled_from) == prior.resolve()


def test_the_rollover_carries_the_catalog_the_list_was_cut_from(tmp_path):
    """Decision 86: a returning client files the same return next year, so
    the Form cell carries; a prior that never recorded one carries a blank."""
    from tracker.manifest import EngagementInfo
    from tracker.rollover import carry_engagement_info

    carried = carry_engagement_info(
        EngagementInfo(client="John Smith", link="https://drive.example/old", form="1120S"),
        rolled_from=str(tmp_path),
    )
    assert carried.form == "1120S" and carried.link == ""
    assert carry_engagement_info(EngagementInfo(client="John Smith"),
                                 rolled_from=str(tmp_path)).form == ""


def test_the_rollover_command_line_writes_the_carried_form_into_next_year(tmp_path):
    """End to end: the prior's details say which catalog, and so do next
    year's - the details the app shows."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    from tracker.manifest import load_engagement_info

    prior = make_engagement(tmp_path / "Smith Family 2025", PRIOR,
                            EngagementInfo(client="John Smith", form="1040"), scaffold=False)
    repo = Path(__file__).resolve().parent.parent
    subprocess.run(
        [sys.executable, "-m", "tracker.rollover", prior.name, "Smith TY2026"],
        cwd=prior.parent, check=True, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"},
    )
    info = load_engagement_info(prior.parent / "Smith TY2026")
    assert info.form == "1040" and info.client == "John Smith"
    assert list((prior.parent / "Smith TY2026").glob("*.xlsx")) == []


def run_the_command_line(monkeypatch, argv, stdout):
    """``python -m tracker.rollover`` in this process, its console ``stdout``:
    the exit code, with a stream a test can choose the encoding of."""
    import runpy
    import sys
    import warnings

    monkeypatch.setattr(sys, "argv", ["tracker.rollover", *argv])
    monkeypatch.setattr(sys, "stdout", stdout)
    try:
        with warnings.catch_warnings():
            # This file imports the module; running its source again as
            # __main__ is the point, and runpy's note about it is not.
            warnings.filterwarnings("ignore", message="'tracker.rollover' found in sys.modules",
                                    category=RuntimeWarning)
            runpy.run_module("tracker.rollover", run_name="__main__")
    except SystemExit as exc:
        return exc.code if isinstance(exc.code, int) else 1
    return 0


def test_the_rollover_command_line_finishes_its_work_on_a_console_that_cannot_print_an_arrow(
    prior, monkeypatch,
):
    """Decision 108: the report carries an arrow; a cp1252 console (a stock
    Windows prompt, the scheduler's) cannot encode one. It used to die
    after the record was written and before the folders were made, and a
    second run into that folder was refused."""
    import io

    from tracker.manifest import load_engagement_info
    from tracker.scaffold import PBC_DIR_NAME, README_NAME, SHARED_DIR_NAME

    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    target = prior.parent / "Smith TY2026"
    code = run_the_command_line(
        monkeypatch, [str(prior), str(target), "--form", "1040", "--scaffold"], console,
    )
    console.flush()
    shown = console.buffer.getvalue().decode("cp1252")

    assert code == 0, shown
    assert load_engagement_info(target).rolled_from == str(prior.resolve())
    assert (target / SHARED_DIR_NAME).is_dir()
    assert (target / SHARED_DIR_NAME / PBC_DIR_NAME).is_dir()
    assert (target / PREPARED_DIR_NAME).is_dir()
    assert (target / SHARED_DIR_NAME / README_NAME).is_file()
    assert "2025 \\u2192 2026" in shown            # the arrow, as its escape


def test_the_rollover_command_line_scaffolds_before_it_reports(prior, monkeypatch):
    """Whatever goes wrong with the report goes wrong after the record AND
    the folders are there - and the error still surfaces."""
    import builtins
    import io

    from tracker.manifest import load_engagement_info
    from tracker.scaffold import README_NAME, SHARED_DIR_NAME

    def refuse_to_print(*args, **kwargs):
        raise RuntimeError("the console is broken")

    monkeypatch.setattr(builtins, "print", refuse_to_print)
    target = prior.parent / "Smith TY2026"
    with pytest.raises(RuntimeError, match="the console is broken"):
        run_the_command_line(monkeypatch, [str(prior), str(target), "--scaffold"], io.StringIO())

    assert load_engagement_info(target).rolled_from == str(prior.resolve())
    assert (target / SHARED_DIR_NAME / README_NAME).is_file()
    assert (target / PREPARED_DIR_NAME).is_dir()


# ------------------------------------------- a row per issuer (decision 93) ----


def test_the_rollover_carries_a_row_per_issuer(tmp_path):
    """Issuer rows are ordinary rows, so nothing in the rollover knows about
    them - and that is the claim: a client who was a partner in two
    partnerships last year is asked for both again, by name."""
    from tracker.templates import issuer_row, item_from_spec, template_items

    k1 = next(i for i in template_items("1040", year=2025) if i.identifier == "F01")
    eng = make_engagement(tmp_path / "Smith Family 2025", [
        k1,
        item_from_spec(issuer_row("F02", "Ashford Holdings LP")),
        item_from_spec(issuer_row("F03", "Birch Lane Partners")),
    ], scaffold=False)
    seed_statuses(eng, {
        "F02": StatusUpdate(status=Status.RECEIVED, file_count=1,
                            received_date=dt.date(2026, 3, 1)),
    })

    rolled = rolled_by_id(roll_forward(eng))

    assert set(rolled) == {"F01", "F02", "F03"}
    assert rolled["F02"].item.document == "Schedule K-1 - Ashford Holdings LP"
    assert rolled["F02"].item.required_keywords == ("Ashford Holdings LP",)
    assert rolled["F03"].item.required_keywords == ("Birch Lane Partners",)
    assert rolled["F02"].item.period == "TY2026"
    # Last year's judgement of last year's files is not carried (decision 10).
    assert rolled["F02"].item.status == "" and rolled["F02"].item.received_date is None

    # And the list it makes reads back as a list: nesting names would be
    # refused here, these are not.
    written = next_year(tmp_path, roll_forward(eng))
    assert [i.identifier for i in load_manifest(written)] == ["F01", "F02", "F03"]


# ------------------------------------------------ through the app (d104) ----


def test_the_rollover_carries_rules_engagement_details_and_learned_keywords_into_next_years_record(
    capsys, tmp_path, monkeypatch,
):
    """The whole of a returning client, through the API: last year's rows
    with a keyword a filing taught, its form and its client carried, its
    link and due date left for this year, Rolled From set - and no
    spreadsheet anywhere under the root."""
    import tracker.api as api
    from tests.test_api import run
    from tracker import store
    from tracker.locking import engagement_lock
    from tracker.manifest import load_engagement_info
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    demo_root = tmp_path / "Clients"                # recorded the way the app records it
    demo_root.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(demo_root)

    spec = {"name": "Smith 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/old", "due": "2026-04-15",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    prior = demo_root / "Smith 2025"
    with engagement_lock(prior):
        ensure(prior)
        store.record(store.connect(), prior, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: "C01", ledger.KEYWORD_KEY: "home lending",
        }))

    code, payload = run(capsys, "rollover", stdin={"prior": "Smith 2025", "year": 2026})
    assert code == 0, payload
    new = demo_root / payload["created"]

    rows = {i.identifier: i for i in load_manifest(new)}
    assert "home lending" in rows["C01"].any_keywords
    assert rows["C01"].period == "TY2026" and rows["C01"].date_pattern_derived
    assert store.learned_keywords(store.connect(), new) == {}       # carried as typed, not taught
    info = load_engagement_info(new)
    assert info.form == "1040" and info.client == "John Smith"
    assert info.link == "" and info.due is None
    assert info.rolled_from == str(prior)
    assert list(demo_root.rglob("*.xlsx")) == []
