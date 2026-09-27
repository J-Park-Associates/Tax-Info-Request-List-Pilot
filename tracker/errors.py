"""What an error is called where a person can see it: its class, never its words.

A parser's message is the file's own text. pypdf quotes the bytes it choked
on, Pillow names the chunk it could not decode, the email parser repeats the
header it refused and an OS error spells out the path. Before decision 190
the tracker put that message, whole, into the reason on a row - so into the
record, both of the firm's pages, the run log and the app's JSON - and a
damaged W-2 could carry its employee's number into every one of them.

**A class name, and not a shortened message** (decision 190). The one
earlier attempt at a limit, the container's first line cut to 120
characters, is the rejected alternative, and the reason is that 120
characters is an SSN - and a name, an address and an account number with
room to spare. No length is short enough to be safe, because nothing
about a message's length says whose words it is. A class name is written
by a programmer (``PdfReadError``, ``BadZipFile``, ``UnknownPacking``); it
says what kind of failure it was, which is all a person deciding "resend
or look at it" needs, and it can never be a document's words.
:func:`error_class` is that name, with an ``OSError``'s errno spelled out
(``FileNotFoundError (ENOENT)``) because "which OS error" is the one thing a
class alone does not say, and the errno is a number the OS chose, never a
path. An error the tracker raises about a store or a record the disk or
the engine refused (``StoreUnavailable``, ``RecordNotWritten``, decision
189) says the code it carries the same way (``StoreUnavailable
(SQLITE_BUSY)``): such a class sets :data:`SAYS_ITS_CODE` and keeps the
code - data, never prose - in ``code``. This module imports nothing of the
package, so the classes mark themselves rather than being named here. The
fixed sentence around it is the reason's own template, so there is no new
vocabulary here.

**One rule, said once.** Decision 189 first wrote this rule as
``content_check.said_as_class``, for a run's and a reading's errors;
decision 190 moved it here, to layer 0, so that every layer that catches
an error names it without reaching upward, in 189's form. There is no
second definition: ``tests/test_errors.py`` fails the suite if a module
under ``tracker/`` defines another function that builds an error's name
from its class, or spells a caught exception's class inline
(``exc.__class__.__name__``) - a second spelling that says an ``OSError``
without its errno, so one failure would read two ways on one page.

**The words are not thrown away: they are kept, apart** (:func:`keep`). A
programmer mending a parser needs the message and the trace, so they go to
the debug logger :data:`DEBUG_LOGGER`, at WARNING, and from it to the one
local debug log the tracker has: decision 193's ``tracker-errors.log``,
beside the store in decision 186's data home, which
:func:`tracker.settings.error_log` attaches to the ``tracker`` logger for
the length of a pass or an app command (decision 190, Part 4). The logger
propagates to ``tracker`` so that log catches it; it keeps a
``NullHandler`` so that outside that block - no log attached, a CLI run by
hand - Python's last-resort handler never prints a kept message on stderr
(it writes only for a record that meets no handler at all). This module
builds no log of its own and names no file: one log, one authority
(security principle 2), and ``tests/test_errors.py`` fails the suite if any
module but ``settings`` attaches a file handler or names a log file. The
one console the package gives the root logger - a hand-run scan's -
is made by :func:`console`, which keeps kept words off it.

**A reading child keeps nothing itself.** It runs in a process of its own
(decision 169) that never opens a log: :func:`keep_for_the_parent` makes
its keeps collect instead, :func:`take_kept` hands them over with each
answer, and the pass keeps each one on its own debug log
(``ocr.Session``), so a child's words land where a pass's do.

**The record's own errors keep their text.** A ``ManifestError`` or a
``StoreError`` is a sentence the firm wrote about the firm's own files; it
is not a client document's words, and a person needs all of it. This module
is for exceptions a client's file can cause.

Standard library only, and nothing of the package: every layer that catches
a parser's error may name it without reaching upward.
"""

from __future__ import annotations

import builtins
import errno as _errno
import logging
import sys
import traceback

#: The logger the full message and trace are kept on. Nothing else in the
#: tracker logs to it; it propagates to ``tracker``, where decision 193's
#: error log is attached (see the module docstring).
DEBUG_LOGGER = "tracker.debug"

#: Where the debug log goes, as the CLI says it.
WHERE_KEPT = ("tracker-errors.log beside the tracker's database, in the data home (decisions 186 "
              "and 193), while a pass or an app command runs; kept nowhere otherwise")

#: At most this many kept entries travel back with one answer from a
#: reading child (:func:`take_kept`); past it, one line says how many more
#: were dropped. A short list: one job's failures, not a log.
KEPT_PER_ANSWER = 20

_debug = logging.getLogger(DEBUG_LOGGER)
_debug.addHandler(logging.NullHandler())
_debug.propagate = True
_debug.setLevel(logging.WARNING)

#: A reading child's keeps, collected for the parent (:func:`keep_for_the_parent`);
#: ``None`` in every other process, which keeps on its own logger.
_for_the_parent: list[str] | None = None
_dropped = 0


#: The class attribute an exception sets, true, when the code it carries
#: in ``code`` is said beside its class (decision 189's ``StoreUnavailable``
#: and ``RecordNotWritten``). A marker rather than an import, so this
#: module stays at layer 0; a third-party error with a ``code`` of its own
#: never sets it, so its ``code`` is never said.
SAYS_ITS_CODE = "says_its_code"


def error_class(exc: BaseException, *, with_code: bool = True) -> str:
    """How an error is said wherever a person or a record reads it
    (decisions 189 and 190, security principle 7): its class, and the code
    it carries - an errno's name (``PermissionError (EACCES)``), or the
    code of a store or record the disk refused (``RecordNotWritten
    (ENOSPC)``) - and never its message. See the module docstring for why
    not even part of it.

    ``with_code=False`` is the class alone, one token, for the run log's
    codes (decision 186's ``crashed:<class>``), which a later reader counts
    by class: the same rule, spelled here rather than a second time inline."""
    name = type(exc).__name__
    if not with_code:
        return name
    if getattr(type(exc), SAYS_ITS_CODE, False):
        return f"{name} ({exc.code})"
    if isinstance(exc, OSError) and exc.errno in _errno.errorcode:
        return f"{name} ({_errno.errorcode[exc.errno]})"
    return name


def said(exc: BaseException, firm_written: tuple[type[BaseException], ...]) -> str:
    """What a row or a page says of ``exc``: the whole sentence when it is
    one of ``firm_written`` - the tracker's own errors, which the firm wrote
    about the firm's own files - and otherwise :func:`error_class`.

    The caller names its own errors because this module imports nothing of
    the package; the rule itself - firm text whole, anything else by its
    class - is spelled here once (decision 190)."""
    return str(exc) if isinstance(exc, firm_written) else error_class(exc)


def keep(where: str, exc_or_text: BaseException | str, *, name: str = "") -> None:
    """Keep the whole of an error - message and trace - on the debug log.

    ``where`` is the firm's word for the place it happened (``"filer"``),
    ``name`` the file's, and ``exc_or_text`` the exception itself or, from
    the reading child, the text it sent back. Nothing here reaches a
    reason, a record, a page or the run log: it goes to
    :data:`DEBUG_LOGGER` at WARNING, which reaches the local debug log when
    one is attached, or - in a reading child - to the list its parent
    takes (:func:`take_kept`)."""
    global _dropped
    said = f"{where} ({name})" if name else where
    if isinstance(exc_or_text, BaseException):
        detail = "".join(traceback.format_exception(
            type(exc_or_text), exc_or_text, exc_or_text.__traceback__))
    else:
        detail = str(exc_or_text)
    if _for_the_parent is not None:
        if len(_for_the_parent) < KEPT_PER_ANSWER:
            _for_the_parent.append(f"{said}: {detail.rstrip()}")
        else:
            _dropped += 1
        return
    _debug.warning("%s: %s", said, detail.rstrip())


def keep_for_the_parent() -> None:
    """In a reading child: collect every :func:`keep` for the pass, and log
    nothing here - the child never opens a log (decision 190, Part 4)."""
    global _for_the_parent, _dropped
    _for_the_parent, _dropped = [], 0


def take_kept() -> list[str]:
    """What this child kept since the last answer, emptied as it is taken:
    at most :data:`KEPT_PER_ANSWER` entries, and a last line counting any
    dropped past them. Empty in a process that keeps on its own logger."""
    global _dropped
    if _for_the_parent is None:
        return []
    taken = list(_for_the_parent)
    if _dropped:
        taken.append(f"errors: {_dropped} more kept entries were dropped past {KEPT_PER_ANSWER}")
    _for_the_parent.clear()
    _dropped = 0
    return taken


class _NotKept(logging.Filter):
    """Drops the debug logger's records from a console's handler."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(DEBUG_LOGGER)


def console(**config) -> None:
    """``logging.basicConfig(**config)`` for a CLI a person runs by hand,
    with every root handler kept free of :data:`DEBUG_LOGGER`: the words
    :func:`keep` holds propagate for the error log's sake, and a console
    must never print them (decision 190, D-6). The one way the package
    gives the root logger a console."""
    logging.basicConfig(**config)
    for handler in logging.getLogger().handlers:
        if not any(isinstance(one, _NotKept) for one in handler.filters):
            handler.addFilter(_NotKept())


def _main(argv: list[str]) -> int:
    """``class <ExceptionName> [errno]``: the name a built-in exception is
    shown by; ``where``: where the full message is kept."""
    if argv[:1] == ["where"] and len(argv) == 1:
        print(WHERE_KEPT)
        return 0
    if argv[:1] == ["class"] and len(argv) in (2, 3):
        kind = getattr(builtins, argv[1], None)
        if not (isinstance(kind, type) and issubclass(kind, BaseException)):
            print(f"not a built-in exception: {argv[1]}", file=sys.stderr)
            return 1
        exc = kind(int(argv[2]), "") if len(argv) == 3 else kind()
        print(error_class(exc))
        return 0
    print("usage: python -m tracker.errors class <ExceptionName> [errno] | where", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
