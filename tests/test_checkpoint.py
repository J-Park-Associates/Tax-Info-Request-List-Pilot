"""Tests for tracker/checkpoint.py - what this machine last saw of each record.

The checkpoint is proved against records in ``tests/test_store.py`` (where
the store holds a record to it), ``tests/test_runner.py`` (the practice
page names what it accepted) and ``tests/test_api.py`` (a person
acknowledges). What is claimed here is the file's own behaviour: where it
lives, what it keeps, the one switch, the intent, the root it belongs to,
its version discipline and its command line. All data is fabricated.
"""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from tracker import checkpoint, store

REPO = Path(__file__).resolve().parents[1]
KEY = "J Park & Associates/Smith Family/2025/1040 - Test Client"


@pytest.fixture
def held(tmp_path):
    with checkpoint.opened(tmp_path / "app" / checkpoint.CHECKPOINT_FILENAME) as connection:
        yield connection


def cli(*args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, "-m", "tracker.checkpoint", *map(str, args)],
                          cwd=REPO, capture_output=True, text=True, encoding="utf-8")


def test_the_checkpoint_lives_beside_the_store_and_is_not_the_store(tmp_path):
    store_file = tmp_path / "home" / store.STORE_FILENAME
    assert checkpoint.path_for(store_file) == store_file.with_name(checkpoint.CHECKPOINT_FILENAME)
    assert checkpoint.path_for(store_file) != store_file


def test_a_line_from_another_machine_is_not_refused_until_the_study_is_decided():
    """Decision 159, question C-1: Jason chose (a) - named until acknowledged."""
    assert checkpoint.foreign_lines_refused() is False


def test_what_is_vouched_for_is_what_was_advanced(held):
    assert checkpoint.vouched(held, KEY) is None
    checkpoint.advance(held, KEY, 3, "c3", seeded=True)
    assert checkpoint.vouched(held, KEY) == (3, "c3")
    checkpoint.advance(held, KEY, 5, "c5", seeded=False)
    assert checkpoint.vouched(held, KEY) == (5, "c5")
    checkpoint.forget(held, KEY)
    assert checkpoint.vouched(held, KEY) is None


def test_the_intent_holds_until_the_count_reaches_it(held):
    """A writer says the chain after each line it is about to write; a
    reader that applies part of the batch leaves the rest expected; the
    writer's own advance clears it. Only exactly those lines are its own
    (the review's M1)."""
    with pytest.raises(checkpoint.CheckpointError, match="seeded before it is written to"):
        checkpoint.expect(held, KEY, 1, ["c2", "c3"])
    checkpoint.advance(held, KEY, 1, "c1", seeded=True)
    checkpoint.expect(held, KEY, 1, ["c2", "c3"])
    said = checkpoint.intent(held, KEY)
    assert said == checkpoint.Intent(start=1, heads=("c2", "c3"))
    assert said.owns(2, "c2") and said.owns(3, "c3")
    assert not said.owns(3, "forged") and not said.owns(4, "c3") and not said.owns(1, "c1")
    checkpoint.advance(held, KEY, 2, "c2", seeded=False)
    assert checkpoint.intent(held, KEY) == said
    checkpoint.advance(held, KEY, 3, "c3", seeded=False)
    assert checkpoint.intent(held, KEY) is None
    checkpoint.expect(held, KEY, 3, ["c4"])
    checkpoint.expect(held, KEY, 3, [])                         # an empty intent clears it
    assert checkpoint.intent(held, KEY) is None


def test_a_checkpoint_that_will_not_open_is_refused_by_name_and_never_set_aside(tmp_path):
    """The review's S4, as ruled: a damaged checkpoint is what a person must
    see - refused naming the file and the runbook's step, left where it is."""
    path = tmp_path / checkpoint.CHECKPOINT_FILENAME
    path.write_bytes(b"this is not a database, fabricated" * 40)
    for opening in (checkpoint.open, checkpoint.open_read_only):
        with pytest.raises(checkpoint.CheckpointError) as refused:
            opening(path)
        said = str(refused.value)
        assert str(path) in said and "cannot read this machine's record checkpoint" in said
        assert "runbook §6" in said and "moment of trust" in said
    assert sorted(p.name for p in tmp_path.iterdir()) == [checkpoint.CHECKPOINT_FILENAME]


def test_a_line_from_another_machine_is_named_until_it_is_acknowledged(held):
    assert checkpoint.note_foreign(held, KEY, [(4, "laptop-2", "2026-09-26T10:00:00Z")]) == 1
    assert checkpoint.note_foreign(held, KEY, [(4, "laptop-2", "2026-09-26T10:00:00Z")]) == 0
    assert [(one.key, one.seq, one.host) for one in checkpoint.unacknowledged(held)] == [
        (KEY, 4, "laptop-2")]
    assert checkpoint.acknowledge(held, KEY) == 1
    assert checkpoint.unacknowledged(held) == []
    assert checkpoint.acknowledge(held, KEY) == 0


def test_the_root_is_claimed_once_and_moves_only_when_a_person_says(held, tmp_path):
    assert checkpoint.root_of(held) is None
    assert checkpoint.claim_root(held, str(tmp_path / "Clients")) == str(tmp_path / "Clients")
    assert checkpoint.claim_root(held, str(tmp_path / "Copy")) == str(tmp_path / "Clients")
    checkpoint.move_root(held, str(tmp_path / "Moved"))
    assert checkpoint.root_of(held) == str(tmp_path / "Moved")


def test_an_older_checkpoint_is_set_aside_and_a_newer_one_refused(tmp_path, monkeypatch):
    """The store's discipline (decision 159, E3), for the checkpoint's own version."""
    path = tmp_path / checkpoint.CHECKPOINT_FILENAME
    checkpoint.open(path).close()
    newer = sqlite3.connect(path)
    newer.execute(f"PRAGMA user_version = {checkpoint.CHECKPOINT_VERSION + 1}")
    newer.close()
    with pytest.raises(checkpoint.CheckpointError, match="install that version again"):
        checkpoint.open(path)

    older = path.with_name("older.db")
    checkpoint.open(older).close()
    monkeypatch.setattr(checkpoint, "CHECKPOINT_VERSION", 2)       # a later version meets version 1
    checkpoint.open(older).close()
    assert older.with_name("older.db.v1.old").is_file()
    assert sqlite3.connect(older).execute("PRAGMA user_version").fetchone()[0] == 2


def test_the_set_aside_never_overwrites(tmp_path):
    path = tmp_path / "tracker.db"
    for _ in range(3):
        path.write_text("x", encoding="utf-8")
        checkpoint.set_aside(path, 7)
    assert sorted(p.name for p in tmp_path.iterdir()) == [
        "tracker.db.v7.old", "tracker.db.v7.old.1", "tracker.db.v7.old.2"]


def test_the_read_only_open_creates_nothing(tmp_path):
    path = tmp_path / checkpoint.CHECKPOINT_FILENAME
    assert checkpoint.open_read_only(path) is None
    assert not path.exists()


def test_the_command_line_states_acknowledges_and_moves_the_root(tmp_path):
    store_file = tmp_path / "app" / store.STORE_FILENAME
    assert cli(store_file, "state").returncode == 1                  # nothing there: nothing made
    assert not checkpoint.path_for(store_file).exists()
    with checkpoint.opened(checkpoint.path_for(store_file)) as held:
        checkpoint.claim_root(held, str(tmp_path / "Clients"))
        checkpoint.advance(held, KEY, 2, "c2", seeded=True)
        checkpoint.note_foreign(held, KEY, [(2, "laptop-2", "2026-09-26T10:00:00Z")])

    stated = cli(store_file, "state")
    assert stated.returncode == 0 and KEY in stated.stdout and "laptop-2" in stated.stdout
    assert cli(store_file.parent, "acknowledge", KEY).returncode == 0
    moved = tmp_path / "Moved"
    moved.mkdir()
    assert cli(store_file, "move-root", moved).returncode == 0
    with checkpoint.opened(checkpoint.path_for(store_file)) as held:
        assert checkpoint.unacknowledged(held) == []
        assert checkpoint.root_of(held) == str(moved.resolve())
