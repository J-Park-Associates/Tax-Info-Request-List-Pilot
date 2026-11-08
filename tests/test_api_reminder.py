"""Tests for tracker/api.py: the reminder card.

The reminder card the app shows for a return and the commands behind it (decision 118).

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
from pathlib import Path

import tracker.api as api
import tracker.screen_words as screen_words
from tests import api_driver
from tests.api_driver import HOUSEHOLD, _typed_as_a_string, chased_engagement, reminder_card, run
from tracker import ledger
from tracker.index import NEEDS_REVIEW
from tracker.layout import inbox_of
from tracker.manifest import Status, load_engagement_info
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.templates import default_tax_year

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ------------------------------------------------- the reminder card (d118) ----
# The app shows the week's draft, moves it up and down the ladder without
# touching the file, copies it and approves it. Nothing sends.


def test_the_reminder_command_reads_the_record_and_the_file_and_renders_on_demand(capsys, demo_root):
    """The card is the record's answer and the letter as it will read, at
    whatever rung the toggle stands on - and not one byte is written."""
    from tracker.reminder import DRAFT_FILENAME, STAGES, stage_named

    folder = chased_engagement(capsys, demo_root)
    card = reminder_card(capsys, folder)

    assert card["held"] == [] and card["editable"] is True
    assert card["last"] is None and card["approved"] is None
    assert card["asked"] == ["A01", "B01"]
    assert card["file"] == {"name": DRAFT_FILENAME, "exists": False, "edited": False,
                            "path": str(folder / DRAFT_FILENAME)}
    assert [s["number"] for s in card["stages"]] == [s.number for s in STAGES]
    assert card["stage"] == 4, "the Due Date has gone by, so the day gives the final notice"
    # The letter names the return as everything does since decision 125:
    # the household, the year and the return.
    label = f"{HOUSEHOLD} {default_tax_year()} Chase"
    assert card["subject"] == stage_named(4).subject.format(engagement=label, n=2)
    assert card["letter"]["greeting"] and card["letter"]["sections"]
    assert card["html"].startswith("<div") and "<style" not in card["html"]
    assert not (folder / DRAFT_FILENAME).exists(), "reading the card never drafts"

    # The toggle: the same recipients, another stage's words, still no file.
    milder = reminder_card(capsys, folder, stage=1)
    assert milder["stage"] == 1 and milder["asked"] == card["asked"]
    assert milder["subject"] == stage_named(1).subject.format(engagement=label, n=2)
    assert milder["letter"]["deadline"] == [], "stage one carries no deadline paragraph"
    assert not (folder / DRAFT_FILENAME).exists()

    # A stage that is not one of the four is refused by name.
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={"stage": 9})
    assert code == 1 and "stage 9" in payload["error"]


def test_the_letter_travels_as_a_shape_with_the_emphasis_already_decided(capsys, demo_root):
    """The page is built from data, never from markup, so the preview is the
    letter's own shape - and which run of the deadline paragraph is marked
    is Python's answer, not the renderer's."""
    folder = chased_engagement(capsys, demo_root)
    letter = reminder_card(capsys, folder, stage=4)["letter"]
    runs = letter["deadline"]
    assert "".join(part["text"] for part in runs)
    assert [part["kind"] for part in runs if part["kind"]] == ["target", "deadline_date",
                                                              "consequences"]
    assert all(part["bold"] for part in runs if part["kind"])
    assert [part["colour"] for part in runs] == [False] * len(runs), "stage four colours the whole paragraph"

    two = reminder_card(capsys, folder, stage=2)["letter"]["deadline"]
    marked = [part for part in two if part["colour"]]
    assert [part["kind"] for part in marked] == ["target"], "stage two marks the date alone"
    assert not any(part["bold"] for part in two)


def test_a_held_reminder_shows_no_letter_and_offers_no_action(capsys, demo_root):
    """Decision 115's rule on this surface: a held client's composed text
    would ask for the clean rows alone, and the card is something a person
    can copy from. The hold, the rows, the toggle - and nothing else."""
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.reminder import stage_for

    folder = chased_engagement(capsys, demo_root, name="Held")
    seed_statuses(folder, {"B01": StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"),
        note_codes=reasons.WRONG_DOCUMENT.code)})

    card = reminder_card(capsys, folder)
    assert [row["identifier"] for row in card["held"]] == ["B01"]
    assert card["held"][0]["document"] == "Bank Statements"
    assert (card["subject"], card["text"], card["html"], card["letter"]) == ("", "", "", {})
    assert card["editable"] is False
    assert card["stage"] == stage_for(load_engagement_info(folder).due, dt.date.today())
    # A stage asked for while held is ignored: there is nothing to re-stage.
    assert reminder_card(capsys, folder, stage=1)["stage"] == card["stage"]

    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": card["stage"], "fingerprint": card["fingerprint"]})
    assert code == 1 and "the reminder is held" in payload["error"]
    assert list(folder.glob("reminder-draft*")) == []


def test_a_letter_that_only_asks_about_a_program_is_offered_on_the_card(capsys, demo_root):
    """The re-check's S-N1 on this surface: every request is in and a
    program is parked. The card offers the letter that asks about it -
    editable, as the scheduler writes it - at no stage, and a stage asked
    for re-stages nothing, because a file that is not a document is no
    rung."""
    from tests.builders import seed_index, seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.records import IndexEntry
    from tracker.reminder import SECTION_FAILED, STAGE_4_CONSEQUENCES

    folder = chased_engagement(capsys, demo_root, name="Program")
    seed_statuses(folder, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1),
                           "B01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    seed_index(folder, [IndexEntry(
        received="2026-02-01", original_name="setup.exe", size_kb=0.1, digest="5" * 64,
        identifier="", prepared_location="", pbc_location="pbc/setup.exe",
        decision=NEEDS_REVIEW, reason=reasons.NOT_A_DOCUMENT.format(),
        code=reasons.NOT_A_DOCUMENT.code,
    )])

    for stage in (None, 4):
        card = reminder_card(capsys, folder, stage=stage)
        assert card["held"] == [] and card["editable"] is True
        assert card["asked"] == []
        assert STAGE_4_CONSEQUENCES not in card["text"]
        assert f"{SECTION_FAILED}\n  - setup.exe - " in card["text"]
        assert "still needed" not in card["subject"]


def test_the_card_shows_the_inbox_hold_in_the_apis_words_and_offers_no_approve(capsys, demo_root):
    """Decision 133 on this surface: a file still waiting in the household's
    inbox holds the card as a held row does (118 §9) - the hold line, no
    rows, a dead toggle, no letter and no approval - and every word of it is
    the API's; the renderer types none."""
    from tracker.reminder import INBOX_HELD_SUMMARY, INBOX_HOLD

    folder = chased_engagement(capsys, demo_root, name="Waiting")
    (inbox_of(folder) / "W-2 from the client.pdf").write_bytes(b"%PDF-1.4 not sorted yet")

    card = reminder_card(capsys, folder)
    assert card["held"] == [] and card["unsorted"] == 1
    # Which file holds it, by its own name (P134).
    assert card["unsorted_files"] == ["W-2 from the client.pdf"]
    assert (card["subject"], card["text"], card["html"], card["letter"]) == ("", "", "", {})
    assert card["editable"] is False

    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": card["stage"], "fingerprint": card["fingerprint"]})
    assert code == 1 and payload["error"] == INBOX_HOLD.format(n=1)
    assert list(folder.glob("reminder-draft*")) == []

    # The household card says the same hold beside the return.
    [one] = api.state(folder)["household"]["returns"]
    assert one["reminder"]["unsorted"] == 1

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["reminder"]["inbox_held_line"] == INBOX_HELD_SUMMARY
    renderer = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "app.js").read_text(
        encoding="utf-8")
    for word in (INBOX_HELD_SUMMARY, INBOX_HELD_SUMMARY.split("{")[0].strip(),
                 INBOX_HOLD.split("{")[0].strip()):
        assert not _typed_as_a_string(renderer, word), word
    assert "vocab.reminder.inbox_held_line" in renderer


def test_approve_writes_the_shown_text_records_the_event_and_sets_the_other_draft_aside(
        capsys, demo_root):
    """What you see is what you approve: the file carries the text the card
    showed, one event carries the stage and the fingerprint, and the draft
    standing beside it is renamed and never deleted."""
    from tracker.reminder import (
        DRAFT_FILENAME,
        NEW_DRAFT_FILENAME,
        SET_ASIDE_DRAFT_PATTERN,
        recorded_fingerprint,
    )

    folder = chased_engagement(capsys, demo_root, name="Approve")
    (folder / NEW_DRAFT_FILENAME).write_bytes(b"an older draft\r\n")
    before = len(list(folder.iterdir()))
    card = reminder_card(capsys, folder, stage=3)

    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 3, "fingerprint": card["fingerprint"]})
    assert code == 0, payload
    written = folder / DRAFT_FILENAME
    assert card["text"] in written.read_text(encoding="utf-8")
    assert card["subject"] in written.read_text(encoding="utf-8")

    [event] = [e for e in ledger.read_events(folder)
               if e[ledger.EVENT_KEY] == ledger.DRAFT_APPROVED]
    assert event["stage"] == 3
    assert event[ledger.FILE_KEY] == DRAFT_FILENAME
    assert event[ledger.FINGERPRINT_KEY] == recorded_fingerprint(written)
    assert event[ledger.ASKED_KEY] == ["A01", "B01"]

    assert payload["set_aside"] == SET_ASIDE_DRAFT_PATTERN.format(date=dt.date.today().isoformat())
    assert (folder / payload["set_aside"]).read_bytes() == b"an older draft\r\n"
    assert not (folder / NEW_DRAFT_FILENAME).exists()
    assert len(list(folder.iterdir())) == before + 1, "one draft written, one renamed, none deleted"
    assert payload["reminder"]["approved"] == {"date": dt.date.today().isoformat(), "stage": 3,
                                               "file": DRAFT_FILENAME}


def test_approve_refuses_a_stale_fingerprint(capsys, demo_root):
    """A panel the record has moved under is refused before a file is
    touched, the way a review card is refused by its row's version."""
    from tracker.reminder import DRAFT_FILENAME

    folder = chased_engagement(capsys, demo_root, name="Stale")
    card = reminder_card(capsys, folder, stage=2)
    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 2, "fingerprint": card["fingerprint"] + "x"})
    assert code == 1 and payload["error"] == screen_words.DRAFT_MOVED
    assert not (folder / DRAFT_FILENAME).exists()
    # The same click at another stage is a different text, and is refused too.
    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 4, "fingerprint": card["fingerprint"]})
    assert code == 1 and payload["error"] == screen_words.DRAFT_MOVED
    assert not (folder / DRAFT_FILENAME).exists()


def test_an_edited_file_is_approved_as_it_stands_and_the_toggle_is_disabled(capsys, demo_root):
    """Their words, not the machine's: the card shows what they wrote, the
    ladder has nothing to say about it, and approve writes nothing."""
    from tracker.reminder import DRAFT_FILENAME, EDITED_BY_HAND

    folder = chased_engagement(capsys, demo_root, name="Edited")
    card = reminder_card(capsys, folder, stage=2)
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": 2, "fingerprint": card["fingerprint"]})[0] == 0
    written = folder / DRAFT_FILENAME
    edited = written.read_bytes() + b"\r\nPS: ask about the rental.\r\n"
    written.write_bytes(edited)

    after = reminder_card(capsys, folder)
    assert after["file"]["edited"] is True and after["editable"] is False
    # Edited after the approval, so the approval lapsed (decision 190).
    assert after["approved"] is None and after["lapsed"] is True
    assert after["letter"] == {} and "ask about the rental" in after["text"]
    assert after["html"].startswith("<div") and "ask about the rental" in after["html"]
    assert EDITED_BY_HAND  # the sentence the card shows beside it, from the vocabulary
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": after["stage"], "fingerprint": after["fingerprint"]})[0] == 0
    assert written.read_bytes() == edited, "an edited draft is approved as it stands"
    again = reminder_card(capsys, folder)
    assert again["approved"] is not None and again["lapsed"] is False


def test_approve_never_sends(capsys, demo_root, monkeypatch):
    """The fourth standing rule, on the one command that writes a letter:
    no socket is opened, and the AST guard over the package still holds."""
    import socket

    from tracker.reminder import DRAFT_FILENAME

    folder = chased_engagement(capsys, demo_root, name="Quiet")
    card = reminder_card(capsys, folder, stage=1)

    def refuse(*args, **kwargs):
        raise AssertionError("the reminder path opened a socket")

    monkeypatch.setattr(socket, "socket", refuse)
    monkeypatch.setattr(socket, "create_connection", refuse)
    code, payload = run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": 1, "fingerprint": card["fingerprint"]})
    assert code == 0, payload
    assert (folder / DRAFT_FILENAME).exists()


def test_an_edited_drafts_footer_is_neither_shown_nor_copied(capsys, demo_root):
    """The staff footer is the machine's note to the person, as the header is.

    A draft written with a row that is ours rather than the client's, and
    with a file nobody has identified yet, ends with sentences naming both.
    They are fenced off by a rule of their own and have never been part of
    the email - so the card must not show them and Copy for Outlook must
    not put them one paste from a client.
    """
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.reminder import (
        DRAFT_FILENAME,
        FOOTER_RULE,
        REVIEW_ADVICE,
        REVIEW_WARNING,
        SIDE_US,
    )

    us_heading = f"{SIDE_US.label.upper()} - {SIDE_US.sentence}"

    folder = chased_engagement(capsys, demo_root, name="Footer")
    # B01 is ours to fix, not the client's to resend, so the draft reports
    # it under the footer instead of asking for it...
    seed_statuses(folder, {"B01": StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="scan.pdf: " + reasons.NO_TEXT_LAYER.format(),
        note_codes=reasons.NO_TEXT_LAYER.code)})
    # ...and a file nobody has identified yet puts the warning there too.
    review = folder / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    review.mkdir(parents=True, exist_ok=True)
    (review / "scan0012.pdf").write_bytes(b"x" * 4096)

    card = reminder_card(capsys, folder)
    assert run(capsys, "approve", api.ENGAGEMENT_FLAG, str(folder),
               stdin={"stage": card["stage"], "fingerprint": card["fingerprint"]})[0] == 0
    written = folder / DRAFT_FILENAME
    on_disk = written.read_text(encoding="utf-8")
    # The warning opens with its count, so the sentence after it is what a
    # test may look for without retyping a word of it.
    warning = REVIEW_WARNING.split("}", 1)[1]
    assert us_heading in on_disk and warning in on_disk

    # A person adds a line to the letter, which is above the footer's rule.
    edited = on_disk.replace(f"\n{FOOTER_RULE}",
                             f"PS: ask about the rental.\n\n{FOOTER_RULE}", 1)
    written.write_text(edited, encoding="utf-8", newline="\r\n")
    kept = written.read_bytes()

    after = reminder_card(capsys, folder)
    assert after["file"]["edited"] is True
    assert "PS: ask about the rental." in after["text"]
    assert "PS: ask about the rental." in after["html"]
    for firm_side in (us_heading, warning, REVIEW_ADVICE, FOOTER_RULE):
        assert firm_side not in after["text"], firm_side
        assert firm_side not in after["html"], firm_side
    assert written.read_bytes() == kept, "reading the card never touches the file"
