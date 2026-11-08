"""Tests for tracker/runner.py: what a pass leaves for a person to read.

The practice on a page, records that need a person (decision 159), the last-pass file, a checkpoint that cannot be
asked, the page that reads the store the walk left (decision 192), the run log's counts and codes, the firm view's
cache filled by the pass, its two firm-wide reads and the pass-order hint.

Split from ``tests/test_runner.py`` by SPEC-architecture-p5 P5.14 (E-3), by the banners the old file kept its
sections under, each test moved byte for byte with its section, so that each family runs as its own process
(Jason, 2026-09-29) and an affected-tests run reaches only the family a change touched. The map owns this file
as ``tracker/runner.py``'s test by its name (decision P350). What more than one family reads is
``tests/passes.py``'s, because a test file may not import another (``tests/test_suite_shape.py``).
"""

import datetime as dt
import html
import json
import re
from pathlib import Path

import pytest

import tracker.runner as runner_module
from tests import passes
from tests.builders import make_engagement
from tests.passes import (
    FRIDAY,
    SATURDAY,
    _a_parked_file,
    _hint_file,
    _hint_lines,
    _lines,
    _page,
    _run_now,
    _settings_for,
    _the_scheduled_job,
    _three_households,
    _two_households,
    a_pass,
    build_engagement,
    households_in_order,
    make_ambiguous,
)
from tests.samples import YEAR
from tests.source_pins import PACKAGE, py_function
from tracker import fsio, ledger, pass_order, run_log, status_page, store
from tracker.index import NEEDS_REVIEW, read_index
from tracker.layout import household_of, inbox_of, root_of
from tracker.manifest import ManifestError, RequestItem
from tracker.registry import Engagement, Registry, discover_engagements
from tracker.reminder import DRAFT_FILENAME
from tracker.run_log import LOG_FILENAME, REMINDERS_NEVER, RunReport, append_log, log_path
from tracker.runner import SETTINGS_FLAG, main, run_household, run_registry
from tracker.settings import product_name
from tracker.status_page import RECORD_UNREADABLE, STATUS_GENERATED, STATUS_PAGE_FILENAME, write_status_page

#: The sample pile, built once per session: a fixture of ``tests/passes.py``, named here
#: so every claim below can ask for it.
samples = passes.samples


# ----------------------------------------------------- the practice on a page ----


def test_a_real_pass_writes_the_status_page_into_the_root_and_a_dry_run_does_not(tmp_path, samples, capsys):
    """The page is the pass's standing answer, so a pass that changed nothing
    on disk must not leave one - a dry run writes nothing, this included."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    build_engagement(root, samples)
    page = root / STATUS_PAGE_FILENAME

    assert main([str(root), "--date", FRIDAY.isoformat(), "--dry-run"]) == 0
    assert not page.exists()

    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    text = page.read_text(encoding="utf-8")
    assert product_name() in text
    assert STATUS_GENERATED.split("{")[0].strip() in text
    assert "Smith TY2025" in text
    assert "<script" not in text and "://" not in text, "one file, nothing fetched to render it"
    capsys.readouterr()


def _policy_matches_the_blocks(text: str) -> None:
    """The page's policy, recomputed from the page as written: each inline
    style and script is allowed by the SHA-256 of its own text, and nothing
    else is allowed at all."""
    import base64
    import hashlib
    import re

    def allowed(block: str) -> str:
        digest = hashlib.sha256(block.encode("utf-8")).digest()
        return f"'sha256-{base64.b64encode(digest).decode('ascii')}'"

    policies = re.findall(r'<meta http-equiv="Content-Security-Policy" content="([^"]*)">', text)
    assert len(policies) == 1, "one policy per page"
    directives = dict(part.strip().split(" ", 1) for part in policies[0].split(";"))
    styles = re.findall(r"<style>(.*?)</style>", text, re.S)
    scripts = re.findall(r"<script>(.*?)</script>", text, re.S)
    assert directives.pop("default-src") == "'none'"
    assert directives.pop("style-src") == " ".join(allowed(block) for block in styles)
    if scripts:
        assert directives.pop("script-src") == " ".join(allowed(block) for block in scripts)
    assert directives == {}, "nothing beyond its own blocks"
    assert text.index("Content-Security-Policy") < text.index("<style>")


def test_both_pages_carry_a_policy_whose_hashes_match(tmp_path, samples, capsys):
    """A page in a shared folder can be edited by anyone who can reach it; its
    policy lets a browser run the page's own style and script and nothing
    else (decision 190). Both pages a pass writes carry one, and the hashes
    in it are the hashes of the blocks actually on the page."""
    from tracker.view import VIEW_FILENAME
    # A root of its own: tmp_path holds the suite's app folder (decision 185).
    root = tmp_path / "root"

    engagement = build_engagement(root, samples)
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    capsys.readouterr()

    status = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    report = (engagement.path / VIEW_FILENAME).read_text(encoding="utf-8")
    _policy_matches_the_blocks(status)
    _policy_matches_the_blocks(report)
    assert "script-src" not in status, "the practice page runs no script"
    assert "script-src" in report, "the engagement page's sort script is allowed by its hash"


def test_the_page_lists_every_engagement_the_registry_finds_including_an_unreadable_one(
    tmp_path, samples, capsys
):
    """An engagement missing from the page is an engagement nobody chases. One
    whose record cannot be read is on it by name, and named as a problem."""
    clients = tmp_path / "Clients"
    good = build_engagement(clients, samples, name="Good TY2025")
    # A return of the same household whose journal will not parse: it sits
    # where a return sits, because a folder anywhere else is a misfit the
    # walk leaves alone rather than an engagement (decision 125).
    bad = good.path.parent / "Bad TY2025"
    bad.mkdir(parents=True)
    ledger.path_for(bad).write_text("{this line is not an event}\n", encoding="utf-8")

    assert main([str(clients), "--date", FRIDAY.isoformat()]) == 1
    text = (clients / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")

    assert "Good TY2025" in text
    assert text.count("Bad TY2025") >= 2            # its row, and the problems list
    assert RECORD_UNREADABLE.split("{")[0] in text
    capsys.readouterr()


def test_the_review_queue_lists_parked_files_newest_first_with_their_reasons(tmp_path, samples):
    """One queue across the practice, because the work is one queue: the file
    that arrived last night is at the top, whichever client sent it."""
    # Two households, because one inbox feeds every return of a household
    # since decision 125 and this claim is about two clients' files.
    older = build_engagement(tmp_path, samples, drops=("vacation photo.bmp",),
                             household="Older Family", name="Older TY2025")
    newer = build_engagement(tmp_path, samples, drops=("Mortgage Notes.docx",),
                             household="Newer Family", name="Newer TY2025")
    first = a_pass(older, today=FRIDAY, reminders=REMINDERS_NEVER)
    second = a_pass(newer, today=SATURDAY, reminders=REMINDERS_NEVER)
    assert first.review == 1 and second.review == 1

    page = write_status_page(tmp_path, RunReport(today=SATURDAY, runs=[first, second]))
    text = page.read_text(encoding="utf-8")

    assert text.index("Mortgage Notes.docx") < text.index("vacation photo.bmp")
    assert SATURDAY.isoformat() in text and FRIDAY.isoformat() in text
    for engagement in (older, newer):
        parked = [e for e in read_index(engagement.path)
                  if e.decision == NEEDS_REVIEW]
        assert parked
        for entry in parked:
            assert html.escape(entry.reason) in text, entry.reason


def test_the_pass_holds_one_lock_from_the_sort_through_the_scan(tmp_path, samples, monkeypatch):
    """Decision 102: one lock across the whole pass, not one per step.

    The filer and the scanner used to take it one after the other, and the
    gap between them is a real one: a click in the app could file something
    into a folder the scan was about to read but had not decided from. The
    test asks the only question that distinguishes the two - while the scan
    step is running, can anybody else take this engagement's lock?
    """
    from tracker import runner as runner_module
    from tracker.locking import EngagementLockedError, acquire_lock

    engagement = build_engagement(tmp_path, samples)

    refused: list[bool] = []
    real = runner_module.scan_engagement

    def scan(engagement_dir, **kwargs):
        try:
            acquire_lock(Path(engagement_dir))
        except EngagementLockedError:
            refused.append(True)
        else:
            refused.append(False)
        return real(engagement_dir, **kwargs)

    monkeypatch.setattr(runner_module, "scan_engagement", scan)
    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER)

    assert run.ok, run.error
    assert refused == [True], "the scan step ran with the pass's lock let go"


def test_a_dry_run_takes_no_lock_at_all(tmp_path, samples, monkeypatch):
    """It writes nothing, so it must never block a real pass."""
    from tracker import runner as runner_module
    from tracker.locking import acquire_lock, release_lock

    engagement = build_engagement(tmp_path, samples)

    taken: list[bool] = []
    real = runner_module.scan_engagement

    def scan(engagement_dir, **kwargs):
        held = acquire_lock(Path(engagement_dir))
        taken.append(True)
        release_lock(held)
        return real(engagement_dir, **kwargs)

    monkeypatch.setattr(runner_module, "scan_engagement", scan)
    run = a_pass(engagement, today=FRIDAY, reminders=REMINDERS_NEVER, dry_run=True)

    assert run.ok and taken == [True]


def test_the_page_is_written_even_when_an_engagements_pass_failed(tmp_path, samples, capsys):
    """The pass that errored is exactly the one a person has to find out about,
    so the page it would have been written by is still written, with the error.
    A typo cannot reach the record (decision 104); what can is a journal
    line something else wrote badly."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    build_engagement(root, samples, name="Good TY2025")
    broken = build_engagement(root, samples, name="Broken TY2025")
    with ledger.path_for(broken.path).open("ab") as handle:
        handle.write(b"{this line is not an event}\n")

    assert main([str(root), "--date", FRIDAY.isoformat()]) == 1
    text = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")

    assert "Good TY2025" in text and text.count("Broken TY2025") >= 2
    assert "does not read as an event" in text
    capsys.readouterr()


def test_an_engagement_nobody_passed_is_read_rather_than_run(tmp_path, samples):
    """The app scans one engagement; the page is still about the practice. The
    others are read - manifest and sidecar, no lock, no scaffold, no scan -
    and say so by carrying no pass time."""
    from tracker.registry import discover_engagements
    from tracker.status_page import STATUS_NOT_PASSED, status_report

    clients = tmp_path / "Clients"
    scanned = build_engagement(clients, samples, name="Scanned TY2025")
    untouched = build_engagement(clients, samples, name="Untouched TY2025")
    earlier = a_pass(untouched, today=FRIDAY, reminders=REMINDERS_NEVER)
    run = a_pass(scanned, today=FRIDAY, reminders=REMINDERS_NEVER)

    report = status_report(discover_engagements(clients), passed=[run])
    rows = {r.engagement.path.name: r for r in report.runs}
    assert set(rows) == {"Scanned TY2025", "Untouched TY2025"}
    assert rows["Scanned TY2025"].last_pass is not None
    # Read back from the manifest its own earlier pass wrote, without a pass.
    assert rows["Untouched TY2025"].outstanding == earlier.outstanding > 0
    assert rows["Untouched TY2025"].statuses == earlier.statuses
    assert rows["Untouched TY2025"].last_pass is None

    text = write_status_page(clients, report).read_text(encoding="utf-8")
    assert STATUS_NOT_PASSED in text


# ------------------------------------------- decision 159: records that need a person ----


def test_conflict_copies_and_lock_siblings_are_named_every_pass_and_never_deleted(tmp_path, samples):
    """A-8 / G-5: what a sync client leaves beside a return's record and
    lock, and beside a household's, is named on the practice page and
    counted in the run log every pass - and no pass deletes, moves or
    renames one; only a person does."""
    from tracker.layout import household_of
    from tracker.page import esc
    from tracker.run_log import append_log
    from tracker.status_page import RECORD_SIBLING, STATUS_RECORDS_HEADING, status_report, write_status_page

    repo = Path(__file__).resolve().parents[1]

    engagement = build_engagement(tmp_path, samples)
    left = [engagement.path / "_ledger (1).jsonl", engagement.path / "_scan (conflict).lock",
            household_of(engagement.path) / "_LEDGER_conflict-2026.jsonl"]
    for copy in left:
        copy.write_text('{"event": "scanned"}\n', encoding="utf-8")
    log = tmp_path / "logs" / "runs.log"

    for _week in range(2):
        report = run_registry(discover_engagements(tmp_path), today=FRIDAY)
        append_log(log, report)
        write_status_page(tmp_path, status_report(discover_engagements(tmp_path), passed=report.runs))
        text = (tmp_path / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
        assert STATUS_RECORDS_HEADING in text
        for copy in left:
            assert esc(RECORD_SIBLING.format(path=copy.relative_to(tmp_path))) in text
            assert copy.read_text(encoding="utf-8") == '{"event": "scanned"}\n'
    # Counted in the run log, never named there (decision 186).
    logged = log.read_text(encoding="utf-8")
    assert logged.count("record_copies=3") == 2
    assert not any(copy.name in logged for copy in left)

    source = "\n".join(path.read_text(encoding="utf-8") for path in (repo / "tracker").glob("*.py"))
    assert "siblings(" in source and not any(
        f"{call}(" in line for line in source.splitlines() if "sibling" in line
        for call in ("unlink", "rename", "replace", "rmtree", "move"))


def test_a_line_written_on_another_machine_is_named_until_acknowledged(tmp_path, samples):
    """Decision 159, C-1 (a): a line another machine wrote is accepted - the
    pass files on - and named on the practice page every pass until a
    person acknowledges it; then it is not."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    from tests.builders import written_elsewhere
    from tracker import checkpoint
    from tracker.status_page import STATUS_RECORDS_HEADING

    engagement = build_engagement(root, samples)
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    written_elsewhere(engagement.path, ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {}}),
                      host="laptop-2")
    seq = len(ledger.read_events(engagement.path))

    for _pass in range(2):
        assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
        text = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
        assert STATUS_RECORDS_HEADING in text
        assert f"line {seq} was written on laptop-2" in text

    with checkpoint.opened(checkpoint.path_for(store.store_path())) as held:
        (line,) = checkpoint.unacknowledged(held)
        assert checkpoint.acknowledge(held, line.key) == 1
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    text = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    assert STATUS_RECORDS_HEADING not in text and "laptop-2" not in text


def test_a_refused_record_is_named_among_the_records_that_need_a_person(tmp_path, samples):
    """A record cut short behind the pass's back is that return's problem -
    the pass goes on - and it is listed first, with what to do."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    from tracker.status_page import STATUS_RECORDS_HEADING

    engagement = build_engagement(root, samples)
    other = build_engagement(root, samples, name="Other TY2025")
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    path = ledger.path_for(engagement.path)
    path.write_bytes(b"".join(path.read_bytes().splitlines(keepends=True)[:-1]))

    assert main([str(root), "--date", FRIDAY.isoformat()]) == 1
    text = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    first, _rest = text.split(f"<h2>{STATUS_RECORDS_HEADING}", 1)[1].split("</ul>", 1)
    # Decision 188's sentence for a journal shorter than the store, with the
    # recover pointer every refused record ends with.
    assert "holds fewer lines than the store has applied" in first and ledger.RUN_RECOVER in first
    assert other.path.name not in first
    path.unlink()                    # the fixtures' own fresh store would read it as it now is


def test_a_root_the_checkpoint_does_not_belong_to_is_refused_by_the_pass(tmp_path, samples, monkeypatch):
    """E5: the settings naming another folder than the one this machine's
    checkpoint belongs to - a copy of the root - stop the pass by name
    before anything is walked."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = tmp_path.parent / f"{tmp_path.name}-app"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    clients, copy = tmp_path / "Clients", tmp_path / "Clients copy"
    build_engagement(clients, samples)
    copy.mkdir()
    set_clients_root(clients)
    assert main(["--date", FRIDAY.isoformat()]) == 0
    set_clients_root(copy)
    with pytest.raises(SystemExit, match="record checkpoint belongs to .*If the clients root really moved"):
        main(["--date", FRIDAY.isoformat()])
    assert not (copy / STATUS_PAGE_FILENAME).exists()


def test_a_failure_before_the_root_is_written_to_the_last_pass_file(tmp_path, monkeypatch, capsys):
    """The scheduled job's shape writes the last-pass file beside the store
    (decision 159, E4): a pass that stops before it reaches a root says so
    with a reason code, and one that runs says when and how it ended. A
    pass run by hand writes nothing there, so it cannot make a stopped
    schedule look alive."""
    import json

    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    beside_the_store = Path(store.store_path()).with_name(run_log.LAST_PASS_FILENAME)
    assert run_log.last_pass_path() == beside_the_store

    empty = tmp_path / "empty-settings"
    empty.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(empty))
    with pytest.raises(SystemExit):
        main([SETTINGS_FLAG, str(empty), "--reminders", "never"])
    failed = json.loads(beside_the_store.read_text(encoding="utf-8"))
    assert failed["result"] == run_log.PASS_FAILED
    assert failed["reason_code"] == run_log.PASS_NO_ROOT
    assert failed["root"] == "" and failed["started"] and failed["ended"] and failed["build"]

    clients = tmp_path / "Clients"
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")])
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(clients)
    assert main([SETTINGS_FLAG, str(settings), "--reminders", "never"]) == 0
    ran = json.loads(beside_the_store.read_text(encoding="utf-8"))
    assert ran["result"] == run_log.PASS_SUCCEEDED and ran["reason_code"] == ""
    assert Path(ran["root"]) == clients

    # By hand, or a dry run: the file is left as the schedule wrote it.
    before = beside_the_store.read_bytes()
    assert main([str(clients), "--reminders", "never"]) == 0
    assert main([SETTINGS_FLAG, str(settings), "--dry-run", "--reminders", "never"]) == 0
    assert beside_the_store.read_bytes() == before
    capsys.readouterr()


def test_a_pass_over_a_root_the_checkpoint_does_not_belong_to_is_refused_however_the_root_is_given(
        tmp_path, samples, monkeypatch):
    """The review's S2 (probe C7): a copy of the root typed on the command
    line is held to the checkpoint exactly as the settings' root is; one
    client's folder inside the claimed root is not a copy."""
    import shutil

    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = tmp_path.parent / f"{tmp_path.name}-app"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    clients, copy = tmp_path / "Clients", tmp_path / "Clients copy"
    build_engagement(clients, samples)
    set_clients_root(clients)
    assert main(["--date", FRIDAY.isoformat()]) == 0
    shutil.copytree(clients, copy)
    with pytest.raises(SystemExit, match="record checkpoint belongs to"):
        main([str(copy), "--date", FRIDAY.isoformat()])
    with pytest.raises(SystemExit, match="record checkpoint belongs to"):
        main([str(copy), "--date", FRIDAY.isoformat(), "--dry-run"])
    assert main([str(clients), "--date", FRIDAY.isoformat(), "--dry-run"]) == 0
    shutil.rmtree(copy)


def test_a_checkpoint_that_will_not_open_stops_the_pass_by_name(tmp_path, samples):
    """The review's S4: the file and the runbook's step, never a traceback;
    the file is left where it is for a person. Since the rebase review's
    MF1 the pass does not stop at the proof: it serves no household, exits
    1, and says it first on the practice page it still writes."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    from tracker import checkpoint

    build_engagement(root, samples)
    where = checkpoint.path_for(store.store_path())
    where.parent.mkdir(parents=True, exist_ok=True)
    where.write_bytes(b"fabricated garbage, not a database" * 40)
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 1
    page = html.unescape((root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))
    assert re.search("No household was served this pass: .*cannot read this machine's record "
                     "checkpoint.*runbook §6", page)
    assert where.read_bytes().startswith(b"fabricated garbage")
    where.unlink()


def test_a_record_that_does_not_read_is_among_the_records_that_need_a_person(tmp_path, samples):
    """The review's S6: a careless hand edit that leaves a line unreadable is
    listed first with what to do, and the page never quotes the parser."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    from tracker.status_page import STATUS_RECORDS_HEADING

    engagement = build_engagement(root, samples)
    with ledger.path_for(engagement.path).open("ab") as handle:
        handle.write(b'{"event": "scanned", "note": "Fabricated" "x"}\n')
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 1
    text = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    first = text.split(f"<h2>{STATUS_RECORDS_HEADING}", 1)[1].split("</ul>", 1)[0]
    assert "does not read as an event (it is not JSON)" in first and ledger.RUN_RECOVER in first
    assert "Fabricated" not in text and "column" not in first
    ledger.path_for(engagement.path).unlink()


def test_the_page_names_the_acknowledge_command_with_this_machines_store(tmp_path, samples):
    """The review's N7: no placeholder a person has to fill in."""
    # The clients root is a folder of its own, not tmp_path: the suite's
    # settings folder is tmp_path/app, and a root holding it is refused (decision 185).
    root = tmp_path / "root"
    from tests.builders import written_elsewhere

    engagement = build_engagement(root, samples)
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    written_elsewhere(engagement.path, ledger.new(ledger.SCANNED, **{ledger.STATUSES_KEY: {}}),
                      host="laptop-2")
    assert main([str(root), "--date", FRIDAY.isoformat()]) == 0
    text = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    assert "&lt;store&gt;" not in text and "<store>" not in text
    assert f"python -m tracker.checkpoint &quot;{store.store_path()}&quot; acknowledge" in text


def test_a_first_pass_typed_on_one_clients_folder_claims_nothing(tmp_path, samples, monkeypatch):
    """The final review's SF1: only the settings' root claims this machine's
    record checkpoint. A first real pass typed on a folder inside it claims
    nothing, so the scheduled pass over the whole root still runs. Since
    decision 188 the door refuses such a root itself - inside a tree of the
    real root - before the checkpoint is asked, so nothing is claimed."""
    from tracker import checkpoint
    from tracker.layout import PRIVATE_TREE
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = tmp_path.parent / f"{tmp_path.name}-app"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    clients = tmp_path / "Clients"
    build_engagement(clients, samples)
    set_clients_root(clients)
    with pytest.raises(SystemExit, match="is inside the"):
        main([str(clients / PRIVATE_TREE), "--date", FRIDAY.isoformat()])
    where = checkpoint.path_for(store.store_path())
    if where.is_file():
        with checkpoint.opened(where) as held:
            assert checkpoint.root_of(held) is None
    assert main([SETTINGS_FLAG, str(settings), "--date", FRIDAY.isoformat()]) == 0
    with checkpoint.opened(where) as held:
        assert checkpoint.root_of(held) == str(clients.resolve())


def test_a_refused_root_is_never_written_into_even_to_log_the_refusal(tmp_path, monkeypatch):
    """The final review's SF2: a settings root refused by decision 137's
    rule gets no run-log line; the last-pass file beside the store carries
    the reason code."""
    import json

    from tracker.run_log import LAST_PASS_FILENAME, LOG_FILENAME, last_pass_path
    from tracker.settings import ENV_SETTINGS_DIR, KEY_CLIENTS_ROOT, settings_path

    settings = tmp_path / "appdata" / "settings"
    settings.mkdir(parents=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    around = settings.parent
    settings_path().write_text(json.dumps({KEY_CLIENTS_ROOT: str(around)}), encoding="utf-8")
    with pytest.raises(SystemExit):
        main([SETTINGS_FLAG, str(settings), "--reminders", "never"])
    assert not (around / LOG_FILENAME).exists()
    assert last_pass_path().name == LAST_PASS_FILENAME
    assert json.loads(last_pass_path().read_text(encoding="utf-8"))["result"] == "failed"


# ------------------- the last-pass file beside 189's log and page (159 on 189) ----


def _a_scheduled_main(tmp_path, monkeypatch, body):
    """Run ``main`` in the scheduled job's shape with ``_pass`` replaced by
    ``body`` (what the pass itself does is 189's, tested above)."""
    from tracker.settings import ENV_SETTINGS_DIR

    settings = tmp_path / "settings"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setattr(runner_module, "_pass", body)
    return main([SETTINGS_FLAG, str(settings), "--reminders", "never", runner_module.LOG_FLAG])


def test_a_household_not_served_twice_is_the_last_pass_files_reason(tmp_path, monkeypatch):
    """Decision 189's exit 3 is its own reason in the file, not "a return
    failed": the app's line points at the page, which names the household."""
    import json

    assert _a_scheduled_main(tmp_path, monkeypatch,
                             lambda ns, parser, reached: runner_module.NOT_SERVED_TWICE_EXIT_CODE) == 3
    written = json.loads(run_log.last_pass_path().read_text(encoding="utf-8"))
    assert written["result"] == run_log.PASS_FAILED
    assert written["reason_code"] == run_log.PASS_NOT_SERVED
    line = run_log.last_pass_line()
    assert run_log.PASS_REASONS[run_log.PASS_NOT_SERVED] in line["text"]


def test_a_last_pass_file_that_cannot_be_written_never_stops_the_pass(tmp_path, monkeypatch):
    """Decision 189: nothing but the pass's own work decides its exit."""
    def refused(*args, **kwargs):
        raise PermissionError(13, "Permission denied")

    monkeypatch.setattr(runner_module, "write_last_pass", refused)
    assert _a_scheduled_main(tmp_path, monkeypatch, lambda ns, parser, reached: 0) == 0


def test_a_pass_that_stops_after_its_root_logs_the_kind_never_the_words(tmp_path, monkeypatch):
    """The run log's early-failure line carries the reason's code, its fixed
    sentence and the class of what stopped the pass - never the message,
    which can name a client's folder (decision 189, security principle 7)."""
    clients = tmp_path / "Clients"
    clients.mkdir()

    def stopped(ns, parser, reached):
        reached["root"] = str(clients)
        raise RuntimeError("Fabricated Client, 1040 - Fabricated Name")

    with pytest.raises(RuntimeError):
        _a_scheduled_main(tmp_path, monkeypatch, stopped)
    said = run_log.log_path().read_text(encoding="utf-8")      # the data home's (decision 186)
    assert f"pass failed ({run_log.PASS_ENDED_EARLY})" in said and "(RuntimeError)" in said
    assert "Fabricated" not in said
    assert not (clients / LOG_FILENAME).exists()


def test_a_pass_that_stops_before_its_root_is_logged_in_the_data_home(tmp_path, monkeypatch):
    """159 had nowhere to log a pass that never found a root; the run log in
    the data home (decision 186) takes it, by code and class only."""
    def stopped(ns, parser, reached):
        raise runner_module.PassFailed(run_log.PASS_NO_ROOT, "Fabricated Client's folder")

    with pytest.raises(SystemExit):
        _a_scheduled_main(tmp_path, monkeypatch, stopped)
    said = run_log.log_path().read_text(encoding="utf-8")
    assert f"pass failed ({run_log.PASS_NO_ROOT})" in said and "(PassFailed)" in said
    assert "Fabricated" not in said


# ------------- a checkpoint that cannot be asked (the rebase review's MF1-SF3) ----


def _the_scheduled_pass_with(tmp_path, monkeypatch, spoil):
    """Two households, the settings naming their root, and ``spoil`` done to
    this machine's record checkpoint; then the scheduled job's pass, logged.
    Returns the exit, the page, the log and the last-pass file."""
    import json

    from tracker import checkpoint
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    clients = tmp_path / "Clients"
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")], household="Smith Family")
    make_engagement(clients, [RequestItem(identifier="A01", document="W-2")], household="Jones Family")
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(clients)
    monkeypatch.setattr(checkpoint, "BUSY_TIMEOUT_MS", 100)
    where = checkpoint.path_for(store.store_path())
    checkpoint.open(where).close()
    with spoil(where):
        code = main([SETTINGS_FLAG, str(settings), "--reminders", "never", "--log"])
    page = html.unescape((clients / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))
    logged = run_log.log_path().read_text(encoding="utf-8")   # the data home's (decision 186)
    written = json.loads(run_log.last_pass_path().read_text(encoding="utf-8"))
    return code, page, logged, written


def test_a_damaged_checkpoint_ends_the_pass_named_with_its_page_and_log_written(tmp_path, monkeypatch):
    """MF1: a record-heads.db damaged past its first page used to end every
    scheduled pass as a traceback before the first household, with no page
    and no log. Now the pass reaches its root, serves no household, writes
    both - the checkpoint's own sentence first under Records that need a
    person - and the last-pass file carries its own reason."""
    from contextlib import contextmanager

    @contextmanager
    def damaged(where):
        data = bytearray(where.read_bytes())
        for i in range(4096, len(data)):
            data[i] = 0xA5
        where.write_bytes(bytes(data))
        yield

    code, page, logged, written = _the_scheduled_pass_with(tmp_path, monkeypatch, damaged)
    assert code == 1
    records = page[page.index(status_page.STATUS_RECORDS_HEADING):]
    first = records.split("<li>", 2)[1]
    assert first.startswith("No household was served this pass") and "Set the file aside" in first
    # The log carries the code and the count, never the sentence (decision 186).
    assert f"{run_log.CODE_CHECKPOINT_NOT_PROVED}=1" in logged and "checkpoint_unread=1" in logged
    assert "No household was served this pass" not in logged and "Traceback" not in logged
    assert written["reason_code"] == run_log.PASS_CHECKPOINT_UNREADABLE
    assert run_log.PASS_REASONS[run_log.PASS_CHECKPOINT_UNREADABLE] in \
        run_log.last_pass_line()["text"]


def test_a_busy_checkpoint_is_never_called_another_root(tmp_path, monkeypatch):
    """SF1: three states, three sentences. Busy says try again and never
    set-aside; it is never "not the root", which sends a person to
    move-root."""
    import sqlite3
    from contextlib import contextmanager

    @contextmanager
    def held_elsewhere(where):
        holder = sqlite3.connect(where, isolation_level=None)
        holder.execute("BEGIN EXCLUSIVE")
        try:
            yield
        finally:
            holder.execute("ROLLBACK")
            holder.close()

    code, page, _logged, written = _the_scheduled_pass_with(tmp_path, monkeypatch, held_elsewhere)
    assert code == 1
    assert written["reason_code"] == run_log.PASS_CHECKPOINT_BUSY
    assert "the next pass tries again" in page and "Set the file aside" not in page
    assert "belongs to" not in run_log.last_pass_line()["text"]


# ------------------- the page reads the store the walk left (decision 192) ----


def _count_journal_reads(monkeypatch) -> list[Path]:
    """Every journal read from now on: each goes through ``Path.read_bytes``
    (``ledger._bytes_of``)."""
    read: list[Path] = []
    real = Path.read_bytes

    def counting(self):
        if self.name == ledger.LEDGER_FILENAME:
            read.append(Path(self))
        return real(self)

    monkeypatch.setattr(Path, "read_bytes", counting)
    return read


def test_the_practice_page_reads_no_journal_the_walk_has_followed(tmp_path, samples, monkeypatch):
    """F-M-3: the page read every return's journal four more times after
    the walk had followed each one. It now reads the store the walk left -
    and still carries each return's counts and parked files."""
    first, second = _two_households(tmp_path, samples)
    for one in (first, second):
        a_pass(one, today=FRIDAY, reminders=REMINDERS_NEVER)
    parked = _a_parked_file(first.path)
    registry = discover_engagements(tmp_path)
    read = _count_journal_reads(monkeypatch)

    report = status_page.status_report(registry)
    write_status_page(tmp_path, report)

    assert read == []
    assert all(run.statuses for run in report.runs)
    assert parked in _page(tmp_path)
    # The recorder sees a journal read when one is made.
    read_index(first.path)
    assert ledger.path_for(first.path) in read


def test_the_page_follows_a_journal_the_store_does_not_hold(tmp_path, samples):
    """R5: a return the store has no row for is built from its journal
    for the page, as every reader builds one - never shown blank."""
    first, second = _two_households(tmp_path, samples)
    earlier = a_pass(first, today=FRIDAY, reminders=REMINDERS_NEVER)
    parked = _a_parked_file(first.path)
    registry = discover_engagements(tmp_path)
    assert store.forget(store.connect(), first.path)

    report = status_page.status_report(registry)
    write_status_page(tmp_path, report)

    row = next(run for run in report.runs if run.engagement.path == first.path)
    assert row.statuses == earlier.statuses and row.outstanding == earlier.outstanding
    assert parked in _page(tmp_path)


def test_the_practice_pages_report_asks_each_machine_question_once(tmp_path, samples, monkeypatch):
    """P226: the report reads every return the pass did not run inside one
    reading, as P215 held the parked files - so where the store is and what
    each folder resolves to are asked of the machine once per folder and
    once in all, not once per record read, as P223 counts them."""
    from collections import Counter

    from tracker import hold, settings

    root = tmp_path / "Clients"
    _three_households(root, samples)
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    with hold.one_reading():
        registry = discover_engagements(root)
    asked: Counter = Counter()
    real_resolved, real_data_home = hold.resolved, settings.data_home

    def resolved(path):
        key = ("resolved", str(Path(path)))
        if hold._HELD is None or key not in hold._HELD:
            asked[key] += 1
        return real_resolved(path)

    def data_home():
        if hold._HELD is None or ("data_home",) not in hold._HELD:
            asked["data_home"] += 1
        return real_data_home()

    monkeypatch.setattr(hold, "resolved", resolved)
    monkeypatch.setattr(settings, "data_home", data_home)
    report = status_page.status_report(registry)
    assert len(report.runs) == 3 and not report.errors
    assert asked["data_home"] <= 1, asked
    assert max(asked.values()) == 1, asked


def test_the_practice_page_is_written_after_its_readings_end(tmp_path, samples, monkeypatch):
    """P226 keeps P215's rule: the report and the parked files are read
    inside a reading, and ``status.html`` is written after it ends - a
    write is never made under held answers."""
    from tracker import hold

    root = tmp_path / "Clients"
    _three_households(root, samples)
    held = []
    real = fsio.write_text_atomically

    def write(path, *args, **kwargs):
        if Path(path).name == STATUS_PAGE_FILENAME:
            held.append(hold._HELD is None)
        return real(path, *args, **kwargs)

    for module in (pass_order, status_page):
        monkeypatch.setattr(module, "write_text_atomically", write)
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    assert held == [True]


def test_only_the_practice_page_reads_the_store_without_following_the_journal():
    """R6: a writer or a card that read without following could act on
    rows behind the journal, so ``follow=False`` is passed in the practice
    page (``tracker/status_page.py`` since P346) and in the firm view that
    the API's read-only ``firm`` command builds its rows with
    (``tracker/firm_view.py`` since P344; SPEC-shell 9.2, which counts what
    the page counts) and nowhere else in the package."""
    package = Path(runner_module.__file__).parent
    passing = sorted(one.name for one in package.glob("*.py")
                     if "follow=False" in one.read_text(encoding="utf-8"))
    assert passing == ["firm_view.py", "status_page.py"]


# ------------------------------------------------ the run log: counts and codes ----
# Decision 186: the run log lives in the data home, names no client and no
# file, and says every failure, skip and pass warning by a code.


def _log_line(text: str, head: str) -> dict[str, str]:
    """The last ``counts`` or ``codes`` line of a run log, as key -> value."""
    [*_, line] = [one.strip() for one in text.splitlines() if one.strip().startswith(head + " ")]
    return dict(pair.split("=", 1) for pair in line.split()[1:])


def test_no_run_log_line_contains_a_client_file_name(tmp_path, samples, monkeypatch, capsys):
    """The proof (decision 186): households, returns and dropped files that
    all carry a made-up marker - one file that fails to sort, one slow
    reading, one held reminder and one crashed return - and not one of
    their names, nor the marker, reaches the run log. The console still
    names them all."""
    import errno

    from tracker.intents import FileError

    marker = "Zqxmarker"
    root = tmp_path / "Clients"
    held = build_engagement(root, samples, household=f"{marker} Held Household",
                            name=f"{marker} Held TY2025",
                            drops=(f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf"))
    crashed = build_engagement(root, samples, household=f"{marker} Crash Household",
                               name=f"{marker} Crash TY2025")
    unsorted = build_engagement(root, samples, household=f"{marker} Unsorted Household",
                                name=f"{marker} Unsorted TY2025")
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    make_ambiguous(held.path)
    slow = f"1099-INT {marker} slow.pdf"
    (inbox_of(held.path) / slow).write_bytes((samples / "1099-INT First National.pdf").read_bytes())
    (inbox_of(unsorted.path) / f"W-2 John Smith {YEAR}.pdf").write_bytes(
        (samples / f"W-2 John Smith {YEAR}.pdf").read_bytes())
    refused = f"{marker} bank statement.pdf"
    where = str(crashed.path / f"{marker} a file the disk refused.pdf")
    real_sort, real_file = runner_module._sort_step, runner_module.file_household_drops

    def sort_step(household, sorting, *args, **kwargs):
        if household == household_of(crashed.path):
            raise OSError(errno.EIO, "Input/output error", where)
        return real_sort(household, sorting, *args, **kwargs)

    def file_drops(inbox, originals, *, own, **kwargs):
        reports = real_file(inbox, originals, own=own, **kwargs)
        if unsorted.path in reports:
            reports[unsorted.path].errors.append(FileError(refused, f"{refused} cannot be read", True))
        return reports

    monkeypatch.setattr(runner_module, "_sort_step", sort_step)
    monkeypatch.setattr(runner_module, "file_household_drops", file_drops)
    monkeypatch.setattr(run_log, "SLOW_READING_SECONDS", 0)

    capsys.readouterr()
    assert _the_scheduled_job(root, monkeypatch, "--reminders", "always", "--log") == 1

    said = capsys.readouterr().out
    text = log_path().read_text(encoding="utf-8")
    counts = _log_line(text, "counts")
    assert counts["failed"] == "2" and counts["held"] == "1" and counts["unsorted"] == "1"
    assert _log_line(text, "codes") == {"crashed:OSError": "1", "unsorted-files": "1"}
    names = [held.label, crashed.label, unsorted.label, slow, refused, where,
             f"W-2 John Smith {YEAR}.pdf", "Form 1098 Mortgage Interest.pdf", "C01", DRAFT_FILENAME]
    assert marker not in text
    for name in names:
        assert name not in text, name
    # The console, a person's, still names them.
    for name in (held.label, crashed.label, unsorted.label, slow, refused):
        assert name in said, name


def test_every_failure_and_skip_is_logged_as_a_code(tmp_path, samples, monkeypatch):
    """Decision 186: every place a return's ``error`` or ``skipped`` is set
    sets its code too, and the codes line counts each."""
    import errno
    import shutil
    from dataclasses import replace
    from types import SimpleNamespace

    from tracker.layout import client_household_dir
    from tracker.locking import LOCK_FILENAME

    cases = iter(range(100))

    def one(**kwargs):
        n = next(cases)
        return build_engagement(tmp_path / f"case {n}", samples, household=f"Case {n} Household",
                                name=f"Case {n} TY2025", **kwargs)

    runs = {}
    runs["no-practice"] = run_household(household_of(one().path), [one()], registry=None)[0]
    stopped = one()
    runs["household-stopped"] = a_pass(stopped, registry=SimpleNamespace(
        stopped={household_of(stopped.path): "stopped"}, paused={}))
    paused = one()
    runs["household-paused"] = a_pass(paused, registry=SimpleNamespace(
        stopped={}, paused={household_of(paused.path): "paused"}))
    gone = one()
    a_pass(gone, today=FRIDAY, reminders=REMINDERS_NEVER)       # the household has had its client folder
    shutil.rmtree(client_household_dir(root_of(gone.path), household_of(gone.path).name))
    runs["client-folder-missing"] = a_pass(gone, today=FRIDAY)
    locked = one()
    (locked.path / LOCK_FILENAME).write_text(f"pid={__import__('os').getpid()}", encoding="utf-8")
    runs["lock-held"] = a_pass(locked, today=FRIDAY)
    runs["rolled-forward"] = a_pass(replace(one(), superseded_by="its successor"), today=FRIDAY)
    runs["inactive"] = a_pass(one(active=False), today=FRIDAY)
    runs["folder-missing"] = a_pass(Engagement(path=tmp_path / "no such return"), today=FRIDAY)
    broken = tmp_path / "Broken 2025"
    broken.mkdir()
    ledger.path_for(broken).write_text("this is not a record\n", encoding="utf-8")
    runs["record-unreadable"] = a_pass(Engagement(path=broken), today=FRIDAY)
    with monkeypatch.context() as patch:
        patch.setattr(runner_module, "room_for",
                      lambda *args: SimpleNamespace(parks=0, floor=261, limit=260))
        runs["no-room"] = a_pass(one(), today=FRIDAY)
    with monkeypatch.context() as patch:
        def crash(*args, **kwargs):
            raise OSError(errno.EIO, "Input/output error")
        patch.setattr(runner_module, "_sort_step", crash)
        runs["crashed:OSError"] = a_pass(one(), today=FRIDAY)
    with monkeypatch.context() as patch:
        def refuse(*args, **kwargs):
            raise ManifestError("the list refused")
        patch.setattr(runner_module, "scan_engagement", refuse)
        runs["refused:ManifestError"] = a_pass(one(), today=FRIDAY)
    with monkeypatch.context() as patch:
        from tracker.intents import FileError
        real = runner_module.file_household_drops

        def file_drops(*args, **kwargs):
            reports = real(*args, **kwargs)
            for report in reports.values():
                report.errors.append(FileError("x.pdf", "x.pdf could not be read", True))
            return reports
        patch.setattr(runner_module, "file_household_drops", file_drops)
        runs["unsorted-files"] = a_pass(one(), today=FRIDAY)

    for code, run in runs.items():
        assert run.code == code, (code, run.error or run.skipped)
        assert run.error or run.skipped, code
    text = append_log(tmp_path / LOG_FILENAME,
                      RunReport(today=FRIDAY, runs=list(runs.values()))).read_text(encoding="utf-8")
    assert _log_line(text, "codes") == {code: "1" for code in runs}


def test_every_pass_warning_carries_a_code(tmp_path, samples, monkeypatch):
    """Decision 186: a pass warning is said with its code beside it -
    left behind, the reader's path, a reader that could not start, an
    unreadable pass order - and the codes line counts each."""
    from tracker import content_check, ocr
    from tracker.settings import ENV_SETTINGS_DIR

    settings = tmp_path / "settings"
    settings.mkdir()
    (settings / store.STORE_SHM_FILENAME).write_bytes(b"")          # left by an earlier version
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setattr(ocr, "reader_path_warning", lambda: ocr.READER_PATH_WARNING)
    asked = []
    monkeypatch.setattr(content_check, "readers_that_could_not_start",
                        lambda: asked.append(1) or (["one.pdf"] if len(asked) > 1 else []))
    hint = store.store_path().parent / pass_order.PASS_ORDER_FILENAME
    hint.parent.mkdir(parents=True, exist_ok=True)
    hint.write_text("not the hint", encoding="utf-8")
    smith = build_engagement(tmp_path / "Clients", samples)

    report = run_registry(Registry(source=tmp_path / "Clients", engagements=[smith]), today=FRIDAY,
                          reminders=REMINDERS_NEVER)

    assert len(report.warning_codes) == len(report.warnings) == 4
    assert sorted(report.warning_codes) == sorted([
        run_log.CODE_LEFT_BEHIND, run_log.CODE_READER_PATH_WARNING,
        run_log.CODE_ORDER_HINT_UNREADABLE, run_log.CODE_READER_COULD_NOT_START])
    text = append_log(tmp_path / LOG_FILENAME, report).read_text(encoding="utf-8")
    assert _log_line(text, "codes") == {code: "1" for code in report.warning_codes}
    assert "one.pdf" not in text


def test_a_pass_warning_is_added_only_with_its_code():
    """The guard (decision 186): nothing in the runner adds a pass warning
    but ``_warn``, so none can reach the page without its code in the log.
    ``_warn`` is found by its name and every module of the package is read
    (R3.1), so a part of the pass that leaves runner.py is still held."""
    adds = re.compile(r"\b(?:report|result)\.warnings\.(?:append|extend|insert)\(")
    warn = py_function("_warn", "run_log")
    found = sum(len(adds.findall(path.read_text(encoding="utf-8"))) for path in sorted(PACKAGE.rglob("*.py")))
    assert found == len(adds.findall(warn))                     # every one of them is inside _warn
    assert re.search(r"report\.warnings\.append\(", warn)


def test_the_run_log_lives_in_the_data_home_when_the_flag_names_no_file(tmp_path, samples, monkeypatch,
                                                                        capsys):
    from tracker.settings import data_home

    root = tmp_path / "Clients"
    build_engagement(root, samples)

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0

    assert log_path().is_file() and log_path().parent.parent == data_home()
    assert not (root / LOG_FILENAME).exists()
    assert list(root.rglob(f"{LOG_FILENAME}*")) == []
    capsys.readouterr()


def test_a_pass_with_no_data_home_says_so_on_the_page_and_exits_non_zero(tmp_path, samples, monkeypatch,
                                                                       capsys):
    """Decision 186's review, S1 (security principle 6): no data home means
    no store and no run log, so nothing is filed - but the pass is never
    silent. The page in the clients root carries the sentence as its one
    problem, and the exit is non-zero with the same sentence."""
    from tracker.runner import DATA_FOLDER_PROBLEM
    from tracker.settings import DATA_HOME_NOT_ABSOLUTE, ENV_DATA_HOME, ENV_SETTINGS_DIR, set_clients_root

    root = tmp_path / "Clients"
    engagement = build_engagement(root, samples)
    settings = tmp_path / "settings"
    settings.mkdir()
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(root)
    (root / STATUS_PAGE_FILENAME).write_text("yesterday's green page", encoding="utf-8")
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")
    sentence = DATA_FOLDER_PROBLEM.format(problem=DATA_HOME_NOT_ABSOLUTE.format(value="relative-data"))

    with pytest.raises(SystemExit) as stopped:
        main([SETTINGS_FLAG, str(settings), "--reminders", REMINDERS_NEVER, "--log"])

    assert stopped.value.code == sentence
    page = (root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8")
    assert html.escape(sentence) in page
    assert (inbox_of(engagement.path) / f"W-2 John Smith {YEAR}.pdf").is_file()   # nothing filed
    capsys.readouterr()


def test_a_pass_with_no_data_home_writes_no_page_in_a_root_the_rule_refuses(tmp_path, monkeypatch, capsys):
    """The page is never written anywhere a pass would not walk: a typed
    root the rule refuses (here, one holding the settings folder) gets no
    page, and the pass still exits with the sentence."""
    from tracker.settings import ENV_DATA_HOME, ENV_SETTINGS_DIR

    root = tmp_path / "Clients"
    settings = root / "settings"
    settings.mkdir(parents=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    monkeypatch.setenv(ENV_DATA_HOME, "relative-data")

    with pytest.raises(SystemExit) as stopped:
        main([str(root), "--reminders", REMINDERS_NEVER])

    assert "Data folder problem" in str(stopped.value.code)
    assert not (root / STATUS_PAGE_FILENAME).exists()
    capsys.readouterr()


def test_a_relative_log_file_is_refused_before_the_pass(tmp_path, samples, monkeypatch, capsys):
    from tracker.runner import LOG_NOT_ABSOLUTE

    root = tmp_path / "Clients"
    engagement = build_engagement(root, samples)
    monkeypatch.chdir(tmp_path)

    with pytest.raises(SystemExit) as stopped:
        _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log", "mine.log")

    assert stopped.value.code == 2
    assert LOG_NOT_ABSOLUTE.format(log="mine.log") in capsys.readouterr().err
    assert (inbox_of(engagement.path) / f"W-2 John Smith {YEAR}.pdf").is_file()   # nothing filed
    assert not (tmp_path / "mine.log").exists() and not log_path().exists()


# ------------------------------------- the firm view's cache, filled (P201) ----


def test_the_pass_fills_the_firm_cache_with_the_apps_own_summary(tmp_path, samples, monkeypatch, capsys):
    """P201 (``pilot/SPEC-firm-cache-fill.md`` R1-R3): the scheduled job's
    line ends by asking the app's own firm summary, in a child, so the
    cache in the data folder is whole under today's head for the saved
    root when the pass returns - and nothing of the reply reaches the
    console or the run log."""
    from tests.plugin_fakes import REAL_FILL
    from tracker import door, firm_cache

    root = tmp_path / "Clients"
    build_engagement(root, samples, drops=())
    monkeypatch.setattr(runner_module, "fill_firm_cache", REAL_FILL)
    assert not firm_cache.cache_path().exists()

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0
    head = firm_cache.head(str(door.checked_root(None)), dt.date.today())
    assert firm_cache.holds(firm_cache.cache_path(), [head])
    assert '"returns"' not in capsys.readouterr().out
    assert run_log.CODE_CACHE_NOT_FILLED not in log_path().read_text(encoding="utf-8")


def test_the_fill_asks_for_the_apps_own_firm_command():
    """R1: the command is named once in the runner and held to the API's
    table, so a renamed command cannot leave every pass asking for one that
    is gone - and it is a reading command, which writes no client tree."""
    from tracker import api

    assert runner_module.FIRM_COMMAND in api.COMMANDS
    assert runner_module.FIRM_COMMAND in api.HELD_READING_COMMANDS


def _warm_cache_for_today() -> None:
    """The firm view's cache as the summary leaves it: whole, under today's
    head for the saved root, keeping nothing. The head carries the settings
    file as it stands, so it is written after the settings are."""
    from tracker import door, firm_cache

    firm_cache.save(firm_cache.cache_path(), firm_cache.head(str(door.checked_root(None)), dt.date.today()), {})


def _run_now_warm(root, household, monkeypatch, capsys) -> tuple[int, list[dict]]:
    """:func:`_run_now` with the cache warm for today: the settings saved
    first, the cache written under their head, then Run now's own line -
    which writes no setting, so the head still holds."""
    from tracker.runner import run_now_arguments

    settings = _settings_for(root, monkeypatch)
    _warm_cache_for_today()
    capsys.readouterr()
    code = main(run_now_arguments(settings, household))
    return code, _lines(capsys.readouterr().out)


def test_a_sort_leaves_the_overview_to_the_app(tmp_path, samples, monkeypatch, capsys, fills_asked):
    """P218 (S1; Jason, 2026-10-08): a person's Sort never asks the summary,
    cold cache or warm - the app asks the Overview the moment the Sort
    ends, and that reply fills the cache as every Overview does. No pass
    warning either way."""
    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    code, said = _run_now(root, household_of(engagement.path), monkeypatch, capsys)
    assert code == 0 and said[-1]["pass_warnings"] == []
    assert fills_asked == []

    code, said = _run_now_warm(root, household_of(engagement.path), monkeypatch, capsys)
    assert code == 0 and said[-1]["pass_warnings"] == []
    assert fills_asked == [], "a warm cache: still the app's Overview to fill"


def test_the_scheduled_pass_fills_the_whole_firm_on_a_cold_cache(tmp_path, samples, monkeypatch, fills_asked):
    """SHOULD-3's other half: the scheduled pass fills whether or not the
    cache holds today's head - its fill is how the first Overview of the
    day is warm."""
    from tracker import door, firm_cache

    root = tmp_path / "Clients"
    build_engagement(root, samples)
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) == 0
    assert not firm_cache.cache_path().exists()
    assert fills_asked == [(str(door.checked_root(None)), "")]


def test_a_pass_a_person_stopped_does_not_fill(tmp_path, samples, monkeypatch, capsys, fills_asked):
    """The engine review's SHOULD-1, ruled "Stop means stop": a stopped pass
    ends without asking the summary, even while the cache is warm, so Stop
    does not wait for it; the next Overview fills the cache as before P201."""
    root = tmp_path / "root"
    engagement = build_engagement(root, samples)
    real = runner_module.run_registry

    def stopped(*args, report, **kwargs):
        real(*args, report=report, **kwargs)
        for run in report.runs:
            run.cancelled = True

    monkeypatch.setattr(runner_module, "run_registry", stopped)
    _code, said = _run_now_warm(root, household_of(engagement.path), monkeypatch, capsys)
    assert said[-1]["runs"][0]["cancelled"] is True
    assert fills_asked == []
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER) in (0, 1)
    assert fills_asked == [], "the scheduled pass, stopped, does not fill either"
    capsys.readouterr()


def test_the_fill_runs_after_the_run_log_line_and_the_page_are_written(tmp_path, samples, monkeypatch, capsys):
    """The engine review's NIT-4, ruled: the fill can run long, so it is
    asked only once the pass's own record - its run log line and its page -
    is written, and a fill stopped by anything cannot cost the pass that."""
    root = tmp_path / "Clients"
    build_engagement(root, samples)
    seen = {}

    def fill(where, *, product=""):
        seen["logged"] = "    counts " in log_path().read_text(encoding="utf-8")
        seen["page"] = bool(_page(root))
        return ""

    monkeypatch.setattr(runner_module, "fill_firm_cache", fill)
    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0
    assert seen == {"logged": True, "page": True}
    capsys.readouterr()


def test_a_dry_run_a_typed_root_and_an_unproved_checkpoint_do_not_fill(
        tmp_path, samples, monkeypatch, capsys, fills_asked):
    """R4: a dry run writes nothing, this included; a root typed on the
    command line is not the one the summary answers for; a pass that could
    prove no household against the record checkpoint served none."""
    from tracker import checkpoint

    root = tmp_path / "Clients"
    build_engagement(root, samples)
    assert _the_scheduled_job(root, monkeypatch, "--dry-run") == 0
    main([str(root), "--reminders", REMINDERS_NEVER])
    assert fills_asked == []

    def unreadable(*args, **kwargs):
        raise checkpoint.CheckpointError("the checkpoint could not be opened")

    monkeypatch.setattr(runner_module.store, "prove_the_root", unreadable)
    _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER)
    assert fills_asked == []
    capsys.readouterr()


def test_a_fill_that_fails_is_a_pass_warning_and_never_the_exit_code(tmp_path, samples, monkeypatch, capsys):
    """R5: said loudly - on the page, as its code in the run log, in Run
    now's final line - and never fatal: the cache only makes the next
    Overview faster."""
    from tracker.run_log import CODE_CACHE_NOT_FILLED
    from tracker.runner import CACHE_NOT_FILLED, FILL_STOPPED

    why = FILL_STOPPED.format(code=3)
    monkeypatch.setattr(runner_module, "fill_firm_cache", lambda root, product="": why)
    root = tmp_path / "root"
    engagement = build_engagement(root, samples)

    assert _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, "--log") == 0
    assert f"{CODE_CACHE_NOT_FILLED}=1" in log_path().read_text(encoding="utf-8")
    assert CACHE_NOT_FILLED.format(why=why) in _page(root)
    assert CACHE_NOT_FILLED.format(why=why) in capsys.readouterr().out

    # A Sort asks no fill (P218), so it has none to fail.
    code, said = _run_now_warm(root, household_of(engagement.path), monkeypatch, capsys)
    assert code == 0 and said[-1]["pass_warnings"] == []


@pytest.mark.parametrize("ending", ["no start", "stopped", "too long", "not kept"])
def test_each_reason_a_fill_fails_is_said_by_its_kind(tmp_path, monkeypatch, ending):
    """R5: the four reasons, each by kind and never a client's words: the
    child could not start, stopped with a code, ran past its limit, or
    finished without leaving the cache whole under today's head."""
    import subprocess

    from tests.plugin_fakes import REAL_FILL
    from tracker.runner import (
        FILL_NOT_KEPT,
        FILL_NOT_STARTED,
        FILL_STOPPED,
        FILL_TIME_LIMIT_SECONDS,
        FILL_TOO_LONG,
    )

    def child(command, **kwargs):
        if ending == "no start":
            raise FileNotFoundError(2, "No such file", str(tmp_path / "a client's folder"))
        if ending == "too long":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        return subprocess.CompletedProcess(command, 2 if ending == "stopped" else 0)

    monkeypatch.setattr(runner_module.subprocess, "run", child)
    said = REAL_FILL(str(tmp_path))
    assert said == {"no start": FILL_NOT_STARTED.format(kind="FileNotFoundError (ENOENT)"),
                    "stopped": FILL_STOPPED.format(code=2),
                    "too long": FILL_TOO_LONG.format(minutes=FILL_TIME_LIMIT_SECONDS // 60),
                    "not kept": FILL_NOT_KEPT}[ending]
    assert "a client's folder" not in said


def test_the_product_name_reaches_the_fill_and_never_the_page(tmp_path, samples, monkeypatch, capsys,
                                                              fills_asked):
    """R6: the packaged schedule names the product so the fill's child can
    import the API; the runner hands it to that child alone - its own
    environment, and so the page's heading, are as they were."""
    import os
    import subprocess

    from tests.plugin_fakes import REAL_FILL
    from tracker.runner import PRODUCT_FLAG
    from tracker.settings import ENV_PRODUCT_NAME

    monkeypatch.delenv(ENV_PRODUCT_NAME, raising=False)
    root = tmp_path / "Clients"
    build_engagement(root, samples)
    _the_scheduled_job(root, monkeypatch, "--reminders", REMINDERS_NEVER, PRODUCT_FLAG, "Named Product")
    assert [product for _root, product in fills_asked] == ["Named Product"]
    assert ENV_PRODUCT_NAME not in os.environ
    assert "Named Product" not in _page(root)

    seen = {}

    def child(command, **kwargs):
        seen.update(command=command, env=kwargs["env"],
                    streams={kwargs[name] for name in ("stdin", "stdout", "stderr")})
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(runner_module.subprocess, "run", child)
    REAL_FILL(str(root), product="Named Product")
    assert seen["env"][ENV_PRODUCT_NAME] == "Named Product"
    assert seen["command"][-1] == runner_module.FIRM_COMMAND
    assert seen["streams"] == {subprocess.DEVNULL}, "the reply names clients; none of it is kept"
    capsys.readouterr()


# ------------------------------- the pass's two firm-wide reads (P215) ----


def test_the_passs_discovery_and_its_page_read_hold_the_machines_answers(tmp_path, samples, monkeypatch):
    """P215 (findings-1 #1): discovery and the practice page's parked-file
    read only read, so each runs inside a reading - the machine's answers
    held for the call, and dropped when it returns."""
    from tracker import hold

    _two_households(tmp_path, samples)
    seen = {}
    for module, name in ((runner_module, "discover_engagements"), (status_page, "_parked_files")):
        real = getattr(module, name)

        def watched(*args, _real=real, _name=name, **kwargs):
            seen[_name] = hold._HOLDING
            return _real(*args, **kwargs)

        monkeypatch.setattr(module, name, watched)
    assert _the_scheduled_job(tmp_path, monkeypatch, "--reminders", "never") == 0
    assert seen == {"discover_engagements": hold.HOLD_READING, "_parked_files": hold.HOLD_READING}
    assert hold._HELD is None


def test_the_page_is_written_outside_the_reading(tmp_path, samples, monkeypatch):
    """Only the read is held: the page's write follows the hold's end, so a
    write inside it can never be refused as a write while reading."""
    from tracker import hold

    _two_households(tmp_path, samples)
    holding = []
    real = fsio.write_text_atomically

    def watched(path, *args, **kwargs):
        if Path(path).name == STATUS_PAGE_FILENAME:
            holding.append(hold._HOLDING)
        return real(path, *args, **kwargs)

    for module in (pass_order, status_page):
        monkeypatch.setattr(module, "write_text_atomically", watched)
    assert _the_scheduled_job(tmp_path, monkeypatch, "--reminders", "never") == 0
    assert holding == [""]
    assert (tmp_path / STATUS_PAGE_FILENAME).is_file()


# ------------------------------------------ the pass-order hint (P217) ----


def _whole_writes_of_the_hint(monkeypatch, *, refuse: bool = False) -> list[Path]:
    """Every whole write of the hint from here on; ``refuse`` makes each fail."""
    writes = []
    real = fsio.write_text_atomically

    def watched(path, *args, **kwargs):
        if Path(path).name == pass_order.PASS_ORDER_FILENAME:
            writes.append(Path(path))
            if refuse:
                raise PermissionError(13, "fabricated: the file is held")
        return real(path, *args, **kwargs)

    for module in (pass_order, status_page):
        monkeypatch.setattr(module, "write_text_atomically", watched)
    return writes


def test_each_household_start_is_one_appended_line_and_the_hint_is_written_once_a_pass(
        tmp_path, samples, monkeypatch):
    _three_households(tmp_path, samples)
    run_registry(discover_engagements(tmp_path), today=FRIDAY)          # settles the hint
    path = _hint_file()
    assert len(_hint_lines(path)) == 1
    writes = _whole_writes_of_the_hint(monkeypatch)
    seen = []
    real = runner_module.run_household

    def watched(household, *args, **kwargs):
        lines = _hint_lines(path)
        seen.append((household.name, len(lines), json.loads(lines[-1])))
        return real(household, *args, **kwargs)

    monkeypatch.setattr(runner_module, "run_household", watched)
    run_registry(discover_engagements(tmp_path), today=FRIDAY)

    assert [count for _name, count, _last in seen] == [2, 3, 4]
    for name, _count, last in seen:
        assert set(last) == {"started", "household"} and last["household"] == name
    assert writes == [path]                                              # once, at the end
    (whole,) = _hint_lines(path)
    assert json.loads(whole)["version"] == pass_order.PASS_ORDER_VERSION == 2


def test_a_pass_killed_in_a_household_leaves_its_mark_and_the_next_pass_puts_it_last(
        tmp_path, samples, monkeypatch):
    """Decision 189's crash mark still lands before the household's work:
    the pass killed in Birch leaves Alder's and Birch's marks after line 1,
    and the next pass folds them, takes the household never started first,
    and settles the file to one line again."""
    _three_households(tmp_path, samples)
    path = _hint_file()
    real = runner_module.run_household

    def killed_in_birch(household, *args, **kwargs):
        if household.name == "Birch Household":
            raise SystemExit("killed")
        return real(household, *args, **kwargs)

    with monkeypatch.context() as patched:
        patched.setattr(runner_module, "run_household", killed_in_birch)
        with pytest.raises(SystemExit):
            run_registry(discover_engagements(tmp_path), today=FRIDAY)
    lines = _hint_lines(path)
    assert [json.loads(line)["household"] for line in lines[1:]] == ["Alder Household", "Birch Household"]

    taken = households_in_order(monkeypatch)
    run_registry(discover_engagements(tmp_path), today=FRIDAY)
    assert taken[0] == "Cedar Household" and taken[-1] in ("Alder Household", "Birch Household")
    assert len(_hint_lines(path)) == 1


def test_an_earlier_versions_hint_is_read_and_settled_before_the_first_mark(tmp_path, samples, monkeypatch):
    _three_households(tmp_path, samples)
    path = _hint_file()
    path.write_text(json.dumps({"version": 1, "households": {
        "Alder Household": {"completed": "2026-03-13T09:00:00", "not_served": 0},
        "Birch Household": {"completed": "2026-03-12T09:00:00", "not_served": 0}}}, indent=2),
        encoding="utf-8")
    seen = []
    real = runner_module.run_household

    def watched(household, *args, **kwargs):
        seen.append(_hint_lines(path))
        return real(household, *args, **kwargs)

    monkeypatch.setattr(runner_module, "run_household", watched)
    report = run_registry(discover_engagements(tmp_path), today=FRIDAY)

    assert pass_order.ORDER_HINT_UNREADABLE not in report.warnings
    first, mark = seen[0]
    settled = json.loads(first)
    assert settled["version"] == 2
    assert settled["households"]["Birch Household"]["completed"] == "2026-03-12T09:00:00"
    assert json.loads(mark)["household"] == "Cedar Household"            # never completed: first


def test_a_hint_that_cannot_be_settled_takes_no_marks(tmp_path, samples, monkeypatch):
    """A mark appended to an earlier version's file would make it
    unreadable: when the settling write fails, no mark is appended this
    pass, and the end-of-pass write is still tried."""
    _three_households(tmp_path, samples)
    path = _hint_file()
    before = json.dumps({"version": 1, "households": {}}, indent=2)
    path.write_text(before, encoding="utf-8")
    writes = _whole_writes_of_the_hint(monkeypatch, refuse=True)

    run_registry(discover_engagements(tmp_path), today=FRIDAY)

    assert writes == [path, path]                     # the settling write, then the end's
    assert path.read_text(encoding="utf-8") == before
