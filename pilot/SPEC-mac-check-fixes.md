# Pilot 0.3 - fixes from the Mac check - SPEC

Status: written 2026-10-11 for separate builders and separate reviewers.
Decisions **P256 to P258** (`pilot/DECISIONS.md`). Source of every item:
Jason's Mac check of commit `6f88e3e` on 2026-10-10 (its RESULT.md: findings
1 and 2, notes 3 and 4), read against the code at that commit. These fixes
ship in Pilot 0.3; no version number is changed here.

**Not in this SPEC:** the Gatekeeper steps the check could not run (Open
Anyway, a quarantined Downloads copy), the overnight run, a real Google
Drive folder, and the H-series steps the walk skipped. Those are the next
Mac check's list, not code.

**Hard rule kept.** Every document in play is made up by
`tests/samples.py` or by this SPEC's additions to
`pilot/wintest/make_samples.py`. No generative AI reads a client document;
no file outside `~/PilotTest` is touched by the kit.

## What staff will notice (plain English)

- While the schedule's pass is running, the side panel says "Sorting" with
  a quiet bar, not "Sort Failed", and there is no red notice. When the pass
  ends, the counts and the pages catch up by themselves within a minute,
  and sooner when the window is clicked. Refresh is no longer needed.
- "Machine Needs Attention" and "Setup Needs Attention" each carry a
  **Details** disclosure. Opening it shows the engine's sentence - what is
  wrong and what to do - instead of sending the person to the error log.
- After Start, and after an upgrade's first open, the app says in a toast
  that this computer now runs the schedule, in the engine's words.
- The Mac check kit's run-log check reads the right line, the sample pile
  gains a macro workbook, an email and a zip so step 10 can be walked, and
  the kit's expected wording matches what the app shows.

---

## 1. Finding 1: a scheduled pass in progress is drawn as a failure (P256)

**Root cause, two halves.** The engine's last-pass file records three
results: started, succeeded, failed. `api._last_pass()` flattens that to
one flag, `ok = result == PASS_SUCCEEDED`, so a running pass answers
`ok: false` exactly as a failed one does; `shell.js` `drawLastSort` and
`syncSortNotice` key on `ok === false` and draw "Sort Failed" with the
failed notice on every page (ruling 20). Second half: the shell learns
`last_pass` only from a `list` reply - start-up, its own Sort's end
(decision 203), F5 - so a pass started by launchd or Task Scheduler never
tells it anything. The wrong word stays until a person presses Refresh.
The runner's own `level` for a running pass is already "ok": the engine is
right and the page is wrong.

**Ruling.** A running scheduled pass is its own state, drawn as sorting;
the shell asks the engine for the last pass on its own, cheaply, and asks
`list` once when a pass has ended, as decision 203 already does for the
app's own Sort.

### 1.1 The API

- `_last_pass()` gains `running` (bool): the file's result is
  `runner.PASS_RUNNING`. `ok` keeps its meaning, "the last pass ended well"
  (false while running, false when there is none or the file cannot be
  read); `running` is false in those cases too. Docstring updated.
- A new command, `last-pass`, answers `{"last_pass": _last_pass()}` and
  reads only the settings file and the last-pass file: no root walk, no
  store, no journal, no lock - the shape of `watch` (decision 193). It is
  registered beside `watch` in the command table and is **not** a writing
  command. It is a CLI the app runs, so it keeps its place in the table
  and gets a line in `tracker/api.py`'s module docstring where the other
  commands are listed, if they are.
- Two numbers the page never types, under `vocab.last_pass_watch`:
  `{"running": LAST_PASS_WATCH_RUNNING_SECONDS, "idle": LAST_PASS_WATCH_IDLE_SECONDS}`,
  5 and 60. Five while a pass runs (the lock watch's cadence); sixty
  otherwise, because one spawn of the engine a minute is the most an idle
  window may cost on a Mac on battery.
- One word under `screen.last_sort`: `"scheduled": "Sorting"` (Title
  Case, like its neighbours). `pilot/wording-shell.tsv` gets its row.

### 1.2 The shell (`app/renderer/shell.js`)

- `drawLastSort`: after the `scanning` branch and before the `never`
  check, `last.running` draws `words.scheduled` in `--text-caption` with
  the 4px bar and no values (as "Stopping" draws it), and never the
  `is-failed` class. The file being read is still never named (P63).
- `syncSortNotice`: a running scheduled pass is left as it is, exactly as
  the app's own running sort is: `if (scanning || (last && last.running)) return;`.
  Ruling 28 holds: the notice stays while the record's last pass failed
  and goes when the record says the next one worked.
- A watcher, `shellWatchLastPass()`, started (or re-timed) by `shellAdopt`
  whenever a list lands, and run once more at once on the window's `focus`
  event. One timer at a time; its delay is `vocab.last_pass_watch.running`
  seconds while `shellLastPass.running` is true, `idle` otherwise. A tick
  does nothing while `scanning` (the app's own pass re-asks `list` at its
  end already) and never overlaps itself (an `asking` flag, as the lock
  watch has). A tick calls `call(["last-pass"])` and hands the reply to a
  pure function:

  ```
  lastPassStep(held, fresh)  ->  "same" | "adopt" | "reread"
  ```

  - `"reread"` when a pass has ended since the shell last looked: `held`
    was running and `fresh` is not; or `fresh.when` differs from
    `held.when` and `fresh` is not running (a whole pass came and went
    between ticks); or `held` was null/`when`-less and `fresh` has a
    `when` and is not running.
  - `"adopt"` when `fresh` says something new but no pass has ended:
    `fresh` is running and (`held` was not, or `held.when` differs).
  - `"same"` otherwise.

  On `"adopt"`: `shellLastPass = fresh; shellChanged();`. On `"reread"`:
  `adoptList(await call(["list"]))` (app.js), exactly what F5 and
  `passEnded` do - the counts, Needs Review and the last-sort line all
  follow. Never `loadEngagements()`: that is the start-up path, which
  re-applies the vocabulary, rebuilds the Schedule dialog's interval list
  (losing an open dialog's choice) and redraws the whole page (review 1,
  finding 1). `scanning` is checked again when the reply lands, not only
  before the call: a tick whose reply arrives after the app's own Sort
  began does nothing (review 1, finding 4). On `"same"`: nothing. A `last-pass` call that throws stops the watcher
  and is said once by `failed(err)` (decision 193's one rule); the next
  list adopt starts it again. No silent swallow, no notice per tick.
- Nothing else in the shell reads `ok`.

### 1.3 Acceptance (fail before, pass after)

`tests/test_api.py`
- `test_the_app_state_reports_the_last_pass` extended: a file written with
  `result=PASS_RUNNING` answers `running: true, ok: false` with its `when`;
  the succeeded and failed files answer `running: false`; an unreadable
  file answers `running: false, ok: false, when: None`.
- `test_last_pass_is_answered_without_a_root_or_a_store` (new): the
  `last-pass` command answers the same dict as `list`'s `last_pass` with no
  clients root chosen **and with the store made unopenable** (its path
  pointed at a folder, or `store.open` patched to raise), proving it was
  never opened; and `vocab.last_pass_watch` is `{running: 5, idle: 60}`.
- `test_the_scheduled_sorting_word_is_in_the_screen_vocabulary` (new, the
  shape of `test_the_speed_round_words_are_in_the_screen_vocabulary`).

`tests/test_shell.py` (node, `run_shell`)
- `test_a_scheduled_pass_still_running_is_drawn_as_sorting_not_as_a_failure`
  (new): `drawLastSort` with `{ok: false, running: true, when}` and
  `scanning` null draws the `scheduled` word, a `progressbar`, and no
  `is-failed`; with `running: false, ok: false` it draws the failed word as
  before; with the app's own `scanning` set it draws the running count as
  before.
- `test_a_failed_last_sort_is_a_keyed_notice_without_retry_that_clears_when_the_record_says_it_worked`
  gains a shape, `{...line, ok: false, running: true, when}` with
  `scanning` null, asserted `[]` ("left as it is while a scheduled pass runs").
- `test_the_shell_asks_list_again_once_a_scheduled_pass_has_ended` (new):
  `lastPassStep` over the table in 1.2 - every row named by the claim it
  makes - and `shellWatchLastPass`'s tick lifted with fakes for `call`,
  `loadEngagements`, `shellChanged`, `failed` and the timer: a tick that
  sees the pass end calls `loadEngagements` once; a tick during `scanning`
  calls nothing; a throwing `call` is handed to `failed` once and stops
  the timer; a throwing reread is handled the same way; a tick before the
  first list lands, or after a stop, does nothing; a reply landing after
  `scanning` was set does nothing (the builder's deviations 2 and 3 and
  finding 4, each a named test).
- A text pin that `shellAdopt` starts the watcher and that the window's
  `focus` listener ticks it.

**Documents.** `pilot/SPEC-shell.md` 8.3 gains the row
`| Scheduled sort running | "Sorting" | --text-caption | the bar, no values |`
and 8.4's sort-failed line notes it is left as it is while a scheduled
pass runs. `docs/runbook.md`'s last-pass paragraph, if it says the app
shows the line only on refresh, says it follows by itself.

---

## 2. Finding 2: the sentences only reach the error log (P257)

**What the check saw.** From the disk image the screen shows two headings,
"Machine Needs Attention" and "Setup Needs Attention"; the sentence that
says *what* and *what to do* ("The app is running from /Volumes/…. Drag it
into Applications…") goes to the error log only
(`renderMachineNotices`, `renderAfterInstall`). At an upgrade's first open
nothing is said at all: `renderAfterInstall` shows a notice only when the
step left findings, and the launch door's reply (which carries
`installed` and `schedule_sentence`) is dropped by `main.js`, which forwards
only "ran". At Start, `set-root`'s reply carries the same sentence and the
page logs it only on failure. SPEC-mac steps 5, 8 and 12 and decision 186
("a sentence the app's first screen keeps showing until it is fixed") expect
the sentence on the screen; SPEC-shell 8.4 ("one line each") and E28
("no path") made it a heading. Both were right about different things.

**Ruling.** The one line stays one line and path-free. Under it, a
**Details** disclosure, closed by default, holds the engine's sentence or
findings as they are. Opened by the person, it may name the program's
folder, the data folder or the clients root - never a client's file (P63
holds: nothing in `machine_warnings` or the after-install findings names a
document). The error log still gets the same text (unchanged). Good news -
the schedule registered - is a toast, as `outcome` already treats it.

### 2.1 Notices gain a detail (`app/renderer/app.js`)

- `notice(failure)` accepts `failure.detail` (a string, lines joined by
  `\n`). `drawNotice` draws it after the text and before the buttons as
  `<details class="notice-detail"><summary>{word}</summary><div class="notice-detail-text">…</div></details>`,
  one block per line, closed. The word is `vocab.screen.notices.details`
  = "Details" (new; `wording-shell.tsv` row). No detail, no element.
- `keyedNotice` treats a changed `detail` as a changed notice (redraw), so
  a second machine warning joining the first is seen.
- Only two callers put a detail on the screen: the machine warnings and
  the after-install findings. `syncNotices` shows a detail only when the
  entry marks it for the screen (`shown: true`, or the caller puts
  `detail` on the failure itself); every other caller's detail - a broken
  row's error and stack (`pages.js`), the household pause and feed
  sentences - stays in the error log only, as E30 and principle 7 say
  (review 1, finding 2; whether the pause and feed sentences may show is
  Q3 below). `renderMachineNotices` marks its entry for the screen.
  `renderAfterInstall` passes `[left.wait, ...lines].filter(Boolean).join("\n")`
  as the detail and still logs it; `wait` is the engine's sentence
  (`after_install.FINDINGS_WAIT`) on every path - the `list` reply's
  `notice()` already carries it, and the replies of `set-root`,
  `install-schedule`, `move-schedule-here` and `set-schedule` gain the same
  `wait` in their `after_install` (empty without findings), so `noticeOf`
  reads the reply's `wait` and never the vocabulary's heading word (review
  1, finding 3: the two paths differed, so the keyed notice redrew and
  logged twice at every Start and a dismissed one came back).
- `pilot-ui.css`: `.notice-detail` under the text, full width, `summary`
  in the notice's ink at caption size, the text at caption size with
  `white-space: pre-wrap` and `overflow-wrap: anywhere` (a path must wrap,
  never widen the notice).
- `tooltip.js`/Escape and the dismiss button are untouched.

### 2.2 The schedule's sentence when the step registers it

- `set-root` (Start): when `result.after_install.installed` is true, the
  page toasts `result.after_install.schedule_sentence`
  (`outcome(sentence, "ok", { toasted: true })`) before `bootstrap()`.
  The toast lasts six seconds; the kit reads it at once (section 3).
- The launch door: `main.js` forwards `{installed, schedule_sentence}` from
  the reply on `LAUNCH_DONE_CHANNEL`; `preload.js` passes the payload to
  the listener; `app.js`'s `onAfterInstallDone` toasts the sentence when
  `installed` is true, then asks `list` again for the notice as now. The
  screenshot tool's stub (listener null) still works.
- `set-schedule` and `install-schedule` already toast; unchanged.
- The screenshot harness (`pilot/harness/stub.js`, `pilot/harness/app-stub.js`)
  answers `last-pass` with a not-running shape and carries whatever the
  reread path needs, so a focus event or a run past the idle cadence puts
  no failed notice on a screenshot (review 1, finding 5).

### 2.3 Acceptance

`tests/test_shell.py` (node)
- `test_a_notice_with_a_detail_keeps_one_line_and_a_closed_details_block`
  (new): `drawNotice` lifted with the harness's element fakes: a failure
  with `detail: "a\nb"` draws the text, a `details` that is not open with
  the `Details` word and two lines, then the dismiss; without `detail` no
  `details` element.
- `test_machine_warnings_and_setup_findings_reach_the_screen_as_details`
  (new): `renderMachineNotices` and `renderAfterInstall` lifted with a
  recording `keyedNotice`/`syncNotices`: the sentence set arrives as the
  detail and is still logged.
- `test_the_schedule_sentence_is_toasted_when_the_step_registered_it`
  (new): the Start path and the launch-done listener toast
  `schedule_sentence` only when `installed` is true (text pins on
  `main.js` and `preload.js` for the forwarded payload, in the shape of
  the existing main.js pins).

`tests/test_api.py`
- `test_the_details_word_is_in_the_screen_vocabulary` (new).

**Documents.** `pilot/SPEC-shell.md` 8.4: "One line each … a notice may
carry a closed Details disclosure holding the engine's sentence; the line
stays one line." E28/E30's "no path" is read as "no path on the line".
`docs/runbook.md`: where it says the sentence is in the error log, it says
"under Details on the notice, and in the error log", and its schedule
paragraph says the app toasts the registration sentence at Start and at
the first open after an upgrade. SPEC-shell's E30 row says "details under
Details and in the error log" (review 1, finding 7).

---

## 3. Notes 3 and 4: the Mac check kit (P258)

### 3.1 The run-log check reads the wrong line (note 3)

`pilot/mactest/run_checks.sh` line 456 reads the run log's first line for
`reader=processor`. Since decision 189 the first line is
`[stamp] pass started` (`runner.PASS_STARTED_LINE`); the reader line is the
pass's closing summary (`runner.append_log`). The check fails on every Mac
whether or not the reader ran. Fix: `grep -q "reader=processor" "$SMOKE/runs.log"`
over the whole log; the note's words become "the run log names no
processor". `runner.py`'s field comment at line 1065 ("the run log's first
line says it") is corrected to "the pass's summary line says it".
`tests/test_pilot.py`'s check of the script, where it pins the line, follows.

### 3.2 The sample pile has no macro workbook, email or zip (note 4)

`pilot/wintest/make_samples.py` (shared by both kits, SPEC-mac R33) adds
three made-up files to `Drop files here` **after** `build_samples`, so the
suite's pile and every count it pins are untouched:

| File | How it is made | What it proves |
|---|---|---|
| `Donation Receipts {YEAR} with macros.xlsm` | `tests/samples.donations_xlsx`'s archive, rewritten with the workbook part's content type set to `application/vnd.ms-excel.sheet.macroEnabled.main+xml` in `[Content_Types].xml` (Excel refuses a file whose suffix and declared type disagree; review 1, finding 1). Still no macro inside; the suffix is what `filer.bears_macros` reads. The test asserts the content type. | step 10: the review copy is marked for Protected View on Windows and opens in Excel; on a Mac the app shows R8's sentence |
| `Email from John Smith.msg` | `tests/samples.msg_bytes([{...}])` holding one made-up PDF attachment from `text_pdf`: a 1099-INT from a payer the pile does not hold ("Riverside Savings Bank"), so it is filed as its own document and not as a duplicate of the pile's (review 1, finding 3) | the email path and its "Came in Email" word (P116) |
| `Scanned forms.zip` | `zipfile` (standard library) holding one made-up PDF from `scanned_pdf` | the zip path |

The script's docstring names them, and `pilot/wintest/SAMPLE-DOCUMENTS.md`
says its zip holds 14 of the made-up documents and names the three the
script adds beyond it (review 1, finding 8). Where a kit document quotes the pile's
counts ("14 files", "filed 9, review 4, …"), the builder runs the pile once
through the engine's dry pass and updates the quote; nothing in the suite
pins those numbers (the frozen smoke compares the package with the source
on the same pile). `tests/test_pilot.py` gains
`test_the_sample_pile_holds_a_macro_workbook_an_email_and_a_zip`: the three
names are in the inbox after the script runs under a throwaway
`TRACKER_DATA_HOME`, the `.msg` opens with `tracker.containers` (or
whatever reads it) to one attachment, the zip to one member.

### 3.3 The prompt and the template say what the app shows

`pilot/mactest/PROMPT.md` and `pilot/mactest/RESULTS-TEMPLATE.md`:

- Step 5: "the first screen shows **Machine Needs Attention**; its Details
  shows the sentence for that place (…)". Record the sentence from Details.
- Step 8: "a toast (bottom of the window, six seconds) says 'This computer
  (<name>) now runs the schedule…'; read it at once". The Time Machine job
  shows nothing when it works (its success line lives only in the step's
  own lines; H9 proves the exclusion with `tmutil`); a refusal is a finding
  under Setup Needs Attention's Details, recorded word for word (review 1,
  finding 2).
- Step 9: add "while the pass runs the side panel says Sorting; when it
  ends the counts and Needs Review follow by themselves within a minute
  (sooner on a click into the window), with no Refresh".
- Step 10: name the three files of 3.2.
- Step 12: "a toast repeats step 8's sentence at the first open".
- Under the safety rules, one new paragraph: *If this session's permission
  rules deny a folder the walk needs (the app's data folder, the run log,
  the inbox), record that step NOT VERIFIED naming the rule and tell
  Jason; never work around a rule. If desktop computer use is absent, the
  app may be driven through its own page (Electron's debugging port) with
  the folder picker stood in for at the app's picker boundary; say so at
  the top of the result, and every step that needs a macOS dialog or the
  Mac's password is NOT VERIFIED.* (What the 2026-10-10 check did, made
  the rule.)
- SPEC-mac section 3's steps 5, 8, 9 and 12 say the same, in one line
  each; its R-rows are not rewritten.

`tests/test_pilot.py`'s prompt/template cross-checks follow (the test
that holds the prompt, the template and the script to one another).

---

## Open for Jason

- **Q1.** The idle cadence of the last-pass watch (60 s). It costs one
  spawn of the engine a minute while the window is open. If that is too
  much on a laptop, the alternative is focus-only (no idle timer): the
  page then catches up only when clicked into. Built as 60 s; one number
  to change.
- **Q2.** Whether the sentence should be visible without a click (an open
  Details by default) on the setup page only, where a buyer first meets
  it. Built closed everywhere.
- **Q3.** Whether the household pause ("Two Years Open") and the prior-year
  feed sentences may also show under Details. Built log-only, as before.
- **Q4.** The reader warning ("Install Folder Name Too Long") has no
  Details either; its sentence names the install folder. Built as before.

---

## Jobs

| Job | Scope | Files | Builder | Tests it runs (both interpreters: 3.11, the floor, and the office's) |
|---|---|---|---|---|
| **1** | Sections 1 and 2 | `tracker/api.py`, `tracker/after_install.py` (the reply's `wait` only), `app/renderer/shell.js`, `app/renderer/app.js`, `app/main.js`, `app/preload.js`, `app/renderer/pilot-ui.css`, `pilot/harness/stub.js`, `pilot/harness/app-stub.js`, `pilot/SPEC-shell.md`, `pilot/wording-shell.tsv`, `docs/runbook.md`, `tests/test_api.py`, `tests/test_shell.py`, `tests/test_single_source.py` (one pin) | sonnet | `tests/test_shell.py`, `tests/test_shell_menu.py`, `tests/test_api.py`, `tests/test_single_source.py`, `tests/test_tripwire.py`, `tests/test_errors.py`, `tests/test_layers.py` |
| **2** | Section 3 | `pilot/mactest/run_checks.sh`, `pilot/mactest/PROMPT.md`, `pilot/mactest/RESULTS-TEMPLATE.md`, `pilot/wintest/make_samples.py`, `pilot/wintest/SAMPLE-DOCUMENTS.md`, `pilot/SPEC-mac.md` (section 3 only), `tracker/runner.py` (one comment), `tests/test_pilot.py` | sonnet | `tests/test_pilot.py`, `tests/test_pilot_installer.py`, `tests/test_single_source.py`, `tests/test_runner.py` (the comment is in a dataclass; prove nothing moved) |

The two jobs share no file and run side by side. Neither runs
`tools/repo_map.py update` or commits: the orchestrating session refreshes
the map once, runs `python -m ruff check .`, `tools/repo_map.py check` and
`tests/test_repo_map.py`, and commits each job as its own commit after its
review has no findings. Each builder writes
`pilot/handoffs/mac-check-fixes-job<N>.md` for the reviewer and the
orchestrator: what was built, what the tests said (output pasted), what is
left. That folder is never committed (SPEC-cleanup: a handoff note goes in
the pull request description); the orchestrator folds the two notes into
`pilot/HANDOFF.md` and the commit messages, and deletes them.

**Review** (opus, high effort, a session that did not build): numbered
findings against this SPEC's sections, each with the line it fails. A
finding that survives one rebuild is fixed by the reviewer's tier.
