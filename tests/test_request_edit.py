"""Tests for tracker/request_edit.py — the request-list editor's save rules.

Since P341 (SPEC-architecture-p5 P5.4) the rules a save from the editor
meets live in their own module, and the API's handlers call them by import.
Most of what they promise is still held where it always was, by
``tests/test_api.py`` and the ``test_api_<family>`` files split from it, driving the ``edit`` and ``create`` commands: a test
whose road runs through a command is about the command. Three tests moved
here by the SPEC's section 4.1 rule, because they call
:func:`tracker.request_edit._people_from_spec` and nothing else - the order
in which a person's kind, name and spellings are judged (P2.5). One is new:
Q-F's answer (C), that the editor's save measures through the one room
function without its review-folder term and so comes out as it did before.
"""

import os
from dataclasses import replace

import pytest

from tests.api_driver import _SPELLING_REFUSED
from tests.builders import make_engagement, root_for_a_return_of
from tracker import layout, request_edit
from tracker.copies import refuse_a_path_past_the_limit, room_for
from tracker.layout import PATH_TOO_LONG, PREPARED_DIR_NAME, REVIEW_DIR_NAME
from tracker.manifest import ManifestError, RequestItem, load_manifest


def test_a_one_word_spelling_is_refused_before_the_text_rule_is_asked():
    from tracker.records import ONE_WORD_SPELLING

    for one_word in ("x" * 1001, "Smith\x07"):
        people = [{"kind": "taxpayer", "name": "Jane Smith", "spellings": [one_word]}]
        with pytest.raises(ManifestError) as raised:
            request_edit._people_from_spec(people)
        assert str(raised.value) == ONE_WORD_SPELLING


def test_a_persons_spellings_are_judged_one_at_a_time_in_order():
    """SPEC-architecture-p2 P2.5 (R2.5.4): each spelling is folded and judged
    before the next is read, so of two bad spellings the first one's
    sentence is the reply - a two-word spelling past the text rule before a
    one-word spelling, and the other way round."""
    from tracker.records import ONE_WORD_SPELLING

    past_the_rule, one_word = "J " + "x" * 1999, "Smith"
    for spellings, said in (([past_the_rule, one_word], _SPELLING_REFUSED),
                            ([one_word, past_the_rule], ONE_WORD_SPELLING)):
        people = [{"kind": "taxpayer", "name": "Jane Smith", "spellings": spellings}]
        with pytest.raises(ManifestError) as raised:
            request_edit._people_from_spec(people)
        assert str(raised.value) == said, spellings


def test_a_persons_kind_is_judged_before_their_spellings_are_read():
    """SPEC-architecture-p2 P2.5 (R2.5.4): a person whose kind nothing knows
    is refused before their spellings are read at all, so spellings that
    are not even a list are a refusal in the kind's words, never a crash."""
    people = [{"kind": "cousin", "name": "Jane Smith", "spellings": 5}]
    with pytest.raises(ManifestError) as raised:
        request_edit._people_from_spec(people)
    assert str(raised.value) == ("'cousin' is not one of taxpayer, spouse, dependent, entity, dba, owner, "
                                 "decedent, trust, fiduciary")


def test_a_save_on_a_return_whose_folder_grew_since_creation_comes_out_as_before(short_root, monkeypatch):
    """Q-F (C), Jason's answer (SPEC-architecture-p5 R5.4.4). A return made
    at 150 characters whose clients root then grew, so that its folder is
    207 - one past the longest a return may be where long paths are off,
    which creation would refuse now. There the one room function, with its
    review-folder term, refuses even the list as it is stored. The editor's
    save calls it with ``review_folder=False`` and measures only the rows it
    changes, so every save comes out as the editor's own check said before
    it called the one function - the same comparison and the same sentence:
    a save that changes no row's path, or renames a row within the room, is
    not refused, and a row whose working copy would pass the limit is."""
    items = [RequestItem(identifier="A01", document="W-2"),
             RequestItem(identifier="B01", document="1099-INT")]
    small = root_for_a_return_of(short_root / "a", 150)
    grown = root_for_a_return_of(short_root / "a", 207)
    small.mkdir(parents=True)
    made = make_engagement(small, items)
    os.rename(small, grown)
    engagement = grown / made.relative_to(small)
    assert len(str(engagement)) == 207
    monkeypatch.setattr(layout, "short_paths", lambda: True)
    limit = layout.path_limit()
    assert limit == 259
    stored = load_manifest(engagement)

    review = layout.folder_need(engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME, layout.room_root(engagement))
    assert review > limit
    with pytest.raises(ManifestError) as refused:
        refuse_a_path_past_the_limit(engagement, stored)
    assert str(refused.value) == PATH_TOO_LONG.format(folder=engagement, length=review, limit=limit)

    def as_before(changed: list[RequestItem]) -> str | None:
        """The editor's own check as it stood (decision 131): the rows it
        changed, measured by ``room_for``, against the room's own limit."""
        room = room_for(engagement, changed)
        if room.need > room.limit:
            return PATH_TOO_LONG.format(folder=engagement, length=room.need, limit=room.limit)
        return None

    def now(sent: list[RequestItem]) -> str | None:
        try:
            request_edit._refuse_a_changed_row_past_the_limit(engagement, sent)
        except ManifestError as said:
            return str(said)
        return None

    a01, b01 = stored
    longer = replace(a01, period="January 2025 to December 2025")
    for sent, changed, saved in (
        ([a01, b01], [], True),                                    # nothing changed
        ([replace(a01, expected_count=2), b01], [], True),         # a count: no path changes
        ([replace(a01, document="W2"), b01], [replace(a01, document="W2")], True),
        ([longer, b01], [longer], False),                          # a working copy past the limit
    ):
        assert now(sent) == as_before(changed), sent
        assert (now(sent) is None) is saved, sent
