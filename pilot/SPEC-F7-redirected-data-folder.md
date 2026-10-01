# Pilot 0.3 - F7: the data folder Windows redirects - SPEC

Status: written 2026-09-30, 10:05 PM Pacific, by the F7 session, for a
separate builder and reviewer. Decision **P193** (`pilot/DECISIONS.md`).
Source: `pilot/wintest/RESULTS-0.3.md` (F7, "Logo build") and
`pilot/handoffs/wincheck-0.3.md` ("Left", item 1).

**Hard rule kept.** No document was opened. The evidence below is row
counts of the store and checkpoint, the event name, time and writer of each
line of the made-up sample records, file names, sizes and times, and the
earlier sessions' own command lines - read at Jason's word ("Yes,
read-only", 2026-09-30).

## The root cause

**In one sentence:** the check session started the app from inside the
Claude desktop app, and Windows silently redirects `%LOCALAPPDATA%` writes
from programs started there into a private copy for the Claude package, so
that app read a copy of the data folder last current at 11:13 PM on 9/29 -
before the samples were first sorted - while the real store was left alone.

**The evidence.**

1. The private copy exists:
   `%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\tax-document-tracker-pilot`,
   holding `tracker.db` (40.7 MB), `record-heads.db`, `after-install.json`,
   `tracker-errors.log` and the rest; its `logs` folder dates from the first
   Windows check (2026-09-28, 10:11 PM). A process started from the agent's
   shell sees this copy at the normal path wherever one exists.
2. The redirect is proven on this PC: a file the agent's shell wrote to a new
   folder under `%LOCALAPPDATA%` was visible at the normal path and
   physically present only under `Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\`
   (written and removed by the F7 session). That process has **no** package
   identity (`GetCurrentPackageFamilyName` answers 15700, "no package"), so
   asking Windows "am I packaged?" does not detect it.
3. In the copy, the 25 returns the sample script made at 11:12 PM on 9/29
   hold line 1 only (their request list) in both the store (`applied_seq` 1,
   no documents, no statuses) and the checkpoint (count 1, advanced 11:12-11:13
   PM, never again). Their records on disk carry lines 2 onward, written at
   11:15 PM by the scheduled task - which Task Scheduler starts outside the
   Claude package, so it wrote the real store.
4. The app's engine in the copy then met line 2, stamped with this machine's
   name, which the copy's checkpoint never saw written and no intent owned:
   `store.py:2638` "says it was written on this machine, and this machine did
   not write it" (`_judge`, `store.py:2760-2797`) - 54 times at 7:46 PM and
   108 more at 8:4x-8:52 PM in the copy's error log, and never before 7:46 PM.
   That refusal is the screen's "Could Not Be Read"; the after-install check's
   1,700 findings ("the store holds 0 index row(s), the record carries 1") are
   the same gap, said correctly.
5. The real folder was in use by the program started outside Claude: the
   7:38 PM scheduled pass wrote `last-pass.json` there ("succeeded"), and the
   2024 return added to Test Household in the app at 7:43 PM has no row in the
   copy until 7:46 PM, when the app first ran from Claude's shell
   (`Start-Process` of the Start-menu shortcut, check session, 02:46 UTC).
6. The handoff's lead does not hold: the admission bump (`ADMISSION_VERSION`
   2 to 3, `store.py:397-418`, `_judge_the_applied_lines` 2121) only re-judges
   rows; it deletes nothing, and the 0.2-to-0.3 diff of `store.py`,
   `checkpoint.py` and `ledger.py` changes no rule of a line's writer.

**What this means for the office PC.** Nothing in the real store is
damaged, as far as the evidence reaches: the real folder could not be read
from the agent's shell (Windows shows the copy there), and starting a
process outside the package to read it was refused by the session's safety
check. **The deciding check is Jason's** (R6).

**Reproduce:** from a shell inside the Claude desktop app, run any engine
command with `TRACKER_DATA_HOME` unset (the sample script, `tracker.api
firm`, or `Start-Process` of the app); sort outside it (the scheduled task,
or the app from the Start menu); start the app from the shell again. A
pytest cannot make Windows redirect, so the tests below stand in a
redirected `%LOCALAPPDATA%` (R1's probe is injected, as `drive_type` is).

**F6 does not share the cause.** `after_install.launch()`
(`tracker/after_install.py:1196-1212`) skips when `_unchanged()` (1214-1223)
finds the program, designation and saved choice as the last clean run left
them; it never asks whether the scheduled task still exists, and the
uninstaller deletes the task (`pilot/installer/setup.iss:75-77`) while the
note stays. That happens on any PC. F6 keeps its own SPEC (handoff item 2),
but its Windows check must start the app outside Claude, by R4.

## What staff will notice (plain English)

- Started from the Start menu, the desktop shortcut or the schedule: nothing
  changes.
- Started from inside another program that Windows redirects (an AI
  assistant's window among them): the first screen says so in one sentence,
  and no return, household or pass is read or written, instead of every
  return reading "Could Not Be Read".
- Where Windows kept such a private copy, the first screen names it and asks
  a person to move it to the Recycle Bin.

## Rulings

**R1. The engine refuses a data folder Windows is redirecting.** Reason:
two copies of the store and checkpoint, each trusted by the programs that
see it, is the one thing decision 159's checkpoint cannot survive: each
copy refuses the other's lines (as F7 shows), and a pass run on the copy
would record moves in a store the schedule never reads.

- Where: `tracker/settings.py`, `data_home()` (666-690), **not**
  `resolve_data_home()` (614-662) or `default_data_home()` (766-772): the
  suite always sets `ENV_DATA_HOME`, and the tripwire's `real_places()`
  (`tests/conftest.py:686-735`) must still learn the real place.
- When: on Windows, only when `ENV_DATA_HOME` is unset or blank (a person
  who names a folder means it), once per process (a module-level answer; it
  cannot change while the process lives), before the first answer.
- How: a probe, injected like `drive_type` so it is testable anywhere:
  write a uniquely named empty file (`.tracker-redirect-probe-<pid>-<16 hex>`)
  directly in `%LOCALAPPDATA%`; look for that name in
  `%LOCALAPPDATA%\Packages\*\LocalCache\Local\`; remove it from wherever it
  landed; a hit is a redirect, named by the package folder. The file is
  removed in a `finally`. A probe that cannot write raises nothing new: the
  data home's own writers say what they cannot do, as today.
- Says (new constant `DATA_HOME_REDIRECTED`, a `SettingsError`, so
  `_machine_warnings` (`tracker/api.py:3543-3561`) and the pass
  (`tracker/runner.py:2808-2815`) say it with no new code):
  "Windows is giving this copy of the app a private data folder of its own,
  because it was started from inside another program ({package}). Close it
  and start Tax Document Console from the Start menu."
  `{package}` is the package folder's name (for example
  `Claude_pzs8sxrjxfjjc`), never a client's.
- Rejected: asking Windows for package identity (proven blind here, see
  evidence 2); comparing file IDs of the normal path and the package copy
  (read-only, but blind until the first redirected write has already made
  the copy).

**R2. A stale redirected copy is named on the first screen, never removed by
the app.** Reason: it holds client-derived data (decision 186), and the app
never deletes that; it is out of date and is never used once R1 holds.

- Where: a new `settings.redirected_copies() -> list[Path]`: every existing
  `%LOCALAPPDATA%\Packages\*\LocalCache\Local\<DATA_HOME_NAME>` (Windows
  only; read-only; nothing when `%LOCALAPPDATA%\Packages` is absent).
  `_machine_warnings` appends one sentence per copy (new constant
  `REDIRECTED_COPY`): "Windows kept a private copy of the app's data folder
  at {path}, from a time the app was started inside another program. The app
  never uses it and it is out of date; move that folder to the Recycle Bin."
- Not in `runner.left_behind()`: that list is decision 186's "beside the
  program", and its move group would move the copy into the data home.

**R3. The sample script never writes the real data folder.** Reason: on
9/29 it did, from inside Claude, and became the copy's first writer.
`pilot/wintest/make_samples.py` (24-46) builds under a throwaway
`TRACKER_DATA_HOME` (a `tempfile.TemporaryDirectory`, removed after) and
says so in its docstring; the app's first read then seeds the checkpoint
from the records, as a first sight does (`store.py:2800-2821`).

**R4. The Windows check starts the app outside Claude.**

- `pilot/wintest/run_checks.ps1` (215 onward, the step after install): start
  the shortcut with `explorer.exe "<shortcut>"`, never `Start-Process`, and
  say why in a comment.
- The next check's prompt (`pilot/wintest/PROMPT-0.3.md` is the model):
  "Start the app only from the Start menu, its shortcut through
  `explorer.exe`, or a person's click - never `Start-Process` from your
  shell. Any engine command from a checkout sets `TRACKER_DATA_HOME` to a
  folder of its own." Steps 19-21 are rerun this way after F7 and F6 land.

**R5. Docs.** `docs/runbook.md`, the paragraph "The app's data folder is
private to one Windows account" (39-50), gains: "Start the app from the
Start menu or its shortcut. A program started from inside another program's
window - some AI assistants among them - can be given a private copy of this
folder by Windows; the app refuses to run that way and says so on its first
screen." The README's data-folder line, if it names where the folder is,
gets the same sentence. The curated map node for `tracker/settings.py`
(`docs/repo-map.curated.json`) says R1 and R2; then `repo_map.py update`.

**R6. The office PC (no code).** The real store is expected to be whole.
Jason closes the app the check session started, starts Tax Document Console
from the Start menu, and opens Overview: the 27 sample returns should read
normally, and the after-install step runs once there with no findings.
Then Jason moves the private copy to the Recycle Bin (question Q1).

## Files and owning tests

| File | Change | Owning test |
|---|---|---|
| `tracker/settings.py` 614-690, new constants beside 136-150 | R1 probe and refusal; R2 `redirected_copies()` | `tests/test_settings.py` (beside 376-495) |
| `tracker/api.py` 3543-3561 | R2 sentence on the first screen | `tests/test_api.py` (the machine-warnings tests) |
| `pilot/wintest/make_samples.py` | R3 | none of its own; the reviewer runs it once on Windows |
| `pilot/wintest/run_checks.ps1` | R4 | `tests/test_single_source.py` if it quotes the script; else the reviewer reads it |
| `docs/runbook.md`, README, `docs/repo-map.curated.json` | R5 | `tests/test_single_source.py`, `tests/test_repo_map.py` |

New tests, named as their claims:
`test_a_redirected_data_folder_is_refused_by_name`,
`test_the_redirect_probe_leaves_nothing_behind`,
`test_a_named_data_folder_is_never_probed`,
`test_the_probe_runs_once_a_process`,
`test_a_stale_redirected_copy_is_named_on_the_first_screen`,
`test_no_packages_folder_names_no_copy`.

**Tests this SPEC runs (floor interpreter and the office's):**
`tests/test_settings.py`, `tests/test_api.py`, plus the guards
`tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_repo_map.py`, `tests/test_errors.py` (new wording) and
`tests/test_tripwire.py` (R1 sits beside the tripwire's data home); then
`ruff`, `repo_map.py check`. Windows proof before merge (CLAUDE.md:
behaviour that depends on the operating system): from the agent's shell on
this PC, `python -m tracker.api list` with `TRACKER_DATA_HOME` unset
answers R1's sentence, and leaves no probe file in either place.

## Open for Jason

**Q1. The private copy on the office PC** (client-derived data, made-up
samples only): (a) you move
`%LOCALAPPDATA%\Packages\Claude_pzs8sxrjxfjjc\LocalCache\Local\tax-document-tracker-pilot`
to the Recycle Bin yourself after R6's check - **recommended**; (b) leave it
until the build lands and its first screen names it; (c) keep it as
evidence. The build does not depend on the answer.

**Q2. Build now?** (a) build and review this SPEC next - **recommended**;
(b) stop here until you have run R6's check.
