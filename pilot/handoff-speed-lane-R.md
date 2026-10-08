# Handoff - the speed round, Lane R (the app)

Builder: Lane R of [`SPEC-speed-round.md`](SPEC-speed-round.md) (section 5.2),
in its own worktree from `51187f6` (the SPEC's commit on top of `8e18570`).
Built against the contracts of section 5.3 without the Python side, which
Lane P built in another worktree at the same time. Made-up data only.

Build order kept: P213, then P218's renderer half, P222, P221, P220.

## Commits

| Commit | Row |
|---|---|
| `ff90c2d` The reminder sheet never offers another return's letter | P213 |
| `8b8d53f` After a Sort one Overview is asked, not two (the renderer's half) | P218 |
| `8831ca5` A wait says what it shows (the renderer's half) | P222 |
| `91e5b17` The Overview is asked beside the list at launch | P221 |
| `7d958c6` A warm spare, still one command a process; the shell reads a reply once (the shell's half) | P220 |
| `2a9ae04` Outline bars and the count's bar are seen in a contrast theme | P222 (a fix found by looking) |
| `57d461d` Refresh the derived map | - |
| (this file, and the map's refresh for it) | - |

`shellLoadFirm` is one function that P218, P221 and P222 all change, so it was
rebuilt once, in the P218 commit, with the early-Overview adoption (P221) and
the count clock (P222) already in it; they are wired (called) in their own
commits.

## P213 - the reminder sheet never offers another return's letter

- `app/renderer/app.js`: `reminderCardFor` (the return the card was drawn
  for); `forgetReminderCard()` (no card, `#reminder-actions` hidden, `#sheet`
  `aria-busy="true"`, the outline in `#reminder-wait`); `reminderWaitOver()`,
  called by `drawReminder` and `drawReminderLine` (clears the outline and
  `aria-busy`); `drawReminder` sets `reminderCardFor = active` and shows
  `#reminder-actions` itself; `reminderCardReady()` guards `copyReminder` and
  `approveReminder` (a card, and on a reminder sheet: drawn for `sheetNow.ret`
  and `sheetNow.ready`).
- `app/renderer/sheet.js`: `sheetFrame` never shows `#reminder-actions` and
  clears `aria-busy` on `#sheet`; `openReminder` forgets the card before
  `showReturn` when the return is not on screen, and when it is, redraws the
  card held for it (or the on-screen state's card) so its buttons come back
  with it; `sheetNextDraft` sets `ready = false`, forgets, reads, then
  `ready = true`; `sheetShow` keeps `shellSkeleton(3)` beside the hidden word.
- `app/renderer/index.html`: `#reminder-wait` inside `#sheet-reminder`.
- `app/renderer/shell.css`: `#sheet-reminder.is-waiting` shows the outline
  alone.
- Tests (`tests/test_shell.py`):
  `test_the_reminder_sheet_offers_nothing_to_copy_until_its_own_return_is_read`,
  `test_next_draft_offers_nothing_to_copy_until_its_return_is_read`,
  `test_copy_refuses_a_card_drawn_for_another_return`,
  `test_a_check_sheet_waiting_on_its_return_is_an_outline` - node probes that
  lift the real functions (`lift()`, `SPEED_DOM`, `REMINDER_SHEET`).

## P218 - one Overview after a Sort (the renderer's half)

- `app/renderer/shell.js`: `shellClock`, `shellFirmSentAt`, `shellWroteAt`,
  `shellFirmHeld`; `shellWriteLanded()`; `shellFirmSent()` stamps each send;
  `shellStateArrived` remembers a differing state while a load sent after the
  last write runs (else asks as before); `shellCountsDiffer(state)`;
  `shellLoadFirm` compares what it remembered with the new counts when it
  lands and asks once more only if they still differ.
- `app/renderer/app.js`: `call()` says `shellWriteLanded()` for a reply to a
  command in `vocab.writing_commands`, before the state is drawn; `passEnded`
  says it first.
- Tests: `test_after_a_sort_one_overview_is_asked_not_two`,
  `test_a_write_that_lands_during_a_load_still_asks_again`. Three existing
  probes got the new fake (`shellWriteLanded`) or the new lifted function
  (`shellCountsDiffer`).

## P222 - a wait says what it shows (the renderer's half)

- W1, `shell.js`: `drawPage` marks a firm page drawn from held counts while
  they load (`aria-busy`, `is-updating`, a first `p.page-updating
  role=status` with `screenWords().updating`) through `shellMarkUpdating`;
  `shellUpdating()` marks the page on screen in place as a load starts
  (no redraw); `drawCounts` gives each `.side-count` `is-held` while counts
  are reloaded. All of it goes when the reply is drawn (or fails).
- W2, `shell.js`: `shellFirmSent` starts a 2,000 ms timer
  (`SHELL_FIRM_SLOW_MS`); `shellFirmProgress(said)` keeps `{done, total}`
  (integers, `0 <= done <= total`, `total >= 1`); `shellReading()`;
  `shellReadingNodes` / `shellSetReading` draw
  `fill(words.reading_households, {n: done, total})` and a determinate
  `role=progressbar` bar (`last-sort-bar` styling, `aria-labelledby` the
  words); `shellDrawReading` updates it in place, or draws the page once;
  `shellFirmDone` clears timer and count when the reply lands.
  `app.js`'s `onPassMessage` hands a message whose `args[0]` is `"firm"` to
  `shellFirmProgress` before its pass check.
- 3: `shellFollowsCounts()` - household and year pages are drawn again when
  the counts land; `pages.js` `pagesReturnSpecs` marks a row `waiting` while
  counts load with none held, and `pagesStatusCell` draws an `aria-hidden`
  outline bar for it.
- 4: `drawPage`'s busy path sets `page.dataset.list = pagesListOf(route)`;
  `shellLoading(title, level)` adds the Overview's three `.figure.is-outline`
  and a head line, a return page's caption line.
- 5: `shell.css` forced-colors block: outline bars and `.side-name:empty`
  outlines `GrayText` with `forced-color-adjust: none`; held figures,
  statuses and side counts `GrayText`.
- 6: `index.html` `#page` starts `aria-busy="true"` with six
  `.row-skeleton`; `shell.css` outlines `.side-name:empty`; the setup page's
  Start shows three outline rows (`.setup-wait`) and the page is busy while
  `set-root` runs.
- Tests: `test_a_firm_page_drawn_from_held_counts_while_they_are_asked_again_says_updating`,
  `test_updating_goes_when_the_new_counts_are_drawn`,
  `test_a_firm_wait_over_two_seconds_says_how_many_households_are_read`,
  `test_a_firm_wait_under_two_seconds_shows_only_the_outline`,
  `test_a_count_line_is_never_taken_for_the_passes`,
  `test_household_and_year_pages_follow_the_counts_when_they_arrive`,
  `test_a_return_row_waiting_for_its_counts_shows_an_outline_never_a_blank`,
  `test_a_skeleton_stands_in_the_grid_of_its_own_page`,
  `test_skeleton_bars_are_greytext_in_a_contrast_theme`,
  `test_the_first_paint_is_the_outline_not_a_blank_shell`. Vocabulary is the
  probes' own stub (`vocab.screen.updating`, `reading_households`), never
  read from `tracker.api`.
- Looked at in headless Chromium (the harness's stub, the two words injected,
  light, dark and forced colours): Updating, the count with its bar, the
  outline, the first paint. That found the contrast fix in `2a9ae04`.

## P221 - the Overview beside the list

- `app/main.js`: `EARLY_COMMANDS = new Set([BOOTSTRAP_COMMAND, "firm"])`;
  `commandProblem` allows exactly those before the allowlist.
- `app/renderer/shell.js`: `shellAskFirmEarly()` sends
  `window.tracker.call(["firm"])` itself and sets `loading`;
  `shellLoadFirm` adopts the pending reply (`shellAdoptEarly`: warnings as
  notices, an error thrown, so the Counts Not Available notice follows once
  the words are there); `shellAdopt` drops it for a `needs_root` list
  (`shellDropEarlyFirm`). A second ask while one is pending sends nothing.
- `app/renderer/app.js`: `bootstrap` calls `shellAskFirmEarly()` before it
  awaits the list. The first `call([...])` in `app.js` is still `list`.
- Tests: `tests/test_single_source.py`
  `test_the_shell_allows_the_read_only_overview_before_the_first_reply`, and
  `test_the_shell_runs_only_commands_the_api_has` extended (every early
  command in `api.HELD_READING_COMMANDS`, none in `api.WRITING_COMMANDS`);
  `tests/test_shell.py`
  `test_the_overview_is_asked_beside_the_list_and_drawn_once_the_words_arrive`,
  `test_an_early_overview_is_dropped_when_the_list_asks_for_a_folder`.

## P220 - the spare and the reader (the shell's half)

- `app/main.js`: `SPARE_FLAG = "--spare"`, `spare` (`{proc, stamp, stderr}`),
  `programStamp()` (packaged: the API's size and `mtimeMs`; source: the
  newest `mtimeMs` of `tracker/*.py`), `startSpare()`, `takeSpare()`,
  `startTracker(args)` (the one spawn every command and spare uses: same
  env, cwd, `windowsHide`). `learn()` starts the first spare the first time
  the allowlist is set. `spawnTracker` takes the spare for a command that is
  not a pass (a stale one is killed and the command spawns fresh), writes
  `JSON.stringify({argv: args}) + "\n"`, then the payload, then ends stdin;
  the kill timer is armed there, at the hand-over; then `startSpare()`.
  `will-quit` kills the spare. The stdout reader keeps the pieces of a line
  in an array, searches each new piece only, joins once per line;
  `take()`, progress lines and last-line-wins are unchanged.
- Tests (`tests/test_single_source.py`, a new harness `_SPAWN_HARNESS` that
  runs the real `main.js` against a recording `child_process`):
  `test_the_shell_hands_a_waiting_spare_the_next_command_and_starts_another`,
  `test_a_pass_is_never_handed_to_the_spare`,
  `test_a_spare_from_before_the_program_changed_is_not_used`,
  `test_quitting_kills_the_spare`, `test_no_spare_starts_before_the_first_list`,
  `test_a_reply_in_a_thousand_pieces_is_read_once_and_whole`.
  `test_the_shell_runs_only_commands_the_api_has` keeps its pins.
- The decision 193 real-process harness's fake tracker (`_FAKE_TRACKER`)
  was taught `--spare` (it reads its command line from stdin), because the
  shell now hands it commands; those tests now run partly through
  spares and pass unchanged.

## Departures, and why

1. **`--text-muted` does not exist** (P222.1). The shell's muted token is
   `--text-caption`; the held figures, statuses and side counts use it.
2. **Contrast selectors are as specific as the rules that draw the bars**
   (P222.5): `.row-skeleton > i:not(.hidden)`, `.outline-bar:not(.hidden)`,
   `.side-name:empty:not(.hidden)::before`. Written as the SPEC words them
   (`.row-skeleton > i`) they lose to the drawing rule and the bars stayed
   `--bg-hover` (seen in Chromium's forced-colours emulation). The same
   specificity bug hid the last-sort bar's fill in a contrast theme; its
   rule now matches the fill's and keeps `Highlight` (`forced-color-adjust:
   none`) - the firm count's bar is built on the same class.
3. **P213's "card body replaced by the outline"** is a new `#reminder-wait`
   shown alone while `#sheet-reminder.is-waiting`: replacing the reminder's
   own children would delete the ids `drawReminder` draws into.
   `forgetReminderCard` also drops `line-only` (which would hide the
   outline). Because the frame no longer shows the buttons, `openReminder`
   on the return on screen redraws its card (or its state's card) at once:
   otherwise Copy would never come back there.
4. **P218 orders sends and writes by a counter** (`shellClock`), not by
   time: two events in one millisecond would tie. A state remembered during
   a load is kept per return path, so two returns' states are both compared.
5. **P220: a spare is also started after any non-pass command when none is
   waiting**, not only right after one is handed - so a spare that died on
   its own (or one killed as stale) is replaced at the next command. A spare
   that cannot start is ignored (commands start their own).
6. **P222.3: "waiting" is `status === "loading"` with no counts held**;
   an idle status with none (no root yet) is not a wait.
7. **P222.1: "Updating" is also put on the page in place as a load starts**
   (`shellUpdating`), since a load starting did not redraw the page; every
   later draw keeps or drops it in `drawPage`. Side counts carry `is-held` on
   every page while counts are reloaded, not only on firm pages.
8. **P220's main.js tests use a new recording harness** in
   `test_single_source.py` rather than the stub at lines 246-320
   (`_ELECTRON_STUB`), whose `ipcMain` keeps no handler.
9. **The count line is routed by `args[0] === "firm"`**, and its fields are
   checked (`done`, `total` integers in range); its `event` name is not read
   by the renderer.
10. No `pilot/harness/interact.mjs` step was added (optional). `interact.mjs`
    reports five failures (search Enter, a row's step name, All vs Work
    Waiting, ruling 21 twice); the same five fail on `51187f6` unchanged, so
    none is this lane's.

## Gate (section 5.4, Lane R)

`ruff` on the changed Python files (`tests/test_shell.py`,
`tests/test_single_source.py`) and dead-code pass first: clean. Then each file
as its own process, two at a time:

| File | 3.11 (`venv311`) | 3.13 (`python3`) |
|---|---|---|
| `tests/test_shell.py` | 191 passed | 191 passed |
| `tests/test_single_source.py` | 186 passed | 186 passed |
| `tests/test_shell_menu.py` | 38 passed | 38 passed |
| `tests/test_api.py` | 447 passed | 447 passed |
| `tests/test_pilot.py` | 25 passed, 5 skipped | 25 passed, 5 skipped |
| `tests/test_pilot_ui.py` | 11 passed | 11 passed |
| `tests/test_pilot_installer.py` | 20 passed | 20 passed |
| `tests/test_layers.py` | 29 passed | 29 passed |
| `tests/test_repo_map.py` | 80 passed | 80 passed |
| `tests/test_tripwire.py` | 19 passed | 19 passed |

Then `python -m ruff check .` (all passed), `python tools/repo_map.py update`
and `python tools/repo_map.py check` (current), committed.

## Meaningful only after the merge

- **Do not ship this lane without Lane P.** Against today's `tracker.api`,
  `--spare` is an unknown command: the spare prints the usage envelope and
  exits at once, and a command handed to it in that moment would get the
  usage reply. With Lane P's `spare()` it waits for its line.
- The P220 tests drive `main.js` against a recording `child_process`; the
  first run against a real `python -m tracker.api --spare` is the merged
  tree's (Lane P's `test_a_spare_runs_the_one_command_it_is_handed_...`
  covers the Python side; the decision 193 real-process tests use a fake
  tracker that speaks the contract).
- The P222 tests use the probes' own words; "Updating" and "Reading {n} of
  {total} Households" reach the screen only once Lane P's `SCREEN` words
  are in. Before then the Updating marker is an empty status line, and no
  count line is ever printed, so the reading words are never drawn.
- `test_a_count_line_is_never_taken_for_the_passes` and the W2 tests feed
  count lines of the contract's shape; real ones come from Lane P's `firm`.
- **The merge adds** (section 5.5, 2) to `tests/test_single_source.py`:
  `test_the_shell_and_the_api_agree_on_the_spare_the_early_overview_and_the_count_line`
  - `main.js`'s `SPARE_FLAG` is `api.SPARE_FLAG`; every early command
  (`EARLY_COMMANDS`, which holds `BOOTSTRAP_COMMAND`) is in
  `api.HELD_READING_COMMANDS` and not in `api.WRITING_COMMANDS`; the
  renderer routes the count lines (`progress.COUNT_EVENT`) by the command
  name in `onPassMessage`'s `m.args[0] === "firm"`, which must equal
  `runner.FIRM_COMMAND`.
- `tests/test_shell.py::test_the_harness_stub_speaks_the_apis_vocabulary`
  is untouched: the stub reads neither new word.

## Doc changes for the orchestrator (section 5.5)

As the SPEC lists them for Lane R's rows, plus what this build found:

- `pilot/DECISIONS.md`: P213, P218 (with the renderer's half: one Overview
  after a Sort), P220, P221, P222 as worded in 5.5; P222 may add "the
  contrast theme's bars and the last-sort bar's fill" (departure 2).
- `pilot/SPEC-shell.md` 4.2, 6 (states) and the vocabulary table, as 5.5
  words them.
- `pilot/SPEC-firm-cache.md` lines 268-273 and 436-438, as 5.5 words them.
- `docs/repo-map.curated.json`, then `update`: `app/main.js` (the spare -
  `startSpare`/`takeSpare`/`programStamp`/`startTracker`, killed at
  `will-quit`; the reader that joins a line once; `EARLY_COMMANDS`);
  `app/renderer/app.js` (`forgetReminderCard`, `reminderCardReady`,
  `shellWriteLanded` in `call()` and `passEnded`, `shellAskFirmEarly` in
  `bootstrap`, count lines in `onPassMessage`); `app/renderer/shell.js`
  (the load's clock and held states, the early Overview, Updating, the
  count and its bar, the outline's shapes); `app/renderer/sheet.js` (P213);
  and, not in the SPEC's list, `app/renderer/pages.js` (a return row waiting
  for its counts) and `app/renderer/index.html` (the first paint, and
  `#reminder-wait`).
- `docs/runbook.md`, suggested: while the app is open one idle tracker
  process waits for the next click (P220) - normal in Task Manager, gone
  when the app quits - so a person checking for stray processes is not
  alarmed (the Windows check's "see no python/tracker process left" is
  after quitting). Worded as P155 asks of a person-facing document (the
  program is "the app"; `test_no_person_facing_document_calls_the_program_the_tracker`).
