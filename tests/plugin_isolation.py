"""Every test gets an app folder of its own: its settings file, its store and its data home are its own
(decision 185), and the suite can never reach the checkout's. The one plugin of the four that sets an autouse fixture up first.

The plugins are listed in ``tests/conftest.py``'s ``pytest_plugins`` in the order isolation, fakes, agreement,
session. pytest sets a plugin's autouse fixtures up in that order and, inside one plugin, by name, so this plugin
(listed first) holds the app folder's fixture, which has to be set up before every other autouse fixture and torn down
after all of them (``tests/test_suite_shape.py``'s ``AUTOUSE_ORDER`` pins the order). It imports nothing from another
plugin. The session's own folder, and the tripwire that watches for a real place, are in ``plugin_session``.

**An app folder of its own** (``an_app_folder_of_its_own``). The store keeps one
connection per process and the file it would otherwise open sits beside
the settings file, which on a developer's machine is the repository.
``TRACKER_STORE`` points it at this test's own ``tmp_path`` instead, and
the connection is closed at teardown before the temporary folder goes,
because Windows will not delete a database a handle is open on. No test
can see another's rows. The settings folder is ``tmp_path / "app"``, the
same folder as the store, so no test reads the checkout's ``settings.json``
(decision 185).
"""
from __future__ import annotations

import shutil
from pathlib import Path

import pytest

from tracker import settings, store

#: The folder, inside a test's tmp_path or the session's folder, that plays
#: "beside the app": the settings file and the store live in it. Most tests
#: that set TRACKER_SETTINGS_DIR themselves already name this one.
APP_FOLDER = "app"

def own_folders(patch: pytest.MonkeyPatch, folder: Path) -> None:
    """Point this process, and every child it starts, at ``folder`` for the
    settings file and the store (decision 185): the one place the suite says
    where "beside the app" is - and at :func:`data_home_for` ``folder`` for
    the data home (decision 186), never the account's own."""
    patch.setenv(settings.ENV_SETTINGS_DIR, str(folder))
    patch.setenv(store.ENV_STORE, str(folder / store.STORE_FILENAME))
    patch.setenv(settings.ENV_DATA_HOME, str(data_home_for(folder)))

def data_home_for(folder: Path) -> Path:
    """The suite's data home for the app folder ``folder``: a sibling of the
    folder that holds it (``<tmp_path>-data`` for a test's
    ``<tmp_path>/app``), never inside it - many tests make ``tmp_path``
    itself the clients root, and a root may not hold the data home
    (``settings.ROOT_HOLDS_DATA``, decision 186)."""
    holder = Path(folder).parent
    return holder.with_name(holder.name + "-data")

@pytest.fixture(autouse=True)
def an_app_folder_of_its_own(tmp_path):
    """Every test gets its own settings folder and its own database, and no
    test leaks either into another - nor reads the checkout's (decision 185).

    Both sit in ``tmp_path / "app"``, set through :func:`own_folders`, the
    one place the suite says where "beside the app" is. This is the one
    fixture that does it for a test, and it cannot be taken away: a test's
    ``monkeypatch.undo()`` restores what was there before the test, which is
    this fixture's value, never the checkout's.

    ``tracker.store`` keeps one connection per process, to the file beside
    the settings file - which on a developer's machine is the repository
    itself. A suite that used it would write every test's rows into one
    database, and the next test would read the last one's engagements.
    ``TRACKER_STORE`` is what the store reads instead, and it is pointed at
    a file under this test's own ``tmp_path``.

    In the plugin listed first, so it is set up before every other autouse
    fixture and torn down after all of them: the connection is closed
    before the temporary folder goes, because Windows will not delete a
    database a handle is open on. It is closed on the way in too, in case
    a test left one open to a file that no longer exists.

    A ``MonkeyPatch`` of its own, not the ``monkeypatch`` fixture: that one
    is shared with the test, and a test calling ``monkeypatch.undo()`` -
    several do, to put a patched writer back - would take this variable
    with it and point the next line at the repository's own database.

    It sets up first and tears down last, so it is also where the short
    clients roots of :func:`short_root` are cleared and removed: the
    agreement fixtures (``plugin_agreement``) have to still see them when they run.
    """
    patch = pytest.MonkeyPatch()
    own_folders(patch, tmp_path / APP_FOLDER)
    # The firm's corpus is seen only by tests/test_real_corpus.py's rows,
    # which captured it at collection; no other test, and no tool a test
    # calls, reads it by accident.
    patch.delenv(settings.ENV_REAL_CORPUS, raising=False)
    store.close()
    _ALSO_WALK.clear()
    try:
        yield
    finally:
        store.close()
        patch.undo()
        for folder in _ALSO_WALK:
            shutil.rmtree(folder, ignore_errors=True)
        _ALSO_WALK.clear()

#: Folders outside this test's ``tmp_path`` the agreement fixtures walk too.
#: A pytest temporary folder is ninety characters before the layout starts,
#: and creation refuses a return whose deepest working copy would pass what
#: Windows will open (decision 125) - which is a refusal about the whole
#: path, so a test that creates a real catalog needs a root as short as the
#: office's. Registered here rather than moved out of the suite's sight:
#: the store and the view are held to the record inside them exactly as
#: they are under ``tmp_path``.
_ALSO_WALK: list[Path] = []
