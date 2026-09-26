"""Tests for tracker/reminder.py — a draft, and only what the client owes.

Three rules run through all of this: the email never asks for something we
already have (or already excused), it never quotes our internal validation
vocabulary back at a client, and (decision 115) it never guesses whose
court an ambiguous request is in - one such request holds the whole draft
for a person, and nothing that reads like a sendable email is written.
"""

import datetime as dt
import hashlib
import os
import subprocess
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tracker import ledger, reasons
from tracker import reminder as reminder_module
from tracker.layout import inbox_of
from tracker.manifest import (
    EXPECTED_PATTERN,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
)
from tracker.reminder import (
    AMBIGUOUS_HOLD,
    APPROVED_NOTE,
    CHANGED_ADDED,
    CHANGED_HEADING,
    CHANGED_REMOVED,
    CONFIRM_HOLD,
    CONFIRM_REFUSAL,
    DEADLINE_CLAUSE,
    DRAFT_BANNER,
    DRAFT_FILENAME,
    EXTENSION_ASK,
    GENERIC_ASK,
    HELD_BACK_HEADING,
    HELD_LINE,
    HELD_REFUSAL,
    HOLD_COLOUR,
    LETTER_INK,
    NEW_DRAFT_FILENAME,
    PARKED_HOLD,
    PARTIAL_ASK,
    PHONE_CLAUSE,
    SECTION_FAILED,
    SECTION_MISSING,
    SECTION_ORDER,
    SECTION_PARTIAL,
    SET_ASIDE_DRAFT_PATTERN,
    STAGE_COLOURS,
    STAGE_EMPHASIS,
    STAGE_KEY,
    STAGE_LINE,
    STAGE_NONE,
    STAGES,
    SUBJECT_COMPLETE,
    SUBJECT_NEEDED,
    Emphasis,
    ReminderError,
    ReminderHeldError,
    approved_event,
    client_ask,
    count_needs_review,
    draft_changed,
    draft_reminder,
    drafted_event,
    held_refusal,
    is_approved_this_week,
    is_protected,
    is_unedited,
    recorded_fingerprint,
    render_html,
    set_aside_other_draft,
    stage_colour,
    stage_for,
    stage_named,
    triage,
    write_draft,
)
from tracker.scaffold import PREPARED_DIR_NAME, README_FIRST_LINE, REVIEW_DIR_NAME
from tracker.scanner import OVERRIDE_NOTE, PARTIAL_NOTE, SYNCING_NOTE


def item(identifier, document, status, **kwargs):
    """A request with the record's status on it. Notes said with a code -
    :func:`failure`, or a Reason's own sentence - carry that code into
    ``note_codes`` as the scan records it (decision 190); plain text carries
    none, however it reads."""
    notes = kwargs.get("validation_notes", "")
    if "note_codes" not in kwargs and reasons.code_of(notes):
        kwargs["note_codes"] = reasons.code_of(notes)
    return RequestItem(
        identifier=identifier, document=document, status=status, **kwargs
    )


def failure(name, said):
    """One failure as the scanner notes it, ``name.pdf: sentence``, carrying
    the sentence's code (decision 190)."""
    return reasons.Said(f"{name}: {said}", reasons.code_of(said))


SCANNED = [
    item("A01", "W-2 Wage Statements", Status.MISSING,
         period="TY2025", expected_count=2),
    item("A02", "Bank Statements", Status.PARTIAL,
         period="TY2025", expected_count=3, file_count=2),
    item("A03", "2024 Form 1040 Tax Return", Status.FAILED, period="TY2024",
         validation_notes=failure("prior.pdf", reasons.PASSWORD_PROTECTED.format())),
    item("A04", "Mortgage Interest Statement", Status.RECEIVED,
         period="TY2025", file_count=1, received_date=dt.date(2026, 2, 1)),
    item("A05", "Charitable Donations", Status.MISSING, manual_override=Override.NOT_APPLICABLE),
    item("A06", "Brokerage Statements", Status.FAILED, manual_override=Override.ACCEPTED,
         override_reason="Client confirmed this is the final version",
         validation_notes=f"{OVERRIDE_NOTE.format(override=Override.ACCEPTED)}; 1099.pdf: {reasons.WRONG_PERIOD.marker}"),
    item("A07", "K-1 Statements", Status.PENDING_SYNC, file_count=0,
         validation_notes=SYNCING_NOTE.format(n=1)),
]
#: The same engagement without A03: a Failed row the rules refused is
#: ambiguous and holds the draft (decision 115), so a test about what a
#: written draft looks like drafts from the rows that can be written.
SENDABLE = [i for i in SCANNED if i.identifier != "A03"]

#: The two dates the stages are written against, and a number for the firm.
DUE = dt.date(2026, 3, 15)
DEADLINE = dt.date(2026, 4, 15)
PHONE = "(555) 010-2020"


def said(when):
    """A date as the draft says it. Read from the draft's own format, so a
    test never asserts a spelling the composer does not use."""
    return when.strftime("%B %d, %Y")


def day(offset):
    """The day ``offset`` days before the Due Date."""
    return DUE - dt.timedelta(days=offset)


@pytest.fixture(autouse=True)
def the_firm_has_no_phone_unless_a_test_says_so(monkeypatch):
    """The firm's telephone number is a setting beside the app (decision
    117), and the settings file on a developer's machine is the firm's
    own. No test may read it: the final notice's phone sentence is blank
    here unless the test patches a number in."""
    monkeypatch.setattr(reminder_module, "firm_phone", lambda: "")


#: How the letter names the return: the household, the year and the return,
#: as everything that names one says it since decision 125.
LABEL = "Test Household 2025 Smith TY2025"


def engagement(tmp_path, items=SCANNED, name="Smith TY2025"):
    """A request list in the record, with the record carrying these statuses.

    The list holds the person's columns and nothing else, so the
    statuses are recorded the way a scan records them: one ``scanned``
    event through the store, under the lock.
    """
    from tests.conftest import make_engagement, seed_statuses

    folder = make_engagement(tmp_path, items, return_name=name, scaffold=False)
    updates = {
        i.identifier: StatusUpdate(
            status=i.status,
            file_count=i.file_count or 0,
            received_date=i.received_date,
            validation_notes=i.validation_notes,
            note_codes=i.note_codes,
        )
        for i in items if i.status
    }
    if updates:
        seed_statuses(folder, updates)
    return folder


# ------------------------------------------------------------- what we ask ----


def test_only_outstanding_rows_become_asks():
    lines, _, held = triage(SCANNED)
    assert [line.item.identifier for line in lines] == ["A01", "A02"]
    assert [line.section for line in lines] == [SECTION_MISSING, SECTION_PARTIAL]
    # A03 arrived and the rules refused it: a person's call, not the client's ask.
    assert [flag.item.identifier for flag in held] == ["A03"]


def test_received_and_pending_sync_are_never_asked_for():
    lines, _, _ = triage(SCANNED)
    asked = {line.item.identifier for line in lines}
    assert "A04" not in asked, "Received must not be re-requested"
    assert "A07" not in asked, "Pending Sync is in; the cloud is just slow"


def test_overrides_are_never_asked_for():
    """Not Applicable does not apply this year; Accepted was judged good
    enough by a person."""
    lines, attention, held = triage(SCANNED)
    everything = {f.item.identifier for f in attention + held}
    everything |= {line.item.identifier for line in lines}
    assert "A05" not in everything
    assert "A06" not in everything


# --------------------------------------------------------- how we phrase it ----


def test_partial_says_how_many_are_left():
    assert client_ask(SCANNED[1]) == PARTIAL_ASK.format(have=2, expected=3, missing=1)


@pytest.mark.parametrize("note, expected_fragment", [
    (failure("x.pdf", reasons.PASSWORD_PROTECTED.format()), reasons.PASSWORD_PROTECTED.client_ask),
    (failure("x.gdoc", reasons.GOOGLE_STUB.format(extension="gdoc")), reasons.GOOGLE_STUB.client_ask),
    (failure("x.pdf", reasons.TOO_SMALL.format(size_kb=0.1, minimum=5)), reasons.TOO_SMALL.client_ask),
    (failure("x.zip", reasons.EXTENSION_NOT_ALLOWED.format(extension="zip", allowed="pdf")),
     reasons.EXTENSION_NOT_ALLOWED.client_ask),
    (failure("x.pdf", reasons.WRONG_DOCUMENT.format(listed="'W-2'")), reasons.WRONG_DOCUMENT.client_ask),
    (failure("x.pdf", reasons.WRONG_PERIOD.format(pattern="2025")), reasons.WRONG_PERIOD.client_ask),
])
def test_failures_translate_to_a_plain_instruction(note, expected_fragment):
    ask = client_ask(item("A01", "Doc", Status.FAILED, validation_notes=note))
    assert expected_fragment in ask


def test_internal_vocabulary_never_reaches_the_client(tmp_path):
    draft = draft_reminder(engagement(tmp_path), client_name="Dana")
    body = draft.body.lower()
    for leak in ("keyword", "kb minimum", "validation", "prepared/",
                 "manifest", "tier", "pattern:", "scaffold"):
        assert leak not in body, f"internal term {leak!r} leaked into the email"


def test_multi_file_requests_say_how_many_are_expected(tmp_path):
    draft = draft_reminder(engagement(tmp_path))
    line = next(line for line in draft.lines if line.item.identifier == "A01")
    assert line.ask == EXPECTED_PATTERN.format(n=2)


# ------------------------------------------------- what we hold back, and why ----


def test_rows_we_have_not_read_go_to_the_accountant_not_the_client():
    rows = [item("B01", "Receipts", Status.FAILED,
                 validation_notes=failure("scan.pdf", reasons.NO_TEXT_LAYER.format()))]
    lines, attention, held = triage(rows)
    assert lines == [] and held == []
    assert [f.item.identifier for f in attention] == ["B01"]
    assert reasons.FIRM_WAITING in attention[0].reason


def test_a_request_with_nothing_in_is_simply_asked_for():
    """Decision 168: no request has a folder that could be missing, so a
    Missing row with no note is not a scaffold problem held back from the
    letter - there is no such list any more - but a plain ask."""
    rows = [item("B02", "Payroll Reports", Status.MISSING)]
    lines, attention, held = triage(rows)
    assert [line.item.identifier for line in lines] == ["B02"]
    assert attention == [] and held == []


def test_needs_review_files_are_counted_as_a_warning(tmp_path):
    folder = engagement(tmp_path)
    review = folder / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review.mkdir(parents=True)
    (review / "scan0012.pdf").write_bytes(b"x")
    (review / "photo.jpg").write_bytes(b"x")

    assert count_needs_review(folder) == 2
    assert draft_reminder(folder).needs_review_files == 2


def test_needs_review_count_is_zero_without_the_folder(tmp_path):
    assert count_needs_review(engagement(tmp_path)) == 0


def test_a_file_a_person_said_nothing_asks_for_is_not_counted_against_the_draft(tmp_path):
    """The warning stops a person asking for a document nobody has looked at.

    They have looked at a dismissed one, so counting it would leave the
    warning standing for the rest of the engagement and teach them to send
    the draft over the top of it. The count is still the folder's, though:
    a file dragged in by hand has no row and is nobody's decision yet.
    """
    from tests.conftest import seed_index
    from tracker.filer import NEEDS_REVIEW, NOT_REQUESTED, IndexEntry

    folder = engagement(tmp_path)
    review = folder / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review.mkdir(parents=True)
    for name in ("irs-notice.pdf", "scan0012.pdf", "dragged in by hand.pdf"):
        (review / name).write_bytes(b"x" * 10)

    def row(name, decision):
        return IndexEntry(
            received="2026-02-01", original_name=name, size_kb=0.1, digest=hashlib.sha256(name.encode()).hexdigest(),
            identifier="", prepared_location=f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/{name}",
            pbc_location=f"pbc/{name}", decision=decision, reason="unrecognized",
        )

    seed_index(folder, [
        row("irs-notice.pdf", NOT_REQUESTED), row("scan0012.pdf", NEEDS_REVIEW),
    ])
    assert count_needs_review(folder) == 2
    assert draft_reminder(folder).needs_review_files == 2


def test_a_resend_after_a_dismissal_counts_in_the_files_waiting_warning(tmp_path):
    """Decision 111: the client sent it again, so somebody has to look again.

    The copy a person set aside is still not counted - they have seen it -
    and the fresh copy beside it is, so the warning says there is one file
    waiting rather than none.
    """
    from tests.conftest import make_engagement, seed_statuses, sort
    from tests.test_scanner import text_pdf
    from tracker.filer import dismiss_review_file
    from tracker.reminder import REVIEW_WARNING

    rows = [item("A01", "W-2 Wage Statements", Status.MISSING, period="TY2025",
                 expected_count=1, allowed_extensions=("pdf",),
                 required_keywords=("W-2",))]
    folder = make_engagement(tmp_path, rows, household="Smith Family",
                             return_name="1040 - John A. Smith")
    seed_statuses(folder, {"A01": StatusUpdate(status=Status.MISSING, file_count=0)})

    text_pdf(inbox_of(folder) / "notice.pdf", "nothing the rules recognise")
    parked = sort(folder, today=dt.date(2026, 2, 1)).review[0]
    dismiss_review_file(folder, parked.pbc_location, "an IRS notice",
                        today=dt.date(2026, 2, 2))
    assert count_needs_review(folder) == 0, "they have looked at it"

    text_pdf(inbox_of(folder) / "notice.pdf", "nothing the rules recognise")
    again = sort(folder, today=dt.date(2026, 2, 8)).review[0]
    assert (folder / again.prepared_location).is_file()

    review = folder / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    assert len(list(review.iterdir())) == 2, "two arrivals, two copies"
    assert count_needs_review(folder) == 1
    draft = draft_reminder(folder)
    assert draft.needs_review_files == 1
    text = write_draft(draft, engagement_dir=folder).read_text(encoding="utf-8")
    assert REVIEW_WARNING.format(n=1) in text


# ----------------------------------------------------------------- drafting ----


def test_draft_greets_signs_and_counts(tmp_path):
    # Written fifteen days before the Due Date, so the stage is the second
    # one and the letter names the target date (decision 117): the day the
    # draft is written is what decides which sentences it carries.
    draft = draft_reminder(
        engagement(tmp_path),
        client_name="Dana Smith",
        share_link="https://drive.example/abc",
        due_date=dt.date(2026, 3, 15),
        today=dt.date(2026, 3, 15) - dt.timedelta(days=15),
        sender="Jason Park",
        firm="J Park & Associates, CPA",
    )
    assert draft.body.startswith("Hi Dana Smith,")
    # A06 is Accepted: signed off, so it is in (the one count, decision 38).
    assert "Of the 6 items we asked for, 2 are in." in draft.body
    assert "https://drive.example/abc" in draft.body
    assert "March 15, 2026" in draft.body
    assert draft.body.rstrip().endswith("J Park & Associates, CPA")
    assert draft.stage == 2
    # A03 holds the draft rather than being asked for; the subject counts the asks.
    assert draft.subject == SUBJECT_NEEDED.format(engagement=LABEL, n=2)
    assert draft.total_requests == 6 and draft.received_requests == 2


def test_draft_with_nothing_outstanding_says_so(tmp_path):
    rows = [item("A01", "W-2", Status.RECEIVED, file_count=1),
            item("A02", "Donations", Status.MISSING, manual_override=Override.NOT_APPLICABLE)]
    draft = draft_reminder(engagement(tmp_path, rows), client_name="Dana")
    assert draft.has_outstanding is False
    assert "we have everything" in draft.subject
    assert "Good news" in draft.body


def test_the_letter_names_the_household_the_year_and_the_return_and_can_be_overridden(tmp_path):
    folder = engagement(tmp_path)
    assert draft_reminder(folder).engagement == LABEL
    assert draft_reminder(folder, engagement_name="2025 Individual Return").engagement == (
        "2025 Individual Return"
    )


def test_a_folder_with_no_record_fails_loudly(tmp_path):
    from tracker.ledger import LEDGER_FILENAME

    with pytest.raises(ReminderError, match=f"no record in .*{LEDGER_FILENAME}"):
        draft_reminder(tmp_path / "nothing-here")


def test_an_unscanned_manifest_will_not_be_drafted_from(tmp_path):
    """Asking from unscanned rows would re-request what the client already sent."""
    rows = [item("A01", "W-2", ""), item("A02", "Bank Statements", "")]
    with pytest.raises(ReminderError, match="scanner"):
        draft_reminder(engagement(tmp_path, rows))


# ------------------------------------------------------------------ writing ----


def test_write_draft_marks_it_as_a_draft(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    path = write_draft(draft_reminder(folder), engagement_dir=folder)

    assert path == folder / DRAFT_FILENAME
    text = path.read_text(encoding="utf-8")
    assert text.startswith(DRAFT_BANNER)
    assert f"Subject: {SUBJECT_NEEDED.format(engagement=LABEL, n=2)}" in text


def test_written_draft_appends_firm_side_notes_below_the_email(tmp_path):
    rows = SENDABLE + [
        item("B01", "Receipts", Status.FAILED,
             validation_notes=failure("scan.pdf", reasons.NO_TEXT_AFTER_OCR.format())),
        item("B02", "Payroll Reports", Status.MISSING,
             validation_notes=reasons.FILE_MOVED.format(
                 listed="Prepared/B02 - Payroll - TY2025.pdf -> nowhere under Prepared")),
    ]
    folder = engagement(tmp_path, rows)
    review = folder / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review.mkdir(parents=True)
    (review / "scan0012.pdf").write_bytes(b"x")

    text = write_draft(draft_reminder(folder), engagement_dir=folder).read_text(
        encoding="utf-8"
    )
    email, _, firm_side = text.partition(HELD_BACK_HEADING)
    assert "B01" not in email and "B02" not in email
    assert "B01" in firm_side and "B02" in firm_side
    assert REVIEW_DIR_NAME in firm_side


def test_write_draft_needs_somewhere_to_write(tmp_path):
    with pytest.raises(ReminderError, match="path or engagement_dir"):
        write_draft(draft_reminder(engagement(tmp_path, SENDABLE)))


def test_a_partial_row_we_have_not_finished_reading_is_ours_not_the_clients():
    # One of two arrived and was read; the other is an un-OCR'd scan. The
    # client may well have sent both, so "1 of 2 received" is not known yet.
    row = item("A01", "W-2 Wage Statements", Status.PARTIAL, expected_count=2,
               file_count=1,
               validation_notes=(f"{PARTIAL_NOTE.format(count=1, expected=2)}; scan.pdf: "
                                 + reasons.NO_TEXT_LAYER.format()),
               note_codes=reasons.NO_TEXT_LAYER.code)
    lines, attention, held = triage([row])
    assert lines == [] and held == []
    assert [flag.item.identifier for flag in attention] == ["A01"]
    assert reasons.FIRM_WAITING_PARTIAL in attention[0].reason


def test_the_draft_is_built_from_the_record_and_nothing_else(tmp_path):
    """Friday: the scan saw A01 arrive and recorded it. Saturday: the draft
    must not ask for A01.

    A status only the record holds is what the draft counts - which since
    decision 103 is every status there is. The workbook a person edits
    carries none of this, and Excel being open on Friday cannot hold a
    status back any more.
    """
    from tests.conftest import seed_statuses

    folder = engagement(tmp_path, [
        item("A01", "W-2 Wage Statements", Status.MISSING),
        item("A02", "Bank Statements", Status.MISSING),
    ])
    seed_statuses(folder, {
        "A01": StatusUpdate(status=Status.RECEIVED, file_count=1, received_date=dt.date(2026, 2, 1)),
    })
    draft = draft_reminder(folder)
    assert [line.item.identifier for line in draft.lines] == ["A02"]
    assert draft.received_requests == 1


def test_needs_review_count_ignores_junk_and_sees_nested_files(tmp_path):
    review = tmp_path / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    (review / "sub").mkdir(parents=True)
    (review / "desktop.ini").write_text("x")
    (review / "top.pdf").write_bytes(b"x" * 10)
    (review / "sub" / "nested.pdf").write_bytes(b"x" * 10)
    assert count_needs_review(tmp_path) == 2


def test_the_draft_reads_the_engagement_details_itself(tmp_path):
    from tracker.manifest import EngagementInfo, load_manifest, save_rules

    folder = engagement(tmp_path)
    save_rules(folder, load_manifest(folder), EngagementInfo(
        client="Dana Lee", link="https://drive.example/abc", due=dt.date(2026, 4, 15),
        sender="Jason Park", firm="J Park & Associates, CPA",
    ))
    # Fifteen days out: the stage that names the target date, so the date
    # the record holds is one a person can read in the letter.
    draft = draft_reminder(folder, today=dt.date(2026, 4, 15) - dt.timedelta(days=15))
    assert "Hi Dana Lee," in draft.body
    assert "https://drive.example/abc" in draft.body
    assert "April 15, 2026" in draft.body
    assert draft.body.rstrip().endswith("Jason Park\nJ Park & Associates, CPA")
    # A one-off override still wins, for the CLI's flags.
    assert "Hi Sam," in draft_reminder(folder, client_name="Sam").body


def test_an_ocr_failure_is_the_firms_to_retry_not_the_clients_to_resend():
    from tracker import reasons

    assert reasons.OCR_FAILED.code in reasons.FIRM_SIDE
    assert reasons.first_of([reasons.OCR_FAILED.code]) is reasons.OCR_FAILED


# ------------------------------------------- the gate: an ambiguity holds ----
# Decision 115. A Failed row the rules refused with no firm-side marker is
# nobody's yet: a filed copy cannot fail the content rules on the router's
# own filing, so it is a rule edited after filing, a copy dragged in by
# hand, or a copy replaced - and whether the client resends or we fix it
# here is a person's call. The draft does not guess; it holds.


def _held_engagement(tmp_path, rows=None):
    return engagement(tmp_path, rows or [
        item("A01", "W-2 Wage Statements", Status.MISSING, expected_count=2),
        item("C01", "Form 1098 Mortgage Interest Statement", Status.FAILED,
             validation_notes=failure("1099.pdf", reasons.WRONG_DOCUMENT.format(listed="'1098'"))),
    ])


def test_a_failed_row_with_a_client_side_reason_holds_the_whole_draft(tmp_path):
    folder = _held_engagement(tmp_path)
    draft = draft_reminder(folder)
    assert [line.item.identifier for line in draft.lines] == ["A01"]
    assert [flag.item.identifier for flag in draft.held] == ["C01"]
    assert draft.held[0].reason.startswith(AMBIGUOUS_HOLD)
    assert reasons.WRONG_DOCUMENT.client_ask in draft.held[0].reason
    assert draft.is_held

    with pytest.raises(ReminderHeldError, match="C01"):
        write_draft(draft, engagement_dir=folder)
    assert not (folder / DRAFT_FILENAME).exists() and not (folder / NEW_DRAFT_FILENAME).exists()


def test_a_failed_row_with_a_firm_side_reason_does_not_hold(tmp_path):
    """Decisions 20 and 21 stand: a row we have not read rides the footer, and
    the draft is written."""
    folder = engagement(tmp_path, [
        item("A01", "W-2 Wage Statements", Status.MISSING),
        item("B01", "Receipts", Status.FAILED,
             validation_notes=failure("scan.pdf", reasons.NO_TEXT_LAYER.format())),
    ])
    draft = draft_reminder(folder)
    assert not draft.is_held and draft.held == []
    assert [flag.item.identifier for flag in draft.needs_attention] == ["B01"]
    text = write_draft(draft, engagement_dir=folder).read_text(encoding="utf-8")
    email, _, footer = text.partition(HELD_BACK_HEADING)
    assert "A01" in email and "B01" not in email and "B01" in footer


def test_a_partial_whose_shortfall_is_a_refused_file_holds_and_a_plain_partial_is_asked():
    refused = item("A02", "Bank Statements", Status.PARTIAL, expected_count=3, file_count=2,
                   validation_notes=f"{PARTIAL_NOTE.format(count=2, expected=3)}; nov.pdf: "
                                    + reasons.PASSWORD_PROTECTED.format(),
                   note_codes=reasons.PASSWORD_PROTECTED.code)
    plain = item("A03", "Brokerage Statements", Status.PARTIAL, expected_count=2, file_count=1,
                 validation_notes=PARTIAL_NOTE.format(count=1, expected=2))
    lines, attention, held = triage([refused, plain])
    assert [line.item.identifier for line in lines] == ["A03"]
    assert lines[0].ask == PARTIAL_ASK.format(have=1, expected=2, missing=1)
    assert attention == []
    assert [flag.item.identifier for flag in held] == ["A02"]
    assert reasons.PASSWORD_PROTECTED.client_ask in held[0].reason


def test_a_missing_row_with_a_firm_side_marker_is_held_back_not_asked():
    """Decision 109's rule, stated once here: a firm-side marker on any
    outstanding status is the firm's, Missing included."""
    row = item("D01", "Charitable Donations", Status.MISSING,
               validation_notes=failure("receipts.pdf", reasons.VANISHED.format(error="moved")))
    lines, attention, held = triage([row])
    assert lines == [] and held == []
    assert [flag.item.identifier for flag in attention] == ["D01"]
    assert attention[0].reason == reasons.VANISHED.firm_side_note


def test_a_failed_row_with_no_recognised_reason_is_held_not_asked_generically():
    """The one guess the drafter made - "please send it again" for a failure
    it could not name - is gone: it is held, with no reason in brackets."""
    row = item("A01", "Doc", Status.FAILED, validation_notes="x.pdf: something nobody predicted")
    lines, attention, held = triage([row])
    assert lines == [] and attention == []
    assert [flag.item.identifier for flag in held] == ["A01"]
    assert held[0].reason == AMBIGUOUS_HOLD
    assert reasons.GENERIC_ASK not in held[0].reason


def test_the_held_refusal_names_every_held_row_and_writes_nothing(tmp_path):
    folder = _held_engagement(tmp_path, [
        item("A01", "W-2 Wage Statements", Status.MISSING),
        item("C01", "Mortgage Interest", Status.FAILED,
             validation_notes=failure("x.pdf", reasons.WRONG_PERIOD.format(pattern="2025"))),
        item("D01", "Donations", Status.FAILED,
             validation_notes=failure("y.pdf", reasons.TOO_SMALL.format(size_kb=0.1, minimum=5))),
    ])
    draft = draft_reminder(folder)
    with pytest.raises(ReminderHeldError) as caught:
        write_draft(draft, engagement_dir=folder, preserve_edits=True)
    said = str(caught.value)
    assert said == HELD_REFUSAL.format(n=2, listed=f"{draft.held[0].item.label}, {draft.held[1].item.label}")
    assert "C01" in said and "D01" in said and "A01" not in said
    assert list(folder.glob("reminder-draft*")) == []
    # A hold's bracketed reason is in the row's own terms, as an ask would be.
    _, _, [xlsx] = triage([item("E01", "Sheet", Status.FAILED, allowed_extensions=("xlsx",),
                                   validation_notes=failure("x.zip", reasons.EXTENSION_NOT_ALLOWED.format(
                                       extension="zip", allowed="xlsx")))])
    assert EXTENSION_ASK.format(accepted=".xlsx") in xlsx.reason


def test_the_manual_draft_refuses_past_the_gate_with_exit_two(tmp_path):
    """Decision 13, amended: always available, never past the gate. The
    command line prints the held rows and, asked to write, refuses with the
    scanner's own "not done, not an error" exit code and writes nothing."""
    folder = _held_engagement(tmp_path)
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"}
    shown = subprocess.run([sys.executable, "-m", "tracker.reminder", str(folder)],
                           cwd=repo, capture_output=True, text=True, env=env)
    assert shown.returncode == 0
    assert f"{HELD_LINE}: " in shown.stdout and "C01" in shown.stdout
    # And no email: the composed text would ask for the clean rows alone,
    # which is the partial reminder the hold exists to prevent.
    assert SUBJECT_NEEDED.split("}")[-1] not in shown.stdout       # "... still needed"
    assert SUBJECT_COMPLETE.split("}")[-1] not in shown.stdout     # "... we have everything"
    assert "Subject:" not in shown.stdout and HELD_REFUSAL.split("{")[0] in shown.stdout
    written = subprocess.run([sys.executable, "-m", "tracker.reminder", str(folder), "--write"],
                             cwd=repo, capture_output=True, text=True, env=env)
    assert written.returncode == 2, written.stdout + written.stderr
    assert HELD_REFUSAL.split("{")[0] in written.stdout and "C01" in written.stdout
    assert not (folder / DRAFT_FILENAME).exists()


def _drafted(asked, at="2026-09-12T14:00:00Z"):
    return {ledger.EVENT_KEY: ledger.DRAFTED, ledger.AT_KEY: at, ledger.ASKED_KEY: asked,
            ledger.FILE_KEY: DRAFT_FILENAME, ledger.FINGERPRINT_KEY: "0" * 16}


def test_the_what_changed_block_names_what_was_added_and_removed_and_stays_out_of_the_body(tmp_path):
    folder = engagement(tmp_path, SENDABLE)          # asks A01 and A02
    draft = draft_reminder(folder)
    path = write_draft(draft, engagement_dir=folder, changed_from=_drafted(["A02", "Z99"]))
    text = path.read_text(encoding="utf-8")
    header, _, body = text.partition("=" * 60)
    day = ledger.day_of("2026-09-12T14:00:00Z").isoformat()
    assert CHANGED_HEADING.format(date=day) in header
    assert CHANGED_ADDED.format(label=draft.labels["A01"]) in header
    # A request no longer on the list is named by its bare identifier.
    assert CHANGED_REMOVED.format(label="Z99") in header
    assert "A02" not in header.split(CHANGED_HEADING.split("{")[0])[1]
    for word in (CHANGED_HEADING.split("{")[0], "(now asked)", "(no longer asked)"):
        assert word not in body
    assert is_unedited(path)


def test_no_what_changed_block_when_nothing_changed_or_no_earlier_draft(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    draft = draft_reminder(folder)
    heading = CHANGED_HEADING.split("{")[0]
    same = write_draft(draft, engagement_dir=folder, changed_from=_drafted(["A01", "A02"]))
    assert heading not in same.read_text(encoding="utf-8")
    none = write_draft(draft, engagement_dir=folder, changed_from=None)
    assert heading not in none.read_text(encoding="utf-8")
    # A hold carries no asked set: the first draft after one compares with
    # nothing, rather than with the rows the hold happened to leave clean.
    hold = {ledger.EVENT_KEY: ledger.DRAFTED, ledger.AT_KEY: "2026-09-12T14:00:00Z",
            ledger.HELD_KEY: ["C01"]}
    after_hold = write_draft(draft, engagement_dir=folder, changed_from=hold)
    assert heading not in after_hold.read_text(encoding="utf-8")


def test_section_failed_is_unreachable_from_a_pass(tmp_path):
    """Nothing a pass sorts lands under the old "RECEIVED, BUT WE COULD NOT
    USE IT": every Failed row is either the firm's or held.

    Decision 124: the heading is kept by choice, with these exact words, and
    stays out of the letter's order; a clean-up must not delete or rename it.
    """
    assert SECTION_FAILED == "RECEIVED, BUT WE COULD NOT USE IT"
    assert SECTION_FAILED not in SECTION_ORDER
    every_failed = [
        item(f"F{n:02d}", "Doc", Status.FAILED, validation_notes="x.pdf: " + reason.marker,
             note_codes=reason.code)
        for n, reason in enumerate(reasons.ALL)
    ] + [item("F99", "Doc", Status.FAILED, validation_notes="x.pdf: nobody predicted this")]
    lines, attention, held = triage(every_failed)
    assert lines == []
    assert {f.item.identifier for f in attention} | {f.item.identifier for f in held} == {
        i.identifier for i in every_failed
    }
    folder = engagement(tmp_path, SENDABLE + [
        item("B01", "Receipts", Status.FAILED,
             validation_notes=failure("scan.pdf", reasons.NO_TEXT_LAYER.format())),
    ])
    text = write_draft(draft_reminder(folder), engagement_dir=folder).read_text(encoding="utf-8")
    assert SECTION_FAILED not in text


def test_a_missing_row_with_a_file_moved_note_is_the_firms_and_the_draft_never_asks(tmp_path):
    """Decision 109 through decision 115's rule. A request whose working copy
    somebody here dragged out of its folder reads Missing - its folder is
    empty, which is the truth - and the firm-side marker on it keeps it out
    of the client's email: they sent the document, and asking them for it
    again is asking for a file the firm mislaid."""
    moved = item("A08", "W-2 Wage Statements", Status.MISSING, period="TY2025",
                 validation_notes="; ".join([
                     "was Received 2026-02-01; files changed",
                     reasons.FILE_MOVED.format(listed="Prepared/A08 - W-2 - TY2025.pdf "
                                                      "-> Prepared/C01 - A08 - W-2 - TY2025.pdf"),
                 ]), note_codes=reasons.FILE_MOVED.code)

    lines, attention, held = triage(SENDABLE + [moved])

    assert "A08" not in {line.item.identifier for line in lines}
    assert "A08" not in {flag.item.identifier for flag in held}
    assert [flag.reason for flag in attention if flag.item.identifier == "A08"] == [
        reasons.FILE_MOVED.firm_side_note
    ]

    folder = engagement(tmp_path, SENDABLE + [moved])
    text = write_draft(draft_reminder(folder), engagement_dir=folder).read_text(encoding="utf-8")
    waiting = text.split(f"{HELD_BACK_HEADING} - waiting on us, not the client:")[1]
    assert moved.label in waiting                  # named where a person will act on it
    assert text.count(moved.label) == 1            # and nowhere the client would read
# ------------------------------------------------- the four stages (d117) ----
# The same flat reminder every week is the one that gets tuned out. The
# stage is measured from the Due Date and changes the words only: who is
# asked is triage()'s answer at every stage, and the gate holds at all four.


@pytest.mark.parametrize("offset, expected", [(22, 1), (21, 2), (10, 3), (0, 4), (-1, 4)])
def test_the_stage_follows_the_due_date_at_the_thresholds(offset, expected):
    assert stage_for(DUE, day(offset)) == expected
    # No Due Date, no ladder: a heads-up with no deadline sentence is the
    # only honest letter when nobody has said when things are due.
    assert stage_for(None, day(offset)) == 1


def test_each_stage_writes_its_own_intro_deadline_and_close(tmp_path):
    folder = engagement(tmp_path, SENDABLE, name="Smith TY2025")
    words = {
        "engagement": LABEL,
        "target": said(DUE),
        "deadline_clause": DEADLINE_CLAUSE.format(deadline=said(DEADLINE)),
        "phone_clause": PHONE_CLAUSE.format(phone=PHONE),
    }
    for stage in STAGES:
        draft = draft_reminder(folder, due_date=DUE, filing_deadline=DEADLINE, phone=PHONE,
                               today=day(30), stage=stage.number)
        assert draft.stage == stage.number
        assert draft.subject == stage.subject.format(engagement=LABEL, n=2)
        assert stage.intro.format(**words) in draft.body
        assert stage.close.format(**words) in draft.body
        if stage.deadline:
            assert stage.deadline.format(**words) in draft.body
        # The list itself never changes with the stage.
        assert SECTION_MISSING in draft.body and SECTION_PARTIAL in draft.body


def test_stage_one_carries_no_deadline_sentence(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    draft = draft_reminder(folder, due_date=DUE, filing_deadline=DEADLINE, today=day(22))
    assert draft.stage == 1 and STAGES[0].deadline == ""
    assert said(DUE) not in draft.body and said(DEADLINE) not in draft.body
    assert STAGES[0].close in draft.body


def test_stages_three_and_four_name_both_dates_when_the_filing_deadline_is_set_and_only_the_target_when_blank(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    for number in (3, 4):
        stage = stage_named(number)
        both = draft_reminder(folder, due_date=DUE, filing_deadline=DEADLINE,
                              today=DUE, stage=number)
        assert said(DUE) in both.body
        assert DEADLINE_CLAUSE.format(deadline=said(DEADLINE)) in both.body

        target_only = draft_reminder(folder, due_date=DUE, today=DUE, stage=number)
        assert said(DUE) in target_only.body and said(DEADLINE) not in target_only.body
        assert DEADLINE_CLAUSE.split("{")[0] not in target_only.body

        # No Due Date at all: the day's stage would be 1, so this only
        # arises when a person forces one - and half a sentence with a
        # blank where a date should be is not written at all.
        forced = draft_reminder(folder, today=DUE, stage=number)
        assert stage.deadline.split("{")[0] not in forced.body
        assert stage.intro in forced.body


def test_stage_four_drops_the_phone_sentence_when_the_firm_has_no_phone(tmp_path, monkeypatch):
    folder = engagement(tmp_path, SENDABLE)
    # The number is the firm's setting, and the draft reads it itself.
    monkeypatch.setattr(reminder_module, "firm_phone", lambda: PHONE)
    with_phone = draft_reminder(folder, due_date=DUE, today=DUE)
    assert with_phone.stage == 4
    assert PHONE_CLAUSE.format(phone=PHONE) in with_phone.body

    monkeypatch.setattr(reminder_module, "firm_phone", lambda: "")
    without = draft_reminder(folder, due_date=DUE, today=DUE)
    assert PHONE not in without.body
    assert PHONE_CLAUSE.split("{")[0] not in without.body
    assert STAGES[3].close.format(phone_clause="") in without.body


def test_the_draft_header_names_the_firm_phone(tmp_path, monkeypatch):
    """The header says which firm number the letter gives, or that it gives
    none (decision 190), so a number changed in the settings is seen before
    the letter goes. The line sits above the rule: the body's fingerprint
    is the same with or without it, and the draft still reads unedited."""
    from tracker.reminder import (
        FIRM_PHONE_LINE,
        FIRM_PHONE_UNUSED_LINE,
        NO_FIRM_PHONE_LINE,
        pasted_text,
    )

    def header_and_body(path):
        header, _, body = path.read_text(encoding="utf-8").partition("=" * 60)
        return header.splitlines(), body

    folder = engagement(tmp_path, SENDABLE)
    unset = write_draft(draft_reminder(folder, due_date=DUE, today=DUE), engagement_dir=folder)
    header, body = header_and_body(unset)
    assert NO_FIRM_PHONE_LINE in header and NO_FIRM_PHONE_LINE not in body
    assert is_unedited(unset)
    quiet_line = write_draft(draft_reminder(folder, due_date=DUE, today=DUE, stage=1),
                             engagement_dir=folder)
    stage_one_without = (recorded_fingerprint(quiet_line), pasted_text(quiet_line))

    monkeypatch.setattr(reminder_module, "firm_phone", lambda: PHONE)
    final = write_draft(draft_reminder(folder, due_date=DUE, today=DUE), engagement_dir=folder)
    header, body = header_and_body(final)
    assert FIRM_PHONE_LINE.format(phone=PHONE) in header and PHONE in body
    assert is_unedited(final)

    # A stage that offers no call: the number is on file, the header does
    # not claim the letter gives it - and only the header changed, so the
    # body and its fingerprint are those of the same letter with no number set.
    early = write_draft(draft_reminder(folder, due_date=DUE, today=DUE, stage=1), engagement_dir=folder)
    header, body = header_and_body(early)
    assert FIRM_PHONE_UNUSED_LINE.format(phone=PHONE) in header and PHONE not in body
    assert (recorded_fingerprint(early), pasted_text(early)) == stage_one_without
    assert is_unedited(early)


def test_the_recipient_set_is_identical_at_every_stage_and_a_firm_side_row_is_in_none(tmp_path):
    rows = SENDABLE + [item("B01", "Receipts", Status.FAILED,
                            validation_notes=failure("scan.pdf", reasons.NO_TEXT_LAYER.format()))]
    folder = engagement(tmp_path, rows, name="Every Stage TY2025")
    drafts = [draft_reminder(folder, due_date=DUE, today=DUE, stage=n) for n in (1, 2, 3, 4)]
    assert {tuple(draft.asked) for draft in drafts} == {("A01", "A02")}
    for draft in drafts:
        assert [flag.item.identifier for flag in draft.needs_attention] == ["B01"]
        assert "B01" not in draft.body, "a row we have not read is never the client's, at any stage"


def test_the_stage_is_in_the_header_above_the_fingerprint_and_not_in_the_fingerprinted_body(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    path = write_draft(draft_reminder(folder, due_date=DUE, today=DUE), engagement_dir=folder)
    text = path.read_text(encoding="utf-8")
    header, _, body = text.partition("=" * 60)
    line = STAGE_LINE.format(number=4, name=stage_named(4).name)
    lines = header.splitlines()
    assert line in lines and line not in body
    assert lines.index(line) < next(i for i, one in enumerate(lines)
                                    if recorded_fingerprint(path) in one)
    assert is_unedited(path), "the stage is a fact about the draft, not part of what is pasted"

    # A quiet week is on no rung at all.
    quiet = engagement(tmp_path, [item("A01", "W-2", Status.RECEIVED, file_count=1)],
                       name="Quiet TY2025")
    written = write_draft(draft_reminder(quiet, due_date=DUE, today=DUE), engagement_dir=quiet)
    assert STAGE_NONE in written.read_text(encoding="utf-8")


def test_the_drafted_event_carries_the_stage_and_a_crossed_threshold_is_a_change(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    before = drafted_event(draft_reminder(folder, due_date=DUE, today=day(11)), None)
    after = drafted_event(draft_reminder(folder, due_date=DUE, today=day(10)), None)
    assert before[STAGE_KEY] == 2 and after[STAGE_KEY] == 3
    assert before[ledger.ASKED_KEY] == after[ledger.ASKED_KEY], "the same rows, a harder letter"
    assert draft_changed(before, after) is True
    assert draft_changed(before, before) is False
    # A hold is not a letter, so it is at no stage.
    held = draft_reminder(_held_engagement(tmp_path / "held"), due_date=DUE, today=DUE)
    assert STAGE_KEY not in drafted_event(held, None)


def test_stage_three_regenerates_the_same_lines_at_stage_three(tmp_path):
    folder = engagement(tmp_path, SENDABLE)
    asked = draft_reminder(folder, due_date=DUE, today=DUE, stage=3)
    assert asked.stage == 3 and asked.subject == stage_named(3).subject.format(
        engagement=LABEL, n=2)

    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"}
    shown = subprocess.run(
        [sys.executable, "-m", "tracker.reminder", str(folder),
         "--due", DUE.isoformat(), "--today", DUE.isoformat(), "--stage", "3"],
        cwd=repo, capture_output=True, text=True, env=env,
    )
    assert shown.returncode == 0, shown.stdout + shown.stderr
    assert asked.text in shown.stdout.replace("\r\n", "\n")


def test_the_gate_holds_at_every_stage(tmp_path):
    folder = _held_engagement(tmp_path)
    for number in (1, 2, 3, 4):
        draft = draft_reminder(folder, due_date=DUE, today=DUE, stage=number)
        assert draft.is_held and [flag.item.identifier for flag in draft.held] == ["C01"]
        with pytest.raises(ReminderHeldError, match="C01"):
            write_draft(draft, engagement_dir=folder)
    assert list(folder.glob("reminder-draft*")) == []


# ------------------------------ a parked file the client could fix (d117) ----
# The end-to-end review's third discrepancy: a drop the rules refused at
# tier 2 never reaches a request's status, so the row stayed Missing and
# the draft asked the client for a document they had sent. The hold reads
# the review queue's own shortlist - what the card shows a person - so a
# locked PDF named for a request holds that request, as it should.

#: The rows the drops below are routed against: the same two requests, with
#: the keywords that let a file name point at one of them.
DROPPED = [
    item("A01", "W-2 Wage Statements", Status.MISSING, period="TY2025", expected_count=2,
         required_keywords=("W-2",), min_size_kb=0),
    item("A02", "Bank Statements", Status.PARTIAL, period="TY2025", expected_count=3,
         file_count=2, any_keywords=("bank statement",), min_size_kb=0),
]


def sorted_drop(folder, write):
    """A file the client sent, sorted by the filer as a pass sorts it.

    ``write`` is handed the drop folder and puts one file in it, so every
    claim below is made about the row the *router* wrote, not one a test
    typed: what a parked file points at is exactly what a person sees on
    the review card.
    """
    from tests.conftest import sort
    from tracker.scaffold import scaffold_engagement

    scaffold_engagement(folder)
    write(inbox_of(folder))
    return sort(folder, today=dt.date(2026, 2, 1))


def locked(name, *, password="secret123"):
    """A password-protected PDF, the file the client is certain they sent."""
    from tests.test_validators import write_pdf

    return lambda shared: write_pdf(shared / name, password=password)


def parked_rows(folder):
    from tracker.filer import NEEDS_REVIEW, read_index

    return [entry for entry in read_index(folder) if entry.decision == NEEDS_REVIEW]


def test_a_locked_pdf_named_for_a_request_parks_with_that_request_on_its_shortlist_and_holds_the_draft(tmp_path):
    """The headline case, end to end: the client sent their W-2 with a
    password on it. Nothing could be read, so no request accepted it and
    the row stayed Missing - and the draft would have asked for a document
    they know they sent. The file's own name is what is left (decision 92),
    it is what the review card offers, and it is what holds the draft."""
    from tracker.review import shortlist_for

    folder = engagement(tmp_path, DROPPED, name="Locked TY2025")
    report = sorted_drop(folder, locked("W-2 Jane Smith 2025.pdf"))
    assert len(report.review) == 1

    [row] = parked_rows(folder)
    assert row.candidates == "", "a name is no candidate; nothing is filed on one"
    assert row.code == reasons.PASSWORD_PROTECTED.code
    assert [s.identifier for s in shortlist_for(row, DROPPED)] == ["A01"]

    draft = draft_reminder(folder)
    assert [line.item.identifier for line in draft.lines] == ["A02"]
    assert [flag.item.identifier for flag in draft.held] == ["A01"]
    assert draft.held[0].reason == PARKED_HOLD.format(ask=reasons.PASSWORD_PROTECTED.client_ask)
    assert draft.is_held
    with pytest.raises(ReminderHeldError, match="A01"):
        write_draft(draft, engagement_dir=folder)
    assert list(folder.glob("reminder-draft*")) == []
    assert drafted_event(draft, None)[ledger.HELD_KEY] == ["A01"]


def test_a_locked_pdf_whose_name_says_nothing_holds_nothing(tmp_path):
    """Nothing could be read and the name says nothing either: there is no
    request to name in the sentence, so there is nothing to ask about and
    the rest of the reminder goes out."""
    folder = engagement(tmp_path, DROPPED, name="Mystery TY2025")
    report = sorted_drop(folder, locked("scan0012.pdf"))
    assert len(report.review) == 1
    assert parked_rows(folder)[0].evidence == "", "nothing pointed anywhere"

    draft = draft_reminder(folder)
    assert draft.held == []
    assert [line.item.identifier for line in draft.lines] == ["A01", "A02"]


def test_a_blocked_reading_still_holds(tmp_path):
    """The other half of the same discrepancy, and the half that already
    worked: a file the rules *could* read and then refused - an upload
    that arrived almost empty. Its own words point at the request, the
    client can fix it, and it holds in the row's own terms."""
    from tests.test_scanner import text_pdf

    rows = [replace(DROPPED[0], min_size_kb=50), DROPPED[1]]
    folder = engagement(tmp_path, rows, name="Blocked TY2025")
    report = sorted_drop(folder, lambda shared: text_pdf(
        shared / "w2.pdf", "Form W-2 Wage and Tax Statement 2025"))
    assert len(report.review) == 1
    assert parked_rows(folder)[0].candidate_list == ["A01"]

    draft = draft_reminder(folder)
    assert [flag.item.identifier for flag in draft.held] == ["A01"]
    assert PARKED_HOLD.format(ask=reasons.TOO_SMALL.client_ask) == draft.held[0].reason
    assert [line.item.identifier for line in draft.lines] == ["A02"]


def test_a_parked_file_with_a_firm_side_reason_holds_nothing(tmp_path, monkeypatch):
    """A scan nobody here could read is ours to fix, not the client's to
    resend: decision 115's rule, unchanged. Its name points at A01 exactly
    as the locked file's did, and it still holds nothing."""
    from tests.test_scanner import text_pdf
    from tracker.review import shortlist_for

    monkeypatch.setattr("tracker.content_check._ocr_pdf", lambda p: None)   # no OCR here
    folder = engagement(tmp_path, DROPPED, name="Unreadable TY2025")
    report = sorted_drop(folder, lambda shared: text_pdf(shared / "W-2 Jane Smith 2025.pdf", ""))
    assert len(report.review) == 1

    [row] = parked_rows(folder)
    assert row.code == reasons.NO_READABLE_TEXT.code
    assert [s.identifier for s in shortlist_for(row, DROPPED)] == ["A01"]

    draft = draft_reminder(folder)
    assert draft.held == []
    assert [line.item.identifier for line in draft.lines] == ["A01", "A02"]


def test_a_set_aside_row_never_holds(tmp_path):
    """A row a person has already answered - "no request asks for this" -
    is their decision, not an open question about the client."""
    from tracker.filer import NOT_REQUESTED, dismiss_review_file, read_index

    folder = engagement(tmp_path, DROPPED, name="Dismissed TY2025")
    sorted_drop(folder, locked("W-2 Jane Smith 2025.pdf"))
    [row] = parked_rows(folder)
    dismiss_review_file(folder, row.pbc_location, "the client sent it twice")
    assert [entry.decision for entry in read_index(folder)] == [NOT_REQUESTED]

    draft = draft_reminder(folder)
    assert draft.held == []
    assert [line.item.identifier for line in draft.lines] == ["A01", "A02"]


def gone_both(folder, row):
    """Staff tidy the review folder and the client deletes the original,
    then a pass runs (decision 157, ruling B5)."""
    from tests.conftest import sort
    from tracker.layout import locate

    (folder / row.prepared_location).unlink()
    locate(folder, row.pbc_location).unlink()
    sort(folder, today=dt.date(2026, 2, 8))


def test_a_parked_file_whose_copy_and_original_are_both_gone_still_holds(tmp_path):
    """Decision 157's review, S-1 (its probe P2). The locked W-2 parked and
    held A01; then its review copy and its original were both deleted. The
    pass says so and the row reads File Moved, but nobody has looked at the
    file: the question it raised is still open, so A01 stays held until a
    person decides, and the client is not asked for it with nobody
    looking."""
    from tracker.filer import FILE_MOVED, both_gone, read_index

    folder = engagement(tmp_path, DROPPED, name="Gone TY2025")
    sorted_drop(folder, locked("W-2 Jane Smith 2025.pdf"))
    [row] = parked_rows(folder)
    assert [flag.item.identifier for flag in draft_reminder(folder).held] == ["A01"]

    gone_both(folder, row)

    [after] = read_index(folder)
    assert after.decision == FILE_MOVED and both_gone(after) and after.identifier == ""
    draft = draft_reminder(folder)
    assert [flag.item.identifier for flag in draft.held] == ["A01"]
    assert draft.held[0].reason == PARKED_HOLD.format(ask=reasons.PASSWORD_PROTECTED.client_ask)
    assert [line.item.identifier for line in draft.lines] == ["A02"]
    assert draft.is_held


def test_a_set_aside_row_whose_copy_and_original_are_both_gone_still_holds_nothing(tmp_path):
    """The other side of the same rule: a person's "no request asks for
    this" stays their answer when the file then goes."""
    from tracker.filer import both_gone, dismiss_review_file, read_index

    folder = engagement(tmp_path, DROPPED, name="Gone dismissed TY2025")
    sorted_drop(folder, locked("W-2 Jane Smith 2025.pdf"))
    [row] = parked_rows(folder)
    dismiss_review_file(folder, row.pbc_location, "the client sent it twice")

    gone_both(folder, row)

    [after] = read_index(folder)
    assert both_gone(after)
    draft = draft_reminder(folder)
    assert draft.held == []
    assert [line.item.identifier for line in draft.lines] == ["A01", "A02"]


def test_a_parked_locked_file_whose_shortlist_is_partial_holds_it_too(tmp_path):
    """A locked second statement is "1 of 2" that the client believes is
    2 of 2, and a count that argues with them is worse than a question."""
    folder = engagement(tmp_path, DROPPED, name="Partial TY2025")   # A02 is 2 of 3
    sorted_drop(folder, locked("November Bank Statement.pdf"))

    draft = draft_reminder(folder)
    assert [flag.item.identifier for flag in draft.held] == ["A02"]
    assert [line.item.identifier for line in draft.lines] == ["A01"]


# ------------------- a near miss holds the letter and blames nobody (d140) ----
# Jason, 2026-09-23: while a document that shows a request's form number
# waits for a person, that request's reminder is held - and nothing tells
# the client their file was wrong, because it may well be exactly right.

#: The same two requests, with A01 asking for the three phrases the 1040
#: catalog's W-2 row asks for.
NEAR_MISSED = [
    replace(DROPPED[0], required_keywords=(
        "W-2", "wage and tax statement", "employee's social security number")),
    DROPPED[1],
]


def test_a_near_miss_holds_the_reminder_and_blames_no_file(tmp_path):
    """Decision 140, claim 4. A W-2 whose reading lost the SSN label parks
    with A01 on its shortlist; the draft holds A01 rather than asking for
    it, and neither the held line nor the draft says the file was wrong."""
    from tests.test_router import LOST_ONE_PHRASE
    from tests.test_scanner import text_pdf
    from tracker.review import shortlist_for

    folder = engagement(tmp_path, NEAR_MISSED, name="Near Miss TY2025")
    report = sorted_drop(folder, lambda shared: text_pdf(shared / "scan0001.pdf", LOST_ONE_PHRASE))
    assert len(report.review) == 1

    [row] = parked_rows(folder)
    assert row.code == reasons.SHOWS_ITS_FORM_NUMBER.code
    assert row.candidates == "", "a suggestion is never a candidate"
    assert [s.identifier for s in shortlist_for(row, NEAR_MISSED)] == ["A01"]

    draft = draft_reminder(folder)
    assert [flag.item.identifier for flag in draft.held] == ["A01"]
    assert draft.held[0].reason == CONFIRM_HOLD.format(
        note=reasons.SHOWS_ITS_FORM_NUMBER.firm_side_note)
    assert [line.item.identifier for line in draft.lines] == ["A02"]
    blame = (reasons.WRONG_DOCUMENT.client_ask, reasons.GENERIC_ASK, "could not be used",
             "wrong", "right file", "send it again")
    for said in (draft.held[0].reason, draft.text):
        for word in blame:
            assert word not in said, word
    refusal = held_refusal(draft)
    assert refusal == CONFIRM_REFUSAL.format(listed=draft.held[0].item.label)
    assert "held until a person confirms the parked file (open it in Needs Review)" in refusal
    assert "resends" not in refusal and "fix it here" not in refusal
    with pytest.raises(ReminderHeldError, match="A01"):
        write_draft(draft, engagement_dir=folder)
    assert list(folder.glob("reminder-draft*")) == []


def test_a_draft_held_both_ways_is_refused_in_both_sentences():
    """Decision 140: a confirm hold beside an ordinary one. Each row is
    refused in its own sentence - the ordinary row still asks whether the
    client resends, the confirm-held row only that a person confirms."""
    from tracker.reminder import FirmSideFlag, ReminderDraft

    decide = FirmSideFlag(item=NEAR_MISSED[1], reason=AMBIGUOUS_HOLD)
    confirm = FirmSideFlag(item=NEAR_MISSED[0], reason=CONFIRM_HOLD.format(note="x"), confirm=True)
    draft = ReminderDraft(engagement="E", subject="", body="", held=[decide, confirm])
    assert held_refusal(draft) == "; ".join([
        HELD_REFUSAL.format(n=1, listed=NEAR_MISSED[1].label),
        CONFIRM_REFUSAL.format(listed=NEAR_MISSED[0].label),
    ])


#: The reasons whose parked file held the letter before decision 140: every
#: one the client could fix, and no other. Typed out, so a reason that
#: starts or stops holding fails here by name.
HELD_BEFORE_140 = {
    "password", "no-pages", "unreadable-pdf", "unreadable-image", "google-stub",
    "extension", "too-small", "wrong-document", "no-keyword", "wrong-period",
    "extraction-failed",
}
#: The client-side reasons decision 143 added - a locked or damaged email or
#: zip, which the client can fix by sending the documents on their own -
#: hold as a locked or damaged PDF does.
HELD_SINCE_143 = {"container-locked", "container-damaged"}


@pytest.mark.parametrize("reason", reasons.ALL, ids=lambda r: r.code)
def test_every_existing_reason_holds_exactly_as_before(reason):
    """Decision 140, claim 5. ``Reason.holds`` replaced "not firm-side" as
    the hold's test, so every reason that held still holds, in the same
    words, every one that did not still does not - and the two new reasons,
    the page's and the file name's, are the firm-side reasons that hold.
    Asked of the hold itself, with a parked row carrying the reason's own
    sentence and evidence for A01."""
    # The reasons' own sample sentence, so a placeholder a later reason adds
    # is filled here the moment test_reasons.py learns it.
    from tests.test_reasons import _sample
    from tests.test_review import parked_row
    from tracker.records import RULE_REQUIRED, WHERE_TITLE, Evidence
    from tracker.reminder import _ask_for, _parked_holds

    row = parked_row("scan.pdf", {"A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),)},
                     reason="scan.pdf: " + _sample(reason), code=reason.code)
    holds = {identifier: (flag.reason, flag.confirm)
             for identifier, flag in _parked_holds(DROPPED, [row]).items()}
    if reason in (reasons.SHOWS_ITS_FORM_NUMBER, reasons.NAME_POINTS_AT):
        assert reason.firm_side and reason.holds
        assert holds == {"A01": (CONFIRM_HOLD.format(note=reason.firm_side_note), True)}
        return
    held = HELD_BEFORE_140 | HELD_SINCE_143
    assert reason.holds == (reason.code in held) == (not reason.firm_side)
    expected = ({"A01": (PARKED_HOLD.format(ask=_ask_for(reason, DROPPED[0])), False)}
                if reason.code in held else {})
    assert holds == expected


# ---------------------- the letter, the body and the ladder (decision 118) ----
# The text a person pastes, the HTML body Outlook keeps and the shape the
# app draws its preview from are three renderings of one Letter. These are
# the claims that say they cannot come apart.


def _plain(markup: str) -> str:
    """Markup with its tags taken out and its whitespace folded.

    A break and the end of a block are where the text breaks; every other
    tag is emphasis inside a sentence and closes over no space at all, so
    a coloured date must not come back with a gap before the full stop.
    """
    import html as html_entities
    import re

    broken = re.sub(r"<(?:br\s*/?|/p|/li|/ul|/div)\s*>", " ", markup)
    return " ".join(html_entities.unescape(re.sub(r"<[^>]+>", "", broken)).split())


def _folded(text: str) -> str:
    return " ".join(text.split())


def _every_letter(tmp_path):
    """One draft per stage, plus a quiet week: every letter there is."""
    folder = engagement(tmp_path, SENDABLE, name="Every Letter TY2025")
    drafts = [draft_reminder(folder, due_date=DUE, filing_deadline=DEADLINE, phone=PHONE,
                             share_link="https://share.example.test/every-letter",
                             today=DUE, stage=number) for number in (1, 2, 3, 4)]
    quiet = engagement(tmp_path, [item("A01", "W-2", Status.RECEIVED, file_count=1)],
                       name="Quiet Letter TY2025")
    drafts.append(draft_reminder(quiet, due_date=DUE, today=DUE))
    return drafts


def test_the_html_body_says_exactly_what_the_text_body_says(tmp_path):
    """Two renderings of one Letter, so a sentence cannot reach a client in
    one and not the other. Tags out, whitespace folded, every stage and a
    quiet week - and the subject is in neither, because it goes in
    Outlook's own box and never in the body."""
    for draft in _every_letter(tmp_path):
        assert _plain(render_html(draft)) == _folded(draft.body)
        assert draft.subject not in _plain(render_html(draft))


def test_the_html_carries_the_stages_colour_inline_and_no_style_block_no_class_and_fetches_nothing(tmp_path):
    """Outlook keeps an inline style and drops everything else, and a letter
    that fetched anything would tell somebody else who is being chased."""
    import re

    drafts = _every_letter(tmp_path)
    for draft in drafts:
        markup = render_html(draft)
        for forbidden in ("<style", "class=", "src=", "<link", "@import", "javascript:",
                          "background-image", "<script"):
            assert forbidden not in markup, (draft.stage, forbidden)
        # The one address in it is the client's own share link, and nothing
        # else is fetched to render it.
        assert re.findall(r'href="([^"]*)"', markup) in ([], [draft.letter.link])
    # Each stage wears its own colour, and no letter wears another's.
    for draft in drafts[1:4]:
        assert stage_colour(draft.stage) in render_html(draft)
    for draft in (drafts[0], drafts[4]):
        markup = render_html(draft)
        for other in (2, 3, 4):
            assert stage_colour(other) not in markup, (draft.stage, other)


def test_the_palette_mirrors_the_design_systems_tokens():
    """The app cannot read the design system at run time, so the values are
    mirrored once in the page module - and held to the tokens wherever the
    design system is readable from the repository's parent tree."""
    import re

    from tracker.page import PALETTE

    assert PALETTE == {
        "navy_900": "#1B2A4A",
        "slate_600": "#3A4660",
        "grey_500": "#5C6577",
        "gold_800": "#7A5F16",
        "warning_600": "#8A5A10",
        "danger_600": "#A8362F",
        "cream_50": "#F5F0E8",
        "white": "#FFFFFF",
    }
    # Every key the ladder and the letter name is one the palette holds.
    assert set(STAGE_COLOURS.values()) <= set(PALETTE)
    assert HOLD_COLOUR in PALETTE and set(LETTER_INK.values()) <= set(PALETTE)

    tokens = None
    for parent in Path(__file__).resolve().parents:
        branding = parent / "Branding"
        if not branding.is_dir():
            continue
        found = sorted(branding.rglob("tokens.json")) + sorted(branding.rglob("colors.css"))
        if found:
            tokens = found[0]
            break
    if tokens is None:
        pytest.skip("the design system is not beside this checkout; the values above are the pin")

    declared = {name.replace("-", "_"): value.upper() for name, value in re.findall(
        r'[-"]{1,2}([a-z]+-\d{2,3})"?\s*:\s*"?(#[0-9a-fA-F]{6})', tokens.read_text(encoding="utf-8"))}
    assert declared, f"no primitives read out of {tokens.name}"
    for name, value in PALETTE.items():
        if name in declared:
            assert declared[name] == value.upper(), name


def test_the_letter_structure_flattens_to_the_text_body(tmp_path):
    """The shape the app draws its preview from cannot say a third thing."""
    for draft in _every_letter(tmp_path):
        assert draft.letter.text() == draft.body
    # And the two cases parts of the shape have to be empty for.
    folder = engagement(tmp_path, SENDABLE, name="Bare TY2025")
    bare = draft_reminder(folder, today=DUE)          # no Due Date, no share link
    assert bare.letter.deadline == () and bare.letter.link == ""
    assert bare.letter.text() == bare.body


def test_the_emphasis_table_matches_the_design_notes():
    """Where each stage spends its colour and its weight, pinned: one table
    serves the letter, the clipboard and the card, and stage 1's colour is
    the body's own ink, so applying it colours nothing."""
    from tracker.page import PALETTE

    assert STAGE_EMPHASIS == {
        1: Emphasis(),
        2: Emphasis(target_colour=True),
        3: Emphasis(deadline_colour=True, dates_bold=True, list_bold=True),
        4: Emphasis(subject_colour=True, subject_bold=True, deadline_colour=True,
                    dates_bold=True, consequences_bold=True, list_colour=True, list_bold=True),
    }
    assert STAGE_COLOURS == {1: "slate_600", 2: "gold_800", 3: "warning_600", 4: "danger_600"}
    assert PALETTE[STAGE_COLOURS[1]] == PALETTE[LETTER_INK["body"]]
    assert HOLD_COLOUR == STAGE_COLOURS[3]


def test_the_stage_toggle_regenerates_the_same_recipients_at_every_stage_and_writes_nothing(tmp_path):
    """Moving the toggle is not drafting: the same rows, different words,
    and not one byte on disk."""
    folder = engagement(tmp_path, SENDABLE, name="Toggle TY2025")
    before = sorted(path.name for path in folder.iterdir())
    asked = set()
    for number in (1, 2, 3, 4):
        draft = draft_reminder(folder, due_date=DUE, today=DUE, stage=number)
        asked.add(tuple(draft.asked))
        assert draft.stage == number and render_html(draft) and draft.body
    assert asked == {("A01", "A02")}
    assert sorted(path.name for path in folder.iterdir()) == before
    assert list(folder.glob("reminder-draft*")) == []


# ------------------------------------------------------- approve (decision 118) ----


def approve(folder, draft, written):
    """Record an approval the way the app's command does: under the lock."""
    from tracker import store
    from tracker.locking import engagement_lock

    with engagement_lock(folder):
        store.record(store.connect(), folder, approved_event(draft, written))


def test_an_approved_draft_is_protected_for_the_week_and_the_approval_is_spent_next_week(tmp_path):
    """The predicate the pass reads, on its own: approved this week, the
    file is protected; the draft day moves, and it is this week's draft to
    write again."""
    folder = engagement(tmp_path, SENDABLE, name="Approved TY2025")
    draft = draft_reminder(folder, due_date=DUE, today=DUE)
    written = write_draft(draft, engagement_dir=folder)
    week = dt.date.today() - dt.timedelta(days=1)
    approve(folder, draft, written)

    assert is_approved_this_week(folder, written, since=week)
    assert is_protected(folder, written, approved_since=week)
    # A writer that cannot measure the week - the command line is a layer
    # below the runner - still may not write over what a person approved.
    assert is_protected(folder, written), "an approval holds against every writer"
    assert is_approved_this_week(folder, written, since=None)
    # The pass, which knows the week, is the one caller that spends it.
    assert not is_approved_this_week(folder, written,
                                     since=dt.date.today() + dt.timedelta(days=7))
    # The event carries a number, a name and identifiers - no word of the letter.
    event = approved_event(draft, written)
    assert event[STAGE_KEY] == draft.stage
    assert event[ledger.FILE_KEY] == DRAFT_FILENAME
    assert event[ledger.FINGERPRINT_KEY] == recorded_fingerprint(written)
    assert event[ledger.ASKED_KEY] == draft.asked


def test_an_approval_names_a_text_and_not_a_filename(tmp_path):
    """The match is on the fingerprint in the file's own header: another
    draft written to the same name is not the one that was approved, and a
    draft a person then edits is protected because they edited it."""
    folder = engagement(tmp_path, SENDABLE, name="Changed TY2025")
    draft = draft_reminder(folder, due_date=DUE, today=DUE)
    written = write_draft(draft, engagement_dir=folder)
    week = dt.date.today() - dt.timedelta(days=1)
    approve(folder, draft, written)
    assert is_approved_this_week(folder, written, since=week)

    # The same file name, a different letter: the approval does not follow it.
    other = write_draft(draft_reminder(folder, due_date=DUE, today=DUE, stage=1),
                        engagement_dir=folder)
    assert other == written and not is_approved_this_week(folder, written, since=week)
    assert not is_protected(folder, written, approved_since=week)

    written.write_bytes(written.read_bytes() + b"\r\nPS: and the boat.\r\n")
    assert is_protected(folder, written, approved_since=week), "an edit protects it anyway"


def test_an_approval_lapses_when_the_letter_is_edited(tmp_path):
    """An approval covers the text a person read, not what the file becomes
    (decision 190). It records that text's fingerprint - the one the card
    shows for it - and an edit after it lapses the approval: the file is
    still protected, because it was edited, and it reads "approved, then
    edited". An approval recorded before 190, with no text fingerprint,
    reads the same way: not an approval, so the person approves again."""
    from tracker import store
    from tracker.locking import engagement_lock
    from tracker.reminder import (
        APPROVED_THEN_EDITED,
        approval_state,
        draft_fingerprint,
        letter_fingerprint,
        shown_text,
    )

    folder = engagement(tmp_path, SENDABLE, name="Lapsed TY2025")
    draft = draft_reminder(folder, due_date=DUE, today=DUE)
    written = write_draft(draft, engagement_dir=folder)
    week = dt.date.today() - dt.timedelta(days=1)
    approve(folder, draft, written)

    event = approved_event(draft, written)
    assert event[ledger.TEXT_FINGERPRINT_KEY] == draft_fingerprint(shown_text(draft.subject, draft.body))
    assert approval_state(folder, written, since=week) == APPROVED_NOTE

    written.write_bytes(written.read_bytes() + b"\r\nPS: and the boat.\r\n")
    assert letter_fingerprint(written) != event[ledger.TEXT_FINGERPRINT_KEY]
    assert approval_state(folder, written, since=week) == APPROVED_THEN_EDITED
    assert not is_approved_this_week(folder, written, since=week)
    assert not is_approved_this_week(folder, written, since=None)
    assert is_protected(folder, written, approved_since=week), "edited, so still protected"

    # Approved again as it now stands: in force, and the edit is covered.
    approve(folder, draft, written)
    assert approval_state(folder, written, since=week) == APPROVED_NOTE

    # An event from before 190 names no text: it is not an approval.
    legacy = {key: value for key, value in approved_event(draft, written).items()
              if key != ledger.TEXT_FINGERPRINT_KEY}
    with engagement_lock(folder):
        store.record(store.connect(), folder, legacy)
    assert approval_state(folder, written, since=week) == APPROVED_THEN_EDITED
    assert not is_approved_this_week(folder, written, since=week)


def test_an_approval_from_before_190_still_protects_its_letter_in_the_deploy_week(tmp_path):
    """An approval recorded before decision 190 has no letter fingerprint,
    so it no longer counts: the card reads "approved, then edited" and the
    person approves again. It still protects the file it names - the pass
    in the week of the deploy writes its draft beside the approved letter,
    never over it, though nobody has edited it (nothing vanishes)."""
    from tracker import store
    from tracker.locking import engagement_lock
    from tracker.reminder import APPROVED_THEN_EDITED, approval_state, is_unedited

    folder = engagement(tmp_path, SENDABLE, name="Deploy Week TY2025")
    draft = draft_reminder(folder, due_date=DUE, today=DUE)
    written = write_draft(draft, engagement_dir=folder)
    approved_letter = written.read_bytes()
    legacy = {key: value for key, value in approved_event(draft, written).items()
              if key != ledger.TEXT_FINGERPRINT_KEY}
    with engagement_lock(folder):
        store.record(store.connect(), folder, legacy)
    week = dt.date.today() - dt.timedelta(days=1)

    assert is_unedited(written), "nobody edited the approved letter"
    assert approval_state(folder, written, since=week) == APPROVED_THEN_EDITED
    assert not is_approved_this_week(folder, written, since=week)
    assert is_protected(folder, written, approved_since=week)

    regenerated = write_draft(draft_reminder(folder, due_date=DUE, today=DUE, stage=1),
                              engagement_dir=folder, preserve_edits=True, approved_since=week)
    assert regenerated.name == NEW_DRAFT_FILENAME, regenerated
    assert written.read_bytes() == approved_letter, "the approved letter was written over"


def test_approve_sets_the_other_draft_aside_by_name_and_never_deletes_anything(tmp_path):
    """Nothing under an engagement is deleted by an approval: a draft
    standing beside the approved one is renamed for the day, and a second
    on the same day takes the filer's own colliding name."""
    folder = engagement(tmp_path, SENDABLE, name="Aside TY2025")
    (folder / NEW_DRAFT_FILENAME).write_bytes(b"another draft\r\n")
    before = len(list(folder.iterdir()))

    moved = set_aside_other_draft(folder, DUE)
    assert moved is not None
    assert moved.name == SET_ASIDE_DRAFT_PATTERN.format(date=DUE.isoformat())
    assert moved.read_bytes() == b"another draft\r\n"
    assert not (folder / NEW_DRAFT_FILENAME).exists()
    assert len(list(folder.iterdir())) == before, "renamed, never deleted"

    (folder / NEW_DRAFT_FILENAME).write_bytes(b"and one more\r\n")
    second = set_aside_other_draft(folder, DUE)
    assert second is not None and second != moved and second.exists() and moved.exists()

    assert set_aside_other_draft(folder, DUE) is None, "nothing beside it, nothing to move"


def test_the_practice_page_says_approved_in_one_word():
    """The Drafted column is narrow and the word is the page's, not a sentence."""
    assert APPROVED_NOTE and " " not in APPROVED_NOTE


def test_the_command_lines_write_lands_beside_an_approved_draft_and_never_over_it(tmp_path):
    """An approval holds against every writer, not only against the pass.

    ``python -m tracker.reminder <dir> --write`` cannot ask the runner
    which draft week it is - it is a layer below it - so it hands
    :func:`write_draft` no week at all. That must not make it the one
    writer allowed to throw away what a person approved in the app an hour
    earlier: without a week, an approval that still names this file's own
    header fingerprint protects it, and the fresh draft lands beside it
    exactly as it lands beside one somebody edited.
    """
    from tracker import store

    folder = engagement(tmp_path, SENDABLE, name="CLI Approved TY2025")
    draft = draft_reminder(folder, due_date=DUE, today=DUE)
    written = write_draft(draft, engagement_dir=folder)
    approve(folder, draft, written)
    kept = written.read_bytes()

    store.close()          # the command line opens the same store for itself
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"}
    run = subprocess.run(
        [sys.executable, "-m", "tracker.reminder", str(folder), "--write",
         "--due", DUE.isoformat(), "--today", DUE.isoformat(), "--stage", "1"],
        cwd=repo, capture_output=True, text=True, env=env,
    )
    assert run.returncode == 0, run.stdout + run.stderr

    assert written.read_bytes() == kept, "an approval must never be clobbered"
    beside = folder / NEW_DRAFT_FILENAME
    assert beside.is_file() and beside.read_bytes() != kept
    assert stage_named(1).close in beside.read_text(encoding="utf-8")
    assert NEW_DRAFT_FILENAME in run.stdout


# ------------------------------------------- the reminder waits for the sort ----
# Decision 133. A pass drafts after it sorts, but the sort does not always
# take what the client sent - and a person can draft from the app hours
# after the last pass. While the household's own Drop files here holds a
# file the sort has not taken, the letter could ask for a document sitting
# in it, and it cannot know which request that file answers: the whole
# draft is held, as decision 115's is.


def waiting_in(folder, *names):
    """Files the client sent, still waiting in this return's household inbox."""
    inbox = inbox_of(folder)
    inbox.mkdir(parents=True, exist_ok=True)
    for name in names:
        (inbox / name).write_bytes(b"%PDF-1.4 waiting to be sorted")
    return inbox


def test_a_file_waiting_in_the_drop_folder_holds_the_whole_reminder(tmp_path):
    from tracker.reminder import INBOX_HOLD, unsorted_in_inbox

    folder = engagement(tmp_path, SENDABLE)
    assert not draft_reminder(folder).is_held, "nothing waits yet"
    waiting_in(folder, "W-2 from the client.pdf")
    # A client who drags a whole folder in has sent that too.
    (inbox_of(folder) / "bank").mkdir()
    (inbox_of(folder) / "bank" / "march.pdf").write_bytes(b"%PDF-1.4 a statement")

    draft = draft_reminder(folder)

    assert unsorted_in_inbox(folder) == 2 and draft.unsorted == 2
    assert draft.is_held and draft.held == [], "no row holds it; the inbox does, whole"
    # The letter is still composed, as a held draft's always is - it is
    # simply never written, shown or sent.
    assert draft.lines and draft.body
    assert reminder_module.held_refusal(draft) == INBOX_HOLD.format(n=2)


def test_a_transfer_still_in_progress_holds_the_reminder(tmp_path):
    from tracker.filer import iter_drops

    folder = engagement(tmp_path, SENDABLE)
    inbox = waiting_in(folder)
    (inbox / "W-2 2025.pdf.driveupload").write_bytes(b"%PDF-1.4 half of it")
    assert iter_drops(inbox) == [], "a transfer in flight is not a drop yet"

    draft = draft_reminder(folder)

    assert draft.unsorted == 1 and draft.is_held


@pytest.mark.skipif(sys.platform == "darwin", reason="APFS refuses the names the machine cannot handle")
def test_a_name_the_machine_cannot_handle_holds_the_reminder_until_a_person_deals_with_it(tmp_path):
    from tracker.filer import unreachable_drops

    folder = engagement(tmp_path, SENDABLE)
    inbox = waiting_in(folder)
    if sys.platform == "win32":
        # A Mac or a sync client can deliver a name ending in a dot; only
        # the \\?\ form creates one here, and only it removes one.
        raw = "\\\\?\\" + str(inbox / "bank statement.pdf.")
    else:
        # A name UTF-8 cannot hold: the record could never name it.
        raw = os.fsencode(inbox) + b"/bank statement \xff.pdf"
    with open(raw, "wb") as handle:
        handle.write(b"%PDF-1.4 a name the machine cannot handle")
    assert len(unreachable_drops(inbox)) == 1

    # Held, and held again on every reading: a file that can never be
    # sorted keeps the letter held until a person deals with the file.
    for _ in range(2):
        draft = draft_reminder(folder)
        assert draft.is_held and draft.unsorted == 1

    os.remove(raw)          # a person deals with the file
    assert not draft_reminder(folder).is_held


def test_the_readme_and_sync_junk_do_not_hold_the_reminder(tmp_path):
    from tracker.layout import README_NAME

    folder = engagement(tmp_path, SENDABLE)
    inbox = waiting_in(folder)
    (inbox / README_NAME).write_text(f"{README_FIRST_LINE}\nWhat we still need from you",
                                      encoding="utf-8")
    for junk in ("desktop.ini", "Thumbs.db", ".DS_Store", "~$W-2.docx"):
        (inbox / junk).write_bytes(b"junk")

    draft = draft_reminder(folder)

    assert draft.unsorted == 0 and not draft.is_held


#: A write killed half way through, in a process of its own: the file whose
#: name begins with argv[3] gets half its text and then the process dies,
#: running no clean-up, as a power cut runs none (decision 155).
A_WRITE_KILLED_HALF_WAY = """
import os
import sys
from pathlib import Path
sys.path[:0] = [sys.argv[2]]
real_open = Path.open

def open_(self, mode="r", *args, **kwargs):
    handle = real_open(self, mode, *args, **kwargs)
    if "w" in mode and self.name.startswith(sys.argv[3]):
        real_write = handle.write
        def half(text):
            real_write(text[: len(text) // 2])
            handle.flush()
            os._exit(9)
        handle.write = half
    return handle

Path.open = open_
folder = Path(sys.argv[1])
if sys.argv[4] == "draft":
    from tracker.reminder import draft_reminder, write_draft
    write_draft(draft_reminder(folder), engagement_dir=folder)
else:
    from tracker.filer import refresh_household_readme
    from tracker.layout import household_of
    refresh_household_readme(household_of(folder))
"""


def test_the_draft_and_the_readme_are_whole_or_absent_after_a_kill(tmp_path):
    """Decision 155, A-F5. A draft torn by a power cut failed its own
    fingerprint and read as a person's edit for good: every week's draft
    went beside it as ``reminder-draft.NEW.txt``. And the README a client
    reads is the same kind of file. Each is written whole to a temp and
    swapped in, so a kill leaves the file as it was - absent, or the last
    whole one - and never half of the new one."""
    from tracker.filer import refresh_household_readme
    from tracker.layout import README_NAME, household_of
    from tracker.scaffold import scaffold_engagement
    from tracker.store import close

    folder = engagement(tmp_path, SENDABLE)
    repo = str(Path(__file__).resolve().parents[1])
    draft = folder / DRAFT_FILENAME

    def killed(prefix: str, what: str) -> None:
        close()
        done = subprocess.run([sys.executable, "-c", A_WRITE_KILLED_HALF_WAY, str(folder), repo,
                               prefix, what], capture_output=True, text=True, timeout=300)
        assert done.returncode == 9, done.stderr

    killed(DRAFT_FILENAME, "draft")                  # the first draft ever: absent after
    assert not draft.exists()
    assert write_draft(draft_reminder(folder), engagement_dir=folder, preserve_edits=True) == draft

    before = draft.read_bytes()
    killed(DRAFT_FILENAME, "draft")                  # a rewrite: the last whole one after
    assert draft.read_bytes() == before
    assert is_unedited(draft)

    scaffold_engagement(folder)
    readme = refresh_household_readme(household_of(folder))
    assert readme is not None and readme.name == README_NAME
    readme.write_text(f"{README_FIRST_LINE}\r\nan older list\r\n", encoding="utf-8", newline="")
    killed(README_NAME, "readme")
    assert readme.read_bytes() == f"{README_FIRST_LINE}\r\nan older list\r\n".encode("ascii")


def test_a_readme_write_left_behind_by_a_crash_does_not_hold_the_reminder(tmp_path):
    """The review of decision 133: the README's atomic write leaves
    ``_README.txt.<pid>.<hex>.tmp`` beside it when it is killed. That is
    the firm's leftover, not a transfer the client started - while a
    client's own ``.tmp`` still holds."""
    from tracker.layout import README_NAME

    folder = engagement(tmp_path, SENDABLE)
    inbox = waiting_in(folder)
    (inbox / README_NAME).write_text(f"{README_FIRST_LINE}\nthe list", encoding="utf-8")
    (inbox / f"{README_NAME}.4242.9f1c0a2b.tmp").write_text("half a list", encoding="utf-8")

    assert draft_reminder(folder).unsorted == 0

    (inbox / "W-2 scan.pdf.tmp").write_bytes(b"still arriving")

    assert draft_reminder(folder).unsorted == 1


def test_a_folder_the_pass_cannot_list_holds_the_reminder(tmp_path, monkeypatch):
    """What the client put in a folder the pass cannot list is not sorted,
    so the letter could ask for it: one count per such folder."""
    from tracker import filer

    folder = engagement(tmp_path, SENDABLE)
    inbox = waiting_in(folder)
    locked = inbox / "From my accountant"
    locked.mkdir()
    monkeypatch.setattr(filer, "unlistable_folders",
                        lambda path: [locked] if path == inbox else [])

    draft = draft_reminder(folder)

    assert draft.unsorted == 1 and draft.is_held


def test_a_held_draft_by_the_inbox_writes_nothing_and_says_why(tmp_path):
    from tracker.reminder import INBOX_HOLD

    folder = engagement(tmp_path, SENDABLE, name="Waiting TY2025")
    waiting_in(folder, "W-2 from the client.pdf")
    draft = draft_reminder(folder)

    with pytest.raises(ReminderHeldError) as caught:
        write_draft(draft, engagement_dir=folder, preserve_edits=True)
    assert str(caught.value) == INBOX_HOLD.format(n=1)
    assert list(folder.glob("reminder-draft*")) == []
    # On the record it is a hold, naming no row: a hold is not a draft.
    assert drafted_event(draft, None)[ledger.HELD_KEY] == []

    # The command line says the same sentence and, asked to write, refuses
    # with the scanner's own "not done, not an error" and writes nothing.
    from tracker import store

    store.close()
    repo = Path(__file__).resolve().parents[1]
    env = {**os.environ, "PYTHONPATH": str(repo), "PYTHONIOENCODING": "utf-8"}
    written = subprocess.run([sys.executable, "-m", "tracker.reminder", str(folder), "--write"],
                             cwd=repo, capture_output=True, text=True, env=env)
    assert written.returncode == 2, written.stdout + written.stderr
    assert INBOX_HOLD.format(n=1) in written.stdout
    assert "Subject:" not in written.stdout
    assert list(folder.glob("reminder-draft*")) == []


def test_both_holds_are_said_together(tmp_path):
    from tracker.reminder import INBOX_HOLD

    folder = _held_engagement(tmp_path)
    waiting_in(folder, "another W-2.pdf")
    draft = draft_reminder(folder)

    assert [flag.item.identifier for flag in draft.held] == ["C01"] and draft.unsorted == 1
    said = reminder_module.held_refusal(draft)
    assert said == "; ".join([
        INBOX_HOLD.format(n=1),
        HELD_REFUSAL.format(n=1, listed=draft.held[0].item.label),
    ])
    with pytest.raises(ReminderHeldError) as caught:
        write_draft(draft, engagement_dir=folder)
    assert str(caught.value) == said


def test_an_inbox_of_another_household_that_feeds_this_return_does_not_hold_it(tmp_path):
    """Decision 133's ruling 4: only the return's own household's inbox. A
    drop folder that also feeds it (decision 132) is another client's, and
    its arrivals are not this household's letter to decide."""
    from dataclasses import replace as replaced

    from tests.conftest import make_engagement
    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir
    from tracker.records import Feed
    from tracker.reminder import unsorted_in_inbox

    folder = engagement(tmp_path, SENDABLE)
    other = make_engagement(tmp_path, SENDABLE, household="Other Family",
                            return_name="1040 - Other Client", scaffold=False)
    feeding = private_household_dir(tmp_path, "Other Family")
    save_household(feeding, replaced(load_household_info(feeding),
                                     feeds=(Feed("Test Household", "Smith TY2025"),)))
    waiting_in(other, "a document for the Smiths.pdf")

    assert unsorted_in_inbox(other) == 1, "it waits in the other household's own inbox"
    draft = draft_reminder(folder)
    assert draft.unsorted == 0 and not draft.is_held


# ---------------------------------------------- decision 137: the security review ----


def test_a_reminder_link_is_only_http_or_https_refused_on_save_and_dropped_from_a_letter(tmp_path):
    """Decision 137 (L5): the link a letter pastes is a web address or
    nothing. Any other kind is refused when the return's or the household's
    details are saved; one already in a record from before the rule is left
    out of the letter, and the draft says so and where to fix it."""
    from tracker import store
    from tracker.households import load_household_info, save_household
    from tracker.layout import household_of
    from tracker.locking import engagement_lock
    from tracker.manifest import EngagementInfo, ManifestError, load_manifest, save_rules
    from tracker.records import LINK_REFUSED
    from tracker.reminder import LINK_DROPPED, write_draft

    # Nothing a person has to decide first, so the draft is written.
    folder = engagement(tmp_path, items=[i for i in SCANNED if i.status != Status.FAILED])
    for bad in ("file:///C:/Users/firm/secret", "javascript:alert(1)", "mailto:x@example.com",
                r"\\server\share"):
        with pytest.raises(ManifestError, match="is not a web address"):
            save_rules(folder, load_manifest(folder), EngagementInfo(client="Dana", link=bad))
        household = household_of(folder)
        with pytest.raises(ManifestError, match="is not a web address"):
            save_household(household, replace(load_household_info(household), link=bad))
    for good in ("https://drive.example/abc", "HTTP://drive.example/abc", ""):
        save_rules(folder, load_manifest(folder), EngagementInfo(client="Dana", link=good))
    assert LINK_REFUSED.format(link="ftp://x").startswith("The link 'ftp://x'")

    # A link recorded before the rule, written straight into the record.
    old = "file:///C:/Users/firm/secret"
    with engagement_lock(folder):
        store.record(store.connect(), folder, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [], ledger.REMOVED_KEY: [], ledger.INFO_KEY: {"link": old}}))
    draft = draft_reminder(folder)
    assert old not in draft.body
    assert draft.link_dropped == LINK_DROPPED.format(link=old)
    written = write_draft(draft, engagement_dir=folder).read_text(encoding="utf-8")
    assert draft.link_dropped in written
    assert old not in written.split(draft.link_dropped)[0]           # never in the letter itself


# --------------------------------------------- decision 142: accepted, not asked ----


def test_the_reminder_never_chases_or_reports_a_not_asked_row(tmp_path):
    """A row nobody asked for is skipped before anything else: no line, no
    firm-side flag, no hold for a failed file under it, and the "N of M"
    figure counts asked rows only."""
    rows = [
        *SENDABLE,
        item("B01", "Social Security Benefit Statement", Status.MISSING, asked=False),
        item("B02", "1099-C", Status.MISSING, asked=False,
             validation_notes=failure("scan.pdf", reasons.NO_TEXT_LAYER.format())),
        item("B03", "W-2G", Status.FAILED, asked=False,
             validation_notes=failure("w2g.pdf", reasons.PASSWORD_PROTECTED.format())),
        item("B04", "1098-E", Status.RECEIVED, asked=False, file_count=1,
             received_date=dt.date(2026, 2, 1)),
    ]
    lines, attention, held = triage(rows)
    unasked = {"B01", "B02", "B03", "B04"}
    for flagged in (lines, attention, held):
        assert not unasked & {one.item.identifier for one in flagged}

    draft = draft_reminder(
        engagement(tmp_path, items=rows), client_name="Dana Smith",
        share_link="https://drive.example/abc", due_date=DUE,
        today=DUE - dt.timedelta(days=15), sender="Jason Park", firm="J Park & Associates, CPA",
    )
    assert "Of the 5 items we asked for, 2 are in." in draft.body
    # B04 is a not-asked row that received a document: thanked apart.
    assert "We have also received 1 other document from you." in draft.body
    assert draft.total_requests == 5 and draft.received_requests == 2
    for word in ("Social Security", "1099-C", "W-2G", "1098-E"):
        assert word not in draft.body, word


@pytest.mark.parametrize("received, total, also, said", [
    (1, 5, 0, "Of the 5 items we asked for, 1 is in."),
    (2, 5, 0, "Of the 5 items we asked for, 2 are in."),
    (1, 1, 0, "Of the 1 item we asked for, 1 is in."),
    (1, 5, 2, "Of the 5 items we asked for, 1 is in. We have also received 2 other documents from you."),
    (3, 5, 1, "Of the 5 items we asked for, 3 are in. We have also received 1 other document from you."),
    (0, 5, 2, "We have received 2 documents from you, thank you. The 5 items we asked for are still needed."),
    (0, 1, 1, "We have received 1 document from you, thank you. The 1 item we asked for is still needed."),
    (0, 1, 3, "We have received 3 documents from you, thank you. The 1 item we asked for is still needed."),
    (0, 4, 1, "We have received 1 document from you, thank you. The 4 items we asked for are still needed."),
    (0, 5, 0, ""),
])
def test_the_letters_count_is_jasons_sentence_in_the_singular_and_the_plural(received, total, also, said):
    """Decision 142, Jason's wording of 2026-09-24: the count is of what we
    asked for, and the documents that arrived for rows nobody asked for are
    thanked in a second sentence, said only when there are any; when none
    of what we asked for is in but others are, his softer pair thanks the
    client first and says what is still needed. Every noun and verb agrees
    with its number: this is a sentence a client reads."""
    from tracker.reminder import progress_line

    assert progress_line(received, total, also) == said


# ------------------------------------------- codes are columns (decision 190) ----
# A row's cause is its code. The Reason cell and the Validation Notes carry
# what the client chose - a file's name, a subfolder's name - and a reason's
# placeholders carry a parser's class or a page's spelling; none of it can
# change what the letter asks or what it holds.


def _filled(reason, text):
    """``reason``'s sentence with every string placeholder filled with
    ``text``, and the numeric ones with numbers."""
    import string

    names = {name for _, name, _, _ in string.Formatter().parse(reason.template) if name}
    numbers = {"size_kb": 1.0, "minimum": 5}
    return reason.format(**{name: numbers.get(name, text) for name in names})


def _what_the_letter_does(reason, text):
    """What one reason, its detail and its file named ``text``, makes the
    letter do: the Failed row's ask, the hold of a parked row pointing at
    A01, and where a Failed row goes."""
    from tests.test_review import parked_row
    from tracker.records import RULE_REQUIRED, WHERE_TITLE, Evidence
    from tracker.reminder import _parked_holds

    said = _filled(reason, text)
    failed = item("A01", "W-2 Wage Statements", Status.FAILED,
                  validation_notes=failure(f"{text}.pdf", said))
    row = parked_row(f"{text}.pdf", {"A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),)},
                     reason=f"{reasons.UNMATCHED}; {said}", code=said.code)
    lines, attention, held = triage([failed])
    holds = {identifier: (flag.reason, flag.confirm)
             for identifier, flag in _parked_holds(DROPPED, [row]).items()}
    return (row.code, client_ask(failed), holds,
            [f.reason for f in attention], [f.reason for f in held], len(lines))


@pytest.mark.parametrize("reason", reasons.ALL, ids=lambda r: r.code)
def test_no_client_text_can_change_what_a_row_means(reason):
    """Decision 190, the SPEC-167 cross product re-aimed. Every reason's
    placeholders, and the file's own name, filled with each other reason's
    marker - the words a search used to find another cause by - and the
    row's code, the ask and the hold are exactly what they are with
    placeholders that say nothing."""
    plain = _what_the_letter_does(reason, "x")
    assert plain[0] == reason.code
    for other in reasons.ALL:
        assert _what_the_letter_does(reason, other.marker) == plain, other.code


def test_rows_written_before_190_read_as_cause_not_recorded():
    """A row or a note written before decision 190 has no code. Its cause
    was not recorded, and nothing reads one back out of its words: a
    parked row holds where its shortlist names a request - the safe
    direction, since a person confirms it - and is asked with the generic
    sentence; a Failed request's ask is the generic one and it is held."""
    from tests.test_review import parked_row
    from tracker.records import RULE_REQUIRED, WHERE_TITLE, Evidence
    from tracker.reminder import _parked_holds

    record = {"A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),)}
    for sentence in (reasons.PASSWORD_PROTECTED.format(), reasons.NO_READABLE_TEXT.format(),
                     reasons.EXTENSION_NOT_ALLOWED.format(extension="exe", allowed="pdf")):
        old = parked_row("w2.pdf", record, reason=str(sentence), code="")
        holds = _parked_holds(DROPPED, [old])
        assert {i: (f.reason, f.confirm) for i, f in holds.items()} == {
            "A01": (PARKED_HOLD.format(ask=GENERIC_ASK), False)}
    nowhere = parked_row("scan.pdf", {}, reason=str(reasons.PASSWORD_PROTECTED.format()), code="")
    assert _parked_holds(DROPPED, [nowhere]) == {}

    failed = item("A01", "W-2 Wage Statements", Status.FAILED,
                  validation_notes="x.pdf: " + str(reasons.NO_TEXT_LAYER.format()))
    assert failed.note_codes == ""
    assert client_ask(failed) == GENERIC_ASK
    lines, attention, held = triage([failed])
    assert attention == [] and [f.reason for f in held] == [AMBIGUOUS_HOLD]


def test_no_client_facing_text_carries_a_reason_sentence(tmp_path):
    """Decision 190. The letter and the client's README of a return with a
    parked file of every kind - each from a subfolder the client named
    after a refusal - hold none of a reason's own words, none of the
    router's and the filer's parking sentences, and not the subfolder
    label: only the fixed asks reach a client."""
    import string

    from tests.conftest import seed_index
    from tests.test_review import parked_row
    from tracker.api import CAME_FROM_SUBFOLDER
    from tracker.filer import CONTESTED_BETWEEN_RETURNS, refresh_household_readme
    from tracker.layout import household_of
    from tracker.records import RULE_REQUIRED, WHERE_TITLE, Evidence
    from tracker.scaffold import README_NAME, scaffold_engagement

    folder = engagement(tmp_path, DROPPED, name="Every Kind TY2025")
    scaffold_engagement(folder)
    record = {"A01": (Evidence(RULE_REQUIRED, "W-2", WHERE_TITLE, 1),)}
    rows = [replace(parked_row(f"{n:02d} {r.code}.pdf", record, reason=_filled(r, "x")),
                    subfolder="not allowed")
            for n, r in enumerate(reasons.ALL)]
    seed_index(folder, rows)
    letter = draft_reminder(folder).body
    refresh_household_readme(household_of(folder))
    readme = (inbox_of(folder) / README_NAME).read_text(encoding="utf-8")

    asks = [GENERIC_ASK, *(r.ask for r in reasons.ALL if r.ask)]
    templates = [r.template for r in reasons.ALL] + [
        reasons.UNMATCHED, reasons.AMBIGUOUS, reasons.OCR_ONLY, reasons.NO_REQUEST_ACCEPTS,
        CONTESTED_BETWEEN_RETURNS, CAME_FROM_SUBFOLDER]
    for template in templates:
        for literal, *_ in string.Formatter().parse(template):
            words = literal.strip(" ;:()'.-")
            if len(words) < 12 or any(words in ask for ask in asks):
                continue
            assert words not in letter, words
            assert words not in readme, words
