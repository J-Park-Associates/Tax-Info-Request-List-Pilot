"""Draft the "still waiting on these" email to a client (component 9).

Reads a scanned ``MANIFEST_FILENAME`` and writes a plain-text draft the
accountant can read, edit and paste into Outlook. **It never sends anything**
— there is no SMTP, no mail client, no network call anywhere in this module.
A reminder goes out because a person decided to send it.

What the client is asked for:

- ``Status.MISSING`` — never arrived.
- ``Status.PARTIAL`` — some of the expected files arrived, not all.
- ``Status.FAILED`` — something arrived that we could not use.

What the client is deliberately *not* asked for:

- ``Status.RECEIVED`` — it is in.
- ``Status.PENDING_SYNC`` — it is in; the cloud is still copying it down. Nothing for
  the client to do, so nothing to say.
- Any row with a Manual Override. ``Override.WAIVED`` is no longer needed and
  ``Override.ACCEPTED`` has already been judged good enough by a person; re-asking
  would contradict that person.
- Rows whose only problem is that *we* have not looked yet ("review
  manually", an un-OCR'd scan). The document may be perfect. Asking a client
  to resend something we simply have not read is how a firm looks careless,
  so those rows go to the accountant instead, under *needs a person*. That
  holds for a ``Status.PARTIAL`` row too: if the file that would complete it is one
  we have not read, "1 of 2 received" is not something we know yet.
- Rows whose request folder does not exist. We cannot honestly tell a client
  we never received something we never made a place to put — that is a
  scaffold problem, and it is reported as one.

Validation notes are **never pasted into the email.** They name keywords,
size floors and internal folders: firm-side vocabulary that would confuse a
client and expose the matching rules. Every note is translated into one plain
sentence saying what to do about it, by deterministic substring rules, and
anything unrecognized falls back to the safe generic ask. No generative AI
touches any of this, and no client document is read here at all — only the
manifest the scanner already wrote.

One more guard: files sitting in ``REVIEW_DIR_NAME`` are things the client
*has* already sent that nobody has identified yet. Sending a reminder over
the top of those risks asking for a document already in hand, so their count
is reported and the CLI says so plainly before you send.
"""

from __future__ import annotations

import datetime as dt
import hashlib
from dataclasses import dataclass, field
from pathlib import Path
from typing import Iterable, Sequence

from tracker.manifest import (
    ISO_DATE_HINT,
    RequestItem,
    Status,
    load_engagement_info,
    load_manifest,
    pending_updates,
    summarize,
    with_pending,
)
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)
from tracker.validators import iter_candidate_files

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
#: The footer's warning about parked files, and what to do about it.
REVIEW_WARNING = "{n} file(s) the client already sent are still in " + REVIEW_DIR_NAME + "."
REVIEW_ADVICE = "Identify them before sending, or you may ask for something you have."
#: What a Partial row is asked with.
PARTIAL_ASK = "{have} of {expected} received, {missing} still to come"
PARTIAL_ASK_COMPLETE = "{have} of {expected} received"

SECTION_MISSING = "NOT YET RECEIVED"
SECTION_PARTIAL = "STARTED, BUT NOT COMPLETE"
SECTION_FAILED = "RECEIVED, BUT WE COULD NOT USE IT"

SECTION_ORDER = (SECTION_MISSING, SECTION_PARTIAL, SECTION_FAILED)

from tracker import reasons
from tracker.reasons import GENERIC_ASK  # re-exported; the one generic sentence


class ReminderError(Exception):
    """A reminder could not be drafted from this engagement."""


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
    needs_review_files: int = 0
    total_requests: int = 0
    received_requests: int = 0
    pending_statuses: int = 0   # deferred by a locked Excel; already reflected here

    @property
    def has_outstanding(self) -> bool:
        return bool(self.lines)

    @property
    def text(self) -> str:
        """Subject and body as one block, ready to paste into an email."""
        return f"Subject: {self.subject}\n\n{self.body}"

    def section(self, name: str) -> list[ReminderLine]:
        return [line for line in self.lines if line.section == name]


# ------------------------------------------------------------ translation ----


def client_ask(item: RequestItem) -> str:
    """One plain sentence telling the client what to do about ``item``.

    Driven by the scanner's validation note, never quoting it. Returns the
    generic ask when nothing in the note is recognized — being vague is the
    safe failure here; guessing at a cause is not.
    """
    if item.status == Status.PARTIAL:
        expected = item.expected_count
        have = item.file_count or 0
        missing = max(expected - have, 0)
        return (PARTIAL_ASK.format(have=have, expected=expected, missing=missing)
                if missing else PARTIAL_ASK_COMPLETE.format(have=have, expected=expected))

    if item.status != Status.FAILED:
        return ""

    reason = reasons.find(item.validation_notes or "")
    return reason.client_ask if reason else GENERIC_ASK


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
        Status.FAILED: SECTION_FAILED,
    }[item.status]


def triage(items: Sequence[RequestItem]) -> tuple[
    list[ReminderLine], list[FirmSideFlag], list[FirmSideFlag]
]:
    """Split scanned rows into client asks, firm-side work and scaffold gaps.

    Overridden rows and anything already in are dropped here and never reach
    the draft.
    """
    lines: list[ReminderLine] = []
    attention: list[FirmSideFlag] = []
    gaps: list[FirmSideFlag] = []

    for item in items:
        if item.manual_override or item.status not in OUTSTANDING:
            continue

        if reasons.NO_REQUEST_FOLDER.matches(item.validation_notes or ""):
            gaps.append(FirmSideFlag(item=item, reason=reasons.NO_REQUEST_FOLDER.firm_side_note))
            continue

        # A Failed row we have not read is ours, not the client's. So is a
        # Partial row whose shortfall is a file we have not read: the client
        # may well have sent everything, and "1 of 2 received" would tell
        # them otherwise.
        reason = _firm_side_reason(item)
        if reason and item.status in (Status.FAILED, Status.PARTIAL):
            if item.status == Status.PARTIAL:
                reason = reasons.FIRM_WAITING_PARTIAL
            attention.append(FirmSideFlag(item=item, reason=reason))
            continue

        section = _section_for(item)
        ask = client_ask(item) if section != SECTION_MISSING else _missing_detail(item)
        lines.append(ReminderLine(item=item, section=section, ask=ask))

    order = {name: i for i, name in enumerate(SECTION_ORDER)}
    lines.sort(key=lambda line: (order[line.section], line.item.identifier))
    return lines, attention, gaps


def count_needs_review(engagement_dir: Path) -> int:
    """Files parked in ``REVIEW_DIR_NAME`` — already sent, not yet identified."""
    review = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    return len(iter_candidate_files(review))


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
    from the manifest's Engagement sheet - the one place they are kept. The
    keyword arguments override it for a one-off (the CLI's flags); nothing
    else needs to pass them in.

    Raises :class:`ReminderError` when the manifest is missing or has never
    been scanned — a reminder built from unscanned rows would ask for
    documents the client may well have sent already.
    """
    engagement_dir = Path(engagement_dir)
    manifest = engagement_dir / MANIFEST_FILENAME
    if not manifest.is_file():
        raise ReminderError(f"no {MANIFEST_FILENAME} in {engagement_dir}")
    info = load_engagement_info(manifest)
    client_name = client_name or info.client
    engagement_name = engagement_name or info.name
    share_link = share_link or info.link
    due_date = due_date or info.due
    sender = sender or info.sender
    firm = firm or info.firm

    # Statuses the last scan could not write because Excel had the manifest
    # open are still the truth about what arrived; a draft that ignored
    # them would ask for documents already in hand.
    deferred = pending_updates(manifest)
    items = with_pending(load_manifest(manifest), deferred)
    if not items:
        raise ReminderError(f"{manifest} has no request rows")
    if not any(item.status for item in items):
        raise ReminderError(
            f"{manifest} has no scan results yet; run "
            f"`python -m tracker.scanner {engagement_dir}` first"
        )

    lines, attention, gaps = triage(items)
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
        needs_review_files=count_needs_review(engagement_dir),
        total_requests=total,
        received_requests=received,
        pending_statuses=len(deferred),
    )


def draft_fingerprint(text: str) -> str:
    """Fingerprint of a draft's content, ignoring the header banner."""
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


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

    recorded = ""
    for line in text.splitlines():
        if line.startswith(_FINGERPRINT_PREFIX):
            recorded = line[len(_FINGERPRINT_PREFIX):].strip()
            break
    if not recorded:
        return False

    _, separator, body = text.partition(_SEPARATOR + "\n")
    if not separator:
        return False
    return draft_fingerprint(body) == recorded


def write_draft(draft: ReminderDraft, path: Path | str | None = None,
                engagement_dir: Path | str | None = None,
                preserve_edits: bool = False) -> Path:
    """Write the draft to a text file. Give it ``path`` or ``engagement_dir``.

    The file opens with a banner saying it is a draft, because a file that
    reads like a sent email is a file someone will believe was sent.

    With ``preserve_edits`` (what the weekly job uses), a draft somebody has
    already edited is never overwritten — the new one is written alongside it
    as ``NEW_DRAFT_FILENAME`` and that path is returned instead. An hour
    of someone's editing is worth more than this week's regenerated text.
    """
    if path is None:
        if engagement_dir is None:
            raise ReminderError("write_draft needs either path or engagement_dir")
        path = Path(engagement_dir) / DRAFT_FILENAME
    path = Path(path)

    if preserve_edits and path.exists() and not is_unedited(path):
        path = path.with_name(NEW_DRAFT_FILENAME)

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
    if draft.pending_statuses:
        footer += ["", "-" * _RULE_WIDTH,
                   f"{draft.pending_statuses} status update(s) are still waiting to be "
                   "written into the manifest (it was open in Excel during the last",
                   "scan). This draft already reflects them; close Excel and re-scan",
                   "to see them in the sheet."]
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
        _SEPARATOR,
        "",
    ]
    path.write_text("\n".join(header) + body, encoding="utf-8", newline="\r\n")
    return path


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

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
        raise SystemExit(f"Cannot draft a reminder: {exc}")

    print(f"{DRAFT_BANNER}\n")
    print(result.text)

    for flag in result.scaffold_gaps:
        print(f"{HELD_BACK_LINE}: {flag.item.label}: {flag.reason}")
    for flag in result.needs_attention:
        print(f"{HELD_BACK_LINE}: {flag.item.label}: {flag.reason}")
    if result.needs_review_files:
        print(f"\nWARNING: {REVIEW_WARNING.format(n=result.needs_review_files)}")
        print(REVIEW_ADVICE)

    if ns.write:
        written = write_draft(result, engagement_dir=ns.engagement_dir)
        print(f"\nDraft written to {written}")
