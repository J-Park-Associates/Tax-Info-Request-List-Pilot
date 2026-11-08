"""Tests for tracker/api.py: the firm view, its cache and the engine's paging of its lists.

The firm view (SPEC-shell 9), its cache (P120), a wait that says what it shows (P222), the Overview's last counts at
launch (P229) and the engine paging the firm lists (P278).

Split from ``tests/test_api.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/api.py``'s test by its name (decision P350). What more than one family reads is
``tests/api_driver.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import json
import os
import re
from pathlib import Path

import pytest

import tracker.api as api
import tracker.screen_words as screen_words
from tests import api_driver
from tests.api_driver import (
    HOUSEHOLD,
    _a_practice_for_the_firm_view,
    _aged,
    _cached_firm,
    _firm_whole,
    _parked_read_pdf_state,
    _parked_row,
    _rows_read,
    _walk_strings,
    a_moved_row,
    chased_engagement,
    payload_of_state,
    run,
    sample_engagement,
    scan,
    where,
)
from tests.wording import title_case
from tracker import firm_view, household_edit, ledger, reasons, request_edit, store
from tracker.index import NEEDS_REVIEW
from tracker.layout import PRIVATE_TREE, inbox_of
from tracker.manifest import Status
from tracker.scaffold import REVIEW_DIR_NAME
from tracker.templates import default_tax_year

#: A fixture of ``tests/api_driver.py``, named here so every claim below can ask for it.
demo_root = api_driver.demo_root


# ---------------------------------------------------------------- firm (SPEC-shell 9) ----


def _tally(state: dict) -> dict:
    """What the return's page draws under each group: the request rows and the
    files that are not filed (a filed file is the Received row it answered)."""
    return {group: sum(1 for item in state["items"] if item["group"] == group)
            + sum(1 for file in state["index"] if file["group"] == group and group != firm_view.GROUP_RECEIVED)
            for group in firm_view.GROUPS}


def test_firm_counts_match_the_return_pages_groups(capsys, demo_root):
    mixed, quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    code, firm = run(capsys, "firm")
    assert code == 0, firm
    counted = {one["path"]: one["counts"] for one in firm["returns"]}
    for folder in (mixed, quiet):
        assert counted[str(folder)] == _tally(payload_of_state(capsys, folder))
    assert counted[str(quiet)][firm_view.GROUP_RECEIVED] == 2
    # A parked program is a file waiting for a person, with its reason's code.
    [row] = [one for one in firm["returns"] if one["path"] == str(mixed)]
    assert row["files"] == 1 and row["oldest"] == "2026-02-01"
    assert [f["name"] for f in firm["files"]] == ["setup.exe"]
    assert firm["files"][0]["code"] == reasons.NOT_A_DOCUMENT.code
    assert firm["files"][0]["return"] == str(mixed)
    assert firm["totals"]["files"] == len(firm["files"]) == 1
    assert firm["totals"]["need"] + firm["totals"]["waiting"] + firm["totals"]["complete"] == len(
        firm["returns"])


def test_every_return_row_the_pages_link_carries_its_year_beside_its_label(capsys, demo_root):
    """Return links read "{Return Name} ({Year})" and the renderer types no
    year (Jason, 2026-09-29): the firm's rows, the files under them, the
    list's returns and the state's household returns each carry it."""
    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _code, firm = run(capsys, "firm")
    assert firm["returns"] and firm["files"]
    for one in firm["returns"]:
        assert one["label"] and isinstance(one["year"], int), one
    paths = {one["path"] for one in firm["returns"]}
    for one in firm["files"]:
        assert one["return"] in paths and isinstance(one["year"], int), one
    _code, listed = run(capsys, "list")
    for household in listed["households"]:
        assert all(isinstance(one["year"], int) and one["label"] for one in household["returns"])
    assert all(isinstance(one["year"], int) for one in listed["engagements"])
    state = payload_of_state(capsys, mixed)
    assert all(isinstance(one["year"], int) for one in state["household"]["returns"])


def test_firm_counts_parked_moved_and_set_aside_files_as_the_return_page_does(capsys, demo_root):
    """A return whose only work is files still needs a person and its counts
    are the tally of its own page (SPEC-shell 9.1: one source)."""
    from tests.builders import seed_index, seed_statuses
    from tracker.index import FILE_MOVED, NOT_REQUESTED
    from tracker.manifest import StatusUpdate
    from tracker.records import IndexEntry

    folder = chased_engagement(capsys, demo_root, name="Files only")
    seed_statuses(folder, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1),
                           "B01": StatusUpdate(status=Status.RECEIVED, file_count=1)})

    def entry(name, decision, day, identifier="", home=""):
        return IndexEntry(received=day, original_name=name, size_kb=0.1, digest=str(len(name)) * 64,
                          identifier=identifier, prepared_location=home, pbc_location=f"pbc/{name}",
                          decision=decision, reason="",
                          code=reasons.NOT_A_DOCUMENT.code if decision == NEEDS_REVIEW else "")

    seed_index(folder, [entry("setup.exe", NEEDS_REVIEW, "2026-02-01"),
                        entry("w2.pdf", FILE_MOVED, "2026-02-02", "A01", "A01/w2.pdf"),
                        entry("junk.pdf", NOT_REQUESTED, "2026-02-03")])
    _code, firm = run(capsys, "firm")
    [row] = firm["returns"]
    assert row["counts"] == {"needs_you": 2, "waiting": 0, "received": 2, "set_aside": 1}
    assert row["counts"] == _tally(payload_of_state(capsys, folder))
    assert firm["totals"] == {"need": 1, "waiting": 0, "complete": 0, "files": 2, "drafts": 0}


def test_firm_reply_names_its_fields_as_the_spec_does_and_carries_year_and_handle(capsys, demo_root):
    """files[].return is the return's path (what the pages group and open by),
    each file has the handle the Check step finds it by, and every return and
    file carries the tax year beside its label (Jason, 2026-09-29)."""
    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _code, firm = run(capsys, "firm")
    [file] = firm["files"]
    assert set(file) == {"return", "year", "name", "handle", "code", "received", "suggestion", "suggestion_short",
                         "open_key"}
    assert file["open_key"] == "", "a program has no working copy, so no key (ruling 15)"
    assert firm["paths"] == {}
    assert file["return"] == str(mixed) and file["year"] == 2025
    [parked] = [one for one in payload_of_state(capsys, mixed)["index"] if one["original_name"] == "setup.exe"]
    assert file["handle"] == parked["handle"] != ""
    assert file["return"] in {one["path"] for one in firm["returns"]}
    for one in firm["returns"]:
        assert one["year"] == 2025 and set(one) == {
            "path", "household", "label", "year", "counts", "files", "oldest", "due", "draft", "problem",
            "paused", "form", "links"}
    assert set(firm["totals"]) == {"need", "waiting", "complete", "files", "drafts"}


def _firm_of_a_scanned_pile(capsys, demo_root, tmp_path):
    engagement = sample_engagement(capsys, demo_root, tmp_path)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    _code, firm = run(capsys, "firm")
    return engagement, payload["state"], firm


def test_a_parked_files_open_key_is_the_states_shown_key_and_names_its_copy(capsys, demo_root, tmp_path):
    """Ruling 15: each firm file carries the key ``state`` gives the same row
    (one file, one key, one kind), and ``firm.paths`` names its working copy."""
    engagement, state, firm = _firm_of_a_scanned_pile(capsys, demo_root, tmp_path)
    assert firm["files"]
    keyed = 0
    for one in firm["files"]:
        [row] = [e for e in state["index"] if e["handle"] == one["handle"]]
        assert one["open_key"] == row["shown_key"], one["name"]
        if one["open_key"]:
            keyed += 1
            assert Path(firm["paths"][one["open_key"]]) == engagement / row["prepared_location"]
            assert Path(firm["paths"][one["open_key"]]).is_file()
            assert not [s for s in _walk_strings(one["open_key"]) if str(engagement) in s]
    assert keyed and set(firm["paths"]) == {one["open_key"] for one in firm["files"] if one["open_key"]}


def test_a_moved_files_open_key_is_where_it_is_now_and_empty_when_it_is_nowhere(capsys, demo_root, tmp_path):
    engagement, _filed, target, state = a_moved_row(
        capsys, demo_root, tmp_path, lambda eng, home: home.with_name("A01 - the 1098 I renamed.pdf"))
    _code, firm = run(capsys, "firm")
    [one] = firm["files"]
    assert one["open_key"] == state["moved"][0]["open_key"]
    assert one["open_key"].startswith("moved_copy ")
    assert Path(firm["paths"][one["open_key"]]) == target
    target.unlink()
    code, _payload = scan(capsys, engagement)
    assert code == 0
    _code, firm = run(capsys, "firm")
    [one] = firm["files"]
    assert one["open_key"] == "" and firm["paths"] == {}


def test_the_firms_paths_name_each_path_under_one_key_and_one_kind(capsys, demo_root, tmp_path):
    _engagement, _scanned_state, firm = _firm_of_a_scanned_pile(capsys, demo_root, tmp_path)
    kinds_of = {}
    for key, path in firm["paths"].items():
        assert screen_words.PATH_KINDS[key.split(" ", 1)[0]] in ("file", "reveal"), key
        kinds_of.setdefault(path, set()).add(screen_words.PATH_KINDS[key.split(" ", 1)[0]])
    assert all(len(kinds) == 1 for kinds in kinds_of.values()), kinds_of
    assert len(firm["paths"]) == len(kinds_of), "one key per path"


def test_a_real_firm_replys_paths_reveal_a_firm_file_and_refuse_an_unreported_one(
        capsys, demo_root, tmp_path):
    """Ruling 15 end to end: the firm reply's ``paths`` through the real
    ``app/main.js`` under node (which learns a reply's top-level ``paths``)."""
    from tests.node_harness import run_menu

    engagement, _scanned_state, firm = _firm_of_a_scanned_pile(capsys, demo_root, tmp_path)
    [one] = [f for f in firm["files"] if f["open_key"].startswith("shown_copy ")][:1]
    path = firm["paths"][one["open_key"]]
    stranger = str(engagement / "Prepared" / "never reported.pdf")
    steps = [{"tracker": ["list"]}, {"open": [path, "reveal"]}, {"open": [path]},
             {"open": [stranger, "reveal"]}]
    ran = run_menu(tmp_path, steps, pathKinds=screen_words.PATH_KINDS, paths=firm["paths"])
    assert ran["revealed"] == [path] and ran["opened"] == []
    assert ran["answers"][0] == "" and ran["answers"][1] != "" and ran["answers"][2] != ""


def test_two_returns_spelling_one_key_for_different_paths_get_a_deterministic_suffix(capsys, demo_root):
    from tests.builders import seed_index
    from tracker.records import IndexEntry

    homes = []
    for name in ("First", "Second"):
        folder = chased_engagement(capsys, demo_root, name=name)
        copy = folder / "Prepared" / "a note.docx"
        copy.parent.mkdir(parents=True, exist_ok=True)
        copy.write_bytes(b"x")
        seed_index(folder, [IndexEntry(
            received="2026-02-01", original_name="a note.docx", size_kb=0.1, digest="7" * 64,
            identifier="", prepared_location="Prepared/a note.docx", pbc_location="pbc/a note.docx",
            decision=NEEDS_REVIEW, reason=reasons.NOT_A_DOCUMENT.format(), code=reasons.NOT_A_DOCUMENT.code)])
        homes.append(copy)
    _code, firm = run(capsys, "firm")
    keys = sorted(f["open_key"] for f in firm["files"])
    assert len(keys) == 2 and keys[1] == keys[0] + " #2"
    assert {Path(firm["paths"][k]) for k in keys} == set(homes)
    assert api._firm_key(firm["paths"], keys[0], firm["paths"][keys[0]]) == keys[0], "same path, same key"


def test_list_state_and_firm_agree_on_a_returns_year(capsys, demo_root):
    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    listed = run(capsys, "list")[1]
    [one] = [r for r in listed["engagements"] if r["path"] == str(mixed)]
    [in_household] = [r for h in listed["households"] for r in h["returns"] if r["path"] == str(mixed)]
    [in_firm] = [r for r in run(capsys, "firm")[1]["returns"] if r["path"] == str(mixed)]
    assert one["year"] == in_household["year"] == in_firm["year"] == 2025 == (
        payload_of_state(capsys, mixed)["engagement"]["tax_year"])


def test_the_after_install_heading_is_the_specs_words():
    assert screen_words.AFTER_INSTALL_HEADING == "Setup Needs Attention"
    assert api.vocab()["after_install"]["heading"] == "Setup Needs Attention"


def test_firm_lists_every_file_it_counts_and_buckets_a_return_with_only_a_file(capsys, demo_root):
    """A file moved by hand is listed with its code and its return's path, so
    the rows under the count agree with it; a return whose only work for a
    person is a parked file (every request received) needs a person."""
    from tests.builders import seed_index, seed_statuses
    from tracker.index import FILE_MOVED
    from tracker.manifest import StatusUpdate
    from tracker.records import IndexEntry

    only_file = chased_engagement(capsys, demo_root, name="Only file")
    seed_statuses(only_file, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1),
                              "B01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    seed_index(only_file, [
        IndexEntry(received="2026-02-01", original_name="setup.exe", size_kb=0.1, digest="5" * 64,
                   identifier="", prepared_location="", pbc_location="pbc/setup.exe",
                   decision=NEEDS_REVIEW, reason=reasons.NOT_A_DOCUMENT.format(),
                   code=reasons.NOT_A_DOCUMENT.code),
        IndexEntry(received="2026-02-02", original_name="w2.pdf", size_kb=1.0, digest="6" * 64,
                   identifier="A01", prepared_location="A01/w2.pdf", pbc_location="pbc/w2.pdf",
                   decision=FILE_MOVED, reason="")])
    _code, firm = run(capsys, "firm")
    [row] = firm["returns"]
    assert row["files"] == 2 and row["oldest"] == "2026-02-01"
    assert [(f["name"], f["code"], f["return"]) for f in firm["files"]] == [
        ("setup.exe", reasons.NOT_A_DOCUMENT.code, str(only_file)),
        ("w2.pdf", reasons.FILE_MOVED.code, str(only_file))]
    _code, state = run(capsys, "state", api.ENGAGEMENT_FLAG, str(only_file))
    handles = {e["original_name"]: e["handle"] for e in state["index"]}
    handles.update({m["original_name"]: m["handle"] for m in state["moved"]})
    assert set(handles) == {"setup.exe", "w2.pdf"}
    for f in firm["files"]:
        assert f["year"] == 2025
        assert f["handle"] and f["handle"] == handles[f["name"]]
    assert firm["totals"]["files"] == 2
    assert firm["totals"]["need"] == 1 and firm["totals"]["complete"] == 0


def test_firm_says_a_reminder_draft_ready_only_until_it_is_approved_and_counts_the_inbox_as_a_hold(
        capsys, demo_root, monkeypatch):
    import datetime as dt

    from tracker import reminder

    folder = chased_engagement(capsys, demo_root, name="Drafted")
    for module in (api, firm_view):
        monkeypatch.setattr(module, "last_drafted", lambda _path: dt.date.today())
        monkeypatch.setattr(module, "last_draft_day", lambda today, _weekday: today - dt.timedelta(days=1))
    monkeypatch.setattr(reminder, "unsorted_in_inbox", lambda _path: 2)
    monkeypatch.setattr(reminder, "approval_state", lambda *_a, **_k: "")

    def draft():
        [row] = run(capsys, "firm")[1]["returns"]
        return row["draft"]

    ready = draft()
    assert ready["ready"] is True and ready["held"] >= 2, "a hold does not unmake a ready draft"
    monkeypatch.setattr(reminder, "approval_state", lambda *_a, **_k: reminder.APPROVED_NOTE)
    assert draft()["ready"] is False
    assert run(capsys, "firm")[1]["totals"]["drafts"] == 0
    assert folder.is_dir()


def test_firm_is_read_only(capsys, demo_root, monkeypatch):
    import traceback

    from tracker import firm_cache, store
    from tracker.locking import LOCK_FILENAME, engagement_lock
    from tracker.settings import data_home

    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    store_file = store.store_path()
    def snapshot():
        found = {str(path.relative_to(demo_root)): path.read_bytes() if path.is_file() else None
                 for path in sorted(demo_root.rglob("*"))}
        # The store and its side files, and the data home beside it.
        for path in sorted({*data_home().rglob("*"), store_file,
                            *store_file.parent.glob(store_file.name + "-*")}):
            # The view's one write is its own cache, in the data folder (P120).
            if path != firm_cache.cache_path():
                found[f"store:{path}"] = path.read_bytes() if path.is_file() else None
        return found

    before = snapshot()
    assert run(capsys, "firm")[0] == 0
    assert snapshot() == before
    assert not list(demo_root.rglob(LOCK_FILENAME))
    assert "firm" not in api.WRITING_COMMANDS and "firm" in api.COMMANDS

    # Final review A, M14: with a store that LAGS its journal. The walk that
    # finds the returns follows every journal, as ``list`` does (it is the one
    # place the store is caught up); the firm's own reads of a return must
    # not - a read with ``follow=True`` would be a write. So no other
    # read of a return may follow the journal, and no document moves.
    def died(*args, **kwargs):
        raise OSError("the machine went down between the two writes")

    with monkeypatch.context() as patch:
        patch.setattr(store, "_apply", died)
        with engagement_lock(mixed), pytest.raises(OSError):
            store.record(store.connect(), mixed, ledger.new(ledger.FILED, key="pbc/lagging.pdf", row={
                "received": "2026-02-02", "original_name": "lagging.pdf", "size_kb": 1.0, "digest": "6" * 64,
                "identifier": "", "prepared_location": "", "pbc_location": "pbc/lagging.pdf",
                "decision": "Needs Review", "reason": "", "candidates": "", "evidence": "", "also_filed": ""}))
    store.close()
    assert store.state(store.connect(), mixed, ledger_head_now=ledger.head(mixed)) == store.BEHIND
    store.close()
    tree = {str(path.relative_to(demo_root)): path.read_bytes() if path.is_file() else None
            for path in sorted(demo_root.rglob("*"))}
    real, from_api = store.follow_the_journal, []

    def watched(conn, root, engagement_dir):
        names = {frame.name for frame in traceback.extract_stack()}
        # The details reader (``load_engagement_info``) has no follow=False
        # form and the walk has already caught the store up; every other read
        # the firm makes of a return must not follow.
        if "_firm_row" in names and "load_engagement_info" not in names:
            from_api.append(sorted(names & {"load_manifest", "read_index", "_firm_row", "triage"}))
        return real(conn, root, engagement_dir)

    monkeypatch.setattr(store, "follow_the_journal", watched)
    assert run(capsys, "firm")[0] == 0
    assert not from_api, "the firm view reads a return with follow=False; only the walk and the details reader follow"
    assert {str(path.relative_to(demo_root)): path.read_bytes() if path.is_file() else None
            for path in sorted(demo_root.rglob("*"))} == tree


def test_firm_says_an_unreadable_record_as_its_own_row(capsys, demo_root, monkeypatch):
    mixed, quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    real = api.load_manifest

    def broken(path, **kwargs):
        if Path(path) == mixed:
            raise api.ManifestError("the record is not readable")
        return real(path, **kwargs)

    for module in (api, firm_view, request_edit):
        monkeypatch.setattr(module, "load_manifest", broken)
    code, firm = run(capsys, "firm")
    assert code == 0, firm
    rows = {one["path"]: one for one in firm["returns"]}
    assert rows[str(mixed)]["problem"] == firm_view.FIRM_UNREADABLE == "Could Not Be Read"
    assert "record" not in firm_view.FIRM_UNREADABLE.lower() and len(firm_view.FIRM_UNREADABLE.split()) <= 5
    assert set(rows[str(mixed)]["counts"].values()) == {0}
    assert rows[str(quiet)]["problem"] == ""
    # A return nobody can read needs a person; it is never counted as complete.
    assert firm["totals"]["need"] == 1 and firm["totals"]["complete"] == 1


def test_firm_leaves_out_inactive_returns(capsys, demo_root):
    _mixed, _quiet, retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _code, firm = run(capsys, "firm")
    assert str(retired) not in {one["path"] for one in firm["returns"]}
    assert len(firm["returns"]) == 2


# ------------------------------------------ the firm view's cache (P120) ----


def test_the_firm_view_from_its_cache_is_the_whole_walks_reply_through_every_change(
        capsys, demo_root, monkeypatch):
    """P120's one rule: a cached reply is the whole walk's, field for field -
    kept households unread, changed ones read, the practice-wide facts (a
    retired prior, two open years) worked out again every time."""
    from tracker import firm_cache
    from tracker.layout import private_household_dir

    mixed, quiet, retired = _a_practice_for_the_firm_view(capsys, demo_root)
    items = [{"identifier": "A01", "document": "W-2"}]
    for household, name in (("Lee Family", "1040 - Ann Lee"), ("Kim Family", "1040 - Kim")):
        assert run(capsys, "create", stdin={"household": household, "return_name": name,
                                            "items": items})[0] == 0
    # Two open years: Lee is paused (ruling 21).
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Lee Family")),
        "return_name": "1040 - Ben Lee", "year": default_tax_year() - 1, "items": items})[0] == 0
    # A Roll Forward: Kim's prior year is retired, not shown.
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Kim Family")),
        "return_name": "1040 - Kim Old", "year": default_tax_year() - 1, "items": items})[0] == 0
    kim_old = where(demo_root, "1040 - Kim Old", household="Kim Family", year=default_tax_year() - 1)
    assert run(capsys, "rollover", stdin={"prior": str(kim_old), "year": default_tax_year()})[0] == 0
    # The review's SHOULD-1: a folder the walk passes over, and one whose
    # name no household may have, leave the cache on for everyone else.
    (demo_root / PRIVATE_TREE / "_Archive").mkdir()
    (demo_root / PRIVATE_TREE / "2019").mkdir()
    _aged(demo_root)

    whole = _firm_whole(capsys, monkeypatch)
    assert any(one["paused"] for one in whole["returns"]) and str(kim_old) not in {
        one["path"] for one in whole["returns"]}
    read = _rows_read(monkeypatch)
    assert _cached_firm(capsys) == whole                      # fills the cache
    assert firm_cache.cache_path().is_file() and len(read) == len(whole["returns"])
    read.clear()
    assert _cached_firm(capsys) == whole                      # answered from it
    assert read == [], "an unchanged practice reads no return"

    # A file dropped in Lee's inbox: only Lee's returns are read again.
    held = {one["path"]: one["draft"]["held"] for one in whole["returns"]}
    lee = where(demo_root, "1040 - Ann Lee", household="Lee Family")
    (inbox_of(lee) / "w2 made up.pdf").write_bytes(b"%PDF-1.4 made up")
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    read.clear()
    assert _cached_firm(capsys) == whole
    assert read and {Path(one).parent.parent.name for one in read} == {"Lee Family"}
    for one in whole["returns"]:
        assert one["draft"]["held"] == held[one["path"]] + (one["household"] == "Lee Family"), one["path"]

    # An edit: Quiet switched off leaves the view.
    rows = payload_of_state(capsys, quiet)["rules"]
    assert run(capsys, "edit", api.ENGAGEMENT_FLAG, str(quiet),
               stdin={"items": rows, "engagement": {"active": False}})[0] == 0
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    assert _cached_firm(capsys) == whole
    assert str(quiet) not in {one["path"] for one in whole["returns"]}
    assert {str(mixed)} <= {one["path"] for one in whole["returns"]} and str(retired) not in {
        one["path"] for one in whole["returns"]}


def test_a_prior_that_another_household_stops_retiring_is_read_again(capsys, demo_root, monkeypatch):
    """A Roll Forward may name a prior in another household. Kept while
    retired, the prior has no row; when the household that retired it goes,
    the prior is shown again, so its household is read - never answered
    blank - though its own folders did not change."""
    import shutil

    from tests.builders import make_engagement
    from tracker.layout import client_household_dir, private_household_dir
    from tracker.manifest import EngagementInfo, RequestItem

    items = [RequestItem(identifier="A01", document="W-2")]
    prior = make_engagement(demo_root, items, household="Park Family", year=default_tax_year(),
                            return_name="1040 - Park")
    make_engagement(demo_root, items, EngagementInfo(rolled_from=str(prior.resolve())),
                    household="Cho Family", year=default_tax_year(), return_name="1040 - Cho")
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    assert str(prior) not in {one["path"] for one in whole["returns"]}
    assert _cached_firm(capsys) == whole == _cached_firm(capsys)

    for folder in (private_household_dir(demo_root, "Cho Family"), client_household_dir(demo_root, "Cho Family")):
        shutil.rmtree(folder, ignore_errors=True)
    _aged(demo_root)
    read = _rows_read(monkeypatch)
    whole = _firm_whole(capsys, monkeypatch)
    assert str(prior) in {one["path"] for one in whole["returns"]}
    read.clear()
    assert _cached_firm(capsys) == whole
    assert read == [str(prior)]


def test_a_household_changed_within_seconds_is_read_fresh_and_not_kept(capsys, demo_root, monkeypatch):
    """The racy window: a record written a moment ago could be written again
    in the same tick at the same size, so its household is read every time
    until it has been still for a few seconds."""
    from tracker import firm_cache

    _a_practice_for_the_firm_view(capsys, demo_root)
    read = _rows_read(monkeypatch)
    assert _cached_firm(capsys)["returns"]
    assert _cached_firm(capsys) == _firm_whole(capsys, monkeypatch)
    assert len(read) == 6, "three replies, two shown returns, every one read"
    assert not firm_cache.cache_path().exists() or json.loads(
        firm_cache.cache_path().read_text(encoding="utf-8"))["households"] == {}


def test_a_household_with_a_problem_is_never_kept_so_its_detail_is_logged_every_time(
        capsys, demo_root, monkeypatch):
    from tracker import firm_cache

    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    real, kept = api.load_manifest, []

    def broken(path, **kwargs):
        if Path(path) == mixed:
            kept.append(1)
            raise api.ManifestError("the record is not readable")
        return real(path, **kwargs)

    for module in (api, firm_view, request_edit):
        monkeypatch.setattr(module, "load_manifest", broken)
    for _ in range(2):
        rows = {one["path"]: one for one in _cached_firm(capsys)["returns"]}
        assert rows[str(mixed)]["problem"] == firm_view.FIRM_UNREADABLE
    assert len(kept) == 2, "read, and said, on every reply"
    households = json.loads(firm_cache.cache_path().read_text(encoding="utf-8"))["households"] \
        if firm_cache.cache_path().exists() else {}
    assert HOUSEHOLD not in households


def test_the_firm_view_answers_whole_when_its_cache_is_unsure(capsys, demo_root, monkeypatch, caplog):
    import logging

    from tracker import firm_cache

    _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)

    def surprised(path, expected):
        raise RuntimeError("an unexpected shape")

    monkeypatch.setattr(firm_cache, "load", surprised)
    with caplog.at_level(logging.WARNING, logger="tracker.api"):
        assert _cached_firm(capsys) == whole
    assert "cache was set aside (RuntimeError)" in caplog.text
    monkeypatch.setattr(firm_view, "household_positions", lambda root: None)       # no one private tree
    assert _cached_firm(capsys) == whole


def test_the_firm_cache_is_one_file_in_the_data_folder_and_nothing_in_either_client_tree(
        capsys, demo_root):
    from tracker import firm_cache
    from tracker.settings import data_home

    _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    tree = {str(path): path.read_bytes() if path.is_file() else None for path in sorted(demo_root.rglob("*"))}
    home = set(data_home().rglob("*"))
    _cached_firm(capsys)
    assert set(data_home().rglob("*")) - home == {firm_cache.cache_path()}
    assert {str(path): path.read_bytes() if path.is_file() else None
            for path in sorted(demo_root.rglob("*"))} == tree
    written = firm_cache.cache_path().stat().st_mtime_ns
    _cached_firm(capsys)
    assert firm_cache.cache_path().stat().st_mtime_ns == written, "an unchanged practice writes nothing"


def test_a_practice_with_nothing_to_keep_yet_still_leaves_todays_head(capsys, demo_root):
    """P201 R5: every household changed within the racy window (as just
    after a pass), so none is kept - and the cache is still written under
    today's head, so the pass's fill can tell an answered summary from one
    that kept nothing because it could not write."""
    import datetime as dt

    from tracker import firm_cache

    _a_practice_for_the_firm_view(capsys, demo_root)
    assert not firm_cache.cache_path().exists()
    _cached_firm(capsys)
    head = firm_cache.head(str(api._saved_root()), dt.date.today())
    assert firm_cache.holds(firm_cache.cache_path(), [head])
    assert firm_cache.load(firm_cache.cache_path(), head) == {}, "nothing racy is kept"


def test_a_practice_with_nothing_to_keep_writes_the_cache_once_per_head_not_every_reply(
        capsys, demo_root, monkeypatch):
    """The engine review's NIT-1: while nothing is kept, the head is left by
    the first reply only; a later reply under the same head writes nothing,
    and a reply under another head (another day) writes it again."""
    import datetime as dt

    from tracker import firm_cache

    monkeypatch.setattr(firm_cache, "RACY_SECONDS", 10 ** 6)     # every household stays racy
    _a_practice_for_the_firm_view(capsys, demo_root)
    _cached_firm(capsys)
    head = firm_cache.head(str(api._saved_root()), dt.date.today())
    assert firm_cache.load(firm_cache.cache_path(), head) == {}, "nothing racy is kept"
    saved = []
    real_save = firm_cache.save
    monkeypatch.setattr(firm_cache, "save", lambda *args: saved.append(args) or real_save(*args))

    _cached_firm(capsys)
    assert saved == [], "the same head, nothing kept: nothing written"

    firm_cache.save(firm_cache.cache_path(), {**head, "day": "1999-01-01"}, {})
    saved.clear()
    _cached_firm(capsys)
    assert len(saved) == 1 and saved[0][1] == head


def test_the_commands_held_to_one_reading_write_nothing_and_a_write_there_is_refused(
        capsys, demo_root, monkeypatch):
    """P118, and the review's SHOULD-3: a command joins
    ``HELD_READING_COMMANDS`` only when it writes nothing; a settings or
    record write inside one is refused outright, and ``list``, ``state``
    and ``firm`` answer with that refusal in place."""
    from tracker import settings

    assert api.HELD_READING_COMMANDS <= set(api.COMMANDS)
    assert not api.HELD_READING_COMMANDS & api.WRITING_COMMANDS
    assert api.PASS_COMMAND not in api.HELD_READING_COMMANDS
    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    for argv in (["list"], ["state", api.ENGAGEMENT_FLAG, str(mixed)], ["firm"]):
        assert run(capsys, *argv)[0] == 0, argv
    real = api._cmd_firm

    def writes(argv):
        settings.set_firm("written inside a read-only reply")
        return real(argv)

    monkeypatch.setitem(api.COMMANDS, "firm", writes)
    code, payload = run(capsys, "firm")
    assert code != 0 and payload["failure"]["kind"] == "failed"
    assert settings.firm() == "J Park & Associates, CPA"


def test_the_firm_key_spells_every_key_as_the_plain_walk_does():
    """P119: remembering each key's spellings gives the plain walk's answer,
    key for key, including the same path asked twice."""
    import random

    chooser = random.Random(209)
    asked = [(f"shown_copy {chooser.randint(1, 4)}", f"C:/r{chooser.randint(1, 30)}/copy.pdf")
             for _ in range(400)]
    plain, fast, spelled_for = {}, {}, {}
    for key, path in asked:
        assert api._firm_key(fast, key, path, spelled_for) == api._firm_key(plain, key, path)
    assert fast == plain
    # A key that already reads like a spelling takes the plain walk.
    literal, walked = {"k #2": "C:/b"}, {"k #2": "C:/b"}
    for key, path in [("k", "C:/a"), ("k", "C:/b"), ("k #2", "C:/c")]:
        assert api._firm_key(literal, key, path, {}) == api._firm_key(walked, key, path)


def test_the_vocabulary_carries_the_shell_join_words_and_keeps_the_dismiss_icon():
    """S5's editor words (two proposed for Jason), the one Close word (S5
    review F9), and the Bad Year reason (ruling 18a); the notice's Dismiss
    icon stays."""
    words = api.vocab()
    screen = words["screen"]
    assert screen["close"] == "Close" and screen["icons"]["dismiss"] == "Dismiss"
    assert screen["notices"]["pick_request"] == "Pick a Request First"
    assert screen["notices"]["name_requests"] == "Name Each Custom Request"
    assert words["editor"]["advanced"] == "Advanced"
    assert screen["misfits"]["reasons"]["not_a_year"] == "Bad Year"


def test_firm_marks_every_return_of_a_household_paused_for_two_open_years(capsys, demo_root):
    """Ruling 21: ``paused`` is true on each returns[] entry of a household
    with two open years (the pass sorts nothing from its inbox) and false on
    every other, and a prior year a person switched off ends the pause."""
    from tracker.layout import private_household_dir

    items = [{"identifier": "A01", "document": "W-2"}]
    assert run(capsys, "create", stdin={"household": "Lee Family", "return_name": "1040 - Ann Lee",
                                        "items": items})[0] == 0
    assert run(capsys, "create", stdin={"household": "Kim Family", "return_name": "1040 - Kim",
                                        "items": items})[0] == 0
    _code, firm = run(capsys, "firm")
    assert [one["paused"] for one in firm["returns"]] == [False, False]

    prior = run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Lee Family")),
        "return_name": "1040 - Ben Lee", "year": default_tax_year() - 1, "items": items})
    assert prior[0] == 0
    _code, firm = run(capsys, "firm")
    said = {one["label"]: one["paused"] for one in firm["returns"]}
    assert len(said) == 3 and sum(said.values()) == 2
    assert {one["household"] for one in firm["returns"] if one["paused"]} == {"Lee Family"}

    ben = where(demo_root, "1040 - Ben Lee", household="Lee Family", year=default_tax_year() - 1)
    rows = payload_of_state(capsys, ben)["rules"]
    assert run(capsys, "edit", api.ENGAGEMENT_FLAG, str(ben),
               stdin={"items": rows, "engagement": {"active": False}})[0] == 0
    _code, firm = run(capsys, "firm")
    assert len(firm["returns"]) == 2 and not any(one["paused"] for one in firm["returns"])


def test_firm_says_a_root_it_cannot_walk_and_answers_an_empty_root_as_nothing(capsys, demo_root,
                                                                            monkeypatch):
    code, firm = run(capsys, "firm")
    assert code == 0 and firm["returns"] == [] and firm["totals"]["need"] == 0

    def not_walked(root):
        raise api.RegistryError("nope")

    monkeypatch.setattr(api, "discover_engagements", not_walked)
    code, payload = run(capsys, "firm")
    assert code == 1 and payload["error"] == screen_words.PRACTICE_NOT_WALKED


def test_list_reports_the_clients_root_and_the_firm_report_as_openable(capsys, demo_root):
    from tracker.status_page import STATUS_PAGE_FILENAME

    _code, payload = run(capsys, "list")
    assert payload["paths"] == {"clients_root": str(demo_root),
                                "status": str(demo_root / STATUS_PAGE_FILENAME)}
    assert screen_words.PATH_KINDS["clients_root"] == "folder"
    assert set(payload["paths"]) <= set(screen_words.PATH_KINDS)
    assert payload["vocab"]["path_kinds"]["clients_root"] == "folder"


def test_the_vocabulary_carries_the_menu_the_screen_and_the_short_words(capsys):
    words = api.vocab()
    assert words["menu"] == screen_words.MENU and words["screen"] == screen_words.SCREEN
    # The key shape of SPEC-shell 11.4, flat: the harness and the renderer read these.
    assert set(words["screen"]["sort"]) == {"now", "stop", "locked", "stopping", "tip"}
    assert words["screen"]["sort"]["stop"] == "Stop Sorting"
    assert words["screen"]["filters"] == {"work": "Work Waiting", "all": "All"}
    assert words["reasons"] == reasons.SHORT_REASONS
    assert words["reason_tips"] == reasons.REASON_TIPS
    assert [stage["short"] for stage in words["reminder"]["stages"]] == [
        "Heads Up", "Checking In", "Deadline Near", "Final Notice"]
    assert [rule["short"] for rule in words["rules"]] == list(api.SAFEGUARDS)
    assert [rule["headline"] for rule in words["rules"]] == [h for h, _ in api.STANDING_RULES]
    # The stored words do not change (P77); the editor shows them as stored.
    assert "Client confirmed this is the final version" in words["override_reasons"]
    assert words["schedule"]["move_warning"] == "Only If {host} Is Retired"
    assert words["editor"]["engagement_fields"][8]["help"] == "No: Sorting Skips This Return"


def test_every_short_word_the_engine_adds_is_five_words_or_fewer():
    import re

    def walk(node, path=""):
        if isinstance(node, dict):
            for key, value in node.items():
                yield from walk(value, f"{path}.{key}")
        else:
            yield path, node

    #: Words that are longer on purpose, with why. SPEC-mac R29 names this
    #: menu item, and the Mac check kit's walk (step 14) chooses it by those words.
    longer_on_purpose = {"menu.remove_schedule_here": "SPEC-mac R29's own label, chosen by the kit's walk"}
    for path, text in [*walk(screen_words.MENU, "menu"), *walk(screen_words.SCREEN, "screen"),
                       *walk(reasons.SHORT_REASONS, "reasons"), *walk(reasons.REASON_TIPS, "reason_tips")]:
        counted = re.sub(r"\{[a-z_]+\}", "x", text.replace("&", "")).split()
        assert 1 <= len(counted) <= (6 if path in longer_on_purpose else 5), (path, text)
    assert screen_words.MENU["remove_schedule_here"] == "Remove the Schedule From This Mac…"


# ------------------------------------------- a wait says what it shows (P222) ----


def _a_practice_of_five_households(capsys, demo_root) -> int:
    """Five households for the batches (made-up names): the three-return
    practice, two more, a Roll Forward that retires a prior, and one whose
    household record is gone. Returns how many household folders there are."""
    from tracker.layout import private_household_dir

    _a_practice_for_the_firm_view(capsys, demo_root)
    items = [{"identifier": "A01", "document": "W-2"}]
    for household, name in (("Lee Family", "1040 - Ann Lee"), ("Kim Family", "1040 - Kim"),
                            ("Oak Family", "1040 - Oak"), ("Gone Family", "1040 - Gone")):
        assert run(capsys, "create", stdin={"household": household, "return_name": name,
                                            "items": items})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Kim Family")),
        "return_name": "1040 - Kim Old", "year": default_tax_year() - 1, "items": items})[0] == 0
    kim_old = where(demo_root, "1040 - Kim Old", household="Kim Family", year=default_tax_year() - 1)
    assert run(capsys, "rollover", stdin={"prior": str(kim_old), "year": default_tax_year()})[0] == 0
    store.close()
    ledger.path_for(private_household_dir(demo_root, "Gone Family")).unlink()
    _aged(demo_root)
    return len([folder for folder in (demo_root / PRIVATE_TREE).iterdir() if folder.is_dir()])


def _firm_lines(capsys) -> list[dict]:
    """Every line ``firm`` printed, the reply last."""
    code = api.main(["firm"])
    lines = [json.loads(line) for line in capsys.readouterr().out.strip().splitlines()]
    assert code == 0, lines[-1]
    return lines


def test_a_cold_overview_says_each_batch_of_households_it_reads(capsys, demo_root, monkeypatch):
    """P222: reading households afresh, ``firm`` says how far it is - one
    count line before the first batch and one after each, flushed before
    the reply: ``done`` from 0 to every household read, never falling, and
    nothing but the format's version, the event and the two counts."""
    from tracker import firm_cache, progress

    households = _a_practice_of_five_households(capsys, demo_root)
    firm_cache.cache_path().unlink(missing_ok=True)
    monkeypatch.setattr(firm_view, "FIRM_READ_BATCH", 2)
    *counts, reply = _firm_lines(capsys)
    assert progress.PROGRESS_KEY not in reply and reply["returns"]
    said = [line[progress.PROGRESS_KEY] for line in counts]
    assert [one["done"] for one in said] == [0, *range(2, households, 2), households]
    for one in said:
        assert one == {"v": progress.FORMAT_VERSION, "event": progress.COUNT_EVENT,
                       "done": one["done"], "total": households}


def test_a_warm_overview_prints_no_count(capsys, demo_root):
    """Nothing read afresh, nothing to count: the reply is the one line.
    (A household with a problem is never kept, so a practice without one.)"""
    _a_practice_for_the_firm_view(capsys, demo_root)
    _aged(demo_root)
    assert len(_firm_lines(capsys)) > 1                      # cold: counted, and the cache filled
    assert len(_firm_lines(capsys)) == 1


def test_an_overview_read_in_batches_is_the_whole_walks_answer(capsys, demo_root, monkeypatch):
    """The batches change when a row is built, never what it says: with one
    and two households a batch - across a Roll Forward and a household whose
    record is gone - the cold reply is the whole walk's, field for field."""
    from tracker import firm_cache

    _a_practice_of_five_households(capsys, demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    for batch in (1, 2):
        firm_cache.cache_path().unlink(missing_ok=True)
        monkeypatch.setattr(firm_view, "FIRM_READ_BATCH", batch)
        assert _firm_lines(capsys)[-1] == whole, batch
        assert _firm_lines(capsys)[-1] == whole, batch          # and kept, the same


def test_the_speed_round_words_are_in_the_screen_vocabulary():
    """P222's two words, approved by Jason 2026-10-08: the shell types
    neither; it fills ``reading_households`` with a count line's numbers."""
    screen = api.vocab()["screen"]
    assert screen["updating"] == "Updating"
    assert screen["reading_households"] == "Reading {n} of {total} Households"
    rows = [line.split("\t") for line in
            (Path(__file__).resolve().parents[1] / "pilot" / "wording-shell.tsv").read_text(
                encoding="utf-8").splitlines()]
    proposed = {row[1]: row[4] for row in rows if len(row) > 4}
    assert proposed["screen.updating"] == screen["updating"]
    assert proposed["screen.reading_households"] == screen["reading_households"]


# ------------------------------- the Overview's last counts at launch (P229) ----

def _a_practice_kept_whole(capsys, demo_root, monkeypatch) -> dict:
    """The firm-view practice with a paused household (two open years) and a
    Roll Forward that retires a prior, aged past the racy window, and one
    ``firm`` reply that kept every household: that reply."""
    from tracker.layout import private_household_dir

    _a_practice_for_the_firm_view(capsys, demo_root)
    items = [{"identifier": "A01", "document": "W-2"}]
    for household, name in (("Lee Family", "1040 - Ann Lee"), ("Kim Family", "1040 - Kim")):
        assert run(capsys, "create", stdin={"household": household, "return_name": name,
                                            "items": items})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Lee Family")),
        "return_name": "1040 - Ben Lee", "year": default_tax_year() - 1, "items": items})[0] == 0
    assert run(capsys, "create", stdin={
        "household_path": str(private_household_dir(demo_root, "Kim Family")),
        "return_name": "1040 - Kim Old", "year": default_tax_year() - 1, "items": items})[0] == 0
    kim_old = where(demo_root, "1040 - Kim Old", household="Kim Family", year=default_tax_year() - 1)
    assert run(capsys, "rollover", stdin={"prior": str(kim_old), "year": default_tax_year()})[0] == 0
    _aged(demo_root)
    whole = _firm_whole(capsys, monkeypatch)
    assert _cached_firm(capsys) == whole
    return whole


def _firm_last(capsys) -> dict:
    code, payload = run(capsys, "firm-last")
    assert code == 0, payload
    return payload


def test_the_last_counts_are_the_firm_reply_when_nothing_changed(capsys, demo_root, monkeypatch):
    """P229: ``firm-last`` is the ``firm`` reply - every row, file, path,
    total and the next sort - built from the kept households alone, plus
    ``last`` and ``as_of``: the cache file's last write, ``HH:MM`` local, as
    ``next_sort`` is said. Paused households and a retired prior are worked
    out again from the kept facts, as ``firm`` does."""
    from tracker import firm_cache

    whole = _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    assert any(one["paused"] for one in whole["returns"])
    last = _firm_last(capsys)
    assert last["last"] is True
    written = dt.datetime.fromtimestamp(firm_cache.cache_path().stat().st_mtime)
    assert last["as_of"] == written.strftime("%H:%M")
    assert re.fullmatch(r"\d{2}:\d{2}", last["as_of"])
    assert {key: value for key, value in last.items() if key not in ("last", "as_of")} == whole
    assert api.COMMANDS["firm-last"] is api._cmd_firm_last


def test_no_last_counts_after_a_program_change_another_root_or_another_day(capsys, demo_root, monkeypatch):
    """Never after an upgrade or any code change, never another clients
    folder's, data folder's or day's, never under another settings file:
    each answers ``{"last": null}`` and the window waits for the fresh
    reply, as before P229."""
    from tracker import firm_cache

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    where = firm_cache.cache_path()
    head = firm_cache.head(str(api._saved_root()), dt.date.today())
    households = firm_cache.load(where, head)
    assert households and _firm_last(capsys)["last"] is True
    for key, other in (("program", "another program"), ("root", "/another/root"), ("day", "2020-01-01"),
                       ("data_home", "/another/data"), ("settings", [1, 2]), ("format", -1)):
        firm_cache.save(where, {**head, key: other}, households)
        payload = _firm_last(capsys)
        assert payload == {"last": None, "warnings": payload["warnings"]}, key
    firm_cache.save(where, head, households)
    assert _firm_last(capsys)["last"] is True
    with monkeypatch.context() as patch:
        # A program changed since the cache was written: its stamp is not the head's.
        patch.setattr(firm_cache, "program_stamp", lambda: "the next version")
        assert _firm_last(capsys)["last"] is None
    where.unlink()
    assert _firm_last(capsys)["last"] is None


def test_no_last_counts_while_any_household_is_not_kept(capsys, demo_root, monkeypatch):
    """No partial practice, no partial totals: a household the walk lists
    with no kept entry, a kept entry the walk no longer lists, a kept
    household with a problem, and a return now shown whose row was never
    kept - each answers nothing."""
    from tracker import firm_cache
    from tracker.layout import private_household_dir

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    where = firm_cache.cache_path()
    head = firm_cache.head(str(api._saved_root()), dt.date.today())
    households = firm_cache.load(where, head)

    newcomer = private_household_dir(demo_root, "Moon Family")
    newcomer.mkdir()
    assert _firm_last(capsys)["last"] is None, "a household position with no kept entry"
    newcomer.rmdir()
    assert _firm_last(capsys)["last"] is True

    firm_cache.save(where, head, {**households, "Gone Family": next(iter(households.values()))})
    assert _firm_last(capsys)["last"] is None, "a kept entry the walk does not list"

    name = next(iter(households))
    troubled = json.loads(json.dumps(households))
    troubled[name]["returns"][0]["problem"] = "could not be read"
    firm_cache.save(where, head, troubled)
    assert _firm_last(capsys)["last"] is None, "a kept household with a problem"

    unshown = json.loads(json.dumps(households))
    shown_one = next(one for entry in unshown.values() for one in entry["returns"] if one["shown"] is not None)
    shown_one["shown"] = None
    firm_cache.save(where, head, unshown)
    assert _firm_last(capsys)["last"] is None, "a shown return whose row was not kept"


def test_every_last_counts_refusal_is_said_by_its_own_name_and_only_the_unusual_reach_the_error_log(
        capsys, demo_root, monkeypatch, caplog):
    """Each way ``firm-last`` answers nothing is driven once and said by
    its name from ``FIRM_LAST_REFUSALS`` and no other: the ordinary ones
    (no cache under today's head, no plain positions, the file rewritten
    while read) below the error log's WARNING floor, the unusual ones
    (households not the walk's, a problem household, a shown return
    without a kept row) on it - never a client's words."""
    import logging

    from tracker import firm_cache

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    where = firm_cache.cache_path()
    head = firm_cache.head(str(api._saved_root()), dt.date.today())
    households = firm_cache.load(where, head)
    said: dict[str, int] = {}

    def refused(name: str) -> None:
        caplog.clear()
        with caplog.at_level(logging.DEBUG, logger="tracker.api"):
            assert _firm_last(capsys)["last"] is None, name
        records = [record for record in caplog.records if "last counts were not shown" in record.getMessage()]
        assert [record.getMessage() for record in records] == [f"The last counts were not shown ({name})"]
        assert all(household not in records[0].getMessage() for household in households)
        said[name] = records[0].levelno
        firm_cache.save(where, head, households)

    with monkeypatch.context() as patch:
        patch.setattr(firm_view, "household_positions", lambda root: None)
        refused("no_positions")
    firm_cache.save(where, {**head, "day": "2020-01-01"}, households)
    refused("no_kept_practice")
    real_load = firm_cache.load

    def load_then_rewritten(path, expected):
        kept = real_load(path, expected)
        stamp = path.stat().st_mtime_ns + 5_000_000_000
        os.utime(path, ns=(stamp, stamp))
        return kept

    with monkeypatch.context() as patch:
        patch.setattr(firm_cache, "load", load_then_rewritten)
        refused("cache_rewritten")
    firm_cache.save(where, head, {**households, "Gone Family": next(iter(households.values()))})
    refused("households_differ")
    troubled = json.loads(json.dumps(households))
    troubled[next(iter(troubled))]["returns"][0]["problem"] = "could not be read"
    firm_cache.save(where, head, troubled)
    refused("household_problem")
    unshown = json.loads(json.dumps(households))
    next(one for entry in unshown.values() for one in entry["returns"] if one["shown"] is not None)["shown"] = None
    firm_cache.save(where, head, unshown)
    refused("row_not_kept")
    assert _firm_last(capsys)["last"] is True

    assert said == firm_view.FIRM_LAST_REFUSALS
    assert {name for name, level in said.items() if level >= logging.WARNING} == \
        {"households_differ", "household_problem", "row_not_kept"}


def test_the_last_counts_time_is_the_files_before_it_was_read(capsys, demo_root, monkeypatch):
    """``as_of`` is the cache file's time taken before the load, never one
    a ``firm`` reply wrote while it was read: a file whose time moved
    between the load and the answer refuses (``cache_rewritten``)."""
    from tracker import firm_cache

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    where = firm_cache.cache_path()
    then = dt.datetime.now().replace(hour=7, minute=5, second=0, microsecond=0).timestamp()
    os.utime(where, (then, then))
    assert _firm_last(capsys)["as_of"] == "07:05"
    real_load = firm_cache.load

    def rewritten_while_read(path, expected):
        kept = real_load(path, expected)
        later = then + 3600
        os.utime(path, (later, later))
        return kept

    monkeypatch.setattr(firm_cache, "load", rewritten_while_read)
    assert _firm_last(capsys)["last"] is None


def test_the_last_counts_read_no_record_and_take_no_fingerprint(capsys, demo_root, monkeypatch):
    """The whole point of P229: no household's folders are listed for a
    fingerprint, no record, list, index or detail is read, and the walk's
    per-household reading never runs - only the cache file and the walk's
    positions (one listing of the private tree)."""
    from tracker import firm_cache, registry

    whole = _a_practice_kept_whole(capsys, demo_root, monkeypatch)

    def forbidden(*args, **kwargs):
        raise AssertionError("firm-last read what it must not")

    for module, name in ((firm_cache, "fingerprint"), (firm_cache, "fingerprints"), (api, "load_manifest"),
                         (firm_view, "load_manifest"), (request_edit, "load_manifest"),
                         (api, "read_index"), (firm_view, "read_index"), (api, "_firm_row"),
                         (firm_view, "_firm_row"), (api, "households_named"), (firm_view, "households_named"),
                         (household_edit, "households_named"),
                         (api, "discover_engagements"), (registry, "engagement_from"),
                         (store, "connect"), (ledger, "read_with_chain")):
        monkeypatch.setattr(module, name, forbidden)
    last = _firm_last(capsys)
    assert {key: value for key, value in last.items() if key not in ("last", "as_of")} == whole


def test_the_last_counts_write_nothing(capsys, demo_root, monkeypatch):
    """No cache save, no record, nothing in either client tree or the data
    folder - asked when it answers and when it refuses."""
    from tracker import firm_cache
    from tracker.settings import data_home

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)

    def snapshot():
        return {str(path): (path.stat().st_mtime_ns, path.read_bytes() if path.is_file() else None)
                for folder in (demo_root, data_home()) for path in sorted(folder.rglob("*"))
                if path.name != "tracker-errors.log"}

    def refused_save(*args, **kwargs):
        raise AssertionError("firm-last saved the cache")

    monkeypatch.setattr(firm_cache, "save", refused_save)
    before = snapshot()
    assert _firm_last(capsys)["last"] is True
    assert snapshot() == before
    monkeypatch.setattr(firm_cache, "program_stamp", lambda: "the next version")
    assert _firm_last(capsys)["last"] is None
    assert snapshot() == before
    assert "firm-last" in api.HELD_READING_COMMANDS and "firm-last" not in api.WRITING_COMMANDS


def test_the_last_counts_words_are_in_the_screen_vocabulary():
    """P229's word, approved by Jason 2026-10-08 as written: the shell fills
    ``updating_as_of`` with ``firm-last``'s ``as_of``, said as a time."""
    screen = api.vocab()["screen"]
    assert screen["updating_as_of"] == "Updating, as of {time}"
    rows = [line.split("\t") for line in
            (Path(__file__).resolve().parents[1] / "pilot" / "wording-shell.tsv").read_text(
                encoding="utf-8").splitlines()]
    proposed = {row[1]: row[4] for row in rows if len(row) > 4}
    assert proposed["screen.updating_as_of"] == screen["updating_as_of"]


def _zip_bytes(*names: str) -> bytes:
    import io
    import zipfile

    packed = io.BytesIO()
    with zipfile.ZipFile(packed, "w") as archive:
        for name in names:
            archive.writestr(name, b"made-up")
    return packed.getvalue()


def test_a_mac_says_protected_view_does_not_exist_each_time_a_macro_copy_opens(
        capsys, demo_root, tmp_path, monkeypatch):
    """SPEC-mac R8 (P240): a Mac cannot mark a review copy for Protected View,
    so the copy is made unmarked as before, and the API names - for the shell -
    each openable path whose copy Windows would have marked
    (``copies._may_carry_code``), with the one sentence the shell then says each
    time it opens one. Windows and Linux name none: there the mark itself is
    the answer."""
    from tracker import fsio, settings

    assert fsio.mark_from_internet(tmp_path / "budget.xlsm", _opener=lambda *a, **k: None) is False
    # The sentence is learned from the API, as the shell's others are.
    assert api.vocab()["shell"]["protected_view_mac"] == screen_words.PROTECTED_VIEW_MAC
    assert screen_words.PROTECTED_VIEW_MAC.startswith("Protected View does not exist on a Mac")

    engagement = tmp_path / "return"
    review = engagement / REVIEW_DIR_NAME
    review.mkdir(parents=True)
    copies = {
        "macros.xlsm": b"made-up",                                   # a macro-enabled type
        "packaged.xlsx": _zip_bytes("[Content_Types].xml", "xl/vbaProject.bin"),   # a VBA project inside
        "plain.xlsx": _zip_bytes("[Content_Types].xml", "xl/workbook.xml"),
        "statement.pdf": b"%PDF-made-up",
    }
    for name, content in copies.items():
        (review / name).write_bytes(content)
    code = sorted(reasons.READ_AND_PARKED_CODES)[0]
    rows = [_parked_row(name, code) for name in copies]
    rows.append(_parked_row("mail.eml", sorted(firm_view._CONTAINER_CODES)[0]))     # never opens, so never named
    (review / "mail.eml").write_bytes(b"made-up")

    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    assert api._code_copies(engagement, rows) == [str(review / "macros.xlsm"), str(review / "packaged.xlsx")]
    for system in ("nt", "posix"):
        monkeypatch.setattr(settings, "host_system", lambda system=system: system)
        assert api._code_copies(engagement, rows) == []

    # And the state the shell reads carries the list beside its paths.
    state, parked = _parked_read_pdf_state(capsys, demo_root, tmp_path)
    assert state["carries_code"] == []
    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    monkeypatch.setattr(settings, "_statfs", lambda path: (settings.MNT_LOCAL, "/"))   # the test's disk
    monkeypatch.setattr(api, "_may_carry_code", lambda copy: copy.suffix == ".pdf")
    code, replied = run(capsys, "state", api.ENGAGEMENT_FLAG, str(where(demo_root, "Smith Family 2025")))
    assert code == 0, replied
    [path] = replied["carries_code"]
    assert path == replied["paths"][parked["open_key"]]


#: A word that names a Windows program, place or file (SPEC-mac R11): none may
#: reach a Mac, whose Finder, launchd and setup.command stand in their places.
WINDOWS_WORDS = re.compile(r"File Explorer|\bPC\b|Task Scheduler|schtasks|Setup\.bat|\.bat\b|\bWindows\b")


def _every_string(value, path=""):
    """(dotted path, text) for every string in a nested reply."""
    if isinstance(value, dict):
        for key, inner in value.items():
            yield from _every_string(inner, f"{path}.{key}" if path else str(key))
    elif isinstance(value, (list, tuple)):
        for n, inner in enumerate(value):
            yield from _every_string(inner, f"{path}[{n}]")
    elif isinstance(value, str):
        yield path, value


def test_a_mac_is_never_shown_a_windows_word(monkeypatch):
    """SPEC-mac R11. Where a sentence the app shows names a Windows program or
    place, darwin gets its own words from the same table: Finder for File
    Explorer, another Mac for another PC, launchd for Task Scheduler, setup.command
    for Setup.bat. Nothing else in the vocabulary changes, and Windows and Linux
    are told what they always were."""
    from tools.lockfiles import CHANGED_MAC, NOT_SET_UP_MAC
    from tracker import after_install, settings

    changed = {"menu.show_in_explorer", "screen.show_in_explorer", "scan.reasons.lock-held"}
    monkeypatch.setattr(settings, "host_system", lambda: "posix")
    windows = dict(_every_string(api.vocab()))
    assert {path for path, text in windows.items() if WINDOWS_WORDS.search(text)} == changed
    assert after_install.schedule_unreachable() == after_install.SCHEDULE_UNREACHABLE
    monkeypatch.setattr(settings, "host_system", lambda: "darwin")
    mac = dict(_every_string(api.vocab()))
    assert [path for path, text in mac.items() if WINDOWS_WORDS.search(text)] == []
    assert mac["menu.show_in_explorer"] == mac["screen.show_in_explorer"] == "Show in Finder"
    assert mac["scan.reasons.lock-held"] == "Another Mac Sorting"
    # (``shell.error_log`` and ``shell.last_pass_file`` are paths this machine names, not words.)
    other = changed | {"shell.error_log", "shell.last_pass_file"}
    assert {path: text for path, text in mac.items() if path not in other} == {
        path: text for path, text in windows.items() if path not in other}
    # The same house style as every other word: title case, five words or fewer.
    for path in changed:
        assert title_case(mac[path]) == mac[path] and len(mac[path].split()) <= 5, path
    # And the two sentences outside the vocabulary that a Mac's person is shown.
    said = after_install.SCHEDULE_FAILED.format(problem=after_install.schedule_unreachable())
    assert "launchd refused it" in said and not WINDOWS_WORDS.search(said)
    for sentence in (NOT_SET_UP_MAC, CHANGED_MAC):
        assert not WINDOWS_WORDS.search(sentence)


def test_the_apis_mac_words_replace_only_what_names_windows():
    assert set(screen_words.MAC_MENU) <= set(screen_words.MENU) and set(screen_words.MAC_SCREEN) <= set(screen_words.SCREEN)
    assert set(screen_words.MAC_SCAN_REASONS) <= set(screen_words.SCAN_REASONS)
    for table, windows in ((screen_words.MAC_MENU, screen_words.MENU), (screen_words.MAC_SCREEN, screen_words.SCREEN),
                           (screen_words.MAC_SCAN_REASONS, screen_words.SCAN_REASONS)):
        for key, word in table.items():
            assert WINDOWS_WORDS.search(windows[key]) and not WINDOWS_WORDS.search(word), key


# ── P278 (SPEC-ui-menu-speed §4): the engine pages the firm lists ───────────

def _a_page(list_="overview", at=0, order=None, view=None, **filter) -> dict:
    """The stdin of one page of one firm list (SPEC 4.2)."""
    ask = {"page": {"list": list_, "at": at, "order": order, "filter": filter}}
    return {**ask, "view": view} if view else ask


def _firm_page(capsys, list_="overview", **kwargs) -> dict:
    code, reply = run(capsys, "firm", stdin=_a_page(list_, **kwargs))
    assert code == 0, reply
    return reply


def _forbid_the_walk(monkeypatch) -> None:
    """Every way ``firm`` reads the firm: the walk, the fingerprints and the record readers."""
    from tracker import firm_cache

    def refuses(*args, **kwargs):
        raise AssertionError("the view was to be read, not the firm")

    for name in ("discover_engagements", "households_named", "_firm_row", "load_manifest", "read_index",
                 "load_engagement_info", "_firm_fresh", "_firm_cached"):
        monkeypatch.setattr(api, name, refuses)
    for name in ("household_positions", "households_named", "_firm_row", "load_manifest", "read_index",
                 "load_engagement_info"):
        monkeypatch.setattr(firm_view, name, refuses)
    monkeypatch.setattr(request_edit, "load_manifest", refuses)
    monkeypatch.setattr(household_edit, "households_named", refuses)
    monkeypatch.setattr(firm_cache, "fingerprint", refuses)
    monkeypatch.setattr(firm_cache, "fingerprints", refuses)


def test_firm_without_a_page_answers_the_whole_reply_as_before(capsys, demo_root):
    from tracker import firm_pages

    _a_practice_for_the_firm_view(capsys, demo_root)
    code, plain = run(capsys, "firm")
    assert code == 0 and set(plain) == {"returns", "files", "totals", "paths", "next_sort", "warnings"}
    code, empty = run(capsys, "firm", stdin={})
    assert code == 0 and empty == plain
    assert not firm_pages.pages_path().exists(), "a whole reply saves no view"


def test_firm_with_a_page_answers_one_page_the_totals_and_every_returns_counts(capsys, demo_root):
    mixed, _quiet, _retired = _a_practice_for_the_firm_view(capsys, demo_root)
    whole = run(capsys, "firm")[1]
    reply = _firm_page(capsys)
    assert set(reply) == {"view", "totals", "next_sort", "return_counts", "page", "paths", "warnings"}
    assert isinstance(reply["view"], str) and len(reply["view"]) == 16
    assert reply["totals"] == whole["totals"] and reply["next_sort"] == whole["next_sort"]
    assert reply["return_counts"] == [{key: one[key] for key in ("path", "household", "year", "form", "counts", "files", "problem", "paused")}
                                      for one in whole["returns"]]
    assert reply["page"]["list"] == "overview" and reply["page"]["rows"] and reply["page"]["total"] == len(reply["page"]["rows"])
    assert {row["path"] for row in reply["page"]["rows"]} <= {one["path"] for one in whole["returns"]}
    review = _firm_page(capsys, "needs_review")
    assert [group["path"] for group in review["page"]["rows"]] == [str(mixed)]
    assert [one["name"] for one in review["files_found"]] == ["setup.exe"] and review["page"]["rows"][0]["files"][0]["name"] == "setup.exe"


def test_the_paged_reply_carries_no_returns_or_files_list_and_paths_only_for_its_rows(capsys, demo_root, tmp_path):
    _firm_of_a_scanned_pile(capsys, demo_root, tmp_path)
    whole = run(capsys, "firm")[1]
    assert whole["files"] and whole["paths"]
    for list_ in ("overview", "needs_review", "reminders", "clients"):
        reply = _firm_page(capsys, list_)
        assert "returns" not in reply and "files" not in reply, list_
    reply = _firm_page(capsys, "needs_review")
    named = {one["open_key"] for group in reply["page"]["rows"] for one in group["files"] if one["open_key"]}
    assert named and reply["paths"] == {key: whole["paths"][key] for key in named}
    assert _firm_page(capsys, "overview")["paths"] == {}, "no row of the Overview names a file"
    assert len(reply["files_found"]) == len(whole["files"]), "the search finds every waiting file"


def test_a_turn_with_the_view_reads_no_record_and_takes_no_fingerprint(capsys, demo_root, monkeypatch):
    whole = _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    fresh = _firm_page(capsys, "overview")
    for list_, order, filter in (("overview", {"cell": "end", "dir": -1}, {"tab": "need"}), ("needs_review", {"cell": "end", "dir": -1}, {"reason": ""}),
                                 ("reminders", None, {}), ("clients", None, {"all": True, "type": ""})):
        with monkeypatch.context() as patch:
            _forbid_the_walk(patch)
            turn = _firm_page(capsys, list_, view=fresh["view"], order=order, **filter)
        assert turn["view"] == fresh["view"], "the token stays: it is the same view"
        assert turn["totals"] == whole["totals"] and len(turn["return_counts"]) == len(whole["returns"])
    assert turn["page"]["list"] == "clients" and turn["page"]["total"] > 0
    with monkeypatch.context() as patch:
        _forbid_the_walk(patch)
        assert _firm_page(capsys, "overview", view=fresh["view"])["page"]["rows"] == fresh["page"]["rows"]


def test_a_turn_with_a_stale_view_answers_fresh_with_a_new_view(capsys, demo_root, monkeypatch):
    from tracker import firm_cache, firm_pages

    _a_practice_for_the_firm_view(capsys, demo_root)
    first = _firm_page(capsys)
    second = _firm_page(capsys)
    assert first["view"] != second["view"], "every fresh ask saves a view of its own"
    turned = _firm_page(capsys, view=first["view"])
    assert turned["view"] not in (first["view"], second["view"]), "another fresh firm replaced the first view: this is a new one"
    assert turned["page"]["rows"] == second["page"]["rows"]
    assert _firm_page(capsys, view=turned["view"])["view"] == turned["view"], "and it is the one saved now"
    # The program changed under the window: its token is not honoured.
    with monkeypatch.context() as patch:
        patch.setattr(firm_cache, "program_stamp", lambda: "a program that came after")
        after = _firm_page(capsys, view=turned["view"])
    assert after["view"] != turned["view"]
    # The file gone, or damaged.
    firm_pages.pages_path().unlink()
    gone = _firm_page(capsys, view=after["view"])
    assert gone["view"] not in (after["view"], None) and firm_pages.pages_path().is_file()
    firm_pages.pages_path().write_text("{ damaged", encoding="utf-8")
    ruined = _firm_page(capsys, view=gone["view"])
    assert ruined["view"] != gone["view"] and ruined["page"]["rows"] == second["page"]["rows"]
    # A new token for no view at all is a fresh read, as the launch's is.
    assert _firm_page(capsys)["view"] != ruined["view"]


def test_the_pages_of_one_view_together_are_the_whole_ordered_list(capsys, demo_root, monkeypatch):
    from tracker import firm_pages

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    everything = {"overview": {"tab": "all"}, "clients": {"all": True, "type": ""}, "reminders": {}, "needs_review": {"reason": ""}}
    for list_, filter in everything.items():
        for order in (None, {"cell": {"overview": "taxpayer", "clients": "name", "reminders": "taxpayer", "needs_review": "name"}[list_], "dir": -1}):
            whole_page = _firm_page(capsys, list_, order=order, **filter)["page"]
            monkeypatch.setattr(firm_pages, "PAGE_SIZE", 2)
            seen, view, at = [], None, 0
            while True:
                reply = _firm_page(capsys, list_, at=at, order=order, view=view, **filter)
                view = view or reply["view"]
                assert reply["view"] == view, "every page of the list is from the one view"
                seen += reply["page"]["rows"]
                at += 1
                if at >= reply["page"]["pages"]:
                    break
            monkeypatch.setattr(firm_pages, "PAGE_SIZE", 50)
            assert seen == whole_page["rows"], (list_, order)
            assert reply["page"]["total"] == whole_page["total"]


def test_firm_last_pages_its_reply_and_names_no_view(capsys, demo_root, monkeypatch):
    from tracker import firm_pages

    whole = _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    firm_pages.pages_path().unlink(missing_ok=True)
    code, last = run(capsys, "firm-last", stdin=_a_page("overview"))
    assert code == 0 and last["last"] is True and re.fullmatch(r"\d{2}:\d{2}", last["as_of"])
    assert last["view"] is None and "returns" not in last and "files" not in last
    fresh = _firm_page(capsys, "overview")
    assert last["page"] == fresh["page"] and last["totals"] == whole["totals"] and last["return_counts"] == fresh["return_counts"]
    firm_pages.pages_path().unlink()
    assert run(capsys, "firm-last", stdin=_a_page("overview"))[1]["last"] is True
    assert not firm_pages.pages_path().exists(), "firm-last saves nothing (P229)"
    assert run(capsys, "firm-last")[1]["returns"] == whole["returns"], "asked for no page it answers the whole reply"


def test_the_firm_page_size_is_fifty():
    from tracker import firm_pages

    assert firm_pages.PAGE_SIZE == 50


def test_an_ask_the_engine_does_not_have_is_refused_by_the_one_sentence_and_nothing_is_read(capsys, demo_root, monkeypatch):
    _a_practice_for_the_firm_view(capsys, demo_root)
    assert api.FIRM_PAGE_REFUSED == "The app asked for a list the engine does not have; nothing was read."
    _forbid_the_walk(monkeypatch)
    for spec in ({"page": {"list": "payroll"}}, {"page": {"list": "overview", "order": {"cell": "bogus", "dir": 1}}},
                 {"page": {"list": "overview", "at": -1}}, {"page": {"list": "clients", "filter": {"type": "dentists"}}}, {"unknown": True}):
        for command in ("firm", "firm-last"):
            code, reply = run(capsys, command, stdin=spec)
            assert code == 1 and reply["error"] == api.FIRM_PAGE_REFUSED and reply["failure"]["kind"] == "refused", (command, spec)


def test_the_page_refusal_alone_carries_the_mark_firm_page_refused(capsys, demo_root, monkeypatch):
    """P278: the window drops Retry on the page refusal only, so the engine marks that
    envelope itself (``key``), beside the fields every envelope keeps; a page ask refused
    for another reason - a clients folder that cannot be walked just now - is unmarked."""
    from tracker.registry import RegistryError

    _a_practice_for_the_firm_view(capsys, demo_root)
    assert api.FIRM_PAGE_REFUSED_KEY == "firm_page_refused"
    for command in ("firm", "firm-last"):
        code, reply = run(capsys, command, stdin={"page": {"list": "payroll"}})
        assert code == 1 and reply["failure"] == {"sentence": api.FIRM_PAGE_REFUSED, "kind": "refused", "seq": None,
                                                  "identifier": None, "key": "firm_page_refused"}, command

    def cannot_walk(root):
        raise RegistryError("made up")

    monkeypatch.setattr(api, "_firm_cached", lambda root, today: None)
    monkeypatch.setattr(api, "discover_engagements", cannot_walk)
    code, reply = run(capsys, "firm", stdin=_a_page("overview"))
    assert code == 1 and reply["failure"]["kind"] == "refused" and reply["error"] == screen_words.PRACTICE_NOT_WALKED
    assert "key" not in reply["failure"], "only the page refusal is marked: this one keeps Retry"


def test_a_view_that_cannot_be_saved_answers_the_page_without_a_token_and_the_next_turn_reads_fresh(capsys, demo_root, monkeypatch):
    from tracker import firm_pages

    _a_practice_for_the_firm_view(capsys, demo_root)
    with monkeypatch.context() as patch:
        def refuses(path, text):
            raise PermissionError("made up")

        patch.setattr(firm_pages, "write_text_atomically", refuses)
        unsaved = _firm_page(capsys)
    assert unsaved["view"] is None and unsaved["page"]["rows"]
    next_turn = _firm_page(capsys, view=None)
    assert next_turn["view"] and next_turn["page"] == unsaved["page"]


def test_the_firm_words_are_the_vocabulary_the_window_reads():
    """The keys' words are handed in from the same sources ``vocab()`` serves, never typed twice."""
    vocab = api.vocab()
    words = api._firm_words()
    counts = vocab["screen"]["counts"]
    assert (words["need"], words["waiting"], words["complete"]) == (counts["need"], counts["waiting"], counts["complete"])
    assert words["paused"] == vocab["screen"]["notices"]["paused"] and words["held"] == vocab["screen"]["held"]
    assert words["stages"] == {one["number"]: one["short"] for one in vocab["reminder"]["stages"]}
    assert words["reasons"] == vocab["reasons"] and words["client_types"] == vocab["client_type_forms"]


def test_the_walk_the_pages_are_cut_from_is_the_same_from_the_cache_and_from_the_whole_walk(capsys, demo_root, monkeypatch):
    """The names a page orders by (each return's name, each household's links and
    forms) come from the kept facts when the cache answers: they equal the whole
    walk's, and the facts kept hold the return's name and its recorded form."""
    from tracker import firm_cache

    _a_practice_kept_whole(capsys, demo_root, monkeypatch)
    root, today = api._saved_root(), dt.date.today()
    cached = firm_view._firm_from_cache(root, today)
    fresh = api._firm_fresh(root, today)
    assert cached[1]["returns"] == fresh[1]["returns"] and cached[1]["returns"]
    ordered = lambda walk: sorted(walk["households"], key=lambda one: one["path"])      # noqa: E731
    assert ordered(cached[1]) == ordered(fresh[1])
    assert all(one["name"] and one["path"] and isinstance(one["forms"], list) for one in cached[1]["households"])
    kept = firm_cache.load(firm_cache.cache_path(), firm_cache.head(str(root), today))
    facts = [fact for entry in kept.values() for fact in entry["returns"]]
    assert facts and all(isinstance(fact["return_name"], str) and fact["return_name"] and "form" in fact for fact in facts)


@pytest.mark.parametrize("list_,filter,damage", [
    ("overview", {"tab": "all"}, "returns"), ("needs_review", {"reason": ""}, "returns"), ("needs_review", {"reason": ""}, "files"),
    ("reminders", {}, "returns"), ("clients", {"all": True, "type": ""}, "returns")])
def test_a_view_damaged_into_other_valid_json_is_said_by_its_class_and_the_ask_is_answered_fresh(
        capsys, demo_root, caplog, list_, filter, damage):
    """SPEC 4.7: a view that cannot be read is answered fresh (slower, never wrong). A view whose
    file is still whole JSON but whose entries are damaged cannot be paged: it is no view - said on
    the error log by its class, as a damaged cache is (P120) - and the ask is answered by a new walk
    under a new token, never a failed turn that Retry would repeat."""
    import logging

    from tracker import firm_pages

    _a_practice_for_the_firm_view(capsys, demo_root)
    fresh = _firm_page(capsys, list_, **filter)
    kept = json.loads(firm_pages.pages_path().read_text(encoding="utf-8"))
    kept["reply"][damage] = kept["reply"][damage][:1] + [7]
    firm_pages.pages_path().write_text(json.dumps(kept), encoding="utf-8")
    with caplog.at_level(logging.WARNING):
        turned = _firm_page(capsys, list_, view=fresh["view"], **filter)
    assert turned["view"] not in (None, fresh["view"]), "a new walk, a new token"
    assert turned["page"]["rows"] == fresh["page"]["rows"] and turned["totals"] == fresh["totals"]
    said = [record.getMessage() for record in caplog.records if "could not be paged" in record.getMessage()]
    assert said and "TypeError" in said[0], "said by its class"
    assert not any(name in said[0] for name in ("Mixed", "Quiet", "Retired", "setup.exe")), "never a client's words"
    assert _firm_page(capsys, list_, view=turned["view"], **filter)["view"] == turned["view"], "and the new view is the one saved"
