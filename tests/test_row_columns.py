"""Every path that builds a request row carries every column (decision 145).

A request row is ``RequestItem``, and its columns are ``records.RULE_FIELDS``.
Most readers take the row whole and cannot lose a column. The risk is a
path that *rebuilds* a row by naming each column by hand: when a decision
adds a column, every such path has to learn it, and nothing says so when
one does not - the column quietly takes its default. Decision 142 found two
that had dropped ``named`` since decision 128 (the rollover's ``_carry`` and
the editor's ``editorRow``), and on each a ``named=no`` row came back
``yes``.

So each rebuilding path is held here to the whole column list, **read from
``records.RULE_FIELDS`` at the moment the test runs**, never copied into it.
A row is built in which every column holds a value away from its default
(:func:`_non_default` derives one from the column's type: a boolean is
flipped, a number moved, a text or a list given a marker; the few columns
whose values the parser constrains have a valid one named), pushed through
the path, and every column must come out as it went in. A column added to
``RULE_FIELDS`` tomorrow therefore fails every path that does not carry it,
without anybody editing this file - which is claim 2, proved by adding one.

A column a path deliberately rewrites - the rollover moves a Period on a
year, a catalog row never sets an override - is listed beside that path
**with the decision that makes it** and the rule that decision states, and
claim 3 holds each one to its rule and to actually changing: a column
carried unchanged on every variant is not a rewrite, and listing it would
be a way to hide a drop.

The Status Report's row is text, not a row, so it is held by whether each
column *moves* its cell rather than by equality: a column the report does
not show, or shows as a constant, is dropped from it.

The editor's ``editorRow`` is JavaScript, and the app has no test harness
of its own. It is held two ways: its source must name every column (always
checked), and the function itself - cut out of ``app.js`` byte for byte and
run by node, which the CI job installs before the suite - must hand back a
row that ``item_from_fields`` reads as the row it was given. Running the
real function is the honest check; the source check is what still holds on
a machine without node.
"""

from __future__ import annotations

import dataclasses
import inspect
import io
import itertools
import json
import re
import shutil
import subprocess
from collections.abc import Callable
from dataclasses import dataclass, fields
from pathlib import Path
from types import SimpleNamespace

import pytest

import tracker.api as api
from tests.conftest import app_stdin, make_engagement
from tracker import ledger, records, store, templates, view
from tracker.manifest import (
    ANY_EXTENSION,
    COLUMNS,
    Override,
    RequestItem,
    Status,
    derived_date_pattern,
    entity_keyword,
    has_arrived,
    issuer_short_title,
    item_from_fields,
    item_from_record,
    list_head,
    load_engagement_info,
    load_manifest,
    save_rules,
    shift_years,
)
from tracker.rollover import _carry

APP_JS = Path(__file__).resolve().parents[1] / "app" / "renderer" / "app.js"


class _Missing:
    """What a path handed back for a column it does not carry at all."""

    def __repr__(self) -> str:
        return "<no such column>"


MISSING = _Missing()

_ITEM_FIELDS = {f.name: f for f in fields(RequestItem)}

#: The columns whose values the row's parser constrains, each with a value
#: it accepts that is not the default. Every other column - and any column
#: added later - takes :func:`_non_default`'s value from its type. A year
#: is in the document and the Period so the rewrites that move a year are
#: seen to move it; the override is Not Applicable so it carries a reason.
_CONSTRAINED: dict[str, object] = {
    "document": "Marker Statement 2031",
    "period": "TY2031",
    "allowed_extensions": ("heic", "tif"),
    "date_pattern": r"marker-\d{3}",
    "manual_override": Override.NOT_APPLICABLE,
    "override_reason": "set aside by the marker",
}


def _default(column: str) -> object:
    """The column's default in ``RequestItem``, or MISSING (no default, or
    no such field)."""
    spec = _ITEM_FIELDS.get(column)
    if spec is None or spec.default is dataclasses.MISSING:
        return MISSING
    return spec.default


def _non_default(column: str) -> object:
    """A value for ``column`` that is not its default, derived from its type."""
    if column in _CONSTRAINED:
        return _CONSTRAINED[column]
    default = _default(column)
    if isinstance(default, bool):
        return not default
    if isinstance(default, int):
        return default + 7
    if isinstance(default, tuple):
        return (f"{column} marker",)
    return f"{column}-marker"


def _other(column: str) -> object:
    """A second value for ``column``: its default, or another marker."""
    default = _default(column)
    return f"{column}-other" if default is MISSING else default


def full_row() -> dict[str, object]:
    """Every column ``records.RULE_FIELDS`` names *now*, each away from its default."""
    return {column: _non_default(column) for column in records.RULE_FIELDS}


#: The rows every path is driven with: the full row, and the variants a
#: rewrite needs to be seen both ways. Status fields are not columns of the
#: rule; the rollover reads them, so a variant may set them.
_VARIANTS: dict[str, tuple[dict[str, object], dict[str, object]]] = {
    "every column set": ({}, {}),
    "a typed date pattern": ({"date_pattern_derived": False}, {}),
    "accepted, not set aside": ({"manual_override": Override.ACCEPTED}, {}),
    "a document arrived": ({}, {"status": Status.RECEIVED, "file_count": 11}),
}
BASE = "every column set"
TYPED = "a typed date pattern"


def _variant(name: str) -> tuple[dict[str, object], dict[str, object]]:
    changes, status = _VARIANTS[name]
    return {**full_row(), **changes}, dict(status)


def _item(values: dict, status: dict | None = None) -> RequestItem:
    """A ``RequestItem`` of the columns it has (a column it lacks is lost here,
    and shows as dropped)."""
    return RequestItem(**{k: v for k, v in values.items() if k in _ITEM_FIELDS}, **(status or {}))


def _columns_of(item: object) -> dict[str, object]:
    return {column: getattr(item, column, MISSING) for column in records.RULE_FIELDS}


def _as_json(values: dict) -> dict:
    """The row as JSON carries it: the word lists as lists."""
    return {k: list(v) if isinstance(v, tuple) else v for k, v in values.items()}


def _from_json(row: dict) -> dict[str, object]:
    return {column: (tuple(row[column]) if isinstance(row.get(column), list) else row.get(column, MISSING))
            for column in records.RULE_FIELDS}


# ------------------------------------------------------------ the rewrites ----


@dataclass(frozen=True)
class Rewrite:
    """A column a path changes on purpose: the decision, and its rule
    ``(values, status, what came out) -> as the decision says``."""

    reason: str
    rule: Callable[[dict, dict, object], bool]


def _position(expected: int, why: str) -> Rewrite:
    return Rewrite(why, lambda v, s, out: out == expected)


def _never_set(why: str, column: str) -> Rewrite:
    return Rewrite(why, lambda v, s, out: out == _default(column))


def _not_shown(why: str) -> Rewrite:
    return Rewrite(why, lambda v, s, out: out is MISSING)


_DERIVED_NOT_TYPED = Rewrite(
    "a derived year check was never typed, so it is read as none typed and the Period derives it "
    "again (decision 40)",
    lambda v, s, out: out == ("" if v["date_pattern_derived"] else v["date_pattern"]))
_DERIVED_IS_VALIDATEDS = Rewrite(
    "whether a year check was derived is validated()'s to say, not the row's (decision 40)",
    lambda v, s, out: out is False)
_POSITION_IS_VALIDATEDS = _position(
    0, "the row's position is numbered by validated() when the list is saved (decision 104)")


def _validated_pattern(v: dict, s: dict, out: object) -> bool:
    return out == (derived_date_pattern(str(v["period"])) if v["date_pattern_derived"] else v["date_pattern"])


#: The catalog's own columns never include these; each takes the default.
def _catalog_never_sets() -> dict[str, Rewrite]:
    reasons = {
        "row": "the row's position is numbered by validated() (decision 104)",
        "date_pattern": "a catalog row's year check is derived from its Period, never typed (decision 40)",
        "date_pattern_derived": "a catalog row's year check is derived from its Period, never typed (decision 40)",
        "min_size_kb": "every catalog row takes the firm's size floor; a person changes it per return "
                       "in the editor (decision 104)",
        "manual_override": "an override is a person's judgment on one return, never the catalog's (decision 116)",
        "override_reason": "an override is a person's judgment on one return, never the catalog's (decision 116)",
        "asked": "the wizard's tick sets it (the row's `core` only pre-ticks it), not the row (decision 142)",
    }
    return {column: _never_set(why, column) for column, why in reasons.items()}


# --------------------------------------------------------------- the paths ----


@dataclass(frozen=True)
class RowPath:
    """One path that builds a request row, and what it rewrites on purpose.

    ``hand_listed``: it names the columns itself, so a column added to
    ``RULE_FIELDS`` reaches it only if somebody teaches it. ``sensitive``:
    its output is not a row, so a column is carried when changing it moves
    the output, not when it comes back equal.
    """

    name: str
    run: Callable[[dict, dict, SimpleNamespace], dict[str, object]]
    rewrites: dict[str, Rewrite]
    variants: tuple[str, ...] = (BASE, TYPED)
    hand_listed: bool = True
    sensitive: bool = False


def _fields_and_back(values, status, ctx):
    """``manifest.item_from_fields``: a row's fields to a ``RequestItem``, and
    that item's fields read again, which must be the same item."""
    item = item_from_fields(values, where="Row 1")
    again = item_from_fields({k: v for k, v in _columns_of(item).items() if v is not MISSING}, where="Row 1")
    assert again == item, "item_from_fields does not read its own row back as the same row"
    return _columns_of(item)


#: ``templates._row``'s arguments, by the column each one sets, and how the
#: catalog writes that column. A ``_row`` argument missing here fails the
#: path: a new catalog column must be declared.
_ROW_ARGUMENTS: dict[str, tuple[str, Callable[[object], object]]] = {
    "identifier": ("identifier", str),
    "document": ("document", str),
    "period": ("period", str),
    "allowed_extensions": ("extensions", ", ".join),
    "named": ("named", bool),
    "required_keywords": ("required_keywords", ", ".join),
    "any_keywords": ("any_keywords", ", ".join),
    "expected_count": ("expected_count", int),
    "short_title": ("short", str),
}


def _catalog_spec(values: dict) -> dict:
    parameters = set(inspect.signature(templates._row).parameters) - {"core"}
    assert parameters == {name for name, _ in _ROW_ARGUMENTS.values()}, (
        "templates._row takes an argument this test does not know; say which column it sets")
    return templates._row(core=False, **{name: convert(values[column])
                                         for column, (name, convert) in _ROW_ARGUMENTS.items()
                                         if column in values})


def _catalog_row(values, status, ctx):
    """``templates._row`` -> ``item_from_spec``: a catalog row as the wizard reads it."""
    return _columns_of(templates.item_from_spec(_catalog_spec(values)))


ISSUER = "Marker Holdings, L.P."
ISSUER_IDENTIFIER = "F09"


def _issuer_row(values, status, ctx):
    """``templates.issuer_row`` cut from a K-1 row that sets every catalog column."""
    source = _catalog_spec(values)
    ctx.monkeypatch.setattr(templates, "k1_row", lambda: source)
    return _columns_of(templates.item_from_spec(templates.issuer_row(ISSUER_IDENTIFIER, ISSUER)))


def _rollover(values, status, ctx):
    """``rollover._carry``: next year's row from last year's, with no template."""
    item, _, _ = _carry(_item(values, status), None, 1, 1)
    return _columns_of(item)


def _status_report(values, status, ctx):
    """``view.request_row``: each column's cell, found by its header."""
    cells = view.request_row(_item(values, status))
    return {column: cells.get(header, MISSING) for header, column in COLUMNS}


def _new_return(ctx, items) -> Path:
    return make_engagement(ctx.root, items, return_name=f"Row Columns {next(ctx.made)}", scaffold=False)


#: The asked row every list beside the full row needs (a list nobody is
#: asked for is refused). Its file types are left at the default, any, so
#: the API path carries an any-file-type row too.
COMPANION = RequestItem(identifier="A01", document="W-2", required_keywords=("W-2",))


def _through_the_record(values, status, ctx):
    """The store's write and read, and the journal's fold of a request-list edit.

    Created with a placeholder, then **edited** to the full row, so what is
    read back went through a ``rules_changed`` event of a change: read from
    the store, folded from the journal, and rebuilt from the journal alone,
    all three the same row.
    """
    identifier = str(values["identifier"])
    folder = _new_return(ctx, [COMPANION, RequestItem(identifier=identifier, document="Placeholder")])
    save_rules(folder, [COMPANION, _item(values)], load_engagement_info(folder))
    read = {i.identifier: i for i in load_manifest(folder)}[identifier]
    folded = item_from_record(ledger.rules(ledger.read_events(folder))[identifier])
    store.rebuild_engagement(store.connect(), ctx.root, folder)
    rebuilt = {i.identifier: i for i in load_manifest(folder)}[identifier]
    assert records.rule_to_json(read) == records.rule_to_json(folded) == records.rule_to_json(rebuilt)
    return _columns_of(read)


def _api(ctx, *argv, stdin=None) -> dict:
    """One API command, as the app sends it. An ``edit`` carries the list's
    version the way the editor does (decision 160): the one ``state`` would
    have handed out now, unless the call names its own."""
    if stdin is not None and argv[0] == "edit" and "head" not in stdin:
        stdin = {**stdin, "head": list_head(argv[argv.index(api.ENGAGEMENT_FLAG) + 1])}
    if stdin is not None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sys.stdin", app_stdin(stdin))
            code = api.main(list(argv))
    else:
        code = api.main(list(argv))
    [line] = ctx.capsys.readouterr().out.strip().splitlines()
    payload = json.loads(line)
    assert code == 0, payload
    return payload


def _through_the_api(values, status, ctx):
    """The API's request-list read and write: the rules the app receives in
    ``state``, sent back unchanged through ``edit``, record nothing - every
    column came back as it went - and read back the same."""
    identifier = str(values["identifier"])
    folder = _new_return(ctx, [COMPANION, _item(values)])
    rules = _api(ctx, "state", api.ENGAGEMENT_FLAG, str(folder))["rules"]
    saved = _api(ctx, "edit", api.ENGAGEMENT_FLAG, str(folder), stdin={"items": rules, "engagement": {}})
    assert saved["saved"]["recorded"] is False, saved["saved"]
    [back] = [row for row in saved["state"]["rules"] if row["identifier"] == identifier]
    return _from_json(back)


def _editor_row_source() -> str:
    """``editorRow`` exactly as ``app.js`` spells it, braces matched."""
    text = APP_JS.read_text(encoding="utf-8")
    start = text.index("function editorRow(rule) {")
    depth = 0
    for at in range(text.index("{", start), len(text)):
        depth += {"{": 1, "}": -1}.get(text[at], 0)
        if depth == 0:
            return text[start:at + 1]
    raise AssertionError("editorRow in app.js has no closing brace")


def _editor_keys() -> set[str]:
    """The keys ``editorRow``'s object literal names (its top level)."""
    return set(re.findall(r"^ {4}(\w+):", _editor_row_source(), flags=re.MULTILINE))


def _editor_names(values, status, ctx):
    """The editor's row, read from its source: a column it names is carried."""
    keys = _editor_keys()
    return {column: (values[column] if column in keys else MISSING) for column in records.RULE_FIELDS}


def _run_editor_rows(rules: list[dict], ctx) -> list[dict]:
    """The real ``editorRow`` over ``rules``, run by node with the API's own
    vocabulary; skipped where node is not on PATH."""
    node = shutil.which("node")
    if node is None:
        pytest.skip("node is not on PATH (CI installs it); the editor's source is still held by name")
    script = ctx.tmp_path / "editor_row.js"
    script.write_text(
        "const input = JSON.parse(require('fs').readFileSync(0, 'utf8'));\n"
        "const vocab = input.vocab;\n"
        f"{_editor_row_source()}\n"
        "process.stdout.write(JSON.stringify(input.rules.map(editorRow)));\n",
        encoding="utf-8", newline="\n")
    done = subprocess.run([node, str(script)], input=json.dumps({"vocab": api._vocab(), "rules": rules}),
                          capture_output=True, text=True, encoding="utf-8", timeout=60, check=False)
    assert done.returncode == 0, done.stderr
    return json.loads(done.stdout)


def _editor_row(values, status, ctx):
    """The editor's round trip: the rule as the API hands it, through the
    real ``editorRow`` (run by node), back through ``item_from_fields`` as
    the save reads it."""
    [row] = _run_editor_rows([_as_json(values)], ctx)
    return _columns_of(item_from_fields(row, where="Row 1"))


_VALIDATED = {
    "row": _position(2, "the row's position in the list, which validated() numbers (decision 104)"),
    "date_pattern": Rewrite("a derived year check is derived again from the Period by validated() "
                            "(decision 40)", _validated_pattern),
}

PATHS: tuple[RowPath, ...] = (
    RowPath("manifest.item_from_fields, and back", _fields_and_back, {
        "row": _POSITION_IS_VALIDATEDS,
        "date_pattern": _DERIVED_NOT_TYPED,
        "date_pattern_derived": _DERIVED_IS_VALIDATEDS,
    }),
    RowPath("templates._row", _catalog_row, _catalog_never_sets(), variants=(BASE,)),
    RowPath("templates.issuer_row", _issuer_row, {
        **_catalog_never_sets(),
        "identifier": Rewrite("the next free identifier in the K-1 row's section, given by the person "
                              "(decision 128's issuer rows)", lambda v, s, out: out == ISSUER_IDENTIFIER),
        "document": Rewrite("the issuer's name in the Document, so the folder says whose K-1 it is "
                            "(decision 128's issuer rows)",
                            lambda v, s, out: out == templates.ISSUER_DOCUMENT.format(entity=entity_keyword(ISSUER))),
        "required_keywords": Rewrite("the issuer's name is the row's Required Keyword (decision 128's issuer rows)",
                                     lambda v, s, out: out == (entity_keyword(ISSUER),)),
        "short_title": Rewrite("K-1 and the issuer, so the firm's folder says whose K-1 it is, by the one "
                               "function a typed K-1 row derives it through too (decision 144)",
                               lambda v, s, out: out == issuer_short_title(entity_keyword(ISSUER))),
    }, variants=(BASE,)),
    RowPath("rollover._carry", _rollover, {
        "row": _POSITION_IS_VALIDATEDS,
        "document": Rewrite("every year in it moves with the year (decision 36)",
                            lambda v, s, out: out == shift_years(str(v["document"]), 1)),
        "period": Rewrite("every year in it moves with the year (decision 36)",
                          lambda v, s, out: out == shift_years(str(v["period"]), 1)),
        "date_pattern": Rewrite(
            "a derived year check is not carried as text, a typed one moves with the year (decision 40)",
            lambda v, s, out: out == ("" if v["date_pattern_derived"] else shift_years(str(v["date_pattern"]), 1))),
        "date_pattern_derived": _DERIVED_IS_VALIDATEDS,
        "expected_count": Rewrite(
            "counts learn from what arrived and never shrink (decision 9's precedence)",
            lambda v, s, out: out == max(v["expected_count"],
                                         (s.get("file_count") or 0) if s.get("status") == Status.RECEIVED else 0)),
        "manual_override": Rewrite(
            "Not Applicable carries, Accepted judged last year's files and does not (decision 10)",
            lambda v, s, out: out == (v["manual_override"] if v["manual_override"] == Override.NOT_APPLICABLE else "")),
        "override_reason": Rewrite(
            "the reason travels with the override that carries, and only with it (decisions 10 and 116)",
            lambda v, s, out: out == (v["override_reason"] if v["manual_override"] == Override.NOT_APPLICABLE else "")),
        "asked": Rewrite(
            "a row nobody asked for that a document arrived for is asked next year (decision 142), and "
            "an Accepted row is one that arrived (decision 33)",
            lambda v, s, out: out == (v["asked"] or has_arrived(_item(v, s)))),
    }, variants=tuple(_VARIANTS)),
    RowPath("view.request_row", _status_report, {
        "row": _not_shown("the report lists the rows in their order; the position is not a column (decision 104)"),
        "date_pattern_derived": _not_shown(
            "the report shows the year check whichever way it came; derived is not a column (decision 40)"),
    }, sensitive=True),
    RowPath("store and journal", _through_the_record, dict(_VALIDATED), hand_listed=False),
    RowPath("api state and edit", _through_the_api, dict(_VALIDATED), hand_listed=False),
    RowPath("app.js editorRow, by name", _editor_names, {
        "row": _not_shown("the editor never holds the position; the save numbers it (decision 104)"),
        "date_pattern_derived": _not_shown(
            "folded into the Date Pattern cell, blank when derived (decision 40)"),
    }, variants=(BASE,)),
    RowPath("app.js editorRow, run", _editor_row, {
        "row": _POSITION_IS_VALIDATEDS,
        "date_pattern": _DERIVED_NOT_TYPED,
        "date_pattern_derived": _DERIVED_IS_VALIDATEDS,
    }),
)


@pytest.fixture
def ctx(short_root, tmp_path, capsys, monkeypatch):
    """Where a path may make a return: a clients root recorded the way the app
    records it, the settings beside it, and a counter for unique names."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(short_root)
    return SimpleNamespace(root=short_root, tmp_path=tmp_path, capsys=capsys, monkeypatch=monkeypatch,
                           made=itertools.count(1))


def _dropped(path: RowPath, variant: str, ctx) -> list[tuple[str, object, object]]:
    """Every column the path loses on ``variant``: (column, what came out,
    what went in). Rewrites are claim 3's."""
    values, status = _variant(variant)
    out = path.run(values, status, ctx)
    missed = []
    for column in records.RULE_FIELDS:
        if column in path.rewrites:
            continue
        got = out.get(column, MISSING)
        if path.sensitive:
            moved = path.run({**values, column: _other(column)}, status, ctx).get(column, MISSING)
            if got is MISSING or got == moved:
                missed.append((column, got, values[column]))
        elif got != values[column]:
            missed.append((column, got, values[column]))
    return missed


# ------------------------------------------------------------------ claims ----


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.name)
def test_every_row_building_path_carries_every_column(path, ctx):
    """Every column of ``RULE_FIELDS``, each away from its default, comes out
    of the path as it went in - bar the rewrites claim 3 holds."""
    row = full_row()
    assert all(row[column] != _default(column) for column in row), "the full row must move every column"
    for variant in path.variants:
        assert _dropped(path, variant, ctx) == [], f"{path.name} drops a column ({variant})"


def test_a_new_column_fails_every_path_that_does_not_know_it(monkeypatch, ctx):
    """A column added to ``RULE_FIELDS`` and taught to nobody is dropped by
    every hand-listing path - and only that column - and the paths that read
    the list itself fail loudly rather than quietly."""
    added = "column_added_by_decision_145s_test"
    monkeypatch.setattr(records, "RULE_FIELDS", (*records.RULE_FIELDS, added))

    hand_listed = [path for path in PATHS if path.hand_listed]
    assert len(hand_listed) >= 6
    for path in hand_listed:
        try:
            missed = {column for column, _, _ in _dropped(path, path.variants[0], ctx)}
        except pytest.skip.Exception:
            continue
        assert missed == {added}, f"{path.name}: {missed}"

    with pytest.raises(AttributeError, match=added):
        records.rule_to_json(COMPANION)
    assert tuple(store.RULE_COLUMNS) != records.RULE_FIELDS     # tests/test_store.py's guard would fail


@pytest.mark.parametrize("path", PATHS, ids=lambda p: p.name)
def test_the_deliberate_rewrites_are_the_ones_the_decisions_name(path, ctx):
    """Each listed rewrite names its decision, comes out exactly as that
    decision says on every variant, and does change on at least one - a
    column carried unchanged is not a rewrite, and listing it would hide a
    drop."""
    changed: set[str] = set()
    for variant in path.variants:
        values, status = _variant(variant)
        out = path.run(values, status, ctx)
        for column, rewrite in path.rewrites.items():
            assert re.search(r"decisions? \d+", rewrite.reason), rewrite.reason
            got = out.get(column, MISSING)
            assert rewrite.rule(values, status, got), f"{path.name} {column} ({variant}): {got!r}; {rewrite.reason}"
            if got != values[column]:
                changed.add(column)
    assert changed == set(path.rewrites), f"{path.name} lists a rewrite that never changes: " \
                                          f"{sorted(set(path.rewrites) - changed)}"



def test_the_api_hands_out_rules_it_reads_back_unchanged(ctx):
    """``state`` hands every rule out in the form ``edit`` reads back as the
    same rule, so the rules sent back unchanged record nothing - for every
    column of ``RULE_FIELDS`` at its default as well as away from it.

    One row per column: the full row with that one column set back to its
    default. An any-file-type row (``allowed_extensions`` at its default,
    ``()``) was handed out as ``[]``, which ``edit`` reads as blank - the
    default types - so the save recorded a change nobody made (decision
    145). The one column whose default alone is not a legal row is the
    override: a reason with no override is refused (decision 116), so its
    row clears the reason with it.
    """
    rows = [COMPANION, RequestItem(identifier="B01", document="Every column at its default")]
    for n, column in enumerate(records.RULE_FIELDS, start=1):
        values = {**full_row(), column: _other(column)}
        if column == "manual_override":
            values["override_reason"] = _default("override_reason")
        values["identifier"] = f"C{n:02}"
        rows.append(_item(values))
    folder = _new_return(ctx, rows)
    sent = _api(ctx, "state", api.ENGAGEMENT_FLAG, str(folder))["rules"]
    saved = _api(ctx, "edit", api.ENGAGEMENT_FLAG, str(folder), stdin={"items": sent, "engagement": {}})
    assert saved["saved"]["changed"] == [] and saved["saved"]["recorded"] is False, saved["saved"]
    assert saved["state"]["rules"] == sent
    stored = {i.identifier: records.rule_to_json(i) for i in load_manifest(folder)}
    for rule in sent:
        assert item_from_fields(rule, where=rule["identifier"]).allowed_extensions ==             tuple(stored[rule["identifier"]]["allowed_extensions"]), rule["identifier"]

    # And the app reads the same rules the same way: the real editorRow
    # opens on them (an any-file-type row shows the star, as before) and
    # its rows, saved untouched, record nothing either.
    if shutil.which("node") is not None:
        opened = _run_editor_rows(sent, ctx)
        assert {row["identifier"]: row["allowed_extensions"] for row in opened}["B01"] == ANY_EXTENSION
        saved = _api(ctx, "edit", api.ENGAGEMENT_FLAG, str(folder), stdin={"items": opened, "engagement": {}})
        assert saved["saved"]["recorded"] is False, saved["saved"]


def test_a_save_without_a_column_keeps_its_recorded_value(ctx):
    """A row saved without a column keeps what the record holds for it
    (decision 160, the audit's E2) - for every column of ``RULE_FIELDS``,
    read from 145's list as the test runs, each away from its default.

    An older window or build sends its rows without the columns added since
    it was built. Each such column used to take its default, and the save
    journalled that as a change nobody made: a short name (decision 144)
    blanked, a row the firm set not asked (decision 142) asked again and
    back in the client's letter. Absent means unchanged, as it already did
    for the engagement's details. ``row`` is the position the save numbers
    from the list's order, and ``date_pattern_derived`` travels with the
    date pattern it describes: left out beside the pattern the record
    holds, the pattern is still the derived one. ``identifier`` is the one
    column that cannot be left out: it is what a sent row is matched to its
    recorded row by.

    One row per column, each with that one column left out, and one real
    change on the companion so the save records an event.
    """
    rows = [COMPANION]
    targets = {}
    for n, column in enumerate(records.RULE_FIELDS, start=1):
        if column == "identifier":
            continue            # the key a sent row is matched to its recorded row by
        values = {**full_row(), "identifier": f"C{n:02}"}
        rows.append(_item(values))
        targets[f"C{n:02}"] = column
    folder = _new_return(ctx, rows)
    state = _api(ctx, "state", api.ENGAGEMENT_FLAG, str(folder))
    before = {rule["identifier"]: rule for rule in state["rules"]}
    sent = []
    for rule in state["rules"]:
        rule = dict(rule)
        if rule["identifier"] in targets:
            del rule[targets[rule["identifier"]]]
        elif rule["identifier"] == COMPANION.identifier:
            rule["expected_count"] = rule["expected_count"] + 1
        sent.append(rule)
    saved = _api(ctx, "edit", api.ENGAGEMENT_FLAG, str(folder), stdin={"items": sent, "engagement": {}})
    assert saved["saved"]["changed"] == [COMPANION.identifier], saved["saved"]
    after = {rule["identifier"]: rule for rule in saved["state"]["rules"]}
    for identifier, column in targets.items():
        assert after[identifier] == before[identifier], f"{column} left out of {identifier}"


def test_a_save_with_a_column_this_version_does_not_know_is_refused(ctx):
    """A row carrying a key that is no column of ``RULE_FIELDS`` is a newer
    window's row, or a mistake: refused by row and key, and nothing is
    recorded (decision 160)."""
    folder = _new_return(ctx, [COMPANION])
    state = _api(ctx, "state", api.ENGAGEMENT_FLAG, str(folder))
    before = ledger.path_for(folder).read_bytes()
    rows = [{**state["rules"][0], "column_from_a_newer_build": "x"}]
    with ctx.monkeypatch.context() as mp:
        mp.setattr("sys.stdin", io.StringIO(json.dumps(
            {"items": rows, "engagement": {}, "head": list_head(folder)})))
        code = api.main(["edit", api.ENGAGEMENT_FLAG, str(folder)])
    payload = json.loads(ctx.capsys.readouterr().out)
    assert code == 1
    assert payload["error"] == api.UNKNOWN_COLUMN.format(n=1, key="column_from_a_newer_build")
    assert ledger.path_for(folder).read_bytes() == before
