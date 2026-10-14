"""The shipped catalogs against the forms themselves.

Every row's keywords are the document's own title, or a phrase only it
carries - never a word another form prints about it. These are
reconstructions of what the IRS forms, bookkeeping exports and statements
actually say, routed the way an engagement routes them: through
validated() over template_items(), so the Period-derived date check is
live. A misfiling here is the worst thing this system can do.

Two kinds of case, because there are two kinds of document. A page of
text is printed to a PDF and read back (``CASES``); a schedule a client
keeps in Excel is written to a real workbook and read as a sheet
(``XLSX_CASES``), where a row is a line and its cells are set apart by a
tab. Half of every catalog asks for a workbook, and typing one as prose
would prove the wrong reading.

Both tables sit in ``tests/routing_cases.py``, which this file imports and
the vocabulary report reads; the tests that route them are here, under the
same ids as before (``d67-<name>``).

``expected`` is where the document belongs, written the way the firm's own
expectations file writes it (``tests.routing_cases.filed_to``): one
identifier, ``None`` for a document that must park, and the identifiers
joined by ``EXPECTED_SEP`` where one page carries several forms and files a
copy under each (decision 94). One shape for both corpora, so a case and a
row of the firm's expectations say where a document goes in the same words.
"""

from dataclasses import replace

import pytest

from tests.routing_cases import _DECISION_141_XLSX, CASES, XLSX_CASES, filed_to, k1_received_lines
from tests.samples import sheet_xlsx, text_pdf
from tracker.content_check import FIRST_PAGE_PHRASES, Extraction
from tracker.manifest import keyword_alternatives, validated
from tracker.router import route_file
from tracker.templates import FORM_TEMPLATES, SHARED, item_from_spec, template_items

NL = chr(10)


def shipped_rows(tmp_path, form):
    return [replace(i, min_size_kb=0) for i in validated(template_items(form, year=2025))]


@pytest.mark.parametrize("decision, form, name, lines, expected", CASES, ids=[f"d{c[0]}-{c[2]}" for c in CASES])
def test_every_shipped_catalog_files_real_forms_where_they_belong(tmp_path, decision, form, name, lines, expected):
    items = shipped_rows(tmp_path, form)
    routing = route_file(text_pdf(tmp_path / name, NL.join(lines)), items)
    assert filed_to(routing) == expected, (f"decision {decision}", name, routing.reason)


@pytest.mark.parametrize("decision, form, name, rows, expected", XLSX_CASES,
                         ids=[f"d{c[0]}-{c[2]}-{c[1]}" for c in XLSX_CASES])
def test_every_shipped_catalog_files_the_workbooks_clients_send(tmp_path, decision, form, name, rows, expected):
    items = shipped_rows(tmp_path, form)
    routing = route_file(sheet_xlsx(tmp_path / name, rows), items)
    assert filed_to(routing) == expected, (f"decision {decision}", name, routing.reason)


# ------------------------------------------------ decision 141's claims ----


@pytest.mark.parametrize("form, row", [("1065", "H01"), ("1120S", "I01"), ("1120", "J01")])
def test_a_k1_the_business_received_files_its_k1_row_this_year_and_next(tmp_path, form, row):
    """A K-1 the business received files its K-1 row and never contests the
    prior-year return. The package's only year is the K-1's own (2025).

    In its own year's engagement it files the K-1 row, the Period check
    live. In the next year's (2026) the return row's period is the K-1's
    own year, so the period guard that stopped the intake's K-1 is gone:
    what holds is that no return row's required keywords are met by a K-1
    package - the cover names the "Return of Income" it came from, which
    is what the 1065's A01 used to take for a California 568 (on main,
    this page files A01 there). With the Period check live the K-1 row's
    own period then fails too, so the page parks with the K-1 row as its
    only candidate - last year's K-1, for a person; with the Period check
    lifted, as the IRS-forms and real-corpus harnesses route, it files the
    K-1 row in the next year as well."""
    page = text_pdf(tmp_path / "K-1 received.pdf", NL.join(k1_received_lines(2025)))

    def rows(year, *, lifted=False):
        return [replace(i, min_size_kb=0, **({"date_pattern": ""} if lifted else {}))
                for i in validated(template_items(form, year=year))]

    this_year = route_file(page, rows(2025))
    assert filed_to(this_year) == row and this_year.candidates == (row,), this_year.reason
    next_year = route_file(page, rows(2026))
    assert filed_to(next_year) is None and next_year.candidates == (row,), next_year.reason
    assert filed_to(route_file(page, rows(2026, lifted=True))) == row


#: The rows a bookkeeping export or a bank statement files under, by name.
_LEDGERS = {SHARED[key]["document"] for key in ("trial_balance", "general_ledger", "december_bank")}


def test_the_schedule_c_sheet_files_m01_and_no_ledger_or_trial_balance_does(tmp_path):
    """The Schedule C sheet is the client's own workbook, so M01 keys on the
    sheet's vocabulary; a trial balance, a general ledger or a bank
    statement a sole proprietor sends with it must not be taken for it.
    Every such document the suite files anywhere is routed against the
    1040 catalog, where M01 lives."""
    rows_1040 = shipped_rows(tmp_path, "1040")
    sheet = next(case for case in _DECISION_141_XLSX if case[3] == "M01")
    assert filed_to(route_file(sheet_xlsx(tmp_path / sheet[1], sheet[2]), rows_1040)) == "M01"

    def ledger_row(form, expected):
        return any(spec["identifier"] == expected and spec["document"] in _LEDGERS
                   for spec in FORM_TEMPLATES[form])

    ledgers = 0
    for n, (_decision, form, name, lines, expected) in enumerate(CASES):
        if expected and ledger_row(form, expected):
            ledgers += 1
            routing = route_file(text_pdf(tmp_path / f"{n}-{name}", NL.join(lines)), rows_1040)
            assert filed_to(routing) != "M01", (name, routing.reason)
    for n, (_decision, form, name, rows, expected) in enumerate(XLSX_CASES):
        if expected and ledger_row(form, expected):
            ledgers += 1
            routing = route_file(sheet_xlsx(tmp_path / f"x{n}-{name}", rows), rows_1040)
            assert filed_to(routing) != "M01", (name, routing.reason)
    assert ledgers >= 10       # the suite's own ledgers, trial balances and bank statements


# --------------------------------------- decision 141, after the review ----


def _without(rows, identifier):
    return [item for item in rows if item.identifier != identifier]


def return_1065_lines(year: int) -> list[str]:
    """This year's partnership return, signed, with a partner's K-1 behind it."""
    return [
        f"Form 1065 U.S. Return of Partnership Income {year}",
        "Department of the Treasury Internal Revenue Service OMB No. 1545-0123",
        "A Principal business activity B Principal product or service C Business code number",
        "1a Gross receipts or sales 1c Balance",
        "Sign Here Under penalties of perjury, I declare that I have examined this return",
        f"Schedule K-1 {year} Final K-1 Amended K-1 OMB No. 1545-0123",
        f"(Form 1065) For calendar year {year}, or tax year",
        "Partner's Share of Income, Deductions, Credits, etc.",
        "Part I Information About the Partnership",
        "1 Ordinary business income (loss) 8,250.",
    ]


def return_1040_with_w2g_lines(year: int) -> list[str]:
    """This year's individual return, signed, with a W-2G stapled behind it."""
    return [
        "Form 1040",
        "Department of the Treasury Internal Revenue Service OMB No. 1545-0074",
        "U.S. Individual Income Tax Return",
        f"For the year Jan. 1 - Dec. 31, {year}, or other tax year beginning",
        "Filing Status Single Married filing jointly Married filing separately (MFS) Head of household (HOH)",
        "1a Total amount from Form(s) W-2, box 1 (see instructions)",
        "Sign Here Under penalties of perjury, I declare that I have examined this return",
        f"Form W-2G {year} Certain Gambling Winnings Copy B Report this income on your federal tax return.",
        "1 Reportable winnings 2 Date won 3 Type of wager",
    ]


def test_this_years_1065_with_k1s_parks_and_never_files_h01(tmp_path):
    """The designer's ruling on the review, F1. This year's 1065 in this
    year's engagement meets A01's required keywords - its title and the
    jurat - and fails only A01's period, which is last year's. Its partners'
    K-1s make the K-1 row match strongly, and without the rule the return
    filed there. A signed return is never filed under another row: it
    parks, with the return row as its shortlist."""
    rows = shipped_rows(tmp_path, "1065")
    page = text_pdf(tmp_path / "2025 1065 with K-1s.pdf", NL.join(return_1065_lines(2025)))
    assert filed_to(route_file(page, _without(rows, "A01"))) == "H01"        # the K-1 row matches
    routing = route_file(page, rows)
    assert filed_to(routing) is None, routing.reason
    assert routing.candidates == ("A01",), routing.candidates


def test_a_1040_with_a_w2g_attached_parks_and_never_files_a09(tmp_path):
    """The same rule on the 1040: this year's return with a W-2G behind it
    meets B01's required keywords and fails only its period; the W-2G row
    matches the stapled page strongly. It parks, never A09."""
    rows = shipped_rows(tmp_path, "1040")
    page = text_pdf(tmp_path / "2025 1040 with W-2G.pdf", NL.join(return_1040_with_w2g_lines(2025)))
    assert filed_to(route_file(page, _without(rows, "B01"))) == "A09"        # the W-2G row matches
    routing = route_file(page, rows)
    assert filed_to(routing) is None, routing.reason
    assert routing.candidates == ("B01",), routing.candidates


def payer_copy_1099_nec_lines(copy: str, whom: str) -> list[str]:
    """A payer's own copy of a 1099-NEC it issued."""
    return [
        f"Form 1099-NEC 2025 Nonemployee Compensation Copy {copy} For {whom}",
        "PAYER'S name, street address, city or town PAYER'S TIN RECIPIENT'S TIN",
        "1 Nonemployee compensation 12,500.00 4 Federal income tax withheld",
    ]


@pytest.mark.parametrize("form, row", [("1065", "H02"), ("1120S", "I02"), ("1120", "J02")])
def test_a_payers_copy_of_a_1099_nec_parks_on_the_business_return(tmp_path, form, row):
    """The designer's ruling on the review, F2. A business issues 1099-NECs
    as well as receiving them, and the copies it keeps - Copy A, for the
    IRS, and Copy C, for the payer - are not a 1099 it received. The row
    wants the recipient's copy: Copy B, "For Recipient" (a 1099-K's says
    "For Payee"). The recipient's copy files; the payer's park."""
    rows = shipped_rows(tmp_path, form)
    for copy, whom in (("A", "Internal Revenue Service Center"), ("C", "Payer")):
        page = text_pdf(tmp_path / f"Copy {copy}.pdf", NL.join(payer_copy_1099_nec_lines(copy, whom)))
        routing = route_file(page, rows)
        assert filed_to(routing) is None and row not in routing.candidates, (copy, routing.reason)
    copy_b = text_pdf(tmp_path / "Copy B.pdf", NL.join(payer_copy_1099_nec_lines("B", "Recipient")))
    assert filed_to(route_file(copy_b, rows)) == row


def test_a_property_tax_bill_mentioning_a_notice_files_g01_not_z01(tmp_path):
    """The designer's ruling on the review, N2. A county bill heads itself a
    property tax bill and says its tax year on page 1; its back page tells
    the owner about the notice date and the IRS. Read anywhere in ten
    pages, those words met the notices row's required keywords and the
    bill filed Z01; a notice says them at its head, so they count on the
    first page only, and the bill files G01 on its own title."""
    first = NL.join([
        "Sample County Treasurer and Tax Collector",
        "2025-26 Annual Secured Property Tax Bill",
        "Assessor's parcel number 000-000-000  Tax year 2025",
        "First installment due November 1, 2025  Total due 4,812.34",
    ])
    back = NL.join([
        "Important information about your bill",
        "Notice date: October 1, 2025. Keep this bill for your records.",
        "The property tax you pay may be deductible; see IRS Publication 530.",
    ])
    path = text_pdf(tmp_path / "property tax bill.pdf", first)
    reading = Extraction(text=first + chr(12) + back)
    routing = route_file(path, shipped_rows(tmp_path, "1040"), reading=reading)
    assert filed_to(routing) == "G01", routing.reason
    assert "Z01" not in routing.candidates
    # The first-page phrases are the notices row's alone, so the rule reads
    # no other row's words.
    for form, specs in FORM_TEMPLATES.items():
        for spec in specs:
            item = item_from_spec(spec)
            phrases = {phrase.lower() for keyword in (*item.required_keywords, *item.any_keywords)
                       for alternative in keyword_alternatives(keyword) for phrase in alternative}
            assert not (phrases & FIRST_PAGE_PHRASES) or spec["identifier"] == "Z01", (form, spec["identifier"])
