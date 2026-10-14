"""Tests for tracker/bounds.py - the value rule's bounds, out of the record.

The claims are the module's whole debt. The bounds reach for nothing in the
package but the layout's name rule, at load time or at call time, and for
no file. Records, which held them until P2.4, still offers every public
name, and each is the very object defined here - the same object, not a
copy - so the editor, the store's gate and every reader that still asks the
record are holding one rule until P2.13 points them here. And the value
rule's tests came with it: each moved from ``tests/test_records.py``
unchanged but for its imports, except the three that read the Date Pattern
analyser's privates, which are read here now because records does not
re-export them.
"""

from __future__ import annotations

import ast
from pathlib import Path

from tests.import_graph import import_edges
from tracker import bounds, manifest, records


def _public_names() -> list[str]:
    """The names bounds binds itself, at module level, without an underscore:
    read off its source, so a name it only imports (the layout's) is not
    counted as its own."""
    tree = ast.parse(Path(bounds.__file__).read_text(encoding="utf-8"))
    names: list[str] = []
    for node in tree.body:
        if isinstance(node, (ast.FunctionDef, ast.ClassDef)):
            names.append(node.name)
        elif isinstance(node, ast.Assign):
            names += [one.id for target in node.targets for one in ast.walk(target) if isinstance(one, ast.Name)]
        elif isinstance(node, ast.AnnAssign) and isinstance(node.target, ast.Name):
            names.append(node.target.id)
    return [name for name in names if not name.startswith("_")]


def test_the_bounds_import_nothing_of_the_package_but_the_layouts_name_rule():
    """A layer 0 module: any layer may ask a bound without loading the
    record's shapes. The Windows character and device rule is the layout's
    (decision 188), which reads no file, and the bounds import it from
    there and nothing else of the package, at load time or at call time."""
    load, call = import_edges()

    assert load["bounds"] == {"layout"}, load["bounds"]
    assert call["bounds"] == set(), call["bounds"]
    assert "bounds" in load["records"], "the record's row checks read the bounds"


def test_the_records_re_export_is_the_bounds_own():
    """Every public name bounds defines resolves from records to this
    module's object - the same object, so ``records.Override`` and
    ``bounds.Override`` cannot be told apart, and a check asked through
    either is the one rule. The facade goes in P2.13."""
    public = _public_names()

    assert {"Override", "YEAR_MIN", "date_pattern_problem", "text_problem"} <= set(public), public
    for name in public:
        assert getattr(records, name) is getattr(bounds, name), name


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
