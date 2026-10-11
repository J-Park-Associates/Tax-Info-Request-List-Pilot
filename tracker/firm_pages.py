"""The firm lists cut into pages (P278, ``pilot/SPEC-ui-menu-speed.md`` section 4).

**Why this exists.** The engine used to send the window the firm's whole
answer - every return, every waiting file and its path, several megabytes at
2,000 returns - and the window built, sorted and filtered all of it before it
showed a page of 50. Now the engine does the narrowing, the ordering and the
cutting, and sends one page, the firm's totals and each return's counts. The
window draws what it is given in the order it is given: it filters nothing,
sorts nothing and slices nothing.

**What it decides, and what it does not.** This module decides no count and
reads no record. :func:`tracker.api._cmd_firm` builds the whole reply exactly
as it always has (the walk, the cache, the totals) and hands it here with the
names that walk saw; ``page`` filters it, orders it, takes the page asked for
and answers. Every word an order key depends on - the status words, the
paused word, the held word, the stage words, the reasons' short labels - is
handed in by the API from the same vocabulary the window reads, never typed
a second time here.

**The view.** A fresh ``firm`` saves its whole answer - *the view* - in the
data folder (:data:`PAGES_FILENAME`) under a token, and answers one page of
it. A page turn, a column header, a tab, a reason card, the Clients switch or
a Client Type asks again with that token; :func:`load_view` reads the saved
view back and the engine pages it: no walk, no fingerprint, no record read.
The engine keeps nothing between commands - the view is a file - so this works
in the long-lived engine of P276, in a process of its own, and after the
engine started afresh. A token that no longer matches (another fresh
``firm`` saved a newer view; the program, the day, the clients folder or the
data folder changed; the file is gone or damaged) is answered by a fresh
``firm`` with a new token: slower, never wrong, and every page of one list
is from one moment.

Like ``firm-view.json`` the file holds household names, return folders and the
names of files waiting for a person; it lives only in the data folder
(decision 186), is never synced, and deleting it is always safe. A damaged
one is not used and is said on the error log by its class, never its words,
as the cache's is (:func:`tracker.firm_cache.read_kept`).

**The orders are the window's, moved here unchanged.** The usual order of
each list and each header's key are what ``pages.js`` computed before:
urgency, the larger count, then the words; blanks last in either direction;
a tie keeps the usual order. Text compares as the window's collator did
(``Intl.Collator(undefined, {numeric: true})``, N1): :func:`name_order`.
Python has no copy of the collator's tables, so for names written in letters
outside the Latin alphabet the order may differ slightly from the one the
window used to give (Jason's question E, SPEC section 8); every page of one
list agrees with every other. ``tests/samples.py`` keeps one made-up list
with its order, held by both languages' tests.

Layer 0: the standard library, ``settings``, ``fsio``, ``errors``,
``layout`` (the return naming pattern) and ``firm_cache``'s head and file
readers; the API hands it the words. It has no command line.
"""

from __future__ import annotations

import functools
import json
import logging
import re
import secrets
import unicodedata
from dataclasses import dataclass, replace
from pathlib import Path
from typing import NamedTuple

from tracker import errors, firm_cache, layout, settings
from tracker.fsio import write_text_atomically

log = logging.getLogger(__name__)

#: The view file's name in the data folder, beside the store and ``firm-view.json``.
PAGES_FILENAME = "firm-pages.json"

#: The shape of the view file; it rises only when this file's own shape changes.
FORMAT = 1

#: Rows (files, on Needs Review) in a page (P174). The engine's, not the window's:
#: Compact Rows changes how many rows fit on screen, not how many a page holds.
PAGE_SIZE = 50

#: The four firm lists, by the names the window's ``PAGES_COLUMNS`` gives them.
LISTS = ("overview", "needs_review", "reminders", "clients")

#: The cells each list's header can order by (the window's ``PAGES_COLUMNS``,
#: less the cells whose header has no word).
CELLS = {
    "overview": ("year", "taxpayer", "form", "status", "end"),
    "needs_review": ("name", "detail", "status", "end"),
    "reminders": ("year", "taxpayer", "form", "status", "end"),
    "clients": ("name", "detail", "status"),
}

#: The Overview's tabs (P145).
TABS = ("all", "need", "waiting")

#: A day later than any real one, standing in for "no date" in the usual orders.
LATE = "9999-99-99"

#: Urgency, the order the app already uses (SPEC-lists 3): a return that cannot
#: be read or a paused household first, then what needs a person, what waits on
#: the taxpayer, what is complete.
URGENCY = {"problem": 0, "needs": 1, "waiting": 2, "done": 3, "plain": 4}


class PageAskError(Exception):
    """The ask names a list, a cell, a filter or a page the engine does not
    have. The API says it as :data:`tracker.api.FIRM_PAGE_REFUSED`; no page
    is ever guessed."""


@dataclass(frozen=True)
class Ask:
    """One page of one list, as the window asks for it."""

    list: str
    at: int
    order: tuple[str, int] | None
    filter: dict
    view: str


def ask_of(spec: dict, client_types: dict) -> Ask | None:
    """The page ``spec`` asks for, or ``None`` when it asks for none (today's
    whole reply). ``client_types`` is the vocabulary's table of Client Types
    (key -> forms), against which a Client Type filter is checked. Anything
    that is not exactly the shape of SPEC section 4.2 is a
    :class:`PageAskError`."""
    if not spec:
        return None
    if set(spec) - {"page", "view"} or "page" not in spec:
        raise PageAskError("keys")
    view = spec.get("view", "")
    if not isinstance(view, str):
        raise PageAskError("view")
    want = spec["page"]
    if not isinstance(want, dict) or set(want) - {"list", "at", "order", "filter"} or "list" not in want:
        raise PageAskError("page")
    name = want["list"]
    if name not in LISTS:
        raise PageAskError("list")
    at = want.get("at", 0)
    if isinstance(at, bool) or not isinstance(at, int) or at < 0:
        raise PageAskError("at")
    order = want.get("order")
    if order is not None:
        if (not isinstance(order, dict) or set(order) != {"cell", "dir"} or order["cell"] not in CELLS[name]
                or isinstance(order["dir"], bool) or order["dir"] not in (1, -1)):
            raise PageAskError("order")
        order = (order["cell"], int(order["dir"]))
    return Ask(name, at, order, _filter_of(name, want.get("filter", {}), client_types), view)


def _filter_of(name: str, given: object, client_types: dict) -> dict:
    """The list's filter, whole: every key it has, defaulted, and no other."""
    if not isinstance(given, dict):
        raise PageAskError("filter")
    if name == "overview":
        if set(given) - {"tab"} or given.get("tab", "all") not in TABS:
            raise PageAskError("filter")
        return {"tab": given.get("tab", "all")}
    if name == "needs_review":
        reason = given.get("reason", "")
        if set(given) - {"reason"} or not isinstance(reason, str):
            raise PageAskError("filter")
        return {"reason": reason}
    if name == "reminders":
        if given:
            raise PageAskError("filter")
        return {}
    everyone, kind = given.get("all", False), given.get("type", "")
    if set(given) - {"all", "type"} or not isinstance(everyone, bool) or not isinstance(kind, str) \
            or (kind and kind not in client_types):
        raise PageAskError("filter")
    return {"all": everyone, "type": kind}


# ---------------------------------------------------------------- text order ----

#: The collator's order for the ASCII marks (ICU's root order, which the
#: window's ``Intl.Collator`` uses): white space, then punctuation, then
#: symbols, then currency, then digits, then letters. Read from the collator
#: itself and held by ``tests/test_firm_pages.py``.
_SPACES = "\t\n\x0b\x0c\r  "
_PUNCTUATION = "_-,;:!?.'\"()[]{}@*/\\&#%"
_SYMBOLS = "`^+<=>|~"
_CURRENCY = "$"

#: Letters the collator files as another letter with a mark, or as two letters.
_ALIASES = {"ø": ("o", "̸"), "đ": ("d", "̵"), "ł": ("l", "̷"), "ð": ("d", "̵"),
            "æ": ("ae", ""), "œ": ("oe", ""), "ß": ("ss", "")}

#: The collator's order of the combining marks U+0300-U+036F (read from it).
_MARK_ORDER = {mark: rank for rank, mark in enumerate(
    (0x34f, 0x332, 0x313, 0x343, 0x314, 0x301, 0x341, 0x300, 0x340, 0x306, 0x302, 0x30c, 0x30a, 0x342, 0x308, 0x344,
     0x30b, 0x303, 0x307, 0x338, 0x327, 0x328, 0x304, 0x30d, 0x30e, 0x312, 0x315, 0x31a, 0x33d, 0x33e, 0x33f, 0x346,
     0x34a, 0x34b, 0x34c, 0x350, 0x351, 0x352, 0x357, 0x35b, 0x35d, 0x35e, 0x316, 0x317, 0x318, 0x319, 0x31c, 0x31d,
     0x31e, 0x31f, 0x320, 0x329, 0x32a, 0x32b, 0x32c, 0x32f, 0x333, 0x33a, 0x33b, 0x33c, 0x347, 0x348, 0x349, 0x34d,
     0x34e, 0x353, 0x354, 0x355, 0x356, 0x359, 0x35a, 0x35c, 0x35f, 0x362, 0x336, 0x337, 0x335, 0x305, 0x309, 0x30f,
     0x310, 0x311, 0x31b, 0x321, 0x322, 0x323, 0x324, 0x325, 0x326, 0x32d, 0x32e, 0x330, 0x331, 0x334, 0x339, 0x345,
     0x358, 0x360, 0x361, 0x363, 0x368, 0x369, 0x364, 0x36a, 0x365, 0x36b, 0x366, 0x36c, 0x36d, 0x367, 0x36e, 0x36f))}


def _mark_rank(mark: str) -> int:
    code = ord(mark)
    return _MARK_ORDER.get(code, 1000 + code)


def name_order(text: str) -> tuple:
    """The key that orders ``text`` as the window's collator did
    (``Intl.Collator(undefined, {numeric: true})``): runs of digits compare as
    numbers; the rest compares first without accents or case (white space,
    then punctuation, then symbols, then currency, then digits, then
    letters), then by accents, then lower case before upper. Strings the
    collator calls equal give equal keys, so a stable sort keeps their
    order, as the window's did.

    Letters outside the Latin alphabet compare by code point within their
    class: the collator's own tables are not copied here, so such names may
    order slightly differently from the window's old order (SPEC section 8,
    question E). Every page of one list agrees with every other."""
    primary: list[tuple] = []
    secondary: list[tuple] = []
    tertiary: list[int] = []
    text = unicodedata.normalize("NFD", text)
    i = 0
    while i < len(text):
        ch = text[i]
        if unicodedata.category(ch) == "Nd":
            j = i
            while j < len(text) and unicodedata.category(text[j]) == "Nd":
                j += 1
            digits = str(int("".join(str(unicodedata.decimal(c)) for c in text[i:j]) or "0")) if j - i < 4000 \
                else text[i:j].lstrip("0") or "0"
            primary.append((4, len(digits), digits))
            secondary.append(())
            tertiary.append(0)
            i = j
            continue
        i += 1
        if unicodedata.combining(ch):
            if secondary:
                secondary[-1] = (*secondary[-1], _mark_rank(ch))
            continue
        upper = int(ch != ch.lower())
        low = ch.lower()
        if low in _ALIASES:
            base, mark = _ALIASES[low]
            primary.extend((5, letter) for letter in base)
            secondary.extend([((_mark_rank(mark),) if mark else ())] + [()] * (len(base) - 1))
            # A ligature sorts after its spelled-out letters and their cases ("ss" < "SS" < "ß"); a letter with a mark is its base's by case.
            tertiary.extend([upper + (0 if mark else 2)] + [0 if mark else 2 + upper] * (len(base) - 1))
            continue
        if ch in _SPACES:
            primary.append((0, _SPACES.index(ch)))
        elif ch in _PUNCTUATION:
            primary.append((1, _PUNCTUATION.index(ch)))
        elif ch in _SYMBOLS:
            primary.append((2, _SYMBOLS.index(ch)))
        elif ch in _CURRENCY:
            primary.append((3, 0))
        else:
            kind = unicodedata.category(ch)
            if kind[0] == "L":
                primary.append((5, low))
            elif kind[0] in "ZC":
                primary.append((0, 100 + ord(ch)))
            elif kind[0] == "P":
                primary.append((1, 100 + ord(ch)))
            elif kind == "Sc":
                primary.append((3, ord(ch)))
            elif kind[0] in "SN":
                primary.append((2, 100 + ord(ch)))
            else:
                primary.append((6, ord(ch)))
        secondary.append(())
        tertiary.append(upper)
    return tuple(primary), tuple(secondary), tuple(tertiary)


# ------------------------------------------------------------------ the words ----

def _fill(pattern: str, **values: object) -> str:
    """The window's ``fill``: ``{n}`` replaced, a name with no value empty."""
    return re.sub(r"\{(\w+)\}", lambda found: str(values.get(found.group(1), "")), pattern)


def _folder_name(path: str) -> str:
    return next((part for part in reversed(re.split(r"[\\/]", path)) if part), "")


def _taxpayer(name: str, form: str) -> str:
    """``pagesTaxpayer``: the return's name without the ``{form} - `` the
    naming pattern puts first, and only when the record's form is what the
    name begins with (letter case and a hyphen inside the form number are not
    differences). A return with no recorded form, or a name somebody typed
    another way, is shown whole: the form is read from the record, never from
    a name, and a name is never cut by a guess."""
    pattern = layout.RETURN_NAME_PATTERN
    at = pattern.find("{client}")
    if not form or pattern.find("{form}") != 0 or at == -1 or at + len("{client}") != len(pattern):
        return name
    sep = pattern[len("{form}"):at]
    cut = name.find(sep) if sep else -1

    def same(text: str) -> str:
        return text.replace("-", "").lower()

    rest = name[cut + len(sep):].strip() if cut > 0 and same(name[:cut]) == same(form) else ""
    return rest or name


def _form_key(form: str, words: dict) -> object:
    """``pagesFormKey``: a form's place in the order the app lists forms in
    (the Client Types'), then the form by its name; a blank form is blank."""
    if not form:
        return ""
    known = [one for forms in words["client_types"].values() for one in forms]
    return [known.index(form) if form in known else len(known), form]


def _counts_said(counts: dict, problem: str, words: dict) -> tuple[str, str]:
    """``pagesCounts``: a return's status words and tone from its counts."""
    if problem:
        return problem, "needs"
    if counts.get("needs_you"):
        return _fill(words["need"], n=counts["needs_you"]), "needs"
    if counts.get("waiting"):
        return _fill(words["waiting"], n=counts["waiting"]), "waiting"
    return words["complete"], "done"


def _urgent(rank: int, count: int, text: str) -> object:
    """A status's order key: its urgency, then the larger count first, then its words."""
    return [rank, -(count or 0), text] if text else ""


# ------------------------------------------------------------------- comparing ----

def _blank(value: object) -> bool:
    return value is None or value == ""


def _compiled(value: object) -> tuple:
    """A key as something Python compares the way ``pagesCompareKeys`` did:
    numbers as numbers, text through :func:`name_order`, lists element by element."""
    if isinstance(value, (list, tuple)):
        return (2, tuple(_compiled(one) for one in value))
    if isinstance(value, (int, float)) and not isinstance(value, bool):
        return (0, value)
    return (1, name_order(str(value)))


@dataclass
class _Entry:
    """One row on its way to a page: what is drawn, what each cell orders by,
    and its place in the usual order (the tie-break)."""

    row: object
    keys: dict
    at: int


def _ordered(entries: list[_Entry], order: tuple[str, int] | None) -> list[_Entry]:
    """``pagesOrdered``: the entries as the header asks, or as they came.
    Blanks go last in either direction, and a tie keeps the usual order
    (``at``) in either direction."""
    if order is None:
        return entries
    cell, direction = order
    compiled = {id(one): _compiled(one.keys.get(cell, "")) for one in entries}

    def compare(a: _Entry, b: _Entry) -> int:
        x, y = a.keys.get(cell, ""), b.keys.get(cell, "")
        if _blank(x) or _blank(y):
            if _blank(x) and _blank(y):
                return a.at - b.at
            return 1 if _blank(x) else -1
        left, right = compiled[id(a)], compiled[id(b)]
        by = (left > right) - (left < right)
        return direction * by or a.at - b.at

    return sorted(entries, key=functools.cmp_to_key(compare))


def _pages(items: list, size_of, at: int) -> tuple[list, int, int, int, int, int]:
    """``pagesPaged``: ``items`` divided into pages of at most
    :data:`PAGE_SIZE` by ``size_of`` (an item larger than a page is a page of
    its own, and none is ever split); the page ``at`` (past the end is the
    last page) and its place: ``(items, at, pages, from, to, total)``."""
    parts: list[list] = []
    part: list = []
    held = 0
    for one in items:
        n = size_of(one)
        if part and held + n > PAGE_SIZE:
            parts.append(part)
            part, held = [], 0
        part.append(one)
        held += n
    if part:
        parts.append(part)
    at = min(at, max(0, len(parts) - 1))
    before = sum(size_of(one) for group in parts[:at] for one in group)
    shown = parts[at] if parts else []
    total = sum(size_of(one) for one in items)
    taken = sum(size_of(one) for one in shown)
    return shown, at, len(parts), (before + 1 if total else 0), (before + taken), total


# ------------------------------------------------------------------ the lists ----

class _Walk:
    """What one page is cut from: the whole reply, the names the walk saw and
    the words, with the lookups every list shares."""

    def __init__(self, whole: dict, names: dict, words: dict) -> None:
        self.whole, self.words = whole, words
        self.returns: list[dict] = whole["returns"]
        self.return_names: dict = names.get("returns", {})
        self.households: list[dict] = names.get("households", [])
        self._house_path: dict[str, str] = {}
        for one in self.households:
            self._house_path.setdefault(one["name"], one["path"])
        self._by_path: dict[str, dict] = {}
        for one in self.returns:
            self._by_path.setdefault(one["path"], one)

    def name_of(self, path: str) -> str:
        """``pagesReturnName``: the return's name, or its folder's when none is known."""
        return self.return_names.get(path) or _folder_name(path)

    def household_path(self, name: str) -> str:
        return self._house_path.get(name, "")

    def owner(self, path: str) -> dict | None:
        return self._by_path.get(path)

    def stage(self, number: int) -> str:
        return self.words["stages"].get(str(number), self.words["stages"].get(number, ""))


def _return_cells(walk: _Walk, one: dict) -> dict:
    """``pagesReturnCells`` and ``pagesReturnKeys``: what a row of a list of
    returns orders by in its first three cells."""
    taxpayer = _taxpayer(walk.name_of(one["path"]), one.get("form") or "")
    return {"year": one.get("year") or "", "taxpayer": taxpayer, "form": _form_key(one.get("form") or "", walk.words)}


def _overview(walk: _Walk, ask: Ask) -> tuple[dict, list[dict]]:
    words = walk.words
    paused = list(dict.fromkeys(one["household"] for one in walk.returns if one.get("paused") is True))
    paused.sort(key=name_order)
    entries: list[_Entry] = []
    for name in paused:
        word = words["paused"]
        entries.append(_Entry({"kind": "paused", "household": name, "household_path": walk.household_path(name)},
                              {"year": "", "taxpayer": name, "form": "", "status": _urgent(URGENCY["problem"], 0, word),
                               "end": ""}, len(entries)))
    tone = {id(entry): "needs" for entry in entries}

    def soonest(one: dict) -> str:
        return "" if one["problem"] else (one["oldest"] or LATE)

    need = [one for one in walk.returns if one["counts"]["needs_you"] > 0 or one["problem"]]
    need.sort(key=lambda one: (soonest(one), name_order(walk.name_of(one["path"]))))
    wait = [one for one in walk.returns
            if not one["problem"] and not one["counts"]["needs_you"] and one["counts"]["waiting"] > 0]
    wait.sort(key=lambda one: (one["due"] or LATE, name_order(walk.name_of(one["path"]))))
    for bucket, ones, date in (("need", need, "oldest"), ("wait", wait, "due")):
        for one in ones:
            text, said = _counts_said(one["counts"], one["problem"], words)
            rank = URGENCY["problem"] if one["problem"] else URGENCY[said]
            keys = {**_return_cells(walk, one),
                    "status": _urgent(rank, one["counts"]["needs_you"] or one["counts"]["waiting"], text),
                    "end": one[date] or ""}
            entry = _Entry({"kind": "return", "bucket": bucket, **one}, keys, len(entries))
            entries.append(entry)
            tone[id(entry)] = said
    many = len({str(entry.keys["year"]) for entry in entries if entry.keys["year"]}) > 1
    counts = {"all": len(entries), "need": sum(1 for entry in entries if tone[id(entry)] == "needs"),
              "waiting": sum(1 for entry in entries if tone[id(entry)] == "waiting")}
    wanted = {"need": "needs", "waiting": "waiting"}.get(ask.filter["tab"])
    shown = [entry for entry in entries if wanted is None or tone[id(entry)] == wanted]
    return _body(_page_of(ask, _ordered(shown, _usable(ask.order, many)), lambda _entry: 1), counts, many), []


def _usable(order: tuple[str, int] | None, many_years: bool) -> tuple[str, int] | None:
    """An order by Tax Year waits, kept, while the list holds one year (P268)."""
    return None if order is not None and order[0] == "year" and not many_years else order


def _body(page: dict, counts: dict, many_years: bool) -> dict:
    """The page's body: the place it is, its counts and its rows (the entries'
    rows, in order)."""
    items = page.pop("items")
    return {**page, "counts": counts, "many_years": many_years, "rows": [entry.row for entry in items]}


def _page_of(ask: Ask, entries: list[_Entry], size_of) -> dict:
    shown, at, pages, start, end, total = _pages(entries, size_of, ask.at)
    return {"list": ask.list, "at": at, "pages": pages, "from": start, "to": end, "total": total,
            "order": None if ask.order is None else {"cell": ask.order[0], "dir": ask.order[1]},
            "filter": dict(ask.filter), "items": shown}


def _reminders(walk: _Walk, ask: Ask) -> tuple[dict, list[dict]]:
    words = walk.words
    ready = [one for one in walk.returns if one.get("draft") and one["draft"].get("ready")]
    ready.sort(key=lambda one: name_order(walk.name_of(one["path"])))
    entries = []
    for one in ready:
        held = one["draft"]["held"] > 0
        status = words["held"] if held else walk.stage(one["draft"]["stage"])
        keys = {**_return_cells(walk, one),
                "status": _urgent(URGENCY["needs"] if held else URGENCY["waiting"],
                                  0 if held else one["draft"]["stage"], status),
                "end": one["draft"]["drafted"] or ""}
        entries.append(_Entry(one, keys, len(entries)))
    many = len({str(entry.keys["year"]) for entry in entries if entry.keys["year"]}) > 1
    return _body(_page_of(ask, _ordered(entries, _usable(ask.order, many)), lambda _entry: 1), {}, many), []


def _needs_review(walk: _Walk, ask: Ask) -> tuple[dict, list[dict]]:
    """Needs Review by whole returns: one group per return, a page holding
    whole groups up to :data:`PAGE_SIZE` files, and a larger group a page of
    its own (P174). The reason cards count every waiting file; a card narrows
    the list before the order and the pages."""
    by_return: dict[str, list[dict]] = {}
    for one in walk.whole["files"]:
        by_return.setdefault(one["return"], []).append(one)

    def file_order(one: dict) -> tuple:
        return (one["received"], name_order(one["name"]))

    groups = [(path, sorted(files, key=file_order)) for path, files in by_return.items()]
    groups.sort(key=lambda group: (min((f["received"] or "" for f in group[1]), default=LATE), name_order(walk.name_of(group[0]))))
    reasons: dict[str, int] = {}
    for _path, files in groups:
        for one in files:
            reasons[one["code"]] = reasons.get(one["code"], 0) + 1
    pick = ask.filter["reason"] if ask.filter["reason"] in reasons else ""
    labelled = sorted(((code, walk.words["reasons"].get(code, code), n) for code, n in reasons.items()),
                      key=lambda one: (-one[2], name_order(one[1])))
    if pick:
        groups = [(path, [f for f in files if f["code"] == pick]) for path, files in groups]
        groups = [group for group in groups if group[1]]

    def keys_of(one: dict) -> dict:
        reason = walk.words["reasons"].get(one["code"], one["code"])
        return {"name": one["name"], "detail": one.get("suggestion") or "",
                "status": _urgent(URGENCY["needs"], 0, reason), "end": one["received"] or ""}

    planned: list[_Entry] = []
    for at, (path, files) in enumerate(groups):
        ordered = [entry.row for entry in _ordered([_Entry(one, keys_of(one), i) for i, one in enumerate(files)], ask.order)]
        first = keys_of(ordered[0])
        planned.append(_Entry({"path": path, "files": ordered}, first, at))
    # The groups follow their first file in the header's order (pagesOrderedGroups).
    planned = _ordered(planned, ask.order)
    # The filter echoed is the one used: a reason no longer present is All, as the window's page has always read it.
    page = _page_of(replace(ask, filter={"reason": pick}), planned, lambda entry: len(entry.row["files"]))
    rows = []
    for entry in page["items"]:
        owner = walk.owner(entry.row["path"]) or {}
        household = owner.get("household", "")
        rows.append({"path": entry.row["path"], "household": household,
                     "household_path": walk.household_path(household), "year": owner.get("year") or 0,
                     "form": owner.get("form") or "", "links": owner.get("links") or [], "files": entry.row["files"]})
    page.pop("items")
    return ({**page, "counts": {"all": sum(reasons.values()), "reasons": [[code, n] for code, _label, n in labelled]},
             "many_years": False, "rows": rows},
            [{"name": one["name"], "return": one["return"], "year": one["year"], "handle": one["handle"]}
             for one in walk.whole["files"]])


def _clients(walk: _Walk, ask: Ask) -> tuple[dict, list[dict]]:
    """Clients: the firm's returns grouped by household once, here, from the
    same walk. A household with no return is still a household."""
    words = walk.words
    own: dict[str, list[dict]] = {}
    for one in walk.returns:
        own.setdefault(one["household"], []).append(one)
    paused = {one["household"] for one in walk.returns if one.get("paused") is True}
    kind = words["client_types"].get(ask.filter["type"]) if ask.filter["type"] else None
    kept = [one for one in walk.households if kind is None or any(form in kind for form in one.get("forms", []))]
    kept.sort(key=lambda one: name_order(one["name"]))
    entries: list[_Entry] = []
    for at, household in enumerate(kept):
        returns = own.get(household["name"], [])
        need = sum(r["counts"]["needs_you"] for r in returns)
        wait = sum(r["counts"]["waiting"] for r in returns)
        problem = next((r["problem"] for r in returns if r["problem"]), "")
        if need:
            text, tone = _fill(words["need"], n=need), "needs"
        elif problem:
            text, tone = problem, "needs"
        elif wait:
            text, tone = _fill(words["waiting"], n=wait), "waiting"
        elif returns:
            text, tone = words["complete"], "done"
        else:
            text, tone = "", "plain"
        rank = URGENCY["problem"] if not need and problem else URGENCY[tone]
        is_paused = household["name"] in paused
        work = need + wait > 0 or bool(problem) or is_paused
        row = {"name": household["name"], "path": household["path"], "links": household.get("links") or [],
               "returns": len(returns), "need": need, "wait": wait, "problem": problem, "paused": is_paused, "work": work}
        entries.append(_Entry(row, {"name": household["name"], "detail": len(returns) or "",
                                    "status": _urgent(rank, need or wait, text)}, at))
    work_count = sum(1 for entry in entries if entry.row["work"])
    shown = entries if ask.filter["all"] else [entry for entry in entries if entry.row["work"]]
    return _body(_page_of(ask, _ordered(shown, ask.order), lambda _entry: 1), {"work": work_count}, False), []


_BUILDERS = {"overview": _overview, "needs_review": _needs_review, "reminders": _reminders, "clients": _clients}


def page(whole: dict, names: dict, words: dict, ask: Ask) -> dict:
    """One page of one firm list, with the firm's totals and each return's
    counts (SPEC section 4.3). The filter narrows the whole list first, then
    the order, then the page (P174's rule, as the window did it): ``at`` past
    the end is the last page. ``whole`` is the reply
    :func:`tracker.api._cmd_firm` built, ``names`` what its walk saw (the
    returns' names, the households with their links and forms) and ``words``
    the vocabulary the keys depend on. ``view`` is left ``None`` for the API
    to fill. Nothing in ``whole`` is changed."""
    walk = _Walk(whole, names, words)
    body, found = _BUILDERS[ask.list](walk, ask)
    paths: dict[str, str] = {}
    if ask.list == "needs_review":
        for group in body["rows"]:
            for one in group["files"]:
                if one["open_key"] and one["open_key"] in whole["paths"]:
                    paths[one["open_key"]] = whole["paths"][one["open_key"]]
    reply = {"view": None, "totals": whole["totals"], "next_sort": whole["next_sort"],
             "return_counts": [{key: one.get(key) for key in ("path", "household", "year", "form", "counts", "files",
                                                               "problem", "paused")} for one in whole["returns"]],
             "page": body, "paths": paths}
    if ask.list == "needs_review":
        reply["files_found"] = found
    return reply


# ---------------------------------------------------------------------- the view ----

class View(NamedTuple):
    """A saved view read back: the firm's whole reply and the names its walk saw."""

    whole: dict
    names: dict


def pages_path() -> Path:
    """Where the view is: the data folder, never a client tree (decision 186)."""
    return settings.data_home() / PAGES_FILENAME


def save_view(whole: dict, names: dict, head: dict) -> str | None:
    """Keep ``whole`` and ``names`` as the view under a new token, all or
    nothing (``fsio.write_text_atomically``), and return the token. A view
    that cannot be written is said on the error log by its class and answers
    ``None``: the reply goes on without a token, and each page turn then reads
    fresh. Call it inside the reading hold, as the firm cache is."""
    token = secrets.token_hex(8)
    text = json.dumps({"format": FORMAT, "view": token, "head": head, "names": names, "reply": whole},
                      separators=(",", ":"))
    try:
        path = pages_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        write_text_atomically(path, text)
    except (settings.SettingsError, OSError) as exc:
        log.warning("The firm view's pages could not be written (%s)", errors.error_class(exc))
        return None
    return token


def load_view(token: str, head: dict) -> View | None:
    """The view saved under ``token`` when the file is whole and its head is
    ``head`` (the same program, clients folder, data folder, day and
    settings); otherwise ``None``, and the caller answers fresh. A missing
    file or a token another fresh ``firm`` has replaced is the ordinary way a
    view ends; a damaged one is said on the error log by its class and not
    used."""
    if not token:
        return None
    try:
        path = pages_path()
    except (settings.SettingsError, OSError):
        return None
    text = firm_cache.read_kept(path, "The firm view's pages could not be read (%s); reading afresh")
    if text is None:
        return None
    try:
        kept = json.loads(text)
    except json.JSONDecodeError:
        log.warning("The firm view's pages are not whole JSON; reading afresh")
        return None
    if not isinstance(kept, dict) or kept.get("format") != FORMAT or kept.get("view") != token \
            or kept.get("head") != head:
        return None
    whole, names = kept.get("reply"), kept.get("names")
    if not _whole_is_whole(whole) or not isinstance(names, dict):
        log.warning("The firm view's pages are damaged; reading afresh")
        return None
    return View(whole, names)


def _whole_is_whole(whole: object) -> bool:
    return (isinstance(whole, dict) and isinstance(whole.get("returns"), list) and isinstance(whole.get("files"), list)
            and isinstance(whole.get("totals"), dict) and isinstance(whole.get("paths"), dict)
            and "next_sort" in whole)
