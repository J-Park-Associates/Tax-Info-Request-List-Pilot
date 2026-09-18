"""Sample client documents for the test suite.

Real-looking W-2s, 1099s, a prior-year return, a 1098, a donations
spreadsheet, plus the things clients actually send by mistake (a duplicate,
last year's form, a Word file, a Google Sheets shortcut, a photo, a
half-uploaded temp file). Built from nothing - no fixture files in the
repository, no client data - so every test starts from the same pile.

This used to live in tracker/api.py as the marketing demo's sample builder.
The demo is gone; the suite still needs the pile.
"""

from __future__ import annotations

import shutil
from pathlib import Path

from openpyxl import Workbook

from tracker.manifest import HEADERS
from tracker.templates import BASE_YEAR, template_items

#: The rows the sample documents were written against.
DEMO_ITEMS = template_items("1040", core_only=True)
YEAR = BASE_YEAR          # the samples are dated for the catalog's base year
PRIOR_YEAR = BASE_YEAR - 1


def col(header: str) -> int:
    """The 1-based column of ``header`` on the Requests sheet, from HEADERS."""
    return HEADERS.index(header) + 1


def row(**by_header: object) -> list:
    """A full-width Requests row in HEADERS order from header-name keys.

    Call it with the COL_* constants unpacked (``row(**{COL_IDENTIFIER: "Z01"})``)
    so a test never retypes the column order the manifest owns.
    """
    unknown = set(by_header) - set(HEADERS)
    if unknown:
        raise KeyError(f"not manifest headers: {sorted(unknown)}")
    return [by_header.get(header) for header in HEADERS]


def text_pdf(path: Path, lines: list[str]) -> Path:
    """Minimal but valid PDF with a real text layer (no extra deps)."""
    body = "\n".join(
        f"BT /F1 11 Tf 60 {740 - 14 * i} Td ({line}) Tj ET"
        for i, line in enumerate(lines[:48])
    )
    content = body.encode("ascii", "replace")
    padding = b" " * 8192  # unreferenced object: realistic file size, renders clean
    bodies = {
        1: b"<< /Type /Catalog /Pages 2 0 R >>",
        2: b"<< /Type /Pages /Kids [3 0 R] /Count 1 >>",
        3: (
            b"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] "
            b"/Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>"
        ),
        4: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(content), content),
        5: b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
        6: b"<< /Length %d >>\nstream\n%s\nendstream" % (len(padding), padding),
    }
    out = bytearray(b"%PDF-1.4\n")
    offsets = {}
    for n in sorted(bodies):
        offsets[n] = len(out)
        out += b"%d 0 obj\n" % n + bodies[n] + b"\nendobj\n"
    xref_at = len(out)
    out += b"xref\n0 %d\n0000000000 65535 f \n" % (len(bodies) + 1)
    for n in sorted(bodies):
        out += b"%010d 00000 n \n" % offsets[n]
    out += b"trailer\n<< /Size %d /Root 1 0 R >>\nstartxref\n%d\n%%%%EOF" % (
        len(bodies) + 1,
        xref_at,
    )
    path.write_bytes(bytes(out))
    return path


def w2_lines(employee: str, employer: str, year: int) -> list[str]:
    return [
        f"Form W-2 Wage and Tax Statement - Tax Year {year}",
        "a Employee's social security number  XXX-XX-1234",
        f"Employer: {employer}",
        f"Employee: {employee}",
        "",
        "Box 1  Wages, tips, other compensation       $84,500.00",
        "Box 2  Federal income tax withheld           $11,240.00",
        "Box 3  Social security wages                 $84,500.00",
        "Box 4  Social security tax withheld           $5,239.00",
        "Box 5  Medicare wages and tips               $84,500.00",
        "Box 6  Medicare tax withheld                  $1,225.25",
        "",
        f"Copy B - To Be Filed With Employee's Federal Tax Return, {year}",
    ]


def lines_1099_int(payer: str, recipient: str, year: int) -> list[str]:
    return [
        f"Form 1099-INT Interest Income - {year}",
        f"Payer: {payer}",
        f"Recipient: {recipient}",
        "",
        "Box 1  Interest income                        $1,842.17",
        "Box 4  Federal income tax withheld                $0.00",
        "",
        "This is important tax information and is being furnished to the IRS.",
    ]


def prior_return_lines(taxpayer: str, year: int) -> list[str]:
    return [
        f"Form 1040 - U.S. Individual Income Tax Return - Tax Year {year}",
        f"Taxpayer: {taxpayer}",
        "Filing status: Married filing jointly",
        "",
        "Line 1   Wages, salaries, tips                $161,300.00",
        "Line 11  Adjusted gross income                $168,455.00",
        "Line 24  Total tax                             $24,918.00",
        "Line 33  Total payments                        $26,102.00",
        "Line 34  Overpayment refunded                   $1,184.00",
        "",
        "Sign Here - Under penalties of perjury, I declare that I have examined this return.",
    ]


def form_1098_lines(lender: str, borrower: str, year: int) -> list[str]:
    return [
        f"Form 1098 Mortgage Interest Statement - {year}",
        f"Recipient/Lender: {lender}",
        f"Payer/Borrower: {borrower}",
        "",
        "Box 1  Mortgage interest received            $12,411.08",
        "Box 2  Outstanding mortgage principal       $342,900.00",
        "Box 5  Mortgage insurance premiums                $0.00",
        "Box 10 Real property taxes paid               $6,240.00",
    ]


def donations_xlsx(path: Path) -> None:
    wb = Workbook()
    ws = wb.active
    ws.title = "Donations"
    ws.append([f"Smith Family - Donation Receipts {YEAR}"])
    ws.append(["Date", "Organization", "Amount", "Receipt on file"])
    for i in range(1, 301):  # enough rows to clear the size minimum
        ws.append([f"0{(i % 9) + 1}/12/{YEAR}", f"Community Charity {i:03d}", 25 + i, "Yes"])
    wb.save(path)


def build_samples(samples: Path) -> None:
    samples.mkdir(parents=True, exist_ok=True)

    good = text_pdf(
        samples / f"W-2 John Smith {YEAR}.pdf",
        w2_lines("John A. Smith", "Acme Manufacturing Inc.", YEAR),
    )
    # Byte-identical duplicate — demonstrates content-hash de-duplication.
    shutil.copyfile(good, samples / f"W-2 John Smith {YEAR} - Copy.pdf")

    text_pdf(
        samples / f"W-2 Jane Smith {YEAR}.pdf",
        w2_lines("Jane R. Smith", "Lakeside Medical Group", YEAR),
    )
    # Wrong tax year — the content date check will flag it.
    text_pdf(
        samples / f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf",
        w2_lines("Jane R. Smith", "Lakeside Medical Group", PRIOR_YEAR),
    )

    text_pdf(
        samples / "1099-INT First National.pdf",
        lines_1099_int("First National Bank", "John A. Smith", YEAR),
    )
    (samples / f"1099-DIV Vanguard {YEAR}.csv").write_text(
        f"Form 1099-DIV dividend summary - Vanguard Brokerage {YEAR}\n"
        + "date,fund,ordinary dividends,qualified dividends\n" * 300,
        encoding="utf-8",
    )

    text_pdf(
        samples / f"{PRIOR_YEAR} Form 1040 Tax Return.pdf",
        prior_return_lines("John A. & Jane R. Smith", PRIOR_YEAR),
    )

    text_pdf(
        samples / "Form 1098 Mortgage Interest.pdf",
        form_1098_lines("Home Lending Corp.", "John A. & Jane R. Smith", YEAR),
    )
    (samples / "Mortgage Notes.docx").write_bytes(b"not a real docx " * 800)

    donations_xlsx(samples / f"Donation Receipts {YEAR}.xlsx")

    # Google Drive realities. A client who keeps records in Google Sheets
    # shares a .gsheet shortcut, which is a link — not the spreadsheet; the
    # scanner rejects it with export instructions rather than a size error.
    (samples / f"Donation Receipts {YEAR}.gsheet").write_text(
        '{"url": "https://docs.google.com/spreadsheets/d/1aB2cD3eF4gH5iJ6kL7mN8oP/edit",'
        ' "doc_id": "1aB2cD3eF4gH5iJ6kL7mN8oP", "email": "client@example.com"}',
        encoding="utf-8",
    )
    # A Google Drive upload caught mid-flight: ignored, never counted as a
    # delivered document, and it disappears on its own once sync finishes.
    (samples / f"W-2 Jane Smith {YEAR}.pdf.tmp.driveupload").write_bytes(b"\x00" * 4096)

    (samples / "vacation photo.jpg").write_bytes(b"\xff\xd8\xff\xe0" + b"J" * 9000)
