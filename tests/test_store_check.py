"""Tests for tracker/store_check.py - the gate, and the export a person keeps.

The check's main claim is not made here: it is the autouse fixture in
tests/plugin_agreement.py, which builds a store for every engagement the suite
leaves behind and asks :func:`tracker.store_check.check` to hold it to the
record. What is made here is the check's own behaviour - that it names the
engagement, the row and the field; that an engagement the store never saw
is said so rather than passed; that it reaches the taught words, the moves
left open and a line today's admission refuses; that a journal that is gone
is one sentence; and that a request is one request whatever its case
(decision 136) - and the export's: every cell as text, a formula-shaped name
kept a name, and nothing in the files the index and the request list do not
carry. Neither looks at the verdict cache.

Every test here came from tests/test_store.py with P324 (SPEC-architecture-p3
P3.4), cut and pasted, its name kept: its subject is the check's verdict or
the export's files. The only edits are the calls, which ask
``tracker.store_check`` where they asked the store. The fixtures and helpers
they share with the store's tests are ``tests/store_helpers.py``'s.
"""

from __future__ import annotations

import csv

import pytest

from tests import store_helpers
from tests.builders import drop, seed_statuses, sort
from tests.store_helpers import (
    DAY1,
    DAY2,
    _a_rule,
    a_pass,
    build,
    cli,
    edit_rules,
    id_of,
    learned,
    said,
    scanned,
    unlearned,
)
from tracker import ledger, store, store_check
from tracker.locking import engagement_lock
from tracker.manifest import Status, load_engagement_info, load_manifest, save_rules
from tracker.records import StatusUpdate

#: The store's fixtures, from ``tests/store_helpers.py``: each named once so
#: that every claim below can ask for it.
root = store_helpers.root
engagement = store_helpers.engagement
by_hand = store_helpers.by_hand
conn = store_helpers.conn


# ---------------------------------------------------------------- the export ----


def test_the_export_writes_every_cell_as_text_and_a_formula_shaped_name_stays_a_name(
        conn, root, engagement, tmp_path):
    drop(engagement, "=SUM scan.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)

    written = store_check.export(conn, tmp_path / "out")

    assert [path.name for path in written] == [
        store_check.DOCUMENTS_CSV, store_check.REQUESTS_CSV, store_check.ENGAGEMENTS_CSV]
    for path in written:
        raw = path.read_bytes()
        assert raw.startswith(b"\xef\xbb\xbf")         # Excel opens it as UTF-8
        assert b"\r\n" not in raw
    documents = list(csv.DictReader(
        (tmp_path / "out" / store_check.DOCUMENTS_CSV).read_text(encoding="utf-8-sig").splitlines()))
    assert len(documents) == 1
    # Behind an apostrophe: a spreadsheet shows the name and never runs it.
    assert documents[0]["original_name"] == "'=SUM scan.pdf"
    assert all(isinstance(value, str) for value in documents[0].values())


def test_the_export_disarms_a_request_named_like_a_command(conn, root, engagement, tmp_path):
    """A document name typed into the request list as a DDE formula reaches
    requests.csv behind an apostrophe, whatever the quoting: a spreadsheet
    evaluates a cell that begins with = + - @ or a tab on the way in."""
    edit_rules(engagement, A01={"document": "=cmd|' /C calc'!A0"})
    build(conn, root, engagement)
    store_check.export(conn, tmp_path / "out")
    text = (tmp_path / "out" / store_check.REQUESTS_CSV).read_text(encoding="utf-8-sig")
    assert "'=cmd|' /C calc'!A0" in text.replace('""', "'")
    assert not any(line.split(",")[2].startswith(('"=', "=")) for line in text.splitlines()[1:])


def test_the_export_carries_nothing_the_index_and_the_request_list_do_not(
        conn, root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane Q Client")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)

    store_check.export(conn, tmp_path / "out")

    for path in (tmp_path / "out").iterdir():
        text = path.read_text(encoding="utf-8-sig")
        # A word out of the document itself, which no reading of the index
        # or the request list ever carries.
        assert "Jane Q Client" not in text


# ----------------------------------------------------------- the verdict cache ----


def test_the_verdict_tables_are_not_in_the_check_and_not_in_the_export(root, engagement, tmp_path):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025 Jane Q Client")
    a_pass(engagement)
    live = store.connect()
    engagement_id = store._engagement_row(live, engagement)["id"]
    stored = list(live.execute(f"SELECT digest, fingerprint, verdict FROM {store.VERDICTS_TABLE} "
                               "WHERE engagement_id = ?", (engagement_id,)))
    assert stored
    # No client text: a verdict row carries the firm's words - the keyword,
    # the Period - and never a word of the document that is not a keyword.
    for row in stored:
        assert "Jane" not in row["verdict"] and "Client" not in row["verdict"]

    assert store_check.check(live, root, engagement) == []
    live.execute(f"DELETE FROM {store.VERDICTS_TABLE} WHERE engagement_id = ?", (engagement_id,))
    live.execute(f"DELETE FROM {store.FILE_MEMOS_TABLE} WHERE engagement_id = ?", (engagement_id,))
    assert store_check.check(live, root, engagement) == []          # the check never looked
    live.execute(f"INSERT INTO {store.VERDICTS_TABLE} VALUES (?, ?, ?, ?, ?)",
                 (engagement_id, "feedface", "0123456789abcdef", 1, '{"ok": false}'))
    assert store_check.check(live, root, engagement) == []          # nor at a row nothing wrote

    written = store_check.export(live, tmp_path / "out")
    assert [path.name for path in written] == [store_check.DOCUMENTS_CSV, store_check.REQUESTS_CSV,
                                               store_check.ENGAGEMENTS_CSV]
    for path in written:
        text = path.read_text(encoding="utf-8-sig")
        assert "feedface" not in text and "0123456789abcdef" not in text
        assert stored[0]["fingerprint"] not in text


# ------------------------------------------------------- the readers, checked ----


def test_the_check_names_the_engagement_the_row_and_the_field(conn, root, engagement):
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    sort(engagement, today=DAY1)
    build(conn, root, engagement)
    assert said(conn, root, engagement) == []

    conn.execute("UPDATE documents SET reason = 'something else'")
    sentence = said(conn, root, engagement)[0]
    assert engagement.name in sentence and "reason" in sentence and "something else" in sentence


def test_an_engagement_the_store_has_never_seen_is_said_so_rather_than_passed(
        conn, root, engagement):
    store.forget(conn, engagement)                # the create's row, gone
    sentence = said(conn, root, engagement)
    assert len(sentence) == 1 and "does not hold this engagement" in sentence[0]


def test_check_reports_a_learned_keyword_in_the_store_and_not_in_the_record_and_the_other_way_round(
        conn, root, by_hand):
    """The gate reaches the learned table at last (decision 113).

    Until now it compared the documents, the statuses and the rules, and
    this table was the one thing in the store the record could not vouch
    for: a row planted or dropped behind the journal's back said nothing.
    """
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "lender"))
    assert said(conn, root, by_hand) == []

    held = conn.execute("SELECT engagement_id, seq FROM learned_keywords").fetchone()
    conn.execute('INSERT INTO learned_keywords (engagement_id, "identifier", keyword, seq) '
                 "VALUES (?, ?, ?, ?)", (held["engagement_id"], "a01", "escrow", held["seq"] + 1))
    (sentence,) = said(conn, root, by_hand)
    assert by_hand.name in sentence and "a01" in sentence
    assert "'lender', 'escrow'" in sentence and "['lender']" in sentence

    conn.execute("DELETE FROM learned_keywords")
    (sentence,) = said(conn, root, by_hand)
    assert "a01" in sentence and "[]" in sentence and "['lender']" in sentence

    store.rebuild_engagement(conn, root, by_hand)
    assert said(conn, root, by_hand) == []


# ------------------------------------------- a request respelled by case (136) ----


def test_a_status_scanned_under_a_case_respelled_identifier_is_one_request_to_the_check(
        conn, root, by_hand):
    """Decision 136: ``A01`` and ``a01`` are one request, so the later scan
    is its status. The store keys it that way; the check used to fold the
    two spellings apart and name the earlier one as the record's word."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED))
        store.record(conn, by_hand, scanned(a01=Status.MISSING))

    held = conn.execute('SELECT status FROM statuses WHERE "identifier" = ?', ("a01",)).fetchone()
    assert held["status"] == Status.MISSING
    assert said(conn, root, by_hand) == []


def test_keywords_taught_under_two_spellings_of_one_request_are_checked_in_the_order_they_were_taught(
        conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "alpha"), learned("a01", "beta"),
                     learned("A01", "gamma"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("alpha", "beta", "gamma")}
    assert said(conn, root, by_hand) == []


def test_a_word_retaught_under_the_other_spelling_is_checked_last_once(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "alpha"), learned("a01", "beta"),
                     learned("A01", "gamma"), learned("a01", "alpha"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("beta", "gamma", "alpha")}
    assert said(conn, root, by_hand) == []


def test_a_word_taken_back_under_the_other_spelling_is_gone_from_both_sides(conn, root, by_hand):
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, learned("A01", "alpha"), learned("A01", "beta"),
                     unlearned("a01", "alpha"))

    assert store.learned_keywords(conn, by_hand) == {"a01": ("beta",)}
    assert said(conn, root, by_hand) == []
    build(conn, root, by_hand)                    # and a store built from nothing agrees
    assert said(conn, root, by_hand) == []


def test_the_check_still_names_a_status_planted_in_the_store_behind_the_journals_back(
        conn, root, by_hand):
    """The gate keeps its teeth: keying the record's side without case
    joins two spellings of one request, and nothing else."""
    build(conn, root, by_hand)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, scanned(A01=Status.RECEIVED), learned("A01", "lender"))
    assert said(conn, root, by_hand) == []
    engagement_id = id_of(conn, by_hand)

    conn.execute('INSERT INTO statuses (engagement_id, "identifier", status, file_count, seq) '
                 "VALUES (?, ?, ?, ?, ?)", (engagement_id, "c01", Status.RECEIVED, 1, 99))
    (sentence,) = said(conn, root, by_hand)
    assert "c01" in sentence and "in the store and none in the record" in sentence
    conn.execute('DELETE FROM statuses WHERE "identifier" = ?', ("c01",))

    conn.execute('UPDATE statuses SET status = ? WHERE "identifier" = ?', (Status.MISSING, "a01"))
    (sentence,) = said(conn, root, by_hand)
    assert "A01" in sentence and repr(Status.MISSING) in sentence and repr(Status.RECEIVED) in sentence

    conn.execute("DELETE FROM statuses")
    (sentence,) = said(conn, root, by_hand)
    assert "A01" in sentence and "in the record and none in the store" in sentence

    conn.execute("DELETE FROM learned_keywords")
    problems = said(conn, root, by_hand)
    assert any("a01" in p and "[]" in p and "['lender']" in p for p in problems)

    store.rebuild_engagement(conn, root, by_hand)
    assert said(conn, root, by_hand) == []


def test_an_end_to_end_respelling_leaves_the_check_empty(conn, root, engagement):
    """The way it happens in the app: a scan and a filing that taught a
    word under ``A01``, the person retypes it ``a01``, then a scan, a
    filing that teaches, and the first word taken back in the editor."""
    from dataclasses import replace

    from tracker.filer import assign_review_file
    from tracker.manifest import unlearn_keyword

    drop(engagement, "scan0012.pdf", "nothing the rules recognise")
    parked = sort(engagement, today=DAY1).review[0]
    assign_review_file(engagement, parked.pbc_location, "A01", keyword="lender", today=DAY1)
    seed_statuses(engagement, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1,
                                                   received_date=DAY1)})

    rules = load_manifest(engagement)
    respelled = [replace(row, identifier="a01") if row.identifier == "A01" else row for row in rules]
    assert save_rules(engagement, respelled, load_engagement_info(engagement)).removed == ("A01",)

    seed_statuses(engagement, {"a01": StatusUpdate(status=Status.PARTIAL, file_count=1,
                                                   received_date=DAY2)})
    drop(engagement, "scan0013.pdf", "nothing the rules recognise either")
    parked = sort(engagement, today=DAY2).review[0]
    assign_review_file(engagement, parked.pbc_location, "a01", keyword="escrow", today=DAY2)
    unlearn_keyword(engagement, "a01", "lender")

    build(conn, root, engagement)
    assert store.learned_keywords(conn, engagement) == {"a01": ("escrow",)}
    assert store_check.check(conn, root, engagement) == []
    live = store.connect()                        # the store as the app left it, not a rebuild
    assert store_check.check(live, root, engagement) == []


# ---------------------------------- the moves begun and not finished (119) ----


def test_the_check_names_a_move_the_two_sides_do_not_agree_is_open(conn, root, engagement,
                                                                   monkeypatch):
    """Decision 119: a recovery finishes what this table says is open, so a
    table that kept an intent the journal has closed would move a file the
    record has already recorded. The check compares the two folds and says
    which key they disagree about."""
    from tests.builders import killed_at_the_record

    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")
    killed_at_the_record(monkeypatch)
    with pytest.raises(KeyboardInterrupt):
        sort(engagement, today=DAY1)
    build(conn, root, engagement)
    assert said(conn, root, engagement) == []
    [open_move] = store.open_intents(conn, engagement)

    conn.execute("DELETE FROM intents")
    sentence = said(conn, root, engagement)[0]
    assert engagement.name in sentence and open_move[ledger.KEY_KEY] in sentence
    assert "not in the store" in sentence

    build(conn, root, engagement)                    # and a rebuild puts it back
    assert said(conn, root, engagement) == []
    assert store.open_intents(conn, engagement) == [open_move]


# ----------------------------------- the record is untrusted input (187) ----


def test_the_store_check_names_a_line_the_gate_now_refuses(conn, root, by_hand, monkeypatch):
    """A line an earlier version applied that today's rule refuses is named
    by ``check`` on the day of the upgrade (decision 187), without the store
    being deleted to find it: every line of every journal is judged again."""
    build(conn, root, by_hand)
    runaway = ledger.new(ledger.RULES_CHANGED, rules=[_a_rule(date_pattern=r"(\d+)+x")])
    monkeypatch.setattr(store, "_refuse_a_malformed_line", lambda *args, **kwargs: None)
    with engagement_lock(by_hand):
        store.record(conn, by_hand, runaway)
    monkeypatch.undo()

    problems = store_check.check(conn, root, by_hand)

    assert len(problems) == 1
    assert "line 2 of the record is malformed" in problems[0] and "'date_pattern'" in problems[0]


# ------------------------ SPEC-162 rulings 5 and 6, kept by decision 188 ----


def test_store_check_reports_a_journal_that_is_gone(conn, root, by_hand, tmp_path):
    """T11 (ruling 5): a journal that is gone is one sentence naming the
    engagement and what the store still holds, saying where to restore it
    from - from the check of the folder, and from the command line's check
    of the whole root, which no walk would otherwise reach."""
    build(conn, root, by_hand)
    applied = store._engagement_row(conn, by_hand, root)["applied_seq"]
    ledger.path_for(by_hand).unlink()
    rel = store.engagement_path(root, by_hand)
    said = store.JOURNAL_GONE.format(n=applied, engagement=rel)

    assert store_check.check(conn, root, by_hand) == [said]
    assert said in store.gone_journals(conn, root)
    conn.commit()
    result = cli(tmp_path / "app" / store.STORE_FILENAME, "check", root)
    assert result.returncode == 1 and said in result.stdout, result.stdout + result.stderr
