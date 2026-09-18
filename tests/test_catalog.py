"""The shipped catalogs against the forms themselves.

Every row's keywords are the document's own title, or a phrase only it
carries - never a word another form prints about it. These are
reconstructions of what the IRS forms, bookkeeping exports and statements
actually say, routed the way an engagement routes them: through
create_template() and load_manifest(), so the Period-derived date check
is live. A misfiling here is the worst thing this system can do.

Two kinds of case, because there are two kinds of document. A page of
text is printed to a PDF and read back (``CASES``); a schedule a client
keeps in Excel is written to a real workbook and read as a sheet
(``XLSX_CASES``), where a row is a line and its cells are set apart by a
tab. Half of every catalog asks for a workbook, and typing one as prose
would prove the wrong reading.
"""

from dataclasses import replace

import pytest

from tests.samples import sheet_xlsx
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


# One block per decision (docs/ROADMAP.md), oldest first. CASES, below,
# tags every case with its decision, so a rule change runs its whole
# history by name before it is trusted: ``python -m pytest -k d67`` is
# decision 67's cases, ``-k "d66 or d67 or d68"`` the three rounds that
# kept reopening one another.
_DECISION_62 = [
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
]
_DECISION_63 = [
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
]
_DECISION_65 = [
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
]
_DECISION_66 = [
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
_DECISION_67 = [
    # Round ten. A form told to the reader is a reference whatever follows it; a title
    # that lists three forms names none; a savings plan's contribution statement is not
    # a charitable receipt; the childcare row knows the provider's statement; the
    # 1040-ES booklet's prose is not a voucher and a paid voucher says what it is.
    ("1040", "organizer homeowners section.pdf", [
        "2025 Individual Income Tax Organizer - Homeowners Section",
        "Mortgage interest paid on your residence: attach Form 1098 (2025)", "Property taxes paid: attach your bill",
    ], None),
    ("1040", "escrow letter.pdf", [
        "Wells Fargo Home Mortgage", "Annual Escrow Account Disclosure Statement",
        "For your mortgage interest deduction, see Form 1098 for 2025 mailed separately.",
    ], None),
    ("1040", "firm transmittal.pdf", [
        "J Park & Associates", "Enclosed please find: Form W-2 2025, Form 1098 2025, Form 1099-INT 2025",
    ], None),
    ("1040", "organizer checklist.pdf", [
        "2025 Individual Income Tax Organizer", "Income Documents Checklist", "Form W-2 - Wage and Tax Statement",
        "Form 1098 - Mortgage Interest Statement", "Form 1099-INT - Interest Income", "Form 1099-DIV - Dividends and Distributions",
    ], None),
    ("1040", "IRA contribution statement.pdf", [
        "Vanguard", "2025 Traditional IRA Contribution Statement", "Contributions for tax year 2025: 7,000.00",
        "Fair market value as of December 31, 2025",
    ], None),
    ("1040", "529 contribution statement.pdf", ["ScholarShare 529", "2025 Contribution Statement", "Total contributions 5,000.00"], None),
    ("1040", "childcare provider statement.pdf", [
        "Little Stars Daycare", "Child Care Provider Statement for 2025", "Provider EIN 12-3456789", "Total paid for care of Emma Smith: 9,600.00",
    ], "J01"),
    ("1040", "giving summary.pdf", ["Fidelity Charitable", "2025 Giving Summary", "Grants recommended 2,500.00"], "D01"),
    ("1040", "goodwill receipt.pdf", ["Goodwill Industries", "Tax Receipt for Donated Goods", "Date 11/02/2025", "3 bags of clothing"], "D01"),
    ("1040", "acknowledgment letter.pdf", [
        "Red Cross", "We gratefully acknowledge your charitable contribution of $500 received on December 15, 2025.",
    ], "D01"),
    ("1040", "paid voucher stub.pdf", [
        "Form 1040-ES", "2025 Estimated Tax Payment Voucher 4", "Amount of estimated tax you are paying by check or money order 2,500.00",
    ], "H01"),
    ("1040", "1040-ES instructions only.pdf", [
        "2025 Form 1040-ES Estimated Tax for Individuals", "Purpose of This Package",
        "make a copy of one of your unused estimated tax payment vouchers, fill it in, and mail it with your payment",
    ], None),
]
_DECISION_68 = [
    # Round eleven. A broker's consolidated 1099 is one family's document: the
    # interest-and-dividend one files, the one with a 1099-B is the rows' own
    # tie. A receipt row keys on receipt wording, not on a pledge, a thank-you
    # or the firm's own letter; a church's giving statement is a receipt. A
    # state voucher is an estimated tax record; an FSA statement is not a
    # childcare provider's statement.
    ("1040", "Vanguard consolidated 1099.pdf", [
        "Vanguard Brokerage Services", "2025 Consolidated Form 1099 - Account 8812-4455",
        "Form 1099-INT   Interest Income", "Form 1099-DIV   Dividends and Distributions",
        "1 Interest income 1,240.00", "1a Total ordinary dividends 3,400.00",
    ], "A02"),
    ("1041", "Vanguard consolidated 1099.pdf", [
        "Vanguard Brokerage Services", "2025 Consolidated Form 1099 - Account 8812-4455",
        "Form 1099-INT   Interest Income", "Form 1099-DIV   Dividends and Distributions",
    ], "B01"),
    ("1040", "Schwab consolidated 1099 with a B.pdf", [
        "Charles Schwab", "2025 Consolidated Form 1099", "Form 1099-DIV Dividends and Distributions",
        "Form 1099-INT Interest Income", "Form 1099-B Proceeds From Broker and Barter Exchange Transactions",
        "Form 1099-MISC Miscellaneous Information", "Realized Gain and Loss",
    ], None),
    ("1040", "pledge acknowledgment.pdf", [
        "State University Foundation", "We gratefully acknowledge your pledge of 10,000.00, payable over five years.",
        "First installment due January 2026.",
    ], None),
    ("1040", "signed engagement letter.pdf", [
        "J Park & Associates", "Engagement Letter for the 2025 tax year",
        "We gratefully acknowledge the trust you place in us each year.", "Signed: Jane Smith",
    ], None),
    ("1040", "volunteer record.pdf", ["Helping Hands", "Thank you for your gift of time: 120 hours in 2025", "Mileage log"], None),
    ("1040", "church contribution statement.pdf", [
        "Grace Community Church", "EIN 95-1111111", "2025 Contribution Statement", "Total contributions for 2025: 1,500.00",
        "No goods or services were provided in exchange for these contributions.",
    ], "D01"),
    ("1040", "statement of giving.pdf", ["First Baptist Church", "2025 Statement of Giving", "Total 2,400.00"], "D01"),
    ("1040", "contribution record.pdf", ["St. Mary's Parish", "Contribution Record for 2025", "Envelope 214", "Total 900.00"], None),
    ("1040", "acknowledgment letter.pdf", [
        "Red Cross", "We gratefully acknowledge your charitable contribution of $500 received on December 15, 2025.",
    ], "D01"),
    ("1040", "CA 540-ES voucher.pdf", [
        "TAXABLE YEAR 2025 Estimated Tax for Individuals CALIFORNIA FORM 540-ES",
        "Amount of payment 1,200.00", "Form 540-ES 2025",
    ], None),
    ("1040", "dependent care FSA statement.pdf", [
        "WageWorks Benefits Administration", "2025 Dependent Care Statement",
        "Dependent Care FSA elected 5,000.00", "Claims reimbursed 5,000.00",
    ], None),
]
_DECISION_69 = [
    # Round twelve. A sentence wraps where it will, so the word before a form
    # may end the line above; a checklist sets a form off from its title with
    # a dash; a savings plan's contribution record, receipt or summary is not
    # a charitable receipt; a state return package with its filing letter is
    # not the estimated tax record.
    ("1040", "organizer homeowners wrapped.pdf", [
        "2025 Individual Income Tax Organizer - Homeowners Section",
        "Mortgage interest paid on your residence: please attach", "Form 1098 (2025) from each lender.",
        "Property taxes paid: attach your bill",
    ], None),
    ("1040", "escrow letter wrapped.pdf", [
        "Wells Fargo Home Mortgage", "Annual Escrow Account Disclosure Statement",
        "For your mortgage interest deduction, see", "Form 1098 for 2025 mailed separately.",
    ], None),
    ("1040", "bank summary wrapped.pdf", [
        "First National Bank", "Annual Account Summary January 1, 2025 - December 31, 2025",
        "Total interest paid 12.50 (reported on", "Form 1099-INT)",
    ], None),
    ("1040", "organizer interest page.pdf", [
        "2025 Individual Income Tax Organizer - Interest and Dividend Income",
        "Form 1099-INT - Interest Income", "Form 1099-DIV - Dividends and Distributions",
        "Form 1099-OID - Original Issue Discount", "Payer name  Amount",
    ], None),
    ("1041", "organizer 1099 page.pdf", [
        "2025 Fiduciary Organizer - Income", "Form 1099-INT - Interest Income", "Form 1099-DIV - Dividends and Distributions",
        "Form 1099-B - Proceeds", "Form 1099-R - Distributions", "Form 1099-MISC - Miscellaneous Information",
    ], None),
    ("1040", "organizer deductions page.pdf", [
        "2025 Individual Income Tax Organizer - Deductions", "Form 1098 - Mortgage Interest Statement",
        "Form 1098-T - Tuition Statement", "Form 1098-E - Student Loan Interest Statement", "Mortgage interest paid",
    ], None),
    ("1040", "IRA contribution record.pdf", ["Fidelity", "Traditional IRA - Account 1234", "2025 Contribution Record", "Contributions 7,000.00"], None),
    ("1040", "IRA contribution receipt.pdf", ["Charles Schwab", "Contribution Receipt", "Account type: Traditional IRA", "Amount 7,000.00"], None),
    ("1040", "IRA contribution summary.pdf", ["Vanguard", "2025 IRA Contribution Summary", "Tax-deductible contributions 7,000.00"], None),
    ("1040", "HSA year-end statement.pdf", ["HealthEquity", "Year-End HSA Statement 2025", "Employee tax-deductible contributions 4,150.00"], None),
    ("1040", "529 contribution record.pdf", ["ScholarShare 529", "2025 Contribution Record", "Total 5,000.00"], None),
    ("1040", "DAF grant confirmation.pdf", [
        "Fidelity Charitable", "Grant Confirmation", "Grants recommended from your giving account are not tax-deductible contributions.",
    ], None),
    ("1040", "plasma donation summary.pdf", ["BioLife", "2025 Donation Summary", "Total compensation paid 1,200.00"], None),
    ("1040", "CA filing instructions then 540.pdf", [
        "2024 California Filing Instructions", "Prepared for John and Jane Smith",
        "Your 2024 California return is attached. Sign and mail Form 540 to the Franchise Tax Board.",
        "Your 2025 estimated tax: mail Form 540-ES vouchers by April 15, June 15, September 15 and January 15.",
        "TAXABLE YEAR 2024 California Resident Income Tax Return FORM 540", "Form 540 2024 Side 5",
    ], None),
]


# Round thirteen: the half of the catalog no round had attacked. Decision
# 70's coverage report named 223 keywords no document in the suite reached
# - almost all of them on the rows that ask for receipts, statements,
# agreements and bookkeeping exports rather than IRS forms - and these are
# the documents those rows are for, with the confusables that reach the
# same words. One reconstruction is routed against every catalog whose
# rows ask for it, so the shared rows are proven in each.
_FS_PDF = [
    "Willow Lane LLC", "Financial Statements and Independent Accountant's Review Report",
    "December 31, 2025", "Balance Sheet as of December 31, 2025", "Total assets 1,240,000",
    "Statement of Operations for the year ended December 31, 2025",
    "Revenue 2,410,000  Net income 184,000", "Statement of Cash Flows",
]
_BANK_DEC = [
    "JPMorgan Chase Bank, N.A.  Chase Business Complete Checking",
    "December 01, 2025 through December 31, 2025   Account Number 000000812344",
    "CHECKING SUMMARY",
    "Beginning Balance 84,210.55  Deposits and Additions 212,400.00  Checks Paid -98,220.10",
    "DEPOSITS AND ADDITIONS  12/02 Remote Online Deposit 1  18,400.00",
]
_NOV_BANK = [
    "JPMorgan Chase Bank, N.A.  Chase Business Complete Checking",
    "November 01, 2025 through November 30, 2025",
    "CHECKING SUMMARY  Deposits and Additions 180,000.00  Checks Paid -22,000.00",
]
_PROMISSORY = [
    "PROMISSORY NOTE", "Principal amount 250,000.00   Date: January 15, 2025",
    "Willow Lane LLC promises to pay Bank of the West the principal balance with interest at 7.25%.",
    "Maturity: January 15, 2032",
]
_TB_QB = ["Smith Holdings LLC", "Trial Balance", "As of December 31, 2025",
          "Shareholder Distributions 10,000.00", "Donation Expense 500.00"]
_GL_QB = ["Smith Holdings LLC", "General Ledger", "January - December 2025",
          "Charitable Contributions 12/15/2025 Check 1042 Red Cross donation 500.00"]
_BS_QB = ["Smith Holdings LLC", "Balance Sheet", "As of December 31, 2025", "ASSETS",
          "Checking 12,000.00", "Fixed Assets 60,000.00"]
_PL = ["Profit and Loss January - December 2025", "Officer Compensation 120,000.00", "Depreciation 6,120.00"]
_DEC_BANK_SHORT = ["Checking Account Statement", "Statement period 12/01/2025 - 12/31/2025",
                   "Deposits and other credits 4,000.00"]
_CAP_TABLE = ["Smith Holdings Inc. Cap Table as of December 31, 2025", "Shareholder Shares Percent", "J Smith 600 60%"]
_NONPROFIT_FS = ["Statements of Financial Position 2025", "Total liabilities 20,704"]
_W3 = ["Form W-3 Transmittal of Wage and Tax Statements 2025", "Total number of Forms W-2",
       "b Employer identification number"]
_F941 = ["Form 941 Employer's QUARTERLY Federal Tax Return 2025", "Form 941-V, Payment Voucher"]
_ES_VOUCHER_1 = ["2025 Estimated Tax Payment Voucher 1", "Form 1040-ES"]
_ES_VOUCHER_4 = ["Form 1040-ES", "2025 Estimated Tax Payment Voucher 4",
                 "Amount of estimated tax you are paying by check or money order 2,500.00"]
_OFFICER_COMP = ["Acme Manufacturing Inc.", "Officer Compensation Detail - 2025",
                 "Officer  Title  Compensation", "John Reyes  President  240,000.00"]
_BROKER_COVER = ["Charles Schwab  2025 Tax Reporting Package",
                 "Enclosed: Form 1099-INT, Form 1098, Form 5498",
                 "Form 1099-INT Interest Income 2025", "1 Interest income 1,842.55"]

_DECISION_73 = [
    # 1040 D01: what a charity's receipt says, and what a fundraiser's
    # thank-you says. `thank you for your donation` is a salutation both print.
    ("1040", "church giving statement.pdf", [
        "Grace Community Church", "2025 Giving Statement",
        "John and Jane Smith  Envelope 214",
        "Total contributions received January 1 - December 31, 2025: 6,400.00",
        "No goods or services were provided in exchange for these contributions.",
    ], "D01"),
    ("1040", "Goodwill donation receipt.pdf", [
        "Goodwill Industries  Donation Receipt",
        "Date of donation: 11/08/2025   Location: Pasadena",
        "Description of donated goods: 4 bags clothing, 1 desk",
        "Donor is responsible for determining value. Goodwill is a 501(c)(3) charity.",
    ], "D01"),
    ("1040", "university acknowledgment letter.pdf", [
        "State University Foundation", "January 15, 2026",
        "Dear Mr. Smith: we acknowledge your donation of 5,000.00 received on December 28, 2025.",
        "No goods or services were provided in exchange for this gift.",
    ], "D01"),
    ("1040", "donor advised fund giving record.pdf", [
        "Fidelity Charitable  Giving Account 88-2200",
        "2025 Giving Record", "Contributions to your giving account in 2025: 20,000.00",
        "Your contributions to Fidelity Charitable are tax-deductible in the year received.",
    ], "D01"),
    ("1040", "food bank donor statement.pdf", [
        "Second Harvest Food Bank", "Annual Donor Statement - 2025",
        "Your charitable giving this year totalled 1,250.00.",
        "Second Harvest is a tax-exempt organization under section 501(c)(3).",
    ], "D01"),
    ("1040", "humane society contribution statement.pdf", [
        "Valley Humane Society", "2025 Charitable Contribution Statement",
        "Total tax-deductible donation amount: 900.00", "Thank you for your donation.",
    ], "D01"),
    ("1040", "museum membership renewal.pdf", [
        "City Museum of Art  Membership Renewal 2025", "Household membership 150.00",
        "Goods and services valued at 40.00 (guest passes) were provided; 110.00 is a tax-deductible gift.",
    ], "D01"),
    ("1040", "political campaign receipt.pdf", [
        "Smith for Congress Committee", "Thank you for your donation of 500.00 on 10/02/2025.",
        "Contributions to political committees are not tax-deductible for federal income tax purposes.",
    ], None),
    ("1040", "GoFundMe receipt.pdf", [
        "GoFundMe", "Thank you for your donation of 100.00 to 'Help Maria's surgery' on 06/11/2025.",
        "Donations to personal fundraisers are generally not tax-deductible.",
    ], None),
    # 1040 E01: a broker's own statement, and the firm's organizer page that
    # asks for one. A menu line names neither the form nor its title, and a
    # document does not ask for itself.
    ("1040", "1099-B Copy B.pdf", [
        "Form 1099-B Proceeds From Broker and Barter Exchange Transactions 2025",
        "Copy B For Recipient OMB No. 1545-0715 For calendar year 2025",
        "Applicable checkbox on Form 8949 1a Description of property (Example: 100 sh. XYZ Co.)",
        "1b Date acquired 03/11/2021 1c Date sold or disposed 08/14/2025",
        "1d Proceeds 24,318.55 1e Cost or other basis 19,004.10",
    ], "E01"),
    ("1040", "Schwab year-end brokerage statement.pdf", [
        "Charles Schwab & Co., Inc.",
        "Year-End Brokerage Statement January 1, 2025 - December 31, 2025",
        "Account 1234-5678 JOHN Q SMITH", "Realized Gain and Loss Summary",
        "Total proceeds 124,300.00 Total cost basis 101,200.00 Net short-term gain 3,120.00",
    ], "E01"),
    ("1040", "Fidelity realized gain and loss report.pdf", [
        "Fidelity Investments", "2025 Realized Gain and Loss Report", "Account Z12-345678",
        "Security  Quantity  Date acquired  Date sold  Proceeds  Cost basis  Gain/(loss)",
        "APPLE INC 100 02/03/2022 09/09/2025 18,400.00 14,220.00 4,180.00",
    ], "E01"),
    ("1040", "organizer investment page.pdf", [
        "2025 Individual Income Tax Organizer - Investment Income",
        "Form 1099-B - Proceeds From Broker and Barter Exchange Transactions",
        "Form 1099-DIV - Dividends and Distributions",
        "Please list every brokerage account below.  Broker  Account number",
    ], None),
    ("1040", "organizer investment page in prose.pdf", [
        "2025 Individual Income Tax Organizer - Investment Income",
        "Did you sell any stocks, bonds or mutual funds in 2025?",
        "If yes, attach your brokerage statement and any realized gain and loss report.",
    ], None),
    ("1040", "1099-B cover letter from the broker.pdf", [
        "Morgan Stanley Wealth Management",
        "Enclosed you will find your Form 1099-B for the 2025 tax year.",
        "Cost basis for covered securities is reported to the IRS.",
    ], None),
    ("1040", "8949 from the prior year package.pdf", [
        "Form 8949 Sales and Other Dispositions of Capital Assets 2024",
        "(a) Description of property (b) Date acquired (c) Date sold (d) Proceeds (sales price)",
        "Totals 124,300.00",
    ], None),
    # 1040 E02
    ("1040", "pension retirement distribution summary.pdf", [
        "CalPERS Retirement System", "2025 Retirement Distribution Summary",
        "Gross distributions 42,000.00  Federal tax withheld 4,200.00",
        "This summary is provided for your records; see your Form 1099-R.",
    ], "E02"),
    ("1040", "401k participant statement.pdf", [
        "Empower Retirement  Participant Statement", "Period 10/01/2025 - 12/31/2025",
        "Beginning balance 210,400.00  Contributions 9,000.00  Ending balance 228,100.00",
    ], None),
    ("1040", "RMD notice for next year.pdf", [
        "Vanguard", "2026 Required Minimum Distribution Notice", "Account 8812-4455",
        "Your 2026 RMD is 18,400.00. A retirement distribution must be taken by December 31, 2026.",
    ], None),
    # 1040 G01: the bill's own title. The assessor's notice says it is not a
    # tax bill, and the servicer's escrow analysis only lists the bill it paid.
    ("1040", "county secured property tax bill.pdf", [
        "COUNTY OF LOS ANGELES  TREASURER AND TAX COLLECTOR",
        "2025 ANNUAL SECURED PROPERTY TAX BILL",
        "ASSESSOR'S IDENTIFICATION NUMBER (PARCEL NUMBER) 5432-011-004",
        "FISCAL YEAR JULY 1, 2025 TO JUNE 30, 2026",
        "1st Installment 3,142.55 due 11/01/2025   2nd Installment 3,142.55 due 02/01/2026",
    ], "G01"),
    ("1040", "property tax statement.pdf", [
        "Hennepin County  2025 Property Tax Statement",
        "Property ID 23-118-21-31-0042  Taxpayer: John Smith", "Total 2025 property tax 4,880.00",
    ], "G01"),
    ("1040", "real estate tax bill.pdf", [
        "Town of Greenwich  Tax Collector", "2025 Real Estate Tax Bill",
        "List 42  Grand List of October 1, 2024", "Total due 8,410.22",
    ], "G01"),
    ("1040", "property tax notice.pdf", [
        "King County Treasury", "2025 Property Tax Notice", "Parcel 042300-0155",
        "First half due April 30, 2025  Second half due October 31, 2025", "Total 6,120.00",
    ], "G01"),
    ("1040", "assessor notice of assessed value.pdf", [
        "Office of the County Assessor  Santa Clara County",
        "2025 Notice of Assessed Value", "Parcel Number 264-11-032",
        "Net assessed value 812,400. This is not a tax bill.",
    ], None),
    ("1040", "escrow analysis statement.pdf", [
        "Wells Fargo Home Mortgage  Annual Escrow Account Disclosure Statement 2025",
        "Escrow disbursements: County property tax bill 6,285.10 paid 12/08/2025; hazard insurance 1,410.00",
        "New monthly payment effective February 2026",
    ], None),
    ("1040", "closing disclosure.pdf", [
        "Closing Disclosure  Issue Date 07/14/2025",
        "Loan Terms  Loan Amount 480,000  Interest Rate 6.125%",
        "Prepaids  City/Town Taxes  County Taxes to County Tax Collector 08/01/25 to 12/31/25  1,842.00",
        "Summaries of Transactions  Cash to Close 112,400.00",
    ], None),
    # 1040 H01: an individual's voucher, in the spellings a person sends.
    ("1040", "1040-ES voucher 2.pdf", [
        "2025 Estimated Tax Payment Voucher 2", "Form 1040-ES  Due June 16, 2025",
        "Amount of estimated tax you are paying by check or money order 4,500.00",
    ], "H01"),
    ("1040", "1040-ES voucher 3.pdf", [
        "2025 Estimated Tax Payment Voucher 3", "Due September 15, 2025",
        "Calendar year - Due Sept. 15, 2025   Amount 4,500.00",
    ], "H01"),
    ("1040", "NY IT-2105 voucher.pdf", [
        "New York State Department of Taxation and Finance",
        "IT-2105 Estimated Tax Payment Voucher for Individuals",
        "Calendar-year filer due date: September 15, 2025   Payment amount 1,900.00",
    ], "H01"),
    ("1040", "estimated tax voucher 4th quarter.pdf", [
        "2025 Estimated Tax Voucher - 4th quarter", "Payable to United States Treasury",
        "Amount 4,500.00  Due January 15, 2026",
    ], "H01"),
    ("1040", "IRS account transcript.pdf", [
        "Internal Revenue Service  Account Transcript  Tax Period December 31, 2025",
        "ESTIMATED TAX PAYMENT  04-15-2025  4,500.00-",
        "ESTIMATED TAX PAYMENT  06-16-2025  4,500.00-",
    ], None),
    # 1040 I01: the form's own identifiers. The marketplace's eligibility
    # notice quotes the credit the form's column is named after.
    ("1040", "1095-A filled.pdf", [
        "Form 1095-A Health Insurance Marketplace Statement 2025",
        "Department of the Treasury Internal Revenue Service  VOID CORRECTED",
        "Part I Recipient Information  1 Marketplace identifier CA  2 Marketplace-assigned policy number 4411903",
        "Part III Coverage Information  A. Monthly enrollment premiums  B. Monthly second lowest cost silver plan (SLCSP) premium  "
        "C. Monthly advance payment of premium tax credit",
        "January 1,240.00 1,180.00 640.00",
    ], "I01"),
    ("1040", "marketplace eligibility notice.pdf", [
        "Covered California  Eligibility Determination Notice  November 2025",
        "Your household is eligible for an advance payment of premium tax credit of 640.00 per month for 2025.",
        "Choose a plan by December 15, 2025.",
    ], None),
    # 1040 J01: the spellings a provider prints, the two-word one included.
    ("1040", "daycare year-end statement.pdf", [
        "Bright Horizons Learning Center", "2025 Childcare Statement",
        "Provider name: Bright Horizons Learning Center  EIN 12-3456789",
        "Child: Emma Smith  Total paid January 1 - December 31, 2025: 14,400.00",
    ], "J01"),
    ("1040", "home daycare receipt.pdf", [
        "Maria's Family Daycare  License 193884", "Daycare Receipt for tax year 2025",
        "Provider SSN on file  Total received 9,600.00  Paid by: Jane Smith",
    ], "J01"),
    ("1040", "day care statement.pdf", [
        "Sunshine Day Care Home", "2025 Day Care Statement",
        "Provider EIN 45-2200113", "Child: Emma Smith  Total paid 10,800.00",
    ], "J01"),
    ("1040", "preschool statement of child care expenses.pdf", [
        "Little Acorns Preschool", "Statement of Child Care Expenses - 2025",
        "Provider EIN 95-4433221  Amount paid 11,200.00",
    ], "J01"),
    ("1040", "year-end child care summary.pdf", [
        "KinderCare Learning Centers", "Year-End Child Care Statement 2025",
        "Tax identification number 33-0099887  Total tuition paid 16,800.00",
    ], "J01"),
    ("1040", "day camp receipt.pdf", [
        "Camp Wildwood Day Camp  2025 Child Care Receipt",
        "Camper: Emma Smith   Provider EIN 77-1122334   Total paid 2,400.00",
    ], "J01"),
    ("1040", "private school tuition statement.pdf", [
        "St. Mark's Academy", "2025 Tuition Statement", "Student: Emma Smith  Grade 4",
        "Tuition billed 18,000.00  Payments received 18,000.00",
    ], None),
    ("1040", "dependent care assistance letter.pdf", [
        "Acme Corp Benefits", "2025 Dependent Care Assistance Program summary",
        "Amount excluded from wages 5,000.00 (reported in box 10 of your Form W-2)",
    ], None),
    # 1040 K01, L01
    ("1040", "5498-ESA.pdf", [
        "Form 5498-ESA Coverdell ESA Contribution Information 2025",
        "TRUSTEE'S name  Fidelity Investments  BENEFICIARY'S name  Emma Smith",
        "1 Coverdell ESA contributions 2,000.00  2 Rollover contributions",
    ], "K01"),
    ("1040", "5498-SA filled.pdf", [
        "Form 5498-SA HSA, Archer MSA, or Medicare Advantage MSA Information 2025",
        "TRUSTEE'S name HealthEquity  PARTICIPANT'S name John Smith",
        "2 Total contributions made in 2025 4,150.00  5 Fair market value of HSA 21,300.00",
    ], "K01"),
    ("1040", "tuition statement without the number.pdf", [
        "State University  Office of the Bursar", "2025 Tuition Statement",
        "Payments received for qualified tuition and related expenses 18,420.00",
    ], "L01"),
    ("1040", "university bill.pdf", [
        "State University  Office of the Bursar", "Student Account Statement - Fall 2025",
        "Tuition and fees 18,420.00  Housing 7,200.00  Payments -25,620.00",
    ], None),
    # A payer's own substitute form sets its title off with a dash, as a
    # checklist does; one such line, dated, is a form naming itself.
    ("1040", "substitute 1099-INT with a dash title.pdf", [
        "2025 Form 1099-INT - Interest Income",
        "Ally Bank  PAYER'S TIN 12-3456789   RECIPIENT'S TIN xxx-xx-6789",
        "1 Interest income 1,842.55   4 Federal income tax withheld 0.00",
        "This is important tax information and is being furnished to the IRS.",
    ], "A02"),
    ("1040", "substitute 1098 with a dash title.pdf", [
        "Form 1098 - Mortgage Interest Statement  2025",
        "RECIPIENT'S/LENDER'S name Wells Fargo Home Mortgage",
        "1 Mortgage interest received from payer(s)/borrower(s) 14,220.19",
        "2 Outstanding mortgage principal 480,000.00",
    ], "C01"),
    # A cover's last form has no punctuation after it and was read as named
    # in its own right, which blinded the form printed behind it.
    ("1040", "broker cover then the 1099-INT.pdf", _BROKER_COVER, "A02"),
    ("1041", "broker cover then the 1099-INT.pdf", _BROKER_COVER, "B01"),
    # 1041 A01: the estate's own instrument names the kind of trust it is; a
    # custodian's IRA paperwork is headed "Trust Agreement" too.
    ("1041", "revocable trust agreement.pdf", [
        "THE DOYLE FAMILY REVOCABLE TRUST AGREEMENT",
        "This Trust Agreement is made on June 3, 2011 between Margaret A. Doyle, as Settlor, and",
        "Margaret A. Doyle and Thomas Doyle, as Trustees.",
        "ARTICLE ONE  Declaration of Trust", "ARTICLE TWO  Distributions During the Settlor's Lifetime",
    ], "A01"),
    ("1041", "last will and testament.pdf", [
        "LAST WILL AND TESTAMENT OF MARGARET A. DOYLE",
        "I, Margaret A. Doyle, of Pasadena, California, declare this to be my Last Will and Testament.",
        "ARTICLE I  I revoke all prior wills and codicils.",
    ], "A01"),
    ("1041", "first codicil.pdf", [
        "FIRST CODICIL TO THE LAST WILL AND TESTAMENT OF MARGARET A. DOYLE",
        "Dated March 2, 2019. I amend Article IV of my Will as follows.",
    ], "A01"),
    ("1041", "certification of trust.pdf", [
        "CERTIFICATION OF TRUST", "The Doyle Family Trust, dated June 3, 2011",
        "The undersigned trustee certifies the trust has not been revoked.",
    ], "A01"),
    ("1041", "IRA custodial trust agreement.pdf", [
        "Fidelity Investments", "Traditional IRA Trust Agreement and Disclosure Statement",
        "Article I. The trustee will accept only cash contributions.",
        "This Trust Agreement is provided for your records; no action is required.",
    ], None),
    # 1041 A02
    ("1041", "CP 575 EIN letter.pdf", [
        "INTERNAL REVENUE SERVICE  CINCINNATI OH 45999-0023",
        "Notice CP 575 A   Notice Date  03-14-2019   EIN 84-1234567",
        "ESTATE OF MARGARET A DOYLE",
        "Thank you for applying for an Employer Identification Number (EIN). We assigned you EIN 84-1234567.",
    ], "A02"),
    ("1041", "EIN assignment letter reprint.pdf", [
        "Internal Revenue Service  EIN Assignment Letter (147C)",
        "Date: February 8, 2025", "Taxpayer: Doyle Family Trust  EIN 84-1234567",
        "We assigned you an Employer Identification Number as shown above.",
    ], "A02"),
    ("1041", "CP 575 in a corporation.pdf", [
        "IRS Department of the Treasury Internal Revenue Service Cincinnati OH 45999-0023",
        "Date of this notice: 03-14-2025 Employer Identification Number: 12-3456789 Form: SS-4 Number of this notice: CP 575 A",
        "For assistance you may call us at: 1-800-829-4933 IF YOU WRITE, ATTACH THE STUB AT THE END OF THIS NOTICE.",
        "SMITH HOLDINGS INC 123 MAIN ST ANYTOWN CA 90000",
        "WE ASSIGNED YOU AN EMPLOYER IDENTIFICATION NUMBER",
        "Thank you for applying for an Employer Identification Number (EIN). We assigned you EIN 12-3456789. This EIN will identify you,",
    ], "A02"),
    # 1041 B01/B02: a broker's year-end statement, and the bank's and the
    # firm's papers that carry the same heading.
    ("1041", "trust brokerage year-end statement.pdf", [
        "Northern Trust  Year-End Brokerage Statement 2025",
        "Account: Doyle Family Trust  12-3456", "January 1, 2025 - December 31, 2025",
        "Realized Gain and Loss  Net long-term gain 18,400.00",
    ], "B02"),
    ("1041", "year-end account statement.pdf", [
        "Charles Schwab", "Year-End Account Statement", "Period 01/01/2025 - 12/31/2025",
        "Estate of Margaret A. Doyle  Account 4411-9922", "Ending account value 812,000.00",
    ], None),
    ("1041", "bank year-end account statement.pdf", [
        "First Republic Bank", "Year-End Account Statement 2025",
        "Doyle Family Trust checking 8812", "Interest paid this year 214.50",
    ], None),
    ("1041", "brokerage.pdf", [
        "Year-end account statement 2025", "Statement period 12/01/2025 - 12/31/2025",
        "Ending balance 40,000", "brokerage",
    ], None),
    ("1041", "fiduciary organizer investment page.pdf", [
        "2025 Fiduciary Organizer - Investment Income",
        "Attach the year-end account statement for each brokerage account.",
        "Attach the realized gain and loss report for the year.",
    ], None),
    ("1041", "Schwab consolidated 1099 with a B.pdf", [
        "Charles Schwab", "2025 Consolidated Form 1099", "Form 1099-DIV Dividends and Distributions",
        "Form 1099-INT Interest Income", "Form 1099-B Proceeds From Broker and Barter Exchange Transactions",
        "Form 1099-MISC Miscellaneous Information", "Realized Gain and Loss",
    ], None),
    ("1041", "fax cover then 1099-R.pdf", [
        "FAX COVER SHEET", "To: J Park & Associates From: Jane Smith Date: 02/01/2026 Pages: 3",
        "Re: Forms 1099-INT and 1099-DIV, plus a 1098 - for my 2025 return", "",
        "Form 1099-R Distributions From Pensions, Annuities, Retirement or Profit-Sharing Plans, IRAs, Insurance Contracts, etc. 2025",
        "OMB No. 1545-0119", "1 Gross distribution 20,000.00", "Instructions for Recipient", "Form 1099-R (2025)",
    ], "B01"),
    # 1041 C01..F01
    ("1041", "beneficiary distribution letter.pdf", [
        "Doyle Family Trust", "Beneficiary Distribution Summary for 2025",
        "Thomas Doyle received 25,000.00 on March 15, 2025.",
    ], "C01"),
    ("1041", "mutual fund distribution schedule.pdf", [
        "Vanguard  2025 Distribution Schedule",
        "Estimated year-end capital gains distribution schedule for Vanguard funds.",
        "Fund  Record date  Payable date  Estimated per share",
        "Total Stock Market Index  12/19/2025  12/22/2025  0.4210",
    ], None),
    ("1041", "beneficiary list.pdf", [
        "Estate of Margaret A. Doyle", "Beneficiary List",
        "Thomas Doyle  18 Alder Ln  SSN xxx-xx-4412", "Sarah Doyle  902 Main St  SSN xxx-xx-9931",
    ], "C02"),
    ("1041", "trustee fee statement.pdf", [
        "Northern Trust  Fiduciary Services", "2025 Trustee Fees",
        "Doyle Family Trust  Annual fiduciary fees paid 12,400.00",
    ], "D01"),
    ("1041", "law firm fee invoice.pdf", [
        "Baker & Lyle LLP  Attorneys at Law", "Fee Invoice 2025-4412  Date December 3, 2025",
        "Estate of Margaret A. Doyle - probate administration", "Legal fees paid 8,200.00",
    ], "D01"),
    ("1041", "funeral home invoice.pdf", [
        "Rose Hills Memorial Park  Invoice 88123  Date January 12, 2025",
        "Services for Margaret A. Doyle", "Total charges 14,800.00",
    ], None),
    ("1041", "basis of assets sold memo.pdf", [
        "Doyle Family Trust", "Basis of Assets Sold During 2025",
        "Date acquired and date sold are shown for each lot below.",
        "Purchase price and sale price per the closing statements.",
    ], "E01"),
    ("1041", "stepped-up basis schedule.pdf", [
        "Estate of Margaret A. Doyle", "Stepped-Up Basis Schedule - 2025",
        "Asset  Value at death  Sale proceeds  Gain",
        "18 Alder Lane  812,000  940,000  128,000",
    ], "E01"),
    ("1041", "date of death appraisal.pdf", [
        "Coastal Appraisal Group  Appraisal Report", "Subject: 18 Alder Lane, Pasadena CA",
        "Date of value: January 4, 2025 (date of death)", "Opinion of market value 812,000",
    ], None),
    ("1041", "property manager annual statement.pdf", [
        "Bayview Property Management", "Owner Statement - Year 2025  902 Main Street",
        "Rental income and expenses summary", "Gross rents 42,000.00  Management fee 3,360.00",
    ], "F01"),
    ("1041", "lease agreement.pdf", [
        "RESIDENTIAL LEASE AGREEMENT", "Premises: 902 Main Street, Unit 1A",
        "Term: July 1, 2025 to June 30, 2026   Monthly rent 1,750.00",
    ], None),
] + [
    # The shared rows, in every catalog that carries them.
    case
    for form in ("1120", "1120S", "1065", "990")
    for case in (
        (form, f"financial statements {form}.pdf", _FS_PDF, "B01"),
        (form, f"Chase December statement {form}.pdf", _BANK_DEC, "B02"),
        (form, f"November bank statement {form}.pdf", _NOV_BANK, None),
    )
] + [
    ("1120", "QuickBooks general ledger.pdf", _GL_QB, "A03"),
    ("1120S", "QuickBooks general ledger.pdf", _GL_QB, "A03"),
    ("1065", "QuickBooks general ledger.pdf", _GL_QB, "A04"),
    ("1065", "QuickBooks trial balance.pdf", _TB_QB, "A03"),
    ("990", "QuickBooks trial balance.pdf", _TB_QB, "A02"),
    ("990", "nonprofit trial balance.pdf", [
        "Riverside Community Center", "Trial Balance", "As of December 31, 2025",
        "1000 Cash 84,210.55", "4000 Contributions 612,000.00", "5100 Salaries and wages 394,000.00",
    ], "A02"),
    ("1065", "QuickBooks balance sheet.pdf", _BS_QB, "B01"),
    ("1120S", "QuickBooks balance sheet.pdf", _BS_QB, "B01"),
    ("990", "QuickBooks balance sheet.pdf", _BS_QB, "B01"),
    ("1065", "P&L.pdf", _PL, "B01"),
    ("1120S", "P&L.pdf", _PL, "B01"),
    ("990", "P&L.pdf", _PL, "B01"),
    ("1120", "nonprofit FS.pdf", _NONPROFIT_FS, "B01"),
    ("1120S", "nonprofit FS.pdf", _NONPROFIT_FS, "B01"),
    ("990", "nonprofit FS.pdf", _NONPROFIT_FS, "B01"),
    ("1065", "Dec 2025 bank.pdf", _DEC_BANK_SHORT, "B02"),
    ("1120", "Dec 2025 bank.pdf", _DEC_BANK_SHORT, "B02"),
    ("1120S", "Dec 2025 bank.pdf", _DEC_BANK_SHORT, "B02"),
    # A December statement of account is a credit-card issuer's and a
    # broker's heading; neither is the bank statement the row asks for.
    ("1120", "December credit card statement.pdf", [
        "Chase Ink Business Preferred  Statement of Account",
        "Opening/Closing Date 12/03/2025 - 01/02/2026",
        "Payments and Other Credits -4,200.00  Purchases 8,412.55",
        "New Balance 8,412.55  Minimum Payment Due 85.00",
    ], None),
    ("1120", "December brokerage statement.pdf", [
        "Fidelity Investments  Statement of Account",
        "December 1, 2025 - December 31, 2025  Account Z12-345678 Willow Lane LLC",
        "Beginning value 420,000.00  Ending value 441,200.00",
    ], None),
    ("1065", "cap table.pdf", _CAP_TABLE, "C01"),
    ("1120S", "cap table.pdf", _CAP_TABLE, "C01"),
    ("1120", "W-3.pdf", _W3, "E01"),
    ("1120S", "W-3.pdf", _W3, "E01"),
    ("990", "W-3.pdf", _W3, "G01"),
    ("1120S", "941.pdf", _F941, "E01"),
    ("1120", "depreciation detail report.pdf", [
        "Willow Lane Inc.  Depreciation Detail Report  2025",
        "Asset  In service  Cost  Method  Current depreciation",
        "Ford Transit van  03/14/2025  48,200.00  MACRS 5yr  9,640.00",
    ], "C02"),
    ("1120", "officer compensation detail as a pdf.pdf", _OFFICER_COMP, "E02"),
    ("990", "officer compensation detail as a pdf.pdf", [
        "Riverside Community Center", "Officer Compensation Detail - 2025",
        "Ana Diaz  Executive Director  147,000.00",
    ], "C02"),
    ("1120", "promissory note.pdf", _PROMISSORY, "D01"),
    ("1065", "promissory note.pdf", _PROMISSORY, "E01"),
    ("1120S", "promissory note.pdf", _PROMISSORY, "G01"),
    ("1120S", "shareholder loan agreement.pdf", [
        "SHAREHOLDER LOAN AGREEMENT",
        "Between Willow Lane Inc. and John Reyes, shareholder.  Dated February 1, 2025",
        "Principal balance at December 31, 2025: 60,000.00",
    ], "G01"),
    ("1120S", "loan amortization schedule.pdf", [
        "Willow Lane Inc.  Note payable - Bank of the West",
        "Loan Amortization Schedule  December 31, 2025",
        "Payment 12  12/15/2025  Principal 1,940.11  Interest 520.21  Balance 216,400.00",
    ], "G01"),
    ("1120", "business loan statement December.pdf", [
        "Bank of the West  Commercial Loan Statement",
        "Statement date December 31, 2025  Loan 88-1290",
        "Principal balance 216,400.00  Interest paid this year 6,940.00",
    ], "D01"),
    # A corporation's estimated tax record says whose it is; an
    # individual's 1040-ES voucher dropped into a corporate engagement is
    # for a person and parks.
    ("1120", "corporation estimated tax voucher.pdf", [
        "2025 Corporation Estimated Tax Voucher - 2nd installment",
        "Willow Lane Inc.  EIN 95-1122334", "Amount of payment 12,000.00  Due June 16, 2025",
    ], "F01"),
    ("1120", "1040-ES voucher in a corporation.pdf", _ES_VOUCHER_1, None),
    ("1120", "paid voucher stub in a corporation.pdf", _ES_VOUCHER_4, None),
    ("1120", "book to tax reconciliation memo.pdf", [
        "Willow Lane Inc.  Book to Tax Reconciliation  December 31, 2025",
        "Net income per books 184,000", "Add: 50% of meals 9,200", "Taxable income 178,840",
    ], "I01"),
    ("1120S", "2% shareholder premium letter.pdf", [
        "Willow Lane Inc.  Payroll memo December 2025",
        "Health insurance premiums paid for a 2% shareholder are included in box 1 wages.",
        "John Reyes: 14,400.00 added to December payroll.",
    ], "D02"),
    ("1065", "partnership agreement.pdf", [
        "AMENDED AND RESTATED LIMITED PARTNERSHIP AGREEMENT OF WILLOW LANE PARTNERS, L.P.",
        "This Agreement is entered into as of March 1, 2019 by and among the General Partner and the Limited Partners.",
        "ARTICLE IV  Capital Contributions   ARTICLE V  Allocations and Distributions",
    ], "A02"),
    ("990", "board minutes.pdf", [
        "Riverside Community Center", "Board Minutes - Meeting of March 4, 2025",
        "Present: A. Diaz, P. Mbeki, L. Howard.  The board approved the 2025 budget.",
    ], "C01"),
    ("990", "minutes of the annual meeting.pdf", [
        "Riverside Community Center",
        "Minutes of the Annual Meeting of the Board of Directors  March 4, 2025",
        "Present: A. Diaz, P. Mbeki, L. Howard.  The 2025 budget was approved.",
    ], "C01"),
    ("990", "program service accomplishments narrative.pdf", [
        "Riverside Community Center", "Program Service Accomplishments - 2025",
        "After-school tutoring: 412 students served across 3 sites, 18,400 contact hours.",
        "Senior meals: 62,000 meals delivered to 900 homebound residents.",
    ], "E01"),
    ("990", "grant proposal program description.pdf", [
        "Riverside Community Center", "Grant Proposal to the Bayside Foundation - 2025",
        "Program description: the after-school tutoring program serves 412 students at three sites.",
        "Amount requested 100,000.00",
    ], None),
    ("990", "grant award letter received.pdf", [
        "Bayside Foundation  Grant Award Letter  October 2, 2025",
        "Grantee: Riverside Community Center   Grant amount 100,000.00",
        "Payable in two instalments during 2025 and 2026.",
    ], None),
    ("990", "990-T for 2025.pdf", [
        "Form 990-T Exempt Organization Business Income Tax Return 2025",
        "For calendar year 2025  Riverside Community Center  EIN 84-1234567",
        "Part I Total Unrelated Business Taxable Income 24,000",
    ], "H01"),
    ("990", "990 Part III page scanned.pdf", [
        "Form 990 (2024) Page 2", "Part III Statement of Program Service Accomplishments",
        "1 Briefly describe the organization's mission:",
        "4a (Code: ) (Expenses $ 640,000 including grants of $ 0 ) (Revenue $ 118,000 )",
    ], None),
    ("990", "990 Part VII page scanned.pdf", [
        "Form 990 (2024) Page 7",
        "Part VII Compensation of Officers, Directors, Trustees, Key Employees, Highest Compensated Employees, and Independent Contractors",
        "(A) Name and title (B) Average hours per week (C) Position (D) Reportable compensation from the organization",
    ], None),
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


#: (decision, form, file name, lines, expected) - every case, tagged with the
#: decision that introduced it. tools/vocab_report.py reads this list too.
CASES = [
    (decision, *case)
    for decision, block in (
        (62, _DECISION_62), (63, _DECISION_63), (65, _DECISION_65), (66, _DECISION_66),
        (67, _DECISION_67), (68, _DECISION_68), (69, _DECISION_69), (73, _DECISION_73),
    )
    for case in block
]

#: (decision, form, file name, rows, expected) - the workbook cases, in the
#: same shape with a sheet's rows in place of a page's lines. The report
#: reads this list too, rendering the rows the way a sheet is read.
XLSX_CASES = [(73, *case) for case in _DECISION_73_XLSX]


@pytest.mark.parametrize("decision, form, name, lines, expected", CASES, ids=[f"d{c[0]}-{c[2]}" for c in CASES])
def test_every_shipped_catalog_files_real_forms_where_they_belong(tmp_path, decision, form, name, lines, expected):
    items = shipped_rows(tmp_path, form)
    routing = route_file(text_pdf(tmp_path / name, NL.join(lines)), items)
    assert routing.identifier == expected, (f"decision {decision}", name, routing.reason)


@pytest.mark.parametrize("decision, form, name, rows, expected", XLSX_CASES,
                         ids=[f"d{c[0]}-{c[2]}-{c[1]}" for c in XLSX_CASES])
def test_every_shipped_catalog_files_the_workbooks_clients_send(tmp_path, decision, form, name, rows, expected):
    items = shipped_rows(tmp_path, form)
    routing = route_file(sheet_xlsx(tmp_path / name, rows), items)
    assert routing.identifier == expected, (f"decision {decision}", name, routing.reason)
