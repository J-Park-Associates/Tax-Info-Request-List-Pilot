"""The shipped catalogs against the forms themselves.

Every row's keywords are the document's own title, or a phrase only it
carries - never a word another form prints about it. These are
reconstructions of what the IRS forms, bookkeeping exports and statements
actually say, routed the way an engagement routes them: through
create_template() and load_manifest(), so the Period-derived date check
is live. A misfiling here is the worst thing this system can do.
"""

from dataclasses import replace

import pytest

from tests.test_scanner import text_pdf
from tracker.manifest import create_template, load_manifest
from tracker.router import route_file
from tracker.scaffold import MANIFEST_FILENAME
from tracker.templates import template_items

NL = chr(10)


def shipped_rows(tmp_path, form):
    manifest = tmp_path / MANIFEST_FILENAME
    manifest.unlink(missing_ok=True)
    create_template(manifest, template_items(form, year=2025))
    return [replace(i, min_size_kb=0) for i in load_manifest(manifest)]


CASES = [
    # form, file name, the document's text (lines), where it belongs (None: parked)
    ("1040", "2024 return with Schedule A.pdf", [
        "Form 1040 2024 U.S. Individual Income Tax Return",
        "Department of the Treasury - Internal Revenue Service OMB No. 1545-0074 IRS Use Only - Do not write or staple in this space.",
        "For the year Jan. 1 - Dec. 31, 2024, or other tax year beginning , 2024, ending , 20 See separate instructions.",
        "Your first name and middle initial Last name Your social security number",
        "If joint return, spouse's first name and middle initial Last name Spouse's social security number",
        "Home address (number and street). If you have a P.O. box, see instructions. Apt. no.",
        "City, town, or post office. If you have a foreign address, also complete spaces below. State ZIP code",
        "Filing Status Single Married filing jointly Married filing separately (MFS) Head of household (HOH) Qualifying surviving spouse (QSS)",
        "1a Total amount from Form(s) W-2, box 1 (see instructions)",
        "26 2025 estimated tax payments and amount applied from 2024 return",
        "36 Amount applied to your 2025 estimated tax",
        "Schedule A 8a Home mortgage interest and points reported to you on Form 1098",
        "Attach Forms W-2G and 1099-R if tax was withheld",
        "1e Taxable dependent care benefits",
        "Sign Here Under penalties of perjury, I declare that I have examined this return and accompanying schedules",
    ], "B01"),
    ("1040", "1099-SA with instructions.pdf", [
        "Form 1099-SA Distributions From an HSA 2025",
        "Instructions for Recipient",
        "An HSA or Archer MSA distribution isn't taxable if you used it to pay qualified medical expenses",
        "direct payment to the medical service provider",
    ], None),
    ("1040", "1095-C with instructions.pdf", [
        "Form 1095-C Employer-Provided Health Insurance Offer and Coverage 2025",
        "Department of the Treasury Internal Revenue Service OMB No. 1545-2251 VOID CORRECTED",
        "Part I Employee 1 Name of employee (first name, middle initial, last name) 2 Social security number (SSN)",
        "3 Street address (including apartment no.) 4 City or town 5 State or province 6 Country and ZIP or foreign postal code",
        "Applicable Large Employer Member (Employer) 7 Name of employer 8 Employer identification number (EIN)",
        "9 Street address (including room or suite no.) 10 Contact telephone number 11 City or town 12 State or province",
        "Part II Employee Offer of Coverage Employee's Age on January 1 Plan Start Month (enter 2-digit number)",
        "14 Offer of Coverage (enter required code) 15 Employee Required Contribution (see instructions) 16 Section 4980H Safe Harbor",
        "Instructions for Recipient",
        "the Marketplace will report information about that coverage on Form 1095-A, Health Insurance Marketplace Statement",
    ], None),
    ("1040", "1099-Q.pdf", [
        "Form 1099-Q Payments From Qualified Education Programs 2025", "Box 5 Qualified tuition program",
    ], None),
    ("1040", "941.pdf", [
        "Form 941 Employer's QUARTERLY Federal Tax Return 2025", "Form 941-V, Payment Voucher",
    ], None),
    ("1040", "W-3.pdf", [
        "Form W-3 Transmittal of Wage and Tax Statements 2025", "Total number of Forms W-2",
        "b Employer identification number",
    ], None),
    ("1040", "W-2.pdf", [
        "Form W-2 Wage and Tax Statement 2025", "a Employee's social security number 123-45-6789",
        "1 Wages, tips, other compensation",
    ], "A01"),
    ("1040", "1099-NEC.pdf", [
        "Form 1099-NEC (Rev. January 2024) Nonemployee Compensation Copy B For Recipient",
        "PAYER'S name, street address, city or town, state or province, country, ZIP or foreign postal code, and telephone no.",
        "PAYER'S TIN RECIPIENT'S TIN RECIPIENT'S name Street address (including apt. no.) City or town, state or province, country, and ZIP or foreign postal code",
        "Account number (see instructions) 1 Nonemployee compensation 12,500.00 2 Payer made direct sales totaling $5,000 or more",
        "4 Federal income tax withheld 5 State tax withheld 6 State/Payer's state no. 7 State income OMB No. 1545-0116 For calendar year 2025",
        "This is important tax information and is being furnished to the IRS. If you are required to file a return, a negligence penalty or other sanction may be imposed on you",
        "Instructions for Recipient Recipient's taxpayer identification number (TIN). For your protection, this form may show only the last four digits of your TIN.",
        "Box 1. Shows nonemployee compensation. If the amount in this box is SE income, report it on Schedule C or F (Form 1040) if a sole proprietor.",
        "If you are not an employee but the amount in this box is not SE income, report it on Schedule 1 (Form 1040), line 8. See Form 1040-ES (or Form 1040-ES (NR)).",
        "report on your income tax return",
        "Form 1099-NEC (Rev. 1-2024) www.irs.gov/Form1099NEC",
    ], None),
    ("1040", "1040-ES voucher.pdf", ["2025 Estimated Tax Payment Voucher 1", "Form 1040-ES"], "H01"),
    ("1120S", "1099-INT.pdf", [
        "Form 1099-INT Interest Income (Rev. January 2024) 2025",
        "report this interest on your income tax return",
    ], None),
    ("1120S", "2024 1120-S.pdf", [
        "Form 1120-S U.S. Income Tax Return for an S Corporation 2024",
        "Sign Here Under penalties of perjury, I declare that I have examined this return",
    ], "A01"),
    ("1120", "2024 1120.pdf", [
        "Form 1120 U.S. Corporation Income Tax Return 2024", "12 Compensation of officers",
        "Schedule M-1 Reconciliation of Income", "Sign Here Under penalties of perjury, I declare",
    ], "A01"),
    ("1120", "K-1 1065.pdf", ["Schedule K-1 (Form 1065) 2025", "17A Post-1986 depreciation adjustment"], None),
    ("1120", "P&L.pdf", [
        "Profit and Loss January - December 2025", "Officer Compensation 120,000.00", "Depreciation 6,120.00",
    ], "B01"),
    ("1120", "brokerage.pdf", [
        "Year-end account statement 2025", "Statement period 12/01/2025 - 12/31/2025",
        "Ending balance 40,000", "brokerage",
    ], None),
    ("1120S", "trial balance.pdf", [
        "Trial Balance As of December 31, 2025", "Payroll Liabilities:Federal Taxes (941/944) 1,200.00",
    ], "A02"),
    ("1065", "K-1 1041.pdf", ["Schedule K-1 (Form 1041) 2025 Beneficiary's Share", "9C Amortization 300"], None),
    ("1065", "nonprofit FS.pdf", ["Statements of Financial Position 2025", "Total liabilities 20,704"], "B01"),
    ("1065", "operating agreement.pdf", [
        "Operating Agreement of Smith Holdings LLC", "allocations under Treas. Reg. 1.704-1(b)",
    ], "A02"),
    ("1041", "941.pdf", [
        "Form 941 Employer's QUARTERLY Federal Tax Return 2025", "Employer identification number 12-3456789",
    ], None),
    ("1041", "CP 575.pdf", ["Notice CP 575 A", "We assigned you Employer Identification Number 12-3456789"], "A02"),
    ("1041", "trial balance.pdf", ["Trial Balance 2025", "Cost of Goods Sold 5,000", "Date Acquired"], None),
    ("1041", "1099-B.pdf", [
        "Form 1099-B Proceeds From Broker and Barter Exchange Transactions 2025",
        "Date acquired 01/02/2024", "Date sold 03/04/2025",
    ], "B01"),
    ("990", "bank Dec 2024.pdf", ["Checking Account Statement December 2024", "Return Item Chargeback 25.00"], None),
    ("990", "2024 990.pdf", [
        "Form 990 Return of Organization Exempt From Income Tax 2024",
        "Part XI Reconciliation of Net Assets", "Board of Directors",
        "Sign Here Under penalties of perjury, I declare that I have examined this return",
    ], "A01"),
    ("990", "Nov 2025 bank.pdf", [
        "Checking Account Statement", "Statement period 11/01/2025 - 11/30/2025", "Deposits and other credits 4,000.00",
    ], None),
    ("990", "Dec 2025 bank.pdf", [
        "Checking Account Statement", "Statement period 12/01/2025 - 12/31/2025", "Deposits and other credits 4,000.00",
    ], "B02"),
    # Round six: the W-2 as the IRS lays it out (title at the foot), documents
    # that mention forms they are not, and returns with their schedules.
    ("1040", "W-2 IRS layout.pdf", [
        "a Employee's social security number 123-45-6789 OMB No. 1545-0008 Safe, accurate, FAST! Use",
        "b Employer identification number (EIN) 12-3456789 1 Wages, tips, other compensation 84,500.00 2 Federal income tax withheld 11,240.00",
        "c Employer's name, address, and ZIP code 3 Social security wages 84,500.00 4 Social security tax withheld 5,239.00",
        "d Control number 5 Medicare wages and tips 84,500.00 6 Medicare tax withheld 1,225.25",
        "e Employee's first name and initial Last name Suff. 7 Social security tips 8 Allocated tips",
        "f Employee's address and ZIP code 10 Dependent care benefits 11 Nonqualified plans 12a See instructions for box 12",
        "13 Statutory employee Retirement plan Third-party sick pay 14 Other",
        "15 State Employer's state ID number 16 State wages, tips, etc. 17 State income tax 18 Local wages, tips, etc. 19 Local income tax 20 Locality name",
        "Form W-2 Wage and Tax Statement 2025 Copy B To Be Filed With Employee's FEDERAL Tax Return.",
        "Department of the Treasury Internal Revenue Service",
        "Notice to Employee Do you have to file? Refer to the Form 1040 instructions to determine if you are required to file a tax return.",
        "Form W-2 Wage and Tax Statement 2025 Copy 2 To Be Filed With Employee's State, City, or Local Income Tax Return.",
    ], "A01"),
    ("1041", "K-1 1065 in a trust.pdf", [
        "Schedule K-1 (Form 1065) 2025 Partner's Share of Income, Deductions, Credits, etc.",
        "1 Ordinary business income (loss) 2 Net rental real estate income (loss) 3 Other net rental income (loss)",
        "Schedule K-1 (Form 1065) 2025 See separate instructions. Schedule E, line 28",
    ], None),
    ("1120", "CP 575 in a corporation.pdf", [
        "IRS Department of the Treasury Internal Revenue Service Cincinnati OH 45999-0023",
        "Date of this notice: 03-14-2025 Employer Identification Number: 12-3456789 Form: SS-4 Number of this notice: CP 575 A",
        "For assistance you may call us at: 1-800-829-4933 IF YOU WRITE, ATTACH THE STUB AT THE END OF THIS NOTICE.",
        "SMITH HOLDINGS INC 123 MAIN ST ANYTOWN CA 90000",
        "WE ASSIGNED YOU AN EMPLOYER IDENTIFICATION NUMBER",
        "Thank you for applying for an Employer Identification Number (EIN). We assigned you EIN 12-3456789. This EIN will identify you,",
        "your business accounts, tax returns, and documents, even if you have no employees. Please keep this notice in your permanent records.",
        "When filing tax documents, payments, and related correspondence, it is very important that you use your EIN and complete name",
        "and address exactly as shown above. Any variation may cause a delay in processing, result in incorrect information in your account,",
        "or even cause you to be assigned more than one EIN.",
        "Based on the information you submitted, you must file the following form(s) by the date(s) shown.",
        "Form 941 04/30/2025", "Form 940 01/31/2026", "Form 1120 03/15/2026",
    ], None),
    ("1040", "CP14 notice.pdf", [
        "Notice CP14 Tax year 2025 Amount due", "Payment options",
        "IRS Direct Pay Electronic Federal Tax Payment System (EFTPS)",
    ], None),
    ("1040", "4868 extension.pdf", [
        "Form 4868 Application for Automatic Extension of Time To File U.S. Individual Income Tax Return 2024",
        "Your social security number",
    ], None),
    ("1040", "closing disclosure.pdf", [
        "Closing Disclosure This form is a statement of final loan terms and closing costs. 2025",
        "F. Prepaids Homeowner's Insurance Premium Property Taxes ( 6 mo.) 1,200.00", "G. Initial Escrow Payment at Closing Property Taxes",
    ], None),
    ("1040", "2024 1040 with schedules.pdf", [
        "Form 1040 2024 U.S. Individual Income Tax Return Department of the Treasury Internal Revenue Service OMB No. 1545-0074",
        "Filing Status Single Married filing jointly Married filing separately Head of household Qualifying surviving spouse",
        "1a Total amount from Form(s) W-2, box 1 26 2025 estimated tax payments 36 Amount applied to your 2025 estimated tax",
        "Form 1040 (2024) Page 2 Schedule A Itemized Deductions 5c State and local personal property taxes",
        "8a Home mortgage interest and points reported to you on Form 1098 Schedule B substitute statement from a brokerage firm",
        "Schedule E Passive income from Schedule K-1 Form 8962 Monthly enrollment premiums Form 8283 Noncash Charitable Contributions",
        "Sign Here Under penalties of perjury, I declare that I have examined this return and accompanying schedules",
        "Form 1040 (2024)",
    ], "B01"),
    ("1120", "2024 1120 with schedules.pdf", [
        "Form 1120 U.S. Corporation Income Tax Return 2024 Department of the Treasury Internal Revenue Service",
        "20 Depreciation from Form 4562 not claimed on Form 1125-A 37 Credited to 2025 estimated tax",
        "Schedule L Balance Sheets per Books Schedule M-1 Reconciliation of Income (Loss) per Books With Income per Return",
        "Sign Here Under penalties of perjury, I declare that I have examined this return",
        "Form 1120 (2024)",
    ], "A01"),
    # Round eight: the firm's own paperwork, and another entity's return, are not the prior-year return.
    ("1040", "organizer.pdf", [
        "2025 Individual Income Tax Organizer", "Filing Status Single Married filing jointly",
        "Please provide your 2024 amounts where asked. Attach your 2024 Form 1040.",
    ], None),
    ("1040", "engagement letter.pdf", [
        "Engagement Letter: we will prepare your 2025 Form 1040, U.S. Individual Income Tax Return.",
        "Filing status will be determined from the information you provide. Prior-year (2024) returns are not included.",
    ], None),
    ("1040", "2024 1120-S dropped by the owner.pdf", [
        "Form 1120-S U.S. Income Tax Return for an S Corporation 2024",
        "Schedule K 12a Cash charitable contributions", "27 Credited to 2025 estimated tax",
        "Sign Here Under penalties of perjury, I declare that I have examined this return",
    ], None),
    ("1120", "QuickBooks trial balance.pdf", [
        "Trial Balance As of December 31, 2025", "Checking Account 12,000.00 Savings Account 30,000.00",
        "Accumulated Depreciation -4,000.00 Shareholder Distributions 10,000.00",
    ], "A02"),
    # Round nine. A form number in the title counts only when the title
    # names the form in its own right: the IRS's "Attention" page, a
    # scanner's or an email's cover, an organizer's lines and a bank's
    # letter all quote forms they are not.
    ("1041", "1098-T behind the Attention page.pdf", [
        "Attention:", "Which Revision To Use for Which Year. We issue information returns up to a year in advance of when issuers will first file them.",
        "For all forms that we do not issue annually (such as Form 1099-NEC), we issue the revision to use for the next calendar year.",
        "For example, we issued an April 2025 revision of Form 1099-NEC, Nonemployee Compensation, to use first to report amounts for calendar year 2025.",
        "", "Form 1098-T Tuition Statement 2025", "OMB No. 1545-1574", "FILER'S name State University",
        "1 Payments received for qualified tuition and related expenses 12,000.00", "Form 1098-T (2025)",
    ], None),
    ("1041", "scanner cover then W-2.pdf", [
        "Scanned by CamScanner", "Scan date 02/01/2026 Pages 2", "Attached: Form 1099-INT, Form 1098 and W-2 for 2025 tax prep", "",
        "a Employee's social security number 123-45-6789 OMB No. 1545-0008",
        "Form W-2 Wage and Tax Statement 2025 Copy B To Be Filed With Employee's FEDERAL Tax Return.",
    ], None),
    ("1041", "email print then 5498.pdf", [
        "From: Fidelity <noreply@fidelity.com>", "Subject: Your 2025 Form 1099-R is ready", "Date: January 20, 2026", "",
        "Form 5498 IRA Contribution Information 2025", "OMB No. 1545-0747", "TRUSTEE'S or ISSUER'S name",
        "1 IRA contributions (other than amounts in boxes 2-4, 8-10, 13a, and 14a) 7,000.00", "Form 5498 (2025)",
    ], None),
    ("1040", "email print then 5498.pdf", [
        "From: Fidelity <noreply@fidelity.com>", "Subject: Your 2025 Form 1099-R is ready", "Date: January 20, 2026", "",
        "Form 5498 IRA Contribution Information 2025", "OMB No. 1545-0747", "TRUSTEE'S or ISSUER'S name",
        "1 IRA contributions (other than amounts in boxes 2-4, 8-10, 13a, and 14a) 7,000.00", "Form 5498 (2025)",
    ], "K01"),
    ("1040", "fax cover then 1099-R.pdf", [
        "FAX COVER SHEET", "To: J Park & Associates From: Jane Smith Date: 02/01/2026 Pages: 3",
        "Re: Forms 1099-INT and 1099-DIV, plus a 1098 - for my 2025 return", "",
        "Form 1099-R Distributions From Pensions, Annuities, Retirement or Profit-Sharing Plans, IRAs, Insurance Contracts, etc. 2025",
        "OMB No. 1545-0119", "1 Gross distribution 20,000.00", "Instructions for Recipient", "Form 1099-R (2025)",
    ], "E02"),
    ("1040", "bank annual summary.pdf", [
        "First National Bank", "Annual Account Summary January 1, 2025 - December 31, 2025",
        "Total deposits and other credits 48,000.00", "Total interest paid 12.50 (reported on Form 1099-INT)",
    ], None),
    ("1041", "bank annual summary.pdf", [
        "First National Bank", "Annual Account Summary January 1, 2025 - December 31, 2025",
        "Total interest paid 12.50 (reported on Form 1099-INT)",
    ], None),
    ("1040", "organizer with every line.pdf", [
        "2025 Individual Income Tax Organizer", "Please complete and return with your documents",
        "Wages: attach all Forms W-2", "Interest and dividends: attach Forms 1099-INT and 1099-DIV", "Mortgage interest: attach Form 1098",
        "Retirement: attach Forms 1099-R", "Filing Status: Single Married filing jointly", "Charitable contributions: list donations and attach receipts",
        "Child care provider name, EIN, amount paid", "Estimated tax payments made for 2025: Q1 Q2 Q3 Q4", "Tuition: attach Form 1098-T", "Property tax paid",
    ], None),
    ("1041", "organizer with every line.pdf", [
        "2025 Individual Income Tax Organizer", "Interest and dividends: attach Forms 1099-INT and 1099-DIV",
    ], None),
    # A keyword's words are on one line, or wrap as a heading from the start of one.
    ("1041", "K-1 with its footer under box 19.pdf", [
        "Schedule K-1 (Form 1065) 2025 Department of the Treasury Internal Revenue Service", "For calendar year 2025",
        "Partner's Share of Income, Deductions, Credits, etc. See separate instructions.",
        "1 Ordinary business income (loss) 12,000", "19 Distributions", "Schedule K-1 (Form 1065) 2025",
    ], None),
    ("1120S", "K-1 with its footer under box 16.pdf", [
        "Schedule K-1 (Form 1120-S) 2025 Department of the Treasury Internal Revenue Service",
        "Shareholder's Share of Income, Deductions, Credits, etc. See separate instructions.",
        "1 Ordinary business income (loss) 12,000", "16 Items affecting shareholder basis", "Schedule K-1 (Form 1120-S) 2025",
    ], None),
    ("1120", "QuickBooks balance sheet.pdf", [
        "Smith Holdings LLC", "Balance Sheet", "As of December 31, 2025", "ASSETS", "Checking 12,000.00", "Fixed Assets 60,000.00",
    ], "B01"),
    # A return's own lines, and a bookkeeping export's account names, are not another row's document.
    ("1040", "QuickBooks general ledger.pdf", [
        "Smith Holdings LLC", "General Ledger", "January - December 2025",
        "Charitable Contributions 12/15/2025 Check 1042 Red Cross donation 500.00",
    ], None),
    ("1040", "QuickBooks trial balance.pdf", [
        "Smith Holdings LLC", "Trial Balance", "As of December 31, 2025", "Shareholder Distributions 10,000.00", "Donation Expense 500.00",
    ], None),
    ("1040", "donation receipt.pdf", [
        "Red Cross", "Thank you for your donation of $500.00 received December 15, 2025",
        "No goods or services were provided in exchange for this contribution.",
    ], "D01"),
    ("1120", "cap table.pdf", ["Smith Holdings Inc. Cap Table as of December 31, 2025", "Shareholder Shares Percent", "J Smith 600 60%"], "G01"),
    ("1040", "childcare statement.pdf", [
        "Little Stars Daycare", "2025 Child Care Statement", "Provider EIN 12-3456789", "Total paid for Emma Smith 8,400.00",
    ], "J01"),
    ("1040", "1099-DIV.pdf", [
        "Form 1099-DIV Dividends and Distributions 2025", "OMB No. 1545-0110", "1a Total ordinary dividends 300.00", "Form 1099-DIV (Rev. January 2024)",
    ], "A02"),
]


@pytest.mark.parametrize("form, name, lines, expected", CASES, ids=[c[1] for c in CASES])
def test_every_shipped_catalog_files_real_forms_where_they_belong(tmp_path, form, name, lines, expected):
    items = shipped_rows(tmp_path, form)
    routing = route_file(text_pdf(tmp_path / name, NL.join(lines)), items)
    assert routing.identifier == expected, (name, routing.reason)
