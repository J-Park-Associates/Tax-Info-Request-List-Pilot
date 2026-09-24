"""Tests for tracker/rollover.py — last year beats the generic checklist.

The rule under test throughout: for a returning client, prior-year data wins.
The form template may fill a blank, never overwrite a value, and never
silently drop something the client actually had.
"""

import datetime as dt

import pytest

from tests.conftest import ensure, make_engagement, seed_statuses
from tracker import ledger
from tracker.layout import inbox_of, root_of
from tracker.manifest import (
    EngagementInfo,
    ManifestError,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    create_engagement,
    load_manifest,
    summarize,
)
from tracker.rollover import (
    NEW_NOT_ASKED_NOTE,
    NOT_APPLICABLE_NOTE,
    ORIGIN_NEW,
    ORIGIN_NOT_APPLICABLE,
    ORIGIN_PRIOR,
    PREVIOUS_NOT_APPLICABLE_HEADING,
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
        manual_override=Override.NOT_APPLICABLE, override_reason="no marketplace plan",
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
def prior(tmp_path, monkeypatch):
    """Last year's return, scanned: A01 received 3 files, C01 never came.

    The clients root is recorded the way the app records it, because a
    return keeps its name every year under the same household (decision
    125) and the store keys a folder by its path below that root: with no
    root written down it keys by the folder's parent, and this year's
    return and next year's would be one row.
    """
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    # The settings beside the root, not inside it: a root that holds the
    # app's settings is refused (decision 137).
    settings = tmp_path.parent / f"{tmp_path.name}-app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    settings.mkdir(exist_ok=True)
    set_clients_root(tmp_path)
    eng = make_engagement(tmp_path, PRIOR, household="Smith Family", scaffold=False)
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


def next_year(tmp_path, report, household="Smith Family", name="1040 - Test Client"):
    """Next year's return, created from the rollover's rows the way the API
    and the command line create it: into the record, no scaffold - under
    the same household, the same name, the year above (decision 125)."""
    from tracker.layout import return_dir_for

    folder = return_dir_for(tmp_path, household, report.target_year or 2026, name)
    folder.mkdir(parents=True, exist_ok=True)
    create_engagement(folder, report.items)
    return folder


def rolled_into(prior, year):
    """Where the rollover puts next year's return: the same household, the
    same name, the year above (decision 125)."""
    from tracker.layout import household_name_of, return_dir_for, root_of

    return return_dir_for(root_of(prior), household_name_of(prior), year, prior.name)


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
    eng = make_engagement(root_of(prior), sparse, household="Sparse Family", scaffold=False)

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


def test_not_applicable_rolls_forward_under_its_own_heading_with_the_fresh_decision_note_and_accepted_does_not(prior):
    """Decision 10 stands and decision 116 groups it: the row carries the
    override and its reason, under its own origin with last year's label
    and the two things a person may do; it is not among the carried rows.
    Accepted is the other half, below."""
    from tracker.manifest import override_label

    report = roll_forward(prior, template=TEMPLATE)
    d01 = rolled_by_id(report)["D01"]
    assert d01.item.manual_override == Override.NOT_APPLICABLE
    assert d01.item.override_reason == "no marketplace plan"
    assert d01.origin == ORIGIN_NOT_APPLICABLE
    assert d01.note == NOT_APPLICABLE_NOTE.format(label="Not Applicable in TY2025")
    assert "decide afresh" in d01.note and "clear the override in the editor" in d01.note
    assert override_label(d01.item) == "Not Applicable in TY2026"        # this year's row, this year's label
    assert [r.item.identifier for r in report.not_applicable] == ["D01"]
    assert "D01" not in [r.item.identifier for r in report.carried]
    assert {r.origin for r in report.carried} == {ORIGIN_PRIOR}


def test_accepted_does_not_carry(prior):
    """Accepted judged one year's files; it must not pre-approve the next."""
    from dataclasses import replace

    from tracker.manifest import load_engagement_info, save_rules

    eng = prior
    seed_statuses(eng,
                   {"C01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    rows = [replace(row, manual_override=Override.ACCEPTED, override_reason="client confirmed")
            if row.identifier == "C01" else row
            for row in load_manifest(eng)]
    save_rules(eng, rows, load_engagement_info(eng))       # the edit, saved in the app
    ensure(eng)

    c01 = rolled_by_id(roll_forward(eng))["C01"].item
    assert c01.manual_override == "" and c01.override_reason == ""      # nor does its reason


def test_unreceived_rows_are_carried_with_a_flag(prior):
    c01 = rolled_by_id(roll_forward(prior))["C01"]
    assert c01.origin == ORIGIN_PRIOR
    assert Status.MISSING in c01.note and "confirm it still applies" in c01.note


# -------------------------------------------------------------- new requests ----


def test_unknown_template_rows_are_added_as_not_asked(prior):
    """Decision 142 rewords decision 9: a catalog row the client never had
    is on the return, but nobody asks for it - it pads nothing the client
    sees, and a document that arrives for it files there."""
    report = roll_forward(prior, template=TEMPLATE)

    assert [r.item.identifier for r in report.rolled] == ["A01", "B01", "C01", "D01", "E01"]
    new = rolled_by_id(report)["E01"]
    assert new.origin == ORIGIN_NEW and new.note == NEW_NOT_ASKED_NOTE
    assert new.item.asked is False and new.item.period == "TY2026"
    assert all(r.item.asked for r in report.rolled if r.item.identifier != "E01")
    assert not hasattr(report, "offered")


def test_a_template_row_differing_from_a_priors_only_in_case_is_the_same_row(prior, tmp_path):
    # The tenth reading: both were written, and the new list was refused as
    # a duplicate until a person edited it.
    from dataclasses import replace

    lowered = [replace(spec, identifier=spec.identifier.lower()) if spec.identifier == "A01" else spec for spec in TEMPLATE]
    report = roll_forward(prior, template=lowered)
    assert [r.item.identifier for r in report.rolled] == ["A01", "B01", "C01", "D01", "E01"]
    out = next_year(tmp_path, report)
    assert [i.identifier for i in load_manifest(out)] == ["A01", "B01", "C01", "D01", "E01"]


def test_rows_added_as_not_asked_are_on_the_list_and_never_asked_for(prior, tmp_path):
    """The created list holds the new row, not asked: a person sets Asked in
    the editor to ask for it."""
    report = roll_forward(prior, template=TEMPLATE)
    out = next_year(tmp_path, report)

    items = {i.identifier: i for i in load_manifest(out)}
    assert items["E01"].asked is False
    assert summarize(items.values()).total == 3              # A01, B01, C01; D01 is set aside


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
    assert items["D01"].manual_override == Override.NOT_APPLICABLE
    # Fresh year: no scanner state carried over.
    assert items["A01"].status == "" and items["A01"].received_date is None

    origins = {r.item.identifier: r.origin for r in report.rolled}
    assert origins["A01"] == ORIGIN_PRIOR
    assert origins["D01"] == ORIGIN_NOT_APPLICABLE
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
        [sys.executable, "-m", "tracker.rollover", prior.name, "--year", "2026"],
        cwd=prior.parent, check=True, capture_output=True,
        env={**__import__("os").environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"},
    )
    info = load_engagement_info(rolled_into(prior, 2026))
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


def test_the_carry_clears_both_of_last_years_dates(tmp_path):
    """Decision 117: a statutory date belongs to its year, and so does the
    target the firm sets against it. Neither carries - the new year's come
    from the form's own table when the engagement is created."""
    import datetime as dt

    from tracker.manifest import EngagementInfo
    from tracker.rollover import carry_engagement_info

    carried = carry_engagement_info(
        EngagementInfo(client="John Smith", due=dt.date(2026, 4, 10),
                       filing_deadline=dt.date(2026, 4, 15), form="1040"),
        rolled_from=str(tmp_path),
    )
    assert carried.due is None and carried.filing_deadline is None
    assert carried.client == "John Smith" and carried.form == "1040"


def test_the_rollover_command_line_writes_the_carried_form_into_next_year(tmp_path):
    """End to end: the prior's details say which catalog, and so do next
    year's - the details the app shows."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    from tracker.manifest import load_engagement_info

    prior = make_engagement(tmp_path, PRIOR,
                            EngagementInfo(client="John Smith", form="1040"),
                            household="Smith Family", scaffold=False)
    repo = Path(__file__).resolve().parent.parent
    subprocess.run(
        [sys.executable, "-m", "tracker.rollover", prior.name, "--year", "2026"],
        cwd=prior.parent, check=True, capture_output=True,
        env={**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"},
    )
    rolled = rolled_into(prior, 2026)
    info = load_engagement_info(rolled)
    assert info.form == "1040" and info.client == "John Smith"
    assert list(rolled.glob("*.xlsx")) == []


def test_the_rollover_command_line_fills_the_new_years_dates_from_the_form(tmp_path):
    """Decision 123: the command line defaults the two dates the way the
    app's Roll Forward does.

    The carry clears last year's on purpose, and nothing on this path
    refilled them - so a rolled engagement had no Due Date and every draft
    was stage 1, months after the tax year. A prior with no form and no
    ``--form`` still fills nothing: the no-guess rule is unchanged.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    from tracker.manifest import load_engagement_info
    from tracker.templates import ask_by_for, filing_deadline_for

    repo = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"}

    prior = make_engagement(tmp_path, PRIOR,
                            EngagementInfo(client="John Smith", form="1040"),
                            household="Smith Family", scaffold=False)
    subprocess.run(
        [sys.executable, "-m", "tracker.rollover", prior.name, "--year", "2026"],
        cwd=prior.parent, check=True, capture_output=True, env=env,
    )
    info = load_engagement_info(rolled_into(prior, 2026))
    assert info.filing_deadline == filing_deadline_for("1040", 2026)
    assert info.due == ask_by_for(info.filing_deadline)

    # No form recorded and none asked for: a statutory date is never guessed.
    unknown = make_engagement(tmp_path, PRIOR, EngagementInfo(client="Jane Jones"),
                              household="Jones Family", return_name="1040 - Jones",
                              scaffold=False)
    subprocess.run(
        [sys.executable, "-m", "tracker.rollover", unknown.name, "--year", "2026"],
        cwd=unknown.parent, check=True, capture_output=True, env=env,
    )
    rolled = load_engagement_info(rolled_into(unknown, 2026))
    assert rolled.filing_deadline is None and rolled.due is None


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

    from tracker.layout import inbox_of, originals_of
    from tracker.manifest import load_engagement_info
    from tracker.scaffold import README_NAME

    console = io.TextIOWrapper(io.BytesIO(), encoding="cp1252")
    code = run_the_command_line(
        monkeypatch, [str(prior), "--year", "2026", "--form", "1040", "--scaffold"], console,
    )
    console.flush()
    shown = console.buffer.getvalue().decode("cp1252")

    target = rolled_into(prior, 2026)
    assert code == 0, shown
    assert load_engagement_info(target).rolled_from == str(prior.resolve())
    # The inbox is the household's and does not change from one year to the
    # next; what the roll adds on the client side is the year's folder.
    assert inbox_of(target) == inbox_of(prior)
    assert originals_of(target).is_dir() and originals_of(target).name == "2026"
    assert (target / PREPARED_DIR_NAME).is_dir()
    assert (inbox_of(target) / README_NAME).is_file()
    assert "2025 \\u2192 2026" in shown            # the arrow, as its escape


def test_the_rollover_command_line_prints_previous_year_not_applicable_after_carried_and_new(
    prior, monkeypatch,
):
    import io

    console = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    target = rolled_into(prior, 2026)
    code = run_the_command_line(
        monkeypatch, [str(prior), "--year", "2026", "--form", "1040"], console,
    )
    console.flush()
    shown = console.buffer.getvalue().decode("utf-8")
    assert code == 0, shown

    heading = shown.index(PREVIOUS_NOT_APPLICABLE_HEADING)
    assert shown.index("CARRIED A01") < shown.index("NEW     E01") < heading
    assert "Not Applicable in TY2026  D01" in shown[heading:]
    assert NOT_APPLICABLE_NOTE.format(label="Not Applicable in TY2025") in shown[heading:]
    assert "WAIVED" not in shown
    # The row is on next year's list, set aside, not in the active rows.
    items = {i.identifier: i for i in load_manifest(target)}
    assert items["D01"].manual_override == Override.NOT_APPLICABLE


def test_the_rollover_command_line_scaffolds_before_it_reports(prior, monkeypatch):
    """Whatever goes wrong with the report goes wrong after the record AND
    the folders are there - and the error still surfaces."""
    import builtins
    import io

    from tracker.layout import inbox_of
    from tracker.manifest import load_engagement_info
    from tracker.scaffold import README_NAME

    def refuse_to_print(*args, **kwargs):
        raise RuntimeError("the console is broken")

    monkeypatch.setattr(builtins, "print", refuse_to_print)
    target = rolled_into(prior, 2026)
    with pytest.raises(RuntimeError, match="the console is broken"):
        run_the_command_line(monkeypatch, [str(prior), "--year", "2026", "--scaffold"],
                             io.StringIO())

    assert load_engagement_info(target).rolled_from == str(prior.resolve())
    assert (inbox_of(target) / README_NAME).is_file()
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
    capsys, short_root, tmp_path, monkeypatch,
):
    """The whole of a returning client, through the API: last year's rows
    with a keyword a filing taught, its form and its client carried, its
    link and due date left for this year, Rolled From set - and no
    spreadsheet anywhere under the root."""
    import tracker.api as api
    from tests.test_api import run
    from tracker import store
    from tracker.layout import return_dir_for
    from tracker.locking import engagement_lock
    from tracker.manifest import load_engagement_info
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    # A short root, recorded the way the app records it: the whole 1040
    # core list has to fit inside what Windows will open (decision 125).
    demo_root = short_root
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(demo_root)

    spec = {"household": "Smith Family", "return_name": "1040 - Smith", "form": "1040",
            "client": "John Smith", "link": "https://drive.example/old", "due": "2026-04-15",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    prior = return_dir_for(demo_root, "Smith Family", 2025, "1040 - Smith")
    with engagement_lock(prior):
        ensure(prior)
        store.record(store.connect(), prior, ledger.new(ledger.KEYWORD_LEARNED, **{
            ledger.IDENTIFIER_KEY: "C01", ledger.KEYWORD_KEY: "home lending",
        }))

    code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
    assert code == 0, payload
    new = return_dir_for(demo_root, "Smith Family", 2026, "1040 - Smith")

    rows = {i.identifier: i for i in load_manifest(new)}
    assert "home lending" in rows["C01"].any_keywords
    assert rows["C01"].period == "TY2026" and rows["C01"].date_pattern_derived
    assert store.learned_keywords(store.connect(), new) == {}       # carried as typed, not taught
    info = load_engagement_info(new)
    assert info.form == "1040" and info.client == "John Smith"
    # The inbox is the household's and does not change from one year to the
    # next, so its link is refilled rather than left for somebody to paste.
    assert info.link == "https://drive.example/old"
    # Neither of last year's dates carries: the new year's are the form's
    # own, so the reminder's ladder works from the first draft (decision 117).
    from tracker.templates import ask_by_for, filing_deadline_for

    assert info.filing_deadline == filing_deadline_for("1040", 2026)
    assert info.due == ask_by_for(info.filing_deadline)
    assert info.rolled_from == str(prior)
    assert list(demo_root.rglob("*.xlsx")) == []


# ------------------------------------------- the target is the layout's ----


def test_rollover_rolls_a_return_into_the_next_years_folder_of_the_same_household_under_the_same_name(
    capsys, short_root, tmp_path, monkeypatch,
):
    """**The target is computed, never typed** (decision 125). A return
    keeps its folder name every year, under the same household, so neither
    the API nor the command line takes a target folder: they are given the
    prior and the year, and the layout says where it goes.
    """
    import os
    import subprocess
    import sys
    from pathlib import Path

    import tracker.api as api
    from tests.test_api import run
    from tracker.layout import household_of, originals_of, return_dir_for
    from tracker.manifest import load_engagement_info
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    demo_root = short_root
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(demo_root)
    assert run(capsys, "create", stdin={
        "household": "Park Family", "return_name": "1040 - John Park", "form": "1040",
        "client": "John", "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]})[0] == 0
    prior = return_dir_for(demo_root, "Park Family", 2025, "1040 - John Park")

    code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
    assert code == 0, payload
    target = return_dir_for(demo_root, "Park Family", 2026, "1040 - John Park")

    assert target.is_dir()
    assert payload["created"] == "Park Family 2026 1040 - John Park"
    assert household_of(target) == household_of(prior)          # the same household
    assert target.name == prior.name                            # the same name
    assert load_engagement_info(target).return_name == "1040 - John Park"
    assert load_engagement_info(target).tax_year == 2026
    # The client side gains the year's folder and keeps the one inbox.
    assert originals_of(target).is_dir() and originals_of(target).name == "2026"
    assert inbox_of(target) == inbox_of(prior)

    # The command line takes no target either: the prior and the year.
    repo = Path(__file__).resolve().parent.parent
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8",
           ENV_SETTINGS_DIR: str(tmp_path / "app")}
    done = subprocess.run(
        [sys.executable, "-m", "tracker.rollover", str(target), "--year", "2027"],
        cwd=repo, capture_output=True, text=True, encoding="utf-8", env=env,
    )
    assert done.returncode == 0, done.stdout + done.stderr
    assert return_dir_for(demo_root, "Park Family", 2027, "1040 - John Park").is_dir()


def test_rollover_refills_the_greeting_and_the_link_from_the_household_where_blank(
    capsys, short_root, tmp_path, monkeypatch,
):
    """The inbox is the household's and does not change from one year to
    the next, so a rolled return whose prior never carried a greeting or a
    link gets the household's rather than a blank somebody has to notice.
    """
    from dataclasses import replace

    from tests.test_api import run
    from tracker.layout import return_dir_for
    from tracker.manifest import load_engagement_info, save_rules
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    demo_root = short_root
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(demo_root)
    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John & Maria",
        "link": "https://drive.example/park", "return_name": "1120S - Park Landscaping",
        "client": "", "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    prior = return_dir_for(demo_root, "Park Family", 2025, "1120S - Park Landscaping")
    # The prior's own greeting and link cleared, the way a record written
    # before the household had either would read.
    before = load_engagement_info(prior)
    save_rules(prior, load_manifest(prior), replace(before, client="", link=""))
    assert load_engagement_info(prior).client == "" and load_engagement_info(prior).link == ""

    code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
    assert code == 0, payload

    rolled = load_engagement_info(return_dir_for(demo_root, "Park Family", 2026,
                                                 "1120S - Park Landscaping"))
    assert rolled.client == "John & Maria"
    assert rolled.link == "https://drive.example/park"

    # And a greeting the prior does carry is not written over by the
    # household's: the return's own details win.
    save_rules(prior, load_manifest(prior),
               replace(load_engagement_info(prior), client="Park Landscaping LLC"))
    code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2027})
    assert code == 0, payload
    kept = load_engagement_info(return_dir_for(demo_root, "Park Family", 2027,
                                               "1120S - Park Landscaping"))
    assert kept.client == "Park Landscaping LLC"


# ------------------------------- the household rolls as a household (d126) ----


PARK = "Park Family"
#: Three short rows: the whole household-year has to fit inside what
#: Windows will open, and the rollover measures it before it writes.
W2 = [RequestItem(identifier="A01", document="W-2 Wage Statements", period="TY2026",
                  allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("w-2",))]
TB = [RequestItem(identifier="B01", document="Trial Balance", period="TY2026",
                  allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("trial balance",))]


@pytest.fixture
def park(short_root, tmp_path, monkeypatch):
    """One household with three returns in one open year, 2026.

    The clients root is recorded the way the app records it, because the
    store keys a return by its path *below* that root: with no root
    written down it keys by the folder's parent, and this year's return
    and next year's would be one row. Short, because the deepest working
    copy of the whole household has to fit in a path Windows will open.
    """
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    set_clients_root(short_root)
    john = make_engagement(short_root, W2, household=PARK, year=2026,
                           return_name="1040 - John Park",
                           members=("John Park", "Maria Park"), contact="John & Maria",
                           link="https://drive.example/park")
    sofia = make_engagement(short_root, W2, household=PARK, year=2026,
                            return_name="1040 - Sofia Park")
    llc = make_engagement(short_root, TB, household=PARK, year=2026,
                          return_name="1120S - Park Landscaping LLC")
    return short_root, john, sofia, llc


def _household(root):
    from tracker.layout import private_household_dir

    return private_household_dir(root, PARK)


def test_the_household_rollover_rolls_every_ticked_return_into_one_new_year_under_its_own_lock(park):
    """Roll Forward is the household's, not one return's (decision 126):
    every ticked return goes into the one new year, each under its own
    lock and by the same carry rule, the year's folders are made once, and
    the client's inbox README lists the new year's lists the day it is
    done."""
    from tracker.layout import originals_of, return_dir_for
    from tracker.locking import lock_status
    from tracker.manifest import load_engagement_info
    from tracker.rollover import ReturnPlan, roll_household
    from tracker.scaffold import README_NAME

    root, john, sofia, llc = park
    before = {one: len(ledger.read_events(one)) for one in (john, sofia, llc)}

    done = roll_household(_household(root), target_year=2027,
                          plans=[ReturnPlan(prior=one) for one in (john, sofia, llc)])

    assert [was.name for was, _, _ in done.rolled] == [
        "1040 - John Park", "1040 - Sofia Park", "1120S - Park Landscaping LLC"]
    assert done.skipped == [] and done.retired == []
    for was, created, _ in done.rolled:
        assert created == return_dir_for(root, PARK, 2027, was.name)
        info = load_engagement_info(created)
        assert (info.household, info.tax_year, info.return_name) == (PARK, 2027, was.name)
        # The greeting and the inbox link are the household's: the inbox
        # does not change from one year to the next.
        assert info.client == "John & Maria"
        assert info.link == "https://drive.example/park"
        assert info.rolled_from == str(was)
        # Its own record, one event: one lock and one transaction per
        # return, exactly as a create is.
        assert len(ledger.read_events(created)) == 1
        assert lock_status(created) is None
        # And nothing was written to the prior: it is read-only history,
        # retired by its successor's Rolled From.
        assert len(ledger.read_events(was)) == before[was]

    # The year's folders are made once, by the first scaffold; the rest
    # find them.
    assert originals_of(return_dir_for(root, PARK, 2027, "1040 - John Park")).is_dir()
    readme = (inbox_of(john) / README_NAME).read_text(encoding="utf-8")
    for name in ("1040 - John Park", "1040 - Sofia Park", "1120S - Park Landscaping LLC"):
        assert name in readme
    assert "2027" in readme


def test_a_return_left_out_of_the_household_rollover_is_retired_and_the_household_has_one_open_year(park):
    """A return nobody ticks is not merely skipped: it is set inactive by
    one details edit, so the household has exactly one open year again and
    its inbox goes on being sorted."""
    from tracker.households import open_years
    from tracker.manifest import load_engagement_info
    from tracker.registry import discover_engagements
    from tracker.rollover import ReturnPlan, roll_household
    from tracker.runner import TWO_OPEN_YEARS, run_household

    root, john, sofia, llc = park
    was = len(ledger.read_events(sofia))

    done = roll_household(_household(root), target_year=2027,
                          plans=[ReturnPlan(prior=john), ReturnPlan(prior=llc)])

    assert done.retired == [sofia]
    assert load_engagement_info(sofia).active is False
    # One event, carrying the one field that moved and no row at all.
    events = ledger.read_events(sofia)
    assert len(events) == was + 1
    assert events[-1][ledger.EVENT_KEY] == ledger.RULES_CHANGED
    assert events[-1][ledger.INFO_KEY] == {"active": False}
    assert not events[-1].get(ledger.RULES_KEY)

    registry = discover_engagements(root)
    returns = registry.by_household()[_household(root)]
    assert open_years(returns) == [2027]
    # And the next pass sorts: nothing warns about two open years.
    runs = run_household(_household(root), returns, root=root, registry=registry)
    said = TWO_OPEN_YEARS.split("(")[0]
    assert [w for run in runs for w in run.warnings if said in w] == []


def test_a_household_with_two_open_years_refuses_to_roll_until_one_is_retired(park):
    """There is no one year to roll: a person retires a year in the editor
    first, exactly as the pass refuses to sort on two."""
    from tracker.rollover import ROLLOVER_TWO_OPEN_YEARS, ReturnPlan, roll_household

    root, john, sofia, llc = park
    make_engagement(root, W2, household=PARK, year=2027, return_name="1040 - Next Year",
                    scaffold=False)

    with pytest.raises(ManifestError, match="two open years"):
        roll_household(_household(root), target_year=2028, plans=[ReturnPlan(prior=john)])
    assert ROLLOVER_TWO_OPEN_YEARS.format(years="2026, 2027").endswith(
        "retire one in the editor before rolling forward")


def test_one_returns_refusal_does_not_undo_the_others_and_is_said(park):
    """Each return is its own decision on its own record: the second plan
    targets a folder that already exists, and the first and the third are
    rolled all the same."""
    from tracker.layout import return_dir_for
    from tracker.rollover import ReturnPlan, roll_household

    root, john, sofia, llc = park
    return_dir_for(root, PARK, 2027, "1040 - Sofia Park").mkdir(parents=True)

    done = roll_household(_household(root), target_year=2027,
                          plans=[ReturnPlan(prior=one) for one in (john, sofia, llc)])

    assert [was.name for was, _, _ in done.rolled] == [
        "1040 - John Park", "1120S - Park Landscaping LLC"]
    [(refused, why)] = done.skipped
    assert refused == sofia and "already exists" in why
    assert return_dir_for(root, PARK, 2027, "1040 - John Park").is_dir()
    assert return_dir_for(root, PARK, 2027, "1120S - Park Landscaping LLC").is_dir()
    # A refusal retires nothing either: every plan was ticked.
    assert done.retired == []


def test_the_household_rollover_makes_no_change_under_the_client_tree_but_the_new_year_folder(park):
    """No permission is changed and no client file is touched: what a roll
    adds on the client side is one folder for the new year, under the same
    grant the household was shared with once."""
    from tracker.layout import CLIENTS_TREE, client_household_dir, originals_dir_for
    from tracker.rollover import ReturnPlan, roll_household

    root, john, sofia, llc = park
    tree = root / CLIENTS_TREE
    before = set(tree.rglob("*"))

    roll_household(_household(root), target_year=2027,
                   plans=[ReturnPlan(prior=one) for one in (john, sofia, llc)])

    after = set(tree.rglob("*"))
    assert after - before == {originals_dir_for(root, PARK, 2027)}
    assert before - after == set()
    assert client_household_dir(root, PARK).is_dir()


def test_the_command_line_rolls_a_household_and_prints_rolled_not_rolled_and_retired(
    park, monkeypatch,
):
    """One command line, two forms (decision 126): a household's folder
    rolls the household's year, told apart from a return by what the path
    holds. It prints what rolled, what refused with its sentence, and what
    it retired."""
    import io

    from tracker.layout import return_dir_for
    from tracker.manifest import load_engagement_info
    from tracker.rollover import NOT_ROLLED_HEADING, RETIRED_HEADING, ROLLED_HEADING

    root, john, sofia, llc = park
    return_dir_for(root, PARK, 2027, "1120S - Park Landscaping LLC").mkdir(parents=True)

    console = io.TextIOWrapper(io.BytesIO(), encoding="utf-8")
    code = run_the_command_line(monkeypatch, [
        str(_household(root)), "--year", "2027",
        "--only", "1040 - John Park", "--only", "1120S - Park Landscaping LLC",
    ], console)
    console.flush()
    shown = console.buffer.getvalue().decode("utf-8")

    assert code == 0, shown
    assert shown.index(ROLLED_HEADING) < shown.index(NOT_ROLLED_HEADING)
    assert shown.index(NOT_ROLLED_HEADING) < shown.index(RETIRED_HEADING.format(year=2027))
    assert "1040 - John Park" in shown and "already exists" in shown
    assert return_dir_for(root, PARK, 2027, "1040 - John Park").is_dir()
    # Sofia was not named, so she is retired for the year and told so.
    assert load_engagement_info(sofia).active is False
    assert "it was not rolled into 2027" in shown


# --------------------------------------------- decision 142: accepted, not asked ----


def test_the_rollover_carries_asked_and_named_and_asks_what_arrived(tmp_path, monkeypatch):
    """A ``named=no`` row stays no (the carry dropped it until decision 142);
    a not-asked row that received a document is asked next year; one that
    received nothing stays not asked; and a catalog row the client never
    had is added as not asked."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    # The settings beside the root, not inside it: a root that holds the
    # app's settings is refused (decision 137).
    settings = tmp_path.parent / f"{tmp_path.name}-app"
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    settings.mkdir(exist_ok=True)
    set_clients_root(tmp_path)
    rows = [
        RequestItem(identifier="A01", document="W-2", period="TY2025", required_keywords=("W-2",)),
        RequestItem(identifier="D01", document="Donation receipts", period="TY2025",
                    any_keywords=("donation receipt",), named=False),
        RequestItem(identifier="E01", document="1099-R", period="TY2025",
                    any_keywords=("1099-r",), asked=False),
        RequestItem(identifier="F01", document="K-1", period="TY2025",
                    any_keywords=("partner's share of income",), asked=False),
    ]
    eng = make_engagement(tmp_path, rows, household="Smith Family", scaffold=False)
    seed_statuses(eng, {
        "E01": StatusUpdate(status=Status.RECEIVED, file_count=1, received_date=dt.date(2026, 3, 1)),
        "F01": StatusUpdate(status=Status.MISSING, file_count=0),
    })
    template = [*rows, RequestItem(identifier="G01", document="Property tax", period="TY2025",
                                   any_keywords=("property tax statement",))]

    rolled = rolled_by_id(roll_forward(eng, template=template))

    assert rolled["D01"].item.named is False
    assert rolled["E01"].item.asked is True and "asked for this year" in rolled["E01"].note
    assert rolled["F01"].item.asked is False
    assert rolled["G01"].item.asked is False and rolled["G01"].origin == ORIGIN_NEW
    assert rolled["A01"].item.asked is True and rolled["A01"].item.named is True
