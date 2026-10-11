# Pilot 0.3 - the menu's speed answers: the engine, the last-pass watch, paged firm lists, long lists - SPEC

Status: written 2026-10-11 from Jason's menu answers to SPEC-ui-polish
section 2, Q12-Q15, recorded as **P276-P279** (`pilot/DECISIONS.md`). It
designs on top of SPEC-ui-polish section 1 (P264) as built on
`claude/ui-polish` - N2's keyed lookups (`shellReturn`, `shellHousehold`,
`pagesFirmReturn`, `pagesHouseholdPath`, `pagesFormKey`), N3's one draw per
visit, N5's debounced search and fold cache, N6's timers that sleep while
the window is hidden - and on the two menu SPECs that land before it
(`pilot/HANDOFF.md`): `SPEC-ui-menu-small.md` (P268, the Tax Year column
only when more than one year is listed) and `SPEC-ui-menu-layout.md` (P271
Compact Rows - the tokens `--size-row` 40px and `--size-row-compact` 32px
under the root's `.rows-compact` class; P272 Needs Review as one flat list,
which that SPEC builds with one heading per **return** by default, its
question J1; P275 the household page's header card). Where an item here
touches one of those, it says so by number.

Source: Jason, 2026-10-11, menu answers Q12 b, Q13 b, Q14 b, Q15 c.

**What this changes, in plain words.** Four things that make the app feel
quicker, most of all on the office PC:

1. **The app stops asking "did a sort happen?" once a minute** (P277). The
   computer tells the app the moment the scheduled sort's note changes.
2. **Long lists on a return, a year, a household and in the request-list
   editor build only the rows you can see** (P279).
3. **The engine starts once, when the app opens, and answers every click**
   (P276), instead of starting from nothing for each click - which is most
   of a second on the office PC before any work is done. A Sort still runs
   in a process of its own, so Stop and its time limit work as they do now.
4. **The engine sorts and cuts the four firm lists into pages** (P278) and
   sends the window only the page it shows.

Nothing here changes a word a person reads, a column, a colour, a ruling
on what is filed, or the record. No new word enters the vocabulary except
two refusals a person should never meet: `OWN_PROCESS_ONLY` (3.3) and
`FIRM_PAGE_REFUSED` (4.4).

**Hard rules kept.** No generative AI reads a client document; nothing
here reads a document at all. Nothing is ever sent: no new network call,
no new module that could make one (`tests/test_layers.py`'s forbidden list
covers the two new modules). Client data never enters a repo, a test, a
commit or a log line: every new log line says a code, a class or a count,
never a name or a path; every test uses the suite's made-up firm or the
harness's made-up names. Originals are never altered: no item touches a
client folder.

**Build order** (section 7): P277, P279, P276, P278 - each its own sonnet
build and its own Opus review. Sections 1-4 below are in that order.

---

## 1. P277 - the app watches the last-pass file (effort S)

**Why, for a person.** While the app sits open it starts the engine once a
minute just to read one small note - the one the scheduled sort writes when
it starts and ends - so the side panel's "Sorted 6:00 AM" line can follow
it. After this change the computer itself tells the app the moment that
note changes: the line follows a sort at once, and nothing runs while
nothing happens.

**What the file holds** (`runner.write_last_pass`): `started`, `ended`,
`build` (the program's own path), `root` (the clients folder's path),
`result` and `reason_code`. No client's name and nothing from a document.
Even so: **the window never reads it, and neither does `main.js`.** `main.js`
learns only that the file's folder changed; the page then asks the engine's
`last-pass`, which is the one reader (`api._last_pass`) and says what the
line needs.

### 1.1 Python: `list` names the file (`tracker/api.py`)

- `_vocab()["shell"]` gains `"last_pass_file"`: `str(runner.last_pass_path())`,
  through a new `_last_pass_file() -> str | None` that answers `None` when
  the data home cannot be had (`SettingsError`, `OSError`) - that state is
  already said by `list`'s `machine_warnings` (decision 186), so nothing new
  is said here. The shell never builds this path itself (decision 186's
  rebase review, MF2: the error log's rule, `vocab.shell.error_log`, applies
  word for word).
- `LAST_PASS_WATCH_RUNNING_SECONDS`, `LAST_PASS_WATCH_IDLE_SECONDS` and
  `vocab["last_pass_watch"]` go (P256's two numbers; P259 Q1's 60 seconds is
  superseded by P277). `_cmd_last_pass`'s docstring says the shell asks it
  when the file changes and when the window is clicked into.

### 1.2 Electron: `main.js` watches the folder (`app/main.js`)

- `LAST_PASS_CHANNEL = "last-pass-changed"`: the fourth main-to-renderer
  channel (with `tracker-progress`, `MENU_CHANNEL`, `LAUNCH_DONE_CHANNEL`).
  It carries **nothing**: no path, no contents, no time.
- `learn(result)`: a string `vocab.shell.last_pass_file` calls
  `watchLastPass(file)`; the same file again changes nothing; another file
  replaces the watch; `null` or no key calls `unwatchLastPass()`.
- `watchLastPass(file)`: `fs.watch(path.dirname(file), { persistent: false },
  (event, name) => ...)`. An event whose `name` is given and is not
  `path.basename(file)` is ignored; one with the name, or with no name (Node
  does not promise one), calls `lastPassSoon()`.
  - **Why the folder and not the file.** `write_last_pass` replaces the file
    whole (`write_json_atomically`: a temporary file, then a rename), so the
    file is a new file after every write. A watch on the file itself is lost
    after the first replace on a Mac (kqueue) and on Linux (inotify); on
    Windows a file watch is a folder watch underneath anyway.
  - **Why `fs.watch` and where `fs.watchFile` is used.** The data home is on
    a fixed disk on Windows by rule (decision 186 refuses anything else) and
    in `~/Library/Application Support` on a Mac (SPEC-mac R1), where
    `fs.watch` is reliable (ReadDirectoryChangesW; FSEvents). Node documents
    `fs.watch` as unreliable on network and virtual file systems, which the
    data home never is. So `fs.watch` everywhere; `fs.watchFile(file,
    { interval: LAST_PASS_POLL_MS, persistent: false })` (5000 ms: a stat in
    `main.js`, never an engine process) only as the fallback when
    `fs.watch` throws at start (the folder is not there - in practice never
    after `list`, whose error log attaches by making the store's folder) or
    emits `error` later. The fallback calls `lastPassSoon()` when the stat's
    `mtimeMs` or `size` moved, and is said once in the error log
    (`keepInLog("shell's last-pass watch", <the error's code>)`): a code, no
    path.
- `lastPassSoon()`: one timer of `LAST_PASS_SETTLE_MS` (250 ms), restarted
  by each event, so the burst one atomic replace makes (create, write,
  rename) is one message; then `mainWindow.webContents.send(LAST_PASS_CHANNEL)`
  when the window exists and is not destroyed.
- `will-quit` closes the watch (`unwatchLastPass()`).
- The watch's handle on Windows shares delete, so the pass replaces the file
  exactly as before; nothing deletes the data home's folder.
- `app/preload.js`: `onLastPassChanged: (listener) =>
  ipcRenderer.on("last-pass-changed", () => listener())` - the listener is
  given nothing.

### 1.3 The page (`app/renderer/shell.js`)

- `shellArmLastPass` and `shellLastPassTimer` go. `shellWatchLastPass` is
  renamed `shellAskLastPass`: one ask, its body as now (the `scanning`,
  `document.hidden`, `shellLastPassAsking` and `shellLastPassStopped` guards,
  `lastPassStep`, the reread with P262's open-return rule), minus the re-arm.
- `shellLastPassChanged()` - registered through
  `window.tracker.onLastPassChanged` where `shellFocused` and `shellShown`
  are registered (`shell.js`, end of file): asks once. **While the window is
  hidden** it sets `shellLastPassOwed = true` and sends nothing; `shellShown`
  asks once when the window is visible again (as N6 does now). **While an ask
  is on its way** it sets `shellLastPassAgain = true`, and one more ask
  follows when that one lands - a change is never dropped, so a sort that
  starts and ends inside one ask is still seen.
- **The focus tick stays** (`shellFocused`, N6's 5 s quiet rule,
  `SHELL_FOCUS_QUIET_MS`): Node does not promise every folder event (a full
  Windows change buffer, a sync tool or virus scanner holding the file), a
  person expects clicking into the window to catch it up, and after P276 the
  ask costs a few milliseconds. It is the safety net, not a timer.
- `shellAdopt` no longer arms anything; it still clears
  `shellLastPassStopped`, so a list that lands starts listening again after
  a failed ask (said once by the one rule, decision 193).
- During the app's own Sort (`scanning`) a change asks nothing, as now: the
  Sort's end asks `list`.
- The lock watch (`watch` every `LOCK_WATCH_SECONDS` while a lock is shown,
  decision 193) is not part of this; it stays, and P276 makes each ask cheap.

### 1.4 Failure behaviour

A watch that cannot be set falls back to the stat watch and says so in the
error log; a `list` that names no file means no data home, which the page
already shows as a machine warning, and the focus tick still asks. An ask
that throws stops listening until the next `list` lands and is said once as
a notice, as today. The page never shows a stale "Sorting" for lack of a
message: the focus tick and the window's being shown each ask.

### 1.5 SPEC-shell and runbook sentences

- SPEC-shell **8.3**, after "When a scheduled pass ends, ...": add "The line
  follows the last-pass file without a timer (P277): `main.js` watches the
  file's folder and tells the page when the file changes; the page then asks
  `last-pass` once - a hidden window asks when it is shown - and clicking
  into the window asks once more unless it asked in the last 5 seconds."
- SPEC-shell **5.4**: the main-to-renderer channels are four; add
  `last-pass-changed`, which carries nothing.
- SPEC-shell **5.5**: add "The last-pass watch (P277): `fs.watch` on the
  folder of the file `list` names as `vocab.shell.last_pass_file`, a stat
  watch only where that cannot be set; the file is never read here."
- `docs/runbook.md`, "The last-pass line": "the app looks again every few
  seconds while a pass runs and about once a minute otherwise, and at once
  when the window is clicked into" becomes "the computer tells the app the
  moment the file changes, and the app looks again when the window is
  clicked into".

### 1.6 Tests

New, as named claims:

- `tests/test_api.py`: `test_the_list_names_the_last_pass_file_the_runner_writes`
  (equal to `runner.last_pass_path()` under a `TRACKER_DATA_HOME` in
  `tmp_path`); `test_the_list_names_no_last_pass_file_when_the_data_home_cannot_be_had`.
- `tests/test_single_source.py` (main.js through `_run_spawns`, whose
  harness gains a fake `fs.watch` / `fs.watchFile` that records the folder
  and can fire events):
  `test_the_shell_watches_the_folder_of_the_last_pass_file_the_list_names`,
  `test_a_burst_of_changes_is_one_message_and_other_files_are_ignored`,
  `test_the_shell_never_reads_the_last_pass_file_and_sends_the_page_nothing_of_it`
  (no `readFile`/`readFileSync` of it; the message has no argument),
  `test_a_watch_that_fails_falls_back_to_a_stat_watch_and_says_its_code_in_the_error_log`,
  `test_a_list_that_names_another_file_moves_the_watch_and_one_that_names_none_ends_it`,
  `test_quitting_closes_the_last_pass_watch`.
- `tests/test_shell.py`:
  `test_a_change_of_the_last_pass_file_asks_last_pass_once`,
  `test_a_change_while_hidden_is_asked_when_the_window_is_shown`,
  `test_a_change_during_an_ask_asks_once_more_when_it_lands`,
  `test_no_timer_asks_last_pass` (text pin: no `setTimeout` reaches
  `shellAskLastPass`; no `last_pass_watch` in the renderer).

Pins that change: `tests/test_api.py::test_last_pass_is_answered_without_a_root_or_a_store`
(its `last_pass_watch` lines become "the key and both constants are gone");
`tests/test_shell.py`'s `LAST_PASS_WATCH_FAKES` (no `last_pass_watch`) and the
tests that lift `shellArmLastPass`/`shellWatchLastPass` (around lines
5727-5877: renamed to the change and the focus starting an ask;
`test_a_throwing_reread_is_said_once_and_stops_the_watch` keeps its claim);
`test_the_last_pass_watch_and_the_lock_watch_send_nothing_while_the_window_is_hidden`
(its last-pass half becomes "a change while hidden is owed, then asked once
when shown"); the IPC channel pins
`test_the_shell_and_the_preload_agree_on_every_ipc_channel` and
`test_the_shell_sends_on_only_the_channels_the_preload_listens_to`
(`tests/test_single_source.py`). The harness stub (`pilot/harness/stub.js`,
`app-stub.js`) gains a no-op `onLastPassChanged`.

### 1.7 Measurement (in the handoff)

On this Mac, with `TRACKER_SETTINGS_DIR` and `TRACKER_DATA_HOME` pointed at
folders in the builder's scratchpad (never the real data home) and the
harness's made-up root: (a) engine processes started by the last-pass watch
in 10 minutes with the window open and idle - before 10 (one a minute),
after 0; (b) the time from a stand-in write of the file
(`runner.write_last_pass` called from a one-line Python command) to the
side panel's line changing - before up to 60 s, after under 1 s. Five
writes, the median.

---

## 2. P279 - long lists draw only the rows in view (effort M)

**Why, for a person.** A return with hundreds of requests and documents, or
its request-list editor, today puts every row on the page at once, and the
page waits while it builds them. After this change only the rows you can
see, and a screen's worth either side, are built; the rest are built as you
scroll. Lists of an ordinary size are drawn exactly as today.

### 2.1 Which lists, and the threshold

- The household page's returns list (after P275, the list beside the header
  card), the year page's list, each group of the return page (Needs You,
  Waiting, Received, Set Aside inside its fold), and the editor's tables (the
  active rows and each set-aside group's rows: `renderEditorRows`).
- **A list is virtual only when it holds more than `PAGES_VIRTUAL_FROM` = 100
  rows** (a constant in `pages.js`, read by `app.js` for the editor). Below
  that every row is drawn as today - rows wrap (rulings 21, 27), the whole
  list is in the document. A household has a handful of returns and a year
  page fewer, so in practice only a large return and its editor change.
  (Jason's question A, section 8: the default is this threshold.)

### 2.2 How a virtual list draws (`app/renderer/pages.js`)

- **Every row's spec is still built at draw time** (`pagesEach`, `pagesSafe`
  as now) and registered in `pagesTokens` under an id assigned then
  (`row-N`), so the right-click menus (`pagesRowFor`), the sheet's next
  arrow (`pagesSteps`, `pagesFiles`, `pagesDrafts`) and Shift+F10 see every
  row, drawn or not. Only the nodes are made on demand.
- `pagesVirtual(list, items)`: the listbox gets class `is-virtual`,
  `position: relative` and a height of `n × H`; each drawn row is placed
  at `top: i × H` (`shell.css`, `.rows.is-virtual > .row`, below). Columns
  are the rows' own grid, so P139's widths (`pagesApplyWidths`) apply
  unchanged.
- **H is one drawn row's own height**, measured once per draw: the first
  row of the window is made, `H = row.offsetHeight`, then the rest are
  placed. The density decides it, never the virtualizer: `--size-row` 40px,
  or `--size-row-compact` 32px under View > Compact Rows (P271's
  `.rows-compact` on the root, SPEC-ui-menu-layout L1), with the row's
  hairline as the stylesheet draws it. No 40 or 32 is typed in `pages.js`.
  An H that is not a positive number (a list not laid out) throws
  `Error("row height")`, which the page's draw says as its failure notice
  (decision 193) - never a guessed height. Switching the density measures
every long list again from `shellToggleCompact` (P271 only toggles the
class; it does not redraw the page, as this SPEC first assumed: build
deviation 1), through the said form that routes a throw to the failure
notice. The rows' own CSS is P271's
  (`min-height` only, as its test holds); a virtual list adds one rule of its
  own, `.rows.is-virtual > .row` (`position: absolute`, `left: 0`, `right: 0`,
  `white-space: nowrap`, the name and status cells' ellipsis), which names no
  `.rows-compact` and sets no height, so every row of a virtual list is
  exactly one line at its density's least height.
- `pagesWindow(count, H, listTop, viewTop, viewHeight, over)` - pure, lifted
  by the tests - answers `{first, last}`: the rows that meet the view plus
  `over` rows either side, `over` = `PAGES_VIRTUAL_OVER` = one viewport's
  rows (`ceil(viewHeight / H)`, at least 15). The drawn set is that window
  **and the active row** (pinned, so `aria-activedescendant` always names a
  node in the document).
- One passive `scroll` listener on `#page` (the page's scroller) and one
  `ResizeObserver` on it, each coalesced to one `requestAnimationFrame`,
  recompute every virtual list on the page; only rows entering the window
  are made and only rows leaving it are removed - a kept row is never
  rebuilt. A closed fold (Set Aside) draws nothing until its `toggle`.
- **Sub-headings** inside a return-page group (`block.sub`) are items of the
  same height H in the flat sequence, drawn as `div.group-sub` with
  `role="presentation"` in a slot of that height (absolute, its `top` and
  `height` set inline from H, as a row's `top` is); each row under one carries the sub-heading's words
  at the front of its `aria-description` (a string, so it holds when the
  sub-heading is not drawn). Child rows (`row-child`, a file under its
  request, ruling 17) are items of height H like any row.
- **One line per row.** In a virtual list `row-wrap` is not applied: a long
  name ends in "…", cut or not, and keeps its tooltip - the link's "Navigate
  to Return" or "Navigate to Client" (P117's ruling O2 and SPEC-shell 3.6
  stand), as a file name keeps its own (Jason's question B, section 8). Every drawn row carries
  `aria-posinset` (its place, from 1) and `aria-setsize` (the list's rows).
- **A row that cannot be made** when it scrolls in, or when a key or a
  restore reaches it (its spec built, its node not), draws an empty row of
  height H in its place and goes through `pagesReportBroken`'s notice once,
  naming the row as every page does - never a silent gap.
- A redraw of the same route keeps `#page`'s scroll position: the sizer's
  height is set before rows are drawn, and the window is computed after the
  new list is in the document.

### 2.3 Keyboard and focus

- Focus rests on the listbox, which a scroll never removes, so focus is kept
  across any scroll by construction.
- `pagesKey(e)` reads the list's model (`list.pagesModel = {ids, specs, H,
  active}`) instead of `querySelectorAll('[role="option"]')`: Up, Down, Home,
  End, PageUp and PageDown move the active **index** over every row, drawn or
  not (PageDown's step is `floor(viewport / H) - 1`, as today's); the row is
  made if it is not drawn, made active (`pagesActivate`), and scrolled into
  view by setting `#page.scrollTop` so its top or bottom is just inside the
  view (`block: "nearest"`'s rule). Enter, Space (the Linked Households
  panel) and Shift+F10 act on the active index.
- `pagesWhere` / `pagesRestore` record and restore the active row by its
  index in the model, not its place among drawn nodes; the restored row is
  drawn and brought into view.
- A list drawn whole keeps today's DOM path; the model path is used only by
  `is-virtual` lists, so nothing changes for short lists.

### 2.4 The editor (`app/renderer/app.js`)

The editor's rows are not one height - an open routing fold, a custom row's
fields, the Advanced switch - and they hold inputs, so its window is drawn
with spacer rows rather than absolute rows, and with the rule that **the row
holding focus is never taken out of the document**:

- Over the threshold, `requestRows` draws a `tr.ed-spacer` above and below
  the window with their heights set. Each row's height is measured when it
  is drawn and kept (a `WeakMap` keyed by the row object); a row not yet
  drawn counts as the plain row's measured height, or that plus the median of
  measured open folds when its fold is open (`fold.isOpen(row)`). The window
  is the rows meeting the view plus one viewport either side, by the running
  sum of those heights. Switching the density (Compact Rows) drops what was
  measured - the medians included - so a row never drawn counts as the new
  density's own height, and the drawn rows are measured again.
- **Focus decides the window's edges.** The window is always widened to
  contain the row holding `document.activeElement`, so a mouse scroll never
  removes an input being typed in, and an input method's composition is
  never interrupted. A `focusin` in the first or last drawn row widens the
  window by `over` rows in that direction before Tab moves on, so Tab and
  Shift+Tab walk every row's inputs in order. A pin is kept only for the edge
  just widened and only near the focused row: a `focusin` drops any pin more
  than `over` rows from the focused row (`reveal`'s pins likewise do not
  outlive focus moving that far), so a Tab walk never ends with the whole
  table drawn.
- **Nothing lives only in a node.** Every input writes to its row object as
  it is typed (`cellInput`'s handler on `input`; if any field writes on
  `change` only, the builder adds `input`), so a row taken out of the
  document holds nothing that is not in `editorRows`. The save reads
  `editorRows`, as now.
- `focusEditorRow(identifier)` finds the row in `editorRows`, scrolls the
  window to it, draws it and focuses it. Enter on the last row adds a row
  (`addrow`) as now: the last row is drawn because it holds focus.

### 2.5 What virtual lists change that a person could notice (said honestly)

- **There is no find-in-page in this app**: Ctrl+F focuses Search (SPEC-shell
  4.3), which searches the list's households and returns (and Needs Review's
  files) from data, never the page - unaffected.
- A screen reader's own find and its list of links in browse mode see only
  the drawn rows of a virtual list; the arrow keys reach every row, and
  every row says its place and the list's size.
- Select-all and copy on such a page copy only the drawn rows.
- The editor's spelling underline appears only on drawn inputs.
- Any test or harness check that reads the page's text sees only drawn rows.

None of these touches a record or a client document.

### 2.6 SPEC-shell sentences

- **3.6**, after "A row may wrap (rulings 21, 27)...": add "**A long list
  draws only what is in view (P279).** A list on a household, year or return
  page of more than 100 rows, and an editor table of more than 100 requests,
  keeps every row's place but puts in the document only the rows in view,
  one screen either side and the active row. Each such row is one line at
  its density's least height (`--size-row` 40px; `--size-row-compact` 32px
  under Compact Rows, P271), so in these lists a long
  name ends in "…" with its tooltip instead of wrapping; rulings 21 and 27
  hold in every list drawn whole. Every drawn row says its place
  (`aria-posinset`, `aria-setsize`)."
- **3.6**, Keyboard paragraph: "Up/Down, Home/End, PageUp/PageDown move"
  becomes "Up/Down, Home/End, PageUp/PageDown move through every row of the
  list, drawn or not; the row moved to is drawn and brought into view".
- **6.5-6.7**: one sentence each pointing at 3.6's long-list rule.

### 2.7 Tests

`tests/test_shell.py` lifts JS through `run_shell` / `run_pages` (node, a
fake `document`); what it can hold is the arithmetic, the model and the
registrations. New:

- `test_the_window_holds_the_rows_in_view_and_one_screen_either_side`
  (`pagesWindow`: top, middle, end, an empty list, a list half above the
  view, a list below it).
- `test_a_list_of_one_hundred_rows_is_drawn_whole_and_may_wrap`.
- `test_a_long_list_draws_only_its_window_and_registers_every_row`
  (`pagesTokens` holds all 1,000; drawn nodes are at most window + 1;
  `pagesFiles()` answers every Check step in order).
- `test_the_active_row_stays_in_the_document_when_scrolled_out_of_the_window`.
- `test_every_drawn_row_says_its_place_and_the_lists_size`.
- `test_the_keys_move_through_rows_not_yet_drawn_and_draw_them` (End on
  1,000 rows: index 999 active and drawn; PageDown's step from H).
- `test_the_row_height_is_a_drawn_rows_own_and_a_list_not_laid_out_is_loud`
  (a fake `offsetHeight` of 40, then 32; 0 throws).
- `test_a_redraw_restores_the_active_row_by_its_place_in_the_list`.
- `test_a_row_that_cannot_be_made_on_scroll_is_said_not_skipped`.
- `test_the_editor_keeps_the_focused_row_and_widens_its_window_at_either_edge`.
- `test_a_value_typed_in_a_row_scrolled_out_of_the_editor_is_in_the_saved_list`.
- `test_focus_editor_row_reaches_a_row_not_drawn`.
- `tests/test_pilot_ui.py`: a text pin on `.rows.is-virtual > .row`
  (absolute, `nowrap`, no height, no `.rows-compact` in its selector, so
  P271's rule that a `.rows-compact` rule sets only `min-height`, `font-size`
  and `line-height` still holds) in the file's shape.

Pins that change: the tests that drive `pagesKey`, `pagesWhere`,
`pagesRestore` and `pagesActivate` over DOM rows keep their claims for
short lists and gain the model path; `test_the_set_aside_fold_is_shut_each_time_the_page_opens`
is unchanged.

**What only the harness shows** (`pilot/harness`, made-up names): that the
absolute rows line up under the column headers at every width, that a fast
scroll shows no blank band, the focus ring on the active row after a long
scroll, and Compact Rows in a virtual list. The stub gains two scenarios,
`long-return` (a return with 500 requests and 500 files) and `long-editor`
(300 rows), shot at the top, the middle and the end, both themes, both
densities; `interact.mjs` presses End, PageUp three times, clicks a row,
tabs through three editor rows, and asserts after each that the document
holds at most window + over + 1 rows and that the active row is drawn. The
shots and the script's output go with the pull request.

### 2.8 Measurement (in the handoff)

In the harness in Electron (1400 × 900), median of five: the return page's
draw at 100, 1,000 and 3,000 rows; the editor's open at 300 rows; the
document's node count after each; the longest frame while scrolling the
1,000-row page end to end (`performance.now` around each animation frame).
Before and after.

---

## 3. P276 - one engine for the session (effort L)

**Why, for a person.** Today every click starts the engine from nothing:
Python starts and loads the program before it does any work - about 0.2 s
on this Mac (`import tracker.api` measured 0.21 s, median of five, while
writing this SPEC) and about 0.85 s on the office PC. The waiting spare
(P220) hides that for one click at a time. After this change the engine
starts once when the app opens and then waits; each click costs only its
own work. A Sort still runs in a process of its own, exactly as now, so
Stop, the time limit and quitting during a Sort are unchanged. The engine
starts afresh by itself whenever anything about it is in doubt.

### 3.1 Decision 193 re-read, and the speed round's five objections answered

SPEC-speed-round section 4 refused "a long-lived worker serving every
command" for five reasons; P276 supersedes that row, and each reason is
answered here, not waived:

| The objection | How it holds with the engine |
|---|---|
| **Decision 171's lock rule**: a live worker's lock refuses clicks for 2 h 05 min | Every lock is taken and let go inside one command, as now. The one way a lock outlives its command - a release that could neither delete nor mark the file (171's F1 case) - leaves a file naming the engine, which is alive, so every other process (the scheduled pass, a Sort, a click run in its own process) would read it as held. **So after any command that left a lock unreleased, or still holds one, the engine retires** (3.3): its process ends, and the dead-owner rule clears the lock at the next take, exactly as a one-command process's leftover is cleared today. |
| **One store per process** | One store per command: `api.main`'s `finally` closes it after every command (unchanged), and a test holds that it is closed between commands. |
| **P118's holds per reply** | `api.main` enters `settings.one_reading()` per command and leaves it at the command's end (unchanged); a test holds that nothing is held between commands. |
| **The kill per command** | Every command handed to the engine has the same kill timer (`TRACKER_TIMEOUT_MS`); at it the shell kills the engine - the only way to stop a stuck command - says the same sentence as now (`killed_read`, or `killed_write` with "It May Be Partly Done."), and starts a new engine. |
| **Crash isolation** | A command that crashes the engine is answered by the shell (a read asked once more in a process of its own; a write never run twice, said as no reply - P220's rule), and a new engine starts. A Sort never shares the engine. |

Decision 193's own safety case - **replies never go quiet, and a pass can
be watched and stopped** - is kept by keeping passes out of the engine
(3.2), and by every engine command ending in either its reply or the
shell's own failure envelope (3.4).

### 3.2 What runs in the engine, and what never does

**Recommendation: passes stay separate spawns.** A pass (`run-now`, decision
203) runs for up to `locking.RUN_TIME_LIMIT_SECONDS` (two hours), holds
household locks for that long, is killed only at the limit its own first
line states, and is stopped at quit by the shell destroying its stdout
(`runner.PASS_APP_CLOSED`) - none of which can be done to one command inside
a shared process without stopping every other click with it. One process
runs one command at a time, so a pass inside it would also hold every click
for its whole length. So the four commands that run a pass or the
after-install step - which can take minutes on a streamed Drive folder -
keep a process of their own:

- `api.OWN_PROCESS_COMMANDS = frozenset({PASS_COMMAND, "after-install",
  "install-schedule", "move-schedule-here"})`, shipped as
  `vocab.own_process_commands`. `main.js` learns it as it learns
  `pass_command`; before the vocabulary arrives only `EARLY_COMMANDS` may
  run, none of them in it, and `LAUNCH_COMMAND` (the shell's own
  after-install, decision 209) always has its own process.
- The engine refuses any of them itself (3.3), so a shell mistake is loud,
  never a pass run in the engine.
- Every other command - `list`, `firm`, `firm-last`, `state`, the writes,
  `watch`, `last-pass`, `cancel-pass` - runs in the engine **when the engine
  is free**. A command that comes while it is busy starts a process of its
  own, as every command did before the spare (no queue, so a slow `firm`
  never holds a `state` behind it - the launch's `list`, `firm` and
  `firm-last` still run side by side, P221 and P229).

### 3.3 Python: `tracker/resident.py` (new module, its own `tests/test_resident.py`)

**Layer 5**, beside `api` (`tests/test_layers.py`'s table, with a comment:
"`resident` joins L5 with P276: the engine's loop over `api.main`; it imports
`api`, `locking`, `settings` and the standard library; nothing imports it
but `api_entry.py`, at call time"). `api` never imports it. Its CLI is
`python -m tracker.resident --resident` (from source; `main.js` starts it so)
and `api_entry.py` dispatches `[RESIDENT_FLAG]` to `resident.serve()` in the
frozen build.

Constants: `RESIDENT_FLAG = "--resident"`, `LINE_MAX = 64 * 1024` (the
spare's `SPARE_LINE_MAX`), `PAYLOAD_MAX = 32 * 1024 * 1024`,
`END_KEY = "engine_end"`, `COMMANDS_MAX = 500`,
`OWN_PROCESS_ONLY` (the refusal, 3.2: "This runs in a process of its own;
nothing was started.").

**The framing - the smallest change from the spare's.** The spare read one
line `{"argv": [...]}`, then the payload to the end of input. The engine
cannot use the end of input, so the line says the payload's length:

- **Request:** one line of UTF-8 JSON `{"id": n, "argv": [str, ...],
  "bytes": k}` (`n` a positive integer, at least one string in `argv`,
  `0 <= k <= PAYLOAD_MAX`, the line at most `LINE_MAX` bytes), then exactly
  `k` bytes: the payload as `main.js` writes it today (`JSON.stringify`, UTF-8;
  `k = 0` is no payload). The payload's bytes are exactly what
  `api._read_spec` decodes now (decision 176), never re-encoded inside the
  line.
- **Reply:** whatever `api.main` prints today, unchanged - progress lines
  (the firm's count lines, P222) and the reply line - then a newline and one
  line `{"engine_end": n, "code": <exit code>, "retiring": <bool>}`. The
  leading newline means output a command left without one can never hide the
  end line.

`serve(stream=None) -> int`:

1. **The real input is the engine's alone.** It duplicates file descriptor 0
   for itself and points 0 at the null device, so nothing a command starts
   (a scheduler tool, a reading child) can read a frame.
2. Reads a line. The end of input before a newline - the app has closed -
   returns 0, printing nothing. A line that is not the shape above, or too
   long, or names too many bytes: the usage envelope (`api.main([])`, no
   words of its own, as the spare did) and an end line with `id` 0 and
   `retiring: true`, then return 2 - the stream can no longer be trusted.
3. Reads exactly `k` bytes; the end of input first returns 0.
4. Refuses `argv[0]` in `api.OWN_PROCESS_COMMANDS` with `OWN_PROCESS_ONLY`
   (the failure envelope, kind `refused`), runs nothing, and retires.
5. Notes how the process stands: `locking.held_now()`, the environment
   (a copy), `tempfile.tempdir`, `os.getcwd()`, `threading.active_count()`.
6. Sets `sys.stdin` to a text stream over the payload's bytes (so
   `_read_spec` reads them as it reads a pipe), runs `code = api.main(argv)`,
   and restores `sys.stdin`. `api.main` already answers every `Exception` as
   the envelope. Anything else that escapes it (`SystemExit`, `MemoryError`,
   `RecursionError`) is said through `api.say_failure(command, exc)` - today's
   `_say_failure`, made public by its rename; its three callers change with
   it - with exit code 1, and the engine retires. `KeyboardInterrupt` ends
   the engine.
7. Flushes stdout and stderr, then decides whether to retire. **It retires
   after any command that left the process unlike it found it**: a lock
   still held (`locking.held_now()` above the note), a lock it could not let
   go (`locking.left_unreleased()` not empty), a changed environment, temp
   folder or working folder, a thread still running, an escaped error, a
   refused own-process command - and after `COMMANDS_MAX` commands (memory a
   long session's large replies leave behind). The reason goes to the error
   log as one line at WARNING, by name only (`"engine retired: lock-left"`,
   `"environment-changed"`, ...: a code, never a value or a path), inside
   `settings.error_log()` as every command's lines are.
8. Writes the end line, flushes, and returns 0 when retiring; otherwise
   reads the next frame.

The engine reads documents only in a reading child, as every app command
does (`content_check.READ_IN_A_CHILD`, decision 169): the reader's
process-wide switches (`ocr.processor_only`, the engine it builds) change
only in that child and end with it.

**`tracker/locking.py`** gains two read-only answers, and nothing else
changes in it: `held_now() -> int` (how many locks this process holds now,
under `_held_guard`) and `left_unreleased() -> tuple[Path, ...]` (the lock
files a release in this process could neither delete nor mark: appended in
`_delete_own`'s last `except OSError` branch, beside today's
`errors.keep`). Its docstring's paragraph "Each app command is its own short
process ..." gains: "The app's engine (P276) runs many commands in one
process; it ends itself after any command that left a lock unreleased or
held (`tracker.resident`), so the dead-owner rule still clears what it
left."

**The run log's lock and the error log.** The run log (`logs/runs.log`) and
its rotation lock (`fsio.ROTATION_LOCK_SUFFIX`) are written only by a pass
(`runner`), which never runs in the engine, so the engine never takes that
lock. The error log is attached per command (`settings.error_log`) and each
line is opened, appended and closed (`settings._ErrorLog.emit`), so the
engine holds no log file open between commands and another process can
rotate it on Windows as now. The firm cache, the view file of P278 and the
store are opened and closed inside each command.

**`tracker/api.py`**: `SPARE_FLAG`, `SPARE_LINE_MAX` and `spare()` go (the
`--spare` is retired); `OWN_PROCESS_COMMANDS` and `vocab.own_process_commands`
come; `_say_failure` is renamed `say_failure`. The module docstring's
command list is unchanged (no command is added). P220's pin that importing
the API opens no file but the program's own, and fixes four names at import
from the environment, stays: the engine is started with the environment a
fresh command gets, and is replaced when the program changes.

**`api_entry.py`**: in its main block, after `freeze_support`, the Mac
floor and the runner and setup modes, the spare's import becomes
`from tracker.resident import RESIDENT_FLAG, serve` beside `tracker.api`'s
`main` (both imported there, at call time, as the API is today), and
`raise SystemExit(serve() if argv == [RESIDENT_FLAG] else main(argv))`; its
docstring's "And a warm spare" paragraph becomes "And the engine".

### 3.4 Electron: `app/main.js`

- **Retired**: `SPARE_FLAG`, `spare`, `startSpare`, `takeSpare` and their
  comments. `programStamp()` stays (the engine's stamp). `HELD_READING_COMMANDS`
  stays (the re-run rule).
- `RESIDENT_FLAG = "--resident"` and `ENGINE_END_KEY = "engine_end"`, each
  pinned to `tracker.resident` by `tests/test_single_source.py`.
- `let engine = null` holds `{proc, stamp, current, nextId, stderr, retiring}`.
  `startEngine()` runs `startTracker([RESIDENT_FLAG])` - the same
  environment, working folder and hidden window as every command (from
  source `python -m tracker.resident --resident`; frozen, `FROZEN_API
  --resident`). It is called **at `app.whenReady()`, after the floor check
  and the one-instance lock, before the window is made**, so its start
  overlaps the window's load; and again after the engine ends (below).
- **Routing, in `spawnTracker`**: a pass, a command in the learned
  `own_process_commands`, `LAUNCH_COMMAND`, a `fresh` re-run, or a command
  while there is no engine, the engine is busy (`engine.current`), retiring,
  or its stamp is not `programStamp()` - **a process of its own**, exactly as
  today. Otherwise the command is **handed to the engine**: the request line
  (with `bytes` = `Buffer.byteLength(body, "utf8")`) and the payload, with no
  end of input. An engine still starting counts as free: its frame waits in
  the pipe, which costs that click no more than a fresh process would.
- **Reading the engine's output**: the one line reader (P220's, which joins
  a line's pieces once) is shared by both paths; for the engine, progress
  lines go to that command's `onProgress` (so `firm`'s count lines still reach
  the page, P222), any other line is the reply candidate, and the end line
  whose `engine_end` is the current id settles the command with the last
  candidate - or the shell's `no_reply` failure if there was none - and its
  code; `learn()` runs on a reply as now. An end line with another id is a
  broken stream: the engine is killed and the command answered as if it had
  died (below).
- **The kill timer**: `TRACKER_TIMEOUT_MS` per handed command, as now. At it,
  the shell kills the engine (`proc.kill()`), answers the command with today's
  killed sentence, and starts a new engine.
- **An engine that ends while it holds a command** without its end line: a
  command in `HELD_READING_COMMANDS` and not in `writingCommands` is asked
  once more in a process of its own; any other is answered with `no_reply`
  (a write is never run twice - P220's rule word for word). Its stderr since
  the hand-over goes to the error log under "shell stderr of an engine that
  closed without a reply".
- **stderr**: the engine's stderr is kept from each hand-over (capped at
  `STDERR_CAP`); a command that fails keeps it in the error log as now
  ("shell stderr of a failed command"). stderr and stdout are two pipes, so a
  line written at a command's very end may land under the next command's
  heading; it stays in the error log either way and is never on screen.
- **A new engine**: when the engine ends - retiring (its end line said so),
  killed, or ended on its own - `startEngine()` runs at once. A retirement
  costs nothing against the budget; an unplanned end counts, and **a third
  unplanned end within five minutes (`ENGINE_RESTARTS = 3`,
  `ENGINE_RESTART_WINDOW_MS = 300000`) leaves the engine off for the rest of
  the session**: every command then runs in a process of its own, and the
  error log says once "engine stopped 3 times in 5 minutes; every command now
  starts its own process", with the exit codes. Nothing is skipped - every
  click is still answered, at today's pre-spare speed - so this is said in
  the log, not as a notice (Jason's question D, section 8).
- **A program that changed under a running app**: before each hand-over the
  stamp is compared, as the spare's was. An engine from an older program has
  its input ended (`proc.stdin.end()`: it finishes nothing, it is idle, and
  exits at the end of input), a new engine starts, and this one command runs
  in a process of its own. **On the office PC** the installer replaces the
  program folder; Windows will not replace a running `tracker-api.exe`, and
  Inno Setup's Restart Manager (`CloseApplications`, left at its default by
  `pilot/installer/setup.iss`) offers to close the app - the engine, and a
  running Sort, included - exactly as it closes the spare today. The stamp
  covers what the installer does not: a source checkout pulled under a
  running app, or a Mac's app dragged over the running one, where the old
  engine keeps running its old files. In every case the shell that keeps
  running talks to a new engine, as a fresh process after an upgrade does
  today, and decision 209's step runs at the next launch.
- **`will-quit`**: passes' stdout destroyed as now (decision 203); the
  engine's input is ended (`proc.stdin.end()`), never killed: one holding a
  write finishes it and exits at the end of input, as a fresh write process
  finishes after the app has gone today. If the shell itself dies, the pipe
  closes and the engine exits at the end of input the same way.
- An engine that cannot start (`spawn` error) is no engine: commands start
  their own processes, and the error log says the error's code once.
- The renderer and `preload.js` change nothing: `window.tracker.call` is the
  same, and where a command ran is invisible to the page.

### 3.5 Failure behaviour, in one place

Every handed command ends in its reply or one of the shell's own sentences
(`no_reply`, the killed sentences, `could_not_start`); nothing is retried
that could write twice; every engine end, retirement and fallback is one
line in the error log, by code; the page's notices and Retry are decision
193's, unchanged.

### 3.6 SPEC-shell, runbook and map sentences

- SPEC-shell **5.5** (handled in `main.js` alone): add "The engine (P276):
  one process per session, started before the window, answering each
  command handed to it while it is free over its standard input (a line and
  the payload's bytes; its reply, then an end line); a Sort and the
  after-install step always have a process of their own; a busy engine's
  command starts its own process; a stuck command is killed with the engine,
  and a new engine starts."
- `docs/runbook.md`, "**One waiting helper in Task Manager is normal**
  (pilot P220)" becomes: "**One engine in Task Manager is normal** (pilot
  P276). While the app is running it keeps one engine process of its own -
  `tracker-api.exe` in the installed app, a `python` process when it runs
  from source - which answers the app's clicks one at a time, so a click does
  not wait for a program to start. It uses no processor while it waits, and
  holds no client file and no lock between clicks. A click that comes while
  it is busy, and every Sort, starts a process of its own. It starts afresh
  by itself now and then: after a few hundred clicks, after a click that left
  anything behind, and when the program has been updated. When the app quits
  it finishes what it is doing and ends; one still there a minute after the
  app has closed (other than a scheduled pass that is running) is worth a
  look."
- `pilot/SPEC-speed-round.md` stays as written (history); P276's row is the
  record that its "long-lived worker" refusal is superseded, and this
  section 3.1 answers each reason.

### 3.7 Tests

**`tests/test_resident.py`** (new; the demo root and `capsys`/a byte stream,
as `tests/test_api.py` does):

- `test_the_engine_answers_each_command_as_a_fresh_process_would_byte_for_byte`
  (`list`, `state`, `firm`, `templates`, `last-pass` through `serve` and
  through `api.main`: the same lines and codes).
- `test_one_command_that_fails_is_answered_and_the_next_is_served`.
- `test_an_error_that_escapes_main_is_said_as_the_envelope_and_the_engine_retires`
  (`SystemExit`, `MemoryError`).
- `test_the_payload_is_read_as_utf8_bytes_of_the_length_its_line_names`
  (a made-up `Muñoz`, decision 176).
- `test_a_malformed_or_oversized_line_says_the_usage_and_retires`.
- `test_the_end_of_input_ends_the_engine_quietly` (before a line; inside a
  payload).
- `test_a_command_that_leaves_a_lock_held_or_unreleased_retires_the_engine`.
- `test_a_command_that_changes_the_environment_the_temp_folder_or_the_working_folder_retires_the_engine`.
- `test_a_thread_left_running_retires_the_engine`.
- `test_the_engine_retires_after_its_command_budget`.
- `test_a_pass_or_the_after_install_step_is_refused_and_never_started_here`.
- `test_nothing_a_command_starts_can_read_the_engines_frames` (a child
  reading its input gets the end of input at once).
- `test_every_command_has_its_own_reading_hold_and_store`
  (`settings._HELD` is `None` and the store closed between commands).
- `test_the_end_line_follows_the_reply_on_a_line_of_its_own_even_after_unended_output`.
- `test_the_engine_reads_documents_only_in_a_child`
  (`content_check.READ_IN_A_CHILD` is true; after a reading command the
  engine's `ocr` built no engine of its own).
- `test_the_retirement_is_said_in_the_error_log_by_its_code_alone`.

**`tests/test_locking.py`**: `test_held_now_counts_the_locks_this_process_holds`,
`test_a_release_that_can_neither_delete_nor_mark_is_named_as_left_unreleased`.

**`tests/test_api.py`**: removed with the spare -
`test_a_spare_runs_the_one_command_it_is_handed_and_replies_as_a_fresh_process_does`,
`test_a_spare_handed_nothing_exits_quietly`,
`test_a_spare_handed_a_malformed_line_says_the_usage_and_runs_nothing`
(their claims move to `test_resident.py`). New:
`test_own_process_commands_are_every_command_that_runs_a_pass_or_the_after_install_step`
(derived from the commands' functions reaching `runner.main` or
`after_install.run`, as `WRITING_COMMANDS` is derived from the writers),
`test_the_vocabulary_names_the_own_process_commands`.

**`tests/test_api_entry.py`**: `test_the_entry_given_the_spare_flag_waits_for_its_command`
becomes `test_the_entry_given_the_resident_flag_serves_until_the_end_of_input`.

**`tests/test_layers.py`**: `resident` in layer 5 with its comment.

**`tests/test_single_source.py`** (main.js through `_run_spawns`; the
harness's fake `spawn` gains an engine child that answers frames, can be
made busy, slow, silent, or to end): replaces the six spare tests (around
lines 4734-4849) with
`test_the_shell_starts_one_engine_before_the_window_and_hands_it_each_command_while_it_is_free`,
`test_a_command_that_comes_while_the_engine_is_busy_starts_a_process_of_its_own`,
`test_a_pass_and_the_own_process_commands_never_go_to_the_engine`,
`test_an_engine_from_before_the_program_changed_is_ended_and_the_command_runs_alone`,
`test_a_read_handed_to_an_engine_that_died_is_asked_once_more_and_a_write_never`,
`test_a_command_past_the_time_limit_kills_the_engine_says_so_and_a_new_one_starts`,
`test_an_engine_that_keeps_stopping_is_left_off_for_the_session_and_said_in_the_error_log`,
`test_a_retiring_engine_is_replaced_at_once`,
`test_an_end_line_for_another_command_is_a_broken_stream`,
`test_quitting_ends_the_engines_input_and_never_kills_it_mid_command`,
`test_the_shell_and_the_engine_agree_on_the_flag_the_end_key_and_the_line_limit`;
`test_the_shell_and_the_api_agree_on_the_spare_the_early_overview_and_the_count_line`
keeps its early-Overview and count-line claims with the engine in place of
the spare.

### 3.8 Measurement (in the handoff)

On this Mac (`build-portable/venv`, Python 3.14) from source, and in the
packaged app's `tracker-api`, with `TRACKER_SETTINGS_DIR` and
`TRACKER_DATA_HOME` in the builder's scratchpad and the suite's made-up
50-household firm (`tests/samples.py`, SPEC-scale-1000 section 8's
method): the time from a command's request to its reply's last byte,
median of 20, for `templates`, `last-pass`, `watch`, `state` (one return),
`list` and `firm` (warm) - three ways: a fresh process, a spare (today), the
engine. A throwaway Node script in the builder's scratchpad starts the
processes exactly as `startTracker` does; it is not committed. Also: the
engine's resident memory after 500 commands (to judge `COMMANDS_MAX`), and
the number of processes started by a scripted session (launch, open ten
returns, three writes, two refreshes) before and after.

**The target:** the office PC's 0.85 s a command (SPEC-speed-round) is the
figure to beat; the Windows check measures `state`, `last-pass` and `watch`
the same way there, and the acceptance is under 0.25 s each with the
engine. On this Mac the engine's `state` should be the command's own time,
with the 0.21 s import gone.

---

## 4. P278 - the engine pages the firm lists (effort L)

**Why, for a person.** Today the engine sends the window the whole firm's
answer - every return, every waiting file and its path, several megabytes
at 2,000 returns (3.9 MB measured in the speed round) - and the window
builds, sorts and filters all of it before it shows a page of 50. After
this change the engine sorts, filters and cuts the list into pages, and
sends only the page shown plus the firm's totals and each return's counts.
Turning a page reads a saved copy of that same answer, so every page of one
list is from one moment, as it is today.

### 4.1 The design in one paragraph

A **fresh** `firm` (at launch, after a Sort, F5, or a write that moves a
count - SPEC-shell 4.2's triggers, unchanged) does exactly today's work,
then saves its whole answer - **the view** - in the data home and answers one
page of it with the view's token. A **page turn**, a column header, an
Overview tab, a reason card, the Clients switch, a Client Type, or moving to
another firm list asks `firm` again **with that token**: the engine reads
the saved view (no walk, no fingerprint, no record read), pages it, and
answers. A token that no longer matches - another fresh `firm` saved a newer
view, the day, the program, the clients folder or the data folder changed,
the file is gone or damaged - is answered by a fresh `firm`, with a new
token. The engine keeps nothing between commands: the view is a file, so
this works the same in the engine of P276, in a process of its own, and
after the engine has started afresh.

### 4.2 The request (`firm` and `firm-last`, JSON on stdin)

```
{"page": {"list": "overview" | "needs_review" | "reminders" | "clients",
          "at": n,                                  # the page, from 0; past the end is the last page
          "order": {"cell": str, "dir": 1 | -1} | null,   # this PC's stored order for the list (P199)
          "filter": {...}},                         # below
 "view": "<token>"}                                 # absent: a fresh firm
```

Filters: `overview` `{"tab": "all" | "need" | "waiting"}` (P145);
`needs_review` `{"reason": "" | <reason code>}` (P149); `reminders` `{}`;
`clients` `{"all": bool, "type": "" | <client type key>}` (P153). Cells are
each list's columns as `PAGES_COLUMNS` names them today. **No `page`**:
today's whole reply, byte for byte - the engine's own tests, the cache's
tests and a command line keep working. The page size is the engine's,
`firm_pages.PAGE_SIZE = 50` (P174), not the window's: Compact Rows changes
how many rows fit on screen, not how many a page holds.

### 4.3 The reply (paged form)

```
{"view": "<token>" | null,          # null: not saved (firm-last; or a save that failed)
 "totals": {...}, "next_sort": ..., # as today, the whole firm
 "return_counts": [{"path", "household", "year", "form", "counts",
                    "files", "problem", "paused"}],   # every active return, compact
 "page": {"list", "at", "pages", "from", "to", "total",
          "order", "filter",        # echoed; a reason no longer present is "" (as the page does now)
          "counts": {...},          # overview {all, need, waiting}; needs_review {all, reasons: [[code, n], ...]};
                                    # clients {work}; reminders {}
          "many_years": bool,       # P268: more than one tax year in the whole list, before its filter and pages
          "rows": [...]},           # the page's rows, in order
 "paths": {key: path},              # only the keys this page's rows name (ruling 15)
 "files_found": [{"name", "return", "year", "handle"}],   # needs_review only: every waiting file, for Search
 "warnings": [...]}
```

`many_years` is SPEC-ui-menu-small M4's count moved to the engine word for
word: over the whole list before its tab and its pages (the Overview's
paused households and both buckets; Reminders' every ready draft), a blank
year not a year; Overview and Reminders only (false elsewhere). When it is
false an order by Tax Year kept on this PC is not applied - the list is in
its usual order - and is still echoed, so it applies again when the column
comes back (M4's rule).

The paged reply carries **no** `returns`, `files` or whole `paths`: a renderer
that still reads them fails loudly in the tests rather than drawing half a
page. `return_counts` is what the household, year and return pages and the
side panel need from the firm (`pagesFirmReturn`, `shellCountsDiffer`,
`pagesReturnSpecs`); about a tenth of today's reply at 2,000 returns, to be
measured.

Rows, per list - the data the window draws from, never its words or keys:

- `overview`: `{"kind": "paused", "household", "household_path"}` (ruling
  21, P195) or `{"kind": "return", "bucket": "need" | "wait", ...today's
  returns[] entry}`.
- `needs_review`: groups as the page groups them when this is built - **one
  per return**, the default SPEC-ui-menu-layout builds for P272 (its
  question J1) - each `{"path", "household", "household_path", "year",
  "form", "links", "files": [today's files[] entries]}`, so the heading
  needs nothing else of the firm. If Jason answers J1 "per household", the
  key is the household and the heading's fields follow; either way the
  builder moves `pagesReviewGroups` as P272 leaves it into the engine
  unchanged. A group is never split across pages; a page holds whole groups
  up to 50 files, and a larger group is a page of its own (P174); `from`,
  `to` and `total` count files.
- `reminders`: today's returns[] entries whose draft is ready.
- `clients`: `{"name", "path", "links", "returns": n, "need": n, "wait": n,
  "problem": str, "paused": bool, "work": bool}` - today's
  `pagesClientSpecs` grouping of the firm's returns by household, done once
  in the engine from the same walk.

### 4.4 Order and filter, in the engine (`tracker/firm_pages.py`, new; its own `tests/test_firm_pages.py`)

**Layer 0** (`tests/test_layers.py`: "`firm_pages` joins L0 with P278: a
firm reply cut into one page, and the view file; the standard library,
`settings`, `fsio`, `errors` and `firm_cache`'s head - the API hands it the
words"). No CLI. It decides nothing about counts: it takes the whole reply
`api._cmd_firm` built and the names that walk saw.

- `page(whole, names, words, ask) -> dict`: the filter narrows the whole
  list first, then the order, then the page (P174's rule, as the window does
  it now); `at` past the end is the last page.
- **The usual orders** (no header pressed), moved from the window unchanged:
  Overview - paused households by name, then the returns needing a person
  (a return with a problem first, then the oldest waiting file, then the
  name), then the returns waiting (the due date, then the name); Needs
  Review - groups by their oldest file, then the name, files by received
  date then name; Reminders - by return name; Clients - by household name.
- **A header's order**: by that cell's key, blanks last in either
  direction, ties keeping the usual order (`pagesCompare` today). The keys
  are today's `keys`: Tax Year (the number), Taxpayer (the return's name
  less its recorded form, `pagesTaxpayer`'s rule against
  `layout.RETURN_NAME_PATTERN`), Form (its place in the client types' forms,
  then its name, `pagesFormKey`), status (`[urgency, -count, words]`, the
  urgencies `PAGES_URGENCY`), the date (ISO), detail and name as text. On
  Needs Review, files are ordered within each group and groups follow their
  first file (`pagesOrderedGroups`).
- **Text order** - `name_order(text)`: the key that orders as the window's
  collator does (`Intl.Collator(undefined, {numeric: true})`, N1): runs of
  digits compare as numbers; other runs compare first without accents or
  case (white space, then punctuation, then symbols, then digits, then
  letters, as the collator's root order puts them), then by accents, then
  lower case before upper. Python has no copy of the collator's tables, so
  for names written in letters outside the Latin alphabet the order may
  differ slightly from today's; every page of one list agrees with every
  other (Jason's question E, section 8). A shared made-up list
  (`tests/samples.py`, `COLLATION_NAMES`, with its order) is held by both
  languages' tests.
- **The words in a key** (status words, the paused word, the held word, the
  stage words, the reasons' short labels) are handed in by the API from the
  same `SCREEN` and vocabulary the window reads (`api._firm_words()`), never
  typed twice.
- **The view file**: `PAGES_FILENAME = "firm-pages.json"` in the data home
  beside the store and `firm-view.json`, written whole through
  `fsio.write_text_atomically` by `save_view(whole, names, head) -> token`
  (`{"format": 1, "view": <16 random hex>, "head": firm_cache.head(root,
  today), "names": ..., "reply": whole}`), read by `load_view(token, head) ->
  View | None`. Missing, damaged, another format, another token or another
  head is `None`; a damaged file is set aside and said on the error log by
  its class, as P120's cache is (never its words). Like `firm-view.json` it
  holds household names, return folders and the names of files waiting for a
  person; it lives only in the data home (decision 186), is never synced,
  and deleting it is always safe. It is saved inside the reading hold, as
  P120's cache is.
- Refusals: an unknown list, cell, filter or a malformed `at` raises
  `PageAskError` with `FIRM_PAGE_REFUSED` - "The app asked for a list the
  engine does not have; nothing was read." (one new sentence in
  `api.py`; the window says it as a notice with Retry) - never a guessed page.

### 4.5 `tracker/api.py`

- `_cmd_firm(argv)` reads `_read_spec()` (an empty stdin is `{}`, today's
  call): no `page` - today's reply; `page` with `view` -
  `firm_pages.load_view(...)`, and on `None` the fresh path; the fresh path
  - today's work, then `save_view` (a save that fails is said on the error
  log by class and the reply's `view` is `null`: right, and the next turn
  reads fresh), then `firm_pages.page`.
- `_cmd_firm_last` pages its reply the same way when asked with `page`, with
  `view: null` (it saves nothing, P229); a page turn while the launch's
  last counts stand waits for the fresh reply (4.6).
- `firm` stays out of `WRITING_COMMANDS` and in `HELD_READING_COMMANDS`: what
  it writes is disposable data-home state, as P120's cache is.

### 4.6 The window (`app/renderer/shell.js`, `pages.js`)

- `shellFirmAsk(list)` builds the request for a list from what the window
  holds today: `pagesPageAt[list]`, `pagesStoredOrder()[list]`, `pagesTab`,
  `pagesReasonPick`, `pagesClientsAll`, `pagesClientType`. The list is the
  firm page on screen, else the Overview.
- `shellLoadFirm` (every fresh trigger) sends it **without** a view, as
  today's `call(["firm"])` with that payload; the launch's early `firm`
  (P221, `shellAskFirmNow`) and `firm-last` (P229) send the Overview's.
- `shellTurnFirm(list)` (a page turn `pagesTurn`, a header `pagesOrderBy`, a
  tab, a card or a type `pagesPick`, and moving to another firm list) sends it
  **with** the held view's token. Meanwhile the page keeps the rows it holds
  for that list, marked Updating (P222's marker, `shellMarkUpdating`); with
  none held for that list, its loading state (SPEC-shell 6). A turn while a
  fresh load is on its way waits for it, and one turn follows from the new
  view if the page wanted is not the one it brought. A late reply for a page
  no longer wanted is dropped (a generation counter, decision 193's way).
- The window keeps the last reply **per list** and takes `totals`,
  `next_sort` and `return_counts` from the newest reply of any list.
  `pagesFirmReturn`, `shellCountsDiffer` and `shellCounts` read
  `return_counts` and `totals`.
- `pagesOverview`, `pagesNeedsReview`, `pagesReminders`, `pagesClients` draw
  the page's rows in the order given: `pagesWorkRows`, `pagesReviewSpec`,
  `pagesReminderSpecs` and `pagesClientSpecs` become mappers from a row to
  its spec (the words, tone, date and links, as today) - no filter, sort or
  slice. The tabs' counts, the reason cards and the Work Waiting count come
  from `page.counts`; the Tax Year column follows `page.many_years` (P268:
  `pagesYearsDiffer` goes, its count now the engine's);
  the footer is `pagesFoot(list, from, to, total, at, pages)` from
  `page` (N10's one-page rule unchanged).
- **Dead code deleted first** (the gate's rule): `PAGES_PER_PAGE`,
  `pagesPaged`'s slicing, `pagesOrdered`, `pagesCompare`, `pagesCompareKeys`,
  `pagesIsBlank`, `pagesUrgent`, `pagesOrderedGroups`, `pagesReviewGroups`,
  the specs' `keys`, and `pagesFormKey` if nothing else reads it.
  `PAGES_COLLATOR` stays: the household, year and return pages still order
  their few rows by name in the window.
- **Search** (8.2) keeps working: households and returns come from `list`,
  which is whole, as today; on Needs Review its waiting files come from the
  reply's `files_found`, every waiting file, not only the page's (N5's fold
  cache is built from it).
- **The household page's grouping, the Clients tab's grouping**: Clients'
  grouping by household moves to the engine (4.3); the household and year
  pages are drawn from `list` and `return_counts`, as today from `list` and
  the firm's returns.
- `shellLastOf` checks the paged shape (`page` and `return_counts`) in place
  of `returns`.

### 4.7 Failure behaviour

A refused ask is the notice with Retry; a failed fresh `firm` is today's
"counts not available" notice, and the pages keep what they last drew; a
view that cannot be read is answered fresh (slower, never wrong); a view
that cannot be saved means each turn reads fresh, said on the error log.
No page is ever drawn from rows of two different views.

### 4.8 SPEC-shell and runbook sentences

- **4.2**, the `firm` bullet, add: "Each ask names one page of one list
  (P278, 9.2's paged form): the firm page on screen, or the Overview's
  first page when none is. A page turn, a column header, an Overview tab, a
  reason card, the Clients switch or a Client Type asks for that page of the
  same view, and the page keeps its rows, marked Updating, until it lands;
  the asks listed above ask without a view, so the counts are read afresh."
- **6.4**: "500 households draw in one pass (one `DocumentFragment`); no
  paging, no virtual list. Search (8.2) is the fast way to one household."
  becomes "The engine pages the list, 50 households a page (P174, P278);
  Search (8.2) finds every household, not only the page's."
- **9.2**: add "**Paged form (P278).**" with 4.2 and 4.3 of this SPEC; **9.4**
  gains the tests of 4.9.
- `docs/runbook.md`, the data folder's paragraph after `firm-view.json`:
  "A fourth, `firm-pages.json` (pilot P278), holds the Overview's last whole
  answer so that turning a page of a firm list does not read every household
  again; like `firm-view.json` it holds household names, return folders and
  the names of files waiting for a person, it is never synced, and deleting
  it is always safe."

### 4.9 Tests

**`tests/test_firm_pages.py`** (new; made-up replies):
`test_a_page_holds_fifty_rows_in_order_and_says_where_it_is`,
`test_a_page_past_the_end_is_the_last_page`,
`test_needs_review_pages_by_whole_groups_up_to_fifty_files_and_a_larger_group_is_a_page_alone`,
`test_the_tab_the_reason_and_the_client_type_narrow_the_whole_list_before_order_and_pages`,
`test_a_reason_no_longer_present_falls_back_to_all`,
`test_each_header_orders_by_its_key_blanks_last_both_ways_and_ties_keep_the_usual_order`,
`test_status_orders_by_urgency_then_the_larger_count_then_its_words`,
`test_the_usual_orders_are_the_pages_own`,
`test_needs_review_orders_files_in_each_group_and_groups_follow_their_first_file`,
`test_names_order_as_the_windows_collator_orders_the_shared_list`,
`test_the_taxpayer_and_form_keys_follow_the_recorded_form_never_a_guess`,
`test_many_years_counts_the_whole_list_before_its_tab_and_pages`,
`test_an_order_by_tax_year_is_not_applied_while_the_list_holds_one_year`,
`test_an_unknown_list_cell_or_filter_is_refused_by_name`,
`test_the_view_is_one_file_in_the_data_folder_written_whole_and_set_aside_when_damaged`,
`test_a_view_of_another_token_root_program_day_or_data_folder_is_never_used`.

**`tests/test_api.py`**:
`test_firm_without_a_page_answers_the_whole_reply_as_before`,
`test_firm_with_a_page_answers_one_page_the_totals_and_every_returns_counts`,
`test_the_paged_reply_carries_no_returns_or_files_list_and_paths_only_for_its_rows`,
`test_a_turn_with_the_view_reads_no_record_and_takes_no_fingerprint`
(the walk, `firm_cache.fingerprint` and the record readers patched to
fail), `test_a_turn_with_a_stale_view_answers_fresh_with_a_new_view`,
`test_the_pages_of_one_view_together_are_the_whole_ordered_list`,
`test_firm_last_pages_its_reply_and_names_no_view`,
`test_the_firm_page_size_is_fifty`. Every existing firm test (`test_firm_*`
around lines 8476-9874, `test_the_last_counts_are_the_firm_reply_when_nothing_changed`)
keeps passing on the whole reply.

**`tests/test_shell.py`** (lifted):
`test_a_turn_asks_the_engine_for_the_page_with_the_view_and_keeps_the_held_rows_marked_updating`,
`test_a_header_a_tab_a_reason_card_or_a_client_type_asks_page_one_of_the_new_order`,
`test_a_refresh_asks_the_page_on_screen_without_a_view`,
`test_a_turn_during_a_fresh_load_follows_it_from_the_new_view`,
`test_the_household_and_year_pages_read_their_counts_from_return_counts`,
`test_search_on_needs_review_finds_files_on_every_page`,
`test_the_pages_collator_orders_the_shared_list_as_the_engine_does`,
`test_the_engines_taxpayer_form_and_count_words_are_the_pages`
(the Python answers for a set of made-up inputs, computed in the test,
against the lifted `pagesTaxpayer`, `pagesFormKey`, `pagesCounts`).
Moved to `test_firm_pages.py` (the claims kept, the window's half becoming
"asks"): `test_the_firm_lists_divide_the_whole_ordered_list_into_pages_of_fifty`,
`test_needs_review_pages_by_whole_return_groups_and_counts_files`,
`test_overviews_tabs_narrow_the_whole_list_and_carry_their_counts`,
`test_needs_reviews_reason_cards_count_each_reason_and_filter_the_whole_page`,
`test_a_client_type_narrows_clients_by_the_recorded_form_and_shows_a_removable_chip`,
`test_a_header_orders_its_list_then_reverses_then_returns_to_the_usual_order`,
`test_status_orders_by_urgency_not_alphabetically`,
`test_dates_order_by_the_iso_date_and_blanks_go_last_both_ways`,
`test_needs_review_orders_files_in_each_group_and_groups_follow_their_first_file`.
Changed: the tests lifting `pagesClientSpecs` (around 1567, 2528, and N7's
call count near 6702), `test_the_firm_pages_rows_link_by_the_firms_keys_and_carry_the_year`,
`test_the_search_finds_waiting_files_on_needs_review_and_its_placeholder_says_so`,
`test_the_harness_stub_replies_have_the_shape_of_the_engines` (the paged
shape). The harness stub (`pilot/harness/stub.js`) answers the paged form
from its made-up data.

**`tests/test_single_source.py`**: `firm_pages.PAGES_FILENAME` joins
`owned` in `test_documents_name_only_runtime_files_the_code_owns`.

### 4.10 Measurement (in the handoff)

With the made-up firm at 1,000 households / 2,000 returns (SPEC-scale-1000
section 8's generator, `TRACKER_DATA_HOME` in the scratchpad): the reply's
bytes for each firm page, before (whole) and after (one page); the fresh
`firm`'s time before and after (the view's save added); a page turn's time
(before: the window's, after: the engine's, through P276's engine and
through a process of its own); and in the harness (500 households, Electron)
each firm page's draw time and a page turn's, median of five.

---

## 5. Measurements, all in one table (filled by the builders' handoffs)

| What | Before | After | Where |
|---|---|---|---|
| Engine processes started by the last-pass watch, 10 idle minutes | 10 (one a minute, by the timer) | 0, by construction: no timer remains (pinned by `test_no_timer_asks_last_pass`); not counted in a live window | this Mac (1.7) |
| A scheduled pass's end to the last-sort line | up to 60 s | the file's write to the app's message 263 ms (median of 5, real `fs.watch` under a fake Electron), plus the `last-pass` command 0.225 s: about 0.5 s to the page's answer; the line's redraw itself not timed in a live window | this Mac (1.7) |
| Return page draw at 1,000 rows; nodes in the document | | | harness (2.8) |
| `import tracker.api` (paid per command before the engine) | 0.21 s (this SPEC, median of 5, Python 3.14) | paid once a session | this Mac (3.8) |
| `state`, `last-pass`, `watch`, `templates`, `list`, `firm`: fresh / spare / engine | | | this Mac (3.8) |
| The same, `state`, `last-pass`, `watch` | about 0.85 s | under 0.25 s (acceptance) | office PC, Windows check |
| Firm reply bytes at 2,000 returns | about 3.9 MB (speed round) | | sandbox (4.10) |
| A firm page turn | | | harness and sandbox (4.10) |

---

## 6. What each item's sentences change, collected

| Document | Section | Item |
|---|---|---|
| `pilot/SPEC-shell.md` | 3.6 (long lists; keyboard) | P279 |
| | 4.2 (`firm` asks one page) | P278 |
| | 5.4 (four channels), 5.5 (the watch; the engine) | P277, P276 |
| | 6.4 (Clients paged by the engine), 6.5-6.7 (pointer to 3.6) | P278, P279 |
| | 8.3 (the line follows the file) | P277 |
| | 9.2 (paged form), 9.4 (tests) | P278 |
| `docs/runbook.md` | "One waiting helper" becomes "One engine" | P276 |
| | "The last-pass line" | P277 |
| | the data folder's files (`firm-pages.json`) | P278 |
| `tracker/locking.py` docstring | "Each app command is its own short process" | P276 |
| `api_entry.py` docstring | "And a warm spare" becomes "And the engine" | P276 |

P259 Q1 (the 60-second idle cadence) is superseded by P277; SPEC-speed-round's
refusal of a long-lived worker is superseded by P276 (3.1). Both are history
and stay as written.

---

## 7. Scope: the order, the builders, the files, the tests, the review

### 7.1 Order, and why not the one first suggested

**P277, then P279, then P276, then P278.** P277 is small and stands alone.
P279 is the window only and stands alone. P278 is not small - it moves the
four firm lists' order and filters into the engine, adds a saved view, and
changes the reply every firm page and the harness read - and its page turns
become engine asks: before P276 each turn is a process start (most of a
second on the office PC) where today it is instant in the window, so P278
lands after P276, never before it. P276 is the largest single change, but
P278 depends on it for its speed, not the other way round.

The builds are sequential, each on the previous one's tree: P277 and P276
both change `main.js`, P279 and P278 both change `pages.js` and `shell.js`,
and all four change `tests/test_shell.py` or `tests/test_single_source.py`.
They land together as one draft pull request when the stack is final
(decisions 207, 211).

### 7.2 Builders, files, tests

One **sonnet** builder per item, in a session of its own. It builds exactly
its section, deletes dead code in the files it changed first, runs its tests
- **each file its own process**, under `build-portable/venv/bin/python` (3.14,
the only interpreter on this Mac); the office PC runs the floor's (3.11)
and its own in the Windows check - and writes its handoff with section 5's
numbers. **No commit and no map update by the builder.** Guard files every
build runs: `tests/test_layers.py`, `tests/test_single_source.py`,
`tests/test_tripwire.py` (tests change in every build), `tests/test_errors.py`
(P276 and P278 add sentences; P277 and P279 run it anyway, it is fast).
`tests/test_repo_map.py` is the orchestrator's, after the map is refreshed.

| Build | Files it may touch | Tests it runs (each its own process) |
|---|---|---|
| **1 - P277** | `app/main.js`, `app/preload.js`, `app/renderer/shell.js`, `tracker/api.py`, `tests/test_api.py`, `tests/test_shell.py`, `tests/test_single_source.py`, `pilot/harness/stub.js`, `pilot/harness/app-stub.js`, `pilot/SPEC-shell.md` (5.4, 5.5, 8.3), `docs/runbook.md` (the last-pass line) | `test_api.py`, `test_api_entry.py` (imports `api`), `test_shell.py`, `test_shell_menu.py`, `test_single_source.py`, guards |
| **2 - P279** | `app/renderer/pages.js`, `app/renderer/app.js` (the editor), `app/renderer/shell.js` (the scroll hook, `pagesKey`'s caller if needed), `app/renderer/shell.css` (`.rows.is-virtual`), `app/renderer/style.css` (editor spacer rows), `tests/test_shell.py`, `tests/test_pilot_ui.py`, `pilot/harness/stub.js`, `pilot/harness/interact.mjs`, `pilot/SPEC-shell.md` (3.6, 6.5-6.7) | `test_shell.py`, `test_shell_menu.py`, `test_pilot_ui.py`, guards; the harness scenarios of 2.7 |
| **3 - P276** | `tracker/resident.py` (new), `tests/test_resident.py` (new), `tracker/api.py`, `tests/test_api.py`, `api_entry.py`, `tests/test_api_entry.py`, `tracker/locking.py`, `tests/test_locking.py`, `tests/test_layers.py`, `app/main.js`, `tests/test_single_source.py`, `pilot/SPEC-shell.md` (5.5), `docs/runbook.md` (the engine) | `test_resident.py`, `test_api.py`, `test_api_entry.py`, `test_locking.py`, and - because `locking` changed and the engine imports it - the own test file of every module that imports it (`repo_map.py show tracker/locking.py`): `test_after_install.py`, `test_filer.py`, `test_households.py`, `test_ledger.py`, `test_manifest.py`, `test_ocr.py`, `test_progress.py`, `test_reminder.py`, `test_rollover.py`, `test_runner.py`, `test_scanner.py`, `test_scheduling.py`, `test_store.py`; guards |
| **4 - P278** | `tracker/firm_pages.py` (new), `tests/test_firm_pages.py` (new), `tracker/api.py`, `tests/test_api.py`, `app/renderer/pages.js`, `app/renderer/shell.js`, `app/renderer/app.js` (only where it calls `firm`), `tests/test_shell.py`, `tests/samples.py` (`COLLATION_NAMES` only), `tests/test_layers.py`, `tests/test_single_source.py`, `pilot/harness/stub.js`, `pilot/SPEC-shell.md` (4.2, 6.4, 9.2, 9.4), `docs/runbook.md` (the data folder) | `test_firm_pages.py`, `test_api.py`, `test_api_entry.py` and `test_resident.py` (both import `api`), `test_firm_cache.py` (its head is read), `test_shell.py`, guards |

Builds 3 and 4 add a Python module; the frozen build must carry it.
`api_entry.py` imports `tracker.resident` at call time inside its main
block, which PyInstaller's analysis follows; the Windows check's installer
build confirms it (`pilot\wintest\run_checks.ps1 -Tests` with build 3's
and 4's files, and the hands-on steps: open the app, open ten returns, one
write, a Sort with Stop, quit during a write; the Mac check the same
through `pilot/mactest/run_checks.sh`).

### 7.3 Review

**Opus, high effort, in a session that did not build**, after each build:
numbered findings against this SPEC. Sonnet fixes the findings and nothing
more and reruns only the tests the fixes touch; Opus reviews again; a
finding that survives one rebuild is fixed by Opus itself, and if that fix
fails review the orchestrator stops and tells Jason. After a review with no
findings the orchestrator deletes dead code it finds, runs
`python -m ruff check .`, edits `docs/repo-map.curated.json` (7.4), runs
`python tools/repo_map.py update`, `check` and `tests/test_repo_map.py`, and
commits.

### 7.4 Curated map entries (`docs/repo-map.curated.json`), for the orchestrator

- **`tracker/resident.py`** (new node): role - "The app's engine (P276,
  pilot/SPEC-ui-menu-speed.md 3): one process per app session that answers
  the commands main.js hands it while it is free, over its standard input -
  a line {id, argv, bytes} and the payload's bytes in, `api.main`'s own
  output and an end line {engine_end, code, retiring} out. It refuses the
  own-process commands (a pass, the after-install step), keeps its real
  input from anything a command starts, and retires after any command that
  left a lock held or unreleased, the environment, temp or working folder
  changed, a thread running, an escaped error, or after COMMANDS_MAX
  commands, saying the reason on the error log by code." Notes - "Layer 5
  beside api; nothing imports it but api_entry.py at call time. Replaces
  P220's spare (api.spare is gone). Decision 171's leftover answered by
  retirement; one store, one reading hold and the kill per command kept
  (SPEC 3.1)."
- **`tracker/firm_pages.py`** (new node): role - "The firm lists cut into
  pages (P278, SPEC-ui-menu-speed 4): the filter, then the order (the
  window's usual orders and header keys, `name_order` for text), then a
  page of 50 (Needs Review by whole groups); and the view file
  firm-pages.json that page turns read instead of walking the firm." Notes -
  "Layer 0: the standard library, settings, fsio, errors and firm_cache's
  head. The API builds the whole reply and hands the words; this module
  decides no count."
- **`artifact:firm-pages.json`** (new node, layer runtime): "The firm's last
  whole answer and the names its order needs, saved by each fresh `firm` in
  the data home beside firm-view.json, keyed by a token the page sends back
  to turn a page; disposable, never synced; client names and return folders,
  as the cache holds." Edges: `tracker/firm_pages.py` writes and reads it.
- **`app/main.js`** notes: the spare's passage becomes the engine's (3.4) and
  the last-pass watch (1.2); edge `app/main.js` spawns `tracker/resident.py`
  beside its two spawns.
- **`tracker/api.py`** notes: P220's spare sentence becomes "retired by P276";
  add `OWN_PROCESS_COMMANDS`, `say_failure`, `vocab.shell.last_pass_file`,
  the paged form of `firm` and `firm-last`, `FIRM_PAGE_REFUSED`.
- **`tracker/locking.py`** notes: `held_now()` and `left_unreleased()`, for
  the engine.
- **`api_entry.py`** role and notes: the resident flag in place of the spare.
- **`artifact:last-pass.json`** role: add "main.js watches its folder and
  tells the page when it changes (P277); main.js never reads it". No edge is
  drawn for the watch: no edge type says "watches", and `reads` would be
  false.

---

## 8. Questions only Jason can answer (each has a default; nothing waits on them)

- **A (P279). Lists of 100 rows or fewer are drawn whole, as today.**
  Default: yes. A household, a year and most returns never reach 100 rows,
  so they look and behave exactly as now; only a very long return and its
  editor change. The alternative is to virtualize every list of those pages
  at any length.
- **B (P279). In a list long enough to be virtual, a long return or
  household name ends in "…" with its tooltip instead of wrapping to a
  second line** (rulings 21, 27 keep wrapping in every list drawn whole).
  Default: yes - rows of one height are what make the long list fast and
  steady.
- **C (P278). Turning a firm page, pressing a column header, or choosing a
  tab, a reason card or a Client Type now asks the engine** - with the
  engine of P276, expected about 0.1-0.3 s; the page keeps its rows marked
  Updating meanwhile. Today these are instant in the window. Default:
  accept, as the price of sending a page instead of the whole firm.
- **D (P276). If the engine stops three times in five minutes, the app
  carries on for that session with a process per click, as before the
  spare**, and says so in the error log only - no notice, since every click
  is still answered. Default: no notice. The alternative is one notice
  "Running slower: the engine kept stopping".
- **E (P278). Names written in letters outside the Latin alphabet may
  order slightly differently from today** (the engine has no copy of the
  window's collation tables); every page of one list agrees with every other.
  Default: accept.
