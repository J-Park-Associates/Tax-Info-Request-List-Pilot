"""Sample client documents for the test suite.

Real-looking W-2s, 1099s, a prior-year return, a 1098, a donations
spreadsheet, plus the things clients actually send by mistake (a duplicate,
last year's form, a Word file, a Google Sheets shortcut, a photo, a
half-uploaded temp file). Built from nothing - no fixture files in the
repository, no client data - so every test starts from the same pile.

This used to live in tracker/api.py as the marketing demo's sample builder.
The demo is gone; the suite still needs the pile.

``build_scratch_root()`` assembles the same pile into a whole clients root,
because the build workflow proves the package it just froze by running it and
a run needs somewhere real to run. That fixture lives here rather than in a
tool of its own so there is one pile, not two that can drift.
"""

from __future__ import annotations

import shutil
from contextlib import contextmanager
from pathlib import Path

from openpyxl import Workbook

from tracker.households import create_household
from tracker.layout import private_household_dir, return_dir_for
from tracker.manifest import EngagementInfo, create_engagement
from tracker.names import propose_spellings
from tracker.records import HouseholdInfo, Person
from tracker.scaffold import scaffold_engagement
from tracker.templates import BASE_YEAR, template_items

#: The rows the sample documents were written against.
DEMO_ITEMS = template_items("1040", core_only=True)
YEAR = BASE_YEAR          # the samples are dated for the catalog's base year
PRIOR_YEAR = BASE_YEAR - 1
#: The invented client one scratch root is built for. Nobody real: the pile
#: below is written from nothing, and no client document enters this repo.
SCRATCH_CLIENT = "John A. Smith"
SCRATCH_SPOUSE = "Jane R. Smith"
SCRATCH_FIRM = "Example CPA"
#: Who the pile's return is for (decision 128). The documents below are
#: addressed to these two - a W-2 to each, a joint return and a joint 1098
#: to both - so a named request files only where one of their spellings is
#: on the page, exactly as it would in the office.
SCRATCH_PEOPLE = (
    Person("taxpayer", SCRATCH_CLIENT, propose_spellings(SCRATCH_CLIENT, "taxpayer")),
    Person("spouse", SCRATCH_SPOUSE, propose_spellings(SCRATCH_SPOUSE, "spouse")),
)
#: The household and the return one scratch root holds, in the layout of
#: decision 125: a household, a year inside it, a return inside that.
SCRATCH_HOUSEHOLD = "Smith Family"
SCRATCH_RETURN = "1040 - John A. Smith"
#: The scan in the scratch root (decision 169): a page with no text layer
#: and a name that says nothing, so only the reader can file it. The
#: frozen smoke check proves the package reads it on the processor.
SCRATCH_SCAN = "scan 0001.pdf"


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


def scanned_pdf(path: Path, lines: list[str]) -> Path:
    """A scan: ``lines`` drawn on a letter page at 150 dpi and saved as a
    PDF with no text layer, so only the reader can say what it is. Every
    pixel is drawn here."""
    from PIL import Image, ImageDraw, ImageFont

    page = Image.new("RGB", (1275, 1650), "white")
    draw = ImageDraw.Draw(page)
    font = ImageFont.load_default(size=30)
    for i, line in enumerate(lines[:28]):
        draw.text((80, 90 + 52 * i), line, font=font, fill="black")
    page.save(path, "PDF", resolution=150)
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


# ------------------------------------------- one page, several forms ----
#
# Decision 94's pile: the sheets that come out of a client's scanner when
# they feed it a stack. Each block is one real form as the IRS prints it -
# its number at the head of a line with its printed title and its year
# after it, which is what ``content_check.self_named_forms`` reads - and a
# block is a page's worth of boxes long, so two of them are never inside
# one title window. Two blocks inside one window would be a menu
# (decision 73), and that is the checklist below, which must go on
# parking.


def scanned_w2_lines(year: int) -> list[str]:
    """A whole W-2 as a page: the self-naming line and enough of the boxes
    that whatever follows is past the title window."""
    return [
        f"Form W-2 Wage and Tax Statement {year}",
        "a Employee's social security number 123-45-6789",
        "b Employer identification number (EIN) 94-1234567",
        "c Employer's name, address, and ZIP code",
        "Willow Lane Bakery LLC 1200 Market Street Springfield IL 62704",
        "e Employee's first name and initial Last name Suff.",
        "f Employee's address and ZIP code",
        "1 Wages, tips, other compensation 64,200.00 2 Federal income tax withheld 7,140.00",
        "3 Social security wages 64,200.00 4 Social security tax withheld 3,980.40",
        "5 Medicare wages and tips 64,200.00 6 Medicare tax withheld 931.00",
        "15 State Employer's state ID number 16 State wages, tips, etc. 17 State income tax",
        "Copy B To Be Filed With Employee's FEDERAL Tax Return",
    ]


def scanned_1099_int_lines(year: int) -> list[str]:
    """A whole 1099-INT as a page, printed the way a payer prints it."""
    return [
        f"Form 1099-INT Interest Income {year}",
        "PAYER'S name street address city or town state or province country ZIP",
        "Harborline Savings Bank 88 Quay Road Springfield IL 62704",
        "PAYER'S TIN RECIPIENT'S TIN RECIPIENT'S name",
        "1 Interest income 1,842.17",
        "4 Federal income tax withheld 0.00",
        "This is important tax information and is being furnished to the IRS.",
    ]


def scanned_1098_lines(year: int) -> list[str]:
    """A whole 1098 as a page."""
    return [
        f"Form 1098 Mortgage Interest Statement {year}",
        "RECIPIENT'S/LENDER'S name street address city or town state ZIP",
        "Cedar Ridge Mortgage Company 410 Vine Street Springfield IL 62704",
        "1 Mortgage interest received from payer(s)/borrower(s) 12,411.08",
        "2 Outstanding mortgage principal 342,900.00",
    ]


def brokerage_cover_lines(year: int) -> list[str]:
    """A page that names no form at all and that a row keyed on a phrase
    would nonetheless accept - the row decision 94 refuses to split on."""
    return [
        f"Harborline Savings Bank - brokerage statement for the year {year}",
        "Account 8812-4455 Ending balance 40,000.00",
    ]


def sheet_xlsx(path: Path, rows: list[list]) -> Path:
    """A workbook whose first sheet holds ``rows``, one list per row.

    Half of every catalog asks for a bookkeeping export or a schedule, and
    those arrive as workbooks: a case typed as lines of text cannot stand
    in for one, because a sheet is read differently. A row is a line and
    its cells are set apart by a tab (``content_check._extract_xlsx``), so
    a phrase that runs across two cells is one phrase and a phrase that
    runs down two rows is two labels - which is the whole point of the
    rule decision 66 wrote. ``tests/test_catalog.py`` routes its workbook
    cases through this.
    """
    wb = Workbook()
    ws = wb.active
    for row in rows:
        ws.append(list(row))
    wb.save(path)
    return path


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
    # A broker's year-end summary carries the account holder's name at the
    # head of it, the way every real one does - which is why the catalog
    # marks the 1099 row named (decision 128).
    (samples / f"1099-DIV Vanguard {YEAR}.csv").write_text(
        f"Form 1099-DIV dividend summary - Vanguard Brokerage {YEAR}\n"
        f"Recipient,{SCRATCH_CLIENT}\n"
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

    # A file no request accepts, whatever its whitelist says. It was a .jpg
    # until decision 127 made a photo a document: a JPEG is now accepted
    # wherever a PDF is, so the pile keeps a bitmap instead - the same
    # claim (a drop no row takes parks with an empty shortlist) about a
    # file type the tracker still has no use for.
    (samples / "vacation photo.bmp").write_bytes(b"BM" + b"J" * 9000)


def build_scratch_root(root: Path | str) -> Path:
    """A throwaway clients root holding one household with one scaffolded
    return, the whole pile already waiting in the household's inbox, and
    the root returned.

    The build workflow proves the package it has just frozen by running the
    frozen executable, and a pass over an empty folder proves only that
    discovery does not crash. This gives it something to walk: the two
    trees of decision 125, the catalog's core rows, the folders the
    scaffold makes, and the documents a client really sends - one that
    routes, its byte-identical copy, last year's form, a Google shortcut,
    a photo, and a scan only the reader can file (:data:`SCRATCH_SCAN`) - so
    a single dry pass goes through filing, routing, reading, scanning and
    drafting the way the scheduled job does.

    Nothing outside ``root`` is written, and nothing in it is a real
    client's: every byte comes from ``build_samples()`` above.
    """
    root = Path(root)
    # The API's own creates, not the suite's helper: the build workflow
    # imports this module without conftest.
    household = private_household_dir(root, SCRATCH_HOUSEHOLD)
    household.mkdir(parents=True, exist_ok=True)
    create_household(household, HouseholdInfo(name=SCRATCH_HOUSEHOLD, contact=SCRATCH_CLIENT))
    engagement = return_dir_for(root, SCRATCH_HOUSEHOLD, YEAR, SCRATCH_RETURN)
    engagement.mkdir(parents=True, exist_ok=True)
    create_engagement(engagement, DEMO_ITEMS, EngagementInfo(
        client=SCRATCH_CLIENT, firm=SCRATCH_FIRM, household=SCRATCH_HOUSEHOLD,
        tax_year=YEAR, return_name=SCRATCH_RETURN, people=SCRATCH_PEOPLE))
    inbox = scaffold_engagement(engagement).inbox
    build_samples(inbox)
    # A W-2 as a scanner hands it over. A box's label and its figure are
    # laid out apart on a form, and drawn as separate lines here, so the
    # reader's words are the form's (a figure run into a label reads as one
    # word, which no keyword matches).
    scanned_pdf(inbox / SCRATCH_SCAN,
                [part for line in w2_lines(SCRATCH_CLIENT, "Northwind Traders", YEAR)
                 for part in line.split("  ", 1) if part.strip()])
    return root


@contextmanager
def listing_denied(folder: Path):
    """``folder`` made unlistable for the running account, the way an ACL a
    client's folder carried in from elsewhere denies a scheduled run - a
    real denial, because ``rglob`` and ``os.walk`` reach the file system
    by different calls and a monkeypatch of one proves nothing about the
    other. Skips where the account cannot be denied (root on POSIX)."""
    import os
    import subprocess
    import sys

    import pytest

    if sys.platform == "win32":
        user = os.environ.get("USERNAME", "")
        if subprocess.run(["icacls", str(folder), "/deny", f"{user}:(RD)"], capture_output=True).returncode:
            pytest.skip("icacls could not deny the folder")
        try:
            yield
        finally:
            subprocess.run(["icacls", str(folder), "/remove:d", user], capture_output=True)
    else:
        if os.geteuid() == 0:
            pytest.skip("root cannot be denied a folder")
        folder.chmod(0)
        try:
            yield
        finally:
            folder.chmod(0o700)


# ------------------------------------------- an email's own file (decision 143) ----
# Outlook saves an email as a compound file (CFB, [MS-CFB]), and nothing in
# the standard library writes one; ``olefile`` only reads. So the suite's
# ``.msg`` fixtures are written here, from nothing, to the letter of the
# format: version 3, 512-byte sectors, streams under 4096 bytes in the mini
# stream, every sector on the FAT. Small on purpose - one FAT sector's worth
# of file is all a test needs, and the writer refuses anything larger.

_FREE, _END, _FATSECT, _NOSTREAM = 0xFFFFFFFF, 0xFFFFFFFE, 0xFFFFFFFD, 0xFFFFFFFF
_SECTOR, _MINI, _CUTOFF = 512, 64, 4096


def cfb_bytes(tree: dict) -> bytes:
    """A compound file holding ``tree``: a name maps to bytes (a stream) or
    to a dict (a storage), nested as deep as the test likes."""
    import struct

    entries: list[dict] = [{"name": "Root Entry", "type": 5, "data": b"", "kids": []}]

    def add(node: dict, into: int) -> None:
        for name, value in node.items():
            entries.append({"name": name, "type": 1 if isinstance(value, dict) else 2,
                            "data": b"" if isinstance(value, dict) else bytes(value), "kids": []})
            index = len(entries) - 1
            entries[into]["kids"].append(index)
            if isinstance(value, dict):
                add(value, index)

    add(tree, 0)
    sectors: list[bytes] = []
    fat: list[int] = []

    def chain(data: bytes) -> int:
        count = -(-len(data) // _SECTOR)
        start = len(sectors)
        for n in range(count):
            sectors.append(data[n * _SECTOR:(n + 1) * _SECTOR].ljust(_SECTOR, b"\0"))
            fat.append(start + n + 1 if n < count - 1 else _END)
        return start

    mini = bytearray()
    minifat: list[int] = []
    for entry in entries[1:]:
        data = entry["data"]
        if entry["type"] != 2 or not data:
            entry["start"] = _END if entry["type"] == 2 else 0
            continue
        if len(data) >= _CUTOFF:
            entry["start"] = chain(data)
            continue
        count = -(-len(data) // _MINI)
        entry["start"] = len(minifat)
        for n in range(count):
            minifat.append(len(minifat) + 1 if n < count - 1 else _END)
        mini += data.ljust(count * _MINI, b"\0")
    entries[0]["start"] = chain(bytes(mini)) if mini else _END
    entries[0]["size"] = len(mini)
    minifat_start = (chain(b"".join(struct.pack("<I", n) for n in minifat)
                           .ljust(-(-len(minifat) * 4 // _SECTOR) * _SECTOR, b"\xff"))
                     if minifat else _END)
    minifat_count = -(-len(minifat) * 4 // _SECTOR)
    for entry in entries:
        entry.setdefault("size", len(entry["data"]))
        entry["left"] = entry["right"] = entry["child"] = _NOSTREAM
    for entry in entries:
        kids = entry["kids"]
        if kids:
            entry["child"] = kids[0]
            for this, following in zip(kids, kids[1:], strict=False):
                entries[this]["right"] = following
    directory = bytearray()
    for entry in entries:
        name = entry["name"].encode("utf-16-le") + b"\0\0"
        assert len(name) <= 64, entry["name"]
        directory += struct.pack(
            "<64sHBBIII16sIQQIQ", name, len(name), entry["type"], 1, entry["left"],
            entry["right"], entry["child"], b"\0" * 16, 0, 0, 0, entry["start"], entry["size"])
    while len(directory) % _SECTOR:
        directory += struct.pack("<64sHBBIII16sIQQIQ", b"", 0, 0, 0, _NOSTREAM, _NOSTREAM,
                                 _NOSTREAM, b"\0" * 16, 0, 0, 0, 0, 0)
    directory_start = chain(bytes(directory))
    fat_count = 1
    while fat_count * (_SECTOR // 4) < len(sectors) + fat_count:
        fat_count += 1
    assert fat_count <= 109, "a test's compound file is one DIFAT's worth at most"
    fat_start = len(sectors)
    fat += [_FATSECT] * fat_count
    fat += [_FREE] * (fat_count * (_SECTOR // 4) - len(fat))
    table = b"".join(struct.pack("<I", n) for n in fat)
    sectors += [table[n * _SECTOR:(n + 1) * _SECTOR] for n in range(fat_count)]
    difat = [fat_start + n for n in range(fat_count)] + [_FREE] * (109 - fat_count)
    header = struct.pack(
        "<8s16sHHHHH6sIIIIIIIII", bytes.fromhex("D0CF11E0A1B11AE1"), b"\0" * 16, 0x3E, 3,
        0xFFFE, 9, 6, b"\0" * 6, 0, fat_count, directory_start, 0, _CUTOFF,
        minifat_start, minifat_count, _END, 0,
    ) + b"".join(struct.pack("<I", n) for n in difat)
    assert len(header) == _SECTOR
    return header + b"".join(sectors)


def _msg_properties(method: int, hidden: bool, flags: int) -> bytes:
    """An attachment's properties stream: 8 reserved bytes, then 16-byte
    entries - the method (PT_LONG), hidden (PT_BOOLEAN) and flags (PT_LONG)."""
    import struct

    def prop(prop_id: int, kind: int, value: int) -> bytes:
        return struct.pack("<IIQ", (prop_id << 16) | kind, 6, value)

    return (b"\0" * 8 + prop(0x3705, 0x0003, method) + prop(0x7FFE, 0x000B, int(hidden))
            + prop(0x3714, 0x0003, flags))


def msg_storage(attachments: list[dict]) -> dict:
    """The storages of one message holding ``attachments``: each a dict with
    ``name`` and ``data``, and optionally ``method`` (1 by value, 5 an
    embedded message whose own ``attachments`` are given), ``hidden`` and
    ``flags``."""
    tree: dict = {"__properties_version1.0": b"\0" * 32}
    for n, one in enumerate(attachments):
        method = one.get("method", 1)
        storage: dict = {"__properties_version1.0": _msg_properties(
            method, one.get("hidden", False), one.get("flags", 0))}
        if one.get("name"):
            storage["__substg1.0_3707001F"] = one["name"].encode("utf-16-le")
        if method == 5:
            storage["__substg1.0_3701000D"] = msg_storage(one.get("attachments", []))
        elif "data" in one:
            storage["__substg1.0_37010102"] = one["data"]
        tree[f"__attach_version1.0_#{n:08X}"] = storage
    return tree


def msg_bytes(attachments: list[dict]) -> bytes:
    """A minimal Outlook ``.msg`` holding ``attachments`` (see
    :func:`msg_storage`): a message body stream and its attachments."""
    tree = msg_storage(attachments)
    tree["__substg1.0_1000001F"] = "Please find attached.".encode("utf-16-le")
    return cfb_bytes(tree)
