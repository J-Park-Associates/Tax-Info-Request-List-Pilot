"""Tests for tracker/door.py - the disk half of the layout (decision 188).

The claims: the clients root is held to the settings' rule wherever it
enters; a path a person typed is a return's or a household's place under
it or nothing, rebuilt from its own names; and a write into the tree a
client is shared goes only into that household's own inbox and year
folders, never through a link. The door holds no rule of its own: every
sentence here is the layout's or the settings'.
"""

from __future__ import annotations

import runpy
import sys

import pytest

from tracker import door, layout
from tracker.layout import CLIENTS_TREE, INBOX_DIR_NAME, PRIVATE_TREE

HOUSEHOLD = "Park Family"
RETURN = "1040 - John Park"


@pytest.fixture
def root(tmp_path, monkeypatch):
    """A clients root with both trees, one household and one return, and
    no root saved - each test says which root it means."""
    from tracker.settings import ENV_SETTINGS_DIR

    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    folder = tmp_path / "Clients root"
    layout.return_dir_for(folder, HOUSEHOLD, 2025, RETURN).mkdir(parents=True)
    layout.inbox_dir_for(folder, HOUSEHOLD).mkdir(parents=True)
    layout.originals_dir_for(folder, HOUSEHOLD, 2025).mkdir()
    return folder.resolve()


def _link_to(target, link):
    """A junction on Windows, a symlink elsewhere: a folder that is a link."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def test_a_client_write_through_a_link_is_refused(root, tmp_path):
    """T20: a folder in the household's inbox swapped for a link to anywhere
    is never written behind, even though the place it names is the
    household's own inbox; the same place with no link is approved."""
    outside = tmp_path / "outside"
    outside.mkdir()
    inbox = layout.inbox_dir_for(root, HOUSEHOLD)
    _link_to(outside, inbox / "swapped")

    with pytest.raises(door.DoorError, match="is not a place the app writes"):
        door.client_write(root, HOUSEHOLD, inbox / "swapped" / "w2.pdf")
    assert door.through_a_link(inbox / "swapped" / "w2.pdf", root)
    assert door.client_write(root, HOUSEHOLD, inbox / "w2.pdf") == inbox / "w2.pdf"
    assert not door.through_a_link(inbox / "w2.pdf", root)
    # A path not under the root at all is refused as if behind a link.
    assert door.through_a_link(outside / "x.pdf", root)


def test_the_door_refuses_another_households_client_folder(root):
    """T20: only this household's inbox and year folders - and its client
    folder while it is being made - are places a write for it may go.
    Another household's, the tree itself, a folder beside the inbox and
    the firm's own tree are refused with the layout's sentence."""
    home = layout.client_household_dir(root, HOUSEHOLD)
    other = layout.client_household_dir(root, "Lee Family")
    for approved in (home / INBOX_DIR_NAME, home / INBOX_DIR_NAME / "_README.txt",
                     home / "2025", home / "2025" / "w2.pdf"):
        assert door.client_write(root, HOUSEHOLD, approved) == approved
    assert door.client_write(root, HOUSEHOLD, home, making=True) == home
    for refused, making in [
        (other / INBOX_DIR_NAME / "w2.pdf", False),
        (other, True),
        (home, False),                                   # only while it is being made
        (root / CLIENTS_TREE, True),
        (home / "Taxes" / "w2.pdf", False),
        (layout.return_dir_for(root, HOUSEHOLD, 2025, RETURN) / "x.pdf", False),
        (root.parent / "elsewhere.pdf", False),
    ]:
        with pytest.raises(door.DoorError) as said:
            door.client_write(root, HOUSEHOLD, refused, making=making)
        assert str(said.value) == layout.OUTSIDE_CLIENT_PLACE.format(path=refused,
                                                                    household=HOUSEHOLD)


def test_a_typed_path_is_a_return_or_a_household_rebuilt_from_its_own_names(root):
    """C-9/E-5: a path from outside is placed by the layout's parser and
    rebuilt from the root and its names, so a ``..`` or a relative path
    names the same return - and a folder in the client tree, a year and
    anything outside the root are never one."""
    ret = layout.return_dir_for(root, HOUSEHOLD, 2025, RETURN)
    assert door.return_dir(ret, root=root) == ret
    assert door.return_dir(ret / "Prepared" / "..", root=root) == ret
    assert door.return_dir(f"{PRIVATE_TREE}/{HOUSEHOLD}/2025/{RETURN}", root=root) == ret
    assert door.household_dir(ret.parent.parent, root=root) == ret.parent.parent
    planted = layout.inbox_dir_for(root, HOUSEHOLD) / "X"
    planted.mkdir()
    for not_a_return in (planted, ret.parent, ret.parent.parent):
        with pytest.raises(layout.LayoutError, match="is not a return's folder"):
            door.return_dir(not_a_return, root=root)
    with pytest.raises(door.DoorError, match="is not under the clients root"):
        door.return_dir(root.parent, root=root)
    with pytest.raises(layout.LayoutError, match="is not a household's folder"):
        door.household_dir(ret, root=root)


def test_a_command_line_parses_its_typed_folder_through_the_door(root, capsys):
    """The block every command line copied is the door's: a return (or, for
    the rollover, a household) comes back rebuilt, and anything else ends
    the command through ``parser.error`` with the door's own sentence."""
    import argparse

    from tracker.settings import set_clients_root

    set_clients_root(root)
    parser = argparse.ArgumentParser(prog="tool")
    ret = layout.return_dir_for(root, HOUSEHOLD, 2025, RETURN)
    assert door.typed_return(parser, ret / "Prepared" / "..") == ret
    assert door.typed_household_or_return(parser, ret.parent.parent) == ret.parent.parent
    assert door.typed_household_or_return(parser, ret) == ret
    for refused, ask in ((ret.parent, door.typed_return),
                         (root.parent, door.typed_household_or_return)):
        with pytest.raises(SystemExit) as stopped:
            ask(parser, refused)
        assert stopped.value.code == 2
    said = capsys.readouterr().err
    assert "is not a return's folder" in said and "is not under the clients root" in said


def test_the_root_is_checked_wherever_it_enters(root, tmp_path, monkeypatch):
    """R11: given or saved, the root is resolved and held to the settings'
    rule - no saved root is a sentence, and a root one level too deep,
    inside a tree of a real root, is refused with "Clients folder problem"."""
    from tracker.settings import set_clients_root

    with pytest.raises(door.DoorError, match="Clients folder problem: no clients root is set"):
        door.checked_root()
    assert door.checked_root(root) == root
    set_clients_root(root)
    assert door.checked_root() == root
    with pytest.raises(door.DoorError, match="Clients folder problem: .* is inside the "
                                             f"{CLIENTS_TREE} folder of the clients root"):
        door.checked_root(layout.client_household_dir(root, HOUSEHOLD))


def test_the_door_command_line_says_the_place_and_whether_a_write_may_go_there(
        root, capsys, monkeypatch):
    """Its own command line writes nothing: it prints the parser's place and
    the door's answer."""
    inbox = layout.inbox_dir_for(root, HOUSEHOLD)
    for target, kind, answer in [
            (inbox / "w2.pdf", layout.IN_INBOX, "a write for the household may go here"),
            (root / PRIVATE_TREE, layout.PRIVATE, "no write goes here")]:
        monkeypatch.setattr(sys, "argv", ["door", str(target), "--root", str(root)])
        runpy.run_module("tracker.door", run_name="__main__")
        said = capsys.readouterr().out
        assert f"place: {kind}" in said and answer in said, said
    assert not (inbox / "w2.pdf").exists()
