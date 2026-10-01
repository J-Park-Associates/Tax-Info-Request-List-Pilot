"""The disk half of the layout: the checked root, a typed path, the link
check, and the one door every write into the client tree passes
(decision 188).

``tracker.layout`` says which household a folder is and where a path may
be - one name rule, one comparison key, one positional parser - and it
promises to open no file, which is what lets every layer ask it (its tests
open none). Three questions cannot be answered without the disk, and they
live here, each worded as "resolve or ``lstat``, then ask the layout":

- **The root** (:func:`checked_root`). The clients root a command reads,
  given or saved, resolved and held to ``settings.clients_root_refusal``
  every time it enters - the app's commands (E-13), the pass, and every
  command line that takes one - so a root saved before a rule existed is
  never walked under it.
- **A path a person typed** (:func:`return_dir`, :func:`household_dir`).
  Resolved from the checked root, placed by ``layout.return_at`` or
  ``layout.household_at``, and rebuilt from the root and its own names
  through the layout's constructors - so no ``..``, no second spelling
  and no folder in the client tree reaches a reader as a return (C-9/E-5).
- **Where a write into the client tree may go** (:func:`client_write`).
  Only a household's own client folder (when it is being made), its
  inbox and its year folders of originals, and never through a link
  (:func:`through_a_link`, moved here from the filer as its one
  definition). The scaffold, the README, the filer's move and every folder
  made for it, and the sweep of a killed write's temps in the inbox all
  pass it; ``tests/test_runner.py`` proves no path under the client tree
  changed that the door did not approve.

**It holds no rule of its own.** Every refusal is the layout's sentence or
the settings' sentence; this module only fetches what the disk says and
asks. Layer 0 beside ``layout``, ``fsio`` and ``settings``, which are all
it imports.
"""

from __future__ import annotations

import os
from pathlib import Path

from tracker import layout
from tracker.fsio import is_link
from tracker.settings import clients_root, clients_root_refusal


class DoorError(ValueError):
    """A root, a path or a write the door refuses, with the sentence."""


#: What every command reading a root is told when the root fails the
#: settings' rule, whether it was typed or saved (E-13).
ROOT_PROBLEM = "Clients folder problem: {refusal}"
#: What a command is told when no root is saved and none was given.
NO_ROOT = "no clients root is set; choose the folder the firm keeps its clients in in Settings"
#: What a typed path outside the clients root is told.
NOT_UNDER_ROOT = "{path} is not under the clients root {root}"


def checked_root(given: Path | str | None = None) -> Path:
    """The clients root - ``given``, else the saved one - resolved and held
    to the settings' rule, or a :class:`DoorError` saying why not.

    Resolved, because every path below it is compared with it and a
    junction or a second spelling of the root would otherwise make one
    folder two. Asked on every entry, never cached: the rule may be newer
    than the saved root (decision 137's review, F12), and a root one level
    too deep (``settings.ROOT_INSIDE_A_TREE``) can appear after it was
    saved, when a person moves the trees around it.
    """
    raw = given if given not in (None, "") else clients_root()
    if raw is None:
        raise DoorError(ROOT_PROBLEM.format(refusal=NO_ROOT))
    root = Path(raw).expanduser().resolve()
    refusal = clients_root_refusal(root)
    if refusal:
        raise DoorError(ROOT_PROBLEM.format(refusal=refusal))
    return root


def _placed(given: Path | str, root: Path) -> Path:
    """``given`` resolved, a relative path read from ``root``; a
    :class:`DoorError` when it is not under the root at all."""
    folder = Path(given).expanduser()
    if not folder.is_absolute():
        folder = root / folder
    resolved = folder.resolve()
    if layout.place_of(root, resolved).kind == layout.OUTSIDE:
        raise DoorError(NOT_UNDER_ROOT.format(path=folder, root=root))
    return resolved


def _base(given: Path | str, root: Path | str | None, depth: int) -> Path:
    """The checked root a typed path is read under: ``root`` when the
    caller has one, else the saved root, else - a command line on a
    machine where no root is saved yet - the folder ``depth`` levels above
    the path, which is where the layout puts the root of such a place.
    Whichever it is, it is held to the settings' rule."""
    if root is not None or clients_root() is not None:
        return checked_root(root)
    resolved = Path(given).expanduser().resolve()
    return checked_root(resolved.parents[depth - 1] if len(resolved.parents) >= depth else resolved)


def return_dir(given: Path | str, *, root: Path | str | None = None) -> Path:
    """The return a typed or sent path names, rebuilt from the checked root
    and its own three names - or a :class:`DoorError` / ``LayoutError``.

    **A path from outside is parsed, never trusted** (decisions 176, 188).
    It must be exactly a return's place (``layout.return_at``): a folder in
    the client tree - where a client can write, and a planted journal
    would otherwise read as a prior - is never one, nor is a year or a
    household folder. What comes back is the root joined with the names
    the resolved path has there, through ``layout.return_dir_for``, so a
    name the rule refuses is refused here too. The API and every command
    line that takes a return's folder ask this.
    """
    base = _base(given, root, 4)
    household, year, name = layout.return_at(base, _placed(given, base))
    return layout.return_dir_for(base, household, year, name)


def household_dir(given: Path | str, *, root: Path | str | None = None) -> Path:
    """The household a typed or sent path names, rebuilt as
    :func:`return_dir` rebuilds a return."""
    base = _base(given, root, 2)
    return layout.private_household_dir(base, layout.household_at(base, _placed(given, base)))


def through_a_link(path: Path | str, root: Path | str) -> bool:
    """True when ``path`` is reached through a link below ``root`` - or is
    not under ``root`` at all.

    ``rglob`` follows a junction, and a junction a client (or a sync
    client) leaves in the drop folder points anywhere: at a folder outside
    the engagement whose files would then be *moved* into the firm's tree
    as the client's originals. What lies behind a link is not a drop, and
    nothing is made or written behind one. Only what lies between the root
    and the path is judged (decision 137's review, F5): the clients root
    may itself sit under a folder that is a link - ``G:\\Shared drives`` is
    Drive for desktop's own - and that must never refuse a move. The one
    definition since decision 188; the filer's walks and its step check
    ask it.
    """
    below = layout.parts_below(root, path)
    if below is None:
        return True
    here = Path(root)
    for name in below:
        here = here / name
        if is_link(here):
            return True
    return False


#: The kinds of place a write into the client tree may land in; the
#: household's own client folder is one only while it is being made.
_CLIENT_WRITES = frozenset({layout.INBOX, layout.IN_INBOX, layout.ORIGINALS, layout.IN_ORIGINALS})


def client_write(root: Path | str, household: str, target: Path | str, *,
                 making: bool = False) -> Path:
    """``target``, when a write for ``household`` may go there - else a
    :class:`DoorError` (``layout.OUTSIDE_CLIENT_PLACE``).

    **The one door into the tree a client is shared** (decision 188, R9).
    Lexically, the layout's parser must place ``target`` in exactly that
    household's inbox or one of its year folders of originals - or, with
    ``making``, the household's own client folder, which only the scaffold
    makes. On the disk, no folder between the root and the target may be a
    link (:func:`through_a_link`). Nothing here writes: the caller writes
    what the door approved.
    """
    place = layout.place_of(root, target)
    allowed = _CLIENT_WRITES | ({layout.CLIENT_HOUSEHOLD} if making else frozenset())
    if (place.kind not in allowed or os.path.normcase(place.household) != os.path.normcase(household)
            or through_a_link(target, root)):
        raise DoorError(layout.OUTSIDE_CLIENT_PLACE.format(path=target, household=household))
    return Path(target)


def client_folder_missing(root: Path | str, household: str, *, had_one: bool) -> str:
    """``layout.CLIENT_FOLDER_MISSING`` when the household's client folder
    is not on the disk and its record shows it had one (``had_one``: it was
    shared, or an original rests there) - else ``""`` (SPEC-162 ruling 2,
    kept by decision 188; the review's M3).

    **Decided here once**, and asked by the pass, by a new return into an
    existing household and by every form of Roll forward, before anything
    is written: a client folder made again under the old name would be an
    empty, unshared inbox the pass reads green while the client's real
    folder - renamed or moved - sits among the misfits. The record's half
    (``had_one``) is the caller's to read; this is the disk's half."""
    if had_one and not layout.client_household_dir(root, household).is_dir():
        return layout.CLIENT_FOLDER_MISSING.format(name=household)
    return ""


# -------------------------------------------------------------------- CLI ----

if __name__ == "__main__":
    import argparse

    from tracker.page import tolerant_console

    tolerant_console()   # a client's name the console cannot encode is no traceback

    parser = argparse.ArgumentParser(
        description="Say what kind of place a path is under the clients root, and whether "
                    "the app may write there for a household (it writes nothing)")
    parser.add_argument("path", help="the path to place")
    parser.add_argument("--root", default=None, help="the clients root (default: the saved one)")
    parser.add_argument("--household", default=None,
                        help="the household a client-tree write would be for (default: the "
                             "household the path names)")
    ns = parser.parse_args()
    try:
        base = checked_root(ns.root)
    except DoorError as exc:
        raise SystemExit(str(exc)) from None
    target = Path(ns.path).expanduser()
    target = (target if target.is_absolute() else base / target).resolve()
    place = layout.place_of(base, target)
    print(f"{target}")
    print(f"  place: {place.kind}")
    for field in ("household", "year", "return_name"):
        if getattr(place, field):
            print(f"  {field}: {getattr(place, field)}")
    try:
        client_write(base, ns.household or place.household, target,
                     making=place.kind == layout.CLIENT_HOUSEHOLD)
        print("  a write for the household may go here")
    except DoorError as exc:
        print(f"  no write goes here: {exc}")
