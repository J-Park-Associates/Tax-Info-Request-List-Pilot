"""Draft the "still waiting on these" email to a client (component 9).

Reads a scanned engagement's record and writes a plain-text draft the
accountant can read, edit and paste into Outlook. **It never sends anything**
— there is no SMTP, no mail client, no network call anywhere in this module.
A reminder goes out because a person decided to send it.

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
- Rows whose request folder does not exist. We cannot honestly tell a client
  we never received something we never made a place to put — that is a
  scaffold problem, and it is reported as one.

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

from tracker import ledger, reasons, store
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
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)
from tracker.validators import iter_candidate_files

log = logging.getLogger("tracker.reminder")

DRAFT_FILENAME = "reminder-draft.txt"
DUE_FLAG = "--due"

#: Where a fresh draft goes when the standing one has been edited by hand.
NEW_DRAFT_FILENAME = Path(DRAFT_FILENAME).stem + ".NEW" + Path(DRAFT_FILENAME).suffix

_FINGERPRINT_PREFIX = "Fingerprint: "
_RULE_WIDTH = 60
_SEPARATOR = "=" * _RULE_WIDTH

#: Statuses that mean the client still owes us something (re-exported).
OUTSTANDING = Status.OUTSTANDING

#: The subject lines and the banner every draft opens with.
SUBJECT_NEEDED = "{engagement}: {n} document(s) still needed"
SUBJECT_COMPLETE = "{engagement}: we have everything - thank you"
DRAFT_BANNER = "DRAFT - NOTHING HAS BEEN SENT."
#: The sentence every draft opens its instructions with.
DROP_ANYWHERE = "Everything goes in the same place - just drop it into the shared"
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
#: What write_draft() refuses a held draft with, and what the run log, the
#: practice page's note and the CLI say: the count, then every held row.
HELD_REFUSAL = (
    "the reminder is held: {n} request(s) need a person to decide whether the client "
    "resends or we fix it here - {listed}; nothing was written"
)
#: The one line the app shows for a held reminder (through the API's vocabulary).
HELD_SUMMARY = "Reminder held: {n} request(s) need a decision"
#: The what-changed block a regenerated draft opens with, above the line a
#: person pastes: the earlier draft's day, then each request now asked that
#: was not, and each no longer asked that was.
CHANGED_HEADING = "Changed since the draft of {date}:"
CHANGED_ADDED = "  + {label}   (now asked)"
CHANGED_REMOVED = "  - {label}   (no longer asked)"
#: The footer's warning about parked files, and what to do about it.
REVIEW_WARNING = "{n} file(s) the client already sent are still in " + REVIEW_DIR_NAME + "."
REVIEW_ADVICE = "Identify them before sending, or you may ask for something you have."
#: What a Partial row is asked with.
PARTIAL_ASK = "{have} of {expected} received, {missing} still to come"
#: The file-type ask, in the row's own terms (the reason's generic ask is for rows that take anything).
EXTENSION_ASK = "we cannot open that file type; please send it as {accepted}"
PARTIAL_ASK_COMPLETE = "{have} of {expected} received"

SECTION_MISSING = "NOT YET RECEIVED"
SECTION_PARTIAL = "STARTED, BUT NOT COMPLETE"
#: The section a Failed row used to be asked under. Unreachable from a pass
#: since decision 115 - a Failed row with no firm-side marker holds the
#: draft instead - so it is not in ``SECTION_ORDER``; the name stays because
#: an "ask the client again" action a person records would put a row here.
SECTION_FAILED = "RECEIVED, BUT WE COULD NOT USE IT"

SECTION_ORDER = (SECTION_MISSING, SECTION_PARTIAL)


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
    """An ambiguous row holds the draft; nothing was written (decision 115)."""


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


@dataclass(slots=True)
class ReminderDraft:
    """A drafted reminder. Nothing here has been, or will be, sent."""

    engagement: str
    subject: str
    body: str
    lines: list[ReminderLine] = field(default_factory=list)
    needs_attention: list[FirmSideFlag] = field(default_factory=list)
    scaffold_gaps: list[FirmSideFlag] = field(default_factory=list)
    #: The ambiguous rows (decision 115). One of these holds the whole draft.
    held: list[FirmSideFlag] = field(default_factory=list)
    needs_review_files: int = 0
    total_requests: int = 0
    received_requests: int = 0
    #: Every request on the list, identifier -> label, so a what-changed
    #: line can name a request the draft no longer asks for.
    labels: dict[str, str] = field(default_factory=dict)

    @property
    def has_outstanding(self) -> bool:
        return bool(self.lines)

    @property
    def is_held(self) -> bool:
        """An ambiguous row holds this draft: nothing may be written from it."""
        return bool(self.held)

    @property
    def asked(self) -> list[str]:
        """The identifiers the draft asks for, in the draft's order."""
        return [line.item.identifier for line in self.lines]

    @property
    def text(self) -> str:
        """Subject and body as one block, ready to paste into an email."""
        return f"Subject: {self.subject}\n\n{self.body}"

    def section(self, name: str) -> list[ReminderLine]:
        return [line for line in self.lines if line.section == name]


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
    spreadsheet round the loop again."""
    if reason is reasons.EXTENSION_NOT_ALLOWED and item.allowed_extensions:
        return EXTENSION_ASK.format(accepted=" or ".join(f".{ext}" for ext in item.allowed_extensions))
    return reason.client_ask


def _firm_side_reason(item: RequestItem) -> str:
    """Why this row is the firm's problem rather than the client's, or ""."""
    note = item.validation_notes or ""
    for reason in reasons.FIRM_SIDE:
        if reason is not reasons.NO_REQUEST_FOLDER and reason.matches(note):
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


def triage(items: Sequence[RequestItem]) -> tuple[
    list[ReminderLine], list[FirmSideFlag], list[FirmSideFlag], list[FirmSideFlag]
]:
    """Sort every outstanding row once, by one rule: client asks (``lines``),
    firm-side work (``attention``), scaffold gaps (``gaps``) and the
    ambiguous rows that hold the whole draft (``held``, decision 115).

    Overridden rows and anything already in are dropped here and never reach
    the draft. For the rest, in this order: a row with no request folder is
    a scaffold gap; a row carrying any firm-side marker, on any outstanding
    status, is the firm's (decisions 20, 21, 58, and 109's rule for a
    Missing row); a Failed row, or a Partial whose shortfall is a refused
    file, is ambiguous and held; a Missing row, and a Partial with no
    reason, is asked.
    """
    lines: list[ReminderLine] = []
    attention: list[FirmSideFlag] = []
    gaps: list[FirmSideFlag] = []
    held: list[FirmSideFlag] = []

    for item in items:
        if item.manual_override or item.status not in OUTSTANDING:
            continue

        if reasons.NO_REQUEST_FOLDER.matches(item.validation_notes or ""):
            gaps.append(FirmSideFlag(item=item, reason=reasons.NO_REQUEST_FOLDER.firm_side_note))
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

    order = {name: i for i, name in enumerate(SECTION_ORDER)}
    lines.sort(key=lambda line: (order[line.section], line.item.identifier))
    held.sort(key=lambda flag: flag.item.identifier)
    return lines, attention, gaps, held


def count_needs_review(engagement_dir: Path) -> int:
    """Files parked in ``REVIEW_DIR_NAME`` — already sent, not yet identified.

    Counted from the folder, not from the index, because a file somebody
    dragged in by hand is still a file nobody has identified. The index only
    takes files *out* of the count: a row a person marked ``NOT_REQUESTED``
    has been looked at, and the whole point of the warning is that a person
    may be about to ask for something already in hand. A row they have seen
    is not that.

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
        engagement_dir / location
        for location, row in newest.items() if row.decision == NOT_REQUESTED
    }
    return sum(1 for path in parked if path not in seen)


# ----------------------------------------------------------------- drafts ----


def _compose_body(
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
) -> str:
    out: list[str] = [f"Hi {client_name}," if client_name else "Hello,", ""]

    if not lines:
        out += [
            f"Good news - we have everything we asked for on {engagement}.",
            "Nothing further is needed from you right now, and we will be in",
            "touch if anything else comes up.",
            "",
        ]
    else:
        if received:
            out.append(
                f"Thank you for what you have sent so far - {received} of {total} "
                f"items are in. Here is what we are still waiting on for {engagement}:"
            )
        else:
            out.append(f"Here is what we still need for {engagement}:")
        out.append("")

        for name in SECTION_ORDER:
            section = [line for line in lines if line.section == name]
            if not section:
                continue
            out.append(name)
            out.extend(line.render() for line in section)
            out.append("")

        if share_link:
            out += [
                DROP_ANYWHERE,
                "folder. One folder, no sorting and no naming needed; we do that:",
                f"  {share_link}",
                "",
            ]
        else:
            out += [
                DROP_ANYWHERE,
                "folder we set up. One folder, no sorting and no naming needed.",
                "",
            ]

        if due_date:
            out += [f"If you can send these by {due_date.strftime('%B %d, %Y')}, "
                    "that keeps us on schedule.", ""]

    out.append("Thank you,")
    if sender:
        out.append(sender)
    if firm:
        out.append(firm)
    return "\n".join(out).rstrip() + "\n"


def draft_reminder(
    engagement_dir: Path | str,
    *,
    client_name: str = "",
    engagement_name: str = "",
    share_link: str = "",
    due_date: dt.date | None = None,
    sender: str = "",
    firm: str = "",
) -> ReminderDraft:
    """Draft the reminder for one engagement. Reads only; sends nothing.

    Who the client is, the share link, the due date and the sign-off come
    from the engagement's details in the record - the one place they are
    kept. The keyword arguments override it for a one-off (the CLI's
    flags); nothing else needs to pass them in.

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
    due_date = due_date or info.due
    sender = sender or info.sender
    firm = firm or info.firm

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

    lines, attention, gaps, held = triage(items)
    summary = summarize(items)
    received, total = summary.received, summary.total
    engagement = engagement_name or engagement_dir.name

    body = _compose_body(
        lines,
        client_name=client_name,
        engagement=engagement,
        share_link=share_link,
        due_date=due_date,
        sender=sender,
        firm=firm,
        received=received,
        total=total,
    )

    if lines:
        subject = SUBJECT_NEEDED.format(engagement=engagement, n=len(lines))
    else:
        subject = SUBJECT_COMPLETE.format(engagement=engagement)

    return ReminderDraft(
        engagement=engagement,
        subject=subject,
        body=body,
        lines=lines,
        needs_attention=attention,
        scaffold_gaps=gaps,
        held=held,
        needs_review_files=count_needs_review(engagement_dir),
        total_requests=total,
        received_requests=received,
        labels={item.identifier: item.label for item in items},
    )


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


def held_refusal(draft: ReminderDraft) -> str:
    """The one sentence a held draft is refused with, naming every held row."""
    return HELD_REFUSAL.format(
        n=len(draft.held), listed=", ".join(flag.item.label for flag in draft.held),
    )


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
                changed_from: dict | None = None) -> Path:
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

    ``changed_from`` is the last ``DRAFTED`` event that carried what was
    asked, when the caller has one: the header then says what this draft
    asks for that the last one did not, and the other way round - above
    the separator, so it is never pasted into the email and never part of
    the fingerprinted body.
    """
    if draft.is_held:
        raise ReminderHeldError(held_refusal(draft))
    if path is None:
        if engagement_dir is None:
            raise ReminderError("write_draft needs either path or engagement_dir")
        path = Path(engagement_dir) / DRAFT_FILENAME
    path = Path(path)

    if preserve_edits and path.exists() and not is_unedited(path):
        path = path.with_name(NEW_DRAFT_FILENAME)
        if path.exists() and not is_unedited(path):
            # Both drafts carry somebody's work. The scheduled repeat runs
            # several times on the draft day; the second one must not
            # take the edits the first one made room for.
            raise DraftsEditedError(BOTH_DRAFTS_EDITED)

    footer: list[str] = []
    if draft.scaffold_gaps:
        footer += ["", "-" * _RULE_WIDTH,
                   f"{HELD_BACK_HEADING} - fix these here first:"]
        footer += [f"  {flag.item.label}: {flag.reason}"
                   for flag in draft.scaffold_gaps]
    if draft.needs_attention:
        footer += ["", "-" * _RULE_WIDTH,
                   f"{HELD_BACK_HEADING} - waiting on us, not the client:"]
        footer += [f"  {flag.item.label}: {flag.reason}"
                   for flag in draft.needs_attention]
    if draft.needs_review_files:
        footer += ["", "-" * _RULE_WIDTH,
                   REVIEW_WARNING.format(n=draft.needs_review_files),
                   REVIEW_ADVICE]

    body = draft.text
    if footer:
        body += "\n" + "\n".join(footer) + "\n"

    header = [
        DRAFT_BANNER,
        "Read it, edit it, then send it yourself.",
        f"{_FINGERPRINT_PREFIX}{draft_fingerprint(body)}",
        "(That line is how the weekly job tells whether you have edited this",
        " draft. Edit it freely - an edited draft is never overwritten.)",
        *_changed_block(draft, changed_from),
        _SEPARATOR,
        "",
    ]
    path.write_text("\n".join(header) + body, encoding="utf-8", newline="\r\n")
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
    quiet week) with the file written and the fingerprint in its header.
    Identifiers only - no word of the email is ever in the record."""
    if draft.is_held:
        return ledger.new(ledger.DRAFTED, **{
            ledger.HELD_KEY: [flag.item.identifier for flag in draft.held],
        })
    payload: dict[str, object] = {ledger.ASKED_KEY: draft.asked}
    if written is not None:
        payload[ledger.FILE_KEY] = Path(written).name
        payload[ledger.FINGERPRINT_KEY] = recorded_fingerprint(written)
    return ledger.new(ledger.DRAFTED, **payload)


def draft_changed(previous: dict | None, event: dict, *, since: dt.date | None = None) -> bool:
    """Whether ``event`` says anything the previous ``DRAFTED`` did not.

    Only what changed goes on the record (the ``scanned`` rule): a repeat
    on the draft day that finds the engagement as the last draft left it
    appends nothing. What counts as changed is the asked set, the held set,
    the file written and its fingerprint. A draft file written in a new
    draft week counts too, when the caller says which week (``since`` -
    the draft day that went by): the week's draft is a fact of that week,
    and it is what the runner reads the last draft day from, so a reminder
    identical to last week's is still this week's reminder.
    """
    if previous is None:
        return True
    for key in (ledger.ASKED_KEY, ledger.HELD_KEY, ledger.FILE_KEY, ledger.FINGERPRINT_KEY):
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
    parser.add_argument("--from-name", default="", help="who the email is from")
    parser.add_argument("--firm", default="", help="firm name for the sign-off")
    parser.add_argument("--write", action="store_true",
                        help=f"also write {DRAFT_FILENAME} into the engagement folder")
    ns = parser.parse_args()

    due = None
    if ns.due:
        try:
            due = dt.date.fromisoformat(ns.due)
        except ValueError:
            parser.error(f"{DUE_FLAG} must be {ISO_DATE_HINT}, got {ns.due!r}")

    try:
        result = draft_reminder(
            ns.engagement_dir,
            client_name=ns.client,
            engagement_name=ns.engagement_name,
            share_link=ns.link,
            due_date=due,
            sender=ns.from_name,
            firm=ns.firm,
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

    for flag in result.scaffold_gaps:
        print(f"{HELD_BACK_LINE}: {flag.item.label}: {flag.reason}")
    for flag in result.needs_attention:
        print(f"{HELD_BACK_LINE}: {flag.item.label}: {flag.reason}")
    for flag in result.held:
        print(f"{HELD_LINE}: {flag.item.label}: {flag.reason}")
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
