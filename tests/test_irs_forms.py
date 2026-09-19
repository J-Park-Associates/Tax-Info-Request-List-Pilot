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
    ("f1065sk1.pdf", "1065", 2025, None), ("f1065sk1.pdf", "1041", 2025, None), ("f1065sk1.pdf", "1120", 2025, None),
    ("f1041.pdf", "1041", 2026, "A03"), ("f1041sk1.pdf", "1040", 2025, "F01"), ("f1041sk1.pdf", "1041", 2025, None),
    ("f1041sk1.pdf", "1120S", 2025, None),
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
    ("fw2g.pdf", "1040", 2025, None), ("fw2g.pdf", "1041", 2025, None),
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
    ("f1041es.pdf", "1041", 2025, None),      # no 1041 row asks for estimated payments: the owner's call
    ("f1041a.pdf", "1040", 2026, None), ("f1041qft.pdf", "1040", 2026, None),
    ("f1098c.pdf", "1040", 2025, None), ("f1098e.pdf", "1040", 2025, None), ("f1098f.pdf", "1040", 2025, None),
    ("f1098q.pdf", "1040", 2025, None), ("f1099a.pdf", "1040", 2025, None), ("f1099c.pdf", "1040", 2025, None),
    ("f1099cap.pdf", "1040", 2025, None), ("f1099h.pdf", "1040", 2025, None), ("f1099ls.pdf", "1040", 2025, None),
    ("f1099ltc.pdf", "1040", 2025, None), ("f1099q.pdf", "1040", 2025, None), ("f1099qa.pdf", "1040", 2025, None),
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
    ("ca568k1.pdf", "1040", 2025, "F01"), ("nyit204ip.pdf", "1040", 2025, "F01"), ("nyit204ip.pdf", "1065", 2025, None),
    # Not committed, because today's rules get them wrong and the fix is
    # Phase C's identity, not a keyword's (decision 96 lists them as open):
    # the CA 100S in a 1040 files F01 on its own K-1 pages; the CA 568 K-1
    # in a 1065 files F01 (decision 85's F1); the 1041-A, 1041-QFT and
    # 1120-ND in a 1041 file D01 on a fee line every return prints; the
    # 1041-ES in a 1040 (H01) and the 1041-T in an 1120 (F01) file as another
    # entity's estimated payments. Not committed either, as calls for the
    # owner: the W-2c (parks; a corrected wage statement), the 1065-X (parks;
    # its title is not the 1065's) and the 1099-DA (parks; broker proceeds
    # without the 1099-B's words).
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
def test_the_irs_forms_file_where_they_belong_or_park(catalogs, pdf, form, year, expected):
    routing = route_file(IRS / pdf, catalogs(form, year))
    assert routing.identifier == expected, (pdf, form, routing.reason)
