"""Whole passes over a household, as the runner's tests stage them.

``test_runner`` made the pile's households, and ``test_page_rows`` and
``test_shell`` borrowed its way of doing it (they imported ``build_engagement``
from ``test_runner``). They live here so that borrowing names a module that is
not a test file (SPEC-architecture E-4, R2.1): a household with the sample pile
waiting in its one inbox, an edit of its rows as a person makes it in the app,
and the scheduled job and the app's Run now called as they call ``main``.

Moved with their words from ``tests/test_runner.py``; nothing here is new.
"""

from pathlib import Path

import pytest

from tests.conftest import make_engagement, seed_index
from tests.samples import DEMO_ITEMS, SCRATCH_PEOPLE, YEAR, build_samples
from tracker import store
from tracker.filer import NEEDS_REVIEW, IndexEntry
from tracker.manifest import EngagementInfo, RequestItem, load_engagement_info, save_rules
from tracker.records import rule_from_json
from tracker.registry import engagement_from
from tracker.runner import SETTINGS_FLAG, main
from tracker.scaffold import scaffold_engagement


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
