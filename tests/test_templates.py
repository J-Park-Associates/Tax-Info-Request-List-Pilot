"""Tests for tracker/templates.py — one catalog, read directly by everyone.

The claim under test: there is exactly one source of truth for what each
return type asks for, every row of it can recognise its own document, and
the year it is written for follows the calendar rather than a person.
"""

import pytest

from tracker.content_check import has_content_rules
from tracker.manifest import (
    ManifestError,
    narrowing_rows,
    validated,
)
from tracker.templates import (
    BASE_YEAR,
    FORM_TEMPLATES,
    FORM_TYPES,
    K1_CATALOG,
    K1_IDENTIFIER,
    TY,
    issuer_row,
    item_from_spec,
    k1_row,
    template_items,
)


def test_every_form_type_has_a_checklist():
    assert {f["id"] for f in FORM_TYPES} == set(FORM_TEMPLATES)


@pytest.mark.parametrize("form", sorted(FORM_TEMPLATES))
def test_each_checklist_is_a_valid_manifest(form, tmp_path):
    # Identifiers unique and folder-safe, at least one core row, and every
    # row able to recognise its own document.
    items = template_items(form)
    assert any(spec["core"] for spec in FORM_TEMPLATES[form])
    assert all(has_content_rules(i) for i in items)
    loaded = validated(items)                         # the round trip an engagement makes
    assert [i.identifier for i in loaded] == [i.identifier for i in items]
    assert [i.row for i in loaded] == list(range(1, len(items) + 1))


def test_unknown_form_is_refused():
    with pytest.raises(ManifestError, match="Unknown tax form type"):
        template_items("1040-EZ")


def test_a_request_with_no_rule_defaults_to_its_own_name():
    # Without a keyword the router could never file it; the visible default
    # is the document name, which the accountant can shorten in the manifest.
    item = item_from_spec({"identifier": "X01", "document": "Rental Property Records"})
    assert item.required_keywords == ("Rental Property Records",)
    assert has_content_rules(item)
    explicit = item_from_spec(
        {"identifier": "X01", "document": "Rental Property Records", "any_keywords": "schedule e"}
    )
    assert explicit.required_keywords == ()
    assert explicit.any_keywords == ("schedule e",)


def test_the_tax_year_comes_from_the_calendar():
    import datetime as dt

    from tracker.templates import default_tax_year

    assert default_tax_year(dt.date(2027, 2, 1)) == 2026
    assert default_tax_year(dt.date(2026, 9, 17)) == 2025
    assert default_tax_year(dt.date(2026, 12, 31)) == 2025


def test_catalog_rows_shift_to_the_engagements_year():
    from tracker.templates import base_year, template_items

    assert base_year("1040") == BASE_YEAR
    shifted = {i.identifier: i for i in template_items("1040", year=2027)}
    assert shifted["A01"].period == "TY2027"
    assert shifted["A01"].date_pattern == ""            # the Period implies it...
    loaded = {i.identifier: i for i in validated(shifted.values())}
    assert loaded["A01"].date_pattern == r"(?i)\b2027\b" and loaded["A01"].date_pattern_derived
    assert loaded["B01"].date_pattern == r"(?i)\b2026\b"   # ...for every row, one year behind here
    assert shifted["B01"].period == "TY2026"           # prior-year return stays one behind
    base = {i.identifier: i for i in template_items("1040")}
    assert shifted["A01"].required_keywords == base["A01"].required_keywords  # keywords never shift
    unshifted = {i.identifier: i for i in template_items("1040")}
    assert unshifted["A01"].period == TY


def test_shared_requests_are_defined_once_and_agree_everywhere():
    from tracker.templates import SHARED

    by_document: dict[str, set[tuple]] = {}
    for rows in FORM_TEMPLATES.values():
        for row in rows:
            signature = (row["document"], row.get("any_keywords", ""), row.get("required_keywords", ""),
                         row["extensions"], row["period"])
            by_document.setdefault(row["document"], set()).add(signature)
    for shared in SHARED.values():
        assert len(by_document.get(shared["document"], set())) == 1, shared["document"]


def test_the_catalogs_year_is_one_constant():
    import re

    from tracker.templates import BASE_YEAR

    years = {int(y) for rows in FORM_TEMPLATES.values() for row in rows
             for y in re.findall(r"(?:19|20)\d{2}", row["period"])}
    assert years == {BASE_YEAR, BASE_YEAR - 1}


# ------------------------------------------- a row per issuer (decision 93) ----


def test_the_catalog_keeps_exactly_one_k_1_row():
    """The owner's decision: one K-1 row, and the issuers are an engagement's
    own business. A second catalog row would be a fact about one client."""
    k1_rows = [
        (form, spec["identifier"])
        for form, specs in FORM_TEMPLATES.items()
        for spec in specs
        if "k-1" in spec["document"].lower()
    ]
    assert k1_rows == [(K1_CATALOG, K1_IDENTIFIER)]


def test_the_k_1_row_asks_for_the_state_k_1_too():
    """California heads Schedule K-1 (568) "Member's Share of Income"."""
    assert "member's share of income" in k1_row()["any_keywords"]


def test_an_issuer_row_is_the_k_1_row_named_for_an_entity():
    row = issuer_row("F02", "Ashford Holdings, L.P.")
    source = k1_row()

    assert row["document"] == "Schedule K-1 - Ashford Holdings LP"
    assert row["required_keywords"] == "Ashford Holdings LP"
    assert row["any_keywords"] == source["any_keywords"]
    assert row["extensions"] == source["extensions"] and row["period"] == source["period"]
    # Nothing new in the schema: it loads as any other row does.
    assert item_from_spec(row).identifier == "F02"


def test_an_issuer_row_needs_an_entity():
    with pytest.raises(ManifestError):
        issuer_row("F02", " , . ")


@pytest.mark.parametrize("form", sorted(FORM_TEMPLATES))
def test_no_shipped_catalog_row_narrows_another(form):
    """The evidence for leaving the tiers alone: the issuer rule can only
    fire on a row a person added, so no shipped placement can move."""
    assert narrowing_rows(template_items(form)) == {}


@pytest.mark.parametrize("form", sorted(FORM_TEMPLATES))
def test_no_shipped_catalog_row_requires_a_subset_of_anothers_words(form):
    """No two rows where one's required keywords are all of another's and
    more: nothing in the catalog is a special case of anything else."""
    rows = template_items(form)
    for one in rows:
        for other in rows:
            if one.identifier == other.identifier:
                continue
            mine = {k.lower() for k in one.required_keywords}
            theirs = {k.lower() for k in other.required_keywords}
            assert not (mine and theirs and mine <= theirs), (one.identifier, other.identifier)


# ------------------------------------------------- the two dates (d117) ----


def test_the_filing_deadline_table_covers_every_form_and_shifts_a_weekend_forward():
    """Decision 117: every return the catalog knows has a statutory date,
    moved forward off the weekend the way the IRS moves it - and a form
    the table does not name has none at all, because a guessed deadline is
    a date read out to a client in the firm's name."""
    import datetime as dt

    from tracker.templates import FILING_DEADLINES, filing_deadline_for

    assert set(FILING_DEADLINES) == {f["id"] for f in FORM_TYPES}
    for form in FILING_DEADLINES:
        when = filing_deadline_for(form, BASE_YEAR)
        assert when is not None and when.year == BASE_YEAR + 1
        assert when.weekday() < 5, form

    # April 15 2028 is a Saturday: the deadline is the Monday after it.
    assert filing_deadline_for("1040", 2027) == dt.date(2028, 4, 17)
    # And a day that is already a weekday does not move.
    assert filing_deadline_for("1040", 2025) == dt.date(2026, 4, 15)
    assert filing_deadline_for("1120S", 2025) == dt.date(2026, 3, 16)   # March 15 is a Sunday
    assert filing_deadline_for("990", 2025) == dt.date(2026, 5, 15)
    assert filing_deadline_for("not a form", 2025) is None


def test_the_ask_by_default_is_five_days_before_the_deadline_moved_back_to_a_weekday():
    """The firm's own target, and it is a default rather than a rule: the
    reminder names the two dates and never the arithmetic between them."""
    import datetime as dt

    from tracker.templates import TARGET_DAYS_BEFORE_DEADLINE, ask_by_for

    assert TARGET_DAYS_BEFORE_DEADLINE == 5
    # April 15 2026 is a Wednesday; five days before it is a Friday.
    assert ask_by_for(dt.date(2026, 4, 15)) == dt.date(2026, 4, 10)
    # April 15 2027 is a Thursday; five days before is a Saturday, so the
    # target is the working day before it - a date the office can act on.
    assert ask_by_for(dt.date(2027, 4, 15)) == dt.date(2027, 4, 9)
    for days in range(0, 400):
        target = ask_by_for(dt.date(2026, 1, 1) + dt.timedelta(days=days))
        assert target.weekday() < 5


# ------------------------------------------------- the name mark (d128) ----

#: What Fable marked named, per catalog: the count, and the identifiers.
#: The payer, the lender, the agency or the return itself addresses a
#: person or an entity on every one of these; a receipt, a log, a schedule,
#: a list, an export or a description is on none of them. Pinned by
#: identifier as well as by count, so a row moved from one side to the
#: other is a test somebody has to change on purpose.
NAMED_ROWS: dict[str, tuple[str, ...]] = {
    "1040": ("A01", "A02", "A03", "A04", "A05", "A06", "B01", "C01",
             "E01", "E02", "F01", "G01", "I01", "K01", "L01"),
    "1120": ("A01", "B01", "B02", "D01", "E01"),
    "1120S": ("A01", "B01", "B02", "D01", "E01", "G01"),
    "1065": ("A01", "A02", "B01", "B02", "E01"),
    "1041": ("A01", "A02", "A03", "B01", "B02"),
    "990": ("A01", "B01", "B02", "G01"),
}
#: Fable's counts, said as the SPEC says them: named of all, per catalog.
NAMED_COUNTS: dict[str, tuple[int, int]] = {
    "1040": (15, 18), "1120": (5, 14), "1120S": (6, 15),
    "1065": (5, 15), "1041": (5, 10), "990": (4, 12),
}


def test_every_shipped_row_carries_a_named_mark_and_the_counts_are_fable_s():
    """Decision 128. Every catalog row says whether the document it asks for
    carries a name, because that is what decides whether a page naming
    nobody parks or files; a row with no mark would be a request whose
    strictness nobody chose. Forty of the eighty-four are named."""
    named = 0
    total = 0
    for form, rows in FORM_TEMPLATES.items():
        for spec in rows:
            assert isinstance(spec.get("named"), bool), (form, spec["identifier"])
        marked = tuple(spec["identifier"] for spec in rows if spec["named"])
        assert marked == NAMED_ROWS[form], form
        assert (len(marked), len(rows)) == NAMED_COUNTS[form], form
        named += len(marked)
        total += len(rows)
    assert (named, total) == (40, 84)
    # The mark reaches the row a person's list is cut from, not just the spec.
    assert all(item_from_spec(spec).named for spec in FORM_TEMPLATES["1040"][:1])
    assert not item_from_spec(
        next(s for s in FORM_TEMPLATES["1040"] if s["identifier"] == "D01")).named


def test_an_issuer_row_is_named_because_the_k1_row_it_is_cut_from_is():
    """A K-1 is addressed to its recipient, so the row a person adds for one
    issuer is as named as the catalog row it was cut from - and the entity's
    name in Required Keywords is still a keyword, saying which K-1 this is
    and never whose."""
    assert k1_row()["named"] is True
    assert issuer_row("F02", "Ashford Holdings LP")["named"] is True
