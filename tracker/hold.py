"""The per-reply memo: the machine's answers, held for one reply or one household and no longer.

A read-only reply asks the machine the same few questions thousands of
times - where the data folder is, where the program is, what the settings
file says, what each folder resolves to - and on the office PC a question
to the disk costs a tenth of a millisecond: 750 returns took 53 s, nearly
all of it these repeats (P118). A pass asked them as often: at 1,000
households, 6.9 million times a pass with nothing new to file (P207). So
the answers are held for one hold and dropped after it.

- Inside :func:`one_reading`, one read-only reply, nothing is written, so
  the first answer is the answer for the whole reply, and a write to the
  settings file or a recorded event is refused outright
  (:func:`refuse_a_write_while_reading`).
- Inside :func:`one_household`, one household of a pass, the pass writes
  its records and the store, so a path is held only once it is there
  (:func:`resolved`), and a write to the settings file is refused
  (:data:`WRITE_WHILE_HOLDING`). A person's change between two households
  is seen by the next one.
- Outside both, nothing is held, so an override takes effect at once. An
  error is never held, and a nested hold is the outer one.

:func:`held` is **the one memo whose life is a hold** (P215): the answers
the package keeps for one reply or one household - where the settings
module says the data folder and the program are, the store's engagement key
and its held record reads (``store.held_read``) - are kept through it, so
what is held, and for how long, is worded once.

**Why it is its own module** (SPEC-architecture-p2 P2.6; the architecture
audit's B-5). The hold is not the settings file's: it is the life of an
answer, and the store keeps its own reads in it as the settings do. It sat
at the foot of :mod:`tracker.settings`, so where a record read is kept was
found in the module of the settings file. Here it is at layer 0 and imports
nothing of the package. The settings file's own key, ``_SETTINGS_HELD``,
stayed in the settings module beside ``_read``, the one function that
holds an answer under it.

**Why the settings module reads it through the module.** :func:`_holding`
rebinds :data:`_HELD` and :data:`_HOLDING` under ``global`` when a hold
begins and when it ends, so ``from tracker.hold import _HELD`` would keep
the ``None`` it found at import and never see a hold begin. The settings
module imports ``hold``, reads ``hold._HELD`` and asks ``hold.held``, and it
re-exports the public names, by assignment - never ``_HELD`` or
``_HOLDING`` - until P2.13 points their readers here. The engine's state
register (:mod:`tracker.resident`) keys both names to this module.

The docstrings below came with the code, word for word: the
:func:`data_home`, :func:`app_dir`, :func:`program_folders`, :func:`_read`
and :func:`_write` they name are the settings module's.
"""

from __future__ import annotations

import os
from collections.abc import Callable, Iterator
from contextlib import contextmanager
from pathlib import Path
from typing import TypeVar

# ------------------------------------------------------- one reading ----

#: The answers held for the one read-only reply under way (P118) or the one
#: household a pass is serving (P207), or None when neither is under way -
#: which is always, outside :func:`one_reading` and :func:`one_household`.
_HELD: dict | None = None
#: Which of the two holds :data:`_HELD`: :data:`HOLD_READING` refuses every
#: write, :data:`HOLD_HOUSEHOLD` lets the pass write its records and the
#: store and refuses only a write to the settings file.
_HOLDING = ""
HOLD_READING = "reading"
HOLD_HOUSEHOLD = "household"
#: Whatever one held answer is (:func:`held`).
T = TypeVar("T")


@contextmanager
def one_reading() -> Iterator[None]:
    """Hold this process's answers to the machine's questions for one
    read-only reply (P118, ``pilot/SPEC-firm-cache.md``): where the data
    folder is (:func:`data_home`), where the program is (:func:`app_dir`,
    :func:`program_folders`), what the settings file says (:func:`_read`)
    and what each path resolves to (:func:`resolved`).

    **Why.** A firm-wide reply asks them thousands of times - every store
    read asks where the store is, and every answer re-proves that the data
    folder is not inside the program by asking the disk - and on the
    office PC a question to the disk costs a tenth of a millisecond: 750
    returns took 53 s, nearly all of it these repeats.

    **Why only here.** A read-only command changes none of the answers - no
    environment variable, no settings file, no folder of its own - so the
    first answer is the answer for the whole reply. A writer, the pass and
    the suite may change them between two questions, and outside a reading
    nothing is held: :func:`data_home` still takes an override at once. An
    error is never held; the question is asked again. Nested readings are
    one reading, and a reading inside a household's hold is part of that
    hold."""
    yield from _holding(HOLD_READING)


@contextmanager
def one_household() -> Iterator[None]:
    """Hold the same answers as :func:`one_reading` for one household of a
    pass (P207, ``pilot/SPEC-scale-1000.md``), while the pass writes.

    **Why.** The pass asks them as often as the firm view did: at 1,000
    households a pass with nothing new to file asked the disk 6.9 million
    times, nearly all of them these repeats, and on the office PC a
    question to the disk costs a tenth of a millisecond.

    **Why it is safe while the pass writes** (the doubt P121 left open).
    The pass changes no environment variable and never writes the settings
    file, and nothing it does moves the program or the data folder, so
    those answers stand for the household. A path is held only once it is
    there (:func:`resolved`): a folder the pass makes later is resolved
    again rather than answered from before it existed. Held for one
    household and dropped after it, so a person's change between two
    households - a settings save, a folder renamed in the app - is seen by
    the next one. A write to the settings file inside it is refused
    (:func:`_write`): every setter writes back what it read, which here is
    the held copy, and would undo a save the app made meanwhile. An error
    is never held. Nested inside a reading or another household's hold, it
    is part of that hold."""
    yield from _holding(HOLD_HOUSEHOLD)


def _holding(kind: str) -> Iterator[None]:
    """The one body of both holds: a fresh :data:`_HELD` of ``kind``, or,
    when a hold is already under way, that hold unchanged - so a nested
    hold is the outer one - and nothing held once the outermost ends,
    whatever ended it."""
    global _HELD, _HOLDING
    if _HELD is not None:
        yield
        return
    _HELD, _HOLDING = {}, kind
    try:
        yield
    finally:
        _HELD, _HOLDING = None, ""


def held(key: tuple, answer: Callable[[], T], *, there: Path | str | None = None) -> T:
    """``answer()``, kept for the hold under way: **the one memo whose life
    is a hold** (pilot P215). Every answer the package keeps for one reply
    or one household is kept here, so what is held, and for how long, is
    worded once.

    - Outside a hold: ``answer()`` every time - nothing is kept.
    - Inside a reading (P118): asked once and kept for the reading, which
      changes nothing.
    - Inside a household's hold (P207): asked once, and kept only when
      ``there`` is None or the folder ``there`` names resolves to an answer
      that is itself held - which, by :func:`resolved`'s rule, means it was
      there when it was resolved. An answer about a folder the pass makes
      later is never kept from before the folder existed.
    - An exception is never kept: the question is asked again.

    ``key`` must name everything the answer depends on, as text - never a
    ``Path``'s equality, which on Windows folds case (P219)."""
    if _HELD is None:
        return answer()
    if key in _HELD:
        return _HELD[key]
    value = answer()
    if there is not None and _HOLDING != HOLD_READING:
        try:
            resolved(there)
        except OSError:
            return value
        if ("resolved", str(Path(there))) not in _HELD:
            return value
    _HELD[key] = value
    return value


#: What a write inside :func:`one_reading` is refused with.
WRITE_WHILE_READING = ("{what} may not be written inside a read-only reply (P118): the reply holds "
                       "its answers, and a write would leave them stale")
#: What a settings write inside :func:`one_household` is refused with.
WRITE_WHILE_HOLDING = ("{what} may not be written while a pass holds a household's answers (P207): "
                       "it would write back the copy read when the household began")


def refuse_a_write_while_reading(what: str) -> None:
    """Raise when a write is asked for inside :func:`one_reading` (the
    review of P118, SHOULD-3): a read-only command writes nothing, and a
    write under held answers would leave the rest of the reply answering
    from before it. The settings file and the store's recorded events ask
    it; the store's own catch-up from a journal is derivation, not a
    write of anything new, and does not. Inside :func:`one_household` the
    pass writes, and nothing is refused."""
    if _HELD is not None and _HOLDING == HOLD_READING:
        raise RuntimeError(WRITE_WHILE_READING.format(what=what))


def resolved(path: Path | str) -> Path:
    """``Path(path).resolve()``, asked once per spelling inside
    :func:`one_reading` (P118) - the store's key for every return is its
    folder resolved, asked on every store read - and every time outside
    one. Inside :func:`one_household` an answer is held only when what it
    names is there (P207): a folder the pass makes later is resolved again,
    because a path resolves differently once it exists (Windows gives the
    folder's own case, a link is followed). An ``OSError`` is raised as
    ``resolve`` raises it, and not held."""
    folder = Path(path)
    key = ("resolved", str(folder))
    if _HELD is not None and key in _HELD:
        return _HELD[key]
    answer = folder.resolve()
    if _HELD is not None and (_HOLDING == HOLD_READING or os.path.lexists(answer)):
        _HELD[key] = answer
    return answer
