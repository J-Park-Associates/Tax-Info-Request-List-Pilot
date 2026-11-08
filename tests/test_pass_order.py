"""Tests for tracker/pass_order.py - the household order hint beside the
store: which household a pass serves first, and who was not served.

Most of what the module promises is held by tests/test_runner.py and the test_runner_<family> files split from it
(SPEC-architecture-p5 P5.14), whose tests
run a pass and read the hint it left: households least recently completed
first, a missing or broken hint the walk's order with one sentence, a nested,
oversized or memory-hungry file only a hint, a household held by a lock tried
once more at the end, one not served two passes running named and the pass
exiting 3, a dry run counting nothing, each household's start one appended
line and the whole written once a pass, a killed pass's mark putting its
household last, an earlier version's hint settled before the first mark, and
a hint that cannot be settled taking no marks. None of them moved here by the
SPEC's rule, because each runs a pass. The three tests below moved here from
tests/test_runner.py (SPEC-architecture-p5 R5.10.5, P347), byte for byte:
each calls the hint's read, its whole write or the reason a household was
not served directly, with the pass's report records at most, and nothing
that stayed in the runner. A read through ``tracker.runner`` of a name the
runner imports back (``_read_order_hint``, ``_write_order_hint``) is kept as
it was, until SPEC-architecture-p5 P5.16 retargets every such read to its
home; a read of a name the runner no longer holds reads
``tracker.pass_order``. Made-up households only.
"""

from pathlib import Path

import tracker.runner as runner_module
from tests.passes import FRIDAY, _hint_file, _hint_lines
from tracker import pass_order
from tracker.registry import Engagement
from tracker.run_log import RunReport


def test_a_hint_for_a_thousand_households_is_read_back_whole(tmp_path):
    """P217: at 64 KiB the hint was unreadable from about 370 households up,
    and decision 189's order was lost. A thousand households' hint - one
    compact line - is read back whole, settled, with no warning."""
    hint = {f"Household {n:04d} of a Fabricated Firm": {
        "completed": "2026-10-07T02:14:09", "ended": "2026-10-07T02:14:09",
        "started": "2026-10-07T02:13:58", "not_served": 0} for n in range(1000)}
    path = _hint_file()
    assert runner_module._write_order_hint(path, hint)
    assert len(_hint_lines(path)) == 1
    assert 65_536 < path.stat().st_size < pass_order.PASS_ORDER_MAX_BYTES
    report = RunReport(today=FRIDAY)
    assert runner_module._read_order_hint(report) == (path, hint, True)
    assert report.warnings == []


def test_a_torn_last_mark_is_skipped_without_a_warning(tmp_path, caplog):
    path = _hint_file()
    path.write_text(
        '{"version":2,"households":{"Alder Household":{"completed":"2026-10-06T02:00:00"}}}\n'
        '{"started":"2026-10-07T02:00:00","household":"Alder Household"}\n'
        '{"started":"2026-10-07T02:00:05","household":"Birch Household"}\n'
        '{"started":"2026-10-07T02:00:1', encoding="ascii")
    report = RunReport(today=FRIDAY)
    with caplog.at_level("WARNING"):
        found, hint, settled = runner_module._read_order_hint(report)
    assert found == path and not settled
    assert hint == {"Alder Household": {"completed": "2026-10-06T02:00:00", "started": "2026-10-07T02:00:00"},
                    "Birch Household": {"started": "2026-10-07T02:00:05"}}
    assert report.warnings == [] and caplog.records == []


def test_a_household_the_run_limit_cut_off_is_not_said_to_be_stopped_by_a_person():
    """A pass nobody stopped is not "stopped by a person": the run has its own reason word."""
    from tracker.pass_order import WHY_CANCELLED, WHY_RUN_LIMIT, _why_not_served
    from tracker.runner import EngagementRun

    assert WHY_RUN_LIMIT == "reached the run limit" != WHY_CANCELLED
    run = EngagementRun(engagement=Engagement(path=Path("x")))
    run.run_limit = True
    assert _why_not_served([run]) == WHY_RUN_LIMIT and not run.cancelled
    run.cancelled = True
    assert _why_not_served([run]) == WHY_CANCELLED
