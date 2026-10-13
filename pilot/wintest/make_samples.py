"""Build the sandbox clients folder for the pilot's Windows check (P28).

The check is driven by Claude, which sees the screen, and generative AI
never reads a client document - so the only documents in play are the
made-up ones the suite's own fixtures build (``tests/samples.py``): one
household, one return, and a pile of fake documents waiting in its
"Drop files here" inbox. The folder is refused anywhere but under
``%USERPROFILE%\\PilotTest``, and an existing non-empty folder is refused
rather than mixed into, so a mistyped path can never write among real files.

It never writes the app's real data folder (F7, P193, R3). Building the
samples writes each return's record and the engine's store and checkpoint;
on 9/29 the script ran from inside the Claude desktop app, which Windows
redirects, and became the first writer of a private copy of the data folder
the app later read instead of the real one. So it builds under a throwaway
``TRACKER_DATA_HOME`` (a temporary folder, removed afterwards), and keeps
nothing of the engine's but the records inside the sample folder: the app's
first read seeds its checkpoint from those records, as it does for any
return it sees for the first time.

Three more made-up files are added to the inbox after the suite's pile is
built, so the suite's own pile, and every count its tests pin, is untouched
(SPEC-mac-check-fixes section 3.2, P258). They are the kinds of file the
pilot treats with care and the suite's pile does not hold:

* ``Donation Receipts {YEAR} with macros.xlsm`` - a workbook under a macro
  workbook's name and declared type (no macro inside; the suffix is all
  ``filer.bears_macros`` reads), so a review copy can be marked for Protected View on Windows, and
  the Mac check can show its sentence that there is none (SPEC-mac step 10);
* ``Email from John Smith.msg`` - an Outlook message holding one made-up
  1099-INT PDF from a payer the pile does not hold, the email path and its
  "Came in Email" word;
* ``Scanned forms.zip`` - a zip holding one made-up scan, the zip path.

Run from the repository root with the checkout's virtual environment:
    .venv\\Scripts\\python.exe pilot\\wintest\\make_samples.py [target]
"""

from __future__ import annotations

import logging
import os
import sys
import tempfile
import zipfile
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
SANDBOX_PARENT = Path.home() / "PilotTest"


MACRO_WORKBOOK = "Donation Receipts {year} with macros.xlsm"
EMAIL_SAMPLE = "Email from John Smith.msg"
ZIP_SAMPLE = "Scanned forms.zip"
#: The zip's own member date, fixed so the archive does not carry the build's
#: clock. The members' bytes are not still: PIL stamps the scan's
#: ``/CreationDate`` and openpyxl stamps the workbook, so two builds differ.
ZIP_STAMP = (2025, 1, 1, 0, 0, 0)
#: The workbook part's content type in a macro-enabled workbook. Excel refuses
#: a file whose suffix and declared type disagree, and openpyxl declares the
#: plain workbook's type unless it is given a VBA archive.
MACRO_MAIN_TYPE = "application/vnd.ms-excel.sheet.macroEnabled.main+xml"
PLAIN_MAIN_TYPE = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"


def _declare_macro_workbook(path: Path) -> None:
    """Rewrite the archive at ``path`` so ``[Content_Types].xml`` declares the
    workbook part as a macro-enabled workbook's main part. Nothing else in the
    archive changes, and no macro is added."""
    with zipfile.ZipFile(path) as source:
        members = [(info, source.read(info)) for info in source.infolist()]
    with zipfile.ZipFile(path, "w") as target:
        for info, data in members:
            if info.filename == "[Content_Types].xml":
                declared = data.decode("utf-8")
                if PLAIN_MAIN_TYPE not in declared:
                    raise RuntimeError(f"{path.name}: no workbook part to declare as macro-enabled")
                data = declared.replace(PLAIN_MAIN_TYPE, MACRO_MAIN_TYPE).encode("utf-8")
            target.writestr(info, data, compress_type=info.compress_type)


def add_container_samples(inbox: Path) -> list[Path]:
    """Add the macro workbook, the email and the zip to ``inbox`` (SPEC-mac-
    check-fixes 3.2), each made from the suite's own fixtures and made-up data
    only, and return the three paths. Written after the suite's pile so that
    pile is exactly what ``build_samples`` makes.

    The workbook is the donations sheet under the ``.xlsm`` name, its content
    type rewritten to match: a zip of parts with no macro in it. The suffix is
    what the filer marks a copy by, and a macro-free file is the safe way to
    walk the step. The message holds a text 1099-INT from a payer the pile
    does not hold, so it is filed as a document of its own and not parked as a
    duplicate, and the zip a scanned one, so each container opens to a
    document the engine can read.
    """
    from samples import YEAR, donations_xlsx, lines_1099_int, msg_bytes, scanned_pdf, text_pdf

    workbook = inbox / MACRO_WORKBOOK.format(year=YEAR)
    donations_xlsx(workbook)
    _declare_macro_workbook(workbook)
    with tempfile.TemporaryDirectory(prefix="pilot-containers-") as scratch:
        text = text_pdf(Path(scratch) / "text.pdf", lines_1099_int("Riverside Savings Bank", "John A. Smith", YEAR),
                        style="padded")
        scan = scanned_pdf(Path(scratch) / "scan.pdf", lines_1099_int("Lakeside Credit Union", "Jane R. Smith", YEAR))
        email = inbox / EMAIL_SAMPLE
        email.write_bytes(msg_bytes([{"name": "1099-INT Riverside Savings Bank.pdf", "data": text.read_bytes()}]))
        archive = inbox / ZIP_SAMPLE
        member = zipfile.ZipInfo("scan 0002.pdf", ZIP_STAMP)
        member.compress_type = zipfile.ZIP_DEFLATED
        with zipfile.ZipFile(archive, "w") as bundle:
            bundle.writestr(member, scan.read_bytes())
    return [workbook, email, archive]


def main(argv: list[str]) -> int:
    target = Path(argv[0]) if argv else SANDBOX_PARENT / "Clients"
    target = target.resolve()
    if SANDBOX_PARENT.resolve() not in target.parents:
        print(f"Refused: {target} is not inside {SANDBOX_PARENT}. The sample folder lives only there.")
        return 2
    if target.exists() and any(target.iterdir()):
        print(f"Refused: {target} already holds files. Delete it first for a fresh sample set.")
        return 2
    sys.path.insert(0, str(REPO))
    sys.path.insert(0, str(REPO / "tests"))
    from samples import build_scratch_root  # the suite's own fake documents

    from tracker import store
    from tracker.settings import ENV_DATA_HOME

    os.environ.pop(store.ENV_STORE, None)           # a named store would be written, not the throwaway one
    with tempfile.TemporaryDirectory(prefix="pilot-samples-") as throwaway:
        os.environ[ENV_DATA_HOME] = throwaway
        try:
            root = build_scratch_root(target)
        finally:
            store.close()                           # Windows cannot remove an open database
            logging.shutdown()                      # nor an open error log
            del os.environ[ENV_DATA_HOME]
    inboxes = [p for p in root.rglob("*") if p.is_dir() and p.name == "Drop files here"]
    for inbox in inboxes:
        add_container_samples(inbox)
    count = sum(1 for inbox in inboxes for f in inbox.rglob("*") if f.is_file())
    if not inboxes or count == 0:
        print(f"Failed: no sample documents were made under {root}.")
        return 1
    print(f"Sample clients folder: {root}")
    print(f"Fake documents waiting in 'Drop files here': {count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
