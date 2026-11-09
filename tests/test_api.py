"""Tests for tracker/api.py — the JSON command layer the desktop app calls.

The contract under test: every command answers with one JSON object and an
exit code, an error is a JSON object too (never a traceback on stdout), and
the create path refuses a bad request list with a sentence a person can act
on. The clients root is a temp folder recorded through settings, the way
the app records it, so no test touches a real one.

What stays here is the contract itself, the vocabulary, a click that walks nothing
(decision 192), replies that never go quiet (decision 193), one spawn per click
(decision 194), Title Case for every drawn word, the engine's commands (P276) and the
side panel's and menu's words. The rest of the file was split by its section banners
into ``tests/test_api_returns.py``, ``test_api_review.py``, ``test_api_editor.py``,
``test_api_root.py``, ``test_api_household.py``, ``test_api_reminder.py`` and
``test_api_firm.py`` (SPEC-architecture-p5 P5.14, E-3), so each family runs as its own
process; what more than one of them reads is ``tests/api_driver.py``'s.
"""

import datetime as dt
import json
import os
from pathlib import Path

import pytest

import tracker.api as api
import tracker.screen_words as screen_words
from tests import api_driver
from tests.api_driver import (
    _AGED_AT,
    HOUSEHOLD,
    _a_practice_for_the_firm_view,
    _a_renamed_household,
    _aged,
    _cached_firm,
    _firm_whole,
    _issuer_return,
    _on_the_office_computer,
    _raw,
    _rows_of,
    _rows_read,
    _typed_as_a_string,
    chased_engagement,
    one_reply,
    payload_of_state,
    reminder_card,
    run,
    said_by_class,
    sample_engagement,
    scan,
    two_households,
    waiting_document,
    where,
)
from tests.builders import TEST_CLIENT, make_engagement
from tests.node_harness import APP_SCRIPTS, renderer_text
from tests.samples import PRIOR_YEAR, text_pdf
from tests.source_pins import py_function
from tests.wording import title_case
from tracker import firm_view, household_edit, layout, ledger, manifest, reasons, reminder, request_edit, store
from tracker.bounds import MAX_EXPECTED_COUNT, MAX_SIZE_KB
from tracker.households import load_household_info
from tracker.index import FILED, NEEDS_REVIEW
from tracker.layout import PRIVATE_TREE, inbox_of
from tracker.locking import lock_line, this_host
from tracker.manifest import ManifestError, Status
from tracker.records import ENGAGEMENT_LABELS
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.scheduling import TASK_NAME
from tracker.status_page import STATUS_PAGE_FILENAME
from tracker.templates import BASE_YEAR

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ------------------------------------------------------------- the contract ----


def test_unknown_command_is_a_json_error(capsys):
    code, payload = run(capsys, "frobnicate")
    assert code == 1
    assert payload["error"].startswith("usage:")


def test_a_request_list_problem_is_a_json_error_not_a_traceback(capsys, demo_root):
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(demo_root / "nowhere"))
    assert code == 1
    assert "not an engagement" in payload["error"]


def test_the_engagement_flag_needs_a_folder_under_the_root(capsys, demo_root, tmp_path):
    hint = f"Pick an engagement first ({api.ENGAGEMENT_FLAG} <folder>)"
    assert run(capsys, "state")[1]["error"] == hint
    assert run(capsys, "state", api.ENGAGEMENT_FLAG)[1]["error"] == hint        # was an IndexError
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, "  ")[1]["error"] == hint
    elsewhere = tmp_path / "Elsewhere" / "Smith"
    elsewhere.mkdir(parents=True)
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(elsewhere))
    assert code == 1 and "not under the clients root" in payload["error"]


def test_an_unplugged_clients_root_is_not_a_licence_to_read_anywhere(capsys, demo_root, tmp_path):
    import shutil

    elsewhere = tmp_path / "Elsewhere" / "Smith"
    elsewhere.mkdir(parents=True)
    shutil.rmtree(demo_root)                          # the drive is gone
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(elsewhere))
    assert code == 1 and "not under the clients root" in payload["error"]


def test_a_rollover_takes_its_prior_only_from_under_the_root(capsys, demo_root, tmp_path):
    from tracker.templates import template_items

    elsewhere = make_engagement(tmp_path / "Elsewhere" / "Smith TY2025",
                                template_items("1040", year=2025), scaffold=False)
    code, payload = run(capsys, "rollover", stdin={"prior": str(elsewhere)})
    assert code == 1 and "not under the clients root" in payload["error"]


def test_a_journal_planted_in_the_client_tree_is_never_a_prior(capsys, demo_root):
    # Decision 176: the rollover's prior was checked only for being under
    # the root, and the client tree is under the root. A client can drop
    # any file, so a _ledger.jsonl in the inbox rolled into a return built
    # from the client's own rows and people, and the household's inbox
    # stopped being sorted (two open years).
    from tracker.templates import template_items

    run(capsys, "create", stdin={"return_name": "1040 - Smith", "form": "1040",
                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    planted = make_engagement(inbox_of(where(demo_root, "1040 - Smith")) / "x",
                              template_items("1040", year=2025), scaffold=False)
    before = sorted(p for p in (demo_root / PRIVATE_TREE).rglob("*"))
    for prior in (planted, planted.parent, where(demo_root, "1040 - Smith").parent.parent):
        code, payload = run(capsys, "rollover", stdin={"prior": str(prior), "year": 2026})
        assert code == 1
        assert payload["error"] == layout.NOT_A_RETURN.format(name=prior.name, tree=PRIVATE_TREE)
    assert sorted(p for p in (demo_root / PRIVATE_TREE).rglob("*")) == before


def test_a_household_path_must_be_a_household_of_the_private_tree(capsys, demo_root):
    run(capsys, "create", stdin={"return_name": "1040 - Smith", "form": "1040",
                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    engagement = where(demo_root, "1040 - Smith")
    for given in (engagement, engagement.parent, inbox_of(engagement).parent):
        code, payload = run(capsys, "create", stdin={
            "household_path": str(given), "return_name": "Evil", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]})
        assert code == 1
        assert payload["error"] == layout.NOT_A_HOUSEHOLD.format(name=given.name,
                                                              tree=PRIVATE_TREE)
    assert not list((demo_root / PRIVATE_TREE).rglob("Evil"))
    assert not (demo_root / "Clients" / engagement.name).exists()


def test_a_return_named_through_dots_is_the_return_it_resolves_to(capsys, demo_root):
    # Decision 176: the path was checked resolved and used as sent, and
    # every layout helper reads position off the text - so "<return>/2031/.."
    # passed as a return and edit-household wrote a household_changed line
    # into the return's own journal, taking the return for its household.
    run(capsys, "create", stdin={"return_name": "1040 - Smith", "form": "1040",
                                 "items": [{"identifier": "A01", "document": "W-2"}]})
    engagement = where(demo_root, "1040 - Smith")
    dotted = f"{engagement}{os.sep}2031{os.sep}.."
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, dotted)
    assert code == 0, payload
    assert payload["paths"]["engagement"] == str(engagement)
    journal = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, dotted,
                        stdin={"contact": "Mallory"})
    assert code == 0, payload
    assert ledger.path_for(engagement).read_bytes() == journal
    assert load_household_info(engagement.parent.parent).contact == "Mallory"


def test_templates_lists_every_form_with_its_checklist(capsys):
    code, payload = run(capsys, "templates")
    assert code == 0
    assert {f["id"] for f in payload["forms"]} == set(payload["templates"])
    for form, rows in payload["templates"].items():
        identifiers = [r["identifier"] for r in rows]
        assert len(identifiers) == len(set(identifiers)), form
        assert any(r["core"] for r in rows), form


# ------------------------------------------------------------- vocabulary ----


def test_the_renderer_gets_its_vocabulary_from_the_api(capsys, demo_root):
    from tracker import STANDING_RULES
    from tracker.index import DUPLICATE, FILE_MOVED, FILED, NEEDS_REVIEW, NOT_REQUESTED
    from tracker.manifest import COLUMN_HELP, COLUMNS, Override, Status
    from tracker.records import DATE_FIELDS, ENGAGEMENT_EDITABLE, ENGAGEMENT_FIELDS
    from tracker.runner import DRAFT_WEEKDAY, WEEKDAY_NAMES
    from tracker.scheduling import DEFAULT_REPEAT_MINUTES, DEFAULT_START

    code, payload = run(capsys, "list")
    vocab = payload["vocab"]
    assert [s["value"] for s in vocab["statuses"]] == list(Status.ALL)
    assert {s["key"] for s in vocab["statuses"]} == {api._slug(s) for s in Status.ALL}
    assert vocab["overrides"] == {"accepted": Override.ACCEPTED,
                                  "not_applicable": Override.NOT_APPLICABLE}
    assert vocab["decisions"] == {"filed": FILED, "needs_review": NEEDS_REVIEW,
                                  "duplicate": DUPLICATE, "dismissed": NOT_REQUESTED,
                                  "file_moved": FILE_MOVED}
    assert vocab["review_labels"] == {
        "dismiss": screen_words.DISMISS_LABEL, "dismiss_note": screen_words.DISMISS_NOTE_HINT,
        "came_from": screen_words.CAME_FROM_SUBFOLDER,
        "dismissed_heading": screen_words.DISMISSED_HEADING, "file": screen_words.FILE_LABEL,
        "file_anyway": screen_words.FILE_ANYWAY_LABEL,
        "unfile": screen_words.UNFILE_LABEL, "unfile_note": screen_words.UNFILE_NOTE_HINT,
        "mark_missing": screen_words.MARK_MISSING_LABEL, "also_answers": screen_words.ALSO_ANSWERS_LABEL,
        "filed_heading": screen_words.FILED_HEADING,
        "suggested": screen_words.SUGGESTED_HEADING, "other_requests": screen_words.OTHER_REQUESTS_HEADING,
        "restore": screen_words.RESTORE_LABEL, "keep": screen_words.KEEP_LABEL,
        "send_to_review": screen_words.SEND_TO_REVIEW_LABEL,
        "moved_heading": screen_words.MOVED_HEADING, "moved_summary": screen_words.MOVED_SUMMARY,
        "moved_nowhere": screen_words.MOVED_NOWHERE,
        "accept": screen_words.ACCEPT_LABEL, "skip": screen_words.SKIP_LABEL,
        "open_in_list": screen_words.OPEN_IN_LIST_LABEL,
        "card_mode": screen_words.CARD_MODE_LABEL, "list_mode": screen_words.LIST_MODE_LABEL,
        "card_position": screen_words.CARD_POSITION,
        "hand_over": screen_words.HAND_OVER_LABEL,
        "hand_over_return": screen_words.HAND_OVER_RETURN_LABEL,
        "hand_over_request": screen_words.HAND_OVER_REQUEST_LABEL,
        "handed_over": screen_words.HANDED_OVER_LINE,
        "file_where_it_waits": screen_words.FILE_WHERE_IT_WAITS_LABEL,
        "buckets": api.BUCKET_HEADINGS, "bucket_order": list(api.BUCKET_HEADINGS),
        "not_a_document": firm_view.BUCKET_NOT_A_DOCUMENT,
        "open_copy": screen_words.OPEN_COPY_LABEL, "true_type": screen_words.TRUE_TYPE,
        "keyword": screen_words.KEYWORD_LABEL, "keyword_help": screen_words.KEYWORD_HELP,
        "issuer_label": screen_words.ISSUER_LABEL, "issuer_help": screen_words.ISSUER_HELP,
        "issuer_add": screen_words.ISSUER_ADD_LABEL, "issuer_not_rescanned": screen_words.ISSUER_NOT_RESCANNED,
    }
    assert "carried_sheet" not in vocab
    # The editor's every word, and the request list's schema.
    assert vocab["columns"] == [{"key": f, "label": h, "help": COLUMN_HELP[f]} for h, f in COLUMNS]
    editor = vocab["editor"]
    assert editor["open"] == screen_words.EDITOR_OPEN_LABEL and editor["title"] == screen_words.EDITOR_TITLE
    assert editor["engagement_title"] == screen_words.EDITOR_ENGAGEMENT_TITLE
    assert editor["save"] == screen_words.EDITOR_SAVE_LABEL and editor["cancel"] == screen_words.EDITOR_CANCEL_LABEL
    assert editor["add_row"] == screen_words.EDITOR_ADD_LABEL and editor["remove_row"] == screen_words.EDITOR_REMOVE_LABEL
    assert editor["paste"] == screen_words.EDITOR_PASTE_LABEL and editor["paste_hint"] == screen_words.EDITOR_PASTE_HINT
    assert editor["warnings_heading"] == screen_words.EDITOR_WARNINGS_HEADING
    assert editor["saved"] == screen_words.RULES_SAVED and editor["nothing_changed"] == screen_words.NOTHING_CHANGED
    assert editor["learned_note"] == screen_words.LEARNED_NOTE
    assert editor["unlearn_label"] == screen_words.UNLEARN_LABEL
    assert editor["unlearned_note"] == screen_words.UNLEARNED_NOTE
    assert [f["key"] for f in editor["engagement_fields"]] == [f for _, f in ENGAGEMENT_FIELDS]
    assert {f["key"] for f in editor["engagement_fields"] if f["editable"]} == set(ENGAGEMENT_EDITABLE)
    # Which details take a date box is the record's answer, not the page's.
    assert editor["date_fields"] == list(DATE_FIELDS)
    assert editor["minimums"] == {"expected_count": 1, "min_size_kb": 0}
    # And the maximums, the record's own (decision 187): the page's number
    # boxes stop where the store's gate would refuse.
    assert editor["maximums"] == {"expected_count": MAX_EXPECTED_COUNT, "min_size_kb": MAX_SIZE_KB}
    assert editor["any_extension"] == "*" and editor["no_date_check"] == "*"
    assert "set_aside_heading" not in editor
    assert vocab["commands"] == sorted(api.COMMANDS)
    assert [r["headline"] for r in vocab["rules"]] == [h for h, _ in STANDING_RULES]
    assert vocab["schedule"] == {"start": DEFAULT_START, "every": DEFAULT_REPEAT_MINUTES,
                                 "draft_day": WEEKDAY_NAMES[DRAFT_WEEKDAY],
                                 "task_name": TASK_NAME,
                                 "repair": screen_words.SCHEDULE_REPAIR_LABEL,
                                 "repair_help": screen_words.SCHEDULE_REPAIR_HELP,
                                 "repair_confirm": screen_words.SCHEDULE_REPAIR_CONFIRM.format(
                                     draft_day=WEEKDAY_NAMES[DRAFT_WEEKDAY]),
                                 "move_confirm": screen_words.SCHEDULE_MOVE_CONFIRM,
                                 "move_warning": screen_words.SCHEDULE_MOVE_WARNING,
                                 "remove_confirm": screen_words.SCHEDULE_REMOVE_CONFIRM,
                                 "button": "Schedule", "title": "Schedule on This Computer",
                                 "enabled_label": "Run the Schedule", "on": "On", "off": "Off",
                                 "start_label": "First Run At", "every_label": "How Often",
                                 "every_choices": [
                                     {"minutes": 0, "label": "Once a Day"},
                                     {"minutes": 30, "label": "Every 30 Minutes"},
                                     {"minutes": 60, "label": "Every Hour"},
                                     {"minutes": 120, "label": "Every 2 Hours"},
                                     {"minutes": 240, "label": "Every 4 Hours"},
                                     {"minutes": 480, "label": "Every 8 Hours"}],
                                 "note": "Scan works either way. Nothing is ever sent.",
                                 "loading": screen_words.SCHEDULE_LOADING, "save": "Save", "cancel": "Cancel"}
    # The settings page's phone box: its label, its sentence and the
    # number as recorded (decision 117).
    assert vocab["settings"] == {"phone_label": screen_words.FIRM_PHONE_LABEL,
                                 "phone_help": screen_words.FIRM_PHONE_HELP, "phone": "",
                                 "firm_label": screen_words.FIRM_NAME_LABEL, "firm_help": screen_words.FIRM_NAME_HELP,
                                 "root_label": screen_words.CLIENTS_FOLDER_LABEL}
    # And every word and colour the Reminder card shows (decision 118).
    _the_reminder_card_words_are_all_pythons(vocab["reminder"])


def _the_reminder_card_words_are_all_pythons(words):
    """The vocabulary pin for decision 118's card: every word from the
    module that owns the draft, the four rungs with the palette key each
    carries and where each spends its emphasis, and the palette those keys
    name. A hex reaches the app only through this map."""
    from dataclasses import asdict

    from tracker import letter_render, reminder
    from tracker.page import PALETTE
    from tracker.runner import NOTHING_OUTSTANDING

    assert words == {
        "held_line": reminder.HELD_SUMMARY,
        "inbox_held_line": reminder.INBOX_HELD_SUMMARY,
        "heading": reminder.REMINDER_HEADING,
        "stage_group": reminder.STAGE_GROUP_LABEL,
        "subject_prefix": reminder.SUBJECT_PREFIX,
        "copy": reminder.COPY_LABEL,
        "approve": reminder.APPROVE_LABEL,
        "open_draft": reminder.OPEN_DRAFT_LABEL,
        "last_drafted_line": reminder.LAST_DRAFTED_LINE,
        "never_drafted_line": reminder.NEVER_DRAFTED_LINE,
        "approved_line": reminder.APPROVED_LINE,
        "approved_then_edited": reminder.APPROVED_THEN_EDITED,
        "edited_by_hand": reminder.EDITED_BY_HAND,
        "stage_toggle_hint": reminder.STAGE_TOGGLE_HINT,
        "copied": reminder.COPIED_NOTE,
        "set_aside_line": reminder.SET_ASIDE_LINE,
        "not_yet": reminder.REMINDER_NOT_YET,
        "unreadable": screen_words.REMINDER_UNREADABLE,
        "line_unreadable": screen_words.REMINDER_LINE_UNREADABLE,
        "nothing_to_send": NOTHING_OUTSTANDING,
        "stages": [{"number": stage.number, "name": stage.name,
                    "colour": letter_render.STAGE_COLOURS[stage.number],
                    "emphasis": asdict(letter_render.STAGE_EMPHASIS[stage.number]),
                    "short": stage.short}
                   for stage in reminder.STAGES],
        "palette": dict(PALETTE),
        "hold_colour": letter_render.HOLD_COLOUR,
        "letter_ink": dict(letter_render.LETTER_INK),
        "sides": [{"key": side.key, "label": side.label, "sentence": side.sentence}
                  for side in reminder.SIDES],
    }
    # Nothing the card shows is typed in the renderer, and no colour of any
    # kind reaches it: every hex it draws with is looked up in this palette.
    renderer = renderer_text(APP_SCRIPTS)
    for word in (words["heading"], words["stage_group"], words["copy"], words["approve"],
                 words["open_draft"], words["edited_by_hand"], words["stage_toggle_hint"],
                 words["copied"], words["nothing_to_send"], words["subject_prefix"],
                 *(stage["name"] for stage in words["stages"])):
        assert f'"{word}"' not in renderer and f"'{word}'" not in renderer, word


def test_the_settings_carry_the_firm_phone_and_the_vocabulary_names_its_box(capsys, demo_root):
    """Decision 117: the firm's telephone number is a firm-wide setting
    beside its name, said only by the final-notice reminder. The app shows
    a box for it and types neither its label nor its sentence."""
    from tracker.settings import firm_phone

    code, payload = run(capsys, "settings")
    assert code == 0 and payload["phone"] == ""

    code, payload = run(capsys, "set-root", stdin={"root": str(demo_root), "phone": "(555) 010-2020"})
    assert code == 0, payload
    assert payload["phone"] == "(555) 010-2020" and firm_phone() == "(555) 010-2020"
    assert payload["firm"] == "J Park & Associates, CPA", "a key not sent leaves what is recorded"
    assert run(capsys, "settings")[1]["phone"] == "(555) 010-2020"

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["settings"]["phone"] == "(555) 010-2020"
    renderer = renderer_text(APP_SCRIPTS)
    html = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "index.html").read_text(
        encoding="utf-8"
    )
    for word in (screen_words.FIRM_PHONE_LABEL, screen_words.FIRM_PHONE_HELP):
        assert word not in renderer and word not in html, word
    assert "vocab.settings.phone_label" in renderer_text(APP_SCRIPTS), "the setup page's box is named by the API"


def test_the_reminder_payload_holds_on_a_parked_client_side_file(capsys, demo_root, tmp_path):
    """Decision 117: a parked file the client could fix holds the request
    the review card offers it for, and the card and the draft day agree -
    both read the shortlist, from the index rows ``state`` already has."""
    from tests.samples import write_pdf
    from tracker import reasons
    from tracker.reminder import PARKED_HOLD

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
    # The client sent their W-2 with a password on it: nothing in it can
    # be read, so no request accepts it and A01 stays Missing.
    write_pdf(inbox_of(folder) / f"W-2 Jane Smith {PRIOR_YEAR + 1}.pdf",
              pages=60, password="secret123")     # over the row's size floor
    assert scan(capsys, folder)[0] == 0

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(folder))
    assert code == 0, payload
    [parked] = [row for row in payload["index"] if row["decision"] == NEEDS_REVIEW]
    assert parked["candidates"] == [], "a name is no candidate"
    assert [s["identifier"] for s in payload["review"][0]["shortlist"]] == ["A01"]
    held = payload["reminder"]["held"]
    assert [row["identifier"] for row in held] == ["A01"]
    assert held[0]["reason"] == PARKED_HOLD.format(ask=reasons.PASSWORD_PROTECTED.client_ask)


def test_state_carries_the_held_rows_and_every_word_is_the_vocabularys(capsys, demo_root):
    """Decision 115: the app shows one line for a held reminder. The rows
    come from the reminder's own triage over the rows state already loaded,
    the sentence from the module that holds the draft, and the renderer
    types neither - it reads ``vocab.reminder`` and counts."""
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate
    from tracker.reminder import AMBIGUOUS_HOLD, HELD_SUMMARY

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"},
                                       {"identifier": "C01", "document": "Form 1098"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, "Smith")
    seed_statuses(folder, {
        "A01": StatusUpdate(status=Status.MISSING),
        "C01": StatusUpdate(status=Status.FAILED, file_count=1,
                            validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"),
                            note_codes=reasons.WRONG_DOCUMENT.code),
    })
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(folder))
    assert code == 0
    held = payload["reminder"]["held"]
    assert [row["identifier"] for row in held] == ["C01"]
    assert held[0]["label"].startswith("C01") and held[0]["reason"].startswith(AMBIGUOUS_HOLD)
    assert payload["reminder"]["last_drafted"] is None      # never drafted
    assert not (folder / "reminder-draft.txt").exists(), "state never drafts (decision 12)"

    vocab = run(capsys, "list")[1]["vocab"]
    assert vocab["reminder"]["held_line"] == HELD_SUMMARY
    renderer = renderer_text(APP_SCRIPTS)
    for word in (HELD_SUMMARY, HELD_SUMMARY.split("{")[0].strip(), AMBIGUOUS_HOLD):
        assert not _typed_as_a_string(renderer, word), word
    assert "vocab.reminder.held_line" in renderer


def test_every_status_the_vocabulary_names_has_the_label_a_row_says(capsys, demo_root):
    """The chips are gone (SPEC 2.5 E58): a row says its status as one word
    from the label table, so each status must have one, keyed as the state's
    `status_key` is."""
    vocab = run(capsys, "list")[1]["vocab"]
    for status in vocab["statuses"]:
        assert vocab["labels"][status["value"]]["label"], status
        assert status["key"] == api._slug(status["value"])
    css = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "style.css").read_text(encoding="utf-8")
    assert ".chip" not in css


def test_the_new_client_name_rule_lives_in_python_and_uses_the_form_label(capsys, demo_root):
    spec = {"form": "1120S", "client": "Acme", "year": 2026,
            "items": [{"identifier": "A01", "document": "Trial Balance", "any_keywords": "trial balance"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"].endswith(api.default_return_name("1120S", "Acme"))


def test_priors_carry_next_year_and_the_index_carries_candidates(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    code, payload = scan(capsys, engagement)
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    assert parked["candidates"] == ["A01"]
    assert parked["filed_as"] == f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf"
    code, payload = run(capsys, "priors")
    [prior] = payload["priors"]
    assert prior["year"] == BASE_YEAR and prior["next_year"] == BASE_YEAR + 1


def test_the_state_carries_each_rows_evidence_as_data_not_as_a_string(capsys, demo_root, tmp_path):
    from tracker.records import EVIDENCE_PLACES, EVIDENCE_RULES, RULE_REQUIRED, WHERE_TITLE

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    # Parsed by the tracker, never split by the renderer: a record keyed by
    # candidate, each entry naming its rule, its term and where it was said.
    assert [(e["rule"], e["term"], e["where"]) for e in parked["evidence"]["A01"]][:1] == [
        (RULE_REQUIRED, "W-2", WHERE_TITLE),
    ]
    assert all(e["rule"] in EVIDENCE_RULES for e in parked["evidence"]["A01"])
    code, listed = run(capsys, "list")
    vocab = listed["vocab"]["evidence"]
    assert vocab["rules"] == list(EVIDENCE_RULES) and vocab["places"] == list(EVIDENCE_PLACES)
    assert RULE_REQUIRED in vocab["rules"] and WHERE_TITLE in vocab["places"]


# ============= a click walks nothing (decision 192) =========================


def _count_walks(monkeypatch) -> list[Path]:
    """Every walk of a clients root from now on: each goes through
    ``registry._walk_root``, and ``households_named`` never does."""
    from tracker import registry

    walked: list[Path] = []
    real = registry._walk_root

    def counting(root):
        walked.append(Path(root))
        return real(root)

    monkeypatch.setattr(registry, "_walk_root", counting)
    return walked


def _count_journal_reads(monkeypatch) -> list[Path]:
    """Every journal read from now on: each goes through
    ``Path.read_bytes`` (``ledger._bytes_of``)."""
    read: list[Path] = []
    real = Path.read_bytes

    def counting(self):
        if self.name == ledger.LEDGER_FILENAME:
            read.append(Path(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    return read


def _a_third_household(capsys, root):
    """A household nothing feeds and that feeds nothing: the rest of the
    practice a click on another return has no business reading."""
    assert run(capsys, "create", stdin={
        "household": "Kim Household", "contact": "Dana",
        "return_name": "1040 - Dana Kim",
        "items": [{"identifier": "C01", "document": "W-2"}]})[0] == 0
    return where(root, "1040 - Dana Kim", household="Kim Household")


def test_showing_a_return_walks_nothing_and_reads_no_other_households_record(
        capsys, demo_root, monkeypatch):
    """F-M-1: the card's two feed lines used to walk the practice and read
    every journal in it. The LLC feeds nothing, so its card reads nothing
    outside its own household - and is still told Park Family feeds it."""
    _father, llc = two_households(capsys, demo_root)
    _a_third_household(capsys, demo_root)
    walked, read = _count_walks(monkeypatch), _count_journal_reads(monkeypatch)

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(llc))

    assert code == 0, payload
    assert walked == []
    household = llc.parent.parent
    assert read and ledger.path_for(llc) in read
    assert all(household in one.parents for one in read), read
    assert [one["name"] for one in payload["household"]["fed_by"]] == ["Park Family"]


def test_a_return_that_feeds_another_household_reads_only_that_households_records(
        capsys, demo_root, monkeypatch):
    """R1: a feed is resolved fresh, over the households the feed list
    names and no other - the third household is never opened."""
    father, llc = two_households(capsys, demo_root)
    third = _a_third_household(capsys, demo_root)
    walked, read = _count_walks(monkeypatch), _count_journal_reads(monkeypatch)

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))

    assert code == 0, payload
    assert walked == []
    mine, theirs = father.parent.parent, llc.parent.parent
    assert read and ledger.path_for(father) in read
    assert all(mine in one.parents or theirs in one.parents for one in read), read
    assert not any(third.parent.parent in one.parents for one in read)
    [feed] = payload["household"]["feeds"]
    assert feed["path"] == str(llc) and feed["warning"] == ""
    assert "1120S - Park & Lee LLC" in feed["label"]


def test_run_now_walks_the_practice_once(capsys, demo_root, monkeypatch):
    """F-M-3: *Run now* walked three or four times - the pass, the page,
    the state and a waiting row. One walk now serves the pass and the
    page, and the state walks nothing; the app's redraw after the pass
    asks ``list`` once (decision 203, the lane's ruling on 194's Q5)."""

    father, llc = two_households(capsys, demo_root)
    third = _a_third_household(capsys, demo_root)
    text_pdf(inbox_of(father) / "tb.pdf", ["Trial balance as of December 31 2025", TEST_CLIENT], style="padded")
    walked = _count_walks(monkeypatch)

    code, payload = scan(capsys, father)

    assert code == 0, payload
    assert walked == [demo_root, demo_root], "the pass's one walk, then the redraw's list"
    assert payload["state"]["household"]["returns"]
    assert not any("RegistryError" in one for one in payload["pass_warnings"])
    page = (demo_root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    for one in (father, llc, third):
        assert one.parent.parent.name.replace("&", "&amp;") in page


def test_fed_by_names_no_household_whose_record_is_gone(capsys, demo_root, tmp_path, monkeypatch):
    """R2: the store still holds Park Family's row after its folder is
    moved aside, and the card does not name it - each row is held to a
    journal that is still where the row says."""
    father, llc = two_households(capsys, demo_root)
    assert [one["name"] for one in api.state(llc)["household"]["fed_by"]] == ["Park Family"]
    father.parent.parent.rename(tmp_path / "aside")
    walked = _count_walks(monkeypatch)

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(llc))

    assert code == 0, payload
    assert payload["household"]["fed_by"] == []
    assert walked == []


def test_a_paused_household_shows_its_pause_and_accept_without_a_walk(capsys, demo_root, monkeypatch):
    """Decision 188's pause is this household's own: its folders and its
    record. Nothing about it needs the practice."""
    from tracker.households import HOUSEHOLD_PAUSED

    engagement = _a_renamed_household(capsys, demo_root)
    walked = _count_walks(monkeypatch)

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))

    assert code == 0, payload
    assert walked == []
    pause = payload["household"]["pause"]
    assert pause["sentence"] == HOUSEHOLD_PAUSED and pause["scope"] == "household"
    assert pause["seq"]


def test_a_waiting_row_costs_the_state_one_household_payload(capsys, demo_root, monkeypatch):
    """R8: the feed list a waiting row is offered from is drawn from the
    household payload the card already built, not a second one."""
    father, llc = two_households(capsys, demo_root)
    waiting_document(capsys, father)
    built: list[Path] = []
    real = api._household_payload

    def counting(engagement):
        built.append(engagement)
        return real(engagement)

    monkeypatch.setattr(api, "_household_payload", counting)

    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(father))

    assert code == 0, payload
    assert built == [father]
    [waiting] = payload["review"]
    assert waiting["waits_for"]["target"] == str(llc)
    assert waiting["waits_for_refused"] == ""


def test_a_household_row_the_store_cannot_read_costs_no_other_card_and_is_said(
        capsys, demo_root, caplog):
    """The review's S1: one household row the store cannot read - a
    schema from another version, a hand-damaged store - used to fail
    every return's card in the practice. Every other card is whole; *Fed
    by* names the households it can read and says, by class alone, that
    one could not be; the class is logged."""
    import logging

    _father, llc = two_households(capsys, demo_root)
    kim = _a_third_household(capsys, demo_root)
    family = llc.parent.parent.parent / "Park Family"
    conn = store.connect()
    with conn:
        conn.execute(f"UPDATE engagements SET {store.HOUSEHOLD_PREFIX}feeds = ? WHERE path LIKE ?",
                     ('{"x": 1}', f"%/{family.name}"))
    said = screen_words.FED_BY_UNREADABLE.format(kind="ValueError")

    with caplog.at_level(logging.WARNING, logger="tracker.api"):
        code, other = run(capsys, "state", api.ENGAGEMENT_FLAG, str(kim))
    assert code == 0, other
    assert other["household"]["fed_by"] == [{"name": said, "path": "", "members": []}]
    assert "ValueError" in caplog.text and str(family) not in caplog.text
    code, fed = run(capsys, "state", api.ENGAGEMENT_FLAG, str(llc))
    assert code == 0, fed
    assert [one["name"] for one in fed["household"]["fed_by"]] == [said]


# ================= decision 193: replies never go quiet ==================


def _live_child():
    """A process that is running and is not this one, for a lock or a pass
    that must read as another's."""
    import subprocess
    import sys

    return subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"])


def test_every_reply_carries_a_warnings_list_and_every_error_a_failure_whose_sentence_is_the_error(
        capsys, demo_root):
    from tracker.progress import FAILURE_KINDS

    code, payload = run(capsys, "list")
    assert code == 0 and payload["warnings"] == [] and "failure" not in payload
    for command in sorted(api.COMMANDS):
        if command == "install-schedule":
            continue    # it registers a real job; its envelope is main()'s like every other's
        code, out = _raw(capsys, command, api.ENGAGEMENT_FLAG, str(demo_root / "nowhere"))
        reply = one_reply(out)
        assert isinstance(reply["warnings"], list), command
        if code:
            failure = reply["failure"]
            assert failure["sentence"] == reply["error"], command
            assert failure["kind"] in FAILURE_KINDS, command
            assert set(failure) >= {"sentence", "kind", "seq", "identifier"}, command
        else:
            assert "error" not in reply, command
    code, payload = run(capsys, "frobnicate")
    assert code == 1 and payload["failure"]["kind"] == "refused"
    assert payload["error"].startswith("usage:") and payload["warnings"] == []


def test_a_stale_click_is_kind_stale_and_names_the_row_and_the_records_seq_now(
        capsys, demo_root, tmp_path):
    from tracker.index import NOT_REQUESTED

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    code, after = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                      stdin={"original": parked["pbc_location"], "note": "an IRS notice",
                             "seq": parked["seq"]})
    assert code == 0, after
    [now] = [e for e in after["state"]["index"] if e["decision"] == NOT_REQUESTED]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": "D01",
                               "seq": parked["seq"]})
    assert code == 1
    failure = payload["failure"]
    assert failure["kind"] == "stale" and failure["sentence"] == payload["error"]
    # The row the person clicked, by the key the card sent, and the line the
    # record holds for it now - not the one the card was drawn from.
    assert failure["identifier"] == parked["pbc_location"]
    assert failure["seq"] == now["seq"] != parked["seq"]


def test_a_list_saved_from_an_old_version_is_kind_stale(capsys, demo_root):
    from tracker.manifest import LIST_MOVED

    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    state = payload_of_state(capsys, engagement)
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": _rows_of(state), "engagement": {}, "head": "not the head it holds"})
    assert code == 1 and payload["error"] == LIST_MOVED
    assert payload["failure"]["kind"] == "stale"


def test_a_click_on_a_held_lock_is_kind_locked_with_the_passes_start_host_and_current_file(
        capsys, demo_root):
    from tracker import progress
    from tracker.locking import LOCK_FILENAME

    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    state = payload_of_state(capsys, engagement)
    other = _live_child()
    try:
        started = dt.datetime.now().replace(microsecond=0)
        (engagement / LOCK_FILENAME).write_text(lock_line(other.pid, started), encoding="utf-8")
        watch = progress.Watch(store.store_path().parent, limit_seconds=60, pass_id=other.pid)
        watch.say("household", household=HOUSEHOLD, n=1, of=1)
        watch.say("file", step="sort", name="W-2 Sample.pdf")
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
            "items": _rows_of(state), "engagement": {}, "head": state["list_head"]})
        assert code == 1, payload
        failure = payload["failure"]
        assert failure["kind"] == "locked" and "delete" not in failure["sentence"].lower()
        lock = failure["lock"]
        assert lock["started"] == started.isoformat() and lock["host"] == this_host()
        assert lock["this_machine"] is True and lock["engagement"] == str(engagement)
        assert lock["pass"]["household"] == HOUSEHOLD and lock["pass"]["name"] == "W-2 Sample.pdf"
        watch.close("finished")
    finally:
        other.kill()
        other.wait()


def test_a_refusal_is_kind_refused_and_keeps_its_sentence(capsys, demo_root):
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(demo_root / "nowhere"))
    assert code == 1 and payload["failure"]["kind"] == "refused"
    assert "not an engagement" in payload["error"]
    assert not payload["error"].startswith(("ManifestError", "LayoutError", "DoorError"))


def test_a_store_refusal_is_said_in_its_own_sentence_and_kind_refused(capsys, demo_root, monkeypatch):
    sentence = store.REWRITTEN.format(rel="Sample Household/2025/1040 - Sample", line=7)

    def rewritten(argv):
        raise store.StoreError(sentence)

    monkeypatch.setitem(api.COMMANDS, "templates", rewritten)
    code, payload = run(capsys, "templates")
    assert code == 1 and payload["error"] == sentence       # was "StoreError: ..."
    assert payload["failure"]["kind"] == "refused"


def test_an_unexpected_error_is_said_by_class_on_screen_and_in_full_only_in_the_error_log(
        capsys, demo_root, monkeypatch):
    from tracker.errlog import error_log_path

    def surprise(argv):
        raise ValueError("a fabricated message naming Sample Client's folder")

    monkeypatch.setitem(api.COMMANDS, "templates", surprise)
    code, out = _raw(capsys, "templates")
    payload = one_reply(out)
    assert code == 1 and said_by_class(payload, "ValueError")
    assert "fabricated message" not in out
    logged = error_log_path().read_text(encoding="utf-8")
    assert "a fabricated message naming Sample Client's folder" in logged
    assert "Traceback" in logged and "templates failed" in logged


def test_a_broken_journal_is_said_in_the_firms_sentence_with_its_line_and_run_recover(
        capsys, demo_root, monkeypatch, tmp_path):
    """Decision 190's landing review, MF1: the app says a LedgerError as the
    status page and the run report do - whole, with its line and the one
    instruction that fixes it - while a disk's or a store's failure stays
    by its class and code."""
    return_dir = tmp_path / "1040 - Sample Household"
    return_dir.mkdir()
    ledger.path_for(return_dir).write_bytes(b"this line is not an event\n{}\n")

    def reads_the_broken_journal(argv):
        ledger.read_events(return_dir)

    monkeypatch.setitem(api.COMMANDS, "templates", reads_the_broken_journal)
    code, payload = run(capsys, "templates")
    sentence = ledger.NOT_AN_EVENT.format(name=ledger.path_for(return_dir).name, line=1,
                                          why="it is not JSON")
    assert code == 1 and payload["error"] == sentence, payload
    assert payload["failure"]["kind"] == "refused" and ledger.RUN_RECOVER in payload["error"]

    for raised, sentence in ((ledger.RecordNotWritten("ENOSPC"), screen_words.RECORD_NOT_WRITTEN),
                             (store.StoreUnavailable("SQLITE_BUSY"), screen_words.STORE_UNAVAILABLE)):
        def fails(argv, raised=raised):
            raise raised

        monkeypatch.setitem(api.COMMANDS, "templates", fails)
        code, payload = run(capsys, "templates")
        assert code == 1 and payload["error"] == sentence.format(
            code=raised.code, log=api.ERROR_LOG_FILENAME), payload
        assert payload["failure"]["kind"] == "failed"


@pytest.mark.parametrize("raised, sentence, code", [
    (store.StoreUnavailable("SQLITE_BUSY"), "STORE_UNAVAILABLE", "SQLITE_BUSY"),
    (ledger.RecordNotWritten("ENOSPC"), "RECORD_NOT_WRITTEN", "ENOSPC"),
])
def test_a_database_that_cannot_be_used_is_said_as_itself_with_its_code_and_keeps_retry(
        raised, sentence, code):
    """The audit's E5 (P298): decision 189 made both expected classes, and
    they were said as "an error it did not expect". Each has a sentence of
    its own with its code; the kind stays ``failed``, so the window keeps
    Retry."""
    failure = api._failure_of(raised)
    assert failure["kind"] == "failed"
    assert failure["sentence"] == getattr(api, sentence).format(code=code, log=api.ERROR_LOG_FILENAME)
    assert code in failure["sentence"] and "did not expect" not in failure["sentence"]
    assert api.ERROR_LOG_FILENAME in failure["sentence"]


def test_a_rollover_that_could_not_read_last_years_index_says_so_in_its_reply(
        capsys, demo_root, monkeypatch):
    """E2 (P297): the reply's ``warnings`` - which the page already draws -
    carry the sentence, as the last line, after the one ``create_engagement``
    assigns."""
    from tracker import copies, index
    from tracker.rollover import UNFILED_LAST_YEAR_UNREAD

    engagement, _ = _issuer_return(capsys, demo_root)

    def torn(*_args, **_kwargs):
        raise copies.FilingError("the index is torn")

    monkeypatch.setattr(index, "read_index", torn)
    code, payload = run(capsys, "rollover", stdin={"prior": str(engagement), "year": BASE_YEAR + 1})
    assert code == 0, payload
    assert payload["rollover"]["warnings"][-1] == UNFILED_LAST_YEAR_UNREAD.format(
        problem="the index is torn")
    assert payload["rollover"]["unfiled_last_year"] == []


def test_the_error_log_rotates_and_never_syncs_to_disk(capsys, demo_root, monkeypatch):
    from tracker import errlog
    from tracker.errlog import error_log_path

    def no_sync(fd):
        raise AssertionError("the error log is never synced to disk")

    def surprise(argv):
        raise ValueError("x" * 400)

    monkeypatch.setattr(os, "fsync", no_sync)
    monkeypatch.setattr(errlog, "ERROR_LOG_MAX_BYTES", 2000)
    monkeypatch.setitem(api.COMMANDS, "templates", surprise)
    for _ in range(12):
        assert run(capsys, "templates")[0] == 1
    path = error_log_path()
    assert path.with_name(path.name + ".1").is_file()
    assert not path.with_name(path.name + f".{errlog.ERROR_LOG_BACKUPS + 1}").exists()


def test_run_now_prints_a_progress_line_per_household_and_file_before_its_one_reply(
        capsys, demo_root, tmp_path):
    from tracker.locking import RUN_TIME_LIMIT_SECONDS
    from tracker.progress import PROGRESS_KEY

    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")
    code, out = _raw(capsys, api.PASS_COMMAND, api.ENGAGEMENT_FLAG, str(engagement))
    lines = [json.loads(line) for line in out.strip().splitlines()]
    assert code == 0
    assert all(PROGRESS_KEY in line for line in lines[:-1]) and PROGRESS_KEY not in lines[-1]
    said = [line[PROGRESS_KEY] for line in lines[:-1]]
    assert said[0]["event"] == "started" and said[0]["limit_seconds"] == RUN_TIME_LIMIT_SECONDS
    assert said[1]["event"] == "household" and (said[1]["n"], said[1]["of"]) == (1, 1)
    files = [one for one in said if one["event"] == "file"]
    assert {"sort", "scan"} <= {one["step"] for one in files}
    assert "Mortgage Notes.docx" in {one["name"] for one in files if one["step"] == "sort"}
    assert all(one["household"] == said[1]["household"] for one in files)
    assert said[-1]["event"] == "ended" and said[-1]["outcome"] == "finished"
    assert lines[-1]["pass"] == said[0]["pass"] and lines[-1]["exit"] == 0
    assert [one["cancelled"] for one in lines[-1]["runs"]] == [False]


@pytest.mark.parametrize("raised", [RuntimeError, ManifestError])
def test_run_now_that_filed_keeps_its_counts_whatever_the_redraw_raises(capsys, demo_root, tmp_path,
                                                                         monkeypatch, raised):
    """D5 whole (the review's M2): a ManifestError from the redraw - a list
    that cannot be read just then - keeps the counts as any other does.
    Since decision 203 the counts are the pass's final line, printed before
    any redraw, and the redraw is the app's own ``state``, whose failure is
    its own notice."""
    engagement = sample_engagement(capsys, demo_root, tmp_path, "Mortgage Notes.docx")

    def cannot_redraw(folder):
        raise raised("a fabricated redraw failure")

    monkeypatch.setattr(api, "state", cannot_redraw)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    assert payload["state"] is None and "error" not in payload
    assert payload["run"]["review"] == 1          # the pass's counts stand


def test_cancel_pass_refuses_a_pass_that_is_not_running(capsys, demo_root):
    from tracker import progress

    code, payload = run(capsys, "cancel-pass", stdin={"pass": 999_999_999})
    assert code == 1 and payload["error"] == screen_words.NOTHING_TO_STOP
    assert payload["failure"]["kind"] == "refused"
    other = _live_child()
    try:
        # The scheduled pass: live, and never this app's to stop.
        scheduled = progress.Watch(store.store_path().parent, limit_seconds=60, pass_id=other.pid)
        scheduled.say("started")
        assert run(capsys, "cancel-pass", stdin={"pass": other.pid})[0] == 1
        # One this app started: asked, and told so.
        started = progress.Watch(store.store_path().parent, emit=lambda line: None,
                                 limit_seconds=60, pass_id=other.pid)
        started.say("started")
        code, payload = run(capsys, "cancel-pass", stdin={"pass": other.pid})
        assert code == 0 and payload["stopping"] is True
        assert started.stop_asked()
        started.close("stopped")
    finally:
        other.kill()
        other.wait()


def test_watch_reports_the_lock_and_then_none_once_it_is_let_go(capsys, demo_root):
    from tracker.locking import LOCK_FILENAME

    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    other = _live_child()
    try:
        (engagement / LOCK_FILENAME).write_text(lock_line(other.pid, dt.datetime.now()),
                                                encoding="utf-8")
        code, payload = run(capsys, "watch", api.ENGAGEMENT_FLAG, str(engagement))
        assert code == 0 and payload["lock"]["stale"] is False
        (engagement / LOCK_FILENAME).unlink()
        code, payload = run(capsys, "watch", api.ENGAGEMENT_FLAG, str(engagement))
        assert code == 0 and payload == {"lock": None, "warnings": []}
    finally:
        other.kill()
        other.wait()


def test_a_reminder_that_cannot_be_read_is_an_error_and_one_not_yet_scanned_is_a_line(
        capsys, demo_root, monkeypatch):
    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(engagement), stdin={})
    assert code == 0 and payload["reminder"] is None
    assert payload["not_yet"] == reminder.REMINDER_NOT_YET == api.vocab()["reminder"]["not_yet"]

    folder = chased_engagement(capsys, demo_root, name="Unreadable")

    def unreadable(*args, **kwargs):
        raise OSError(5, "a fabricated read failure")

    monkeypatch.setattr(reminder, "draft_reminder", unreadable)
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={})
    assert code == 1 and payload["failure"]["kind"] == "failed"
    assert "fabricated" not in payload["error"]


def test_a_returns_reminder_line_that_cannot_be_read_says_so(capsys, demo_root, monkeypatch):
    folder = chased_engagement(capsys, demo_root, name="Line")

    def unreadable(*args, **kwargs):
        raise OSError(5, "a fabricated read failure")

    monkeypatch.setattr(reminder, "last_approved_event", unreadable)
    payload = payload_of_state(capsys, folder)
    [line] = [r["reminder"] for r in payload["household"]["returns"] if r["path"] == str(folder)]
    assert line["unreadable"] is True and line["kind"] == "OSError (EIO)"
    [label] = [r["label"] for r in payload["household"]["returns"] if r["path"] == str(folder)]
    said = screen_words.REMINDER_LINE_UNREADABLE_WARNING.format(label=label)
    assert label in said, "the warning must name the return"
    assert said in payload["warnings"]


def test_a_root_that_cannot_be_walked_says_so_on_the_feeds_and_the_list(capsys, demo_root,
                                                                         monkeypatch):
    from tracker.registry import RegistryError

    father, _llc = two_households(capsys, demo_root)

    def cannot_walk(*args, **kwargs):
        raise RegistryError("a fabricated walk failure")

    for module in (api, firm_view, household_edit):
        monkeypatch.setattr(module, "households_named", cannot_walk)
    payload = payload_of_state(capsys, father)
    assert [feed["warning"] for feed in payload["household"]["feeds"]] == [screen_words.PRACTICE_NOT_WALKED]
    assert screen_words.PRACTICE_NOT_WALKED in payload["warnings"]

    monkeypatch.setattr(api, "discover_engagements", cannot_walk)
    code, payload = run(capsys, "list")
    assert code == 0 and payload["root_problem"] == screen_words.PRACTICE_NOT_WALKED
    assert payload["warnings"] == [screen_words.PRACTICE_NOT_WALKED]
    assert "fabricated" not in json.dumps(payload)


def test_a_reminder_held_a_week_says_so(capsys, demo_root, monkeypatch):
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate

    folder = chased_engagement(capsys, demo_root, name="Held Long")
    seed_statuses(folder, {"B01": StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"))})
    days = reminder.HELD_WARN_DAYS + 3
    monkeypatch.setattr(api, "created_on", lambda path: dt.date.today() - dt.timedelta(days=days))
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={})
    assert code == 0, payload
    said = reminder.HELD_TOO_LONG.format(days=days)
    assert payload["reminder"]["held_too_long"] == said and said in payload["warnings"]

    monkeypatch.setattr(api, "created_on", lambda path: dt.date.today())
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={})
    assert payload["reminder"]["held_too_long"] == "" and payload["warnings"] == []


def test_a_draft_beside_an_edited_one_is_said_in_the_app(capsys, demo_root):
    folder = chased_engagement(capsys, demo_root, name="Beside")
    (folder / reminder.NEW_DRAFT_FILENAME).write_text("a fabricated fresh draft\n", encoding="utf-8")
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={})
    assert code == 0 and payload["warnings"] == [reminder.DRAFT_WRITTEN_BESIDE]


def test_an_action_whose_readme_cannot_be_rewritten_warns(capsys, demo_root, monkeypatch):
    import tracker.readme_ack as readme_ack_module
    from tracker.readme_ack import README_NOT_REWRITTEN

    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")

    def cannot_write(*args, **kwargs):
        raise OSError(13, "a fabricated denial")

    state = payload_of_state(capsys, engagement)
    monkeypatch.setattr(readme_ack_module, "write_readme", cannot_write)
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": _rows_of(state), "engagement": {"due": "2026-03-15"}, "head": state["list_head"]})
    assert code == 0, payload
    assert payload["warnings"] == [README_NOT_REWRITTEN.format(kind="PermissionError (EACCES)")]


def test_a_rolled_from_naming_nothing_is_a_warning(capsys, demo_root, monkeypatch):
    from dataclasses import replace as replaced

    from tracker.registry import ROLLED_FROM_UNMATCHED

    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    real = api.engagement_from

    def rolled_from_nothing(folder):
        found = real(folder)
        return replaced(found, info=replaced(found.info, rolled_from="1040 - Nobody Sample"))

    monkeypatch.setattr(api, "engagement_from", rolled_from_nothing)
    payload = payload_of_state(capsys, engagement)
    assert payload["warnings"] == [ROLLED_FROM_UNMATCHED.format(rolled_from="1040 - Nobody Sample")]


def test_a_lock_on_the_household_is_watched_there_and_named_by_its_own_label(capsys, demo_root):
    """The review's S1: the lock that refuses a click may be the household's
    or a sibling's; the notice names it by its label and ``watch`` asks
    about that folder, a household folder included."""
    from tracker.layout import private_household_dir
    from tracker.locking import LOCK_FILENAME

    spec = {"household": HOUSEHOLD, "return_name": "Smith",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    household = private_household_dir(demo_root, HOUSEHOLD)
    other = _live_child()
    try:
        (household / LOCK_FILENAME).write_text(lock_line(other.pid, dt.datetime.now()),
                                               encoding="utf-8")
        code, payload = run(capsys, "watch", api.ENGAGEMENT_FLAG, str(household))
        assert code == 0, payload
        assert payload["lock"]["engagement"] == str(household)
        assert payload["lock"]["label"] == HOUSEHOLD
        (engagement / LOCK_FILENAME).write_text(lock_line(other.pid, dt.datetime.now()),
                                                encoding="utf-8")
        code, payload = run(capsys, "watch", api.ENGAGEMENT_FLAG, str(engagement))
        assert payload["lock"]["label"] == payload_of_label(capsys, engagement)
        (household / LOCK_FILENAME).unlink()
        code, payload = run(capsys, "watch", api.ENGAGEMENT_FLAG, str(household))
        assert code == 0 and payload["lock"] is None
    finally:
        other.kill()
        other.wait()
    code, payload = run(capsys, "watch", api.ENGAGEMENT_FLAG, str(demo_root / "nowhere"))
    assert code == 1 and payload["failure"]["kind"] == "refused"


def payload_of_label(capsys, engagement) -> str:
    """The label the app lists this return by."""
    code, listed = run(capsys, "list")
    return next(e["name"] for e in listed["engagements"] if e["path"] == str(engagement))


# ============= one spawn per click (decision 194) ===========================


def _held_engagement(capsys, demo_root, name):
    """One return held by a failed row: a card with no letter (decision 115)."""
    from tests.builders import seed_statuses
    from tracker import reasons
    from tracker.manifest import StatusUpdate

    folder = chased_engagement(capsys, demo_root, name=name)
    seed_statuses(folder, {"B01": StatusUpdate(
        status=Status.FAILED, file_count=1,
        validation_notes="x.pdf: " + reasons.WRONG_DOCUMENT.format(listed="'1098'"))})
    return folder


def test_the_state_reply_carries_the_reminder_card_the_reminder_command_gives(capsys, demo_root):
    """The card ships inside the state reply (decision 194, R1): for a return
    with rows outstanding, a held one and one nobody has scanned (193's
    not-yet line), ``state.reminder_card`` is exactly what ``reminder``
    answers, less the envelope - one renderer function draws either."""
    chased = chased_engagement(capsys, demo_root, name="Outstanding")
    held = _held_engagement(capsys, demo_root, "Held")
    assert run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Never Scanned",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    never = where(demo_root, "Never Scanned")
    for folder in (chased, held, never):
        card = payload_of_state(capsys, folder)["reminder_card"]
        code, reply = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder), stdin={})
        assert code == 0, reply
        reply.pop("warnings")
        assert card == reply, folder.name
    assert payload_of_state(capsys, never)["reminder_card"] == {
        "reminder": None, "not_yet": reminder.REMINDER_NOT_YET}
    assert payload_of_state(capsys, held)["reminder_card"]["reminder"]["held"]
    assert payload_of_state(capsys, chased)["reminder_card"]["reminder"]["editable"] is True


def test_a_write_that_returns_state_carries_the_reminder_card_too(capsys, demo_root, tmp_path):
    """Every write's state carries the card, so a write is one process and
    the card is the record's after it (decision 194)."""
    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]

    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "identifier": "D01",
                               "keyword": "mortgage notes", "seq": parked["seq"]})
    assert code == 0, payload
    assert payload["state"]["reminder_card"]["reminder"]["fingerprint"] \
        == reminder_card(capsys, engagement)["fingerprint"]

    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "seq": filed["seq"]})
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "seq": parked["seq"]})
    assert code == 0, payload
    assert payload["state"]["reminder_card"]["reminder"]["fingerprint"] \
        == reminder_card(capsys, engagement)["fingerprint"]


def test_a_reminder_that_cannot_be_read_is_said_and_the_page_still_arrives(
        capsys, demo_root, monkeypatch):
    """193's D7, carried into the state (decision 194, R4): a letter that
    cannot be composed takes nothing else with it. The card says why, the
    same sentence is in the reply's warnings, and it names the class only -
    never the exception's text, which can quote a client's path (security
    principle 7)."""
    folder = chased_engagement(capsys, demo_root, name="Unreadable Card")

    def unreadable(*args, **kwargs):
        raise OSError("C:\\secret\\Park W-2.pdf")

    monkeypatch.setattr(api, "_reminder_now", unreadable)
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(folder))
    assert code == 0, payload
    assert payload["items"]
    said = payload["reminder_card"]["unreadable"]
    assert payload["reminder_card"] == {"reminder": None, "unreadable": said}
    assert said == screen_words.FAILED.format(kind="OSError", log=api.ERROR_LOG_FILENAME)
    assert said in payload["warnings"]
    for word in ("secret", "Park W-2"):
        assert word not in json.dumps(payload)


def _the_list_now(capsys) -> dict:
    code, listed = run(capsys, "list")
    assert code == 0, listed
    return {key: listed[key] for key in ("engagements", "households", "misfits", "root")}


def test_the_writes_that_change_the_list_carry_it_without_the_vocabulary(capsys, demo_root):
    """Decision 194, R5-R7: a new return, a new year (one return or the
    household's), a household's details, an accepted name and a return made
    inactive each change what the picker shows, so each reply carries the
    whole list from one walk - the list ``list`` gives, and no vocabulary,
    which only ``list`` ships. Every command :data:`api.LIST_CHANGING`
    names is walked here (the review's S3). Sort & Scan is not among them
    since decision 203: ``run-now`` is the runner's pass and carries no
    list; the app asks ``list`` once when it ends (the ruling on 194's Q5)."""
    carried = set()

    def carries(command, payload):
        assert payload["list"] == _the_list_now(capsys) and "vocab" not in payload["list"], command
        carried.add(command)

    code, payload = run(capsys, "create", stdin={
        "household": "Other Household", "return_name": "Smith 2025", "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 0, payload
    carries("create", payload)
    prior = where(demo_root, "Smith 2025", household="Other Household")

    assert run(capsys, "create", stdin={
        "household": "Third Household", "return_name": "Lee 2025", "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    code, payload = run(capsys, "rollover", stdin={
        "prior": str(where(demo_root, "Lee 2025", household="Third Household")), "year": 2026})
    assert code == 0, payload
    carries("rollover", payload)
    assert str(where(demo_root, "Lee 2025", year=2026, household="Third Household")) in \
        [one["path"] for one in payload["list"]["engagements"]]

    code, payload = run(capsys, "roll-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"year": 2026, "returns": [{"prior": str(prior)}]})
    assert code == 0, payload
    carries("roll-household", payload)
    assert str(where(demo_root, "Smith 2025", year=2026, household="Other Household")) in \
        [one["path"] for one in payload["list"]["engagements"]]

    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"contact": "Pat"})
    assert code == 0, payload
    carries("edit-household", payload)
    [household] = [h for h in payload["list"]["households"] if h["name"] == "Other Household"]
    assert household["contact"] == "Pat"

    rows = payload_of_state(capsys, prior)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(prior),
                        stdin={"items": rows, "engagement": {"active": False}})
    assert code == 0, payload
    assert "active" in payload["saved"]["engagement"]
    carries("edit", payload)

    engagement = _a_renamed_household(capsys, demo_root)
    pause = payload_of_state(capsys, engagement)["household"]["pause"]
    code, payload = run(capsys, "accept-folder-name", api.ENGAGEMENT_FLAG, pause["engagement"],
                        stdin={"seq": pause["seq"], "scope": "household"})
    assert code == 0, payload
    carries("accept-folder-name", payload)
    assert "Park Household" in [h["name"] for h in payload["list"]["households"]]

    assert "scan" not in api.COMMANDS and api.PASS_COMMAND not in api.LIST_CHANGING
    assert carried == set(api.LIST_CHANGING)


def test_the_writes_that_cannot_change_the_list_do_not_walk(capsys, demo_root, tmp_path,
                                                            monkeypatch):
    """Decision 194, R5: showing, filing, dismissing, unfiling, restoring,
    marking missing, the firm's word, approving, the card's own command
    and an edit that leaves ``active`` alone never walk the root and carry
    no list."""
    from tests.builders import _consolidated_return

    engagement = sample_engagement(capsys, demo_root, tmp_path,
                                   "Mortgage Notes.docx", "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    # One filed copy dragged by hand into the review folder, for restore.
    home = engagement / filed["prepared_location"]
    target = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / home.name
    target.parent.mkdir(parents=True, exist_ok=True)
    home.rename(target)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [moved] = payload["state"]["moved"]
    statement = _consolidated_return(demo_root)
    code, payload = scan(capsys, statement)
    assert code == 0, payload
    [answered] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
               stdin={"link": "https://drive.example/smith"})[0] == 0
    chased = chased_engagement(capsys, demo_root, name="Chased")
    card = reminder_card(capsys, chased)

    walked = _count_walks(monkeypatch)
    calls = [
        ("assign", engagement, {"original": parked["pbc_location"], "identifier": "D01",
                                "keyword": "mortgage notes", "seq": parked["seq"]}),
        ("restore", engagement, {"original": moved["pbc_location"], "seq": moved["seq"]}),
        ("mark-missing", statement, {"original": answered["pbc_location"], "identifier": "A02",
                                     "seq": answered["seq"]}),
        ("mark-shared", engagement, None),
        ("approve", chased, {"stage": card["stage"], "fingerprint": card["fingerprint"]}),
        ("reminder", chased, {}),
        ("state", engagement, None),
        ("edit", chased, {"items": payload_of_state(capsys, chased)["rules"],
                          "engagement": {"client": "Jane"}}),
    ]
    for command, folder, spec in calls:
        code, payload = run(capsys, command, api.ENGAGEMENT_FLAG, str(folder), stdin=spec)
        assert code == 0, (command, payload)
        assert "list" not in payload, command
    # The document assign filed goes back for review, and is then dismissed.
    [filed] = [e for e in payload_of_state(capsys, engagement)["index"]
               if e["decision"] == FILED and e["identifier"] == "D01"]
    code, payload = run(capsys, "unfile", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "seq": filed["seq"]})
    assert code == 0, payload
    assert "list" not in payload
    [parked] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    code, payload = run(capsys, "dismiss", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": parked["pbc_location"], "seq": parked["seq"]})
    assert code == 0, payload
    assert "list" not in payload
    assert walked == []


def test_sort_and_scan_ends_with_one_list_and_one_state(capsys, demo_root, monkeypatch):
    """Decision 203 (the lane's ruling on 194's Q5): the pass is the
    runner's, which walks the root once and prints no list; when it ends
    the app asks ``list`` once and ``state`` once, at the same time (P228) -
    the list is how a folder made by hand reaches the picker. Neither the
    pass's final line nor the state walks again."""
    engagement = chased_engagement(capsys, demo_root, name="Scanned")
    walked = _count_walks(monkeypatch)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    assert walked == [demo_root, demo_root], "the pass's walk, then the redraw's one list"
    assert payload["list"] == _the_list_now(capsys)
    assert api.PASS_COMMAND not in api.LIST_CHANGING


def test_no_command_outside_the_list_changing_ones_carries_the_list():
    """``LIST_CHANGING`` decides it (the review's S3): each command in it
    is a command whose function adds the list, no other function adds one,
    and under any other command :func:`api._with_list` walks nothing and
    adds nothing, whoever calls it. ``set-root`` is not one: the app starts
    again after it (R8)."""
    import inspect

    assert set(api.LIST_CHANGING) <= set(api.COMMANDS)
    assert "set-root" not in api.LIST_CHANGING
    adders = {name for name, fn in api.COMMANDS.items() if "_with_list(" in inspect.getsource(fn)}
    assert adders == set(api.LIST_CHANGING)
    # Read wherever the door's code sits (R3.1): api and every module a
    # command's function is written in; the one place is _with_list's.
    homes = {inspect.getsourcefile(api), *(inspect.getsourcefile(fn) for fn in api.COMMANDS.values())}
    source = "".join(Path(home).read_text(encoding="utf-8") for home in sorted(homes))
    assert source.count('["list"] =') == 1 and '"list":' not in source.replace('"list": _cmd_list', '')
    assert '["list"] =' in py_function("_with_list")
    try:
        for command in set(api.COMMANDS) - set(api.LIST_CHANGING):
            api._RUNNING["command"] = command
            assert api._with_list({}) == {}, command
    finally:
        api._RUNNING["command"] = ""


def test_the_list_a_write_carries_is_one_reading_after_the_write(capsys, demo_root, monkeypatch):
    """P209: the write is done, and what follows is the ``list`` command's
    own read, held as that command holds it (P118) - and the write itself
    is never inside the reading, which would refuse it."""
    from tracker import hold, store

    seen = {}
    real_payload, real_record = api._list_payload, store.record

    def drawn(*args, **kwargs):
        seen["list"] = hold._HOLDING
        return real_payload(*args, **kwargs)

    def recorded(*args, **kwargs):
        seen.setdefault("writes", set()).add(hold._HOLDING)
        return real_record(*args, **kwargs)

    monkeypatch.setattr(api, "_list_payload", drawn)
    monkeypatch.setattr(store, "record", recorded)
    code, payload = run(capsys, "create", stdin={
        "household": "Other Household", "return_name": "Smith 2025", "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 0, payload
    assert seen["list"] == hold.HOLD_READING and "list" in payload
    assert seen["writes"] == {""}, "the write is made before the reading, holding nothing"
    assert hold._HELD is None


def test_the_scheduled_tasks_working_folder_is_the_apps_own_not_the_settings_folder(tmp_path, monkeypatch):
    """Decision 185: the task's working folder is the app's own folder,
    whatever settings folder is named. Since decision 209 the one
    registration (``scheduling.register_here``) writes it, so it is asked
    there, of the task file it writes."""
    from tracker import scheduling, settings

    monkeypatch.setenv(settings.ENV_SETTINGS_DIR, str(tmp_path / "app"))
    monkeypatch.setattr(scheduling, "install_task", lambda xml, name=TASK_NAME: ["schtasks"])
    scheduling.register_here(settings.settings_dir())
    written = scheduling.schedule_xml_path().read_text(encoding=scheduling.SCHEDULE_XML_ENCODING)
    # The folder is written XML-escaped: an "&" in the office PC's path is "&amp;".
    assert f"<WorkingDirectory>{scheduling._xml_escape(settings.app_dir())}</WorkingDirectory>" in written
    assert settings.app_dir() != settings.settings_dir()


def _program_on(monkeypatch, kind):
    """Windows answers ``kind`` for the drive the program and its settings
    folder are on; the data home stays on the fixed disk, which it must."""
    from tracker import settings as settings_module

    program = {settings_module.app_dir(), settings_module.settings_dir().resolve()}
    monkeypatch.setattr(settings_module, "drive_type",
                        lambda path: kind if Path(path) in program else settings_module.DRIVE_FIXED)


def test_install_schedule_refuses_when_the_program_is_on_a_removable_drive(capsys, demo_root, monkeypatch):
    """Decision 186: the schedule runs whatever program sits where the app
    is, so the repair path refuses a stick - in 186's own sentence, as the
    step's first answer (decision 209: ``refused_drive``, a failure), before
    any file is written and before the task is registered."""
    from tracker import scheduling
    from tracker import settings as settings_module
    from tracker.scheduling import schedule_xml_path

    calls = _on_the_office_computer(monkeypatch)
    _program_on(monkeypatch, settings_module.DRIVE_REMOVABLE)
    code, payload = run(capsys, "install-schedule", stdin={})
    said = settings_module.PROGRAM_ON_REMOVABLE.format(folder=settings_module.app_dir())
    assert code == 0, payload
    assert payload["outcome"] == scheduling.REFUSED_DRIVE and payload["sentence"] == said
    assert payload["installed"] is False and said in payload["after_install"]["failed"]
    assert calls == []
    assert not schedule_xml_path().exists()


def test_install_schedule_refuses_a_network_drive_and_one_windows_cannot_name(capsys, demo_root, monkeypatch):
    from tracker import settings as settings_module

    _on_the_office_computer(monkeypatch)
    for kind, said in ((settings_module.DRIVE_REMOTE, settings_module.PROGRAM_ON_NETWORK),
                       (settings_module.DRIVE_UNKNOWN, settings_module.PROGRAM_DRIVE_UNKNOWN)):
        _program_on(monkeypatch, kind)
        code, payload = run(capsys, "install-schedule", stdin={})
        assert code == 0 and payload["installed"] is False, payload
        assert payload["sentence"] == said.format(folder=settings_module.app_dir())


def test_the_first_screen_says_when_the_app_runs_from_a_removable_drive(capsys, demo_root, monkeypatch):
    """Decision 186: the scheduled pass never refuses (it would go quiet),
    so the app's first screen says it every time it opens from a stick."""
    from tracker import settings as settings_module

    assert run(capsys, "list")[1]["machine_warnings"] == []
    _program_on(monkeypatch, settings_module.DRIVE_REMOVABLE)
    code, payload = run(capsys, "list")
    assert code == 0
    assert payload["machine_warnings"] == [
        settings_module.PROGRAM_ON_REMOVABLE.format(folder=settings_module.app_dir())]


def test_a_stale_redirected_copy_is_named_on_the_first_screen(capsys, demo_root, tmp_path, monkeypatch):
    """F7 (P193, R2): a copy of the data folder Windows kept for a package
    the app was once started inside is named, one sentence each, and never
    removed - it holds client-derived data."""
    from tracker import settings as settings_module

    local = tmp_path / "Local"
    copy = (local / settings_module.PACKAGES_DIR_NAME / "Claude_pzs8sxrjxfjjc" / "LocalCache"
            / "Local" / settings_module.DATA_HOME_NAME)
    copy.mkdir(parents=True)
    (copy / "tracker.db").write_bytes(b"made-up")
    monkeypatch.setattr(api, "redirected_copies", lambda: settings_module.redirected_copies(
        {"LOCALAPPDATA": str(local)}, windows=True))
    code, payload = run(capsys, "list")
    assert code == 0
    assert payload["machine_warnings"] == [settings_module.REDIRECTED_COPY.format(path=copy)]
    assert (copy / "tracker.db").read_bytes() == b"made-up"                 # named, never removed


def test_a_packages_folder_windows_will_not_list_is_one_sentence_and_the_rest_still_shows(
        capsys, demo_root, tmp_path, monkeypatch):
    """Combined review S2: a raw PermissionError used to fail the whole
    list reply; now the first screen says one sentence - the folder and
    the error's class - once, even when the probe said it too, and the
    rest of the reply still comes."""
    from tracker import settings as settings_module

    packages = tmp_path / "Local" / settings_module.PACKAGES_DIR_NAME
    said = settings_module.PACKAGES_UNREADABLE.format(folder=packages, error="PermissionError (EACCES)")

    def unreadable():
        raise settings_module.SettingsError(said)
    monkeypatch.setattr(api, "redirected_copies", unreadable)
    code, payload = run(capsys, "list")
    assert code == 0
    assert payload["machine_warnings"] == [said]
    assert payload["vocab"] and "households" in payload and "last_pass" in payload   # the rest still shows
    monkeypatch.setattr(api, "data_home", unreadable)
    assert run(capsys, "list")[1]["machine_warnings"] == [said]              # said once


def test_a_redirected_app_says_its_refusal_alone_not_also_a_copy_it_never_uses(
        capsys, demo_root, tmp_path, monkeypatch):
    """Combined review N3: while R1 refuses this process's data home, the
    copy this process sees is not named as one "the app never uses"."""
    from tracker import settings as settings_module

    refusal = settings_module.DATA_HOME_REDIRECTED.format(package="Claude_pzs8sxrjxfjjc",
                                                          product=settings_module.product_name())

    def redirected():
        raise settings_module.DataHomeRedirected(refusal)
    monkeypatch.setattr(api, "data_home", redirected)
    monkeypatch.setattr(api, "redirected_copies", lambda: [tmp_path / "copy"])
    assert run(capsys, "list")[1]["machine_warnings"] == [refusal]


# ----------------------------------------- Title Case for every drawn word (Jason, 2026-09-29) ----


def test_the_title_case_rule_does_what_jason_wrote():
    assert title_case("Could not Sort") == "Could Not Sort"
    assert title_case("Fits two requests") == "Fits Two Requests"
    assert title_case("Moved by hand") == "Moved by Hand"
    assert title_case("Nothing is waiting") == "Nothing Is Waiting"
    assert title_case("Take the tour") == "Take the Tour"
    assert title_case("Show in File Explorer") == "Show in File Explorer"
    assert title_case("Prior-year or substitute document accepted") == \
        "Prior-Year or Substitute Document Accepted"
    assert title_case("Correct; only formatting flagged") == "Correct; Only Formatting Flagged"
    assert title_case("{n} need you") == "{n} Need You"
    assert title_case("W-2 to review") == "W-2 to Review"
    assert title_case("Sort stopped: ran too long") == "Sort Stopped: Ran Too Long"
    assert title_case("Set aside") == "Set Aside" and title_case("Log in") == "Log In"
    # A small word that is neither first nor last is lower-cased, not just left alone.
    assert title_case("Waiting On Clients") == "Waiting on Clients"
    assert title_case("Waiting on Clients") == "Waiting on Clients"
    assert title_case("On Hold") == "On Hold" and title_case("Wait For") == "Wait For"


#: Drawn words that are cased on purpose, each with the reason. Machine
#: values, keys, commands, folder names, the record's own words and the
#: fragments a sentence is built from are not on the screen as headings.
_TITLE_EXEMPT_BRANCHES = (
    "commands", "path_kinds", "statuses", "evidence", "layout",
    "engagement_flag", "pass_command", "view.states", "schedule.draft_day", "reminder.letter_ink",
    "editor.date_fields", "editor.plain_columns", "editor.routing_columns",
    "editor.yes", "editor.no", "people.kinds", "people.outcomes",
    "review_labels.bucket_order", "review_labels.not_a_document", "household.editable",
    "shell.error_log",
    # the standing rules' headlines are quoted exactly in the docs (STANDING_RULES)
    "rules",
    # sentences over the limit, and the fragments a sentence splices in
    "origin_",
    "labels.Not asked", "not_asked_label", "override_reasons",
)


#: Exact drawn strings, by path, cased on purpose. Each is exempt alone, never
#: its branch: anything else beside it must still be in Title Case.
_TITLE_EXEMPT_STRINGS = {
    ("columns[13].label", "Short name"):
        "a record column's own name, shown as record data (manifest.COL_SHORT_TITLE)",
    # Fragments spliced into a longer line (ledger default 5, pending Jason):
    # they are never on the screen on their own.
    ("triage.places.title", "in the title"): "fragment spliced into a longer reason line",
    ("triage.places.footer", "in the page {page} footer"): "fragment spliced into a longer reason line",
    ("triage.places.first_page", "on page {page}"): "fragment spliced into a longer reason line",
    ("triage.places.deep", "on page {page}"): "fragment spliced into a longer reason line",
    # The new-return dialog's heading splices it between the form and Ask the Taxpayer (R5.5).
    ("request_list", "request list"): "fragment spliced into the new-return dialog's heading, as it has always read",
    ("scan.complete", "Pass complete \u2014 {did}.   {summary}"):
        "a sentence with a dash and two placeholders, over the five-word limit once filled",
    ("scan.filed", "Filed {n}"): "piece spliced into the Pass complete line ({did})",
    ("scan.review", "{n} to Review"): "piece spliced into the Pass complete line ({did})",
    ("scan.syncing", "{n} Still Syncing"): "piece spliced into the Pass complete line ({did})",
    # SPEC 7 cuts the editor's help lines from the screen; the Active warning is kept and is Title Case.
    ("editor.engagement_fields[0].help", "greeting name in the reminder"): "help line SPEC 7 cuts from the screen",
    ("editor.engagement_fields[2].help", "pasted into the reminder"): "help line SPEC 7 cuts from the screen",
    ("editor.engagement_fields[5].help", "who the reminder is from"): "help line SPEC 7 cuts from the screen",
}


def _drawn_words(vocab):
    def walk(value, path):
        if isinstance(value, str):
            yield path, value
        elif isinstance(value, dict):
            for key, inner in value.items():
                yield from walk(inner, f"{path}.{key}" if path else str(key))
        elif isinstance(value, (list, tuple)):
            for n, inner in enumerate(value):
                yield from walk(inner, f"{path}[{n}]")
    yield from walk(vocab, "")


def test_every_drawn_word_the_vocabulary_carries_is_in_title_case(capsys, demo_root):
    bad = []
    for path, text in _drawn_words(api.vocab()):
        if len(text.split()) > 5 or " " not in text.strip():
            continue        # one word is a name or a key; over five words is a sentence
        if path.endswith((".key", ".value")) or any(part in path for part in _TITLE_EXEMPT_BRANCHES):
            continue
        if (path, text) in _TITLE_EXEMPT_STRINGS:
            continue
        if title_case(text) != text:
            bad.append((path, text, title_case(text)))
    assert not bad, bad


#: The drawn words that still say "Client" (pilot P196, SPEC-taxpayer-words
#: R3): each names a folder on disk, whose own name is ``Clients``.
_FOLDER_WORDS = {"Change Clients Folder…", "Open Clients Folder", "Open Client Folder",
                 "Choose Your Clients Folder", "Clients Folder"}
#: P196's one exception: the override menu shows the reasons as stored, and
#: the first of them is a stored value that says "Client" (SPEC-error-handling-small
#: section 13). The editor draws a stored value as it is stored, so the word
#: is the record's, not a screen's. Exempted by its exact text, written out
#: here and asserted to be one of the manifest's reasons, so a reworded or
#: removed reason is a failure, not a silent pass; a second "Client" in that
#: menu still fails the guard.
_STORED_REASON_WITH_CLIENT = "Client confirmed this is the final version"


def test_no_word_the_window_draws_says_client_but_a_folders_own_name(capsys, demo_root):
    """P196: the person is the Taxpayer, the listed household a Household;
    only a button naming a folder on disk keeps the folder's word."""
    # The exemption is the literal text, so a reworded or removed reason
    # fails here instead of being exempted silently (SPEC-error-handling-small
    # section 14).
    assert _STORED_REASON_WITH_CLIENT in manifest.OVERRIDE_REASONS
    vocab = api.vocab()
    drawn = [("menu", vocab["menu"]), ("screen", vocab["screen"]), ("reasons", vocab["reasons"]),
             ("ask_the_client", vocab["ask_the_client"]),
             ("engagement_fields", [f["label"] for f in vocab["editor"]["engagement_fields"]]),
             # the editor draws a help line only beside its yes/no boxes (app.js renderEngagementFields)
             ("engagement_help", [f["help"] for f in vocab["editor"]["engagement_fields"]
                                  if f["editable"] and f["key"] in ("reminders", "active")]),
             ("settings.root_label", vocab["settings"]["root_label"]),
             ("open_client_folder", screen_words.OPEN_CLIENT_FOLDER_LABEL),
             ("override_reasons", vocab["override_reasons"])]
    said = [(where + path, text) for where, branch in drawn for path, text in _drawn_words(branch)
            if "client" in text.lower() and text not in _FOLDER_WORDS
            and (where, text) != ("override_reasons", _STORED_REASON_WITH_CLIENT)]
    assert not said, said
    assert vocab["screen"]["sections"]["clients"] == vocab["menu"]["clients"] == "Households"
    assert vocab["screen"]["side"]["types"] == "Taxpayer Types"


def test_the_editor_says_taxpayer_where_the_record_keeps_client():
    """P196 R7: the record and the files it writes keep their label; only
    the editor's word for the greeting name changes."""
    [field] = [f for f in api.vocab()["editor"]["engagement_fields"] if f["key"] == "client"]
    assert field["label"] == "Taxpayer"
    assert ENGAGEMENT_LABELS["client"] == "Client"


def test_the_notices_carry_a_short_word_for_every_kind_the_pages_show():
    """S4's missing keys: each notice has five words or fewer, in Title Case, and no path."""
    notices = api.vocab()["screen"]["notices"]
    assert {k: notices[k] for k in ("reader", "machine", "renamed", "paused", "feed", "drive")} == {
        "reader": "Install Folder Name Too Long", "machine": "Machine Needs Attention",
        "renamed": "Folder Renamed", "paused": "Two Years Open; Sorting Paused",
        "feed": "Prior Year Data Not Found", "drive": "Drive Not Signed In"}
    for key, text in notices.items():
        assert len(text.replace(";", "").split()) <= 5 and title_case(text) == text, (key, text)
        assert "/" not in text and "\\" not in text and ":" not in text[1:3], (key, text)


def test_every_title_exception_is_an_exact_string_that_is_really_drawn_with_a_reason():
    drawn = set(_drawn_words(api.vocab()))
    for (path, text), reason in _TITLE_EXEMPT_STRINGS.items():
        assert (path, text) in drawn, (path, text)
        assert len(reason) > 20, (path, text)
    # The Active warning is drawn, so it is not exempt and is in Title Case.
    assert ("editor.engagement_fields[8].help", "No: Sorting Skips This Return") in drawn
    assert not [k for k in _TITLE_EXEMPT_STRINGS if k[0] == "editor.engagement_fields[8].help"]
    assert title_case("No: Sorting Skips This Return") == "No: Sorting Skips This Return"


def test_the_title_case_test_can_fail(monkeypatch):
    monkeypatch.setitem(reasons.SHORT_REASONS, "unmatched", "Could not Sort")
    assert title_case(reasons.SHORT_REASONS["unmatched"]) != reasons.SHORT_REASONS["unmatched"]


def test_list_carries_each_misfits_code_and_the_vocabulary_words_it(capsys, demo_root):
    from tracker.api import vocab

    (demo_root / "Archive").mkdir()
    code, payload = run(capsys, "list")
    assert code == 0
    [misfit] = [m for m in payload["misfits"] if Path(m["path"]).name == "Archive"]
    assert misfit["code"] == "not_a_tree"
    assert misfit["sentence"] and misfit["where"]
    assert vocab()["screen"]["misfits"]["reasons"][misfit["code"]] == "Unknown Folder"


def test_a_record_rewritten_at_its_own_size_and_time_is_seen_once_anything_else_moves(
        capsys, demo_root, monkeypatch):
    """P212, Jason's trade of 2026-10-07, reversing the review's SHOULD-2
    (probe P15): a record rewritten at the same length with its time put
    back breaks its chain, and the whole walk says Could Not Be Read; the
    cached reply, judging the record by its size and time, keeps what it
    had until anything else in the household moves (or the next day's head,
    which reads every household again) - and then says what the walk says."""
    mixed, before, whole = _a_record_rewritten_with_its_size_and_time_put_back(capsys, demo_root, monkeypatch)
    assert _cached_firm(capsys) == before, "size and time put back: the cache keeps what it had"
    # Another file of the same household moves - here the household's own
    # record, one folder up from the year - and the household is read again.
    household_record = ledger.path_for(mixed.parent.parent)
    os.utime(household_record, (_AGED_AT - 60, _AGED_AT - 60))
    assert _cached_firm(capsys) == whole, "once anything else in it moves, the household is read again"


def test_a_record_rewritten_at_its_own_size_and_time_is_seen_the_next_day(capsys, demo_root, monkeypatch):
    """P212's bound: the head carries the day, so the first reply of the
    next day reads every household again and says what the whole walk says."""
    _mixed, before, _whole = _a_record_rewritten_with_its_size_and_time_put_back(capsys, demo_root, monkeypatch)
    assert _cached_firm(capsys) == before

    import types

    class Tomorrow(dt.date):
        @classmethod
        def today(cls):
            return dt.date.fromordinal(dt.date.today().toordinal() + 1)

    # Tomorrow for the API, which hands the day to every firm row - and
    # for firm_view and request_edit, which read the same ``dt`` (a stand-in
    # follows the name's readers) - and for nothing else.
    for module in (api, firm_view, request_edit):
        monkeypatch.setattr(module, "dt", types.SimpleNamespace(**{**vars(dt), "date": Tomorrow}))
    tomorrow = _firm_whole(capsys, monkeypatch)
    assert _cached_firm(capsys) == tomorrow and tomorrow != before


def _a_record_rewritten_with_its_size_and_time_put_back(capsys, demo_root, monkeypatch):
    """The practice cached, then one return's record rewritten at the same
    length with its time put back (probe P15): the chain breaks, and the
    whole walk says Could Not Be Read. Returns the return, the cached reply
    from before, and the whole walk's reply now."""
    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    before = _cached_firm(capsys)
    assert before == _firm_whole(capsys, monkeypatch)
    record = ledger.path_for(mixed)
    kept = record.stat()
    text = record.read_bytes()
    assert b'"active": true' in text
    record.write_bytes(text.replace(b'"active": true', b'"active":false', 1))
    os.utime(record, ns=(kept.st_atime_ns, kept.st_mtime_ns))
    assert record.stat().st_size == kept.st_size
    whole = _firm_whole(capsys, monkeypatch)
    assert {one["path"]: one["problem"] for one in whole["returns"]}[str(mixed)] == firm_view.FIRM_UNREADABLE
    return mixed, before, whole


def test_the_first_overview_after_a_pass_reads_no_household_again(capsys, demo_root, monkeypatch):
    """The review's SHOULD-4: a pass rewrites each return's status page and
    moves its folders' times with its lock; nothing the firm view reads
    changed, so the next reply reads no return."""
    from tracker.view import VIEW_FILENAME

    mixed, quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    assert _cached_firm(capsys) == whole
    for folder in (mixed, quiet):
        (folder / VIEW_FILENAME).write_text("<p>drawn again by the pass</p>", encoding="utf-8")
        (folder / "held by the pass.tmp").write_text("x", encoding="utf-8")
        (folder / "held by the pass.tmp").unlink()
    read = _rows_read(monkeypatch)
    assert _cached_firm(capsys) == whole
    assert read == []


def test_every_file_a_firm_reply_opens_is_in_the_fingerprint_and_never_the_status_page(
        capsys, demo_root, monkeypatch):
    """What the fingerprint leaves out (``firm_view.FIRM_JUDGED``) is pinned to
    what the firm view opens: a page it leaves out must be one it never
    opens, and every file it does open is judged by its size and time
    (P212), inside the household's two folders."""
    import sys

    from tracker import reminder
    from tracker.view import VIEW_FILENAME

    mixed, quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    for folder in (mixed, quiet):
        (folder / reminder.DRAFT_FILENAME).write_text("Dear client", encoding="utf-8")
    opened = []
    root = str(demo_root.resolve()).lower()

    def watch(event, args):
        if event == "open" and isinstance(args[0], (str, os.PathLike)):
            where = os.path.abspath(os.fsdecode(args[0]))
            if where.lower().startswith(root):
                opened.append(Path(where))

    sys.addaudithook(watch)
    try:
        whole = _firm_whole(capsys, monkeypatch)
    finally:
        root = "\0"                          # an audit hook cannot be removed; it stops matching
    assert whole["returns"] and opened
    from tracker import firm_cache
    from tracker.layout import CLIENTS_TREE

    judged = firm_view.FIRM_JUDGED
    for place in opened:
        assert place.name != VIEW_FILENAME
        # Its names below its household's folder, in the tree it is in: the
        # place must be in one of the household's two folders, and never one
        # the fingerprint leaves out.
        tree, _household, *below = place.relative_to(demo_root.resolve()).parts
        assert tree in (PRIVATE_TREE, CLIENTS_TREE) and below, place
        assert not firm_cache._at(judged.private_left_out, tuple(below)), place


@pytest.mark.parametrize("dropped", ["a file", "a folder holding a file"])
def test_a_client_drop_named_like_the_status_page_is_seen_by_the_cache(capsys, demo_root, monkeypatch, dropped):
    """The re-check's MUST-R1: a client who forwards the firm's page back, as
    a file or inside a folder of that name, has a file waiting in the inbox;
    the cached reply holds the draft for it exactly as the whole walk does."""
    from tracker.view import VIEW_FILENAME

    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    assert _cached_firm(capsys) == _firm_whole(capsys, monkeypatch)
    inbox = inbox_of(mixed)
    if dropped == "a file":
        (inbox / VIEW_FILENAME).write_text("<p>forwarded back</p>", encoding="utf-8")
    else:
        (inbox / VIEW_FILENAME).mkdir()
        (inbox / VIEW_FILENAME / "w2.pdf").write_bytes(b"%PDF-1.4 made up")
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    assert {one["path"]: one["draft"]["held"] for one in whole["returns"]}[str(mixed)] >= 1
    assert _cached_firm(capsys) == whole


# ----------------------------- P276 (SPEC-ui-menu-speed §3): the engine's commands ----


def _commands_that_reach(*targets: tuple[str, str]) -> set[str]:
    """Every command whose handler in ``tracker/api.py`` reaches one of the
    ``(module, function)`` calls named, through the API's own functions by name,
    to a fixed point - as :func:`_writers_in_the_package` derives the writers."""
    import ast
    from pathlib import Path

    tree = ast.parse((Path(__file__).resolve().parents[1] / "tracker" / "api.py").read_text(encoding="utf-8"))
    calls: dict[str, set[str]] = {}
    reaches: set[str] = set()
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef):
            continue
        named = calls.setdefault(node.name, set())
        for call in (one for one in ast.walk(node) if isinstance(one, ast.Call)):
            func = call.func
            if isinstance(func, ast.Attribute):
                named.add(func.attr)
                if isinstance(func.value, ast.Name) and (func.value.id, func.attr) in targets:
                    reaches.add(node.name)
            elif isinstance(func, ast.Name):
                named.add(func.id)
    grew = True
    while grew:
        grew = False
        for name, called in calls.items():
            if name not in reaches and called & reaches:
                reaches.add(name)
                grew = True
    return {command for command, handler in api.COMMANDS.items() if handler.__name__ in reaches}


def test_own_process_commands_are_every_command_that_runs_a_pass_or_the_after_install_step():
    """P276: a pass, and the after-install step (which can take minutes on a
    streamed Drive folder), get a process of their own. Derived from the
    handlers - those that reach ``runner.main`` or the step's ``run`` or
    ``launch`` - never listed by hand, so a command a later decision gives the
    step is caught here. ``set-schedule`` and ``set-root`` save a choice and
    then run the step, so they are among them."""
    derived = _commands_that_reach(("runner", "main"), ("after_install", "run"), ("after_install", "launch"))
    assert {api.PASS_COMMAND, "after-install", "install-schedule", "move-schedule-here"} <= derived
    assert derived == set(api.OWN_PROCESS_COMMANDS)
    assert api.OWN_PROCESS_COMMANDS <= set(api.COMMANDS)
    assert not api.OWN_PROCESS_COMMANDS & api.HELD_READING_COMMANDS


def test_the_vocabulary_names_the_own_process_commands(capsys, demo_root):
    code, listed = run(capsys, "list")
    assert code == 0
    assert listed["vocab"]["own_process_commands"] == sorted(api.OWN_PROCESS_COMMANDS)
    assert listed["vocab"]["pass_command"] in listed["vocab"]["own_process_commands"]


def test_the_spare_is_gone_and_the_failure_sayer_is_public():
    """P276 retired P220's ``--spare`` (the engine, ``tracker.resident``, is its
    successor) and made ``_say_failure`` public for it."""
    assert not hasattr(api, "SPARE_FLAG") and not hasattr(api, "spare") and not hasattr(api, "SPARE_LINE_MAX")
    assert callable(api.say_failure) and not hasattr(api, "_say_failure")


#: What ``import tracker.api`` may open or list (P220): the interpreter's
#: own files, its packages, the checkout's ``tracker/`` - and a folder on the
#: import path, which the import system lists to find a module.
_IMPORT_PROBE = """
import json, os, sys, sysconfig
# Asked before the hook is up: on a Mac ``sysconfig`` reads the system's own
# SystemVersion.plist for its platform tag, which is the probe's open, not
# the API's.
roots = {sys.prefix, sys.base_prefix, sys.exec_prefix, *(p for p in sysconfig.get_paths().values())}
seen = []
def hook(event, args):
    if event in ("open", "os.listdir", "os.scandir") and args and isinstance(args[0], (str, bytes, os.PathLike)):
        seen.append((event, os.fsdecode(args[0])))
sys.addaudithook(hook)
import tracker.api
print(json.dumps({"seen": seen, "roots": sorted(roots), "path": sys.path}))
"""


def test_importing_the_api_opens_no_file_but_the_programs_own():
    """P220, P276: the engine is the API imported before the click, so importing it
    must read nothing a command would read differently later - no settings
    file, no data folder, no clients root: every file opened and every
    folder listed is the interpreter's, its packages', the checkout's
    ``tracker/``, or a folder on the import path."""
    import os
    import subprocess
    import sys

    from tests.plugin_session import REPO, TRIPWIRE_DIR, child_env

    done = subprocess.run([sys.executable, "-c", _IMPORT_PROBE], cwd=REPO,
                          env=child_env(TRACKER_PRODUCT_NAME="Fabricated Product"),
                          capture_output=True, text=True, timeout=180)
    assert done.returncode == 0, done.stderr
    said = json.loads(done.stdout.splitlines()[-1])
    # The suite's own tripwire (decision 185) is loaded first in every child.
    own = [os.path.realpath(root) for root in said["roots"]] + [
        os.path.realpath(REPO / "tracker"), os.path.realpath(TRIPWIRE_DIR)]
    on_the_path = {os.path.realpath(entry or REPO) for entry in said["path"]}
    strays = []
    for event, place in said["seen"]:
        real = os.path.realpath(os.path.join(REPO, place))
        if event != "open" and real in on_the_path:
            continue
        if not any(real == root or real.startswith(root + os.sep) for root in own):
            strays.append((event, place))
    assert strays == []


#: Everything at a module's top level that asks the machine (P220): the
#: environment, the clock, the disk, the program's place - by the calls and
#: values that do, and the settings' own questions.
_ASKS_BY_CALL = frozenset({
    "getenv", "now", "today", "time", "monotonic", "perf_counter", "read_text", "read_bytes", "open",
    "resolve", "cwd", "home", "exists", "is_file", "is_dir", "iterdir", "stat", "lstat", "listdir",
    "scandir", "glob", "rglob", "expanduser", "getcwd", "gethostname", "getpid", "urandom", "getuser",
    "node", "localtime", "product_name", "data_home", "settings_dir", "settings_path", "clients_root",
    "app_dir", "program_folders", "default_data_home", "schedule_preference", "firm",
    "beside_the_program", "resolved", "_read"})
_ASKS_BY_VALUE = frozenset({"environ", "__file__", "executable", "argv"})


def _fixed_at_import() -> set[tuple[str, str]]:
    """Each ``(module file, name)`` a top-level statement of ``tracker/``
    binds from the machine, following calls into the module's own
    functions; ``if __name__ == "__main__"`` blocks are a command line's."""
    import ast

    from tests.plugin_session import REPO

    def asks(node, defined, seen):
        for sub in ast.walk(node):
            if isinstance(sub, ast.Call):
                func = sub.func
                name = func.id if isinstance(func, ast.Name) else getattr(func, "attr", None)
                if name in _ASKS_BY_CALL:
                    return True
                if isinstance(func, ast.Name) and func.id in defined and func.id not in seen:
                    seen.add(func.id)
                    if asks(defined[func.id], defined, seen):
                        return True
            elif (isinstance(sub, ast.Attribute) and sub.attr in _ASKS_BY_VALUE) or (
                    isinstance(sub, ast.Name) and sub.id in _ASKS_BY_VALUE):
                return True
        return False

    fixed = set()
    for path in sorted((REPO / "tracker").glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        defined = {node.name: node for node in tree.body
                   if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef))}
        for node in tree.body:
            if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef, ast.Import,
                                 ast.ImportFrom)):
                continue
            if isinstance(node, ast.If) and "__main__" in ast.unparse(node.test):
                continue
            if asks(node, defined, set()):
                targets = getattr(node, "targets", None) or [getattr(node, "target", None)]
                fixed |= {(path.name, ast.unparse(target)) for target in targets if target is not None}
                if not any(targets):
                    fixed.add((path.name, f"line {node.lineno}"))
    return fixed


def test_only_the_task_name_and_the_programs_own_place_are_fixed_at_import():
    """P220, P276: the engine imports the API before its commands, so what a module
    works out at import must be the same for a fresh command and the engine.
    The true list (an AST scan of every module's top level): the product's
    name - the scheduled task's, and the side panel's word in ``SCREEN`` -
    from the environment the shell gives both alike, and the program's own
    place, twice. Nothing reads the clock, the settings file, the data
    folder or the clients root at import."""
    assert _fixed_at_import() == {("scheduling.py", "TASK_NAME"), ("screen_words.py", "SCREEN"),
                                  ("settings.py", "PACKAGE_JSON"), ("after_install.py", "CHECKOUT")}


# ── P265-P280 (SPEC-ui-menu-small) ───────────────────────────────────────

def _wording_rows() -> dict[str, list[str]]:
    rows = [line.split("\t") for line in
            (Path(__file__).resolve().parents[1] / "pilot" / "wording-shell.tsv").read_text(encoding="utf-8").splitlines()]
    return {row[1]: row for row in rows if len(row) > 4}


def test_the_side_panels_unbuilt_items_have_short_names_and_one_soon_word():
    """P265: each unbuilt page is a short name with a "Soon" tag; the longer
    "Under Construction" is its tooltip and description, said once."""
    side = screen_words.SCREEN["side"]
    assert side["soon"] == {"ready_to_sign": "Ready to Sign", "family_entities": "Family Entities", "personal_trusts": "Personal Trusts",
                            "corporate_entities": "Corporate Entities", "portal_settings": "Portal Settings"}
    assert not any("Under Construction" in said for said in side["soon"].values())
    assert side["soon_tag"] == "Soon" and side["under_construction"] == "Under Construction"
    assert "brand" not in side, "P266: nothing draws the firm's name in the panel"
    rows = _wording_rows()
    for key, said in side["soon"].items():
        assert rows[f"side.soon.{key}"][4] == said, key
    assert rows["side.soon_tag"][4] == "Soon"
    assert rows["side.brand"][3] == "cut" and rows["side.brand"][4] == ""


def test_the_sort_buttons_words_are_the_apis_and_its_tooltip_says_what_it_sorts():
    """P274: the Sort Now button's five words are the API's; the new tooltip
    says what the button sorts, and the firm pages' "Open a Household to
    Sort" is cut (those pages have no sort control). Only the new and the cut
    words have rows in the wording table: the unchanged ones never did."""
    sort = screen_words.SCREEN["sort"]
    assert set(sort) == {"now", "stop", "locked", "stopping", "tip"}
    assert sort["tip"] == "Sort This Household's Inbox"
    assert sort["now"] == "Sort Now" and sort["stop"] == "Stop Sorting"
    rows = _wording_rows()
    assert rows["sort.tip"][4] == sort["tip"]
    assert rows["sort.firm"][3] == "cut" and rows["sort.firm"][4] == ""


# ── P271-P273, P275 (SPEC-ui-menu-layout) ────────────────────────────────

def test_the_compact_rows_word_is_in_the_menu_and_the_wording_table():
    """P271: View > Compact Rows is a check item with an access key; its word
    is the API's and has a row in the wording table."""
    assert screen_words.MENU["compact_rows"] == "&Compact Rows"
    assert _wording_rows()["compact_rows"][4] == screen_words.MENU["compact_rows"]


def test_the_household_card_words_are_in_the_screen_vocabulary_and_the_wording_table():
    """P275: the household page's card is drawn from the API's five words (and
    the existing Shared and Not Shared); the page types none. Each has a row in
    the wording table, and Contact {name}, which nothing reads once the caption
    is the card, is gone."""
    screen = api.vocab()["screen"]
    card = screen["household_card"]
    assert card == {"contact": "Contact", "shared_with": "Shared With", "inbox_link": "Inbox Link", "link_saved": "Saved", "no_link": "Not Saved"}
    assert screen["shared"] == "Shared" and screen["not_shared"] == "Not Shared"
    assert "contact" not in screen, "screen.contact had no reader once the caption went (P275)"
    rows = _wording_rows()
    for key, said in card.items():
        assert rows[f"household_card.{key}"][4] == said, key
        assert len(said.split()) <= 5
