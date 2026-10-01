# P200 build hand-back: the Windows check scripts and the test_shell_menu flake

Branch `claude/check-scripts` from `4534b30`. SPEC: `pilot/SPEC-check-scripts-0.3.md`
(each item's cause, ruling, lines, tests, what a person notices). Not pushed.

## What was built

| Item | Ruling | Where |
|---|---|---|
| A1 | Build only after every named test file has ended (not: build folders moved out of the checkout - that changes the shared build script). | `pilot/wintest/run_checks.ps1` steps 4-5 |
| N7 | Close the app first, as its own Close button does, only processes whose program is the installed `Tax Document Console.exe`; never forced; still open after 30 s = `close_app` FAIL and a stop with one sentence (not `/CLOSEAPPLICATIONS`: it is Inno's default already and the install still aborted). | `run_checks.ps1` app-close helpers, step 6 |
| N8 | `-Tests` takes `test_x`, `test_x.py`, `tests\test_x.py`, `tests/test_x`; every name is resolved before any test starts. | `Resolve-TestFile`, step 4 |
| Flake | `test_open_error_log_opens_the_named_file_and_says_so_when_there_is_none`: the harness waited fixed 100 ms / 60 ms, and the error-log file check is not awaited by the click, so a busy PC logged before it answered. The harness now counts pending work (whenReady, fake children, `fs.promises`) and waits until it is nought. | `tests/test_shell_menu.py` `_HARNESS` |
| Prompt | "Note for the next check (P200)" with the three naming forms, the build order and the app close. | `pilot/wintest/PROMPT-0.3.md` |

F7 rulings untouched: step 8 still never starts the app; `make_samples.py` unchanged.

## Results (each file its own process)

| File | Python 3.11.15 (scratchpad venv, hash-checked) | Python 3.14 (`C:\Python314`) |
|---|---|---|
| tests/test_shell_menu.py | 34 passed, 3 skipped - three whole-file runs, all pass (3.2-3.7 s each, was 13.4 s) | 34 passed, 3 skipped |
| tests/test_pilot.py (guards run_checks.ps1; 4 new tests) | 28 passed | 28 passed |
| tests/test_pilot_installer.py (guards the scripts' names) | 20 passed | 20 passed |
| tests/test_single_source.py | 179 passed | 179 passed |
| tests/test_repo_map.py | 80 passed | 80 passed |

Flake proof: a scratch probe ran every node-harness test of `test_shell_menu` with each `lstat` and `whenReady` 150 ms late - old harness 17 failed (the flaky test among them), new harness 0. Dead code: the harness's `wait` helper and the post-build collection loop were removed; nothing else unused. `ruff check .`: all checks passed. `run_checks.ps1` parses in PowerShell 5.1.26100 with 0 errors.

## Proven here, and what waits for the next Windows check

- Proven: the lifted helpers in PowerShell 5.1 - name resolution (4 forms + a miss); the close helper closes a stand-in with a window, returns a window-less one still running and unkilled, and touches no unnamed process; the order (tests waited for and recorded before the build; close before install; no Stop-Process, Kill, taskkill or force flag) by static tests.
- Waits for the next Windows check (not run here; it installs the app): `run_checks.ps1` whole - the build after real test files, the real app closed before a real install, `-Tests` bare names against the real `tests\`.

## Left for the orchestrator

- `CLAUDE.md` lines 323-324 still say `-Tests` "runs the files alongside the installer build"; outside this lane. Wording: "runs the files side by side, then builds the installer once they have ended."
- `pilot/DECISIONS.md` row P200: status "SPEC to write" -> built; and the N7 cause reading (window-less Electron helpers) is the likely one, from the install log line quoted in RESULTS-0.3; the full `install.log` under `%USERPROFILE%\PilotTest` was not opened.

## Review fold (2026-10-01 02:07, branch `claude/fold-screen` from 7e90834)

Findings from `pilot/reviews/lanes-screen-review.md`, as ruled in `pilot/reviews/lanes-rulings.md` "Screen and scripts".

- **S1 (accepted, fixed).** `pilot/wintest/run_checks.ps1` 123-139 new `Get-AppExePatterns`: both product names, in the real `%LOCALAPPDATA%\Programs` and in `%LOCALAPPDATA%\Packages\*\LocalCache\Local\Programs`, fixed parts wildcard-escaped; 144-147 `Find-AppProcess` matches those patterns (`-like`; a plain path matches only itself); step 6 line 299 uses it. Still never forced, still nothing but `Tax Document Console.exe`. New test `tests/test_pilot.py::test_the_check_script_finds_the_app_wherever_it_was_installed_and_nothing_else` (5.1, stand-in %LOCALAPPDATA% named with `[x]`: finds the real and the Packages copy, not another name or folder, closes nothing). `pilot/wintest/PROMPT-0.3.md` P200 note gains the line.
- **N1 (fixed).** `run_checks.ps1` 83-91 `Get-TestFileCandidates`; the stop message (248-252) names those same places, never ".py.py".
- **N2 (fixed).** `run_checks.ps1` 100-111 `Get-UniqueTestFiles` (by full path, first naming kept); step 4 line 256.
- **N3 (fixed).** Only `.py` names are candidates, so `-Tests README.md` stops. N1-N3 test: `tests/test_pilot.py::test_the_check_script_takes_only_py_files_says_where_it_looked_and_runs_a_file_named_twice_once` (5.1, lifted helpers).
- The whole script parses in Windows PowerShell 5.1.26100 (0 errors). `run_checks.ps1` was not run whole (it installs the app); the app was not started or closed; nothing under %USERPROFILE%\PilotTest or %LOCALAPPDATA% was opened.
- `pilot/SPEC-check-scripts-0.3.md` sections 2 and 3 (rulings, line ranges, owning tests) updated.

Runs (each file its own process, two at a time per interpreter): Python 3.11.15 (scratchpad venv) / C:\Python314:
- tests/test_pilot.py: 30 passed in 10.43s / 30 passed in 11.65s
- tests/test_single_source.py: 179 passed in 40.21s / 179 passed in 38.85s
- tests/test_repo_map.py: 80 passed in 27.69s / 80 passed in 26.07s
- `python -m ruff check .`: All checks passed! `python tools/repo_map.py check`: Map is current (424 nodes).
