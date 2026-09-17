"""Tests for tracker/templates.py — one catalog, and the CSVs are copies of it.

The claim under test: there is exactly one source of truth for what each
return type asks for. The CSVs in templates/ are generated from the Python
catalog, so a hand edit to a CSV, or a catalog edit without a regenerate,
fails here rather than quietly forking the list.
"""

from pathlib import Path

import pytest

from tracker.content_check import has_content_rules
from tracker.manifest import ManifestError, load_manifest, create_template
from tracker.templates import (
    CSV_COLUMNS,
    FORM_TEMPLATES,
    FORM_TYPES,
    csv_name,
    export_csvs,
    item_from_spec,
    render_csv,
    stale_csvs,
    template_items,
)

REPO = Path(__file__).resolve().parent.parent
TEMPLATES_DIR = REPO / "templates"


def test_the_committed_csvs_match_the_catalog():
    assert stale_csvs(TEMPLATES_DIR) == [], (
        "templates/*.csv have drifted from tracker/templates.py — "
        "run `python -m tracker.templates export`"
    )


def test_every_form_type_has_a_checklist_and_a_csv():
    assert {f["id"] for f in FORM_TYPES} == set(FORM_TEMPLATES)
    for form in FORM_TEMPLATES:
        assert (TEMPLATES_DIR / csv_name(form)).is_file(), form


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


def test_csv_carries_the_manifest_columns_and_the_core_flag():
    text = render_csv("1040")
    header, first = text.splitlines()[:2]
    assert header == ",".join(CSV_COLUMNS)
    assert first.startswith("A01,W-2 Wage Statements - All Employers,TY2025,2,pdf,5,W-2,")
    assert first.endswith(",yes")


def test_export_writes_one_csv_per_form(tmp_path):
    written = export_csvs(tmp_path)
    assert sorted(p.name for p in written) == sorted(csv_name(f) for f in FORM_TEMPLATES)
    assert stale_csvs(tmp_path) == []
    (tmp_path / csv_name("1040")).write_text("edited by hand\n", encoding="utf-8")
    assert stale_csvs(tmp_path) == [csv_name("1040")]


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

    assert base_year("1040") == 2025
    shifted = {i.identifier: i for i in template_items("1040", year=2027)}
    assert shifted["A01"].period == "TY2027"
    assert shifted["A01"].date_pattern == ""            # the Period implies it...
    path = create_template(__import__("tempfile").mkdtemp() + "/_manifest.xlsx", shifted.values())
    loaded = {i.identifier: i for i in load_manifest(path)}
    assert loaded["A01"].date_pattern == r"(?i)\b2027\b" and loaded["A01"].date_pattern_derived
    assert loaded["B01"].date_pattern == r"(?i)\b2026\b"   # ...for every row, one year behind here
    assert shifted["B01"].period == "TY2026"           # prior-year return stays one behind
    assert shifted["A01"].required_keywords == ("W-2",)  # keywords never shift
    unshifted = {i.identifier: i for i in template_items("1040")}
    assert unshifted["A01"].period == "TY2025"
