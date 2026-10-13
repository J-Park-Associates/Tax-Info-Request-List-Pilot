"""What the suites that route documents share: the blank forms' placements, two printed forms, the workbook cases, and the words a filing is checked in.

``test_catalog`` (cases typed from what the documents say), ``test_irs_forms``
(the IRS's own blank forms) and ``test_real_corpus`` (the firm's own documents)
are the three decision-70 suites, and four other test files imported pieces of
them (``EXPECT`` from ``test_irs_forms``, ``cp_notice_lines`` and ``XLSX_CASES``
from ``test_catalog``, ``filed_to`` from ``test_real_corpus``). The borrowed
pieces live here so the borrowing names a module that is not a test file (SPEC-architecture E-4, R2.1). They are moved with their
words, and each of the three suites imports back what it uses, so
``tools/vocab_report.py`` and ``tools/backtest.py``, which import ``CASES``,
``XLSX_CASES``, ``EXPECT`` and the corpus readers from the suites by name, are
untouched.

This file feeds the vocabulary coverage report - ``EXPECT`` is where each blank
form belongs, the workbook cases are half of every catalog's cases, and the two
line makers are inside typed cases - so it is one of the report's inputs
(``vocab_report.INPUT_PATHS``) and a change to it makes the committed report
stale until it is rebuilt.
"""

from pathlib import Path

from tracker.settings import EXPECTED_SEP

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


# Decision 141, the owner's rows for what clients actually send (SPEC-141).
# Each document is typed from the form's own printed lines, never from a
# client's: the SSA-1099 with the revision code the SSA prints at the top of
# the page, which is where E02's `1099-r` was being said; the K-1 a business
# receives, with a preparer's cover that names the "Return of Income"; an IRS
# notice by the header every current CP notice prints; and the corrections
# that must keep parking (the owner's item 17).
def ssa_1099_lines(year: int) -> list[str]:
    """The SSA-1099's printed lines, as the SSA prints them each January."""
    return [
        f"Form SSA-1099-R-OP1 (01-{year})",
        "Discontinue Prior Editions",
        "FORM SSA-1099 -- SOCIAL SECURITY BENEFIT STATEMENT",
        f"{year} PART OF YOUR SOCIAL SECURITY BENEFITS SHOWN IN BOX 5 MAY BE TAXABLE INCOME.",
        "Box 1. Name Box 2. Beneficiary's Social Security Number",
        "JANE Q SAMPLE 000-00-0000",
        f"Box 3. Benefits paid in {year} Box 4. Benefits Repaid to SSA in {year} "
        f"Box 5. Net Benefits for {year} (Box 3 minus Box 4)",
        "Box 6. Voluntary Federal Income Tax Withheld",
        "DO NOT RETURN THIS FORM TO SSA OR IRS",
    ]


def cp_notice_lines(year: int) -> list[str]:
    """The header block the IRS's current notices print on every page."""
    return [
        "Department of the Treasury",
        "Internal Revenue Service",
        "Notice CP14",
        f"Tax year {year - 1}",
        f"Notice date March 3, {year}",
        "Social Security number XXX-XX-0000",
        "To contact us Phone 800-829-0922",
        "Page 1 of 4",
        "Amount due: 1,234.56",
        f"We believe you owe tax for {year - 1}. Pay the amount due now to avoid additional interest.",
        f"Notice CP14 Tax year {year - 1} Notice date March 3, {year} Page 2 of 4",
    ]


#: The same round's workbook cases. A schedule a client keeps in Excel is
#: read as a sheet, not as prose (``samples.sheet_xlsx``), so these are
#: routed through a real .xlsx rather than typed as lines.
_BANK_RECONCILIATION = [
    ["Willow Lane Inc."], ["Bank Reconciliation - December 31, 2025"],
    ["Balance per bank statement", 157190.45], ["Outstanding checks", -8120.00],
    ["Balance per books", 149070.45],
]


_LOAN_AMORTIZATION = [
    ["Willow Lane LLC  Note payable"],
    ["Loan Amortization Schedule as of December 31, 2025"],
    ["Payment", "Date", "Principal", "Interest", "Balance"],
    [12, "12/15/2025", 1940.11, 520.21, 216400.00],
]


_FIXED_ASSETS = [
    ["Willow Lane Inc."], ["Fixed Asset Schedule - 2025"],
    ["Asset", "Date placed in service", "Cost", "Prior depreciation", "Current depreciation"],
    ["Ford Transit van", "03/14/2025", 48200, 0, 9640],
]


_APPORTIONMENT = [
    ["Willow Lane Inc."], ["State Apportionment Schedule - 2025"],
    ["State", "Sales", "Payroll", "Property"], ["California", 1810000, 402000, 240000],
]


_SHAREHOLDER_LIST = [
    ["Willow Lane Inc."], ["Shareholder List and Ownership Changes - 2025"],
    ["Shareholder", "Shares", "Percent", "Date acquired"], ["John Reyes", 600, "60%", "01/02/2018"],
]


_DECISION_73_XLSX = [
    # 1120 E02 / 990 C02: the schedule's own title. "Compensation of
    # officers" alone is a line on every 990's Part VII and every
    # nonprofit's Statement of Functional Expenses.
    ("1120", "officer compensation detail.xlsx", [
        ["Acme Manufacturing Inc."], ["Officer Compensation Detail - 2025"],
        ["Officer", "Title", "% time devoted", "Compensation"],
        ["John Reyes", "President", "100%", 240000],
    ], "E02"),
    ("1120", "officer comp schedule per 1125-E.xlsx", [
        ["Acme Manufacturing Inc.  2025"],
        ["Officer Compensation Schedule (support for Form 1125-E)"],
        ["Officer", "SSN", "Percent of stock owned", "Amount of compensation"],
        ["John Reyes", "xxx-xx-1234", "60%", 240000],
    ], "E02"),
    ("1120", "trial balance with a 1125-E memo.xlsx", [
        ["Acme Manufacturing Inc."], ["Trial Balance - December 31, 2025"],
        ["Account", "Debit", "Credit"], ["1000 Cash", 84000, 0],
        ["6100 Officer salaries (tie to Form 1125-E)", 425000, 0],
    ], "A02"),
    ("990", "officer and key employee compensation detail.xlsx", [
        ["Riverside Community Center"], ["Officer Compensation Detail - Calendar Year 2025"],
        ["Name", "Title", "Hours/week", "Base pay", "Benefits", "Total"],
        ["Ana Diaz", "Executive Director", 40, 128000, 19000, 147000],
    ], "C02"),
    ("990", "compensation of officers schedule.xlsx", [
        ["Riverside Community Center  2025"], ["Compensation of Officers, Directors and Trustees"],
        ["Name", "Title", "Reportable compensation", "Other compensation"],
        ["Ana Diaz", "Executive Director", 128000, 19000],
    ], "C02"),
    # 990 B01: a nonprofit's package, and the statement within it whose
    # first expense line names the officers.
    ("990", "statement of functional expenses.xlsx", [
        ["Riverside Community Center"], ["Statement of Functional Expenses"],
        ["For the year ended December 31, 2025"],
        ["", "Program services", "Management and general", "Fundraising", "Total"],
        ["Compensation of officers, directors and key employees", 90000, 45000, 12000, 147000],
        ["Other salaries and wages", 310000, 60000, 24000, 394000],
    ], "B01"),
    ("990", "audited financial statements package.xlsx", [
        ["Riverside Community Center"], ["Financial Statements and Independent Auditor's Report"],
        ["December 31, 2025"], ["Statement of Financial Position"], ["Total assets", 1840000],
        ["Statement of Activities"], ["Change in net assets", 92000],
        ["Statement of Functional Expenses"],
        ["Compensation of officers, directors and key employees", 147000],
        ["Statement of Cash Flows"], ["Net cash provided by operating activities", 61000],
    ], "B01"),
    ("990", "donor detail.xlsx", [
        ["Riverside Community Center"], ["Donor Detail - Contributions Received in 2025"],
        ["Donor name", "Address", "Amount", "Type"], ["Helen Ward", "44 Oak St", 25000, "Cash"],
    ], "D01"),
    ("990", "schedule b support workbook.xlsx", [
        ["Riverside Community Center  EIN 84-1234567"],
        ["Schedule B Support - Contributors of $5,000 or more, 2025"],
        ["No.", "Name of contributor", "Aggregate contributions", "Type of contribution"],
        [1, "Helen Ward", 25000, "Person"],
    ], "D01"),
    ("990", "board of directors list.xlsx", [
        ["Riverside Community Center"], ["Board of Directors List - 2025"],
        ["Name", "Office", "Term ends"], ["L. Howard", "Chair", 2026],
    ], "C01"),
    ("990", "board roster.xlsx", [
        ["Riverside Community Center"], ["Board Roster - Directors and Officers 2025"],
        ["Name", "Office", "Term ends"], ["L. Howard", "Chair", 2026],
    ], "C01"),
    ("990", "grants paid schedule.xlsx", [
        ["Riverside Community Center"], ["Grants Paid Schedule - 2025"],
        ["Grantee", "EIN", "Purpose", "Amount"],
        ["Eastside Youth Center", "84-9911223", "After-school", 25000],
    ], "D02"),
    ("990", "grants made detail.xlsx", [
        ["Riverside Community Center"], ["Grants Made - Recipients and Amounts 2025"],
        ["Grantee", "EIN", "Purpose", "Amount"],
        ["Eastside Youth Center", "84-9911223", "After-school", 25000],
    ], "D02"),
    ("990", "fundraising event detail.xlsx", [
        ["Riverside Community Center"], ["Fundraising Event Detail - Spring Gala 2025"],
        ["Gross receipts", 184000], ["Contributions portion", 120000], ["Direct expenses", 61000],
    ], "F01"),
    ("990", "UBTI schedule.xlsx", [
        ["Riverside Community Center"], ["Unrelated Business Income Detail - 2025"],
        ["Activity", "Gross income", "Direct expenses", "Net"],
        ["Parking lot rental (debt-financed)", 42000, 18000, 24000],
    ], "H01"),
    # The shared schedules, in every catalog that carries them.
    ("1120", "fixed asset schedule.xlsx", _FIXED_ASSETS, "C01"),
    ("1120S", "fixed asset schedule.xlsx", _FIXED_ASSETS, "F01"),
    ("1065", "fixed asset schedule.xlsx", _FIXED_ASSETS, "D01"),
    ("1120", "apportionment schedule.xlsx", _APPORTIONMENT, "H01"),
    ("1120S", "apportionment schedule.xlsx", _APPORTIONMENT, "H01"),
    ("1065", "apportionment schedule.xlsx", _APPORTIONMENT, "G01"),
    ("1120", "bank reconciliation.xlsx", _BANK_RECONCILIATION, "B02"),
    ("1120S", "bank reconciliation.xlsx", _BANK_RECONCILIATION, "B02"),
    ("1065", "bank reconciliation.xlsx", _BANK_RECONCILIATION, "B02"),
    ("990", "bank reconciliation.xlsx", _BANK_RECONCILIATION, "B02"),
    ("1120", "loan amortization schedule.xlsx", _LOAN_AMORTIZATION, "D01"),
    ("1065", "loan amortization schedule.xlsx", _LOAN_AMORTIZATION, "E01"),
    ("1120", "depreciation schedule.xlsx", [
        ["Willow Lane Inc."], ["Depreciation Schedule - Year ended December 31, 2025"],
        ["Asset", "Cost", "Prior", "Current", "Accumulated"],
        ["Ford Transit van", 48200, 0, 9640, 9640],
    ], "C02"),
    ("1120", "shareholder list.xlsx", _SHAREHOLDER_LIST, "G01"),
    ("1120S", "shareholder list.xlsx", _SHAREHOLDER_LIST, "C01"),
    ("1120", "stock ledger.xlsx", [
        ["Willow Lane Inc.  Stock Ledger"],
        ["Certificate", "Holder", "Shares", "Date issued", "Date transferred"],
        [1, "John Reyes", 600, "01/02/2018", ""], [3, "Marie Chen", 400, "06/30/2025", ""],
    ], "G01"),
    ("1120", "M-1 support schedule.xlsx", [
        ["Willow Lane Inc."], ["Schedule M-1 support - book-tax differences 2025"],
        ["Description", "Book", "Tax", "Difference"],
        ["Meals and entertainment", 18400, 9200, 9200],
    ], "I01"),
    ("1120", "corporate estimated payments made.xlsx", [
        ["Willow Lane Inc."], ["Estimated payments made - 2025"],
        ["Date", "Federal", "California"], ["04/15/2025", 12000, 3000],
    ], "F01"),
    ("1120", "corporate estimated tax payments made.xlsx", [
        ["Willow Lane Inc."], ["Estimated tax payments made - 2025"],
        ["Date", "Federal", "California"], ["04/15/2025", 12000, 3000],
    ], "F01"),
    ("1120S", "distributions by shareholder.xlsx", [
        ["Willow Lane Inc."], ["Distributions by Shareholder - 2025"],
        ["Shareholder", "Date", "Amount"], ["John Reyes", "06/30/2025", 60000],
    ], "C02"),
    ("1120S", "shareholder basis schedule.xlsx", [
        ["Willow Lane Inc."], ["Shareholder Basis Schedule - 2025"],
        ["Shareholder", "Beginning stock basis", "Income", "Distributions", "Ending stock basis"],
        ["John Reyes", 120000, 92000, -60000, 152000],
    ], "C03"),
    ("1120S", "basis and distribution worksheet.xlsx", [
        ["Willow Lane Inc.  2025"],
        ["Stock and Debt Basis Worksheet with Distribution Detail by Shareholder"],
        ["Shareholder", "Stock basis", "Distributions"], ["John Reyes", 152000, 60000],
    ], None),
    ("1120S", "officer W-2 compensation detail.xlsx", [
        ["Willow Lane Inc."], ["Officer Compensation Detail - 2025"],
        ["Officer", "W-2 Box 1", "Health insurance in box 1"], ["John Reyes", 180000, 14400],
    ], "D01"),
    ("1120S", "shareholder health insurance premiums.xlsx", [
        ["Willow Lane Inc."], ["Shareholder Health Insurance Premiums - 2025"],
        ["Shareholder", "Premiums paid", "Included in W-2 box 1"], ["John Reyes", 14400, "Yes"],
    ], "D02"),
    ("1065", "partner list.xlsx", [
        ["Willow Lane Partners, L.P."], ["Partner List with Ownership Percentages - 2025"],
        ["Partner", "Type", "Profit %", "Capital %"], ["A. Okafor", "General", "40%", "40%"],
    ], "C01"),
    ("1065", "capital account detail.xlsx", [
        ["Willow Lane Partners, L.P."], ["Partner Capital Account Detail - 2025"],
        ["Partner", "Beginning", "Contributions", "Income", "Distributions", "Ending"],
        ["A. Okafor", 210000, 0, 74000, -40000, 244000],
    ], "C02"),
    ("1065", "contributions and distributions by partner.xlsx", [
        ["Willow Lane Partners, L.P."], ["Contributions and Distributions by Partner - 2025"],
        ["Partner", "Contributions", "Distributions"], ["A. Okafor", 0, 40000],
    ], "C03"),
    ("1065", "guaranteed payment detail.xlsx", [
        ["Willow Lane Partners, L.P."], ["Guaranteed Payment Detail - 2025"],
        ["Partner", "Services", "Capital", "Total"], ["A. Okafor", 90000, 0, 90000],
    ], "C04"),
    ("1065", "special allocation 704(b) support.xlsx", [
        ["Willow Lane Partners, L.P.  2025"], ["Special Allocation Support - Section 704(b)"],
        ["Partner", "704(b) book capital", "Tax capital"], ["A. Okafor", 244000, 198000],
    ], "F01"),
    ("1041", "distributions to beneficiaries.xlsx", [
        ["Doyle Family Trust  EIN 84-1234567"], ["Distributions to Beneficiaries - 2025"],
        ["Beneficiary", "Date", "Amount", "Character"], ["Thomas Doyle", "03/15/2025", 25000, "Income"],
    ], "C01"),
    ("1041", "beneficiary information schedule.xlsx", [
        ["Doyle Family Trust"], ["Beneficiary Information"],
        ["Name", "Address", "Taxpayer ID", "Relationship"],
        ["Thomas Doyle", "18 Alder Ln, Pasadena CA", "xxx-xx-4412", "Son"],
    ], "C02"),
    ("1041", "fees paid schedule.xlsx", [
        ["Doyle Family Trust  2025"], ["Fiduciary, attorney and accounting fees paid"],
        ["Payee", "Type", "Amount"], ["Northern Trust", "Trustee fees", 12400],
        ["Baker & Lyle LLP", "Legal fees paid", 8200],
    ], "D01"),
    ("1041", "cost basis schedule.xlsx", [
        ["Estate of Margaret A. Doyle"], ["Cost Basis Schedule - Assets Sold in 2025"],
        ["Asset", "Date acquired", "Date sold", "Proceeds", "Basis", "Gain"],
        ["18 Alder Lane", "06/03/2011", "08/14/2025", 940000, 812000, 128000],
    ], "E01"),
    ("1041", "rental income and expenses.xlsx", [
        ["Doyle Family Trust"], ["Rental Income and Expenses - 2025"],
        ["Property", "Rents received", "Repairs", "Insurance", "Depreciation"],
        ["902 Main St", 42000, 3100, 1800, 7400],
    ], "F01"),
    ("1041", "rent roll.xlsx", [
        ["902 Main Street  Rent Roll  December 2025"],
        ["Unit", "Tenant", "Monthly rent", "Lease end"], ["1A", "R. Alvarez", 1750, "06/30/2026"],
    ], "F01"),
    ("1040", "estimated payments made schedule.xlsx", [
        ["John and Jane Smith"], ["2025 Estimated payments made"],
        ["Quarter", "Date paid", "Federal", "State"], ["Q1", "04/15/2025", 4500, 1200],
    ], "H01"),
    ("1040", "childcare provider statement workbook.xlsx", [
        ["Childcare Provider Statement - 2025"], ["Provider", "EIN", "Child", "Amount"],
        ["Bright Horizons", "12-3456789", "Emma Smith", 14400],
    ], "J01"),
]


_DECISION_85_XLSX = [
    # 1040 E01 takes the workbook a broker exports, and the sheet's own
    # name runs the words together the way an export does.
    ("1040", "realized gain loss.xlsx", [
        ["Realized GainLoss"], ["Realized Gain/Loss"],
        ["Account: Individual - TOD ****2566   Period: 01/01/2025 to 12/31/2025"],
        ["Symbol", "Description", "Quantity", "Date sold", "Proceeds", "Cost basis", "Gain/Loss", "Term"],
        ["IRNW", "IRONWOOD PROPERTIES INC COM", 339, "07/23/2025", 19878.84, 22110.05, -2231.21, "Short"],
    ], "E01"),
    ("1040", "unrealized gain loss.xlsx", [
        ["Unrealized GainLoss"], ["Unrealized Gain/Loss by Position"],
        ["Account: Individual - TOD ****2566   As of 12/31/2025"],
        ["Symbol", "Description", "Quantity", "Cost basis", "Market value", "Gain/Loss"],
        ["IRNW", "IRONWOOD PROPERTIES INC COM", 1400, 240030.00, 369978.00, 129948.00],
    ], None),
]


_DECISION_90_XLSX = [
    ("1120S", "depreciation schedule.xlsx", [
        ["Willow Lane Inc."], ["Depreciation Schedule - Year ended December 31, 2025"],
        ["Asset", "Cost", "Prior", "Current", "Accumulated"],
        ["Ford Transit van", 48200, 0, 9640, 9640],
    ], "F02"),
    ("1065", "depreciation schedule.xlsx", [
        ["Willow Lane LLC"], ["Depreciation Schedule - Year ended December 31, 2025"],
        ["Asset", "Cost", "Prior", "Current", "Accumulated"],
        ["Ford Transit van", 48200, 0, 9640, 9640],
    ], "D02"),
    # The confusable the depreciation row must not take: a register of
    # what the entity bought and sold, which never says depreciation. It
    # is the fixed-asset row's document and stays there - the two rows
    # ask for different schedules, and the register is not the 4562's.
    ("1120", "asset additions and disposals.xlsx", [
        ["Willow Lane Inc."], ["Asset Additions and Disposals - 2025"],
        ["Asset", "Date", "Cost", "Disposed", "Proceeds"],
        ["Ford Transit van", "03/14/2025", 48200, "", ""],
    ], "C01"),
    ("1120S", "asset additions and disposals.xlsx", [
        ["Willow Lane Inc."], ["Asset Additions and Disposals - 2025"],
        ["Asset", "Date", "Cost", "Disposed", "Proceeds"],
        ["Ford Transit van", "03/14/2025", 48200, "", ""],
    ], "F01"),
    ("1065", "asset additions and disposals.xlsx", [
        ["Willow Lane LLC"], ["Asset Additions and Disposals - 2025"],
        ["Asset", "Date", "Cost", "Disposed", "Proceeds"],
        ["Ford Transit van", "03/14/2025", 48200, "", ""],
    ], "D01"),
]


# The Schedule C sheet: the client's own workbook, in the shape the firm's
# organizer worksheet has - a 1099-NEC named in a cell, which the 1099-NEC
# row cannot take (it asks for a PDF or a CSV), beside the expense lines.
_DECISION_141_XLSX = [
    ("1040", "2025 business income and expense.xlsx", [
        ["Business name (DBA)", "Sample Studio"], ["Year 2025"],
        ["GROSS SALES", 30000, "1099-NEC: Sample Payer Inc"],
        ["ENDING INVENTORY", 0], ["COST OF GOODS SOLD", 0], ["AUTOMOBILE EXPENSE", 1200], ["SUPPLIES", 850],
        ["BUSINESS MILEAGE", 2100], ["COMMUTE MILEAGE", 0],
        ["TOTAL EXPENSE", 9000], ["NET INCOME", 21000],
    ], "M01"),
    ("1040", "Schedule C summary 2025.xlsx", [
        ["Schedule C Summary - 2025"], ["Gross receipts", 48000], ["Total expenses", 17250],
    ], "M01"),
    ("1040", "Schedule C worksheet.xlsx", [
        ["Schedule C Worksheet"], ["Tax year 2025"], ["Gross receipts", 48000], ["Total expenses", 17250],
    ], "M01"),
    ("1040", "business income and expense summary.xlsx", [
        ["Sample Studio - Business Income and Expense Summary - 2025"],
        ["Gross receipts", 48000], ["Total expenses", 17250],
    ], "M01"),
    ("1040", "business income & expense summary.xlsx", [
        ["Business Income & Expense Summary"], ["Year", 2025], ["Gross receipts", 48000],
    ], "M01"),
    # A mileage log is Schedule C support, not the summary M01 asks for,
    # and says none of the summary's lines (the designer's ruling on G5).
    ("1040", "2025 mileage log.xlsx", [
        ["Vehicle mileage log 2025"], ["Date", "Destination", "Purpose", "Business mileage"],
        ["01/06/2025", "Client site", "Consultation", 42], ["Total business mileage", 2100],
    ], None),
]


#: (decision, form, file name, rows, expected) - the workbook cases, in the
#: same shape with a sheet's rows in place of a page's lines. The report
#: reads this list too, rendering the rows the way a sheet is read.
XLSX_CASES = ([(73, *case) for case in _DECISION_73_XLSX]
              + [(85, *case) for case in _DECISION_85_XLSX]
              + [(90, *case) for case in _DECISION_90_XLSX]
              + [(141, *case) for case in _DECISION_141_XLSX])


def filed_to(routing) -> str | None:
    """Where one routing filed the document, as the ``expected`` column
    writes it: None for a park, one identifier for the ordinary filing,
    and the identifiers ``EXPECTED_SEP``-joined where decision 94 filed a
    copy under each. One reader for both sides of the comparison, and the
    one ``tools/backtest.py`` scores the firm's real mail with."""
    filed = routing.filed_to
    return EXPECTED_SEP.join(filed) if filed else None
