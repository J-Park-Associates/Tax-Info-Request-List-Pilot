# SPEC: The schedule comes back after a reinstall (P198, F6)

Decision P198 (`pilot/DECISIONS.md`). Jason, 2026-10-01: "take care of all of
f7 root cause md ... finish the application in this session now" (the
handoff's item 4; `wincheck-0.3.md` Left item 2; decision 209). Branch
`claude/f6-schedule`, from `4534b30`.

## 1. The fault

Root cause, in one sentence: the app's launch door decides "nothing to do"
from its own note alone, and the uninstaller deletes the scheduled task while
that note stays, so the same build reinstalled never registers the task again.

- `after_install.launch()` (`tracker/after_install.py:1196-1211`) returns at
  once when `_unchanged()` (`:1214-1223`) finds the program identity, the
  designation and the saved schedule choice as the last clean run left them.
- The uninstaller deletes the task (`pilot/installer/setup.iss:75-77`) and
  keeps the data folder, so `after-install.json` stays; `settings.json` still
  says `schedule_enabled: true`.
- The first screen's notice shows failures and findings only, and nothing
  failed, so nothing on screen says the schedule is not running
  (`pilot/wintest/RESULTS-0.3.md`, F6). Repair the Schedule was the only way
  back: a step that depends on a person remembering it (decision 209).

The same hole opens whenever the task disappears behind the app's back (a
person deletes it in Task Scheduler, an IT clean-up): the note cannot know.

## 2. Rulings and reasons

1. **The launch door asks Windows whether the task is there, but only when
   the note says this computer registered it.** `_unchanged()` gains one last
   condition: when the record's `schedule` is one of `scheduling.REGISTERING`
   (`claimed` or `registered`), the task must exist. Reason: the note is a
   record of what was done, not of what is true now; the only fact the
   uninstaller (or a person) can take away is the task itself.
2. **The designated-machine rule holds (decision 159 / M1).** The question is
   asked only when the record says *this* computer registered the schedule,
   and only after the designation already matched the record. A computer the
   designation does not name (`elsewhere`), a schedule switched off (`off`),
   no root, no Task Scheduler: none of them expects a task, so none is asked
   and none registers. When the task is missing the door runs the whole step
   (`_run`), which goes through `scheduling.schedule_decision` as every door
   does - so even then only the designated computer registers.
3. **The cheapest reliable check is `schtasks /query /tn <name>`**: exit 0 is
   "it exists". It is the check `remove_task` already makes, now spelled once
   as `scheduling.task_exists()`, and `remove_task` uses it. No XML is read,
   no task is changed. Rejected: the Task Scheduler COM API (needs `pywin32`
   or `ctypes` COM plumbing - a package or a page of fragile code for one
   yes/no); reading `C:\Windows\System32\Tasks\` (needs administrator rights
   and is an internal layout).
4. **Its cost at every launch** is one `schtasks.exe` process on the
   designated computer only - tens of milliseconds, at most a few hundred on a
   cold start - inside the launch step, which already runs in the background
   and never holds the first screen. Every other computer pays nothing new.
   It is asked last, after the cheap checks, so a launch that must run the
   step anyway does not ask.
5. **A query that fails is never read as "the task is there".** Any non-zero
   answer (not found, access denied, Task Scheduler stopped) means "not
   confirmed", and the door runs the step. The step registers with
   `schtasks /create ... /f`, which is idempotent: if Windows really is
   refusing, the create fails and says so in `SCHEDULE_FAILED` with
   `schtasks`'s own words, recorded and shown on the first screen until a run
   succeeds; if the query alone misfired, the task is simply registered again.
   A `schtasks` that cannot even be started (`OSError`) is kept on the local
   error log and runs the step too, whose own registration then fails loudly
   with `SCHEDULE_UNREACHABLE`. Nothing is skipped silently.
   *Changed by the engine review's rulings (`pilot/reviews/lanes-rulings.md`,
   Engine, SHOULD-2 and NIT-2):* every `schtasks` command now has a 60-second
   limit (`scheduling.SCHTASKS_TIME_LIMIT_SECONDS`), because the query now
   runs at every start inside the step's lock and a hung Task Scheduler
   would otherwise hold that lock, and every later Repair or root save,
   for ever. One that runs past it raises `TimeoutError` (an `OSError`), so
   it takes the `OSError` path above: kept on the error log, the step runs,
   and its registration is said as `SCHEDULE_UNREACHABLE` - never "the task
   exists". A query that is refused keeps its exit code (never `schtasks`'s
   words) on the error log, once per start (`scheduling.task_query`,
   `after_install.QUERY_REFUSED`), so a task registered again at every
   start has its reason written down.
6. **No new words, no new screen.** A re-registration that succeeds is the
   step doing its job, as at a first install: the note records it and the
   first screen shows nothing. A registration that fails uses the existing
   `SCHEDULE_FAILED` sentence. So `tracker/api.py` and the app (lane B) are
   untouched.
7. **The uninstaller is not changed.** Deleting the note at uninstall would
   also fix a reinstall, but not a task deleted by hand, and the data folder
   is never the installer's to touch (`setup.iss:70-71`).

No owner questions: no money, client wording, client data or season need.

## 3. Files to touch

| File | Change |
|---|---|
| `tracker/scheduling.py` (`remove_task`, about `:477-495`) | New `task_exists(task_name=TASK_NAME) -> bool`; `remove_task` asks it. |
| `tracker/after_install.py` (`launch` `:1196`, `_unchanged` `:1214`, the module docstring's "Three doors" paragraph) | `_unchanged` asks `_task_missing(record)` last; docstrings say so. |
| `tests/test_after_install.py` | The `windows` fake keeps whether the task exists (`/create` makes it, `/delete` removes it), as Windows does; new claims below; the two "no `schtasks` call when nothing changed" claims become "one `/query` and nothing else". |
| `tests/test_scheduling.py` | `task_exists` claims. |
| `docs/runbook.md` (section 1, after the line "tries again at its next start", about `:131`) | One sentence: a task deleted by an uninstall or by hand comes back at the app's next start on the designated computer. |
| `docs/repo-map.curated.json`, then `python tools/repo_map.py update` | The after_install node says the launch door asks whether the task exists. |

Not touched: `tracker/api.py`, `app/renderer/*`, `pilot/installer/setup.iss`.

## 4. Owning tests (named as claims)

`tests/test_after_install.py`:
- `test_a_launch_after_the_task_was_removed_registers_it_again`
- `test_a_reinstall_that_kept_the_note_registers_the_schedule_at_first_start`
- `test_a_launch_with_the_schedule_off_registers_nothing`
- `test_a_launch_on_a_computer_the_designation_does_not_name_asks_nothing_and_registers_nothing`
- `test_a_query_that_fails_is_never_read_as_a_task_that_exists`
- `test_a_schtasks_that_cannot_start_runs_the_step_and_says_so`
- rewritten: `test_the_launch_door_does_nothing_when_the_program_is_unchanged`,
  `test_the_launch_door_makes_only_one_query_when_nothing_changed`,
  `test_the_windows_check_sequence_keeps_the_task_through_a_restart` (two `/query`s, nothing else).

`tests/test_scheduling.py`:
- `test_task_exists_asks_schtasks_and_only_exit_zero_is_yes`

Added by the engine review's fold: `test_a_query_refused_keeps_its_exit_code_on_the_error_log_once_per_start`
and `test_a_schtasks_that_hangs_is_said_as_unreachable` (`tests/test_after_install.py`; the
"...and says so" test now asserts its error-log entry, NIT-3);
`test_task_query_hands_back_the_exit_code_and_asks_nothing_off_windows` and
`test_a_schtasks_that_hangs_is_stopped_at_its_limit_as_an_os_error` (`tests/test_scheduling.py`).

Guards: `tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py` (no wording change, so not `test_errors`).

## 5. What staff notice

After uninstalling and reinstalling the app on the office computer, with the
schedule on, the scheduled pass runs again from the first start - no visit to
Tools > Repair the Schedule. If Windows refuses the task, the first screen
says so in the existing sentence until it works. Other computers notice
nothing.
