"""Tests for tracker/copies.py - how the sorter names, measures, copies and moves a file.

The promises being tested: a working copy's name is the request's
identifier, short name and period, cut to the room its folder leaves and
never past it, and every other name the sorter gives comes from one
numbering function that never hands out a name a row still names; the room a
return has is measured from its request list alone, and creation and the
rollover refuse a return whose deepest copy would not fit, in Windows's
numbers on a Mac too; a review copy is never named for a program and is cut
to fit or refused as a review copy; a copy is proved against the bytes the
record holds and says its names as the record keeps them; a move whose
source is now behind a link moves nothing; and the sweep at the start of a
household pass takes only the tracker's own temps, never through a junction,
and counts what it cannot take without naming it.

These tests came from ``tests/test_filer.py`` with the code they drive
(SPEC-architecture-p4 P4.4, P331): each one whose only homes, by section
4.1's rule, are in ``tracker/copies.py``, cut and pasted with its name. The
helpers they share with the filer's tests are ``tests/filer_helpers.py``'s.
Many still drive the code through a pass, as they did; the claim each makes
is about the code here.
"""

import os
import sys
from dataclasses import replace
from pathlib import Path

import pytest

from tests.builders import (
    DAY1,
    ITEMS,
    OVER,
    ROOM_ITEMS,
    drop,
    engagement_fixture,
    link_to,
    make_engagement,
    sort,
    tight_return,
)
from tests.filer_helpers import (
    A_CLIENT_PATH,
    _catalog_w2,
    _logged_outside_the_debug_log,
    _refused_with_a_client_path,
    originals,
    prepared,
    review_dir,
)
from tracker.copies import (
    FilingError,
    prepared_name_for,
)
from tracker.layout import household_of, inbox_of, locate
from tracker.manifest import (
    RequestItem,
    load_manifest,
)
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    README_NAME,
    REVIEW_DIR_NAME,
)

engagement = engagement_fixture(ITEMS)


def test_prepared_name_for_collides_safely():
    item = ITEMS[0]
    taken: set[str] = set()
    first = prepared_name_for(item, "pdf", taken)
    second = prepared_name_for(item, "pdf", taken)
    assert first == "A01 - W-2 Wage Statements - TY2025.pdf"
    assert second == "A01 - W-2 Wage Statements - TY2025 (2).pdf"


def test_the_trackers_own_temp_files_are_swept_and_nothing_else(engagement):
    """Decision 155, A-F6. A killed write leaves its temp for ever - one in
    the client's own Drop folder, counted as "syncing" every pass. The
    household pass takes away the tracker's own temps and nothing else: the
    exact shape (``fsio.TEMP_NAME``), older than the pass, left by a
    process that is gone, and only in the return's folder, the household's
    ``_Opened``, or beside the README. A client's file is never touched,
    whatever it is called, and nothing in the year's folder, where the
    originals rest, is ever looked at."""
    import subprocess
    import time

    from tracker.copies import sweep_stranded_temps
    from tracker.layout import opened_dir_of

    pid = os.getpid()
    ours = [
        prepared(engagement, "A01") / f"A01 - W-2 Wage Statements - TY2025.pdf.{pid}.0a1b2c3d.tmp",
        review_dir(engagement) / f"scan.pdf.{pid}.1b2c3d4e.tmp",
        engagement / f"Status Report.html.{pid}.2c3d4e5f.tmp",
        opened_dir_of(engagement) / "statement" / f"page.pdf.{pid}.3d4e5f6a.tmp",
        inbox_of(engagement) / f"{README_NAME}.{pid}.4e5f6a7b.tmp",
    ]
    theirs = [
        inbox_of(engagement) / "W-2 scan.pdf.tmp",                          # a client's .tmp
        inbox_of(engagement) / f"photo.jpg.{pid}.5f6a7b8c.tmp",             # the shape, not the README's
        inbox_of(engagement) / f"{README_NAME.upper()}.{pid}.6a7b8c9d.tmp",  # not the README's name
        originals(engagement) / f"W2.pdf.{pid}.7b8c9d0e.tmp",               # the year's folder: never
        prepared(engagement, "A01") / "notes.tmp",                          # not the shape
        prepared(engagement, "A01") / f"x.pdf.{pid}.8C9D0E1F.tmp",          # not the shape (case)
        prepared(engagement, "A01") / f"x.pdf.{pid}.8c9d0e.tmp",            # not the shape (length)
    ]
    for path in [*ours, *theirs]:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(b"half")
    # The README's own temp holds the README's text: in the client's inbox a
    # name is not enough to make a file ours (decision 190).
    from tracker.scaffold import README_FIRST_LINE
    ours[-1].write_bytes(README_FIRST_LINE.encode("ascii") + b"\r\nhalf")

    # A temp that came to be after the pass started, and one whose writer is
    # still running, are somebody's write in progress: left.
    started = time.time() - 60
    with subprocess.Popen([sys.executable, "-c", "import time; time.sleep(60)"]) as live:
        try:
            alive = engagement / f"view.html.{live.pid}.9d0e1f2a.tmp"
            alive.write_bytes(b"being written")
            assert sweep_stranded_temps(household_of(engagement), [engagement],
                                        started=started) == []
            assert all(path.exists() for path in [*ours, *theirs, alive])
            taken = sweep_stranded_temps(household_of(engagement), [engagement],
                                         started=time.time() + 1)
            assert sorted(map(str, taken)) == sorted(map(str, ours))
            assert alive.exists()
        finally:
            live.kill()

    assert not any(path.exists() for path in ours)
    assert all(path.read_bytes() == b"half" for path in theirs)


@pytest.mark.skipif(sys.platform != "win32", reason="junctions are Windows'")
def test_the_sweep_never_walks_through_a_junction(engagement, tmp_path):
    """Decision 155's review, FIX 1. A junction under a return's folder or
    under ``_Opened`` points anywhere - at a client's folder, at another
    household's - and a temp-shaped file behind it is not this household's
    to take. The walk asks the one link test the package has
    (``fsio.is_link``, read from the reparse tag), which every supported
    Python answers: ``DirEntry.is_junction()`` does not exist on 3.11."""
    import _winapi
    import time

    from tracker.copies import sweep_stranded_temps
    from tracker.fsio import is_link
    from tracker.layout import opened_dir_of

    elsewhere = tmp_path / "elsewhere"
    elsewhere.mkdir()
    behind = elsewhere / f"statement.pdf.{os.getpid()}.0a1b2c3d.tmp"
    behind.write_bytes(b"somebody else's")
    opened_dir_of(engagement).mkdir(parents=True, exist_ok=True)
    links = [prepared(engagement, "A01") / "linked", opened_dir_of(engagement) / "linked"]
    for link in links:
        _winapi.CreateJunction(str(elsewhere), str(link))
    try:
        assert all(is_link(link) for link in links)
        taken = sweep_stranded_temps(household_of(engagement), [engagement],
                                     started=time.time() + 1)
        assert taken == [] and behind.read_bytes() == b"somebody else's"
    finally:
        for link in links:
            os.rmdir(link)


def test_the_room_is_measured_from_the_list_alone_and_creations_figure_is_unchanged(tmp_path, path_setting):
    """``room_for`` reads no disk: a return folder that does not exist is
    measured as readily as one that does. Its ``need`` is creation's figure
    exactly - the deepest canonical copy: 138 for the example row, 138 for
    the whole 1040 core list at its longest extension, 215 for a row whose
    name is a hundred characters - each copy in Prepared itself (decision
    168; 164, 163 and 316 while each request had a folder, 223 for the core
    list with the full titles before decision 144)."""
    from tracker.copies import Room, room_for, shortest_name_for
    from tracker.layout import (
        deepest_path_length,
        folder_need,
        limit_for,
        path_limit,
        return_dir_for,
        short_paths,
    )
    from tracker.templates import template_items

    root = Path("G:/Shared drives/JPA Clients")
    engagement = return_dir_for(root, "Park Family", 2026, "1040 - John & Maria Park")
    assert not engagement.exists()

    w2 = replace(ITEMS[0], period="TY2026", expected_count=1)
    room = room_for(engagement, [w2])
    assert room.need == 138 and room.limit == path_limit() and room.short == 0
    # The shortest name: the identifier, the period, a two-digit suffix, the extension.
    assert shortest_name_for(w2, "pdf") == "A01 - TY2026 (99).pdf"
    assert room.least == len(str(engagement / PREPARED_DIR_NAME / "A01 - TY2026 (99).pdf"))
    # With long paths off the review folder is measured as Windows measures
    # a folder the tracker makes and writes into, its temp names included:
    # fifteen deeper than ``x (99).pdf`` (pilot decision P29).
    floor = len(str(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "x (99).pdf"))
    assert room.floor == max(floor, folder_need(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME, root))
    assert room.floor == (143 if short_paths() else 128)
    assert room.parks == 0

    core = [replace(item, allowed_extensions=("xlsx",))
            for item in template_items("1040", core_only=True)]
    subpaths = [f"{PREPARED_DIR_NAME}/{prepared_name_for(item, 'xlsx', set())}" for item in core]
    assert room_for(engagement, core).need == deepest_path_length(engagement, subpaths) == 138
    # Every copy is a workbook, and a workbook's reader allows 218: with the
    # short names every one fits (it was five short with the full titles).
    assert limit_for("xlsx") == 218
    assert room_for(engagement, core).short == 0

    # A name of a hundred characters: no short title typed in the editor may
    # be one (it is refused past twenty), but the measure is arithmetic on
    # whatever name a row carries, and is held to it here.
    long_row = replace(template_items("1040", core_only=True)[0], document="x" * 100,
                       short_title="x" * 100, allowed_extensions=("xlsx",))
    long = room_for(engagement, [long_row])
    # With no folder named after the hundred characters too, the name is in
    # the path once, capped: it fits even a workbook's reader, where it was
    # 98 characters short and a workbook parked.
    assert long.need == 215 and long.short == 0
    assert long.least == len(str(engagement / PREPARED_DIR_NAME / "A01 - TY2026 (99).xlsx"))
    assert long.parks == 0

    # A row set aside is not measured, as creation does not measure it.
    from tracker.manifest import Override

    aside = replace(long_row, manual_override=Override.NOT_APPLICABLE)
    nothing = max(len(str(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME / "x (99).xlsx")),
                  folder_need(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME, root))
    assert room_for(engagement, [aside]) == Room(need=0, least=0, floor=nothing, parks=0, short=0,
                                                 limit=path_limit())


def test_a_working_copy_is_named_to_fit_the_room_left_under_its_folder(tmp_path, path_setting):
    """A root long enough that the canonical name does not fit: the pass
    files all the same, under a name that keeps the identifier, the period
    and the extension and loses the tail of the document label. The row
    names the copy on disk, the scan proves it, and the next pass's reuse
    check finds it."""
    from tracker.filer import _existing_copy
    from tracker.layout import path_limit
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement
    from tracker.validators import sha256_of

    engagement = tight_return(tmp_path, OVER)
    drop(engagement, "w2.pdf", "Form W-2 Wage and Tax Statement 2025")

    report = sort(engagement, today=DAY1)

    [entry] = report.filed
    folder = prepared(engagement, "A01")
    [copy] = list(folder.iterdir())
    assert copy.name == "A01 - W-2 Wage S - Jan 2025 to Dec 2025.pdf"           # "tatements" cut
    assert len(str(copy)) == path_limit()
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/{copy.name}"
    assert locate(engagement, entry.prepared_location) == copy

    scan_engagement(engagement, today=DAY1)
    assert load_manifest(engagement)[0].status == Status.RECEIVED

    original = originals(engagement) / "w2.pdf"
    assert _existing_copy(copy.parent, original, sha256_of(original)) == copy


def test_creation_and_the_rollover_still_refuse_the_canonical_name_past_the_limit(tmp_path, path_setting):
    """Creation's and the rollover's refusal are unchanged: the canonical
    name at each row's longest extension, against Windows's 260 (259 with
    long paths off) - not a reader's 218, which only cuts a name - with
    decision 125's words."""
    from tracker.copies import refuse_a_path_past_the_limit
    from tracker.layout import PATH_TOO_LONG, path_limit, return_dir_for
    from tracker.manifest import ManifestError
    from tracker.templates import template_items

    # A household name fifty characters longer than the example's: the
    # core list still fits (138 at the example's, 188 here), and a row named
    # by a hundred characters - 215 at the example's since decision 168 -
    # is past the limit (the measure is arithmetic on the name the row
    # carries; a typed short title is refused past twenty).
    root = Path("G:/Shared drives/JPA Clients")
    engagement = return_dir_for(root, "Park Family " + "p" * 49, 2026, "1040 - John & Maria Park")
    core = [replace(item, allowed_extensions=("xlsx",))
            for item in template_items("1040", core_only=True)]
    refuse_a_path_past_the_limit(engagement, core)          # 188 - accepted

    long_row = replace(core[0], document="x" * 100, short_title="x" * 100)
    with pytest.raises(ManifestError) as refused:
        refuse_a_path_past_the_limit(engagement, [long_row])
    assert str(refused.value) == PATH_TOO_LONG.format(folder=engagement, length=265, limit=path_limit())


def test_a_return_that_fits_on_windows_fits_on_a_mac_and_one_character_more_does_not(on_a_mac):
    """SPEC-mac R9, P241 and P244. A Mac measures a return against the
    259 a default Windows opens, as if the folder sat under a Windows root
    of 48 characters: the household name that makes the deepest working
    copy exactly 259 characters there is accepted, and one character more
    is refused in Windows's numbers - whatever the Mac's own root."""
    from pathlib import PureWindowsPath

    from tracker.copies import refuse_a_path_past_the_limit, room_for
    from tracker.layout import (
        PATH_TOO_LONG,
        PREPARED_DIR_NAME,
        REVIEW_DIR_NAME,
        folder_need,
        path_limit,
        return_dir_for,
    )
    from tracker.manifest import ManifestError

    root = Path("/Users/jpark/Library/CloudStorage/GoogleDrive-jpark@jparkassociates.com"
                "/Shared drives/JPA Clients")

    def the_need_of(extra: int) -> tuple[Path, int]:
        """The return with ``extra`` more characters in its names (a
        household and a return name each take at most 80)."""
        in_the_household = min(extra, 60)
        engagement = return_dir_for(root, "Park Family" + "h" * in_the_household, 2026,
                                    "1040 - John & Maria Park" + "q" * (extra - in_the_household))
        review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
        return engagement, max(room_for(engagement, ROOM_ITEMS).need, folder_need(review, root))

    _engagement, base = the_need_of(0)
    assert path_limit() == 259
    extra = path_limit() - base
    engagement, need = the_need_of(extra)
    assert need == 259
    refuse_a_path_past_the_limit(engagement, ROOM_ITEMS)              # fits: accepted

    deepest = engagement / PREPARED_DIR_NAME / prepared_name_for(ROOM_ITEMS[0], "pdf", set())
    windows = PureWindowsPath("G:/Shared drives/" + "x" * 31).joinpath(*deepest.relative_to(root).parts)
    assert len(str(windows)) == room_for(engagement, ROOM_ITEMS).need, "the length it has on Windows"

    longer, need = the_need_of(extra + 1)
    assert need == 260
    with pytest.raises(ManifestError) as refused:
        refuse_a_path_past_the_limit(longer, ROOM_ITEMS)
    assert str(refused.value) == PATH_TOO_LONG.format(folder=longer, length=260, limit=259)
    assert "past the 259 Windows allows" in str(refused.value)


def test_a_mac_cuts_a_working_copys_name_to_the_room_a_windows_desk_leaves(on_a_mac):
    """SPEC-mac R9: the room a name may take in a folder, and the figures a
    refusal quotes, are Windows's - so the name cut on a Mac is the name cut
    under the Windows root (names and parks match on both)."""
    from pathlib import PureWindowsPath

    from tracker.copies import REVIEW_NO_ROOM, NoRoom, _review_copy_path, _room_in, _unique_path

    root = Path("/Users/jpark/Library/CloudStorage/GoogleDrive-a@b.com/Shared drives/JPA Clients")
    folder = root / "J Park & Associates" / "Park Family" / "2026" / "1040 - John Park" / "Prepared"
    windows = PureWindowsPath("G:/Shared drives/" + "x" * 31).joinpath(*folder.relative_to(root).parts)
    assert _room_in(folder, "pdf", root) == 259 - len(str(windows)) - 1
    assert _room_in(folder, "xlsx", root) == 218 - len(str(windows)) - 1

    with pytest.raises(NoRoom) as refused:
        _unique_path(folder, "statement.pdf", room=4, root=root)
    assert str(refused.value) == REVIEW_NO_ROOM.format(
        name="statement.pdf", length=len(str(windows)) + len("/s.pdf"),
        limit=len(str(windows)) + 1 + 4, ext=".pdf")
    long_name = "n" * 300 + ".pdf"
    cut, said = _review_copy_path(folder, long_name, root)
    assert said == "" and cut.name.endswith(".pdf")
    assert len(cut.name) == 259 - len(str(windows)) - 1


def test_a_spreadsheet_limit_is_never_called_what_windows_allows(path_setting):
    """F2: since the owner's Q-A a workbook's limit is a reader's 218, so
    every sentence of decision 131 names the limit as that kind of copy's,
    never as what Windows allows."""
    from tracker.copies import (
        HOUSEHOLD_NO_ROOM,
        PATH_NO_ROOM,
        PATH_NO_ROOM_IN,
        REVIEW_NO_ROOM,
        NoRoom,
    )
    from tracker.layout import path_limit

    for sentence in (PATH_NO_ROOM, PATH_NO_ROOM_IN, HOUSEHOLD_NO_ROOM, REVIEW_NO_ROOM):
        assert "Windows" not in sentence
    workbook = replace(ROOM_ITEMS[0], allowed_extensions=("xlsx",))
    with pytest.raises(NoRoom) as refused:
        prepared_name_for(workbook, "xlsx", set(), room=5)
    said = str(refused.value)
    assert refused.value.limit == 218 and "past the 218 characters a .xlsx copy may have" in said
    assert "Windows" not in said
    with pytest.raises(NoRoom) as refused:
        prepared_name_for(ROOM_ITEMS[0], "pdf", set(), room=5)
    assert f"past the {path_limit()} characters a .pdf copy may have" in str(refused.value)
    with pytest.raises(NoRoom) as refused:
        prepared_name_for(ROOM_ITEMS[0], "", set(), room=5)
    assert "a working copy may have" in str(refused.value)


def test_a_review_copy_with_an_odd_suffix_is_cut_to_fit_or_said_as_a_review_copy(tmp_path, path_setting):
    """F4: the pass's floor proves room for a short extension, not for
    whatever a client's file name ends in. A name whose "suffix" is not an
    extension is cut as one stem to fit; a real extension is kept whole,
    and where not even one character of stem fits beside it the sentence
    says a *review copy* could not be made - never a request's label."""
    from tracker.copies import REVIEW_NO_ROOM, NoRoom, _review_copy_path, _unique_path
    from tracker.layout import path_limit

    folder = tmp_path / "review"
    folder.mkdir()
    odd = "Scan 2026.01.15 from the phone of the client for the W-2"
    cut = _unique_path(folder, odd, room=30, root=tmp_path)
    assert len(cut.name) <= 30 and cut.name.startswith("Scan 2026.01")
    cut.write_text("one")
    again = _unique_path(folder, odd, room=30, root=tmp_path)
    assert again != cut and len(again.name) <= 30 and again.name.endswith("(2)")
    # Through the one function every review copy is named by.
    fitted, said = _review_copy_path(folder, odd * 5, tmp_path)
    assert said == "" and len(str(fitted)) <= path_limit()

    with pytest.raises(NoRoom) as refused:
        _unique_path(folder, "statement.pdf", room=4, root=tmp_path)
    assert str(refused.value) == REVIEW_NO_ROOM.format(
        name="statement.pdf", length=len(str(folder / "s.pdf")), limit=len(str(folder)) + 1 + 4,
        ext=".pdf")
    assert "label" not in str(refused.value)
    # Without a room nothing changes: an original keeps its own name, always.
    assert _unique_path(folder, odd).name == odd


def test_the_period_survives_a_long_label():
    """F6: the cap on a working copy's name cuts the document label, never
    the period - the one part that says which year a copy belongs to."""
    from tracker.copies import _MAX_STEM

    long = RequestItem(identifier="A01", document="X" * 120, short_title="X" * 120, period="TY2026")
    name = prepared_name_for(long, "pdf", set())
    assert name.endswith(" - TY2026.pdf") and len(name) == _MAX_STEM + len(".pdf")
    assert name.startswith("A01 - XXX")
    fitted = prepared_name_for(long, "pdf", set(), room=40)
    assert fitted.endswith(" - TY2026.pdf") and len(fitted) <= 40


def test_a_move_whose_source_is_now_behind_a_link_moves_nothing(engagement, tmp_path, monkeypatch):
    """Decision 137 (L2): the link check is made again immediately before
    the rename. The walk refuses what lies behind a junction, but the move
    comes later; a drop's folder swapped for a junction in between must not
    have the rename fetch a file from wherever the junction points."""
    import tracker.copies as copies
    import tracker.filer as filer

    outside = tmp_path / "outside"
    outside.mkdir()
    (outside / "theirs.pdf").write_bytes(b"%PDF-1.4 somebody else's file")
    inbox = inbox_of(engagement)
    link_to(outside, inbox / "swapped")
    behind = inbox / "swapped" / "theirs.pdf"

    # Directly: the move itself refuses, and says why.
    with pytest.raises(copies.MovedThroughALinkError, match="reached through a link"):
        filer._move_whole(behind, originals(engagement) / "theirs.pdf", within=inbox)
    assert (outside / "theirs.pdf").exists()

    # Through a pass whose listing was made before the swap: left in place.
    monkeypatch.setattr(filer, "iter_drops", lambda folder, **_: [behind])
    report = sort(engagement, today=DAY1)
    assert [e.name for e in report.errors] == ["theirs.pdf"]
    assert report.errors[0].left_in_place and "(MovedThroughALinkError" in report.errors[0].error
    assert (outside / "theirs.pdf").exists()
    assert report.filed == [] and report.review == []


def test_the_working_copy_uses_the_short_title(short_root):
    """Decision 144, claim 2: the owner's example. A W-2 filed on the
    catalog's A01 is ``A01 - W-2 - TY2025.pdf`` - the request's short name
    where the full title "W-2 Wage Statements - All Employers" used to be -
    and since decision 168 it sits in Prepared itself, where 144 put it in
    a folder ``A01 - W-2``."""
    w2 = _catalog_w2(expected_count=1, min_size_kb=0)
    assert w2.short_title == "W-2" and w2.document == "W-2 Wage Statements - All Employers"
    assert prepared_name_for(w2, "pdf", set()) == "A01 - W-2 - TY2025.pdf"

    engagement = make_engagement(short_root, [w2])
    drop(engagement, "scan.pdf", "Form W-2 Wage and Tax Statement 2025 wages, tips, other "
                                 "compensation employee's social security number")
    [entry] = sort(engagement, today=DAY1).filed
    assert entry.prepared_location == f"{PREPARED_DIR_NAME}/A01 - W-2 - TY2025.pdf"
    assert (engagement / PREPARED_DIR_NAME / "A01 - W-2 - TY2025.pdf").is_file()


def test_the_one_numbering_function_takes_a_name_a_row_still_names(tmp_path):
    from tracker.filer import _unique_path

    folder = tmp_path / "2025"
    folder.mkdir()
    gone = folder / "W2.pdf"                                    # a row names it; the file is gone
    assert _unique_path(folder, "W2.pdf", recorded={gone: "a" * 64}, digest="b" * 64).name == "W2 (2).pdf"
    # The row's own bytes are no exception since decision 157: they go home
    # through _put_back_home, which writes no new row, and never here.
    assert _unique_path(folder, "W2.pdf", recorded={gone: "a" * 64}, digest="a" * 64).name == "W2 (2).pdf"
    # A row with no fingerprint is nobody's (decision 65): its name stays taken.
    assert _unique_path(folder, "W2.pdf", recorded={gone: ""}, digest="").name == "W2 (2).pdf"
    # The digest is asked for only when a file on the disk might be reused.
    asked = []
    assert _unique_path(folder, "W2.pdf", recorded={gone: "a" * 64},
                        digest=lambda: asked.append(1) or "a" * 64).name == "W2 (2).pdf"
    assert asked == []


def test_a_copy_already_there_is_reused_only_under_its_own_request(engagement):
    """Every request's copies share Prepared (decision 168), so the check
    for a killed run's copy looks only among the request's own: decision
    94's page filed under A01 and C01 has the same bytes under both names,
    and C01's filing never takes A01's copy for its own."""
    from tests.samples import scanned_1098_lines, scanned_w2_lines
    from tracker.filer import _existing_copy, copies_of
    from tracker.validators import sha256_of

    original = drop(engagement, "scan0003.pdf",
                    "\n".join(scanned_w2_lines(2025) + scanned_1098_lines(2025)))
    (entry,) = sort(engagement, today=DAY1).filed
    a01, c01 = (engagement / location for location in entry.filed_locations)
    kept = originals(engagement) / original.name
    prepared_dir = engagement / PREPARED_DIR_NAME

    c01.unlink()                                      # as if the pass was killed before it
    assert _existing_copy(prepared_dir, kept, sha256_of(kept),
                          among=copies_of(ITEMS[1], ITEMS, prepared_dir)) is None
    assert _existing_copy(prepared_dir, kept, sha256_of(kept),
                          among=copies_of(ITEMS[0], ITEMS, prepared_dir)) == a01


def test_room_is_measured_without_a_request_folder():
    """Claim 9: ``room_for(...).need`` for the 1040 core list under the
    firm's 28-character root is decision 144's figure (163) less the folder
    the deepest copy sat in: 138. The deepest row is still B01, whose
    folder ``B01 - Prior-Year Returns/`` was 25 characters."""
    from tracker.copies import room_for
    from tracker.layout import return_dir_for
    from tracker.manifest import label_for
    from tracker.scaffold import sanitize_component
    from tracker.templates import template_items

    root = Path("G:/Shared drives/JPA Clients")
    engagement = return_dir_for(root, "Park Family", 2026, "1040 - John & Maria Park")
    core = [replace(item, allowed_extensions=("xlsx",))
            for item in template_items("1040", core_only=True)]

    def with_a_folder(item):
        folder = label_for(sanitize_component(item.identifier), sanitize_component(item.short_name))
        return len(str(engagement / PREPARED_DIR_NAME / folder / prepared_name_for(item, "xlsx", set())))

    deepest = max(core, key=with_a_folder)
    folder = label_for(deepest.identifier, deepest.short_name) + "/"
    assert with_a_folder(deepest) == 163                        # decision 144's figure
    assert room_for(engagement, core).need == 163 - len(folder) == 138
    assert folder == "B01 - Prior-Year Returns/"


def test_an_unproved_copy_says_its_names_as_the_record_keeps_them(engagement):
    """COPY_UNPROVED names the files the way COPY_MISMATCH two lines below
    it does, through layout.recorded_name: a bidi override or a control
    character in a client's file name never reaches the sentence (decision
    190, the review's N2). Fabricated name. Windows refuses a control
    character in a file name, so there the name carries only the bidi
    override (which Windows accepts); elsewhere it carries both."""
    from tracker.copies import COPY_UNPROVED, _copy_whole

    control = "" if sys.platform == "win32" else "\x07"
    original = originals(engagement) / f"w2\u202efdp{control}.pdf"
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"%PDF-1.4 a fabricated W-2")
    target = engagement / PREPARED_DIR_NAME / "new" / "w2.pdf"

    with pytest.raises(FilingError) as refused:
        _copy_whole(original, target, expect="", root=engagement.parents[3])
    said = refused.value.args[0]
    assert said == COPY_UNPROVED.format(source="w2fdp.pdf", target="w2.pdf"), said
    assert "\u202e" not in said and "\x07" not in said


def test_a_sweep_that_cannot_read_a_returns_rows_logs_the_class_never_the_path(engagement, monkeypatch, caplog):
    """A return whose rows cannot be read is not swept, and the warning that
    says so names the error by its class, never a message carrying a
    client's folder (decision 190, the review's S1)."""
    import logging
    import time

    import tracker.copies as copies
    import tracker.filer as filer
    import tracker.intents as intents

    for module in (filer, copies, intents):
        monkeypatch.setattr(module, "read_index", _refused_with_a_client_path)
    with caplog.at_level(logging.DEBUG):
        assert copies.sweep_stranded_temps(household_of(engagement), [engagement],
                                           started=time.time() + 1) == []
    logged = _logged_outside_the_debug_log(caplog)
    assert "PermissionError (EACCES)" in logged, logged
    assert A_CLIENT_PATH not in logged and "Test Household/Drop" not in logged, logged


def test_no_review_copy_is_ever_named_for_a_program(tmp_path):
    """The review's M1, in depth: the one function that names a review copy
    refuses a program - whatever road asked, and whatever the row says -
    loudly, as a FilingError naming it."""
    from tracker.copies import REVIEW_OF_A_PROGRAM, _review_copy_path

    with pytest.raises(FilingError) as refused:
        _review_copy_path(tmp_path, "Pay.scr\ufeff", tmp_path)
    assert str(refused.value) == REVIEW_OF_A_PROGRAM.format(name="Pay.scr")
    assert list(tmp_path.iterdir()) == []


def test_a_temp_that_cannot_be_swept_is_counted_not_named(engagement, monkeypatch):
    import os
    import time
    from pathlib import Path

    import tracker.copies as copies_module
    from tracker.copies import TEMPS_NOT_SWEPT, sweep_stranded_temps

    stuck = engagement / f"view.html.{os.getpid()}.1a2b3c4d.tmp"
    stuck.write_bytes(b"half")
    real = Path.unlink

    def refused(self, *args, **kwargs):
        if self == stuck:
            raise PermissionError(13, "a fabricated denial", str(self))
        return real(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", refused)
    monkeypatch.setattr(copies_module, "make_writable", lambda path: None)
    said: list[str] = []
    assert sweep_stranded_temps(household_of(engagement), [engagement],
                                started=time.time() + 1, said=said) == []
    assert said == [TEMPS_NOT_SWEPT.format(n=1)]
    assert stuck.name not in said[0] and "fabricated" not in said[0]
