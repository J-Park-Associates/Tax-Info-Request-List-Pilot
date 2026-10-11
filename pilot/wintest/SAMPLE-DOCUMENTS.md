# The sample documents

`Pilot-Sample-Documents.zip` holds 14 of the made-up documents the Windows check
uses. They are the same files that `make_samples.py` puts in the sample
household's "Drop files here" folder. Every byte comes from the suite's own
fixtures in `tests/samples.py`, so no real client's data is in them.

| File | What it tests |
|---|---|
| `W-2 John Smith 2025.pdf`, `W-2 Jane Smith 2025.pdf` | Routine filing to the W-2 requests. |
| `W-2 John Smith 2025 - Copy.pdf` | A byte-for-byte duplicate. |
| `W-2 Jane Smith 2024 - old.pdf` | Last year's form. |
| `1099-INT First National.pdf` | A 1099-INT. |
| `1099-DIV Vanguard 2025.csv` | A 1099-DIV sent as a spreadsheet export. |
| `Form 1098 Mortgage Interest.pdf` | A 1098. |
| `2024 Form 1040 Tax Return.pdf` | The prior-year return. |
| `Donation Receipts 2025.xlsx` | A spreadsheet. |
| `Donation Receipts 2025.gsheet` | A Google shortcut, not a real file. |
| `Mortgage Notes.docx` | A document no request asks for. |
| `W-2 Jane Smith 2025.pdf.tmp.driveupload` | A half-finished upload. |
| `vacation photo.bmp` | A photo that is not a tax document. |
| `scan 0001.pdf` | A scanned W-2 that only the page reader can file. |

`make_samples.py` also adds three files the zip does not hold (P258): `Donation Receipts 2025 with
macros.xlsm` (a workbook under a macro workbook's name, no macro inside), `Email from John Smith.msg` (an
email holding one made-up PDF) and `Scanned forms.zip` (a zip holding one made-up scan), so the kit's inbox
holds 17 files.

The kit builds the full sample clients folder itself, with the household, the
return and these files in its inbox. The zip is there to look at, or to drop
in by hand.
