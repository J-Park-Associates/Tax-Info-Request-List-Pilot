# F6 build (P198): the schedule comes back after a reinstall

Branch `claude/f6-schedule`, from `4534b30`. SPEC:
`pilot/SPEC-F6-schedule-after-reinstall.md`. Built 2026-10-01 (builder agent);
a separate reviewer is next. Not pushed, no pull request.

## Root cause

The launch door decided "nothing to do" from its own note alone, and the
uninstaller deletes the task while the note stays, so the same build
reinstalled never registered the task again.

## Rulings, where they live

- R1/R2, the launch door asks only on the designated computer:
  `tracker/after_install.py:1233` (`_unchanged` ends `and not _task_missing(record)`)
  and `:1236` (`_task_missing`: asks only when the record's `schedule` is in
  `scheduling.REGISTERING`; `off`, `elsewhere`, no root, no Task Scheduler are
  never asked). A missing task runs the whole step, so `schedule_decision`
  still decides who registers (decision 159 / M1).
- R3, the one check: `tracker/scheduling.py:477` `task_exists()` (`schtasks
  /query /tn`, exit 0 only is yes); `remove_task` now asks it (`:500`).
- R4, cost: one `schtasks.exe` per launch on the designated computer only,
  asked last, inside the background launch step.
- R5, a failing query is never "there": non-zero runs the step (`/create /f`
  registers again or says `SCHEDULE_FAILED`); an `OSError` is kept on the
  error log and runs the step, which fails loudly with `SCHEDULE_UNREACHABLE`.
- R6, no new words: `tracker/api.py` and the app untouched; `test_errors` not run.
- R7, the uninstaller is unchanged.
- Docstrings: the module's "Three doors" paragraph and `launch()`.
- No owner questions.

## Shared files changed

- `docs/runbook.md:131-135`: one sentence after "tries again at its next
  start" (section 1): every start on the scheduling computer asks whether
  the task is there, and registers a deleted one again (P198).
- `tracker/scheduling.py:477-502` (no other lane owns it).
- `docs/repo-map.curated.json`: the after_install and scheduling nodes' notes
  (one appended sentence each); `docs/repo-map.json` / `.md` regenerated.
- Not changed: `pilot/DECISIONS.md` (P198's status still says "SPEC to
  write"; left for the orchestrator so lanes B-D's adjacent rows do not
  conflict).

## Tests

The `windows` fake now keeps whether the task exists (`/create` makes it,
`/delete` removes it) and has `query_fails`. New:
`test_a_launch_after_the_task_was_removed_registers_it_again`,
`test_a_reinstall_that_kept_the_note_registers_the_schedule_at_first_start`,
`test_a_launch_with_the_schedule_off_registers_nothing`,
`test_a_launch_on_a_computer_the_designation_does_not_name_asks_nothing_and_registers_nothing`,
`test_a_query_that_fails_is_never_read_as_a_task_that_exists`,
`test_a_schtasks_that_cannot_start_runs_the_step_and_says_so`,
`test_task_exists_asks_schtasks_and_only_exit_zero_is_yes` (test_scheduling).
Changed claims (the no-op launch now asks one `/query`):
`test_the_launch_door_does_nothing_when_the_program_is_unchanged` (only
`/query` allowed), `test_the_launch_door_makes_no_schtasks_call_when_nothing_changed`
renamed `..._makes_only_one_query_when_nothing_changed`,
`test_the_windows_check_sequence_keeps_the_task_through_a_restart` (two
`/query`s, nothing else).

| File | Python 3.11.15 (venv in scratchpad) | Python 3.14 (`C:\Python314`) |
|---|---|---|
| tests/test_after_install.py | 97 passed, 3 skipped | 97 passed, 3 skipped |
| tests/test_scheduling.py | 115 passed | 115 passed |
| tests/test_layers.py | 29 passed | 29 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

Each file its own process, in parallel. Dead code: none found in the changed
files (the inline `/query` in `remove_task` replaced by `task_exists`; one
needless `mkdir` removed from a new test before commit).
`python -m ruff check .`: All checks passed. `python tools/repo_map.py check`:
current (415 nodes after this file is added).

## Not done

- Not proven on a real Task Scheduler: no real task may be touched on this
  PC. The next Windows check should redo RESULTS-0.3's "Reinstall after
  step 21" row on the test PC (uninstall, reinstall the same build, start,
  `schtasks /Query /TN "Tax Document Console"` finds the task).
- The office PC's schedule stays off (Jason); with it off the door asks nothing.
