"""Tests for tracker/layout.py — the shape of the clients root, named once.

The claims here are about arithmetic and words: where a household, a year
and a return go, and the one way a path the record holds is written and
read back. Nothing here opens a file, because nothing in the module does.
"""

import os
from pathlib import Path

import pytest

from tracker.filer import prepared_name_for
from tracker.layout import (
    CLIENTS_TREE,
    ENGAGEMENT_LABEL_PATTERN,
    INBOX_DIR_NAME,
    MAX_PATH_LENGTH,
    PREPARED_DIR_NAME,
    PRIVATE_TREE,
    RETURN_NAME_PATTERN,
    STEP_ABOVE_ROOT,
    STEP_ABSOLUTE,
    STEP_BLANK,
    STEP_CLIENT_TREE,
    STEP_NOT_A_PLACE,
    STEP_NOT_A_RETURN,
    STEP_OTHER_HOUSEHOLD,
    STEP_OTHER_YEAR,
    STEP_PROBLEMS,
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
    place_problem,
    private_household_dir,
    return_dir_for,
    root_of,
    year_folder_name,
    year_of,
)
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

    # The same return with a request named by a hundred characters was
    # past it while the name was in the path twice, once as the request's
    # folder (316). Since decision 144 the name in the path is the row's
    # short name, which a person cannot type past twenty, and since
    # decision 168 it is there once - the copy sits in Prepared itself and
    # its name is capped - so even a hundred characters fits (215).
    long_row = template_items("1040", core_only=True)[0]
    from dataclasses import replace

    long_row = replace(long_row, document="x" * 100, short_title="x" * 100)
    deepest = f"{PREPARED_DIR_NAME}/{prepared_name_for(long_row, 'xlsx', set())}"
    assert deepest_path_length(engagement, [deepest]) <= MAX_PATH_LENGTH
    assert deepest_path_length(engagement, [deepest]) == 215

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
    subpaths = [f"{PREPARED_DIR_NAME}/{prepared_name_for(item, 'xlsx', set())}"
                for item in template_items("1040", core_only=True)]
    deepest = deepest_path_length(engagement, subpaths)
    assert deepest <= MAX_PATH_LENGTH, (
        f"the suite's short root is {len(str(short_root))} characters and leaves "
        f"{deepest - MAX_PATH_LENGTH} too few for a whole 1040: {short_root}")


def test_the_whole_1040_core_list_fits_under_the_firms_own_root():
    """The measurement that matters at the office: every row of the
    catalog a real client is cut from fits inside what Windows will open -
    138 characters with each copy in Prepared itself (decision 168), 163
    with a folder per request and the short names (decision 144), 223 with
    the full titles."""
    engagement = return_dir_for(ROOT, HOUSEHOLD, 2026, RETURN)
    subpaths = [f"{PREPARED_DIR_NAME}/{prepared_name_for(item, 'xlsx', set())}"
                for item in template_items("1040", core_only=True)]
    assert deepest_path_length(engagement, subpaths) == 138
    assert deepest_path_length(engagement, subpaths) <= MAX_PATH_LENGTH


# ------------------------------------------- decision 131: a moved root ----


def test_a_rolled_from_path_names_the_same_return_after_the_clients_root_moves():
    """Rolled From is written absolute, so a root that moves leaves it naming
    a folder that is not there; the household's, the year's and the
    return's names below the root still say which return it was. Two
    trailing names are not enough - a return keeps its name every year and
    two households may each hold one called the same - and a path equal but
    for its case is the same folder, as Windows says."""
    from tracker.layout import ROLLED_FROM_TAIL, same_return, shared_tail

    moved = return_dir_for(Path("E:/Archive/JPA Clients"), HOUSEHOLD, 2025, RETURN)
    was = str(return_dir_for(ROOT, HOUSEHOLD, 2025, RETURN))

    assert ROLLED_FROM_TAIL == 3
    assert same_return(was, moved)
    assert shared_tail(was, moved) >= ROLLED_FROM_TAIL
    # Two names in common - another household's return of the same name.
    elsewhere = return_dir_for(Path("E:/Archive/JPA Clients"), "Lee Family", 2025, RETURN)
    assert shared_tail(was, elsewhere) == 2
    assert not same_return(was, elsewhere)
    # The same path, lexically.
    here = return_dir_for(ROOT, HOUSEHOLD, 2025, RETURN)
    assert same_return(str(here), here)
    if os.name == "nt":
        assert same_return(str(here).upper(), here)


def test_the_limit_for_an_extension_is_the_shortest_that_applies(monkeypatch):
    """Windows's 260 for everything no reader limits further; a reader's
    shorter figure for its own extensions, whatever their case or dot.
    The owner's ruling (decision 131, Q-A) sets spreadsheets at 218."""
    import tracker.layout as layout
    from tracker.layout import OPEN_LIMITS, limit_for

    assert OPEN_LIMITS == {"xlsx": 218, "xlsm": 218, "xls": 218, "csv": 218}
    monkeypatch.setattr(layout, "OPEN_LIMITS", {})
    assert limit_for("xlsx") == limit_for("pdf") == MAX_PATH_LENGTH == 260
    monkeypatch.setattr(layout, "OPEN_LIMITS", {"xlsx": 218})
    assert limit_for("xlsx") == limit_for(".XLSX") == 218
    assert limit_for("pdf") == 260
    # Never above Windows's own, whatever a table says.
    monkeypatch.setattr(layout, "OPEN_LIMITS", {"pdf": 400})
    assert limit_for("pdf") == 260


# Decision 187: where a step of a return may act is the layout's rule, worded once.

PLACE_RETURN = return_dir_for(ROOT, HOUSEHOLD, 2025, RETURN)


@pytest.mark.parametrize("location, writes, code", [
    ("Prepared/A01 - W-2/x.pdf", True, None),                                    # the return itself
    ("../_Opened/mail/x.pdf", True, None),                                       # its year's _Opened
    ("../../2024/_Opened/mail/x.pdf", False, None),                              # another year's, to read
    ("../../2024/_Opened/mail/x.pdf", True, STEP_OTHER_YEAR),                    # never to write
    ("../../../Other Household/2025/_Opened/mail/x.pdf", False, STEP_NOT_A_PLACE),  # another household's
    (f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/{INBOX_DIR_NAME}/x.pdf", False, None),  # its inbox
    (f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/{INBOX_DIR_NAME}/sub/x.pdf", False, None),
    (f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/2025/x.pdf", True, None),         # its year folder
    (f"../../../../{CLIENTS_TREE}/Other Household/2025/x.pdf", False, None),    # a feed's original
    (f"../../../../{CLIENTS_TREE}/Other Household/2025/x.pdf", True, STEP_OTHER_HOUSEHOLD),
    (f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/x.pdf", False, STEP_NOT_A_PLACE),  # beside the inbox
    ("../1040 - Someone Else/Prepared/x.pdf", False, STEP_NOT_A_PLACE),          # another return
    ("../../_ledger.jsonl", True, STEP_NOT_A_PLACE),                             # the household's record
    ("../../../../../outside/secret.pdf", False, STEP_ABOVE_ROOT),               # above the root
    ("/etc/passwd", False, STEP_ABSOLUTE),
    ("C:/Windows/win.ini", False, STEP_ABSOLUTE),
    ("C:x.pdf", False, STEP_ABSOLUTE),
    ("\\\\host\\share\\x.pdf", False, STEP_ABSOLUTE),
    ("", False, STEP_BLANK),
])
def test_a_step_may_act_only_in_its_returns_places(location, writes, code):
    assert place_problem(PLACE_RETURN, location, writes=writes) == code
    assert code is None or code in STEP_PROBLEMS


def test_a_return_named_relative_to_the_root_has_the_same_places_as_one_named_absolutely():
    """The store keys a return by its path below the clients root; the filer
    holds it absolute. One rule, one answer, whichever is asked."""
    relative = Path(PRIVATE_TREE) / HOUSEHOLD / "2025" / RETURN
    for location, writes in [
        ("Prepared/x.pdf", True),
        ("../../2024/_Opened/x.pdf", True),
        (f"../../../../{CLIENTS_TREE}/Other Household/{INBOX_DIR_NAME}/x.pdf", False),
        (f"../../../../{CLIENTS_TREE}/Other Household/{INBOX_DIR_NAME}/x.pdf", True),
        ("../../../../../outside/x.pdf", False),
        ("../../_ledger.jsonl", False),
        ("/etc/passwd", False),
    ]:
        assert place_problem(relative, location, writes=writes) == \
            place_problem(PLACE_RETURN, location, writes=writes)
        assert place_problem(relative.as_posix(), location, writes=writes) == \
            place_problem(PLACE_RETURN, location, writes=writes)


def test_a_location_that_climbs_above_the_root_is_above_the_root_whatever_it_names_after():
    """Out past the root and back down by the root's own name lands, as text,
    in a place a step may act - and is still above the root."""
    back_in = f"../../../../../{ROOT.name}/{CLIENTS_TREE}/{HOUSEHOLD}/{INBOX_DIR_NAME}/x.pdf"
    assert place_problem(PLACE_RETURN, back_in, writes=False) == STEP_ABOVE_ROOT
    assert place_problem(PLACE_RETURN, "Prepared/../../../../../../x.pdf", writes=False) == STEP_ABOVE_ROOT


def test_a_record_not_at_a_returns_place_has_no_places():
    """A path that is not ``root/PRIVATE_TREE/<household>/<year>/<return>``
    is no return, and nothing is a place for its steps."""
    for not_a_return in [
        ROOT / CLIENTS_TREE / HOUSEHOLD / "2025" / RETURN,          # the client tree
        ROOT / PRIVATE_TREE / HOUSEHOLD / "Prior" / RETURN,         # no year above it
        Path(HOUSEHOLD) / "2025" / RETURN,                          # too short
        private_household_dir(ROOT, HOUSEHOLD),
    ]:
        assert place_problem(not_a_return, "Prepared/x.pdf", writes=False) == STEP_NOT_A_RETURN


def test_the_place_rule_touches_no_disk(monkeypatch):
    """Arithmetic on the layout: the root need not exist, and a rule that
    asked the disk anything would fail here."""
    missing = return_dir_for(ROOT / "no such root", HOUSEHOLD, 2025, RETURN)

    def refuse(*_args, **_kwargs):
        raise AssertionError("the place rule asked the disk")

    monkeypatch.setattr(os, "stat", refuse)
    monkeypatch.setattr(os, "lstat", refuse)
    assert place_problem(missing, "Prepared/x.pdf", writes=True) is None
    assert place_problem(missing, "../../../../../x.pdf", writes=False) == STEP_ABOVE_ROOT
    assert place_problem(missing, f"../../../../{CLIENTS_TREE}/Other/2025/x.pdf", writes=True) \
        == STEP_OTHER_HOUSEHOLD


def test_a_removal_may_act_only_under_the_return_or_its_years_opened():
    """The review's M4: a removal takes away one of the firm's own copies,
    so it is narrower than a write - the client tree is never a place for
    one, not even this household's own inbox or year folder."""
    for location, code in [
        ("Prepared/A01 - W-2.pdf", None),
        ("../_Opened/mail/x.pdf", None),
        ("../../2024/_Opened/mail/x.pdf", STEP_OTHER_YEAR),
        (f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/2025/w2.pdf", STEP_CLIENT_TREE),
        (f"../../../../{CLIENTS_TREE}/{HOUSEHOLD}/{INBOX_DIR_NAME}/w2.pdf", STEP_CLIENT_TREE),
        (f"../../../../{CLIENTS_TREE}/Other Household/2025/w2.pdf", STEP_CLIENT_TREE),
        ("../../_ledger.jsonl", STEP_NOT_A_PLACE),
    ]:
        assert place_problem(PLACE_RETURN, location, writes=True, removes=True) == code, location
    assert STEP_CLIENT_TREE in STEP_PROBLEMS


# ----------------------------- decision 188: one name rule, one key, one parser ----


def test_the_five_constructors_refuse_a_bad_name_or_year():
    """A path is never built through a name the rule refuses, nor under a
    year that is not an ``int`` of four digits (a ``bool`` is not one) -
    so no label, however it got into a record, becomes a path of its own."""
    from tracker.layout import LayoutError

    builders = [
        lambda name: client_household_dir(ROOT, name),
        lambda name: inbox_dir_for(ROOT, name),
        lambda name: originals_dir_for(ROOT, name, 2025),
        lambda name: private_household_dir(ROOT, name),
        lambda name: return_dir_for(ROOT, name, 2025, RETURN),
        lambda name: return_dir_for(ROOT, HOUSEHOLD, 2025, name),
    ]
    for bad in ["../Other", "Park/..", "", ".hidden", "_private", "~$lock", "NUL", "Park.",
                f"{CLIENTS_TREE}", "2025", "Pa\u200brk", "P\u0430rk", "x" * 81]:
        for build in builders:
            with pytest.raises(LayoutError):
                build(bad)
    for year in ["2025", 25, 20250, True, 2025.0, None]:
        with pytest.raises(LayoutError):
            originals_dir_for(ROOT, HOUSEHOLD, year)
        with pytest.raises(LayoutError):
            return_dir_for(ROOT, HOUSEHOLD, year, RETURN)
    # And a return whose folder name is refused has no inbox or originals.
    with pytest.raises(LayoutError):
        inbox_of(ROOT / PRIVATE_TREE / ".." / "2025" / RETURN)


def test_every_name_discovery_passes_over_is_refused():
    """Every name the walk passes over without a word begins with one of
    the machine's prefixes, and the rule refuses every one - so a
    household or a return is never a folder the walk would not list."""
    from tracker.layout import MACHINE_PREFIXES, NAME_FIRST_CHARACTER, segment_problem
    from tracker.validators import OFFICE_LOCK_PREFIX, is_sync_staging

    assert OFFICE_LOCK_PREFIX in MACHINE_PREFIXES
    for name in [".git", ".tmp.driveupload", ".tmp.drivedownload", "_Opened", "_archive",
                 "~$Park Family", ".DS_Store"]:
        assert name.startswith(MACHINE_PREFIXES), name
        assert segment_problem(name) == NAME_FIRST_CHARACTER, name
    assert is_sync_staging(".tmp.driveupload") and ".tmp.driveupload".startswith(MACHINE_PREFIXES)


def test_each_part_of_the_name_rule_says_its_own_reason():
    """Eight refusals, each with its fixed phrase; the character is named by
    code point and Unicode name, never by quoting the name."""
    from tracker import layout

    cases = {
        "": layout.NAME_EMPTY,
        "x" * 81: layout.NAME_TOO_LONG.format(limit=80, n=81),
        "-Park": layout.NAME_FIRST_CHARACTER,
        "Park Jr.": layout.NAME_TRAILING,
        "Park<1>": layout.NAME_ILLEGAL,
        "Park\tFamily": layout.NAME_ILLEGAL,
        "COM1": layout.NAME_DEVICE.format(names=layout.WINDOWS_RESERVED_NAMES_TEXT),
        "Park\u200bFamily": layout.NAME_INVISIBLE.format(character="U+200B ZERO WIDTH SPACE"),
        "Park\u00a0Family": layout.NAME_INVISIBLE.format(character="U+00A0 NO-BREAK SPACE"),
        "Park\ufe0f": layout.NAME_INVISIBLE.format(character="U+FE0F VARIATION SELECTOR-16"),
        "\uff30ark": layout.NAME_COMPATIBILITY.format(
            character="U+FF30 FULLWIDTH LATIN CAPITAL LETTER P"),
        "\ufb01sher": layout.NAME_COMPATIBILITY.format(
            character="U+FB01 LATIN SMALL LIGATURE FI"),
        "P\u0430rk": layout.NAME_SCRIPTS.format(first="Latin", second="Cyrillic"),
        "Drop Files Here": layout.NAME_LAYOUT_WORD,
        PRIVATE_TREE: layout.NAME_LAYOUT_WORD,
        "2025": layout.NAME_LAYOUT_WORD,
    }
    for name, reason in cases.items():
        assert layout.segment_problem(name) == reason, name
    for fine in [HOUSEHOLD, RETURN, "Mu\u00f1oz", "\u4e2d\u6751\u3055\u3093", "1040 - O'Brien",
                 "\u041f\u0435\u0442\u0440\u043e\u0432"]:
        assert layout.segment_problem(fine) is None, fine
    # Entry normalises once: stripped, one space, NFC.
    assert layout.normalised_name("  Mun\u0303oz   Family ") == "Mu\u00f1oz Family"
    with pytest.raises(layout.LayoutError, match="'-Park' is not a household name: must begin"):
        layout.checked_name(" -Park", "household")


def test_the_key_folds_exactly_the_stated_look_alikes():
    """Every entry of the look-alike table folds to its Latin letter, the
    key is idempotent, NFC and NFD spell one key, and the ASCII look-alikes
    the SPEC names fold too - so a look-alike name is the name it imitates."""
    from tracker.layout import LOOK_ALIKES, name_key

    assert len([c for c in LOOK_ALIKES if "\u0400" <= c <= "\u052f"]) == 31
    assert len([c for c in LOOK_ALIKES if "\u0370" <= c <= "\u03ff"]) == 16
    for char, latin in LOOK_ALIKES.items():
        assert name_key(char) == name_key(latin), hex(ord(char))
    for name in ["Park", "PARK", "\u0420\u0430rk", "P\u0430rk",
                 "\uff30\uff41\uff52\uff4b", "Pa\u00adrk", "Pa\u200brk"]:
        assert name_key(name) == name_key("Park"), name
    # A name all in one look-alike script: Cyrillic spells "COX" whole.
    # It has no R, so "\u0420\u0410\u0420\u041a" reads PAPK, and is PAPK.
    assert name_key("\u0421\u041e\u0425") == name_key("Cox")
    assert name_key("\u0420\u0410\u0420\u041a") == name_key("PAPK") != name_key("Park")
    assert name_key("Kim") == name_key("Klm") == name_key("K1m")
    assert name_key("Mu\u00f1oz") == name_key("Mun\u0303oz")
    assert name_key("Corn") == name_key("Com")
    assert name_key("O'Brien") == name_key("O\u2019Brien")
    assert name_key("Smith-Jones") == name_key("Smith\u2013Jones")
    for name in ["Park", "\u0421\u041e\u0425", "Mu\u00f1oz", "Kim  Lee"]:
        assert name_key(name_key(name)) == name_key(name)
    assert name_key("Park") != name_key("Parks")


def test_the_positional_parser_names_every_place():
    """One parser says what kind of place a path is under the root, the
    trees and the inbox compared as the filesystem compares them; a ``..``
    left over is outside."""
    from tracker import layout

    home = ROOT / CLIENTS_TREE / HOUSEHOLD
    ret = return_dir_for(ROOT, HOUSEHOLD, 2025, RETURN)
    cases = [
        (ROOT, layout.Place(layout.ROOT)),
        (ROOT / CLIENTS_TREE, layout.Place(layout.CLIENTS)),
        (home, layout.Place(layout.CLIENT_HOUSEHOLD, HOUSEHOLD)),
        (home / INBOX_DIR_NAME, layout.Place(layout.INBOX, HOUSEHOLD)),
        (home / INBOX_DIR_NAME / "w2.pdf", layout.Place(layout.IN_INBOX, HOUSEHOLD)),
        (home / "2025", layout.Place(layout.ORIGINALS, HOUSEHOLD, 2025)),
        (home / "2025" / "w2.pdf", layout.Place(layout.IN_ORIGINALS, HOUSEHOLD, 2025)),
        (home / "Taxes", layout.Place(layout.MISPLACED, HOUSEHOLD)),
        (ROOT / PRIVATE_TREE, layout.Place(layout.PRIVATE)),
        (ret.parent.parent, layout.Place(layout.HOUSEHOLD, HOUSEHOLD)),
        (ret.parent, layout.Place(layout.YEAR, HOUSEHOLD, 2025)),
        (ret.parent / "_Opened", layout.Place(layout.OPENED, HOUSEHOLD, 2025)),
        (ret.parent / "_Opened" / "m" / "x.pdf", layout.Place(layout.IN_OPENED, HOUSEHOLD, 2025)),
        (ret, layout.Place(layout.RETURN, HOUSEHOLD, 2025, RETURN)),
        (ret / "Prepared" / "x.pdf", layout.Place(layout.IN_RETURN, HOUSEHOLD, 2025, RETURN)),
        (ret.parent.parent / "Prior", layout.Place(layout.MISPLACED, HOUSEHOLD)),
        (ROOT / "Archive", layout.Place(layout.MISPLACED)),
        (ROOT.parent / "Elsewhere", layout.Place(layout.OUTSIDE)),
        (Path(str(ROOT) + "/../Elsewhere"), layout.Place(layout.OUTSIDE)),
    ]
    for path, place in cases:
        assert layout.place_of(ROOT, path) == place, path
    # A root given relative, and a path relative to it, are the same places.
    assert layout.place_of("", Path(PRIVATE_TREE) / HOUSEHOLD).kind == layout.HOUSEHOLD
    assert layout.place_of("", "../x").kind == layout.OUTSIDE
    if os.name == "nt":
        assert layout.place_of(ROOT, ROOT / "clients" / HOUSEHOLD).kind == layout.CLIENT_HOUSEHOLD
    # Built on it: a return and a household, or the sentence refusing one -
    # and anything in the client tree is never one.
    assert layout.return_at(ROOT, ret) == (HOUSEHOLD, 2025, RETURN)
    assert layout.household_at(ROOT, ret.parent.parent) == HOUSEHOLD
    for not_a_return in [home / INBOX_DIR_NAME / "X", ret.parent, ret / "Prepared", ROOT.parent]:
        with pytest.raises(layout.LayoutError, match="is not a return's folder"):
            layout.return_at(ROOT, not_a_return)
    for not_a_household in [home, ret.parent, ROOT / PRIVATE_TREE]:
        with pytest.raises(layout.LayoutError, match="is not a household's folder"):
            layout.household_at(ROOT, not_a_household)
    # And the one test of lying under another path.
    assert layout.parts_below(ROOT, ret) == (PRIVATE_TREE, HOUSEHOLD, "2025", RETURN)
    assert layout.parts_below(ROOT, ROOT) == ()
    assert layout.parts_below(ret, ROOT) is None
    assert layout.parts_below(ROOT, Path(str(ROOT) + "x")) is None
