"""The command line as main.js drives it: argv in, one JSON reply out.

Every claim about the API is made through ``run(capsys, *argv)``, which calls
``api.main`` exactly as the window's ``main.js`` does and reads the one reply
back; ``scan`` is Sort & Scan as the app runs it (``run-now`` and then one
``list`` and one ``state``), and ``sample_engagement`` is a 1040 created through
the API with the sample pile dropped in. ``test_api`` wrote them and
``test_shell`` and ``test_rollover`` imported them from it; they live here so
the borrowing names a module that is not a test file (SPEC-architecture E-4, R2.1). Moved with their words from
``tests/test_api.py``, with the household, the people and ``where`` they lean on.

``_SPELLING_REFUSED`` came from ``tests/test_api.py`` too, with its words, when
the people tests that call ``_people_from_spec`` directly left for
``tests/test_request_edit.py`` (SPEC-architecture-p5 P5.4, P341): the tests
that stayed and one that moved read it, and a test file may not import
another (``tests/test_suite_shape.py``).

When ``tests/test_api.py`` was split by its section banners into ``tests/test_api_<family>.py``
(SPEC-architecture-p5 P5.14, E-3), every module-level helper two or more of the resulting files
read came here, byte for byte with its words and left where it was: ``COUNTS``, the ``demo_root``
fixture, ``said_by_class``, ``payload_of_state``, ``_raw``, ``_rows_of``, ``_typed_as_a_string``,
``_on_the_office_computer``, ``_parked_row``, ``a_moved_row``, ``chased_engagement``, ``reminder_card``,
``two_households``, ``waiting_document``, ``client_readme``, ``_a_deeper_root`` (with
``DEEPER_ROOT_LENGTH``), ``_tree_hashes``, ``_a_renamed_household``, ``_issuer_return``,
``_a_practice_for_the_firm_view``, ``_aged`` (with ``_AGED_AT``), ``_firm_whole``, ``_rows_read``,
``_cached_firm``, ``_walk_strings`` and ``_parked_read_pdf_state``. A helper one file reads moved with
that file. ``demo_root`` is a fixture, so each user names it once by assignment
(``demo_root = api_driver.demo_root``), as ``tests/passes.py``'s ``samples`` is named, because an
imported fixture a test then takes as a parameter trips ruff's F811.
"""

import datetime as dt
import json
import os
from pathlib import Path

import pytest

import tracker.api as api
from tests.builders import TEST_CLIENT, app_stdin
from tests.samples import PRIOR_YEAR, SCRATCH_PEOPLE, text_pdf
from tracker import firm_view, layout, ledger, reasons
from tracker.bounds import COUNT_BOUNDS, MAX_EXPECTED_COUNT, MIN_EXPECTED_COUNT
from tracker.index import FILED, NEEDS_REVIEW
from tracker.layout import PRIVATE_TREE, inbox_of, return_dir_for
from tracker.manifest import ManifestError, Status
from tracker.names import propose_spellings
from tracker.records import IndexEntry
from tracker.scaffold import REVIEW_DIR_NAME
from tracker.templates import BASE_YEAR

#: The one household every spec below names unless the claim is about
#: households. A client folder is a household since decision 125, and a
#: return lives under its year inside it.
HOUSEHOLD = "Test Household"


#: Who every spec below says the return is for, unless the claim is about
#: the people list. A return is refused without one since decision 128.
PEOPLE = [{"kind": "taxpayer", "name": TEST_CLIENT,
           "spellings": list(propose_spellings(TEST_CLIENT, "taxpayer"))}]


#: Who the sample pile's documents are addressed to, as a spec sends them.
SAMPLE_PEOPLE = [{"kind": one.kind, "name": one.name, "spellings": list(one.spellings)}
                 for one in SCRATCH_PEOPLE]


_SPELLING_REFUSED = (f"{api.PEOPLE_LABEL}: a spelling of Jane Smith must be one line of text of "
                     "at most 1000 characters, with no control character")


def where(root, return_name, year=None, household=HOUSEHOLD):
    """Where the return a spec named landed.

    The layout's answer, never a name a test typed: the private tree, the
    household, the year, the return (decision 125).
    """
    from tracker.templates import default_tax_year

    return return_dir_for(root, household, year or default_tax_year(), return_name)


def _head_now(argv) -> str:
    """The version of the list ``state`` would hand the editor now (decision
    160), for an ``edit`` or a ``rename`` that does not name its own - blank
    where the command names no engagement, which it then refuses anyway."""
    from tracker.manifest import list_head

    try:
        return list_head(argv[list(argv).index(api.ENGAGEMENT_FLAG) + 1])
    except (ValueError, IndexError, ManifestError):
        return ""


def run(capsys, *argv, stdin=None):
    """Run one command the way main.js does: argv in, one JSON object out.

    A ``create`` spec that names no household, or names the one these
    claims use, is given that one - by its folder once it exists, as the wizard picks it in the list
    (decision 188 refuses a household name typed again): since decision 125 every return belongs to a household, and most
    of what is claimed here is about the API rather than about households.
    The same for the people it is for: since decision 128 a return is
    refused without one, and most of what is claimed here is not about the
    name tier. And an ``edit`` or a ``rename`` carries the version of the
    list it was made from, as the editor's does (decision 160): the current
    one, unless the claim is about a stale one and names it.
    """
    if (stdin is not None and argv and argv[0] == "create"
            and stdin.get("household", HOUSEHOLD) == HOUSEHOLD and "household_path" not in stdin):
        stdin = {key: value for key, value in stdin.items() if key != "household"}
        # Picked in the list once it exists, as the wizard does: since
        # decision 188 a household name typed again is refused.
        from tracker.layout import private_household_dir
        from tracker.settings import clients_root

        root = clients_root()
        known = private_household_dir(root, HOUSEHOLD) if root else None
        stdin = ({"household_path": str(known), **stdin}
                 if known is not None and ledger.path_for(known).is_file()
                 else {"household": HOUSEHOLD, **stdin})
    if stdin is not None and argv and argv[0] == "create" and "people" not in stdin:
        stdin = {"people": PEOPLE, **stdin}
    if stdin is not None and argv and argv[0] in ("edit", "rename") and "head" not in stdin:
        stdin = {**stdin, "head": _head_now(argv)}
    if stdin is not None:
        with pytest.MonkeyPatch.context() as mp:
            mp.setattr("sys.stdin", app_stdin(stdin))
            code = api.main(list(argv))
    else:
        code = api.main(list(argv))
    return code, one_reply(capsys.readouterr().out)


def one_reply(out: str) -> dict:
    """The one reply a command printed, the way main.js reads stdout
    (decision 193): every line but the last is a progress line, and the
    last - the only one without ``progress`` - is the reply."""
    from tracker.progress import PROGRESS_KEY

    lines = [json.loads(line) for line in out.strip().splitlines()]
    assert lines, "expected a reply, got nothing"
    assert all(PROGRESS_KEY in line for line in lines[:-1]), lines
    assert PROGRESS_KEY not in lines[-1], lines[-1]
    return lines[-1]


def scan(capsys, engagement) -> tuple[int, dict]:
    """Sort & Scan the way the app runs it since decision 203: ``run-now``,
    which hands this return's household to the runner's own pass in this
    process, then - when the pass ends - one ``list`` and one ``state``, as
    the renderer redraws (the lane's ruling on 194's Q5).

    Answers with the pass's exit code and the reply the claims below read:
    ``run`` is the asked return's entry in the final line, ``household``
    the household's other returns, ``pass_warnings`` and ``pass`` the final
    line's own, ``lock`` the lock a locked-out return met, and ``state``,
    ``list`` and ``warnings`` the redraw's. A refusal is its envelope."""
    code = api.main([api.PASS_COMMAND, api.ENGAGEMENT_FLAG, str(engagement)])
    final = one_reply(capsys.readouterr().out)
    if "error" in final:
        return code, final
    # Matched as the renderer matches (decision 203's review, S2): the
    # path's own spelling, the one the API gives the app, so a mismatch
    # fails here rather than hiding the counts on screen.
    asked = str(api._return_dir(engagement))
    [run] = [one for one in final["runs"] if one["path"] == asked]
    held = next((one["locked_at"] for one in final["runs"] if one["locked_at"]), None)
    assert api.main(["list"]) == 0
    listed = one_reply(capsys.readouterr().out)
    state_code = api.main(["state", api.ENGAGEMENT_FLAG, str(engagement)])
    state = one_reply(capsys.readouterr().out)
    return code, {
        "run": run,
        "household": [one for one in final["runs"] if one is not run],
        "pass_warnings": final["pass_warnings"],
        "pass": final["pass"],
        "lock": api._lock_payload(Path(held)) if held else None,
        "state": state if state_code == 0 else None,
        "list": {key: listed[key] for key in ("engagements", "households", "misfits", "root")},
        "warnings": state.get("warnings", []),
    }


def sample_engagement(capsys, demo_root, tmp_path, *names):
    """A 1040 engagement created through the API with sample documents dropped in."""
    from tests.samples import build_samples

    # The pile is addressed to the two people the samples name, so the
    # return lists them (decision 128) exactly as the office's would.
    spec = {"household": HOUSEHOLD, "return_name": "Smith Family 2025", "form": "1040", "client": "John Smith",
            "people": SAMPLE_PEOPLE,
            "items": [t for t in api.FORM_TEMPLATES["1040"] if t["core"]]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    engagement = where(demo_root, "Smith Family 2025")
    samples = tmp_path / "samples"
    build_samples(samples)
    for sample in samples.iterdir():
        if not names or sample.name in names:
            (inbox_of(engagement) / sample.name).write_bytes(sample.read_bytes())
    return engagement


#: What a count outside the record's bounds is refused with (decision 187).
COUNTS = COUNT_BOUNDS.format(minimum=MIN_EXPECTED_COUNT, maximum=MAX_EXPECTED_COUNT)


@pytest.fixture
def demo_root(short_root, tmp_path, monkeypatch):
    """A clients root recorded the way the app records it: settings.json beside the app.

    Short, because ``create`` refuses a return whose deepest working copy
    would pass what Windows will open (decision 125) and a pytest temporary
    folder spends ninety characters before the layout starts - where the
    office's own root spends twenty-seven. ``short_root`` is walked by the
    agreement fixtures exactly as ``tmp_path`` is.
    """
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root, set_firm

    root = short_root
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(tmp_path / "app"))
    set_clients_root(root)
    set_firm("J Park & Associates, CPA")
    return root


def said_by_class(payload: dict, kind: str) -> bool:
    """An unexpected error said on screen by its class alone (decision 193):
    never its message, which stays in the error log."""
    return payload["error"] == api.FAILED.format(kind=kind, log=api.ERROR_LOG_FILENAME) \
        and payload["failure"]["kind"] == "failed"


def _parked_row(name: str, code: str) -> IndexEntry:
    """A parked row with a review copy, as the filer writes one: fabricated."""
    return IndexEntry(
        received="2026-02-01", original_name=name, size_kb=12.0, digest="7" * 64,
        identifier="", prepared_location=f"{REVIEW_DIR_NAME}/{name}",
        pbc_location=f"pbc/{name}", decision=NEEDS_REVIEW, reason="fabricated", code=code)


def payload_of_state(capsys, engagement):
    code, payload = run(capsys, "state", api.ENGAGEMENT_FLAG, str(engagement))
    assert code == 0, payload
    return payload


def _typed_as_a_string(source: str, word: str) -> bool:
    """Is ``word`` typed in ``source`` as the start of a string literal? The
    approved words are short (P84), and a short word is also a substring of
    a comment or an identifier (``Held:`` in a comment, ``Spelling`` in
    ``teachSpelling``); what the renderer must not do is show one, so it is
    looked for where a string begins."""
    return any(quote + word in source for quote in ('"', "'", "`"))


def _on_the_office_computer(monkeypatch, *, task_exists=False):
    """This computer is ``office-pc`` with Task Scheduler, and its
    ``schtasks`` a fake that keeps every command (decision 209)."""
    import platform

    from tracker import scheduling, settings

    calls = []

    class Said:
        def __init__(self, returncode=0):
            self.returncode, self.stdout, self.stderr = returncode, "", ""

    def answer(command):
        calls.append(command)
        return Said(0 if task_exists or command[1] != "/query" else 1)

    monkeypatch.setattr(platform, "node", lambda: "OFFICE-PC")
    # Windows' scheduler, whatever this is; a Windows runner stays Windows.
    monkeypatch.setattr(settings, "host_system", lambda: "nt" if os.name == "nt" else "posix")
    monkeypatch.setattr(scheduling, "scheduler_here", lambda: True)
    monkeypatch.setattr(scheduling, "_schtasks", answer)
    return calls


def a_moved_row(capsys, demo_root, tmp_path, drag_to):
    """One filed document dragged by hand, and the state the pass leaves.

    ``drag_to`` is given the engagement and the copy's home and answers with
    where the hand put it. Comes back with the engagement, the row as it was
    filed (its own sequence number included) and the state that now holds it
    in ``moved``.
    """
    engagement = sample_engagement(capsys, demo_root, tmp_path, "Form 1098 Mortgage Interest.pdf")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [filed] = [e for e in payload["state"]["index"] if e["decision"] == FILED]
    home = engagement / filed["prepared_location"]
    target = drag_to(engagement, home)
    target.parent.mkdir(parents=True, exist_ok=True)
    home.rename(target)

    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    return engagement, filed, target, payload["state"]


def chased_engagement(capsys, demo_root, name="Chase", client="John Smith"):
    """One engagement with two documents outstanding and a scan behind them."""
    from tests.builders import seed_statuses
    from tracker.manifest import StatusUpdate

    spec = {"household": HOUSEHOLD, "return_name": name, "client": client, "due": "2026-03-15", "filing_deadline": "2026-04-15",
            "items": [{"identifier": "A01", "document": "W-2 Wage Statements"},
                      {"identifier": "B01", "document": "Bank Statements"}]}
    assert run(capsys, "create", stdin=spec)[0] == 0
    folder = where(demo_root, name)
    seed_statuses(folder, {"A01": StatusUpdate(status=Status.MISSING),
                           "B01": StatusUpdate(status=Status.MISSING)})
    return folder


def reminder_card(capsys, folder, stage=None):
    code, payload = run(capsys, "reminder", api.ENGAGEMENT_FLAG, str(folder),
                        stdin={"stage": stage})
    assert code == 0, payload
    return payload["reminder"]


def two_households(capsys, root):
    """Park Family with a 1040, Park & Lee LLC with an 1120S, and Park
    Family's drop folder feeding the LLC's return line - made the way the
    app makes them, and extended the way a person extends it."""
    assert run(capsys, "create", stdin={
        "household": "Park Family", "contact": "John", "return_name": "1040 - John Park",
        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    assert run(capsys, "create", stdin={
        "household": "Park & Lee LLC", "contact": "John & Sam",
        "return_name": "1120S - Park & Lee LLC",
        "items": [{"identifier": "B01", "document": "Trial Balance"}]})[0] == 0
    father = where(root, "1040 - John Park", household="Park Family")
    llc = where(root, "1120S - Park & Lee LLC", household="Park & Lee LLC")
    code, payload = run(capsys, "edit-household", api.ENGAGEMENT_FLAG, str(father),
                        stdin={"feeds": [{"household": "Park & Lee LLC",
                                          "return_name": "1120S - Park & Lee LLC"}]})
    assert code == 0, payload
    return father, llc


def waiting_document(capsys, father):
    """A trial balance naming the LLC's person, dropped in the father's
    inbox and parked by *Run now* for one click (decision 204): its triage
    entry, as the card receives it."""

    text_pdf(inbox_of(father) / "tb.pdf", ["Trial balance as of December 31 2025", TEST_CLIENT], style="padded")
    code, payload = scan(capsys, father)
    assert code == 0, payload
    [waiting] = payload["state"]["review"]
    return waiting


def client_readme(engagement) -> str:
    from tracker.scaffold import README_NAME

    return (inbox_of(engagement) / README_NAME).read_text(encoding="utf-8")


#: How long :func:`_a_deeper_root` makes the clients root, in characters,
#: whatever the machine's temporary folder spends of it: deep enough that a
#: return of two names at the longest may pass Windows's limit, and shallow
#: enough that a plain return keeps :data:`FITS_MARGIN` to spare.
DEEPER_ROOT_LENGTH = 108


def _a_deeper_root(demo_root):
    """A clients root one long folder below the suite's short one, recorded
    as the app records it. Since decision 188 a name is at most eighty
    characters, so under the short root no return's path can pass what
    Windows will open; a root this deep is where a root that grew leaves
    the firm."""
    from tracker.settings import set_clients_root

    # The same length on every machine, from the real temporary folder: a
    # Windows runner's is longer than Linux's, and a fixed pad left the
    # "fits" return below one character short of Excel's 218 there.
    pad = DEEPER_ROOT_LENGTH - len(str(demo_root / "Clients root "))
    if pad < 1:
        pytest.skip(f"{demo_root} is too long to make a root of {DEEPER_ROOT_LENGTH} characters")
    deeper = demo_root / ("Clients root " + "d" * pad)
    deeper.mkdir()
    set_clients_root(deeper)
    return deeper


def _rows_of(state) -> list[dict]:
    """The rows the editor would send back for ``state``, untouched."""
    return [dict(rule) for rule in state["rules"]]


def _tree_hashes(folder):
    """Every file and folder under ``folder``, with each file's bytes."""
    import hashlib

    return {str(p.relative_to(folder)): (hashlib.sha256(p.read_bytes()).hexdigest()
                                         if p.is_file() else "folder")
            for p in sorted(folder.rglob("*"))}


def _a_renamed_household(capsys, demo_root, *, received=False):
    """Park Family with one return, its private folder then renamed in
    Explorer to Park Household: the record still claims Park Family."""
    from tests.builders import seed_index
    from tracker.index import FILED
    from tracker.records import IndexEntry

    assert run(capsys, "create", stdin={"household": "Park Family", "return_name": "1040 - Park",
                                        "items": [{"identifier": "A01", "document": "W-2"}]})[0] == 0
    engagement = where(demo_root, "1040 - Park", household="Park Family")
    if received:
        seed_index(engagement, [IndexEntry(
            received="2026-02-02", original_name="w2.pdf", size_kb=5.0, digest="ab" * 32,
            identifier="A01", prepared_location="Prepared/A01 - W-2.pdf",
            pbc_location=f"../../../../{layout.CLIENTS_TREE}/Park Family/2025/w2.pdf",
            decision=FILED, reason="filed")])
    private = demo_root / PRIVATE_TREE
    (private / "Park Family").rename(private / "Park Household")
    return private / "Park Household" / engagement.parent.name / engagement.name


def _raw(capsys, *argv, stdin=None):
    """A command's whole stdout, lines and all, the way the shell reads it."""
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr("sys.stdin", app_stdin(stdin or {}))
        code = api.main(list(argv))
    return code, capsys.readouterr().out


def _issuer_return(capsys, demo_root, *, year=BASE_YEAR, items=None, name="Issuer Return"):
    """A 1040 whose list asks for K-1s one row per issuer - the catalog's K-1
    row and one issuer row, as the catalog builds them, for ``year`` - and a
    K-1 from an issuer it does not name, parked for a person by a pass.
    Returns the return and the parked row as the state shows it."""
    from tracker import templates

    # Written for the catalog's year: the create shifts them to the return's.
    rows = items or [templates.k1_row(), templates.issuer_row("F02", "Ashford Holdings")]
    spec = {"household": HOUSEHOLD, "return_name": name, "form": "1040", "year": year,
            "items": rows}
    code, payload = run(capsys, "create", stdin=spec)
    assert code == 0, payload
    engagement = where(demo_root, name, year)
    text_pdf(inbox_of(engagement) / "k-1 dunmore.pdf", [
        f"Schedule K-1 {year} (Form 1065) Partner's Share of Income, Deductions, Credits, etc.",
        "k-1 statement", "Part I Information About the Partnership", "Dunmore Capital Group",
        "Part II Information About the Partner", TEST_CLIENT], style="padded")
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    [row] = [e for e in payload["state"]["index"] if e["decision"] == NEEDS_REVIEW]
    return engagement, row


def _a_practice_for_the_firm_view(capsys, demo_root):
    """Three returns: one with a request in, one out and one nobody asked for
    plus a program parked for a person; one with everything in; one inactive.
    Made-up names only."""
    from tests.builders import seed_index, seed_statuses
    from tracker.manifest import StatusUpdate
    from tracker.records import IndexEntry

    mixed = chased_engagement(capsys, demo_root, name="Mixed")
    seed_statuses(mixed, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    seed_index(mixed, [IndexEntry(
        received="2026-02-01", original_name="setup.exe", size_kb=0.1, digest="5" * 64,
        identifier="", prepared_location="", pbc_location="pbc/setup.exe",
        decision=NEEDS_REVIEW, reason=reasons.NOT_A_DOCUMENT.format(),
        code=reasons.NOT_A_DOCUMENT.code)])
    quiet = chased_engagement(capsys, demo_root, name="Quiet")
    seed_statuses(quiet, {"A01": StatusUpdate(status=Status.RECEIVED, file_count=1),
                          "B01": StatusUpdate(status=Status.RECEIVED, file_count=1)})
    retired = chased_engagement(capsys, demo_root, name="Retired")
    rows = payload_of_state(capsys, retired)["rules"]
    assert run(capsys, "edit", api.ENGAGEMENT_FLAG, str(retired),
               stdin={"items": rows, "engagement": {"active": False}})[0] == 0
    return mixed, quiet, retired


#: One time in the past every aged entry is given, so an entry aged twice
#: keeps its time and only what changed in between reads as changed.
_AGED_AT = int(dt.datetime.now().timestamp()) - 3600


def _aged(root: Path) -> None:
    """Every entry under ``root`` dated an hour ago - past the cache's racy
    window, as a practice nobody has touched for a while is - so the firm
    view keeps what it reads. The records' contents are not touched."""
    for path in [root, *root.rglob("*")]:
        os.utime(path, (_AGED_AT, _AGED_AT))


def _firm_whole(capsys, monkeypatch) -> dict:
    """The firm reply with the cache set aside: the whole walk, as it was
    before P120 - the reference every cached reply is held to."""
    with monkeypatch.context() as patch:
        patch.setattr(api, "_firm_cached", lambda root, today: None)
        code, payload = run(capsys, "firm")
    assert code == 0, payload
    return payload


def _rows_read(monkeypatch) -> list[str]:
    """The returns the next replies read (``_firm_row``), by path."""
    read, real = [], api._firm_row

    def counted(one, household, today):
        read.append(str(one.path))
        return real(one, household, today)

    for module in (api, firm_view):
        monkeypatch.setattr(module, "_firm_row", counted)
    return read


def _cached_firm(capsys) -> dict:
    code, payload = run(capsys, "firm")
    assert code == 0, payload
    return payload


def _walk_strings(value):
    if isinstance(value, str):
        yield value
    elif isinstance(value, dict):
        for inner in value.values():
            yield from _walk_strings(inner)
    elif isinstance(value, (list, tuple)):
        for inner in value:
            yield from _walk_strings(inner)


def _parked_read_pdf_state(capsys, demo_root, tmp_path):
    """A real scan whose pile parks a read PDF (last year's W-2): a row whose
    copy opens, beside rows whose copies are only shown."""
    engagement = sample_engagement(capsys, demo_root, tmp_path)
    code, payload = scan(capsys, engagement)
    assert code == 0, payload
    state = payload["state"]
    [parked] = [e for e in state["index"] if e["original_name"] == f"W-2 Jane Smith {PRIOR_YEAR} - old.pdf"]
    assert parked["open_key"].startswith("review_copy "), parked
    return state, parked
