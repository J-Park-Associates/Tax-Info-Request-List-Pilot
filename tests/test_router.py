"""Tests for tracker/router.py — deciding where a dropped file belongs.

The rule under test throughout: route only when the evidence is
unambiguous, and never guess. A misfiled tax document is worse than one
sitting in Needs Review.
"""



import pytest

from tests.test_scanner import text_pdf
from tracker import reasons
from tracker.manifest import Override, RequestItem
from tracker.router import (
    AMBIGUOUS,
    CONTESTED_PREFIX,
    EVIDENCE_CONTENT,
    EVIDENCE_FILENAME,
    NO_REQUEST_ACCEPTS,
    OCR_ONLY,
    UNMATCHED,
    route_file,
    route_files,
)
from tracker.scaffold import MANIFEST_FILENAME

W2 = RequestItem(
    identifier="A01", document="W-2 Wage Statements", period="TY2025",
    expected_count=2, allowed_extensions=("pdf",), min_size_kb=0,
    required_keywords=("W-2",), date_pattern=r"(?i)\b2025\b",
)
INT_DIV = RequestItem(
    identifier="A02", document="1099-INT / 1099-DIV", period="TY2025",
    allowed_extensions=("pdf", "csv"), min_size_kb=0,
    any_keywords=("1099-int", "1099-div", "dividend"),
)
MORTGAGE = RequestItem(
    identifier="C01", document="Mortgage Interest Statement", period="TY2025",
    allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
)
# No keyword rules at all — deliberately unroutable.
DONATIONS = RequestItem(
    identifier="D01", document="Charitable Contribution Receipts",
    allowed_extensions=("pdf", "xlsx"), min_size_kb=0,
)
ITEMS = [W2, INT_DIV, MORTGAGE, DONATIONS]


# ------------------------------------------------------------- routed ----


def test_content_match_routes(tmp_path):
    f = text_pdf(tmp_path / "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    routing = route_file(f, ITEMS)
    assert routing.identifier == "A01"
    assert routing.evidence == EVIDENCE_CONTENT
    assert "content matched" in routing.reason


def test_extension_alone_is_not_evidence(tmp_path):
    """A PDF that says nothing recognizable must not fall into a pdf row."""
    f = text_pdf(tmp_path / "mystery.pdf", "Shopping list: milk, eggs")
    routing = route_file(f, ITEMS)
    assert routing.identifier is None
    assert routing.reason.startswith(UNMATCHED)
    # and the note tells the firm how to make it routable next time
    assert "D01" in routing.reason


def test_wrong_year_is_not_routed(tmp_path):
    """The 2024 W-2 fails A01's date rule and must not land anywhere.

    It must not quietly fall into some *other* row either: a document that
    announces itself as a W-2 is contested, so it goes to a human with the
    rule it failed spelled out.
    """
    prior_year = RequestItem(
        identifier="B01", document="Prior-Year Returns",
        allowed_extensions=("pdf",), min_size_kb=0,
        any_keywords=("tax statement",),   # boilerplate many forms carry
    )
    f = text_pdf(tmp_path / "old.pdf", "Form W-2 Wage and Tax Statement 2024")
    routing = route_file(f, [*ITEMS, prior_year])
    assert routing.identifier is None
    assert f"{CONTESTED_PREFIX} A01" in routing.reason
    assert reasons.WRONG_PERIOD.matches(routing.reason)


def test_filename_rescues_a_scan_with_no_text_layer(tmp_path):
    """An image-only PDF still routes when the client named it sensibly."""
    for name in ("Form 1098 Mortgage Interest.pdf", "smith_1098.pdf", "smith-1098-2025.pdf", "W2 2025.pdf"):
        f = tmp_path / name
        text_pdf(f, "")  # valid PDF, no usable text
        routing = route_file(f, ITEMS, text=None)
        assert routing.identifier == ("A01" if name.startswith("W2") else "C01"), name
        assert routing.evidence == EVIDENCE_FILENAME


def test_filename_match_respects_word_boundaries(tmp_path):
    f = tmp_path / "ledger-10983.pdf"
    text_pdf(f, "")
    assert route_file(f, ITEMS).identifier is None


def test_an_image_only_scan_routes_on_its_required_keywords_after_ocr(tmp_path, monkeypatch):
    # No text layer, and a name that says nothing: OCR is the only evidence
    # left, and it is read the way the scanner reads it. A required-keyword
    # match on OCR text is a filing decision.
    calls = []
    monkeypatch.setattr(
        "tracker.content_check._ocr_pdf",
        lambda p: (calls.append(p), "Form 1098 Mortgage Interest Statement 2025")[1],
    )
    f = text_pdf(tmp_path / "scan0012.pdf", "")
    routing = route_file(f, ITEMS)
    assert routing.identifier == "C01" and routing.evidence == EVIDENCE_CONTENT
    assert calls == [f]


def test_ocr_text_alone_never_routes_on_any_keywords(tmp_path, monkeypatch):
    # OCR misreads words; the looser any-keyword tier is exactly where a
    # misread "1099" files a document under the wrong request. A person
    # gets it, with the lead.
    monkeypatch.setattr(
        "tracker.content_check._ocr_pdf", lambda p: "Consolidated 1099 dividend summary 2025"
    )
    f = text_pdf(tmp_path / "scan0013.pdf", "")
    routing = route_file(f, ITEMS)
    assert routing.identifier is None
    assert routing.reason.startswith(OCR_ONLY) and routing.candidates == ("A02",)


def test_a_sensibly_named_scan_is_not_ocrd(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "tracker.content_check._ocr_pdf",
        lambda p: (_ for _ in ()).throw(AssertionError("OCR ran on a scan the name already routes")),
    )
    f = text_pdf(tmp_path / "Form 1098 Mortgage Interest.pdf", "")
    routing = route_file(f, ITEMS)
    assert routing.identifier == "C01" and routing.evidence == EVIDENCE_FILENAME


def test_the_router_and_the_scanner_reach_one_verdict_for_one_document(tmp_path, monkeypatch):
    # The verdicts the router reaches on a drop are the scanner's verdicts on
    # the working copy: same bytes, same reading, read once.
    from tests.test_content_check import counting_extractor
    from tracker.content_check import ContentCache, check_content

    calls = counting_extractor(monkeypatch)
    cache = ContentCache(tmp_path / "cache.json")
    dropped = text_pdf(tmp_path / "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert route_file(dropped, ITEMS, cache=cache).identifier == "A01"
    assert calls["n"] == 1

    working_copy = tmp_path / "A01 - W-2 Wage Statements - TY2025.pdf"
    working_copy.write_bytes(dropped.read_bytes())
    assert check_content(working_copy, W2, cache).ok
    assert not check_content(working_copy, MORTGAGE, cache).ok
    assert calls["n"] == 1                        # the scan never read it again


# ---------------------------------------------------------- not routed ----


def test_ambiguous_match_goes_to_review(tmp_path):
    """A combined 1099 that satisfies two rows is a person's decision."""
    both = RequestItem(
        identifier="E01", document="Brokerage Year-End",
        allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1099-b",),
    )
    # A composite prints each form's title on its own line; "1099-INT and
    # 1099-B" in one sentence would be a document talking about both.
    f = text_pdf(tmp_path / "combined.pdf", "Form 1099-INT Interest Income 2025\nForm 1099-B Proceeds From Broker 2025")
    routing = route_file(f, [INT_DIV, both])
    assert routing.identifier is None
    assert routing.reason.startswith(AMBIGUOUS)
    assert set(routing.candidates) == {"A02", "E01"}


def test_waived_rows_never_receive_files(tmp_path):
    waived = RequestItem(
        identifier="A01", document="W-2 Wage Statements",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("W-2",),
        manual_override=Override.WAIVED,
    )
    f = text_pdf(tmp_path / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    assert route_file(f, [waived]).identifier is None


def test_wrong_extension_is_not_routed(tmp_path):
    f = tmp_path / "Mortgage Notes 1098.docx"
    f.write_bytes(b"not a pdf " * 200)
    assert route_file(f, ITEMS).identifier is None


def test_google_stub_is_not_routed(tmp_path):
    f = tmp_path / "Donation Receipts 2025.gsheet"
    f.write_text('{"url": "https://docs.google.com/..."}', encoding="utf-8")
    assert route_file(f, ITEMS).identifier is None


def test_placeholder_is_left_alone(tmp_path, monkeypatch):
    f = text_pdf(tmp_path / "cloud.pdf", "Form W-2 Wage and Tax Statement 2025")
    monkeypatch.setattr("tracker.router.is_cloud_placeholder", lambda p: True)
    routing = route_file(f, ITEMS)
    assert routing.pending is True
    assert routing.identifier is None


def test_route_files_skips_sync_junk(tmp_path):
    good = text_pdf(tmp_path / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    junk = tmp_path / "w2.pdf.tmp.driveupload"
    junk.write_bytes(b"partial")
    routed = route_files([good, junk], ITEMS)
    assert [r.path for r in routed] == [good]


def test_required_keyword_beats_a_generic_any_keyword(tmp_path):
    """Two rows accept the file; the one asserting what it *is* wins.

    Real W-2s carry the line "To Be Filed With Employee's FEDERAL Tax
    Return", which a prior-year-returns row happily matches. A01 requires
    the document to say "W-2", which is the stronger claim.
    """
    prior_year = RequestItem(
        identifier="B01", document="Prior-Year Returns",
        allowed_extensions=("pdf",), min_size_kb=0,
        any_keywords=("tax return",),
    )
    f = text_pdf(
        tmp_path / "w2.pdf",
        "Form W-2 Wage and Tax Statement 2025 - Copy B To Be Filed With "
        "Employee's FEDERAL Tax Return",
    )
    assert route_file(f, [W2, prior_year]).identifier == "A01"


def test_keywords_match_on_token_boundaries(tmp_path):
    """'EIN' must not match 'being'; '1098' must not match '10983' - nor '1098-T'."""
    ein = RequestItem(
        identifier="Z01", document="EIN Letter", allowed_extensions=("pdf",),
        min_size_kb=0, any_keywords=("EIN",),
    )
    f = text_pdf(tmp_path / "note.pdf", "This is being sent regarding 10983 units")
    assert route_file(f, [ein, MORTGAGE]).identifier is None
    f = text_pdf(tmp_path / "IMG_2025_0311.pdf", "Form 1098-T Tuition Statement 2025 qualified tuition")
    assert route_file(f, [ein, MORTGAGE]).identifier is None


def test_a_tuition_statement_is_never_filed_as_mortgage_interest(tmp_path):
    # The one misfiling a required keyword of "1098" allowed: Form 1098-T
    # carries the number, and required keywords outrank the tuition row's
    # any-keywords. A hyphen-joined variant is part of the form's name.
    from dataclasses import replace

    from tracker.templates import template_items

    items = [replace(i, min_size_kb=0) for i in template_items("1040", year=2025)]   # L01 included
    f = text_pdf(tmp_path / "IMG_2025_0311.pdf", "Form 1098-T Tuition Statement 2025 qualified tuition")
    routing = route_file(f, items)
    assert routing.identifier == "L01"
    core = [i for i in items if i.identifier != "L01"]   # a manifest without the tuition row
    assert route_file(f, core).identifier is None
    core_only = [replace(i, min_size_kb=0) for i in template_items("1040", core_only=True, year=2025)]
    f = text_pdf(tmp_path / "IMG_2025_0312.pdf", "Form 1099-R Distributions From Pensions 2025")
    assert route_file(f, core_only).identifier is None   # not the 1099-INT/DIV row either
    f = text_pdf(tmp_path / "IMG_2025_0313.pdf", "Form 1098 Mortgage Interest Statement 2025")
    assert route_file(f, items).identifier == "C01"


def test_a_multi_page_scan_with_no_text_layer_still_routes_by_its_name(tmp_path):
    # Two blank pages extract to a newline, which is text to a truthiness
    # test and nothing to a reader. The name is the evidence, as for one page.
    f = text_pdf(tmp_path / "Form 1098 Mortgage Interest.pdf", "", pages=2)
    routing = route_file(f, ITEMS)
    assert routing.identifier == "C01" and routing.evidence == EVIDENCE_FILENAME
    f = text_pdf(tmp_path / "1098-T scan.pdf", "", pages=2)
    assert route_file(f, ITEMS).identifier is None


def test_google_stub_review_reason_tells_the_client_what_to_do(tmp_path):
    f = tmp_path / "Donation Receipts 2025.gsheet"
    f.write_text('{"url": "https://docs.google.com/..."}', encoding="utf-8")
    reason = route_file(f, ITEMS).reason
    assert reasons.GOOGLE_STUB.matches(reason)
    assert reasons.GOOGLE_EXPORT_HINT in reason


# ------------------------------------------------------ honest review reasons ----


def test_a_matching_document_the_row_refuses_says_why(tmp_path):
    # The content says "W-2", but the row's size floor rejects the file. The
    # review reason must carry the real cause, not UNMATCHED.
    strict = RequestItem(
        identifier="A01", document="W-2 Wage Statements", allowed_extensions=("pdf",),
        min_size_kb=50, required_keywords=("W-2",),
    )
    f = text_pdf(tmp_path / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    routing = route_file(f, [strict])
    assert routing.identifier is None
    assert f"{CONTESTED_PREFIX} A01" in routing.reason
    assert reasons.TOO_SMALL.matches(routing.reason) and "50 KB" in routing.reason
    assert routing.candidates == ("A01",)


def test_a_file_type_nobody_accepts_is_named_as_such(tmp_path):
    f = tmp_path / "notes.docx"
    f.write_bytes(b"not a real docx " * 100)
    routing = route_file(f, ITEMS)
    assert routing.identifier is None
    assert NO_REQUEST_ACCEPTS.format(extension="docx") in routing.reason


def test_a_corrupt_pdf_is_a_review_reason_not_a_crash(tmp_path):
    f = tmp_path / "broken.pdf"
    f.write_bytes(b"%PDF-1.4 garbage " * 40)
    routing = route_file(f, ITEMS)
    assert routing.identifier is None
    assert reasons.UNREADABLE_PDF.matches(routing.reason)


def test_filename_fallback_tolerates_the_run_together_spelling(tmp_path):
    # Clients name scans "W2", not "W-2". Same whole token, not a substring.
    f = text_pdf(tmp_path / "Smith W2 2025.pdf", "")
    routing = route_file(f, ITEMS)
    assert routing.identifier == "A01"
    assert routing.evidence == EVIDENCE_FILENAME
    # ...but "W20" is still not "W-2".
    other = text_pdf(tmp_path / "Smith W20 form.pdf", "")
    assert route_file(other, ITEMS).identifier is None


def test_a_derived_year_never_routes_on_its_own_but_still_contests(tmp_path):
    # Loaded from a manifest, C01's Period TY2025 implies a year check. A
    # 2024 mortgage statement says "1098", so it looks like C01 - and is
    # contested, not filed. A row with ONLY a derived year never claims a
    # document just because the document mentions the year.
    from tracker.manifest import create_template, load_manifest

    path = create_template(tmp_path / MANIFEST_FILENAME, [
        RequestItem(identifier="C01", document="Mortgage Interest Statement", period="TY2025",
                    allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",)),
        RequestItem(identifier="Z01", document="Anything from 2025", period="TY2025",
                    allowed_extensions=("pdf",), min_size_kb=0),
    ])
    items = load_manifest(path)
    old = text_pdf(tmp_path / "old.pdf", "Form 1098 Mortgage Interest Statement 2024")
    routing = route_file(old, items)
    assert routing.identifier is None
    assert f"{CONTESTED_PREFIX} C01" in routing.reason and reasons.WRONG_PERIOD.matches(routing.reason)

    current = text_pdf(tmp_path / "new.pdf", "Form 1098 Mortgage Interest Statement 2025")
    assert route_file(current, items).identifier == "C01"

    only_year = text_pdf(tmp_path / "letter.pdf", "A letter dated March 2025 about nothing")
    routing = route_file(only_year, items)
    assert routing.identifier is None                      # Z01 must not claim it
    assert "add a keyword to Z01" in routing.reason


def test_a_scanners_stamp_is_not_a_text_layer(tmp_path):
    # "Page 1 of 2" on each of two pages, or "Scanned by CamScanner" on one,
    # is more than a handful of characters and still no reading of the
    # document. The name routes it, as for a blank scan.
    for text, pages in (("Page 1 of 2", 2), ("Scanned by CamScanner", 1)):
        f = text_pdf(tmp_path / "Form 1098 Mortgage Interest.pdf", text, pages=pages)
        routing = route_file(f, ITEMS)
        assert routing.identifier == "C01" and routing.evidence == EVIDENCE_FILENAME, text


def test_a_clients_hyphenated_file_name_still_routes(tmp_path):
    # A form's own variant is part of its name; a bank's or a person's is
    # a separator. Both sides of the hyphen, both ways.
    for name, expected in (
        ("1098-Citi.pdf", "C01"), ("W2-Tom.pdf", "A01"), ("Jane-W2.pdf", "A01"),
        ("smith-1098-mtg.pdf", "C01"), ("1098-T.pdf", None), ("W-2G winnings.pdf", None),
    ):
        f = text_pdf(tmp_path / name, "")
        assert route_file(f, ITEMS).identifier == expected, name


def test_a_run_together_form_number_is_still_its_own_variant(tmp_path):
    # "Form1040-ES.pdf" is not last year's Form 1040. The keyword pattern
    # reads "form 1040" as "form1040" itself; a separate run-together
    # fallback used to skip the variant rule.
    from dataclasses import replace

    from tracker.templates import template_items

    items = [replace(i, min_size_kb=0) for i in template_items("1040", core_only=True, year=2025)]
    for name in ("Form1040-ES.pdf", "Form1040 V.pdf", "Form1040_V.pdf", "Form 1040-V.pdf"):
        assert route_file(text_pdf(tmp_path / name, ""), items).identifier is None, name
    assert route_file(text_pdf(tmp_path / "W2 2025.pdf", ""), items).identifier == "A01"


def test_a_keyword_with_nothing_in_it_matches_nothing(tmp_path):
    # "-" or "n/a" typed into a keyword cell must not be a keyword that
    # every document satisfies - least of all a required one.
    dash = RequestItem(
        identifier="Z01", document="Not applicable", allowed_extensions=("pdf",),
        min_size_kb=0, required_keywords=("-",),
    )
    f = text_pdf(tmp_path / "IMG_2025_0312.pdf", "Form 1099-R Distributions From Pensions 2025")
    assert route_file(f, [dash]).identifier is None
    assert route_file(f, [dash, MORTGAGE]).identifier is None


def _shipped_rows(tmp_path, form="1040"):
    """A catalog as an engagement loads it: the Period-derived date check
    is live, which template_items() alone does not give."""
    from dataclasses import replace

    from tracker.manifest import create_template, load_manifest
    from tracker.templates import template_items

    manifest = tmp_path / MANIFEST_FILENAME
    manifest.unlink(missing_ok=True)
    create_template(manifest, template_items(form, year=2025))
    return [replace(i, min_size_kb=0) for i in load_manifest(manifest)]


def _shipped_1040_rows(tmp_path):
    return _shipped_rows(tmp_path, "1040")


def test_a_document_whose_year_alone_failed_names_the_row_it_looks_like(tmp_path):
    """"Matched no request" is a lie about last year's childcare statement.

    Only six of the seventy-eight catalog rows have required keywords, so
    only six could ever be *contested*; on the rest, a document that
    matched every keyword and failed the year went to a person with no
    candidate and nothing to go on, and the client was asked the generic
    ask. The decision is unchanged - it is still parked, because the year
    is a check and never evidence - but the reason names the row, the
    candidates travel with it, and the ask is the wrong-period one.
    """
    items = _shipped_1040_rows(tmp_path)
    f = text_pdf(tmp_path / "childcare.pdf",
                 "Bright Horizons Learning Center\n2024 Childcare Statement\nProvider EIN 12-3456789")
    routing = route_file(f, items)
    assert routing.identifier is None
    assert f"{CONTESTED_PREFIX} J01" in routing.reason
    assert routing.candidates == ("J01",)
    assert routing.evidence == EVIDENCE_CONTENT
    assert reasons.find(routing.reason) is reasons.WRONG_PERIOD


def test_a_lead_never_takes_a_filing_from_the_row_that_accepted_the_file(tmp_path):
    """A row whose any-keywords matched with the wrong year is a lead, not a
    claim: unlike a required-keyword match it pre-empts nothing, so a file
    one row accepts is still filed there."""
    childcare = RequestItem(
        identifier="J01", document="Childcare Provider Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0,
        any_keywords=("child care statement",), date_pattern=r"(?i)\b2025\b",
    )
    receipts = RequestItem(
        identifier="D01", document="Charitable Contribution Receipts",
        allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("donation receipt",),
    )
    f = text_pdf(tmp_path / "both.pdf", "2024 Child Care Statement\nGoodwill Donation Receipt")
    routing = route_file(f, [childcare, receipts])
    assert routing.identifier == "D01"
    # And with nobody to file it, the lead is what the person is given.
    assert route_file(f, [childcare]).candidates == ("J01",)


@pytest.mark.parametrize("name, text, expected", [
    # What other forms print about their neighbours must not file them there.
    ("2024 Tax Return.pdf",
     "Form 1040 U.S. Individual Income Tax Return 2024\nFiling Status Single\nAttach Form(s) W-2 here.\n"
     "1a Total amount from Form(s) W-2\n36 Amount applied to your 2025 estimated tax\n"
     "Sign Here Under penalties of perjury, I declare that I have examined this return", "B01"),
    ("1095-C.pdf",
     "Form 1095-C Employer-Provided Health Insurance Offer and Coverage 2025\nIf you purchased health "
     "insurance coverage for 2025 through the Health Insurance Marketplace and wish to claim the premium tax credit", None),
    ("1095-B.pdf",
     "Form 1095-B Health Coverage 2025\nPart III Issuer or Other Coverage Provider", None),
    ("1099-SA.pdf",
     "Form 1099-SA Distributions From an HSA 2025\nBox 1 The amount may have been a direct payment to the "
     "medical service provider or distributed to you.", None),
    ("5498-SA.pdf",
     "Form 5498-SA HSA, Archer MSA, or Medicare Advantage MSA Information 2025\n"
     "Box 2 Total HSA or Archer MSA contributions made in 2025", "K01"),
    ("W-2.pdf", "Form W-2 Wage and Tax Statement 2025\na Employee's social security number\nCopy B To Be Filed With Employee's FEDERAL Tax Return", "A01"),
    ("1095-A.pdf", "Form 1095-A Health Insurance Marketplace Statement 2025", "I01"),
    ("church.pdf", "Annual Contribution Statement 2025\nNo goods or services were provided in exchange for these contributions", "D01"),
    ("K-1.pdf", "Schedule K-1 (Form 1065) 2025 Partner's Share of Income\n5 Interest income 120", "F01"),
])
def test_the_shipped_1040_catalog_files_real_forms_where_they_belong(tmp_path, name, text, expected):
    items = _shipped_1040_rows(tmp_path)
    assert route_file(text_pdf(tmp_path / name, text), items).identifier == expected, name


# ------------------------------------------------------- the evidence record ----


def test_a_routed_file_records_which_keyword_matched_and_where(tmp_path):
    from tracker.content_check import RULE_REQUIRED, WHERE_TITLE

    f = text_pdf(tmp_path / "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    routing = route_file(f, ITEMS)
    assert routing.identifier == "A01"
    found = routing.evidence_record["A01"]
    assert [(e.rule, e.term, e.where) for e in found if e.rule == RULE_REQUIRED] == [
        (RULE_REQUIRED, "W-2", WHERE_TITLE),
    ]


def test_the_record_names_only_the_rows_the_decision_names(tmp_path):
    # Every row considered leaves something behind; one index cell must not
    # carry the whole manifest's workings.
    f = text_pdf(tmp_path / "scan0012.pdf", "Form W-2 Wage and Tax Statement 2025")
    routing = route_file(f, ITEMS)
    assert set(routing.evidence_record) == set(routing.candidates) == {"A01"}


def test_a_file_routed_by_its_name_records_the_name_as_its_evidence(tmp_path):
    from tracker.content_check import RULE_FILENAME, WHERE_TITLE

    f = text_pdf(tmp_path / "smith_1098.pdf", "")     # a scan, no text layer
    routing = route_file(f, ITEMS)
    assert routing.identifier == "C01" and routing.evidence == EVIDENCE_FILENAME
    # A name is all title and has no pages.
    assert [(e.rule, e.term, e.where, e.page) for e in routing.evidence_record["C01"]] == [
        (RULE_FILENAME, "1098", WHERE_TITLE, 0),
    ]


def test_a_tier_two_refusal_travels_as_the_reasons_own_code(tmp_path):
    from tracker.content_check import RULE_REFUSED

    strict = RequestItem(
        identifier="A01", document="W-2 Wage Statements", allowed_extensions=("pdf",),
        min_size_kb=50, required_keywords=("W-2",),
    )
    f = text_pdf(tmp_path / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    routing = route_file(f, [strict])
    assert routing.candidates == ("A01",)
    # The code, not the sentence: the sentence is written for a person and
    # may be reworded; reasons.TOO_SMALL.code is the cause's one name.
    assert [(e.rule, e.term) for e in routing.evidence_record["A01"] if e.rule == RULE_REFUSED] == [
        (RULE_REFUSED, reasons.TOO_SMALL.code),
    ]


def test_a_blocked_file_keeps_the_request_it_looked_like_beside_the_refusal(tmp_path):
    """The refusal says which rule said no; only the keyword says which request."""
    from tracker.content_check import RULE_REFUSED, RULE_REQUIRED, WHERE_TITLE

    strict = RequestItem(
        identifier="A01", document="W-2 Wage Statements", allowed_extensions=("pdf",),
        min_size_kb=50, required_keywords=("W-2",),
    )
    f = text_pdf(tmp_path / "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    routing = route_file(f, [strict])

    # The content fit the row and the file itself was refused: both halves
    # are on the record, so a reader knows what it looked like and why it
    # was not filed. The verdict was already read to decide that; keeping
    # what it found costs no second reading.
    assert [(e.rule, e.term, e.where) for e in routing.evidence_record["A01"]] == [
        (RULE_REQUIRED, "W-2", WHERE_TITLE),
        (RULE_REFUSED, reasons.TOO_SMALL.code, ""),
    ]
    assert routing.identifier is None, "a blocked file is still never filed"


def test_a_contested_file_keeps_the_keywords_that_did_match(tmp_path):
    from tracker.content_check import RULE_REQUIRED

    # Last year's W-2: the required keyword matched, the year did not.
    f = text_pdf(tmp_path / "w2.pdf", "Form W-2 Wage and Tax Statement 2024")
    routing = route_file(f, ITEMS)
    assert routing.identifier is None and routing.candidates == ("A01",)
    assert [(e.rule, e.term) for e in routing.evidence_record["A01"]] == [
        (RULE_REQUIRED, "W-2"),
    ]
