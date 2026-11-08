"""Creating a return - the folder it takes, the refusals it meets before
anything is written - and decision 137's undo of what a failed create or
rollover made.

Each part upholds the decision rows it names:

- **The folder a new return takes** (decisions 125, 131 and 188).
  :func:`_new_return_dir` is ``<root>/<private tree>/<household>/<year>/<return>``,
  the layout's answer and never a typed path. It refuses a household or a
  return that is not one folder name (``household_edit._folder_name``), a
  year outside the bounds the dialog shows, a return of that name already
  there for the household and year by the layout's key (decision 188), and
  a list whose deepest working copy would pass what Windows will open,
  through the one room function (``copies.refuse_a_path_past_the_limit``,
  decision 131) with its review-folder term, because the scaffold is about
  to make that folder.
- **A typed household name already taken** (decision 188, R7).
  :func:`_refuse_a_taken_household_name` holds a new household's name to
  the layout's key across both trees: a household folder or a household
  record's name, a folder the tracker did not make where a household would
  be, and a client folder no household owns. :func:`_folders_in` is its one
  listing of a tree.
- **The undo** (decision 137, M1, and its review's F4). :func:`_undo_made`
  undoes, innermost first, exactly the folders one call's own ``mkdir``
  made (``fsio.make_new_folders``' list): a folder the call owns - the
  return, or a household whose record it wrote - goes whole, through
  :func:`_undo_create`; a level above one, such as a year folder, goes only
  when it is empty. **``_undo_create``'s ``shutil.rmtree`` is reached only
  through ``_undo_made``, on a folder the call made**, so a folder that was
  already there - a person's own, an old return - is never removed, which
  is what it once did. The two are one guard and live together, never
  apart: that is the whole of "remove only what this call made".

**Why it is its own module** (SPEC-architecture-p5 P5.6, P343; the
architecture audit's C-1 item 4). These rules sat in ``tracker.api`` at
layer 5, where only the app's commands could reach them - the bug class
decision 123 found, when a rollover run on the command line missed a rule
the API alone applied. Here, a command line could reach them. The
handlers keep their bodies and call these by import:
``tracker.api._cmd_create`` writes the command's warnings and reads its
per-command state, which is the API's (the audit's C-3), and builds its
reply where it always did; ``tracker.api._cmd_rollover`` shares
:func:`_new_return_dir` and :func:`_undo_made`.

**Why it sits at layer 3.** It reads a typed name through
:mod:`tracker.household_edit` in its own layer, measures the room through
:mod:`tracker.copies` (layer 2), and asks the household record
(``households``), the journal's place (``ledger``), the request list's
refusal and the year's bounds (``manifest``), the store, and
:mod:`tracker.screen_words` (layer 1; the three refusals it says) below
it, and the layout and ``errors`` (layer 0). It imports nothing above
layer 3, and never the API, which imports back by name what its handlers
call. A stand-in follows the name's readers (the audit's A-4):
``load_household_info`` is read here as well as in the API and in
``household_edit``, so a stand-in for it is set on all three.

It does not log: it binds no logger. The one line it may write, when a
failed return's store row cannot be dropped, goes through
``errors.keep`` under the words it always had (``"api: forgetting a
failed return"``), so the debug log reads the same.
"""

from __future__ import annotations

import os
import shutil
from pathlib import Path

from tracker import errors, layout, ledger, store
from tracker.copies import refuse_a_path_past_the_limit
from tracker.household_edit import _folder_name
from tracker.households import load_household_info, return_name_taken
from tracker.layout import return_dir_for
from tracker.manifest import ManifestError, check_tax_year
from tracker.screen_words import CLIENT_FOLDER_TAKEN, DUPLICATE_HOUSEHOLD, HOUSEHOLD_NOT_OURS


def _new_return_dir(root: Path, household: str, year: int, return_name: str,
                    items: list | None = None) -> Path:
    """Where a new return goes: ``<root>/<private tree>/<household>/<year>/<return>``.

    Refused when the household or the return is not a single folder name,
    when the year is outside the bounds the dialog shows, when a return of
    that name already exists for that household and year, and when the
    deepest working copy the list implies would pass what Windows will
    open (§3.9.1 of decision 125): a folder made today that cannot hold a
    filed document in February is a failure at a filing deadline, and the
    refusal names the length so a person knows what to shorten.
    """
    household = _folder_name(household, "household")
    return_name = _folder_name(return_name, "return")
    year = check_tax_year(int(year))
    engagement = return_dir_for(root, household, year, return_name)
    # Unique by the layout's key within the household-year (decision
    # 188), so a look-alike of a return already there is that return.
    if (taken := return_name_taken(engagement.parent, return_name)) is not None:
        raise ManifestError(
            f"A return named '{taken}' already exists for {household} {year}")
    refuse_a_path_past_the_limit(engagement, items or [])
    return engagement


def _folders_in(tree: Path) -> list[Path]:
    """The folders directly in one tree, by name, from one listing."""
    try:
        with os.scandir(tree) as entries:
            return sorted(Path(entry.path) for entry in entries if entry.is_dir(follow_symlinks=False))
    except OSError:
        return []


def _refuse_a_taken_household_name(root: Path, household: str) -> None:
    """Refuse a typed household name that is, by the layout's key, one
    already taken in either tree (decision 188, R7): a household folder or
    a household record's name (:data:`DUPLICATE_HOUSEHOLD` - pick it in the
    list), a folder the tracker did not make where a household would be
    (:data:`HOUSEHOLD_NOT_OURS`), or a client folder no household owns
    (:data:`CLIENT_FOLDER_TAKEN`). Names are unique across both trees."""
    key = layout.name_key(household)
    for folder in _folders_in(layout.private_tree_of(root)):
        recorded = ledger.path_for(folder).is_file()
        claim = ""
        if recorded:
            try:
                claim = load_household_info(folder).name
            except ManifestError:
                claim = ""
        if layout.name_key(folder.name) == key or (claim and layout.name_key(claim) == key):
            if recorded:
                raise ManifestError(DUPLICATE_HOUSEHOLD.format(existing=folder.name))
            raise ManifestError(HOUSEHOLD_NOT_OURS.format(name=folder.name))
    for folder in _folders_in(layout.clients_tree_of(root)):
        if layout.name_key(folder.name) == key:
            raise ManifestError(CLIENT_FOLDER_TAKEN)


def _undo_made(made: list[Path], owned: set[Path]) -> None:
    """Undo, innermost first, the folders one create or rollover made -
    :func:`tracker.fsio.make_new_folders`' list and nothing else.

    Only a folder this call **owns** - the return, or a household whose
    record it wrote - is removed whole (:func:`_undo_create`). A level
    above one, such as a year folder it had to make, is removed only when
    it is empty (the review's F4): a second create running at the same
    moment may have put its own return there, and that is not this call's
    to take."""
    for folder in reversed(made):
        if folder in owned:
            _undo_create(folder)
            continue
        try:
            folder.rmdir()
        except OSError:
            pass


def _undo_create(engagement: Path) -> None:
    """What a failed create or rollover leaves behind: nothing.

    **Only ever called on a folder this call's own mkdir created**
    (decision 137; :func:`_undo_made` is how every caller reaches it). The
    ``rmtree`` is whole because everything under such a folder is this
    call's too; called on a folder that was already there it would remove
    a person's folder, or an old return, which is what it once did.

    The folder first, so the name is free again whatever happens next;
    then the store's row, in its own try, because a store that cannot be
    reached at this moment (locked, refused by version) must not replace
    the refusal sentence the person is owed with its own, nor leave the
    folder standing for :func:`_new_return_dir` to refuse by name. The
    row it could not drop is a ghost ``create_engagement`` forgets on the
    next attempt.
    """
    shutil.rmtree(engagement, ignore_errors=True)
    try:
        store.forget(store.connect(), engagement)
    except Exception as exc:
        errors.keep("api: forgetting a failed return", exc, name=engagement.name)
