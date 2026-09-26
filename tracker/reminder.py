"""Draft the "still waiting on these" email to a client (component 9).

Reads a scanned engagement's record and writes a plain-text draft the
accountant can read, edit and paste into Outlook. **It never sends anything**
— there is no SMTP, no mail client, no network call anywhere in this module.
A reminder goes out because a person decided to send it.

**Four stages, measured against the Due Date** (decision 117). The same
flat reminder every week is the one that gets tuned out by the third one,
so the draft escalates: more than three weeks from the Due Date a heads-up
with no deadline sentence at all; inside three weeks a check-in that names
the target; in the last ten days a firm request that names the target and
the Filing Deadline beside it; on the day and after it a final notice with
the consequences sentence and the firm's telephone number. The stage
changes the *words* and nothing else: who is asked is :func:`triage`'s
answer and is identical at every stage, and the gate below holds at every
stage. ``STAGES`` is the wording, once; the two thresholds are constants.

The sentences name the two dates and never the arithmetic between them.
The Due Date defaults to five days before the Filing Deadline, but either
is a person's to move, and a draft that said "five days before" would be
made to tell a client something false the moment somebody did.

What the client is asked for:

- ``Status.MISSING`` — never arrived.
- ``Status.PARTIAL`` — some of the expected files arrived, not all.

What holds the whole reminder back for a person (decision 115):

- ``Status.FAILED`` with no firm-side marker, and ``Status.PARTIAL`` whose
  shortfall is a file the rules refused. Something arrived and the rules
  could not use it - but a copy the router filed cannot fail the content
  rules on its own filing (the scan's verdict is the router's), so a Failed
  row on a filed copy is nearly always the firm's doing: a rule edited
  after filing, a copy dragged in by hand, a copy replaced. Whether the
  client resends or we fix it here is a person's call, and the draft does
  not guess. One such row *holds the client's whole reminder*: no draft
  file is written, the run's own unedited draft from an earlier week is
  retired, an edited one is left, and the hold is said everywhere a person
  looks - the run log, the practice page, the app - with the rows named.
  The client is asked once, correctly, or not yet.
- **A parked file the client could fix** (decision 117, amending the
  above). A locked PDF, an empty upload, a file type nothing accepts: the
  drop never reaches a request's status at all - it parks for a person and
  the request stays Missing - so the draft used to ask for a document the
  client is certain they sent. When such a parked row's reason is the
  client's to fix and the review queue's shortlist for it - what the card
  shows a person, the file's own name included - names a request still
  outstanding, that request holds the draft exactly as a Failed row does:
  a person decides whether the client resends it or we file what came. A
  parked row that points at no request holds nothing - there is nothing to
  name - and a row whose reason is ours (a scan with no text layer) holds
  nothing either.
- **A file still waiting in the household's inbox** (decision 133). A
  pass drafts after it sorts, but the sort does not always take what the
  client sent: a household with two open years does not read its inbox, a
  drop can fail to sort, a transfer can still be in flight, a name can be
  one the machine cannot handle, a file can land after the sort - and a
  person can press *Draft* in the app hours after the last pass. Each time
  the letter could ask for a document sitting in the client's own drop
  folder. So while the return's own household's ``Drop files here`` holds
  any file the sort has not taken (:func:`unsorted_in_inbox`), the whole
  draft is held: the letter cannot know which request such a file answers.
  The count is made here and nowhere else, so the pass, the command line
  and the app hold alike, and it heals itself: a hold writes no draft, so
  the next pass that sorts the inbox drafts that same day. An inbox in
  another household that also feeds this return is not read - it is
  another client's folder - and that is a known limit, not a gap.

What the client is deliberately *not* asked for:

- ``Status.RECEIVED`` — it is in.
- ``Status.PENDING_SYNC`` — it is in; the cloud is still copying it down. Nothing for
  the client to do, so nothing to say.
- Any row with a Manual Override. ``Override.NOT_APPLICABLE`` does not apply
  this year and ``Override.ACCEPTED`` has already been judged good enough by a
  person; re-asking would contradict that person.
- Rows whose only problem is that *we* have not looked yet ("review
  manually", an un-OCR'd scan). The document may be perfect. Asking a client
  to resend something we simply have not read is how a firm looks careless,
  so those rows go to the accountant instead, under *needs a person*. That
  holds for a ``Status.PARTIAL`` row too: if the file that would complete it is one
  we have not read, "1 of 2 received" is not something we know yet. And it
  holds on any outstanding status - a ``Status.MISSING`` row whose note
  carries a firm-side marker is the firm's as well (decision 109's rule,
  stated once here). A firm-side row rides the staff-side report under the
  draft, which is still written; it never holds it.
- (Until decision 168, a row whose request folder did not exist was held
  as a scaffold problem. No request has a folder any more - its copies sit
  in ``Prepared`` itself, named by it - so a request with nothing in is
  simply Missing and asked for.)

Validation notes are **never pasted into the email.** They name keywords,
size floors and internal folders: firm-side vocabulary that would confuse a
client and expose the matching rules. Every note is translated into one plain
sentence saying what to do about it, by deterministic substring rules. No
generative AI touches any of this, and no client document is read here at
all — only the statuses the scanner already recorded.

**The draft is on the record** (decision 115). What a draft asked for, or
what held it, and which file it wrote go into the engagement's journal as
one ``ledger.DRAFTED`` event - identifiers only, never a word of the
email - appended only when that differs from the last one. The runner
reads the day of the last draft from it, and the next draft opens with
what changed since the one before, above the line a person pastes.

**And the draft has a surface** (decision 118). The letter is a structure
before it is words: :func:`_compose_letter` builds a :class:`Letter` and
:meth:`Letter.text` is the body the file carries, so the text a person
pastes, :func:`render_html`'s inline-styled body for the clipboard and the
shape the app draws its preview from are three renderings of one thing and
cannot come apart. The stage's own emphasis is one table
(:data:`STAGE_EMPHASIS`) over colours this module names by their key in
:data:`tracker.page.PALETTE`, so the letter, the clipboard and the card
apply one ladder and nothing downstream picks a colour. The HTML is
rendered when a person asks for it and **never written to disk**: the text
file is what the pass writes (decisions 11 to 15) and a second file would
be a second draft to keep in step.

A person who reads that letter in the app may **approve** it, and from
then until the next draft day the pass treats the file exactly as it
treats one somebody edited - :func:`is_protected` is the one predicate for
both, :func:`write_draft` puts the regenerated draft beside it, and
:func:`set_aside_other_draft` renames what was already standing there
rather than deleting it, because nothing under an engagement is the
machine's to throw away. The approval is one ``ledger.DRAFT_APPROVED``
line carrying a number, a name and identifiers, like every other line
here. Which day the draft week began is handed in rather than worked out:
the runner decides the draft day (decision 12) and it sits above this
module.

One more guard: files sitting in ``REVIEW_DIR_NAME`` are things the client
*has* already sent that nobody has identified yet. Sending a reminder over
the top of those risks asking for a document already in hand, so their count
is reported and the CLI says so plainly before you send. A file a person has
marked ``NOT_REQUESTED`` has been identified - as something no request asks
for - and is not counted; the warning is there to stop a person sending over
a document nobody has looked at, and they have looked at that one.
"""

from __future__ import annotations

import datetime as dt
import hashlib
import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from pathlib import Path

from tracker import ledger, page, reasons, store
from tracker.fsio import temp_owner, write_text_atomically
from tracker.layout import README_NAME, household_name_of, inbox_of, label_for, locate, year_of
from tracker.manifest import (
    ISO_DATE_HINT,
    ManifestError,
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    summarize,
)
from tracker.reasons import GENERIC_ASK  # re-exported; the one generic sentence
from tracker.records import link_problem
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)
from tracker.settings import firm_phone  # the firm's number, not an engagement's
from tracker.validators import PDF_EXTENSION, iter_candidate_files

log = logging.getLogger("tracker.reminder")

DRAFT_FILENAME = "reminder-draft.txt"
#: Where the draft a person approved puts a draft that was standing beside
#: it (decision 118). Named for the day it was set aside, never deleted:
#: nothing under an engagement is removed by an approval, and a person
#: throws these away when they like.
SET_ASIDE_DRAFT_PATTERN = "reminder-draft.set-aside-{date}.txt"
DUE_FLAG = "--due"
#: The command line's one-off dates and the two flags that read a stage
#: other than today's: what next week's letter will say, today.
DEADLINE_FLAG = "--deadline"
TODAY_FLAG = "--today"
STAGE_FLAG = "--stage"

#: Where a fresh draft goes when the standing one has been edited by hand.
NEW_DRAFT_FILENAME = Path(DRAFT_FILENAME).stem + ".NEW" + Path(DRAFT_FILENAME).suffix

_FINGERPRINT_PREFIX = "Fingerprint: "
_RULE_WIDTH = 60
_SEPARATOR = "=" * _RULE_WIDTH
#: What opens the staff-side footer a draft file may end with - the rows
#: the draft did not ask the client for, and the warning about files
#: nobody has identified yet. It is the machine's note to the person, as
#: the header above the letter is, and it has never been part of the
#: email: :func:`pasted_text` cuts the letter off here.
FOOTER_RULE = "-" * _RULE_WIDTH

#: Statuses that mean the client still owes us something (re-exported).
OUTSTANDING = Status.OUTSTANDING

#: The subject lines and the banner every draft opens with. The last two
#: are the stages that ask in their own voice (decision 117): a subject
#: that did not change with the letter would be the line a client's inbox
#: has already learned to skip.
SUBJECT_NEEDED = "{engagement}: {n} document(s) still needed"
SUBJECT_COMPLETE = "{engagement}: we have everything - thank you"
SUBJECT_RESPONSE = "{engagement}: {n} document(s) still needed - response requested"
SUBJECT_URGENT = "URGENT - {engagement}: final notice, {n} document(s) still needed"
DRAFT_BANNER = "DRAFT - NOTHING HAS BEEN SENT."
#: The sentence every draft opens its instructions with.
DROP_ANYWHERE = "Everything goes in the same place - just drop it into the shared"
#: What is said before the stage's own opening, at every stage, whenever
#: anything at all has arrived. It is true at every stage, and a client who
#: has sent half of it should never read a final notice that talks as
#: though they sent nothing. In Jason's words (decision 142, 2026-09-24):
#: the count is of what we **asked** for, and a document that arrived for a
#: row nobody asked for is thanked in a second sentence, said only when
#: there is one - so the figure never reads "7 of 5". Worded in the
#: singular and the plural by :func:`progress_line`.
PROGRESS_ASKED = "Of the {m} {items} we asked for, {n} {verb} in."
PROGRESS_ALSO = "We have also received {k} other {documents} from you."
#: Jason's softer words for the one case the count would read "0 are in"
#: while other documents have arrived (2026-09-24): thank the client for
#: what came first, then say what is still needed.
PROGRESS_NONE_ASKED = ("We have received {k} {documents} from you, thank you. "
                       "The {m} {items} we asked for {verb} still needed.")
#: The footer headings for what the draft deliberately did not ask for.
HELD_BACK_HEADING = "NOT ASKED FOR"
HELD_BACK_LINE = "NOT ASKED"
#: What the CLI prefixes a row that holds the whole draft with.
HELD_LINE = "HELD"
#: Why an ambiguous row is held (decision 115): a person decides which
#: side it is on; the draft does not. A row's own reason sentence follows
#: in brackets when the note carried one, so the person sees what the scan
#: said without opening anything.
AMBIGUOUS_HOLD = "held - a person decides whether the client resends this or we fix it here"
#: Why a request a parked file points at holds the draft (decision 117, the
#: end-to-end review's third discrepancy). The file never reached a status,
#: so the row is still Missing and the draft would ask for a document the
#: client knows they sent. The reason's own client ask rides in brackets,
#: so the person sees what was wrong with the file without opening it.
PARKED_HOLD = ("held - a file the client sent for this could not be used ({ask}); "
               "a person decides whether the client resends it or we file what came")
#: Why a request holds the draft when the parked file pointing at it is
#: waiting on a person here rather than on the client (decision 140): a
#: document that matched no request but shows this request's form number.
#: The file may be exactly what was asked for, so nothing here says it
#: could not be used, and there is no client ask to quote - the reason's
#: firm note rides in brackets instead.
CONFIRM_HOLD = "held - a file the client sent may be this one ({note})"
#: What write_draft() refuses a held draft with, and what the run log, the
#: practice page's note and the CLI say: the count, then every held row.
HELD_REFUSAL = (
    "the reminder is held: {n} request(s) need a person to decide whether the client "
    "resends or we fix it here - {listed}; nothing was written"
)
#: What a draft held only by a confirm hold (:data:`CONFIRM_HOLD`,
#: decision 140) is refused with, beside :data:`HELD_REFUSAL`: there is no
#: question of the client resending anything - the parked file may be
#: exactly what was asked for - only of a person here confirming it. Said
#: of the confirm-held rows alone; a draft held both ways says both.
CONFIRM_REFUSAL = (
    "the reminder is held until a person confirms the parked file (open it in Needs Review) "
    "- {listed}; nothing was written"
)
#: The one line the app shows for a held reminder (through the API's vocabulary).
HELD_SUMMARY = "Reminder held: {n} request(s) need a decision"
#: Why a reminder waits for the sort (decision 133): the household's own
#: ``Drop files here`` still holds files the sort has not taken - one that
#: failed to sort, a transfer still in flight, a name the machine cannot
#: handle, one that landed after the sort, or a household with two open
#: years whose inbox is not read at all. The letter cannot know which
#: request such a file answers, so the whole draft waits, as decision
#: 115's does. What the run log, the practice page's note and the CLI say
#: (through :func:`held_refusal`), and what :func:`write_draft` refuses with.
INBOX_HOLD = ("held - {n} file(s) the client sent are still waiting in Drop files here "
              "and have not been sorted yet")
#: The app's line for a reminder the inbox holds (through the API's vocabulary).
INBOX_HELD_SUMMARY = "Reminder held: {n} file(s) still waiting to be sorted"
#: The what-changed block a regenerated draft opens with, above the line a
#: person pastes: the earlier draft's day, then each request now asked that
#: was not, and each no longer asked that was.
CHANGED_HEADING = "Changed since the draft of {date}:"
CHANGED_ADDED = "  + {label}   (now asked)"
CHANGED_REMOVED = "  - {label}   (no longer asked)"
#: The footer's warning about parked files, and what to do about it.
REVIEW_WARNING = "{n} file(s) the client already sent are still in " + REVIEW_DIR_NAME + "."
REVIEW_ADVICE = "Identify them before sending, or you may ask for something you have."
#: What a draft says, above the letter's footer and on the command line,
#: when the recorded link is not a web address (decision 137, L5). The
#: letter is written without it - it says "the folder we shared with you"
#: as a letter with no link does - and a person is told why and where to
#: fix it, because a link recorded before the rule is not refused anywhere
#: else.
LINK_DROPPED = ("The link '{link}' was left out of this letter: it is not a web address "
                "(http:// or https://). Fix it in the household's or the return's details.")
#: What a Partial row is asked with.
PARTIAL_ASK = "{have} of {expected} received, {missing} still to come"
#: The file-type ask, in the row's own terms (the reason's generic ask is for rows that take anything).
EXTENSION_ASK = "we cannot open that file type; please send it as {accepted}"
#: What the file-type ask adds where the row accepts a PDF (decision 127):
#: an image is a scan, so a photo of the document is one of the things
#: that row will take, and the client should be told so in the same breath.
EXTENSION_ASK_PHOTO = "a photo"
PARTIAL_ASK_COMPLETE = "{have} of {expected} received"

SECTION_MISSING = "NOT YET RECEIVED"
SECTION_PARTIAL = "STARTED, BUT NOT COMPLETE"
#: The section a Failed row used to be asked under. Unreachable from a pass
#: since decision 115 - a Failed row with no firm-side marker holds the
#: draft instead - so it is not in ``SECTION_ORDER``; the name stays because
#: an "ask the client again" action a person records would put a row here.
SECTION_FAILED = "RECEIVED, BUT WE COULD NOT USE IT"

SECTION_ORDER = (SECTION_MISSING, SECTION_PARTIAL)

#: What stands in front of the subject line, in the text a person pastes
#: and on the card that shows it. One prefix, so the two cannot differ.
SUBJECT_PREFIX = "Subject: "


# ------------------------------------------------- the card's own words ----
# Decision 118: the reminder gets a surface in the app. Every word on it is
# here, because the renderer types none - it reads the API's vocabulary,
# and the API reads this module.

#: The card's heading, and the name a screen reader gives the preview.
REMINDER_HEADING = "Reminder"
#: What a screen reader calls the four-button stage toggle.
STAGE_GROUP_LABEL = "Stage"
#: The card's three buttons. Nothing sends: one puts the letter on the
#: clipboard, one makes the shown text this week's draft, one opens the
#: file a person has always been able to open.
COPY_LABEL = "Copy for Outlook"
APPROVE_LABEL = "Approve"
OPEN_DRAFT_LABEL = "Open the draft file"
#: What the card's status line says: the record's last word on the draft.
LAST_DRAFTED_LINE = "last drafted {date} at stage {n}"
NEVER_DRAFTED_LINE = "not drafted yet"
APPROVED_LINE = "approved {date} at stage {n}"
#: Why the toggle is dead on a draft somebody has already worked on, and
#: what the practice page's Drafted column says about an approved one.
EDITED_BY_HAND = "edited by hand - approve it as it stands, or delete it to regenerate at a stage"
APPROVED_NOTE = "approved"
#: The sentence under the toggle: the pass chose the rung, and moving it is
#: a person's call, made before they send and not recorded as a fact.
STAGE_TOGGLE_HINT = ("the pass pre-selects the stage from the Due Date; move it up or down "
                     "before you send")
#: What is said after the letter goes on the clipboard. It names what was
#: copied and what was not, because the subject belongs in Outlook's own
#: box and a person who pasted the body would otherwise look for it.
COPIED_NOTE = ("the letter is on the clipboard - paste it into Outlook as the body; "
               "the subject line is on the card above it")
#: What is said about a draft an approval moved out of the way.
SET_ASIDE_LINE = "the other draft was set aside as {name}"


# ----------------------------------------------------------------- stages ----


@dataclass(frozen=True, slots=True)
class Stage:
    """One rung of the reminder: its name, its subject and its three sentences.

    Every word a stage says is here and nowhere else, so the letters a
    client reads are one table a person can be shown - the owner signs the
    wording off, and nothing downstream retypes a phrase of it.
    """

    number: int
    name: str
    subject: str        # the SUBJECT template: {engagement}, {n}
    intro: str          # straight after the greeting: {engagement}
    #: The paragraph after the drop-anywhere lines; "" for none.
    #: {target}, {deadline_clause}, {phone_clause}
    deadline: str
    close: str          # the last sentence before the sign-off: {phone_clause}


#: How far from the Due Date each stage begins, in days. Constants and not
#: settings (the owner, 2026-09-20): the ladder is the firm's one way of
#: chasing, and a per-engagement threshold would be a second answer to
#: "how hard are we asking this client?" that nobody could see from the
#: draft.
STAGE_2_DAYS = 21
STAGE_3_DAYS = 10
#: The consequences sentence of the final notice; it speaks for the firm and
#: its wording is the owner's.
STAGE_4_CONSEQUENCES = ("Without them, we cannot guarantee your return will be completed by the deadline, "
                        "which may result in late-filing penalties or the need to file an extension.")
#: The filing deadline said beside the target, when the engagement records
#: one; blank when it does not, because a deadline nobody recorded is not a
#: date this system may tell a client.
DEADLINE_CLAUSE = " - ahead of the filing deadline of {deadline}"
#: The final notice's offer of a telephone call, dropped when the firm has
#: recorded no number.
PHONE_CLAUSE = ", or call us right away at {phone} so we can discuss your options"

#: The four stages, in order. The list of requests and the drop-anywhere
#: lines are the same in all of them; only these sentences change.
STAGES: tuple[Stage, ...] = (
    Stage(
        number=1,
        name="Just a Heads Up",
        subject=SUBJECT_NEEDED,
        intro="Just a quick heads up that we're still waiting on a few items to get started "
              "on your return. Whenever you get a chance, here's what we have outstanding "
              "for {engagement}:",
        deadline="",
        close="Just wanted to keep it on your radar. Let us know if you have any questions "
              "or if something's already on its way.",
    ),
    Stage(
        number=2,
        name="Checking In",
        subject=SUBJECT_NEEDED,
        intro="Checking in on your return. We're still missing a few items for {engagement} "
              "and wanted to make sure they didn't slip through the cracks:",
        deadline="As a reminder, our firm asks to have everything in hand ahead of the filing "
                 "deadline, which gives us time to prepare and file your return properly. "
                 "For you that means we'd need these by {target}.",
        close="Let us know if you have any questions or if anything's already on its way.",
    ),
    Stage(
        number=3,
        name="Response Requested; Deadline Approaching",
        subject=SUBJECT_RESPONSE,
        intro="We still need the following items to complete your return, and the deadline "
              "is approaching:",
        deadline="To file on time, our firm needs these by {target}{deadline_clause}, and we "
                 "hold to that so there is enough time to prepare your return properly. At "
                 "this point we do need these items promptly to stay on track.",
        close="Please send them as soon as you can, or reply to let us know when we can "
              "expect them.",
    ),
    Stage(
        number=4,
        name="URGENT! Final Notice",
        subject=SUBJECT_URGENT,
        intro="This is an urgent final notice regarding your return. We have now reached or "
              "passed our firm's cutoff to receive your documents, and we still need the "
              "following:",
        deadline="Our firm's deadline to receive everything is {target}{deadline_clause}. We "
                 "need these items immediately to file your return on time. " + STAGE_4_CONSEQUENCES,
        close="Please send everything today{phone_clause}.",
    ),
)

#: What the draft's header says the stage is, above the fingerprint line and
#: so outside the text a person pastes: the stage is a fact about the draft,
#: not a sentence in the email.
STAGE_LINE = "Stage: {number} - {name}"
#: And what it says when there is no stage at all - a quiet week, where the
#: draft says we have everything and no ladder applies.
STAGE_NONE = "Stage: -"
#: The key the ``DRAFTED`` event carries the stage under. A number, never a
#: word of the letter: nothing a client would read goes on the record.
STAGE_KEY = "stage"


# ------------------------------------------------- the ladder of emphasis ----


@dataclass(frozen=True, slots=True)
class Emphasis:
    """Where one stage spends its colour and its weight, and nowhere else.

    Eight flags, all off by default, so a stage that emphasises nothing is
    the empty one. Read by the letter's HTML renderer and shipped to the
    app in the API's vocabulary, so the card's preview and the body on the
    clipboard apply one table rather than two readings of a brief.
    """

    subject_colour: bool = False
    subject_bold: bool = False
    list_colour: bool = False
    list_bold: bool = False
    #: The whole deadline paragraph.
    deadline_colour: bool = False
    #: The two dates inside it - the target and the filing deadline.
    dates_bold: bool = False
    #: The target date alone, which is all stage 2 marks.
    target_colour: bool = False
    #: The final notice's consequences sentence.
    consequences_bold: bool = False


#: Which of :data:`tracker.page.PALETTE`'s colours each stage carries: the
#: toggle's ink in the app, and the letter's one colour. Stage 1's is the
#: body's own ink, so applying it colours nothing - the toggle needs a
#: colour for every rung and the letter needs none at the first, and one
#: table serves both.
STAGE_COLOURS = {1: "slate_600", 2: "gold_800", 3: "warning_600", 4: "danger_600"}
#: What a held reminder is said in: the hold line and the rule beside each
#: held row. Not a rung of the ladder - a hold is not a letter - but the
#: same warning the third rung carries, because it is the same kind of
#: "this needs you" the card is asking for.
HOLD_COLOUR = "warning_600"
#: The letter's own surface, by palette key: the body's ink, the quieter
#: ink its section headings take, and the paper under both.
LETTER_INK = {"body": "slate_600", "muted": "grey_500", "paper": "white"}

#: The ladder, in one place. Stage 4 marks the subject and the list, and
#: inside the deadline paragraph the two dates and the consequences
#: sentence, while the connective text is not: a fully bold paragraph
#: reads as shouting, and the letter is still meant to be respectful.
STAGE_EMPHASIS = {
    1: Emphasis(),
    2: Emphasis(target_colour=True),
    3: Emphasis(deadline_colour=True, dates_bold=True, list_bold=True),
    4: Emphasis(subject_colour=True, subject_bold=True, deadline_colour=True, dates_bold=True,
                consequences_bold=True, list_colour=True, list_bold=True),
}


class ReminderError(Exception):
    """A reminder could not be drafted from this engagement."""


#: What the run says when it left both drafts alone.
BOTH_DRAFTS_EDITED = (
    f"{DRAFT_FILENAME} and {NEW_DRAFT_FILENAME} have both been edited; this week's "
    "draft was not written - send or delete one of them first"
)


class DraftsEditedError(ReminderError):
    """Both draft files carry a person's edits; nothing was overwritten."""


class ReminderHeldError(ReminderError):
    """An ambiguous row (decision 115) or a file waiting in the household's
    inbox (decision 133) holds the draft; nothing was written."""


@dataclass(frozen=True, slots=True)
class ReminderLine:
    """One bullet in the draft: a request, and what we are asking for."""

    item: RequestItem
    section: str
    ask: str = ""          # client-facing sentence; "" for a plain "not received"

    @property
    def label(self) -> str:
        return self.item.label

    def render(self) -> str:
        line = f"  - {self.label}"
        if self.ask:
            line += f" - {self.ask}"
        return line


@dataclass(frozen=True, slots=True)
class FirmSideFlag:
    """Something for the accountant to handle, never put to the client."""

    item: RequestItem
    reason: str
    #: True for a confirm hold (decision 140): the row is held because a
    #: parked file that may be it waits for a person here, not because the
    #: client might have to resend. It picks the refusal sentence
    #: (:data:`CONFIRM_REFUSAL` rather than :data:`HELD_REFUSAL`).
    confirm: bool = False


@dataclass(frozen=True, slots=True)
class Run:
    """One stretch of the deadline paragraph, and what it is.

    ``kind`` is "" for the connective text, or ``target``,
    ``deadline_date`` or ``consequences`` for the three things a stage may
    mark. The runs are cut by formatting the stage's own sentence with
    sentinels around those values and splitting on them - never by looking
    for a date in the finished sentence, which an engagement's name could
    also contain.
    """

    text: str
    kind: str = ""


@dataclass(frozen=True, slots=True)
class Section:
    """One heading of the letter with the request lines under it."""

    heading: str
    items: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class Letter:
    """The letter as a shape, before it is words on a page (decision 118).

    The text a person pastes and the HTML body that goes on the clipboard
    are two renderings of this one structure, so they cannot say different
    things, and the app's preview is drawn from it as DOM nodes - the page
    is built from data and never from an HTML string. ``intro`` may carry
    its own line breaks (the quiet week's paragraph is written wrapped);
    ``deadline`` is empty when the stage has no such paragraph or the
    engagement has no Due Date to name in it.
    """

    greeting: str
    progress: str = ""
    intro: str = ""
    sections: tuple[Section, ...] = ()
    drop: tuple[str, ...] = ()
    link: str = ""
    deadline: tuple[Run, ...] = ()
    close: str = ""
    signoff: tuple[str, ...] = ()
    stage: int = 0

    @property
    def deadline_text(self) -> str:
        """The deadline paragraph as one sentence again."""
        return "".join(run.text for run in self.deadline)

    def text(self) -> str:
        """The body a person pastes: this structure as plain lines.

        The one place the letter becomes text. Every other rendering -
        the HTML for the clipboard, the app's preview - starts from the
        same fields, so a sentence cannot reach a client in one and not
        the other.
        """
        out: list[str] = [self.greeting, ""]
        if self.progress:
            out += [self.progress, ""]
        if self.intro:
            out += [*self.intro.split("\n"), ""]
        for section in self.sections:
            out += [section.heading, *section.items, ""]
        if self.drop:
            out += list(self.drop)
            if self.link:
                out.append(f"  {self.link}")
            out.append("")
        if self.deadline:
            out += [self.deadline_text, ""]
        if self.close:
            out += [self.close, ""]
        out += list(self.signoff)
        return "\n".join(out).rstrip() + "\n"


@dataclass(slots=True)
class ReminderDraft:
    """A drafted reminder. Nothing here has been, or will be, sent."""

    engagement: str
    subject: str
    body: str
    #: Which of the four stages this draft is written at (decision 117),
    #: and 0 on a quiet week - there is no ladder when we have everything.
    stage: int = 0
    lines: list[ReminderLine] = field(default_factory=list)
    needs_attention: list[FirmSideFlag] = field(default_factory=list)
    #: The ambiguous rows (decision 115). One of these holds the whole draft.
    held: list[FirmSideFlag] = field(default_factory=list)
    #: How many files the household's own ``Drop files here`` holds that
    #: the sort has not taken (decision 133). Any at all holds the whole
    #: draft, as one ambiguous row does; ``held`` stays the rows alone.
    unsorted: int = 0
    needs_review_files: int = 0
    total_requests: int = 0
    received_requests: int = 0
    #: Every request on the list, identifier -> label, so a what-changed
    #: line can name a request the draft no longer asks for.
    labels: dict[str, str] = field(default_factory=dict)
    #: The letter this draft's body was rendered from (decision 118). The
    #: body is its text; the HTML for the clipboard and the app's preview
    #: are the same structure rendered two other ways.
    letter: Letter | None = None
    #: :data:`LINK_DROPPED` when the recorded link was left out because it
    #: is not a web address (decision 137, L5), else ``""``.
    link_dropped: str = ""

    @property
    def has_outstanding(self) -> bool:
        return bool(self.lines)

    @property
    def is_held(self) -> bool:
        """An ambiguous row (decision 115), or a file still waiting in the
        household's inbox (decision 133), holds this draft: nothing may be
        written from it."""
        return bool(self.held) or self.unsorted > 0

    @property
    def asked(self) -> list[str]:
        """The identifiers the draft asks for, in the draft's order."""
        return [line.item.identifier for line in self.lines]

    @property
    def text(self) -> str:
        """Subject and body as one block, ready to paste into an email."""
        return f"{SUBJECT_PREFIX}{self.subject}\n\n{self.body}"

    def section(self, name: str) -> list[ReminderLine]:
        return [line for line in self.lines if line.section == name]


def stage_for(due: dt.date | None, today: dt.date) -> int:
    """Which stage a reminder written ``today`` is at, given the Due Date.

    The one rule, and the only thing that decides a stage: how far today is
    from the date the firm asked the client to send things by. An
    engagement with no Due Date is at stage 1 for ever - a heads-up with no
    deadline sentence, which is the only honest letter when nobody has said
    when things are due.

    The day itself is stage 4, not stage 3: "we need these by the 10th" on
    the 10th is a sentence that has already stopped being true.
    """
    if due is None:
        return 1
    days = (due - today).days
    if days > STAGE_2_DAYS:
        return 1
    if days > STAGE_3_DAYS:
        return 2
    if days > 0:
        return 3
    return 4


def stage_named(number: int) -> Stage:
    """The stage numbered ``number``; anything else is a loud refusal."""
    for stage in STAGES:
        if stage.number == number:
            return stage
    raise ReminderError(
        f"there is no stage {number}; the stages are "
        f"{', '.join(str(stage.number) for stage in STAGES)}"
    )


# ------------------------------------------------------------ translation ----


def client_ask(item: RequestItem) -> str:
    """One plain sentence telling the client what to do about ``item``.

    Driven by the scanner's validation note, never quoting it. A Partial
    row's sentence is the count, and the row's own reason after it when the
    note carries a client-side one. A Failed row's sentence still translates
    here - the generic ask when nothing in the note is recognised - but
    since decision 115 no pass asks it: :func:`triage` holds a Failed row
    for a person instead, and this branch waits for the action that would
    put one back to the client on a person's say-so.
    """
    if item.status == Status.PARTIAL:
        expected = item.expected_count
        have = item.file_count or 0
        missing = max(expected - have, 0)
        ask = (PARTIAL_ASK.format(have=have, expected=expected, missing=missing)
               if missing else PARTIAL_ASK_COMPLETE.format(have=have, expected=expected))
        # A count alone hides why: the client who sent both W-2s, one of
        # them password-protected, is told what to fix, not just "1 of 2".
        reason = reasons.find(item.validation_notes or "")
        if reason is not None and not reason.firm_side:
            ask = f"{ask}; {_ask_for(reason, item)}"
        return ask

    if item.status != Status.FAILED:
        return ""

    reason = reasons.find(item.validation_notes or "")
    return _ask_for(reason, item) if reason else GENERIC_ASK


def _ask_for(reason: reasons.Reason, item: RequestItem) -> str:
    """The reason's client ask, in the row's own terms where it has them:
    "a PDF or an Excel file" would send a client whose row wants a
    spreadsheet round the loop again.

    A row that takes a PDF takes a photo of the same document (decision
    127), so it is offered - and a row that wants a spreadsheet still is
    not, because a photo of a general ledger is no use to anybody.
    """
    if reason is reasons.EXTENSION_NOT_ALLOWED and item.allowed_extensions:
        accepted = [f".{ext}" for ext in item.allowed_extensions]
        if PDF_EXTENSION in item.allowed_extensions:
            accepted.append(EXTENSION_ASK_PHOTO)
        return EXTENSION_ASK.format(accepted=" or ".join(accepted))
    return reason.client_ask


def _firm_side_reason(item: RequestItem) -> str:
    """Why this row is the firm's problem rather than the client's, or ""."""
    note = item.validation_notes or ""
    for reason in reasons.FIRM_SIDE:
        if reason.matches(note):
            return reason.firm_side_note
    return ""


def _missing_detail(item: RequestItem) -> str:
    return item.expected_text


# ---------------------------------------------------------------- sorting ----


def _section_for(item: RequestItem) -> str:
    return {
        Status.MISSING: SECTION_MISSING,
        Status.PARTIAL: SECTION_PARTIAL,
    }[item.status]


def _ambiguous_reason(item: RequestItem) -> str:
    """Why this row holds the draft, or "" when it does not (decision 115).

    Called for a row no firm-side marker claimed. A Failed row is ambiguous
    as it stands: something arrived and the rules refused it, and whether
    the client resends or we fix it here is not the draft's to decide. A
    Partial row is ambiguous when its shortfall is a refused file - the
    note carries a client-side reason - rather than a file that never came.
    The reason's own sentence rides in brackets so the person sees what the
    scan said.
    """
    reason = reasons.find(item.validation_notes or "")
    if item.status == Status.FAILED:
        return f"{AMBIGUOUS_HOLD} ({_ask_for(reason, item)})" if reason else AMBIGUOUS_HOLD
    if item.status == Status.PARTIAL and reason is not None:
        return f"{AMBIGUOUS_HOLD} ({_ask_for(reason, item)})"
    return ""


def _parked_holds(items: Sequence[RequestItem], parked: Sequence) -> dict[str, FirmSideFlag]:
    """Which requests a parked file the client could fix holds, and why.

    Decision 117, the end-to-end review's third discrepancy. A drop the
    rules refused at tier 2 - a locked PDF, an empty upload, a file type
    nothing accepts - never reaches a request's status: it parks for a
    person, the request stays Missing, and the draft asked for it as if
    nothing had come. The client, who sent it, reads that as a firm that
    loses things.

    A parked row holds a request when both halves are true: its reason is
    one that holds (``Reason.holds``), and the review queue's own shortlist
    for that row names the request. Every reason the *client* could fix
    holds; a firm-side one - a scan with no text layer, a file nobody here
    has read - does not, because decision 115's rule that we never chase a
    client for our own work stands. The one firm-side reason that holds is
    decision 140's: a read document that matched no request and shows a
    request's form number. It holds, because asking for a W-2 the client
    sent while it waits in review is the letter this exists to stop; and
    its sentence (:data:`CONFIRM_HOLD`) blames no file, because the file
    may be perfectly good. Whether a reason holds is its own property, read
    here and nowhere else, so "whose problem" and "does it hold" can never
    be answered by one flag again.

    **The shortlist, not the row's Candidates cell.** Candidates are the
    router's column - the requests that *accepted* the file - and a file
    the rules refused before reading it has none, which is exactly the
    headline case: the password-protected PDF the client is certain they
    sent. :func:`tracker.review.shortlist_for` is what the card shows the
    person looking at that file, evidence and all, including what its own
    name said (decision 92, and the router records it beside a refusal it
    could not read through). So the draft and the card now agree about
    what a parked file points at, and a parked row that points at nothing
    holds nothing - there is no request to name in the sentence, and no
    client to ask about it.

    Only rows the filer parked are read: a row a person dismissed is their
    answer, and a row they filed or unfiled is a decision, not a question.

    **A parked row whose copy and original are both gone** (decision 157,
    ruling B5, and its review's S-1) still holds. The pass turns it into
    ``FILE_MOVED`` with the both-gone sentence, keeping what it said before,
    and it has no identifier because nobody filed it. Nobody has looked at
    the file either, so the question it raised is still open: the request
    it points at stays held until a person decides (an override, or the
    file coming back). A set-aside row that went the same way does not: its
    Reason still starts with the person's answer.
    """
    from tracker.filer import DISMISSED_BY_PERSON, NEEDS_REVIEW, both_gone
    from tracker.review import shortlist_for

    def still_parked(row) -> bool:
        if row.decision == NEEDS_REVIEW:
            return True
        return (both_gone(row) and not row.identifier
                and not (row.reason or "").startswith(DISMISSED_BY_PERSON))

    rows = {item.identifier: item for item in items}
    listed = list(items)
    holds: dict[str, FirmSideFlag] = {}
    for row in parked:
        if not still_parked(row):
            continue
        reason = reasons.find(row.reason or "")
        if reason is None or not reason.holds:
            continue
        for suggestion in shortlist_for(row, listed):
            item = rows.get(suggestion.identifier)
            if item is not None:
                holds[suggestion.identifier] = (
                    FirmSideFlag(item=item, reason=CONFIRM_HOLD.format(note=reason.firm_side_note),
                                 confirm=True) if reason.firm_side
                    else FirmSideFlag(item=item, reason=PARKED_HOLD.format(ask=_ask_for(reason, item))))
    return holds


def triage(items: Sequence[RequestItem], parked: Sequence = ()) -> tuple[
    list[ReminderLine], list[FirmSideFlag], list[FirmSideFlag]
]:
    """Sort every outstanding row once, by one rule: client asks (``lines``),
    firm-side work (``attention``) and the ambiguous rows that hold the
    whole draft (``held``, decisions 115 and 117). The fourth list, the
    scaffold gaps - a request whose folder was missing - retired with the
    folder per request (decision 168).

    A row nobody asked for (decision 142) is dropped first, whatever its
    status or notes. Overridden rows and anything already in are dropped
    here too and never reach the draft. For the rest, in this order: a row carrying any
    firm-side marker, on any outstanding
    status, is the firm's (decisions 20, 21, 58, and 109's rule for a
    Missing row); a Failed row, or a Partial whose shortfall is a refused
    file, is ambiguous and held; a Missing row, and a Partial with no
    reason, is asked.

    ``parked`` is the engagement's index rows, when the caller has them
    (:func:`_parked_holds`): a request that would have been asked for, and
    that a file the client could fix points at, is held instead. It is
    applied last and only to what was going to be asked, so a row already
    the firm's, already held, already overridden or already in stays
    exactly where the rules above put it.
    """
    lines: list[ReminderLine] = []
    attention: list[FirmSideFlag] = []
    held: list[FirmSideFlag] = []

    for item in items:
        # Decision 142: a row nobody asked for is never chased, and is
        # skipped before anything else.
        if not item.asked:
            continue
        if item.manual_override or item.status not in OUTSTANDING:
            continue

        # A row we have not read is ours, not the client's, whatever its
        # status. A Partial row whose shortfall is a file we have not read
        # is ours too: the client may well have sent everything, and "1 of
        # 2 received" would tell them otherwise.
        reason = _firm_side_reason(item)
        if reason:
            if item.status == Status.PARTIAL:
                reason = reasons.FIRM_WAITING_PARTIAL
            attention.append(FirmSideFlag(item=item, reason=reason))
            continue

        ambiguous = _ambiguous_reason(item)
        if ambiguous:
            held.append(FirmSideFlag(item=item, reason=ambiguous))
            continue

        section = _section_for(item)
        ask = client_ask(item) if section != SECTION_MISSING else _missing_detail(item)
        lines.append(ReminderLine(item=item, section=section, ask=ask))

    holds = _parked_holds(items, parked)
    if holds:
        asked: list[ReminderLine] = []
        for line in lines:
            flag = holds.get(line.item.identifier)
            if flag is not None:
                held.append(flag)
            else:
                asked.append(line)
        lines = asked

    order = {name: i for i, name in enumerate(SECTION_ORDER)}
    lines.sort(key=lambda line: (order[line.section], line.item.identifier))
    held.sort(key=lambda flag: flag.item.identifier)
    return lines, attention, held


def count_needs_review(engagement_dir: Path) -> int:
    """Files parked in ``REVIEW_DIR_NAME`` — already sent, not yet identified.

    Counted from the folder, not from the index, because a file somebody
    dragged in by hand is still a file nobody has identified. The index only
    takes files *out* of the count: a row a person marked ``NOT_REQUESTED``
    has been looked at, and the whole point of the warning is that a person
    may be about to ask for something already in hand. A row they have seen
    is not that.

    A document a person set aside and the client then sent again is parked
    afresh, with a working copy of its own and a row of its own (decision
    111), so it counts here as any parked file does - the set-aside copy
    beside it still does not, and the warning says the client sent something
    nobody has looked at yet, which is what it has always said.

    An index that cannot be read leaves every file counted. The warning is
    the loud side of the choice, and the index is the filer's to complain
    about, not the draft's.
    """
    from tracker.filer import NOT_REQUESTED, read_index

    review = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    parked = iter_candidate_files(review)
    if not parked:
        return 0
    try:
        rows = read_index(engagement_dir)
    except Exception as exc:
        log.warning("Could not read the index for the files a person has seen: %s", exc)
        return len(parked)
    # The newest row for a working copy is the one that counts: a name freed
    # and taken by the next drop called the same is not the earlier decision.
    newest = {row.prepared_location: row for row in rows if row.prepared_location}
    seen = {
        locate(engagement_dir, location)
        for location, row in newest.items() if row.decision == NOT_REQUESTED
    }
    return sum(1 for path in parked if path not in seen)


# ----------------------------------------------------------------- drafts ----


def _said_date(when: dt.date) -> str:
    """A date as a client reads it. One format, both dates."""
    return when.strftime("%B %d, %Y")


#: What marks a run of the deadline paragraph while it is being cut up. A
#: character no letter can carry, written round the value and its kind, so
#: the sentence is split on what was put into it rather than searched for
#: what might be in it.
_RUN_MARK = "\x00"
#: The three things a stage may mark inside that paragraph.
RUN_TARGET = "target"
RUN_DEADLINE_DATE = "deadline_date"
RUN_CONSEQUENCES = "consequences"
#: The two continuations of the drop-anywhere sentence: with a share link
#: to give, and without one.
DROP_WITH_LINK = "folder. One folder, no sorting and no naming needed; we do that:"
DROP_NO_LINK = "folder we set up. One folder, no sorting and no naming needed."
#: The quiet week's paragraph, wrapped as it is written into the file.
NOTHING_OWED = ("Good news - we have everything we asked for on {engagement}.\n"
                "Nothing further is needed from you right now, and we will be in\n"
                "touch if anything else comes up.")
#: How every letter signs off, above the sender and the firm.
SIGN_OFF = "Thank you,"


def _marked(kind: str, text: str) -> str:
    return f"{_RUN_MARK}{kind}{_RUN_MARK}{text}{_RUN_MARK}"


def _cut_runs(marked: str) -> tuple[Run, ...]:
    """A sentence with marked values in it, cut into runs in order."""
    parts = marked.split(_RUN_MARK)
    runs: list[Run] = [Run(parts[0])] if parts[0] else []
    for i in range(1, len(parts) - 1, 3):
        runs.append(Run(parts[i + 1], parts[i]))
        tail = parts[i + 2]
        if tail:
            runs.append(Run(tail))
    return tuple(runs)


def _deadline_runs(stage: Stage, *, engagement: str, due_date: dt.date,
                   filing_deadline: dt.date | None, phone: str) -> tuple[Run, ...]:
    """The stage's deadline paragraph, cut where its emphasis lands."""
    marked = stage.deadline.format(
        engagement=engagement,
        target=_marked(RUN_TARGET, _said_date(due_date)),
        deadline_clause=(DEADLINE_CLAUSE.format(
            deadline=_marked(RUN_DEADLINE_DATE, _said_date(filing_deadline)))
            if filing_deadline else ""),
        phone_clause=PHONE_CLAUSE.format(phone=phone) if phone else "",
    )
    # The consequences sentence is concatenated into stage 4's paragraph
    # rather than substituted into it, so it is marked by the constant it
    # is - a whole sentence this module owns, carrying no value of anyone's.
    marked = marked.replace(STAGE_4_CONSEQUENCES,
                            _marked(RUN_CONSEQUENCES, STAGE_4_CONSEQUENCES))
    return _cut_runs(marked)


def progress_line(received: int, total: int, also_received: int = 0) -> str:
    """The letter's count, in Jason's words (decision 142), or nothing when
    nothing has arrived at all.

    ``Of the 5 items we asked for, 1 is in.`` - the asked rows only - and,
    only when a document arrived for a row nobody asked for, ``We have also
    received 2 other documents from you.`` When nothing asked for is in
    but other documents are, Jason's softer pair instead:
    ``We have received 2 documents from you, thank you. The 5 items we
    asked for are still needed.`` Each noun and verb agrees with its
    number, because this is a sentence a client reads.
    """
    if not received and not also_received:
        return ""
    if not received:
        return PROGRESS_NONE_ASKED.format(
            k=also_received, documents="document" if also_received == 1 else "documents",
            m=total, items="item" if total == 1 else "items", verb="is" if total == 1 else "are")
    said = PROGRESS_ASKED.format(m=total, items="item" if total == 1 else "items",
                                 n=received, verb="is" if received == 1 else "are")
    if also_received:
        said += " " + PROGRESS_ALSO.format(
            k=also_received, documents="document" if also_received == 1 else "documents")
    return said


def _compose_letter(
    lines: Sequence[ReminderLine],
    *,
    client_name: str,
    engagement: str,
    share_link: str,
    due_date: dt.date | None,
    sender: str,
    firm: str,
    received: int,
    total: int,
    stage: Stage | None,
    filing_deadline: dt.date | None = None,
    phone: str = "",
    also_received: int = 0,
) -> Letter:
    """The letter as a shape: the greeting, the stage's own three sentences
    around the list, and the sign-off.

    ``stage`` is None only on a quiet week, where there is nothing to chase
    and no ladder to be on. The deadline paragraph is written only when the
    engagement has a Due Date to name: a stage the caller forced with no
    date to put in it drops the paragraph rather than printing half of it.
    """
    greeting = f"Hi {client_name}," if client_name else "Hello,"
    signoff = (SIGN_OFF, *(name for name in (sender, firm) if name))

    if not lines or stage is None:
        return Letter(greeting=greeting, intro=NOTHING_OWED.format(engagement=engagement),
                      signoff=signoff)

    words = {
        "engagement": engagement,
        "target": _said_date(due_date) if due_date else "",
        "deadline_clause": (DEADLINE_CLAUSE.format(deadline=_said_date(filing_deadline))
                            if filing_deadline else ""),
        "phone_clause": PHONE_CLAUSE.format(phone=phone) if phone else "",
    }
    sections = tuple(
        Section(name, tuple(line.render() for line in lines if line.section == name))
        for name in SECTION_ORDER
        if any(line.section == name for line in lines)
    )
    return Letter(
        greeting=greeting,
        progress=progress_line(received, total, also_received),
        intro=stage.intro.format(**words),
        sections=sections,
        drop=(DROP_ANYWHERE, DROP_WITH_LINK if share_link else DROP_NO_LINK),
        link=share_link,
        deadline=(_deadline_runs(stage, engagement=engagement, due_date=due_date,
                                 filing_deadline=filing_deadline, phone=phone)
                  if stage.deadline and due_date else ()),
        close=stage.close.format(**words),
        signoff=signoff,
        stage=stage.number,
    )


def _parked_index_rows(engagement_dir: Path) -> list:
    """The engagement's index rows, for the parked-file hold (decision 117).

    An index that cannot be read holds nothing: the hold names a request a
    parked file points at, and a shortlist nobody could read names none.
    The draft is still written, and the index is the filer's to complain
    about - the same division :func:`count_needs_review` makes.
    """
    from tracker.filer import read_index

    try:
        return read_index(engagement_dir)
    except Exception as exc:
        log.warning("Could not read the index for the files a person is holding: %s", exc)
        return []


def unsorted_in_inbox(engagement_dir: Path | str) -> int:
    """How many files this return's own household inbox holds that the sort
    has not taken (decision 133): every distinct path the filer's three
    walks name - a drop waiting to be sorted (``iter_drops``), a transfer
    still in progress (``unfinished_drops``) and a name the machine cannot
    handle (``unreachable_drops``). The README the firm writes there and a
    sync client's junk are none of them. 0 when there is no inbox.

    **Only the return's own household's inbox** (decision 133's ruling 4).
    A drop folder in another household that also feeds this return
    (decision 132) is not read: that is another client's folder, and its
    arrivals are not this household's letter to decide.

    The one place the count is made - :func:`draft_reminder` asks it, so
    the pass, the command line and the app all hold alike - and the
    household card asks it too, for the same answer. The filer is imported
    here, at call time, as the rest of this module reaches it.

    **Two corrections from the review.** A temporary file the README's own
    atomic write left behind when it was killed (``README_NAME`` in
    :data:`tracker.fsio.TEMP_NAME`'s exact shape) is the firm's leftover,
    not a transfer the client started, and never holds a letter; the
    household pass sweeps it away first (decision 155), and this is for the
    one a live writer still holds. A folder the pass cannot list (``unlistable_folders``)
    does, one count per folder: whatever the client put in it cannot be
    sorted, so the letter could ask for it.
    """
    from tracker.filer import iter_drops, unfinished_drops, unlistable_folders, unreachable_drops

    inbox = inbox_of(Path(engagement_dir))
    waiting = {*iter_drops(inbox), *unfinished_drops(inbox), *unreachable_drops(inbox),
               *unlistable_folders(inbox)}
    return sum(1 for path in waiting if not _readme_leftover(path, inbox))


def _readme_leftover(path: Path, inbox: Path) -> bool:
    """Whether ``path`` is a temporary file the README's own write left in
    the inbox: beside the README, named after it in the exact shape every
    temp the tracker writes has (:func:`tracker.fsio.temp_owner`). The
    client's own ``.tmp`` files are not this."""
    return path.parent == inbox and temp_owner(path.name, target=README_NAME) is not None


def draft_reminder(
    engagement_dir: Path | str,
    *,
    client_name: str = "",
    engagement_name: str = "",
    share_link: str = "",
    due_date: dt.date | None = None,
    filing_deadline: dt.date | None = None,
    sender: str = "",
    firm: str = "",
    phone: str = "",
    today: dt.date | None = None,
    stage: int | None = None,
) -> ReminderDraft:
    """Draft the reminder for one engagement. Reads only; sends nothing.

    Who the client is, the share link, the two dates and the sign-off come
    from the engagement's details in the record - the one place they are
    kept - and the firm's telephone number from the settings beside the
    app, because it is the firm's and not this engagement's. The keyword
    arguments override all of it for a one-off (the CLI's flags); nothing
    else needs to pass them in.

    ``today`` is the day the letter is written on, and with the Due Date it
    decides the stage (:func:`stage_for`); ``stage`` forces one instead, so
    a person can read what next week's letter will say without waiting for
    next week. Neither changes who is asked.

    Raises :class:`ReminderError` when the folder holds no record or has
    never been scanned — a reminder built from unscanned rows would ask for
    documents the client may well have sent already.
    """
    from tracker.ledger import LEDGER_FILENAME

    engagement_dir = Path(engagement_dir)
    try:
        info = load_engagement_info(engagement_dir)
    except ManifestError:
        raise ReminderError(f"no record in {engagement_dir} ({LEDGER_FILENAME})") from None
    client_name = client_name or info.client
    engagement_name = engagement_name or info.name
    share_link = share_link or info.link
    # Only a web address reaches a letter (decision 137, L5). A link
    # recorded before that rule is dropped here, and the draft says so.
    link_dropped = ""
    if link_problem(share_link):
        link_dropped = LINK_DROPPED.format(link=share_link.strip())
        share_link = ""
    due_date = due_date or info.due
    filing_deadline = filing_deadline or info.filing_deadline
    sender = sender or info.sender
    firm = firm or info.firm
    phone = phone or firm_phone()
    today = today or dt.date.today()

    # Straight from the record, which is where every status is since
    # decision 103: what the last scan found is what this asks the client
    # for, and there is no second reading of a workbook to disagree with.
    items = load_manifest(engagement_dir)
    if not items:
        raise ReminderError(f"{engagement_dir} has no request rows")
    if not any(item.status for item in items):
        raise ReminderError(
            f"{engagement_dir} has no scan results yet; run "
            f"`python -m tracker.scanner {engagement_dir}` first"
        )

    lines, attention, held = triage(items, _parked_index_rows(engagement_dir))
    summary = summarize(items)
    received, total = summary.received, summary.total
    # The household, the year and the return, as everything that names one
    # return says it (decision 125) - or whatever a caller handed in, and
    # whatever the record's own ``name`` holds where one does.
    engagement = engagement_name or label_for(
        info.household or household_name_of(engagement_dir),
        info.tax_year if info.tax_year is not None else year_of(engagement_dir),
        info.return_name or engagement_dir.name,
    )

    # The stage is the letter's, so a week with nothing to chase has none:
    # "we have everything" is not a rung of a ladder.
    number = (stage if stage is not None else stage_for(due_date, today)) if lines else 0
    rung = stage_named(number) if number else None

    letter = _compose_letter(
        lines,
        client_name=client_name,
        engagement=engagement,
        share_link=share_link,
        due_date=due_date,
        sender=sender,
        firm=firm,
        received=received,
        total=total,
        also_received=summary.also_received,
        stage=rung,
        filing_deadline=filing_deadline,
        phone=phone,
    )
    body = letter.text()

    if rung is not None:
        subject = rung.subject.format(engagement=engagement, n=len(lines))
    else:
        subject = SUBJECT_COMPLETE.format(engagement=engagement)

    return ReminderDraft(
        engagement=engagement,
        subject=subject,
        body=body,
        stage=number,
        lines=lines,
        needs_attention=attention,
        held=held,
        unsorted=unsorted_in_inbox(engagement_dir),
        needs_review_files=count_needs_review(engagement_dir),
        total_requests=total,
        received_requests=received,
        labels={item.identifier: item.label for item in items},
        letter=letter,
        link_dropped=link_dropped,
    )


# ------------------------------------------------- the body, as Outlook reads it ----


def stage_emphasis(stage: int) -> Emphasis:
    """What this stage marks. A quiet week marks nothing."""
    return STAGE_EMPHASIS.get(stage, Emphasis())


def stage_colour(stage: int) -> str:
    """The colour this stage carries, as a value (decision 118). A letter
    at no stage is written in the body's own ink, which is stage 1's."""
    return page.PALETTE[STAGE_COLOURS.get(stage, STAGE_COLOURS[1])]


def _styled(tag: str, style: str, inner: str) -> str:
    return f'<{tag} style="{style}">{inner}</{tag}>'


def run_emphasis(run: Run, marks: Emphasis) -> tuple[bool, bool]:
    """Whether one run of the deadline paragraph is coloured, and whether it
    is bold, by the stage's own table.

    One answer, read by the body that goes on the clipboard and sent to the
    app beside the run itself, so the letter and the preview cannot mark
    different words - and so the page never has to know what a kind means.
    """
    colour = run.kind == RUN_TARGET and marks.target_colour
    bold = ((run.kind in (RUN_TARGET, RUN_DEADLINE_DATE) and marks.dates_bold)
            or (run.kind == RUN_CONSEQUENCES and marks.consequences_bold))
    return bool(colour), bool(bold)


def _emphasised(runs: Sequence[Run], marks: Emphasis, colour: str) -> str:
    """The deadline paragraph's runs, each wearing what its stage gives it."""
    out: list[str] = []
    for run in runs:
        text = page.esc(run.text)
        coloured, bold = run_emphasis(run, marks)
        if coloured:
            text = _styled("span", f"color: {colour};", text)
        if bold:
            text = _styled("b", "font-weight: bold;", text)
        out.append(text)
    return "".join(out)


def _paragraph(text: str, style: str) -> str:
    """One paragraph, its own line breaks kept as the breaks they are."""
    inner = "<br />".join(page.esc(line) for line in text.split("\n"))
    return _styled("p", style, inner)


def render_html(draft: ReminderDraft) -> str:
    """The letter as an HTML body, for the clipboard and for nothing else.

    The same words as :attr:`ReminderDraft.body` - both are renderings of
    one :class:`Letter` - with the stage's own emphasis where
    :data:`STAGE_EMPHASIS` puts it. **Inline styles only**: Outlook keeps
    an inline style and drops a style sheet, a class and a variable, so
    every colour here is a value out of :data:`tracker.page.PALETTE` and
    there is no ``<style>`` block, no class name and nothing fetched. The
    one address in it is the client's own share link, which is the point
    of the paragraph it sits in.

    It is never written to disk. The draft file is what the pass writes
    (decisions 11 to 15); this is rendered when a person asks for it and
    goes on the clipboard beside the plain text.
    """
    letter = draft.letter
    if letter is None:
        return ""
    ink = page.PALETTE[LETTER_INK["body"]]
    muted = page.PALETTE[LETTER_INK["muted"]]
    paper = page.PALETTE[LETTER_INK["paper"]]
    colour = stage_colour(letter.stage)
    marks = stage_emphasis(letter.stage)
    heading_style = (f"margin: 0 0 6px; font-family: {page.FONT_SERIF}; font-size: 13px; "
                     f"letter-spacing: 0.08em; color: {muted};")
    item_marks = ""
    if marks.list_colour:
        item_marks += f" color: {colour};"
    if marks.list_bold:
        item_marks += " font-weight: bold;"

    out = [f'<div style="font-family: {page.FONT_SANS}; font-size: 15px; line-height: 1.6; '
           f'color: {ink}; background-color: {paper};">']
    out.append(_paragraph(letter.greeting, "margin: 0 0 14px;"))
    if letter.progress:
        out.append(_paragraph(letter.progress, "margin: 0 0 14px;"))
    if letter.intro:
        out.append(_paragraph(letter.intro, "margin: 0 0 18px;"))
    for last, section in _with_last(letter.sections):
        out.append(_styled("p", heading_style, page.esc(section.heading)))
        out.append(f'<ul style="margin: 0 0 {18 if last else 16}px; padding: 0; list-style: none;">')
        for final, line in _with_last(section.items):
            margin = "margin: 0;" if final else "margin: 0 0 4px;"
            style = f"{margin} padding-left: 16px; text-indent: -16px;{item_marks}"
            out.append(_styled("li", style, page.esc(line.strip())))
        out.append("</ul>")
    if letter.drop:
        inner = page.esc(" ".join(letter.drop))
        if letter.link:
            address = page.esc(letter.link)
            inner += ("<br />" + f'<a href="{address}" style="padding-left: 16px; '
                      f'display: inline-block; color: {ink}; text-decoration: underline;">'
                      f"{address}</a>")
        out.append(_styled("p", "margin: 0 0 18px;", inner))
    if letter.deadline:
        style = "margin: 0 0 18px;"
        if marks.deadline_colour:
            style += f" color: {colour};"
        out.append(_styled("p", style, _emphasised(letter.deadline, marks, colour)))
    if letter.close:
        out.append(_paragraph(letter.close, "margin: 0 0 18px;"))
    if letter.signoff:
        out.append(_paragraph("\n".join(letter.signoff),
                              f"margin: 0; font-family: {page.FONT_SERIF}; font-size: 15px; "
                              f"line-height: 1.6; color: {ink};"))
    out.append("</div>")
    return "".join(out)


def pasted_text(path: Path | str) -> str:
    """The letter in a draft file: what lies between the header's rule and
    the footer's.

    Both rules fence off notes the machine wrote to the person, and neither
    side has ever been part of the email. Above: the banner, the stage, the
    fingerprint, what changed since the last draft. Below
    (:data:`FOOTER_RULE`): the rows the draft did not put to the client
    because they are ours, and the warning about files nobody has
    identified yet - firm-side sentences that must not be one paste from a
    client, which is exactly what the app's Copy for Outlook would make
    them (decision 118). A file with no header rule at all is not one this
    module wrote, so all of it is offered rather than none.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    _, separator, below = text.partition(_SEPARATOR + "\n")
    body = (below if separator else text).lstrip("\n")
    letter = body.split(f"\n{FOOTER_RULE}\n", 1)[0]
    return letter.rstrip("\n") + "\n" if letter.strip() else ""


def split_pasted(text: str) -> tuple[str, str]:
    """A pasted draft as its subject line and the body under it."""
    if text.startswith(SUBJECT_PREFIX):
        first, _, rest = text.partition("\n")
        return first[len(SUBJECT_PREFIX):].strip(), rest.lstrip("\n")
    return "", text


def render_text_html(text: str) -> str:
    """A body somebody wrote by hand, as HTML for the clipboard.

    A draft a person has edited has no :class:`Letter` behind it any more -
    the words are theirs - so there is nothing to put a stage's emphasis
    on and none is put: their paragraphs, in the letter's own type, with
    the same words the plain text carries. Inline styles only, as the
    generated body's are, and nothing fetched.
    """
    ink = page.PALETTE[LETTER_INK["body"]]
    paper = page.PALETTE[LETTER_INK["paper"]]
    out = [f'<div style="font-family: {page.FONT_SANS}; font-size: 15px; line-height: 1.6; '
           f'color: {ink}; background-color: {paper};">']
    for block in text.strip("\n").split("\n\n"):
        if block.strip():
            out.append(_paragraph(block.strip("\n"), "margin: 0 0 14px;"))
    out.append("</div>")
    return "".join(out)


def _with_last(values: Sequence):
    """Each value with whether it is the last one - the only thing the
    letter's spacing needs to know about where it is."""
    total = len(values)
    return [(i == total - 1, value) for i, value in enumerate(values)]


def draft_fingerprint(text: str) -> str:
    """Fingerprint of a draft's content, ignoring the header banner."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def recorded_fingerprint(path: Path | str) -> str:
    """The fingerprint in a draft file's header, or "" when it has none or
    cannot be read. The one reading of that line: ``is_unedited()``
    compares it with the body, and the ``DRAFTED`` event carries it."""
    try:
        text = Path(path).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""
    for line in text.splitlines():
        if line.startswith(_FINGERPRINT_PREFIX):
            return line[len(_FINGERPRINT_PREFIX):].strip()
    return ""


def is_unedited(path: Path | str) -> bool:
    """True when the file on disk is exactly as this module last wrote it.

    A draft with no fingerprint, an unreadable one, or one whose content no
    longer matches its fingerprint all answer False. The weekly job leans on
    this, so the conservative answer is the right one: anything we are not
    certain we wrote ourselves is treated as somebody's edit and left alone.
    """
    path = Path(path)
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return False

    recorded = recorded_fingerprint(path)
    if not recorded:
        return False

    _, separator, body = text.partition(_SEPARATOR + "\n")
    if not separator:
        return False
    return draft_fingerprint(body) == recorded


# ------------------------------------------------------------- approval ----
# Decision 118. A person reads the week's draft in the app and approves the
# text they are looking at. From then until the next draft day the pass
# treats that file exactly as it treats one somebody edited: never
# overwritten, a regenerated draft beside it. Nothing is sent, and nothing
# under the engagement is deleted.


def last_approved_event(engagement_dir: Path | str) -> dict | None:
    """The newest ``DRAFT_APPROVED`` on this engagement's record, or None."""
    return store.last_event(store.connect(), engagement_dir, ledger.DRAFT_APPROVED)


def approved_event(draft: ReminderDraft, written: Path) -> dict:
    """The ``DRAFT_APPROVED`` event for what a person approved: the stage,
    the file, the fingerprint in its header and the identifiers it asks
    for. A number, a name and identifiers - no word of the letter, as the
    draft's own event carries none."""
    return ledger.new(ledger.DRAFT_APPROVED, **{
        STAGE_KEY: draft.stage,
        ledger.FILE_KEY: Path(written).name,
        ledger.FINGERPRINT_KEY: recorded_fingerprint(written),
        ledger.ASKED_KEY: draft.asked,
    })


def is_approved_this_week(engagement_dir: Path | str, path: Path | str, *,
                          since: dt.date | None) -> bool:
    """Whether the file at ``path`` is the draft a person approved.

    ``since`` is the draft day that went by (``tracker.runner.last_draft_day``),
    handed in rather than worked out here: the runner decides the draft day
    (decision 12) and this module is below it. With one, the approval is
    spent when that day moves - next week's pass writes the week's draft as
    before, which is the bound the pass needs and the only caller that ever
    needed it.

    **``None`` asks only whether this is the approved file**, whenever it
    was approved. A caller that cannot measure the week - the command line,
    which is a layer below the runner - would otherwise write over a draft
    a person approved in the app an hour earlier, and approving is the same
    act as editing (decision 118). So the conservative answer is the right
    one, exactly as it is for :func:`is_unedited`: a file we are not certain
    is ours to replace is left where it is.

    Matched on the fingerprint in the file's own header, not on its name: a
    different draft written to the same name is not the one that was
    approved, and a file a person edited after approving it is protected
    because they edited it.
    """
    event = last_approved_event(engagement_dir)
    if event is None or event.get(ledger.FILE_KEY) != Path(path).name:
        return False
    if since is not None and ledger.day_of(str(event.get(ledger.AT_KEY, ""))) < since:
        return False
    fingerprint = recorded_fingerprint(path)
    return bool(fingerprint) and event.get(ledger.FINGERPRINT_KEY) == fingerprint


def is_protected(engagement_dir: Path | str, path: Path | str, *,
                 approved_since: dt.date | None = None) -> bool:
    """Whether a writer that preserves a person's work must leave this
    draft file alone.

    One predicate for the two reasons there are, and they are the same
    reason: somebody edited this draft, or somebody approved it.
    ``approved_since`` is the draft day that went by, when the caller knows
    it - the pass does, and it is what spends the approval next week.
    Without one the approval still protects the file: an approval is not
    the pass's to overrule, whichever writer is asking.
    """
    if not is_unedited(path):
        return True
    return is_approved_this_week(engagement_dir, path, since=approved_since)


def set_aside_other_draft(engagement_dir: Path | str, today: dt.date) -> Path | None:
    """Move any standing ``NEW_DRAFT_FILENAME`` out of the way of an approval.

    Renamed, never deleted: a person approving this week's text has said
    nothing about the other draft, and a file the client's own reminder was
    written into is not the machine's to throw away. Two on one day get the
    filer's own ``(2)`` name, so nothing is ever overwritten either.
    Returns where it went, or None when there was nothing beside it.
    """
    from tracker.filer import numbered

    engagement_dir = Path(engagement_dir)
    standing = engagement_dir / NEW_DRAFT_FILENAME
    if not standing.is_file():
        return None
    name = SET_ASIDE_DRAFT_PATTERN.format(date=today.isoformat())
    target = engagement_dir / name
    counter = 2
    while target.exists():
        target = engagement_dir / numbered(Path(name).stem, counter, Path(name).suffix)
        counter += 1
    standing.rename(target)
    return target


def stage_line(draft: ReminderDraft) -> str:
    """The header's stage line: which rung this draft is on, or none at all.

    In the header and never in the body, above the fingerprint line: the
    stage is a fact about the draft for the person sending it, not a
    sentence in the email, and a line inside the fingerprinted text would
    make every crossed threshold look like somebody's edit.
    """
    if not draft.stage:
        return STAGE_NONE
    return STAGE_LINE.format(number=draft.stage, name=stage_named(draft.stage).name)


def held_refusal(draft: ReminderDraft) -> str:
    """The one sentence a held draft is refused with: the inbox's (decision
    133) when files wait to be sorted, the held rows' (decision 115) when a
    row holds it, the confirm-held rows' (decision 140) when a parked file
    waits for a person here to confirm it, and each of them, joined, when
    more than one does."""
    said = []
    if draft.unsorted:
        said.append(INBOX_HOLD.format(n=draft.unsorted))
    decide = [flag for flag in draft.held if not flag.confirm]
    confirm = [flag for flag in draft.held if flag.confirm]
    if decide:
        said.append(HELD_REFUSAL.format(
            n=len(decide), listed=", ".join(flag.item.label for flag in decide),
        ))
    if confirm:
        said.append(CONFIRM_REFUSAL.format(listed=", ".join(flag.item.label for flag in confirm)))
    return "; ".join(said)


def _changed_block(draft: ReminderDraft, changed_from: dict | None) -> list[str]:
    """The what-changed lines for the header, or nothing.

    Only against an earlier *draft*: a ``DRAFTED`` event that carries the
    asked identifiers. A hold carries none, so a caller hands in the last
    event that does (``last_draft_event(..., carrying=ledger.ASKED_KEY)``)
    and the first draft after a hold says what the resolution changed
    against the last draft a person could have sent. A request no longer
    on the list is named by its bare identifier.
    """
    if not changed_from or ledger.ASKED_KEY not in changed_from:
        return []
    before = [str(identifier) for identifier in changed_from.get(ledger.ASKED_KEY) or []]
    now = draft.asked
    added = [identifier for identifier in now if identifier not in before]
    removed = [identifier for identifier in before if identifier not in now]
    if not added and not removed:
        return []
    day = ledger.day_of(str(changed_from.get(ledger.AT_KEY, ""))).isoformat()
    block = [CHANGED_HEADING.format(date=day)]
    block += [CHANGED_ADDED.format(label=draft.labels.get(i, i)) for i in added]
    block += [CHANGED_REMOVED.format(label=draft.labels.get(i, i)) for i in removed]
    return block


def write_draft(draft: ReminderDraft, path: Path | str | None = None,
                engagement_dir: Path | str | None = None,
                preserve_edits: bool = False, *,
                changed_from: dict | None = None,
                approved_since: dt.date | None = None) -> Path:
    """Write the draft to a text file. Give it ``path`` or ``engagement_dir``.

    The file opens with a banner saying it is a draft, because a file that
    reads like a sent email is a file someone will believe was sent.

    A held draft is refused before any file is touched
    (:class:`ReminderHeldError`, decision 115): a file that reads like a
    sendable email must not exist for a client whose reminder a person has
    yet to decide.

    With ``preserve_edits`` (what the weekly job uses), a draft somebody has
    already edited is never overwritten — the new one is written alongside it
    as ``NEW_DRAFT_FILENAME`` and that path is returned instead. An hour
    of someone's editing is worth more than this week's regenerated text.

    ``approved_since`` is the draft day that went by, when the caller knows
    it: a draft a person approved in the app since then is protected the
    same way an edited one is (decision 118), because approving it is the
    same act — a person has read this week's text and said it is the one.

    ``changed_from`` is the last ``DRAFTED`` event that carried what was
    asked, when the caller has one: the header then says what this draft
    asks for that the last one did not, and the other way round - above
    the separator, so it is never pasted into the email and never part of
    the fingerprinted body.

    **Whole or not written** (decision 155): through
    :func:`tracker.fsio.write_text_atomically`, flushed before it takes the
    name. A draft written straight onto its name and torn by a power cut
    failed its own fingerprint, so it read as a person's edit for good -
    every week's draft went to ``NEW_DRAFT_FILENAME`` beside a half letter
    nobody would regenerate.
    """
    if draft.is_held:
        raise ReminderHeldError(held_refusal(draft))
    if path is None:
        if engagement_dir is None:
            raise ReminderError("write_draft needs either path or engagement_dir")
        path = Path(engagement_dir) / DRAFT_FILENAME
    path = Path(path)

    folder = path.parent
    if preserve_edits and path.exists() and is_protected(folder, path, approved_since=approved_since):
        path = path.with_name(NEW_DRAFT_FILENAME)
        if path.exists() and is_protected(folder, path, approved_since=approved_since):
            # Both drafts carry somebody's work. The scheduled repeat runs
            # several times on the draft day; the second one must not
            # take the edits the first one made room for.
            raise DraftsEditedError(BOTH_DRAFTS_EDITED)

    footer: list[str] = []
    if draft.link_dropped:
        footer += ["", FOOTER_RULE, draft.link_dropped]
    if draft.needs_attention:
        footer += ["", FOOTER_RULE,
                   f"{HELD_BACK_HEADING} - waiting on us, not the client:"]
        footer += [f"  {flag.item.label}: {flag.reason}"
                   for flag in draft.needs_attention]
    if draft.needs_review_files:
        footer += ["", FOOTER_RULE,
                   REVIEW_WARNING.format(n=draft.needs_review_files),
                   REVIEW_ADVICE]

    body = draft.text
    if footer:
        body += "\n" + "\n".join(footer) + "\n"

    header = [
        DRAFT_BANNER,
        "Read it, edit it, then send it yourself.",
        stage_line(draft),
        f"{_FINGERPRINT_PREFIX}{draft_fingerprint(body)}",
        "(That line is how the weekly job tells whether you have edited this",
        " draft. Edit it freely - an edited draft is never overwritten.)",
        *_changed_block(draft, changed_from),
        _SEPARATOR,
        "",
    ]
    write_text_atomically(path, "\n".join(header) + body, encoding="utf-8", newline="\r\n")
    return path


# ------------------------------------------------------------- the record ----


def last_draft_event(engagement_dir: Path | str, *, carrying: str | None = None) -> dict | None:
    """The newest ``DRAFTED`` event on this engagement's record - the one
    carrying ``carrying`` when a key is named - or None. What a draft is
    compared with, and what the runner reads the last draft day from."""
    return store.last_event(store.connect(), engagement_dir, ledger.DRAFTED, carrying=carrying)


def drafted_event(draft: ReminderDraft, written: Path | None) -> dict:
    """The ``DRAFTED`` event for what this draft decided: the identifiers
    held when it is held, otherwise the identifiers asked (``[]`` on a
    quiet week) with the stage it was written at, the file written and the
    fingerprint in its header. Identifiers and a number - no word of the
    email is ever in the record.

    A hold carries no stage: nothing was written, so there is no letter to
    have been at a stage.
    """
    if draft.is_held:
        return ledger.new(ledger.DRAFTED, **{
            ledger.HELD_KEY: [flag.item.identifier for flag in draft.held],
        })
    payload: dict[str, object] = {ledger.ASKED_KEY: draft.asked, STAGE_KEY: draft.stage}
    if written is not None:
        payload[ledger.FILE_KEY] = Path(written).name
        payload[ledger.FINGERPRINT_KEY] = recorded_fingerprint(written)
    return ledger.new(ledger.DRAFTED, **payload)


def draft_changed(previous: dict | None, event: dict, *, since: dt.date | None = None) -> bool:
    """Whether ``event`` says anything the previous ``DRAFTED`` did not.

    Only what changed goes on the record (the ``scanned`` rule): a repeat
    on the draft day that finds the engagement as the last draft left it
    appends nothing. What counts as changed is the asked set, the held set,
    the stage, the file written and its fingerprint. The stage is one of
    them because a client who crossed a threshold gets a different letter
    this week even when the list of documents did not move, and a record
    that said nothing happened would be wrong about the one thing that
    did. A draft file written in a new
    draft week counts too, when the caller says which week (``since`` -
    the draft day that went by): the week's draft is a fact of that week,
    and it is what the runner reads the last draft day from, so a reminder
    identical to last week's is still this week's reminder.
    """
    if previous is None:
        return True
    for key in (ledger.ASKED_KEY, ledger.HELD_KEY, STAGE_KEY,
                ledger.FILE_KEY, ledger.FINGERPRINT_KEY):
        if previous.get(key) != event.get(key):
            return True
    if since is not None and ledger.FILE_KEY in event:
        return ledger.day_of(str(previous.get(ledger.AT_KEY, ""))) < since
    return False


def record_draft(engagement_dir: Path | str, event: dict) -> None:
    """Put one ``DRAFTED`` event on the record: the journal, then the store,
    in one call. The caller holds the engagement lock - the pass does across
    the whole pass, the CLI takes one - or the store refuses by name."""
    store.record(store.connect(), engagement_dir, event)


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="Draft (never send) a client reminder from a scanned engagement"
    )
    parser.add_argument("engagement_dir", help="the engagement folder")
    parser.add_argument("--client", default="", help="client's name for the greeting")
    parser.add_argument("--engagement-name", default="", help="override the folder name")
    parser.add_argument("--link", default="", help="share link to the client drop folder")
    parser.add_argument(DUE_FLAG, default="", help=f"due date, {ISO_DATE_HINT}")
    parser.add_argument(DEADLINE_FLAG, default="", help=f"filing deadline, {ISO_DATE_HINT}")
    parser.add_argument("--from-name", default="", help="who the email is from")
    parser.add_argument("--firm", default="", help="firm name for the sign-off")
    parser.add_argument("--phone", default="", help="firm phone for the final notice")
    parser.add_argument(TODAY_FLAG, default="",
                        help=f"the day the letter is written on, {ISO_DATE_HINT} "
                             "(the stage is measured from it)")
    parser.add_argument(STAGE_FLAG, type=int, default=None,
                        choices=[stage.number for stage in STAGES],
                        help="write the same lines at this stage instead of the day's")
    parser.add_argument("--write", action="store_true",
                        help=f"also write {DRAFT_FILENAME} into the engagement folder")
    ns = parser.parse_args()

    def _day(flag: str, typed: str) -> dt.date | None:
        if not typed:
            return None
        try:
            return dt.date.fromisoformat(typed)
        except ValueError:
            parser.error(f"{flag} must be {ISO_DATE_HINT}, got {typed!r}")

    due = _day(DUE_FLAG, ns.due)
    deadline = _day(DEADLINE_FLAG, ns.deadline)
    today = _day(TODAY_FLAG, ns.today)

    try:
        result = draft_reminder(
            ns.engagement_dir,
            client_name=ns.client,
            engagement_name=ns.engagement_name,
            share_link=ns.link,
            due_date=due,
            filing_deadline=deadline,
            sender=ns.from_name,
            firm=ns.firm,
            phone=ns.phone,
            today=today,
            stage=ns.stage,
        )
    except ReminderError as exc:
        raise SystemExit(f"Cannot draft a reminder: {exc}") from None

    print(f"{DRAFT_BANNER}\n")
    if result.is_held:
        # Not the email. A held client's composed text would ask for the
        # clean rows alone - the partial reminder the hold exists to
        # prevent - on a console a person can paste from. The refusal and
        # the rows, and nothing that reads like something to send.
        print(held_refusal(result))
    else:
        print(result.text)

    for flag in result.needs_attention:
        print(f"{HELD_BACK_LINE}: {flag.item.label}: {flag.reason}")
    for flag in result.held:
        print(f"{HELD_LINE}: {flag.item.label}: {flag.reason}")
    if result.link_dropped:
        print(f"\n{result.link_dropped}")
    if result.needs_review_files:
        print(f"\nWARNING: {REVIEW_WARNING.format(n=result.needs_review_files)}")
        print(REVIEW_ADVICE)

    if ns.write:
        from tracker.locking import engagement_lock

        # The manual draft is always available, and never past the gate
        # (decision 13, amended by 115): what the pass would not put to
        # the client, a person's command line may not either. Exit 2 is
        # the scanner's own "not done, not an error".
        if result.is_held:
            print(f"\n{held_refusal(result)}")
            raise SystemExit(2)
        # The write and the record under the engagement lock, as a person's
        # filing is: the record refuses a writer that holds none.
        with engagement_lock(Path(ns.engagement_dir)):
            previous = last_draft_event(ns.engagement_dir)
            last_asked = last_draft_event(ns.engagement_dir, carrying=ledger.ASKED_KEY)
            try:
                written = write_draft(result, engagement_dir=ns.engagement_dir,
                                      preserve_edits=True, changed_from=last_asked)
            except DraftsEditedError as exc:
                print(f"\n{exc}")
                raise SystemExit(1) from None
            event = drafted_event(result, written)
            if draft_changed(previous, event):
                record_draft(ns.engagement_dir, event)
        print(f"\nDraft written to {written}")
