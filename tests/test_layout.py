"""Tests for tracker/layout.py — the shape of the clients root, named once.

The claims here are about arithmetic and words: where a household, a year
and a return go, and the one way a path the record holds is written and
read back. Nothing here opens a file, because nothing in the module does.
"""

import os
from pathlib import Path

from tracker.filer import prepared_name_for
from tracker.layout import (
    CLIENTS_TREE,
    ENGAGEMENT_LABEL_PATTERN,
    INBOX_DIR_NAME,
    MAX_PATH_LENGTH,
    PREPARED_DIR_NAME,
    PRIVATE_TREE,
    RETURN_NAME_PATTERN,
    client_household_dir,
    deepest_path_length,
    household_name_of,
    household_of,
    inbox_dir_for,
    inbox_of,
    is_year_folder,
    label_for,
    locate,
    location_of,
    originals_dir_for,
    originals_of,
    private_household_dir,
    return_dir_for,
    root_of,
    year_folder_name,
    year_of,
)
from tracker.scaffold import folder_name_for
from tracker.templates import template_items

ROOT = Path("G:/Shared drives/JPA Clients")
HOUSEHOLD = "Park Family"
RETURN = "1040 - John & Maria Park"


def test_the_two_trees_the_inbox_and_the_return_folder_are_named_once():
    """One example, and every helper agrees about it: the client tree holds
    the household, its inbox and the year's originals; the private tree
    holds the household's record and the return under its year."""
    engagement = return_dir_for(ROOT, HOUSEHOLD, 2026, RETURN)

    assert engagement == ROOT / PRIVATE_TREE / HOUSEHOLD / "2026" / RETURN
    assert private_household_dir(ROOT, HOUSEHOLD) == ROOT / PRIVATE_TREE / HOUSEHOLD
    assert client_household_dir(ROOT, HOUSEHOLD) == ROOT / CLIENTS_TREE / HOUSEHOLD
    assert inbox_dir_for(ROOT, HOUSEHOLD) == ROOT / CLIENTS_TREE / HOUSEHOLD / INBOX_DIR_NAME
    assert originals_dir_for(ROOT, HOUSEHOLD, 2026) == ROOT / CLIENTS_TREE / HOUSEHOLD / "2026"

    # And read back off one return folder, positionally.
    assert root_of(engagement) == ROOT
    assert household_of(engagement) == private_household_dir(ROOT, HOUSEHOLD)
    assert household_name_of(engagement) == HOUSEHOLD
    assert year_of(engagement) == 2026
    assert inbox_of(engagement) == inbox_dir_for(ROOT, HOUSEHOLD)
    assert originals_of(engagement) == originals_dir_for(ROOT, HOUSEHOLD, 2026)

    # The year folder is four digits, always, and nothing else is one.
    assert year_folder_name(2026) == "2026" and is_year_folder("2026")
    assert not is_year_folder("Archive 2026") and not is_year_folder("202")
    assert year_of(ROOT / PRIVATE_TREE / HOUSEHOLD / "Archive" / RETURN) is None

    # The two patterns, and the label everything that lists returns says.
    assert RETURN_NAME_PATTERN.format(form="1040", client="John & Maria Park") == RETURN
    assert label_for(HOUSEHOLD, 2026, RETURN) == ENGAGEMENT_LABEL_PATTERN.format(
        household=HOUSEHOLD, year=2026, return_name=RETURN)
    assert label_for(HOUSEHOLD, 2026, RETURN) == f"{HOUSEHOLD} 2026 {RETURN}"
    # A return whose record carries no year says the two it has, and the
    # pattern's own gap is what is left of the third.
    assert label_for(HOUSEHOLD, None, RETURN).startswith(HOUSEHOLD)
    assert label_for(HOUSEHOLD, None, RETURN).endswith(RETURN)


def test_a_location_is_relative_to_the_return_and_posix_on_every_platform():
    """Every path the record holds is written by one helper and read by
    one: relative to the return folder, POSIX, and across the two trees
    with ``..`` - so a line written on one machine reads on another and
    nothing in the record ever names a drive."""
    engagement = return_dir_for(ROOT, HOUSEHOLD, 2026, RETURN)
    copy = engagement / PREPARED_DIR_NAME / "A01 - W-2 Wage Statements" / "A01 - W-2 - TY2026.pdf"
    original = originals_of(engagement) / "W2 john.pdf"

    assert location_of(engagement, copy) == (
        f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements/A01 - W-2 - TY2026.pdf")
    assert location_of(engagement, original) == f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/2026/W2 john.pdf"

    for path in (copy, original):
        written = location_of(engagement, path)
        assert "\\" not in written                       # POSIX, on every platform
        assert not os.path.splitdrive(written)[0]        # and never a drive
        assert locate(engagement, written) == path       # read back, exactly


def test_a_location_is_read_back_lexically_so_a_junction_stays_a_junction(tmp_path):
    """``locate`` normalises the ``..`` segments textually and never
    resolves: the filer's link check exists to refuse what lies behind a
    junction, and a resolved path would come back naming the target."""
    engagement = tmp_path / PRIVATE_TREE / HOUSEHOLD / "2026" / RETURN
    engagement.mkdir(parents=True)
    linked = tmp_path / PRIVATE_TREE / HOUSEHOLD / "2026" / "link"

    where = locate(engagement, "../link/x.pdf")
    assert where == linked / "x.pdf"
    assert "link" in where.parts                          # the link is still in the path


def test_the_deepest_path_is_measured_from_the_return_folder():
    """The figures decision 125 measured: the firm's own root and the
    catalog's own rows fit, and a request document of a hundred characters
    does not."""
    engagement = return_dir_for(ROOT, HOUSEHOLD, 2026, RETURN)
    assert len(str(ROOT)) == 28                          # G:\Shared drives\JPA Clients
    assert len(str(engagement)) - len(str(ROOT)) == 62   # the private tree, the household, the year, the return

    copy = f"{PREPARED_DIR_NAME}/A01 - W-2 Wage Statements/A01 - W-2 Wage Statements - TY2026.pdf"
    assert len(copy) + 1 == 74
    assert deepest_path_length(engagement, [copy]) == 164
    assert deepest_path_length(engagement, [copy]) <= MAX_PATH_LENGTH

    # The same return with a hundred-character request document is past it.
    long_row = template_items("1040", core_only=True)[0]
    from dataclasses import replace

    long_row = replace(long_row, document="x" * 100)
    deepest = (f"{PREPARED_DIR_NAME}/{folder_name_for(long_row)}/"
               f"{prepared_name_for(long_row, 'xlsx', set())}")
    assert deepest_path_length(engagement, [deepest]) > MAX_PATH_LENGTH
    assert deepest_path_length(engagement, [deepest]) == 316

    assert deepest_path_length(engagement, []) == 0       # a return with no request


def test_the_suites_own_short_root_leaves_room_for_the_whole_1040_core_list(short_root):
    """The measurement that matters on whatever machine the suite runs on.

    The refusal is about the **whole** path, so a temporary folder the
    build runner spells more generously than this one turns a claim about
    the tracker into a claim about the runner's account name - which is
    how the 1040 core list went five characters past the limit on a runner
    called ``runneradmin`` while it fitted here. Said once, by name, so a
    machine with no room says so instead of failing every create.
    """
    engagement = return_dir_for(short_root, HOUSEHOLD, 2026, RETURN)
    subpaths = [f"{PREPARED_DIR_NAME}/{folder_name_for(item)}/"
                f"{prepared_name_for(item, 'xlsx', set())}"
                for item in template_items("1040", core_only=True)]
    deepest = deepest_path_length(engagement, subpaths)
    assert deepest <= MAX_PATH_LENGTH, (
        f"the suite's short root is {len(str(short_root))} characters and leaves "
        f"{deepest - MAX_PATH_LENGTH} too few for a whole 1040: {short_root}")


def test_the_whole_1040_core_list_fits_under_the_firms_own_root():
    """The measurement that matters at the office: every row of the
    catalog a real client is cut from fits inside what Windows will open."""
    engagement = return_dir_for(ROOT, HOUSEHOLD, 2026, RETURN)
    subpaths = [f"{PREPARED_DIR_NAME}/{folder_name_for(item)}/"
                f"{prepared_name_for(item, 'xlsx', set())}"
                for item in template_items("1040", core_only=True)]
    assert deepest_path_length(engagement, subpaths) == 223
    assert deepest_path_length(engagement, subpaths) <= MAX_PATH_LENGTH
