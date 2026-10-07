"""The firm view's cache file (P120, ``pilot/SPEC-firm-cache.md``): where it
lives, what its fingerprint notices, and that a damaged, foreign or stale
file is never used. Whether a cached reply equals the whole walk's is
``tests/test_api.py``'s claim; this file holds the parts that decide it."""

from __future__ import annotations

import datetime as dt
import json
import logging
import os
import time
from pathlib import Path

import pytest

from tracker import firm_cache, settings

TODAY = dt.date(2026, 3, 2)


def _aged(*folders: Path, seconds: int = 120) -> None:
    """Every entry under ``folders`` dated ``seconds`` ago: past the racy
    window, as a household nobody has touched for a while is."""
    past = time.time() - seconds
    for folder in folders:
        for path in [folder, *folder.rglob("*")]:
            os.utime(path, (past, past))


def _household(tmp_path: Path) -> tuple[Path, Path]:
    private = tmp_path / "private" / "Lee Family"
    client = tmp_path / "clients" / "Lee Family"
    (private / "2025" / "1040 - Ann Lee").mkdir(parents=True)
    (private / "2025" / "1040 - Ann Lee" / "record.jsonl").write_text("one\n", encoding="utf-8")
    (client / "Drop files here").mkdir(parents=True)
    _aged(private, client)
    return private, client


def test_the_cache_lives_in_the_data_folder_and_is_named_once():
    assert firm_cache.cache_path() == settings.data_home() / firm_cache.CACHE_FILENAME
    assert firm_cache.cache_path().parent == settings.data_home()


def test_an_unchanged_household_keeps_its_fingerprint(tmp_path):
    private, client = _household(tmp_path)
    first = firm_cache.fingerprint(private, client)
    assert first is not None and first == firm_cache.fingerprint(private, client)


@pytest.mark.parametrize("change", ["a file dropped in the inbox", "a record grown", "a record rewritten",
                                    "a file removed", "a folder added", "a file renamed"])
def test_every_kind_of_change_under_either_folder_changes_the_fingerprint(tmp_path, change):
    private, client = _household(tmp_path)
    before = firm_cache.fingerprint(private, client)
    record = private / "2025" / "1040 - Ann Lee" / "record.jsonl"
    if change == "a file dropped in the inbox":
        (client / "Drop files here" / "w2.pdf").write_bytes(b"x")
    elif change == "a record grown":
        record.write_text("one\ntwo\n", encoding="utf-8")
    elif change == "a record rewritten":
        # The same size, an older time: a sync client restoring a copy.
        record.write_text("uno\n", encoding="utf-8")
        past = time.time() - 3600
        os.utime(record, (past, past))
    elif change == "a file removed":
        record.unlink()
    elif change == "a folder added":
        (private / "2024").mkdir()
    else:
        record.rename(record.with_name("other.jsonl"))
    _aged(private, client, seconds=60)       # past the racy window, at another time
    if change == "a record rewritten":
        past = time.time() - 3600
        os.utime(record, (past, past))
    assert firm_cache.fingerprint(private, client) != before, change


def test_a_household_touched_within_the_racy_window_is_never_fingerprinted(tmp_path):
    """A file rewritten twice in one tick of the clock at one size would keep
    its fingerprint; so anything this new is read fresh until it settles."""
    private, client = _household(tmp_path)
    (private / "2025" / "1040 - Ann Lee" / "record.jsonl").write_text("two\n", encoding="utf-8")
    assert firm_cache.fingerprint(private, client) is None
    _aged(private, client)
    ahead = time.time() + 3600               # a file dated by a clock ahead of this one
    os.utime(private / "2025" / "1040 - Ann Lee" / "record.jsonl", (ahead, ahead))
    assert firm_cache.fingerprint(private, client) is None


def test_a_missing_client_folder_is_said_not_skipped(tmp_path):
    private, client = _household(tmp_path)
    with_it = firm_cache.fingerprint(private, client)
    for path in sorted(client.rglob("*"), reverse=True):
        path.rmdir()
    client.rmdir()
    without = firm_cache.fingerprint(private, client)
    assert without is not None and without != with_it


def test_a_household_holding_a_link_is_never_fingerprinted(tmp_path):
    private, client = _household(tmp_path)
    try:
        (private / "linked").symlink_to(tmp_path, target_is_directory=True)
    except OSError:
        pytest.skip("this machine cannot make a symbolic link")
    _aged(private, client)
    assert firm_cache.fingerprint(private, client) is None


def test_the_head_names_the_format_the_program_the_root_the_data_folder_the_day_and_the_settings(tmp_path):
    head = firm_cache.head(tmp_path, TODAY)
    assert set(head) == {"format", "program", "root", "data_home", "day", "settings"}
    assert head["format"] == firm_cache.FORMAT and head["day"] == "2026-03-02"
    assert head["root"] == str(tmp_path) and head["data_home"] == str(settings.data_home())
    assert firm_cache.head(tmp_path, TODAY + dt.timedelta(days=1)) != head
    settings.set_firm("Another Name LLP")                    # the settings file changed
    assert firm_cache.head(tmp_path, TODAY)["settings"] != head["settings"]


def test_the_program_stamp_follows_the_packaged_executable(tmp_path, monkeypatch):
    program = tmp_path / "tracker-api.exe"
    program.write_bytes(b"one")
    monkeypatch.setattr("sys.frozen", True, raising=False)
    monkeypatch.setattr("sys.executable", str(program))
    first = firm_cache.program_stamp()
    program.write_bytes(b"one and two")
    assert firm_cache.program_stamp() != first


def _entry(fingerprint="f" * 32):
    return {"fingerprint": fingerprint, "kind": "household", "name": "Lee Family", "feeds": [], "related": [],
            "returns": [{"path": "p", "household": "h", "problem": "", "active": True, "tax_year": 2025,
                         "rolled_from": "", "shown": {"row": {"a": 1}, "files": [], "paths": {}}}]}


def test_what_is_saved_is_what_is_loaded_under_the_same_head(tmp_path):
    where = tmp_path / "firm-view.json"
    head = firm_cache.head(tmp_path, TODAY)
    firm_cache.save(where, head, {"Lee Family": _entry()})
    assert firm_cache.load(where, head) == {"Lee Family": _entry()}


def test_another_head_is_not_used(tmp_path):
    where = tmp_path / "firm-view.json"
    head = firm_cache.head(tmp_path, TODAY)
    firm_cache.save(where, head, {"Lee Family": _entry()})
    assert firm_cache.load(where, {**head, "day": "2026-03-03"}) == {}
    assert firm_cache.load(where, {**head, "program": "another"}) == {}
    assert firm_cache.load(where, {**head, "format": firm_cache.FORMAT + 1}) == {}


def test_holds_only_a_whole_file_under_one_of_the_heads(tmp_path, caplog):
    """P201 R5: how the pass knows the summary it asked for left the cache
    filled - whole JSON, its digest true, under one of the heads given -
    and nothing is logged, since the reply already said any surprise."""
    where = tmp_path / "firm-view.json"
    head = firm_cache.head(tmp_path, TODAY)
    tomorrow = {**head, "day": "2026-03-03"}
    with caplog.at_level(logging.WARNING, logger="tracker.firm_cache"):
        assert not firm_cache.holds(where, [head])                      # missing
        firm_cache.save(where, head, {"Lee Family": _entry()})
        assert firm_cache.holds(where, [head]) and firm_cache.holds(where, [tomorrow, head])
        assert not firm_cache.holds(where, [tomorrow])
        firm_cache.save(where, head, {})
        assert firm_cache.holds(where, [head]), "a practice with nothing kept yet is still filled"
        kept = json.loads(where.read_text(encoding="utf-8"))
        kept["households"]["Lee Family"] = _entry()
        where.write_text(json.dumps(kept), encoding="utf-8")
        assert not firm_cache.holds(where, [head]), "a digest that does not match is not whole"
        where.write_text("{not json", encoding="utf-8")
        assert not firm_cache.holds(where, [head])
    assert not caplog.records


def test_a_missing_file_is_the_ordinary_first_reply_and_is_not_logged(tmp_path, caplog):
    with caplog.at_level(logging.WARNING, logger="tracker.firm_cache"):
        assert firm_cache.load(tmp_path / "firm-view.json", firm_cache.head(tmp_path, TODAY)) == {}
    assert not caplog.records


@pytest.mark.parametrize("damage", ["not json", "a row changed", "a key missing", "a wrong type"])
def test_a_damaged_file_is_never_used_and_is_said_by_its_reason(tmp_path, caplog, damage):
    where = tmp_path / "firm-view.json"
    head = firm_cache.head(tmp_path, TODAY)
    firm_cache.save(where, head, {"Lee Family": _entry()})
    if damage == "not json":
        where.write_text(where.read_text(encoding="utf-8")[:-7], encoding="utf-8")
    else:
        kept = json.loads(where.read_text(encoding="utf-8"))
        one = kept["households"]["Lee Family"]
        if damage == "a row changed":            # valid JSON, the digest no longer agrees
            one["returns"][0]["shown"]["row"]["a"] = 2
        elif damage == "a key missing":
            del one["returns"][0]["active"]
            kept["digest"] = firm_cache._households_digest(kept["households"])
        else:
            one["returns"][0]["tax_year"] = "2025"
            kept["digest"] = firm_cache._households_digest(kept["households"])
        where.write_text(json.dumps(kept), encoding="utf-8")
    with caplog.at_level(logging.WARNING, logger="tracker.firm_cache"):
        assert firm_cache.load(where, head) == {}
    said = " ".join(record.getMessage() for record in caplog.records)
    assert "rebuilding it" in said and "Lee Family" not in said


def test_a_cache_that_cannot_be_written_is_logged_and_the_reply_goes_on(tmp_path, caplog, monkeypatch):
    def refused(path, text):
        raise PermissionError(13, "held by another reader")

    monkeypatch.setattr(firm_cache, "write_text_atomically", refused)
    with caplog.at_level(logging.WARNING, logger="tracker.firm_cache"):
        firm_cache.save(tmp_path / "firm-view.json", firm_cache.head(tmp_path, TODAY), {"Lee Family": _entry()})
    said = " ".join(record.getMessage() for record in caplog.records)
    assert "could not be written" in said and "held by another reader" not in said


def test_fingerprints_taken_eight_at_a_time_are_the_ones_taken_one_at_a_time(tmp_path):
    pairs = []
    for n in range(20):
        private = tmp_path / "private" / f"Household {n}"
        client = tmp_path / "clients" / f"Household {n}"
        (private / "2025").mkdir(parents=True)
        (private / "2025" / "record.jsonl").write_text("x" * n, encoding="utf-8")
        client.mkdir(parents=True)
        pairs.append((private, client))
    _aged(tmp_path)
    assert firm_cache.fingerprints(pairs) == [firm_cache.fingerprint(*pair) for pair in pairs]
    assert len(set(firm_cache.fingerprints(pairs, threads=3))) == 20
    assert firm_cache.fingerprints([]) == []


def test_an_error_in_any_thread_is_raised_to_the_caller(tmp_path, monkeypatch):
    def broken(*folders):
        raise RuntimeError("a surprise")

    monkeypatch.setattr(firm_cache, "fingerprint", broken)
    with pytest.raises(RuntimeError):
        firm_cache.fingerprints([(tmp_path, tmp_path)] * 5)


# ------------------------------------------ the review's folds (P120) ----

ANY = firm_cache.ANY
JUDGED = firm_cache.Judged(private_left_out=frozenset({(ANY, ANY, "Status Report.html")}))


def test_a_record_is_judged_by_its_size_and_time_and_a_rewrite_that_puts_both_back_is_not_seen(tmp_path):
    """P212, Jason's trade of 2026-10-07, reversing P120's SHOULD-2: a
    record is judged by its size and last-saved time, so a rewrite that puts
    both back (a backup restore, a copy that keeps times) is not seen until
    the next day's head or anything else in the household moves - while a
    rewrite that moves either is seen at once."""
    private, client = _household(tmp_path)
    record = private / "2025" / "1040 - Ann Lee" / "record.jsonl"
    before = firm_cache.fingerprint(private, client, JUDGED)
    kept = record.stat()
    record.write_text("uno\n", encoding="utf-8")                  # the same four bytes long
    os.utime(record, ns=(kept.st_atime_ns, kept.st_mtime_ns))
    assert record.stat().st_size == kept.st_size
    assert firm_cache.fingerprint(private, client, JUDGED) == before, "size and time put back: not seen"
    os.utime(record, ns=(kept.st_atime_ns, kept.st_mtime_ns - 10 * 1_000_000_000))
    assert firm_cache.fingerprint(private, client, JUDGED) != before, "a time that moved is seen"
    record.write_text("one more\n", encoding="utf-8")
    os.utime(record, ns=(kept.st_atime_ns, kept.st_mtime_ns))
    assert firm_cache.fingerprint(private, client, JUDGED) != before, "a size that moved is seen"


def test_the_fingerprint_opens_no_file(tmp_path, monkeypatch):
    """P212: at 1,000 households the whole bytes of every record were read
    on every Overview; now nothing is opened, only listed."""
    import builtins
    import io

    private, client = _household(tmp_path)

    def refuse(*args, **kwargs):
        raise AssertionError(f"a file was opened: {args[0]}")

    monkeypatch.setattr(builtins, "open", refuse)
    monkeypatch.setattr(io, "open", refuse)
    assert firm_cache.fingerprint(private, client, JUDGED) is not None


def test_the_status_page_and_folder_times_leave_the_fingerprint_alone(tmp_path):
    """SHOULD-4: every pass rewrites each return's status page and moves the
    folders' times with its lock and temporary files; neither is anything
    the firm view reads, so neither makes a household read again."""
    private, client = _household(tmp_path)
    page = private / "2025" / "1040 - Ann Lee" / "Status Report.html"
    page.write_text("<p>one</p>", encoding="utf-8")
    _aged(private, client)
    before = firm_cache.fingerprint(private, client, JUDGED)
    page.write_text("<p>written again by a pass</p>", encoding="utf-8")
    passing = private / "2025" / "1040 - Ann Lee" / ".lock"
    passing.write_text("x", encoding="utf-8")
    passing.unlink()
    for folder in (private, private / "2025", private / "2025" / "1040 - Ann Lee"):
        os.utime(folder, (time.time() - 30, time.time() - 30))
    assert firm_cache.fingerprint(private, client, JUDGED) == before


def test_a_household_with_no_client_folder_to_ask_is_taken_by_its_own_folder(tmp_path):
    """SHOULD-1: a folder whose name no household may have has no client
    folder; it is fingerprinted by its own and kept, not refused."""
    private, client = _household(tmp_path)
    alone = firm_cache.fingerprint(private, None, JUDGED)
    assert alone is not None and alone != firm_cache.fingerprint(private, client, JUDGED)


def test_a_household_holding_a_junction_is_never_fingerprinted(tmp_path):
    """NIT-5: the Windows link a person can make without Developer Mode."""
    winapi = pytest.importorskip("_winapi")
    private, client = _household(tmp_path)
    target = tmp_path / "elsewhere"
    target.mkdir()
    winapi.CreateJunction(str(target), str(private / "joined"))
    _aged(private, client)
    assert firm_cache.fingerprint(private, client, JUDGED) is None


def test_a_surprise_is_said_once_until_it_changes(tmp_path):
    """SHOULD-1: the cached path set aside for one surprise says it once."""
    note = tmp_path / firm_cache.SAID_FILENAME
    assert firm_cache.first_time_said(note, "LayoutError") is True
    assert firm_cache.first_time_said(note, "LayoutError") is False
    assert firm_cache.first_time_said(note, "OSError (EACCES)") is True
    assert firm_cache.first_time_said(note, None) is True and not note.exists()
    assert firm_cache.first_time_said(note, None) is False


def test_a_client_file_or_folder_named_like_the_status_page_is_never_left_out(tmp_path):
    """The re-check's MUST-R1: only the page the tracker writes, directly in
    a return folder of the private tree, is left out - never a client's file
    or folder of that name in the inbox, nor the name at another depth."""
    private, client = _household(tmp_path)
    before = firm_cache.fingerprint(private, client, JUDGED)
    (client / "Drop files here" / "Status Report.html").write_text("forwarded back", encoding="utf-8")
    _aged(private, client)
    dropped = firm_cache.fingerprint(private, client, JUDGED)
    assert dropped != before
    held = client / "Drop files here" / "Status Report.html"
    held.unlink()
    held.mkdir()
    (held / "w2.pdf").write_bytes(b"made up")
    _aged(private, client)
    assert firm_cache.fingerprint(private, client, JUDGED) not in (before, dropped)
    (private / "2025" / "Status Report.html").write_text("not where the tracker writes it", encoding="utf-8")
    _aged(private, client)
    elsewhere = firm_cache.fingerprint(private, client, JUDGED)
    (private / "2025" / "Status Report.html").write_text("changed", encoding="utf-8")
    _aged(private, client, seconds=90)
    assert firm_cache.fingerprint(private, client, JUDGED) != elsewhere


def test_a_client_file_carrying_a_tracker_name_is_never_read(tmp_path, monkeypatch):
    """The re-check's NIT-R1, kept under P212: a client's file named like
    the firm's README, in an inbox subfolder, is judged by its size and time
    and never opened - and since P212 neither is the README itself."""
    private, client = _household(tmp_path)
    (client / "Drop files here" / "_README.txt").write_text("the firm's", encoding="utf-8")
    (client / "Drop files here" / "from the bank").mkdir()
    (client / "Drop files here" / "from the bank" / "_README.txt").write_text("a client's", encoding="utf-8")
    _aged(private, client)
    opened = []
    real = Path.read_bytes

    def watched(self):
        opened.append(self)
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", watched)
    assert firm_cache.fingerprint(private, client, JUDGED) is not None
    assert opened == []


def test_an_entry_whose_feeds_or_related_is_not_a_list_of_words_is_damage(tmp_path):
    """FORMAT 2 (the 0.3 landing): a kept household carries its own feeds and
    related names; anything else there is damage, and the file is rebuilt."""
    where = tmp_path / "firm-view.json"
    head = firm_cache.head(tmp_path, TODAY)
    for key, bad in (("feeds", "Lee Family"), ("related", [1]), ("related", None)):
        firm_cache.save(where, head, {"Lee Family": {**_entry(), key: bad}})
        assert firm_cache.load(where, head) == {}
    firm_cache.save(where, head, {"Lee Family": _entry()})
    assert firm_cache.load(where, head) == {"Lee Family": _entry()}
