# Engine review: P198 (F6) and P201 (firm-cache fill), at c7eed52

Reviewer: separate agent; built none of it. Scope: `git diff 4534b30..c7eed52` for tracker/after_install.py, tracker/scheduling.py, tracker/runner.py, tracker/firm_cache.py, tracker/api.py (the firm cache save condition), their tests, docs/runbook.md, docs/repo-map.curated.json, and the seams between them. No file edited, nothing committed or pushed, no real scheduled task touched.

## Verdict

**No MUST.** Three SHOULDs and four NITs. Both lanes do what their SPECs say, the merge kept both lanes' changes to scheduling.py, and every named test file passes on both interpreters.

## What was checked and holds

- **F6 asks only on the designated computer and only once.** `_task_missing` (after_install.py:1238-1256) is the last condition in `_unchanged`'s `and` chain (after_install.py:1231-1233). So it runs only when the program, the designation and the saved choice all match, and only when the record says this computer CLAIMED or REGISTERED the schedule. A computer the designation doesn't name, a schedule that is off, and a computer without Task Scheduler are never asked. Its only caller is `launch()` (after_install.py:1214), which the shell runs in the background at start (api.py:5606). No read-only reply asks.
- **A failed query never counts as "the task exists".** `task_exists` (scheduling.py:486-498) returns True only when schtasks exits 0. If schtasks can't be started, the error is kept on the log (`errors.keep`) and the step runs anyway. The step's `/create /f` either registers the task or explains why it can't. Off Windows the record never says REGISTERING, so `_task_missing` returns False there and nothing is asked.
- **`remove_task` behaves as before.** It now calls `task_exists` (scheduling.py:501-515), with the same exit-0 test as the old inline query.
- **The merge kept both lanes' scheduling.py changes.** P201's product flag is on the packaged command line (scheduling.py:186-197); F6's `task_exists`/`remove_task` split is at scheduling.py:486-515. F6 re-registers through `register_here` → `_task_xml` → `runner_arguments(settings, frozen=frozen)` (scheduling.py:362), so a re-registered packaged task carries `--run --product "<name>"`. A source checkout's command line is unchanged.
- **The product flag is parsed and harmless.** api_entry.py hands everything after `--run` to `runner.main`. `_parser()` accepts `--product` (runner.py:2728-2730), and the runner passes it only to the fill's child, as `TRACKER_PRODUCT_NAME` (runner.py:620-622). The page title doesn't use it. A task registered before this change has no `--product`: its packaged fill fails and is reported as a pass warning until the first app start after the upgrade registers the task again (R6; runbook says so).
- **A fill failure never fails the pass, and it is reported.** Every way the fill can end — couldn't start, non-zero code, timed out, finished but didn't leave the cache — becomes one `_warn(... CODE_CACHE_NOT_FILLED ...)` (runner.py:3054-3057). The exit code is untouched. The warning names the reason by kind only. The child's stdin, stdout and stderr all go to DEVNULL, so no client name reaches the pass log.
- **The fill holds no lock.** It runs after `watch.close` and after every household lock is released (runner.py:3047-3057). The pass holds no pass-wide lock at that point: `main` wraps `_pass` only in `error_log` (runner.py:2771). The store is open but idle.
- **Staleness rules still hold.** In `_firm_from_cache`, each household's fingerprint is taken before the household is read (api.py:6042-6051). A household that changes during the fill is saved under its earlier fingerprint, so the next reply sees a mismatch and reads it again. Writes are atomic (firm_cache.py:373), so two writers racing each leave a whole file. Both the parent and the child get the root from `door.checked_root`, and their cache heads (data home, program stamp, settings file) match, so `holds()` compares like with like.
- **P118 (a read-only reply writes nothing) is not broken.** The firm reply already wrote the cache when what it kept changed (P120, before this branch). P118 refuses settings writes and recorded events inside a reading. The cache is neither: it is a speed file in the data home (decision 186), never a client tree. R5a only adds a write when nothing is kept (api.py:6101-6106). See NIT-1.
- **P193 data-home guard is reached.** In the fill's child, a redirected data home stops the `firm` reply with a non-zero code, which the pass reports as "the firm summary stopped with code N". In the parent, `cache_path()` raising `SettingsError` is caught and treated as "not filled" (runner.py:636-640).
- **Layers hold.** At load time the runner adds only `firm_cache` and `subprocess`. It never imports `api` or `scheduling`; `api` appears only inside a test. tests/test_layers.py passes.
- **Curated map notes.** The note for `tracker/scheduling.py` names both F6 (`task_exists`, P198) and P201 (`--product`). The runner and firm_cache notes name P201; the after_install note names P198. The map is current.
- **No dead code.** Ruff is clean, and every new constant (FILL_*, CODE_CACHE_NOT_FILLED, PRODUCT_FLAG, FIRM_COMMAND, FILL_TIME_LIMIT_SECONDS) has a user.
- **Tests are named as claims, and none reaches a real Task Scheduler.** The F6 tests use the `windows` fixture's fake `_schtasks`, and conftest's `no_task_scheduler_unless_faked` stays on. conftest's new autouse `fills_asked` stops any pass in the suite from starting a real fill unless its test puts `REAL_FILL` back.

## Findings

**SHOULD-1: a pass a person stopped still runs the fill, so Stop seems to hang.** tracker/runner.py:3054.
- R4 rules that a stopped, timed-out or app-closed pass still fills. When a person presses Stop on a Sort (Run now), the household work ends, but the final line waits for the fill: up to 65 s cold at 750 returns, and up to 300 s at the cap.
- Fix: skip the fill when `outcome == "stopped"`, i.e. `if not ns.dry_run and not ns.root and unproved is None and outcome != "stopped":`, and add the matching case to `test_a_dry_run_a_typed_root_and_an_unproved_checkpoint_do_not_fill`.
- This partly reverses R4, so the orchestrator rules on it. It is not an owner question.

**SHOULD-2: `schtasks` has no time limit, and it now runs at every start on the office PC.** tracker/scheduling.py:453.
- `_schtasks` calls `subprocess.run(command, capture_output=True, text=True)` with no `timeout`. This was already true, but until F6 the query ran only when something had changed. Now it runs at every launch, inside the step's lock (`_one_at_a_time`). If the Task Scheduler service hangs, that lock stays held and a later Repair or root save reports it as busy.
- Fix: pass `timeout=60` and raise `OSError(...)` from `subprocess.TimeoutExpired`, so every caller's existing `OSError` path reports it. Add a test in tests/test_scheduling.py: `test_a_schtasks_that_hangs_is_said_as_unreachable`.

**SHOULD-3: a person's one-household Sort pays the whole practice's cold fill, with no progress line.** tracker/runner.py:3054.
- On the first Sort of a day, after an upgrade, or after settings.json changes (all are part of the cache head), the fill re-reads every household. The hand-back measured 4-5.4 s at 150 households; N4 measured 65 s at 750. The progress file is already closed, so the window shows nothing new while it waits.
- Fix (one of the two):
  - when `lines` is set, emit one progress line before the fill (e.g. `_emit_line({"event": "preparing_overview"})`) and have the renderer show it;
  - or record a measured 750-household one-household Sort on a cold day in the hand-back, so the cost is a written choice.

**NIT-1: while nothing is kept, every Overview reply rewrites the cache file.** tracker/api.py:6105.
- `or not kept` rewrites a small file on each `firm` reply while nothing is keepable. R5a accepts this.
- Fix: `if keep != kept or (not kept and not firm_cache.holds(where, [head])):` writes once a day instead of on every reply.

**NIT-2: one query refusal can re-register the task at every start.** tracker/after_install.py:1253.
- A query refused for a reason other than "not found" (e.g. "Access is denied") reads as missing, so every start re-runs the step with `/create /f`. This is safe, but no log line says why.
- Fix: in `task_exists`, keep a non-zero exit other than "not found" on the error log once, e.g. via `errors.keep` with the exit code only.

**NIT-3: a test doesn't check the log entry it is named for.** tests/test_after_install.py:1350-1364.
- `test_a_schtasks_that_cannot_start_runs_the_step_and_says_so` doesn't check that `_task_missing` put the query failure on the local error log (the "says so" in the name).
- Fix: also assert that the error log carries "after_install: asking whether the scheduled task exists".

**NIT-4: the fill can push a long scheduled pass past Task Scheduler's limit.** tracker/runner.py:586 and 3054.
- The fill can add up to `FILL_TIME_LIMIT_SECONDS` (300 s) after a pass that has already run close to the task's two-hour `ExecutionTimeLimit` (`RUN_TIME_LIMIT_SECONDS`). The log and page are written after the fill, so Task Scheduler could stop the pass before writing them.
- Fix: pass `timeout=min(FILL_TIME_LIMIT_SECONDS, remaining)`, where `remaining` is measured from the pass's start against `RUN_TIME_LIMIT_SECONDS` minus a 10-minute margin. Skip the fill, with the warning, when nothing remains.

## Tests (each file in its own process, at most two at a time per interpreter)

| File | Python 3.11.15 (private venv, hash-checked locks) | Python 3.14 (C:\Python314) |
|---|---|---|
| tests/test_after_install.py | 97 passed, 3 skipped in 82.25s | 97 passed, 3 skipped in 67.33s |
| tests/test_scheduling.py | 116 passed, 4 warnings in 3.80s | 116 passed, 4 warnings in 1.70s |
| tests/test_firm_cache.py | 31 passed, 1 skipped in 2.60s | 31 passed, 1 skipped in 0.93s |
| tests/test_runner.py | 204 passed, 1 warning in 333.35s | 204 passed, 1 warning in 248.79s |
| tests/test_api.py -k "firm or after_install or cache" | 29 passed, 415 deselected in 110.70s | 29 passed, 415 deselected in 93.19s |
| tests/test_layers.py | 29 passed in 15.81s | 29 passed in 19.22s |
| tests/test_settings.py | 67 passed in 1.56s | 67 passed in 6.88s |

The warnings were there before this branch: runpy's "found in sys.modules" RuntimeWarning from the `__main__` tests.

- `python -m ruff check .`: All checks passed!
- `python tools/repo_map.py check`: "Map is current (421 nodes, generated 2026-10-01)". Its one warning, that the working copy of docs/repo-map.curated.json has CRLF line endings, doesn't make the map stale.
