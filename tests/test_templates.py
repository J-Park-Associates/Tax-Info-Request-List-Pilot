"""Tests for tracker/templates.py — one catalog, read directly by everyone.

The claim under test: there is exactly one source of truth for what each
return type asks for, every row of it can recognise its own document, and
the year it is written for follows the calendar rather than a person.
"""

import pytest

from tracker.content_check import has_content_rules
from tracker.manifest import ManifestError, create_template, load_manifest
from tracker.scaffold import MANIFEST_FILENAME
from tracker.templates import (
    BASE_YEAR,
    FORM_TEMPLATES,
    FORM_TYPES,
    TY,
    item_from_spec,
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
    path = create_template(tmp_path / f"{form}.xlsx", items)
    loaded = load_manifest(path)
    assert [i.identifier for i in loaded] == [i.identifier for i in items]


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
    path = create_template(__import__("tempfile").mkdtemp() + "/" + MANIFEST_FILENAME, shifted.values())
    loaded = {i.identifier: i for i in load_manifest(path)}
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
