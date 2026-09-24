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


#: The one catalog row that carries a shared row's title with rules of its
#: own. Decision 73 named the corporate estimated-tax row apart so that one
#: document name never means two sets of rules; decision 141's 1041 G01 is
#: the exception by ruling - the owner approved the title, and the designer
#: ruled (on the build's G1) that the trust's row files only a 1041-ES, not
#: the individual's voucher the 1040's row keys on.
SAME_TITLE_OWN_RULES = {("1041", "G01")}


def test_shared_requests_are_defined_once_and_agree_everywhere():
    from tracker.templates import SHARED

    by_document: dict[str, set[tuple]] = {}
    for form, rows in FORM_TEMPLATES.items():
        for row in rows:
            if (form, row["identifier"]) in SAME_TITLE_OWN_RULES:
                continue
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
    own business. A second catalog row would be a fact about one client.

    Decision 141 is the owner's too: each business catalog that can be a
    partner or a beneficiary asks for the K-1s *the business* received, one
    row each. The 1040's stays the one row issuer rows are cut from."""
    k1_rows = [
        (form, spec["identifier"])
        for form, specs in FORM_TEMPLATES.items()
        for spec in specs
        if "k-1" in spec["document"].lower()
    ]
    assert k1_rows == [(K1_CATALOG, K1_IDENTIFIER), ("1120", "J01"), ("1120S", "I01"), ("1065", "H01")]


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
    "1040": ("A01", "A02", "A03", "A04", "A05", "A06", "A07", "A08", "A09", "B01", "C01",
             "E01", "E02", "F01", "G01", "I01", "K01", "L01", "L02", "L03", "N01", "Z01"),
    "1120": ("A01", "B01", "B02", "D01", "E01", "J01", "J02", "J03", "Z01"),
    "1120S": ("A01", "B01", "B02", "D01", "E01", "G01", "I01", "I02", "I03", "Z01"),
    "1065": ("A01", "A02", "B01", "B02", "E01", "H01", "H02", "H03", "Z01"),
    "1041": ("A01", "A02", "A03", "B01", "B02", "Z01"),
    "990": ("A01", "B01", "B02", "G01", "Z01"),
}
#: Fable's counts, said as the SPEC says them: named of all, per catalog.
#: Decision 141 added twenty-three rows, twenty-one of them named (the
#: Schedule C sheet and the 1041's estimated-tax row are not).
NAMED_COUNTS: dict[str, tuple[int, int]] = {
    "1040": (22, 26), "1120": (9, 18), "1120S": (10, 19),
    "1065": (9, 19), "1041": (6, 12), "990": (5, 13),
}


def test_every_shipped_row_carries_a_named_mark_and_the_counts_are_fable_s():
    """Decision 128. Every catalog row says whether the document it asks for
    carries a name, because that is what decides whether a page naming
    nobody parks or files; a row with no mark would be a request whose
    strictness nobody chose. Sixty-one of the hundred and seven are named."""
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
    assert (named, total) == (61, 107)
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


#: Decision 141, the owner's rows and titles exactly as he approved them
#: (SPEC-141 §1): (catalog, identifier, title, named, extensions).
_K1_RECEIVED = "Schedule K-1s Received by the Business"
_PAYMENT_FORMS = "1099-K / 1099-NEC Received by the Business"
_FOREIGN = "1042-S - Foreign Person's U.S. Source Income"
_NOTICES = "IRS & State Tax Notices and Letters"
OWNERS_ROWS_141 = [
    ("1040", "A07", "SSA-1099 / RRB-1099 - Social Security & Railroad Retirement Benefits", True, "pdf"),
    ("1040", "A08", "1099-C - Cancellation of Debt", True, "pdf"),
    ("1040", "A09", "W-2G - Gambling Winnings", True, "pdf"),
    ("1040", "L02", "1098-E - Student Loan Interest", True, "pdf, csv"),
    ("1040", "L03", "1099-Q - 529 / Coverdell Education Savings Distributions", True, "pdf"),
    ("1040", "M01", "Schedule C - Business Income & Expense Summary", False, "xlsx, pdf, csv"),
    ("1040", "N01", _FOREIGN, True, "pdf"),
    *[(form, f"{letter}0{n}", title, True, ext)
      for form, letter in (("1120", "J"), ("1120S", "I"), ("1065", "H"))
      for n, title, ext in ((1, _K1_RECEIVED, "pdf"), (2, _PAYMENT_FORMS, "pdf, csv"), (3, _FOREIGN, "pdf"))],
    ("1041", "G01", "Estimated Tax Payment Records", False, "pdf, xlsx"),
    *[(form, "Z01", _NOTICES, True, "pdf") for form in ("1040", "1120", "1120S", "1065", "1041", "990")],
]


def test_every_new_row_is_in_its_catalog_with_the_owners_exact_title():
    """Decision 141: every row the owner added, identifier by identifier and
    title by title, none of them pre-ticked - the wizard shows them unticked
    and what an unticked row does is a later decision's (go-live item 15).
    The 1041's G01 carries the 1040's estimated-tax title but the 1041-ES's
    own words (the designer's ruling on the build), and the notices row is
    one row on every catalog, so its words live in one place."""
    assert len(OWNERS_ROWS_141) == 23
    for form, identifier, title, named, extensions in OWNERS_ROWS_141:
        spec = next((s for s in FORM_TEMPLATES[form] if s["identifier"] == identifier), None)
        assert spec is not None, (form, identifier)
        assert spec["document"] == title, (form, identifier)
        assert spec["named"] is named and spec["core"] is False, (form, identifier)
        assert spec["extensions"] == extensions, (form, identifier)
        assert spec.get("required_keywords") or spec.get("any_keywords"), (form, identifier)
    h01 = next(s for s in FORM_TEMPLATES["1040"] if s["identifier"] == "H01")
    g01 = next(s for s in FORM_TEMPLATES["1041"] if s["identifier"] == "G01")
    assert g01["document"] == h01["document"]
    assert "1041-es" in g01["required_keywords"] and "any_keywords" not in g01
    notices = [next(s for s in rows if s["identifier"] == "Z01") for rows in FORM_TEMPLATES.values()]
    assert all(row == notices[0] for row in notices)
    # Z01 sorts last on every catalog, so a notice reads the same everywhere.
    assert all(rows[-1]["identifier"] == "Z01" for rows in FORM_TEMPLATES.values())


def test_every_catalog_row_has_a_legal_short_title_within_the_limit_and_unique_per_catalog():
    """Decision 144, claim 1. Every row the catalogs write carries its own
    short name - none is left to the derivation, because the owner approved
    each one (2026-09-24) - of at most twenty characters, a name a folder
    can have, unique within its catalog. A row several catalogs share has
    one short name everywhere: the same document never has two."""
    from tracker.manifest import SHORT_TITLE_MAX, short_title_problem
    from tracker.scaffold import sanitize_component

    by_document: dict[str, set[str]] = {}
    for form in FORM_TEMPLATES:
        items = template_items(form)
        shorts = [item.short_title for item in items]
        assert all(shorts), (form, [i.identifier for i in items if not i.short_title])
        for item in items:
            assert len(item.short_title) <= SHORT_TITLE_MAX, (form, item.identifier, item.short_title)
            assert short_title_problem(item.short_title) == "", (form, item.identifier)
            # Legal as it stands: the sanitiser leaves it alone.
            assert sanitize_component(item.short_title) == item.short_title
            by_document.setdefault(item.document, set()).add(item.short_title)
        casefolded = [short.casefold() for short in shorts]
        assert len(set(casefolded)) == len(casefolded), (form, sorted(shorts))
    assert {doc: names for doc, names in by_document.items() if len(names) > 1} == {}
    # Two of the owner's names, to hold the list to the one he approved.
    first = {i.identifier: i.short_title for i in template_items("1040")}
    assert first["A01"] == "W-2" and first["C01"] == "1098 Mortgage"


def test_a_k1_issuer_row_is_short_named_by_its_issuer():
    """Decision 144, the owner's Q-B (2026-09-24): a per-issuer K-1 row's
    short name is ``K-1`` and the issuer, cut to twenty characters at a
    whole word - not the first twenty of its Document, which kept at most
    five letters of the issuer ("Schedule K-1") and none of Ashford's. The
    Document the client reads keeps the whole name; the row's folder takes
    the short one."""
    from tracker.manifest import item_from_fields, short_title_problem
    from tracker.scaffold import folder_name_for

    cases = {
        "Ashford Holdings, L.P.": "K-1 Ashford Holdings",
        "Birch Lane Partners": "K-1 Birch Lane",
        "ABC Partners LLC": "K-1 ABC Partners LLC",
        "A/B: Co": "K-1 A-B- Co",
    }
    for entity, short in cases.items():
        row = item_from_spec(issuer_row("F02", entity))
        assert row.short_title == short, entity
        assert short_title_problem(row.short_title) == ""
    ashford = item_from_spec(issuer_row("F02", "Ashford Holdings, L.P."))
    assert ashford.document == "Schedule K-1 - Ashford Holdings LP"
    assert folder_name_for(ashford) == "F02 - K-1 Ashford Holdings"
    # Any other title a preparer types still derives its first twenty.
    own = item_from_fields({"identifier": "X01", "document": "Schedule K-1s Received by the Trust"},
                           where="Row 1")
    assert own.short_title == "" and own.short_name == "Schedule K-1s"


def test_a_hand_added_k1_row_derives_its_short_name_from_the_issuer():
    """Decision 144, the designer's ruling on the build: in the app a K-1
    row per issuer is added by hand in the editor (the runbook's "Adding
    one"), with the Document written as ``ISSUER_DOCUMENT`` and the Short
    name left blank. Its folder still says whose K-1 it is: the blank
    derives ``K-1 <issuer>`` through the one function ``issuer_row`` uses
    - the same cut, the same hyphen for a character a folder cannot hold -
    and the title is recognised from the one constant, its prefix without
    case. Any other title derives its first twenty characters."""
    from tracker import manifest, templates
    from tracker.manifest import derived_short_title, issuer_short_title, item_from_fields
    from tracker.scaffold import folder_name_for

    assert templates.ISSUER_DOCUMENT is manifest.ISSUER_DOCUMENT
    typed = item_from_fields({"identifier": "F02", "document": "Schedule K-1 - Ashford Holdings LP",
                              "required_keywords": "Ashford Holdings LP"}, where="Row 1")
    assert typed.short_title == "" and typed.short_name == "K-1 Ashford Holdings"
    assert folder_name_for(typed) == "F02 - K-1 Ashford Holdings"
    # The same name issuer_row gives the same entity, by the same function.
    cut = item_from_spec(issuer_row("F02", "Ashford Holdings, L.P."))
    assert cut.short_title == typed.short_name == issuer_short_title("Ashford Holdings LP")
    # The prefix is matched without case; what a folder cannot hold is a hyphen.
    assert derived_short_title("SCHEDULE K-1 - Birch Lane Partners") == "K-1 Birch Lane"
    assert derived_short_title("schedule k-1 - A/B Co") == "K-1 A-B Co"
    # Not the pattern: the first twenty characters, as any title.
    assert derived_short_title("Schedule K-1s Received") == "Schedule K-1s"
    assert derived_short_title(templates.ISSUER_DOCUMENT.format(entity="")) == "Schedule K-1"
