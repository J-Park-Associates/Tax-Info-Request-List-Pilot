"""The shipped catalogs against the IRS's own forms.

``tests/irs/`` holds the blank forms as the IRS publishes them (irs.gov,
public domain: fifty fetched 2026-09-17, the two W-2 revisions and, with
decision 96, every variant ``FORM_VARIANTS`` names that irs.gov publishes,
2026-09-18) and the California and New York returns the catalogs name
(ftb.ca.gov and tax.ny.gov, the same day): the blank Copy B with its
Instructions for Recipient, a return with its schedules, a K-1 of each
flavour, the notices and transmittals that mention forms they are not, the
prior revisions whose layout changed, and the siblings that share a family's
lines (1120 and 1120-F, W-2 and W-2c) so that no form is known only by what
its neighbours do not print. Each is routed
against a shipped catalog the way an engagement routes it - through
validated() over template_items(), the same validation create_engagement()
makes - and must land where it belongs, or park. A reconstruction typed from memory omits the instruction page
that names three other forms; these do not.

Two rules are lifted, as tests/test_catalog.py lifts them: the size floor
(a blank form is small) and the Period's year check (a continuous-use
form prints "For calendar year 20__" and no year; a filled one prints the
year). The year check has its own tests. ``None`` means the form must
park: no row in that catalog asks for it, or it is another form's own
document, and misfiling a tax document is worse than not filing it.
"""

from dataclasses import replace

import pytest

from tests.routing_cases import EXPECT, IRS, cp_notice_lines, ssa_1099_lines
from tests.samples import text_pdf
from tracker.manifest import validated
from tracker.router import route_file
from tracker.templates import template_items


@pytest.fixture(scope="module")
def catalogs():
    built = {}

    def rows(form, year):
        if (form, year) not in built:
            built[(form, year)] = [replace(i, min_size_kb=0, date_pattern="")
                                   for i in validated(template_items(form, year=year))]
        return built[(form, year)]

    return rows


@pytest.mark.parametrize("pdf, form, year, expected", EXPECT, ids=[f"{p}-{f}" for p, f, _, _ in EXPECT])
def test_the_irs_blank_corpus_keeps_every_placement_and_every_park(catalogs, pdf, form, year, expected):
    """Every committed placement, and every committed park (decision 96,
    and decision 141's claim 2): a catalog change may file a blank that
    parked only into a new row that names that blank's own form."""
    routing = route_file(IRS / pdf, catalogs(form, year))
    assert routing.identifier == expected, (pdf, form, routing.reason)


@pytest.mark.parametrize("pdf", ["fw2c.pdf", "fw3c.pdf", "fw3ss.pdf", "fw3pr.pdf"])
def test_the_w3_family_and_the_w2c_park_on_the_1040(catalogs, pdf):
    """Decision 140, claim 6. Every looser A01 rule the fact sheet tried
    filed the W-3 family and the W-2c as W-2s, and only ``fw3.pdf``'s
    expectation noticed. Each is pinned here, so no later keyword change
    files one silently. They park; since decision 140 a person is shown
    A01, because each shows the W-2's number - and A01 is never a
    candidate, so nothing files on it."""
    routing = route_file(IRS / pdf, catalogs("1040", 2025))
    assert routing.identifier is None, (pdf, routing.reason)
    assert routing.candidates == (), (pdf, routing.reason)


# ------------------------------------------------ decision 141's claims ----


def _without(rows, identifier):
    return [item for item in rows if item.identifier != identifier]


def test_an_ssa_1099_files_a07_and_never_e02(catalogs, tmp_path):
    """The SSA publishes no blank, so the page is typed from the lines the
    SSA prints (``tests.test_catalog.ssa_1099_lines``). The collision was
    the revision code at the top of the page, "Form SSA-1099-R-OP1": E02's
    `1099-r` is said there, in the title, and without A07 the statement
    files as a 1099-R. With A07 it files A07, because a required keyword
    outranks an any keyword; E02 keeps its `1099-r`."""
    page = text_pdf(tmp_path / "SSA-1099.pdf", chr(10).join(ssa_1099_lines(2025)))
    rows = catalogs("1040", 2025)
    assert route_file(page, _without(rows, "A07")).identifier == "E02"      # the cause, kept
    routing = route_file(page, rows)
    assert routing.identifier == "A07", routing.reason
    assert "E02" not in routing.filed_to


def test_a_1099_r_still_files_e02(catalogs):
    """The IRS's own 1099-R says nothing A07 asks for, and files E02."""
    routing = route_file(IRS / "f1099r.pdf", catalogs("1040", 2025))
    assert routing.identifier == "E02", routing.reason
    assert "A07" not in routing.candidates


def test_a_1040_es_parks_on_the_1041_and_a_1041_es_files_g01(catalogs, tmp_path):
    """The designer's ruling on G1: the 1041's G01 keeps the owner's title
    and files only the 1041-ES - the IRS's booklet, and a voucher torn off
    and sent alone. An individual's 1040-ES, the booklet or one voucher, is
    another entity's estimated payments and parks (decision 96's (b)).
    The Period check is lifted, as for every blank here."""
    rows = catalogs("1041", 2025)
    assert route_file(IRS / "f1041es.pdf", rows).identifier == "G01"
    assert route_file(IRS / "f1040es_2025.pdf", rows).identifier is None
    assert route_file(IRS / "f1040es.pdf", catalogs("1041", 2026)).identifier is None
    voucher_1041 = text_pdf(tmp_path / "1041-ES voucher.pdf", chr(10).join([
        "Form 1041-ES 2025 Payment Voucher 3",
        "File only if the estate or trust is making a payment of estimated tax.",
        "Amount of estimated tax you are paying by check or money order.",
    ]))
    voucher_1040 = text_pdf(tmp_path / "1040-ES voucher.pdf", chr(10).join([
        "Form 1040-ES 2025 Estimated Tax Payment Voucher 3",
        "Amount of estimated tax you are paying by check or money order.",
    ]))
    assert route_file(voucher_1041, rows).identifier == "G01"
    routing = route_file(voucher_1040, rows)
    assert routing.identifier is None and "G01" not in routing.candidates, routing.reason


def test_a_1099_g_read_as_1099_c_does_not_file_a08(catalogs, tmp_path):
    """The designer's ruling on G4. OCR reads a 1099-G's "G" as "C"; a page
    that says "1099-C" and the 1099-G's own words parks, because A08 wants
    the 1099-C's words as well as its number. On the number alone - the
    rule as first built - the same page filed A08."""
    misread = text_pdf(tmp_path / "1099-G misread.pdf", chr(10).join([
        "Form 1099-C 2025 Certain Government Payments Copy B For Recipient",
        "PAYER'S name, street address, city or town",
        "1 Unemployment compensation 4 Federal income tax withheld",
        "2 State or local income tax refunds, credits, or offsets",
    ]))
    rows = catalogs("1040", 2025)
    number_alone = [replace(i, required_keywords=("1099-c",)) if i.identifier == "A08" else i for i in rows]
    assert route_file(misread, number_alone).identifier == "A08"      # the risk, kept visible
    routing = route_file(misread, rows)
    assert routing.identifier is None and "A08" not in routing.filed_to, routing.reason
    assert route_file(IRS / "f1099c.pdf", rows).identifier == "A08"   # the real form still files


@pytest.mark.corpus
def test_a_notice_files_z01_and_no_return_or_form_does(catalogs, tmp_path):
    """The notices row files a CP notice on every catalog, and no blank the
    IRS or a state publishes - return, schedule, information return,
    voucher or transmittal - is one: each is read against Z01 alone, so
    nothing else in a catalog can stand in the way of a false match."""
    notice = text_pdf(tmp_path / "CP14.pdf", chr(10).join(cp_notice_lines(2025)))
    forms = ("1040", "1120", "1120S", "1065", "1041", "990")
    for form in forms:
        routing = route_file(notice, catalogs(form, 2025))
        assert routing.identifier == "Z01", (form, routing.reason)
    # One row on every catalog (tests/test_templates.py holds it to that),
    # so the 1040's is every catalog's.
    z01 = [item for item in catalogs("1040", 2025) if item.identifier == "Z01"]
    filed = [pdf.name for pdf in sorted(IRS.glob("*.pdf")) if route_file(pdf, z01).identifier]
    assert filed == []
