"""Tests for tracker/scaffold.py — folder scaffolding, no OneDrive needed."""

import pytest

from tests.conftest import TEST_HOUSEHOLD, TEST_RETURN, TEST_YEAR, make_engagement
from tracker.filer import refresh_household_readme
from tracker.layout import household_of, inbox_of, originals_of
from tracker.manifest import EXPECTED_PATTERN, ManifestError, Override, RequestItem
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    README_HEADING,
    README_NAME,
    README_PHOTO_LINE,
    README_STEP_2,
    REVIEW_DIR_NAME,
    assign_folders,
    folder_name_for,
    matches_identifier,
    sanitize_component,
    scaffold_engagement,
)

ITEMS = [
    RequestItem(identifier="A01", document="Dec 2025 Bank Statement", period="Dec 2025"),
    RequestItem(
        identifier="A02",
        document="Monthly Bank Statements FY2025",
        period="FY2025",
        expected_count=12,
    ),
    RequestItem(
        identifier="B01",
        document='Q4: A/R "Aging" <Final>?',  # illegal chars everywhere
    ),
    RequestItem(
        identifier="C01",
        document="Fixed Asset Register.",  # trailing dot is illegal on Windows
        manual_override=Override.NOT_APPLICABLE,
    ),
]


@pytest.fixture
def engagement(tmp_path):
    return make_engagement(tmp_path, ITEMS, scaffold=False)


def readme_of(engagement) -> str:
    """The household's README as its one composer writes it (decision 130):
    what the pass and every app action call after a change."""
    written = refresh_household_readme(household_of(engagement))
    assert written is not None
    return written.read_text(encoding="utf-8")


# ------------------------------------------------------------ name rules ----


def test_sanitize_component():
    assert sanitize_component('Q4: A/R "Aging" <Final>?') == 'Q4- A-R -Aging- -Final--'
    assert sanitize_component("Fixed Asset Register.") == "Fixed Asset Register"
    assert sanitize_component("  spaced   out  ") == "spaced out"
    assert sanitize_component("12/31/2025") == "12-31-2025"


def test_folder_names_are_windows_safe():
    for item in ITEMS:
        name = folder_name_for(item)
        assert not set('\\/:*?"<>|') & set(name)
        assert not name.endswith((".", " "))
        assert name.startswith(f"{item.identifier} - ")


def test_matches_identifier_boundaries():
    assert matches_identifier("A01 - Dec 2025 Bank Statement", "A01")
    assert matches_identifier("a01 - renamed by client", "A01")  # case-insensitive
    assert matches_identifier("A01-whatever", "A01")
    assert matches_identifier("A01", "A01")
    assert not matches_identifier("A10 - Something", "A1")   # boundary: '0' is alnum
    assert not matches_identifier("A012", "A01")
    assert not matches_identifier("XA01 - Nope", "A01")
    assert not matches_identifier("A01x", "A01")


def test_assign_folders_longest_identifier_wins(tmp_path):
    (tmp_path / "A01 - Bank").mkdir()
    (tmp_path / "A01-B - Loan Docs").mkdir()
    assigned = assign_folders(tmp_path, ["A01", "A01-B"])
    assert [p.name for p in assigned["A01"]] == ["A01 - Bank"]
    assert [p.name for p in assigned["A01-B"]] == ["A01-B - Loan Docs"]


# -------------------------------------------------------------- scaffold ----


def test_the_scaffold_makes_both_trees_and_the_readme_in_the_inbox_is_grouped_by_return(engagement):
    from tracker.scaffold import write_readme

    result = scaffold_engagement(engagement)
    inbox = inbox_of(engagement)
    originals = originals_of(engagement)
    prepared = engagement / PREPARED_DIR_NAME

    # Client side, in the tree a client is shared: one inbox to drop into
    # and the year's folder their originals rest in. Nothing of the firm's.
    assert inbox.is_dir() and inbox.name == "Drop files here"
    assert originals.is_dir() and originals.name == str(TEST_YEAR)
    assert inbox.parent == originals.parent
    assert result.inbox == inbox and result.originals_dir == originals
    assert not any(p.is_dir() for p in inbox.iterdir())
    # Firm side: one folder per request, plus somewhere for the unclear.
    assert (prepared / REVIEW_DIR_NAME).is_dir()
    assert [p.name for p in result.created] == [
        "A01 - Dec 2025 Bank Statement",
        "A02 - Monthly Bank Statements FY2025",
        "B01 - Q4- A-R -Aging- -Final--",
    ]
    assert result.not_applicable == ["C01"]
    assert not (prepared / "C01 - Fixed Asset Register").exists()

    readme = write_readme(household_of(engagement), contact="J Park & Associates"
                          ).read_text(encoding="utf-8")
    assert f"Household: {TEST_HOUSEHOLD}" in readme
    assert TEST_RETURN in readme                  # one sub-heading per return
    assert "  A01 - Dec 2025 Bank Statement" in readme     # its rows, indented under it
    assert f"[{EXPECTED_PATTERN.format(n=12)}]" in readme
    assert "C01" not in readme                    # set-aside items dropped
    assert "J Park & Associates" in readme
    assert "Google Docs" in readme                # export-first guidance


def test_the_readme_names_the_household_contact(tmp_path):
    engagement = make_engagement(tmp_path, ITEMS, contact="Maria Park")
    readme = readme_of(engagement)
    assert README_STEP_2 in readme
    assert "Questions? Contact Maria Park." in readme


def test_step_2_reads_jasons_sentence_and_the_old_wording_is_gone(tmp_path):
    """Decision 130, D-b: step 2 is exactly the owner's sentence - no
    timing clause, and none of the two lines that used to follow it."""
    readme = readme_of(make_engagement(tmp_path, ITEMS, contact="Maria Park"))

    assert README_STEP_2 in readme
    assert README_STEP_2 == ("2. We will examine and place all documents into the current year's\n"
                             "   folder.")
    assert "next scheduled pass" not in readme
    assert "That is us filing it" not in readme
    assert "renamed or deleted" not in readme
    lines = readme.splitlines()
    step_2 = lines.index(README_STEP_2.split("\n")[0])
    assert lines[step_2 + 2].startswith("3. ")                 # nothing more in step 2


def test_step_4_reads_jasons_sentence_and_the_three_dropped_phrases_are_gone(tmp_path):
    """Decision 130, D-c: the three photo phrases are dropped; decision
    128's two lines on the name stay, and stay in step 4."""
    readme = readme_of(make_engagement(tmp_path, ITEMS, contact="Maria Park"))

    assert README_PHOTO_LINE == (
        "4. Original PDFs or Excel files are preferred. A clear photo from your\n"
        "   phone is fine too, just get the whole page in the frame.")
    for dropped in ("one document per photo", "straight on", "in good light"):
        assert dropped not in readme
    name_lines = ("   Statements and reports should show the name they were issued\n"
                  "   to - please send the whole page, with its header.")
    assert README_PHOTO_LINE + "\n" + name_lines + "\n5. " in readme


def test_the_readme_says_a_clear_photo_is_fine_in_the_owners_words(tmp_path):
    """Decision 127, the owner's sign-off item. Until it landed the README
    told the client "scans and photos are fine as long as they are
    readable" while every request refused an image, so the one sentence
    the client actually read was the one thing the software would not do.
    The step is a constant because a promise made to a client belongs
    where a test can hold the code to it - and the promise is now true."""
    readme = readme_of(make_engagement(tmp_path, ITEMS, contact="Maria Park"))

    assert README_PHOTO_LINE in readme
    assert "A clear photo from your" in README_PHOTO_LINE
    assert "the whole page in the" in README_PHOTO_LINE
    assert "as long as they are readable" not in readme      # the old promise is gone
    assert README_PHOTO_LINE.startswith("4. ")               # still step 4


def test_idempotent_rerun_creates_nothing(engagement):
    scaffold_engagement(engagement)
    result = scaffold_engagement(engagement)
    assert result.created == []
    assert sorted(result.existing) == ["A01", "A02", "B01"]


def test_recreates_deleted_folder(engagement):
    scaffold_engagement(engagement)
    (engagement / PREPARED_DIR_NAME / "A01 - Dec 2025 Bank Statement").rmdir()
    result = scaffold_engagement(engagement)
    assert [p.name for p in result.created] == ["A01 - Dec 2025 Bank Statement"]


def test_client_rename_with_prefix_not_duplicated(engagement):
    scaffold_engagement(engagement)
    prepared = engagement / PREPARED_DIR_NAME
    (prepared / "A01 - Dec 2025 Bank Statement").rename(prepared / "A01 - bank stuff")

    result = scaffold_engagement(engagement)
    assert result.created == []
    assert "A01" in result.existing
    assert sum(1 for p in prepared.iterdir() if p.name.startswith("A01")) == 1


def test_existing_client_files_never_touched(engagement):
    scaffold_engagement(engagement)
    folder = engagement / PREPARED_DIR_NAME / "A01 - Dec 2025 Bank Statement"
    client_file = folder / "chase_dec_2025.pdf"
    client_file.write_bytes(b"%PDF-1.7 fake")

    scaffold_engagement(engagement)
    assert client_file.read_bytes() == b"%PDF-1.7 fake"


def test_not_applicable_folder_left_alone_if_it_exists(engagement):
    # Client already uploaded to C01 before the item was set aside.
    prepared = engagement / PREPARED_DIR_NAME
    prepared.mkdir()
    stale = prepared / "C01 - Fixed Asset Register"
    stale.mkdir()
    (stale / "far.xlsx").write_bytes(b"data")

    result = scaffold_engagement(engagement)
    assert result.not_applicable == ["C01"]
    assert (stale / "far.xlsx").exists()          # never deleted


def test_readme_refreshed_on_rerun(engagement):
    """A rerun rewrites the README over whatever is there - and decision 124:
    the heading stays, so this assertion is also the pin on that choice."""
    scaffold_engagement(engagement)
    readme_of(engagement)
    readme = inbox_of(engagement) / README_NAME
    readme.write_text("client scribbled over this", encoding="utf-8")

    assert README_HEADING in readme_of(engagement)


def test_a_folder_with_no_record_raises(tmp_path):
    with pytest.raises(ManifestError, match="not an engagement"):
        scaffold_engagement(tmp_path)


def test_the_review_folder_is_never_assigned_to_an_identifier(tmp_path):
    # "00 - Needs Review" starts with "00"; an identifier "00" must not
    # claim it and count every parked file as its own.
    (tmp_path / REVIEW_DIR_NAME).mkdir()
    (tmp_path / "00 - Opening Balances").mkdir()
    assigned = assign_folders(tmp_path, ["00"])
    assert [p.name for p in assigned["00"]] == ["00 - Opening Balances"]


def test_the_readme_contact_comes_from_the_engagement_details(tmp_path):
    from tracker.manifest import EngagementInfo, RequestItem
    from tracker.scaffold import write_readme

    folder = make_engagement(tmp_path, [RequestItem(identifier="A01", document="W-2")],
                             EngagementInfo(firm="J Park & Associates, CPA"))
    assert "Questions? Contact J Park & Associates, CPA." in readme_of(folder)
    written = write_readme(household_of(folder), contact="Someone Else")
    assert "Contact Someone Else." in written.read_text(encoding="utf-8")


def test_a_readme_the_client_side_holds_does_not_stop_the_scaffold(engagement, monkeypatch):
    # The README is cosmetic and client-visible. A viewer holding it, a sync
    # client uploading it, or a folder the client made under its name is a
    # log line, not the end of the pass behind it.
    import tracker.scaffold as scaffold_module
    from tracker.scaffold import README_NAME, scaffold_engagement

    scaffold_engagement(engagement)
    readme_of(engagement)
    readme = inbox_of(engagement) / README_NAME
    readme.unlink()
    readme.mkdir()                                     # a folder under the README's name

    def refused(*args, **kwargs):
        raise PermissionError("[WinError 32] being uploaded")
    monkeypatch.setattr(scaffold_module, "write_text_atomically", refused)
    result = scaffold_engagement(engagement)
    assert refresh_household_readme(household_of(engagement)) is None
    assert result.prepared_dir is not None and readme.is_dir()


def test_each_issuer_gets_its_own_client_folder(tmp_path):
    """An issuer row is an ordinary row, so the client sees one folder per
    issuing entity and the filed copy carries the entity's name (decision 93)."""
    from tracker.templates import issuer_row, item_from_spec

    rows = [item_from_spec(issuer_row("F02", "Ashford Holdings, L.P.")),
            item_from_spec(issuer_row("F03", "Birch Lane Partners"))]
    eng = make_engagement(tmp_path, rows)

    names = {f.name for f in (eng / PREPARED_DIR_NAME).iterdir() if f.is_dir()}
    assert "F02 - Schedule K-1 - Ashford Holdings LP" in names
    assert "F03 - Schedule K-1 - Birch Lane Partners" in names


# ================== what we have received (decision 130) ==================
#
# The README acknowledges what has arrived: a document confirmed into its
# request is Received, under the request's own label and its return; one a
# person is looking at is Under Review, counted by the day it arrived and
# never named. The index is the only source; the scaffold renders what the
# filer reads out of it and never reads it itself.


def arrived(identifier: str, decision: str, *, original: str = "client scan.pdf",
            received: str = "2026-09-23", also: str = ""):
    """One index row as a pass would leave it. ``original`` is the client's
    own file name - the one thing the README may never say."""
    from tracker.filer import NEEDS_REVIEW
    from tracker.records import IndexEntry

    folder = REVIEW_DIR_NAME if decision == NEEDS_REVIEW else f"{identifier} - folder"
    return IndexEntry(
        received=received, original_name=original, size_kb=12.0, digest=f"d-{original}",
        identifier="" if decision == NEEDS_REVIEW else identifier,
        prepared_location=f"{PREPARED_DIR_NAME}/{folder}/{original}",
        pbc_location=f"../../Clients/{TEST_HOUSEHOLD}/{TEST_YEAR}/{original}",
        decision=decision, reason="a reason", also_filed=also,
    )


def section_of(readme: str, heading: str) -> list[str]:
    """The lines under ``heading`` up to the blank line that ends them."""
    lines = readme.splitlines()
    start = lines.index(heading)
    end = lines.index("", start)
    return lines[start:end]


def test_the_received_section_is_absent_until_something_has_arrived(tmp_path):
    from tracker.scaffold import RECEIVED_HEADING, UNDER_REVIEW_HEADING

    readme = readme_of(make_engagement(tmp_path, ITEMS))

    assert RECEIVED_HEADING not in readme
    assert UNDER_REVIEW_HEADING not in readme
    assert "Received" not in readme


def test_a_filed_document_is_listed_as_received_under_its_return_by_its_request_label(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILE_MOVED, FILED
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf", received="2026-09-24"),
                            arrived("A02", FILE_MOVED, original="moved.pdf")])

    section = section_of(readme_of(engagement), RECEIVED_HEADING)

    assert section == [
        RECEIVED_HEADING,
        "-" * 45,
        TEST_RETURN,
        "  A02 - Monthly Bank Statements FY2025 (FY2025)  Received 23 Sep 2026",
        "  A01 - Dec 2025 Bank Statement (Dec 2025)  Received 24 Sep 2026",
    ]


def test_a_document_filed_to_two_requests_is_listed_once_per_request(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED
    from tracker.scaffold import RECEIVED_HEADING, folder_name_for

    engagement = make_engagement(tmp_path, ITEMS)
    also = f"{PREPARED_DIR_NAME}/{folder_name_for(ITEMS[2])}/two forms.pdf"
    seed_index(engagement, [arrived("A01", FILED, original="two forms.pdf", also=also)])

    section = section_of(readme_of(engagement), RECEIVED_HEADING)

    assert section[3:] == [
        "  A01 - Dec 2025 Bank Statement (Dec 2025)  Received 23 Sep 2026",
        f"  {ITEMS[2].label}  Received 23 Sep 2026",
    ]


def test_a_parked_document_is_counted_under_review_by_day_and_never_named(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import NEEDS_REVIEW
    from tracker.scaffold import RECEIVED_HEADING, UNDER_REVIEW_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [
        arrived("", NEEDS_REVIEW, original="Grandmas shoebox scan 7731.pdf"),
        arrived("", NEEDS_REVIEW, original="another.pdf"),
        arrived("", NEEDS_REVIEW, original="later.pdf", received="2026-09-24"),
    ])

    readme = readme_of(engagement)

    assert section_of(readme, RECEIVED_HEADING) == [
        RECEIVED_HEADING,
        "-" * 45,
        UNDER_REVIEW_HEADING,
        "  2 documents received 23 Sep 2026",
        "  1 document received 24 Sep 2026",
    ]
    for name in ("Grandmas shoebox scan 7731", "another", "later.pdf"):
        assert name not in readme


def test_duplicates_and_not_requested_rows_are_not_listed(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import DUPLICATE, NOT_REQUESTED
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived("A01", DUPLICATE, original="again.pdf"),
                            arrived("", NOT_REQUESTED, original="irs notice.pdf"),
                            arrived("A02", "Handed Over", original="handed.pdf")])

    readme = readme_of(engagement)

    assert RECEIVED_HEADING not in readme
    assert "Received" not in readme and "Under Review" not in readme


def test_the_client_file_name_never_reaches_the_readme(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived("A01", FILED, original="ZQX-private-name-4417.pdf")])

    readme = readme_of(engagement)

    assert "ZQX-private-name-4417" not in readme
    assert "Received 23 Sep 2026" in readme


def test_what_we_still_need_is_unchanged_by_the_new_section(tmp_path):
    """Decision 124's guarantee, narrowed by 130 and kept: the list of what
    is still needed is every active request, received or not, byte for byte
    what it was before anything arrived."""
    from tests.conftest import seed_index
    from tracker.filer import FILED, NEEDS_REVIEW
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    before = readme_of(engagement)
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf"),
                            arrived("", NEEDS_REVIEW, original="parked.pdf")])
    after = readme_of(engagement)

    assert RECEIVED_HEADING in after
    assert section_of(after, README_HEADING) == section_of(before, README_HEADING)
    assert "  A01 - Dec 2025 Bank Statement (Dec 2025)" in section_of(after, README_HEADING)


def test_the_readme_is_not_rewritten_when_nothing_changed(tmp_path):
    import os

    from tests.conftest import seed_index
    from tracker.filer import FILED

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf")])
    readme = refresh_household_readme(household_of(engagement))
    long_ago = 1_000_000_000
    os.utime(readme, ns=(long_ago * 10**9, long_ago * 10**9))

    assert refresh_household_readme(household_of(engagement)) == readme
    assert refresh_household_readme(household_of(engagement)) == readme
    assert readme.stat().st_mtime_ns == long_ago * 10**9


def test_a_household_with_two_open_years_is_left_alone(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED
    from tracker.scaffold import write_readme

    engagement = make_engagement(tmp_path, ITEMS)
    readme = inbox_of(engagement) / README_NAME
    before = readme.read_bytes()
    make_engagement(tmp_path, ITEMS, year=TEST_YEAR + 1,     # a second open year
                    return_name="1040 - Next Year")
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf")])

    assert refresh_household_readme(household_of(engagement)) is None
    assert write_readme(household_of(engagement)) is None
    assert readme.read_bytes() == before


def test_a_write_failure_is_a_log_line_and_the_caller_goes_on(engagement, monkeypatch, caplog):
    import logging

    import tracker.filer as filer_module
    import tracker.scaffold as scaffold_module

    scaffold_engagement(engagement)

    def refused(*args, **kwargs):
        raise PermissionError("[WinError 32] being uploaded")
    monkeypatch.setattr(scaffold_module, "write_text_atomically", refused)
    with caplog.at_level(logging.WARNING):
        assert refresh_household_readme(household_of(engagement)) is None
    assert "being uploaded" in caplog.text

    # And anything else that goes wrong reading the record is a log line too.
    def broken(returns):
        raise RuntimeError("the store is away")
    monkeypatch.setattr(filer_module, "received_for", broken)
    caplog.clear()
    with caplog.at_level(logging.WARNING):
        assert refresh_household_readme(household_of(engagement)) is None
    assert "the store is away" in caplog.text


def test_scaffolding_a_return_writes_no_readme(engagement):
    """The one-composer rule (decision 130): laying out folders never writes
    the README; only ``write_readme``, reached through the refresh, does."""
    from tracker.scaffold import scaffold_household

    result = scaffold_engagement(engagement)
    scaffold_household(household_of(engagement))

    assert result.inbox.is_dir()
    assert not (result.inbox / README_NAME).exists()
    assert result.readme == result.inbox / README_NAME


def test_the_received_heading_is_written_only_over_a_line_under_it(tmp_path):
    """The review's F4 (decision 130): data that renders no line - a
    Received line for a return the README does not speak for, an Under
    Review day counted zero - writes no heading, which would otherwise tell
    the client something arrived when the section says nothing did."""
    import datetime as dt

    from tracker.records import Received, ReceivedLine, UnderReview
    from tracker.scaffold import RECEIVED_HEADING, UNDER_REVIEW_HEADING, write_readme

    engagement = make_engagement(tmp_path, ITEMS)
    day = dt.date(2026, 9, 23)
    nothing_renders = Received(
        lines=(ReceivedLine(return_path=tmp_path / "not a return of this README",
                            label="A01 - W-2", day=day),),
        under_review=(UnderReview(day=day, count=0),),
    )

    readme = write_readme(household_of(engagement), nothing_renders).read_text(encoding="utf-8")

    assert RECEIVED_HEADING not in readme
    assert UNDER_REVIEW_HEADING not in readme
    assert "Received" not in readme


def test_a_readme_refresh_never_writes_older_text_over_newer(tmp_path, monkeypatch):
    """The review's F2 (decision 130). Two refreshes of one household
    interleave: the first has read the record and not yet written when a
    document is recorded and the second refresh starts. Under the
    household README's lock the second waits, then reads the record
    itself, so the later record wins; without it the second writes first
    and the first then lays its older text over it."""
    import functools
    import sqlite3
    import threading

    import tracker.filer as filer_module
    from tests.conftest import seed_index
    from tracker import store
    from tracker.filer import FILED
    from tracker.locking import EngagementLockedError

    # Two threads share the process's one store connection here, never at
    # the same moment: the first is paused outside any statement.
    store.close()
    monkeypatch.setattr(sqlite3, "connect",
                        functools.partial(sqlite3.connect, check_same_thread=False))
    engagement = make_engagement(tmp_path, ITEMS)
    household = household_of(engagement)
    readme = inbox_of(engagement) / README_NAME

    first_has_read, first_may_write, second_waits = (threading.Event() for _ in range(3))
    real_received_for, real_acquire = filer_module.received_for, filer_module.acquire_lock

    def pausing(returns):
        found = real_received_for(returns)
        if threading.current_thread().name == "older":
            first_has_read.set()
            assert first_may_write.wait(30)
        return found

    def watched(*args, **kwargs):
        try:
            return real_acquire(*args, **kwargs)
        except EngagementLockedError:
            if threading.current_thread().name == "newer":
                second_waits.set()
            raise

    monkeypatch.setattr(filer_module, "received_for", pausing)
    monkeypatch.setattr(filer_module, "acquire_lock", watched)
    older = threading.Thread(name="older", target=refresh_household_readme, args=(household,))
    newer = threading.Thread(name="newer", target=refresh_household_readme, args=(household,))

    older.start()
    assert first_has_read.wait(30)
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf")])   # the newer record
    newer.start()
    if not second_waits.wait(3):        # nothing made it wait: let it finish first
        newer.join(30)
    first_may_write.set()
    older.join(30)
    newer.join(30)

    assert not older.is_alive() and not newer.is_alive()
    assert "A01 - Dec 2025 Bank Statement (Dec 2025)  Received 23 Sep 2026" in \
        readme.read_text(encoding="utf-8")


def test_a_refresh_that_finds_the_readme_busy_waits_briefly_then_skips_with_a_log_line(
        tmp_path, monkeypatch, caplog):
    """The review's F2 (decision 130): the household README's lock is in the
    household's private folder, never the client's, and a refresh that
    finds it held past the brief wait leaves the README alone and says so."""
    import logging

    import tracker.filer as filer_module
    from tests.conftest import seed_index
    from tracker.filer import FILED, README_LOCK_FILENAME
    from tracker.layout import client_household_dir, root_of
    from tracker.locking import acquire_lock, release_lock

    engagement = make_engagement(tmp_path, ITEMS)
    household = household_of(engagement)
    readme = inbox_of(engagement) / README_NAME
    before = readme.read_bytes()
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf")])
    monkeypatch.setattr(filer_module, "README_LOCK_WAIT_SECONDS", 0.2)

    held = acquire_lock(household, README_LOCK_FILENAME)
    try:
        assert held.path == household / README_LOCK_FILENAME
        client_side = client_household_dir(root_of(engagement), household.name)
        assert not list(client_side.rglob(README_LOCK_FILENAME))
        with caplog.at_level(logging.WARNING):
            assert refresh_household_readme(household) is None
    finally:
        release_lock(held)

    assert "being refreshed by another run" in caplog.text
    assert readme.read_bytes() == before
    assert "Received 23 Sep 2026" in readme_of(engagement)
    assert not (household / README_LOCK_FILENAME).exists()
