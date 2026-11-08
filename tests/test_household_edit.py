"""Tests for tracker/household_edit.py - a household's own edits, and the
mirror that writes a related mark onto every other household's record.

Most of what the module promises is held by tests/test_api.py, whose tests
drive the create and edit-household commands and so are about the command:
the members' one parser, the feeds' and the related list's refusals, the
mark written on both records and a half-finished save repaired. None of
them moved here by the SPEC's rule, because each runs a command. These call
the mirror directly (SPEC-architecture-p5 R5.5.4, P342), on households made
the way a test makes a return and with no command run, for the claims its
docstring makes about the engagement lock (pilot P170).
"""

from dataclasses import replace

from tests.builders import make_engagement
from tracker import ledger
from tracker.household_edit import _mirror_related
from tracker.households import load_household_info, save_household
from tracker.layout import private_household_dir
from tracker.locking import acquire_lock, release_lock
from tracker.manifest import RequestItem

ITEMS = [RequestItem(identifier="A01", document="W-2")]


def _households(root, *names):
    """Each named household's folder in the private tree, with one return
    and its record (no scaffold: the mirror reads the records alone)."""
    for name in names:
        make_engagement(root, ITEMS, household=name, return_name=f"1040 - {name}", scaffold=False)
    return [private_household_dir(root, name) for name in names]


def _relate(folder, *names):
    """This household's own record naming ``names`` as related - what the
    edit-household handler saves before it asks for the mirror."""
    save_household(folder, replace(load_household_info(folder), related=tuple(names)))
    return load_household_info(folder).related


def test_a_household_another_pass_holds_is_returned_pending_and_not_waited_on(tmp_path):
    """Pilot P170, the re-check's MUST-R1: the mirror takes each other
    household's lock in turn and does not wait on one that is held. The
    held household comes back as pending with nothing written into it, the
    free one is written, and the call returns while the lock is still held,
    which a mirror that waited for it never would. Once the lock is free,
    the same call completes the link."""
    park, lee, kim = _households(tmp_path, "Park Family", "Lee Family", "Kim Family")
    saved = _relate(park, "Lee Family", "Kim Family")
    lines = len(ledger.read_events(lee))
    held = acquire_lock(lee)
    try:
        pending = _mirror_related(park, saved)
    finally:
        release_lock(held)
    assert pending == ["Lee Family"]
    assert len(ledger.read_events(lee)) == lines and load_household_info(lee).related == ()
    assert load_household_info(kim).related == ("Park Family",)
    assert load_household_info(park).related == ("Lee Family", "Kim Family")

    assert _mirror_related(park, saved) == []
    assert load_household_info(lee).related == ("Park Family",)


def test_a_household_whose_record_already_agrees_is_neither_locked_nor_written(tmp_path):
    """The re-check's MUST-R1 (1): a household whose record names this one
    exactly when the saved list does - linked or not - is left alone, with
    no lock taken and nothing written. So a save that changes nothing about
    the links succeeds while another pass holds every other household."""
    park, lee, kim = _households(tmp_path, "Park Family", "Lee Family", "Kim Family")
    saved = _relate(park, "Lee Family")
    _relate(lee, "Park Family")
    lines = {folder: len(ledger.read_events(folder)) for folder in (lee, kim)}
    held = [acquire_lock(lee), acquire_lock(kim)]
    try:
        pending = _mirror_related(park, saved)
    finally:
        for lock in held:
            release_lock(lock)
    assert pending == []
    assert {folder: len(ledger.read_events(folder)) for folder in (lee, kim)} == lines


def test_the_mirror_reconciles_every_other_household_rather_than_diffing_the_last_save(tmp_path):
    """Pilot P170, the review's M1: every other household is made to agree
    with the list just saved, whatever the save before it did. A household
    the list names gains this one; one whose record names this one while
    the list does not loses it and keeps the rest of its own list. So a save
    that stopped between its two writes is repaired by saving either side."""
    park, lee, kim = _households(tmp_path, "Park Family", "Lee Family", "Kim Family")
    _relate(kim, "Lee Family", "Park Family")
    saved = _relate(park, "Lee Family")
    assert _mirror_related(park, saved) == []
    assert load_household_info(lee).related == ("Park Family",)
    assert load_household_info(kim).related == ("Lee Family",)
