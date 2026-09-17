"""Why a file was refused, said once (component 14).

Every sentence the validators, the content check and the scanner write into
Validation Notes used to be typed where it was produced, and the reminder
then recognised it by a substring typed again in reminder.py. Rewording a
producer silently changed what the client was asked for - or turned "a
person here has not read it yet" into a request to the client - with no
test failing at either end.

Each :class:`Reason` here is the one definition of one cause: the sentence
the scanner writes (a template, since most carry a detail), the marker the
reminder recognises it by (a literal part of that template, checked by the
suite), the plain sentence the client is asked with, and whether the row is
the firm's to look at rather than the client's to fix. Producers call
``REASON.format(...)``; the reminder consults the same objects. There is
nothing to keep in step.
"""

from __future__ import annotations

from dataclasses import dataclass

#: Shown to the client when a failure has no recognised cause. Deliberately
#: vague about our rules and specific about what the client should do.
GENERIC_ASK = "we could not read the file that arrived; please send it again"

#: The one firm-side sentence: the row is ours to look at, not the client's.
FIRM_WAITING = "waiting on a person here to read it, not on the client"
FIRM_WAITING_PARTIAL = ("some of what arrived is waiting on a person here to "
                        "read it; confirm before asking for more")


@dataclass(frozen=True, slots=True)
class Reason:
    """One cause: what the scanner writes, what the client is asked, whose problem it is."""

    code: str
    template: str      # the note as written; {placeholders} carry the detail
    marker: str        # a literal part of the template the reminder keys on
    ask: str = ""      # the client-facing sentence; "" means GENERIC_ASK
    firm_side: bool = False   # True: waiting on a person here, never put to the client
    firm_note: str = ""       # what the firm is told instead; "" means FIRM_WAITING

    def format(self, **detail: object) -> str:
        return self.template.format(**detail)

    def matches(self, note: str) -> bool:
        return self.marker.lower() in (note or "").lower()

    @property
    def client_ask(self) -> str:
        return self.ask or GENERIC_ASK

    @property
    def firm_side_note(self) -> str:
        return self.firm_note or FIRM_WAITING


#: How a client turns a Google Docs/Sheets shortcut into a document we can
#: read. Said once: the note, the ask and the folder README all quote it.
GOOGLE_EXPORT_HINT = "File > Download > PDF or Excel"

# ---- tier 2: the file itself -----------------------------------------------

PASSWORD_PROTECTED = Reason(
    "password", "PDF is password-protected; please ask the client for an unlocked copy",
    "password-protected", "the file is password-protected; please send an unlocked copy",
)
NO_PAGES = Reason("no-pages", "PDF contains no pages", "contains no pages")
UNREADABLE_PDF = Reason("unreadable-pdf", "not a readable PDF ({error})", "not a readable PDF")
GOOGLE_STUB = Reason(
    "google-stub",
    ".{extension} is a Google Docs shortcut, not the document itself; "
    f"ask the client to download it ({GOOGLE_EXPORT_HINT}) and upload that copy",
    "Google Docs shortcut",
    "that was a Google Docs/Sheets shortcut rather than the document itself; "
    f"please download it ({GOOGLE_EXPORT_HINT}) and send that copy",
)
EXTENSION_NOT_ALLOWED = Reason(
    "extension", "extension .{extension} not allowed (expected: {allowed})", "not allowed",
    "we cannot open that file type; please send it as a PDF or an Excel file",
)
TOO_SMALL = Reason(
    "too-small",
    "file is {size_kb:.1f} KB, below the {minimum} KB minimum; possible placeholder or failed upload",
    "possible placeholder or failed upload",
    "the file arrived almost empty, so the upload may not have finished; please send it again",
)
PENDING_SYNC = Reason(
    "pending-sync", "cloud-only placeholder; waiting for OneDrive/Google Drive to sync",
    "cloud-only placeholder", firm_side=True,
)
VANISHED = Reason(
    "vanished", "file disappeared during the scan ({error}); will re-check next run",
    "disappeared during the scan", firm_side=True,
)

# ---- tier 3: what the document says ----------------------------------------

WRONG_DOCUMENT = Reason(
    "wrong-document", "required keyword(s) {listed} not found; possible wrong document",
    "possible wrong document",
    "the document that arrived does not look like this item; please check that the right file was sent",
)
NO_EXPECTED_KEYWORD = Reason(
    "no-keyword", "none of the expected keywords found ({listed})",
    "none of the expected keywords found",
    "the document that arrived does not look like this item; please check that the right file was sent",
)
WRONG_PERIOD = Reason(
    "wrong-period", "expected period not found (pattern: {pattern}); possible wrong period",
    "possible wrong period",
    "the document that arrived appears to cover a different period; please check the year",
)
EXTRACTION_FAILED = Reason(
    "extraction-failed", "text extraction failed ({error})", "text extraction failed",
)
UNCHECKABLE_TYPE = Reason(
    "uncheckable-type", "content rules cannot be checked on .{extension} files; review manually",
    "review manually", firm_side=True,
)
NO_TEXT_LAYER = Reason(
    "no-text-layer",
    "PDF appears to be a scan with no text layer and OCR is not installed; review manually",
    "no text layer", firm_side=True,
)
NO_TEXT_AFTER_OCR = Reason(
    "no-text-after-ocr", "no readable text found in PDF, even after OCR; review manually",
    "no readable text", firm_side=True,
)

# ---- the folder ---------------------------------------------------------------

NO_REQUEST_FOLDER = Reason(
    "no-folder", "request folder not found; the next pass creates it", "request folder not found",
    firm_side=True,
    firm_note="no request folder, so nothing could be filed here; the next pass creates it",
)

#: Every reason, in the order the reminder tries them: the specific causes
#: before the vague ones, so a note carrying two markers gets the better ask.
ALL: tuple[Reason, ...] = (
    PASSWORD_PROTECTED, GOOGLE_STUB, TOO_SMALL, EXTENSION_NOT_ALLOWED,
    WRONG_DOCUMENT, NO_EXPECTED_KEYWORD, WRONG_PERIOD,
    NO_PAGES, UNREADABLE_PDF, EXTRACTION_FAILED,
    UNCHECKABLE_TYPE, NO_TEXT_LAYER, NO_TEXT_AFTER_OCR, PENDING_SYNC, VANISHED,
    NO_REQUEST_FOLDER,
)

#: Reasons that mean "a person here has not looked yet", never a client ask.
FIRM_SIDE: tuple[Reason, ...] = tuple(r for r in ALL if r.firm_side)


def find(note: str) -> Reason | None:
    """The first reason whose marker appears in ``note``, or None."""
    for reason in ALL:
        if reason.matches(note):
            return reason
    return None
