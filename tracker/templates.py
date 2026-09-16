"""The per-form request catalog: one checklist per return type (component 11).

Every request list starts from here. Pick the return (1040, 1120, 1120-S,
1065, 1041, 990) and this module says which documents to ask for, what
they are called, how many to expect and — the part that makes the pipeline
run unattended — the keyword and date rules the router and scanner use to
recognise each one.

This is the **only** place the checklists live. The plain-CSV copies in
``templates/`` are generated from it (``python -m tracker.templates
export``) so an accountant can read them in Excel, and
``tests/test_templates.py`` fails if the committed CSVs drift from the
catalog. Edit the Python, regenerate the CSVs, commit both. There is no
second list to keep in step.

Every row carries a content rule. A request with no keyword has no way to
recognise its document, so it never auto-files (see :mod:`tracker.router`);
a template row like that would be a request the system can only ever park
for a person, which defeats the point of a template.
"""

from __future__ import annotations

import csv
from pathlib import Path

from tracker.manifest import ManifestError, RequestItem, identifier_problem

#: Where the generated CSV copies live, relative to the repository root.
TEMPLATES_DIRNAME = "templates"

#: Columns of the generated CSVs: the manifest's accountant columns, plus
#: whether the wizard pre-ticks the row.
CSV_COLUMNS = (
    "Identifier", "Document", "Period", "Expected Count", "Allowed Extensions",
    "Min Size KB", "Required Keywords", "Any Keywords", "Date Pattern", "Core",
)

# Tax form catalog — the wizard's first page. Selecting a form type tailors
# the request template below to that return.
FORM_TYPES = [
    {
        "id": "1040", "label": "Form 1040",
        "who": "Individual / joint return",
        "blurb": "Wages, investments, deductions, credits",
    },
    {
        "id": "1120", "label": "Form 1120",
        "who": "C corporation",
        "blurb": "Corporate income tax return",
    },
    {
        "id": "1120S", "label": "Form 1120-S",
        "who": "S corporation",
        "blurb": "Pass-through corporate return with K-1s",
    },
    {
        "id": "1065", "label": "Form 1065",
        "who": "Partnership / multi-member LLC",
        "blurb": "Partnership return with K-1s",
    },
    {
        "id": "1041", "label": "Form 1041",
        "who": "Estate or trust",
        "blurb": "Fiduciary income tax return",
    },
    {
        "id": "990", "label": "Form 990",
        "who": "Tax-exempt organization",
        "blurb": "Annual information return",
    },
]

# Per-form request templates shown on the wizard's second page. "core" items
# are pre-checked; the 1040 core items also match the staged sample documents,
# so an engagement created live on stage still plays through the whole
# drag-and-scan story.
FORM_TEMPLATES = {
    "1040": [
        {
            "identifier": "A01", "document": "W-2 Wage Statements - All Employers",
            "period": "TY2025", "expected_count": 2, "extensions": "pdf",
            "required_keywords": "W-2",
            "date_pattern": r"(?i)\b2025\b", "core": True,
        },
        {
            "identifier": "A02", "document": "1099-INT / 1099-DIV - Interest & Dividend Income",
            "period": "TY2025", "expected_count": 3, "extensions": "pdf, csv",
            "any_keywords": "1099, interest income, dividend", "core": True,
        },
        {
            "identifier": "B01", "document": "Prior-Year Federal & State Tax Returns",
            "period": "TY2024", "extensions": "pdf",
            "any_keywords": "form 1040, tax return", "core": True,
        },
        {
            "identifier": "C01", "document": "Mortgage Interest Statement - Form 1098",
            "period": "TY2025", "extensions": "pdf",
            "required_keywords": "1098", "core": True,
        },
        {
            "identifier": "D01", "document": "Charitable Contribution Receipts",
            "any_keywords": "charitable, contribution, donation",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": True,
        },
        {
            "identifier": "E01", "document": "1099-B / Brokerage Year-End Statements",
            "any_keywords": "1099-b, brokerage, proceeds from broker",
            "period": "TY2025", "extensions": "pdf, csv", "core": False,
        },
        {
            "identifier": "E02", "document": "1099-R Retirement Distributions",
            "any_keywords": "1099-r, retirement distribution",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "F01", "document": "Schedule K-1s Received",
            "any_keywords": "schedule k-1, k-1",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "G01", "document": "Property Tax Statements",
            "any_keywords": "property tax, assessor, parcel",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "H01", "document": "Estimated Tax Payment Records",
            "any_keywords": "estimated tax, 1040-es, 1120-w",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "I01", "document": "Form 1095-A - Marketplace Health Insurance",
            "any_keywords": "1095-a, marketplace",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "J01", "document": "Childcare Provider Statements - Name, EIN, Amounts",
            "any_keywords": "childcare, dependent care, provider",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "K01", "document": "IRA / HSA Contribution Statements - Form 5498",
            "any_keywords": "5498, ira contribution, hsa",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "L01", "document": "Tuition Statements - Form 1098-T",
            "any_keywords": "1098-t, tuition",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
    ],
    "1120": [
        {
            "identifier": "A01", "document": "Prior-Year Federal & State Corporate Returns",
            "period": "TY2024", "extensions": "pdf",
            "any_keywords": "form 1120, tax return", "core": True,
        },
        {
            "identifier": "A02", "document": "Trial Balance - Year-End",
            "any_keywords": "trial balance",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "A03", "document": "General Ledger Detail",
            "any_keywords": "general ledger",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "B01", "document": "Year-End Financial Statements",
            "any_keywords": "balance sheet, income statement, statement of operations, statement of activities",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": True,
        },
        {
            "identifier": "B02", "document": "December Bank Statements & Year-End Reconciliations",
            "any_keywords": "bank statement, ending balance, reconciliation",
            "period": "Dec 2025", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "C01", "document": "Fixed Asset Additions & Disposals Detail",
            "any_keywords": "fixed asset, asset detail, disposals",
            "period": "TY2025", "extensions": "xlsx", "core": True,
        },
        {
            "identifier": "C02", "document": "Depreciation Schedules",
            "any_keywords": "depreciation",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "D01", "document": "Loan Agreements & Year-End Balances",
            "any_keywords": "loan agreement, promissory note, amortization",
            "period": "As of 12/31/2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "E01", "document": "Payroll Tax Returns - Forms 941 & W-3",
            "any_keywords": "941, w-3, payroll tax",
            "period": "TY2025", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "E02", "document": "Officer Compensation Detail",
            "any_keywords": "officer compensation",
            "period": "TY2025", "extensions": "xlsx", "core": False,
        },
        {
            "identifier": "F01", "document": "Estimated Tax Payment Records",
            "any_keywords": "estimated tax, 1040-es, 1120-w",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "G01", "document": "Shareholder List & Ownership Changes",
            "any_keywords": "shareholder list, ownership",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "H01", "document": "State Apportionment Data - Sales, Payroll, Property by State",
            "any_keywords": "apportionment",
            "period": "TY2025", "extensions": "xlsx", "core": False,
        },
        {
            "identifier": "I01", "document": "Book-Tax Difference Support - Schedule M-1 Items",
            "any_keywords": "schedule m-1, book-tax",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
    ],
    "1120S": [
        {
            "identifier": "A01", "document": "Prior-Year Federal & State S-Corp Returns",
            "period": "TY2024", "extensions": "pdf",
            "any_keywords": "form 1120-s, form 1120s, tax return", "core": True,
        },
        {
            "identifier": "A02", "document": "Trial Balance - Year-End",
            "any_keywords": "trial balance",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "A03", "document": "General Ledger Detail",
            "any_keywords": "general ledger",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "B01", "document": "Year-End Financial Statements",
            "any_keywords": "balance sheet, income statement, statement of operations, statement of activities",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": True,
        },
        {
            "identifier": "B02", "document": "December Bank Statements & Year-End Reconciliations",
            "any_keywords": "bank statement, ending balance, reconciliation",
            "period": "Dec 2025", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "C01", "document": "Shareholder List with Ownership % & Changes",
            "any_keywords": "shareholder list, ownership",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": True,
        },
        {
            "identifier": "C02", "document": "Distributions by Shareholder",
            "any_keywords": "distributions",
            "period": "TY2025", "extensions": "xlsx", "core": True,
        },
        {
            "identifier": "C03", "document": "Shareholder Basis Schedules",
            "any_keywords": "stock basis, shareholder basis",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "D01", "document": "Officer / Shareholder W-2 Compensation Detail",
            "any_keywords": "officer compensation, shareholder w-2",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": True,
        },
        {
            "identifier": "D02", "document": "Health Insurance Premiums for >2% Shareholders",
            "any_keywords": "health insurance premium",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "E01", "document": "Payroll Tax Returns - Forms 941 & W-3",
            "any_keywords": "941, w-3, payroll tax",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "F01", "document": "Fixed Asset Additions & Disposals Detail",
            "any_keywords": "fixed asset, asset detail, disposals",
            "period": "TY2025", "extensions": "xlsx", "core": False,
        },
        {
            "identifier": "G01", "document": "Loan Agreements & Shareholder Loan Activity",
            "any_keywords": "loan agreement, promissory note, shareholder loan",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "H01", "document": "State Apportionment Data",
            "any_keywords": "apportionment",
            "period": "TY2025", "extensions": "xlsx", "core": False,
        },
    ],
    "1065": [
        {
            "identifier": "A01", "document": "Prior-Year Federal & State Partnership Returns",
            "period": "TY2024", "extensions": "pdf",
            "any_keywords": "form 1065, tax return", "core": True,
        },
        {
            "identifier": "A02", "document": "Partnership Agreement & Amendments",
            "any_keywords": "partnership agreement, operating agreement",
            "period": "Current", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "A03", "document": "Trial Balance - Year-End",
            "any_keywords": "trial balance",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "A04", "document": "General Ledger Detail",
            "any_keywords": "general ledger",
            "period": "TY2025", "extensions": "xlsx, csv", "core": False,
        },
        {
            "identifier": "B01", "document": "Year-End Financial Statements",
            "any_keywords": "balance sheet, income statement, statement of operations, statement of activities",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": True,
        },
        {
            "identifier": "B02", "document": "December Bank Statements & Year-End Reconciliations",
            "any_keywords": "bank statement, ending balance, reconciliation",
            "period": "Dec 2025", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "C01", "document": "Partner List with Ownership % & Changes",
            "any_keywords": "partner list, ownership",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": True,
        },
        {
            "identifier": "C02", "document": "Partner Capital Account Detail",
            "any_keywords": "capital account",
            "period": "TY2025", "extensions": "xlsx", "core": True,
        },
        {
            "identifier": "C03", "document": "Contributions & Distributions by Partner",
            "any_keywords": "contributions, distributions",
            "period": "TY2025", "extensions": "xlsx", "core": True,
        },
        {
            "identifier": "C04", "document": "Guaranteed Payment Detail",
            "any_keywords": "guaranteed payment",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "D01", "document": "Fixed Asset Additions & Disposals Detail",
            "any_keywords": "fixed asset, asset detail, disposals",
            "period": "TY2025", "extensions": "xlsx", "core": False,
        },
        {
            "identifier": "E01", "document": "Loan Agreements & Year-End Balances",
            "any_keywords": "loan agreement, promissory note, amortization",
            "period": "As of 12/31/2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "F01", "document": "Special Allocation Support - Section 704(b)",
            "any_keywords": "special allocation, 704",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "G01", "document": "State Apportionment Data",
            "any_keywords": "apportionment",
            "period": "TY2025", "extensions": "xlsx", "core": False,
        },
    ],
    "1041": [
        {
            "identifier": "A01", "document": "Trust Instrument / Will & Amendments",
            "any_keywords": "trust agreement, last will, codicil",
            "period": "Current", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "A02", "document": "IRS EIN Assignment Letter",
            "any_keywords": "cp 575, employer identification number",
            "period": "Current", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "A03", "document": "Prior-Year Fiduciary Returns",
            "period": "TY2024", "extensions": "pdf",
            "any_keywords": "form 1041, tax return", "core": True,
        },
        {
            "identifier": "B01", "document": "1099s for Trust / Estate Accounts",
            "period": "TY2025", "expected_count": 3, "extensions": "pdf, csv",
            "any_keywords": "1099", "core": True,
        },
        {
            "identifier": "B02", "document": "Brokerage Year-End Statements",
            "any_keywords": "1099-b, brokerage, realized gain",
            "period": "TY2025", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "C01", "document": "Distributions to Beneficiaries - Dates & Amounts",
            "any_keywords": "beneficiary, distribution",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": True,
        },
        {
            "identifier": "C02", "document": "Beneficiary Names, Addresses & Tax IDs",
            "any_keywords": "beneficiary",
            "period": "Current", "extensions": "xlsx, pdf", "core": True,
        },
        {
            "identifier": "D01", "document": "Fiduciary, Attorney & Accounting Fees Paid",
            "any_keywords": "fiduciary fee, attorney fee, accounting fee",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "E01", "document": "Cost Basis for Assets Sold During the Year",
            "any_keywords": "cost basis, acquired, sold",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "F01", "document": "Rental / Business Income & Expense Detail",
            "any_keywords": "rental income, schedule e, schedule c",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
    ],
    "990": [
        {
            "identifier": "A01", "document": "Prior-Year Form 990 & State Filings",
            "period": "TY2024", "extensions": "pdf",
            "any_keywords": "form 990, return", "core": True,
        },
        {
            "identifier": "A02", "document": "Trial Balance - Year-End",
            "any_keywords": "trial balance",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "B01", "document": "Year-End Financial Statements",
            "any_keywords": "balance sheet, income statement, statement of operations, statement of activities",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": True,
        },
        {
            "identifier": "B02", "document": "December Bank Statements & Reconciliations",
            "any_keywords": "bank statement, ending balance, reconciliation",
            "period": "Dec 2025", "extensions": "pdf", "core": True,
        },
        {
            "identifier": "C01", "document": "Board of Directors List & Meeting Minutes",
            "any_keywords": "board of directors, minutes",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": True,
        },
        {
            "identifier": "C02", "document": "Officer & Key Employee Compensation Detail",
            "any_keywords": "officer compensation, key employee",
            "period": "TY2025", "extensions": "xlsx", "core": True,
        },
        {
            "identifier": "D01", "document": "Contribution / Donor Detail - Schedule B Support",
            "any_keywords": "donor, contribution, schedule b",
            "period": "TY2025", "extensions": "xlsx, csv", "core": True,
        },
        {
            "identifier": "D02", "document": "Grants Made - Recipients & Amounts",
            "any_keywords": "grant, grantee",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "E01", "document": "Program Service Accomplishment Descriptions",
            "any_keywords": "program service",
            "period": "TY2025", "extensions": "pdf, xlsx", "core": False,
        },
        {
            "identifier": "F01", "document": "Fundraising Event Revenue & Expense Detail",
            "any_keywords": "fundraising",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
        {
            "identifier": "G01", "document": "Payroll Tax Returns - Forms 941 & W-3",
            "any_keywords": "941, w-3, payroll tax",
            "period": "TY2025", "extensions": "pdf", "core": False,
        },
        {
            "identifier": "H01", "document": "Unrelated Business Income Detail",
            "any_keywords": "unrelated business, 990-t",
            "period": "TY2025", "extensions": "xlsx, pdf", "core": False,
        },
    ],
}

DEMO_FORM = "1040"


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

    A row with no content rule at all gets its own document name as the
    required keyword. Without a rule the request could never auto-file, and
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
        expected_count=_whole_number(spec, "expected_count", 1, 1, "Expected count"),
        allowed_extensions=tuple(
            e.lower().lstrip(".")
            for e in _csv_field(spec.get("extensions") or spec.get("allowed_extensions"))
        ),
        min_size_kb=_whole_number(spec, "min_size_kb", 5, 0, "Minimum size"),
        required_keywords=required,
        any_keywords=any_keywords,
        date_pattern=date_pattern,
    )


def template_items(form: str, *, core_only: bool = False) -> list[RequestItem]:
    """The checklist for ``form`` as request items. Unknown form → ManifestError."""
    if form not in FORM_TEMPLATES:
        raise ManifestError(
            f"Unknown tax form type '{form}'; expected one of {', '.join(FORM_TEMPLATES)}"
        )
    return [
        item_from_spec(spec)
        for spec in FORM_TEMPLATES[form]
        if spec["core"] or not core_only
    ]


# -------------------------------------------------------------------- csv ----


def csv_name(form: str) -> str:
    """``form-1120s.csv`` for ``1120S``: the file an accountant opens."""
    return f"form-{form.lower()}.csv"


def csv_rows(form: str) -> list[list[str]]:
    """The CSV body for one form, one list per row, header excluded."""
    rows = []
    for spec in FORM_TEMPLATES[form]:
        item = item_from_spec(spec)
        rows.append([
            item.identifier,
            item.document,
            item.period,
            str(item.expected_count),
            ", ".join(item.allowed_extensions),
            str(item.min_size_kb),
            ", ".join(item.required_keywords),
            ", ".join(item.any_keywords),
            item.date_pattern,
            "yes" if spec["core"] else "",
        ])
    return rows


def render_csv(form: str) -> str:
    """The exact text of the generated CSV for ``form``."""
    import io

    out = io.StringIO()
    writer = csv.writer(out, lineterminator="\n")
    writer.writerow(CSV_COLUMNS)
    writer.writerows(csv_rows(form))
    return out.getvalue()


def export_csvs(directory: Path | str) -> list[Path]:
    """Write every form's CSV into ``directory``; returns the paths written."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    written = []
    for form in FORM_TEMPLATES:
        path = directory / csv_name(form)
        path.write_text(render_csv(form), encoding="utf-8", newline="")
        written.append(path)
    return written


def stale_csvs(directory: Path | str) -> list[str]:
    """Names of CSVs in ``directory`` that differ from the catalog (or are missing)."""
    directory = Path(directory)
    stale = []
    for form in FORM_TEMPLATES:
        path = directory / csv_name(form)
        if not path.exists() or path.read_text(encoding="utf-8") != render_csv(form):
            stale.append(path.name)
    return stale


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse
    import sys

    repo_root = Path(__file__).resolve().parent.parent
    parser = argparse.ArgumentParser(
        description="Export the form catalog to CSV, or check the committed CSVs match it"
    )
    parser.add_argument("command", choices=("export", "check"))
    parser.add_argument("--dir", default=str(repo_root / TEMPLATES_DIRNAME),
                        help="where the CSVs live (default: templates/ in the repo)")
    ns = parser.parse_args()

    if ns.command == "export":
        for path in export_csvs(ns.dir):
            print(f"wrote {path}")
        raise SystemExit(0)

    drift = stale_csvs(ns.dir)
    if drift:
        print(f"Stale: {', '.join(drift)} - run `python -m tracker.templates export`")
        sys.exit(1)
    print(f"{len(FORM_TEMPLATES)} CSV(s) in {ns.dir} match the catalog")
