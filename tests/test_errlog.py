"""Tests for tracker/errlog.py - the tracker's one local debug log, out of the settings.

The claims are the module's whole debt. The log sat in the settings module
until P2.7 and asked the store where to live, while the store asked the
settings module for the data home and the program's folders, so each
imported the other. Now the log imports the settings module for its
``SettingsError`` and nothing else of the package when it loads, and asks the
store and ``errors`` only when it is used; the settings module imports
neither the store nor the log. It does not offer the log either: errlog
imports the settings module at load time, so a re-export there would be a
load-time cycle, and every reader names this module.

The log's own tests came with it from ``tests/test_settings.py``, whole and
unchanged but for their imports: the three that ask only the log. It lives
beside the tracker's database wherever the store goes; with the log unwritable
it says one fixed line on stderr and never the kept words; and with no data
home it yields ``None`` and the command still runs.
"""

from __future__ import annotations

import pytest

from tests.import_graph import import_edges
from tracker.settings import ENV_SETTINGS_DIR, settings_dir


@pytest.fixture
def beside_the_app(tmp_path, monkeypatch):
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    return tmp_path


def test_the_error_log_imports_only_the_settings_when_it_loads_and_the_store_and_errors_when_it_is_used():
    """A layer 0 module whose one load-time import of the package is the
    settings module, for ``SettingsError``. ``error_log_path`` asks the store
    and ``handleError`` asks ``errors``, each inside the function that needs
    it, so loading the log pulls in neither."""
    load, call = import_edges()

    assert load["errlog"] == {"settings"}, load["errlog"]
    assert call["errlog"] == {"errors", "store"}, call["errlog"]


def test_the_error_log_lives_beside_the_tracker_database(beside_the_app, monkeypatch):
    # Decision 193, the lane's ruling: beside the store, the folder 189's
    # pass-order.json uses, so it moves wherever the store moves - and
    # never in either client tree.
    import logging

    from tracker import store
    from tracker.errlog import ERROR_LOG_FILENAME, error_log, error_log_path

    elsewhere = beside_the_app / "data" / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(elsewhere))
    assert error_log_path() == elsewhere.parent / ERROR_LOG_FILENAME
    with error_log() as path:
        logging.getLogger("tracker.test").warning("a fabricated warning")
    assert path == elsewhere.parent / ERROR_LOG_FILENAME
    assert "a fabricated warning" in path.read_text(encoding="utf-8")
    assert not (settings_dir() / ERROR_LOG_FILENAME).exists()


def test_an_error_log_that_cannot_be_written_never_spills_kept_words_to_stderr(
        beside_the_app, monkeypatch, capfd):
    """Decision 190's landing review, SF1: with the log unwritable, logging's
    own handleError would print the record's arguments - the kept error's
    whole words - to stderr. The handler says one fixed line instead."""
    import logging

    from tracker import errors, store
    from tracker.errlog import ERROR_LOG_FILENAME, ERROR_LOG_NOT_WRITTEN, error_log
    from tracker.layout import CLIENTS_TREE

    quoted = f"/{CLIENTS_TREE}/Sample Household/Drop files here/W2.pdf"
    elsewhere = beside_the_app / "data" / store.STORE_FILENAME
    monkeypatch.setenv(store.ENV_STORE, str(elsewhere))
    (elsewhere.parent / ERROR_LOG_FILENAME).mkdir(parents=True)     # a folder: never writable as a file
    monkeypatch.setattr(logging, "raiseExceptions", True)
    capfd.readouterr()
    with error_log("tracker") as path:
        errors.keep("probe", ValueError(quoted), name="W2.pdf")
    err = capfd.readouterr().err
    assert quoted not in err and "W2.pdf" not in err, err
    said = err.strip().splitlines()
    head, tail = ERROR_LOG_NOT_WRITTEN.format(name=path.name, kind="\0").split("\0")
    assert len(said) == 1 and said[0].startswith(head) and said[0].endswith(tail), err


def test_the_error_log_is_none_when_the_data_home_cannot_be_had(monkeypatch):
    """Decision 186 on 193: the error log sits beside the store, in the
    data home; with no data home there is no log, and the block still runs
    rather than raising before the command can say why."""
    import logging

    from tracker import store
    from tracker.errlog import error_log
    from tracker.settings import ENV_DATA_HOME

    monkeypatch.delenv(store.ENV_STORE, raising=False)
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")
    with error_log() as path:
        logging.getLogger("tracker.test").warning("a fabricated warning")
    assert path is None
