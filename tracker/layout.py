"""The shape of the clients root: two trees, a household, a year, a return.

One folder per client with one year inside it could not hold the practice
(decision 125). Most clients are a business and its owner's 1040, some are
ten entities, some are families, and two 1040s share every row of their
request lists - so a drop folder that fed one return could not say whose
W-2 it held. A client folder is a **household**, with one folder per **tax
year** inside it and one folder per **return** inside that.

There are two trees under the clients root, and which one a thing lives in
is the whole of what it is safe to share:

- :data:`CLIENTS_TREE` holds the household's folder, its one permanent
  inbox (:data:`INBOX_DIR_NAME`) and one folder per tax year holding the
  originals the pass moved out of that inbox. It is the only tree a client
  is ever shared, and nothing under it is ever a record, a lock, a working
  copy, a draft or a page.
- :data:`PRIVATE_TREE` holds the household's own record and, under a year,
  one folder per return: the engagement folder, with its journal, its
  lock, its working copies, its Status Report and its drafts. It is never
  shared.

**Nothing here reads a file, opens a record or takes a lock.** It is path
arithmetic on one layout and the words that name it, so it sits at layer 0
and imports nothing of the package - every layer above may ask where a
thing belongs without reaching for the module that puts it there.

**The one convention for a stored path** is :func:`location_of` and
:func:`locate`. Every location a record holds is relative to the return
folder and POSIX, as decision 102 made it: a working copy is
``PREPARED_DIR_NAME/A01 - W-2 - TY2025.pdf`` (decision 168) and an original, which lives in
the other tree, is written with ``..`` back to the root and down the
client tree. The
relative form names no drive, so a journal line written on one machine
reads on another, and ``locate`` normalises lexically and never resolves -
a junction must stay a junction for the filer's link check.

The engagement remains the software's word for one return in one year: the
return folder *is* the engagement folder. "Household" is the new word.
"""

from __future__ import annotations

import os
from collections.abc import Iterable
from pathlib import Path

#: The only tree a client is ever shared. It holds the household's folder,
#: its inbox and the year folders of originals - and no record, ever.
CLIENTS_TREE = "Clients"
#: The firm's own tree: the household record and every return. Never shared.
PRIVATE_TREE = "J Park & Associates"
#: The household's one permanent inbox, in the client tree. One per
#: household however many returns it has, because a client is told about
#: one folder and keeps using it (decision 125).
INBOX_DIR_NAME = "Drop files here"
#: The firm's working set inside a return: the working copies side by side,
#: each named by its request (decision 168), and the review folder.
PREPARED_DIR_NAME = "Prepared"
#: Where anything the rules could not confidently identify waits for a person.
REVIEW_DIR_NAME = "00 - Needs Review"
#: The generated note telling the client they need not sort anything. It
#: lives in the inbox, which is the one folder they are asked to use.
README_NAME = "_README.txt"
#: Where what was taken out of a client's email or zip rests (decision
#: 143): one hidden folder per household-year in the **private** tree,
#: beside the year's returns, never in the tree the client is shared. The
#: leading underscore is what keeps discovery from listing it as a folder
#: that does not fit; it holds no journal, so it is never read as a return;
#: and it is not under any return's working set, so the sweep of the
#: working copies never names what is in it. Synced like everything in the
#: private tree - a named exception to decision 107's rule, by the owner's
#: decision of 2026-09-23 - because a recovery (decision 119) and a move to
#: another machine must both reach it.
OPENED_DIR_NAME = "_Opened"

#: How a return folder is named: the form first, the name after, so the
#: same return line can be followed year after year. ``form`` is the
#: catalog's own id (``1040``, ``1120S``), not its label.
RETURN_NAME_PATTERN = "{form} - {client}"
#: How one return is named wherever a person reads a list of them: the
#: household, the year and the return. The year is the folder above the
#: return, so it is never repeated inside the return's own name.
ENGAGEMENT_LABEL_PATTERN = "{household} {year} {return_name}"

#: What Windows will open a path of. Creation refuses a return whose
#: deepest working copy would pass it, naming the length (decision 125) -
#: a folder made today that cannot hold a filed document in February is a
#: failure at a filing deadline.
MAX_PATH_LENGTH = 260
#: What such a refusal says.
PATH_TOO_LONG = ("the deepest file the tracker would write under {folder} would be {length} "
                 "characters, past the {limit} Windows allows; shorten the household or the return name")
#: Readers with a documented limit shorter than Windows's, by extension,
#: lower-case without the dot (decision 131). A working copy is written
#: once and then opened by people, and their programs have limits of their
#: own: Microsoft documents 218 characters as the longest path Excel opens
#: a workbook from. The owner ruled (decision 131, Q-A) that spreadsheet
#: copies are cut to fit it; creation's refusal stays at
#: :data:`MAX_PATH_LENGTH`, because this is a reader's limit and not the
#: tracker's own write. A name is cut to the shortest limit that applies
#: to its extension (:func:`limit_for`).
OPEN_LIMITS: dict[str, int] = {"xlsx": 218, "xlsm": 218, "xls": 218, "csv": 218}
#: How many trailing folder names a Rolled From path must share with a
#: return folder to name it once the path itself no longer resolves: the
#: household's, the year's and the return's (decision 125's three; moved
#: here from the registry by decision 131 so the scaffold reads the same
#: rule). Three, because a return keeps its name every year and two
#: households may each hold ``2025/1040 - John Park`` - two names would tie.
ROLLED_FROM_TAIL = 3


# --------------------------------------------------------------- the year ----


def year_folder_name(year: int) -> str:
    """A tax year as its folder is named: four digits, always."""
    return f"{year:04d}"


def is_year_folder(name: str) -> bool:
    """Whether a folder name is a year folder's: four digits and nothing else.

    What discovery asks at the third level (``tracker.registry``). Four
    digits rather than a range, because the walk is telling a year folder
    from a folder somebody made, not validating a tax year - the bounds
    are the manifest's (``check_tax_year``) and are asked when a person
    types one.
    """
    return len(name) == 4 and name.isdigit()


# -------------------------------------------------------------- the trees ----


def client_household_dir(root: Path | str, household: str) -> Path:
    """The household's folder in the tree a client is shared."""
    return Path(root) / CLIENTS_TREE / household


def inbox_dir_for(root: Path | str, household: str) -> Path:
    """The household's one inbox."""
    return client_household_dir(root, household) / INBOX_DIR_NAME


def originals_dir_for(root: Path | str, household: str, year: int) -> Path:
    """The year's folder of originals, in the tree a client can see.

    Flat: what the pass moved out of the inbox, under the client's own
    names, and never sorted again. An original's resting place is the
    record's identity for the document, so moving it a second time when a
    request accepts it would rewrite the recovery of decisions 109, 110
    and 119 for a sort the client never asked for. The firm's working
    copies are sorted by request, under :data:`PREPARED_DIR_NAME` in the other tree.
    """
    return client_household_dir(root, household) / year_folder_name(year)


def private_household_dir(root: Path | str, household: str) -> Path:
    """The household's folder in the tree that is never shared: its record."""
    return Path(root) / PRIVATE_TREE / household


def return_dir_for(root: Path | str, household: str, year: int, return_name: str) -> Path:
    """One return's folder - the engagement folder - under its year."""
    return private_household_dir(root, household) / year_folder_name(year) / return_name


# ------------------------------------------------- one return, upwards ----


def root_of(return_dir: Path | str) -> Path:
    """The clients root a return folder sits under.

    Positional: a return is ``root/PRIVATE_TREE/<household>/<year>/<return>``
    and nothing else is a return, so the root is four levels up.
    """
    return Path(return_dir).parents[3]


def household_of(return_dir: Path | str) -> Path:
    """The private household folder a return belongs to: the one holding the
    household's own record."""
    return Path(return_dir).parent.parent


def household_name_of(return_dir: Path | str) -> str:
    """The household's name as its folders spell it."""
    return household_of(return_dir).name


def year_of(return_dir: Path | str) -> int | None:
    """The tax year a return's folder sits under, or ``None`` when the
    folder above it is not named as a year.

    ``None`` rather than a guess: a year nobody can read off the layout is
    the record's to say (``EngagementInfo.tax_year``), and a folder whose
    name disagrees with its record is processed as the record says and
    warned (``tracker.registry.NAME_DISAGREES``).
    """
    name = Path(return_dir).parent.name
    return int(name) if is_year_folder(name) else None


def inbox_of(return_dir: Path | str) -> Path:
    """The inbox this return's drops arrive in: the household's one inbox,
    in the client tree."""
    return inbox_dir_for(root_of(return_dir), household_name_of(return_dir))


def opened_dir_of(return_dir: Path | str) -> Path:
    """Where this return's household-year keeps what was taken out of an
    email or a zip (:data:`OPENED_DIR_NAME`): beside the return, in the
    private tree, shared by every return of the household-year as the
    originals folder is."""
    return Path(return_dir).parent / OPENED_DIR_NAME


def originals_of(return_dir: Path | str) -> Path:
    """Where this return's originals rest: its household's folder for its
    year, in the tree the client can see.

    Shared with every other return of the household-year, which is the
    point: one inbox feeds them all and an original belongs to the
    household's year, not to the return that happened to accept it.
    """
    year = year_of(return_dir)
    if year is None:
        raise ValueError(f"{Path(return_dir).parent.name!r} is not a year folder")
    return originals_dir_for(root_of(return_dir), household_name_of(return_dir), year)


def lock_order_key(return_dir: Path | str) -> tuple[str, str]:
    """Where one return stands in the **one global lock order** (decision
    129): its household's folder name, then its own, without case.

    Every pass that touches more than one household takes every lock it
    needs in this order before anything is read. A household's drop folder
    may feed a return line in another household, so two passes running at
    once can want the same two returns - and two processes taking their
    locks in the same order cannot deadlock, whichever household each
    started from. Without case, because Windows folder names differ by it
    and two spellings of one order are not an order.

    It is also what "the first return by order" means wherever the sort
    says it, so the return a contested drop parks in is the return whose
    lock was taken first.
    """
    return (household_name_of(return_dir).casefold(), Path(return_dir).name.casefold())


def label_for(household: str, year: object, return_name: str) -> str:
    """How one return is named wherever a person reads a list of them.

    The picker, the practice page, the Status Report's title, the run log
    and the command line all say this, so nobody reads a column of years
    or two identical return names from different households.
    """
    return ENGAGEMENT_LABEL_PATTERN.format(
        household=household, year=year if year is not None else "", return_name=return_name,
    ).strip()


# ----------------------------------------------------- a location, both ways ----


def location_of(engagement_dir: Path | str, path: Path | str) -> str:
    """Where ``path`` is, as the record holds it: relative to the return
    folder, POSIX.

    **The one convention for every path a record holds** (decision 102,
    widened by 125). A working copy is ``PREPARED_DIR_NAME/<name>`` (decision
    168; ``PREPARED_DIR_NAME/<request>/<name>`` before it); an original now
    lives in the other tree and is written with
    ``..`` back to the root and down the client tree to the household's
    folder for the year. Neither
    names a drive, so a line written on one machine reads on another, and
    every reader turns it back into a path through :func:`locate` and
    nothing else.
    """
    return Path(os.path.relpath(Path(path), Path(engagement_dir))).as_posix()


def locate(engagement_dir: Path | str, location: str) -> Path:
    """The path a stored location names: the one way back.

    **Lexical, never resolved.** ``Path.resolve()`` would follow a junction
    and the filer's link check (``_through_a_link``) exists precisely to
    refuse what lies behind one; a resolved path would come back naming the
    target and the check would pass. ``os.path.normpath`` collapses the
    ``..`` segments textually, which is what Windows does with them too.
    """
    return Path(os.path.normpath(os.path.join(str(engagement_dir), location)))


def deepest_path_length(return_dir: Path | str, subpaths: Iterable[str]) -> int:
    """The longest path the tracker would write under ``return_dir``, in
    characters, over ``subpaths``.

    What creation measures against :data:`MAX_PATH_LENGTH` before a folder
    is made: the deepest working copy a request list implies. ``0`` for no
    subpaths at all, because a return with no request has nothing to write.
    """
    lengths = [len(str(Path(return_dir) / sub)) for sub in subpaths]
    return max(lengths, default=0)


def limit_for(extension: str) -> int:
    """The longest path a working copy with ``extension`` may have: the
    shortest of Windows's limit and any reader's (:data:`OPEN_LIMITS`).

    ``xlsx``, ``.XLSX`` and ``.xlsx`` are one extension."""
    return min(MAX_PATH_LENGTH, OPEN_LIMITS.get(extension.lower().lstrip("."), MAX_PATH_LENGTH))


# ------------------------------------------------ a return, after a move ----


def shared_tail(a: str | Path, b: str | Path) -> int:
    """How many trailing folder names ``a`` and ``b`` have in common,
    compared as Windows compares them (``os.path.normcase``)."""
    named = [os.path.normcase(part) for part in Path(a).parts]
    folder = [os.path.normcase(part) for part in Path(b).parts]
    count = 0
    while count < len(named) and count < len(folder) and named[-1 - count] == folder[-1 - count]:
        count += 1
    return count


def same_return(rolled_from: str, path: Path | str) -> bool:
    """Whether a Rolled From path names the return folder ``path``: the
    same path, or - once the clients root has moved and the recorded path
    names nothing - the same last :data:`ROLLED_FROM_TAIL` folder names.

    **Lexical, never resolved** (decision 131): this is layer 0 and reads
    no link. Rolled From is written absolute, so a root that moves leaves
    every one of them naming a folder that is no longer there; the three
    names below the root still say which return it was. The registry adds
    its own uniqueness rule across the whole practice; within one
    household, where the scaffold asks, ``<household>/<year>/<return>`` is
    unique by construction.
    """
    left = os.path.normcase(os.path.normpath(rolled_from))
    right = os.path.normcase(os.path.normpath(str(path)))
    return left == right or shared_tail(rolled_from, path) >= ROLLED_FROM_TAIL
