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
from pathlib import Path

import pytest

from tests.test_catalog import cp_notice_lines, ssa_1099_lines
from tests.test_scanner import text_pdf
from tracker.manifest import validated
from tracker.router import route_file
from tracker.templates import template_items

IRS = Path(__file__).parent / "irs"

#: (form as the IRS names its file, catalog, engagement year, where it belongs)
EXPECT = [
    # The 2026 revision prints two copies to the page and says "W-2 2026"; the
    # 2024 and 2025 revisions print one copy, whose only "W-2" is the foot's
    # "W-2 Wage and Tax Statement 2025 Department of the Treasury" (decision 85).
    ("fw2.pdf", "1040", 2025, "A01"), ("fw2_2024.pdf", "1040", 2025, "A01"), ("fw2_2025.pdf", "1040", 2025, "A01"),
    ("fw3.pdf", "1040", 2025, None), ("fw3.pdf", "1120", 2025, "E01"),
    ("f1099int.pdf", "1040", 2025, "A02"), ("f1099div.pdf", "1040", 2025, "A02"), ("f1099oid.pdf", "1040", 2025, "A02"),
    ("f1099int.pdf", "1041", 2025, "B01"), ("f1099div.pdf", "1041", 2025, "B01"), ("f1099nec.pdf", "1041", 2025, "B01"),
    ("f1099msc.pdf", "1041", 2025, "B01"), ("f1099r.pdf", "1040", 2025, "E02"),
    # Decision 90, the owner's: the 1040 catalog asks for these four by
    # name now, so the blanks file rather than park. The two beside them
    # still park - no 1040 row asks for a 1099-S or a 1099-SA.
    ("f1099nec.pdf", "1040", 2025, "A03"), ("f1099nec_2024.pdf", "1040", 2025, "A03"),
    ("f1099msc.pdf", "1040", 2025, "A04"), ("f1099k.pdf", "1040", 2025, "A05"),
    ("f1099g.pdf", "1040", 2025, "A06"), ("f1099s.pdf", "1040", 2025, None),
    ("f1099sa.pdf", "1040", 2025, None), ("f1098.pdf", "1040", 2025, "C01"), ("f1098t.pdf", "1040", 2025, "L01"),
    ("f1095a.pdf", "1040", 2025, "I01"), ("f1095b.pdf", "1040", 2025, None), ("f1095c.pdf", "1040", 2025, None),
    ("f5498.pdf", "1040", 2025, "K01"), ("f5498sa.pdf", "1040", 2025, "K01"),
    ("f1040.pdf", "1040", 2026, "B01"), ("f1040x.pdf", "1040", 2026, "B01"), ("f1040nr.pdf", "1040", 2026, None),
    ("f1040s.pdf", "1040", 2026, None), ("f1040sa.pdf", "1040", 2026, None), ("f1040sb.pdf", "1040", 2026, None),
    ("f1040sd.pdf", "1040", 2026, None), ("f1040s1.pdf", "1040", 2026, None),
    # The 1040-ES booklet's instructions say "estimated tax payment voucher" in prose, which is not
    # a voucher; the 2025 package's vouchers are within the pages read and say what a voucher says.
    ("f1040es.pdf", "1040", 2026, None), ("f1040es_2025.pdf", "1040", 2025, "H01"), ("f1040es.pdf", "1120", 2026, None),
    ("f4868.pdf", "1040", 2026, None), ("f8879.pdf", "1040", 2026, None), ("f1096.pdf", "1040", 2025, None),
    ("f1096.pdf", "1120", 2025, None), ("f1096.pdf", "1041", 2025, None),
    ("f1120.pdf", "1120", 2026, "A01"), ("f1120h.pdf", "1120", 2026, None), ("f1120s.pdf", "1120", 2026, None),
    ("f1120s.pdf", "1120S", 2026, "A01"), ("f1120ssk.pdf", "1120S", 2025, None), ("f1120ssk.pdf", "1040", 2025, "F01"),
    ("f1120ssk_2024.pdf", "1040", 2025, "F01"),          # the year check, lifted here, is what parks last year's
    ("f1065.pdf", "1065", 2026, "A01"), ("f1065sk1.pdf", "1040", 2025, "F01"), ("f1065sk1_2024.pdf", "1040", 2025, "F01"),
    ("f1065sk1.pdf", "1065", 2025, "H01"), ("f1065sk1.pdf", "1041", 2025, None), ("f1065sk1.pdf", "1120", 2025, "J01"),
    ("f1041.pdf", "1041", 2026, "A03"), ("f1041sk1.pdf", "1040", 2025, "F01"), ("f1041sk1.pdf", "1041", 2025, None),
    ("f1041sk1.pdf", "1120S", 2025, "I01"),
    ("f990.pdf", "990", 2026, "A01"), ("f990ez.pdf", "990", 2026, "A01"), ("f990pf.pdf", "990", 2026, None),
    ("f940.pdf", "1120", 2025, "E01"), ("f941.pdf", "1120", 2025, "E01"), ("f940.pdf", "1120S", 2025, "E01"),
    ("f941.pdf", "990", 2025, "G01"), ("f941.pdf", "1040", 2025, None), ("f940.pdf", "1041", 2025, None),
    # The same shared row, in the two catalogs decision 90 added it to:
    # before it, Form 4562 parked in both because nothing asked for it.
    ("f4562.pdf", "1120", 2025, "C02"), ("f4562.pdf", "1120S", 2025, "F02"), ("f4562.pdf", "1065", 2025, "D02"),
    ("f1125e.pdf", "1120", 2025, None),
    # The ninth reading: the IRS "Attention" page ahead of every information
    # return names Form 1099-NEC by way of example, and is not a 1099; a
    # return's own lines ("dividends and distributions in exchange for
    # stock", "the ownership percentage (by vote or value)", "D-Donation")
    # are not a 1099-DIV, a shareholder list or a charitable receipt.
    ("f5498.pdf", "1041", 2025, None), ("f1098t.pdf", "1041", 2025, None), ("f1099g.pdf", "1041", 2025, None),
    ("f1099k.pdf", "1041", 2025, None), ("f1099s.pdf", "1041", 2025, None),
    ("f1120.pdf", "1040", 2026, None), ("f1120.pdf", "1120S", 2026, None), ("f1120.pdf", "1065", 2026, None),
    ("f1065.pdf", "1120", 2026, None), ("f1065.pdf", "1120S", 2026, None), ("f990pf.pdf", "1040", 2026, None),
    # The thirteenth reading: placements the corpus already held and no
    # catalog was asked for, and the one the split of the estimated-tax row
    # settles - an individual's 1040-ES package is not a corporation's
    # estimated tax record, whichever catalog it is dropped into.
    ("f1099oid.pdf", "1041", 2025, "B01"), ("f1099r.pdf", "1041", 2025, "B01"),
    ("f941.pdf", "1120S", 2025, "E01"), ("fw3.pdf", "1120S", 2025, "E01"),
    ("f940.pdf", "990", 2025, "G01"), ("fw3.pdf", "990", 2025, "G01"),
    ("f1040es_2025.pdf", "1120", 2025, None),
    # Decision 96: the corpus completed. A W-2 for a territory is a W-2, an
    # amended return is that return, an amended 941 is a payroll return and a
    # 990-T is what the 990's H01 names; a corrected or transmittal form is
    # not a wage statement; a return type no catalog serves parks, as the
    # 1120-H always has; an information return no row names parks.
    ("fw2as.pdf", "1040", 2025, "A01"), ("fw2gu.pdf", "1040", 2025, "A01"), ("fw2vi.pdf", "1040", 2025, "A01"),
    ("fw2g.pdf", "1040", 2025, "A09"), ("fw2g.pdf", "1041", 2025, None),
    ("fw3c.pdf", "1120", 2025, None), ("fw3pr.pdf", "1120", 2025, None), ("fw3ss.pdf", "1120", 2025, None),
    ("f941x.pdf", "1120", 2025, "E01"), ("f941x.pdf", "1120S", 2025, "E01"), ("f941x.pdf", "990", 2025, "G01"),
    ("f941x.pdf", "1040", 2025, None),
    ("f990t.pdf", "990", 2026, "H01"), ("f990t.pdf", "1040", 2026, None),
    ("f1120x.pdf", "1120", 2026, "A01"), ("f1120x.pdf", "1120S", 2026, None), ("f1120x.pdf", "1040", 2026, None),
    ("f1120c.pdf", "1120", 2026, None), ("f1120f.pdf", "1120", 2026, None), ("f1120l.pdf", "1120", 2026, None),
    ("f1120pc.pdf", "1120", 2026, None), ("f1120pol.pdf", "1120", 2026, None), ("f1120rei.pdf", "1120", 2026, None),
    ("f1120ric.pdf", "1120", 2026, None), ("f1120sf.pdf", "1120", 2026, None), ("f1120nd.pdf", "1120", 2026, None),
    ("f1120f.pdf", "1120S", 2026, None), ("f1120f.pdf", "1040", 2026, None),
    ("f1040c.pdf", "1040", 2026, None), ("f1040ss.pdf", "1040", 2026, None), ("f1040v.pdf", "1040", 2026, None),
    ("f1041n.pdf", "1041", 2026, None), ("f1041v.pdf", "1041", 2026, None), ("f1041t.pdf", "1041", 2025, None),
    ("f1041es.pdf", "1041", 2025, "G01"),     # parked until decision 141 gave the 1041 its estimated-tax row
    ("f1041a.pdf", "1040", 2026, None), ("f1041qft.pdf", "1040", 2026, None),
    ("f1098c.pdf", "1040", 2025, None), ("f1098e.pdf", "1040", 2025, "L02"), ("f1098f.pdf", "1040", 2025, None),
    ("f1098q.pdf", "1040", 2025, None), ("f1099a.pdf", "1040", 2025, None), ("f1099c.pdf", "1040", 2025, "A08"),
    ("f1099cap.pdf", "1040", 2025, None), ("f1099h.pdf", "1040", 2025, None), ("f1099ls.pdf", "1040", 2025, None),
    ("f1099ltc.pdf", "1040", 2025, None), ("f1099q.pdf", "1040", 2025, "L03"), ("f1099qa.pdf", "1040", 2025, None),
    ("f1099sb.pdf", "1040", 2025, None), ("f5498qa.pdf", "1040", 2025, None),
    ("f1099c.pdf", "1041", 2025, None), ("f1099q.pdf", "1041", 2025, None), ("f1098e.pdf", "1041", 2025, None),
    # The state forms: decision 90 files a standalone state return into the
    # "& State" row and decision 93 a state K-1 on the K-1 row; a state
    # form for another entity, or the LLC fee form, parks.
    ("ca540.pdf", "1040", 2026, "B01"), ("ca540.pdf", "1041", 2026, None),
    ("nyit201.pdf", "1040", 2026, "B01"), ("nyit201.pdf", "1041", 2026, None),
    ("ca100s.pdf", "1120S", 2026, "A01"), ("ca100s.pdf", "1120", 2026, None),
    ("ca565.pdf", "1065", 2026, "A01"), ("ca565.pdf", "1040", 2026, None), ("ca565.pdf", "1120S", 2026, None),
    ("ca568.pdf", "1065", 2026, "A01"), ("ca568.pdf", "1040", 2026, None), ("ca568.pdf", "1120S", 2026, None),
    ("nyit204.pdf", "1065", 2026, "A01"), ("nyit204.pdf", "1040", 2026, None),
    ("nyit204ll.pdf", "1065", 2026, None), ("nyit204ll.pdf", "1040", 2026, None),
    ("ca568k1.pdf", "1040", 2025, "F01"), ("nyit204ip.pdf", "1040", 2025, "F01"), ("nyit204ip.pdf", "1065", 2025, "H01"),
    # Decision 141, the owner's rows. Each blank that files here names its
    # own form and files the row that asks for that form: the K-1s a
    # business receives (the federal partnership and fiduciary K-1s, the
    # California LLC's and New York's partner K-1), the 1099-K and 1099-NEC
    # a business receives, and the 1099-C, W-2G, 1098-E and 1099-Q above.
    # The S corporation's K-1 still parks in every business catalog - no
    # corporation or partnership can hold S stock - and the CA 568 K-1 in a
    # 1065 now files the partnership's K-1 row on its required title, which
    # closes decision 85's F1.
    ("f1065sk1.pdf", "1120S", 2025, "I01"), ("f1065sk1_2024.pdf", "1065", 2025, "H01"),
    ("f1041sk1.pdf", "1065", 2025, "H01"), ("f1041sk1.pdf", "1120", 2025, "J01"),
    ("ca568k1.pdf", "1065", 2025, "H01"), ("ca568k1.pdf", "1120", 2025, "J01"), ("ca568k1.pdf", "1120S", 2025, "I01"),
    ("nyit204ip.pdf", "1120", 2025, "J01"), ("nyit204ip.pdf", "1120S", 2025, "I01"),
    ("f1120ssk.pdf", "1065", 2025, None), ("f1120ssk.pdf", "1120", 2025, None),
    ("f1099k.pdf", "1120", 2025, "J02"), ("f1099k.pdf", "1120S", 2025, "I02"), ("f1099k.pdf", "1065", 2025, "H02"),
    ("f1099nec.pdf", "1120", 2025, "J02"), ("f1099nec.pdf", "1120S", 2025, "I02"), ("f1099nec.pdf", "1065", 2025, "H02"),
    ("f1099nec_2024.pdf", "1065", 2025, "H02"),
    # The 1041's G01 is the 1041-ES's row: an individual's 1040-ES, package
    # or voucher, is another entity's estimated payments there and parks.
    ("f1040es_2025.pdf", "1041", 2025, None), ("f1040es.pdf", "1041", 2026, None),
    # The owner's item 17, now committed: a corrected or amended form parks
    # in every catalog, whatever row it resembles - the W-2c and W-3c are
    # not wage statements or transmittals, the 1065-X's title is not the
    # 1065's, and the 1099-DA is broker proceeds without the 1099-B's words.
    *[(pdf, form, 2025, None)
      for pdf in ("fw2c.pdf", "fw3c.pdf", "f1065x.pdf", "f1099da.pdf")
      for form in ("1040", "1120", "1120S", "1065", "1041", "990")
      if (pdf, form) != ("fw3c.pdf", "1120")],
    # Not committed, because today's rules get them wrong and the fix is
    # Phase C's identity, not a keyword's (decision 96 lists them as open):
    # the CA 100S in a 1040 files F01 on its own K-1 pages; the 1041-A,
    # 1041-QFT and 1120-ND in a 1041 file D01 on a fee line every return
    # prints; the 1041-ES in a 1040 (H01) and the 1041-T in an 1120 (F01)
    # file as another entity's estimated payments.
]


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
