"""Tests for tracker/status_page.py - the practice status page in the clients
root: every engagement with what it owes, every file waiting for a person,
everything that failed and every folder the walk left alone.

Most of what the module promises is held by tests/test_runner.py and the test_runner_<family> files split from it
(SPEC-architecture-p5 P5.14), whose tests
run a pass and read the page it left: the review queue newest first with its
reasons, the held and approved Drafted cell, the records that need a person
named every pass and never deleted, the page read from the store the walk
left and written after its readings end, the page written even when a
return's pass failed, and the folders left alone at its end. None of them
moved here by the SPEC's rule, because each runs a pass or the runner's
command line. The seven tests below moved here from tests/test_runner.py
(SPEC-architecture-p5 R5.9.8, P346), byte for byte: each calls the page's
writer, its report or its Drafted cell directly, with the pass's report
records at most, and nothing that stayed in the runner. A read through
``tracker.runner`` of a name the runner imports back (``status_report``) is
kept as it was, until SPEC-architecture-p5 P5.16 retargets every such read
to its home; a read of a name the runner no longer holds reads
``tracker.status_page``, and a stand-in sits on every module that reads its
name (SPEC-architecture-p5 section 4.0). Made-up households only.
"""

import html

from tests import passes
from tests.builders import make_engagement, seed_index
from tests.passes import FRIDAY, _page, _two_households, build_engagement
from tests.samples import DEMO_ITEMS
from tracker import status_page, store
from tracker.index import NEEDS_REVIEW
from tracker.records import IndexEntry
from tracker.registry import Engagement, discover_engagements
from tracker.reminder import DRAFT_FILENAME
from tracker.run_log import STAGE_NOTE, EngagementRun, RunReport
from tracker.status_page import RECORD_UNREADABLE, STATUS_HELD, write_status_page

#: The sample pile, built once per session: a fixture of ``tests/passes.py``, named here
#: so every claim below can ask for it.
samples = passes.samples


def test_a_file_named_like_markup_is_shown_as_a_name_not_rendered(tmp_path):
    """Every value on the page goes through html.escape. The name cannot be
    made on Windows, so it arrives the way it would in life: an index row
    written elsewhere, from a client's folder that is not this machine's."""
    folder = make_engagement(tmp_path, DEMO_ITEMS, return_name="Evil TY2025", scaffold=False)
    name = "<b>evil</b>.pdf"
    reason = "<i>nothing matched</i>"
    seed_index(folder, [IndexEntry(
        received=FRIDAY.isoformat(), original_name=name, size_kb=1.0, digest="0" * 64,
        identifier="", prepared_location="",
        pbc_location=f"../../../../Clients/Test Household/2025/{name}",
        decision=NEEDS_REVIEW, reason=reason,
    )])

    report = RunReport(today=FRIDAY, runs=[EngagementRun(engagement=Engagement(path=folder))])
    text = write_status_page(tmp_path, report).read_text(encoding="utf-8")

    assert name not in text and reason not in text
    assert "&lt;b&gt;evil&lt;/b&gt;.pdf" in text
    assert "&lt;i&gt;nothing matched&lt;/i&gt;" in text


def test_the_page_still_has_a_heading_where_nothing_can_say_what_the_product_is_called(
    tmp_path, monkeypatch
):
    """The packaged app's scheduled job runs without the Electron shell, which
    is the only thing that knows the product's name there. A pass that has
    already moved the client's files must not end in a traceback over a
    heading, so the firm's name - and then the folder - stand in."""
    from tracker.settings import SettingsError

    def unknown():
        raise SettingsError("no shell, no package.json")

    folder = tmp_path / "Clients"
    folder.mkdir()
    report = RunReport(today=FRIDAY, runs=[])

    monkeypatch.setattr("tracker.status_page.product_name", unknown)
    monkeypatch.setattr("tracker.status_page.firm", lambda: "J Park & Associates, CPA")
    assert "J Park &amp; Associates, CPA" in write_status_page(folder, report).read_text(encoding="utf-8")

    monkeypatch.setattr("tracker.status_page.firm", lambda: "")
    assert folder.name in write_status_page(folder, report).read_text(encoding="utf-8")


def test_the_practice_page_says_approved_where_it_would_say_the_stage(tmp_path, samples):
    """One column, one answer per engagement: held, then approved, then the
    rung the letter was written at."""
    from tracker.reminder import APPROVED_NOTE
    from tracker.status_page import _drafted_cell

    engagement = build_engagement(tmp_path, samples)
    run = EngagementRun(engagement=engagement, drafted=engagement.path / DRAFT_FILENAME, stage=3)
    assert _drafted_cell(run) == STAGE_NOTE.format(n=3)
    run.approved = True
    assert _drafted_cell(run) == APPROVED_NOTE
    run.held = 2
    assert _drafted_cell(run) == STATUS_HELD.format(n=2)
    assert APPROVED_NOTE in run.summary()


def test_one_unreadable_record_costs_one_row_of_the_page(tmp_path, samples, monkeypatch):
    import tracker.runner as runner
    from tracker.ledger import RecordNotWritten
    from tracker.status_page import status_report

    first, second = _two_households(tmp_path, samples)
    real = runner.load_manifest

    def unreadable_first(folder, *args, **kwargs):
        if folder == first.path:
            raise RecordNotWritten("EACCES")
        return real(folder, *args, **kwargs)

    for module in (runner, status_page):
        monkeypatch.setattr(module, "load_manifest", unreadable_first)
    report = status_report(discover_engagements(tmp_path))
    write_status_page(tmp_path, report)

    by_label = {run.engagement.label: run for run in report.runs}
    assert by_label[first.label].error == RECORD_UNREADABLE.format(
        problem="RecordNotWritten (EACCES)")
    assert by_label[second.label].ok and not by_label[second.label].error
    assert second.label in _page(tmp_path)


def test_a_record_the_disk_refuses_is_said_by_its_class_and_code_never_its_path(
        tmp_path, samples, monkeypatch):
    """The page's per-row error names the class and the errno's code, never
    the operating system's message, which names the record's path - a
    client's folder (security principle 7; the review's S2)."""
    import errno

    import tracker.runner as runner
    from tracker.status_page import status_report

    engagement = build_engagement(tmp_path, samples)
    where = str(engagement.path / "journal.jsonl")

    def refused(folder, *args, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied", where)

    for module in (runner, status_page):
        monkeypatch.setattr(module, "load_manifest", refused)
    report = status_report(discover_engagements(tmp_path))
    write_status_page(tmp_path, report)

    [row] = report.runs
    assert row.error == RECORD_UNREADABLE.format(problem="PermissionError (EACCES)")
    assert where not in _page(tmp_path) and engagement.path.name not in row.error


def test_lines_from_other_machines_that_cannot_be_listed_are_said_where_they_would_be(
        tmp_path, samples, monkeypatch):
    """SF3: a checkpoint that fails only when asked for the lines from other
    machines leaves a sentence in their place on the page, never nothing."""
    from tracker import checkpoint

    clients = tmp_path / "Clients"
    build_engagement(clients, samples)

    def unlisted():
        raise checkpoint.CheckpointUnavailable("record-heads.db", "SQLITE_IOERR_READ")

    monkeypatch.setattr(store, "foreign_lines", unlisted)
    report = status_page.status_report(discover_engagements(clients))
    page = html.unescape(write_status_page(clients, report).read_text(encoding="utf-8"))
    assert "Lines from other machines could not be listed this pass: record-heads.db" in page
    assert "SQLITE_IOERR_READ" in page


def test_an_index_the_page_cannot_read_is_said_by_its_class_never_its_message(
        tmp_path, samples, monkeypatch):
    """R7: the page's unreadable-index sentence names the class and the
    errno's code - an OSError's message names a client's folder (security
    principle 7)."""
    import errno

    engagement = build_engagement(tmp_path, samples)
    where = str(engagement.path / "somewhere private")

    def refused(folder, *args, **kwargs):
        raise PermissionError(errno.EACCES, "Permission denied", where)

    monkeypatch.setattr(status_page, "read_index", refused)
    write_status_page(tmp_path, status_page.status_report(discover_engagements(tmp_path)))

    page = _page(tmp_path)
    assert status_page.STATUS_INDEX_UNREADABLE.format(
        label=engagement.label, error="PermissionError (EACCES)") in page
    assert where not in page
