"""Recordings of what the program says and does today, to compare a move against.

The phases after SPEC-architecture's first tranche move code between modules,
and a move must change nothing anyone can see. The suite's claims each check
what they were written to check; a reply that gains or loses a key nobody's
claim reads, or a document that files under another request, can pass all of
them. So this file keeps three kinds of recording in ``tests/golden/`` and
holds the program to them (J4, R4.3; findings E-2, E-7):

- ``vocab.keys.json``: the key tree of ``api._vocab()``, the words the app
  draws, as keys and value types.
- ``replies.<command>.keys.json``: the key tree of the reply to each command
  the app's screens are drawn from - ``list``, ``state``, ``edit-household``,
  ``firm``, ``firm-last``, ``reminder``, ``edit``, ``assign`` and ``create`` -
  on a scratch clients root holding one return and the sample pile.
- ``pass.samples.json``: one whole pass over that pile, the app's Sort &
  Scan: per index row the decision word, the reason code and where the
  working copy went, relative to the return, and the kinds of the events in
  the return's record and in its household's, in order.

**Only made-up data, and nothing that moves on its own.** The pile is
``tests/samples.py``'s; the scratch root is a short temporary folder (the
tripwire, decision 185, fails a run that reaches a real root). A key tree
holds keys and the names of value types, never a value: no sentence, no name,
no path, no date and no count. A table keyed by data - the ``paths`` of a
reply, keyed by kind and path, or anything keyed by a year or a household's
name - is one ``<map>`` entry with the shape of its values, so a recording
names no folder and no year. The pass records words and codes the program
defines, file names from the pile, and locations relative to the return, in
the index's own order - the pass's, which sorts the inbox by name without
case, so it is the same on every file system.

**The calendar.** The program reads today's date, and the recordings do not
hold it. Freezing the clock was the rejected alternative: a stand-in for the
date in every module that reads it would itself be a set of stand-ins a move
must keep pointed right, and a frozen clock next to real file times turns a
lock into a stale one. Instead what is recorded does not depend on the day:
the return's tax year is the pile's own (``YEAR``), Run now drafts no letter,
and the return names no Due Date, so the letter's stage is the first for ever.
What still moves is the roll a household is offered once the year after its
tax year has ended (decision 196): from 1 January of ``YEAR + 2`` its
``roll_year`` is a number, not null - the day the suite's sample pile is
re-dated anyway.

**When a recording differs**, the failure names the file and every path in
it that changed. A move that changes one changed behaviour: stop and find out
why (the migration guide's step 8). A change meant to be seen is recorded
again with ``pytest tests/test_golden.py --record-golden`` in the same commit,
and the diff of ``tests/golden/`` is part of what the review reads.
"""

from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

import tracker.api as api
from tests import passes
from tests.api_driver import HOUSEHOLD, SAMPLE_PEOPLE, run, scan, where
from tests.conftest import RECORD_GOLDEN
from tests.samples import SCRATCH_RETURN, YEAR
from tracker import ledger
from tracker.bounds import Override
from tracker.filer import NEEDS_REVIEW, read_index
from tracker.layout import household_of, inbox_of

GOLDEN = Path(__file__).resolve().parent / "golden"

#: The sample pile, built once per session: a fixture of ``tests/passes.py``.
samples = passes.samples

#: A key the program wrote: a word, or a few words with a space between (the
#: status labels, ``Not asked``). Any other key - a path, a year, a sentence -
#: is data, and its table is recorded as one :data:`MAP` entry.
WORD = re.compile(r"[A-Za-z_][A-Za-z0-9_-]*(?: [A-Za-z][A-Za-z0-9_-]*)*")
MAP = "<map>"
#: A list whose items are not all of one kind (dicts, lists or values).
ANY_OF = "<any of>"
#: The value types a key tree can name: what ``json.loads`` gives.
TYPES = frozenset({"str", "int", "float", "bool", "NoneType"})

#: The commands whose replies are recorded, in the order the scene asks
#: them. ``household`` in the SPEC is ``edit-household``: the API has no
#: ``household`` command, and the household's card is the state reply's.
REPLIES = ("create", "list", "state", "firm", "firm-last", "reminder", "edit-household", "edit", "assign")

#: The firm the scratch root is recorded for, as ``demo_root`` records it.
FIRM = "J Park & Associates, CPA"


# ------------------------------------------------------------ the key trees ----


def shape(value: object) -> object:
    """``value`` as its key tree: a dict's keys with the shape of each value,
    a list as the one shape its items share, and a value as its type."""
    if isinstance(value, dict):
        if not all(isinstance(key, str) and WORD.fullmatch(key) for key in value):
            return {MAP: merged([shape(one) for one in value.values()])}
        return {key: shape(value[key]) for key in sorted(value)}
    if isinstance(value, list):
        return [merged([shape(one) for one in value])] if value else []
    return type(value).__name__


def merged(shapes: list[object]) -> object:
    """The one shape a list's items share: every key any item has, and every
    type a value takes, joined (``NoneType|str``)."""
    dicts = [one for one in shapes if isinstance(one, dict)]
    lists = [one for one in shapes if isinstance(one, list)]
    leaves = sorted({one for one in shapes if isinstance(one, str)})
    kinds = []
    if leaves:
        kinds.append("|".join(leaves))
    if dicts:
        keys = sorted({key for one in dicts for key in one})
        kinds.append({key: merged([one[key] for one in dicts if key in one]) for key in keys})
    if lists:
        inner = [one[0] for one in lists if one]
        kinds.append([merged(inner)] if inner else [])
    return kinds[0] if len(kinds) == 1 else {ANY_OF: kinds} if kinds else []


# ------------------------------------------------------------ the recordings ----


def _text(recording: object) -> str:
    return json.dumps(recording, indent=2, sort_keys=True, ensure_ascii=True) + "\n"


def differences(recorded: object, now: object, at: str = "") -> list[str]:
    """Every path at which ``now`` is not ``recorded``, said plainly."""
    here = at or "the top"
    if isinstance(recorded, dict) and isinstance(now, dict):
        said = [f"{at}.{key}: recorded, now gone" for key in sorted(set(recorded) - set(now))]
        said += [f"{at}.{key}: new, not recorded" for key in sorted(set(now) - set(recorded))]
        for key in sorted(set(recorded) & set(now)):
            said += differences(recorded[key], now[key], f"{at}.{key}")
        return said
    if isinstance(recorded, list) and isinstance(now, list):
        if len(recorded) != len(now):
            return [f"{here}: {len(recorded)} recorded, {len(now)} now"
                    + "".join(f"\n    {line}" for line in differences(recorded[:len(now)], now[:len(recorded)],
                                                                         at))]
        return [line for number, (old, new) in enumerate(zip(recorded, now, strict=True))
                for line in differences(old, new, f"{at}[{number}]")]
    return [] if recorded == now else [f"{here}: recorded {json.dumps(recorded)}, now {json.dumps(now)}"]


def held_to(name: str, now: object, record: bool) -> list[str]:
    """Write ``now`` to ``tests/golden/<name>`` when recording; otherwise what
    differs between it and the recording there, each line led by the file."""
    path = GOLDEN / name
    if record:
        GOLDEN.mkdir(exist_ok=True)
        path.write_text(_text(now), encoding="utf-8", newline="\n")
        return []
    if not path.is_file():
        return [f"{name}: no recording; run pytest tests/test_golden.py {RECORD_GOLDEN}"]
    recorded = json.loads(path.read_text(encoding="utf-8"))
    return [f"{name}: {line}" for line in differences(recorded, json.loads(_text(now)))]


def _verdict(lines: list[str]) -> None:
    assert not lines, ("what the program says or does is not what tests/golden/ recorded. A move that "
                       "changes it changed behaviour; a change meant to be seen is recorded again with "
                       f"pytest tests/test_golden.py {RECORD_GOLDEN}:\n  " + "\n  ".join(lines))


@pytest.fixture
def record(request) -> bool:
    return bool(request.config.getoption(RECORD_GOLDEN))


# ------------------------------------------------------------------ the scene ----


@pytest.fixture
def scratch_root(short_root, tmp_path, monkeypatch):
    """A small clients root recorded the way the app records it (the fixture
    ``test_api`` and ``test_shell`` use, spelled here so this file does not
    import a test file's fixture)."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root, set_firm

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(short_root)
    set_firm(FIRM)
    return short_root


def _the_pass(engagement: Path) -> dict:
    """What the pass left: each index row's decision, code and destination,
    in the index's order, and the records' event kinds in order."""
    return {
        "index": [{"original": row.original_name, "decision": row.decision, "code": row.code,
                   "destination": row.prepared_location.replace("\\", "/"),
                   "also_filed": row.also_filed.replace("\\", "/")} for row in read_index(engagement)],
        "return_record": [event[ledger.EVENT_KEY] for event in ledger.read_events(engagement)],
        "household_record": [event[ledger.EVENT_KEY] for event in ledger.read_events(household_of(engagement))],
    }


def test_the_vocabulary_has_the_recorded_key_tree(record):
    _verdict(held_to("vocab.keys.json", shape(api._vocab()), record))


def test_the_replies_and_a_pass_over_the_sample_pile_are_the_recorded_ones(capsys, scratch_root, samples, record):
    """One return created through the API, the pile dropped in its
    household's inbox, Sort & Scan, and then each screen's command; the pass
    is recorded straight after Sort & Scan, before an edit or an assign
    changes the record."""
    replies: dict[str, dict] = {}
    spec = {"household": HOUSEHOLD, "return_name": SCRATCH_RETURN, "form": "1040", "year": YEAR,
            "client": "John Smith", "people": SAMPLE_PEOPLE,
            "items": [one for one in api.FORM_TEMPLATES["1040"] if one["core"]]}
    code, replies["create"] = run(capsys, "create", stdin=spec)
    assert code == 0, replies["create"]
    engagement = where(scratch_root, SCRATCH_RETURN, year=YEAR)
    for sample in sorted(samples.iterdir()):
        (inbox_of(engagement) / sample.name).write_bytes(sample.read_bytes())
    code, scanned = scan(capsys, engagement)
    assert code == 0, scanned
    the_pass = _the_pass(engagement)

    asked = (api.ENGAGEMENT_FLAG, str(engagement))
    for command, argv, stdin in (("list", (), None), ("state", asked, None), ("firm", (), None),
                                 (api.FIRM_LAST_COMMAND, (), None), ("reminder", asked, {"stage": None}),
                                 ("edit-household", asked, {"members": ["John A. Smith", "Jane R. Smith"],
                                                            "contact": "John & Jane",
                                                            "link": "https://drive.example/smith"})):
        code, replies[command] = run(capsys, command, *argv, stdin=stdin)
        assert code == 0, (command, replies[command])
    rows = replies["state"]["rules"]
    edited = [{**rows[0], "manual_override": Override.NOT_APPLICABLE}, *rows[1:]]
    code, replies["edit"] = run(capsys, "edit", *asked, stdin={"items": edited, "engagement": {}})
    assert code == 0, replies["edit"]
    [parked] = [row for row in run(capsys, "state", *asked)[1]["index"]
                if row["decision"] == NEEDS_REVIEW and row["original_name"] == "Mortgage Notes.docx"]
    code, replies["assign"] = run(capsys, "assign", *asked, stdin={
        "original": parked["pbc_location"], "identifier": "D01", "keyword": "mortgage notes", "seq": parked["seq"]})
    assert code == 0, replies["assign"]

    assert list(replies) == list(REPLIES)
    lines = held_to("pass.samples.json", the_pass, record)
    for command in REPLIES:
        lines += held_to(f"replies.{command}.keys.json", shape(replies[command]), record)
    _verdict(lines)


# --------------------------------------------------- the helpers' own claims ----


def test_a_key_tree_keeps_keys_and_types_and_folds_a_table_keyed_by_data():
    reply = {"count": 3, "label": "Two W-2s", "Not asked": True, "maybe": None,
             "rows": [{"name": "a", "year": 2025}, {"name": "b", "side": "left"}, {"name": "c", "side": None}],
             "paths": {"review_copy ../../Clients/Test Household/2025/a.pdf": "/tmp/x/a.pdf"},
             "by_year": {"2025": [1], "2024": []}, "none": [], "nested": [[1], ["x"]]}
    assert shape(reply) == {
        "Not asked": "bool", "by_year": {MAP: ["int"]}, "count": "int", "label": "str", "maybe": "NoneType",
        "nested": [["int|str"]], "none": [], "paths": {MAP: "str"},
        "rows": [{"name": "str", "side": "NoneType|str", "year": "int"}]}
    assert shape([1, {"a": 1}]) == [{ANY_OF: ["int", {"a": "int"}]}]


def test_a_difference_is_said_where_it_is():
    recorded = {"a": {"b": "int", "gone": "str"}, "rows": ["x", "y"]}
    now = {"a": {"b": "str", "new": "int"}, "rows": ["x", "z"]}
    assert differences(recorded, now) == [
        ".a.gone: recorded, now gone", ".a.new: new, not recorded", '.a.b: recorded "int", now "str"',
        '.rows[1]: recorded "y", now "z"']
    assert differences(["x"], ["x", "y"]) == ["the top: 1 recorded, 2 now"]
    assert differences(recorded, recorded) == []


# ------------------------------------------------------------ what is kept ----


def _leaves(tree: object):
    if isinstance(tree, dict):
        for key, value in tree.items():
            yield "key", key
            yield from _leaves(value)
    elif isinstance(tree, list):
        for value in tree:
            yield from _leaves(value)
    else:
        yield "value", tree


def test_a_key_tree_holds_words_and_type_names_and_nothing_else():
    """No value reaches a key-tree recording: every key is a word the
    program wrote or the map marker, and every leaf a type name."""
    trees = sorted(GOLDEN.glob("*.keys.json"))
    assert {path.name for path in trees} == {"vocab.keys.json", *(f"replies.{one}.keys.json" for one in REPLIES)}
    for path in trees:
        for kind, said in _leaves(json.loads(path.read_text(encoding="utf-8"))):
            if kind == "key":
                assert said in (MAP, ANY_OF) or WORD.fullmatch(said), (path.name, said)
            else:
                assert set(said.split("|")) <= TYPES, (path.name, said)


def test_the_pass_recording_holds_no_clock_no_sentence_and_no_absolute_path():
    recorded = json.loads((GOLDEN / "pass.samples.json").read_text(encoding="utf-8"))
    said = [value for kind, value in _leaves(recorded) if kind == "value"]
    assert said and all(isinstance(one, str) for one in said)
    for one in said:
        assert not re.search(r"\d{4}-\d{2}-\d{2}|\d{1,2}:\d{2}", one), f"a date or a time: {one!r}"
        assert not one.startswith(("/", "\\")) and not re.match(r"[A-Za-z]:[\\/]", one), f"a path from a root: {one!r}"
        assert not re.search(r"[a-z]\. |[a-z][.;!?]$", one), f"a sentence: {one!r}"
