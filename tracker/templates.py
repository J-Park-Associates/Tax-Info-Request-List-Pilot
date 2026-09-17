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
    DEFAULT_EXTENSIONS,
    DEFAULT_EXPECTED_COUNT,
    DEFAULT_MIN_SIZE_KB,
    ManifestError,
    RequestItem,
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
                          extensions="xlsx, csv"),
    "general_ledger": dict(document="General Ledger Detail", any_keywords="general ledger",
                           extensions="xlsx, csv"),
    "financial_statements": dict(
        document="Year-End Financial Statements",
        any_keywords="balance sheet, income statement, statement of operations, statement of activities",
        extensions="pdf, xlsx"),
    "december_bank": dict(document="December Bank Statements & Year-End Reconciliations",
                          any_keywords="bank statement, ending balance, reconciliation", period=DEC),
    "payroll_returns": dict(document="Payroll Tax Returns - Forms 941 & W-3",
                            any_keywords="941, w-3, payroll tax"),
    "estimated_tax": dict(document="Estimated Tax Payment Records",
                          any_keywords="estimated tax, 1040-es, 1120-w", extensions="pdf, xlsx"),
    "fixed_assets": dict(document="Fixed Asset Additions & Disposals Detail",
                         any_keywords="fixed asset, asset detail, disposals", extensions="xlsx"),
    "loans": dict(document="Loan Agreements & Year-End Balances",
                  any_keywords="loan agreement, promissory note, amortization", period=AS_OF_YEAR_END),
    "apportionment": dict(document="State Apportionment Data - Sales, Payroll, Property by State",
                          any_keywords="apportionment", extensions="xlsx"),
    "officer_comp": dict(document="Officer Compensation Detail", any_keywords="officer compensation",
                         extensions="xlsx"),
}


def _shared(identifier: str, key: str, *, core: bool) -> dict:
    return _row(identifier, core=core, **SHARED[key])


# Per-form request templates shown on the wizard's second page. "core" items
# are pre-checked.
FORM_TEMPLATES = {
    "1040": [
        _row("A01", "W-2 Wage Statements - All Employers", core=True, required_keywords="W-2", expected_count=2),
        _row("A02", "1099-INT / 1099-DIV - Interest & Dividend Income", core=True, extensions="pdf, csv", any_keywords="1099, interest income, dividend", expected_count=3),
        _row("B01", "Prior-Year Federal & State Tax Returns", core=True, period=TY_PRIOR, any_keywords="form 1040, tax return"),
        _row("C01", "Mortgage Interest Statement - Form 1098", core=True, required_keywords="1098"),
        _row("D01", "Charitable Contribution Receipts", core=True, extensions="pdf, xlsx", any_keywords="charitable, contribution, donation"),
        _row("E01", "1099-B / Brokerage Year-End Statements", core=False, extensions="pdf, csv", any_keywords="1099-b, brokerage, proceeds from broker"),
        _row("E02", "1099-R Retirement Distributions", core=False, any_keywords="1099-r, retirement distribution"),
        _row("F01", "Schedule K-1s Received", core=False, any_keywords="schedule k-1, k-1"),
        _row("G01", "Property Tax Statements", core=False, any_keywords="property tax, assessor, parcel"),
        _shared("H01", "estimated_tax", core=False),
        _row("I01", "Form 1095-A - Marketplace Health Insurance", core=False, any_keywords="1095-a, marketplace"),
        _row("J01", "Childcare Provider Statements - Name, EIN, Amounts", core=False, extensions="pdf, xlsx", any_keywords="childcare, dependent care, provider"),
        _row("K01", "IRA / HSA Contribution Statements - Form 5498", core=False, any_keywords="5498, ira contribution, hsa"),
        _row("L01", "Tuition Statements - Form 1098-T", core=False, any_keywords="1098-t, tuition"),
    ],
    "1120": [
        _row("A01", "Prior-Year Federal & State Corporate Returns", core=True, period=TY_PRIOR, any_keywords="form 1120, tax return"),
        _shared("A02", "trial_balance", core=True),
        _shared("A03", "general_ledger", core=True),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _shared("C01", "fixed_assets", core=True),
        _row("C02", "Depreciation Schedules", core=False, extensions="xlsx, pdf", any_keywords="depreciation"),
        _shared("D01", "loans", core=False),
        _shared("E01", "payroll_returns", core=True),
        _shared("E02", "officer_comp", core=False),
        _shared("F01", "estimated_tax", core=False),
        _row("G01", "Shareholder List & Ownership Changes", core=False, extensions="xlsx, pdf", any_keywords="shareholder list, ownership"),
        _shared("H01", "apportionment", core=False),
        _row("I01", "Book-Tax Difference Support - Schedule M-1 Items", core=False, extensions="xlsx, pdf", any_keywords="schedule m-1, book-tax"),
    ],
    "1120S": [
        _row("A01", "Prior-Year Federal & State S-Corp Returns", core=True, period=TY_PRIOR, any_keywords="form 1120-s, form 1120s, tax return"),
        _shared("A02", "trial_balance", core=True),
        _shared("A03", "general_ledger", core=True),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _row("C01", "Shareholder List with Ownership % & Changes", core=True, extensions="xlsx, pdf", any_keywords="shareholder list, ownership"),
        _row("C02", "Distributions by Shareholder", core=True, extensions="xlsx", any_keywords="distributions"),
        _row("C03", "Shareholder Basis Schedules", core=False, extensions="xlsx, pdf", any_keywords="stock basis, shareholder basis"),
        _row("D01", "Officer / Shareholder W-2 Compensation Detail", core=True, extensions="xlsx, pdf", any_keywords="officer compensation, shareholder w-2"),
        _row("D02", "Health Insurance Premiums for >2% Shareholders", core=False, extensions="pdf, xlsx", any_keywords="health insurance premium"),
        _shared("E01", "payroll_returns", core=False),
        _shared("F01", "fixed_assets", core=False),
        _row("G01", "Loan Agreements & Shareholder Loan Activity", core=False, extensions="pdf, xlsx", any_keywords="loan agreement, promissory note, shareholder loan"),
        _shared("H01", "apportionment", core=False),
    ],
    "1065": [
        _row("A01", "Prior-Year Federal & State Partnership Returns", core=True, period=TY_PRIOR, any_keywords="form 1065, tax return"),
        _row("A02", "Partnership Agreement & Amendments", core=True, period="Current", any_keywords="partnership agreement, operating agreement"),
        _shared("A03", "trial_balance", core=True),
        _shared("A04", "general_ledger", core=False),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _row("C01", "Partner List with Ownership % & Changes", core=True, extensions="xlsx, pdf", any_keywords="partner list, ownership"),
        _row("C02", "Partner Capital Account Detail", core=True, extensions="xlsx", any_keywords="capital account"),
        _row("C03", "Contributions & Distributions by Partner", core=True, extensions="xlsx", any_keywords="contributions, distributions"),
        _row("C04", "Guaranteed Payment Detail", core=False, extensions="xlsx, pdf", any_keywords="guaranteed payment"),
        _shared("D01", "fixed_assets", core=False),
        _shared("E01", "loans", core=False),
        _row("F01", "Special Allocation Support - Section 704(b)", core=False, extensions="xlsx, pdf", any_keywords="special allocation, 704"),
        _shared("G01", "apportionment", core=False),
    ],
    "1041": [
        _row("A01", "Trust Instrument / Will & Amendments", core=True, period="Current", any_keywords="trust agreement, last will, codicil"),
        _row("A02", "IRS EIN Assignment Letter", core=False, period="Current", any_keywords="cp 575, employer identification number"),
        _row("A03", "Prior-Year Fiduciary Returns", core=True, period=TY_PRIOR, any_keywords="form 1041, tax return"),
        _row("B01", "1099s for Trust / Estate Accounts", core=True, extensions="pdf, csv", any_keywords="1099", expected_count=3),
        _row("B02", "Brokerage Year-End Statements", core=True, any_keywords="1099-b, brokerage, realized gain"),
        _row("C01", "Distributions to Beneficiaries - Dates & Amounts", core=True, extensions="xlsx, pdf", any_keywords="beneficiary, distribution"),
        _row("C02", "Beneficiary Names, Addresses & Tax IDs", core=True, period="Current", extensions="xlsx, pdf", any_keywords="beneficiary"),
        _row("D01", "Fiduciary, Attorney & Accounting Fees Paid", core=False, extensions="pdf, xlsx", any_keywords="fiduciary fee, attorney fee, accounting fee"),
        _row("E01", "Cost Basis for Assets Sold During the Year", core=False, extensions="xlsx, pdf", any_keywords="cost basis, acquired, sold"),
        _row("F01", "Rental / Business Income & Expense Detail", core=False, extensions="xlsx, pdf", any_keywords="rental income, schedule e, schedule c"),
    ],
    "990": [
        _row("A01", "Prior-Year Form 990 & State Filings", core=True, period=TY_PRIOR, any_keywords="form 990, return"),
        _shared("A02", "trial_balance", core=True),
        _shared("B01", "financial_statements", core=True),
        _shared("B02", "december_bank", core=True),
        _row("C01", "Board of Directors List & Meeting Minutes", core=True, extensions="pdf, xlsx", any_keywords="board of directors, minutes"),
        _row("C02", "Officer & Key Employee Compensation Detail", core=True, extensions="xlsx", any_keywords="officer compensation, key employee"),
        _row("D01", "Contribution / Donor Detail - Schedule B Support", core=True, extensions="xlsx, csv", any_keywords="donor, contribution, schedule b"),
        _row("D02", "Grants Made - Recipients & Amounts", core=False, extensions="xlsx, pdf", any_keywords="grant, grantee"),
        _row("E01", "Program Service Accomplishment Descriptions", core=False, extensions="pdf, xlsx", any_keywords="program service"),
        _row("F01", "Fundraising Event Revenue & Expense Detail", core=False, extensions="xlsx, pdf", any_keywords="fundraising"),
        _shared("G01", "payroll_returns", core=False),
        _row("H01", "Unrelated Business Income Detail", core=False, extensions="xlsx, pdf", any_keywords="unrelated business, 990-t"),
    ],
}



# ------------------------------------------------------------------ items ----


def _csv_field(value) -> tuple[str, ...]:
    if isinstance(value, (list, tuple)):
        return tuple(str(v).strip() for v in value if str(v).strip())
    return tuple(p.strip() for p in str(value or "").split(",") if p.strip())


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
    required = _csv_field(spec.get("required_keywords"))
    any_keywords = _csv_field(spec.get("any_keywords"))
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
