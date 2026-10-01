"""Why a file was refused, said once (component 14).

Every sentence the validators, the content check and the scanner write into
Validation Notes used to be typed where it was produced, and the reminder
then recognised it by a substring typed again in reminder.py. Rewording a
producer silently changed what the client was asked for - or turned "a
person here has not read it yet" into a request to the client - with no
test failing at either end.

Each :class:`Reason` here is the one definition of one cause: its code,
the sentence the scanner writes (a template, since most carry a detail),
the plain sentence the client is asked with, whether the row is the firm's
to look at rather than the client's to fix, and - its own answer since
decision 140 - whether a parked file carrying it holds the client's
reminder. Producers call ``REASON.format(...)``; the reminder consults the
same objects. There is nothing to keep in step.

**Codes are columns (decision 190).** Until then the reminder and the
review card found a row's cause by searching its sentence for a marker.
The sentence carries what the client chose - a file's name, a subfolder's
name, a parser's words - so a subfolder called "not allowed" turned a
password-protected PDF into a file-type ask, and quoting the client's text
(SPEC-167) only moved the problem. The search is gone. A sentence is said
as a :class:`Said`, which carries its Reason's code; every record that
keeps a sentence keeps the code beside it (``IndexEntry.code``,
``StatusUpdate.note_codes``, ...), and every reader reads the code:
:data:`BY_CODE` for the Reason, :data:`HOLDS` and :data:`FIRM_SIDE` as sets
of codes, :func:`first_of` for the most specific of several. The router's
and the filer's own sentences that are not Reasons have codes here too
(``*_CODE``), so every sentence that parks a row has one. A row written
before 190 has the code ``""``: its cause was not recorded, and nothing
reads one back out of its words.

Not every cause is a validation note. :data:`NO_READABLE_TEXT` and
:data:`ISSUER_NOT_NAMED` are the router's, written into the index's Reason
column rather than into a request's notes, and they are worded here for the
same reason the rest are: one sentence, one owner, and one code the index,
the review queue and the status report all read without retyping a word
of it. :data:`FILE_MOVED` and :data:`COPY_CHANGED` are a third kind
again (decision 109): the scanner writes them into a request's notes, but
it does not decide them - it reads them off the rows the filer's sweep of
the working copies recorded, so what the fingerprint identified and what a
person is told are one sentence apart. :data:`INTERRUPTED_MOVE` and
:data:`INTERRUPTED_MOVE_LOST` (decision 119) are of that kind too: the
filer's recovery writes them onto the row it could not finish as decided,
and the scanner says them of the request the file was going to be a
copy for. So are decision 157's three: :data:`COPY_MISSING`,
:data:`COPY_AND_ORIGINAL_GONE` and :data:`ANSWER_NOT_COUNTED` are what the
scanner says of a request whose working copy the record claims and the
firm cannot count - read off the rows the sweep left, every one of them
firm-side, so a missing copy is never by itself a letter to the client.

And not every sentence here is a cause at all. :data:`NAMES_SEVERAL_FORMS`
is what the index says when a document *was* filed - under several
requests at once (decision 94) - and :data:`SEVERAL_FORMS_UNSORTED` when
that same page would not sort. They are plain templates rather than
:class:`Reason`\\ s, and deliberately outside ``ALL``: the reminder asks
``ALL`` what to tell a client about a failure, and a document that filed
is not one.
"""

from __future__ import annotations

from dataclasses import dataclass


class Said(str):
    """A sentence one cause said, carrying that cause's code (decision 190).

    What :meth:`Reason.format` returns, and what every producer hands on
    when it hands a sentence on: the text is the sentence exactly as it
    always was - equal to it, printed as it, stored as it - and ``code``
    rides beside it, so the record a producer builds takes its code from
    the object that said the sentence and never from the sentence's words.

    **Why a string that carries its code, rather than a pair.** A tier-2
    refusal is handed through a function that returns a sentence
    (``validators.too_large_reason``), across the reading's child (decision
    150, pickled), through the verdict cache, into a row. Each hop already
    passes the sentence; the code now travels in the same object, and
    every record that keeps one - ``FileResult``, ``ContentResult``,
    ``Extraction``, ``Routing``, ``IndexEntry`` - has a ``code`` field of
    its own, set from it where the record is made. A sentence anybody
    edits - a clause joined on, a slice - is a plain ``str`` again with no
    code, which is right: an edited sentence is no longer one cause's.
    """

    code: str

    def __new__(cls, text: str, code: str) -> Said:
        said = super().__new__(cls, text)
        said.code = code
        return said

    def __reduce__(self):
        # Pickled across the reading's child and copied by asdict(): the
        # code goes with it both ways.
        return (Said, (str(self), self.code))


def code_of(sentence: str) -> str:
    """The code ``sentence`` was said with, or ``""`` for a plain string.

    Reads the attribute a :class:`Said` carries. It never looks at the
    words: a sentence that does not carry a code has none, whatever it
    says (decision 190)."""
    return sentence.code if isinstance(sentence, Said) else ""

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
    #: A literal part of the template: what the review card names the
    #: refusal by (``review._refusals_for``). Until decision 190 it was also
    #: what a note was searched for; nothing searches a sentence now - a
    #: row's cause is its code.
    marker: str
    ask: str = ""      # the client-facing sentence; "" means GENERIC_ASK
    firm_side: bool = False   # True: waiting on a person here, never put to the client
    firm_note: str = ""       # what the firm is told instead; "" means FIRM_WAITING
    #: True: a parked file carrying this reason holds the reminder for every
    #: request its shortlist names (decision 117's hold). Its own property
    #: since decision 140, and deliberately not read off ``firm_side``: a
    #: file the client can fix holds, and so does one that shows a request's
    #: form number and waits for a person here - which is firm-side, because
    #: the client's file may be perfectly good. Whose problem a row is and
    #: whether it holds the letter are two questions.
    holds: bool = False

    def format(self, **detail: object) -> Said:
        """The sentence, filled, carrying this reason's code."""
        return Said(self.template.format(**detail), self.code)

    @property
    def client_ask(self) -> str:
        return self.ask or GENERIC_ASK

    @property
    def firm_side_note(self) -> str:
        return self.firm_note or FIRM_WAITING


#: How a client turns a Google Docs/Sheets shortcut into a document we can
#: read. Said once: the note, the ask and the folder README all quote it.
GOOGLE_EXPORT_HINT = "File > Download > PDF or Excel"

#: Where a file this machine will not open is opened, if at all (decision
#: 184): said once, so the notes, the review card and the runbook agree.
OTHER_MACHINE = "on a machine with no Drive sign-in and no client folder"

# ---- tier 2: the file itself -----------------------------------------------

PASSWORD_PROTECTED = Reason(
    "password", "PDF is password-protected; please ask the client for an unlocked copy",
    # "PDF is ..." since decision 143, when a locked email or zip began
    # saying "password-protected" in a sentence of its own: the marker is
    # still a literal part of this template, so every note written before
    # is found by it as it was.
    "PDF is password-protected", "the file is password-protected; please send an unlocked copy",
    holds=True,
)
NO_PAGES = Reason("no-pages", "PDF contains no pages", "contains no pages", holds=True)
UNREADABLE_PDF = Reason("unreadable-pdf", "not a readable PDF ({error})", "not a readable PDF",
                        holds=True)
#: A photo Pillow will not open (decision 127). The client's to fix, like a
#: corrupt PDF: a half-transferred photo is a photo they still have.
UNREADABLE_IMAGE = Reason(
    "unreadable-image", "not a readable image ({error})", "not a readable image",
    "the photo that arrived could not be opened; please send it again",
    holds=True,
)
#: An iPhone's HEIC photo on a machine whose HEIC decoder is missing
#: (decision 127). Ours, and only ours: the client sent an ordinary photo,
#: and the package that reads it is pinned and bundled, so this means a
#: checkout that was never installed. Transient by the same rule OCR is -
#: installing the reader must be able to change the answer.
HEIC_NOT_SUPPORTED = Reason(
    "heic-reader",
    "a HEIC photo needs the HEIC reader installed on this machine; review manually",
    "HEIC reader installed", firm_side=True,
)
GOOGLE_STUB = Reason(
    "google-stub",
    ".{extension} is a Google Docs shortcut, not the document itself; "
    f"ask the client to download it ({GOOGLE_EXPORT_HINT}) and upload that copy",
    "Google Docs shortcut",
    "that was a Google Docs/Sheets shortcut rather than the document itself; "
    f"please download it ({GOOGLE_EXPORT_HINT}) and send that copy",
    holds=True,
)
EXTENSION_NOT_ALLOWED = Reason(
    "extension", "extension .{extension} not allowed (expected: {allowed})", "not allowed",
    "we cannot open that file type; please send it as a PDF, a photo or an Excel file",
    holds=True,
)
#: A program, or a file Windows runs as one (``validators.PROGRAM_EXTENSIONS``,
#: decision 190). Decided before any reading, so nothing the file's name
#: says reaches a request, and parked with no review copy: nobody here opens
#: it. It holds nothing - no request is named - and the client is asked
#: about it in the words any unusable file gets: the ask is
#: EXTENSION_NOT_ALLOWED's own, referenced, so it has one home.
NOT_A_DOCUMENT = Reason(
    "not-a-document", "not a document; do not open; ask the client what they meant to send",
    "not a document", EXTENSION_NOT_ALLOWED.ask,
)
TOO_SMALL = Reason(
    "too-small",
    "file is {size_kb:.1f} KB, below the {minimum} KB minimum; possible placeholder or failed upload",
    "possible placeholder or failed upload",
    "the file arrived almost empty, so the upload may not have finished; please send it again",
    holds=True,
)
#: A drop past ``validators.MAX_READ_MB`` (decision 137, M5), or a picture
#: past Pillow's own decompression-bomb limit (decision 137, B1). Not read
#: at all - no text, no OCR - and parked for a person, because reading it is
#: how a pass stalls. Ours to look at, never the client's to fix: the file
#: may be exactly what was asked for, only large. ``size`` is "N MB" for a
#: file, "N megapixels" for a picture.
TOO_LARGE = Reason(
    "too-large", "Too large to read ({size}). A person looks at it.",
    "Too large to read", firm_side=True,
    firm_note=f"too large for the app to read; a person opens it, if at all, {OTHER_MACHINE}",
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
    holds=True,
)
NO_EXPECTED_KEYWORD = Reason(
    "no-keyword", "none of the expected keywords found ({listed})",
    "none of the expected keywords found",
    "the document that arrived does not look like this item; please check that the right file was sent",
    holds=True,
)
WRONG_PERIOD = Reason(
    "wrong-period", "expected period not found (pattern: {pattern}); possible wrong period",
    "possible wrong period",
    "the document that arrived appears to cover a different period; please check the year",
    holds=True,
)
EXTRACTION_FAILED = Reason(
    "extraction-failed", "text extraction failed ({error})", "text extraction failed",
    holds=True,
)
UNCHECKABLE_TYPE = Reason(
    "uncheckable-type", "content rules cannot be checked on .{extension} files; review manually",
    "content rules cannot be checked", firm_side=True,
)
#: A scan or a photo the reader could not run on (decision 169, ruling 9):
#: the reader ships inside the app, so this is a model file missing or
#: broken - the machine's, transient, and read again once it is mended. It
#: said "OCR is not installed" while the engine was a separate install.
NO_TEXT_LAYER = Reason(
    "no-text-layer",
    "PDF or photo appears to be a scan with no text layer and the reader could not run "
    "on this machine; review manually",
    "no text layer", firm_side=True,
)
#: A scan or a photo the reader got nothing out of. It said "in PDF" until
#: decision 127, when a photo started reaching this sentence too; the
#: marker is unchanged, so nothing that recognises it had to move.
NO_TEXT_AFTER_OCR = Reason(
    "no-text-after-ocr", "no readable text found, even after OCR; review manually",
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
#: row would put two entities' K-1s under one request, which is the thing the
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

#: A document that was read, matched no request, and shows the **form
#: number** of one or more rows on its page - in the title, or as the form
#: that dominates the first page (decision 140). The commonest cause is an
#: OCR reading that lost one of a row's required phrases: a real W-2 whose
#: "employee's social security number" label the scan cut at the box rule.
#: The rows are the shortlist a person is handed, never candidates: a
#: suggestion is not evidence to file on (decision 92).
#:
#: Firm-side, because the client's file may be perfectly good and nothing
#: may tell them it was wrong; and it **holds** the reminder for the rows
#: its shortlist names (Jason, 2026-09-23), because asking the client for a
#: W-2 they sent, while it sits in review, is the letter decision 117
#: exists to stop.
SHOWS_ITS_FORM_NUMBER = Reason(
    "shows-form-number",
    "matched no request, but it shows the form number of {listed}; a person should confirm",
    "but it shows the form number of", firm_side=True, holds=True,
    firm_note="it matched no request but shows this request's form number; "
              "a person here confirms it - never the client",
)
#: The same near miss where the page shows no row's form number and only
#: the file's **name** carries a row's keyword (decision 140, the designer's
#: ruling on the build): decision 92's hint for a file nothing could read,
#: now also given to a read file that matched nothing. Its own sentence,
#: because the page did not show anything - the client's name for the file
#: did - and a reason must not claim the page said what only the name said.
#: Firm-side and holding, exactly as :data:`SHOWS_ITS_FORM_NUMBER`.
NAME_POINTS_AT = Reason(
    "name-points-at",
    "matched no request, but its file name points at {listed}; a person should confirm",
    "but its file name points at", firm_side=True, holds=True,
    firm_note="it matched no request but its file name points at this request; "
              "a person here confirms it - never the client",
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
#: the row (decision 109, extending decision 3) - the original's. Since
#: decision 155 the file is not counted: a copy torn in half, or another
#: document put in its place, is not the document, whatever rules it
#: passes. This says so, firm-side, so the request's Missing is never a
#: client ask.
COPY_CHANGED = Reason(
    "copy-changed",
    "the file at {listed} is not the one the record filed there, so it is not counted; a "
    "person should look",
    "not the one the record filed there", firm_side=True,
    firm_note="a working copy here no longer holds the bytes the record filed; a person "
              "here looks - never the client",
)
#: A path the record claims for this request's working copy holds nothing,
#: and the pass did not make it again (decision 157, ruling B9): the
#: original could not be read this pass (still syncing, or refused), or
#: the copy could not be written. A missing copy is never a client ask by
#: itself - the firm holds the client's original, and the next pass makes
#: the copy from it - so this is firm-side, and only a person's Mark
#: missing turns it into one.
COPY_MISSING = Reason(
    "copy-missing",
    "the working copy {listed} is missing; it is made again from the original when the "
    "original can be read",
    "is made again from the original when the original can be read", firm_side=True,
    firm_note="a working copy here is missing and is made again from the client's original "
              "when it can be read; a person here looks if it stays - never the client",
)
#: This request's working copy is gone and so is the client's original - or
#: the original holds other bytes now (decision 157, ruling B5). Nothing
#: can be made again and nothing is guessed, so the request is held here,
#: firm-side, until a person looks: it replaces ``FILE_MOVED``'s
#: put-it-back wording, because there is nothing to put back. A person's
#: Mark missing on the row is what asks the client again.
COPY_AND_ORIGINAL_GONE = Reason(
    "copy-and-original-gone",
    "the copy and the original of {listed} are both gone; a person should look",
    "are both gone; a person should look", firm_side=True,
    firm_note="the working copy and the client's original are both gone; a person here "
              "looks, and marks it missing if the client should send it again - never the "
              "client until then",
)
#: A consolidated statement (decision 146) answers this request, and the
#: statement's own working copy is not counted - it is missing, it is not
#: the one the record filed, it is not where the record put it, or it and
#: its original are both gone (decision 157, ruling B9, from 146's restack
#: review). An answer is only as good as the document that gives it, so
#: this request is not counted Received either: it is held here, naming
#: the statement and why. A copy made again heals it in the same pass.
ANSWER_NOT_COUNTED = Reason(
    "answer-not-counted",
    "{listed} is not counted, so neither is its answer for this request; a person should look",
    "so neither is its answer for this request", firm_side=True,
    firm_note="the consolidated statement that answers this request has no working copy the "
              "firm can count; a person here looks - never the client",
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

# ---- the name on the page (decision 128) ---------------------------------

#: How a spelling and the return it belongs to are said together, in the
#: one sentence that carries both (:data:`NAMES_ANOTHER_RETURN`). Worded
#: here because both the filer, which composes it, and
#: :mod:`tracker.review`, which reads the other return's label back off the
#: row for the card, derive from this template through
#: :func:`tracker.records.as_pattern` - so rewording it moves its reader.
NAME_AND_RETURN = "{spelling} ({label})"

#: The page names nobody on this return's people list, and the request that
#: accepted it is one whose document carries a name. Firm-side, always: the
#: people list is the firm's and may simply be short a spelling, and asking
#: the client to send a document they already sent would be the firm's
#: paperwork put to them as their mistake.
NAME_NOT_ON_PAGE = Reason(
    "name-absent",
    "the page names none of this return's people ({listed}); a person should confirm",
    "names none of this return's people", firm_side=True,
    firm_note="the name check found none of the return's spellings; add a spelling in the "
              "editor if the page does name them",
)
#: The page names somebody who is on another return of this household, and
#: nobody here. Filing it here would put one person's document under
#: another's return, which is exactly the failure the name tier exists to
#: stop, so it parks and says whose it looks like.
NAMES_ANOTHER_RETURN = Reason(
    "name-other",
    "the page names {listed}, who is on another return; a person should confirm",
    "who is on another return", firm_side=True, firm_note=FIRM_WAITING,
)
#: The return lists nobody yet, so a named request has nothing to confirm
#: against. Strict, on purpose: filing on the keywords alone is what the
#: name tier replaced, and the fix is one edit in the editor.
NO_PEOPLE_ON_FILE = Reason(
    "no-people",
    "this return lists no people yet ({listed}); add them in the editor before its named "
    "requests can file",
    "lists no people yet", firm_side=True, firm_note=FIRM_WAITING,
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
#: A broker's consolidated 1099 (decision 146): several rows accepted it,
#: and exactly one was accepted because of its 1099-B section, so the
#: statement files whole there - one file, one copy, never split.
#: Plain templates, outside ``ALL``, for the reason the two above are: a
#: document that filed is not a failure to put to a client.
FILED_WHOLE = ("carries a 1099-B section and files whole under the one request "
               "its 1099-B was accepted by ({filed})")
#: What the same row says of the other asked requests the statement
#: answers without a copy (decision 146, the owner's answer to 146-Q).
ALSO_ANSWERS = "it also answers {listed}, with no copy"
#: What an answered request says it holds, for the firm: the scanner's
#: note on the request - which the Status Report and the app's filed list
#: show - and the runbook quote this one sentence, because a person at the
#: firm needs the row. ``{row}`` is the request the statement filed under.
IN_CONSOLIDATED = "in {row}'s consolidated statement"
#: The same answer in the client's words (decision 146, Jason's Q-L): the
#: client's received list says it after the date, naming no request, no
#: label and no possessive. "Brokerage" is always true here, because a
#: statement files whole only when one request accepted its 1099-B section.
IN_CONSOLIDATED_CLIENT = "included in your consolidated brokerage statement"

# ---- the firm's folder -------------------------------------------------------

#: A folder inside a return's Prepared folder that is not the review
#: folder (decision 168): working copies sit in Prepared itself, named by
#: their request, so any folder in it is a person's - or a request folder
#: of a return made before 168. Nothing is filed into it, counted in it or
#: moved out of it, and the pass names it once, firm-side. A plain template
#: rather than a :class:`Reason`, outside ``ALL``: it is a sentence about a
#: folder on the run's warnings, never a note on a request, and never a
#: thing to ask a client. ``{prepared}`` is ``layout.PREPARED_DIR_NAME``.
#: Until 168 a request whose folder was not there said
#: "request folder not found; the next pass creates it" - retired with the
#: folder, because a request can no longer lack one.
PERSONS_FOLDER = ("{folder} is a folder inside {prepared}. The app files into {prepared} "
                  "itself and counts nothing in this folder.")

#: A reading that hit the safety stop (decision 137, B1.2; the owner's
#: Q-1 of 2026-09-24): ten times the speed ceiling he approved for decision
#: 127 - a minute a page, ten minutes a file. The reading is abandoned and
#: the verdict kept, so the file is not read again until it changes. Ours:
#: the file may be perfectly good, and a person reads it.
READING_STOPPED = Reason(
    "reading-stopped",
    "The reader stopped after {minutes} on this file. A person reads it.",
    "The reader stopped after", firm_side=True,
    firm_note="the reader gave up on it at the safety stop; a person here reads it",
)

#: A reading whose process ended without an answer (decision 150): the PDF
#: library or the reader crashed, or memory ran out. Not an abandoned reading - the
#: stop was not reached - but kept the same way, so the file is not read
#: again until it changes, and the pass goes on to the next document where
#: it used to end with this one. Ours: the file may be perfectly good.
READING_CRASHED = Reason(
    "reading-crashed",
    "The reader could not read this file (it stopped unexpectedly). A person reads it.",
    "The reader could not read this file", firm_side=True,
    firm_note="the reader stopped unexpectedly on it; a person here reads it",
)

#: A reader that could not start at all (decision 150): its child process
#: was never created, or ended - or said nothing - before it touched the
#: file. The machine's doing, not the file's, so it leaves nothing
#: permanent: no verdict is kept, a drop is neither decided nor recorded
#: (it waits, in the inbox or as a stray in the year's folder), the scan
#: asks again, and the pass warns once. The file is read again on the next
#: pass. Ours.
READER_UNAVAILABLE = Reason(
    "reader-unavailable",
    "The reader could not start on this machine, so this file was not read. "
    "It is read again on the next pass.",
    "The reader could not start on this machine", firm_side=True,
    firm_note="the reader could not start on this machine; a person here looks at the machine",
)

#: A document the household's drop folder feeds to a return in **another**
#: household, whose page names nobody (decision 137, B2; the owner's Q-2 of
#: 2026-09-24: "never; a person decides"). Within one household an unnamed
#: request still files on its keywords (decision 128's table); across
#: households filing needs the name confirmed, because the original moves
#: into a folder that household's people can open. Ours: a person here
#: decides which return it is.
UNNAMED_ACROSS_HOUSEHOLDS = Reason(
    "unnamed-across",
    "Unnamed, so it was not filed into another household's return.",
    "not filed into another household's return", firm_side=True,
    firm_note="no name on it, so it was not filed into another household's return; "
              "a person here decides",
)
#: A document the household's drop folder feeds to a return in **another**
#: household, whose page names that return's person (decision 204,
#: revising 132). The pass never files across households: the name is
#: confirmed, so the only question left is whether a person here agrees,
#: and the row carries what the other household's list accepted
#: (``waits_for``) so that agreeing is one click. ``{spelling}`` is the
#: firm's own spelling that matched, never a word of the page; ``{label}``
#: is the return's label. Ours, and it holds nothing: the client's file is
#: good.
NAMED_ACROSS_HOUSEHOLDS = Reason(
    "named-across",
    "Names {spelling}, who is on {label}, a return in another household; "
    "it waits here for a person to file it there.",
    "a return in another household; it waits here for a person", firm_side=True,
    firm_note="it names somebody on a return in another household; a person here files it "
              "there - never the client",
)

# ---- an email or a zip (decision 143) ----------------------------------------

#: An email or a zip that will not open because it is locked: a zip member
#: carrying the encryption flag, or packed with a method this reader has
#: not got (AES is the common one). Nothing inside was read or written. The
#: client's to fix - they can send the documents themselves - so it holds
#: the letter like a locked PDF does.
CONTAINER_LOCKED = Reason(
    "container-locked",
    "an email or zip that is password-protected, so nothing in it was opened; "
    "ask the client for the documents themselves",
    "so nothing in it was opened",
    "the email or zip file that arrived is password-protected; please send the documents "
    "in it on their own",
    holds=True,
)
#: An email or a zip that does not read as one: a zip whose directory is
#: broken, an ``.msg`` whose structure is not a compound file, an ``.eml``
#: with no message headers at all. The client's to fix, like a damaged PDF.
CONTAINER_DAMAGED = Reason(
    "container-damaged",
    "could not be opened as an email or a zip ({error}); read it here",
    "could not be opened as an email or a zip",
    "the email or zip file that arrived could not be opened; please send the documents "
    "in it on their own",
    holds=True,
)
#: An email or a zip with nothing attached - every part was the message's
#: own text or an inline picture. Ours: a person reads the message, which
#: may say what the client meant to send.
CONTAINER_EMPTY = Reason(
    "container-empty",
    "{kind} with nothing attached; read it here",
    "with nothing attached; read it here", firm_side=True,
    firm_note="an email or zip arrived with nothing attached; a person here reads it - "
              "never the client",
)
#: An email or a zip past one of the limits it is opened under (each named
#: in ``tracker.containers``, the limit in the sentence): too deep, too
#: many attachments, too large once unpacked, or a member that unpacks far
#: past its packed size. Ours: nothing about it is wrong for the client to
#: fix, and a person opens it, if at all, on a machine with no Drive
#: sign-in and no client folder (decision 184).
CONTAINER_LIMIT = Reason(
    "container-limit",
    "not opened: it passes a limit for an email or a zip ({error}); opened, if at all, "
    + OTHER_MACHINE,
    "passes a limit for an email or a zip", firm_side=True,
    firm_note="an email or zip was too large or too deep to open here; a person opens it, "
              f"if at all, {OTHER_MACHINE} - never the client",
)
#: A document that came out of an email or a zip, which a return in
#: **another** household would have taken: an attachment's original is the
#: firm's copy of a part of the client's file, not a file of the client's,
#: so it never moves into another household's folder (decision 143). It
#: parks at home, and a person's hand-over refuses it in the same words.
OPENED_NOT_ACROSS = Reason(
    "opened-not-across",
    "came inside an email or zip; a document from inside one is not filed into another "
    "household. Open it here and file it by hand.",
    "a document from inside one is not filed into another household", firm_side=True,
    firm_note="it came inside an email or zip and is not filed into another household; "
              "a person here files it",
)

#: What a verdict on a ``.csv``/``.tsv``/``.txt`` says when only the first
#: ``validators.TEXT_READ_CAP_MB`` of it was read (decision 137). Appended
#: to the reason, never a reason itself: the cut explains a verdict, it does
#: not decide one - so it is outside ``ALL``, like the templates above.
TEXT_CUT = "only the first {limit} MB of this file's text was read"

#: Every reason, in the order of preference: the specific causes before the
#: vague ones, so a note that says two causes gets the better ask
#: (:func:`first_of`).
ALL: tuple[Reason, ...] = (
    CONTAINER_LOCKED, CONTAINER_DAMAGED, CONTAINER_EMPTY, CONTAINER_LIMIT,
    NOT_A_DOCUMENT, PASSWORD_PROTECTED, GOOGLE_STUB, TOO_SMALL, TOO_LARGE, EXTENSION_NOT_ALLOWED,
    WRONG_DOCUMENT, NO_EXPECTED_KEYWORD, WRONG_PERIOD,
    NO_PAGES, UNREADABLE_PDF, UNREADABLE_IMAGE, HEIC_NOT_SUPPORTED, EXTRACTION_FAILED,
    UNCHECKABLE_TYPE, NO_TEXT_LAYER, NO_TEXT_AFTER_OCR, OCR_FAILED, NO_READABLE_TEXT,
    ISSUER_NOT_NAMED, SHOWS_ITS_FORM_NUMBER, NAME_POINTS_AT,
    NAME_NOT_ON_PAGE, NAMES_ANOTHER_RETURN, NO_PEOPLE_ON_FILE, UNNAMED_ACROSS_HOUSEHOLDS,
    NAMED_ACROSS_HOUSEHOLDS, OPENED_NOT_ACROSS, FILE_MOVED, COPY_CHANGED, COPY_MISSING, COPY_AND_ORIGINAL_GONE,
    ANSWER_NOT_COUNTED, INTERRUPTED_MOVE, INTERRUPTED_MOVE_LOST,
    READING_STOPPED, READING_CRASHED, READER_UNAVAILABLE, PENDING_SYNC, VANISHED,
)

#: Every reason by its code: how a reader turns a row's ``code`` back into
#: the one object that says what it means (decision 190).
BY_CODE: dict[str, Reason] = {reason.code: reason for reason in ALL}
#: The codes of the reasons that mean "a person here has not looked yet",
#: never a client ask.
FIRM_SIDE: frozenset[str] = frozenset(r.code for r in ALL if r.firm_side)
#: The codes of the reasons whose parked file holds the reminder for the
#: requests its shortlist names (decisions 117 and 140).
HOLDS: frozenset[str] = frozenset(r.code for r in ALL if r.holds)


def first_of(codes) -> Reason | None:
    """The most specific Reason among ``codes`` - the first of them in
    :data:`ALL`'s order - or None when no code names one. A code no Reason
    has (the router's own, an empty one) is passed over, never guessed at."""
    found = [BY_CODE[code] for code in codes if code in BY_CODE]
    return min(found, key=ALL.index) if found else None


# ---- the sentences that park a row and are not Reasons ----------------------
#
# The router's and the filer's own sentences (decision 190): each gets a code
# here, so every row that parks carries one, and the row's cause is read
# from it. None of them is in ALL - none has a client ask or a hold of its
# own - so BY_CODE does not name them, and a reader that asks it for one
# gets None, which is what "not one of the reasons" means. The router's are
# worded here, beside their codes, and tracker.router names them; the
# filer's sentences carry detail only the filer has, so they stay in
# tracker.filer and their codes are here.

#: Read, and no request's rules accepted it.
UNMATCHED = "matched no request"
UNMATCHED_CODE = "unmatched"
#: More than one request accepted it equally.
AMBIGUOUS = "matched more than one request"
AMBIGUOUS_CODE = "ambiguous"
#: OCR text matched a request's looser keywords only; not enough to file on.
OCR_ONLY = "matched only by OCR text"
OCR_ONLY_CODE = "ocr-only"
#: Every request refused the file type.
NO_REQUEST_ACCEPTS = "no request accepts .{extension} files"
NO_REQUEST_ACCEPTS_CODE = "no-request-accepts"
#: How a contested file's sentence starts ("looks like A01 (...) - a person
#: should confirm"). The candidates travel as data (Routing.candidates, then
#: the index's Candidates column); nothing parses this sentence to get them
#: back. A contested row's code is the most specific refusal that contested
#: it (:func:`first_of`), since that is what decided it; ``CONTESTED_CODE``
#: is for one with no refusal a Reason names, and
#: ``SEVERAL_FORMS_UNSORTED_CODE`` for a page whose forms would not sort one
#: to a request.
CONTESTED_PREFIX = "looks like"
CONTESTED_CODE = "contested"
SEVERAL_FORMS_UNSORTED_CODE = "several-forms-unsorted"
#: Where a document filed: the router's three filing sentences, so a filed
#: row says what decided it as a parked one does.
MATCHED_CODE = "matched"
SEVERAL_FORMS_CODE = "several-forms"
FILED_WHOLE_CODE = "filed-whole"
#: tracker.filer's ``CONTESTED_BETWEEN_RETURNS``: requests in two returns
#: accepted it and the name did not tell them apart.
CONTESTED_BETWEEN_RETURNS_CODE = "between-returns"
#: tracker.filer's ``PATH_NO_ROOM`` and ``PATH_NO_ROOM_IN``: no room for
#: even the request's shortest name.
NO_ROOM_CODE = "no-room"
#: The filer's catch-all: "could not be filed (...) - file it by hand".
COULD_NOT_FILE_CODE = "could-not-file"
#: tracker.filer's ``UNFILED_BY_PERSON``: a person took a filed document
#: back to the review queue.
UNFILED_BY_PERSON_CODE = "unfiled"
#: tracker.filer's ``DISMISSED_BY_PERSON``: a person set it aside as not
#: requested.
DISMISSED_BY_PERSON_CODE = "not-requested"
#: tracker.filer's ``ASSIGNED_BY_PERSON``: a person filed it.
ASSIGNED_BY_PERSON_CODE = "assigned"
#: tracker.filer's ``PUT_BACK_REFUSED``: a person asked for a moved copy to
#: go home, somebody's file was there, and the row parks with a copy.
PUT_BACK_REFUSED_CODE = "put-back-refused"

#: Every code above, for the suite's one check that no two causes share a
#: code and that every one of them is here.
PLAIN_CODES: tuple[str, ...] = (
    UNMATCHED_CODE, AMBIGUOUS_CODE, OCR_ONLY_CODE, NO_REQUEST_ACCEPTS_CODE,
    CONTESTED_CODE, SEVERAL_FORMS_UNSORTED_CODE, MATCHED_CODE, SEVERAL_FORMS_CODE, FILED_WHOLE_CODE,
    CONTESTED_BETWEEN_RETURNS_CODE, NO_ROOM_CODE, COULD_NOT_FILE_CODE,
    UNFILED_BY_PERSON_CODE, DISMISSED_BY_PERSON_CODE, ASSIGNED_BY_PERSON_CODE,
    PUT_BACK_REFUSED_CODE,
)

#: Every code a row or a status may carry: a Reason's and a plain one.
#: What the store admits (decision 187's value rule, held to decision
#: 190's columns): a code outside it is refused as a malformed line,
#: because the letter, its holds and the review card read it.
KNOWN_CODES: frozenset[str] = frozenset(BY_CODE) | frozenset(PLAIN_CODES)


#: One short label per code, five words or fewer (SPEC-shell 11.5, P84): what a
#: row on the app's pages says in place of the sentence, which stays where the
#: index, the letter and the log use it. Keyed by code, never by a sentence's
#: words; ``tests/test_reasons.py`` requires one for every code in :data:`BY_CODE`
#: and :data:`PLAIN_CODES` and no other.
SHORT_REASONS: dict[str, str] = {
    "unmatched": "Could Not Sort",
    "name-absent": "No Taxpayer Name Found",
    "ambiguous": "Fits Two Requests",
    "name-other": "Names Another Return",
    "contested": "Claimed by Two Requests",
    "named-across": "Names Another Household",
    "between-returns": "Fits Two Returns",
    "unnamed-across": "No Name on It",
    "ocr-only": "Read From Scan Only",
    "name-points-at": "Name Hints a Request",
    "no-request-accepts": "File Type Not Asked",
    "shows-form-number": "Shows a Form Number",
    "several-forms-unsorted": "Several Forms, Unsorted",
    "issuer-not-named": "Issuer Not Named",
    "no-room": "No Room for Name",
    "no-people": "Return Has No People",
    "could-not-file": "Could Not File",
    "answer-not-counted": "Statement Not Counted",
    "put-back-refused": "Could Not Put Back",
    "opened-not-across": "Email or Zip",
    "unfiled": "Unfiled by a Person",
    "container-damaged": "Email or Zip Damaged",
    "not-requested": "Not Requested",
    "container-empty": "Nothing Attached",
    "assigned": "Filed by a Person",
    "container-limit": "Email or Zip Too Big",
    "matched": "Filed",
    "container-locked": "Email or Zip Locked",
    "several-forms": "Filed as Several Forms",
    "password": "Password Protected",
    "filed-whole": "Filed Whole",
    "google-stub": "Google Shortcut Only",
    "file-moved": "Moved by Hand",
    "extension": "File Type Not Allowed",
    "copy-missing": "Copy Missing",
    "not-a-document": "Not a Document",
    "copy-changed": "Copy Was Changed",
    "too-small": "File Almost Empty",
    "copy-and-original-gone": "Copy and Original Gone",
    "too-large": "Too Large to Read",
    "interrupted-move": "Step Interrupted",
    "no-pages": "PDF Has No Pages",
    "interrupted-move-lost": "Move Interrupted",
    "unreadable-pdf": "PDF Will Not Open",
    "pending-sync": "Syncing",
    "unreadable-image": "Photo Will Not Open",
    "vanished": "File Disappeared",
    "heic-reader": "HEIC Photo, No Reader",
    "no-keyword": "Expected Words Missing",
    "uncheckable-type": "Cannot Check This Type",
    "wrong-document": "Looks Like Wrong Document",
    "extraction-failed": "Text Could Not Be Read",
    "wrong-period": "Wrong Period",
    "no-text-layer": "Scan Not Readable",
    "reader-unavailable": "Reader Did Not Start",
    "no-text-after-ocr": "No Readable Text",
    "reading-crashed": "Reader Stopped",
    "ocr-failed": "Scan Reading Failed",
    "reading-stopped": "Reading Timed Out",
    "unreadable": "Nothing Readable",
}

#: The longer words a short label stands for, shown as its tooltip every
#: time, cut or not (pilot P116, SPEC-email-zip-tag). Only a label that was
#: shortened into a tag to fit the 160px status column is here: its tag
#: alone could be read as something else - "Email or Zip" on a document's
#: row does not say the document came out of one - so the words it replaced
#: stay one hover away. Every other label says all it means and has no
#: tip unless it is cut. Five words or fewer, like every tooltip (SPEC-shell
#: 11); keyed by code, and ``tests/test_reasons.py`` keeps each key a code
#: of :data:`SHORT_REASONS` and each tip different from its tag.
REASON_TIPS: dict[str, str] = {
    "opened-not-across": "Came in Email or Zip",
}
