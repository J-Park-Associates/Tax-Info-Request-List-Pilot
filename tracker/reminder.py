"""Draft the "still waiting on these" email to a client (component 9).

Reads a scanned ``_manifest.xlsx`` and writes a plain-text draft the
accountant can read, edit and paste into Outlook. **It never sends anything**
— there is no SMTP, no mail client, no network call anywhere in this module.
A reminder goes out because a person decided to send it.

What the client is asked for:

- ``Missing`` — never arrived.
- ``Partial`` — some of the expected files arrived, not all.
- ``Failed Validation`` — something arrived that we could not use.

What the client is deliberately *not* asked for:

- ``Received`` — it is in.
- ``Pending Sync`` — it is in; the cloud is still copying it down. Nothing for
  the client to do, so nothing to say.
- Any row with a Manual Override. ``Waived`` is no longer needed and
  ``Accepted`` has already been judged good enough by a person; re-asking
  would contradict that person.
- Rows whose only problem is that *we* have not looked yet ("review
  manually", an un-OCR'd scan). The document may be perfect. Asking a client
  to resend something we simply have not read is how a firm looks careless,
  so those rows go to the accountant instead, under *needs a person*. That
  holds for a ``Partial`` row too: if the file that would complete it is one
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

One more guard: files sitting in ``00 - Needs Review`` are things the client
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

from tracker.manifest import RequestItem, Status, load_manifest
from tracker.scaffold import (
    MANIFEST_FILENAME,
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)

DRAFT_FILENAME = "reminder-draft.txt"

#: Where a fresh draft goes when the standing one has been edited by hand.
NEW_DRAFT_FILENAME = "reminder-draft.NEW.txt"

_FINGERPRINT_PREFIX = "Fingerprint: "
_SEPARATOR = "=" * 60

#: Statuses that mean the client still owes us something.
OUTSTANDING = (Status.MISSING, Status.PARTIAL, Status.FAILED)

SECTION_MISSING = "NOT YET RECEIVED"
SECTION_PARTIAL = "STARTED, BUT NOT COMPLETE"
SECTION_FAILED = "RECEIVED, BUT WE COULD NOT USE IT"

SECTION_ORDER = (SECTION_MISSING, SECTION_PARTIAL, SECTION_FAILED)

#: Shown when a failure has no recognized cause. Deliberately vague about our
#: rules and specific about what the client should do.
GENERIC_ASK = "we could not read the file that arrived; please send it again"

#: Notes that mean "a person here has not looked yet", not "the client did
#: something wrong". These never become a client ask.
_FIRM_SIDE_MARKERS = (
    "review manually",
    "no text layer",
    "no readable text",
)

_SCAFFOLD_MARKER = "request folder not found"

#: (substring found in a validation note, sentence written to the client).
#: First match wins, so the specific causes are listed before the vague ones.
_ASK_RULES: tuple[tuple[str, str], ...] = (
    ("password-protected",
     "the file is password-protected; please send an unlocked copy"),
    ("google docs shortcut",
     "that was a Google Docs/Sheets shortcut rather than the document itself; "
     "please download it (File > Download > PDF or Excel) and send that copy"),
    ("possible placeholder or failed upload",
     "the file arrived almost empty, so the upload may not have finished; "
     "please send it again"),
    ("not allowed",
     "we cannot open that file type; please send it as a PDF or an Excel file"),
    ("possible wrong document",
     "the document that arrived does not look like this item; "
     "please check that the right file was sent"),
    ("none of the expected keywords found",
     "the document that arrived does not look like this item; "
     "please check that the right file was sent"),
    ("possible wrong period",
     "the document that arrived appears to cover a different period; "
     "please check the year"),
    ("contains no pages", GENERIC_ASK),
    ("not a readable pdf", GENERIC_ASK),
    ("text extraction failed", GENERIC_ASK),
)


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
        entry = f"{self.item.identifier} - {self.item.document}"
        if self.item.period:
            entry += f" ({self.item.period})"
        return entry

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
        return (f"{have} of {expected} received, {missing} still to come"
                if missing else f"{have} of {expected} received")

    if item.status != Status.FAILED:
        return ""

    note = (item.validation_notes or "").lower()
    for marker, sentence in _ASK_RULES:
        if marker in note:
            return sentence
    return GENERIC_ASK


def _firm_side_reason(item: RequestItem) -> str:
    """Why this row is the firm's problem rather than the client's, or ""."""
    note = (item.validation_notes or "").lower()
    if any(marker in note for marker in _FIRM_SIDE_MARKERS):
        return "waiting on a person here to read it, not on the client"
    return ""


def _missing_detail(item: RequestItem) -> str:
    return f"{item.expected_count} files expected" if item.expected_count > 1 else ""


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

        note = (item.validation_notes or "").lower()
        if _SCAFFOLD_MARKER in note:
            gaps.append(FirmSideFlag(
                item=item,
                reason="no request folder, so nothing could be filed here; re-run scaffold",
            ))
            continue

        # A Failed row we have not read is ours, not the client's. So is a
        # Partial row whose shortfall is a file we have not read: the client
        # may well have sent everything, and "1 of 2 received" would tell
        # them otherwise.
        reason = _firm_side_reason(item)
        if reason and item.status in (Status.FAILED, Status.PARTIAL):
            if item.status == Status.PARTIAL:
                reason = ("some of what arrived is waiting on a person here to "
                          "read it; confirm before asking for more")
            attention.append(FirmSideFlag(item=item, reason=reason))
            continue

        section = _section_for(item)
        ask = client_ask(item) if section != SECTION_MISSING else _missing_detail(item)
        lines.append(ReminderLine(item=item, section=section, ask=ask))

    order = {name: i for i, name in enumerate(SECTION_ORDER)}
    lines.sort(key=lambda line: (order[line.section], line.item.identifier))
    return lines, attention, gaps


def count_needs_review(engagement_dir: Path) -> int:
    """Files parked in ``00 - Needs Review`` — already sent, not yet identified."""
    review = engagement_dir / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    if not review.is_dir():
        return 0
    return sum(1 for path in review.iterdir() if path.is_file())


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
                "Everything goes in the same place - just drop it into the shared",
                "folder. One folder, no sorting and no naming needed; we do that:",
                f"  {share_link}",
                "",
            ]
        else:
            out += [
                "Everything goes in the same place - just drop it into the shared",
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

    Raises :class:`ReminderError` when the manifest is missing or has never
    been scanned — a reminder built from unscanned rows would ask for
    documents the client may well have sent already.
    """
    engagement_dir = Path(engagement_dir)
    manifest = engagement_dir / MANIFEST_FILENAME
    if not manifest.is_file():
        raise ReminderError(f"no {MANIFEST_FILENAME} in {engagement_dir}")

    items = load_manifest(manifest)
    if not items:
        raise ReminderError(f"{manifest} has no request rows")
    if not any(item.status for item in items):
        raise ReminderError(
            f"{manifest} has no scan results yet; run "
            f"`python -m tracker.scanner {engagement_dir}` first"
        )

    lines, attention, gaps = triage(items)
    active = [item for item in items if not item.manual_override]
    received = sum(1 for item in active if item.status == Status.RECEIVED)
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
        total=len(active),
    )

    if lines:
        subject = f"{engagement}: {len(lines)} document(s) still needed"
    else:
        subject = f"{engagement}: we have everything - thank you"

    return ReminderDraft(
        engagement=engagement,
        subject=subject,
        body=body,
        lines=lines,
        needs_attention=attention,
        scaffold_gaps=gaps,
        needs_review_files=count_needs_review(engagement_dir),
        total_requests=len(active),
        received_requests=received,
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
    as ``reminder-draft.NEW.txt`` and that path is returned instead. An hour
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
        footer += ["", "-" * 60,
                   "NOT ASKED FOR - fix these here first:"]
        footer += [f"  {flag.item.identifier} - {flag.item.document}: {flag.reason}"
                   for flag in draft.scaffold_gaps]
    if draft.needs_attention:
        footer += ["", "-" * 60,
                   "NOT ASKED FOR - waiting on us, not the client:"]
        footer += [f"  {flag.item.identifier} - {flag.item.document}: {flag.reason}"
                   for flag in draft.needs_attention]
    if draft.needs_review_files:
        footer += ["", "-" * 60,
                   f"{draft.needs_review_files} file(s) the client already sent are "
                   f"still in {REVIEW_DIR_NAME}.",
                   "Identify them before sending, or you may ask for something you have."]

    body = draft.text
    if footer:
        body += "\n" + "\n".join(footer) + "\n"

    header = [
        "DRAFT - NOTHING HAS BEEN SENT.",
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
    parser.add_argument("--due", default="", help="due date, YYYY-MM-DD")
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
            parser.error(f"--due must be YYYY-MM-DD, got {ns.due!r}")

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

    print("DRAFT - nothing has been sent.\n")
    print(result.text)

    for flag in result.scaffold_gaps:
        print(f"NOT ASKED: {flag.item.identifier} - {flag.item.document}: {flag.reason}")
    for flag in result.needs_attention:
        print(f"NOT ASKED: {flag.item.identifier} - {flag.item.document}: {flag.reason}")
    if result.needs_review_files:
        print(f"\nWARNING: {result.needs_review_files} file(s) the client already sent "
              f"are still in {REVIEW_DIR_NAME}.")
        print("Identify them before sending this, or you may ask for something you have.")

    if ns.write:
        written = write_draft(result, engagement_dir=ns.engagement_dir)
        print(f"\nDraft written to {written}")
