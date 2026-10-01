# SPEC-check-scripts-0.3 - the Windows check scripts and one test flake (P200)

Decision P200 (`pilot/DECISIONS.md`). Sources: `pilot/wintest/RESULTS-0.3.md`
A1, N7 and N8; `pilot/handoffs/wincheck-0.3.md` "Left" item 4; `pilot/HANDOFF.md`
and `pilot/reviews/combined-review.md` N5 (the flake). Branch
`claude/check-scripts`, from `4534b30`.

The F7 rulings stay as they are: `run_checks.ps1` never starts the app (its
step 8 says how; `pilot/reviews/combined-rulings.md` ruling 3), and
`make_samples.py` builds under a throwaway `TRACKER_DATA_HOME`. Neither line is
touched.

## 1. A1 - the build trips the suite's end-of-run guard

**Cause.** `run_checks.ps1` started the named test files and then built the
installer while they ran, and the build writes `build-portable\pyi-work` and
`build-portable\dist` into the checkout, which the suite's end-of-run guard
(decision 185, "the session left a new folder in the checkout") fails in
every file still running.

**Ruling: build only after every test process has ended** (not: point the
build's work folders outside the checkout). Reasons:
- The guard is right to flag a new folder in the checkout, and the clash is
  the script's ordering, so the fix belongs in the script.
- `pilot\Build Pilot Installer.bat` is shared by every build (a person's too)
  and is not this lane's file; moving its work folders changes what every
  other build and its own test (`test_build`) expect.
- The cost is time only: the run takes as long as the slowest test file plus
  the build, instead of the longer of the two.

**Where.** `pilot/wintest/run_checks.ps1` step 4 (lines 200-236): the named
files are started together, then each is waited for and its verdict recorded;
step 5 (line 238 on) builds afterwards. The collection loop that sat after the
build is removed. Header comment (lines 10-16) says so.

**Owning tests.** `tests/test_pilot.py::test_the_check_script_builds_only_after_every_named_test_file_has_ended`
(new: the wait and the verdicts come before the build line).

**What the person running a check notices.** The log says "the build starts
when all have ended"; test verdicts appear before the build line; no file
reads FAIL with every test passed.

## 2. N7 - the silent install aborts while the app is open

**Cause.** The app open from an earlier step holds its own files, and Windows'
Restart Manager, which Inno Setup uses to close it, cannot close Electron's
window-less helper processes without force, so the installer's "files in use"
question is asked and `/SUPPRESSMSGBOXES` answers it with Abort (exit 5,
rolled back).

**Ruling: the script closes the app first, gracefully, and never forces it**
(not: `/CLOSEAPPLICATIONS`). Reasons:
- `pilot/installer/setup.iss` does not set `CloseApplications`, so Inno's
  default (`yes`) already applies, and Inno's documentation says a silent
  install then closes such applications by itself; `/CLOSEAPPLICATIONS` asks
  for what was already on, and the 0.3 install still aborted. The force
  variant (`/FORCECLOSEAPPLICATIONS`) would end the app without its own close,
  in the middle of a pass.
- Asking the window to close is what the app's own Close button does: a pass
  in progress stops after the file it is on (decision 203), and the window's
  storage is flushed.
- Only processes whose program file is the installed
  `Tax Document Console.exe` (in `Programs\Tax Document Console` or the
  earlier `Programs\Tax Document Tracker Pilot`) are counted, wherever that
  `Programs` folder is: the real `%LOCALAPPDATA%\Programs`, or a packaged
  app's private copy, `%LOCALAPPDATA%\Packages\<package>\LocalCache\Local\Programs`,
  where an install run from inside such an app lands (P193; the screen
  review's S1, accepted). `Get-AppExePatterns` writes both places for both
  names as path patterns whose fixed parts are escaped, so only the package
  folder is a wildcard and no program of another name or folder matches.
  Nothing is ever killed; if the app is still open after 30 seconds the script records
  `close_app` FAIL with the process ids and stops, telling the person to close
  it with File > Exit.
- Honest limit: the "window-less helpers" cause is the most likely reading of
  the install log's "RestartManager found an application ... Defaulting to
  Abort"; the full log is under `%USERPROFILE%\PilotTest`, which this build
  does not open. The ruling holds either way: the app is closed before the
  installer looks.

**Where.** `run_checks.ps1` lines 122-163, the `app-close` helpers
(`Get-AppExePatterns`, `Find-AppProcess`, `Close-App`, a lifted BEGIN/END
block as the test-file helpers are); step 6, lines 289-309, before the
installer's `Start-Process` (line 310).

**Owning tests.** `tests/test_pilot.py`:
- `test_the_check_script_closes_only_the_app_and_never_forces_it_before_installing`
  (static: no `Stop-Process`, `.Kill(`, `taskkill` or `/FORCECLOSEAPPLICATIONS`;
  the close and its stop come before the install);
- `test_the_check_script_asks_the_app_to_close_and_leaves_alone_what_will_not`
  (Windows, PowerShell 5.1: the helpers lifted as they are close a stand-in
  with a window, return a window-less stand-in still running and unkilled, and
  never touch a process whose program is not named);
- `test_the_check_script_finds_the_app_wherever_it_was_installed_and_nothing_else`
  (S1; Windows, 5.1: against a stand-in `%LOCALAPPDATA%` whose name holds
  `[x]`, the helpers find a stand-in program in the real `Programs` folder and
  in a `Packages\<package>\LocalCache\Local\Programs` copy, and neither a
  program of another name nor one in another folder; nothing is closed).

**What the person notices.** If the app is open, it closes by itself just
before the install (`close_app` INFO in `checks.json`); if it will not close,
the script stops with one sentence saying what to do, and nothing is forced.

## 3. N8 - `-Tests` takes only paths

**Cause.** The script tested each `-Tests` value with `Test-Path` as typed, so
a bare name (`test_build`) was not found and the run stopped.

**Ruling.** Each value is resolved by `Resolve-TestFile`: the name with `.py`
added when it has none, as typed, else under `tests\`
(`Get-TestFileCandidates`). `test_build`, `test_build.py`,
`tests\test_build.py` and `tests/test_build` name the same file. Only a `.py`
file is a test file, so `-Tests README.md` finds nothing and stops (the screen
review's N3). Every name is resolved before any test starts, so a typo stops
the run at once, and the message names the same places the resolver looked,
never "test_x.py.py" (N1). A file named twice, in any of those ways, runs once
under its first naming (`Get-UniqueTestFiles`, by full path; N2): two runs
would write one output file.

**Where.** `run_checks.ps1` lines 83-120 (inside the test-file helpers), step 4
lines 247-256; the header's example uses bare names.

**Owning tests.** `tests/test_pilot.py::test_the_check_script_takes_a_test_file_by_bare_name_by_file_name_or_by_path`
(Windows, 5.1, lifted helper);
`tests/test_pilot.py::test_the_check_script_takes_only_py_files_says_where_it_looked_and_runs_a_file_named_twice_once`
(N1-N3; Windows, 5.1, lifted helpers); the existing
`test_the_check_script_splits_a_comma_joined_test_list_and_reads_each_exit_code`
now looks for `Start-TestFile $vpy $file $out`.

**Prompt lines.** `pilot/wintest/PROMPT-0.3.md` gains "Note for the next check
(P200)", carried into the next check's prompt: the three naming forms, the
build after the tests, and the app being asked to close.

## 4. The `test_shell_menu` flake under Python 3.11

**The test.** `tests/test_shell_menu.py::test_open_error_log_opens_the_named_file_and_says_so_when_there_is_none`
(failed once with 12 files in parallel; passes alone and on `392ec27`).

**Cause.** The node harness waited fixed times - 100 ms for `main.js` to be
ready and 60 ms after each step - and Open Error Log's file check
(`fs.promises.lstat`, `app/main.js:436`) is not awaited by the menu click, so
on a busy PC the harness wrote its log before the check had answered.

**Ruling: wait on a condition, never on a time.** The harness counts what
`main.js` has started and not seen finish - Electron's `whenReady`, each fake
tracker child until it closes, every `fs.promises` call - and `settle()` turns
the event loop until that count is nought. Every continuation of a settled
promise runs before the next turn, so a turn with nothing pending means
`main.js` has finished answering. Both fixed waits are replaced by `settle()`.

**Where.** `tests/test_shell_menu.py` `_HARNESS`: lines 162-177 (`track`,
`settle`), the `whenReady` stand-in, the fake spawn (lines 228-232), the `fs`
stand-in's `promises`, and the run loop (lines 265, 283). `app/main.js` is not
touched.

**Proof.** A scratch probe ran every node-harness test with a slow PC
simulated (each `lstat` and `whenReady` 150 ms late): 17 failed with the old
harness, 0 with the new one. Then the file whole, under 3.11, three times.

## Files

| File | Change |
|---|---|
| `pilot/wintest/run_checks.ps1` | A1, N7, N8 |
| `pilot/wintest/PROMPT-0.3.md` | the note for the next check |
| `tests/test_pilot.py` | four new tests; one assertion follows a renamed variable |
| `tests/test_shell_menu.py` | the harness waits on a condition |
| `pilot/SPEC-check-scripts-0.3.md`, `pilot/handoffs/check-scripts-build.md` | this SPEC, the hand-back |

**One doc line outside this lane.** `CLAUDE.md` lines 323-324 say `-Tests`
"runs the files alongside the installer build"; after A1 it runs them, then
builds. The orchestrator owns that file; the wording to use: "runs the files
side by side, then builds the installer once they have ended."

## What waits for the next Windows check

Proven here: the helpers in Windows PowerShell 5.1 (lifted, as the tests do),
the script's parse, and the ordering by static tests. Not run here (it
installs the app): `run_checks.ps1` whole - the build after the tests, the
close of the real app before a real install, and `-Tests` with bare names
against the real `tests\` folder.
