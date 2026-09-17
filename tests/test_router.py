"""Tests for tracker/router.py — deciding where a dropped file belongs.

The rule under test throughout: route only when the evidence is
unambiguous, and never guess. A misfiled tax document is worse than one
sitting in Needs Review.
"""



from tests.test_scanner import text_pdf
from tracker import reasons
from tracker.manifest import Override, RequestItem
from tracker.router import (
    AMBIGUOUS,
    CONTESTED_PREFIX,
    EVIDENCE_CONTENT,
    EVIDENCE_FILENAME,
    NO_REQUEST_ACCEPTS,
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
    any_keywords=("1099", "dividend"),
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
    f = tmp_path / "Form 1098 Mortgage Interest.pdf"
    text_pdf(f, "")  # valid PDF, no usable text
    routing = route_file(f, ITEMS, text=None)
    assert routing.identifier == "C01"
    assert routing.evidence == EVIDENCE_FILENAME


def test_filename_match_respects_word_boundaries(tmp_path):
    f = tmp_path / "ledger-10983.pdf"
    text_pdf(f, "")
    assert route_file(f, ITEMS).identifier is None


# ---------------------------------------------------------- not routed ----


def test_ambiguous_match_goes_to_review(tmp_path):
    """A combined 1099 that satisfies two rows is a person's decision."""
    both = RequestItem(
        identifier="E01", document="Brokerage Year-End",
        allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("1099",),
    )
    f = text_pdf(tmp_path / "combined.pdf", "Form 1099-INT and 1099-B combined 2025")
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
    """'EIN' must not match 'being'; '1098' must not match '10983'."""
    ein = RequestItem(
        identifier="Z01", document="EIN Letter", allowed_extensions=("pdf",),
        min_size_kb=0, any_keywords=("EIN",),
    )
    f = text_pdf(tmp_path / "note.pdf", "This is being sent regarding 10983 units")
    assert route_file(f, [ein, MORTGAGE]).identifier is None


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
