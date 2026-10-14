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
"""

from __future__ import annotations

from tests.import_graph import import_edges


def test_the_error_log_imports_only_the_settings_when_it_loads_and_the_store_and_errors_when_it_is_used():
    """A layer 0 module whose one load-time import of the package is the
    settings module, for ``SettingsError``. ``error_log_path`` asks the store
    and ``handleError`` asks ``errors``, each inside the function that needs
    it, so loading the log pulls in neither."""
    load, call = import_edges()

    assert load["errlog"] == {"settings"}, load["errlog"]
    assert call["errlog"] == {"errors", "store"}, call["errlog"]
