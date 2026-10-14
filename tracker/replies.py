"""The shape of every reply the API prints, written down once (SPEC-architecture 5.1 (6)).

**Why it exists.** The engine and the screen meet at one JSON line per
command, and until now that line's shape lived only in the code that built
it and the code that read it. This module is the one written contract
between them: the harness's stub, the recorded replies (``tests/golden/``)
and the JavaScript are held to it. ``tests/test_replies.py`` holds each
recording's top-level keys to its type here, holds the one envelope
:func:`tracker.progress.failure_reply` builds to :class:`Envelope` and
:class:`Failure`, and holds every failure kind the screen names to
:data:`tracker.progress.FAILURE_KINDS`.

**Why ``TypedDict`` and not dataclasses.** A reply is a JSON object the
screen reads by key. A ``TypedDict`` is that dictionary with its keys
written down: nothing is converted on the way out, ``json.dumps`` prints it
as it is, and a key that only some replies carry is ``NotRequired``. A
dataclass would be a second shape beside the dictionary, with a conversion
between them that could itself drift.

**What the types describe: ``api.main``'s output.** ``main`` adds
``warnings`` after the handler returns (decision 193), so every success
reply here has ``warnings: list[str]``, and the screen reads exactly what is
written here. The ``_cmd_*`` handlers keep ``-> dict``: no handler returns
``warnings``, and typing the handlers with a body type each is the thin
door's work (SPEC-architecture 5.1 (5), phase 5), not a move's. The value
types are as precise as the recordings and the code that builds them show;
a nested shape is ``dict`` or ``list`` unless a type here already names it.

**No ``from __future__ import annotations``**, unlike its neighbours. A
``TypedDict``'s required and optional keys are worked out when the class is
made, from the annotations as they are then; written as strings,
``NotRequired[...]`` is not seen, every key reads as required, and the keys
check in ``tests/test_replies.py`` would hold the recordings to the wrong
set. The floor (Python 3.11) writes every annotation here without it.

It imports ``typing`` and nothing else, so it sits at layer 0 and anything
may name it; ``api`` imports :class:`Envelope` and :class:`Failure`, and the
suite imports the rest.
"""

from typing import NotRequired, TypedDict


class Failure(TypedDict):
    """What went wrong, once (decision 193): the sentence the person reads,
    its kind (one of :data:`tracker.progress.FAILURE_KINDS`) and the row it
    was about. ``lock`` is there on a ``locked`` failure - the lock it met,
    or ``None`` when that could not be read - and ``key`` on the firm page's
    one refusal without Retry (``api.FIRM_PAGE_REFUSED_KEY``, P278)."""

    sentence: str
    kind: str
    seq: int | None
    identifier: str | None
    lock: NotRequired[dict | None]
    key: NotRequired[str]


class Envelope(TypedDict):
    """The one error envelope (decision 193): ``error`` is the failure's
    sentence again, and ``warnings`` is always a list."""

    error: str
    failure: Failure
    warnings: list[str]


class StateReply(TypedDict):
    """``state``: everything the app draws one return from (decision 194).

    Every write that redraws the return carries the same dict as its
    ``state`` (``api._state`` builds both). There ``warnings`` is the
    editor's rule warnings; on the ``state`` command itself ``main`` writes
    the envelope's over it."""

    view: dict
    engagement: dict
    lock: dict | None
    summary: dict
    items: list[dict]
    rules: list[dict]
    list_head: str
    learned: dict[str, list[str]]
    warnings: list[str]
    room: dict
    room_note: str
    index: list[dict]
    review: list[dict]
    moved: list[dict]
    reminder: dict
    reminder_card: dict
    household: dict
    paths: dict[str, str]
    carries_code: list[str]


class ListReply(TypedDict):
    """``list``: every household, return and left-alone folder under the
    root, and the app's vocabulary. ``root_problem`` is there when the saved
    root is refused or could not be walked."""

    engagements: list[dict]
    households: list[dict]
    misfits: list[dict]
    reader_warning: str
    last_pass: dict
    paths: dict[str, str]
    machine_warnings: list[str]
    after_install: dict | None
    needs_root: bool
    root: str
    root_problem: NotRequired[str]
    vocab: dict
    warnings: list[str]


class FirmReply(TypedDict):
    """``firm``: the firm view. Asked for no page it is the whole view
    (``returns`` and ``files``); asked for one (P278) it is that page
    (``view``, ``return_counts``, ``page`` and, for Needs Review,
    ``files_found``). Both carry the totals, the paths and the next sort."""

    returns: NotRequired[list[dict]]
    files: NotRequired[list[dict]]
    totals: dict
    paths: dict[str, str]
    next_sort: str | None
    view: NotRequired[str | None]
    return_counts: NotRequired[list[dict]]
    page: NotRequired[dict]
    files_found: NotRequired[list[dict]]
    warnings: list[str]


class FirmLastReply(TypedDict):
    """``firm-last``: the Overview's last counts at launch (P229). ``last``
    is ``None`` when there is nothing to answer, and then nothing else is
    there; otherwise it is ``True``, with ``as_of`` and the keys of a
    :class:`FirmReply`."""

    last: bool | None
    as_of: NotRequired[str]
    returns: NotRequired[list[dict]]
    files: NotRequired[list[dict]]
    totals: NotRequired[dict]
    paths: NotRequired[dict[str, str]]
    next_sort: NotRequired[str | None]
    view: NotRequired[str | None]
    return_counts: NotRequired[list[dict]]
    page: NotRequired[dict]
    files_found: NotRequired[list[dict]]
    warnings: list[str]


class ReminderReply(TypedDict):
    """``reminder``: the week's draft at a stage. ``reminder`` is ``None``,
    with ``not_yet``, for a return nobody has scanned yet."""

    reminder: dict | None
    not_yet: NotRequired[str]
    warnings: list[str]


class EditReply(TypedDict):
    """``edit``: what the save changed, and the return redrawn. ``list`` is
    there when the save changed whether the return is active."""

    saved: dict
    state: StateReply
    list: NotRequired[dict]
    warnings: list[str]


class EditHouseholdReply(TypedDict):
    """``edit-household``: the household fields saved, and the return
    redrawn; ``list`` when the root could be walked."""

    saved: dict
    state: StateReply
    list: NotRequired[dict]
    warnings: list[str]


class CreateReply(TypedDict):
    """``create``: the new return, drawn. ``checklist`` comes with a
    household's first return only (decision 126), and ``list`` when the root
    could be walked."""

    created: str
    state: StateReply
    link_dropped: str
    checklist: NotRequired[dict]
    list: NotRequired[dict]
    warnings: list[str]


class AssignReply(TypedDict):
    """``assign``: a parked document filed under a request (``assigned``), or
    handed to a return this drop folder feeds (``handed_over``) - one or the
    other - and the return redrawn."""

    assigned: NotRequired[dict]
    handed_over: NotRequired[dict]
    state: StateReply
    warnings: list[str]
