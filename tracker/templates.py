"""The per-form request catalog: one checklist per return type (component 11).

Every request list starts from here. Pick the return (1040, 1120, 1120-S,
1065, 1041, 990) and this module says which documents to ask for, what
they are called, how many to expect and — the part that makes the pipeline
run unattended — the keyword and date rules the router and scanner use to
recognise each one.

This is the **only** place the checklists live. There is no second copy to
keep in step: an engagement's list is cut from it into the record, and the
wizard reads this module directly.

One thing the catalog deliberately does not hold is a row per issuing
entity. A person can hold Schedule K-1s from several partnerships, and the
owner's rule (2026-09-18) is that those are separate requests - but which
entities they are is a fact about one client, not about the 1040. So the
catalog carries one K-1 row and :func:`issuer_row` cuts a row per issuer
from it, into that engagement's own list.

Every row carries a keyword rule. A request with no keyword has no way to
recognise its document, so it never auto-files (see :mod:`tracker.router`);
a template row like that would be a request the system can only ever park
for a person, which defeats the point of a template. The year check is not
written here: a Period like ``TY2025`` implies it (:func:`tracker.manifest.derived_date_pattern`).

Every row also carries a **name mark** (decision 128): whether the document
this request asks for is addressed to somebody. A W-2, a 1099, a K-1, a
mortgage statement, a bank statement and a return are named - the payer,
the lender, the agency or the return itself writes a name on the page - and
a receipt, a log, a trial balance, a schedule or a spreadsheet export is
not. Sixty-one of the hundred and seven rows here are named. Financial
statements and bank statements are named because a statement without the
entity's name on it is not one, which is why the client README asks for
reports with their headers on. The mark decides what the household pass
does when a document names nobody on the return: a named request parks it
for a person, an unnamed one files it on its keywords alone.

And every row carries a **short name** (decision 144, the owner's list of
2026-09-24): what the firm's working folder and working copies are called,
``A01 - W-2/A01 - W-2 - TY2025.pdf``, twenty characters at most. The full
title was in every working path twice and, under the firm's real clients
root, refused a business with a household name of 26 characters. A row the
several catalogs share has the same short name on each. The client never
sees one: the README, the letter and the received list keep the title.
"""

from __future__ import annotations

import datetime as dt
from dataclasses import replace

from tracker.manifest import (
    DEFAULT_EXTENSIONS,
    JURAT,
    KEYWORD_ALL_OF,
    KEYWORD_ANY_OF,
    ManifestError,
    RequestItem,
    detect_year,
    entity_keyword,
    identifier_problem,
    item_from_fields,
    shift_item,
)

# Tax form catalog — the wizard's first page. Selecting a form type tailors
# the request template below to that return.
#: How a form is labelled to people; the fallback for an unknown form uses it too.
FORM_LABEL_PATTERN = "Form {form}"
FORM_TYPES = [
    {
        "id": "1040", "label": FORM_LABEL_PATTERN.format(form="1040"),
        "who": "Individual / joint return",
        "blurb": "Wages, investments, deductions, credits",
    },
    {
        "id": "1120", "label": FORM_LABEL_PATTERN.format(form="1120"),
        "who": "C corporation",
        "blurb": "Corporate income tax return",
    },
    {
        "id": "1120S", "label": FORM_LABEL_PATTERN.format(form="1120-S"),
        "who": "S corporation",
        "blurb": "Pass-through corporate return with K-1s",
    },
    {
        "id": "1065", "label": FORM_LABEL_PATTERN.format(form="1065"),
        "who": "Partnership / multi-member LLC",
        "blurb": "Partnership return with K-1s",
    },
    {
        "id": "1041", "label": FORM_LABEL_PATTERN.format(form="1041"),
        "who": "Estate or trust",
        "blurb": "Fiduciary income tax return",
    },
    {
        "id": "990", "label": FORM_LABEL_PATTERN.format(form="990"),
        "who": "Tax-exempt organization",
        "blurb": "Annual information return",
    },
]

#: The tax year the catalog is written for. Every dated row derives from it;
#: template_items(form, year=...) shifts the whole catalog to another year.
BASE_YEAR = 2025
#: How a tax year is written in a Period and in an engagement's name.
PERIOD_PATTERN = "TY{year}"
TY = PERIOD_PATTERN.format(year=BASE_YEAR)
TY_PRIOR = PERIOD_PATTERN.format(year=BASE_YEAR - 1)
DEC = f"Dec {BASE_YEAR}"
AS_OF_YEAR_END = f"As of 12/31/{BASE_YEAR}"


def _row(identifier: str, document: str, *, core: bool, named: bool, short: str = "",
         period: str = TY, extensions: str = "pdf", required_keywords: str = "",
         any_keywords: str = "", expected_count: int = 1) -> dict:
    row = {"identifier": identifier, "document": document, "period": period,
           "extensions": extensions, "core": core, "named": named}
    # The short name the firm's working folder and copies are named by
    # (decision 144); blank derives one from the document title.
    if short:
        row["short_title"] = short
    if expected_count > 1:
        row["expected_count"] = expected_count
    if required_keywords:
        row["required_keywords"] = required_keywords
    if any_keywords:
        row["any_keywords"] = any_keywords
    return row


# JURAT, the line every federal return carries over its signature (decision
# 65), is read from tracker.manifest since decision 141: six rows here ask
# for it, and the router knows a return row by it.


def _prior_return(*federal: str, state: tuple[str, ...] = ()) -> str:
    """The required keyword of a "Prior-Year Federal & State ..." row.

    The federal return is known by the lines only it prints - its own
    title and, since decision 65, the jurat - and a state return that
    arrives on its own shares none of them: California heads Form 540
    "California Resident Income Tax Return", New York heads IT-204
    "Partnership Return", and the signature side, where the jurat is, is
    not always the side a client sends. Required Keywords is an AND over
    its cells and Any Keywords an OR over theirs, so neither column can
    say "the federal words, or a state form's"; the alternatives inside
    one keyword can (``tracker.manifest.keyword_alternatives``), and they
    leave the row's required set *required* - a prior-year return still
    outranks a row that matched on any keyword, and one that fails
    another rule is still contested rather than filed elsewhere.

    Another state is one more phrase in ``state``: one keyword, no rule.
    """
    return f" {KEYWORD_ANY_OF} ".join([f" {KEYWORD_ALL_OF} ".join(federal), *state])


# Requests several return types share. Defined once, so a keyword fix here
# reaches every form that asks for the document; each form only says which
# identifier it uses and whether the row is pre-ticked.
SHARED = {
    "trial_balance": dict(short="Trial Balance", document="Trial Balance - Year-End", any_keywords="trial balance",
                          extensions="xlsx, csv, pdf"),
    "general_ledger": dict(short="General Ledger", document="General Ledger Detail", any_keywords="general ledger",
                           extensions="xlsx, csv, pdf"),
    # A nonprofit's statements carry titles a company's do not; the
    # Statement of Functional Expenses is one of the package's own, and
    # keying the officer-compensation row on its "compensation of officers"
    # line filed the whole package there (the thirteenth reading).
    "financial_statements": dict(short="Financial Statements",
        document="Year-End Financial Statements",
        any_keywords="balance sheet as of, statement of financial position, income statement, statement of income, "
                     "profit and loss, statement of operations, statement of activities, statement of cash flows, "
                     "statement of functional expenses",
        extensions="pdf, xlsx"),
    # `statement of account` is what a credit-card issuer and a broker head
    # their December statements with, and neither is the bank statement this
    # row asks for; a bank's own statement says what its columns are. The row
    # asks for the year-end reconciliation too, which arrives as a workbook.
    "december_bank": dict(short="December Bank Recs", document="December Bank Statements & Year-End Reconciliations",
                          any_keywords="bank statement, checking summary, deposits and additions, "
                                       "deposits and other credits, checks paid, withdrawals and other debits, "
                                       "bank reconciliation",
                          period=DEC, extensions="pdf, xlsx"),
    "payroll_returns": dict(short="Payroll 941 W-3", document="Payroll Tax Returns - Forms 941 & W-3",
                            any_keywords="form 941, employer's quarterly federal tax return, form 940, "
                                         "employer's annual federal unemployment, form w-3, w-3 transmittal"),
    # An individual's voucher, by its own lines: its numbered heading and
    # the amount line. The 1040-ES booklet's instructions say "estimated
    # tax payment voucher" in prose, and its blank vouchers are pages the
    # reader never reaches. These lines are the *person's*, which is why a
    # corporation's row no longer shares them: the individual's 1040-ES
    # voucher was filing as the corporation's estimated tax record.
    "estimated_tax": dict(short="Estimated Payments", document="Estimated Tax Payment Records",
                          any_keywords="estimated tax payment voucher 1, estimated tax payment voucher 2, "
                                       "estimated tax payment voucher 3, estimated tax payment voucher 4, "
                                       "estimated tax payment voucher for individuals, "
                                       "amount of estimated tax you are paying, estimated tax voucher, "
                                       "estimated payments made",
                          extensions="pdf, xlsx"),
    # A corporation's record of the same thing, by the words a corporate
    # voucher and a bookkeeper's schedule print. A voucher headed
    # "Estimated Tax Payment Voucher 2" is a person's and must not land
    # here; the row is named apart from the individual's so that one
    # document name never means two sets of rules.
    "business_estimated_tax": dict(short="Estimated Payments", document="Corporate Estimated Tax Payment Records",
                                   any_keywords="corporation estimated tax, estimated tax voucher, "
                                                "estimated payments made, estimated tax payments made",
                                   extensions="pdf, xlsx"),
    # The schedules below are bookkeeping exports, so a workbook is what
    # arrives most - but a client who prints one to PDF is answering the
    # request, and an xlsx-only row parked every one of those.
    "fixed_assets": dict(short="Fixed Assets", document="Fixed Asset Additions & Disposals Detail",
                         any_keywords="fixed asset schedule, fixed asset listing, fixed asset additions, "
                                      "asset additions and disposals",
                         extensions="xlsx, pdf"),
    # The schedule behind Form 4562, asked for by every entity that owns
    # anything (decision 90: the owner wanted the 1120's row in the
    # 1120-S's and the partnership's too). Its own titles, and the form
    # number the software prints across the top of the detail page - the
    # row asking for a *fixed asset* register is `fixed_assets`, and a
    # register that never says depreciation stays there.
    "depreciation": dict(short="Depreciation", document="Depreciation Schedules",
                         any_keywords="depreciation schedule, depreciation detail, depreciation report, "
                                      "form 4562",
                         extensions="xlsx, pdf"),
    "loans": dict(short="Loans", document="Loan Agreements & Year-End Balances",
                  any_keywords="loan agreement, promissory note, amortization schedule, loan statement, "
                               "principal balance",
                  period=AS_OF_YEAR_END, extensions="pdf, xlsx"),
    "apportionment": dict(short="State Apportionment", document="State Apportionment Data - Sales, Payroll, Property by State",
                          any_keywords="apportionment schedule, apportionment data, sales by state, payroll by state",
                          extensions="xlsx, pdf"),
    # `form 1125-e` went with the PDF: the blank Form 1125-E is the IRS's
    # own Compensation of Officers page, which decision 64 parks, and a
    # row that accepts a PDF would have filed it as the firm's schedule.
    "officer_comp": dict(short="Officer Comp", document="Officer Compensation Detail",
                         any_keywords="officer compensation detail, officer compensation schedule",
                         extensions="xlsx, pdf"),
    # Decision 141, the owner's rows. A K-1 a *business* receives, by the
    # title every federal K-1 prints on its face and the California LLC
    # K-1's (568) - required, so the row outranks the return's own rows on
    # a K-1 and a K-1 never contests the prior-year return. The S
    # corporation's `shareholder's share of income` is left out on purpose:
    # a corporation or a partnership cannot hold S corporation stock, the
    # 1120-S return and California's 100S print that title on their own
    # K-1 pages, and the row would have contested every S-corp return.
    "k1_received": dict(short="K-1s Received", document="Schedule K-1s Received by the Business",
                        required_keywords="partner's share of income | beneficiary's share of income "
                                          "| member's share of income"),
    # By the forms' numbers, as the 1040's A03 and A05 are known. Neither
    # title can be a keyword: `nonemployee compensation` is on the IRS
    # "Attention" page ahead of every information return (decision 90),
    # and `payment card` is said by papers that only mention a 1099-K.
    # And the recipient's copy (the designer's ruling on the review, F2): a
    # business also *issues* 1099-NECs, and its own Copy A or Copy C is not
    # one it received. Copy B says "For Recipient" on the 1099-NEC and "For
    # Payee" on the 1099-K; Copy A says "For Internal Revenue Service
    # Center" and Copy C "For Payer".
    "payment_forms_received": dict(short="1099-K NEC Received", document="1099-K / 1099-NEC Received by the Business",
                                   required_keywords="1099-k | 1099-nec, for recipient | for payee",
                                   extensions="pdf, csv"),
    # The 1042-S by its printed title. Its number cannot be the keyword:
    # 1042 is no form family the matcher knows, so `1042-s` is a phrase,
    # and the Form 1065, 1120, 1120-F, 1040-NR and W-2G say it in their
    # withholding lines. One entry, because the owner put the same row on
    # the 1040 and on every business catalog.
    "foreign_source_income": dict(short="1042-S", document="1042-S - Foreign Person's U.S. Source Income",
                                  required_keywords="foreign person's u.s. source income"),
    # The notice's own header, never `notice` or `letter` alone. The IRS's
    # current notice prints its CP number beside "Tax year" (or "Tax
    # period") and "Notice date" on every page; the CP number cannot be a
    # keyword (it varies, and a keyword is a whole phrase), so the header's
    # two fields stand for it, with the agency by either of its names - a
    # scan of a notice's later pages carries "IRS" and not the heading.
    # All of it on the first page (the designer's ruling on the review, N2):
    # the matcher reads these header phrases there and nowhere else
    # (``content_check.FIRST_PAGE_PHRASES``), so a county tax bill whose
    # back page says "notice date", "tax year" and "IRS" is not a notice.
    # No blank form says "notice date", and an EIN letter (CP 575) prints
    # no tax year, so it stays the 1041's A02. A notice laid out any other
    # way - a state's, an IRS letter - parks for a person, which is safe;
    # the row is narrow on purpose (SPEC-141 §2.5).
    "notices": dict(short="Tax Notices", document="IRS & State Tax Notices and Letters",
                    required_keywords=f" {KEYWORD_ANY_OF} ".join(
                        f"notice date {KEYWORD_ALL_OF} {field} {KEYWORD_ALL_OF} {agency}"
                        for field in ("tax year", "tax period")
                        for agency in ("irs", "internal revenue service"))),
}


def _shared(identifier: str, key: str, *, core: bool, named: bool) -> dict:
    return _row(identifier, core=core, named=named, **SHARED[key])


# Per-form request templates shown on the wizard's second page. Every row goes
# on the return (decision 142); "core" rows are pre-ticked under "Ask the
# client", and a tick is whether the client is asked for the row and chased
# for it. An unticked row is on the return as not asked: never listed as
# needed, never chased, but a document that arrives for it files there.
FORM_TEMPLATES = {
    "1040": [
        _row("A01", "W-2 Wage Statements - All Employers", short="W-2", core=True, named=True, required_keywords="W-2, wage and tax statement, employee's social security number", expected_count=2),
        _row("A02", "1099-INT / 1099-DIV - Interest & Dividend Income", short="1099-INT-DIV", core=True, named=True, extensions="pdf, csv", any_keywords="1099-int, 1099-div, 1099-oid", expected_count=3),
        # Decision 90, the owner's: a 1040 gets one row per 1099 a person
        # actually receives, and each is known by its own number. Its
        # printed title is not always usable: the IRS "Attention" page
        # ahead of every information return names "Form 1099-NEC,
        # Nonemployee Compensation", so `nonemployee compensation` is said
        # by the blank 1098-T, 1099-G, 1099-K, 1099-R, 1099-S and 5498 as
        # well, and `certain government payments` is said by the 1040-ES
        # package and not by the 1099-G at all. The two printed titles no
        # form but its own says are kept.
        _row("A03", "1099-NEC - Nonemployee Compensation", short="1099-NEC", core=False, named=True, extensions="pdf, csv", any_keywords="1099-nec"),
        _row("A04", "1099-MISC - Miscellaneous Income", short="1099-MISC", core=False, named=True, extensions="pdf, csv", any_keywords="1099-misc, miscellaneous information"),
        # The 1099-K prints "Payment Card and Third Party Network
        # Transactions" across three boxes, so its whole title is never on
        # one line; `payment card` is what the form's box 1a and a
        # processor's own year-end summary both print, and it begins the
        # title on a checklist's line, where a menu's words are not the
        # document's (decision 73). `third party network transactions`
        # would not: it begins mid-title, past where the menu rule reads.
        _row("A05", "1099-K - Payment Card & Third-Party Network Transactions", short="1099-K", core=False, named=True, extensions="pdf, csv", any_keywords="1099-k, payment card"),
        _row("A06", "1099-G - Certain Government Payments", short="1099-G", core=False, named=True, extensions="pdf, csv", any_keywords="1099-g"),
        # Decision 141, the owner's. The SSA-1099 heads itself "Social
        # Security Benefit Statement" and the RRB-1099 "Payments by the
        # Railroad Retirement Board"; required, so the statement outranks
        # E02 - the SSA prints its revision code "Form SSA-1099-R-OP1" at
        # the top of the page, and E02's `1099-r` is said there. The
        # RRB-1099-R, the railroad pension ("Annuities or Pensions by the
        # Railroad Retirement Board"), says neither and stays with E02.
        _row("A07", "SSA-1099 / RRB-1099 - Social Security & Railroad Retirement Benefits", short="SSA-1099 RRB-1099", core=False, named=True,
             required_keywords="social security benefit statement | payments by the railroad retirement board"),
        # These three, L02 and L03 by their numbers, required: no other form
        # in either corpus says them where a form names itself, and each
        # number's variants keep it off its siblings (1099-C is not 1099-CAP,
        # W-2G is not W-2). A printed title cannot serve alone: Schedule 1
        # says "cancellation of debt" and "student loan interest", the
        # 1040-ES booklet "gambling winnings".
        # The 1099-C's number is not enough on its own either (the designer's
        # ruling on the build): OCR reads a 1099-G's "G" as "C", and a
        # required number would file that misreading. So A08 also wants the
        # form's own words - its title, or its box 2 label, because the IRS
        # sets the title one word to a line ("Cancellation" / "of Debt") and
        # the blank never says it as a phrase. Schedule 1's "cancellation of
        # debt" is harmless here: a return does not say "1099-C" as its own.
        _row("A08", "1099-C - Cancellation of Debt", short="1099-C", core=False, named=True,
             required_keywords=f"1099-c, cancellation of debt {KEYWORD_ANY_OF} amount of debt discharged"),
        _row("A09", "W-2G - Gambling Winnings", short="W-2G", core=False, named=True, required_keywords="w-2g"),
        _row("B01", "Prior-Year Federal & State Tax Returns", short="Prior-Year Returns", core=True, named=True, period=TY_PRIOR,
             required_keywords=_prior_return("individual income tax return", "filing status", JURAT,
                                             state=("resident income tax return",))),
        _row("C01", "Mortgage Interest Statement - Form 1098", short="1098 Mortgage", core=True, named=True, required_keywords="1098, mortgage interest"),
        # `thank you for your donation` is a salutation every fundraiser
        # prints: a political committee's receipt and a crowdfunding site's
        # both opened with it and both say they are not deductible. The row
        # keys on receipt wording only; a per-row refusal ("not
        # tax-deductible") is the structural fix and waits for Phase C.
        _row("D01", "Charitable Contribution Receipts", short="Charity Receipts", core=True, named=False, extensions="pdf, xlsx", any_keywords="donation receipt, giving statement, statement of giving, giving summary, giving record, donor statement, charitable contribution statement, charitable giving, tax-deductible donation, tax-deductible gift, donated goods, no goods or services, receipt for your donation, acknowledge your donation, acknowledge your charitable contribution"),
        # `realized gain and loss` is the firm's own wording; a broker heads
        # the export itself "Realized Gain/Loss" (Schwab) or "Realized
        # GainLoss" (a workbook's sheet name), and sends it as a workbook as
        # often as a CSV (decision 85). No IRS form in tests/irs/ says either.
        _row("E01", "1099-B / Brokerage Year-End Statements", short="1099-B Brokerage", core=False, named=True, extensions="pdf, csv, xlsx", any_keywords="1099-b, proceeds from broker, brokerage statement, realized gain and loss, realized gain/loss, realized gain loss"),
        _row("E02", "1099-R Retirement Distributions", short="1099-R", core=False, named=True, any_keywords="1099-r, retirement distribution"),
        # The catalog keeps **one** K-1 row (decision 93, the owner's), and
        # a federal and a state K-1 file on it alike: California heads its
        # Schedule K-1 (568) "Member's Share of Income, Deductions,
        # Credits, etc." - the LLC member's version of the three lines
        # already here, and the words decision 85's F1 was waiting on. An
        # individual who holds several K-1s gets a row per issuing entity
        # instead, added to that engagement's own list from this one
        # (`issuer_row`, `docs/runbook.md`); the catalog cannot know which
        # entities a client is a partner in.
        _row("F01", "Schedule K-1s Received", short="K-1s Received", core=False, named=True, any_keywords="partner's share of income, shareholder's share of income, beneficiary's share of income, member's share of income"),
        # The bill's own titles. `assessor` and `parcel number` are printed
        # by the assessor's "Notice of Assessed Value - This is not a tax
        # bill", and `property tax bill` by the servicer's escrow analysis,
        # which lists the bill it paid; a county bill that prints nothing
        # but "property tax bill" mid-page parks for a person.
        _row("G01", "Property Tax Statements", short="Property Tax", core=False, named=True, any_keywords="secured property tax bill, annual secured property tax, property tax statement, real estate tax bill, property tax notice"),
        _shared("H01", "estimated_tax", core=False, named=False),
        # `advance payment of premium tax credit` is the marketplace's
        # eligibility notice's sentence as much as the form's column head,
        # and it never matched the form anyway: the 1095-A wraps it across
        # two lines. The form's own identifiers are enough.
        _row("I01", "Form 1095-A - Marketplace Health Insurance", short="1095-A", core=False, named=True, any_keywords="1095-a, marketplace identifier, monthly enrollment premium"),
        # The matcher reads the space between a keyword's words as optional,
        # so `child care statement` already finds "Childcare Statement" and
        # `day care receipt` finds "Daycare Receipt"; the run-together
        # spellings were a second copy of every keyword. What was missing
        # was the two-word one a provider actually prints.
        _row("J01", "Childcare Provider Statements - Name, EIN, Amounts", short="Childcare", core=False, named=False, extensions="pdf, xlsx", any_keywords="child care statement, day care statement, child care provider statement, day care provider statement, dependent care provider statement, child care receipt, day care receipt, child care tax statement, statement of child care expenses, statement of day care expenses, year-end child care, year-end day care"),
        _row("K01", "IRA / HSA Contribution Statements - Form 5498", short="5498 IRA-HSA", core=False, named=True, any_keywords="5498, 5498-sa, 5498-esa, ira contribution information, medicare advantage msa information"),
        _row("L01", "Tuition Statements - Form 1098-T", short="1098-T", core=False, named=True, any_keywords="1098-t, qualified tuition and related expenses"),
        _row("L02", "1098-E - Student Loan Interest", short="1098-E", core=False, named=True, extensions="pdf, csv", required_keywords="1098-e"),
        _row("L03", "1099-Q - 529 / Coverdell Education Savings Distributions", short="1099-Q", core=False, named=True, required_keywords="1099-q"),
        # The client's own sheet, so no form title exists; any keyword, so a
        # return that prints the same words outranks it. `schedule c` alone
        # is what every 1099's instructions say ("report on Schedule C"),
        # and `cost of goods sold`, `gross sales`, `total expense` and `net
        # income` are every business return's lines. A summary is known by
        # its shape: the sales line, the inventory that goes into cost of
        # goods and the expense total, together - the 990s print the first
        # and the last but never `ending inventory`, and a mileage log, a
        # receipt or a bank statement prints none of the three (a mileage
        # line alone is a log, not a summary: the designer's ruling on the
        # build). The others are the headings a client's summary carries,
        # the owner's title among them.
        _row("M01", "Schedule C - Business Income & Expense Summary", short="Schedule C", core=False, named=False,
             extensions="xlsx, pdf, csv",
             any_keywords=f"gross sales {KEYWORD_ALL_OF} ending inventory {KEYWORD_ALL_OF} total expense, "
                          "business income and expense summary, "
                          "business income & expense summary, schedule c worksheet, schedule c summary"),
        _shared("N01", "foreign_source_income", core=False, named=True),
        _shared("Z01", "notices", core=False, named=True),
    ],
    "1120": [
        # No state corporate return is in the corpus the suite defends, so
        # this row's alternatives are the federal words alone; California's
        # Form 100 would be one more phrase (decision 90).
        _row("A01", "Prior-Year Federal & State Corporate Returns", short="Prior-Year Returns", core=True, named=True, period=TY_PRIOR,
             required_keywords=_prior_return("u.s. corporation income tax return", JURAT)),
        _shared("A02", "trial_balance", core=True, named=False),
        _shared("A03", "general_ledger", core=True, named=False),
        _shared("B01", "financial_statements", core=True, named=True),
        _shared("B02", "december_bank", core=True, named=True),
        _shared("C01", "fixed_assets", core=True, named=False),
        _shared("C02", "depreciation", core=False, named=False),
        _shared("D01", "loans", core=False, named=True),
        _shared("E01", "payroll_returns", core=True, named=True),
        _shared("E02", "officer_comp", core=False, named=False),
        _shared("F01", "business_estimated_tax", core=False, named=False),
        _row("G01", "Shareholder List & Ownership Changes", short="Shareholder List", core=False, named=False, extensions="xlsx, pdf", any_keywords="shareholder list, stock ledger, cap table, capitalization table"),
        _shared("H01", "apportionment", core=False, named=False),
        _row("I01", "Book-Tax Difference Support - Schedule M-1 Items", short="Schedule M-1", core=False, named=False, extensions="xlsx, pdf", any_keywords="book-tax difference, m-1 adjustment, m-1 support, book to tax reconciliation"),
        _shared("J01", "k1_received", core=False, named=True),
        _shared("J02", "payment_forms_received", core=False, named=True),
        _shared("J03", "foreign_source_income", core=False, named=True),
        _shared("Z01", "notices", core=False, named=True),
    ],
    "1120S": [
        # California heads Form 100S "California S Corporation / Franchise
        # or Income Tax Return", and the second line is what survives the
        # break; no form in tests/irs/ says it (decision 90).
        _row("A01", "Prior-Year Federal & State S-Corp Returns", short="Prior-Year Returns", core=True, named=True, period=TY_PRIOR,
             required_keywords=_prior_return("income tax return for an s corporation", JURAT,
                                             state=("franchise or income tax return",))),
        _shared("A02", "trial_balance", core=True, named=False),
        _shared("A03", "general_ledger", core=True, named=False),
        _shared("B01", "financial_statements", core=True, named=True),
        _shared("B02", "december_bank", core=True, named=True),
        _row("C01", "Shareholder List with Ownership % & Changes", short="Shareholder List", core=True, named=False, extensions="xlsx, pdf", any_keywords="shareholder list, stock ledger, cap table, capitalization table"),
        _row("C02", "Distributions by Shareholder", short="Distributions", core=True, named=False, extensions="xlsx", any_keywords="distributions by shareholder, shareholder distribution schedule, distribution detail by shareholder"),
        _row("C03", "Shareholder Basis Schedules", short="Shareholder Basis", core=False, named=False, extensions="xlsx, pdf", any_keywords="shareholder basis schedule, stock basis schedule, stock and debt basis, basis computation"),
        _row("D01", "Officer / Shareholder W-2 Compensation Detail", short="Officer W-2", core=True, named=True, extensions="xlsx, pdf", any_keywords="officer compensation detail, shareholder w-2, officer w-2"),
        _row("D02", "Health Insurance Premiums for >2% Shareholders", short="Health Insurance 2%", core=False, named=False, extensions="pdf, xlsx", any_keywords="health insurance premiums paid, 2% shareholder, shareholder health insurance premiums"),
        _shared("E01", "payroll_returns", core=False, named=True),
        _shared("F01", "fixed_assets", core=False, named=False),
        _shared("F02", "depreciation", core=False, named=False),
        # `shareholder loan agreement` is inside `loan agreement`; the row
        # was missing the two words an amortisation schedule and a loan
        # statement print, which the shared loans row has always had.
        _row("G01", "Loan Agreements & Shareholder Loan Activity", short="Shareholder Loans", core=False, named=True, extensions="pdf, xlsx", any_keywords="loan agreement, promissory note, loan statement, amortization schedule, principal balance"),
        _shared("H01", "apportionment", core=False, named=False),
        _shared("I01", "k1_received", core=False, named=True),
        _shared("I02", "payment_forms_received", core=False, named=True),
        _shared("I03", "foreign_source_income", core=False, named=True),
        _shared("Z01", "notices", core=False, named=True),
    ],
    "1065": [
        # California heads Form 568 "Limited Liability Company / Return of
        # Income" and New York heads IT-204 "Partnership Return"; both
        # second lines are the state form's own. `partnership return` is
        # said by the blank Form 1065 as well, which is this same row's
        # federal document, so it takes nothing the row must not have
        # (decision 90). The 568's second line wants its first beside it
        # (decision 141): a preparer's cover letter names the "Return of
        # Income" a K-1 came from, and a bare `return of income` made the
        # K-1 a partnership received a prior-year return.
        _row("A01", "Prior-Year Federal & State Partnership Returns", short="Prior-Year Returns", core=True, named=True, period=TY_PRIOR,
             required_keywords=_prior_return("return of partnership income", JURAT,
                                             state=(f"return of income {KEYWORD_ALL_OF} limited liability company",
                                                    "partnership return"))),
        _row("A02", "Partnership Agreement & Amendments", short="Partnership Agmt", core=True, named=True, period="Current", any_keywords="partnership agreement, operating agreement"),
        _shared("A03", "trial_balance", core=True, named=False),
        _shared("A04", "general_ledger", core=False, named=False),
        _shared("B01", "financial_statements", core=True, named=True),
        _shared("B02", "december_bank", core=True, named=True),
        _row("C01", "Partner List with Ownership % & Changes", short="Partner List", core=True, named=False, extensions="xlsx, pdf", any_keywords="partner list, partner roster, member list, cap table, capitalization table"),
        _row("C02", "Partner Capital Account Detail", short="Capital Accounts", core=True, named=False, extensions="xlsx", any_keywords="capital account detail, capital account statement, capital account analysis by partner"),
        _row("C03", "Contributions & Distributions by Partner", short="Contrib & Distrib", core=True, named=False, extensions="xlsx", any_keywords="contributions and distributions by partner, partner contribution detail, partner distribution detail"),
        _row("C04", "Guaranteed Payment Detail", short="Guaranteed Payments", core=False, named=False, extensions="xlsx, pdf", any_keywords="guaranteed payment detail, guaranteed payments by partner"),
        _shared("D01", "fixed_assets", core=False, named=False),
        _shared("D02", "depreciation", core=False, named=False),
        _shared("E01", "loans", core=False, named=True),
        # Decision 85's F1: a CA Schedule K-1 (568) prints "Enter member's
        # percentage (without regard to special allocations)", so it
        # reaches this row in a 1065 engagement. Decision 141 gave the
        # partnership a row for the K-1s it *receives* (H01), which the
        # K-1 reaches on its required title, so it files there; `special
        # allocation` stays this row's only plain-English word.
        _row("F01", "Special Allocation Support - Section 704(b)", short="704(b) Allocations", core=False, named=False, extensions="xlsx, pdf", any_keywords="special allocation, section 704(b)"),
        _shared("G01", "apportionment", core=False, named=False),
        _shared("H01", "k1_received", core=False, named=True),
        _shared("H02", "payment_forms_received", core=False, named=True),
        _shared("H03", "foreign_source_income", core=False, named=True),
        _shared("Z01", "notices", core=False, named=True),
    ],
    "1041": [
        # A bare `trust agreement` is what a custodian heads an IRA's
        # "Traditional IRA Trust Agreement and Disclosure Statement" with;
        # the estate's own instrument names the kind of trust it is.
        _row("A01", "Trust Instrument / Will & Amendments", short="Trust or Will", core=True, named=True, period="Current", any_keywords="revocable trust agreement, irrevocable trust agreement, declaration of trust, certification of trust, trust instrument, amendment to the trust, last will, codicil"),
        _row("A02", "IRS EIN Assignment Letter", short="EIN Letter", core=False, named=True, period="Current", any_keywords="cp 575, ein assignment, assigned you employer identification number, assigned you an employer identification number"),
        _row("A03", "Prior-Year Fiduciary Returns", short="Prior-Year Returns", core=True, named=True, period=TY_PRIOR,
             required_keywords=_prior_return("income tax return for estates and trusts", JURAT)),
        # A broker's realized gain/loss export is the trust's 1099-B by
        # another name: the trust reports the same lots, and the export is
        # what arrives where the consolidated 1099 does not (decision 85).
        # Decision 68's composite is untouched - it never prints the words.
        _row("B01", "1099s for Trust / Estate Accounts", short="Trust 1099s", core=True, named=True, extensions="pdf, csv", any_keywords="1099-int, 1099-div, 1099-b, 1099-oid, 1099-r, 1099-misc, 1099-nec, realized gain/loss, realized gain loss", expected_count=3),
        # `year-end account statement` is a bank's heading as much as a
        # broker's, and a bank's year-end statement is not the brokerage
        # statement this row asks for; a document titled only that parks.
        _row("B02", "Brokerage Year-End Statements", short="Brokerage Statements", core=True, named=True, any_keywords="brokerage statement, realized gain and loss"),
        # `distribution schedule` is a mutual fund's own heading for its
        # year-end capital gains dates.
        _row("C01", "Distributions to Beneficiaries - Dates & Amounts", short="Distributions", core=True, named=False, extensions="xlsx, pdf", any_keywords="distributions to beneficiaries, beneficiary distribution"),
        _row("C02", "Beneficiary Names, Addresses & Tax IDs", short="Beneficiaries", core=True, named=False, period="Current", extensions="xlsx, pdf", any_keywords="beneficiary information, beneficiary list, beneficiary names"),
        _row("D01", "Fiduciary, Attorney & Accounting Fees Paid", short="Fees Paid", core=False, named=False, extensions="pdf, xlsx", any_keywords="fiduciary fees paid, trustee fees, accounting fees paid, legal fees paid, attorney fees paid, fee invoice"),
        # An estate's basis is the value at death, which its schedules call
        # stepped-up. A bare `date of death` is not the row's: the Form
        # 5498's instructions tell an estate to ask for a date-of-death
        # value, and the blank form would have filed here.
        _row("E01", "Cost Basis for Assets Sold During the Year", short="Cost Basis", core=False, named=False, extensions="xlsx, pdf", any_keywords="cost basis schedule, basis of assets sold, date acquired and date sold, purchase price and sale price, stepped-up basis"),
        _row("F01", "Rental / Business Income & Expense Detail", short="Rental-Business", core=False, named=False, extensions="xlsx, pdf", any_keywords="rental income and expenses, rent roll, schedule e detail, schedule c detail"),
        # The owner's title (decision 141), and the 1041-ES's own words, not
        # the 1040's: an individual's 1040-ES voucher in a trust's engagement
        # is another entity's estimated payments and parks (decision 96's
        # (b)). Required: the form's number, with its title (the booklet's
        # first page) or the voucher's own line (a voucher torn off alone).
        _row("G01", SHARED["estimated_tax"]["document"], short="Estimated Payments", core=False, named=False, extensions="pdf, xlsx",
             required_keywords=f"1041-es, estimated income tax for estates and trusts {KEYWORD_ANY_OF} "
                               "estate or trust is making a payment of estimated tax"),
        _shared("Z01", "notices", core=False, named=True),
    ],
    "990": [
        _row("A01", "Prior-Year Form 990 & State Filings", short="Prior-Year 990", core=True, named=True, period=TY_PRIOR,
             required_keywords=_prior_return("return of organization exempt from income tax", JURAT)),
        _shared("A02", "trial_balance", core=True, named=False),
        _shared("B01", "financial_statements", core=True, named=True),
        _shared("B02", "december_bank", core=True, named=True),
        _row("C01", "Board of Directors List & Meeting Minutes", short="Board & Minutes", core=True, named=False, extensions="pdf, xlsx", any_keywords="board of directors list, list of directors, meeting minutes, board minutes, minutes of the, board roster, directors and officers"),
        # `compensation of officers` is the line every 990's Part VII and
        # every nonprofit Statement of Functional Expenses prints, and the
        # 1120 prints it too; the schedule this row asks for is headed
        # "Compensation of Officers, Directors and Trustees", whose "and"
        # the Part VII heading ("Directors, Trustees, Key Employees") does
        # not have - a keyword cannot carry the comma, since Any Keywords
        # is a comma-separated column.
        _row("C02", "Officer & Key Employee Compensation Detail", short="Officer Comp", core=True, named=False, extensions="xlsx, pdf", any_keywords="officer compensation detail, key employee compensation, directors and trustees"),
        _row("D01", "Contribution / Donor Detail - Schedule B Support", short="Donors Schedule B", core=True, named=False, extensions="xlsx, csv", any_keywords="donor list, donor detail, contributions by donor, schedule b"),
        # A bare `grantee` is the word on a grant award letter the charity
        # *received*; this row is the grants it made. A bare `grants paid`
        # is line 25 of the 990-PF ("contributions, gifts, grants paid"),
        # so the schedule is named by its own heading.
        _row("D02", "Grants Made - Recipients & Amounts", short="Grants Made", core=False, named=False, extensions="xlsx, pdf", any_keywords="grants paid schedule, grants made, schedule of grants, grantee list"),
        # `program description` is a grant proposal's own heading.
        _row("E01", "Program Service Accomplishment Descriptions", short="Program Services", core=False, named=False, extensions="pdf, xlsx", any_keywords="program service accomplishment, program accomplishments"),
        _row("F01", "Fundraising Event Revenue & Expense Detail", short="Fundraising Events", core=False, named=False, extensions="xlsx, pdf", any_keywords="fundraising event detail, special event revenue, event revenue and expense"),
        _shared("G01", "payroll_returns", core=False, named=True),
        _row("H01", "Unrelated Business Income Detail", short="Unrelated Business", core=False, named=False, extensions="xlsx, pdf", any_keywords="form 990-t, unrelated business income detail, ubti schedule"),
        _shared("Z01", "notices", core=False, named=True),
    ],
}



# ------------------------------------------------------- a row per issuer ----

#: Which catalog row a K-1 arrives on, and so which row an issuer row is
#: cut from. One row, named once: the runbook tells a person to copy it,
#: and this is which one they copy.
K1_CATALOG = "1040"
K1_IDENTIFIER = "F01"
#: How an issuer row is named, so the client folder and the filed copy both
#: say whose K-1 is in them ("F02 - Schedule K-1 - Ashford Holdings LP").
ISSUER_DOCUMENT = "Schedule K-1 - {entity}"


def k1_row() -> dict:
    """The catalog's one K-1 row, the row every issuer row is cut from."""
    return next(spec for spec in FORM_TEMPLATES[K1_CATALOG]
                if spec["identifier"] == K1_IDENTIFIER)


def issuer_row(identifier: str, entity: str) -> dict:
    """One K-1 request, for the one entity that issued it, as a row spec.

    The owner's decision (2026-09-18): federal and state K-1s file on the
    same K-1 row, but K-1s are separated by the entity that issued them,
    because one person can hold several and two entities' K-1s in one
    folder is a folder nobody can work from. So the *catalog* keeps one
    K-1 row - it cannot know which partnerships a client is in - and a
    person adds one row per issuer to that engagement's own list.

    Nothing new in the schema: an issuer row is the K-1 row with the
    entity's name in Required Keywords and the entity in its Document
    name. That makes it the stronger evidence of the two by the rules
    already in :mod:`tracker.router` - a required keyword outranks an any
    keyword, and the generic row has none - so the K-1 that names its
    issuer files on that issuer's row, and the one that names no listed
    issuer parks (``reasons.ISSUER_NOT_NAMED``) instead of joining
    everybody else's on the generic row.

    ``identifier`` is the next free one in the K-1 row's section (``F02``,
    ``F03``…). The name is normalised the one way entity names are
    (:func:`tracker.manifest.entity_keyword`), so two people typing
    "Ashford Holdings, L.P." and "Ashford Holdings LP" build one row and
    neither smuggles a comma into a comma-separated cell.

    It has no short name of its own (decision 144): one is derived from its
    Document, so "ABC Partners LLC"'s row is named ``Schedule K-1 - ABC``
    in the firm's folders, the issuer's name as far as twenty characters
    allow.
    """
    name = entity_keyword(entity)
    if not name:
        raise ManifestError("an issuer row needs the name of the entity that issued the K-1")
    source = k1_row()
    return _row(
        identifier,
        ISSUER_DOCUMENT.format(entity=name),
        core=False,
        # A K-1 is addressed to its recipient, so the row it is cut from is
        # named and so is this one (decision 128). The entity's name in
        # Required Keywords is still a keyword and never a name: it says
        # *which* K-1 this is, and the people list says whose it is.
        named=source["named"],
        period=source["period"],
        extensions=source["extensions"],
        required_keywords=name,
        any_keywords=source["any_keywords"],
        # How many files the K-1 row expects, as the row it is cut from says
        # (decision 145: this line was missing, so an issuer row expected one
        # whatever the K-1 row expected - one today, so no list changed).
        expected_count=source.get("expected_count", 1),
    )


# ------------------------------------------------------------------ items ----


def item_from_spec(spec: dict) -> RequestItem:
    """One catalog row (or one wizard row) as a :class:`RequestItem`.

    The parsing is the manifest's (:func:`tracker.manifest.item_from_fields`,
    with the identifier as the prefix of every refusal); this adds the
    catalog's own one rule: a row with no content rule at all gets its own
    document name as the required keyword. Without a rule the request could
    never auto-file, and a custom request typed into the wizard in a hurry
    should still work; the editor shows the rule, so it is a visible
    default, not a secret. A row still needs an identifier and a document
    name, and an identifier the file system would alter is refused here as
    it is everywhere else.
    """
    identifier = str(spec.get("identifier", "") or "").strip()
    document = str(spec.get("document", "") or "").strip()
    if not identifier or not document:
        raise ManifestError("every request needs an identifier and a document name")
    problem = identifier_problem(identifier)
    if problem:
        raise ManifestError(f"Identifier {identifier!r} {problem}")
    item = item_from_fields(spec, where=identifier)
    if not (item.required_keywords or item.any_keywords or item.date_pattern):
        item = replace(item, required_keywords=(document,))
    return item


def default_tax_year(today: dt.date | None = None) -> int:
    """The tax year a new engagement is for: the most recently ended year.

    A return prepared at any point in 2027 is for tax year 2026. The
    catalog is written for one base year and shifted to this, so nobody
    edits TY2025 into TY2026 across six checklists every January - or
    forgets to, and creates a year of engagements asking for last year's
    forms.
    """
    today = today or dt.date.today()
    return today.year - 1


# --------------------------------------------------------------- the dates ----

#: The statutory filing date of each return the catalog knows, as (month,
#: day) in the year after the tax year - the owner's table, 2026-09-20
#: (decision 117). A form that is not in here has no default at all: a
#: deadline guessed for a return nobody wrote a date for would be read to a
#: client as the firm's own word for when their return is due.
FILING_DEADLINES: dict[str, tuple[int, int]] = {
    "1040": (4, 15),
    "1120": (4, 15),
    "1041": (4, 15),
    "1120S": (3, 15),
    "1065": (3, 15),
    "990": (5, 15),
}
#: How far ahead of the filing deadline the firm asks to have everything in
#: hand: the Due Date a new engagement starts with. The reminder never says
#: this number - it names the two dates and never the arithmetic between
#: them, because either is a person's to move (decision 117).
TARGET_DAYS_BEFORE_DEADLINE = 5
#: The days a date is never moved on to, or back on to: the weekend.
_WEEKEND = (5, 6)


def filing_deadline_for(form: str, year: int) -> dt.date | None:
    """When ``form``'s return for tax year ``year`` has to be filed, or None.

    The table's day in the year after the tax year, moved **forward** off
    the weekend the way the IRS moves it. A holiday is a person's edit: the
    federal and state calendars differ, they move, and a date the code got
    wrong would be a date a client was told in the firm's name. Unknown
    form, unknown deadline - never a guess.
    """
    when = FILING_DEADLINES.get(form)
    if when is None:
        return None
    month, day = when
    deadline = dt.date(year + 1, month, day)
    while deadline.weekday() in _WEEKEND:
        deadline += dt.timedelta(days=1)
    return deadline


def ask_by_for(deadline: dt.date) -> dt.date:
    """The Due Date that goes with ``deadline``: the firm's own ask-by target.

    :data:`TARGET_DAYS_BEFORE_DEADLINE` days before it, moved **back** off
    the weekend - a target the office cannot work on is not a target. It is
    a default and nothing more: a person moves either date in the editor,
    and the reminder reads whatever they left.
    """
    target = deadline - dt.timedelta(days=TARGET_DAYS_BEFORE_DEADLINE)
    while target.weekday() in _WEEKEND:
        target -= dt.timedelta(days=1)
    return target


#: What the wizard says about the year field and the two blank-able rules.
YEAR_NOTE = "Defaults to the most recently ended year; the checklist's periods follow it"
EXTENSION_DEFAULT_NOTE = ("blank means " + ", ".join(DEFAULT_EXTENSIONS)
                          + "; a photo or an image counts as a PDF")
KEYWORD_DEFAULT_NOTE = "defaults to the document name"


def require_form(form: str) -> None:
    """Refuse a form the catalog does not know, with the one sentence for it."""
    if form not in FORM_TEMPLATES:
        raise ManifestError(
            f"Unknown tax form type '{form}'; expected one of {', '.join(FORM_TEMPLATES)}"
        )


def base_year(form: str) -> int | None:
    """The tax year the catalog's rows for ``form`` are written for."""
    return detect_year(item_from_spec(spec) for spec in FORM_TEMPLATES[form])


def template_items(
    form: str, *, core_only: bool = False, year: int | None = None
) -> list[RequestItem]:
    """The checklist for ``form`` as request items, for tax year ``year``.

    ``year=None`` returns the catalog as written (its base year); the
    wizard and the create command pass :func:`default_tax_year` or the
    year the person chose. Relative periods shift with it, so the
    prior-year-return row stays one year behind. Unknown form → ManifestError.
    """
    require_form(form)
    items = [
        item_from_spec(spec)
        for spec in FORM_TEMPLATES[form]
        if spec["core"] or not core_only
    ]
    if year is None:
        return items
    base = base_year(form)
    delta = (year - base) if base else 0
    return [shift_item(item, delta) for item in items]
