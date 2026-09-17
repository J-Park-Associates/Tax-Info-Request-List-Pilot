"""Tests for tracker/rollover.py — last year beats the generic checklist.

The rule under test throughout: for a returning client, prior-year data wins.
The form template may fill a blank, never overwrite a value, and never
silently drop something the client actually had.
"""

import datetime as dt

import pytest
from openpyxl import load_workbook

from tracker.manifest import (
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    create_template,
    write_statuses,
)
from tracker.rollover import (
    CARRIED_SHEET,
    ORIGIN_NEW,
    ORIGIN_PRIOR,
    ORIGIN_WAIVED,
    detect_year,
    roll_forward,
    shift_years,
    write_rollover_manifest,
)
from tracker.scaffold import MANIFEST_FILENAME

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
    eng = tmp_path / "Smith Family 2025"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, PRIOR)
    write_statuses(eng / MANIFEST_FILENAME, {
        "A01": StatusUpdate(status=Status.RECEIVED, file_count=3,
                            received_date=dt.date(2026, 3, 1)),
        "B01": StatusUpdate(status=Status.RECEIVED, file_count=1,
                            received_date=dt.date(2026, 3, 2)),
        "C01": StatusUpdate(status=Status.MISSING, file_count=0),
    })
    return eng


def rolled_by_id(report):
    return {r.item.identifier: r for r in report.rolled}


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
    write_statuses(eng / MANIFEST_FILENAME,
                   {"A01": StatusUpdate(status=Status.PARTIAL, file_count=1)})
    a01 = rolled_by_id(roll_forward(eng))["A01"]
    assert a01.item.expected_count == 2
    assert "confirm it still applies" in a01.note


def test_template_only_fills_blanks(prior):
    """A blank has nothing to override, so the template may fill it."""
    sparse = [RequestItem(identifier="A01", document="W-2s", period="TY2025",
                          min_size_kb=0)]
    eng = prior.parent / "Sparse 2025"
    eng.mkdir()
    create_template(eng / MANIFEST_FILENAME, sparse)

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
    eng = prior
    write_statuses(eng / MANIFEST_FILENAME,
                   {"C01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    wb = load_workbook(eng / MANIFEST_FILENAME)
    ws = wb["Requests"]
    for row in ws.iter_rows(min_row=2):
        if row[0].value == "C01":
            row[9].value = Override.ACCEPTED
    wb.save(eng / MANIFEST_FILENAME)
    wb.close()

    c01 = rolled_by_id(roll_forward(eng))["C01"].item
    assert c01.manual_override == ""


def test_unreceived_rows_are_carried_with_a_flag(prior):
    c01 = rolled_by_id(roll_forward(prior))["C01"]
    assert c01.origin == ORIGIN_PRIOR
    assert "Missing" in c01.note and "confirm it still applies" in c01.note


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


def test_offers_reach_the_workbook_without_becoming_requests(prior, tmp_path):
    """A person must be able to see what was withheld, in Excel."""
    from tracker.manifest import load_manifest

    report = roll_forward(prior, template=TEMPLATE)
    out = tmp_path / "Smith Family 2026" / MANIFEST_FILENAME
    write_rollover_manifest(out, report)

    assert "E01" not in {i.identifier for i in load_manifest(out)}
    wb = load_workbook(out)
    text = "\n".join(
        " ".join(str(c) for c in row if c)
        for row in wb[CARRIED_SHEET].iter_rows(values_only=True)
    )
    wb.close()
    assert "NOT added" in text and "E01" in text


def test_unfiled_documents_from_last_year_are_surfaced(prior, tmp_path):
    """What arrived and fitted nowhere is exactly next year's gap."""
    from tracker.filer import IndexEntry, NEEDS_REVIEW, INDEX_FILENAME, write_index

    write_index(prior / INDEX_FILENAME, [
        IndexEntry(received="2026-03-01", original_name="K-1 Redwood LP.pdf",
                   size_kb=12.0, digest="abc", identifier="", document="",
                   filed_as="K-1 Redwood LP.pdf", prepared_location="",
                   pbc_location="", decision=NEEDS_REVIEW,
                   reason="matched no request"),
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


# --------------------------------------------------------------- the workbook ----


def test_written_manifest_is_loadable_and_explains_itself(prior, tmp_path):
    report = roll_forward(prior, template=TEMPLATE)
    out = tmp_path / "Smith Family 2026" / MANIFEST_FILENAME
    write_rollover_manifest(out, report)

    from tracker.manifest import load_manifest
    items = {i.identifier: i for i in load_manifest(out)}
    assert items["A01"].period == "TY2026"
    assert items["A01"].expected_count == 3
    assert items["D01"].manual_override == Override.WAIVED
    # Fresh year: no scanner state carried over.
    assert items["A01"].status == "" and items["A01"].received_date is None

    wb = load_workbook(out)
    rows = list(wb[CARRIED_SHEET].iter_rows(min_row=2, values_only=True))
    wb.close()
    origins = {r[0]: r[2] for r in rows if r[0]}
    assert origins["A01"] == ORIGIN_PRIOR
    assert origins["D01"] == ORIGIN_WAIVED
    assert origins["E01"] == ORIGIN_NEW


def test_prior_engagement_is_never_written_to(prior):
    before = (prior / MANIFEST_FILENAME).read_bytes()
    roll_forward(prior, template=TEMPLATE)
    assert (prior / MANIFEST_FILENAME).read_bytes() == before


def test_shift_years_leaves_digits_inside_longer_numbers_alone():
    # An account number is not a year, even when four of its digits look
    # like one.
    assert shift_years("Account 120250 statement TY2025", 1) == "Account 120250 statement TY2026"
    assert shift_years("Policy 2025-1234 for 2025", 1) == "Policy 2026-1234 for 2026"


def test_a_derived_year_check_is_not_carried_as_text(prior, tmp_path):
    # The prior's TY2025 rows had their year check derived from Period; the
    # rolled manifest gets TY2026 and derives again. The Date Pattern cell
    # stays blank rather than being filled with last year's regex.
    from openpyxl import load_workbook as lw
    from tracker.manifest import load_manifest

    report = roll_forward(prior)
    target = tmp_path / "next"
    target.mkdir()
    path = write_rollover_manifest(target / MANIFEST_FILENAME, report)
    wb = lw(path)
    ws = wb["Requests"]
    cells = {ws.cell(row=r, column=1).value: ws.cell(row=r, column=9).value for r in range(2, ws.max_row + 1)}
    wb.close()
    rows = {i.identifier: i for i in load_manifest(path)}
    assert rows["C01"].period == "TY2026"
    assert cells["C01"] is None and rows["C01"].date_pattern == r"(?i)\b2026\b"
    assert rows["C01"].date_pattern_derived
    assert cells["A01"] == r"(?i)\b2026\b"        # A01 typed its own pattern; it shifts and stays
