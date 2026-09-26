"""Tests for tracker/scaffold.py — folder scaffolding, no OneDrive needed."""

import hashlib

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
    assign_files,
    matches_identifier,
    owner_of,
    persons_folders,
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


def test_working_copy_names_are_windows_safe_and_begin_with_their_identifier():
    """Decision 168: the name is all there is to say which request a copy
    is for, so it always begins with the identifier and a separator."""
    from tracker.filer import prepared_name_for

    for item in ITEMS:
        name = prepared_name_for(item, "pdf", set())
        assert not set('\\/:*?"<>|') & set(name)
        assert not name.endswith((".", " "))
        assert name.startswith(f"{item.identifier} - ")
        assert owner_of(name, [one.identifier for one in ITEMS]) == item.identifier


def test_matches_identifier_boundaries():
    assert matches_identifier("A01 - Dec 2025 Bank Statement", "A01")
    assert matches_identifier("a01 - renamed by client", "A01")  # case-insensitive
    assert matches_identifier("A01-whatever", "A01")
    assert matches_identifier("A01", "A01")
    assert not matches_identifier("A10 - Something", "A1")   # boundary: '0' is alnum
    assert not matches_identifier("A012", "A01")
    assert not matches_identifier("XA01 - Nope", "A01")
    assert not matches_identifier("A01x", "A01")


def test_assign_files_longest_identifier_wins(tmp_path):
    """Decision 168, ruling 2: the rule the request folders were assigned
    by, applied to the files directly in Prepared."""
    (tmp_path / "A01 - Bank - Dec 2025.pdf").write_bytes(b"a")
    (tmp_path / "A01-B - Loan Docs - TY2025.pdf").write_bytes(b"b")
    (tmp_path / "A01 - Bank - Dec 2025 (2).pdf").write_bytes(b"c")
    assigned = assign_files(tmp_path, ["A01", "A01-B"])
    assert [p.name for p in assigned["A01"]] == ["A01 - Bank - Dec 2025 (2).pdf",
                                                 "A01 - Bank - Dec 2025.pdf"]
    assert [p.name for p in assigned["A01-B"]] == ["A01-B - Loan Docs - TY2025.pdf"]


def test_only_files_directly_in_prepared_are_a_requests(tmp_path):
    """A folder inside Prepared - the review folder, a person's, a request
    folder of a return made before decision 168 - holds nothing of any
    request's, and a name no identifier begins is nobody's."""
    (tmp_path / REVIEW_DIR_NAME).mkdir()
    (tmp_path / REVIEW_DIR_NAME / "A01 - parked.pdf").write_bytes(b"a")
    (tmp_path / "A01 - W-2").mkdir()
    (tmp_path / "A01 - W-2" / "A01 - W-2 - TY2025.pdf").write_bytes(b"b")
    (tmp_path / "scan0012.pdf").write_bytes(b"c")
    assert assign_files(tmp_path, ["A01"]) == {"A01": []}
    assert [p.name for p in persons_folders(tmp_path)] == ["A01 - W-2"]


def test_a_temp_file_a_killed_copy_left_is_never_a_requests(tmp_path):
    """Decision 155's temp is the target's name with ``.<pid>.<tag>.tmp``
    after it, so it begins with the identifier and a separator like the
    copy it was going to be. It is never counted as one (SPEC-168 §8)."""
    from tracker.fsio import temp_path_for

    target = tmp_path / "A01 - W-2 - TY2025.pdf"
    temp = temp_path_for(target)
    temp.write_bytes(b"half a copy")
    assert temp.name.startswith("A01 - W-2 - TY2025.pdf.")
    assert owner_of(temp.name, ["A01"]) == "A01"            # its name alone would claim it
    assert assign_files(tmp_path, ["A01"]) == {"A01": []}   # the one function never does


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
    # Firm side: somewhere for the unclear, and nothing else - no request
    # has a folder since decision 168; its copies sit in Prepared itself.
    assert [p.name for p in prepared.iterdir()] == [REVIEW_DIR_NAME]
    assert result.prepared_dir == prepared

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


def test_step_3_keeps_asking_for_what_is_outstanding_in_jasons_words(tmp_path):
    """Decision 130, the owner's wording of 2026-09-23: step 3 points at
    the list that holds what is outstanding."""
    from tracker.scaffold import README_STEP_3

    readme = readme_of(make_engagement(tmp_path, ITEMS, contact="Maria Park"))

    assert README_STEP_3 == ("3. Please keep sending the documents listed under REQUESTED,\n"
                             "   NOT YET RECEIVED. Send them as you find them; there's no\n"
                             "   need to wait and send everything at once.")
    assert README_STEP_3 in readme
    assert "lists below are covered" not in readme
    assert README_HEADING in README_STEP_3.replace("\n   ", " ")


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
    scaffold_engagement(engagement)
    assert [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir()] == [REVIEW_DIR_NAME]


def test_recreates_deleted_folder(engagement):
    scaffold_engagement(engagement)
    (engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME).rmdir()
    scaffold_engagement(engagement)
    assert (engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME).is_dir()


def test_a_copy_renamed_with_its_prefix_still_belongs_to_its_request(engagement):
    """Rename-tolerant, flat (decision 168): a copy a person renamed
    ``A01 - bank stuff.pdf`` is still A01's, and the scaffold makes
    nothing beside it."""
    scaffold_engagement(engagement)
    prepared = engagement / PREPARED_DIR_NAME
    (prepared / "A01 - bank stuff.pdf").write_bytes(b"%PDF-1.7 fake")

    scaffold_engagement(engagement)
    assigned = assign_files(prepared, [item.identifier for item in ITEMS])
    assert [p.name for p in assigned["A01"]] == ["A01 - bank stuff.pdf"]
    assert sorted(p.name for p in prepared.iterdir()) == [REVIEW_DIR_NAME, "A01 - bank stuff.pdf"]


def test_existing_client_files_never_touched(engagement):
    scaffold_engagement(engagement)
    prepared = engagement / PREPARED_DIR_NAME
    client_file = prepared / "chase_dec_2025.pdf"
    client_file.write_bytes(b"%PDF-1.7 fake")
    (prepared / "my notes").mkdir()
    kept = prepared / "my notes" / "draft.xlsx"
    kept.write_bytes(b"data")

    scaffold_engagement(engagement)
    assert client_file.read_bytes() == b"%PDF-1.7 fake"
    assert kept.read_bytes() == b"data"


def test_an_old_request_folder_is_left_alone(engagement):
    """A request folder made before decision 168 - here a set-aside row's,
    with a file in it - is a person's folder now: never deleted, never
    emptied, and nothing is made beside it."""
    prepared = engagement / PREPARED_DIR_NAME
    prepared.mkdir()
    stale = prepared / "C01 - Fixed Asset Register"
    stale.mkdir()
    (stale / "far.xlsx").write_bytes(b"data")

    scaffold_engagement(engagement)
    assert (stale / "far.xlsx").exists()          # never deleted
    assert persons_folders(prepared) == [stale]


def test_readme_refreshed_on_rerun(engagement):
    """A rerun rewrites the firm's own README - and decision 124: the
    heading stays, so this assertion is also the pin on that choice."""
    scaffold_engagement(engagement)
    readme = inbox_of(engagement) / README_NAME
    readme.write_text(readme_of(engagement).replace(README_HEADING, "an older list"),
                      encoding="utf-8")

    assert README_HEADING in readme_of(engagement)


def test_a_client_file_at_the_readmes_name_is_sorted_and_never_written_over(engagement):
    """Decision 179. The README was skipped by the sort and written over by
    every refresh, so a client's own ``_README.txt`` - or the README the
    client wrote their own note over - was replaced unread. A file there
    that does not begin as the firm's does is the client's: the refresh
    leaves it alone, the pass moves it into the year's folder byte for
    byte as it moves every drop, and the README is written after it."""
    import datetime as dt

    from tests.conftest import sort
    from tracker.filer import read_index

    scaffold_engagement(engagement)
    readme = inbox_of(engagement) / README_NAME
    note = b"Hi - the W-2 is coming next week. Maria\r\n"
    readme.write_bytes(note)

    assert refresh_household_readme(household_of(engagement)) is None
    assert readme.read_bytes() == note

    sort(engagement, today=dt.date(2026, 2, 2))
    refresh_household_readme(household_of(engagement))       # after the sort, as the pass does

    [row] = read_index(engagement)
    assert row.original_name == README_NAME
    assert (originals_of(engagement) / README_NAME).read_bytes() == note
    assert README_HEADING in readme.read_text(encoding="utf-8")


def test_a_file_at_the_readmes_name_is_the_firms_the_clients_or_cannot_be_told(tmp_path, monkeypatch):
    """Decision 179, three answers: a small file beginning with the first
    line (a byte-order mark allowed) is the firm's; a large one, or one
    beginning otherwise, is the client's; one whose read raises is neither."""
    from pathlib import Path

    from tracker.scaffold import (
        README_CLIENTS,
        README_FIRMS,
        README_FIRST_LINE,
        README_MAX_BYTES,
        README_UNKNOWN,
        whose_readme,
    )

    one = tmp_path / README_NAME
    one.write_bytes(f"{README_FIRST_LINE}\r\n====".encode("ascii"))
    assert whose_readme(one) == README_FIRMS
    one.write_bytes(b"\xef\xbb\xbf" + f"{README_FIRST_LINE}\r\n".encode("ascii"))
    assert whose_readme(one) == README_FIRMS                  # a BOM an editor added
    one.write_bytes(b"My own notes\r\n" + f"{README_FIRST_LINE}\r\n".encode("ascii"))
    assert whose_readme(one) == README_CLIENTS
    one.write_bytes(f"{README_FIRST_LINE}\r\n".encode("ascii") + b"x" * README_MAX_BYTES)
    assert whose_readme(one) == README_CLIENTS              # never read whole to find out
    one.write_bytes(f"{README_FIRST_LINE}\r\n".encode("ascii"))
    real_open = Path.open

    def held(self, *args, **kwargs):
        if self.name == README_NAME:
            raise PermissionError(13, "held by another process", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", held)
    assert whose_readme(one) == README_UNKNOWN              # held open: cannot be told
    assert whose_readme(tmp_path / "missing.txt") == README_UNKNOWN


def test_a_readme_that_cannot_be_read_just_now_waits_where_it_is(engagement, monkeypatch):
    """The review's S-3: a README a sync client or a viewer held for a
    moment was not known to be the firm's, so the pass moved it into the
    year's folder and parked it as the client's drop - noise a person had
    to dismiss, every time it happened. One that cannot be read just now
    is left where it is, not recorded and not written over, and the pass
    names it in its warnings; the next pass, able to read it, knows it as
    the firm's and refreshes it."""
    import datetime as dt
    from pathlib import Path

    from tests.conftest import sort
    from tracker.filer import README_UNREAD, read_index
    from tracker.scaffold import README_FIRST_LINE

    scaffold_engagement(engagement)
    readme = inbox_of(engagement) / README_NAME
    stale = f"{README_FIRST_LINE}\r\nan older list\r\n".encode("ascii")
    readme.write_bytes(stale)
    real_open = Path.open

    def held(self, *args, **kwargs):
        if self.name == README_NAME and self.parent == inbox_of(engagement):
            raise PermissionError(13, "held by another process", str(self))
        return real_open(self, *args, **kwargs)

    monkeypatch.setattr(Path, "open", held)
    report = sort(engagement, today=dt.date(2026, 2, 2))
    refresh_household_readme(household_of(engagement))       # after the sort, as the pass does
    monkeypatch.setattr(Path, "open", real_open)             # the file is free again

    assert readme.read_bytes() == stale                       # not moved, not written over
    assert not (originals_of(engagement) / README_NAME).exists()
    assert read_index(engagement) == []
    household = household_of(engagement).name
    assert [(one.name, one.error) for one in report.attention] == [
        (README_NAME, README_UNREAD.format(household=household))]

    report = sort(engagement, today=dt.date(2026, 2, 3))
    refresh_household_readme(household_of(engagement))

    assert report.attention == [] and read_index(engagement) == []
    assert not (originals_of(engagement) / README_NAME).exists()
    assert README_HEADING in readme.read_text(encoding="utf-8")


def test_a_folder_with_no_record_raises(tmp_path):
    with pytest.raises(ManifestError, match="not an engagement"):
        scaffold_engagement(tmp_path)


def test_the_review_folder_is_never_assigned_to_an_identifier(tmp_path):
    # "00 - Needs Review" starts with "00"; an identifier "00" must not
    # claim it and count every parked file as its own.
    (tmp_path / REVIEW_DIR_NAME).mkdir()
    (tmp_path / REVIEW_DIR_NAME / "00 - parked.pdf").write_bytes(b"a")
    (tmp_path / "00 - Opening Balances - TY2025.pdf").write_bytes(b"b")
    assigned = assign_files(tmp_path, ["00"])
    assert [p.name for p in assigned["00"]] == ["00 - Opening Balances - TY2025.pdf"]
    assert persons_folders(tmp_path) == []


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


def test_each_issuer_gets_its_own_working_copy_name(tmp_path):
    """An issuer row is an ordinary row, so each issuing entity's copies
    have names of their own (decision 93) - since decision 168 side by side
    in Prepared, with no folder per request. Since decision 144 the name
    carries the row's short name, ``K-1`` and the issuer cut to twenty
    characters at a whole word (the owner's Q-B), while the Document the
    client reads keeps the entity's whole name."""
    from tracker.filer import prepared_name_for
    from tracker.templates import issuer_row, item_from_spec

    rows = [item_from_spec(issuer_row("F02", "Ashford Holdings, L.P.")),
            item_from_spec(issuer_row("F03", "Birch Lane Partners"))]
    eng = make_engagement(tmp_path, rows)

    assert persons_folders(eng / PREPARED_DIR_NAME) == []
    names = [prepared_name_for(row, "pdf", set()) for row in rows]
    assert names[0].startswith("F02 - K-1 Ashford Holdings - ")
    assert names[1].startswith("F03 - K-1 Birch Lane - ")
    assert [row.document for row in rows] == ["Schedule K-1 - Ashford Holdings LP",
                                              "Schedule K-1 - Birch Lane Partners"]


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

    # A working copy sits in Prepared itself, named by its request
    # (decision 168); a parked one in the review folder under its own name.
    where = (f"{REVIEW_DIR_NAME}/{original}" if decision == NEEDS_REVIEW
             else f"{identifier} - {original}")
    return IndexEntry(
        received=received, original_name=original, size_kb=12.0,
        digest=hashlib.sha256(original.encode()).hexdigest(),
        identifier="" if decision == NEEDS_REVIEW else identifier,
        prepared_location=f"{PREPARED_DIR_NAME}/{where}",
        pbc_location=f"../../../../Clients/{TEST_HOUSEHOLD}/{TEST_YEAR}/{original}",
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
    from tracker.filer import FILED, prepared_name_for
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    also = f"{PREPARED_DIR_NAME}/{prepared_name_for(ITEMS[2], 'pdf', set())}"
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


A01_LABEL = "A01 - Dec 2025 Bank Statement (Dec 2025)"
ACTIVE_IDS = ("A01", "A02", "B01")   # C01 is Not Applicable: on no list


def _mentions(section: list[str], identifier: str) -> bool:
    return any(line.strip().startswith(f"{identifier} - ") for line in section[2:])


def test_the_first_list_is_headed_in_jasons_words():
    """Jason's decision of 2026-09-23 (decision 130), replacing 124's D-1."""
    from tracker.scaffold import NOTHING_OUTSTANDING_LINE

    assert README_HEADING == "REQUESTED, NOT YET RECEIVED"
    assert NOTHING_OUTSTANDING_LINE == "  Nothing at the moment."


def test_a_request_with_a_received_document_leaves_the_not_yet_received_list(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf")])
    readme = readme_of(engagement)

    first = section_of(readme, README_HEADING)
    assert not _mentions(first, "A01")
    assert _mentions(first, "A02") and _mentions(first, "B01")
    assert TEST_RETURN in first      # a return with something left keeps its heading
    assert any(A01_LABEL in line for line in section_of(readme, RECEIVED_HEADING))


def test_a_document_under_review_does_not_take_its_request_off_the_list(tmp_path):
    import dataclasses

    from tests.conftest import seed_index
    from tracker.filer import NEEDS_REVIEW

    engagement = make_engagement(tmp_path, ITEMS)
    before = section_of(readme_of(engagement), README_HEADING)
    # A parked row that names a request (a failed name check, an unfiled
    # row) must still not take that request off: nothing is confirmed yet.
    parked = dataclasses.replace(arrived("", NEEDS_REVIEW, original="parked.pdf"),
                                 identifier="A02")
    seed_index(engagement, [parked])

    assert section_of(readme_of(engagement), README_HEADING) == before


def test_receiving_a_request_in_one_return_leaves_the_same_request_on_another(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED

    alice = make_engagement(tmp_path, ITEMS, return_name="1040 - Alice")
    make_engagement(tmp_path, ITEMS, return_name="1040 - Bob")
    seed_index(alice, [arrived("A01", FILED, original="bank.pdf")])
    first = section_of(readme_of(alice), README_HEADING)

    bob = first.index("1040 - Bob")
    assert any(line.strip().startswith("A01 - ") for line in first[bob:])
    assert "1040 - Alice" in first            # Alice still has A02 and B01 left


def test_an_also_filed_copy_takes_its_request_off_the_list(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived("A01", FILED, original="two forms.pdf",
                                    also=f"{PREPARED_DIR_NAME}/B01 - Aging - TY2025.pdf")])
    readme = readme_of(engagement)

    assert not _mentions(section_of(readme, README_HEADING), "B01")
    assert _mentions(section_of(readme, RECEIVED_HEADING), "B01")


def test_an_other_document_line_takes_nothing_off_the_list(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED, OTHER_DOCUMENT
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, ITEMS)
    before = section_of(readme_of(engagement), README_HEADING)
    seed_index(engagement, [arrived("ZZ9", FILED, original="old request.pdf")])
    readme = readme_of(engagement)

    assert section_of(readme, README_HEADING) == before
    assert any(OTHER_DOCUMENT in line for line in section_of(readme, RECEIVED_HEADING))


def _all_received(tmp_path):
    from tests.conftest import seed_index
    from tracker.filer import FILED

    engagement = make_engagement(tmp_path, ITEMS)
    seed_index(engagement, [arrived(i, FILED, original=f"{i}.pdf") for i in ACTIVE_IDS])
    return readme_of(engagement)


def test_a_return_with_nothing_outstanding_has_no_heading_there(tmp_path):
    readme = _all_received(tmp_path)

    assert TEST_RETURN not in section_of(readme, README_HEADING)


def test_nothing_outstanding_reads_nothing_at_the_moment(tmp_path):
    from tracker.scaffold import NOTHING_OUTSTANDING_LINE

    readme = _all_received(tmp_path)

    assert section_of(readme, README_HEADING)[2:] == [NOTHING_OUTSTANDING_LINE]


def test_every_request_is_on_exactly_one_list_or_under_review_never_lost(tmp_path):
    """No *asked* request is ever on neither list, and none is on both: a
    request that leaves the first list is a Received line below it
    (decision 130's invariant, reworded by decision 142 - a row nobody
    asked for with nothing received is on neither, by the owner's rule)."""
    from tests.conftest import seed_index
    from tracker.filer import FILED, NEEDS_REVIEW
    from tracker.scaffold import RECEIVED_HEADING

    engagement = make_engagement(tmp_path, [*ITEMS, RequestItem(
        identifier="D01", document="Brokerage Statements", asked=False)])
    seed_index(engagement, [arrived("A01", FILED, original="bank.pdf"),
                            arrived("", NEEDS_REVIEW, original="parked.pdf")])
    readme = readme_of(engagement)
    first = section_of(readme, README_HEADING)
    received = section_of(readme, RECEIVED_HEADING)

    for identifier in ACTIVE_IDS:
        assert _mentions(first, identifier) != _mentions(received, identifier), identifier
    assert not _mentions(first, "C01") and not _mentions(received, "C01")
    assert not _mentions(first, "D01") and not _mentions(received, "D01")


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
                            label="A01 - W-2", day=day, identifier="A01"),),
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
# ------------------------------------ decision 131: a clients root that moves ----


def test_the_readme_is_still_written_after_the_clients_root_moves(short_root, tmp_path, monkeypatch):
    """Rolled From is written absolute, so after the clients root moves it
    names a folder that is not there. The scaffold used to retire a prior by
    resolved path only, so every household that had ever rolled over read
    to it as two open years and its README was never rewritten again. It
    retires by discovery's rule now - the path, else its three trailing
    names - so the pass and the scaffold both see one open year, the README
    is written with the new year's list, and the practice page still shows
    the prior as rolled forward."""
    from tracker.layout import README_NAME, inbox_dir_for, originals_dir_for, private_household_dir
    from tracker.registry import SKIP_ROLLED_FORWARD, discover_engagements
    from tracker.rollover import ReturnPlan, roll_household
    from tracker.runner import (
        REMINDERS_NEVER,
        TWO_OPEN_YEARS,
        run_household,
        status_report,
        write_status_page,
    )
    from tracker.scaffold import scaffold_household
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    (tmp_path / "app").mkdir(exist_ok=True)
    before = short_root / "One"
    before.mkdir()
    set_clients_root(before)
    w2 = [RequestItem(identifier="A01", document="W-2 Wage Statements", period="TY2025",
                      allowed_extensions=("pdf",), min_size_kb=0, any_keywords=("w-2",))]
    prior = make_engagement(before, w2, household="Park Family", year=2025,
                            return_name="1040 - John Park")
    roll_household(private_household_dir(before, "Park Family"), target_year=2026,
                   plans=[ReturnPlan(prior=prior)])

    after = short_root / "Two"
    before.rename(after)
    set_clients_root(after)
    household = private_household_dir(after, "Park Family")
    readme = inbox_dir_for(after, "Park Family") / README_NAME
    readme.unlink()

    done = scaffold_household(household)
    # The scaffold lays out folders only; the README's one composer is the
    # refresh (decision 130), which reads the same open-year rule.
    assert refresh_household_readme(household) == readme

    assert done.originals == [originals_dir_for(after, "Park Family", 2026)]
    assert readme.is_file() and "2026" in readme.read_text(encoding="utf-8")

    readme.unlink()
    registry = discover_engagements(after)
    returns = registry.by_household()[household]
    runs = run_household(household, returns, root=after, reminders=REMINDERS_NEVER, registry=registry)
    said = TWO_OPEN_YEARS.split("(")[0]
    assert [w for run in runs for w in run.warnings if said in w] == []
    assert readme.is_file() and "2026" in readme.read_text(encoding="utf-8")   # the pass's refresh too
    page = write_status_page(after, status_report(registry, passed=runs)).read_text(encoding="utf-8")
    assert SKIP_ROLLED_FORWARD.split("{")[0] in page


# ---------------------------------------------- decision 137: the security review ----


def test_windows_reserved_device_names_are_never_folder_names(tmp_path):
    """Decision 137 (L6): ``CON``, ``PRN``, ``AUX``, ``NUL``, ``COM1``-``9``
    and ``LPT1``-``9`` - with or without an extension, in any case - are
    devices to Windows, not folders. The sanitiser never hands one back as
    itself, an identifier may not be one, and a household, a return or a
    feed whose name the sanitiser would change is refused. On Windows the
    name the sanitiser gives back is made as a real folder."""
    import os

    import tracker.api as api
    from tracker.manifest import ManifestError, identifier_problem, is_reserved_name
    from tracker.scaffold import sanitize_component

    reserved = ["CON", "prn", "Aux", "NUL", "nul.txt", "COM1", "com9.pdf", "LPT1", "LPT9 .log"]
    ordinary = ["CONSOLE", "Smith", "COM10", "LPT", "CON - W-2", "1040 - Con Ed"]
    for name in reserved:
        assert is_reserved_name(name), name
        cleaned = sanitize_component(name)
        assert cleaned != name and not is_reserved_name(cleaned), (name, cleaned)
        assert "device" in identifier_problem(name.split(".")[0].strip()), name
        with pytest.raises(ManifestError, match="is not a folder name"):
            api._folder_name(name, "type the household's name on its own")
        with pytest.raises(ManifestError):
            api._feeds_from_spec([{"household": name, "return_name": "1040 - John"}],
                                 tmp_path / "Park Family")
        if os.name == "nt":
            made = tmp_path / cleaned
            made.mkdir()
            assert made.is_dir() and cleaned in os.listdir(tmp_path)
    for name in ordinary:
        assert not is_reserved_name(name) and sanitize_component(name) == name, name
    assert api._feeds_from_spec([{"household": "Smith", "return_name": "1040 - John"}],
                                tmp_path / "Park Family")


def test_superscript_ports_and_the_console_devices_are_reserved_too():
    """Decision 137's review (F6): Windows also keeps COM and LPT with a
    superscript 1, 2 or 3, and CONIN$ and CONOUT$. None of them is ever a
    folder name, alone or before an extension, in any case."""
    from tracker.manifest import identifier_problem, is_reserved_name
    from tracker.scaffold import sanitize_component

    for name in ("COM\u00b9", "com\u00b2", "LPT\u00b3", "lpt\u00b9.txt", "CONIN$", "conout$",
                 "CONOUT$.log"):
        assert is_reserved_name(name), name
        cleaned = sanitize_component(name)
        assert cleaned != name and not is_reserved_name(cleaned), (name, cleaned)
    assert "device" in identifier_problem("CONIN$")
    for name in ("COM\u00b9\u00b2", "CONINS", "LPT4x"):
        assert not is_reserved_name(name), name


# --------------------------------------------- decision 142: accepted, not asked ----


def test_the_readme_asks_only_for_asked_rows_and_lists_what_arrived_under_any(tmp_path):
    """A row nobody asked for is never on *REQUESTED, NOT YET RECEIVED*. With
    nothing received it is on neither list; a document filed under it is a
    Received line under the row's own title, exactly as under an asked one."""
    from tests.conftest import seed_index
    from tracker.filer import FILED
    from tracker.scaffold import RECEIVED_HEADING

    unasked = RequestItem(identifier="D01", document="Social Security Benefit Statement",
                          period="TY2025", asked=False)
    engagement = make_engagement(tmp_path, [*ITEMS, unasked])
    readme = readme_of(engagement)
    assert not _mentions(section_of(readme, README_HEADING), "D01")
    assert RECEIVED_HEADING not in readme and "Social Security" not in readme

    seed_index(engagement, [arrived("D01", FILED, original="ssa.pdf")])
    readme = readme_of(engagement)
    assert not _mentions(section_of(readme, README_HEADING), "D01")
    received = section_of(readme, RECEIVED_HEADING)
    assert any(line.strip().startswith(unasked.label) for line in received)
    for identifier in ACTIVE_IDS:                           # every asked request still on its list
        assert _mentions(section_of(readme, README_HEADING), identifier), identifier


def test_the_scaffold_makes_no_request_folders(tmp_path):
    """Decision 168, claim 5 (decision 142's "no folder for a row nobody
    asked for", widened to every row): a fresh return's Prepared holds only
    the review folder, and every asked row is simply Missing - never
    "request folder not found", which retired with the folder."""
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    unasked = RequestItem(identifier="D01", document="Social Security Benefit Statement",
                          asked=False)
    engagement = make_engagement(tmp_path, [*ITEMS, unasked], scaffold=False)

    scaffold_engagement(engagement)
    prepared = engagement / PREPARED_DIR_NAME
    assert [p.name for p in prepared.iterdir()] == [REVIEW_DIR_NAME]

    report = scan_engagement(engagement)
    for identifier in ("A01", "A02", "B01"):
        update = report.updates[identifier]
        assert update.status == Status.MISSING and update.file_count == 0
        assert "folder" not in update.validation_notes
    assert report.warnings == []


def test_the_client_readme_keeps_the_full_title(short_root):
    """Decision 144, claim 7: the short name is the firm's. The request's
    copies on the firm's side are named ``A01 - W-2 - ...``, and the README the
    client reads in their inbox still asks for the "W-2 Wage Statements -
    All Employers" by its full title, and never by the short one alone."""
    from tracker.templates import template_items

    w2 = template_items("1040", year=TEST_YEAR)[0]
    engagement = make_engagement(short_root, [w2])
    from tracker.filer import prepared_name_for

    assert prepared_name_for(w2, "pdf", set()).startswith("A01 - W-2 - ")
    assert persons_folders(engagement / PREPARED_DIR_NAME) == []
    readme = (inbox_of(engagement) / README_NAME).read_text(encoding="utf-8")
    assert "A01 - W-2 Wage Statements - All Employers" in readme
    assert "A01 - W-2 (" not in readme and "A01 - W-2\n" not in readme
