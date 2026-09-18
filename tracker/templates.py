"""The per-form request catalog: one checklist per return type (component 11).

Every request list starts from here. Pick the return (1040, 1120, 1120-S,
1065, 1041, 990) and this module says which documents to ask for, what
they are called, how many to expect and — the part that makes the pipeline
run unattended — the keyword and date rules the router and scanner use to
recognise each one.

This is the **only** place the checklists live. There is no second copy to
keep in step: the manifest an engagement is created with is the readable
one, and the wizard reads this module directly.

Every row carries a keyword rule. A request with no keyword has no way to
recognise its document, so it never auto-files (see :mod:`tracker.router`);
a template row like that would be a request the system can only ever park
for a person, which defeats the point of a template. The year check is not
written here: a Period like ``TY2025`` implies it (:func:`tracker.manifest.derived_date_pattern`).
"""

from __future__ import annotations

import datetime as dt

from tracker.manifest import (
    COL_EXPECTED_COUNT,
    COL_MIN_SIZE_KB,
    DEFAULT_EXPECTED_COUNT,
    DEFAULT_EXTENSIONS,
    DEFAULT_MIN_SIZE_KB,
    ManifestError,
    RequestItem,
    csv_tuple,
    detect_year,
    identifier_problem,
    parse_extensions,
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


def _row(identifier: str, document: str, *, core: bool, period: str = TY, extensions: str = "pdf",
         required_keywords: str = "", any_keywords: str = "", expected_count: int = 1) -> dict:
    row = {"identifier": identifier, "document": document, "period": period,
           "extensions": extensions, "core": core}
    if expected_count > 1:
        row["expected_count"] = expected_count
    if required_keywords:
        row["required_keywords"] = required_keywords
    if any_keywords:
        row["any_keywords"] = any_keywords
    return row


# Requests several return types share. Defined once, so a keyword fix here
# reaches every form that asks for the document; each form only says which
# identifier it uses and whether the row is pre-ticked.
SHARED = {
    "trial_balance": dict(document="Trial Balance - Year-End", any_keywords="trial balance",
                          extensions="xlsx, csv, pdf"),
    "general_ledger": dict(document="General Ledger Detail", any_keywords="general ledger",
                           extensions="xlsx, csv, pdf"),
    "financial_statements": dict(
        document="Year-End Financial Statements",
        any_keywords="balance sheet as of, statement of financial position, income statement, statement of income, "
                     "profit and loss, statement of operations, statement of activities, statement of cash flows",
        extensions="pdf, xlsx"),
    "december_bank": dict(document="December Bank Statements & Year-End Reconciliations",
                          any_keywords="bank statement, statement of account, checking summary, deposits and additions, "
                                       "deposits and other credits, checks paid, withdrawals and other debits, "
                                       "bank reconciliation",
                          period=DEC),
    "payroll_returns": dict(document="Payroll Tax Returns - Forms 941 & W-3",
                            any_keywords="form 941, employer's quarterly federal tax return, form 940, "
                                         "employer's annual federal unemployment, form w-3, w-3 transmittal"),
    # A voucher's own lines: its numbered heading and the amount line. The
    # 1040-ES booklet's instructions say "estimated tax payment voucher" in
    # prose, and its blank vouchers are pages the reader never reaches.
    "estimated_tax": dict(document="Estimated Tax Payment Records",
                          any_keywords="estimated tax payment voucher 1, estimated tax payment voucher 2, "
                                       "estimated tax payment voucher 3, estimated tax payment voucher 4, "
                                       "estimated tax payment voucher for individuals, "
                                       "amount of estimated tax you are paying, estimated tax voucher, "
                                       "estimated payments made",
                          extensions="pdf, xlsx"),
    "fixed_assets": dict(document="Fixed Asset Additions & Disposals Detail",
                         any_keywords="fixed asset schedule, fixed asset listing, fixed asset additions, "
                                      "asset additions and disposals",
                         extensions="xlsx"),
    "loans": dict(document="Loan Agreements & Year-End Balances",
                  any_keywords="loan agreement, promissory note, amortization schedule, loan statement, "
                               "principal balance",
                  period=AS_OF_YEAR_END),
    "apportionment": dict(document="State Apportionment Data - Sales, Payroll, Property by State",
                          any_keywords="apportionment schedule, apportionment data, sales by state, payroll by state",
                          extensions="xlsx"),
    "officer_comp": dict(document="Officer Compensation Detail",
                         any_keywords="officer compensation detail, officer compensation schedule, form 1125-e",
                         extensions="xlsx"),
}


def _shared(identifier: str, key: str, *, core: bool) -> dict:
    return _row(identifier, core=core, **SHARED[key])


# Per-form request templates shown on the wizard's second page. "core" items
# are pre-checked.
FORM_TEMPLATES = {
    "1040": [
        _row("A01", "W-2 Wage Statements - All Employers", core=True, required_keywords="W-2, wage and tax statement, employee's social security number", expected_count=2),
        _row("A02", "1099-INT / 1099-DIV - Interest & Dividend Income", core=True, extensions="pdf, csv", any_keywords="1099-int, 1099-div, 1099-oid", expected_count=3),
        _row("B01", "Prior-Year Federal & State Tax Returns", core=True, period=TY_PRIOR, required_keywords="individual income tax return, filing status, under penalties of perjury"),
        _row("C01", "Mortgage Interest Statement - Form 1098", core=True, required_keywords="1098, mortgage interest"),
        _row("D01", "Charitable Contribution Receipts", core=True, extensions="pdf, xlsx", any_keywords="donation receipt, giving statement, statement of giving, giving summary, giving record, donor statement, charitable contribution statement, charitable contributions statement, charitable giving, tax-deductible donation, tax-deductible gift, donated goods, no goods or services, thank you for your donation, receipt for your donation, acknowledge your donation, acknowledge your charitable contribution"),
        _row("E01", "1099-B / Brokerage Year-End Statements", core=False, extensions="pdf, csv", any_keywords="1099-b, proceeds from broker, brokerage statement, realized gain and loss"),
        _row("E02", "1099-R Retirement Distributions", core=False, any_keywords="1099-r, retirement distribution"),
        _row("F01", "Schedule K-1s Received", core=False, any_keywords="partner's share of income, shareholder's share of income, beneficiary's share of income"),
        _row("G01", "Property Tax Statements", core=False, any_keywords="property tax statement, property tax bill, secured property tax, tax assessor, assessor, parcel number"),
        _shared("H01", "estimated_tax", core=False),
        _row("I01", "Form 1095-A - Marketplace Health Insurance", core=False, any_keywords="1095-a, marketplace identifier, monthly enrollment premium, advance payment of premium tax credit"),
        _row("J01", "Childcare Provider Statements - Name, EIN, Amounts", core=False, extensions="pdf, xlsx", any_keywords="child care statement, childcare statement, daycare statement, child care provider statement, childcare provider statement, daycare provider statement, dependent care provider statement, child care receipt, childcare receipt, daycare receipt, child care tax statement, childcare tax statement, statement of child care expenses, statement of childcare expenses, statement of daycare expenses, year-end child care, year-end childcare, year-end daycare"),
        _row("K01", "IRA / HSA Contribution Statements - Form 5498", core=False, any_keywords="5498, 5498-sa, 5498-esa, ira contribution information, medicare advantage msa information"),
        _row("L01", "Tuition Statements - Form 1098-T", core=False, any_keywords="1098-t, qualified tuition and related expenses"),
    ],
    "1120": [
        _row("A01", "Prior-Year Federal & State Corporate Returns", core=True, period=TY_PRIOR, required_keywords="u.s. corporation income tax return, under penalties of perjury"),
        _shared("A02", "trial_balance", core=True),
        _shared("A03", "general_ledger", core=True),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _shared("C01", "fixed_assets", core=True),
        _row("C02", "Depreciation Schedules", core=False, extensions="xlsx, pdf", any_keywords="depreciation schedule, depreciation detail, depreciation report, form 4562"),
        _shared("D01", "loans", core=False),
        _shared("E01", "payroll_returns", core=True),
        _shared("E02", "officer_comp", core=False),
        _shared("F01", "estimated_tax", core=False),
        _row("G01", "Shareholder List & Ownership Changes", core=False, extensions="xlsx, pdf", any_keywords="shareholder list, stock ledger, cap table, capitalization table"),
        _shared("H01", "apportionment", core=False),
        _row("I01", "Book-Tax Difference Support - Schedule M-1 Items", core=False, extensions="xlsx, pdf", any_keywords="book-tax difference, m-1 adjustment, m-1 support, book to tax reconciliation"),
    ],
    "1120S": [
        _row("A01", "Prior-Year Federal & State S-Corp Returns", core=True, period=TY_PRIOR, required_keywords="income tax return for an s corporation, under penalties of perjury"),
        _shared("A02", "trial_balance", core=True),
        _shared("A03", "general_ledger", core=True),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _row("C01", "Shareholder List with Ownership % & Changes", core=True, extensions="xlsx, pdf", any_keywords="shareholder list, stock ledger, cap table, capitalization table"),
        _row("C02", "Distributions by Shareholder", core=True, extensions="xlsx", any_keywords="distributions by shareholder, shareholder distribution schedule, distribution detail by shareholder"),
        _row("C03", "Shareholder Basis Schedules", core=False, extensions="xlsx, pdf", any_keywords="shareholder basis schedule, stock basis schedule, stock and debt basis, basis computation"),
        _row("D01", "Officer / Shareholder W-2 Compensation Detail", core=True, extensions="xlsx, pdf", any_keywords="officer compensation detail, shareholder w-2, officer w-2"),
        _row("D02", "Health Insurance Premiums for >2% Shareholders", core=False, extensions="pdf, xlsx", any_keywords="health insurance premiums paid, 2% shareholder, shareholder health insurance premiums"),
        _shared("E01", "payroll_returns", core=False),
        _shared("F01", "fixed_assets", core=False),
        _row("G01", "Loan Agreements & Shareholder Loan Activity", core=False, extensions="pdf, xlsx", any_keywords="loan agreement, promissory note, shareholder loan agreement, loan statement"),
        _shared("H01", "apportionment", core=False),
    ],
    "1065": [
        _row("A01", "Prior-Year Federal & State Partnership Returns", core=True, period=TY_PRIOR, required_keywords="return of partnership income, under penalties of perjury"),
        _row("A02", "Partnership Agreement & Amendments", core=True, period="Current", any_keywords="partnership agreement, operating agreement"),
        _shared("A03", "trial_balance", core=True),
        _shared("A04", "general_ledger", core=False),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _row("C01", "Partner List with Ownership % & Changes", core=True, extensions="xlsx, pdf", any_keywords="partner list, partner roster, member list, cap table, capitalization table"),
        _row("C02", "Partner Capital Account Detail", core=True, extensions="xlsx", any_keywords="capital account detail, capital account statement, capital account analysis by partner"),
        _row("C03", "Contributions & Distributions by Partner", core=True, extensions="xlsx", any_keywords="contributions and distributions by partner, partner contribution detail, partner distribution detail"),
        _row("C04", "Guaranteed Payment Detail", core=False, extensions="xlsx, pdf", any_keywords="guaranteed payment detail, guaranteed payments by partner"),
        _shared("D01", "fixed_assets", core=False),
        _shared("E01", "loans", core=False),
        _row("F01", "Special Allocation Support - Section 704(b)", core=False, extensions="xlsx, pdf", any_keywords="special allocation, section 704(b)"),
        _shared("G01", "apportionment", core=False),
    ],
    "1041": [
        _row("A01", "Trust Instrument / Will & Amendments", core=True, period="Current", any_keywords="trust agreement, last will, codicil"),
        _row("A02", "IRS EIN Assignment Letter", core=False, period="Current", any_keywords="cp 575, ein assignment, assigned you employer identification number, assigned you an employer identification number"),
        _row("A03", "Prior-Year Fiduciary Returns", core=True, period=TY_PRIOR, required_keywords="income tax return for estates and trusts, under penalties of perjury"),
        _row("B01", "1099s for Trust / Estate Accounts", core=True, extensions="pdf, csv", any_keywords="1099-int, 1099-div, 1099-b, 1099-oid, 1099-r, 1099-misc, 1099-nec", expected_count=3),
        _row("B02", "Brokerage Year-End Statements", core=True, any_keywords="brokerage statement, realized gain and loss, year-end account statement"),
        _row("C01", "Distributions to Beneficiaries - Dates & Amounts", core=True, extensions="xlsx, pdf", any_keywords="distributions to beneficiaries, beneficiary distribution, distribution schedule"),
        _row("C02", "Beneficiary Names, Addresses & Tax IDs", core=True, period="Current", extensions="xlsx, pdf", any_keywords="beneficiary information, beneficiary list, beneficiary names"),
        _row("D01", "Fiduciary, Attorney & Accounting Fees Paid", core=False, extensions="pdf, xlsx", any_keywords="fiduciary fees paid, trustee fees, accounting fees paid, legal fees paid, attorney fees paid, fee invoice"),
        _row("E01", "Cost Basis for Assets Sold During the Year", core=False, extensions="xlsx, pdf", any_keywords="cost basis schedule, basis of assets sold, date acquired and date sold, purchase price and sale price"),
        _row("F01", "Rental / Business Income & Expense Detail", core=False, extensions="xlsx, pdf", any_keywords="rental income and expenses, rent roll, schedule e detail, schedule c detail"),
    ],
    "990": [
        _row("A01", "Prior-Year Form 990 & State Filings", core=True, period=TY_PRIOR, required_keywords="return of organization exempt from income tax, under penalties of perjury"),
        _shared("A02", "trial_balance", core=True),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _row("C01", "Board of Directors List & Meeting Minutes", core=True, extensions="pdf, xlsx", any_keywords="board of directors list, list of directors, meeting minutes, board minutes"),
        _row("C02", "Officer & Key Employee Compensation Detail", core=True, extensions="xlsx", any_keywords="officer compensation detail, key employee compensation, compensation of officers"),
        _row("D01", "Contribution / Donor Detail - Schedule B Support", core=True, extensions="xlsx, csv", any_keywords="donor list, donor detail, contributions by donor, schedule b"),
        _row("D02", "Grants Made - Recipients & Amounts", core=False, extensions="xlsx, pdf", any_keywords="grants paid schedule, schedule of grants, grantee list, grantee"),
        _row("E01", "Program Service Accomplishment Descriptions", core=False, extensions="pdf, xlsx", any_keywords="program service accomplishment, program accomplishments, program description"),
        _row("F01", "Fundraising Event Revenue & Expense Detail", core=False, extensions="xlsx, pdf", any_keywords="fundraising event detail, special event revenue, event revenue and expense"),
        _shared("G01", "payroll_returns", core=False),
        _row("H01", "Unrelated Business Income Detail", core=False, extensions="xlsx, pdf", any_keywords="form 990-t, unrelated business income detail, ubti schedule"),
    ],
}



# ------------------------------------------------------------------ items ----


def _whole_number(spec: dict, key: str, default: int, minimum: int, label: str) -> int:
    """A wizard field as an int, refused with a sentence rather than a traceback."""
    raw = spec.get(key)
    if raw in (None, ""):
        return default
    try:
        number = int(raw)
    except (TypeError, ValueError):
        raise ManifestError(
            f"{label} for {spec.get('identifier', '?')} must be a whole number, got {raw!r}"
        ) from None
    if number < minimum:
        raise ManifestError(f"{label} for {spec.get('identifier', '?')} must be at least {minimum}")
    return number


def item_from_spec(spec: dict) -> RequestItem:
    """One catalog row (or one wizard row) as a validated :class:`RequestItem`.

    A row with no file types gets the manifest's safe default
    (``DEFAULT_EXTENSIONS``); ``*`` means ``ANY_EXTENSION``. A row with no content rule at all gets its
    own document name as the required keyword. Without a rule the request could never auto-file, and
    a custom request typed into the wizard in a hurry should still work;
    the manifest shows the rule, so it is a visible default, not a secret.
    """
    identifier = str(spec.get("identifier", "")).strip()
    document = str(spec.get("document", "")).strip()
    if not identifier or not document:
        raise ManifestError("every request needs an identifier and a document name")
    problem = identifier_problem(identifier)
    if problem:
        raise ManifestError(f"Identifier {identifier!r} {problem}")
    required = csv_tuple(spec.get("required_keywords"))
    any_keywords = csv_tuple(spec.get("any_keywords"))
    date_pattern = str(spec.get("date_pattern", "") or "")
    if not (required or any_keywords or date_pattern):
        required = (document,)
    return RequestItem(
        identifier=identifier,
        document=document,
        period=str(spec.get("period", "") or ""),
        expected_count=_whole_number(spec, "expected_count", DEFAULT_EXPECTED_COUNT, 1, COL_EXPECTED_COUNT),
        allowed_extensions=parse_extensions(
            spec.get("extensions") or spec.get("allowed_extensions")
        ),
        min_size_kb=_whole_number(spec, "min_size_kb", DEFAULT_MIN_SIZE_KB, 0, COL_MIN_SIZE_KB),
        required_keywords=required,
        any_keywords=any_keywords,
        date_pattern=date_pattern,
    )


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


#: What the wizard says about the year field and the two blank-able rules.
YEAR_NOTE = "Defaults to the most recently ended year; the checklist's periods follow it"
EXTENSION_DEFAULT_NOTE = "blank means " + ", ".join(DEFAULT_EXTENSIONS)
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
