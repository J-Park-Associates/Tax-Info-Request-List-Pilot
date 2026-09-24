"""Tests for tracker/reasons.py — every refusal said once.

The claim: each reason's marker is a literal part of the sentence the
scanner writes, so the reminder recognises what the producers produce, and
rewording either side without the other fails here rather than in a
client's inbox.
"""

import pytest

from tracker import reasons
from tracker.reasons import ALL, FIRM_SIDE, GENERIC_ASK, Reason, find


@pytest.mark.parametrize("reason", ALL, ids=lambda r: r.code)
def test_every_marker_is_part_of_its_own_sentence(reason: Reason):
    sample = reason.template.format(**{
        name: "x" for name in ("error", "extension", "allowed", "listed", "pattern")
    } | {"size_kb": 1.0, "minimum": 5, "size": "300 MB", "minutes": "10 minutes"})
    assert reason.marker.lower() in sample.lower()
    assert reason.matches(sample)


def test_codes_are_unique():
    codes = [r.code for r in ALL]
    assert len(codes) == len(set(codes))


def _sample(reason: Reason) -> str:
    return reason.template.format(**{
        name: "x" for name in ("error", "extension", "allowed", "listed", "pattern")
    } | {"size_kb": 1.0, "minimum": 5, "size": "300 MB", "minutes": "10 minutes"})


@pytest.mark.parametrize("reason", ALL, ids=lambda r: r.code)
def test_no_marker_is_part_of_another_reasons_sentence(reason: Reason):
    """Decision 121. A marker is how ``find()`` tells one reason from
    another, so a marker that is also a phrase of some other reason's
    sentence is a lie waiting for ``ALL``'s order to tell it: three
    sentences ended "; review manually", and that was ``UNCHECKABLE_TYPE``'s
    marker, so a scan with no text layer was found as an uncheckable file
    type. Each marker in its own sentence and in no other."""
    for other in ALL:
        if other is not reason:
            assert not reason.matches(_sample(other)), (reason.code, other.code)


@pytest.mark.parametrize("reason", ALL, ids=lambda r: r.code)
def test_find_gives_every_reason_back_from_its_own_sentence(reason: Reason):
    """The scanner writes the sentence; the reminder and the review queue
    must get the same reason back from it, whatever ``ALL``'s order."""
    assert find("scan.pdf: " + _sample(reason)) is reason


def test_find_returns_the_most_specific_reason_first():
    note = "scan.pdf: " + reasons.TOO_SMALL.format(size_kb=3.1, minimum=5)
    assert find(note) is reasons.TOO_SMALL
    assert find("nothing recognisable") is None
    assert reasons.NO_PAGES.client_ask == GENERIC_ASK          # no ask of its own


def test_firm_side_reasons_never_become_a_client_ask():
    for reason in FIRM_SIDE:
        assert reason.ask == ""
    assert reasons.NO_TEXT_LAYER in FIRM_SIDE and reasons.WRONG_PERIOD not in FIRM_SIDE


def test_the_two_sweep_reasons_are_firm_side():
    """Decision 109. A working copy somebody here dragged, and a file that is
    not the one the record filed, are the firm's doing either way: the
    client sent the document. A draft that asked them for it would be
    asking for a file the firm mislaid, so both carry a firm note of their
    own and neither can ever become an ask."""
    for reason in (reasons.FILE_MOVED, reasons.COPY_CHANGED):
        assert reason in FIRM_SIDE and reason in ALL
        assert reason.ask == "" and reason.firm_note
        assert reason.firm_side_note == reason.firm_note
        assert "client" in reason.firm_note        # never the client, said in the sentence
