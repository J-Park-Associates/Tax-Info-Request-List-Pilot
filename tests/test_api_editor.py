"""Tests for tracker/api.py: the engagement's details and the request list's editor.

Engagement details, edit, lock and names, accepted and not asked (decision 142), short names (decision 144), a save
that keeps what it did not change (decision 160) and the form's inputs.

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import json
from pathlib import Path

import pytest

import tracker.api as api
import tracker.household_edit as household_edit
import tracker.request_edit as request_edit
from tests import api_driver
from tests.api_driver import (
    _SPELLING_REFUSED,
    COUNTS,
    HOUSEHOLD,
    _rows_of,
    client_readme,
    one_reply,
    payload_of_state,
    run,
    sample_engagement,
    scan,
    where,
)
from tests.builders import make_engagement
from tests.node_harness import APP_SCRIPTS, js_function, renderer_text
from tests.samples import text_pdf
from tracker import layout, ledger, screen_words, store
from tracker.households import load_household_info
from tracker.index import FILED, NEEDS_REVIEW, read_index
from tracker.layout import inbox_of
from tracker.locking import STALE_LOCK_SECONDS, lock_line, this_host
from tracker.manifest import (
    COL_DATE_PATTERN,
    COL_EXPECTED_COUNT,
    ManifestError,
    Status,
    load_engagement_info,
    load_manifest,
)
from tracker.records import ENGAGEMENT_LABELS
from tracker.scaffold import PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.templates import default_tax_year

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ------------------------------------------------------- engagement details ----


def test_create_records_the_engagement_details_the_scheduled_run_reads(capsys, demo_root):
    from tracker.registry import discover_engagements

    spec = {"household": HOUSEHOLD, "return_name": "Smith Family 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/abc", "due": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["client"] == "John Smith"
    assert payload["state"]["engagement"]["due"] == "2026-04-15"
    [found] = discover_engagements(demo_root).engagements
    assert found.client == "John Smith" and found.link == "https://drive.example/abc"
    from tracker.settings import firm
    assert found.firm == firm() and found.reminders is True
    assert found.name == ""          # the folder is the name; nothing to drift


def test_create_records_the_catalog_the_wizard_chose_and_state_carries_it(capsys, demo_root):
    """Decision 86: the engagement says which checklist it was cut from, in
    the record and in the state the app draws from."""

    spec = {"household": HOUSEHOLD, "return_name": "Willow Inc 2025", "form": "1120S", "client": "Willow Inc",
            "items": [t for t in api.FORM_TEMPLATES["1120S"] if t["core"]]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == "1120S"
    assert load_engagement_info(where(demo_root, "Willow Inc 2025")).form == "1120S"


def test_an_engagement_created_without_a_form_says_nothing_rather_than_guessing(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == ""


def test_rollover_carries_the_catalog_the_prior_was_cut_from(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    assert payload["state"]["engagement"]["form"] == "1040"


def test_rollover_carries_the_client_but_not_last_years_link_or_due(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "client": "John Smith",
            "link": "https://drive.example/old", "due": "2026-04-15", "sender": "Jason",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    info = payload["state"]["engagement"]
    assert info["client"] == "John Smith" and info["sender"] == "Jason"
    # The inbox is the household's and does not change from one year to the
    # next (decision 125), so the link the household holds is refilled
    # rather than left blank for somebody to paste again.
    assert info["link"] == "https://drive.example/old"
    # Last year's due date does not carry either: what is there is this
    # year's own default (decision 117), never the date twelve months gone.
    assert info["due"] != "2026-04-15"
    assert info["name"] == ""                      # the folder is the name
    assert payload["created"] == f"{HOUSEHOLD} 2026 Smith 2025"


def test_a_bad_due_date_is_a_sentence(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "X", "due": "next friday", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1
    # The sentence names the field by the label the editor shows, so the
    # two dates are refused in the same words (decision 117).
    assert payload["error"] == f"{ENGAGEMENT_LABELS['due']} must be YYYY-MM-DD, got 'next friday'"
    assert not (where(demo_root, "X")).exists()
    bad = {"household": HOUSEHOLD, "return_name": "X", "form": "1040", "filing_deadline": "april",
           "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=bad)
    assert code == 1
    assert payload["error"] == f"{ENGAGEMENT_LABELS['filing_deadline']} must be YYYY-MM-DD, got 'april'"


def test_create_defaults_both_dates_from_the_form_and_the_year_and_leaves_them_editable(capsys, demo_root):
    """Decision 117: the reminder's ladder is measured against the Due
    Date, so a new engagement has one without anybody typing it - the
    form's own filing deadline, and the firm's ask-by target before it.
    Both are ordinary details afterwards, and a date the wizard was given
    is never written over."""
    from tracker.templates import ask_by_for, filing_deadline_for

    spec = {"household": HOUSEHOLD, "return_name": "Willow 2025", "form": "1040", "year": 2025, "client": "Willow",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    deadline = filing_deadline_for("1040", 2025)
    info = payload["state"]["engagement"]
    assert info["filing_deadline"] == deadline.isoformat()
    assert info["due"] == ask_by_for(deadline).isoformat()
    assert load_engagement_info(where(demo_root, "Willow 2025")).filing_deadline == deadline

    # What a person typed wins over the default, and both stay editable.
    typed = {**spec, "return_name": "Typed 2025", "due": "2026-03-01", "filing_deadline": "2026-04-18"}
    code, payload = run(capsys, "create", stdin=typed)
    assert code == 0, payload
    assert payload["state"]["engagement"]["due"] == "2026-03-01"
    assert payload["state"]["engagement"]["filing_deadline"] == "2026-04-18"

    # A form the catalog has no deadline for fills nothing, rather than guessing.
    none = {"household": HOUSEHOLD, "return_name": "No Form 2025", "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=none)
    assert code == 0, payload
    assert payload["state"]["engagement"]["filing_deadline"] == ""
    assert payload["state"]["engagement"]["due"] == ""


def test_the_editor_saves_and_clears_the_filing_deadline(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "form": "1040", "year": 2025,
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"filing_deadline": "2026-04-20"}})
    assert code == 0, payload
    assert payload["saved"]["engagement"] == ["filing_deadline"]
    assert payload["state"]["engagement"]["filing_deadline"] == "2026-04-20"

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"filing_deadline": ""}})
    assert code == 0, payload
    assert payload["state"]["engagement"]["filing_deadline"] == ""
    assert load_engagement_info(engagement).filing_deadline is None


def test_rollover_clears_the_filing_deadline_and_redefaults_it_for_the_new_year(capsys, demo_root):
    """A statutory date belongs to its year. Last year's does not carry,
    and the new year's comes from the same table the wizard used."""
    from tracker.templates import ask_by_for, filing_deadline_for

    spec = {"household": HOUSEHOLD, "return_name": "Smith 2025", "form": "1040", "year": 2025, "client": "John Smith",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    prior = load_engagement_info(where(demo_root, "Smith 2025"))
    assert prior.filing_deadline == filing_deadline_for("1040", 2025)

    code, payload = run(capsys, "rollover", stdin={"prior": str(where(demo_root, "Smith 2025")), "year": 2026})
    assert code == 0, payload
    deadline = filing_deadline_for("1040", 2026)
    info = payload["state"]["engagement"]
    assert info["filing_deadline"] == deadline.isoformat() != prior.filing_deadline.isoformat()
    assert info["due"] == ask_by_for(deadline).isoformat()


# ---------------------------------------------------- edit, lock and names ----


def test_an_invalid_row_is_refused_by_the_api_with_the_row_and_column_named_and_nothing_is_recorded(capsys, demo_root):
    from tests.builders import k1_rows
    from tracker.records import rule_to_json

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    before = ledger.path_for(engagement).read_bytes()
    rows = payload_of_state(capsys, engagement)["rules"]

    bad = [dict(rows[0]), {**rows[1], "expected_count": "two"}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": bad, "engagement": {}})
    assert code == 1
    assert payload["error"] == f"Row 2: {COL_EXPECTED_COUNT} {COUNTS}"
    assert ledger.path_for(engagement).read_bytes() == before
    assert payload_of_state(capsys, engagement)["rules"] == rows

    nesting = [rule_to_json(i) for i in k1_rows(("F02", "Ashford"), ("F03", "Ashford Holdings"))]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": nesting, "engagement": {}})
    assert code == 1 and "F02" in payload["error"] and "F03" in payload["error"]
    assert ledger.path_for(engagement).read_bytes() == before

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"rolled_from": "last year"}})
    assert code == 1 and payload["error"] == "'rolled_from' is not edited here"
    assert ledger.path_for(engagement).read_bytes() == before
    assert payload_of_state(capsys, engagement)["rules"] == rows


def test_edit_saves_the_list_and_the_details_as_one_event_and_says_what_moved(capsys, demo_root):
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "client": "John", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "A02", "document": "1098", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]

    # The editor's rows: the file types as a string, a new row typed with
    # nothing but a name and a keyword, and one row gone.
    edited = [
        {**rows[0], "allowed_extensions": "pdf, jpg", "any_keywords": "wage statement"},
        {"identifier": "Z01", "document": "Rental Records", "period": "TY2025", "any_keywords": "schedule e"},
    ]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": edited, "engagement": {"client": "Jane", "reminders": False}})
    assert code == 0, payload
    assert payload["saved"] == {"changed": ["A01", "Z01"], "removed": ["A02"],
                                "engagement": ["client", "reminders"], "recorded": True}
    assert payload["warnings"] == []
    state = payload["state"]
    assert [r["identifier"] for r in state["rules"]] == ["A01", "Z01"]
    assert state["rules"][0]["allowed_extensions"] == ["pdf", "jpg"]
    assert state["rules"][1]["row"] == 2 and state["rules"][1]["date_pattern_derived"] is True
    assert state["engagement"]["client"] == "Jane" and state["engagement"]["reminders"] is False
    events = [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == ledger.RULES_CHANGED]
    assert len(events) == 2 and events[-1][ledger.REMOVED_KEY] == ["A02"]

    # The same list again records nothing, and says so.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": state["rules"], "engagement": {"client": "Jane"}})
    assert code == 0 and payload["saved"]["recorded"] is False
    assert len(ledger.read_events(engagement)) == 2


def test_the_editor_clears_a_detail_it_sends_blank_and_keeps_one_it_leaves_out(capsys, demo_root):
    """A person who empties the Link box means the link to go: for ``edit``
    a key present with a blank value clears the recorded value, and a key
    absent keeps it. The wizard's fallback (a blank is nothing typed) is
    the create's and the rollover's, not the editor's."""
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "client": "John", "link": "https://y", "due": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"link": "", "due": ""}})
    assert code == 0, payload
    assert payload["saved"] == {"changed": [], "removed": [], "engagement": ["link", "due"], "recorded": True}
    details = payload["state"]["engagement"]
    assert details["link"] == "" and details["due"] == "" and details["client"] == "John"
    assert load_engagement_info(engagement).due is None

    # Absent keys keep what is recorded: nothing moved, nothing written.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False
    assert payload["state"]["engagement"]["client"] == "John"


def test_a_date_pattern_of_star_survives_an_unchanged_resave(capsys, demo_root):
    """A row whose Date Pattern the person set to ``*`` (no year check) is
    recorded with a blank pattern that is not derived; ``state`` hands it
    back that way, the editor shows and sends it as ``*`` again
    (``vocab.editor.no_date_check``), and a resave of the same list records
    nothing - sent blank instead, ``validated()`` would derive the year
    check and record the row as changed on every Save."""
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "period": "TY2025", "required_keywords": "W-2",
         "date_pattern": "*"},
        {"identifier": "A02", "document": "1098", "period": "TY2025", "required_keywords": "1098"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]
    assert rows[0]["date_pattern"] == "" and rows[0]["date_pattern_derived"] is False
    assert rows[1]["date_pattern_derived"] is True

    star = api.NO_DATE_CHECK
    as_the_editor_sends = [{**rows[0], "date_pattern": star}, {**rows[1], "date_pattern": ""}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": as_the_editor_sends, "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False, payload["saved"]
    assert payload["state"]["rules"][0]["date_pattern"] == ""
    js = renderer_text(APP_SCRIPTS)
    assert "(rule.date_pattern || vocab.editor.no_date_check)" in js


def test_a_count_typed_as_infinity_is_refused_with_the_row_and_column_named(capsys, demo_root):
    for typed in ("inf", "Infinity", "1e400"):
        spec = {"household": HOUSEHOLD, "return_name": f"Bad {typed}", "items": [
            {"identifier": "A01", "document": "W-2", "expected_count": typed}]}
        code, payload = run(capsys, "create", stdin=spec)
        assert code == 1 and payload["error"] == f"A01: {COL_EXPECTED_COUNT} {COUNTS}", payload


def test_a_name_whose_folder_was_deleted_by_hand_can_be_created_again(capsys, demo_root):
    """The store still holds the row of a folder someone deleted in
    Explorer; without forgetting it first, the new, shorter journal would
    read as truncated and the create would fail once with that sentence."""
    import shutil

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    assert scan(capsys, where(demo_root, "Smith"))[0] == 0
    shutil.rmtree(where(demo_root, "Smith"))
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert [r["identifier"] for r in payload["state"]["rules"]] == ["A01"]


def test_a_detail_with_a_line_break_inside_it_is_recorded_on_one_line(capsys, demo_root):
    """A sender pasted with a CRLF inside it would carry that break into
    the reminder draft's headers; every detail is one line, inner
    whitespace folded to a space."""
    spec = {"household": HOUSEHOLD, "return_name": "Smith", "sender": "Jason Park\r\nBcc: x@evil.example", "client": " John\tSmith ",
            "items": [{"identifier": "A01", "document": "W-2", "required_keywords": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    details = payload["state"]["engagement"]
    assert details["sender"] == "Jason Park Bcc: x@evil.example" and details["client"] == "John Smith"
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith")),
                        stdin={"items": payload["state"]["rules"], "engagement": {"firm": "J Park\n& Associates"}})
    assert code == 0 and payload["state"]["engagement"]["firm"] == "J Park & Associates"


def test_a_failed_create_leaves_no_folder_and_no_store_row(capsys, demo_root, monkeypatch):
    spec = {"household": HOUSEHOLD, "return_name": "Bad", "items": [
        {"identifier": "A01", "document": "W-2"},
        {"identifier": "A02", "document": "x", "date_pattern": "(unclosed"},
    ]}
    conn = store.connect()
    rows_before = conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0]
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"].startswith(f"Row 2: {COL_DATE_PATTERN}")
    assert not (where(demo_root, "Bad")).exists()
    conn = store.connect()
    assert conn.execute("SELECT COUNT(*) FROM engagements").fetchone()[0] == rows_before
    assert store.rules(conn, where(demo_root, "Bad")) is None

    # A household the record already knows is adopted, so the only writer
    # the refusal below meets is the undo's own.
    assert run(capsys, "create", stdin={"household": HOUSEHOLD, "return_name": "Good",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0

    # A store that cannot be reached at that moment neither replaces the
    # refusal sentence with its own nor leaves the half-built folder behind.
    def cannot(*a, **k):
        raise store.StoreError("the store is locked")

    monkeypatch.setattr(store, "forget", cannot)
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 1 and payload["error"].startswith(f"Row 2: {COL_DATE_PATTERN}")
    assert not (where(demo_root, "Bad")).exists()


def test_the_editor_shows_the_persons_rows_and_never_a_taught_keyword_as_a_typed_one(capsys, demo_root, tmp_path):

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "any_keywords": "w-2"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    text_pdf(inbox_of(engagement) / "scan0012.pdf", "nothing the rules recognise")
    assert scan(capsys, engagement)[0] == 0
    [parked] = api.state(engagement)["index"]
    code, payload = run(capsys, "assign", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": "scan0012.pdf", "identifier": "A01",
                               "keyword": "wage statement", "seq": parked["seq"]})
    assert code == 0, payload

    state = payload["state"]
    [rule] = state["rules"]
    assert rule["any_keywords"] == ["w-2"]                       # typed, as stored
    assert state["learned"] == {"A01": ["wage statement"]}      # taught, beside it
    [item] = state["items"]
    assert item["any_keywords"] == ["w-2", "wage statement"]     # both, for the pass


def test_state_carries_the_warnings_the_pass_reports(capsys, demo_root):
    from tracker.registry import engagement_from
    from tracker.run_log import REMINDERS_NEVER
    from tracker.runner import run_engagement

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [*rows, {"identifier": "Z01", "document": "Anything", "allowed_extensions": "pdf"}],
        "engagement": {},
    })
    assert code == 0, payload
    # The editor's rule warnings are the state's (decision 193, ruling 2);
    # the reply's own warnings mean one thing, and this save said nothing.
    [warning] = payload["state"]["warnings"]
    assert warning.startswith("Row 2 (Z01)") and "never be filed automatically" in warning
    assert payload["warnings"] == []
    run_result = run_engagement(engagement_from(engagement), root=demo_root, reminders=REMINDERS_NEVER)
    assert run_result.warnings == [warning]


def test_state_shows_the_lock_and_unlock_clears_only_a_stale_one(capsys, demo_root):
    import os

    from tracker.locking import LOCK_FILENAME

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [{"identifier": "A01", "document": "W-2"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    assert run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))[1]["lock"] is None

    lock = engagement / LOCK_FILENAME
    # Started this minute: a lock this machine wrote before it last started
    # is dead by the boot rule (decision 189), so a fixed old date would be.
    started = dt.datetime.now().replace(microsecond=0)
    lock.write_text(lock_line(os.getpid(), started), encoding="utf-8")
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert payload["lock"] == {"started": started.isoformat(), "age_minutes": 0, "stale": False,
                               "stale_after_minutes": STALE_LOCK_SECONDS // 60,
                               "host": this_host(), "this_machine": True, "pass": None,
                               "engagement": str(engagement),
                               "label": api._lock_label(engagement)}
    code, payload = run(capsys, "unlock", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 1 and "may still be going" in payload["error"]

    old = (dt.datetime.now() - dt.timedelta(seconds=STALE_LOCK_SECONDS + 1)).timestamp()
    os.utime(lock, (old, old))
    code, payload = run(capsys, "unlock", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0 and payload["cleared"] and payload["state"]["lock"] is None


def test_a_new_client_engagement_is_named_from_client_year_and_form(capsys, demo_root):
    spec = {"form": "1040", "client": "Smith Family",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    assert payload["created"].endswith(api.default_return_name("1040", "Smith Family"))
    code, payload = run(capsys, "templates")
    assert payload["default_year"] == default_tax_year()


# --------------------------------------------- decision 142: accepted, not asked ----


def test_the_wizard_sends_every_catalog_row_and_the_tick_is_asked(capsys, demo_root):
    """The wizard sends the whole catalog, each row carrying its tick as
    ``asked``, and the custom rows asked; a list with no asked row is
    refused and nothing is made."""
    catalog = [{**t, "asked": bool(t["core"])} for t in api.FORM_TEMPLATES["1040"]]
    ticked = {t["identifier"] for t in catalog if t["asked"]}
    assert len(ticked) == 5
    custom = {"identifier": "X01", "document": "Home office log", "required_keywords": "home office"}
    spec = {"household": HOUSEHOLD, "return_name": "Everything", "form": "1040",
            "items": [*catalog, custom]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload

    rules = {row["identifier"]: row for row in payload["state"]["rules"]}
    assert set(rules) == {t["identifier"] for t in catalog} | {"X01"}
    assert {i for i, row in rules.items() if row["asked"]} == ticked | {"X01"}
    assert payload["state"]["summary"]["total"] == 6
    assert payload["state"]["summary"]["not_asked"] == len(catalog) - 5

    nothing = {"household": HOUSEHOLD, "return_name": "Nothing Asked", "form": "1040",
               "items": [{**t, "asked": False} for t in api.FORM_TEMPLATES["1040"]]}
    code, payload = run(capsys, "create", stdin=nothing)
    assert code == 1 and payload["error"] == "Tick at Least One Request"
    assert not where(demo_root, "Nothing Asked").exists()


def test_creation_measures_the_room_of_asked_rows_only(capsys, tmp_path, monkeypatch, path_setting):
    """A return whose longest *unasked* label would not fit is created: the
    catalog's longest label must not refuse a return the preparer never
    asked it of. The same row asked is refused, as ever. A document for the
    unasked row is measured where it is written - cut to fit, or parked
    with decision 131's sentence. Since decision 144 a label in the path is
    a short name of twenty characters at most, and since decision 168 it is
    in the path once, so the room is the return folder's: 198 characters
    here, and 197 with long paths off, where the long row asks for a long
    period so that it is past the limit in a return whose review folder has
    room (pilot decision P29; 212 with TY2025 before it, 205 while each
    request had a folder)."""
    from tests.builders import named_page, root_for_a_return_of, sort
    from tracker.layout import PATH_TOO_LONG, path_limit
    from tracker.scaffold import PREPARED_DIR_NAME
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    period = "Jan 2025 to Dec 2025"
    length = path_limit() - len(f"/{PREPARED_DIR_NAME}/Z99 - Zebra Ledger Details - {period}.pdf") + 1
    root = root_for_a_return_of(tmp_path, length, return_name="Tight")
    root.mkdir(parents=True)
    set_clients_root(root)
    w2 = {"identifier": "A01", "document": "W-2", "period": "TY2025",
          "extensions": "pdf", "required_keywords": "W-2", "min_size_kb": 0}
    long_row = {"identifier": "Z99", "document": "Zebra Ledger " + "x" * 90, "period": period,
                "date_pattern": r"(?i)\b2025\b",
                "short_title": "Zebra Ledger Details", "extensions": "pdf",
                "required_keywords": "zebra ledger", "min_size_kb": 0}

    code, payload = run(capsys, "create", stdin={"return_name": "Tight", "year": 2025,
                                                 "items": [w2, {**long_row, "asked": True}]})
    assert code == 1 and payload["error"].startswith(PATH_TOO_LONG.split("{")[0])

    code, payload = run(capsys, "create", stdin={"return_name": "Tight", "year": 2025,
                                                 "items": [w2, {**long_row, "asked": False}]})
    assert code == 0, payload
    engagement = where(root, "Tight", year=2025)
    assert len(str(engagement)) == length

    text_pdf(inbox_of(engagement) / "zebra.pdf", named_page("Zebra ledger for 2025"))
    report = sort(engagement)
    # Prepared leaves the name fifty-two characters: the short name is
    # cut from its end, and the copy keeps its identifier, its period and
    # its extension (test_filer's decision-131 claims). Until decision 168
    # the row's own folder took the room and the short name went whole.
    [filed] = report.filed
    assert filed.prepared_location == f"{PREPARED_DIR_NAME}/Z99 - Zebra Ledger Detail - {period}.pdf"
    assert len(str(engagement)) + 1 + len(filed.prepared_location) == path_limit()


def test_the_editor_round_trips_asked_and_named(capsys, demo_root):
    """The rows the renderer's ``editorRow`` builds from ``state.rules``,
    saved untouched, change nothing and record nothing - a ``named=no`` row
    and a not-asked row included (the editor dropped ``named`` until
    decision 142, so every save turned it to yes)."""
    spec = {"household": HOUSEHOLD, "return_name": "Round Trip", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "D01", "document": "Donation receipts", "any_keywords": "donation receipt",
         "named": "no"},
        {"identifier": "E01", "document": "1099-R", "any_keywords": "1099-r", "asked": False},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Round Trip")
    state = payload_of_state(capsys, engagement)
    vocab = run(capsys, "list")[1]["vocab"]
    editor = vocab["editor"]
    assert editor["yes_no_fields"] == ["named", "asked"]

    def editor_row(rule):          # app.js editorRow, key for key
        return {
            "identifier": rule["identifier"], "document": rule["document"], "period": rule["period"],
            "expected_count": rule["expected_count"],
            "allowed_extensions": ", ".join(rule["allowed_extensions"]) or editor["any_extension"],
            "min_size_kb": rule["min_size_kb"],
            "required_keywords": ", ".join(rule["required_keywords"]),
            "any_keywords": ", ".join(rule["any_keywords"]),
            "date_pattern": "" if rule["date_pattern_derived"] else (
                rule["date_pattern"] or editor["no_date_check"]),
            "manual_override": rule["manual_override"],
            "override_reason": rule["override_reason"] or "",
            "named": editor["no"] if rule["named"] is False else editor["yes"],
            "asked": editor["no"] if rule["asked"] is False else editor["yes"],
        }

    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [editor_row(r) for r in state["rules"]], "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False, payload
    assert ledger.path_for(engagement).read_bytes() == before
    rules = {r["identifier"]: r for r in payload["state"]["rules"]}
    assert rules["D01"]["named"] is False and rules["E01"]["asked"] is False

    # Asking for it is flipping the pick and saving: one rules_changed.
    flipped = [{**editor_row(r), "asked": editor["yes"]} if r["identifier"] == "E01" else editor_row(r)
               for r in state["rules"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": flipped, "engagement": {}})
    assert code == 0 and payload["saved"]["changed"] == ["E01"]

    js = renderer_text(APP_SCRIPTS)
    assert 'named: rule.named === false ? vocab.editor.no : vocab.editor.yes' in js
    assert 'asked: rule.asked === false ? vocab.editor.no : vocab.editor.yes' in js
    assert "vocab.editor.yes_no_fields.includes(key)" in js


def test_the_apps_request_table_folds_not_asked_rows_with_no_document_into_a_closed_group(capsys, demo_root):
    """The designer's ruling on the 142 build, the app's half: every state
    item says whether a document is in it and whether it folds, by the one
    rule the Status Report uses - only a row nobody asked for with no
    document at all folds - and the request table draws those rows in a
    closed "Not asked (N)" group headed in the API's words; the editor
    regroups a row live on the same fact."""
    from tests.builders import seed_statuses
    from tracker.manifest import Status, StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": "Folded", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "B01", "document": "SSA-1099", "required_keywords": "ssa-1099", "asked": False},
        {"identifier": "B02", "document": "W-2G", "required_keywords": "w-2g", "asked": False},
        {"identifier": "B03", "document": "1099-C", "required_keywords": "1099-c", "asked": False},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Folded")
    seed_statuses(engagement, {
        "B01": StatusUpdate(status=Status.RECEIVED, file_count=1),
        "B02": StatusUpdate(status=Status.FAILED, file_count=0, validation_notes="w2g.pdf: refused"),
        "B03": StatusUpdate(status=Status.MISSING, file_count=0),
    })
    items = {i["identifier"]: i for i in payload_of_state(capsys, engagement)["items"]}

    assert {i: (one["has_document"], one["not_asked_idle"]) for i, one in items.items()} == {
        "A01": (False, False), "B01": (True, False), "B02": (True, False), "B03": (False, True)}

    # The page does not decide which rows fold: the API's `group` does (SPEC
    # 9.1), and the set-aside group is a closed `details` (SPEC 6.7).
    pages = (Path(__file__).resolve().parent.parent / "app" / "renderer" / "pages.js").read_text(encoding="utf-8")
    assert "not_asked_idle" not in pages and "item.group" in pages
    assert 'h("details", { className: "group-fold" }' in pages and "fold.open = Boolean(spec.open)" in pages
    assert "let pagesSetAsideOpen = false;" in pages, "shut each time the page opens"


def test_the_editor_refuses_a_list_nobody_is_asked_for_in_creations_words(capsys, demo_root):
    """Decision 142's review, R6: a return always asks for at least one
    thing. The editor's save of a list with no asked row is refused with
    creation's own sentence, and nothing is recorded."""
    spec = {"household": HOUSEHOLD, "return_name": "Asks Something", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "B01", "document": "1099-R", "required_keywords": "1099-r", "asked": False},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Asks Something")
    rows = payload_of_state(capsys, engagement)["rules"]
    before = ledger.path_for(engagement).read_bytes()

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [{**row, "asked": False} for row in rows], "engagement": {}})
    assert code == 1 and payload["error"] == screen_words.NOTHING_ASKED
    assert ledger.path_for(engagement).read_bytes() == before

    code, payload = run(capsys, "create", stdin={**spec, "return_name": "Asks Nothing", "items": [
        {**one, "asked": False} for one in spec["items"]]})
    assert code == 1 and payload["error"] == screen_words.NOTHING_ASKED


def test_the_returning_client_page_picks_the_returns_recorded_form_by_default(capsys, demo_root):
    """Decision 142's review, R2: each prior carries the catalog it was cut
    from, and the page's template pick defaults to it, so the catalog rows
    the return never had arrive as not asked without anybody choosing; a
    return that recorded no form defaults to no template. Since decision
    196 the pick is the roll fold's on the household's card, and the form
    comes from the card's own state; ``priors`` still carries it for the
    command line."""
    spec = {"household": HOUSEHOLD, "return_name": "Recorded", "form": "1040",
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    [prior] = run(capsys, "priors")[1]["priors"]
    assert prior["form"] == "1040"
    engagement = where(demo_root, "Recorded")
    assert [r["form"] for r in api.state(engagement)["household"]["returns"]] == ["1040"]

    js = renderer_text(APP_SCRIPTS)
    assert ": r.form;" in js and "const known = forms.some((f) => f.id === picked);" in js
    assert "selected: f.id === picked" in js and "selected: !known" in js


# ------------------------------------------------ decision 144: short names ----


def _editor_rows_by_the_app(rules, vocab, tmp_path):
    """``editorRow`` exactly as ``app.js`` spells it, run by node over
    ``rules``; where node is not on PATH, the line that carries the short
    name is held by its source instead, and the rows are built key for key
    as the function builds them."""
    import re
    import shutil
    import subprocess

    source = js_function("editorRow")
    assert re.search(r'^\s+short_title: rule\.short_title \|\| "",$', source, flags=re.MULTILINE)
    node = shutil.which("node")
    if node is None:
        editor = vocab["editor"]
        return [{**{k: rule[k] for k in ("identifier", "document", "period", "expected_count",
                                         "min_size_kb", "manual_override")},
                 "allowed_extensions": ", ".join(rule["allowed_extensions"]) or editor["any_extension"],
                 "required_keywords": ", ".join(rule["required_keywords"]),
                 "any_keywords": ", ".join(rule["any_keywords"]),
                 "date_pattern": "" if rule["date_pattern_derived"] else (
                     rule["date_pattern"] or editor["no_date_check"]),
                 "override_reason": rule["override_reason"] or "",
                 "named": editor["no"] if rule["named"] is False else editor["yes"],
                 "asked": editor["no"] if rule["asked"] is False else editor["yes"],
                 "short_title": rule["short_title"] or ""} for rule in rules]
    script = tmp_path / "editor_row.js"
    script.write_text("const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
                      "const vocab = input.vocab;\n" + source + "\n"
                      "process.stdout.write(JSON.stringify(input.rules.map(editorRow)));\n",
                      encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(script)], input=json.dumps({"vocab": vocab, "rules": rules}),
                          capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def test_the_short_title_round_trips_through_the_editor_and_the_rollover(capsys, demo_root, tmp_path):
    """Decision 144, claim 5 - the lesson of 142's ``named`` defects, where
    the editor and the rollover each rebuilt a row by hand and dropped a
    column. The short name comes back from ``state``, goes through the
    app's real ``editorRow`` and a save untouched with nothing recorded, is
    changed by one edit of one row, and is carried by the rollover: a typed
    one as typed, a blank one on a catalog row filled from the catalog, a
    blank one on a row a person renamed left blank, to derive its own."""
    from tracker.rollover import roll_forward
    from tracker.templates import FORM_TEMPLATES, template_items

    catalog_w2 = {**FORM_TEMPLATES["1040"][0], "asked": True}
    spec = {"household": HOUSEHOLD, "return_name": "Short Names", "year": 2025, "items": [
        catalog_w2,
        {"identifier": "D01", "document": "Donation receipts", "any_keywords": "donation receipt",
         "short_title": "Donations", "period": "TY2025"},
        {"identifier": "E01", "document": "My own brokerage statements", "any_keywords": "brokerage",
         "period": "TY2025"},
        {"identifier": "X01", "document": "Schedule K-1 - ABC Partners LLC", "any_keywords": "abc partners",
         "period": "TY2025"},
    ]}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    engagement = where(demo_root, "Short Names", year=2025)
    state = payload_of_state(capsys, engagement)
    assert {r["identifier"]: r["short_title"] for r in state["rules"]} == {
        "A01": "W-2", "D01": "Donations", "E01": "", "X01": ""}
    assert {i["identifier"]: i["short_name"] for i in state["items"]} == {
        "A01": "W-2", "D01": "Donations", "E01": "My own brokerage", "X01": "K-1 ABC Partners LLC"}
    vocab = run(capsys, "list")[1]["vocab"]
    assert {"key": "short_title", "label": "Short name"}.items() <= next(
        c for c in vocab["columns"] if c["key"] == "short_title").items()

    rows = _editor_rows_by_the_app(state["rules"], vocab, tmp_path)
    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {}})
    assert code == 0 and payload["saved"]["recorded"] is False, payload
    assert ledger.path_for(engagement).read_bytes() == before

    # One row's short name changed, and the catalog row's cleared: one event.
    changed = [{**row, "short_title": {"D01": "Gifts", "A01": ""}.get(row["identifier"], row["short_title"])}
               for row in rows]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": changed, "engagement": {}})
    assert code == 0 and sorted(payload["saved"]["changed"]) == ["A01", "D01"], payload
    assert {r["identifier"]: r["short_title"] for r in payload["state"]["rules"]} == {
        "A01": "", "D01": "Gifts", "E01": "", "X01": ""}
    # A name no folder can have is refused with the column named.
    bad = [{**row, "short_title": "x" * 21} if row["identifier"] == "D01" else row for row in changed]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": bad, "engagement": {}})
    assert code == 1 and "Short name may have at most 20 characters" in payload["error"]

    rolled = {r.item.identifier: r.item for r in roll_forward(
        engagement, template=template_items("1040", year=2025)).rolled}
    assert rolled["A01"].short_title == "W-2"            # a blank, filled from the catalog's own row
    assert rolled["D01"].short_title == "Gifts"          # typed, carried
    assert rolled["E01"].short_title == ""               # renamed by a person: derives its own
    assert rolled["X01"].short_title == ""


# ------------------------------------------------- decision 160: a save keeps ----


def _waiting_in(readme: str) -> str:
    """The README's *REQUESTED, NOT YET RECEIVED* section alone."""
    from tracker.scaffold import README_HEADING, RECEIVED_HEADING

    if README_HEADING not in readme:
        return ""
    return readme.split(README_HEADING, 1)[1].split(RECEIVED_HEADING, 1)[0]


def test_a_save_from_a_stale_list_is_refused(capsys, demo_root):
    """Two windows open the editor; the second saves; the first's save,
    made from the list as it was, is refused and records nothing (decision
    160, the audit's B-4). It used to remove the row the second added,
    clear the due date and drop the spelling it taught. A save with no
    version is refused too; a pass run while the editor is open is not a
    change of the list and refuses nothing."""
    from tracker.manifest import LIST_MOVED, NO_LIST_HEAD

    spec = {"household": HOUSEHOLD, "return_name": "Smith", "items": [
        {"identifier": "A01", "document": "W-2", "required_keywords": "W-2"},
        {"identifier": "B01", "document": "1099-INT", "required_keywords": "1099-INT"},
    ]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith")
    first = payload_of_state(capsys, engagement)
    second = payload_of_state(capsys, engagement)
    assert first["list_head"] == second["list_head"] != ""

    people = [{**person, "spellings": [*person["spellings"], "T CLIENT"]}
              for person in second["engagement"]["people"]]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": _rows_of(second) + [{"identifier": "F02", "document": "K-1 Example Partners",
                                      "required_keywords": "Schedule K-1"}],
        "engagement": {"due": "2026-03-15", "people": people}, "head": second["list_head"]})
    assert code == 0 and payload["saved"]["changed"] == ["F02"], payload

    before = ledger.path_for(engagement).read_bytes()
    stale = _rows_of(first)
    stale[1]["any_keywords"] = ["interest income"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": stale, "engagement": {"due": "", "people": first["engagement"]["people"]},
        "head": first["list_head"]})
    assert code == 1 and payload["error"] == LIST_MOVED
    assert ledger.path_for(engagement).read_bytes() == before
    now = payload_of_state(capsys, engagement)
    assert [rule["identifier"] for rule in now["rules"]] == ["A01", "B01", "F02"]
    assert now["engagement"]["due"] == "2026-03-15"
    assert "T CLIENT" in now["engagement"]["people"][0]["spellings"]

    for head in ("", None, 7):
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                            stdin={"items": _rows_of(now), "engagement": {}, "head": head})
        assert code == 1 and payload["error"] == NO_LIST_HEAD
    assert ledger.path_for(engagement).read_bytes() == before

    # A pass moves the record's head, not the list's: the editor opened
    # before it saves after it.
    opened = payload_of_state(capsys, engagement)
    journal = ledger.head(engagement)
    assert scan(capsys, engagement)[0] == 0
    assert ledger.head(engagement) != journal
    assert payload_of_state(capsys, engagement)["list_head"] == opened["list_head"]
    edited = _rows_of(opened)
    edited[0]["any_keywords"] = ["wages"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": edited, "engagement": {}, "head": opened["list_head"]})
    assert code == 0 and payload["saved"]["changed"] == ["A01"], payload
    assert payload["state"]["list_head"] != opened["list_head"]


def _filed_documents(capsys, demo_root, tmp_path):
    """The sample return with both current-year W-2s filed under A01 and the
    1098 under C01, by a real pass."""
    from tests.samples import YEAR

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 John Smith {YEAR}.pdf",
                                   f"W-2 Jane Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    filed = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert sorted(e["identifier"] for e in filed) == ["A01", "A01", "C01"], filed
    return engagement, payload["state"]


def test_respelling_an_identifier_with_documents_is_refused_unless_renamed_with_them(
        capsys, demo_root, tmp_path):
    """A01 holds two filed W-2s. Saving the list with A01 spelled A1 - or
    without A01 at all - used to save as a removal and an addition with no
    warning: the W-2s became "Other document", A1 was missing, and the
    letter and the README asked the client again (decision 160, the audit's
    D-7). The save is refused by name and count, and nothing is recorded;
    the rename action is the way, and it carries the documents."""
    from tracker.scaffold import OTHER_DOCUMENT

    engagement, state = _filed_documents(capsys, demo_root, tmp_path)
    label = next(i.label for i in load_manifest(engagement) if i.identifier == "A01")
    before = ledger.path_for(engagement).read_bytes()
    respelt = [{**rule, "identifier": "A1"} if rule["identifier"] == "A01" else rule
               for rule in _rows_of(state)]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": respelt, "engagement": {}})
    assert code == 1 and payload["error"] == screen_words.HOLDS_DOCUMENTS.format(identifier="A01", n=2)
    dropped = [rule for rule in _rows_of(state) if rule["identifier"] != "A01"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": dropped, "engagement": {}})
    assert code == 1 and payload["error"] == screen_words.HOLDS_DOCUMENTS.format(identifier="A01", n=2)
    assert ledger.path_for(engagement).read_bytes() == before
    # A row that holds nothing is still removed by a save, as it always was.
    empty = [rule for rule in _rows_of(state) if rule["identifier"] != "B01"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": empty, "engagement": {}})
    assert code == 0 and payload["saved"]["removed"] == ["B01"], payload

    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 0, payload
    assert (payload["renamed"]["old"], payload["renamed"]["new"], payload["renamed"]["moved"]) == \
        ("A01", "A1", 2)
    items = {i["identifier"]: i for i in payload["state"]["items"]}
    assert "A01" not in items and items["A1"]["status"] == Status.RECEIVED
    assert sorted(e["identifier"] for e in payload["state"]["index"] if e["decision"] == FILED) == \
        ["A1", "A1", "C01"]
    readme = client_readme(engagement)
    renamed_label = next(i.label for i in load_manifest(engagement) if i.identifier == "A1")
    assert renamed_label != label and renamed_label not in _waiting_in(readme)
    assert f"  {renamed_label}  Received" in readme and OTHER_DOCUMENT not in readme


def test_a_rename_carries_its_documents(capsys, demo_root, tmp_path):
    """The rename gives every working copy of the request's the new
    identifier at the front of its name, in Prepared itself (decision 168),
    rewrites each row that names them, and records
    it as one act: the list renamed and each row's intent in one write,
    then the moves, then the rows (decision 119's intents). A stale list,
    a case-only change, a name already taken and a request that is not on
    the list are refused, and nothing moves."""
    from tracker.manifest import LIST_MOVED

    engagement, state = _filed_documents(capsys, demo_root, tmp_path)
    prepared = engagement / PREPARED_DIR_NAME
    old_copies = sorted(e["prepared_location"] for e in state["index"]
                        if e["decision"] == FILED and e["identifier"] == "A01")
    assert all((engagement / location).is_file() for location in old_copies)
    assert all("/A01 - " in location for location in old_copies)
    before = ledger.path_for(engagement).read_bytes()

    for spec, said in (({"from": "A01", "to": "a01"}, "differ only in case"),
                       ({"from": "A01", "to": "c01"}, "C01"),
                       ({"from": "Z9", "to": "A1"}, "Z9"),
                       ({"from": "A01", "to": "A1", "head": "stale"}, LIST_MOVED)):
        code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement), stdin=spec)
        assert code == 1 and said in payload["error"], (spec, payload)
    assert ledger.path_for(engagement).read_bytes() == before
    assert all((engagement / location).is_file() for location in old_copies)

    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 0, payload
    assert payload["renamed"]["head"] == payload["state"]["list_head"]
    moved = sorted(e["prepared_location"] for e in payload["state"]["index"]
                   if e["decision"] == FILED and e["identifier"] == "A1")
    assert moved == sorted(location.replace("/A01 - ", "/A1 - ") for location in old_copies)
    for location in moved:
        assert (engagement / location).is_file()
        assert Path(location).name.startswith("A1 - ")
    assert not any((engagement / location).exists() for location in old_copies)
    assert not [child for child in prepared.iterdir() if child.name.startswith("A01")]
    # The record says it once: the list renamed and each row's intent in
    # one write, each row closed by the person's rename, no intent left
    # open - and the store agrees with the journal (the suite's own check
    # runs after every test).
    events = ledger.read_events(engagement)
    added = events[len(before.splitlines()):]
    names = [e[ledger.EVENT_KEY] for e in added]
    assert names[0] == ledger.RULES_CHANGED
    assert added[0][ledger.REMOVED_KEY] == ["A01"]
    assert [row["identifier"] for row in added[0][ledger.RULES_KEY]] == ["A1"]
    intents = [e for e in added if e[ledger.EVENT_KEY] == ledger.MOVING]
    closed = [e for e in added if e[ledger.EVENT_KEY] == ledger.RENAMED_BY_PERSON]
    assert len(intents) == len(closed) >= 2
    assert {e[ledger.KEY_KEY] for e in intents} == {e[ledger.KEY_KEY] for e in closed}
    assert not store.open_intents(store.connect(), engagement)


def test_a_rename_carries_duplicates_and_parked_candidates_that_name_it(
        capsys, demo_root, tmp_path, monkeypatch):
    """Rows with nothing to move still follow a rename (decision 160, the
    review's gap): a Duplicate row that names the request, and a parked
    row with the request among its candidates, name the new identifier
    afterwards - the parked row's evidence cell too, where it round-trips.
    Each gets its own intent in the rename's one write, so a rename a run
    was killed in is finished for them by the next pass as well; and a
    rename that runs through carries them the same way."""
    import tracker.actions as actions
    import tracker.filer as filer
    import tracker.intents as intents
    from tests.samples import PRIOR_YEAR, YEAR
    from tracker.index import DUPLICATE

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 John Smith {YEAR}.pdf",
                                   f"W-2 John Smith {YEAR} - Copy.pdf",
                                   f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload

    def rows(state):
        return {e["original_name"]: e for e in state["index"]}

    before = rows(payload["state"])
    duplicate = next(e for e in before.values() if e["decision"] == DUPLICATE)
    parked = next(e for e in before.values() if e["decision"] == NEEDS_REVIEW)
    assert duplicate["identifier"] == "A01" and duplicate["prepared_location"] == ""
    assert parked["candidates"] == ["A01"] and list(parked["evidence"]) == ["A01"]

    def follows(state, identifier):
        now = rows(state)
        assert now[duplicate["original_name"]]["identifier"] == identifier
        assert now[parked["original_name"]]["candidates"] == [identifier]
        assert list(now[parked["original_name"]]["evidence"]) == [identifier]
        assert now[parked["original_name"]]["evidence"][identifier] == parked["evidence"]["A01"]
        assert now[parked["original_name"]]["decision"] == NEEDS_REVIEW

    # Killed at its one move: every row's intent is already written.
    real = intents._do_op

    def killed(engagement_dir, op, **kwargs):
        raise PermissionError("held open by another program")

    for module in (filer, intents, actions):
        monkeypatch.setattr(module, "_do_op", killed)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 1, payload
    open_keys = {intent[ledger.KEY_KEY] for intent in store.open_intents(store.connect(), engagement)}
    assert {duplicate["pbc_location"], parked["pbc_location"]} <= open_keys
    for module in (filer, intents, actions):
        monkeypatch.setattr(module, "_do_op", real)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    assert not store.open_intents(store.connect(), engagement)
    follows(payload["state"], "A1")

    # And a rename that runs through carries them the same way.
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A1", "to": "A01"})
    assert code == 0, payload
    follows(payload["state"], "A01")
    closed = [e[ledger.KEY_KEY] for e in ledger.read_events(engagement)
              if e[ledger.EVENT_KEY] == ledger.RENAMED_BY_PERSON]
    assert closed.count(duplicate["pbc_location"]) == 2 and closed.count(parked["pbc_location"]) == 2


def test_an_interrupted_rename_is_finished_by_the_next_pass(capsys, demo_root, tmp_path, monkeypatch):
    """A rename whose second move fails is on the record from its first
    write, and the next pass finishes it (decision 119): nothing lost and
    nothing doubled. Since decision 168 it renames the copies only, in
    Prepared itself: no folder is made and none is left to tidy."""
    import tracker.actions as actions
    import tracker.filer as filer
    import tracker.intents as intents
    from tracker.actions import RENAME_UNFINISHED

    engagement, _ = _filed_documents(capsys, demo_root, tmp_path)
    prepared = engagement / PREPARED_DIR_NAME
    real = intents._do_op
    calls = {"n": 0}

    def the_second_move_fails(engagement_dir, op, **kwargs):
        calls["n"] += 1
        if calls["n"] == 2:
            raise PermissionError("held open by another program")
        return real(engagement_dir, op, **kwargs)

    for module in (filer, intents, actions):
        monkeypatch.setattr(module, "_do_op", the_second_move_fails)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A01", "to": "A1"})
    assert code == 1 and payload["error"].startswith(RENAME_UNFINISHED.split("{name}")[0].format(
        old="A01", new="A1"))
    assert store.open_intents(store.connect(), engagement)
    # One copy moved before the failure, one did not: both in Prepared itself.
    assert len([child for child in prepared.iterdir() if child.name.startswith("A01 - ")]) == 1
    assert len([child for child in prepared.iterdir() if child.name.startswith("A1 - ")]) == 1

    for module in (filer, intents, actions):
        monkeypatch.setattr(module, "_do_op", real)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    assert not store.open_intents(store.connect(), engagement)
    assert not [child for child in prepared.iterdir() if child.name.startswith("A01")]
    assert [child.name for child in prepared.iterdir() if child.is_dir()] == [REVIEW_DIR_NAME]
    assert payload["run"]["warnings"] == []
    filed = [e for e in payload["state"]["index"] if e["decision"] == FILED and e["identifier"] == "A1"]
    assert len(filed) == 2 and all((engagement / e["prepared_location"]).is_file() for e in filed)
    assert len({e["prepared_location"] for e in filed}) == 2                  # nothing doubled
    assert len([child for child in prepared.iterdir() if child.name.startswith("A1 - ")]) == 2


@pytest.mark.parametrize("only_the_cell", [False, True], ids=["as-routed", "only-the-cell"])
def test_a_rename_carries_what_a_consolidated_statement_answers(capsys, demo_root, monkeypatch,
                                                                only_the_cell):
    """d146 over 160, SPEC-146 R-1. The Schwab statement is filed under E01
    and answers A02 through its Also Answers cell, with no copy under A02.
    Renaming A02 to A02X rewrites that cell, sections and all: A02X reads
    Received with the scanner's in-the-statement note, the letter does not
    ask for it, the client README says it is received inside the brokerage
    statement, and marking it missing again takes the new name. A rename
    killed after its one write is finished by the next pass to the same
    result, because the statement's row - linked to A02 by that cell alone -
    has its own intent in the write.

    The router's row also names A02 among its candidates and evidence,
    which 160's rename already carried; so the claim runs a second time
    with the statement's row recorded naming A02 in its Also Answers cell
    alone, through the filer's own writer, and the cell must carry it."""
    from dataclasses import replace

    import tracker.actions as actions
    import tracker.filer as filer
    from tests.builders import _consolidated_return
    from tracker import intents
    from tracker.reasons import IN_CONSOLIDATED, IN_CONSOLIDATED_CLIENT
    from tracker.reminder import draft_reminder

    engagement = _consolidated_return(demo_root)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["identifier"] == "E01" and filed["answered"] == ["A02", "A04"]
    if only_the_cell:
        from tracker.locking import engagement_lock
        from tracker.records import entry_to_json, ledger_key

        with engagement_lock(engagement):
            entries = read_index(engagement)
            before = {ledger_key(e): entry_to_json(e) for e in entries}
            entries = [replace(e, candidates="E01", evidence="") if e.decision == FILED else e
                       for e in entries]
            intents._record(engagement, before, entries)
        [row] = [r for r in read_index(engagement) if r.decision == FILED]
        assert row.candidate_list == ["E01"] and row.evidence == "" and "A02" in row.answers

    def carried(state, new):
        [row] = [r for r in read_index(engagement) if r.decision == FILED]
        assert row.identifier == "E01"
        assert row.answers == f"{new} (1099-int, 1099-div); A04 (1099-misc)"
        items = {i.identifier: i for i in load_manifest(engagement)}
        assert "A02" not in items or new == "A02"
        assert items[new].status == Status.RECEIVED, items[new].validation_notes
        assert items[new].file_count == 2
        assert IN_CONSOLIDATED.format(row="E01") in items[new].validation_notes
        assert new not in draft_reminder(engagement).asked
        readme = client_readme(engagement)
        label = items[new].label
        assert label not in _waiting_in(readme)
        [said] = [one for one in readme.splitlines() if one.strip().startswith(label)]
        assert said.endswith(f", {IN_CONSOLIDATED_CLIENT}"), said
        [shown] = [e for e in state["index"] if e["decision"] == FILED]
        assert shown["answered"] == [new, "A04"]

    # Killed after the rename's one write: the list and every row's intent
    # are on the record, and the statement's row is not yet rewritten.
    real = intents._record

    def killed(*args, **kwargs):
        raise PermissionError("the run was stopped")

    for module in (filer, actions):
        monkeypatch.setattr(module, "_record", killed)
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A02", "to": "A02K"})
    assert code == 1, payload
    open_keys = {intent[ledger.KEY_KEY] for intent in store.open_intents(store.connect(), engagement)}
    assert filed["pbc_location"] in open_keys
    for module in (filer, actions):
        monkeypatch.setattr(module, "_record", real)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    assert not store.open_intents(store.connect(), engagement)
    carried(payload["state"], "A02K")

    # A rename that runs through carries it the same way.
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"from": "A02K", "to": "A02X"})
    assert code == 0, payload
    assert payload["renamed"]["moved"] == 0
    carried(payload["state"], "A02X")
    closed = [e[ledger.KEY_KEY] for e in ledger.read_events(engagement)
              if e[ledger.EVENT_KEY] == ledger.RENAMED_BY_PERSON]
    assert closed.count(filed["pbc_location"]) == 2

    # And the person's button takes the new name.
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A02X",
                               "seq": filed["seq"]})
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    assert filed["answered"] == ["A04"]
    a02x = next(i for i in payload["state"]["items"] if i["identifier"] == "A02X")
    assert a02x["status"] == Status.MISSING


def test_a_request_answered_only_by_a_statement_cannot_be_deleted_by_a_save(capsys, demo_root):
    """d146 over 160, SPEC-146 R-2. A04 holds no copy: the Schwab statement
    filed under E01 answers it through its Also Answers cell. A save that
    takes A04 off the list is refused with decision 160's sentence, and
    nothing is recorded; once a person marks A04 missing again, the same
    save goes through."""
    from tests.builders import _consolidated_return

    engagement = _consolidated_return(demo_root)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]
    [filed] = [e for e in state["index"] if e["decision"] == FILED]
    assert filed["identifier"] == "E01" and "A04" in filed["answered"]
    assert not [e for e in state["index"] if e["identifier"] == "A04"]

    before = ledger.path_for(engagement).read_bytes()
    dropped = [rule for rule in _rows_of(state) if rule["identifier"] != "A04"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": dropped, "engagement": {}})
    assert code == 1 and payload["error"] == screen_words.HOLDS_DOCUMENTS.format(identifier="A04", n=1)
    assert ledger.path_for(engagement).read_bytes() == before

    code, payload = run(capsys, "mark-missing", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"original": filed["pbc_location"], "identifier": "A04",
                               "seq": filed["seq"]})
    assert code == 0, payload
    state = payload["state"]
    dropped = [rule for rule in _rows_of(state) if rule["identifier"] != "A04"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": dropped, "engagement": {}})
    assert code == 0 and payload["saved"]["removed"] == ["A04"], payload


def test_a_filing_racing_a_save_is_seen_under_the_lock(capsys, demo_root, tmp_path, monkeypatch):
    """The documents-held check runs inside the save's engagement lock, in
    the same critical section as the write (decision 160, the designer's
    ruling on the build). A pass that files the 1098 into C01 after the
    editor sent a list without C01, and before the save takes the lock, is
    seen: the save is refused and C01 stays."""
    from tests.samples import YEAR
    from tracker.locking import lock_is_held

    engagement = sample_engagement(capsys, demo_root, tmp_path, f"W-2 John Smith {YEAR}.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]
    assert not [e for e in state["index"] if e["identifier"] == "C01"]
    samples = tmp_path / "samples"
    before_the_lock = request_edit._refuse_a_changed_row_past_the_limit

    def a_pass_files_first(folder, items):
        # Outside the lock: the 1098 arrives and the household's sort files it.
        assert not lock_is_held(folder)
        (inbox_of(folder) / "Form 1098 Mortgage Interest.pdf").write_bytes(
            (samples / "Form 1098 Mortgage Interest.pdf").read_bytes())
        from tests.builders import sort
        sort(folder)
        return before_the_lock(folder, items)

    seen_under = []
    real_check = request_edit._refuse_taking_away_documents

    def the_check(folder, recorded, items):
        seen_under.append(lock_is_held(folder))
        return real_check(folder, recorded, items)

    monkeypatch.setattr(api, "_refuse_a_changed_row_past_the_limit", a_pass_files_first)
    monkeypatch.setattr(api, "_refuse_taking_away_documents", the_check)
    without_c01 = [rule for rule in _rows_of(state) if rule["identifier"] != "C01"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": without_c01, "engagement": {}, "head": state["list_head"]})
    assert code == 1 and payload["error"] == screen_words.HOLDS_DOCUMENTS.format(identifier="C01", n=1)
    assert seen_under == [True]
    assert "C01" in [rule["identifier"] for rule in payload_of_state(capsys, engagement)["rules"]]


def test_a_case_only_change_reads_the_same_in_the_readme_and_the_letter(capsys, demo_root, tmp_path):
    """C01 holds the filed 1098. Respelling it c01 is the same request
    everywhere (decision 160, the audit's D-8): the save needs no rename,
    the status is Received, the letter does not ask for it, and the client
    README lists the 1098 as received under its own label - it used to say
    "not received" beside an "Other document"."""
    from tracker import reminder
    from tracker.readme_ack import received_for
    from tracker.scaffold import OTHER_DOCUMENT

    engagement, state = _filed_documents(capsys, demo_root, tmp_path)
    respelt = [{**rule, "identifier": "c01"} if rule["identifier"] == "C01" else rule
               for rule in _rows_of(state)]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": respelt, "engagement": {}})
    assert code == 0, payload
    items = {i["identifier"]: i for i in payload["state"]["items"]}
    assert items["c01"]["status"] == Status.RECEIVED
    label = next(i.label for i in load_manifest(engagement) if i.identifier == "c01")

    received = received_for([engagement])
    assert label in {line.label for line in received.lines}
    assert OTHER_DOCUMENT not in {line.label for line in received.lines}
    assert "c01" in {line.identifier for line in received.lines}

    readme = client_readme(engagement)
    assert label not in _waiting_in(readme)
    assert f"  {label}  Received" in readme and OTHER_DOCUMENT not in readme

    letter = reminder.draft_reminder(engagement)
    assert "c01" not in {line.item.identifier.lower() for line in letter.lines}


# ------------------------------------------------- the form inputs, 2026-10-12 ----
# The audit of every form's payload against the real API (P287 to P294):
# each rule lives in Python and the store, so each claim is made through the
# commands the page calls.


def _a_return_to_type_into(capsys, demo_root, name="Typed Into"):
    """One small return, and the rows the editor would send back."""
    assert run(capsys, "create", stdin={
        "household": HOUSEHOLD, "return_name": name, "form": "1040",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    return where(demo_root, name)


def test_create_reads_a_members_string_as_lines_and_never_as_letters(capsys, demo_root):
    spec = {"household": "Doe Family", "return_name": "1040 - Jane Doe", "form": "1040",
            "items": [{"identifier": "A01", "document": "W-2"}]}
    code, payload = run(capsys, "create", stdin={**spec, "members": "Jane Doe\nJohn  Doe\n\n"})
    assert code == 0, payload
    from tracker.layout import private_household_dir

    held = load_household_info(private_household_dir(demo_root, "Doe Family"))
    assert held.members == ("Jane Doe", "John Doe")

    # Anything that is neither a list nor text is refused by name, and
    # nothing is written: no household folder for the household it named.
    code, payload = run(capsys, "create", stdin={**spec, "household": "Roe Family",
                                                 "return_name": "1040 - Roe", "members": 7})
    assert code == 1 and payload["error"] == f"{screen_words.MEMBERS_LABEL} must be a list of names"
    assert not private_household_dir(demo_root, "Roe Family").exists()


def test_create_and_edit_household_parse_members_through_one_helper(capsys, demo_root):
    from tracker.layout import private_household_dir

    typed = "  Jane   Doe \nJohn Doe\n"
    code, payload = run(capsys, "create", stdin={
        "household": "Doe Family", "return_name": "1040 - Jane Doe", "form": "1040",
        "members": typed, "items": [{"identifier": "A01", "document": "W-2"}]})
    assert code == 0, payload
    created = load_household_info(private_household_dir(demo_root, "Doe Family")).members

    engagement = where(demo_root, "1040 - Jane Doe", household="Doe Family")
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": ["Someone Else"]})
    assert code == 0, payload
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": typed})
    assert code == 0, payload
    edited = load_household_info(private_household_dir(demo_root, "Doe Family")).members
    assert created == edited == ("Jane Doe", "John Doe")
    assert household_edit._members_from_spec(["Jane  Doe", " ", "John Doe"]) == ("Jane Doe", "John Doe")
    assert household_edit._members_from_spec(None) == household_edit._members_from_spec("") == ()
    for odd in (7, {"a": "b"}, True):
        with pytest.raises(ManifestError, match="must be a list of names"):
            household_edit._members_from_spec(odd)


def test_a_persons_name_longer_than_the_text_rule_is_refused_by_name(capsys, demo_root):
    from tracker.manifest import list_head

    engagement = _a_return_to_type_into(capsys, demo_root)
    rows = payload_of_state(capsys, engagement)["rules"]
    before = (list_head(engagement), ledger.path_for(engagement).read_bytes())
    people = [{"kind": "taxpayer", "name": "J" * 10_000, "spellings": []}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"people": people}})
    assert code == 1
    assert payload["error"] == (f"{api.PEOPLE_LABEL}: the Taxpayer's name must be one line of "
                                "text of at most 1000 characters, with no control character")
    assert (list_head(engagement), ledger.path_for(engagement).read_bytes()) == before


def _a_spelling_typed_is_refused_and_nothing_is_written(capsys, demo_root, typed):
    from tracker.manifest import list_head

    engagement = _a_return_to_type_into(capsys, demo_root)
    rows = payload_of_state(capsys, engagement)["rules"]
    before = (list_head(engagement), ledger.path_for(engagement).read_bytes())
    people = [{"kind": "taxpayer", "name": "Jane Smith", "spellings": [typed]}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"people": people}})
    assert code == 1
    assert payload["error"] == _SPELLING_REFUSED
    assert (list_head(engagement), ledger.path_for(engagement).read_bytes()) == before


def test_a_typed_spelling_of_1001_characters_is_refused_by_name_and_nothing_is_written(
        capsys, demo_root):
    """P304: a spelling is searched on every page as the name is, so it is
    held to the name's rule where it is typed - one line, at most 1,000
    characters, no control character."""
    _a_spelling_typed_is_refused_and_nothing_is_written(capsys, demo_root, "J " + "x" * 999)


def test_a_typed_spelling_with_a_control_character_is_refused_and_nothing_is_written(
        capsys, demo_root):
    _a_spelling_typed_is_refused_and_nothing_is_written(capsys, demo_root, "Jane\x07 Smith")


def test_a_typed_spelling_of_exactly_the_text_rule_saves(capsys, demo_root):
    engagement = _a_return_to_type_into(capsys, demo_root)
    rows = payload_of_state(capsys, engagement)["rules"]
    longest = "J " + "x" * 998                                   # 1,000 characters, two words
    assert len(longest) == 1000
    people = [{"kind": "taxpayer", "name": "Jane Smith", "spellings": [longest]}]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": rows, "engagement": {"people": people}})
    assert code == 0, payload
    [saved] = load_engagement_info(engagement).people
    assert saved.spellings == (longest,)


def test_a_stored_spelling_past_the_rule_refuses_a_row_only_save_and_names_the_person(
        capsys, demo_root):
    """P306: the editor sends the people block back on every save and the
    store's gate does not judge a spelling (P304), so a return written
    before the rule keeps one and a row-only edit is refused. The refusal
    says whose spelling, and nothing is written."""
    from tests.builders import TEST_YEAR
    from tracker.manifest import RequestItem, list_head
    from tracker.records import Person

    held = "J " + "x" * 1999
    make_engagement(demo_root, [RequestItem(identifier="A01", document="W-2")],
                    household=HOUSEHOLD, return_name="Stored Past The Rule",
                    people=(Person(kind="taxpayer", name="Jane Smith", spellings=(held,)),))
    engagement = where(demo_root, "Stored Past The Rule", year=TEST_YEAR)
    [stored] = load_engagement_info(engagement).people
    assert stored.spellings == (held,)
    rows = payload_of_state(capsys, engagement)["rules"]
    before = (list_head(engagement), ledger.path_for(engagement).read_bytes())
    people = [{"kind": stored.kind, "name": stored.name, "spellings": list(stored.spellings)}]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"items": [{**rows[0], "document": "W2"}],
                               "engagement": {"people": people}})

    assert code == 1
    assert payload["error"] == _SPELLING_REFUSED
    assert (list_head(engagement), ledger.path_for(engagement).read_bytes()) == before


def test_the_firms_name_and_phone_are_held_to_the_one_line_text_rule(capsys, tmp_path, monkeypatch):
    from tracker.settings import ENV_SETTINGS_DIR, clients_root, firm, firm_phone, settings_path

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    clients = tmp_path / "Clients"
    clients.mkdir()
    refused = [
        ({"firm": "F" * 1001}, f"{screen_words.FIRM_NAME_LABEL} must be one line"),
        ({"phone": "555-0100\n555-0101"}, f"{screen_words.FIRM_PHONE_LABEL} must be one line"),
        ({"firm": "Park\x00 CPA"}, f"{screen_words.FIRM_NAME_LABEL} must be one line"),
    ]
    for extra, start in refused:
        code, payload = run(capsys, "set-root", stdin={"root": str(clients), **extra})
        assert code == 1 and payload["error"].startswith(start), payload
        # Refused before the root is written: nothing was saved at all.
        assert clients_root() is None and not settings_path().exists()
    code, payload = run(capsys, "set-root", stdin={
        "root": str(clients), "firm": "F" * 1000, "phone": "555-0100 x12"})
    assert code == 0, payload
    assert firm() == "F" * 1000 and firm_phone() == "555-0100 x12"
    # Blank stays allowed: it clears the value.
    code, payload = run(capsys, "set-root", stdin={"root": str(clients), "firm": "", "phone": ""})
    assert code == 0 and firm() == "" and firm_phone() == ""


def test_a_short_name_hiding_a_right_to_left_override_is_refused_in_the_editor(capsys, demo_root):
    engagement = _a_return_to_type_into(capsys, demo_root)
    rows = payload_of_state(capsys, engagement)["rules"]
    before = ledger.path_for(engagement).read_bytes()
    for hidden in ("\u202e", "\u200d"):  # right-to-left override, zero-width joiner
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
            "items": [{**rows[0], "short_title": f"W-2{hidden}"}], "engagement": {}})
        assert code == 1
        assert payload["error"].startswith("Row 1: Short name may not contain an invisible character")
        assert "U+" in payload["error"]
    assert ledger.path_for(engagement).read_bytes() == before


def test_the_editor_refuses_every_invisible_character_in_an_identifier_or_a_short_name(
        capsys, demo_root):
    """P290 (amended): where a person types, the full rule - the spoofing
    controls, and the no-break space and soft hyphen a paste leaves - and
    the sentence names the character by code point without carrying it."""
    engagement = _a_return_to_type_into(capsys, demo_root)
    rows = payload_of_state(capsys, engagement)["rules"]
    before = ledger.path_for(engagement).read_bytes()
    for field, typed, named in (
            ("identifier", "W-2\u202efdp", "U+202E RIGHT-TO-LEFT OVERRIDE"),
            ("identifier", "A\u00a001", "U+00A0 NO-BREAK SPACE"),
            ("short_title", "W\u200d2", "U+200D ZERO WIDTH JOINER"),
            ("short_title", "W\u00adX", "U+00AD SOFT HYPHEN")):
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
            "items": [{**rows[0], field: typed}], "engagement": {}})
        assert code == 1, (field, named)
        assert named in payload["error"] and payload["error"].startswith("Row 1: ")
        assert not any(character in payload["error"] for character in "\u202e\u00a0\u200d\u00ad")
    assert ledger.path_for(engagement).read_bytes() == before


def test_a_list_holding_a_long_identifier_stays_editable_and_renames_it_away(capsys, demo_root):
    """P291 (amended): the 80-character cap is for a new or changed
    identifier, never one the list already holds - a rename to 120
    characters used to leave a list the editor would not save."""
    from dataclasses import replace

    from tracker.actions import RENAME_CASE_ONLY
    from tracker.locking import engagement_lock
    from tracker.manifest import list_head, load_manifest
    from tracker.records import rule_to_json

    engagement = _a_return_to_type_into(capsys, demo_root)
    long_one = "L" * 120
    [item] = load_manifest(engagement)
    with engagement_lock(engagement):
        store.record(store.connect(), engagement, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [rule_to_json(replace(item, identifier=long_one))],
            ledger.REMOVED_KEY: ["A01"]}))
    rows = payload_of_state(capsys, engagement)["rules"]
    assert [row["identifier"] for row in rows] == [long_one]

    # An edit that leaves the held identifier alone is saved.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "document": "W-2 Wage Statements"}], "engagement": {}})
    assert code == 0, payload
    # A new row of the same length is the cap's, and a rename to one is too.
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [*rows, {**rows[0], "identifier": "M" * 120}], "engagement": {}})
    assert code == 1 and "Row 2: Identifier" in payload["error"]
    assert "may have at most 80 characters, got 120" in payload["error"]
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "from": long_one, "to": "M" * 120, "head": list_head(engagement)})
    assert code == 1 and "may have at most 80 characters, got 120" in payload["error"]
    # Section 16's way out of the dead end: Rename refuses a change of case
    # alone and sends the person to the editor, and the editor saves it.
    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "from": long_one, "to": long_one.lower(), "head": list_head(engagement)})
    assert code == 1
    assert payload["error"] == RENAME_CASE_ONLY.format(
        old=layout.quoted(long_one), new=layout.quoted(long_one.lower()))
    assert ledger.path_for(engagement).read_bytes() == before
    rows = payload_of_state(capsys, engagement)["rules"]
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "identifier": long_one.lower()}], "engagement": {}})
    assert code == 0, payload
    assert [rule["identifier"] for rule in payload["state"]["rules"]] == [long_one.lower()]
    long_one = long_one.lower()
    # Renamed away to a short one, it is renamed; a held long one can be.
    code, payload = run(capsys, "rename", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "from": long_one, "to": "B01", "head": list_head(engagement)})
    assert code == 0, payload
    assert [rule["identifier"] for rule in payload["state"]["rules"]] == ["B01"]


def test_a_list_holding_what_an_older_paste_left_stays_editable_and_a_changed_spelling_is_typed(
        capsys, demo_root):
    """P290 and P291 (the second review's G1): a no-break space or a soft
    hyphen the store admits, held in a record from before the typed rule,
    never stops a save of the list - an edit to another column, or an older
    window's row that sends only the identifier and the Document. A value
    changed from what the list holds is new, and gets the typed rule."""
    from dataclasses import replace

    from tracker.locking import engagement_lock
    from tracker.manifest import load_manifest
    from tracker.records import rule_to_json

    engagement = _a_return_to_type_into(capsys, demo_root)
    pasted = "A\u00a001"
    [item] = load_manifest(engagement)
    with engagement_lock(engagement):
        store.record(store.connect(), engagement, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [rule_to_json(replace(item, identifier=pasted, short_title="W\u00adX"))],
            ledger.REMOVED_KEY: ["A01"]}))
    rows = payload_of_state(capsys, engagement)["rules"]
    assert [(row["identifier"], row["short_title"]) for row in rows] == [(pasted, "W\u00adX")]

    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "document": "W-2 Wage Statements"}], "engagement": {}})
    assert code == 0, payload
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{"identifier": pasted, "document": "W-2 Forms"}], "engagement": {}})
    assert code == 0, payload
    assert [(rule["document"], rule["short_title"]) for rule in payload["state"]["rules"]] == [
        ("W-2 Forms", "W\u00adX")]

    rows = payload_of_state(capsys, engagement)["rules"]
    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "identifier": "B\u00a001"}], "engagement": {}})
    assert code == 1
    assert payload["error"] == ("Row 1: Identifier 'B<U+00A0>01' may not contain an invisible "
                                "character (U+00A0 NO-BREAK SPACE)")
    assert ledger.path_for(engagement).read_bytes() == before
    # A change of case alone is the same request (decision 160), not a new one.
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "identifier": "a\u00a001"}], "engagement": {}})
    assert code == 0, payload
    assert [rule["identifier"] for rule in payload["state"]["rules"]] == ["a\u00a001"]


def test_a_held_document_hiding_a_right_to_left_override_is_refused_by_row_and_nothing_is_written(
        capsys, demo_root, monkeypatch):
    """P301, defence in depth: a record the store admitted (here written past
    the gate, a row it holds at the current admission) holds a Document with
    a right-to-left override. An edit that sends it back, with a blank short
    name, is refused in the editor's words - the row and the Document, the
    character by code point - and not as an unnamed refused change; and
    nothing is written. This is not the upgrade path: a household whose
    stored Document was spoofed under an older admission is stopped by the
    store's malformed-line refusal, which the editor's ``state`` call
    refuses too, so it is repaired as any refused line is, by the runbook's
    malformed-line repair (its section 9: say which return and which line),
    not by retyping in the editor."""
    from dataclasses import replace

    from tracker.locking import engagement_lock
    from tracker.manifest import load_manifest
    from tracker.records import rule_to_json

    engagement = _a_return_to_type_into(capsys, demo_root)
    [item] = load_manifest(engagement)
    spoofed = "W-2\u202efdp.exe"
    monkeypatch.setattr(store, "_refuse_a_malformed_line", lambda *args, **kwargs: None)
    with engagement_lock(engagement):
        store.record(store.connect(), engagement, ledger.new(ledger.RULES_CHANGED, **{
            ledger.RULES_KEY: [rule_to_json(replace(item, document=spoofed, short_title=""))]}))
    monkeypatch.undo()
    try:
        rows = payload_of_state(capsys, engagement)["rules"]
        assert [row["document"] for row in rows] == [spoofed]

        before = ledger.path_for(engagement).read_bytes()
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
            "items": [{**rows[0], "short_title": ""}], "engagement": {}})
        assert code == 1
        assert payload["error"] == ("Row 1: Document 'W-2<U+202E>fdp.exe' may not contain an "
                                    "invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)")
        assert ledger.path_for(engagement).read_bytes() == before
        # Retyped, the row saves.
        code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
            "items": [{**rows[0], "document": "W-2 Wage Statements", "short_title": ""}],
            "engagement": {}})
        assert code == 0, payload
    finally:
        # The journal keeps the line written past the gate, which a rebuild of
        # it (the suite's store fixture) refuses; the record is removed as the
        # store tests' `by_hand` fixture removes theirs.
        ledger.path_for(engagement).unlink(missing_ok=True)


def test_a_long_identifier_is_refused_as_too_long_and_never_as_a_long_folder_name(
        capsys, demo_root):
    engagement = _a_return_to_type_into(capsys, demo_root)
    rows = payload_of_state(capsys, engagement)["rules"]
    before = ledger.path_for(engagement).read_bytes()
    code, payload = run(capsys, "edit", api.ENGAGEMENT_FLAG, str(engagement), stdin={
        "items": [{**rows[0], "identifier": "A" * 200}], "engagement": {}})
    assert code == 1
    assert payload["error"].startswith("Row 1: Identifier ")
    assert "may have at most 80 characters, got 200" in payload["error"]
    assert "shorten the household" not in payload["error"]
    assert len(payload["error"]) < 300, "and the echo of what was typed is cut"
    assert ledger.path_for(engagement).read_bytes() == before


def test_an_overlong_member_is_refused_as_a_change_not_a_corrupt_record(capsys, demo_root):
    engagement = _a_return_to_type_into(capsys, demo_root)
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(engagement),
                        stdin={"members": ["M" * 10_000]})
    assert code == 1
    assert payload["error"] == ("This change carries details whose 'members' must be a list of text; "
                                "nothing was written")
    assert "malformed" not in payload["error"] and "line " not in payload["error"]


def test_stdin_that_is_not_json_is_refused_like_a_non_object_and_logs_nothing(
        capsys, demo_root, monkeypatch):
    import io

    from tracker.errlog import error_log_path

    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"not json"), encoding="utf-8"))
    code = api.main(["set-schedule"])
    payload = one_reply(capsys.readouterr().out)
    assert code == 1 and payload["error"] == screen_words.NOT_A_SPEC
    log = error_log_path()
    assert not log.exists() or log.read_text(encoding="utf-8") == ""


def test_stdin_that_is_not_utf8_is_refused_like_a_non_object_and_logs_nothing(
        capsys, demo_root, monkeypatch):
    import io

    from tracker.errlog import error_log_path

    monkeypatch.setattr("sys.stdin", io.TextIOWrapper(io.BytesIO(b"\xff\xfe{"), encoding="utf-8"))
    code = api.main(["set-schedule"])
    payload = one_reply(capsys.readouterr().out)
    assert code == 1 and payload["error"] == screen_words.NOT_A_SPEC
    log = error_log_path()
    assert not log.exists() or log.read_text(encoding="utf-8") == ""
