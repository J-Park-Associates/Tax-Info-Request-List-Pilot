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

**Where a step of a return may act is worded here once**
(:func:`place_problem`, decision 187). It is a question about the layout -
which of these folders belong to this return - so the filer asks it before
it carries a step out and the store asks it before it admits a record
line, and neither holds a copy of the answer. It returns a code naming the
class of problem, never the location, because the location is whatever a
record line said.

**Which household is this, and may this path exist, is worded here once**
(decision 188). One name rule (:func:`segment_problem`, after
:func:`normalised_name`) is what a household or return name may be,
wherever it is typed and wherever a record carries one; one comparison key
(:func:`name_key`) is how two names are compared wherever identity is
asked; the constructors refuse a name the rule refuses, or a year that is
not four digits; and one positional parser (:func:`place_of`) says what
kind of place a path is. This module is the only place a word of the
layout (:data:`CLIENTS_TREE`, :data:`PRIVATE_TREE`, the inbox, ``_Opened``)
is compared with a path; ``tests/test_layers.py`` holds every other module
to that. What must touch the disk - resolving a path a person typed, the
link check, the one door into the client tree - is ``tracker.door``, which
holds no rule of its own and asks this module.

The engagement remains the software's word for one return in one year: the
return folder *is* the engagement folder. "Household" is the new word.
"""

from __future__ import annotations

import functools
import ntpath
import os
import posixpath
import re
import unicodedata
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path, PurePath

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
#: The one file in the private tree that is not under a household (decision
#: 209): it names, in one line, the computer that runs the schedule for this
#: clients root. In the private tree because that tree is synced to every
#: desk that has the root and shared with no client, so every desk reads the
#: same answer. A file, not a folder: every walk of the private tree lists
#: folders only, so discovery never names it a folder that does not fit;
#: and the leading underscore keeps it clear of any household name.
DESIGNATION_FILENAME = "_Scheduling computer.txt"

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
#: failure at a filing deadline. The limit a measure is made against is
#: :func:`path_limit`, which is this figure everywhere but a Windows that
#: refuses long paths (pilot decision P29).
MAX_PATH_LENGTH = 260
#: What Windows keeps back from a folder's path for the 8.3 name of a file
#: inside it, where long paths are off: ``CreateDirectory`` refuses a
#: folder of ``MAX_PATH - 12`` characters or more (pilot decision P29).
SHORT_NAME_RESERVE = 12
#: What a folder the tracker writes into must leave, where long paths are
#: off, for the temporary name every write passes through beside its
#: target (``fsio.temp_path_for``, decision 155): the separator, one
#: character of the target's name - the least the temp is cut to - and
#: ``.<process id>.<tag>.tmp`` at its longest, a ten-digit process id
#: (``fsio.TEMP_NAME``). Twenty-six. The longest, not this process's own,
#: so a return's room is the same number at every run (pilot decision P29).
TEMP_NAME_RESERVE = len("/x." + "9" * 10 + "." + "f" * 8 + ".tmp")
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


#: What a drop whose name is nothing but invisible characters is recorded
#: as (:func:`recorded_name`).
NAMELESS = "unnamed"

def recorded_name(raw: object, fallback: str = NAMELESS) -> str:
    """A client's file or folder name as the record holds it: composed
    (NFC), with none of the characters the layout's one invisible set
    names (:func:`is_invisible`, decision 188) - no formatting, control,
    private-use or default-ignorable character - but for a space other than
    U+0020, which draws a space (decision 190).

    **Once, where a name enters the record.** A right-to-left override made
    ``W2<RLO>fdp.exe`` show as ``W2exe.pdf`` - a program dressed as a PDF on
    every screen that shows the name - and a zero-width space made two
    names that look alike two files. Decision 176 stripped them from an
    attachment's name only; a top-level drop, the subfolder it came from and
    its review copy kept them. This is the one normaliser of a client's
    name, and :func:`tracker.containers.safe_name` delegates its character
    stripping here; what counts as invisible is decided once, by
    :func:`is_invisible`, for this, the name rule and the name key alike.
    It is not a person's typed name (:func:`normalised_name`) nor a
    matcher's fold (:func:`tracker.names.normalise`).

    **The original keeps its raw name on disk** (standing rule 2), and a
    row's ``pbc_location`` keeps the raw path, so a row still finds its file.
    A name the record cannot hold as UTF-8 (an unpaired surrogate) is mended
    first. A name with nothing visible left - nothing but dots, spaces and
    underscores - is ``fallback``: :data:`NAMELESS` for a drop, and ``""``
    for :func:`~tracker.containers.safe_name`, which then names the part
    its own way. Arithmetic on a string: nothing here touches a disk.
    """
    text = str(raw or "").encode("utf-8", "replace").decode("utf-8")
    text = unicodedata.normalize("NFC", text)
    # The one invisible set (:func:`is_invisible`, decision 188) says what
    # draws nothing; a space other than U+0020 is in it but draws a space,
    # so it stays, as it always has in a client's file name.
    text = "".join(ch for ch in text if not is_invisible(ch) or unicodedata.category(ch) == "Zs")
    return text if text.strip("._ ") else fallback


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


# -------------------------------------------------------------- the names ----


class LayoutError(ValueError):
    """A name, a year or a path the layout refuses, with the sentence that
    says why. A ``ValueError``, so a caller that already answered a bad
    value keeps answering this one."""


#: The longest household or return name (decision 188): a pasted paragraph
#: is not a name. :data:`PATH_TOO_LONG` stays the final word on a whole path.
NAME_MAX_CHARS = 80
#: What a name the machine made begins with - hidden state, private
#: folders, an office lock file's, the sync client's ``.tmp.drive*``
#: staging. The walk passes over a folder named so without a word
#: (``tracker.registry``), and no household or return may be named so,
#: because the walk would never list it.
MACHINE_PREFIXES: tuple[str, ...] = (".", "_", "~$")

#: Characters Windows forbids in file and folder names, plus control
#: characters - the one list, for identifiers, for sanitising names and for
#: the name rule (moved here from ``tracker.records`` by decision 188).
_ILLEGAL_PUNCTUATION = '\\/:*?"<>|'
WINDOWS_ILLEGAL_CHARS = re.compile("[" + re.escape(_ILLEGAL_PUNCTUATION) + r"\x00-\x1f]")
WINDOWS_ILLEGAL_CHARS_TEXT = " ".join(_ILLEGAL_PUNCTUATION)


def recorded_subfolder_part(part: object) -> str:
    """One folder of a client's inbox subfolder as the record holds it: its
    :func:`recorded_name`, with every character Windows keeps out of a
    folder name made ``_``, as :func:`tracker.containers.safe_name` does.

    **One rule for the writer and the admission** (decision 190's review of
    the port, S2). On Linux or macOS a client can name an inbox folder
    ``Q1: bank``; the filer used to record it raw and the store's admission
    refused it, so the pass that had already moved the original raised.
    The filer now records each part through this, and the store admits a
    part exactly when this would not change it - so ``.``, ``..``, a part
    holding ``/``, ``\\`` or ``:``, and one with nothing visible are refused,
    because no writer wrote them. Not the household and return name rule
    (:func:`segment_problem`): a client may well name an inbox folder
    ``2025`` or ``_old``. The folder on disk keeps its name (standing rule
    2); the field is display only, and nothing joins it to a path.
    Idempotent: a part this returns comes back unchanged.
    """
    text = WINDOWS_ILLEGAL_CHARS.sub("_", recorded_name(part))
    return text if text.strip("._ ") else NAMELESS
#: The names Windows keeps for devices (decision 137, L6). A folder or a
#: file named one of them - with or without an extension, in any case - is
#: not a folder at all: ``NUL`` is the null device, ``COM1`` a serial port,
#: and a working copy, a household or a return named one could never
#: hold a document.
WINDOWS_RESERVED_NAMES: frozenset[str] = frozenset(
    {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
    | {f"COM{n}" for n in range(1, 10)}
    | {f"LPT{n}" for n in range(1, 10)}
    # The superscript digits Windows reserves too (the review's F6).
    | {f"{port}{digit}" for port in ("COM", "LPT") for digit in "¹²³"}
)
WINDOWS_RESERVED_NAMES_TEXT = ("CON, PRN, AUX, NUL, CONIN$, CONOUT$, COM1-COM9, LPT1-LPT9 "
                               "and their superscript-1, 2 and 3 forms")


def is_reserved_name(name: str) -> bool:
    """Whether Windows reads ``name`` as a device rather than a file or a
    folder: a reserved name, alone or before an extension (``nul.txt``),
    whatever its case and any spaces before the dot."""
    stem = str(name).split(".", 1)[0].rstrip(" ")
    return stem.upper() in WINDOWS_RESERVED_NAMES


#: The categories no name may hold a character of: control, format
#: (soft hyphen, the zero-width and direction marks, tags), surrogate,
#: private use, unassigned, and the line and paragraph separators.
_INVISIBLE_CATEGORIES = frozenset({"Cc", "Cf", "Cs", "Co", "Cn", "Zl", "Zp"})
#: The default-ignorable characters outside those categories: a
#: combining grapheme joiner, the Hangul and Khmer fillers, the Mongolian
#: variation selectors, the blank Braille pattern and the variation
#: selectors. Each draws nothing, so two names differing by one look alike.
_IGNORABLE_CODES = frozenset(
    {0x034F, 0x115F, 0x1160, 0x17B4, 0x17B5, 0x180B, 0x180C, 0x180D, 0x2800, 0x3164, 0xFFA0}
    | set(range(0xFE00, 0xFE10)) | set(range(0xE0100, 0xE01F0))
)


def is_invisible(char: str) -> bool:
    """Whether ``char`` draws nothing a person could read (decision 188, R2
    rule 5): a control, format, surrogate, private-use or unassigned
    character, a line or paragraph separator, a space other than U+0020,
    or a default-ignorable one. The one set: the name rule refuses them,
    the key removes them, and :func:`recorded_name` drops them - but for a
    non-plain space - from every client name the record keeps, an
    attachment's included (decision 190)."""
    category = unicodedata.category(char)
    return (category in _INVISIBLE_CATEGORIES or (category == "Zs" and char != " ")
            or ord(char) in _IGNORABLE_CODES)


#: Why the name rule refuses a household or return name (decision 188).
#: Each is said after :data:`NAME_REFUSED`, and each names a character by
#: its code point and Unicode name, never the name itself where a record
#: carried it - only a person's own typing is quoted.
NAME_EMPTY = "may not be empty"
NAME_TOO_LONG = "may be at most {limit} characters, got {n}"
NAME_FIRST_CHARACTER = "must begin with a letter or a digit"
NAME_TRAILING = "may not end with a dot or a space (Windows drops them from folder names)"
NAME_ILLEGAL = 'may not contain any of < > : " / \\ | ? * or a control character'
NAME_DEVICE = "may not be a name Windows keeps for a device ({names})"
NAME_INVISIBLE = "may not contain an invisible character ({character})"
NAME_COMPATIBILITY = ("may not contain a full-width or compatibility character ({character}); "
                      "type it plainly")
NAME_SCRIPTS = "may not mix letters of two alphabets ({first} and {second})"
NAME_LAYOUT_WORD = "may not be a name the folder layout uses itself"
#: How a typed name is refused: the name as typed, what it is, and why.
NAME_REFUSED = "'{typed}' is not a {what} name: {reason}"
#: The scripts that count as one alphabet in a name: Chinese characters
#: are written beside Japanese kana, and Korean beside Chinese characters.
_ONE_SCRIPT = {"HIRAGANA": "CJK", "KATAKANA": "CJK", "HANGUL": "CJK"}


def _character(char: str) -> str:
    """A character as a refusal names it: its code point and its name."""
    return f"U+{ord(char):04X} {unicodedata.name(char, 'UNNAMED')}"


def _script(char: str) -> str:
    """The alphabet a letter belongs to: the first word of its Unicode name,
    with Chinese, Japanese and Korean counted as one."""
    first = unicodedata.name(char, "UNNAMED").split()[0]
    return _ONE_SCRIPT.get(first, first)


def normalised_name(typed: object) -> str:
    """A name as a person typed it, normalised once at entry (decision 188):
    stripped, every run of white space one space, and Unicode NFC - so the
    ``ñ`` a Mac sends as two characters is the ``ñ`` Windows sends as one."""
    return unicodedata.normalize("NFC", " ".join(str(typed if typed is not None else "").split()))


def segment_problem(name: str) -> str | None:
    """Why ``name`` is not a household or return name, as a fixed phrase -
    or ``None`` where it is one (decisions 187 and 188).

    **The one name rule.** A household or a return is a folder name every
    path under it carries, in both trees, on every machine the Shared
    Drive syncs to, so it is exactly one folder name that Windows keeps as
    typed, that a person can read, and that is not a word of the layout
    itself. Refused, each with its own reason: empty or longer than
    :data:`NAME_MAX_CHARS`; beginning with anything but a letter or a digit
    (every name the walk passes over, :data:`MACHINE_PREFIXES`, begins so);
    ending with a dot or a space; holding a character Windows forbids or a
    control character; a device name; an invisible character
    (:func:`is_invisible` - refused, never stripped, because the name is
    what every path carries and a person is told why); a character not in
    NFKC form (full-width letters, ligatures, superscripts); letters of two
    alphabets; and a word of the layout, or four digits.

    The store's admission asks it of every household and return label a
    record line carries, blank excepted, so a forged label is refused at
    the gate by the rule a person's typing gets. The phrase names a
    character by code point, never the name, which may be whatever a line
    said.
    """
    text = str(name)
    if not text:
        return NAME_EMPTY
    if len(text) > NAME_MAX_CHARS:
        return NAME_TOO_LONG.format(limit=NAME_MAX_CHARS, n=len(text))
    if WINDOWS_ILLEGAL_CHARS.search(text) or any(unicodedata.category(c) == "Cc" for c in text):
        return NAME_ILLEGAL
    if (hidden := next((c for c in text if is_invisible(c)), None)) is not None:
        return NAME_INVISIBLE.format(character=_character(hidden))
    if not text[0].isalnum():
        return NAME_FIRST_CHARACTER
    if text.endswith((".", " ")):
        return NAME_TRAILING
    if is_reserved_name(text):
        return NAME_DEVICE.format(names=WINDOWS_RESERVED_NAMES_TEXT)
    if not unicodedata.is_normalized("NFKC", text):
        odd = next((c for c in text if unicodedata.normalize("NFKC", c) != c),
                   next((c for c in text if unicodedata.combining(c)), text[0]))
        return NAME_COMPATIBILITY.format(character=_character(odd))
    scripts: list[str] = []
    for char in text:
        if char.isalpha() and (script := _script(char)) not in scripts:
            scripts.append(script)
    if len(scripts) > 1:
        return NAME_SCRIPTS.format(first=scripts[0].title(), second=scripts[1].title())
    if is_year_folder(text) or name_key(text) in _LAYOUT_WORD_KEYS:
        return NAME_LAYOUT_WORD
    return None


def checked_name(typed: object, what: str) -> str:
    """The name a person typed, normalised - or a :class:`LayoutError`
    saying which name and why (``what`` is ``household`` or ``return``).
    Every box and command line a name is typed in asks this, so one rule
    gives one sentence wherever a name is typed."""
    name = normalised_name(typed)
    if (reason := segment_problem(name)) is not None:
        raise LayoutError(NAME_REFUSED.format(typed=name, what=what, reason=reason))
    return name


#: The look-alikes the comparison key folds (decision 188, R3): the
#: Cyrillic, Greek and Latin letters Unicode's confusables data (UTS #39)
#: maps to one basic Latin letter and the firm's fonts draw identically,
#: the dashes and the apostrophes. A fixed table, stated here, because
#: anything wider needs the confusables file, a dependency the firm does
#: not take. It errs wide: over-folding costs a refusal a person answers
#: by typing a fuller name; under-folding is two households for one family.
LOOK_ALIKES: dict[str, str] = {
    # Cyrillic
    "\u0410": "A", "\u0430": "a", "\u0412": "B", "\u0415": "E", "\u0435": "e",
    "\u0405": "S", "\u0455": "s", "\u0406": "I", "\u0456": "i", "\u0408": "J",
    "\u0458": "j", "\u041a": "K", "\u041c": "M", "\u041d": "H", "\u041e": "O",
    "\u043e": "o", "\u0420": "P", "\u0440": "p", "\u0421": "C", "\u0441": "c",
    "\u0422": "T", "\u0443": "y", "\u0425": "X", "\u0445": "x", "\u04ae": "Y",
    "\u051b": "q", "\u051d": "w", "\u04bb": "h", "\u0501": "d", "\u04cf": "l",
    "\u04c0": "I",
    # ... and the capitals of the lowercase entries above (the review's M1)
    "\u0423": "Y", "\u051a": "Q", "\u051c": "W", "\u04ba": "H", "\u0500": "D",
    # Greek
    "\u0391": "A", "\u0392": "B", "\u0395": "E", "\u0396": "Z", "\u0397": "H",
    "\u0399": "I", "\u039a": "K", "\u039c": "M", "\u039d": "N", "\u039f": "O",
    "\u03bf": "o", "\u03a1": "P", "\u03a4": "T", "\u03a5": "Y", "\u03a7": "X",
    "\u03bd": "v",
    # Latin, with the capitals of the two that have one
    "\u0131": "i", "\u0251": "a", "\u0261": "g", "\u2c6d": "A", "\ua7ac": "G",
    # Dashes and apostrophes
    "\u2010": "-", "\u2011": "-", "\u2012": "-", "\u2013": "-", "\u2014": "-",
    "\u2015": "-", "\u2212": "-", "\ufe63": "-", "\uff0d": "-",
    "\u2018": "'", "\u2019": "'", "\u02bc": "'", "\u2032": "'",
}
#: What the key folds after case: the ASCII look-alikes of ``l`` and ``o``.
_ASCII_LOOK_ALIKES = str.maketrans({"1": "l", "i": "l", "|": "l", "0": "o"})


def name_key(name: str) -> str:
    """The one key two household or return names are compared by (decision
    188, R3): NFKC; every invisible character removed; white space
    collapsed; :data:`LOOK_ALIKES` folded and case folded, twice; ``1``, ``i`` and
    ``|`` folded to ``l``, ``0`` to ``o`` and ``rn`` to ``m``; NFKC again.

    Two names with one key are one name: household uniqueness, a return's
    within its household-year, a feed, the rollover's ``--only`` and the
    claim a record makes about its folder all ask it. The rule refuses a
    mixed-script name at entry, so the fold is for what the rule cannot
    see - a name all in one look-alike script, and names on disk from
    before the rule. :func:`lock_order_key` is an order, not an identity,
    and keeps its own.
    """
    text = unicodedata.normalize("NFKC", str(name))
    text = " ".join("".join(c for c in text if not is_invisible(c)).split())
    # The table, case, the table again and case again (the review's M1): a
    # capital only the table knows (Cyrillic VE is B, its lowercase is no
    # b) is folded before case can lose it, a letter case turns into one the
    # table knows (a narrow o, a capital the table does not list) is folded
    # after - so the key of a key is the key.
    for _ in range(2):
        text = "".join(LOOK_ALIKES.get(c, c) for c in text).casefold()
    text = text.translate(_ASCII_LOOK_ALIKES).replace("rn", "m")
    return unicodedata.normalize("NFKC", text)


#: The words of the layout itself: no household or return is named one.
_LAYOUT_WORD_KEYS = frozenset(name_key(word) for word in (
    CLIENTS_TREE, PRIVATE_TREE, INBOX_DIR_NAME, PREPARED_DIR_NAME, REVIEW_DIR_NAME,
    OPENED_DIR_NAME))


# -------------------------------------------------------------- the trees ----


def _named(name: str, what: str) -> str:
    """``name``, when the name rule accepts it as a folder a constructor
    may build - else the :class:`LayoutError` saying why."""
    if (reason := segment_problem(name)) is not None:
        raise LayoutError(NAME_REFUSED.format(typed=name, what=what, reason=reason))
    return name


def _year(year: object) -> int:
    """``year``, when it is an ``int`` of four digits (a ``bool`` is not)."""
    if type(year) is not int or not 1000 <= year <= 9999:
        raise LayoutError(f"{year!r} is not a tax year of four digits")
    return year


def clients_tree_of(root: Path | str) -> Path:
    """The tree a client is shared, under a clients root. The one place
    ``root / CLIENTS_TREE`` is spelled (decision 188)."""
    return Path(root) / CLIENTS_TREE


def private_tree_of(root: Path | str) -> Path:
    """The firm's own tree, under a clients root."""
    return Path(root) / PRIVATE_TREE


def designation_file(root: Path | str) -> Path:
    """The file naming the computer that runs the schedule for this clients
    root (decision 209): the one spelling of its path."""
    return private_tree_of(root) / DESIGNATION_FILENAME


def client_household_dir(root: Path | str, household: str) -> Path:
    """The household's folder in the tree a client is shared.

    Like every constructor here it refuses a name the name rule refuses
    (decision 188, :class:`LayoutError`): a folder already on disk with
    such a name is a misfit discovery lists, and never reaches here."""
    return clients_tree_of(root) / _named(household, "household")


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
    return client_household_dir(root, household) / year_folder_name(_year(year))


def private_household_dir(root: Path | str, household: str) -> Path:
    """The household's folder in the tree that is never shared: its record."""
    return private_tree_of(root) / _named(household, "household")


def return_dir_for(root: Path | str, household: str, year: int, return_name: str) -> Path:
    """One return's folder - the engagement folder - under its year."""
    return (private_household_dir(root, household) / year_folder_name(_year(year))
            / _named(return_name, "return"))


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
    name disagrees with its record pauses its household (decision 188,
    ``tracker.households.pause_of``).
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


# ------------------------------------------------- what kind of place ----

#: The kinds of place :func:`place_of` names (decision 188).
ROOT = "root"
CLIENTS = "clients-tree"
CLIENT_HOUSEHOLD = "client-household"
INBOX = "inbox"
IN_INBOX = "in-inbox"
ORIGINALS = "originals"
IN_ORIGINALS = "in-originals"
PRIVATE = "private-tree"
HOUSEHOLD = "household"
YEAR = "year"
OPENED = "opened"
IN_OPENED = "in-opened"
RETURN = "return"
IN_RETURN = "in-return"
#: Under the root, and fitting none of the places above.
MISPLACED = "misplaced"
#: Not under the root at all.
OUTSIDE = "outside"
#: Every kind of place in the tree a client is shared.
CLIENT_KINDS = frozenset({CLIENTS, CLIENT_HOUSEHOLD, INBOX, IN_INBOX, ORIGINALS, IN_ORIGINALS})

#: What a path that is not a return's folder is told (decision 137, L1;
#: moved here from the API by decision 188). A year folder or a household
#: folder holds a journal too - the household's own record - so a folder
#: is a return by where it sits, as discovery reads it.
NOT_A_RETURN = ("{name} is not a return's folder (a return sits at <clients root>\\{tree}"
                "\\<household>\\<year>\\<return>); it is not an engagement")
#: What a path that is not a household's folder is told (decision 176).
NOT_A_HOUSEHOLD = ("{name} is not a household's folder (a household sits at <clients root>\\{tree}"
                   "\\<household>); nothing was changed")
#: What a write the one door refuses is told (decision 188, R9): only a
#: household's own client folder, its inbox and its year folders of
#: originals are places the tracker writes in the tree a client is shared.
OUTSIDE_CLIENT_PLACE = ("{path} is not a place the tracker writes for the household {household} "
                        "in the tree its client is shared; nothing was written")


#: What a household whose client folder is gone, when its record shows it
#: had one, is told by every writer (SPEC-162 ruling 2, kept by decision
#: 188): the pass, a new return, every form of Roll Forward. Nothing is
#: made again under the old name.
CLIENT_FOLDER_MISSING = ("`Clients\\{name}` is missing. Was the household renamed or moved? "
                         "Give its client folder back the name `{name}`.")


@dataclass(frozen=True, slots=True)
class Place:
    """What kind of place a path is under a clients root, and the names it
    has there. ``household``, ``year`` and ``return_name`` are the path's
    own spellings, filled as far as the kind reaches."""

    kind: str
    household: str = ""
    year: int | None = None
    return_name: str = ""


def _parts(path: Path | str) -> tuple[str, ...]:
    """A path's parts after lexical normalisation, in its own spelling."""
    return PurePath(os.path.normpath(str(path))).parts


def parts_below(outer: Path | str, inner: Path | str) -> tuple[str, ...] | None:
    """The names ``inner`` has below ``outer`` - ``()`` for ``outer``
    itself - or ``None`` when ``inner`` is not under it.

    **Lexical**, both normalised, the parts compared as the filesystem
    compares them (``os.path.normcase``); a caller that must see through a
    link resolves first. The one place a path is tested for lying under
    another (decision 188): every ``relative_to`` it replaces answered the
    same question with its own rule about case and ``..``.
    """
    top, below = _parts(outer), _parts(inner)
    if outer in ("", ".") or top == (os.curdir,):
        top = ()
    if len(below) < len(top) or [os.path.normcase(p) for p in below[:len(top)]] != [
            os.path.normcase(p) for p in top]:
        return None
    rest = below[len(top):]
    return None if os.pardir in rest else rest


def place_of(root: Path | str, path: Path | str) -> Place:
    """What kind of place ``path`` is under the clients root ``root``
    (decision 188, R5) - pure and positional, the caller passing both
    already resolved when a link matters.

    The client tree: :data:`CLIENTS`, a :data:`CLIENT_HOUSEHOLD`, its
    :data:`INBOX` or a year's :data:`ORIGINALS` and anything
    :data:`IN_INBOX` or :data:`IN_ORIGINALS`. The private tree:
    :data:`PRIVATE`, a :data:`HOUSEHOLD`, a :data:`YEAR`, a year's
    :data:`OPENED` and what is :data:`IN_OPENED`, a :data:`RETURN` and what
    is :data:`IN_RETURN`. :data:`ROOT` itself; :data:`MISPLACED` for what
    is under the root and fits none of them, and :data:`OUTSIDE` for what
    is not under it, a ``..`` left after normalisation included. The
    trees' and the inbox's names compare as the filesystem does
    (``os.path.normcase``).
    """
    below = parts_below(root, path)
    if below is None:
        return Place(OUTSIDE)
    if not below:
        return Place(ROOT)
    same = [os.path.normcase(part) for part in below]
    depth = len(below)
    household = below[1] if depth > 1 else ""
    if same[0] == os.path.normcase(CLIENTS_TREE):
        if depth == 1:
            return Place(CLIENTS)
        if depth == 2:
            return Place(CLIENT_HOUSEHOLD, household)
        if same[2] == os.path.normcase(INBOX_DIR_NAME):
            return Place(INBOX if depth == 3 else IN_INBOX, household)
        if is_year_folder(below[2]):
            return Place(ORIGINALS if depth == 3 else IN_ORIGINALS, household, int(below[2]))
        return Place(MISPLACED, household)
    if same[0] == os.path.normcase(PRIVATE_TREE):
        if depth == 1:
            return Place(PRIVATE)
        if depth == 2:
            return Place(HOUSEHOLD, household)
        if not is_year_folder(below[2]):
            return Place(MISPLACED, household)
        year = int(below[2])
        if depth == 3:
            return Place(YEAR, household, year)
        if same[3] == os.path.normcase(OPENED_DIR_NAME):
            return Place(OPENED if depth == 4 else IN_OPENED, household, year)
        return Place(RETURN if depth == 4 else IN_RETURN, household, year, below[3])
    return Place(MISPLACED)


def same_folder_name(a: str, b: str) -> bool:
    """Whether two names in one folder name one folder, as Windows compares
    them: without case. For the layout's own words (the review folder);
    two households or returns are compared by :func:`name_key`."""
    return str(a).casefold() == str(b).casefold()


def names_one_folder(a: str, b: str) -> bool:
    """Whether two names in one folder are one folder as the file system
    compares them (``os.path.normcase``). What says a client folder is a
    household's own (the re-check of decision 188, R1): the comparison key
    refuses a new name, it never identifies a folder on the disk."""
    return os.path.normcase(str(a)) == os.path.normcase(str(b))


def tree_of(root: Path | str, path: Path | str) -> str | None:
    """The tree - :data:`CLIENTS_TREE` or :data:`PRIVATE_TREE`, as the
    layout spells it - that ``path`` lies in or is, under ``root``; ``None``
    for anything else."""
    below = parts_below(root, path)
    if not below:
        return None
    for tree in (CLIENTS_TREE, PRIVATE_TREE):
        if os.path.normcase(below[0]) == os.path.normcase(tree):
            return tree
    return None


def return_at(root: Path | str, path: Path | str) -> tuple[str, int, str]:
    """The household, year and return name of the return folder ``path``
    is, or a :class:`LayoutError` (:data:`NOT_A_RETURN`).

    Only a :data:`RETURN` is one: a folder in the client tree - where a
    client can write, and where a planted journal would otherwise read as
    a prior - is never one, nor is anything above or below a return."""
    place = place_of(root, path)
    if place.kind != RETURN:
        raise LayoutError(NOT_A_RETURN.format(name=Path(path).name or path, tree=PRIVATE_TREE))
    assert place.year is not None
    return place.household, place.year, place.return_name


def household_at(root: Path | str, path: Path | str) -> str:
    """The household name of the household folder ``path`` is, or a
    :class:`LayoutError` (:data:`NOT_A_HOUSEHOLD`)."""
    place = place_of(root, path)
    if place.kind != HOUSEHOLD:
        raise LayoutError(NOT_A_HOUSEHOLD.format(name=Path(path).name or path, tree=PRIVATE_TREE))
    return place.household


# ------------------------------------- where a step of a return may act ----

#: Why :func:`place_problem` refuses a location (decision 187). A code and
#: never the location itself, so a caller may put it in a sentence a person
#: reads without quoting whatever a record line said.
STEP_BLANK = "blank"
#: Absolute, a drive or a share.
STEP_ABSOLUTE = "absolute"
#: Climbs above the clients root, whatever it names after that.
STEP_ABOVE_ROOT = "above-root"
#: The return's own path is not ``.../PRIVATE_TREE/<household>/<year>/<return>``.
STEP_NOT_A_RETURN = "not-a-return"
#: Inside the root but in none of the places a step of this return goes.
STEP_NOT_A_PLACE = "not-a-place"
#: A write into another household's client folder.
STEP_OTHER_HOUSEHOLD = "other-household"
#: A write into another year's ``_Opened``.
STEP_OTHER_YEAR = "other-year"
#: A removal in the client tree (decision 187, the review's M4): the only
#: files a step ever removes are the firm's own copies, so a removal of a
#: client's original or of anything in their inbox is never a step.
STEP_CLIENT_TREE = "client-tree"
#: Every code :func:`place_problem` returns.
STEP_PROBLEMS = frozenset({STEP_BLANK, STEP_ABSOLUTE, STEP_ABOVE_ROOT, STEP_NOT_A_RETURN,
                           STEP_NOT_A_PLACE, STEP_OTHER_HOUSEHOLD, STEP_OTHER_YEAR,
                           STEP_CLIENT_TREE})


def place_problem(return_dir: Path | str, location: str, *, writes: bool,
                  removes: bool = False) -> str | None:
    """Why a location a step of this return names is not where such a step
    may act, as one of the ``STEP_`` codes - or ``None`` where it may
    (decision 180; worded here once by decision 187).

    Every step a decision writes is relative to the return whose record
    holds it, and every one stays in these places, read off the layout:
    under the return itself; under its household's ``_Opened`` of a year -
    its own year's where the step writes, any year's where it reads,
    because a person may hand an attachment parked in one open year to a
    return of the next (decision 129); and in the client tree only under
    some household's inbox or year folder - **this** return's household
    where the step writes (a move's or a copy's destination), any
    household where it reads, because a return a drop folder feeds takes
    its original out of another household's inbox. Nothing else - not an
    absolute path, a drive, a share, another return, the private tree's own
    files or anything above the clients root - is a place a step goes, so a
    line the record did not get from this code, however it got there,
    moves nothing.

    **A removal is narrower** (``removes``, which implies ``writes``;
    decision 187, the review's M4): it may act only under the return itself
    or its own year's ``_Opened``. Every removal the tracker writes takes
    away one of the firm's own copies; a removal naming the client tree is
    :data:`STEP_CLIENT_TREE`, because originals are never altered. This
    narrows the rule decision 180 wrote, which let a removal act wherever a
    move may write.

    **Lexical and positional, and it touches no disk**, as :func:`locate`
    is: the filer's link check guards what lies behind a junction, and this
    guards what a line says. The location is walked from the return's own
    four folders below the root, so ``return_dir`` may be absolute or
    relative to the clients root (the store's key) and the answer is the
    same; a ``..`` still leading after normalisation has climbed above the
    root, and is :data:`STEP_ABOVE_ROOT` whatever it names after.
    """
    if not location:
        return STEP_BLANK
    if any(isabs(location) for isabs in (ntpath.isabs, posixpath.isabs)) or ntpath.splitdrive(location)[0]:
        return STEP_ABSOLUTE
    # The return's own four folders, read as if they stood at a root of
    # their own: the answer is the same for a return named absolutely and
    # one named relative to the root (the store's key).
    own_parts = _parts(return_dir)[-4:]
    if len(own_parts) < 4 or any(os.path.isabs(part) for part in own_parts):
        return STEP_NOT_A_RETURN
    own = place_of("", os.path.join(*own_parts))
    if own.kind != RETURN:
        return STEP_NOT_A_RETURN
    at = place_of("", os.path.join(*own_parts, location))
    if at.kind == OUTSIDE:
        return STEP_ABOVE_ROOT

    def same(a: str, b: str) -> bool:
        return os.path.normcase(a) == os.path.normcase(b)

    if at.kind == IN_RETURN and same(at.household, own.household) and at.year == own.year \
            and same(at.return_name, own.return_name):
        return None
    if at.kind == IN_OPENED and same(at.household, own.household):
        return None if at.year == own.year or not writes else STEP_OTHER_YEAR
    if at.kind in (IN_INBOX, IN_ORIGINALS):
        if removes:
            return STEP_CLIENT_TREE
        return None if not writes or same(at.household, own.household) else STEP_OTHER_HOUSEHOLD
    return STEP_NOT_A_PLACE


def deepest_path_length(return_dir: Path | str, subpaths: Iterable[str]) -> int:
    """The longest path the tracker would write under ``return_dir``, in
    characters, over ``subpaths``.

    What creation measures against :func:`path_limit` before a folder
    is made: the deepest working copy a request list implies. ``0`` for no
    subpaths at all, because a return with no request has nothing to write.
    """
    lengths = [len(str(Path(return_dir) / sub)) for sub in subpaths]
    return max(lengths, default=0)


@functools.cache
def _long_paths_on() -> bool:
    """Whether Windows lets this process past ``MAX_PATH``: the answer of
    ``RtlAreLongPathsEnabled``, which is the registry's
    ``LongPathsEnabled`` and the program's own manifest together.

    Asked of ntdll rather than read from the registry because the registry
    alone is half the answer: a program not built long-path aware is held
    to ``MAX_PATH`` whatever the registry says, and the packaged app and
    ``python.exe`` are different programs. Windows reads the setting once
    per process, so it is asked once and kept. Anything that goes wrong
    asking - no such function before Windows 10 1607, which had no long
    paths to give - reads as off, the stricter answer: a limit measured
    too short cuts a name a character early, one measured too long is the
    ``WinError 206`` this exists to prevent.
    """
    try:
        import ctypes

        ask = ctypes.WinDLL("ntdll").RtlAreLongPathsEnabled
        ask.argtypes = []
        ask.restype = ctypes.c_ubyte          # a BOOLEAN: the low byte only
        return bool(ask())
    except (ImportError, OSError, AttributeError):
        return False


def short_paths() -> bool:
    """True on a Windows that holds this process to ``MAX_PATH`` - long
    paths off, the Windows default (pilot decision P29).

    Read when called, so a test stands in for either setting on any
    machine by replacing this function."""
    return os.name == "nt" and not _long_paths_on()


def path_limit() -> int:
    """The longest path, in characters, the tracker may write a file at:
    the one limit every measure of room is made against (decision 131).

    :data:`MAX_PATH_LENGTH` - except where :func:`short_paths` says long
    paths are off. There ``MAX_PATH`` counts the terminating null, so a
    file path of 260 characters is refused (``WinError 206``) and 259 is
    the longest Windows opens. Pilot decision P29 found the 260 the room
    rule allowed failing on a default Windows as "could not be filed
    (FileNotFoundError)" instead of the room's own sentence. The figure is
    not lowered everywhere: Linux, macOS and a long-path Windows write a
    path of 260 characters, and every return measured there keeps the
    room it had.
    """
    return MAX_PATH_LENGTH - 1 if short_paths() else MAX_PATH_LENGTH


def folder_need(folder: Path | str) -> int:
    """What a folder the tracker makes and writes into costs against
    :func:`path_limit`: its length and the larger of
    :data:`SHORT_NAME_RESERVE` and :data:`TEMP_NAME_RESERVE` where long
    paths are off, else ``0`` - a folder is then never deeper than the
    files it holds.

    Windows refuses to *make* a folder of 248 characters or more with long
    paths off although it opens a file of 259, so a return whose review
    folder is 249 characters passed the room rule (its floor, a review
    copy, is 260) and then failed its scaffold with ``WinError 206``; and a
    review copy that fits is written through a temp up to twenty-four
    characters longer, which Windows refused as well (pilot decision P29).
    Measured this way a folder fits exactly when Windows will make it and
    every write into it, its temp included."""
    if not short_paths():
        return 0
    return len(str(folder)) + max(SHORT_NAME_RESERVE, TEMP_NAME_RESERVE)


def limit_for(extension: str) -> int:
    """The longest path a working copy with ``extension`` may have: the
    shortest of Windows's limit (:func:`path_limit`) and any reader's
    (:data:`OPEN_LIMITS`).

    ``xlsx``, ``.XLSX`` and ``.xlsx`` are one extension."""
    limit = path_limit()
    return min(limit, OPEN_LIMITS.get(extension.lower().lstrip("."), limit))


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
