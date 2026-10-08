"""Tests for tracker/page_rows.py - the practice page's kept rows (P227).

The rule under test is P120's: **a cache may never make a status wrong.**
A kept row is used only while the record's own token is the one it was read
under, so the page drawn from kept rows is byte for byte the page drawn
from fresh reads; anything that moves a record - a file filed, a row
edited, a record rebuilt from its journal, a write landing while the row
was read - reads that return again; and a file from another day, program
or root, or a damaged one, is set aside. Made-up households only.
"""

import datetime as dt
import json
import logging
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests.test_runner import (  # noqa: F401 - ``samples`` is a fixture
    _a_parked_file,
    _run_now,
    _the_scheduled_job,
    _three_households,
    build_engagement,
    edit_rows,
    samples,
)
from tracker import ledger, page_rows, store
from tracker.layout import household_of
from tracker.manifest import Override, load_manifest
from tracker.registry import discover_engagements
from tracker.runner import REMINDERS_NEVER, STATUS_PAGE_FILENAME, status_report, write_status_page
from tracker.settings import one_reading

#: The page's stamp, held still so two drawings can be compared byte for byte.
NOW = dt.datetime(2026, 10, 8, 12, 0, 0)


@pytest.fixture
def firm(tmp_path, samples, monkeypatch):  # noqa: F811
    """The suite's three made-up households after one scheduled pass, with a
    file parked for a person in the first, and no kept rows yet."""
    root = tmp_path / "Clients"
    engagements = _three_households(root, samples)
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    _a_parked_file(engagements[0].path)
    page_rows.rows_path().unlink(missing_ok=True)
    return root, [one.path for one in engagements]


def _draw(root, kept) -> str:
    """The practice page as a pass draws it, from ``kept`` (or fresh reads
    with ``None``), with the stamp held still: the page's bytes."""
    with one_reading():
        registry = discover_engagements(root)
    write_status_page(registry.source, status_report(registry, kept=kept), now=NOW, kept=kept)
    return (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")


def _kept(root):
    with one_reading():
        return page_rows.open_kept(root)


@pytest.fixture
def reads(monkeypatch):
    """Every record the page reads, by folder: the list and the index, each
    read without following the journal - the page's reads alone."""
    seen = {"list": [], "index": []}
    real_list, real_index = runner_module.load_manifest, runner_module.read_index

    def listed(folder, *args, **kwargs):
        if kwargs.get("follow") is False:
            seen["list"].append(folder)
        return real_list(folder, *args, **kwargs)

    def indexed(folder, *args, **kwargs):
        if kwargs.get("follow") is False:
            seen["index"].append(folder)
        return real_index(folder, *args, **kwargs)

    monkeypatch.setattr(runner_module, "load_manifest", listed)
    monkeypatch.setattr(runner_module, "read_index", indexed)
    return seen


def test_the_practice_page_from_kept_rows_is_the_page_from_fresh_reads(firm, reads):
    """The prototype's check (``equiv_page.py``, 2,000 returns), on the
    suite's firm: drawn from fresh reads, from a filling file and from every
    row kept, the page is three equal byte strings - and the last read no
    record at all."""
    root, folders = firm
    fresh = _draw(root, None)
    filling = _draw(root, _kept(root))
    assert page_rows.rows_path().is_file()
    reads["list"].clear()
    reads["index"].clear()
    kept = _draw(root, _kept(root))
    assert fresh == filling == kept
    assert "unclear scan.pdf" in fresh                  # a parked row is on it
    assert reads == {"list": [], "index": []}


def test_a_return_written_since_its_row_was_kept_is_read_again(firm, reads):
    """A file parked and a row marked Not Applicable in one return after
    the rows were kept: that return is read again and shows the new
    outstanding count and parked row; every other row comes from the file."""
    root, folders = firm
    _draw(root, _kept(root))
    before = _draw(root, None)
    changed = folders[1]
    identifier = load_manifest(changed)[0].identifier
    edit_rows(changed, **{identifier: {"manual_override": Override.NOT_APPLICABLE}})
    parked = "a second scan.pdf"
    from tests.conftest import seed_index
    from tracker.filer import NEEDS_REVIEW, IndexEntry
    seed_index(changed, [IndexEntry(
        received="2026-02-03", original_name=parked, size_kb=5.0, digest="ef" * 32, identifier="",
        prepared_location="", pbc_location=parked, decision=NEEDS_REVIEW, reason="no request matched")])
    reads["list"].clear()
    reads["index"].clear()
    page = _draw(root, _kept(root))
    assert reads == {"list": [changed], "index": [changed]}
    assert page == _draw(root, None)                     # what a fresh read draws
    assert page != before and parked in page


def test_a_record_rebuilt_from_its_journal_is_read_again(firm, reads, monkeypatch):
    """The store row deleted and followed again from the same journal: the
    same head and seq, but a new ``built_at`` - so a miss, never a hit on a
    row the token cannot vouch for."""
    root, folders = firm
    _draw(root, _kept(root))
    rebuilt = folders[2]
    before = store.read_tokens(store.connect())[store.record_key(rebuilt)]
    store.forget(store.connect(), rebuilt)
    # Rebuilt in a later second than it was built (``built_at`` is to the
    # second): within the same one the token, and the rows, are the same.
    monkeypatch.setattr(ledger, "stamp", lambda: "2099-01-01T00:00:00Z")
    load_manifest(rebuilt)                               # follows the journal: the row rebuilt
    after = store.read_tokens(store.connect())[store.record_key(rebuilt)]
    assert after != before
    reads["list"].clear()
    reads["index"].clear()
    page = _draw(root, _kept(root))
    assert reads == {"list": [rebuilt], "index": [rebuilt]}
    assert page == _draw(root, None)


def test_a_row_written_while_it_was_read_is_not_kept(firm, monkeypatch):
    """The token moves between the two token reads: the page shows the
    read, and the file keeps nothing for that return."""
    root, folders = firm
    moving = folders[0]
    real = store.read_tokens

    def moved(conn, path=None):
        found = real(conn, path)
        if path is not None and path == store.record_key(moving):
            return {key: (*token[:-1], "rebuilt meanwhile") for key, token in found.items()}
        return found

    monkeypatch.setattr(store, "read_tokens", moved)
    page = _draw(root, _kept(root))
    monkeypatch.setattr(store, "read_tokens", real)
    assert page == _draw(root, None)
    entries = page_rows.load(page_rows.rows_path(), _kept(root).head)
    assert str(moving) not in entries
    assert {str(folders[1]), str(folders[2])} <= set(entries)


def test_kept_rows_from_another_day_program_or_root_are_set_aside(firm, monkeypatch):
    """The head is the firm cache's - program, root, data folder, day,
    settings - and the file's own format: any of them changed, nothing kept
    is used."""
    root, _folders = firm
    _draw(root, _kept(root))
    kept = _kept(root)
    assert kept.entries
    path, head = kept.path, kept.head
    for key, other in (("day", "2020-01-01"), ("program", "another program"), ("root", "/elsewhere"),
                       ("data_home", "/another/data"), ("rows_format", page_rows.FORMAT + 1)):
        assert page_rows.load(path, {**head, key: other}) == {}, key
    assert page_rows.open_kept(root, dt.date(2020, 1, 1)).entries == {}
    assert page_rows.load(path, head) == kept.entries


def test_a_damaged_kept_rows_file_is_set_aside_and_said_by_its_class(firm, caplog):
    """Half a file, a file whose entries were changed into other valid
    JSON, and a file whose entries have the wrong shape: each read as
    nothing, said on the error log by its reason - never a client's
    words, which the file holds."""
    root, _folders = firm
    _draw(root, _kept(root))
    path = page_rows.rows_path()
    head = _kept(root).head
    whole = path.read_text(encoding="utf-8")
    first, rest = whole.split("\n", 1)
    entries = json.loads(rest)
    some = next(iter(entries))
    tampered = dict(entries)
    tampered[some] = {**tampered[some], "outstanding": 99}
    misshapen = json.dumps({some: {"token": "not a list"}}, separators=(",", ":"))
    misshapen_head = json.dumps({"head": head, "digest": page_rows._digest(misshapen)}, separators=(",", ":"))
    for text in (whole[: len(whole) // 2],
                 f"{first}\n{json.dumps(tampered, separators=(',', ':'))}",
                 f"{misshapen_head}\n{misshapen}",
                 "not json at all\n{}"):
        path.write_text(text, encoding="utf-8")
        caplog.clear()
        with caplog.at_level(logging.WARNING, logger="tracker.page_rows"):
            assert page_rows.load(path, head) == {}
        said = " ".join(record.getMessage() for record in caplog.records)
        assert "kept rows" in said
        assert "Household" not in said and "scan" not in said
    path.write_bytes(b"\xff\xfe\x00")
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="tracker.page_rows"):
        assert page_rows.load(path, head) == {}
    assert "UnicodeDecodeError" in caplog.text
    path.unlink()
    assert page_rows.load(path, head) == {}               # missing: the ordinary first page


def test_a_parked_row_with_a_field_that_is_not_text_forgets_its_return_and_never_damages_the_file(
        firm, caplog):
    """A return whose parked rows hold one field that is not text (an index
    line with a field left ``null``) is forgotten, read afresh every page -
    never kept, where it would make the whole file read as damaged and
    every other return's rows be read again."""
    root, folders = firm
    _draw(root, _kept(root))
    kept = _kept(root)
    tokens = page_rows.load(page_rows.rows_path(), kept.head)
    token = tuple(tokens[str(folders[0])]["token"])
    assert kept.parked(folders[0], token) is not None
    kept.keep_parked(folders[0], token, [["2026-02-03", "a scan.pdf", "no request matched", None]])
    assert kept.parked(folders[0], token) is None
    kept.save()
    caplog.clear()
    with caplog.at_level(logging.WARNING, logger="tracker.page_rows"):
        entries = page_rows.load(page_rows.rows_path(), kept.head)
    assert caplog.records == []
    assert str(folders[0]) not in entries
    assert {str(folders[1]), str(folders[2])} <= set(entries)


def test_a_store_that_cannot_give_the_tokens_is_said_once_and_every_row_is_read(firm, monkeypatch, caplog, reads):
    """The first ``read_tokens`` that fails is said once by its class; the
    rest of the report asks nothing more of the store's tokens, reads every
    return's records and keeps nothing."""
    root, folders = firm
    asked = []

    def unanswered(*args, **kwargs):
        asked.append(args)
        raise OSError("the store is busy")

    monkeypatch.setattr(store, "read_tokens", unanswered)
    with caplog.at_level(logging.WARNING, logger="tracker.runner"):
        _draw(root, _kept(root))
    said = [record for record in caplog.records if "reads every row" in record.getMessage()]
    assert [record.getMessage() for record in said] == ["The practice page reads every row (OSError)"]
    assert len(asked) == 1
    assert sorted(reads["index"]) == sorted(folders)
    assert not page_rows.rows_path().exists()


def test_a_return_whose_record_cannot_be_read_is_never_kept(firm, monkeypatch, reads):
    """A read that raised costs its own row, as ever, and is not kept: the
    next page reads it again and says it again."""
    root, folders = firm
    broken = folders[1]
    real = runner_module.load_manifest

    def refused(folder, *args, **kwargs):
        if folder == broken:
            raise OSError("refused")
        return real(folder, *args, **kwargs)

    monkeypatch.setattr(runner_module, "load_manifest", refused)
    first = _draw(root, _kept(root))
    entries = page_rows.load(page_rows.rows_path(), _kept(root).head)
    assert "statuses" not in entries.get(str(broken), {})
    second = _draw(root, _kept(root))
    assert first == second
    assert "OSError" in second


def test_a_sort_reads_only_its_own_households_records_for_the_page(firm, monkeypatch, capsys, reads):
    """After one Sort has kept the other returns' rows, a Sort's page reads
    only the records of the household it ran - the 2,000-return page's
    whole saving. (The scheduled pass runs every return, so it keeps their
    parked rows; the first Sort after it reads the others' counts once.)"""
    from tracker.runner import main, run_now_arguments

    root, folders = firm
    own = folders[0]
    code, _said = _run_now(root, household_of(own), monkeypatch, capsys)
    assert code == 0
    reads["list"].clear()
    reads["index"].clear()
    # The settings file as it stands: a Sort writes no setting, so the
    # head the first Sort kept its rows under still holds.
    assert main(run_now_arguments(root.parent / "settings", household_of(own))) == 0
    assert set(reads["list"]) <= {own} and set(reads["index"]) <= {own}
    assert reads["list"] == []                           # its own counts are the pass's


def test_a_dry_run_and_a_page_with_no_data_home_keep_nothing(firm, monkeypatch):
    """A dry run writes nothing, the kept rows included; and with no data
    folder the page reads every row, as before P227."""
    from tracker import settings as settings_module

    root, _folders = firm
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--dry-run") == 0
    assert not page_rows.rows_path().exists()

    def nowhere():
        raise settings_module.SettingsError("no data folder")

    monkeypatch.setattr(settings_module, "data_home", nowhere)
    assert page_rows.open_kept(root) is None


def test_the_kept_rows_are_kept_only_for_the_saved_root(firm, monkeypatch, tmp_path, samples):  # noqa: F811
    """A pass over the saved root keeps the page's rows; their file sits in
    the data folder, never in a client tree (decision 186). A pass over a
    root typed on the command line while another root is saved - one that
    reaches its page because the record checkpoint could not be read -
    draws its page from fresh reads and neither opens nor keeps any row."""
    from tracker import checkpoint

    root, _folders = firm
    opened = []
    real_open = page_rows.open_kept

    def open_kept(source):
        opened.append(Path(source))
        return real_open(source)

    def unreadable(*args, **kwargs):
        raise checkpoint.CheckpointError("the checkpoint could not be opened")

    monkeypatch.setattr(page_rows, "open_kept", open_kept)
    other = tmp_path / "Elsewhere" / "Clients"
    build_engagement(other, samples, household="Dogwood Household", name="Dogwood TY2025")
    with monkeypatch.context() as patch:
        patch.setattr(runner_module.store, "prove_the_root", unreadable)
        runner_module.main([runner_module.SETTINGS_FLAG, str(root.parent / "settings"), str(other),
                            "--reminders", REMINDERS_NEVER])
    assert (other / STATUS_PAGE_FILENAME).is_file()
    assert opened == []
    assert not page_rows.rows_path().exists()

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    assert opened == [root.resolve()]
    path = page_rows.rows_path()
    assert path.is_file()
    assert root not in path.parents
    assert page_rows.load(path, _kept(root).head)
