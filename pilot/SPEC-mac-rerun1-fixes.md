# Pilot 0.3 - fixes from the Mac check's re-run 1 - SPEC

Status: written 2026-10-10 for separate builders and separate reviewers.
Decisions **P260 to P263** (`pilot/DECISIONS.md`). Source of every item:
Jason's Mac check re-run 1 of commit `287732c` on 2026-10-10
(`~/PilotTest/results/RESULT-rerun1.md`: failure 1, notes 3, 4, 5, 6 and 7),
read against the code at that commit, and Jason's instruction of the same
evening: "Fix the new errors found in this pass locally, testing to make sure
they pass before committing and merging to github." These fixes ship in Pilot
0.3; no version number is changed here.

**Not in this SPEC:** the background item's name in Login Items
("tracker-api, Item from unidentified developer"), which signing (SPEC-mac
R37) fixes; the overnight run; Google Drive; the Sorting word on a pass
shorter than the watch's cadence (a limit, not a bug); the PyInstaller
child's abort at build time (the library's own, section 4 only turns the
telemetry off at run time).

**Hard rule kept.** No generative AI reads a client document; every document
a test touches is made up by `tests/samples.py`. No step here reads a
client's file.

## What staff will notice (plain English)

- On a Mac, switching the app off under System Settings > General > Login
  Items > Allow in the Background now holds: the app's next start shows
  Setup Needs Attention with the sentence "macOS has switched the schedule
  off for this app…" under Details, registers nothing, and the switch stays
  off. Switching it back on registers again at the next start, as before.
- A return's page follows a scheduled pass: when the pass ends, its rows
  catch up with the counts, unless a sheet or dialog is open, in which case
  they catch up the moment it closes.
- After Change Clients Folder > Start, the page goes to the Overview of the
  new folder; a refused folder's sentence goes away once a folder is set.
- Nothing visible: the document reader's library is told at start never to
  send its own telemetry, and the suite's affected tests pass on a Mac.

---

## 1. Failure 1: the Login Items switch does not hold (P260)

**What the check saw (macOS 26.6).** The switch unloads the agent and
leaves its file in `~/Library/LaunchAgents`. `launchctl print-disabled
gui/<uid>` keeps answering `enabled` for the label (the only signal R27
asked), while Background Task Management marks the item "disallowed"
(`sfltool dumpbtm`, which hung twice when asked again and is not relied on).
So `_task_missing` saw a missing agent, the step registered it again, the
switch went back on, and `SCHEDULE_SWITCHED_OFF` was never said.

**Ruling (P260).** On a Mac, an agent launchd no longer has while its file
is still where the step put it is the person's switch, not a missing agent.
The launch door says `SCHEDULE_SWITCHED_OFF` and registers nothing, at every
start, until launchd has the agent again (the person switched it back on:
macOS loads it; or they ran Repair, the deliberate re-run, which registers
over anything). An agent whose file is gone is missing, as today, and is
registered again.

### 1.1 The probe (`tracker/scheduling.py`)

- `agent_switched_off(unloaded: bool | None = None) -> bool`: true when
  `launchctl print-disabled` lists the label as disabled (today's rule,
  kept for a macOS that says so), **or** when the agent is unloaded and
  `launch_agent_path().exists()`. `unloaded` is what the caller already
  knows from `task_query()` (exit code not 0); when `None`, the probe asks
  `task_query()` itself. `print-disabled` is asked first, as today; a
  `launchctl` that refuses raises `RuntimeError` as today. Docstring:
  the two signals and why (R27, re-run 1, H5).
- Nothing else in `scheduling.py` changes. `remove_agent` still unlinks the
  file, so a schedule removed in the app is never "switched off".

### 1.2 The launch door (`tracker/after_install.py`)

- `_switched_off(record, unloaded=None)` passes `unloaded` through to the
  probe. `_task_missing(record)` passes `code != 0` as `unloaded` (one
  `print`, one `print-disabled`: the launch door still asks launchd exactly
  twice when nothing changed). `launch()` asks `_switched_off(record)` as
  today (the probe then asks `task_query` itself; a third `launchctl` call
  on a launch that runs the step is fine).
- `SCHEDULE_SWITCHED_OFF`'s words do not change. The docstrings of
  `_switched_off` and `_task_missing` say the new rule and drop the sentence
  about H5 recording whether `print-disabled` reflects the switch (it does
  not, on macOS 26).

### 1.3 Acceptance (`tests/test_after_install.py`, the `mac` fixture)

- `test_the_launch_door_asks_a_mac_only_whether_its_agent_is_loaded`:
  the "agent is gone" half deletes the agent's file as well as setting
  `loaded = False` (a gone agent has no file), and still expects
  `ran.installed`; verbs on the unchanged launch stay `["print",
  "print-disabled"]`.
- `test_an_agent_macos_unloaded_but_whose_file_remains_is_the_persons_switch`
  (new): after Setup, `mac.launchd.loaded = False` with `switched_off`
  False and the file present (as macOS 26 leaves it): `launch()` answers
  `schedule == SWITCHED_OFF_KEY`, the sentence in `failed` and in
  `notice()["failed"]`, nothing bootstrapped, kicked or booted out, at two
  starts in a row; then `mac.launchd.loaded = True` (the person switched it
  on; macOS loaded it) and the next `launch()` registers (`installed`,
  `failed == ()`, `notice()` None).
- `test_an_agent_whose_file_is_gone_is_missing_not_switched_off` (new):
  `loaded = False` and the file unlinked: `launch()` registers again
  (`installed`), never `SWITCHED_OFF_KEY`.
- `test_the_probe_reads_both_signals` (new, `tests/test_scheduling.py` if
  that file holds the probe's tests, else beside the above): with the fake
  launchd, `agent_switched_off(unloaded=True)` is true with the file
  present and `switched_off` False; false with the file absent; true with
  `switched_off` True whatever the file; `agent_switched_off()` with no
  argument asks `print` itself.
- Every existing R27 test still passes unchanged except the one amended
  above.

**Documents.** `pilot/SPEC-mac.md` R27: one sentence added - "On macOS 26
the switch unloads the agent and leaves its file while `print-disabled`
still says enabled (re-run 1, H5), so an unloaded agent whose file remains
is read as the switch." `docs/runbook.md`'s "If the Allow in the Background
switch is turned off" paragraph: unchanged in what it promises; add that
the app learns it from launchd no longer holding the agent.
`pilot/mactest/PROMPT.md` H5: record that the app shows Setup Needs
Attention with the sentence under Details and that the switch stays off.

---

## 2. Note 5: the suite's affected tests fail on a Mac (P261)

**What the check saw.** 65 failing items in `test_api`, `test_after_install`,
`test_shell` and `test_tripwire`, identical at `6f88e3e` and `287732c`: the
suite was written against the Windows runner and the Linux floor, where
`settings.host_system()` answers `"nt"` or `"posix"`. On a Mac it answers
`"darwin"`, so a test that never said which computer it is on takes the
Mac branches: the after-install step's Time Machine job reaches the real
`tmutil` (the guard raises), the designation reads the Mac's own name
instead of the faked `platform.node()` ("office-pc"), the shell's
vocabulary says "Another Mac Sorting", and the tripwire's office-shaped
copy resolves the Mac's data home.

**Ruling (P261).** The suite stands on the Linux floor's answer unless a
test says otherwise: on a Mac, `settings.host_system` is pinned to
`"posix"` for every test by the same autouse fixture that guards the
schedulers, and `a_mac` keeps pinning `"darwin"` on top of it. The platform
itself is never patched; only the seam, as SPEC-mac says.

### 2.1 `tests/conftest.py`

- In `no_task_scheduler_unless_faked` (the autouse guard, so the pin is up
  before any other fixture and cannot be lifted by a test's `monkeypatch.undo()`):
  when `settings.host_system()` answers `"darwin"` before the pin,
  `patch.setattr(settings, "host_system", lambda: "posix")`. The docstring
  says why: the suite's default computer is the floor's, a Mac test says
  `a_mac`/`mac`.
- `a_mac` is unchanged (it pins `"darwin"` after the autouse pin).
- Nothing in `tracker/` changes for this section.

### 2.2 What else the four files need

The builder runs, on this Mac, `tests/test_api.py`,
`tests/test_after_install.py`, `tests/test_shell.py` and
`tests/test_tripwire.py` and makes every remaining failure pass by fixing
the **test** (a fake, a pin, a platform-aware expectation), never by
weakening what it claims, and never by changing `tracker/` for it. A
failure that turns out to be the code's is reported in the handoff, not
patched around. Known candidates after the pin: the tripwire's
office-shaped copy (`test_b_store`'s data-home canary and the
`test_api_entry`/`test_settings` items it runs), whose nested session
inherits the same conftest.

### 2.4 What the whole suite found on this Mac (added 2026-10-11)

The first whole-suite run on this Mac (`-n auto`, after jobs 1-3 landed)
left ten items, split by a run of the same files at `main`:

- **Pre-existing on a Mac, found now.** (a) Four room failures
  (`test_filer`, `test_content_check`, `test_runner`, `test_shell`'s
  lock-held sort): `layout.on_a_mac` is already pinned off for every test,
  so room is the absolute length, and this Mac's pytest folders are about
  145 characters long where the floor's are about 40. The suite's temporary
  root on a Mac is made short: in `tests/conftest.py`'s `pytest_configure`,
  on the controller only (never in an xdist worker, which has
  `workerinput`) and only when `basetemp` was not given, set
  `config.option.basetemp` to a folder of the suite's own under `/tmp`
  (`/private/tmp/<name>`, its real path), so a test's path is as long as
  the floor's. (b) `tests/test_view.py` imports `engagement_dirs` from
  `tracker.registry`, which the cleanup (9b3e9f8) moved to
  `tests/test_registry.py`: import it from there. (c) The tripwire's
  office-shaped tests under `-n auto`: make them pass on this Mac in a
  parallel run as they do alone.
- **New on the branch.** (d) `test_store`'s admission digest reads the
  source of `settings.host_system`, which the pin replaces: the pin is
  wrapped with `functools.wraps(original)` as `_on_a_mac`'s is, so
  `inspect` unwraps to the real source. (e) `office_shaped_copy`, a
  session-scoped fixture, errors at setup under `-n auto` on the branch
  (`StoreError`: the journal holds fewer lines than the store applied):
  find the cause - a session fixture is set up before the function-scoped
  autouse fixtures that give a test its store and its pins - and fix the
  fixture, never the store.

Acceptance: `python -m pytest -q -n auto` on this Mac ends with no failure
and no error; each change is test-only; `test_no_test_opens_the_real_data_home`
and the office-shaped canaries still prove the wire on a Mac.

### 2.3 Acceptance

- The four files pass on this Mac under the office interpreter (3.14; the
  floor is not installed on this Mac - the handoff says so).
- `test_the_suite_stands_on_the_floor_unless_a_test_says_a_mac` (new,
  `tests/test_conftest.py` if it exists, else `tests/test_tripwire.py`
  beside the other suite-shape tests): with `host_system` really answering
  `"darwin"` (monkeypatch the pre-pin seam, or the fixture's own helper), a
  bare test sees `"posix"`, and `a_mac` sees `"darwin"`.
- The whole suite (`python -m pytest -q -n auto`) is run once on this Mac
  by the orchestrator after the job lands, because the pin touches every
  test; its result goes in the pull request.

---

## 3. Notes 3, 4 and 7: the shell (P262)

### 3.1 The return page follows a scheduled pass (note 3)

`shellWatchLastPass`'s `"reread"` step (`app/renderer/shell.js`) today
adopts the list and stops; a return page that is open keeps its rows until
a navigation. After `adoptList(listed)`, when `shellRoute.level ===
"return"` and `!scanning`: if `dialogStack.length === 0`, `await
showReturn(shellRoute.ret)` (what F5 does); otherwise set
`shellReturnStale = true`. `closeDialog` (`app/renderer/app.js`), after it
pops the last dialog (`dialogStack.length === 0`), when
`shellReturnStale` and the route is still a return page: clear the flag and
`showReturn(shellRoute.ret)`. `showReturn` clears the flag too, so a
navigation in between does not redraw twice. A `showReturn` that throws is
handed to `failed(err)` once, as the reread's other errors are.

### 3.2 Start on the change-folder path goes to the Overview (note 4)

`saveRoot()` (`app.js`): after `set-root` succeeds and before
`bootstrap()`, `shellBack = null`, so `shellNeedsRoot(false, listed)`'s
rule (`shell.js`: a setup page with nothing to go back to goes to the
Overview) fires on the change path as it does on a first run. Cancel is
untouched: it still goes back to the last route. SPEC-shell 6.8 gains the
sentence "Start, when it succeeds, goes to the Overview of the folder just
set, however the page was reached."

### 3.3 A refused folder's sentence goes when a folder is set (note 7)

`saveRoot()`'s refusal (`failed(err, saveRoot)` in its catch) becomes a
keyed notice: `keyedNotice("set-root", failure, { retry: saveRoot })` with
the failure's own sentence and kind (the API's `failure` when the error
carries one, else `failureSentence(err)` as `failed` builds it);
`clearNotice("set-root")` when `set-root` succeeds and when the setup page
is left by Cancel. A second refusal with a different sentence replaces the
first (keyed notices already do).

### 3.4 Acceptance (`tests/test_shell.py`, node, `run_shell`)

- `test_a_scheduled_pass_that_ended_redraws_an_open_return_page` (new):
  the reread step lifted with fakes for `call`, `adoptList`, `showReturn`,
  `dialogStack` and `shellRoute`: on a return page with no dialog,
  `showReturn` is called once with the route's `ret`; with a dialog open it
  is not and `shellReturnStale` is true; on the Overview it is not called
  and the flag stays false; during `scanning` nothing is called.
- `test_closing_the_last_dialog_redraws_a_stale_return_page` (new):
  `closeDialog` lifted with the fakes: with the flag set and one dialog on
  the stack, closing it calls `showReturn` once and clears the flag; with
  two on the stack, closing one does not; with the flag set but the route
  not a return page, it does not and the flag is cleared by the next
  `showReturn` only.
- `test_start_goes_to_the_overview_however_the_setup_page_was_reached`
  (new): `shellNeedsRoot(false, listed)` with `shellRoute` setup and
  `shellBack` null goes to the overview; `saveRoot`'s success path (lifted
  with a fake `call`, `bootstrap`, `outcome`, `renderAfterInstall`,
  `renderShortOfRoom`) sets `shellBack` to null before `bootstrap`.
- `test_a_refused_folder_is_one_keyed_notice_that_goes_when_a_folder_is_set`
  (new): `saveRoot` with a `call` that rejects with a failure draws the
  keyed notice `set-root` with the sentence and a Retry; a second rejection
  with another sentence replaces it; a `call` that resolves clears it; the
  Cancel path clears it.
- Text pins, in the shape the file already uses, that `shellRefresh` and
  the reread both reach `showReturn` only on a return page.

**Documents.** `pilot/SPEC-shell.md` 6.8 (the Start sentence) and 8.3
(one line: an open return page follows the reread; a dialog defers it).

---

## 4. Note 6: the reader's library is told to send nothing (P263)

**What the check saw.** The Python child the disk-image build starts to
analyse `onnxruntime` aborted at exit in the library's telemetry worker
(`Microsoft::Applications::Events::HttpClientManager::onHttpResponse`): the
macOS wheel carries a telemetry client with an HTTP path. The standing
rule is that nothing in the reader's path talks to the network.

**Ruling (P263).** Right after the engine imports `onnxruntime`
(`tracker/ocr.py`, the engine's import and `_on_the_card`'s), it calls
`onnxruntime.disable_telemetry_events()`, before any session is made, as
the first thing it does with the module (before
`set_default_logger_severity`). A wheel without that function (none we
lock) is a `ReaderUnavailable`, said loudly like a missing import, never a
silent skip. The build-time child is PyInstaller's own and is out of scope.

### 4.1 Acceptance (`tests/test_ocr.py`)

- `test_the_reader_switches_its_librarys_telemetry_off_before_any_session`
  (new): with `onnxruntime.disable_telemetry_events` replaced by a recorder
  and the engine built the way the file's other engine tests build it (or,
  if none builds one without the models, a text pin that the call follows
  each `import onnxruntime` in `ocr.py` before any other use of the
  module), the recorder was called once before `set_default_logger_severity`.
- `test_a_library_without_the_telemetry_switch_is_said_as_unavailable`
  (new): the attribute removed, building the engine raises
  `ReaderUnavailable` naming it.

**Documents.** `docs/runbook.md` where it says the reader reads offline
(§6 step 5 or the reader's paragraph): one clause - "and its library is told
at start to send no telemetry".

---

## Jobs

| Job | Scope | Files | Builder | Tests it runs (the office interpreter, 3.14; the floor is not on this Mac) |
|---|---|---|---|---|
| **1** | Sections 1 and 4 | `tracker/scheduling.py`, `tracker/after_install.py`, `tracker/ocr.py`, `tests/test_after_install.py`, `tests/test_scheduling.py`, `tests/test_ocr.py`, `pilot/SPEC-mac.md` (R27 only), `docs/runbook.md`, `pilot/mactest/PROMPT.md` (H5 only) | sonnet | `tests/test_after_install.py`, `tests/test_scheduling.py`, `tests/test_ocr.py`, `tests/test_api.py` (the schedule commands), `tests/test_single_source.py`, `tests/test_layers.py`, `tests/test_errors.py` - **with the pin of section 2 applied locally in conftest first** if job 2 has not landed, since the file does not pass on a Mac without it; say so in the handoff |
| **2** | Section 2 | `tests/conftest.py`, and the test files section 2.2 names where a test's own fake or expectation must become platform-aware; `tests/test_tripwire.py` for the new suite-shape test | sonnet, after job 1 | the four files of section 2.2, `tests/test_single_source.py`, `tests/test_layers.py`, `tests/test_tripwire.py`, `tests/test_errors.py` |
| **3** | Section 3 | `app/renderer/shell.js`, `app/renderer/app.js`, `tests/test_shell.py`, `pilot/SPEC-shell.md` | sonnet | `tests/test_shell.py`, `tests/test_shell_menu.py`, `tests/test_pilot_ui.py`, `tests/test_single_source.py`, `tests/test_tripwire.py`, `tests/test_errors.py`, `tests/test_layers.py` |

Jobs 1 and 3 share no file and run side by side; job 2 follows job 1. No
builder runs `tools/repo_map.py update` or commits: the orchestrating
session refreshes the map once, runs `python -m ruff check .`,
`tools/repo_map.py check` and `tests/test_repo_map.py`, runs the whole
suite once on this Mac (section 2.3), and commits each job as its own
commit after its review has no findings. Each builder writes a handoff
note for the reviewer in the session's scratch folder (never in the
checkout): what was built, what the tests said (output pasted), what is
left.

**Review** (opus, high effort, a session that did not build): numbered
findings against this SPEC's sections, each with the line it fails. A
finding that survives one rebuild is fixed by the reviewer's tier.
