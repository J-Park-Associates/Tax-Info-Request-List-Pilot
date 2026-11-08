"""The practice status page: every engagement, every file waiting for a
person and everything that failed, on one page in the clients root.

Each part upholds the decision rows it names:

- **A page, not a workbook** (decisions 75 and 91). :func:`write_status_page`
  writes :data:`STATUS_PAGE_FILENAME` into the clients root at the end of
  every real pass: a row per engagement, the practice's review queue newest
  first, the problems, the count each inbox left alone by name and the
  folders the walk left alone (decision 125). Every word the page shows
  that is not data is worded here, and every value goes through
  ``tracker.page.esc``: a document called like a tag is shown as its name.
- **Drawn from a report, never from a lock** (decisions 189 and 192).
  :func:`status_report` folds the runs a pass made into every engagement
  the walk found and reads the rest - each record and index as the store
  holds them after the walk, never following a journal again - with no
  lock and nothing written, inside a reading (pilot P215, P226). So the
  page can be drawn as often as anyone likes, and drawing it never changes
  what it describes. One record that will not read costs its own row
  (:func:`_engagement_status`), said by its class and code, never its
  message, which can name a client's folder.
- **The records that need a person, first** (decision 159).
  :func:`records_needing_a_person` lists the copies beside a record or a
  lock and the lines from another machine not yet acknowledged, and says
  when those lines could not be listed (:data:`FOREIGN_UNLISTED`); the page
  draws them before the counts, and only when there is one.
- **Kept rows** (pilot P227). Handed the page's kept rows
  (``tracker.page_rows``), a return whose record's token has not moved is
  drawn from what was kept under it - exactly what a fresh read would give.
- **Nothing fetched, and written whole** (decisions 190 and 155). The head
  is ``tracker.page.document``'s, given the page's own style
  (:data:`_STATUS_STYLE`), so its policy is computed from the very style
  the page writes: no script, no style sheet, nothing fetched when it is
  opened, because a page naming the firm's clients must not reach the
  network to render. It is written through ``fsio.write_text_atomically``,
  so a pass killed half way leaves the last page whole.

**Where it came from** (SPEC-architecture-p5 P5.9, P346; the architecture
audit's C-5 and C-6). Moved byte for byte out of ``tracker.runner``, with
its words and comments; the runner imports back by name what its own code
still reads - the page's writer and its report, the records that need a
person, the page's file name, the misfits heading
``tracker.runner.format_report`` prints at the end of a pass, and
:data:`RECORD_UNREADABLE`, which the pass's own pre-checks say too.
``tracker.runner.CHECKPOINT_NOT_PROVED`` stayed there: only the pass says
it. :data:`STATUS_MISFITS_HEADING` is also the heading the app's household
screen shows over the same folders: the API imports it from here rather
than typing the same words a second time (C-6), so the page and the screen
cannot drift apart.

**Why it sits at layer 3.** It imports the pass's report records
(``tracker.run_log``), the registry and the reminder's two approval words
(layer 3, its own layer), the store, the index, the manifest, the record
types and the ledger (layer 1), and ``page``, ``page_rows``, ``hold``,
``checkpoint``, ``fsio``, ``errors``, ``layout`` and ``settings`` (layer 0).
It imports neither ``scheduling`` nor the API (P313), nor the runner, which
imports it, nor :mod:`tracker.screen_words`: the scheduled pass loads this
module, and ``tests/test_layers.py`` keeps the product's name, which that
pass is not given (P220), out of everything it loads. The page asks for
the product's name only when it draws its title, and falls back to the
firm's name and then the folder's.

It logs as ``tracker.runner`` (``logging.getLogger("tracker.runner")``), the
name its lines have always carried: the error log prints each line's logger
name, so a new one would change lines a person reads (P331's rule;
SPEC-architecture-p5 section 2.1).
"""

from __future__ import annotations

import datetime as dt
import logging
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path

from tracker import checkpoint, errors, ledger, page_rows, store
from tracker.fsio import write_text_atomically
from tracker.hold import one_reading
from tracker.index import NEEDS_REVIEW, read_index
from tracker.layout import parts_below
from tracker.ledger import LedgerError
from tracker.manifest import ManifestError, load_manifest, summarize
from tracker.page import document, esc, page_text, table
from tracker.records import YES
from tracker.registry import Engagement, Registry
from tracker.reminder import APPROVED_NOTE, APPROVED_THEN_EDITED
from tracker.run_log import (
    CODE_RECORD_UNREADABLE,
    IGNORED_NOTE,
    STAGE_NOTE,
    EngagementRun,
    RunReport,
    why_skipped,
)
from tracker.settings import SettingsError, firm, product_name
from tracker.store import StoreError

log = logging.getLogger("tracker.runner")


#: The firm-wide status page, written into the clients root at the end of
#: every real pass. The log is the machine's trace of one run; this is the
#: standing answer to what the practice owes and what needs a person.
STATUS_PAGE_FILENAME = "status.html"


#: Why an engagement cannot be run at all - worded once, as why one is
#: passed over is (:data:`tracker.run_log.SKIP_INACTIVE`), because the pass
#: and the status page must agree about the same engagement.
RECORD_UNREADABLE = "the record could not be read: {problem}"


def records_needing_a_person(
        registry: Registry) -> tuple[list[Path], list[checkpoint.Foreign], list[str]]:
    """The copies beside every household's and every return's record and
    lock, the lines from another machine not yet acknowledged (decision
    159, §4.4), and - when the checkpoint cannot be read - the sentence
    that says those lines could not be listed (:data:`FOREIGN_UNLISTED`;
    the rebase review's SF3), so they never vanish from the page in
    silence. Reads only: a copy is never deleted, moved or renamed, because
    the tracker cannot know which one is right."""
    folders = [household.path for household in registry.households]
    folders += [engagement.path for engagement in registry.engagements]
    siblings = [copy for folder in folders for copy in ledger.siblings(folder)]
    try:
        return siblings, store.foreign_lines(), []
    except Exception as exc:
        # Nothing may stop a pass before its first household (decision
        # 189): the pass goes on, and the page says why the lines from
        # other machines are not listed.
        errors.keep("runner", exc, name="record checkpoint")
        log.warning("Could not read the record checkpoint (%s)", errors.error_class(exc))
        # Spelled inline, not through tracker.runner.checkpoint_said(): tests/test_errors.py's
        # static guard knows errors.said() alone as the one sanitizer of an
        # exception's words (decision 190).
        return siblings, [], [FOREIGN_UNLISTED.format(why=errors.said(exc, (checkpoint.CheckpointError,)))]


# ------------------------------------------------------------- status page ----

#: Every word the page shows that is not data. A person reads this page and
#: nothing else does, so the sentences are worded here rather than buried in
#: the markup that renders them.
STATUS_GENERATED = "Generated {stamp}"
STATUS_ENGAGEMENTS_HEADING = "Engagements"
STATUS_REVIEW_HEADING = "Waiting for a person"
STATUS_PROBLEMS_HEADING = "Problems"
STATUS_NOTHING_PARKED = "Nothing is waiting for a person."
STATUS_NO_PROBLEMS = "Nothing failed."
#: The folders the walk left alone (decision 125), and what is said when
#: there are none. The sentence on each is the registry's; this is only the
#: heading a person reads and the two columns it is drawn in.
STATUS_MISFITS_HEADING = "Folders the App Leaves Alone"
STATUS_NO_MISFITS = "Every folder fits the layout."
MISFIT_COLUMNS = ("Folder", "Why it is left alone")
#: What the last-pass cell says for an engagement the page read rather than ran.
STATUS_NOT_PASSED = "not this pass"
#: What the Drafted cell says for an engagement whose reminder is held (decision 115).
STATUS_HELD = "held ({n})"
STATUS_INDEX_UNREADABLE = "{label}: the index could not be read ({error})"
#: Records that need a person (decision 159, §4.4): drawn first, before the
#: counts, and only when there is one - on a good day there is nothing.
STATUS_RECORDS_HEADING = "Records that need a person"
RECORD_SIBLING = ("{path}: a copy beside a record or its lock, left by a sync client or a second "
                  "machine. The app never deletes one; a person decides which copy is right.")
RECORD_FOREIGN = ("{key}: line {seq} was written on {host} ({at}). Once a person has looked, "
                  "acknowledge it: {command}")
#: The command that acknowledges, with this machine's own store in it - no
#: placeholder a person would have to fill in (the review's N7).
ACKNOWLEDGE_COMMAND = 'python -m tracker.checkpoint "{store}" acknowledge "{key}"'
#: Where the lines from other machines would be, when the checkpoint could
#: not be read this pass (the rebase review's SF3).
FOREIGN_UNLISTED = "Lines from other machines could not be listed this pass: {why}"
#: The heading over each household's count of files left alone by name
#: (decision 190), drawn only when there is one.
STATUS_IGNORED_HEADING = "Left alone in the inboxes"

#: The two tables, column by column, in the order they are drawn. There is
#: no "Deferred writes" column any more: nothing a pass decides waits for
#: anything (decision 103 took the last deferred write).
STATUS_COLUMNS = (
    "Engagement", "Client", "Outstanding", STATUS_REVIEW_HEADING, "Still syncing",
    "Problem or skipped", "Warnings", "Last pass", "Drafted",
)
REVIEW_COLUMNS = ("Received", "Engagement", "File the client sent", "Reason", "Candidates")

#: Inline, because the page is one file that must render from a share, a
#: memory stick or an email attachment with nothing fetched: a page about
#: the firm's clients that reaches the network to look right is a page that
#: tells somebody else which firm is reading what.
_STATUS_STYLE = """
body { font-family: "Segoe UI", system-ui, sans-serif; margin: 2rem 2.5rem; color: #1c1c1c;
       background: #fbfbfa; line-height: 1.45; }
h1 { font-size: 1.35rem; margin: 0 0 0.2rem; }
h2 { font-size: 1.05rem; margin: 2rem 0 0.6rem; border-bottom: 1px solid #d8d6d1; padding-bottom: 0.3rem; }
p.stamp { margin: 0 0 0.5rem; color: #6b6862; font-size: 0.85rem; }
table { border-collapse: collapse; width: 100%; font-size: 0.87rem; }
th, td { text-align: left; padding: 0.35rem 0.6rem; border-bottom: 1px solid #e6e4df; vertical-align: top; }
th { background: #f0eeea; font-weight: 600; white-space: nowrap; }
tr:hover td { background: #f6f5f2; }
ul { margin: 0; padding-left: 1.2rem; }
li { margin-bottom: 0.3rem; }
"""


@dataclass(frozen=True, slots=True)
class ParkedFile:
    """One file waiting for a person, and the engagement it is waiting in."""

    engagement: str
    received: str
    original_name: str
    reason: str
    candidates: str


def _parked_files(report: RunReport,
                  kept: page_rows.Kept | None = None) -> tuple[dict[Path, list[ParkedFile]], list[str]]:
    """Every file parked for a person, by engagement folder, and what could
    not be read.

    Each engagement's index is read the way every reader reads it - no
    lock, no quarantine of a sidecar it cannot parse - because drawing the
    practice must never move a client's file or stand in the way of the
    pass that is filing one. An index that cannot be read is said rather
    than skipped: an engagement missing from the queue for a reason nobody
    can see is how a document waits a month.

    **Read from the store as the walk left it** (decision 192): the walk
    that found these engagements followed every journal moments before,
    and the pass's own writes went into the same store, so the index is
    read without following the journal again (``follow=False``, the
    page's alone); a return the store does not hold is followed as ever.
    An index that cannot be read is said by its class and code, never its
    message, which can name a client's folder (security principle 7).

    **Kept rows** (P227): with ``kept``, a return whose record's token is
    the one its parked rows were kept under is not read again - the kept
    rows are exactly what this read would return - and a fresh read is
    kept when its token did not move while it was read.
    """
    parked: dict[Path, list[ParkedFile]] = {}
    problems: list[str] = []
    for run in report.runs:
        engagement = run.engagement
        token = _page_token(kept, engagement.path)
        rows = kept.parked(engagement.path, token) if kept is not None else None
        if rows is None:
            try:
                entries = read_index(engagement.path, follow=False)
            except Exception as exc:
                # The firm's own sentence whole; anything else - an OS error
                # whose message is the record's path - by its class (decision 190).
                errors.keep("runner: the parked files", exc, name=engagement.path.name)
                problems.append(STATUS_INDEX_UNREADABLE.format(
                    label=engagement.label, error=errors.said(exc, (ManifestError, LedgerError, StoreError))))
                if kept is not None:
                    kept.forget(engagement.path)      # never kept: read, and said, every page
                continue
            rows = [[entry.received, entry.original_name, entry.reason, entry.candidates]
                    for entry in entries if entry.decision == NEEDS_REVIEW]
            if kept is not None and token is not None:
                if _page_token(kept, engagement.path, again=True) == token:
                    kept.keep_parked(engagement.path, token, rows)
                else:
                    kept.forget(engagement.path)      # written while it was read
        parked[engagement.path] = [
            ParkedFile(engagement=engagement.label, received=received, original_name=original_name,
                       reason=reason, candidates=candidates)
            for received, original_name, reason, candidates in rows
        ]
    return parked, problems


def _page_token(kept: page_rows.Kept | None, folder: Path, *, again: bool = False) -> tuple | None:
    """The record's token for the practice page's kept rows (P227), or
    ``None`` when nothing is kept for this page or the return cannot be
    kept: outside the recorded root (the store finds it by its tail), or
    with no row in the store. Every record's token is asked in one
    statement, the first time the page asks; ``again`` asks this one
    record's afresh, after its read, so a record written while it was read
    is never kept under the older token. A store that cannot answer keeps
    nothing, said once by its class: the tokens become none for the rest of
    the report, so every row is then read, as before P227."""
    if kept is None:
        return None
    key = store.record_key(folder)
    if key is None:
        return None
    try:
        conn = store.connect()
        if again:
            return store.read_tokens(conn, key).get(key)
        if kept.tokens is None:
            kept.tokens = store.read_tokens(conn)
    except Exception as exc:
        log.warning("The practice page reads every row (%s)", errors.error_class(exc))
        kept.tokens = {}
        return None
    return kept.tokens.get(key)


def _page_title(root: Path) -> str:
    """What the page calls itself.

    The product's name, which the Electron shell passes in and a source
    checkout reads from the app's own package.json. The packaged app's
    scheduled job has neither (``api_entry.py`` says why it must not need
    them), and a pass that has finished its work must not end in a
    traceback over a heading: the firm's name, and then the folder the
    practice lives in, are names for the same thing that are always there.
    """
    for named in (product_name, firm):
        try:
            name = named()
        except SettingsError:
            continue
        if name:
            return name
    return root.name


def _drafted_cell(run: EngagementRun) -> str:
    """What the practice page's Drafted column says about one engagement:
    the hold and its count, else that a person has approved this week's
    draft, else that they approved it and then edited it (decision 190),
    else the stage the draft was written at, else yes for a draft
    from before the stages, else nothing at all."""
    if run.held:
        return STATUS_HELD.format(n=run.held)
    if run.approved:
        return APPROVED_NOTE
    if run.approval_lapsed:
        return APPROVED_THEN_EDITED
    if run.stage:
        return STAGE_NOTE.format(n=run.stage)
    return YES if run.drafted else ""


def _engagement_cells(run: EngagementRun, parked: list[ParkedFile]) -> tuple:
    """One engagement's row, in ``STATUS_COLUMNS`` order."""
    return (
        run.engagement.label,
        run.engagement.client,
        run.outstanding,
        len(parked),
        run.waiting,
        run.error or run.skipped,
        len(run.warnings),
        run.last_pass.isoformat(sep=" ", timespec="seconds") if run.last_pass else STATUS_NOT_PASSED,
        _drafted_cell(run),
    )


def write_status_page(root: Path | str, report: RunReport, *,
                      now: dt.datetime | None = None, kept: page_rows.Kept | None = None) -> Path:
    """Write the practice on one page into ``root``, and return where it went.

    One self-contained file: no script, no style sheet, no image, nothing
    fetched when it is opened. It names client files, which is why it is
    written into the firm's own clients folder and never into the
    repository, and why every value on it goes through :func:`tracker.page.esc`
    - a document called like a tag is shown as its name, not rendered as one.

    Drawn from ``report``, never from a fresh pass: the caller decides what
    was run and what was only read (see :func:`status_report`), so nothing
    here takes a lock or writes anything but this page. The parked files
    are each return's index as the store holds it after the walk and the
    pass (decision 192), read once per return and never followed again -
    or, with ``kept``, taken from the rows kept under the record's own
    token (P227), which are what that read would return.
    """
    root = Path(root)
    stamp = (now or dt.datetime.now()).isoformat(sep=" ", timespec="seconds")
    # Inside a reading (pilot P215): the parked-file read only reads, so the
    # machine's answers are held for it - and only for it; the page is
    # written after the hold ends.
    with one_reading():
        parked, problems = _parked_files(report, kept)
    # The pass's own sentences first (decision 189): a pass that stopped, a
    # run log that could not be written - what a person must see before
    # any one return's problem.
    problems = [*report.warnings,
                *(f"{run.engagement.label}: {run.error}" for run in report.errors), *problems]

    # Newest first, across the practice: what arrived last night is what
    # nobody has looked at. Reversed first, so that among files received on
    # the same day the later index row comes first - the sort is stable and
    # leaves them in the order it is given.
    queue = [file for run in report.runs for file in parked.get(run.engagement.path, ())][::-1]
    queue.sort(key=lambda file: file.received, reverse=True)

    title = _page_title(root)
    # The head is page.document()'s, with the page's policy (decision 190):
    # its own style and nothing else, by hash.
    lines = document(title, _STATUS_STYLE, [
        f"<h1>{esc(title)}</h1>",
        f'<p class="stamp">{esc(STATUS_GENERATED.format(stamp=stamp))}</p>',
        *_records_needing_a_person(root, report),
        f"<h2>{esc(STATUS_ENGAGEMENTS_HEADING)} ({len(report.runs)})</h2>",
        *table(STATUS_COLUMNS,
               (_engagement_cells(run, parked.get(run.engagement.path, []))
                for run in report.runs)),
        f"<h2>{esc(STATUS_REVIEW_HEADING)} ({len(queue)})</h2>",
        *(table(REVIEW_COLUMNS,
                ((f.received, f.engagement, f.original_name, f.reason, f.candidates)
                 for f in queue))
          if queue else [f"<p>{esc(STATUS_NOTHING_PARKED)}</p>"]),
        f"<h2>{esc(STATUS_PROBLEMS_HEADING)} ({len(problems)})</h2>",
        *(["<ul>", *(f"<li>{esc(problem)}</li>" for problem in problems), "</ul>"]
          if problems else [f"<p>{esc(STATUS_NO_PROBLEMS)}</p>"]),
        # What each household's inbox held that the sort leaves alone by
        # name, as a count (decision 190). Not a problem: a person looks
        # only when a count is not what they expected.
        *([f"<h2>{esc(STATUS_IGNORED_HEADING)}</h2>", "<ul>",
           *(f"<li>{esc(run.engagement.label)}: {esc(IGNORED_NOTE.format(n=run.ignored))}</li>"
             for run in report.runs if run.ignored),
           "</ul>"]
          if any(run.ignored for run in report.runs) else []),
        # Every folder that does not fit the layout, with the one sentence
        # saying why it is left alone (decision 125, the owner's rule).
        # Nothing in one is ever read, moved or renamed; a person fixes it.
        f"<h2>{esc(STATUS_MISFITS_HEADING)} ({len(report.misfits)})</h2>",
        *(table(MISFIT_COLUMNS,
                ((_under(root, misfit.path), misfit.sentence) for misfit in report.misfits))
          if report.misfits else [f"<p>{esc(STATUS_NO_MISFITS)}</p>"]),
    ])
    path = root / STATUS_PAGE_FILENAME
    write_text_atomically(path, page_text(lines))
    if kept is not None:
        # After the page (P227): the kept rows only make the next page
        # faster, so a file that cannot be written is a log line by its
        # class and changes nothing else - the page already stands.
        try:
            kept.save()
        except Exception as exc:
            log.warning("The practice page's kept rows could not be written (%s)", errors.error_class(exc))
    return path


def _records_needing_a_person(root: Path, report: RunReport) -> list[str]:
    """The page's first section (decision 159), one sentence per thing a
    person must look at: a copy beside a record or a lock, a record refused
    as altered, a line from another machine. Nothing when there is none."""
    said = list(report.unread)
    said += [RECORD_SIBLING.format(path=_under(root, copy)) for copy in report.siblings]
    said += [f"{run.engagement.label}: {run.error}" for run in report.refused]
    said += [RECORD_FOREIGN.format(key=line.key, seq=line.seq, host=line.host, at=line.at,
                                   command=ACKNOWLEDGE_COMMAND.format(store=store.store_path(),
                                                                      key=line.key))
             for line in report.foreign]
    if not said:
        return []
    return [f"<h2>{esc(STATUS_RECORDS_HEADING)} ({len(said)})</h2>",
            "<ul>", *(f"<li>{esc(one)}</li>" for one in said), "</ul>"]


def _engagement_status(engagement: Engagement, kept: page_rows.Kept | None = None) -> EngagementRun:
    """One engagement's line, read rather than run.

    The record, the way the app reads it for one engagement - no lock, no
    scaffold, no scan, nothing written in the folder. A row the page read
    carries no pass time, because no pass was made.

    With ``kept`` (P227): the skip, the problem and the warning come from
    the walk, as ever; the counts come from the kept rows when the record's
    token is the one they were read under, and otherwise from the read,
    which is kept when its token did not move while it was read.
    """
    run = EngagementRun(engagement=engagement)
    run.code, run.skipped = why_skipped(engagement)
    if run.skipped:
        return run           # a prior year's numbers are not this year's work
    if engagement.problem:
        run.error = RECORD_UNREADABLE.format(problem=engagement.problem)
        run.code = CODE_RECORD_UNREADABLE
        return run
    token = _page_token(kept, engagement.path)
    counted = kept.counts(engagement.path, token) if kept is not None else None
    if counted is not None:
        run.statuses, run.outstanding = counted
    else:
        try:
            summary = summarize(load_manifest(engagement.path, follow=False))
        except (ManifestError, LedgerError, StoreError, OSError) as exc:
            # One bad record costs its own row, never the page (decision 189),
            # said by its class and code: the message can name the record's
            # path, a client's folder (security principle 7; the review's S2).
            # The words are kept on the debug log (decision 190).
            errors.keep("runner: the return's record", exc, name=engagement.path.name)
            run.error = RECORD_UNREADABLE.format(problem=errors.error_class(exc))
            run.code = CODE_RECORD_UNREADABLE
            if kept is not None:
                kept.forget(engagement.path)      # never kept: read, and said, every page
            return run
        run.statuses = summary.counts
        run.outstanding = summary.outstanding
        if kept is not None and token is not None:
            if _page_token(kept, engagement.path, again=True) == token:
                kept.keep_counts(engagement.path, token, summary.counts, summary.outstanding)
            else:
                kept.forget(engagement.path)      # written while it was read
    if engagement.warning:
        run.warnings.append(engagement.warning)
    return run


def _under(root: Path, path: Path) -> str:
    """A folder as a person reads it on the practice page: its path below
    the clients root, or the whole path when it is not under one."""
    below = parts_below(root, path)
    return str(Path(*below)) if below else str(path)


def status_report(registry: Registry, *, passed: Iterable[EngagementRun] = (),
                  today: dt.date | None = None, warnings: Iterable[str] = (),
                  unread: Iterable[str] = (), kept: page_rows.Kept | None = None) -> RunReport:
    """Every engagement in ``registry``, with the runs in ``passed`` folded in.

    The page is about the practice, not about whichever engagement was
    just run: a pass over one engagement (the app's button) or over a
    subset (``--only``) still draws every engagement the registry found.
    An engagement this pass did not touch is read, not run, so the page
    can be regenerated as often as anyone likes. ``warnings`` are the
    pass's own sentences, for the page's problems list (decision 189);
    ``unread`` what the pass could not ask of the record checkpoint, drawn
    first in the records section.

    **Each part from one source** (decision 192). Which returns exist,
    their labels, the problem rows, a stopped household's returns and the
    misfits come from the walk, ``registry``: discovery is positional and
    only a walk knows (decision 125). A return the pass ran is the pass's
    own run. Every other return's counts are read from the store as the
    walk left it - the walk followed every journal, moments before for
    *Run now* and at the start for the schedule - with no second read of
    its journal; a return the store does not hold is followed. So a
    return the pass did not run shows as its record stood when the pass
    began, plus anything recorded on this computer since.

    ``kept`` (P227): the rows kept from earlier pages, used for a return
    only while its record's token is the one they were read under
    (:func:`_engagement_status`). The tokens are asked afresh for each
    report.
    """
    ran = {run.engagement.path: run for run in passed}
    if kept is not None:
        kept.tokens = None
    # Inside a reading (P226, as P215 held the parked files): the pass's
    # work is done and every household's lock is gone, and the report only
    # reads, so the machine's answers - where the store is, what the
    # settings say, what each folder resolves to - are asked once for it,
    # not once a record. The page is still written after the hold ends.
    with one_reading():
        siblings, foreign, not_listed = records_needing_a_person(registry)
        runs = [ran[engagement.path] if engagement.path in ran else _engagement_status(engagement, kept)
                for engagement in registry.engagements]
    return RunReport(
        today=today or dt.date.today(),
        runs=runs,
        misfits=list(registry.misfits),
        warnings=list(warnings),
        siblings=siblings,
        foreign=foreign,
        unread=[*unread, *(one for one in not_listed if one not in unread)],
    )
