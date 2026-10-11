"""Tests for tracker/reasons.py — every refusal said once, and known by its code.

The claim: each cause has one sentence and one code, the code travels with
the sentence from where it is said, and nothing reads a cause out of a
sentence's words (decision 190) - so a client's file name, subfolder or a
parser's text can never change what a row means.
"""

import ast
import copy
import pickle
from pathlib import Path

import pytest

from tracker import reasons
from tracker.reasons import ALL, BY_CODE, FIRM_SIDE, GENERIC_ASK, HOLDS, PLAIN_CODES, Reason, Said

REASONS_PY = Path(reasons.__file__)


def _sample(reason: Reason) -> str:
    return reason.template.format(**{
        name: "x" for name in ("error", "extension", "allowed", "listed", "pattern")
    } | {"size_kb": 1.0, "minimum": 5, "size": "300 MB", "minutes": "10 minutes",
         "kind": "an email", "spelling": "x", "label": "x"})


@pytest.mark.parametrize("reason", ALL, ids=lambda r: r.code)
def test_every_marker_is_part_of_its_own_sentence(reason: Reason):
    """The marker is what the review card names a refusal by, so it is a
    literal part of the sentence the scanner writes."""
    assert reason.marker.lower() in _sample(reason).lower()


def test_codes_are_unique():
    """Every cause - a Reason, or one of the router's and the filer's own
    sentences - has a code no other cause has, and no code is empty."""
    codes = [r.code for r in ALL] + list(PLAIN_CODES)
    assert len(codes) == len(set(codes))
    assert all(codes)


def test_every_parking_sentence_has_a_code():
    """Decision 190. Every Reason's sentence is said carrying its code, and
    every ``*_CODE`` constant the module defines is in PLAIN_CODES - the
    router's bare strings included - so a code added without a place in
    the one list fails here."""
    for reason in ALL:
        said = reason.format(**{name: "x" for name in (
            "error", "extension", "allowed", "listed", "pattern", "size", "minutes", "kind",
            "spelling", "label")},
            size_kb=1.0, minimum=5)
        assert isinstance(said, Said) and said.code == reason.code
        assert reasons.code_of(said) == reason.code
    defined = {value for name, value in vars(reasons).items()
               if name.endswith("_CODE") and isinstance(value, str)}
    assert defined == set(PLAIN_CODES)
    for sentence in (reasons.UNMATCHED, reasons.AMBIGUOUS, reasons.OCR_ONLY,
                     reasons.NO_REQUEST_ACCEPTS, reasons.CONTESTED_PREFIX):
        assert sentence                        # worded here, beside its code


def test_reasons_has_no_function_that_searches_a_sentence():
    """Decision 190 removes the search rather than patching it: ``find``,
    ``Reason.matches``, ``reasons_in`` and the file-name prefix are gone,
    and the module compiles no pattern to read a sentence with."""
    for gone in ("find", "reasons_in", "_FILE_PREFIX"):
        assert not hasattr(reasons, gone), gone
    assert not hasattr(Reason, "matches")
    tree = ast.parse(REASONS_PY.read_text(encoding="utf-8"))
    imported = {alias.name for node in ast.walk(tree)
                if isinstance(node, (ast.Import, ast.ImportFrom)) for alias in node.names}
    assert "re" not in imported


def test_a_plain_string_has_no_code_whatever_it_says():
    """``code_of`` reads the code a sentence was said with, never its
    words: the exact words of a reason, typed again, carry no cause."""
    assert reasons.code_of(reasons.PASSWORD_PROTECTED.template) == ""
    assert reasons.code_of(str(reasons.PASSWORD_PROTECTED.format())) == ""
    assert reasons.code_of("") == ""


def test_the_code_survives_the_reading_child_and_a_copy():
    """A sentence crosses the reading's child pickled (decision 150) and is
    copied by asdict(): the code goes with it both ways, and the text is
    the same text."""
    said = reasons.UNREADABLE_PDF.format(error="PdfReadError")
    for again in (pickle.loads(pickle.dumps(said)), copy.deepcopy(said)):
        assert again == said and again.code == reasons.UNREADABLE_PDF.code


def test_first_of_takes_the_most_specific_code():
    """The order ALL gives is the order of preference: the specific causes
    before the vague ones. A code no Reason has is passed over."""
    codes = [reasons.UNREADABLE_PDF.code, "unmatched", reasons.PASSWORD_PROTECTED.code]
    assert reasons.first_of(codes) is reasons.PASSWORD_PROTECTED
    assert reasons.first_of(["unmatched", ""]) is None
    assert reasons.first_of([]) is None


def test_by_code_names_every_reason_and_the_sets_are_codes():
    assert BY_CODE == {r.code: r for r in ALL}
    assert FIRM_SIDE == {r.code for r in ALL if r.firm_side}
    assert HOLDS == {r.code for r in ALL if r.holds}
    assert reasons.NO_PAGES.client_ask == GENERIC_ASK          # no ask of its own


def test_firm_side_reasons_never_become_a_client_ask():
    for code in FIRM_SIDE:
        assert BY_CODE[code].ask == ""
    assert reasons.NO_TEXT_LAYER.code in FIRM_SIDE and reasons.WRONG_PERIOD.code not in FIRM_SIDE


def test_the_two_sweep_reasons_are_firm_side():
    """Decision 109. A working copy somebody here dragged, and a file that is
    not the one the record filed, are the firm's doing either way: the
    client sent the document. A draft that asked them for it would be
    asking for a file the firm mislaid, so both carry a firm note of their
    own and neither can ever become an ask."""
    for reason in (reasons.FILE_MOVED, reasons.COPY_CHANGED):
        assert reason.code in FIRM_SIDE and reason in ALL
        assert reason.ask == "" and reason.firm_note
        assert reason.firm_side_note == reason.firm_note
        assert "client" in reason.firm_note        # never the client, said in the sentence


def test_the_named_across_reason_is_firm_side_holds_nothing_and_its_marker_is_in_its_template():
    """Decision 204: a document naming another household's person waits
    for a person here, never the client, and holds no letter - the
    client's file is good."""
    reason = reasons.NAMED_ACROSS_HOUSEHOLDS
    assert reason in ALL and reason.code in FIRM_SIDE
    assert reason not in reasons.HOLDS and not reason.holds
    assert reason.marker in reason.template
    said = reason.format(spelling="Dana Reyes", label="Reyes 2025 1040 - Dana Reyes")
    assert said.code == reason.code and reasons.code_of(said) == reason.code
    assert said.code != reasons.UNNAMED_ACROSS_HOUSEHOLDS.code
    assert "never the client" in reason.firm_side_note


def test_a_program_is_asked_about_in_the_words_any_unusable_file_gets():
    """NOT_A_DOCUMENT has no client words of its own: its ask is
    EXTENSION_NOT_ALLOWED's, one home; it holds nothing and is the
    client's, not the firm's (decision 190)."""
    assert reasons.NOT_A_DOCUMENT.client_ask == reasons.EXTENSION_NOT_ALLOWED.client_ask
    assert reasons.NOT_A_DOCUMENT.code not in HOLDS and reasons.NOT_A_DOCUMENT.code not in FIRM_SIDE
    assert BY_CODE[reasons.NOT_A_DOCUMENT.code] is reasons.NOT_A_DOCUMENT
    source = (Path(reasons.__file__)).read_text(encoding="utf-8")
    assert source.count(repr(reasons.EXTENSION_NOT_ALLOWED.ask)[1:-1]) == 1


#: The readers that still read a row's text - each for a **path** the firm
#: itself wrote into the tail of its own sentence, never for the row's
#: cause - by module and function, each with why (decision 190's Part 2
#: review, S-2). A new one is a decision, made here where it shows.
TAIL_READERS = {
    ("filer", "moved_to"): "where the firm's moved sentence says a working copy now is",
    ("filer", "interrupted"): "the path the firm's interrupted-move sentence names, and the sentence itself",
    ("review", "_label_of"): "the return's label the firm's own veto sentence names",
    ("scanner", "_regression_why"): "the count the firm's own regression sentence names",
    ("containers", "add"): "which limit (LIMIT_DEPTH) the firm's own container-limit sentence names",
}
#: What a reason or a note is called where a reader holds one.
_TEXT_ATTRIBUTES = {"reason", "validation_notes", "sentence"}
_TEXT_NAMES = {"reason", "note", "notes", "previous_note", "sentence"}
_SEARCHES = {"startswith", "endswith", "find", "rfind", "index", "count"}
_REGEX = {"search", "match", "fullmatch", "findall", "finditer", "split", "sub"}


def _is_text(node) -> bool:
    if isinstance(node, ast.BoolOp):          # (row.reason or "")
        return any(_is_text(value) for value in node.values)
    return ((isinstance(node, ast.Attribute) and node.attr in _TEXT_ATTRIBUTES)
            or (isinstance(node, ast.Name) and node.id in _TEXT_NAMES))


def _searches_text(node) -> bool:
    if isinstance(node, ast.Compare) and any(isinstance(op, (ast.In, ast.NotIn)) for op in node.ops):
        return any(_is_text(side) for side in node.comparators)
    if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
        if node.func.attr in _SEARCHES and _is_text(node.func.value):
            return True
        if node.func.attr in _REGEX and any(_is_text(arg) for arg in node.args):
            return True
    return False


def test_no_reader_decides_a_rows_cause_from_its_text():
    """Security principle 2, over all of ``tracker/`` (the Part 2 review's
    S-2): no ``in <row>.reason``, no ``.reason.startswith``, no pattern run
    over a reason or a note decides a branch - a row's cause is its code.
    The few readers that recover a path from a firm-made tail are named in
    :data:`TAIL_READERS`, each with its reason, and one that no longer
    reads text must leave the list."""
    found, seen = [], set()
    for path in sorted((REASONS_PY.parent).glob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"))
        for function in ast.walk(tree):
            if not isinstance(function, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            hits = [node for node in ast.walk(function) if _searches_text(node)]
            if not hits:
                continue
            key = (path.stem, function.name)
            if key in TAIL_READERS:
                seen.add(key)
                continue
            found += [f"tracker/{path.name}:{node.lineno} in {function.name}" for node in hits]
    assert found == [], "a reader searches a row's text:\n" + "\n".join(found)
    assert seen == set(TAIL_READERS), f"no longer a tail reader: {sorted(set(TAIL_READERS) - seen)}"


def test_every_code_has_one_short_label_of_five_words_or_fewer():
    """SPEC-shell 11.5: a row on the app's pages says the short label, the
    sentence stays where the index, the letter and the log use it. Keyed by
    code, one for every code in ``BY_CODE`` and ``PLAIN_CODES`` and no other."""
    from tracker.reasons import SHORT_REASONS

    assert set(SHORT_REASONS) == set(BY_CODE) | set(PLAIN_CODES)
    for code, short in SHORT_REASONS.items():
        assert 1 <= len(short.split()) <= 5, (code, short)
        assert short == short.strip() and not short.endswith("."), (code, short)


def test_a_label_shortened_into_a_tag_keeps_the_words_it_replaced_as_its_tooltip():
    """Pilot P116: "Came in Email or Zip" became the tag "Email or Zip" to
    fit the 160px status column, and the words it replaced are its tooltip.
    A tip belongs to a code that has a label, says more than the tag, and is
    five words or fewer like every tooltip (SPEC-shell 11)."""
    from tracker.reasons import REASON_TIPS, SHORT_REASONS

    assert SHORT_REASONS["opened-not-across"] == "Email or Zip"
    assert REASON_TIPS == {"opened-not-across": "Came in Email or Zip"}
    for code, tip in REASON_TIPS.items():
        assert code in SHORT_REASONS and len(tip) > len(SHORT_REASONS[code]), (code, tip)
        assert 1 <= len(tip.split()) <= 5, (code, tip)
        assert tip == tip.strip() and not tip.endswith("."), (code, tip)
