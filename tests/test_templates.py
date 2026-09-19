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
