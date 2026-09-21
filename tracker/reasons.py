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

Not every cause is a validation note. :data:`NO_READABLE_TEXT` and
:data:`ISSUER_NOT_NAMED` are the router's, written into the index's Reason
column rather than into a request's notes, and they are worded here for the
same reason the rest are: one sentence, one owner, and a marker the index,
the review queue and the status report all recognise without retyping a
word of it. :data:`FILE_MOVED` and :data:`COPY_CHANGED` are a third kind
again (decision 109): the scanner writes them into a request's notes, but
it does not decide them - it reads them off the rows the filer's sweep of
the working copies recorded, so what the fingerprint identified and what a
person is told are one sentence apart. :data:`INTERRUPTED_MOVE` and
:data:`INTERRUPTED_MOVE_LOST` (decision 119) are of that kind too: the
filer's recovery writes them onto the row it could not finish as decided,
and the scanner says them of the request whose folder the file was going
into.

And not every sentence here is a cause at all. :data:`NAMES_SEVERAL_FORMS`
is what the index says when a document *was* filed - under several
requests at once (decision 94) - and :data:`SEVERAL_FORMS_UNSORTED` when
that same page would not sort. They are plain templates rather than
:class:`Reason`\\ s, and deliberately outside ``ALL``: the reminder asks
``ALL`` what to tell a client about a failure, and a document that filed
is not one.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

#: How the scanner prefixes a failure with the file it is about
#: (``"name.pdf: reason"``). A marker is looked for in the reasons, never in
#: a file name: a client who names a file "Not allowed deductions.pdf" has
#: not been told the file type is not allowed.
_FILE_PREFIX = re.compile(r"(^|; )[^;]*?\.[a-z0-9]{1,5}: ", re.IGNORECASE)


def reasons_in(note: str) -> str:
    """``note`` with each failure's file-name prefix removed."""
    return _FILE_PREFIX.sub(lambda m: m.group(1), note or "")

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
        return self.marker.lower() in reasons_in(note).lower()

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
    "content rules cannot be checked", firm_side=True,
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
OCR_FAILED = Reason(
    "ocr-failed", "OCR failed on this file ({error}); will try again next run",
    "OCR failed", firm_side=True,
)

# ---- routing: what the router could not do ---------------------------------

#: No word of the document could be read - a scan with no text layer and no
#: OCR on this machine, an image-only PDF, a sheet with nothing in it - so
#: the only thing left is the file's own name, and a name is the client's
#: word for what a document is, never the document's (decision 40). Owner,
#: 2026-09-18: a document nobody can read is filed by nobody. Deliberately
#: not "matched no request", which says the words were read and no request
#: asked for them: the fix here is OCR or a person, never a keyword.
NO_READABLE_TEXT = Reason(
    "unreadable",
    "nothing in this file could be read, so only its name says what it is; "
    "a scan needs OCR before it can be filed",
    "nothing in this file could be read", firm_side=True,
    firm_note="nothing in it could be read here, so nobody has identified it yet; "
              "OCR or a person, never the client",
)

#: The request list asks for this document one row per issuer - a Schedule
#: K-1 per entity that issued one (decision 93, the owner's) - the broad
#: row accepted the document, and no issuer row did. Filing it on the broad
#: row would put two entities' K-1s in one folder, which is the thing the
#: issuer rows exist to stop; picking the issuer row that is left over
#: would be guessing by elimination, and a document is filed only when
#: exactly one request accepts it. So it parks, named: a person files it,
#: or adds the row for the issuer the client did not tell us about.
#: Ours, never the client's - they sent the right document.
ISSUER_NOT_NAMED = Reason(
    "issuer-not-named",
    "this request list asks for this document one row per issuer ({listed}) "
    "and this one names none of them; a person should file it, or add the "
    "row for its issuer",
    "names none of them", firm_side=True,
    firm_note="the list asks for this one by issuer and the document names none of "
              "the issuers on it; a person here files it or adds the row",
)

#: The record says this row's working copy is at one path and the pass
#: found its bytes at another (decision 109). Nothing was moved to find
#: that out and nothing is moved because of it: the fingerprint identifies,
#: and a person decides with the three answers the app offers. Firm-side,
#: always: the client sent the document and somebody here dragged the copy,
#: so a draft that asked them for it would be asking for a file the firm
#: mislaid.
FILE_MOVED = Reason(
    "file-moved",
    "the working copy {listed} is not where the record put it; a person decides - "
    "put it back, keep it where it is, or send it to review",
    "not where the record put it", firm_side=True,
    firm_note="a working copy here was moved by hand; a person here puts it back, keeps it, "
              "or sends it to review - never the client",
)
#: A path the record claims holds bytes that are not the ones recorded on
#: the row (decision 109, extending decision 3). The request keeps the
#: status its files earn - the newcomer may pass every rule - and this says
#: the file is not the one the record filed there, which no count can say.
COPY_CHANGED = Reason(
    "copy-changed",
    "the file at {listed} is not the one the record filed there; a person should look "
    "before trusting it",
    "not the one the record filed there", firm_side=True,
    firm_note="a working copy here no longer holds the bytes the record filed; a person "
              "here looks - never the client",
)

#: A run died between one of its file operations and the record of them,
#: and what it was about to do could not be finished as it was decided
#: (decision 119): the place the file was going holds a different file
#: now. Nothing there is touched - it is somebody's, and the machine never
#: deletes what it finds - so the row parks with a working copy of its own
#: and this says why. Firm-side, always: the client sent the document, and
#: a power cut here is not theirs to answer for.
INTERRUPTED_MOVE = Reason(
    "interrupted-move",
    "an interrupted step meant to put {listed}; a person should look",
    "an interrupted step meant to put", firm_side=True,
    firm_note="a step interrupted here was putting a working copy somewhere that now holds "
              "a different file; a person here looks - never the client",
)
#: The same interrupted step, where neither the place it was taking the
#: file from nor the place it was taking it to holds those bytes now
#: (decision 119). Nothing is guessed from that: the row parks and the
#: sentence says whether the client's own original is still there.
INTERRUPTED_MOVE_LOST = Reason(
    "interrupted-move-lost",
    "an interrupted step was moving {listed}; a person should look",
    "an interrupted step was moving", firm_side=True,
    firm_note="a step interrupted here was moving a working copy and neither end of it holds "
              "those bytes now; a person here looks - never the client",
)

#: One page, several forms (decision 94, the owner's). Neither of these is
#: a refusal, so neither is a :class:`Reason` and neither is in ``ALL``:
#: they are what the index's Reason column says about a document that
#: printed more than one form's own name, and they are worded here for the
#: reason the refusals are - one sentence, one owner, and a wording the
#: index, the status report and the runbook's reason table all quote
#: instead of retyping.
#:
#: Counts and identifiers only. What the *page* said is never in here: a
#: form number read off a client's document is a word of that document,
#: and the index's sentences carry the firm's words and the client's file
#: names, never the document's (the same line :class:`Evidence` draws).
NAMES_SEVERAL_FORMS = (
    "names {n} forms as itself, each asked for by exactly one request ({listed}); "
    "a copy is filed under each"
)
#: The same page where the forms will not sort one to a request: a form no
#: request asks for, two requests wanting one form, or a request accepted
#: on a phrase that names no form at all. The whole page parks - filing
#: the half that does sort would put the other half somewhere nobody will
#: look for it. Said inside the router's contested sentence, so a person
#: reads the shortlist they already know how to read.
SEVERAL_FORMS_UNSORTED = "it names {n} forms as itself and they do not sort one to a request"

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
    UNCHECKABLE_TYPE, NO_TEXT_LAYER, NO_TEXT_AFTER_OCR, OCR_FAILED, NO_READABLE_TEXT,
    ISSUER_NOT_NAMED,
    FILE_MOVED, COPY_CHANGED, INTERRUPTED_MOVE, INTERRUPTED_MOVE_LOST,
    PENDING_SYNC, VANISHED,
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
