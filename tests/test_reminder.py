"""Tests for tracker/reminder.py — a draft, and only what the client owes.

Three rules run through all of this: the email never asks for something we
already have (or already excused), it never quotes our internal validation
vocabulary back at a client, and (decision 115) it never guesses whose
court an ambiguous request is in - one such request holds the whole draft
for a person, and nothing that reads like a sendable email is written.
"""

import datetime as dt
import os
import subprocess
import sys
from pathlib import Path

import pytest

from tracker import ledger, reasons
from tracker.manifest import (
    EXPECTED_PATTERN,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
)
from tracker.reminder import (
    AMBIGUOUS_HOLD,
    CHANGED_ADDED,
    CHANGED_HEADING,
    CHANGED_REMOVED,
    DRAFT_BANNER,
    DRAFT_FILENAME,
    EXTENSION_ASK,
    HELD_BACK_HEADING,
    HELD_LINE,
    HELD_REFUSAL,
    NEW_DRAFT_FILENAME,
    PARTIAL_ASK,
    SECTION_FAILED,
    SECTION_MISSING,
    SECTION_ORDER,
    SECTION_PARTIAL,
    SUBJECT_COMPLETE,
    SUBJECT_NEEDED,
    ReminderError,
    ReminderHeldError,
    client_ask,
    count_needs_review,
    draft_reminder,
    is_unedited,
    triage,
    write_draft,
)
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.scanner import OVERRIDE_NOTE, PARTIAL_NOTE, SYNCING_NOTE


def item(identifier, document, status, **kwargs):
    return RequestItem(
        identifier=identifier, document=document, status=status, **kwargs
    )


SCANNED = [
    item("A01", "W-2 Wage Statements", Status.MISSING,
         period="TY2025", expected_count=2),
    item("A02", "Bank Statements", Status.PARTIAL,
         period="TY2025", expected_count=3, file_count=2),
    item("A03", "2024 Form 1040 Tax Return", Status.FAILED, period="TY2024",
         validation_notes="prior.pdf: " + reasons.PASSWORD_PROTECTED.format()),
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


def engagement(tmp_path, items=SCANNED, name="Smith TY2025"):
    """A request list in the record, with the record carrying these statuses.

    The list holds the person's eleven columns and nothing else, so the
    statuses are recorded the way a scan records them: one ``scanned``
    event through the store, under the lock.
    """
    from tests.conftest import make_engagement, seed_statuses

    folder = make_engagement(tmp_path / name, items, scaffold=False)
    updates = {
        i.identifier: StatusUpdate(
            status=i.status,
            file_count=i.file_count or 0,
            received_date=i.received_date,
            validation_notes=i.validation_notes,
        )
        for i in items if i.status
    }
    if updates:
        seed_statuses(folder, updates)
    return folder


# ------------------------------------------------------------- what we ask ----


def test_only_outstanding_rows_become_asks():
    lines, _, _, held = triage(SCANNED)
    assert [line.item.identifier for line in lines] == ["A01", "A02"]
    assert [line.section for line in lines] == [SECTION_MISSING, SECTION_PARTIAL]
    # A03 arrived and the rules refused it: a person's call, not the client's ask.
    assert [flag.item.identifier for flag in held] == ["A03"]


def test_received_and_pending_sync_are_never_asked_for():
    lines, _, _, _ = triage(SCANNED)
    asked = {line.item.identifier for line in lines}
    assert "A04" not in asked, "Received must not be re-requested"
    assert "A07" not in asked, "Pending Sync is in; the cloud is just slow"


def test_overrides_are_never_asked_for():
    """Not Applicable does not apply this year; Accepted was judged good
    enough by a person."""
    lines, attention, gaps, held = triage(SCANNED)
    everything = {f.item.identifier for f in attention + gaps + held}
    everything |= {line.item.identifier for line in lines}
    assert "A05" not in everything
    assert "A06" not in everything


# --------------------------------------------------------- how we phrase it ----


def test_partial_says_how_many_are_left():
    assert client_ask(SCANNED[1]) == PARTIAL_ASK.format(have=2, expected=3, missing=1)


@pytest.mark.parametrize("note, expected_fragment", [
    ("x.pdf: " + reasons.PASSWORD_PROTECTED.format(), reasons.PASSWORD_PROTECTED.client_ask),
    ("x.gdoc: " + reasons.GOOGLE_STUB.format(extension="gdoc"), reasons.GOOGLE_STUB.client_ask),
    ("x.pdf: " + reasons.TOO_SMALL.format(size_kb=0.1, minimum=5), reasons.TOO_SMALL.client_ask),
    ("x.zip: " + reasons.EXTENSION_NOT_ALLOWED.format(extension="zip", allowed="pdf"),
     reasons.EXTENSION_NOT_ALLOWED.client_ask),
    ("x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'W-2'"), reasons.WRONG_DOCUMENT.client_ask),
    ("x.pdf: " + reasons.WRONG_PERIOD.format(pattern="2025"), reasons.WRONG_PERIOD.client_ask),
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
                 validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format())]
    lines, attention, _, held = triage(rows)
    assert lines == [] and held == []
    assert [f.item.identifier for f in attention] == ["B01"]
    assert reasons.FIRM_WAITING in attention[0].reason


def test_a_missing_request_folder_is_our_problem_not_the_clients():
    rows = [item("B02", "Payroll Reports", Status.MISSING,
                 validation_notes=reasons.NO_REQUEST_FOLDER.format())]
    lines, _, gaps, _ = triage(rows)
    assert lines == [], "we cannot claim a document never arrived with nowhere to put it"
    assert [f.item.identifier for f in gaps] == ["B02"]


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
            received="2026-02-01", original_name=name, size_kb=0.1, digest=name,
            identifier="", prepared_location=f"{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}/{name}",
            pbc_location=f"pbc/{name}", decision=decision, reason="unrecognized",
        )

    seed_index(folder, [
        row("irs-notice.pdf", NOT_REQUESTED), row("scan0012.pdf", NEEDS_REVIEW),
    ])
    assert count_needs_review(folder) == 2
    assert draft_reminder(folder).needs_review_files == 2


# ----------------------------------------------------------------- drafting ----


def test_draft_greets_signs_and_counts(tmp_path):
    draft = draft_reminder(
        engagement(tmp_path),
        client_name="Dana Smith",
        share_link="https://drive.example/abc",
        due_date=dt.date(2026, 3, 15),
        sender="Jason Park",
        firm="J Park & Associates, CPA",
    )
    assert draft.body.startswith("Hi Dana Smith,")
    # A06 is Accepted: signed off, so it is in (the one count, decision 38).
    assert "2 of 6 items are in" in draft.body
    assert "https://drive.example/abc" in draft.body
    assert "March 15, 2026" in draft.body
    assert draft.body.rstrip().endswith("J Park & Associates, CPA")
    # A03 holds the draft rather than being asked for; the subject counts the asks.
    assert draft.subject == SUBJECT_NEEDED.format(engagement="Smith TY2025", n=2)
    assert draft.total_requests == 6 and draft.received_requests == 2


def test_draft_with_nothing_outstanding_says_so(tmp_path):
    rows = [item("A01", "W-2", Status.RECEIVED, file_count=1),
            item("A02", "Donations", Status.MISSING, manual_override=Override.NOT_APPLICABLE)]
    draft = draft_reminder(engagement(tmp_path, rows), client_name="Dana")
    assert draft.has_outstanding is False
    assert "we have everything" in draft.subject
    assert "Good news" in draft.body


def test_engagement_name_defaults_to_the_folder_and_can_be_overridden(tmp_path):
    folder = engagement(tmp_path)
    assert draft_reminder(folder).engagement == "Smith TY2025"
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
    assert f"Subject: {SUBJECT_NEEDED.format(engagement='Smith TY2025', n=2)}" in text


def test_written_draft_appends_firm_side_notes_below_the_email(tmp_path):
    rows = SENDABLE + [
        item("B01", "Receipts", Status.FAILED,
             validation_notes="scan.pdf: " + reasons.NO_TEXT_AFTER_OCR.format()),
        item("B02", "Payroll Reports", Status.MISSING,
             validation_notes=reasons.NO_REQUEST_FOLDER.format()),
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
               validation_notes=f"{PARTIAL_NOTE.format(count=1, expected=2)}; scan.pdf: " + reasons.NO_TEXT_LAYER.format())
    lines, attention, _, held = triage([row])
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
    draft = draft_reminder(folder)          # nothing passed in
    assert "Hi Dana Lee," in draft.body
    assert "https://drive.example/abc" in draft.body
    assert "April 15, 2026" in draft.body
    assert draft.body.rstrip().endswith("Jason Park\nJ Park & Associates, CPA")
    # A one-off override still wins, for the CLI's flags.
    assert "Hi Sam," in draft_reminder(folder, client_name="Sam").body


def test_an_ocr_failure_is_the_firms_to_retry_not_the_clients_to_resend():
    from tracker import reasons

    assert reasons.OCR_FAILED in reasons.FIRM_SIDE
    note = "scan.pdf: " + reasons.OCR_FAILED.format(error="TesseractError: timeout")
    assert reasons.find(note) is reasons.OCR_FAILED


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
             validation_notes="1099.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'")),
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
             validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format()),
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
                                    + reasons.PASSWORD_PROTECTED.format())
    plain = item("A03", "Brokerage Statements", Status.PARTIAL, expected_count=2, file_count=1,
                 validation_notes=PARTIAL_NOTE.format(count=1, expected=2))
    lines, attention, _, held = triage([refused, plain])
    assert [line.item.identifier for line in lines] == ["A03"]
    assert lines[0].ask == PARTIAL_ASK.format(have=1, expected=2, missing=1)
    assert attention == []
    assert [flag.item.identifier for flag in held] == ["A02"]
    assert reasons.PASSWORD_PROTECTED.client_ask in held[0].reason


def test_a_missing_row_with_a_firm_side_marker_is_held_back_not_asked():
    """Decision 109's rule, stated once here: a firm-side marker on any
    outstanding status is the firm's, Missing included."""
    row = item("D01", "Charitable Donations", Status.MISSING,
               validation_notes="receipts.pdf: " + reasons.VANISHED.format(error="moved"))
    lines, attention, _, held = triage([row])
    assert lines == [] and held == []
    assert [flag.item.identifier for flag in attention] == ["D01"]
    assert attention[0].reason == reasons.VANISHED.firm_side_note


def test_a_failed_row_with_no_recognised_reason_is_held_not_asked_generically():
    """The one guess the drafter made - "please send it again" for a failure
    it could not name - is gone: it is held, with no reason in brackets."""
    row = item("A01", "Doc", Status.FAILED, validation_notes="x.pdf: something nobody predicted")
    lines, attention, _, held = triage([row])
    assert lines == [] and attention == []
    assert [flag.item.identifier for flag in held] == ["A01"]
    assert held[0].reason == AMBIGUOUS_HOLD
    assert reasons.GENERIC_ASK not in held[0].reason


def test_the_held_refusal_names_every_held_row_and_writes_nothing(tmp_path):
    folder = _held_engagement(tmp_path, [
        item("A01", "W-2 Wage Statements", Status.MISSING),
        item("C01", "Mortgage Interest", Status.FAILED,
             validation_notes="x.pdf: " + reasons.WRONG_PERIOD.format(pattern="2025")),
        item("D01", "Donations", Status.FAILED,
             validation_notes="y.pdf: " + reasons.TOO_SMALL.format(size_kb=0.1, minimum=5)),
    ])
    draft = draft_reminder(folder)
    with pytest.raises(ReminderHeldError) as caught:
        write_draft(draft, engagement_dir=folder, preserve_edits=True)
    said = str(caught.value)
    assert said == HELD_REFUSAL.format(n=2, listed=f"{draft.held[0].item.label}, {draft.held[1].item.label}")
    assert "C01" in said and "D01" in said and "A01" not in said
    assert list(folder.glob("reminder-draft*")) == []
    # A hold's bracketed reason is in the row's own terms, as an ask would be.
    _, _, _, [xlsx] = triage([item("E01", "Sheet", Status.FAILED, allowed_extensions=("xlsx",),
                                   validation_notes="x.zip: " + reasons.EXTENSION_NOT_ALLOWED.format(
                                       extension="zip", allowed="xlsx"))])
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
    USE IT": every Failed row is either the firm's or held."""
    assert SECTION_FAILED not in SECTION_ORDER
    every_failed = [
        item(f"F{n:02d}", "Doc", Status.FAILED, validation_notes="x.pdf: " + reason.marker)
        for n, reason in enumerate(reasons.ALL) if reason is not reasons.NO_REQUEST_FOLDER
    ] + [item("F99", "Doc", Status.FAILED, validation_notes="x.pdf: nobody predicted this")]
    lines, attention, _, held = triage(every_failed)
    assert lines == []
    assert {f.item.identifier for f in attention} | {f.item.identifier for f in held} == {
        i.identifier for i in every_failed
    }
    folder = engagement(tmp_path, SENDABLE + [
        item("B01", "Receipts", Status.FAILED,
             validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format()),
    ])
    text = write_draft(draft_reminder(folder), engagement_dir=folder).read_text(encoding="utf-8")
    assert SECTION_FAILED not in text

