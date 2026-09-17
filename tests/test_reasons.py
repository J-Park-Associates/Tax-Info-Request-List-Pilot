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
    } | {"size_kb": 1.0, "minimum": 5})
    assert reason.marker.lower() in sample.lower()
    assert reason.matches(sample)


def test_codes_are_unique():
    codes = [r.code for r in ALL]
    assert len(codes) == len(set(codes))


def test_find_returns_the_most_specific_reason_first():
    note = "scan.pdf: " + reasons.TOO_SMALL.format(size_kb=3.1, minimum=5)
    assert find(note) is reasons.TOO_SMALL
    assert find("nothing recognisable") is None
    assert reasons.NO_PAGES.client_ask == GENERIC_ASK          # no ask of its own


def test_firm_side_reasons_never_become_a_client_ask():
    for reason in FIRM_SIDE:
        assert reason.ask == ""
    assert reasons.NO_TEXT_LAYER in FIRM_SIDE and reasons.WRONG_PERIOD not in FIRM_SIDE
