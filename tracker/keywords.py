"""The matcher and the rules a reading is judged by: a keyword said whole,
a form's number and its variants, which forms a page names as its own,
where on the page a word is said, and the row's keyword and date rules.

Every keyword, form number and place that tier 3 judges a document on is
computed here, as a pure function of the text. Nothing here opens a file,
keeps a document's words past the call or writes anything; the one name
it keeps between calls is ``_last_line``, below.

- **A keyword said whole** (decisions 55, 57, 58 and 60).
  :func:`contains_keyword` finds a keyword as a whole token, never as a
  bare substring, so ``EIN`` is not in "being". A form's own variant is
  part of its name: ``1098`` is not in "1098-T", because
  ``FORM_VARIANTS`` is the one list of the suffixes the IRS joins to each
  number, reached across any dash or space (``_JOINER``), and any other
  hyphen-joined neighbour (``1098-Citi``) is a separator's. A keyword's
  own dash or space is optional in the pattern, so no run-together
  fallback sits beside it, and :func:`_seams` lets a keyword typed ``w2``
  find "W-2", reads a plural and keeps a number out of a larger amount. A
  keyword may name alternatives and join phrases
  (``manifest.keyword_alternatives``, decision 90).
- **Said as content evidence** (decisions 62 to 73, 82, 85 and 141).
  :func:`says` is :func:`contains_keyword` as evidence. A form number
  counts only where the title names it in its own right or as the number
  the document prints most (:func:`dominant_forms`, each mention weighed by
  its shape: a form naming itself, or a sentence about another), and every
  other keyword where the page says it in its own words rather than on a
  menu line or after an ask. :func:`_says_where` reaches the same verdict
  and says where - the title, the footer, the rest of page 1, or deeper -
  so a verdict carries an :class:`Evidence` for each rule that found its
  word. ``FIRST_PAGE_PHRASES`` count only when first said on page 1.
- **Which forms a page counts as its own** (decisions 94, 105, 107 and
  146). :func:`self_named_forms` lists the forms a page prints its own name
  on. :func:`own_forms` is the one reading of which forms a page counts as
  its own, so the router's split and the scanner's miss path read a
  two-form page the same way and the cache holds nothing a reader cannot
  recompute from the bytes (107's step-0 finding).
  :func:`carries_a_1099b_section` says whether a broker's statement
  carries the section that makes it one.
- **The row's rules** (decisions 40, 137, 187 and 190).
  :func:`evaluate_rules` applies the row's Required Keywords, Any Keywords
  and Date Pattern, and returns a :class:`ContentResult`, the rules'
  verdict. A Date Pattern a person typed runs line by line, lines over
  ``DATE_LINE_MAX`` skipped (:func:`date_pattern_at`); the one derived
  from the Period, recomputed rather than read from the record's flag,
  runs over the whole text. :func:`required_matched` and
  :func:`any_keyword_matched` are the router's two leads, and
  :func:`rules_fingerprint` is the part of the cache key a row's rules
  make.

Keyword matching is case-insensitive. Date Pattern is applied to the raw
text as-is, so authors control case sensitivity with inline flags (``(?i)``).

**A verdict keeps its evidence.** ``ok`` and ``reason`` say *what* was
decided; :class:`Evidence` says *why* — which rule found which of the row's
own words, where in the document, on which page. The verdict is unchanged
by it: nothing here reads the evidence back to decide anything, and the
reason sentence is worded exactly as before. It exists because a person
working the review queue needs "'1098' in the title, 'mortgage interest' on
page 1", not "matched no request", and because a later layer ranks parked
files from it. What is kept is the *firm's* words - the keyword the
manifest row asked for, the Period it asked for - and never a word of the
client's document, which is the same line
:class:`tracker.verdicts.ContentCache` draws.

**A file name is read the same way, but only for a person** (decision
128). The router reads a file's name with :func:`contains_keyword`, the
same whole-token rule, run-together spelling and all, and all of it
title; what a name says is evidence for the person who opens a parked
file, never a filing.

**Linear in the reading** (decision 178). :func:`_line_of` finds a line's
ends by the nearest break of any kind, and a mention on the line it found
last reuses it (``_last_line``, held by reference), so a long reading
costs its length and not its square. ``_last_line`` is the engine's
per-command state (``tracker.resident.PER_COMMAND``), put back to None
after every command.

**Where it runs** (decision 189). Every function here runs in the
reading's child, inside :func:`tracker.content_check.judge`: the pass holds
no document's words, and a text that makes a rule crawl - a typed Date
Pattern that backtracks, a one-line workbook the form scan walks - costs
one stop and parks its file. A caller outside the pass - the command
lines, the backtest, the vocabulary report - reads and judges in its own
process, with the same functions.

**Why it is its own module** (SPEC-architecture-p4 P4.10, P336; the
architecture audit's A-5). This code sat in content_check, between the
reading and the judgment, and reads nothing of either: content_check's own
code calls ten of its names, and nothing here calls content_check. Out of
it, content_check is the reading and the judgment (the verdict cache left
for :mod:`tracker.verdicts` with P337), and a change to how a keyword is
read lands in a module about nothing else.

**Why it sits at layer 2.** It imports only ``manifest`` and ``records``
(layer 1) and ``reasons`` (layer 0), and could sit lower. It sits beside
the one reading it judges for - its caller is
:func:`tracker.content_check.judgment_of` - and moving it lower would be a
decision row of its own. It imports nothing of ``content_check``, ``ocr``
or ``store``, and it does not log: a function of the text has nothing to
say to the run log.

**Every reader asks this module.** content_check imports back by name what
its own code reads and offers none of it on; every other reader imports
each name from here. A stand-in follows the name's readers (the audit's
A-4): ``says`` is read here alone, and ``dominant_forms`` both here and by
content_check's judgment, so a stand-in on it is set on both.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from typing import cast

from tracker import reasons
from tracker.manifest import RequestItem, derived_date_pattern, has_routing_rules, keyword_alternatives

# The Evidence record and the cell format it is written in live in
# tracker/records.py (decision 100): they are the shape of a verdict, not the
# reading of a document. This module imports Evidence, the rules and places a
# verdict says it rested on, and the page break it counts pages by; it offers
# none of them on (P322).
from tracker.records import (
    PAGE_BREAK,
    RULE_ANY,
    RULE_DATE,
    RULE_REQUIRED,
    WHERE_DEEP,
    WHERE_FIRST_PAGE,
    WHERE_FOOTER,
    WHERE_TITLE,
    Evidence,
)

#: How many non-blank lines at the end of a page count as its footer, where
#: a form repeats its own number on every copy. The Evidence record's own
#: ``WHERE_FOOTER`` is named from this reading.
_FOOTER_LINES = 2


@dataclass(frozen=True, slots=True)
class ContentResult:
    """Verdict of tier-3 rules for one file."""

    ok: bool
    reason: str = ""
    extractable: bool = True  # False: could not get text (no extractor / no OCR)
    #: True when the verdict is about the machine, not the document: the
    #: reader could not run, or it failed this once. Never cached - mending the reader
    #: or a second try must be able to change the answer.
    transient: bool = False
    #: Why the verdict went this way: one Evidence per rule that found its
    #: word, in the order the rules are applied. Collected on a failing
    #: verdict too - what *did* match is the lead a person works from - and
    #: read by nothing that decides anything.
    evidence: tuple[Evidence, ...] = ()
    #: The code of the Reason ``reason`` says (decision 190), kept with the
    #: verdict so a verdict read back from the cache says it too.
    code: str = ""


# ------------------------------------------------------------------ rules ----


def has_content_rules(item: RequestItem) -> bool:
    """Whether tier 3 has anything to check on this row at all: a routing
    rule, or a year check derived from Period (which checks but never routes)."""
    return has_routing_rules(item) or bool(item.date_pattern)


def rules_fingerprint(item: RequestItem) -> str:
    """Stable hash of the row's tier-3 rules; part of the cache key."""
    blob = json.dumps(
        [list(item.required_keywords), list(item.any_keywords), item.date_pattern]
    )
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]


#: The variants the IRS joins to a form's number: ``1098-T`` is the tuition
#: form, not the mortgage form ``1098``; ``1099-R`` is not ``1099-INT``. A
#: keyword of the bare number means the bare form and must not match a
#: variant. Keyed by the number with its dashes removed (``w2`` for W-2), so
#: a keyword written either way is found. Any other hyphen-joined neighbour
#: - an employer, a bank, a person (``1098-Citi``, ``W2-Tom``) - is a
#: separator's hyphen and still matches, which is what a client's file
#: name usually carries. One list, in the one module that reads keywords.
FORM_VARIANTS: dict[str, tuple[str, ...]] = {
    "1098": ("t", "e", "c", "f", "q", "ma"),
    "1099": ("int", "div", "b", "r", "misc", "nec", "oid", "k", "g", "s", "sa",
             "q", "ltc", "patr", "cap", "c", "a", "h", "da", "ls", "sb", "qa"),
    "1095": ("a", "b", "c"),
    "1040": ("sr", "nr", "x", "es", "v", "ss", "c"),
    "1041": ("a", "es", "n", "qft", "t", "v"),
    "1065": ("x", "b"),
    "1120": ("s", "x", "f", "h", "w", "c", "l", "pc", "pol", "reit", "ric", "sf", "nd"),
    "940": ("pr", "ss"),
    "941": ("x", "ss", "pr"),
    "990": ("ez", "pf", "t", "n"),
    "5498": ("sa", "esa", "qa"),
    "w2": ("g", "gu", "as", "vi", "c"),
    "w3": ("c", "ss", "pr"),
}
#: What may sit between a number and its variant, or between a keyword's
#: words: nothing ("1098T"), spaces, or any dash a PDF or a keyboard yields
#: - not a line break, unless the phrase is a heading that wraps. A
#: keyword names one thing, and its words are printed together; a line
#: break is where one label ends and the next begins. A K-1's box "19
#: Distributions" above its footer "Schedule K-1" is not a distribution
#: schedule, and "Items affecting shareholder basis" above the same
#: footer is not a shareholder basis schedule. A heading set in its own
#: box wraps - "Balance Sheet" over "As of December 31, 2025" - and a
#: heading begins its line with two words or more; a phrase that begins
#: mid-line and runs on to the next is a sentence, and one word over
#: another is two labels. (The IRS sets the 1098's title one word per
#: line, "Mortgage / Interest / Statement"; that form is known by its
#: number, as every form in tests/irs/ is.)
_DASH_CHARS = "".join(("-", chr(0x2010), chr(0x2011), chr(0x2012), chr(0x2013), chr(0x2014), chr(0x2212), chr(0xAD)))   # hyphen, the Unicode dashes, minus, soft hyphen
#: An apostrophe as a keyboard types it, as a PDF prints it, and as OCR reads it.
_APOSTROPHES = "".join(("'", chr(0x2019), chr(0x2018), chr(0x02BC), chr(0x60)))
_SAME_LINE = r"[^\S\r\n\f\v]"   # whitespace that is not a line break (a no-break space included)
_JOINER = rf"(?:{_SAME_LINE}|[{re.escape(_DASH_CHARS)}])*"
_WRAPPING_JOINER = rf"[\s{re.escape(_DASH_CHARS)}]*"
#: A heading begins its line, after nothing but blank space, a bullet, a
#: pipe or a rule (OCR reads a box's edge as "|", a list as "-" or "•").
_LINE_START = rf"(?:^|(?<=[\r\n\f\v]))(?:{_SAME_LINE}|[{re.escape(_DASH_CHARS)}•*|_])*"
_DASHES = re.compile(rf"[\s{re.escape(_DASH_CHARS)}]")


def _joined_to_a_variant(text: str, keyword: str, match: re.Match[str]) -> bool:
    """True when the matched keyword ends in a form number that ``text``
    continues with one of that form's variants: ``1098`` in "1098-T" or
    "1098 T", ``form 1040`` in "Form-1040-SR"."""
    variants = FORM_VARIANTS.get(_DASHES.sub("", keyword.strip().lower().split()[-1]))
    if not variants:
        return False
    tail = re.compile(rf"{_JOINER}(?:{'|'.join(variants)})(?![a-z0-9])")
    return tail.match(text, match.end()) is not None


def keyword_pattern(keyword: str, *, wrapping: bool = False) -> str | None:
    """The regular expression one keyword is looked for with, or None if blank.

    Whole tokens only. Between a keyword's words, and on either side of a
    dash inside a word, anything a dash can become: ``interest income``
    matches "interest-income" in a file name, ``w-2`` matches "W2" and
    "W–2", ``1099-int`` matches "1099INT". A keyword's words are on one
    line (``_JOINER``); the ``wrapping`` pattern is the other reading, a
    heading that begins its line with two words or more of the keyword
    and wraps the rest on to the next, and is None for a keyword that
    cannot wrap. Two one-word lines are two labels, not one phrase.
    """
    # Only the letters and digits are the keyword; a "-" or "$" typed into
    # a keyword cell is nothing to look for, and must not match everything.
    keyword = keyword.strip().lower()
    if not any(ch.isalnum() for ch in keyword):
        return None
    words = [_JOINER.join(_seams(part) for part in _DASHES.split(w) if part) for w in keyword.split()]
    words = [w for w in words if w]
    if not wrapping:
        return rf"(?<![a-z0-9]){_JOINER.join(words)}(?![a-z0-9])"
    if len(words) < 3:
        return None
    first_line = _JOINER.join(words[:2])
    return rf"{_LINE_START}(?<![a-z0-9]){first_line}{_WRAPPING_JOINER}{_WRAPPING_JOINER.join(words[2:])}(?![a-z0-9])"


def _seams(part: str) -> str:
    """``part`` escaped, with a dash allowed where letters meet digits (a
    keyword typed ``w2`` finds "W-2" as ``w-2`` finds "W2"), a plural
    allowed on a word (``fixed asset`` finds "Fixed Assets"), and a number
    kept out of a larger amount (``704`` is not in "20,704" or "704.50")."""
    pieces = re.findall(r"[a-z]+|[0-9]+|[^a-z0-9]+", part)
    out = []
    for piece in pieces:
        if piece.isalpha() and len(piece) >= 3:
            out.append(re.escape(piece) + "(?:e?s)?")
        elif piece.isdigit():
            out.append(rf"(?<![0-9][,.]){re.escape(piece)}(?![,.][0-9])")
        elif all(ch in _APOSTROPHES for ch in piece):
            out.append(f"[{re.escape(_APOSTROPHES)}]?")   # typed straight, printed curly, or dropped
        else:
            out.append(re.escape(piece))
    return _JOINER.join(out)


def _occurrences(low: str, keyword: str):
    """Every place ``low`` (lower-cased text) says ``keyword`` as a whole token.

    Both readings of the keyword - its words on one line, and the heading
    that wraps - in the order they are written, so a caller that weighs
    *where* a keyword is said (:func:`says`) sees each occurrence.
    """
    for wrapping in (False, True):
        pattern = keyword_pattern(keyword, wrapping=wrapping)
        if pattern is None:
            continue
        for match in re.finditer(pattern, low):
            if not _joined_to_a_variant(low, keyword, match):
                yield match


def contains_keyword(text: str, keyword: str) -> bool:
    """True if ``keyword`` appears in ``text`` as a whole token.

    Matched on token boundaries rather than as a bare substring, so ``EIN``
    does not match "being", ``1098`` does not match "10983", and ``W-2``
    still matches "W-2 Wage and Tax Statement". A form's own variant is
    part of its name, not a boundary: ``1098`` does not match "1098-T"
    and ``1099`` does not match "1099-R" (``FORM_VARIANTS``), because a
    tuition statement filed as mortgage interest is exactly the misfiling
    the keywords exist to prevent. A row that means every 1099 lists them.
    Keywords drive both status and — via :mod:`tracker.router` — where a
    document gets filed, so a coincidental substring must never count as
    evidence.

    A keyword that names alternatives is there when one of them is, and
    an alternative that joins phrases is there when every phrase is
    (``keyword_alternatives``); a plain keyword is one phrase and reads
    exactly as it always did.

    This is the plain reading: the words are there. Whether they are the
    document's own words is :func:`says`, which the routing and status
    rules use; a file name, being all title, is read with this one.
    """
    low = text.lower()
    return any(all(next(_occurrences(low, phrase), None) is not None for phrase in alternative)
               for alternative in keyword_alternatives(keyword))


#: A form number a keyword names is content evidence only where a form
#: prints its own: in the title - the first ``TITLE_CHARS`` of the text -
#: or as the number the document prints most, on every copy and every
#: page's footer (a W-2 prints its title at the foot of the form, below
#: the boxes). Every 1040 says "Attach Form(s) W-2", every 1095-C's
#: instructions name "Form 1095-A", every 1099's say "Form 1040-ES", and
#: those are single mentions of other forms, not the form this is. In the
#: title as everywhere, a mention counts only when its shape is a form
#: naming itself, not a sentence about another form (``_weigh_mention``):
#: the IRS prints an "Attention" page ahead of every information return
#: that names Form 1099-NEC by way of example, an organizer's first lines
#: say "attach Form 1098", a bank's letter says "reported on Form
#: 1099-INT". A file name is read whole: it is all title.
TITLE_CHARS = 400
_FORM_NUMBER = re.compile(r"^(?:form\s+)?([a-z]?\d{3,4}|w\d)(?:[a-z]{1,4})?$")
_FORM_MENTION = re.compile(
    rf"(?<![a-z0-9])(?:form\s+)?(w[{re.escape(_DASH_CHARS)}]?[23]|\d{{3,4}})"
    rf"(?:[\s{re.escape(_DASH_CHARS)}]?([a-z]{{1,4}}))?(?![a-z0-9])"
)


def is_form_number(keyword: str) -> bool:
    """True for a keyword that is a form's number: ``1098``, ``form 1095-a``,
    ``W-2``, ``form 940``. A bare number counts only for a known family
    (``FORM_VARIANTS``); ``form`` in front makes any number one."""
    bare = _DASHES.sub("", keyword.strip().lower())
    if bare.startswith("form"):
        return _FORM_NUMBER.match("form " + bare[4:]) is not None
    match = _FORM_NUMBER.match(bare)
    return match is not None and match.group(1) in FORM_VARIANTS


def _form_key(number: str, variant: str | None) -> str:
    return _DASHES.sub("", number) + (variant or "")


def form_key(keyword: str) -> str | None:
    """The form a keyword names, keyed the way a mention is (``w2``,
    ``1099int``), or None for a keyword that is not a form number.

    The one normalisation, so a manifest row's own word and a number read
    off a document are compared as one thing: :func:`_one_says_where` asks
    it of the row's keyword, and :mod:`tracker.router` asks it of the
    keyword an :class:`Evidence` kept, to say which form a row was
    accepted because of (decision 94).
    """
    if not is_form_number(keyword):
        return None
    bare = _DASHES.sub("", keyword.strip().lower())
    return bare[4:] if bare.startswith("form") else bare


def _title(text: str) -> str:
    """The first ``TITLE_CHARS``, extended to the end of the word it cuts."""
    if len(text) <= TITLE_CHARS:
        return text
    space = re.compile(r"\s").search(text, TITLE_CHARS)
    return text[:space.start()] if space else text


#: How a form names itself, and how it names another form. Its own number
#: is followed by its year or revision - "Form 1040 (2025)", "Form 1099-DIV
#: (Rev. January 2024)", "941 for 2026:" - on the title and on every page's
#: footer. Another form's number is quoted: "(Form 1040)", "Form 1040 or
#: 1040-SR", "Form 1040 instructions", "Form 1040, line 8" - or told to
#: the reader: "attach Form 1098", "Forms W-2", "reported on Form
#: 1099-INT", "a 1098". The two shapes are told apart here, because a
#: W-2's instruction pages name Form 1040 thirty times and the W-2 itself
#: a dozen. A self-mention's year is on the same line as its number.
_SELF_WEIGHT, _PLAIN_WEIGHT, _REFERENCE_WEIGHT = 3, 1, 0
_SELF_AFTER = re.compile(
    rf"{_SAME_LINE}*(?:[{re.escape(_DASH_CHARS)}]{_SAME_LINE}*)?(?:\({_SAME_LINE}*)?(?:rev\b|(?:19|20)\d{{2}}\b)"
    rf"|{_SAME_LINE}+for{_SAME_LINE}+(?:19|20)\d{{2}}\b"
)
#: A form's number set off from what follows by a dash - "Form 1098 -
#: Mortgage Interest Statement", "Form 1099-INT - Interest Income" - is
#: a checklist's line where the page is a menu of forms. A payer's own
#: substitute form prints its title that way too, so the shape alone is
#: not the answer: see ``_lists_forms`` and ``_year_beside``.
_REFERENCE_AFTER = re.compile(
    rf"\s*[,.;)]|{_SAME_LINE}+[{re.escape(_DASH_CHARS)}]{_SAME_LINE}+|"
    r"\s+(?:or|and|line|lines|instructions?|to|if|is|are|was|were|schedule|box|boxes|page|"
    r"worksheet|for|with|at|by|filers?|must|may|should)\b"
)
#: The words a document prints before a form it is telling the reader
#: about; a form never names itself after them - on the same line or the
#: one above, because a wrapped sentence breaks where it will ("please
#: attach" / "Form 1098 (2025) from each lender", the twelfth reading).
#: A page footer whose prose above ends in one of these words is read as
#: a reference too; that costs nothing the corpus shows, since a footer
#: repeats on every page and the others count. A colon may stand between
#: the word and the form, because that is how a cover writes it:
#: "Enclosed: Form 1099-INT", "Re: Forms 1099-INT and 1099-DIV".
_REFERENCE_BEFORE = re.compile(
    r"(?<![a-z0-9])(?:forms|attach|attached|see|file|files|filed|use|of|on|from|with|to|and|or|a|an|the|"
    r"include|including|per|report|reported|enclosed|enclosure|enclosures|re)\s*:?\s+$"
)
#: A form number that continues a list - ", Form 5498", ", 5498" - is one
#: of the forms a cover names rather than the form the page is. The last
#: item of "Enclosed: Form 1099-INT, Form 1098, Form 5498" carries no
#: punctuation after it, and was read as named in its own right, which
#: blinded the 1099-INT printed behind it (the thirteenth reading).
_LIST_CONTINUES = re.compile(rf",{_SAME_LINE}*$")
_BEFORE_CHARS = 14   # room for the longest word above, its colon and the space after it

#: What decided a mention's weight. The number alone is enough to weigh a
#: document's forms; the shape is what tells a menu's line from a payer's
#: own title, and where that line's title begins (``_menu_tails``).
_BY_PAREN, _BY_TOLD, _BY_LIST, _BY_YEAR = "paren", "told", "list", "year"
_BY_DASH, _BY_COMMA, _BY_WORD, _BY_NOTHING = "dash", "comma", "word", ""


def _weigh_mention(text: str, match: re.Match[str], end: int) -> tuple[int, str]:
    """A mention's weight and the shape that decided it.

    ``end`` is where the form number (with its real variant) stops.
    """
    start = match.start()
    if start > 0 and text[start - 1] == "(":
        return _REFERENCE_WEIGHT, _BY_PAREN
    # What comes before is read first: "attach Form 1098 (2025)" is told to
    # the reader, year or no year (the tenth reading added the year).
    if _REFERENCE_BEFORE.search(text, max(0, start - _BEFORE_CHARS), start):
        return _REFERENCE_WEIGHT, _BY_TOLD
    if _LIST_CONTINUES.search(text, max(0, start - _BEFORE_CHARS), start):
        return _REFERENCE_WEIGHT, _BY_LIST
    if _SELF_AFTER.match(text, end):
        return _SELF_WEIGHT, _BY_YEAR
    separator = _REFERENCE_AFTER.match(text, end)
    if separator:
        return _REFERENCE_WEIGHT, _shape_after(separator.group(0))
    return _PLAIN_WEIGHT, _BY_NOTHING


def _shape_after(separator: str) -> str:
    """Which of ``_REFERENCE_AFTER``'s shapes matched: a dash, a comma, a word."""
    stripped = separator.strip()
    if len(stripped) == 1 and stripped in _DASH_CHARS:
        return _BY_DASH
    return _BY_COMMA if stripped == "," else _BY_WORD


def _mention_span(low: str, match: re.Match[str]) -> tuple[str, str | None, int] | None:
    """The number, its real variant and where it stops; None for a match
    that is no mention at all.

    A known family (``FORM_VARIANTS``) is a mention bare or after "Form":
    "W-2", "941 for 2026", "Form 1099-DIV". Any other number is one only
    after "Form" and takes a variant only joined by a dash - "Form 4562",
    "Form 1125-E" - because a bare 4562 is as likely a year, an OMB number
    or an amount, and "Form 4562 line" is not Form 4562-LINE.
    """
    number, variant = match.group(1), match.group(2)
    base = _DASHES.sub("", number)
    end = match.end()
    if base in FORM_VARIANTS:
        if variant and variant not in FORM_VARIANTS[base]:
            variant, end = None, match.end(1)   # "1040 line" is Form 1040, not a variant
    else:
        if not match.group(0).startswith("form"):
            return None
        if variant and low[match.start(2) - 1].isspace():
            variant, end = None, match.end(1)
    return number, variant, end


#: A menu lists. Two or more forms heading a line of their own title
#: within the title window is a checklist ("Form 1099-INT - Interest
#: Income", "Form 1099-DIV - Dividends and Distributions", ...); one such
#: line is a payer's own substitute form printing its title the way it
#: always has, and a year beside the number on its line is that form's
#: evidence, as a year after the number is (``_SELF_AFTER``). Decision
#: 69's dash rule alone parked "2025 Form 1099-INT - Interest Income".
_FORMS_IN_A_MENU = 2
_LINE_BREAKS = "\r\n\f\v"
_BREAK_RUN = re.compile(rf"[{re.escape(_LINE_BREAKS)}]+")
_A_YEAR = re.compile(r"(?<![0-9])(?:19|20)\d{2}(?![0-9])")
_SPACES = re.compile(rf"{_SAME_LINE}*")
#: What may stand between the start of a line and a form naming itself: a
#: bullet or a rule, its own year, and the word "Form" where the year ate
#: it (``_FORM_MENTION`` reads "2025 form" as a number and its would-be
#: variant, so the mention that follows begins at the number). A form
#: prints its number at the head of its title line; "2025 Consolidated
#: Form 1099 - Account 8812" is a broker's sentence about a family.
_HEADS_ITS_LINE = re.compile(
    rf"(?:{_SAME_LINE}|[{re.escape(_DASH_CHARS)}•*|_])*"
    rf"(?:(?:19|20)\d{{2}}{_SAME_LINE}+)?(?:forms?{_SAME_LINE}+)?"
)


_A_BREAK = re.compile(rf"[{re.escape(_LINE_BREAKS)}]")
#: Everything up to and including the last break in what it is matched
#: against: the look back of :func:`_line_of`, one search over a window.
_TO_THE_LAST_BREAK = re.compile(rf"(?s:.*)[{re.escape(_LINE_BREAKS)}]")
#: How far the look back of :func:`_line_of` first reaches; each window
#: that holds no break doubles it.
_LOOK_BACK = 256
#: The line :func:`_line_of` found last and the text it was found in, held
#: by reference: a mention inside it is on it, with nothing searched.
_last_line: tuple[str, int, int] | None = None


def _line_of(low: str, start: int, end: int) -> tuple[int, int]:
    """Where the line holding ``low[start:end]`` begins and ends.

    Each end is the nearest break of any kind, found without walking past
    it (decision 178). Looking for the nearest of *each* kind walked the
    whole text for every kind a page never uses - a form feed, a vertical
    tab - so every mention cost the length of the reading and a long one
    cost its square: a 1.9 MB text took a minute a return. The look back
    is one search over a window that doubles from ``start`` until it holds
    a break or reaches the start of the text; the look forward stops at
    the first break there is; and a mention on the line found last is on
    it, so many mentions on one long line pay for the line once. The
    answer is the old one on every text, whatever its line ends.
    """
    global _last_line
    last = _last_line
    if last is not None and last[0] is low and last[1] <= start and end <= last[2]:
        return last[1], last[2]
    left, reach = 0, _LOOK_BACK
    while True:
        lo = max(0, start - reach)
        found = _TO_THE_LAST_BREAK.match(low, lo, start)
        if found is not None:
            left = found.end()
            break
        if lo == 0:
            break
        reach *= 2
    ahead = _A_BREAK.search(low, end)
    right = ahead.start() if ahead else len(low)
    if _A_BREAK.search(low, start, end) is None:     # a mention across a break is on no one line
        _last_line = (low, left, right)
    return left, right


def _titles_its_own_line(low: str, start: int, end: int) -> bool:
    """A form number at the head of its line with a year beside it, before
    or after: "2025 Form 1099-INT - Interest Income", "Form 1098 -
    Mortgage Interest Statement 2025", "W-2 Wage and Tax Statement 2025
    Department of the Treasury". That is how a payer prints its own
    substitute form and how the IRS prints the foot of a one-copy
    information return, and the only shape a dash-set-off number is not a
    checklist's line in."""
    left, right = _line_of(low, start, end)
    if not _HEADS_ITS_LINE.fullmatch(low, left, start):
        return False
    return bool(_A_YEAR.search(low, left, start) or _A_YEAR.search(low, end, right))


#: A form's own printed title between its number and its year, with
#: nothing to set it off: "W-2 Wage and Tax Statement 2025", "1099-DIV
#: Dividends and Distributions 2025", "Form 1040 U.S. Individual Income
#: Tax Return 2025". The IRS prints that line at the foot of every copy of
#: an information return, and the 2024 and 2025 W-2 revisions print one
#: copy to the page, so Copy B says "W-2" exactly once and says it that
#: way. Words only, on the form's own line, and the year is a year rather
#: than the tail of a date - "Form 941 04/30/2025" on a CP 575 is a filing
#: deadline, and the notice is not a 941. A title is short.
_TITLE_WORDS = 8
_SELF_TITLED = re.compile(
    rf"(?:{_SAME_LINE}+[a-z][a-z&/.{re.escape(_APOSTROPHES)}{re.escape(_DASH_CHARS)}]*){{1,{_TITLE_WORDS}}}"
    rf"{_SAME_LINE}+\(?(?:19|20)\d{{2}}(?![0-9])"
)


def _names_itself(low: str, start: int, end: int, shape: str) -> bool:
    """Whether the mention at ``low[start:end]`` is a form printing its own
    name on a line of its own, in either shape a printed title wears: a
    dash between the number and the title, with a year beside them
    (``_titles_its_own_line``), or nothing between them and the year after
    the title (``_SELF_TITLED``). Both shapes head their line, because
    "2025 Consolidated Form 1099 - Account 8812-4455" is a broker's
    sentence about a family, not a form.
    """
    if shape == _BY_DASH:
        return _titles_its_own_line(low, start, end)
    if shape != _BY_NOTHING:
        return False
    left, _right = _line_of(low, start, end)
    return (_HEADS_ITS_LINE.fullmatch(low, left, start) is not None
            and _SELF_TITLED.match(low, end) is not None)


def _lists_forms(low: str) -> bool:
    """Whether the title window heads ``_FORMS_IN_A_MENU`` lines or more
    with a form naming itself (``_names_itself``): a menu of forms, not a
    form. A dash-set-off number counts wherever it stands, as decision 69
    counted it."""
    stop = len(_title(low))
    listed = 0
    for match in _FORM_MENTION.finditer(low, 0, stop):
        span = _mention_span(low, match)
        if span is None:
            continue
        shape = _weigh_mention(low, match, span[2])[1]
        if shape == _BY_DASH or _names_itself(low, match.start(), span[2], shape):
            listed += 1
            if listed >= _FORMS_IN_A_MENU:
                return True
    return False


def _scan(low: str):
    """Every form number ``low`` (lower-cased text) mentions, as
    ``(key, start, end, weight, shape)``.

    A form heading its own title line with its year beside it names
    itself (``_titles_its_own_line``), whether a dash sets the title off
    or nothing does: "W-2 Wage and Tax Statement 2025" is the dated
    self-mention "W-2 2025" is, printed the way the IRS prints a one-copy
    return's foot. A page that heads two such lines is a menu, and the
    mention that is not the first on the page is not the page's own.
    """
    menu = _lists_forms(low)
    first = True
    for match in _FORM_MENTION.finditer(low):
        span = _mention_span(low, match)
        if span is None:
            continue
        number, variant, end = span
        weight, shape = _weigh_mention(low, match, end)
        if (first and not menu
                and not _asked_for(low, match.start())
                and _names_itself(low, match.start(), end, shape)):
            weight, shape = _SELF_WEIGHT, _BY_YEAR
        first = False
        yield _form_key(number, variant), match.start(), end, weight, shape


def _mentions(low: str):
    """Every form number ``low`` mentions, as ``(key, start, weight)``."""
    for key, start, _end, weight, _shape in _scan(low):
        yield key, start, weight


def dominant_forms(text: str) -> set[str]:
    """The form number ``text`` is about, normalised (``w2``, ``1099int``),
    as a set of at most one.

    Mentions are weighed by their shape (``_weigh_mention``): a form's
    own number, dated, on the title and every footer outweighs the other
    forms its instructions quote. The heaviest is its own; among equals,
    the first mentioned. A number that never appears in its own right and
    only once in passing is nobody's - an IRS notice that lists three
    forms to file is about none of them.
    """
    scores: dict[str, int] = {}
    first: dict[str, int] = {}
    for key, start, weight in _mentions(text.lower()):
        scores[key] = scores.get(key, 0) + weight
        first.setdefault(key, start)
    if not scores:
        return set()
    top = max(scores.values())
    if top < 2:
        return set()
    return {min((key for key, n in scores.items() if n == top), key=lambda key: first[key])}


#: A title that names this many form families in their own right is a
#: list of forms - an organizer's checklist ("Form W-2 - Wage and Tax
#: Statement", "Form 1098 - Mortgage Interest Statement", "Form 1099-INT
#: - Interest Income"), a transmittal's "Enclosed: Form W-2 2025, Form
#: 1098 2025, Form 1099-INT 2025" - and is none of them, as decision 63
#: says of a notice that lists three forms to file. Families, not
#: numbers: a broker's consolidated 1099 names "Form 1099", "1099-INT",
#: "1099-DIV" and "1099-B" and is one family's document, which the rows
#: that ask for its parts then contest (the eleventh reading found it
#: blinded, parked with no candidate at all).
_LIST_OF_FORMS = 3
_FAMILY = re.compile(r"[a-z]?\d{3,4}|w\d")


def _title_forms(low: str) -> set[str]:
    """The form numbers the title (``_title``) of ``low`` (lower-cased
    text) names in their own right: a mention there that is not a
    sentence about another form. None when the title names
    ``_LIST_OF_FORMS`` families or more."""
    stop = len(_title(low))
    forms = set()
    for key, start, weight in _mentions(low):
        if start >= stop:
            break
        if weight > _REFERENCE_WEIGHT:
            forms.add(key)
    # Every form key begins with its family, by construction, so the match is never None.
    families = {cast(re.Match[str], _FAMILY.match(key)).group(0) for key in forms}
    return forms if len(families) < _LIST_OF_FORMS else set()


def form_family(key: str) -> str:
    """The family a form key belongs to: ``1099int`` and ``1099div`` are
    both ``1099``, ``w2`` is ``w2``. A broker's consolidated statement
    prints several of one family's numbers and is one document
    (``_title_forms``' note); two families on one page are two documents
    (decision 94)."""
    return cast(re.Match[str], _FAMILY.match(key)).group(0)   # every form key begins with its family


#: How many distinct form families naming themselves make one page two
#: documents. A broker's consolidated statement prints "1099-INT" and
#: "1099-DIV" and is one family's document (``_title_forms`` says so of a
#: title); two families is two forms on one sheet (decision 94). Here, and
#: not in the router, since decision 107: the scanner reads through the
#: same rule on a cache miss.
MULTI_FORM_FAMILIES = 2


def own_forms(named: tuple[str, ...]) -> set[str] | None:
    """The forms a page counts as its own when ``named``, its self-named
    forms (:func:`self_named_forms`, read once by the judgment), come from
    two or more families, else ``None`` - the ordinary reading.

    **The one reading of which forms a page is** (decision 107). Decision
    94 files a page that prints two forms' own names under both requests,
    and the verdict the second copy needs is the page read with both forms
    counted as its own; decision 105 kept that verdict in the cache, and
    the cache alone. The step-0 re-run of 107 found what that meant: a
    rebuilt store - the runbook's own upgrade path, a new machine,
    ``rebuild`` - read the second copy the ordinary way, called it the
    other form's page, and the Saturday draft asked the client for a form
    already sent. The cache was carrying a decision, not a derivation. So
    the router's split (:mod:`tracker.router`) and the scanner's miss
    path (:func:`check_content`) both read through this, and the cache
    holds nothing a reader cannot recompute from the bytes.
    """
    if len({form_family(key) for key in named}) >= MULTI_FORM_FAMILIES:
        return set(named)
    return None


#: The form whose section makes a statement a broker's (decision 146):
#: ``1099-B``, keyed the way :func:`form_key` keys a mention.
BROKER_FORM = "1099b"


def carries_a_1099b_section(text: str, dominant: set[str] | None = None) -> bool:
    """Whether ``text`` carries a 1099-B section - which is what makes a
    broker's consolidated 1099 a brokerage statement (decision 146).

    **Not the word "consolidated".** A bank's "Consolidated Statement", the
    consolidated-return blanks and a broker's "your Consolidated Form 1099
    is available" email all say it, and none of them is a brokerage
    statement. What decides is the 1099-B section, read as a form label
    exactly the way a ``1099-b`` keyword is read (:func:`_one_says_where`):
    named in its own right in the title (``_title_forms``), or as the page's
    own dominant number. So this is true of a page exactly when a row asking
    for ``1099-b`` could be accepted *because of* the 1099-B - a checklist
    that lists it and a notice that only mentions it are not, and a
    statement with only interest and dividend sections carries none and
    still files with the 1099-INT/DIV row.

    It says what the page carries and nothing more. Which request the page
    then files under is :mod:`tracker.router`'s: exactly one of the rows
    that accepted it must have been accepted because of the 1099-B, or it
    parks.

    ``dominant`` is :func:`dominant_forms`'s answer when the caller already
    has it - a judgment reads it once for every question (decision 189) -
    and is read here when it does not.
    """
    low = text.lower()
    if BROKER_FORM in _title_forms(low):
        return True
    return BROKER_FORM in (dominant_forms(text) if dominant is None else dominant)


def self_named_forms(text: str) -> tuple[str, ...]:
    """Every form ``text`` prints its *own* name on, first mention first.

    Decision 85's predicate asked of every mention rather than only of the
    page's first: a form number heading its own line with its year after
    it, with the form's printed title in between (``_names_itself``, both
    shapes a title wears) or with nothing in between (``_SELF_AFTER``'s
    dated self-mention, "Form 1040 (2025)", "941 for 2026"). Anything a
    page says *about* another form - quoted, told to the reader, asked for
    - names nothing, and a page the menu rules call a menu
    (``_lists_forms``, decision 73) names none at all: a checklist lists
    forms, it is not one, which is what stops a cover letter buying itself
    a filing per line.

    Where :func:`dominant_forms` asks which one form the page *is* and
    answers with at most one - weighing every mention against every other
    - this asks which forms print their own name on it. Two families of
    them (:func:`form_family`) is two documents on one sheet, which is the
    owner's decision 94: the page files a copy under each, but only when
    each of those forms is asked for by exactly one request. Nothing here
    decides that; :mod:`tracker.router` does, and this says only what the
    page names.
    """
    low = text.lower()
    if _lists_forms(low):
        return ()
    first: dict[str, int] = {}
    for match in _FORM_MENTION.finditer(low):
        span = _mention_span(low, match)
        if span is None:
            continue
        number, variant, end = span
        shape = _weigh_mention(low, match, end)[1]
        if _asked_for(low, match.start()):
            continue
        if shape == _BY_YEAR:
            # A dated self-mention still has to head its own line to be
            # this page's own: "the 2025 Form 1098 from each lender" in a
            # cover's prose is a sentence about a form.
            left, _right = _line_of(low, match.start(), end)
            if _HEADS_ITS_LINE.fullmatch(low, left, match.start()) is None:
                continue
        elif not _names_itself(low, match.start(), end, shape):
            continue
        first.setdefault(_form_key(number, variant), match.start())
    return tuple(sorted(first, key=first.__getitem__))


#: The words a document asks for a document with. What one of them
#: introduces is what the page wants, not what the page is: the firm's own
#: organizer prints "If yes, attach your brokerage statement and any
#: realized gain and loss report", and a row that keys on a broker's words
#: filed the organizer as the client's brokerage statement (the thirteenth
#: reading). An ask governs the rest of its own sentence, because one ask
#: names several documents, and the line below it when the ask is what
#: that line ends with - a request wraps where it will.
_ASK_WORDS = ("attached", "attach", "provide", "send", "include", "enclosed", "enclose",
              "upload", "submit", "bring", "list", "see", "copies of", "copy of")
#: What may stand between an ask and the document it asks for and still
#: leave the two joined ("attach your", "see the latest", "copies of all").
_ASK_FILLER = ("most recent", "applicable", "either", "latest", "each", "both", "your",
               "and", "any", "all", "the", "an", "or", "of", "a")
_ASKED_FOR = re.compile(rf"(?<![a-z0-9])(?:{'|'.join(_ASK_WORDS)})(?![a-z0-9])")
#: An ask that ends the line above, with nothing but filler after it: the
#: request wrapped, and what begins the next line is what it asked for.
_ASK_WRAPPED = re.compile(
    rf"(?<![a-z0-9])(?:{'|'.join(_ASK_WORDS)})(?![a-z0-9])(?:\s+(?:{'|'.join(_ASK_FILLER)})(?![a-z0-9]))*\s*$"
)
#: Where the sentence an ask began ends. A colon is not an end: it is how
#: a page introduces what it is asking for ("Please send the following:").
_SENTENCE_END = re.compile(r"[.?!;]")
#: How far back an ask is looked for: within its own sentence on its own
#: line (so a "see" earlier in a form's dense column is not one), and, for
#: the wrapped shape, the words the line above ends with.
_ASK_WITHIN = 200
_WRAP_WITHIN = 40


def _ask_window(low: str, start: int) -> int:
    """Where to start looking back from ``start`` for an ask-word: at most
    ``_ASK_WITHIN`` characters, no further back than this line, and never
    past the end of an earlier sentence."""
    edge = max(0, start - _ASK_WITHIN, _line_of(low, start, start)[0])
    ends = list(_SENTENCE_END.finditer(low, edge, start))
    return ends[-1].end() if ends else edge


def _asked_for(low: str, start: int) -> bool:
    """True when what begins at ``start`` is what an ask-word asked for.

    On its own line the ask governs the rest of its sentence, because one
    ask names several documents; across a line break it governs only the
    wrap - the ask and its filler ending the line above - because a line
    further up is another label, not the rest of this request. A tax
    return's "Attach Forms W-2G and 1099-R if tax was withheld" two lines
    above its jurat asks for nothing on the jurat's line.
    """
    if _ASKED_FOR.search(low, _ask_window(low, start), start):
        return True
    return _ASK_WRAPPED.search(low, max(0, start - _WRAP_WITHIN), start) is not None


def _menu_tails(low: str) -> set[int]:
    """Where each menu line's title begins: just past a form number set off
    from what follows by a dash or a comma.

    A checklist's "Form 1099-B - Proceeds From Broker and Barter Exchange
    Transactions" names the form and prints its title, and the whole line
    is the one reference: a keyword that starts there is the menu's word,
    not a word the document says about itself.
    """
    tails = set()
    for _key, _start, end, weight, shape in _scan(low):
        if weight != _REFERENCE_WEIGHT or shape not in (_BY_DASH, _BY_COMMA):
            continue
        separator = _REFERENCE_AFTER.match(low, end)
        if separator is None:                      # the shape says it matched
            continue
        # The run of spaces may be empty, so it matches at any position.
        tail = cast(re.Match[str], _SPACES.match(low, separator.end())).end()
        if not _BREAK_RUN.search(low, end, tail):  # the title is on the form's own line
            tails.add(tail)
    return tails


def _in_its_own_words_at(low: str, keyword: str) -> int | None:
    """Where ``low`` first says ``keyword`` the way a document says what it
    is, or None.

    An occurrence that is a menu line's title (``_menu_tails``) or what an
    ask-word asked for (``_asked_for``) is a page talking about a document
    rather than being one. One occurrence that is neither is enough: a
    document prints its own words plainly somewhere.
    """
    tails = None
    for match in _occurrences(low, keyword):
        if tails is None:                          # only worth scanning if it is said at all
            tails = _menu_tails(low)
        if match.start() in tails or _asked_for(low, match.start()):
            continue
        return match.start()
    return None


def _in_the_footer(low: str, at: int) -> bool:
    """Whether ``at`` falls in the last ``_FOOTER_LINES`` non-blank lines of
    its page - where a form repeats its own number on every copy."""
    start = low.rfind(PAGE_BREAK, 0, at) + 1
    end = low.find(PAGE_BREAK, at)
    end = len(low) if end < 0 else end
    spans: list[tuple[int, int]] = []
    offset = start
    for line in low[start:end].splitlines(keepends=True):
        if line.strip():
            spans.append((offset, offset + len(line)))
        offset += len(line)
    return any(left <= at < right for left, right in spans[-_FOOTER_LINES:])


def _where_said(text: str, at: int) -> tuple[str, int]:
    """The place and the 1-based page of the character at ``at``.

    The title wins over everything - a form printing its own name at the
    top is the strongest place a word can be said - then the footer, which
    is a real place on page 1 as much as on page 7, and only then the rest
    of the first page.
    """
    page = text.count(PAGE_BREAK, 0, at) + 1
    if at < len(_title(text)):
        return WHERE_TITLE, page
    if _in_the_footer(text, at):
        return WHERE_FOOTER, page
    return (WHERE_FIRST_PAGE if page == 1 else WHERE_DEEP), page


def _first_said_at(low: str, keyword: str, within: int | None = None) -> int | None:
    """Where ``low`` says ``keyword`` as a whole token, first or within the
    first ``within`` characters; None if it does not."""
    starts = (match.start() for match in _occurrences(low, keyword))
    if within is None:
        return next(starts, None)
    return next((start for start in starts if start < within), None)


def _says_where(text: str, keyword: str, dominant: set[str] | None = None) -> tuple[str, int] | None:
    """Where ``text`` says ``keyword`` as content evidence, reading the
    keyword's alternatives (``keyword_alternatives``): the first
    alternative whose every phrase is said, placed where its first phrase
    is. A plain keyword is one alternative of one phrase, so this is
    :func:`_one_says_where` for every keyword written before decision 90.

    The place named is the leading phrase's because that is the row's own
    order - the phrase the accountant wrote first is the one that says
    what the document is, and the others confirm it.
    """
    if dominant is None:
        dominant = dominant_forms(text)
    for alternative in keyword_alternatives(keyword):
        places = [_one_says_where(text, phrase, dominant) for phrase in alternative]
        if all(place is not None for place in places):
            return places[0]
    return None


#: The phrases a notice prints in its header block, which count as evidence
#: only on the first page (decision 141, the designer's ruling on the
#: review, N2). A notice says who sent it, the tax year and the notice date
#: at its head; the same words deep in another document - the back of a
#: county tax bill, a letter's closing paragraph - are that document talking
#: about a notice. Keyed by the phrase, as ``FORM_VARIANTS`` is by the
#: number, in the one module that reads keywords; the catalog's notices row
#: (``tracker.templates.SHARED["notices"]``) is the only row that uses them,
#: and ``tests/test_irs_forms.py`` holds it to that. A reading with no page
#: breaks (OCR reads a scan as one run of text) is all first page.
FIRST_PAGE_PHRASES = frozenset({"notice date", "tax year", "tax period", "irs", "internal revenue service"})


def _one_says_where(text: str, keyword: str, dominant: set[str]) -> tuple[str, int] | None:
    """Where ``text`` says one phrase as content evidence - the place and
    the page - or None where it does not say it at all.

    The verdict is :func:`says`'s, unchanged: a form number counts only
    where the title names it in its own right (``_title_forms``) or as the
    document's own (dominant) number, and every other keyword counts where
    the document says it in its own words (``_in_its_own_words_at``)
    rather than on a menu line or after an ask. All this adds is *where*,
    so an :class:`Evidence` can name it.
    """
    low = text.lower()
    if not is_form_number(keyword):
        at = _in_its_own_words_at(low, keyword)
        if at is None:
            return None
        place = _where_said(low, at)
        # The first place a phrase is said in its own words; a header phrase
        # first said past page 1 is not said on page 1 at all.
        if keyword.strip().lower() in FIRST_PAGE_PHRASES and place[1] > 1:
            return None
        return place
    at = _first_said_at(low, keyword)
    if at is None:
        return None
    key = form_key(keyword)
    if key in _title_forms(low):
        # It is the title that accepted it, so it is the title's occurrence
        # the evidence names, not whichever came first in a long document.
        in_title = _first_said_at(low, keyword, within=len(_title(low)))
        return _where_said(low, at if in_title is None else in_title)
    if key in dominant:
        return _where_said(low, at)
    return None


def says(text: str, keyword: str, dominant: set[str] | None = None) -> bool:
    """``contains_keyword`` as content evidence.

    A form number counts only where the title names it in its own right
    (``_title_forms``) or as the document's own (dominant) number. Every
    other keyword counts where the document says it in its own words
    rather than on a menu line or after an ask. A keyword naming
    alternatives is said when one of them is, every phrase of it
    (``keyword_alternatives``). The thin wrapper over :func:`_says_where`
    is deliberate: one reading of a document, whether the caller wants
    the verdict or the evidence behind it.
    """
    return _says_where(text, keyword, dominant) is not None


def _keywords_said(text: str, keywords: tuple[str, ...], combine: Callable[[Iterable[bool]], bool],
                   dominant: set[str] | None) -> bool:
    """``combine`` (``any`` or ``all``) over whether each of ``keywords`` is
    said in ``text``; False for none. ``dominant`` as
    :func:`carries_a_1099b_section` takes it."""
    if not keywords:
        return False
    if dominant is None:
        dominant = dominant_forms(text)
    return combine(says(text, k, dominant) for k in keywords)


def any_keyword_matched(text: str, item: RequestItem, dominant: set[str] | None = None) -> bool:
    """Whether the row's any-keywords accept ``text``, apart from every other rule.

    The year a Period implies is a *check* on a document a keyword already
    matched, never evidence on its own (decision 40). When only that check
    fails, the row is still the lead a person needs, and this is how
    :mod:`tracker.router` asks for it without reading a verdict's sentence.
    """
    return _keywords_said(text, item.any_keywords, any, dominant)


def required_matched(text: str, item: RequestItem, dominant: set[str] | None = None) -> bool:
    """True if every one of ``item``'s required keywords is said in ``text``.

    Required keywords are the accountant's strongest assertion about what a
    document *is* ("a W-2 says W-2"), which is why they both outrank
    ``any_keywords`` when :mod:`tracker.router` chooses between requests
    and, when they match a request whose other rules then fail, stop the
    file being filed elsewhere.
    """
    return _keywords_said(text, item.required_keywords, all, dominant)


def _found(rule: str, text: str, keyword: str, dominant: set[str]) -> Evidence | None:
    """The Evidence for one of the row's words under one rule, or None."""
    place = _says_where(text, keyword, dominant)
    return None if place is None else Evidence(rule, keyword, place[0], place[1])


#: The longest line a Date Pattern is run over (decision 137, L3). A
#: pattern is a person's typing, and a typo such as ``(\d+)+x`` backtracks
#: exponentially in the length of what it is run over. Run over the whole
#: of an OCR reading, one such pattern could hold a pass for hours; run
#: line by line, with long lines left out, the worst it can do is bounded
#: by one short line. A date on a real document sits on a short line.
DATE_LINE_MAX = 500


def date_pattern_at(pattern: str, text: str) -> int | None:
    """Where in ``text`` the row's Date Pattern first matches, or None.

    Compiled once, then run **line by line** (decision 137, L3), and a
    line longer than :data:`DATE_LINE_MAX` is skipped. The offset is into
    the whole text, so where the date was said is still found by
    :func:`_where_said`. A pattern that does not compile was refused when
    it was saved; one that reaches here anyway matches nothing.
    """
    try:
        compiled = re.compile(pattern)
    except re.error:
        return None
    offset = 0
    for line in text.splitlines(keepends=True):
        if len(line) <= DATE_LINE_MAX and (match := compiled.search(line)):
            return offset + match.start()
        offset += len(line)
    return None


def evaluate_rules(text: str, item: RequestItem, dominant: set[str] | None = None) -> ContentResult:
    """Apply the manifest row's content rules to extracted text.

    The verdict and the reason are what they have always been; what is new
    is that every rule that *did* find its word leaves an :class:`Evidence`
    behind, on a failing verdict as much as on a passing one, because what
    matched is the lead a person works a parked file from.

    ``dominant`` is which form numbers count as the document's own, and is
    :func:`dominant_forms`'s answer unless a caller says otherwise. A page
    that names two forms as itself is two documents
    (:func:`self_named_forms`, decision 94), and the ordinary reading calls
    at most one of them the page's own; the router reads such a page a
    second time with both, and files only under the strict rule decision
    94 sets. Since decision 107 the scanner's miss path reads it the same
    way, through :func:`own_forms`, so every verdict the cache keeps is
    one the miss path reproduces; for a page naming at most one family
    :func:`own_forms` is ``None`` and this is the reading it always was.
    """
    if dominant is None:
        dominant = dominant_forms(text)
    found: list[Evidence] = []
    missing: list[str] = []
    for keyword in item.required_keywords:
        evidence = _found(RULE_REQUIRED, text, keyword, dominant)
        if evidence is None:
            missing.append(keyword)
        else:
            found.append(evidence)
    if missing:
        listed = ", ".join(f"'{k}'" for k in missing)
        return ContentResult(ok=False, reason=reasons.WRONG_DOCUMENT.format(listed=listed),
                             evidence=tuple(found), code=reasons.WRONG_DOCUMENT.code)

    if item.any_keywords:
        hits = [e for e in (_found(RULE_ANY, text, k, dominant) for k in item.any_keywords)
                if e is not None]
        if not hits:
            listed = ", ".join(item.any_keywords)
            return ContentResult(ok=False, reason=reasons.NO_EXPECTED_KEYWORD.format(listed=listed),
                                 evidence=tuple(found), code=reasons.NO_EXPECTED_KEYWORD.code)
        found.extend(hits)

    if item.date_pattern:
        # A pattern a person typed runs line by line (decision 137, L3); the
        # one derived from the Period is the firm's own and runs over the
        # whole text as it always did (the review's F7), so "December" and
        # "2025" split by a line break still say the year. "Derived" is
        # what the pattern *is*, recomputed from the Period, never what the
        # record's flag claims (decision 187): a pattern that is not the
        # firm's own runs line by line whatever the flag says.
        if item.date_pattern == derived_date_pattern(item.period):
            hit = re.search(item.date_pattern, text)
            at = hit.start() if hit else None
        else:
            at = date_pattern_at(item.date_pattern, text)
        if at is None:
            return ContentResult(ok=False,
                                 reason=reasons.WRONG_PERIOD.format(pattern=item.date_pattern),
                                 evidence=tuple(found), code=reasons.WRONG_PERIOD.code)
        # The row's Period, not the regex it derives and not a word of the
        # document: what a person reading the index needs is "TY2025".
        where, page = _where_said(text, at)
        found.append(Evidence(RULE_DATE, item.period or item.date_pattern, where, page))

    return ContentResult(ok=True, evidence=tuple(found))
