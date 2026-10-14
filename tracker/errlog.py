"""The tracker's one local debug log, where every unexpected error's words go (decision 193).

An unexpected error's full text and traceback, and every warning the package
logs, are written to ``tracker-errors.log`` and nowhere else: never on
screen, in the record, on the page or in the run log (security principle 7).
They can name a client's folder, so the log sits beside the tracker's
database on this machine (decision 186), never in either client tree, and
is rotated by size. :func:`error_log` attaches it to the ``tracker`` logger
for the length of a pass or an app command; the API, the runner and the
resident engine attach it. It is the one file any logger writes (decision
190, Part 4): ``errors.keep``'s words reach it through ``tracker.debug``,
and ``tests/test_errors.py`` fails a second log file, a second handler or a
name for one in any other module.

**Why it is its own module** (SPEC-architecture-p2 P2.7, decision P318; the
architecture audit's B-5 and B-6). The log sat at the foot of
:mod:`tracker.settings`, which is the settings file's: where the clients
live and where the data folder is. To say where the log lives it asked
``store.store_path()``, at call time, while the store asked the settings
module for the data home and the program's folders, so each imported the
other (B-6). Here the log asks the store from this module, and the settings
module imports neither: the settings↔store cycle is gone. The store's own
rule for where it lives stays in the store, which may not import the
settings module at load time (decision 101).

**Why the settings module does not re-export it.** This module imports
``SettingsError`` from the settings module at load time, so a re-export in
the settings module would be a load-time cycle. There is no facade: the
API, the runner, the resident engine and the suite import the log from here.
The store and :mod:`tracker.errors` are imported where the log asks them,
at call time, as they were in the settings module: the store sits above this
module, and this module's one load-time import of the package is the
settings module.
"""

from __future__ import annotations

import logging
import os
import sys
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import cast

from tracker.settings import SettingsError

#: The local debug log (decision 193, security principle 7): an
#: unexpected error's full text and traceback, and every warning the
#: package logs, go here and nowhere else - never on screen, in the record,
#: on the page or in the run log. It can name a client's folder, so it
#: lives beside the tracker's database, on this machine, never in either
#: client tree; rotated by size, and never synced to disk per line.
ERROR_LOG_FILENAME = "tracker-errors.log"
ERROR_LOG_MAX_BYTES = 1_000_000
ERROR_LOG_BACKUPS = 3
ERROR_LOG_FORMAT = "%(asctime)s pid=%(process)d %(name)s %(levelname)s %(message)s"
#: The one line said on stderr when the error log cannot take a record
#: (decision 190's landing review, SF1): the failure's class and code,
#: never the record - whose words go to the log "and nowhere else".
ERROR_LOG_NOT_WRITTEN = "{name} could not be written ({kind}); what it would have held is not said here."


def error_log_path() -> Path:
    """Where :data:`ERROR_LOG_FILENAME` lives: beside the tracker's database
    (the folder of ``store.store_path()``, the one the pass-order hint uses),
    so it moves with the store wherever the store goes. ``store`` is asked
    at call time: it sits above this module."""
    from tracker import store

    return store.store_path().parent / ERROR_LOG_FILENAME


class _ErrorLog(logging.Handler):
    """The error log's own few lines of rotation (decision 193's review,
    S2): not ``logging.handlers``, which loads ``socket`` at import, so
    importing the tracker loads no network module. Before a record that
    would take the file past :data:`ERROR_LOG_MAX_BYTES` the file becomes
    ``.1``, ``.1`` becomes ``.2`` and so on to :data:`ERROR_LOG_BACKUPS`;
    each record is appended whole in UTF-8 and never ``fsync``-ed. Both
    numbers are read when a record is written.

    A record it cannot write is said by :meth:`handleError` as one fixed
    line, never through ``logging``'s own, which prints the record's
    message and arguments - a kept error's whole words - to stderr
    (decision 190's landing review, SF1)."""

    def __init__(self, path: Path) -> None:
        super().__init__(logging.WARNING)
        self.path = path

    def emit(self, record: logging.LogRecord) -> None:
        try:
            data = (self.format(record) + "\n").encode("utf-8")
            try:
                size = self.path.stat().st_size
            except FileNotFoundError:
                size = 0
            if size and size + len(data) > ERROR_LOG_MAX_BYTES:
                self._rotate()
            with self.path.open("ab") as handle:
                handle.write(data)
        except Exception:
            self.handleError(record)

    def handleError(self, record: logging.LogRecord) -> None:
        # At call time, as store is in error_log_path(): this module's one
        # load-time import of the package is settings.
        from tracker import errors

        if logging.raiseExceptions and sys.stderr is not None:
            try:
                # handleError runs only inside emit's except, so there is an exception.
                sys.stderr.write(ERROR_LOG_NOT_WRITTEN.format(
                    name=self.path.name, kind=errors.error_class(cast(BaseException, sys.exc_info()[1]))) + "\n")
            except OSError:
                pass    # no stderr to say it on either: as logging's own handleError does

    def _rotate(self) -> None:
        def kept(n: int) -> Path:
            return self.path.with_name(f"{self.path.name}.{n}")

        kept(ERROR_LOG_BACKUPS).unlink(missing_ok=True)
        for n in range(ERROR_LOG_BACKUPS - 1, 0, -1):
            if kept(n).exists():
                os.replace(kept(n), kept(n + 1))
        os.replace(self.path, kept(1))


@contextmanager
def error_log(logger_name: str = "tracker") -> Iterator[Path | None]:
    """Attach the rotating error log to ``logger_name`` for the block.

    WARNING and above, UTF-8, opened only when something is written, and
    never ``fsync``-ed: it is a debug aid, and a sync per line would cost
    the pass that is failing. A folder that cannot hold it costs the log,
    never the command - and so does a data home that cannot be had
    (decision 186): the log sits beside the store, which lives there, so
    there is no log and the block yields ``None``; the command says why.
    """
    logger = logging.getLogger(logger_name)
    path: Path | None = None
    handler: logging.Handler | None = None
    try:
        path = error_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        handler = _ErrorLog(path)
    except (OSError, SettingsError):
        handler = None
    if handler is not None:
        handler.setFormatter(logging.Formatter(ERROR_LOG_FORMAT))
        logger.addHandler(handler)
    try:
        yield path
    finally:
        if handler is not None:
            logger.removeHandler(handler)
            handler.close()
