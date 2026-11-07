"""What the suite builds, in one place: a return, a document dropped into its inbox, the rows a pass records.

Test files used to borrow these from one another (``test_runner`` imported
``drop`` from ``test_filer``, ``test_reminder`` imported ``parked_row`` from
``test_review``). The affected-tests gate
cannot see that edge, and splitting the owner's file breaks every borrower
(SPEC-architecture E-4, R2.1). Here they sit in a module that is not a test
file, so every user names it and the map draws the edge as "exercised by".

Nothing here is new behaviour: each helper is the one a test file already had,
moved with its words. Where several files wrote the same helper out (``drop``,
``cache_rows``, ``original_at``, ``link_to``, the ``engagement`` fixture) they
now share one. The filer's scenes at the end are the made-up households and
returns that more than one file stages (a household with a business, a return
with no room for a name, a consolidated brokerage statement).

The builders that were in ``tests/conftest.py`` came here with P4.2 (SPEC-architecture E-6), so that no
helper module imports a conftest: making an engagement, sorting an inbox, seeding an index and a status, and the
``TEST_*`` names they share. What conftest said of them moved with them:

**Making an engagement** (``make_engagement``) **is one call**: the
household's record where its folder has none, the return folder under its
year, the list and the details recorded through ``create_engagement()`` -
the same calls the API makes - and the scaffold on top when asked. It
takes the **clients root**, not a folder, because since decision 125 where
a return goes is the layout's answer and not a test's: a household, a
year, a return. Two returns in one household is the same call twice with
the same ``household``.

**Sorting one household's inbox** (``sort``) is the pass's own call
(``file_household_drops``) under the locks the pass holds, over whichever
returns the test names. One return is the ordinary case and reads as one
line.

**Seeding an index** (``seed_index``) **and a status**
(``seed_statuses``). A test that needs rows or statuses to exist records
them, because recording them is the only way they can exist: the helpers
append ``imported`` and ``scanned`` events under the engagement lock
through the store, which is the same call every writer in the package
makes.
"""

import datetime as dt
import hashlib
import io
import json
import sys
from contextlib import ExitStack
from dataclasses import replace
from pathlib import Path

import pytest

from tests.samples import text_pdf, write_pdf
from tracker import ledger, reasons, store
from tracker.content_check import extract_text
from tracker.filer import file_household_drops
from tracker.households import create_household
from tracker.index import NEEDS_REVIEW, ensure
from tracker.layout import inbox_of, location_of, lock_order_key, originals_of, private_household_dir, return_dir_for
from tracker.locking import engagement_lock
from tracker.manifest import EngagementInfo, RequestItem, Status, create_engagement
from tracker.names import propose_spellings
from tracker.readme_ack import refresh_household_readme
from tracker.reasons import Reason
from tracker.records import (
    CANDIDATE_SEP,
    HouseholdInfo,
    IndexEntry,
    Person,
    entry_to_json,
    format_evidence,
    ledger_key,
    status_to_json,
)
from tracker.registry import _walk_root
from tracker.router import AMBIGUOUS, UNMATCHED
from tracker.scaffold import scaffold_engagement

#: What a test's household and return are called when it does not care.
TEST_HOUSEHOLD = "Test Household"
TEST_RETURN = "1040 - Test Client"
TEST_YEAR = 2025
#: Who a test's return is for when it does not care (decision 128). Every
#: named request files only where one of this person's spellings is on the
#: page, so the suite's documents carry this name - ``named_page()`` puts
#: it there - exactly as a real W-2 carries its employee's.
TEST_CLIENT = "Test Client"
TEST_PEOPLE = (Person("taxpayer", TEST_CLIENT, propose_spellings(TEST_CLIENT, "taxpayer")),)

#: The code page Python reads a pipe in on the firm's Windows machine,
#: whatever the machine running the suite uses.
WINDOWS_PIPE_ENCODING = "cp1252"

def app_stdin(spec) -> io.TextIOWrapper:
    """``spec`` as the tracker's stdin sees it when the app sends it (decision
    176): the UTF-8 bytes ``JSON.stringify`` and Node's pipe produce, under a
    text stream in Windows' ANSI code page. A command that reads the text
    rather than the bytes turns ``Muñoz`` into ``MuÃ±oz`` here as it would
    at the office, so every API claim in the suite is made through the
    reading the office gets.
    """
    raw = json.dumps(spec, ensure_ascii=False).encode("utf-8")
    return io.TextIOWrapper(io.BytesIO(raw), encoding=WINDOWS_PIPE_ENCODING)

def named_page(text: str, who: str = TEST_CLIENT) -> str:
    """``text`` as a page addressed to somebody - the document's words with
    the name on it, which is what a real named document has.

    Every helper that drops a document into an inbox goes through this, so
    the suite's pages are pages the name tier can confirm (decision 128)
    and a test that means "a page naming nobody" says so by not using it.
    """
    return f"{text}\n{who}" if text else who

def make_engagement(root, items, info: EngagementInfo | None = None, *,
                    household: str = TEST_HOUSEHOLD, year: int = TEST_YEAR,
                    return_name: str = TEST_RETURN,
                    people: tuple[Person, ...] | None = None,
                    members: tuple[str, ...] = (), contact: str = "", link: str = "",
                    form: str = "", scaffold: bool = True) -> Path:
    """The one way a test makes a return: its household's record where the
    household has none, the return folder under its year, its record and,
    unless told not to, its scaffold. Returns the **return folder**.

    ``create_household()`` and ``create_engagement()`` are the API's own
    creates, so what a test seeds is exactly what the app would have made:
    one ``household_changed`` event carrying the whole household, one
    ``rules_changed`` event carrying the whole list and the details,
    validated on the way in. The scaffold is the folders the filer and the
    scanner need, and the README the app writes after them (decision 130);
    a test that wants only the record says ``scaffold=False``.

    A test that wants two returns in one household calls this twice with
    the same ``household`` - the second finds the household's record
    already there and leaves it alone.
    """
    root = Path(root)
    household_dir = private_household_dir(root, household)
    household_dir.mkdir(parents=True, exist_ok=True)
    if not ledger.path_for(household_dir).is_file():
        create_household(household_dir, HouseholdInfo(
            name=household, members=tuple(members), contact=contact, link=link))
    folder = return_dir_for(root, household, year, return_name)
    folder.mkdir(parents=True, exist_ok=True)
    details = info or EngagementInfo()
    # Who the return is for (decision 128). ``people=()`` is a test saying
    # "nobody is listed yet", which is a real state and parks every named
    # request; anything else, said or unsaid, is the one test person.
    if people is None:
        people = details.people or TEST_PEOPLE
    create_engagement(folder, list(items),
                      replace(details, household=household, tax_year=year,
                              return_name=return_name, people=tuple(people)),
                      form=form)
    if scaffold:
        # What the app's create does: the folders, then the README from its
        # one composer (decision 130).
        scaffold_engagement(folder)
        refresh_household_readme(household_dir)
    return folder

def root_for_a_return_of(base, length: int, *, household: str = TEST_HOUSEHOLD,
                         year: int = TEST_YEAR, return_name: str = TEST_RETURN) -> Path:
    """A clients root under ``base`` whose return folder is exactly
    ``length`` characters (decision 131).

    The room a return has is arithmetic on the whole path, so a claim about
    it is made at a known length rather than at whatever the machine's
    temporary folder happens to spend: one folder of padding is added under
    ``base`` to reach it. A machine whose ``base`` is already longer than
    the claim can use says so by name and skips.
    """
    base = Path(base)
    below = len(str(return_dir_for(Path("r"), household, year, return_name))) - 1
    pad = length - below - len(str(base)) - 1
    if pad < 1:
        pytest.skip(f"{base} is too long to make a return folder of {length} characters under it")
    return base / ("r" * pad)

def floor_return() -> int:
    """The longest return folder whose review folder still has room for a
    review copy: its floor, ``Prepared/00 - Needs Review/x (99).pdf``, is
    exactly the limit - 222 characters at 260. With long paths off it is
    206: the review folder is measured as Windows measures a folder the
    tracker makes and writes into, its temp names included
    (``layout.folder_need``, pilot decision P29)."""
    from tracker.layout import PREPARED_DIR_NAME, REVIEW_DIR_NAME, folder_need, path_limit

    review = len(f"/{PREPARED_DIR_NAME}/{REVIEW_DIR_NAME}")
    return path_limit() - review - max(len("/x (99).pdf"), folder_need("", ""))

def sort_all(returns, *, home=None, today=None, dry_run: bool = False):
    """One pass of the household's sort over these returns, answering for
    every one of them: the mapping ``file_household_drops`` returns.

    One inbox feeds them all (decision 125), so one call is the whole
    sort - a second would find nothing left to do. The first return's
    household is the one whose inbox is sorted; ``home`` names that
    household's **own** returns when the list also holds returns it feeds
    (decision 129) - handed down as the two lists the sort takes since
    decision 132, own and fed, in the order they are listed here - and
    the locks are taken in the one global order, as the pass takes them.
    """
    folders = [Path(one) for one in returns]
    own = folders if home is None else [one for one in folders if one in set(map(Path, home))]
    with ExitStack() as locks:
        if not dry_run:
            for folder in sorted(folders, key=lock_order_key):
                locks.enter_context(engagement_lock(folder))
        return file_household_drops(
            inbox_of(folders[0]), originals_of(folders[0]),
            own=own, fed=[one for one in folders if one not in own],
            today=today, dry_run=dry_run,
        )

def sort(engagement, *, returns=None, home=None, today=None, dry_run: bool = False):
    """Sort one household's inbox the way a pass does, and answer for
    ``engagement``.

    The pass takes every open return's lock before anything is read
    (decision 125), so this does too; ``returns`` names the household's
    returns when a test has more than one, and one return is the ordinary
    case. A dry run takes no lock, as the pass takes none.
    """
    engagement = Path(engagement)
    folders = returns if returns is not None else [engagement]
    return sort_all(folders, home=home, today=today, dry_run=dry_run)[engagement]

def seed_index(engagement_dir, entries):
    """Put ``entries`` in the engagement's record, the way a pass would.

    The one way a test seeds an index. There is no workbook to write any
    more, so a test that wants rows to exist records them: ``imported``
    events, under the engagement lock, through the store - the same call
    every writer in the package makes, so a seeded engagement is
    indistinguishable from one a pass left behind. Returns the entries, so
    a test can seed and keep them in one line.
    """
    engagement_dir = Path(engagement_dir)
    entries = list(entries)
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        store.record(store.connect(), engagement_dir, *[
            ledger.new(ledger.IMPORTED, **{ledger.KEY_KEY: ledger_key(entry),
                                           ledger.ROW_KEY: entry_to_json(entry)})
            for entry in entries
        ])
    return entries

def written_elsewhere(engagement_dir, event, host="another-machine"):
    """Put one line in a record the way the tracker on another machine
    writes it: linked to the line before, with that machine's host and the
    record's format (decision 159). The one way a test puts a line in a
    record that no writer on this machine would make - a line of the wrong
    shape, a retired name - without it reading as a hand edit."""
    _lines, _head, chain = ledger.read_with_chain(engagement_dir)
    line = {**event, ledger.LINK_KEY: ledger.chain_at(chain, len(chain)), ledger.HOST_KEY: host,
            ledger.FORMAT_KEY: ledger.RECORD_FORMAT}
    ledger._write_raw(ledger.path_for(engagement_dir),
                      json.dumps(line, ensure_ascii=False, sort_keys=True).encode("utf-8"))

def seed_statuses(engagement_dir, updates):
    """Put ``updates`` in the engagement's record, the way a scan would.

    The one way a test seeds a status. There are no scanner columns to
    write any more (decision 103), so a test that wants a row to be
    Received records it: one ``scanned`` event, under the engagement
    lock, through the store - the same call ``tracker.scanner`` makes.
    Returns the updates, so a test can seed and keep them in one line.
    """
    engagement_dir = Path(engagement_dir)
    updates = dict(updates)
    with engagement_lock(engagement_dir):
        ensure(engagement_dir)
        store.record(store.connect(), engagement_dir, ledger.new(
            ledger.SCANNED,
            **{ledger.STATUSES_KEY: {i: status_to_json(u) for i, u in updates.items()}},
        ))
    return updates


def engagement_fixture(items, household=None, *, root="tmp_path"):
    """The ``engagement`` fixture a test file writes when its claims are about
    one return: ``make_engagement(<root>, items[, household=...])``, with the
    request list and the household the file says. ``root`` names the fixture
    the return is made under (``tmp_path``, or a file's own ``root``)::

        engagement = engagement_fixture(ITEMS, household="Smith Family")
    """
    options = {} if household is None else {"household": household}

    @pytest.fixture(name="engagement")
    def engagement(request):
        return make_engagement(request.getfixturevalue(root), items, **options)

    return engagement


def drop(engagement, name, text, who=TEST_CLIENT):
    """Client drops one document into the household's one inbox.

    The page carries the return's person on it (decision 128), the way a
    real W-2 carries its employee's name: a named request files only where
    one of the return's spellings is on the page. A test that means "a
    page naming nobody here" passes ``who=""`` or writes the PDF itself.
    """
    return text_pdf(inbox_of(engagement) / name, named_page(text, who) if who else text)


def original_at(engagement, name):
    """How a row names an original it holds: relative to the return folder,
    POSIX, and across the two trees - so it begins with ``..``."""
    return location_of(engagement, originals_of(engagement) / name)


def cache_rows(engagement):
    """The engagement's verdict cache as the store holds it: (memos, verdicts)."""
    from tracker.content_check import CACHE_VERSION

    return store.cached_verdicts(store.connect(), engagement, version=CACHE_VERSION)


def engagement_dirs(root):
    """Every return folder under ``root`` in the walk's order: the fourth
    level below the root and nothing else, as the registry's own walk
    reads it (``registry._walk_root``)."""
    return _walk_root(Path(root)).returns


def link_to(target, link):
    """A junction on Windows, a symlink elsewhere: a folder that is a link."""
    if sys.platform == "win32":
        import _winapi

        _winapi.CreateJunction(str(target), str(link))
    else:
        link.symlink_to(target, target_is_directory=True)


def item(identifier, document, status, **kwargs):
    """A request with the record's status on it. Notes said with a code -
    :func:`failure`, or a Reason's own sentence - carry that code into
    ``note_codes`` as the scan records it (decision 190); plain text carries
    none, however it reads."""
    notes = kwargs.get("validation_notes", "")
    if "note_codes" not in kwargs and reasons.code_of(notes):
        kwargs["note_codes"] = reasons.code_of(notes)
    return RequestItem(
        identifier=identifier, document=document, status=status, **kwargs
    )


def failure(name, said):
    """One failure as the scanner notes it, ``name.pdf: sentence``, carrying
    the sentence's code (decision 190)."""
    return reasons.Said(f"{name}: {said}", reasons.code_of(said))


#: The rows the drops below are routed against: the same two requests, with
#: the keywords that let a file name point at one of them.
DROPPED = [
    item("A01", "W-2 Wage Statements", Status.MISSING, period="TY2025", expected_count=2,
         required_keywords=("W-2",), min_size_kb=0),
    item("A02", "Bank Statements", Status.PARTIAL, period="TY2025", expected_count=3,
         file_count=2, any_keywords=("bank statement",), min_size_kb=0),
]


def locked(name, *, password="secret123"):
    """A password-protected PDF, the file the client is certain they sent."""
    return lambda shared: write_pdf(shared / name, password=password)


def parked_row(name, record, *, reason=UNMATCHED, decision=NEEDS_REVIEW, candidates=(),
               code=None):
    """One index row as the filer writes it, evidence through its own formatter.

    Its code (decision 190) is the one ``reason`` was said with, as the
    filer takes it, unless the test gives one; the router's two bare
    sentences carry theirs as the router gives them."""
    if code is None:
        code = reasons.code_of(reason) or {
            UNMATCHED: reasons.UNMATCHED_CODE, AMBIGUOUS: reasons.AMBIGUOUS_CODE}.get(reason, "")
    return IndexEntry(
        received="2026-01-01", original_name=name, size_kb=9.4, digest=hashlib.sha256(name.encode()).hexdigest(),
        identifier="", prepared_location="",
        pbc_location=f"../../../../Clients/Smith Family/2025/{name}",
        decision=decision, reason=reason,
        candidates=CANDIDATE_SEP.join(candidates),
        evidence=format_evidence(record),
        code=code,
    )


K1_WORDS = ("partner's share of income", "member's share of income")


def k1_rows(*issuers):
    """The generic K-1 row and one row per (identifier, entity) after it."""
    rows = [RequestItem(identifier="F01", document="Schedule K-1s Received",
                        allowed_extensions=("pdf",), any_keywords=K1_WORDS)]
    rows += [RequestItem(identifier=identifier, document=f"Schedule K-1 - {entity}",
                         allowed_extensions=("pdf",), required_keywords=(entity,),
                         any_keywords=K1_WORDS)
             for identifier, entity in issuers]
    return rows


def counting_extractor(monkeypatch):
    calls = {"n": 0}
    real = extract_text

    def wrapped(path):
        calls["n"] += 1
        return real(path)

    monkeypatch.setattr("tracker.content_check.extract_text", wrapped)
    return calls


def killed_at_the_record(monkeypatch):
    """The machine dies as the rows of a decision are recorded: the files
    have moved, the intent is open, the index says nothing yet."""
    real = store.record
    state = {"died": False}

    def killing(conn, engagement_dir, *events):
        if events[0][ledger.EVENT_KEY] != ledger.MOVING and not state["died"]:
            state["died"] = True
            raise KeyboardInterrupt
        return real(conn, engagement_dir, *events)

    monkeypatch.setattr(store, "record", killing)
    return state


# ------------------------------------------------ the filer's scenes ----

DAY1 = dt.date(2026, 7, 1)
DAY2 = dt.date(2026, 7, 9)

ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        expected_count=2, allowed_extensions=("pdf",), min_size_kb=0,
        required_keywords=("W-2",), date_pattern=r"(?i)\b2025\b",
    ),
    RequestItem(
        identifier="C01", document="Mortgage Interest Statement", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("1098",),
    ),
]

BUSINESS = [
    RequestItem(
        identifier="B01", document="Trial Balance", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0, required_keywords=("trial balance",),
    ),
]

FATHER = (Person("taxpayer", "John Park", propose_spellings("John Park", "taxpayer")),)

LLC_PEOPLE = (Person("entity", "Park & Lee LLC",
                     propose_spellings("Park & Lee LLC", "entity")),)


def feeding(tmp_path, feeds):
    """Park Family's drop folder, extended to these return lines by a
    person - one ``household_changed`` event, exactly as the editor
    records it."""
    from tracker.households import load_household_info, save_household
    from tracker.layout import private_household_dir

    folder = private_household_dir(tmp_path, "Park Family")
    save_household(folder, replace(load_household_info(folder), feeds=tuple(feeds)))
    return folder


#: One request with no second file expected, as the room's claims want it:
#: its canonical copy is ``Prepared/A01 - W-2 Wage Statements - TY2025.pdf``,
#: 48 characters below the return folder (74 while it sat in a request
#: folder of its own, before decision 168).
ROOM_ITEMS = [
    RequestItem(
        identifier="A01", document="W-2 Wage Statements", period="TY2025",
        allowed_extensions=("pdf",), min_size_kb=0,
        required_keywords=("W-2",), date_pattern=r"(?i)\b2025\b",
    ),
]

#: Below the return folder: the canonical copy's path, and the folder it
#: sits in - Prepared itself since decision 168.
CANONICAL_BELOW = 48
FOLDER_BELOW = 9

#: A period long enough that ``A01 - <period>.pdf`` (44 characters) does not
#: fit the 43 a return of :func:`no_room_return` characters leaves in
#: Prepared - while its review folder still has room (decision 131's
#: floor). Since decision 168 that is the only way a request is left no
#: room: Prepared is shallower than the review folder, so an ordinary TY2025
#: name fits wherever a review copy does. This long, not ``Jan 2025 - Dec
#: 2025``, because with long paths off a review folder has room only in a
#: return of 206 characters at most, whose Prepared leaves 43 (pilot
#: decision P29) - and one period makes the claim under both settings.
LONG_PERIOD = "January 01 2025 - December 31 2025"
#: The period :func:`tight_return` asks for: long enough that the canonical
#: copy is nine past the limit in a return whose review folder has room
#: under either setting (pilot decision P29) - a TY2025 copy never is,
#: with long paths off.
TIGHT_PERIOD = "Jan 2025 to Dec 2025"
#: How far past the limit :func:`tight_return`'s claims put the canonical
#: copy, whose name then keeps ten characters of its document.
OVER = 9


def no_room_return() -> int:
    """A return whose Prepared leaves 43 characters for a name: 207 at 260,
    206 with long paths off - where it is also the deepest whose review
    folder has room (``tests.builders.floor_return``)."""
    from tracker.layout import path_limit

    return path_limit() - FOLDER_BELOW - 1 - 43


def no_room_prepared() -> int:
    """How long Prepared is in a return of :func:`no_room_return`."""
    return no_room_return() + FOLDER_BELOW


def with_the_long_period(item):
    """``item`` asking for :data:`LONG_PERIOD`, its year check stated - a
    period this long would derive a month check a year-end form does not
    pass, and the claims here are about room, not about the check."""
    return replace(item, period=LONG_PERIOD, date_pattern=r"(?i)\b2025\b")


def tight_return(base, over: int, items=ROOM_ITEMS, **kwargs):
    """A return whose A01 canonical copy, asking for :data:`TIGHT_PERIOD`,
    passes the limit by ``over`` characters: its folder is
    ``path_limit() + over - 62`` characters long."""
    from tracker.layout import path_limit

    below = CANONICAL_BELOW - len("TY2025") + len(TIGHT_PERIOD)
    items = [replace(item, period=TIGHT_PERIOD, date_pattern=r"(?i)\b2025\b") for item in items]
    root = root_for_a_return_of(base, path_limit() + over - below)
    engagement = make_engagement(root, items, **kwargs)
    assert len(str(engagement)) + below == path_limit() + over
    return engagement


SCHWAB_146 = "\n".join([
    "Charles Schwab", "2025 Consolidated Form 1099", "Form 1099-DIV Dividends and Distributions",
    "Form 1099-INT Interest Income", "Form 1099-B Proceeds From Broker and Barter Exchange Transactions",
    "Form 1099-MISC Miscellaneous Information", "Realized Gain and Loss",
])


def _consolidated_return(tmp_path, *, int_div_expected=2):
    """A 1040 on the shipped catalog, the Schwab statement dropped, sorted
    and scanned. A02 expects two statements here: the consolidated one
    carries two of them, its 1099-INT and its 1099-DIV."""
    from tracker.manifest import validated
    from tracker.scanner import scan_engagement
    from tracker.templates import template_items

    items = [replace(i, min_size_kb=0,
                     expected_count=int_div_expected if i.identifier == "A02" else i.expected_count)
             for i in validated(template_items("1040", year=2025))]
    engagement = make_engagement(tmp_path, items)
    drop(engagement, "Schwab 2025 1099.pdf", SCHWAB_146)
    sort(engagement, today=DAY1)
    scan_engagement(engagement, today=DAY1)
    return engagement


def sample_sentence(reason: Reason) -> str:
    """A Reason's sentence with every placeholder filled by a made-up value."""
    return reason.template.format(**{
        name: "x" for name in ("error", "extension", "allowed", "listed", "pattern")
    } | {"size_kb": 1.0, "minimum": 5, "size": "300 MB", "minutes": "10 minutes",
         "kind": "an email", "spelling": "x", "label": "x"})
