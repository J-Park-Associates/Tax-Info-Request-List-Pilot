"""Tests for tracker/reminder.py — a draft, and only what the client owes.

Two rules run through all of this: the email never asks for something we
already have (or already excused), and it never quotes our internal
validation vocabulary back at a client.
"""

import datetime as dt

import pytest

from tracker import reasons
from tracker.manifest import (
    EXPECTED_PATTERN,
    Override,
    RequestItem,
    Status,
    StatusUpdate,
    create_template,
    write_statuses,
)
from tracker.scanner import OVERRIDE_NOTE, PARTIAL_NOTE, SYNCING_NOTE
from tracker.reminder import (
    DRAFT_BANNER,
    PARTIAL_ASK,
    SUBJECT_NEEDED,
    DRAFT_FILENAME,
    GENERIC_ASK,
    SECTION_FAILED,
    SECTION_MISSING,
    SECTION_PARTIAL,
    ReminderError,
    client_ask,
    count_needs_review,
    draft_reminder,
    triage,
    write_draft,
)
from tracker.scaffold import MANIFEST_FILENAME, PREPARED_DIR_NAME, REVIEW_DIR_NAME


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
    item("A05", "Charitable Donations", Status.MISSING, manual_override=Override.WAIVED),
    item("A06", "Brokerage Statements", Status.FAILED, manual_override=Override.ACCEPTED,
         validation_notes=f"{OVERRIDE_NOTE.format(override=Override.ACCEPTED)}; 1099.pdf: {reasons.WRONG_PERIOD.marker}"),
    item("A07", "K-1 Statements", Status.PENDING_SYNC, file_count=0,
         validation_notes=SYNCING_NOTE.format(n=1)),
]


def engagement(tmp_path, items=SCANNED, name="Smith TY2025"):
    """A manifest on disk carrying the scanner state these items describe.

    create_template writes the accountant's columns only, so the scanner
    columns are written back exactly as a real scan would write them.
    """
    folder = tmp_path / name
    folder.mkdir()
    manifest = create_template(folder / MANIFEST_FILENAME, items)
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
        write_statuses(manifest, updates)
    return folder


# ------------------------------------------------------------- what we ask ----


def test_only_outstanding_rows_become_asks():
    lines, _, _ = triage(SCANNED)
    assert [line.item.identifier for line in lines] == ["A01", "A02", "A03"]


def test_received_and_pending_sync_are_never_asked_for():
    lines, _, _ = triage(SCANNED)
    asked = {line.item.identifier for line in lines}
    assert "A04" not in asked, "Received must not be re-requested"
    assert "A07" not in asked, "Pending Sync is in; the cloud is just slow"


def test_overrides_are_never_asked_for():
    """Waived is no longer needed; Accepted was judged good enough by a person."""
    lines, attention, gaps = triage(SCANNED)
    everything = {f.item.identifier for f in attention + gaps}
    everything |= {line.item.identifier for line in lines}
    assert "A05" not in everything
    assert "A06" not in everything


def test_sections_are_ordered_missing_partial_failed():
    lines, _, _ = triage(SCANNED)
    assert [line.section for line in lines] == [
        SECTION_MISSING, SECTION_PARTIAL, SECTION_FAILED
    ]


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


def test_unrecognized_failure_falls_back_to_the_generic_ask():
    ask = client_ask(item("A01", "Doc", Status.FAILED,
                          validation_notes="x.pdf: something nobody predicted"))
    assert ask == GENERIC_ASK


def test_internal_vocabulary_never_reaches_the_client(tmp_path):
    draft = draft_reminder(engagement(tmp_path), client_name="Dana")
    body = draft.body.lower()
    for leak in ("keyword", "kb minimum", "validation", "prepared/",
                 "manifest", "tier", "pattern:", "scaffold"):
        assert leak not in body, f"internal term {leak!r} leaked into the email"


def test_multi_file_requests_say_how_many_are_expected(tmp_path):
    draft = draft_reminder(engagement(tmp_path))
    line = next(l for l in draft.lines if l.item.identifier == "A01")
    assert line.ask == EXPECTED_PATTERN.format(n=2)


# ------------------------------------------------- what we hold back, and why ----


def test_rows_we_have_not_read_go_to_the_accountant_not_the_client():
    rows = [item("B01", "Receipts", Status.FAILED,
                 validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format())]
    lines, attention, _ = triage(rows)
    assert lines == []
    assert [f.item.identifier for f in attention] == ["B01"]
    assert reasons.FIRM_WAITING in attention[0].reason


def test_a_missing_request_folder_is_our_problem_not_the_clients():
    rows = [item("B02", "Payroll Reports", Status.MISSING,
                 validation_notes=reasons.NO_REQUEST_FOLDER.format())]
    lines, _, gaps = triage(rows)
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
    assert draft.subject == SUBJECT_NEEDED.format(engagement="Smith TY2025", n=3)
    assert draft.total_requests == 6 and draft.received_requests == 2


def test_draft_with_nothing_outstanding_says_so(tmp_path):
    rows = [item("A01", "W-2", Status.RECEIVED, file_count=1),
            item("A02", "Donations", Status.MISSING, manual_override=Override.WAIVED)]
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


def test_missing_manifest_fails_loudly(tmp_path):
    with pytest.raises(ReminderError, match=MANIFEST_FILENAME):
        draft_reminder(tmp_path / "nothing-here")


def test_an_unscanned_manifest_will_not_be_drafted_from(tmp_path):
    """Asking from unscanned rows would re-request what the client already sent."""
    rows = [item("A01", "W-2", ""), item("A02", "Bank Statements", "")]
    with pytest.raises(ReminderError, match="scanner"):
        draft_reminder(engagement(tmp_path, rows))


# ------------------------------------------------------------------ writing ----


def test_write_draft_marks_it_as_a_draft(tmp_path):
    folder = engagement(tmp_path)
    path = write_draft(draft_reminder(folder), engagement_dir=folder)

    assert path == folder / DRAFT_FILENAME
    text = path.read_text(encoding="utf-8")
    assert text.startswith(DRAFT_BANNER)
    assert f"Subject: {SUBJECT_NEEDED.format(engagement='Smith TY2025', n=3)}" in text


def test_written_draft_appends_firm_side_notes_below_the_email(tmp_path):
    rows = SCANNED + [
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
    email, _, firm_side = text.partition("NOT ASKED FOR")
    assert "B01" not in email and "B02" not in email
    assert "B01" in firm_side and "B02" in firm_side
    assert REVIEW_DIR_NAME in firm_side


def test_write_draft_needs_somewhere_to_write(tmp_path):
    with pytest.raises(ReminderError, match="path or engagement_dir"):
        write_draft(draft_reminder(engagement(tmp_path)))


def test_a_partial_row_we_have_not_finished_reading_is_ours_not_the_clients():
    # One of two arrived and was read; the other is an un-OCR'd scan. The
    # client may well have sent both, so "1 of 2 received" is not known yet.
    row = item("A01", "W-2 Wage Statements", Status.PARTIAL, expected_count=2,
               file_count=1,
               validation_notes=f"{PARTIAL_NOTE.format(count=1, expected=2)}; scan.pdf: " + reasons.NO_TEXT_LAYER.format())
    lines, attention, _ = triage([row])
    assert lines == []
    assert [flag.item.identifier for flag in attention] == ["A01"]
    assert reasons.FIRM_WAITING_PARTIAL in attention[0].reason


def test_statuses_deferred_by_a_locked_excel_still_count(tmp_path):
    # Friday: Excel open, the scan saw A01 arrive but could not write it.
    # Saturday: the draft must not ask for A01.
    from tracker.manifest import _save_pending

    folder = engagement(tmp_path, [
        item("A01", "W-2 Wage Statements", Status.MISSING),
        item("A02", "Bank Statements", Status.MISSING),
    ])
    _save_pending(folder / MANIFEST_FILENAME, {
        "A01": StatusUpdate(status=Status.RECEIVED, file_count=1, received_date=dt.date(2026, 2, 1)),
    })
    draft = draft_reminder(folder)
    assert [line.item.identifier for line in draft.lines] == ["A02"]
    assert draft.received_requests == 1
    assert draft.pending_statuses == 1
    written = write_draft(draft, engagement_dir=folder).read_text(encoding="utf-8")
    assert "1 status update(s) are still waiting" in written


def test_needs_review_count_ignores_junk_and_sees_nested_files(tmp_path):
    review = tmp_path / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    (review / "sub").mkdir(parents=True)
    (review / "desktop.ini").write_text("x")
    (review / "top.pdf").write_bytes(b"x" * 10)
    (review / "sub" / "nested.pdf").write_bytes(b"x" * 10)
    assert count_needs_review(tmp_path) == 2


def test_the_draft_reads_the_engagement_sheet_itself(tmp_path):
    from tracker.manifest import EngagementInfo, write_engagement_info

    folder = engagement(tmp_path)
    write_engagement_info(folder / MANIFEST_FILENAME, EngagementInfo(
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
