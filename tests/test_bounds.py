"""Tests for tracker/bounds.py - the value rule's bounds, out of the record.

The claims are the module's whole debt. The bounds reach for nothing in the
package but the layout's name rule, at load time or at call time, and for
no file. Records, which held them until P2.4, offered every public name,
each the very object defined here - the same object, not a copy - so the
editor, the store's gate and every reader that still asked the record held
one rule; P2.13 pointed them here. And the value rule's tests came
with it: each moved from ``tests/test_records.py`` unchanged but for its
imports, except the three that read the Date Pattern analyser's privates,
which read bounds from the start because records never re-exported them.
Since P2.13 the others read ``bounds.`` where they read ``records.``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from tests.import_graph import import_edges
from tracker import bounds, ledger, manifest


def test_the_bounds_import_nothing_of_the_package_but_the_layouts_name_rule():
    """A layer 0 module: any layer may ask a bound without loading the
    record's shapes. The Windows character and device rule is the layout's
    (decision 188), which reads no file, and the bounds import it from
    there and nothing else of the package, at load time or at call time."""
    load, call = import_edges()

    assert load["bounds"] == {"layout"}, load["bounds"]
    assert call["bounds"] == set(), call["bounds"]
    assert "bounds" in load["records"], "the record's row checks read the bounds"


def test_the_bounds_reach_no_file():
    """A bound knows nothing about where a value is stored. The imports say
    so: no openpyxl, no os, no pathlib; `datetime` only because a date and a
    stamp are read as the calendar reads them, and `re` only because a date,
    a stamp, a digest and a line of text are held to a pattern.
    `math`, `re._parser` and `typing` are the value rule's (decision 187):
    a count is finite, a Date Pattern's shape is read off the standard
    library's own parser rather than a second engine, and `typing` says what
    `_is_number` proves (P2.1). `tracker.layout` is the Windows name rule's
    (decision 188), and it reads no file either."""
    source = (Path(bounds.__file__)).read_text(encoding="utf-8")
    imported = {line.split()[1] for line in source.splitlines()
                if line.startswith("import ") or line.startswith("from ")}

    assert imported == {"__future__", "datetime", "math", "re", "re._parser", "typing",
                        "tracker.layout"}, imported


# Decision 187: the value rule, worded once, for the editor and the gate.
# The tests below moved here from tests/test_records.py with the rule (P2.4).


def test_a_nested_or_alternating_repetition_is_not_a_date_pattern():
    """The shape rule is read off the standard library's own parser: a
    repetition that can repeat more than once may hold no other such
    repetition, no alternation and no back-reference, at any depth; at most
    three of them, one open-ended, the rest at most twenty."""
    refused = {
        r"(\d+)+x": bounds.DATE_PATTERN_NESTED,
        r"(?:(?:\d{1,4}\s)*)x": bounds.DATE_PATTERN_NESTED,
        r"(?:Dec|12)+": bounds.DATE_PATTERN_ALTERNATES,
        r"(\d)(?:\1x)+": bounds.DATE_PATTERN_REFERS_BACK,
        r"\d{1,2}\d{1,2}\d{1,2}\d{1,2}": bounds.DATE_PATTERN_TOO_MANY,
        r"\d*-\d*": bounds.DATE_PATTERN_TOO_OPEN,
        r"\d{0,21}": bounds.DATE_PATTERN_TOO_WIDE,
        "x" * (bounds.DATE_PATTERN_MAX + 1): bounds.DATE_PATTERN_TOO_LONG,
        "([unclosed": bounds.DATE_PATTERN_NOT_A_REGEX,
        5: bounds.TEXT_BOUNDS,
    }
    for pattern, phrase in refused.items():
        assert bounds.date_pattern_problem(pattern) == phrase, pattern
    for fine in [r"(?i)\b2025\b", r"\d+/\d{1,2}/2025", r"(?:Dec|12)\s?2025", r"0?1/[0-3]?[0-9]/2025",
                 r"(?:Dec|12)?\s?2025", r"\d{0,20}x\d{0,20}y"]:
        assert bounds.date_pattern_problem(fine) == "", fine


def test_every_derived_date_pattern_passes_the_shape_rule():
    """The flag that marks a pattern derived is the record's claim, so a
    derived pattern is held to the same rule - and every one the Period
    derives passes it."""
    months = ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
    periods = [f"{month} {year}" for month in months for year in (2025, 2099)] + ["TY2025", "TY1900"]
    for period in periods:
        pattern = manifest.derived_date_pattern(period)
        assert pattern, period
        assert bounds.date_pattern_problem(pattern) == "", period


def test_a_flag_is_true_false_zero_or_one_and_nothing_else():
    for fine in (True, False, 0, 1):
        assert bounds.flag_problem(fine) == ""
    for refused in ("no", "yes", "false", 2, 1.0, None, [], ""):
        assert bounds.flag_problem(refused) == bounds.FLAG_BOUNDS, refused


def test_an_optional_chain_is_not_a_date_pattern():
    """The review's M1: an optional is a choice point too. ``\\d?`` twenty
    times over a line of digits backtracks without end though no single
    part repeats more than once, so every variable repetition counts -
    ``?`` included - for nesting and for the budget, and the ways one line
    may be tried are held to the measured 0.22 s case."""
    assert bounds.date_pattern_problem(r"\d?" * 20 + "x") == bounds.DATE_PATTERN_TOO_MANY_OPTIONAL
    assert bounds.date_pattern_problem(r"\d?" * 60 + "x") == bounds.DATE_PATTERN_TOO_MANY_OPTIONAL
    assert bounds.date_pattern_problem(r"(?:\d?){20}x") == bounds.DATE_PATTERN_NESTED
    assert bounds.date_pattern_problem(r"\d*\d{0,20}\d{0,20}\d?x") == bounds.DATE_PATTERN_TOO_MANY_WAYS
    assert bounds.date_pattern_problem(r"\d?" * 8 + "x") == ""
    assert bounds.date_pattern_problem(r"\d*\d{0,20}\d{0,20}x") == bounds.DATE_PATTERN_TOO_MANY_WAYS
    assert bounds.DATE_PATTERN_VARIABLE_MAX == 8 and bounds.DATE_PATTERN_OPEN_MAX == 1


def test_a_stamp_is_the_one_form_the_ledger_writes_from_the_epoch():
    """The review's S1: ``ledger.stamp`` has only ever written one form, and
    Windows cannot give a time before 1970 its local day."""
    assert bounds.stamp_problem(ledger.stamp()) == ""
    for refused in ("1900-01-01T00:00:00Z", "2025-W01-1", "20250101T000000", "2025-01-01T00:00:00",
                    "2025-01-01T00:00:00+00:00", 12345):
        assert bounds.stamp_problem(refused) == bounds.STAMP_BOUNDS, refused


#: The re-check's timing corpus (decision 187's review, M1a and M1b): each
#: took from 0.7 s to a minute on one 500-character line under the rule it
#: broke, and each is refused now.
RUNAWAYS = [
    "(?:" + "(?:1|11)" * 23 + "){1}x",                  # a {1} wrapper hid the chain: 60 s at k=22
    "(?:1|11)" * 17 + "x",                              # an alternation chain: 1.6 s
    "(?:1|11|111)" * 11 + "x",
    r"\d+\d{0,20}\d{0,20}\D",                           # no literal ending to short-cut: 0.85 s
    r"\d+\d{0,20}\d{0,20}\s",
    r"\d{0,20}" * 3 + r"\d?" * 4 + "x",
    r"\d{0,20}" * 3 + "(?:1|11)" * 4 + "x",
]


@pytest.mark.parametrize("pattern", RUNAWAYS)
def test_a_once_wrapped_alternation_is_counted(pattern):
    """Ways are counted through every repetition - a fixed ``{1}`` too - and
    an alternation's branches add, so no wrapping hides a chain, and the
    limit is the one measured on lines with no literal ending."""
    assert bounds.date_pattern_problem(pattern) == bounds.DATE_PATTERN_TOO_MANY_WAYS
    assert bounds.DATE_PATTERN_WAYS_MAX == 16_384


def test_an_optional_alternation_is_a_date_pattern():
    """A plain optional may hold an alternation (the re-check's ruling): its
    ways are counted like any other, and ``(?:Dec|12)?`` tries three. Only a
    repetition that can repeat more than once may not hold one. The common
    patterns a person types all pass."""
    for common in [r"(?:Dec|12)?", r"12/31/20\d\d", r"20(24|25)", r"Q[1-4]",
                   r"(0[1-9]|1[0-2])/\d{2}/\d{4}", r"Dec(ember)?\s+31", r"(?:Dec|12)?/31/2025",
                   r"(?:Q4|4th Quarter)?\s*2025", r"\d{1,2}/\d{1,2}/\d{2,4}"]:
        assert bounds.date_pattern_problem(common) == "", common
    assert bounds.date_pattern_problem(r"(?:Dec|12){0,2}") == bounds.DATE_PATTERN_ALTERNATES


def test_every_period_form_derives_a_pattern_the_rule_admits():
    """As the re-check generated them: every year 1900-2100 with TY, FY, a
    bare year and every month's abbreviation and full name, in four
    spellings. None is refused, and none is tried more than 176 ways."""
    forms = [*manifest._MONTHS, *manifest._MONTH_NAMES, "TY", "FY", ""]
    most = 0
    for year in range(1900, 2101):
        for head in forms:
            for period in (f"{head} {year}", f"{head}{year}", f"{head.upper()} {year}", f"{head}  {year}"):
                pattern = manifest.derived_date_pattern(period)
                if pattern:
                    assert bounds.date_pattern_problem(pattern) == "", period
                    most = max(most, bounds._ways(bounds._re_parser.parse(pattern)))
    assert most <= 176


#: The second re-check's table (decision 187's review, M1c): a fixed-count
#: repetition adds no way and hundreds of characters of matching to each -
#: from 0.72 s to 15 s on one 500-character line under the ways rule alone.
COSTLY = [
    "(?:1|11)" * 14 + r"(?:\d\d){200}\D",
    "(?:1|11)" * 13 + r"(?:\d\d){200}\D",
    r"\d{0,20}" * 3 + r"(?:\d\d){200}\D",
    r"\d+\d{0,20}(?:\d\d){150}\D",
    "(?:1|11)?" * 8 + r"(?:\d\d){200}\D",
    "(?:1|11)" * 13 + r"\w{400}\D",
    "(?:1|11)" * 13 + r"\d{300}\D",
    "(?:1|11)?" * 8 + r"\d{300}\D",
    "(?:1|11)" * 13 + r"(?=\d{400})\D",
    r"\d{0,20}" * 3 + r"\d{400}\D",
]


@pytest.mark.parametrize("pattern", COSTLY)
def test_a_fixed_count_of_matching_is_counted_in_the_cost(pattern):
    """A pattern's cost is its ways times the widest match of its bounded
    parts - a fixed ``{n}`` and a lookaround included - and one over
    200,000 is refused."""
    assert bounds.date_pattern_problem(pattern) == bounds.DATE_PATTERN_TOO_COSTLY
    assert bounds.DATE_PATTERN_COST_MAX == 200_000


def test_every_derived_and_common_pattern_is_within_the_cost():
    """Every pattern the Period derives costs at most 6,688, and the ten
    common hand-typed patterns pass the cost rule too."""
    most = 0
    for year in range(1900, 2101):
        for head in [*manifest._MONTHS, *manifest._MONTH_NAMES, "TY", "FY"]:
            pattern = manifest.derived_date_pattern(f"{head} {year}")
            if pattern:
                parsed = bounds._re_parser.parse(pattern)
                most = max(most, bounds._ways(parsed) * bounds._width(parsed))
                assert bounds.date_pattern_problem(pattern) == "", pattern
    assert most <= 6_688
    for common in [r"(?:Dec|12)?", r"12/31/20\d\d", r"20(24|25)", r"Q[1-4]",
                   r"(0[1-9]|1[0-2])/\d{2}/\d{4}", r"Dec(ember)?\s+31", r"(?:Dec|12)?/31/2025",
                   r"(?:Q4|4th Quarter)?\s*2025", r"\d{1,2}/\d{1,2}/\d{2,4}", r"(?:12/31|Dec(?:ember)?\s+31)"]:
        assert bounds.date_pattern_problem(common) == "", common


def test_a_zero_width_assertion_counts_toward_the_width():
    """The third re-check: ``\\B`` matches nothing yet is a test at every
    step, so a fixed group padded with thirty of them did unbounded work per
    counted character - 14.4 s on one 500-digit line. Every zero-width
    assertion counts one toward the width."""
    padded = "(?:1|11)?" * 7 + "(?:" + r"\B" * 30 + r"\d){35}\D"
    assert bounds.date_pattern_problem(padded) == bounds.DATE_PATTERN_TOO_COSTLY
    for assertion in (r"\b", r"\B", "^", "$", r"\A", r"\Z"):
        assert bounds._width(bounds._re_parser.parse(assertion)) == 1, assertion


def test_an_identifier_or_short_name_with_a_spoofing_character_is_refused_by_code_point():
    """P290: both become part of a file name, and a right-to-left override
    there is the classic spoof. The character is named, never quoted. This
    is the store's gate, so it asks the narrow rule (``layout.spoofing_problem``)
    and a no-break space or a soft hyphen an older paste left is admitted."""
    override, joiner = "\u202e", "\u200d"
    for checker in (bounds.identifier_problem, bounds.short_title_problem):
        assert checker("W-2") == ""
        assert checker(f"W-2{override}") == (
            "may not contain an invisible character (U+202E RIGHT-TO-LEFT OVERRIDE)")
        assert "U+200D ZERO WIDTH JOINER" in checker(f"W{joiner}-2")
        assert override not in checker(f"W-2{override}")
        assert checker("A\u00a001") == "" and checker("W\u00adX") == ""


def test_a_document_with_a_spoofing_character_is_refused_by_code_point_and_a_paste_is_not():
    """P301: the Document names a working copy whenever the row has no short
    name of its own (and an issuer row by the entity it names), so the
    store's gate reads it as it reads an identifier or a short name: only the
    spoofing characters, by code point, never quoted. A no-break space or a
    soft hyphen a paste left in an older Document is admitted."""
    assert bounds.document_problem("W-2 Wage Statements") == ""
    assert bounds.document_problem("") == ""
    for hidden, named in (("\u202e", "U+202E RIGHT-TO-LEFT OVERRIDE"),
                          ("\u200b", "U+200B ZERO WIDTH SPACE")):
        said = bounds.document_problem(f"W-2 Wage Statements{hidden}fdp.exe")
        assert said == f"may not contain an invisible character ({named})"
        assert hidden not in said
    assert bounds.document_problem("W-2\u00a0Wage\u00adStatements") == ""


def test_what_a_person_types_is_held_to_the_full_invisible_character_rule():
    """P290: the no-break space and the soft hyphen that the gate admits are
    refused where a person types, by code point."""
    for typed in (bounds.typed_identifier_problem, bounds.typed_short_title_problem):
        assert typed("W-2") == ""
        assert typed("W\u202e-2") == bounds.identifier_problem("W\u202e-2")
        assert "U+00A0 NO-BREAK SPACE" in typed("A\u00a001")
        assert "U+00AD SOFT HYPHEN" in typed("W\u00adX")
    # The other rules come first, in the same words.
    assert bounds.typed_short_title_problem("A" * 21) == bounds.short_title_problem("A" * 21)


def test_a_typed_identifier_longer_than_eighty_characters_is_refused_as_too_long():
    """P291: the typing limit is the typed check's, not the store's gate,
    which keeps the unbounded rule - a record's identifier is not re-judged
    by what a person may type."""
    assert bounds.IDENTIFIER_MAX_CHARS == 80
    assert bounds.typed_identifier_problem("A" * 80) == ""
    assert bounds.typed_identifier_problem("A" * 81) == (
        "may have at most 80 characters, got 81 (it begins a file name)")
    assert bounds.identifier_problem("A" * 200) == ""
    # The other rules come first, in the same words.
    assert bounds.typed_identifier_problem("A:" + "A" * 200) == bounds.identifier_problem("A:")
