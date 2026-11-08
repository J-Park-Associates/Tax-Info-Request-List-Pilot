"""Whole passes over a household, as the runner's tests stage them.

``test_runner`` made the pile's households, and ``test_page_rows`` and
``test_shell`` borrowed its way of doing it (they imported ``build_engagement``
from ``test_runner``). They live here so that borrowing names a module that is
not a test file (SPEC-architecture E-4, R2.1): a household with the sample pile
waiting in its one inbox, an edit of its rows as a person makes it in the app,
and the scheduled job and the app's Run now called as they call ``main``.

Moved with their words from ``tests/test_runner.py``; nothing here is new.
The draft week's dates (``FRIDAY``, ``SATURDAY``, ``SUNDAY``) joined them,
one block as it was, when ``tests/test_run_log.py`` was split out of
``test_runner`` (SPEC-architecture-p5 R5.8.7, P345): both files tell a pass
or its report a day of that week, and a test file may not import another.
Two households with a W-2 in each inbox (``_two_households``) and the
practice page's text as a person reads it (``_page``) joined them when
``tests/test_status_page.py`` was split out of ``test_runner``
(SPEC-architecture-p5 R5.9.8, P346), for the same reason: both files draw
the page and read it back. The order hint's file beside the store
(``_hint_file``) and its lines (``_hint_lines``) joined them when
``tests/test_pass_order.py`` was split out of ``test_runner``
(SPEC-architecture-p5 R5.10.5, P347): both files write the hint and read it
back.

When ``tests/test_runner.py`` was split by its section banners into ``tests/test_runner_<family>.py``
(SPEC-architecture-p5 P5.14, E-3), the helpers two or more of the resulting files read came here,
byte for byte with their words: the ``stamped_on`` fixture (named once by assignment in each user, as
``samples`` is), ``a_pass`` and ``pass_on``, ``drafted_events``, ``make_ambiguous`` and
``households_in_order``. A helper one file reads moved with that file.
"""

import datetime as dt
import html
from pathlib import Path

import pytest

import tracker.pass_order as pass_order
from tests.builders import make_engagement, seed_index
from tests.samples import DEMO_ITEMS, SCRATCH_PEOPLE, YEAR, build_samples
from tracker import ledger, store
from tracker.index import NEEDS_REVIEW
from tracker.layout import household_of, root_of
from tracker.manifest import EngagementInfo, RequestItem, load_engagement_info, save_rules
from tracker.records import IndexEntry, rule_from_json
from tracker.registry import discover_engagements, engagement_from
from tracker.runner import DRAFT_WEEKDAY, SETTINGS_FLAG, main, run_household
from tracker.scaffold import scaffold_engagement
from tracker.status_page import STATUS_PAGE_FILENAME

# The draft day is whatever the runner says it is; the dates follow it.
_WEEK_START = dt.date(2026, 3, 9)                      # a Monday
SATURDAY = _WEEK_START + dt.timedelta(days=DRAFT_WEEKDAY)  # the draft day
FRIDAY = SATURDAY - dt.timedelta(days=1)                # the day before
SUNDAY = SATURDAY + dt.timedelta(days=1)                # the day after


@pytest.fixture(scope="session")
def samples(tmp_path_factory):
    folder = tmp_path_factory.mktemp("samples")
    build_samples(folder)
    return folder


def build_engagement(tmp_path, samples, drops=(f"W-2 John Smith {YEAR}.pdf",),
                     name="Smith TY2025", household="Test Household", **kwargs):
    """A scaffolded return with files waiting in its household's inbox."""
    # The return's details in the record are where the draft learns who the
    # client is; the Engagement dataclass only echoes it. It is read back
    # out of the record rather than typed here, because since decision 125
    # the pass reads the household, the year and the return name off it.
    from dataclasses import replace

    # The pile is addressed to the two people the samples name, so the
    # return lists them (decision 128) as the office's would.
    folder = make_engagement(tmp_path, DEMO_ITEMS,
                             EngagementInfo(client="John Smith", firm="J Park"),
                             household=household, return_name=name,
                             people=SCRATCH_PEOPLE, scaffold=False)
    result = scaffold_engagement(folder)
    for drop in drops:
        (result.inbox / drop).write_bytes((samples / drop).read_bytes())
    found = engagement_from(folder)
    return replace(found, info=replace(found.info, **kwargs)) if kwargs else found


def edit_rows(engagement_dir, **fields_by_identifier):
    """A person's edit of one or more rows in the app, saved as one event."""
    from dataclasses import replace

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement_dir)]
    edited = [replace(row, **fields_by_identifier.get(row.identifier, {})) for row in rows]
    return save_rules(engagement_dir, edited, load_engagement_info(engagement_dir))


def edit_details(engagement_dir, **fields):
    """A person's edit of the engagement's details in the app."""
    from dataclasses import replace

    rows = [RequestItem(**rule_from_json(row)) for row in store.rules(store.connect(), engagement_dir)]
    return save_rules(engagement_dir, rows, replace(load_engagement_info(engagement_dir), **fields))


def _the_scheduled_job(root, monkeypatch, *args) -> int:
    """``main`` as the scheduled job calls it: the settings folder beside
    ``root``, whose file names ``root`` as the clients root, and the flags."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = root.parent / "settings"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(root)
    return main([SETTINGS_FLAG, str(settings), *args])


def _settings_for(root, monkeypatch) -> Path:
    """The settings folder beside ``root``, whose file names it, as the
    app's and the job's own; the store sits beside it."""
    from tracker.settings import ENV_SETTINGS_DIR, set_clients_root

    settings = root.parent / "settings"
    settings.mkdir(exist_ok=True)
    monkeypatch.setenv(ENV_SETTINGS_DIR, str(settings))
    set_clients_root(root)
    return settings


def _lines(out: str) -> list[dict]:
    import json

    return [json.loads(line) for line in out.strip().splitlines()]


def _run_now(root, household, monkeypatch, capsys) -> tuple[int, list[dict]]:
    """``main`` as the app's Run now calls it (``run_now_arguments``): its
    exit code and every stdout line, progress lines then the final one."""
    from tracker.runner import run_now_arguments

    settings = _settings_for(root, monkeypatch)
    capsys.readouterr()
    code = main(run_now_arguments(settings, household))
    return code, _lines(capsys.readouterr().out)


def _three_households(tmp_path, samples):
    return [build_engagement(tmp_path, samples, household=f"{name} Household", name=f"{name} TY2025")
            for name in ("Alder", "Birch", "Cedar")]


def _a_parked_file(engagement_dir) -> str:
    """One file parked for a person in this return's record."""
    seed_index(engagement_dir, [IndexEntry(
        received="2026-02-02", original_name="unclear scan.pdf", size_kb=5.0, digest="cd" * 32,
        identifier="", prepared_location="", pbc_location="unclear scan.pdf",
        decision=NEEDS_REVIEW, reason="no request matched")])
    return "unclear scan.pdf"


def _two_households(tmp_path, samples):
    """Two households, each with a W-2 waiting in its inbox."""
    first = build_engagement(tmp_path, samples, household="Alder Household", name="Alder TY2025")
    second = build_engagement(tmp_path, samples, household="Birch Household", name="Birch TY2025")
    return first, second


def _page(root) -> str:
    return html.unescape((root / STATUS_PAGE_FILENAME).read_text(encoding="utf-8"))


def _hint_file() -> Path:
    path = store.store_path().parent / pass_order.PASS_ORDER_FILENAME
    path.parent.mkdir(parents=True, exist_ok=True)
    return path


def _hint_lines(path: Path) -> list[str]:
    return path.read_text(encoding="ascii").splitlines()


@pytest.fixture
def stamped_on(monkeypatch):
    """Stamp every line the record writes as if written at noon on ``day``.

    Since decision 115 the pass reads the day of the last draft from the
    ``drafted`` event's own stamp, not from a file time - so a test that
    tells the pass today is a Saturday in March must let the record say
    March too. ``ledger.stamp()`` is the one place a stamp is made.
    """
    def _on(day: dt.date) -> None:
        noon = dt.datetime.combine(day, dt.time(12)).astimezone(dt.UTC)
        monkeypatch.setattr(
            ledger, "stamp", lambda: noon.isoformat(timespec="seconds").replace("+00:00", "Z"))
    return _on


def a_pass(engagement, **kwargs):
    """One pass over this return's household, answering for the return.

    A pass is the household's since decision 125 - one inbox feeds every
    return of it - so this is what the scheduled job does to one folder,
    and the claims below are about the run it hands back for the return
    they named.
    """
    # A pass needs the practice (decision 132): the walk of the root this
    # return sits under, as the scheduled job hands it.
    kwargs.setdefault("registry", discover_engagements(root_of(engagement.path)))
    runs = run_household(household_of(engagement.path), [engagement], **kwargs)
    return next(run for run in runs if run.engagement.path == engagement.path)


def pass_on(stamped_on, engagement, day, **kwargs):
    """One pass on ``day``, with the record stamped that day."""
    stamped_on(day)
    return a_pass(engagement, today=day, **kwargs)


def drafted_events(engagement_dir):
    """The ``drafted`` lines on the record, without their stamps."""
    return [{k: v for k, v in e.items()
             if k not in (ledger.EVENT_KEY, ledger.AT_KEY) and k not in ledger.LINE_KEYS}
            for e in ledger.read_events(engagement_dir) if e[ledger.EVENT_KEY] == ledger.DRAFTED]


def make_ambiguous(engagement_dir, identifier="C01"):
    """Edit the rule under a filed copy so the copy no longer satisfies it:
    the fingerprint moves, the copy is re-read, and the row fails the
    content check with a client-side reason nobody put there. The copy must
    already be filed - a pass has run - or the edited rule simply parks it."""
    return edit_rows(engagement_dir, **{identifier: {"required_keywords": ("form 8889",)}})


def households_in_order(monkeypatch) -> list[str]:
    """The households a pass takes, in the order it takes them."""
    import tracker.runner as runner

    taken, real = [], runner.run_household

    def recorded(household, *args, **kwargs):
        taken.append(household.name)
        return real(household, *args, **kwargs)

    monkeypatch.setattr(runner, "run_household", recorded)
    return taken
