"""Tests for tracker/review.py — the review queue, triaged and never filed.

The promises being tested: a shortlist is built from the evidence and from
nothing else, it never offers a row that wants nothing, it is ordered the
same way twice over the same bytes, it is short, and computing it leaves
the engagement exactly as it was — no lock, no write, not one changed byte.
"""

import datetime as dt
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.conftest import make_engagement, seed_index
from tests.test_scanner import text_pdf
from tracker import reasons
from tracker.content_check import (
    EVIDENCE_PLACES,
    EVIDENCE_RULES,
    RULE_ANY,
    RULE_FILENAME,
    RULE_REFUSED,
    RULE_REQUIRED,
    WHERE_DEEP,
    WHERE_FIRST_PAGE,
    WHERE_TITLE,
    Evidence,
    format_evidence,
)
from tracker.filer import (
    _CANDIDATE_SEP,
    NEEDS_REVIEW,
    NOT_REQUESTED,
    IndexEntry,
    file_drops,
    read_index,
)
from tracker.locking import LOCK_FILENAME
from tracker.manifest import Override, RequestItem, Status
from tracker.review import (
    MAX_SUGGESTIONS,
    NOTHING_SUGGESTED,
    PLACE_STRENGTH,
    PLACE_WORDS,
    RULE_STRENGTH,
    triage,
)
from tracker.router import UNMATCHED
from tracker.scaffold import (
    PBC_DIR_NAME,
    SHARED_DIR_NAME,
)

DAY1 = dt.date(2026, 7, 1)
REPO = Path(__file__).resolve().parent.parent

#: Catalog order is A01, A02, B01, C01, W01 — the order triage must fall
#: back on when two rows say exactly as much as each other.
ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",),
        date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="A02", document="1099-INT Interest Income", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1099-INT",),
    ),
    RequestItem(
        identifier="B01", document="Charitable Donation Receipts", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("donation",),
    ),
    RequestItem(
        identifier="C01", document="Mortgage Interest Statement", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
    ),
    RequestItem(
        identifier="W01", document="Rental Property Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("rental",),
        manual_override=Override.NOT_APPLICABLE,
    ),
]


@pytest.fixture
def engagement(tmp_path):
    return make_engagement(tmp_path / "Smith Family 2025", ITEMS)


def parked_row(name, record, *, reason=UNMATCHED, decision=NEEDS_REVIEW, candidates=()):
    """One index row as the filer writes it, evidence through its own formatter."""
    return IndexEntry(
        received="2026-01-01", original_name=name, size_kb=9.4, digest=name,
        identifier="", prepared_location="",
        pbc_location=f"{SHARED_DIR_NAME}/{PBC_DIR_NAME}/{name}",
        decision=decision, reason=reason,
        candidates=_CANDIDATE_SEP.join(candidates),
        evidence=format_evidence(record),
    )


def park(engagement, *entries):
    """Record those rows in the engagement's real record."""
    seed_index(engagement, entries)
    return engagement


def triage_of(engagement, **kwargs):
    """``triage`` with the index read for it.

    Since decision 100 ``entries`` is required: the caller reads the index
    and hands it over, which is what the app, the view and the CLI all do.
    These tests are that caller, and read it the way the CLI does.
    """
    return triage(engagement, read_index(engagement), **kwargs)


def identifiers(triaged):
    return [suggestion.identifier for suggestion in triaged.shortlist]


# ------------------------------------------------------------- the ordering ----


def test_a_row_that_says_it_in_the_title_outranks_one_that_says_it_deep(engagement):
    park(engagement, parked_row("scan0012.pdf", {
        "A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_DEEP, 6),),
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),),
    }))

    [triaged] = triage_of(engagement)

    assert identifiers(triaged) == ["C01", "A01"], "the title beats the catalog order"


def test_a_required_keyword_outranks_an_any_keyword_said_in_the_same_place(engagement):
    park(engagement, parked_row("scan0013.pdf", {
        "B01": (Evidence(RULE_ANY, "donation", WHERE_TITLE, 1),),
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_FIRST_PAGE, 1),),
    }))

    [triaged] = triage_of(engagement)

    assert identifiers(triaged) == ["C01", "B01"]


def test_a_keyword_in_the_file_name_ranks_below_anything_the_document_said(engagement):
    park(engagement, parked_row("1098.pdf", {
        "C01": (Evidence(RULE_FILENAME, "1098", WHERE_TITLE),),
        "B01": (Evidence(RULE_ANY, "donation", WHERE_DEEP, 9),),
    }))

    [triaged] = triage_of(engagement)

    assert identifiers(triaged) == ["B01", "C01"]


def test_two_rows_with_equal_evidence_keep_catalog_order(engagement):
    park(engagement, parked_row("scan0014.pdf", {
        # Written strongest-looking-first in the cell; neither is stronger.
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),),
        "A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),),
    }))

    [triaged] = triage_of(engagement)

    assert identifiers(triaged) == ["A01", "C01"], "the manifest's own order breaks the tie"
    first, second = triaged.shortlist
    assert first.rank[:2] == second.rank[:2], "a tie is kept as a tie above the catalog slot"


def test_the_shortlist_is_capped(engagement):
    park(engagement, parked_row("everything.pdf", {
        item.identifier: (Evidence(RULE_REQUIRED, item.identifier, WHERE_TITLE, 1),)
        for item in ITEMS if item.manual_override != Override.NOT_APPLICABLE
    }))

    [triaged] = triage_of(engagement)

    assert len(ITEMS) - 1 > MAX_SUGGESTIONS, "the fixture has to offer more than the cap"
    assert len(triaged.shortlist) == MAX_SUGGESTIONS
    assert identifiers(triaged) == ["A01", "A02", "B01"], "the cap keeps the best, not the first read"


# ------------------------------------------------------ what is never offered ----


def test_a_not_applicable_row_is_named_as_set_aside_and_never_suggested(engagement):
    """Decision 83 amended by 116: the row is never a Suggestion, and when
    the evidence points at it the shortlist says so in one sentence, with
    the row's year label, so the person who set it aside decides."""
    from tracker.review import SET_ASIDE_NOTE, SetAside, set_aside_note

    park(engagement, parked_row("rental.pdf", {
        "W01": (Evidence(RULE_REQUIRED, "rental", WHERE_TITLE, 1),),
        "C01": (Evidence(RULE_ANY, "1098", WHERE_DEEP, 4),),
    }), parked_row("mystery.pdf", {}))

    rental, mystery = triage_of(engagement)

    assert identifiers(rental) == ["C01"], "a row that wants nothing is never suggested"
    assert rental.set_aside == (SetAside("W01", "Not Applicable in TY2025"),)
    assert set_aside_note(rental.set_aside[0]) == SET_ASIDE_NOTE.format(
        identifier="W01", label="Not Applicable in TY2025")
    assert set_aside_note(rental.set_aside[0]) == (
        "W01 is Not Applicable in TY2025 - clear it in the editor to file here")
    assert mystery.set_aside == () and mystery.shortlist == ()

    # Named when it is a candidate the router refused, too - evidence or not.
    park(engagement, parked_row("rental2.pdf", {}, candidates=("W01",)))
    by_name = {t.entry.original_name: t for t in triage_of(engagement)}
    assert by_name["rental2.pdf"].set_aside == (SetAside("W01", "Not Applicable in TY2025"),)
    assert by_name["rental2.pdf"].shortlist == ()


@pytest.mark.parametrize("state", [Status.MISSING, Status.RECEIVED])
def test_a_file_with_no_evidence_gets_no_suggestion_whatever_the_request_list_says(
    engagement, state,
):
    """The request list's state is not a prior: an empty row is not a hint."""
    park(engagement, parked_row("mystery.pdf", {}))
    wanting = [replace(item, status=state) for item in ITEMS]

    [triaged] = triage_of(engagement, items=wanting)

    assert triaged.entry.evidence == ""
    assert triaged.shortlist == (), "no evidence, no suggestion — the person reads it"
    assert triaged.entry.reason == UNMATCHED, "the router's reason is kept"


def test_a_refusal_on_its_own_is_not_a_suggestion(engagement):
    park(engagement, parked_row("tiny.pdf", {
        "C01": (Evidence(RULE_REFUSED, reasons.TOO_SMALL.code),),
    }))

    [triaged] = triage_of(engagement)

    assert triaged.shortlist == ()


def test_a_row_a_person_said_nothing_asks_for_is_not_triaged(engagement):
    park(
        engagement,
        parked_row("notice.pdf", {"C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),)},
                   decision=NOT_REQUESTED),
        parked_row("scan0015.pdf", {"A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),)}),
    )

    triaged = triage_of(engagement)

    assert [t.entry.original_name for t in triaged] == ["scan0015.pdf"]


def test_a_candidate_no_longer_on_the_manifest_is_not_offered(engagement):
    park(engagement, parked_row("gone.pdf", {
        "Z99": (Evidence(RULE_REQUIRED, "something", WHERE_TITLE, 1),),
    }))

    [triaged] = triage_of(engagement)

    assert triaged.shortlist == (), "there is no row left to file it into"


# ------------------------------------------------------------- the sentences ----


def test_the_reason_says_each_keyword_and_where_it_was_said(engagement):
    park(engagement, parked_row("statement.pdf", {
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),
                Evidence(RULE_ANY, "mortgage interest", WHERE_FIRST_PAGE, 1)),
    }))

    [triaged] = triage_of(engagement)
    (suggestion,) = triaged.shortlist

    assert suggestion.reason.startswith("C01")
    assert "'1098' in the title" in suggestion.reason
    assert "'mortgage interest' on page 1" in suggestion.reason


def test_a_keyword_found_in_the_file_name_is_said_to_be_the_file_name(engagement):
    park(engagement, parked_row("1098-t.pdf", {
        "C01": (Evidence(RULE_FILENAME, "1098", WHERE_TITLE),),
    }))

    [triaged] = triage_of(engagement)
    (suggestion,) = triaged.shortlist

    assert "the file name says 1098" in suggestion.reason


def test_a_contested_file_names_the_row_it_looks_like_with_the_rule_that_failed(engagement):
    """Last year's W-2 announces itself as A01 and then fails A01's year check."""
    text_pdf(engagement / SHARED_DIR_NAME / "old.pdf",
             "Form W-2 Wage and Tax Statement 2024")
    report = file_drops(engagement, today=DAY1)
    assert len(report.review) == 1

    [triaged] = triage_of(engagement)

    assert identifiers(triaged)[0] == "A01"
    assert reasons.WRONG_PERIOD.marker in triaged.shortlist[0].reason
    assert "'W-2'" in triaged.shortlist[0].reason


def test_a_refusal_beside_content_evidence_is_said_in_that_suggestions_sentence(engagement):
    park(engagement, parked_row("locked.pdf", {
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),
                Evidence(RULE_REFUSED, reasons.PASSWORD_PROTECTED.code)),
    }))

    [triaged] = triage_of(engagement)
    (suggestion,) = triaged.shortlist

    assert "'1098' in the title" in suggestion.reason
    assert reasons.PASSWORD_PROTECTED.marker in suggestion.reason


def test_a_locked_file_the_rules_never_read_is_offered_by_its_name_with_the_refusal(engagement):
    """Decision 117: the router now records what a locked file's *name*
    said beside the refusal that stopped it being read, so the card offers
    the request it was probably meant for and says both things about it -
    at the weakest tier, beside a document the person has to open anyway.
    """
    from tests.test_validators import write_pdf

    write_pdf(engagement / SHARED_DIR_NAME / "W-2 Jane Smith 2025.pdf", password="secret123")
    report = file_drops(engagement, today=DAY1)
    assert len(report.review) == 1

    [triaged] = triage_of(engagement)
    (suggestion,) = triaged.shortlist

    assert suggestion.identifier == "A01"
    assert "the file name says W-2" in suggestion.reason
    assert reasons.PASSWORD_PROTECTED.marker in suggestion.reason
    assert triaged.entry.candidates == "", "a name is still no candidate"


def test_every_rule_and_place_the_evidence_defines_has_a_strength_and_a_word():
    """A new evidence word must not quietly rank last and read as nothing."""
    assert set(RULE_STRENGTH) == set(EVIDENCE_RULES) - {RULE_REFUSED}
    assert set(PLACE_STRENGTH) == set(EVIDENCE_PLACES)
    assert set(PLACE_WORDS) == set(EVIDENCE_PLACES)


# ------------------------------------------------------ it computes, it reads ----


def test_two_runs_over_the_same_bytes_give_identical_output(engagement):
    park(engagement, parked_row("scan0016.pdf", {
        "C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),),
        "A01": (Evidence(RULE_ANY, "W-2", WHERE_DEEP, 3),),
    }))

    assert triage_of(engagement) == triage_of(engagement)


def test_triage_takes_no_lock_and_writes_nothing(engagement):
    text_pdf(engagement / SHARED_DIR_NAME / "old.pdf",
             "Form W-2 Wage and Tax Statement 2024")
    file_drops(engagement, today=DAY1)
    before = _fingerprint(engagement)

    assert triage_of(engagement)

    assert _fingerprint(engagement) == before, "triage changed something on disk"
    assert not list(engagement.rglob(LOCK_FILENAME)), "triage took the engagement lock"


def test_the_cli_prints_each_parked_file_and_its_shortlist(engagement):
    park(
        engagement,
        parked_row("statement.pdf", {"C01": (Evidence(RULE_REQUIRED, "1098", WHERE_TITLE, 1),)}),
        parked_row("mystery.pdf", {}),
    )

    done = subprocess.run(
        [sys.executable, "-m", "tracker.review", str(engagement)],
        cwd=REPO, check=True, capture_output=True, text=True,
        env={**os.environ, "PYTHONPATH": str(REPO), "PYTHONIOENCODING": "utf-8"},
    )

    assert "statement.pdf" in done.stdout
    assert "C01" in done.stdout and "'1098' in the title" in done.stdout
    assert "mystery.pdf" in done.stdout and NOTHING_SUGGESTED in done.stdout


# ------------------------------------------------------------------ helpers ----


def _fingerprint(root: Path) -> dict:
    """Every file under ``root`` by name, size and modification time."""
    return {
        str(path.relative_to(root)): (path.stat().st_size, path.stat().st_mtime_ns)
        for path in sorted(root.rglob("*")) if path.is_file()
    }
