"""Whose document is this? The name tier (component 15, decision 128).

Two 1040s in one household share every row of their request lists - 15 of
the 1040's 18 rows are any-keyword rows - so once a household's inbox held
two people's papers the keywords could not say whose W-2 this was, and the
failure they allowed was the worst kind: filed silently on the wrong
return. The owner's decision (Q4 REPLY, 2026-09-21/22) is that every return
carries the names its documents will show, and a document is filed only
where the name on it confirms.

**What this module is, and is not.** It is the matcher and nothing else:
:func:`normalise`, :func:`spelling_in`, :func:`propose_spellings` and
:func:`check_name` are pure functions over text the caller already has.
Nothing here reads a file, takes a lock, or knows what a return is. The
check is asked in the reader child, beside the rules (decision 189,
:func:`tracker.content_check.judge`), and its verdict read in the
household pass (:func:`tracker.filer.file_household_drops`), after the
request lists have accepted a document and before the exactly-one rule;
the router is untouched, because the router judges a request list and
knows no person.

**The rules it keeps.**

- **A spelling is at least two words** (:data:`tracker.records.MIN_SPELLING_WORDS`).
  A family name on its own is a whole phrase inside a company's name:
  ``Park`` would confirm ``Park Landscaping LLC``'s bank statement as the
  family's. An entity's spelling is its name with or without its suffix,
  and both are two words or more.
- **A spelling matches as a whole phrase, never inside a word.**
  :func:`normalise` folds case away and turns everything that is not a
  letter or a digit into a space, so ``O'Brien``, ``Park, John A.`` and
  ``PARK JOHN A`` all read alike; the padding on each side is what makes
  the boundary.
- **Nothing is guessed and nothing is inferred.** The app *proposes*
  spellings from the name a person typed; a person ticks them. No
  spelling is ever learned from a document, no person is ever inferred
  from one, and no fuzzy match is made: a page either says one of the
  firm's own spellings or it does not.
- **No word of a client's document is kept.** What a verdict carries back
  is the firm's own spelling that matched - which is the firm's term,
  exactly as a keyword is - and never the text it was found in. No
  identifier of a person is read at all: there is no SSN fragment here,
  nowhere.

**Confirmed beats vetoed beats absent.** A page that names this return's
person is this return's, even when it also names somebody on another
return - a joint 1040 and one spouse's business share a page all the time
- and the exactly-one rule then decides between the returns that were
confirmed. Only a page that names *nobody here* and *somebody there* is
vetoed.
"""

from __future__ import annotations

from dataclasses import dataclass

from tracker.content_check import PAGE_BREAK
from tracker.records import (
    WHERE_DEEP,
    WHERE_FIRST_PAGE,
    is_a_spelling,
    name_parts,
    name_words,
)

#: What the app refuses a one-word spelling with, wherever one is typed.
ONE_WORD_SPELLING = ("a spelling needs at least two words, so a family name alone never "
                     "confirms a document")
#: What creation refuses a return with nobody on it with.
NO_PEOPLE = ("add at least one person to the return; a named request files only where a name "
             "confirms")

#: The three answers the check can give. ``NAME_VETOED``'s value is the
#: phrase a sentence reads it as, the way a decision's words are their own
#: name everywhere else in this package.
NAME_CONFIRMED = "confirmed"
NAME_VETOED = "another return's"
NAME_ABSENT = "absent"
NAME_OUTCOMES: tuple[str, ...] = (NAME_CONFIRMED, NAME_VETOED, NAME_ABSENT)

#: The suffixes an entity's name may end with and still be the same entity.
#: Both spellings of each are listed as a person would type them; they are
#: compared on their letters alone, so ``L.L.C.`` and ``LLC`` are one
#: suffix and neither has to be typed twice.
ENTITY_SUFFIXES: tuple[str, ...] = (
    "llc", "l.l.c.", "inc", "inc.", "corp", "corp.", "co", "co.", "ltd", "lp", "llp", "pc",
    "trust",
)
#: The kinds whose name is an organisation's rather than a person's: their
#: proposals are the name as typed and the name without its suffix, never a
#: first-name/family-name rearrangement.
ENTITY_KINDS: tuple[str, ...] = ("entity", "dba", "trust")


def normalise(text: str) -> str:
    """``text`` folded for matching: lower case, every character that is not
    a letter or a digit a space, runs of them collapsed, one space at each
    end.

    The padding is the whole of the boundary rule: ``" park "`` is not
    inside ``" park landscaping llc "``'s word ``parkway`` and never can
    be, because every separator became a space before the search.
    """
    return " " + " ".join(name_words(text)) + " "


def spelling_in(text: str, spelling: str) -> bool:
    """Whether ``text`` says ``spelling`` as a whole phrase.

    The phrase test and nothing else: ``Park`` *is* a whole phrase inside
    ``Park Landscaping LLC``, which is precisely why a one-word spelling
    may never be recorded as one. That rule is kept where a spelling is
    accepted - the editor, the wizard, a filing that teaches one, the
    store's guard against a hand-edited journal - and again in
    :func:`check_name`, which is the thing that confirms.
    """
    return _said_at(text, spelling) is not None


@dataclass(frozen=True, slots=True)
class NamesOnPage:
    """A page's words folded once for the name check (:func:`read_names`):
    the folded copy, and where each of its words begins in the page.

    Decision 189: :func:`check_name` used to fold the whole page again for
    every spelling of every return - on a long reading, the name check's
    whole cost. Folded once, every spelling is one search. It lives only
    where the page is judged (the reader child) and is never kept.
    """

    hay: str
    #: Offset in ``hay`` of each word's first letter -> offset in the page.
    starts: dict[int, int]


def read_names(text: str) -> NamesOnPage:
    """Fold ``text`` for the name check, once (:class:`NamesOnPage`)."""
    parts = name_parts(text)
    starts: dict[int, int] = {}
    at = 1
    for word, where in parts:
        starts[at] = where
        at += len(word) + 1
    return NamesOnPage(" " + " ".join(word for word, _at in parts) + " ", starts)


def _said_at(text: str, spelling: str, page: NamesOnPage | None = None) -> int | None:
    """Where in ``text`` a spelling's first word begins, or None.

    The search is over the folded copy (:func:`normalise`); the offset
    comes back in the *original* text, because the place a record names is
    a place on the page the reader produced - the folded copy has no page
    breaks left in it. ``page`` is ``text`` already folded
    (:func:`read_names`), when the caller asks of it more than once.
    """
    page = read_names(text) if page is None else page
    if not page.starts:
        return None
    needle = normalise(spelling)
    if not needle.strip():
        return None
    at = page.hay.find(needle)
    if at < 0:
        return None
    # Which word of the original begins at that position: the words are
    # laid out one space apart, so their starts are known without another
    # search.
    return page.starts.get(at + 1)


def _place_of(text: str, at: int) -> tuple[str, int]:
    """The place and the 1-based page of the character at ``at``.

    A name is not a form's own title and is not repeated in a footer: it
    is printed where the addressee goes. So the only thing worth saying
    about where it was found is which page - the first, or further in,
    which is the weakest place and the one a person most wants named.
    """
    page = text.count(PAGE_BREAK, 0, at) + 1
    return (WHERE_FIRST_PAGE if page == 1 else WHERE_DEEP), page


def _without_a_suffix(name: str) -> str:
    """``name`` with a trailing entity suffix removed, or "" where there is
    none to remove or too little would be left."""
    words = name.split()
    if len(words) < 2:
        return ""
    last = "".join(c for c in words[-1].lower() if c.isalnum())
    if not any(last == "".join(c for c in one if c.isalnum()) for one in ENTITY_SUFFIXES):
        return ""
    left = " ".join(words[:-1]).rstrip(" ,")
    return left if is_a_spelling(left) else ""


def propose_spellings(name: str, kind: str) -> tuple[str, ...]:
    """The spellings a document might print ``name`` in, for a person to tick.

    A proposal, never a rule: what a return matches on is what somebody
    ticked or typed, and this only saves them typing the obvious ones. For
    a person: the name as given with the middle name and without it, and
    the family name first with a comma. For an entity, a DBA or a trust:
    the name as typed, and the name without its suffix when two words are
    left.

    There is no family-name-first form to propose, and no mark on the
    person for one: :func:`normalise` reads a comma as a space, so
    ``Park John A`` and ``Park, John A.`` are one spelling and the comma
    form already matches a page that prints neither.

    Case never matters (:func:`normalise` folds it), so no all-capitals
    proposal is offered. Duplicates fold away and a proposal of one word is
    dropped, so a person with one name to their name gets nothing to tick
    and types what their documents actually print.
    """
    name = " ".join(str(name or "").split())
    if not name:
        return ()
    if kind in ENTITY_KINDS:
        return _distinct([name, _without_a_suffix(name)])
    words = name.split()
    if len(words) < 2:
        return ()
    first, last, middle = words[0], words[-1], words[1:-1]
    with_middle = " ".join([first, *middle])
    return _distinct([
        f"{with_middle} {last}",
        f"{first} {last}",
        f"{last}, {with_middle}",
        f"{last}, {first}",
    ])


def _distinct(proposed: list[str]) -> tuple[str, ...]:
    """The proposals that are two words or more, first spelling wins, no two
    the same once folded."""
    out: list[str] = []
    seen: set[str] = set()
    for one in proposed:
        if not one or not is_a_spelling(one):
            continue
        folded = normalise(one)
        if folded in seen:
            continue
        seen.add(folded)
        out.append(one)
    return tuple(out)


@dataclass(frozen=True, slots=True)
class NameVerdict:
    """What one page said about whose it is.

    ``matched`` is this return's spelling that was found, ``other`` the
    other return's and ``other_label`` that return's own label; ``where``
    and ``page`` say where the one that decided it was said, so the
    decision can leave :data:`tracker.records.RULE_NAME` evidence without
    reading the page a second time. Every one of them is the firm's own
    word.
    """

    outcome: str
    matched: str = ""
    other: str = ""
    other_label: str = ""
    where: str = ""
    page: int = 0


def check_name(
    text: str, own: tuple[str, ...], others: dict[str, tuple[str, ...]],
    *, page: NamesOnPage | None = None,
) -> NameVerdict:
    """Whether ``text`` names somebody on this return, somebody on another,
    or nobody at all.

    ``own`` is every spelling of every person on this return, in the list's
    order; ``others`` maps each other return the drop may feed to its own
    spellings. A spelling of one word decides nothing here, whichever side
    it is on: it could not have been recorded, and a record that somehow
    holds one must not confirm a business's statement as a family's.
    Confirmed wins outright: a page naming this return's person
    is this return's even when it also names somebody on another return,
    which is the joint 1040 whose spouse also has a business - both returns
    are confirmed and the exactly-one rule then decides. Only a page that
    names nobody here and somebody there is vetoed.

    ``text`` is folded once for every spelling (decision 189), or not at
    all when the caller hands it folded as ``page`` (:func:`read_names`) -
    the judgment asks one page about every return the drop may feed.
    """
    page = read_names(text) if page is None else page
    for spelling in own:
        at = _said_at(text, spelling, page) if is_a_spelling(spelling) else None
        if at is not None:
            where, page = _place_of(text, at)
            return NameVerdict(NAME_CONFIRMED, matched=spelling, where=where, page=page)
    for label, spellings in others.items():
        for spelling in spellings:
            at = _said_at(text, spelling, page) if is_a_spelling(spelling) else None
            if at is not None:
                where, page = _place_of(text, at)
                return NameVerdict(NAME_VETOED, other=spelling, other_label=label,
                                   where=where, page=page)
    return NameVerdict(NAME_ABSENT)


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="What would the app propose as spellings of this name? Read-only."
    )
    parser.add_argument("name", help="the name as a person would type it")
    parser.add_argument("--kind", default="taxpayer", help="one of the person kinds")
    ns = parser.parse_args()

    for proposal in propose_spellings(ns.name, ns.kind):
        print(proposal)
