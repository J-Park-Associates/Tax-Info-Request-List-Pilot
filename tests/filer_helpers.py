"""What the filer's family of test files shares, in one place.

``tests/test_filer.py`` wrote these for itself. With P331
(SPEC-architecture-p4 P4.4) the tests that drive only the code that moved to
``tracker/copies.py`` - a working copy's name, the room a return has, the
byte-proved copy, the rename-only move and the stranded-temp sweep - left it
for ``tests/test_copies.py``, each still reading the helpers it was written
against. A test file may not import another (``tests/test_suite_shape.py``),
so what both files read sits here, in a module that is not a test file, and
each names it; the map draws the edge as "exercised by". Each later move out
of the filer (SPEC-architecture-p4 section 4.1) adds here what its split
shares.

From ``tests/test_filer.py``, with their words: :func:`originals` (the
client's folder for a return's year), :class:`RequestFiles` and
:func:`prepared` (a request's files in Prepared, and the review folder),
:func:`review_dir`, :func:`_catalog_w2` (the 1040 catalog's A01, decision
144), and the fabricated client path a refused read names
(:data:`A_CLIENT_PATH`, :func:`_refused_with_a_client_path`) with
:func:`_logged_outside_the_debug_log`, which reads what was logged outside
the debug log (decision 190). Nothing here is new behaviour.

With P332 (SPEC-architecture-p4 P4.6) the tests that drive only the code
that moved to ``tracker/intents.py`` - the write-ahead intents, the places a
step may touch and finishing an interrupted move - left for
``tests/test_intents.py``, and :func:`_forge_line` came here from
``tests/test_filer.py`` with its words: it puts one line in the journal past
the store, as another machine would, and a forged step's tests there and an
old intent's finish in the filer's tests both write with it.

With P333 (SPEC-architecture-p4 P4.7) the tests that drive only the code
that moved to ``tracker/inbox.py`` - the walk, the folders it cannot list
and the folder of originals the household's returns share - left for
``tests/test_inbox.py``, and the :func:`two_returns` fixture came here from
``tests/test_filer.py`` with its words: one household with two returns of
the open year, which the shared folder's test there and the household's
tests in the filer's file both take.

With P334 (SPEC-architecture-p4 P4.8) the tests that drive only the code
that moved to ``tracker/readme_ack.py`` - the client README's received list
and its refresh - left for ``tests/test_readme_ack.py``, and seven helpers
came here from ``tests/test_filer.py`` with their words, because tests in
both files read them: :data:`DAY3` (the day a pass recovers what a run left
half done, decision 119), :func:`events_named` (every journal line of one
event name), :func:`open_intents` (the moves begun and not finished),
:func:`_status` (one request's row in the list), :data:`MORTGAGE` (the
1098's text), :func:`_filed_1098` (C01's one document, sorted and scanned
the ordinary way) and :func:`_a_pass` (the pass as the runner makes it).

With P335 (SPEC-architecture-p4 P4.9) the tests that drive the code that
moved to ``tracker/actions.py`` - a person's filing, setting aside,
unfiling, Mark missing, put-back and rename - left for
``tests/test_actions.py``, and twenty-one helpers came here from
``tests/test_filer.py`` with their words, because tests in both files read
them: :func:`kept_files` (every original and working copy, by place),
:func:`counted_records` (every ``store.record`` call), :func:`seq_of` (the
sequence number a person's action carries, decision 112), the conservation
checks :func:`_everything`, :func:`files_under`, :func:`digests_under` and
:func:`conserved`, :func:`drag` (a person dragging a file in Explorer),
:func:`counting_hashes` (every path the package hashes), the crash points'
:func:`moves_made`, :func:`killed_after_ops`, :func:`killed_after_the_move`
and :func:`killed_at_the_intent` (decision 119), :data:`JOHN` (the
taxpayer and his spellings, decision 128), the :func:`fed` fixture and
:func:`click` (a household feeding another's return, and the one click that
hands a document over, decisions 129, 132 and 204), :func:`parked_notice`
and :func:`rows_rest_at_home` (the row a hand-over acts on, and claim 27's
invariant), :func:`_only_the_review_folder` (decision 168), :func:`_asked`
(what the letter asks for, decision 157) and :func:`_review_folder_files`
(decision 190).

**The two fixtures here are named, not imported.** ``two_returns`` and
``fed`` are fixtures, and a test file that wants one names it once by
assignment (``two_returns = filer_helpers.two_returns``), as
``tests/store_helpers.py``'s are named: a fixture imported by name and then
taken as a parameter trips ruff's F811 at every such test. The other
fixture both files take, ``engagement``, is ``tests.builders``'
``engagement_fixture(ITEMS)``, named once in each file.
"""

import datetime as dt
from dataclasses import replace
from pathlib import Path

import pytest

from tests.builders import BUSINESS, DAY1, DAY2, FATHER, ITEMS, LLC_PEOPLE, drop, feeding, make_engagement, sort
from tracker import ledger, store, store_check
from tracker.index import read_index
from tracker.layout import inbox_of, locate, location_of, originals_of
from tracker.manifest import load_manifest
from tracker.names import propose_spellings
from tracker.records import Person
from tracker.scaffold import (
    PREPARED_DIR_NAME,
    REVIEW_DIR_NAME,
)


def originals(engagement):
    """The folder the client sees for this return's year: where an original
    rests once the pass has moved it out of the inbox (decision 125)."""
    return originals_of(engagement)


class RequestFiles:
    """What one request's folder was, flat (decision 168): its working copies
    sit in Prepared itself, and a file is the request's when its name begins
    with the identifier (``tracker.scaffold.assign_files``). So ``/ name``
    is where a file named for the request goes - ``Prepared/A01 - name``,
    or ``Prepared/<name>`` for a name that already begins with it - and
    ``iterdir()`` is the request's files. Dragging a copy "into C01" is
    renaming it under C01's name beside the others, which is the only way a
    person can move a copy between requests now."""

    def __init__(self, root: Path, identifier: str):
        self.root, self.identifier = root, identifier

    def __truediv__(self, name: str) -> Path:
        from tracker.scaffold import matches_identifier

        if matches_identifier(name, self.identifier):
            return self.root / name
        return self.root / f"{self.identifier} - {name}"

    def iterdir(self):
        from tracker.scaffold import assign_files

        return iter(assign_files(self.root, [self.identifier])[self.identifier])

    def mkdir(self, **_kwargs) -> None:
        self.root.mkdir(parents=True, exist_ok=True)


def prepared(engagement, folder_prefix):
    """The review folder itself, or one request's files as a
    :class:`RequestFiles` - there is no folder per request (decision 168)."""
    root = engagement / PREPARED_DIR_NAME
    if folder_prefix == REVIEW_DIR_NAME:
        return root / REVIEW_DIR_NAME
    return RequestFiles(root, folder_prefix.split(" ")[0])


def review_dir(engagement):
    return engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME


def _catalog_w2(**changes):
    """The 1040 catalog's A01, as a return created today would have it."""
    from tracker.templates import template_items

    return replace(template_items("1040", year=2025)[0], **changes)


#: A fabricated OS error's path, shaped like a client's inbox (decision 190).
A_CLIENT_PATH = "/Clients/Test Household/Drop files here/W2.pdf"


def _refused_with_a_client_path(*_args, **_kwargs):
    import errno

    raise PermissionError(errno.EACCES, "Permission denied", A_CLIENT_PATH)


def _logged_outside_the_debug_log(caplog) -> str:
    """Every line logged, but the debug log's, where the words are kept on
    purpose (tracker.errors.keep)."""
    from tracker.errors import DEBUG_LOGGER

    return "\n".join(record.getMessage() for record in caplog.records if record.name != DEBUG_LOGGER)


def _forge_line(engagement, event: dict) -> bytes:
    """Put one line in the journal past the store, as another machine
    would; returns the journal as it was. Linked to the line before
    (decision 159), so it is the store's admission and the filer's own
    checks that judge it, not the ledger's link."""
    from tests.builders import written_elsewhere

    honest = ledger.path_for(engagement).read_bytes()
    written_elsewhere(engagement, event)
    return honest


@pytest.fixture
def two_returns(tmp_path):
    """One household with two returns of the open year: a 1040 and an 1120S."""
    personal = make_engagement(tmp_path, ITEMS, household="Park Family",
                               return_name="1040 - John Park")
    business = make_engagement(tmp_path, BUSINESS, household="Park Family",
                               return_name="1120S - Park Landscaping")
    return personal, business


#: The day a pass recovers what a run left half done (decision 119): the
#: row it records is still dated the day the decision was made.
DAY3 = dt.date(2026, 7, 15)


def events_named(engagement, name):
    """Every journal line of one event name."""
    return [e for e in ledger.read_events(engagement) if e[ledger.EVENT_KEY] == name]


def open_intents(engagement):
    """The moves this engagement has begun and not finished."""
    return store.open_intents(store.connect(), engagement)


def _status(engagement, identifier):
    return next(i for i in load_manifest(engagement) if i.identifier == identifier)


MORTGAGE = "Form 1098 Mortgage Interest Statement 2025"


def _filed_1098(engagement, name="1098.pdf"):
    """C01's one document, sorted and scanned the ordinary way: Received."""
    from tracker.manifest import Status
    from tracker.scanner import scan_engagement

    drop(engagement, name, MORTGAGE)
    [filed] = sort(engagement, today=DAY1).filed
    scan_engagement(engagement, today=DAY1)
    assert filed.identifier == "C01" and _status(engagement, "C01").status == Status.RECEIVED
    return filed


def _a_pass(engagement, today):
    """The pass as the runner makes it: the sort, whose sweep proves every
    copy first, and then the scan."""
    from tracker.scanner import scan_engagement

    report = sort(engagement, today=today)
    return report, scan_engagement(engagement, today=today)


def kept_files(engagement):
    """Every preserved original and every working copy, by relative path.

    The conservation check: what is under the engagement is the arrivals
    plus the copies a rule made, and nothing else. ``files_under()`` below
    is the whole folder with each file's bytes and time, for the claims
    about a pass that must change nothing; this one names the two folders a
    rule writes in, which is what a claim about copies wants to say.
    """
    roots = (originals(engagement), engagement / PREPARED_DIR_NAME)
    return sorted(location_of(engagement, path)
                  for root in roots for path in root.rglob("*") if path.is_file())


def counted_records(monkeypatch) -> list[tuple]:
    """Every call to ``store.record``, with the events it was given.

    The pass's own import of the request list is left out: it is one call
    of its own at the start (decision 103), and what these tests are
    about is the decisions about documents.
    """
    calls: list[tuple] = []
    real = store.record

    def counting(conn, engagement_dir, *events):
        named = tuple(e[ledger.EVENT_KEY] for e in events)
        if named != (ledger.RULES_IMPORTED,):
            calls.append(named)
        return real(conn, engagement_dir, *events)

    monkeypatch.setattr(store, "record", counting)
    return calls


def seq_of(engagement, entry):
    """One index row's sequence number - the journal line that last wrote it.

    What the API ships beside the row and what a person's action carries
    back, read here the way the API reads it.
    """
    from tracker.records import ledger_key

    return store.document_seqs(store.connect(), engagement)[ledger_key(entry)]


def _everything(engagement):
    """Every file this return and its household's client side hold, in one
    list: the return folder, the household's inbox and the year's folder of
    originals. Since decision 125 an original lives in the other tree, so a
    conservation check over the return folder alone would not see one."""
    roots = (engagement, inbox_of(engagement), originals_of(engagement))
    return sorted(path for root in roots for path in root.rglob("*")
                  if path.is_file() and path.name != ledger.LEDGER_FILENAME)


def files_under(engagement):
    """Every file the return and its client side hold, with its bytes and
    its mtime.

    The record aside, which a pass is meant to write. Every claim below that
    moves a file by hand takes this before the pass and after it: the sweep
    identifies by fingerprint and a person decides, so nothing under the
    client's root may move, change or appear because of what it found.
    """
    return {
        location_of(engagement, path): (path.read_bytes(), path.stat().st_mtime_ns)
        for path in _everything(engagement)
    }


def drag(path, folder):
    """A person dragging one file in Explorer, and where it lands."""
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / path.name
    path.rename(target)
    return target


def counting_hashes(monkeypatch) -> list[str]:
    """Every path anything in the package hashes, as it is hashed.

    Eight modules hold the name now, and each holds its own: the memo's is
    the content check's, and a pass that reached around it would show up
    here and nowhere else. The scanner held one until decision 109 and
    holds none; the index's is the one ``holds_the_row`` reads, since that
    proof moved out of the filer (P319), copies' is the one a working
    copy is found and proved with, since that code did (P331),
    intents' is the one an intent and its recovery prove a step with,
    since that code did (P332), inbox's is the one the walk checks a
    replaced or moved original with, since that code did (P333), and
    actions' is the one a person's action proves the bytes it is about to
    move with, since that code did (P335).
    """
    import tracker.actions as actions_module
    import tracker.content_check as content_check_module
    import tracker.copies as copies_module
    import tracker.filer as filer_module
    import tracker.inbox as inbox_module
    import tracker.index as index_module
    import tracker.intents as intents_module
    import tracker.validators as validators_module

    read: list[str] = []
    for module in (filer_module, copies_module, intents_module, inbox_module, content_check_module, index_module,
                   validators_module, actions_module):
        real = module.sha256_of

        def counted(path, _real=real):
            read.append(str(path))
            return _real(path)

        monkeypatch.setattr(module, "sha256_of", counted)
    return read


def digests_under(engagement):
    """Every file the return and its client side hold, by location, with
    its bytes' digest.

    The record aside, which a pass is meant to write. What the three
    conservation checks below are made of.
    """
    from tracker.validators import sha256_of

    return {location_of(engagement, path): sha256_of(path)
            for path in _everything(engagement)}


def conserved(engagement, before, moves, *, added=(), gone=()):
    """The three conservation checks every crash claim below ends with.

    (a) every document that was under the engagement is still under it,
    with exactly the copies the decision meant to make added and the
    stand-downs it recorded gone; (b) nothing that was already there had
    its bytes changed - a recovery never overwrites and never deletes what
    it finds; (c) no intended move was made twice, across the crash and
    the recovery together. And the store agrees with the record with no
    move left open, which is the fixture's question asked here too, where
    its answer is about a folder a run died in the middle of.
    """
    from collections import Counter

    after = digests_under(engagement)
    for path, digest in before.items():
        assert after.get(path, digest) == digest, f"{path}: the bytes changed"
    assert Counter(after.values()) == Counter(before.values()) + Counter(added) - Counter(gone)
    assert len(moves) == len(set(moves)), moves
    assert store_check.check(store.connect(), engagement.parent, engagement) == []
    assert open_intents(engagement) == []


def moves_made(monkeypatch) -> list[tuple[str, str]]:
    """Every rename the filer makes, as it makes it: the check that a move
    the crash made is not made again by the recovery."""
    import tracker.actions as actions_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module

    real = filer_module._move_whole
    made: list[tuple[str, str]] = []

    def counted(source, target, *, within):
        made.append((str(source), str(target)))
        return real(source, target, within=within)

    for module in (filer_module, intents_module, actions_module):
        monkeypatch.setattr(module, "_move_whole", counted)
    return made


def killed_after_ops(monkeypatch, after=1):
    """The machine dies once ``after`` file operations of one decision have
    been made and before the row that explains them is recorded.

    The only faithful place to inject it: a rollback cannot run on a power
    cut, so the kill goes where no ``except`` of the caller's can catch it,
    between the work and the record. Once only, so the pass that recovers
    runs for real.
    """
    import tracker.actions as actions_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module

    real = filer_module._do_op
    state = {"made": 0, "died": False}

    def dying(engagement_dir, op, *, cache=None):
        real(engagement_dir, op, cache=cache)
        state["made"] += 1
        if not state["died"] and state["made"] >= after:
            state["died"] = True
            raise KeyboardInterrupt

    for module in (filer_module, intents_module, actions_module):
        monkeypatch.setattr(module, "_do_op", dying)
    return state


def killed_after_the_move(monkeypatch):
    """The machine dies once the drop has been moved out of the inbox and
    before anything else: the one move no intent covers since decision 125."""
    import tracker.actions as actions_module
    import tracker.filer as filer_module
    import tracker.intents as intents_module

    real = filer_module._move_whole
    state = {"died": False}

    def dying(source, target, *, within):
        real(source, target, within=within)
        if not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt

    for module in (filer_module, intents_module, actions_module):
        monkeypatch.setattr(module, "_move_whole", dying)
    return state


def killed_at_the_intent(monkeypatch, kind=None):
    """The machine dies with an intent on the record and not one step of
    what it stands for done. ``kind`` picks which intent."""
    real = store.record
    state = {"died": False}

    def killing(conn, engagement_dir, *events):
        result = real(conn, engagement_dir, *events)
        this_one = events[0][ledger.EVENT_KEY] == ledger.MOVING and (
            kind is None
            or any(op[ledger.OP_KEY] == kind for op in events[0][ledger.OPS_KEY]))
        if this_one and not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt
        return result

    monkeypatch.setattr(store, "record", killing)
    return state


JOHN = Person("taxpayer", "John Park", propose_spellings("John Park", "taxpayer"))


@pytest.fixture
def fed(tmp_path):
    """The plan's example: a father's household with his own 1040, the
    co-owned LLC in a household of its own, and the father's drop folder
    feeding the LLC's return line."""
    from tracker.records import Feed

    father = make_engagement(tmp_path, ITEMS, household="Park Family",
                             return_name="1040 - John Park", people=FATHER)
    llc = make_engagement(tmp_path, BUSINESS, household="Park & Lee LLC",
                          return_name="1120S - Park & Lee LLC", people=LLC_PEOPLE)
    feeding(tmp_path, [Feed("Park & Lee LLC", "1120S - Park & Lee LLC")])
    return father, llc


def click(home, row, target, *, today=DAY2, seq=None):
    """The one click (decision 204), as the API makes it: the row's own
    Waits For claim handed to the return it names, nothing picked."""
    from tracker.filer import hand_over

    claim = row.waiting_for
    return hand_over(home, row.pbc_location, target, claim.identifiers[0],
                     also=claim.identifiers[1:], answers=claim.answers, waiting=True,
                     seq=seq, today=today)


def parked_notice(father):
    """One document nothing asks for, waiting for a person in the father's
    own return - the row a hand-over acts on."""
    drop(father, "notice.pdf", "an agency notice nothing asks for")
    return sort(father, returns=[father], today=DAY1).review[0]


def rows_rest_at_home(*returns):
    """Claim 27's invariant (decision 132), asked of every record named:
    once no intent is open, every row a record holds names an original
    under **that record's own** household-year folder. A row about a
    document resting under another household is the one thing the owner's
    sentence rules out."""
    for engagement in returns:
        assert open_intents(engagement) == [], engagement.name
        home = originals_of(engagement)
        for row in read_index(engagement):
            assert locate(engagement, row.pbc_location).parent == home, (engagement.name, row)


def _only_the_review_folder(engagement) -> None:
    """No folder per request (decision 168): the one folder inside Prepared
    is the review folder."""
    folders = [p.name for p in (engagement / PREPARED_DIR_NAME).iterdir() if p.is_dir()]
    assert folders == [REVIEW_DIR_NAME], folders


def _asked(engagement, today):
    from tracker.reminder import draft_reminder

    return set(draft_reminder(engagement, today=today).asked)


def _review_folder_files(engagement):
    review = engagement / PREPARED_DIR_NAME / REVIEW_DIR_NAME
    return sorted(p.name for p in review.iterdir()) if review.exists() else []
