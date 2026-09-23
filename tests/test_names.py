"""Tests for tracker/names.py — whose document is this (decision 128).

The claims: a spelling matches as a whole phrase and never inside a word,
case and punctuation decide nothing, the app proposes the forms a document
might print and never one word alone - and no family-name-first form,
because the comma form already matches one - and a page that names this
return's person is this return's even when it names somebody else's too.
"""

from tracker.names import (
    NAME_ABSENT,
    NAME_CONFIRMED,
    NAME_VETOED,
    check_name,
    normalise,
    propose_spellings,
    spelling_in,
)
from tracker.records import WHERE_DEEP, WHERE_FIRST_PAGE


def test_normalise_ignores_case_and_punctuation_and_a_spelling_matches_only_as_a_whole_phrase():
    """A family name alone is a whole phrase inside a company's name, which
    is why a spelling needs two words; two words are matched as a phrase and
    never inside a longer one, and the folding makes every way of writing a
    name read alike."""
    assert normalise("Park, John A.") == normalise("PARK JOHN A") == " park john a "
    assert normalise("O'Brien") == " o brien "

    # `Park` **is** a whole phrase inside `Park Landscaping LLC` - which is
    # exactly the confusion the two-word rule exists to stop, and why one
    # word never confirms however the matcher reads it.
    assert spelling_in("Park Landscaping LLC", "Park")
    assert check_name("Park Landscaping LLC", ("Park",), {}).outcome == NAME_ABSENT
    assert not spelling_in("Park Landscaping LLC", "John Park")
    # ...and a two-word spelling is never found inside a longer word.
    assert spelling_in("Employee: PARK, JOHN A.", "John Park") is False
    assert spelling_in("Employee: PARK, JOHN A.", "Park, John")
    assert spelling_in("Statement for John A. Park", "John A. Park")
    assert not spelling_in("Parkway Johnson Ltd", "Park Johnson")


def test_proposals_cover_first_last_and_last_first_and_never_one_word():
    assert propose_spellings("John A. Park", "taxpayer") == (
        "John A. Park", "John Park", "Park, John A.", "Park, John")
    # No middle name: the with-middle and without-middle forms fold into
    # one, and so do the two comma forms.
    assert propose_spellings("John Park", "spouse") == ("John Park", "Park, John")
    # There is no family-name-first form to propose and no mark on the
    # person for one: a page printing the family name first *without* the
    # comma is matched by the comma spelling already, because normalise()
    # reads a comma as a space. That is why the flag is not kept.
    assert spelling_in("Employee: PARK JOHN A", "Park, John A.")
    assert spelling_in("Employee: PARK JOHN", "Park, John")
    # One word is one word, however it is written.
    assert propose_spellings("Park", "taxpayer") == ()
    assert propose_spellings("", "taxpayer") == ()
    assert all(len(normalise(one).split()) >= 2
               for one in propose_spellings("Maria de la Cruz", "spouse"))


def test_an_entitys_proposals_include_the_name_without_its_suffix_when_two_words_remain():
    assert propose_spellings("Park Landscaping LLC", "entity") == (
        "Park Landscaping LLC", "Park Landscaping")
    assert propose_spellings("Park Landscaping, L.L.C.", "dba") == (
        "Park Landscaping, L.L.C.", "Park Landscaping")
    # One word would be left, so the suffix stays on: `Park Trust` is the
    # only spelling, and `Park` is never proposed.
    assert propose_spellings("Park Trust", "trust") == ("Park Trust",)
    # An entity is never rearranged into a person's name.
    assert "Landscaping, Park" not in propose_spellings("Park Landscaping", "entity")


def test_confirmed_beats_vetoed_beats_absent_and_a_page_naming_two_returns_people_confirms_both():
    own = ("John A. Park", "Park, John A.")
    others = {"Park Family 2025 1040 - Maria Park": ("Maria Park",)}

    confirmed = check_name("Employee: John A. Park", own, others)
    assert confirmed.outcome == NAME_CONFIRMED and confirmed.matched == "John A. Park"
    assert confirmed.where == WHERE_FIRST_PAGE and confirmed.page == 1

    vetoed = check_name("Employee: Maria Park", own, others)
    assert vetoed.outcome == NAME_VETOED and vetoed.other == "Maria Park"
    assert vetoed.other_label == "Park Family 2025 1040 - Maria Park"

    assert check_name("Employee: Sofia Ruiz", own, others).outcome == NAME_ABSENT

    # A joint page names both, and is confirmed for each return: the
    # exactly-one rule decides between them, not the name.
    both = "Taxpayer: John A. Park and Maria Park"
    assert check_name(both, own, others).outcome == NAME_CONFIRMED
    assert check_name(both, ("Maria Park",), {"other": own}).outcome == NAME_CONFIRMED


def test_where_a_name_was_said_is_the_page_it_was_printed_on():
    """A name is not a form's own title and is not repeated in a footer, so
    the only thing worth recording about where it was found is the page."""
    deep = "page one says nothing\fEmployee: John A. Park"
    said = check_name(deep, ("John A. Park",), {})
    assert said.where == WHERE_DEEP and said.page == 2
