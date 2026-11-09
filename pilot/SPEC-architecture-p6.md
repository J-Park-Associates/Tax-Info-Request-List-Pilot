# SPEC-architecture phase 6: the shell

Written by the SPEC writer and measured at `9df1724`, the phase's base, where P5.16 landed and phase 5 ended. Every
line number below is at `9df1724` unless a job says it was measured after an earlier job. The scope is
SPEC-architecture section 9's "Phase 6" paragraph (837-842), with section 5.4's target shape (404-414) and the
`app.js`, `shell.js` and `main.js` rows of section 4.2. The audit findings it builds are in
`pilot/AUDIT-2026-10-13-architecture.md`: D-1 (1147), D-3 (1226), D-4 (1250), D-5 (1295), D-6 (1326), D-7 (1342),
D-11 (1401) and D-12 (1413); section 2 says in one line each what is left of D-2, D-8, D-9 and D-10. The SPEC
reviewer's findings go to `ORCH/spec-p6/review-<r>.md`. This is the round-4 draft: revised against review 1's
findings S1-S16 and its notes, review 2's findings S17-S23 and its notes, review 3's findings S24-S26 and its notes,
and the orchestrator's answer
(`threads/P6/003`: nothing a person sees may change in any window, so the SPEC removes the difference rather than
asking Jason; P6.6 says how, and P6.5 does the same for the Hand Over list's own window, R6.5.5).

## 1. The answer

Phase 6 takes apart the window's three big scripts without changing anything a person sees. `app/renderer/app.js`
(4,285 lines) becomes nine classic scripts loaded just before it - `api-client.js`, `notices.js`, `dialogs.js`,
`reminder-card.js`, `review-rows.js`, `household.js`, `editor.js`, `schedule.js`, `pass.js` - and keeps the state,
the vocabulary, the start, the lock watch and the wiring (about 830 lines). `shell.js` (1,819) gives its loading of
the Overview's counts and the scheduled-pass watch to `firm-loader.js`. `app/main.js` (1,357) keeps the window, the
message channels and the app's lifecycle, and requires `shell-words.js`, `logs.js`, `last-pass-watch.js`,
`open-path.js`, `menu.js` and `engine.js`. Every name the scripts share keeps its spelling, so `shell.js`, `pages.js`
and `sheet.js` work unchanged; still plain scripts, no bundler, no framework, no new package.

Before anything moves, the tests stop reading these scripts by file name (D-5): a claim reads the function it is
about or the page's code as a whole, a guard fails if a test names a script this phase splits, and a new test loads
every script in order in one scope, so a move that breaks the load order fails in the suite. The engine then sends
four results the page works out for itself today (D-3): who a document may be handed to, a return's counts by group,
the group names and each return's taxpayer (on every row of the list, which the firm lists then read); the page draws
them and a test holds the engine's answer to the page's old one on the page's own inputs. `pilot.js` waits on a promise instead of polling (D-6), the paste parser gets its test (D-12), and - only
if Jason says yes to Q-D - the stylesheets' overridden rules are folded into one home (D-11).

## 2. What it relies on

**Decision rows:**
- 42, P63: every word on screen is the API's; at most five words.
- 76 and P76: the one `keydown` listener stays in `app.js` and hands the shell's keys on.
- 129, 192, 204: the feed list a hand-over may name; the household payload built once; the feed list read once.
- 137 and 201: `el()`'s attribute list; the one dialog registry, `openDialog` and `requestClose`.
- 176, 188, 190, 193: the window's checks, the one path authority, no network, the envelope and the error log.
- 203, P218, P221, P222, P228, P229, P262, P277, P278: the pass from the window, the counts' loading, the last-pass
  watch, the engine pages the firm lists.
- 209: one-time steps run themselves (main.js's launch door is untouched).
- P7, P10, P51, P67: pilot code additive, `style.css` unedited - all relaxed or retired by P309 (one codebase).
- P276: the resident engine and its framing; P279: the two virtual lists (deliberate).
- P309-P314: the plan, the type checker, the loop, the answers built meanwhile, the domains.
- P315 (P2.3, `replies.py`), P339 (`api.vocab`, `api.state`), P344 (`firm_view.py` at L4), P351 (the Mac kit's list).

**Landed jobs:**
- J3: `RENDERER_SCRIPTS`, `APP_SCRIPTS`, `PILOT_SCRIPTS`, `SHELL_SCRIPTS`, `renderer_text()` and the one lifter
  `js_function` (`tests/node_harness.py` 40-128); `tests/test_renderer_seams.py` with `SEAMS` (226) and `WRITES` (391);
  the double's test (499).
- J4: `tests/golden/` and `tools/patch_sites.py`. J5: `assigned.said`, `fromMainWindow`. J6: `tools/typecheck.py`
  (at `9df1724`: 106 errors in 19 files; `firm_pages` 6, `api` and `firm_view` 0).
- P2.3: `tracker/replies.py` (`StateReply` 68, `ListReply` 97, `FirmReply` 117, `FirmLastReply` 135).
- P5.7: `firm_view.GROUPS` (220), `item_group` (223), `file_group` (241), `_firm_row` (340).

**What the audit's other slice-D findings are now** (one line each):
- D-2 (renderer state in one global scope): phase 7's owner objects. This phase moves code byte for byte, so each
  split adds the cross-script writes it cannot avoid to `WRITES`, each named in its job (section 3).
- D-5 (text pins tied to file names): J3 built the shared readers; P6.1-P6.4 finish it.
- D-8 (the harness's double): J3 holds the double to the scripts; P6.4 holds the stub's replies to `replies.py`.
- D-9 (sentences typed in `app.js`): done, J3 (the guard) and J5 (`assigned.said`).
- D-10 (the sender check): done by J5; its comment and its typed refusal are closed in P6.15.

**SPEC-architecture:** section 5.1 (8: no new runtime dependency; 9: the engine decides, the screen draws), 5.4,
section 6, section 9's paragraph, section 11 (Q-D, Q-E) and P313.

### 2.1 Where this SPEC departs from section 5.4, section 9 or the audit, and why

| Item | What the plan or the audit asks | What this SPEC does | Why |
|---|---|---|---|
| **No facade** | Section 5.1 (4): the old module re-exports what moved until a last job removes it | No re-export and no facade job. A renderer script's top-level names are globals of the one page scope, so a moved function answers at the same name; a main-process module is `require`d by the one file that uses it. | Classic scripts have no module to re-export from; the global names stay the same (5.4). |
| **`reminder-card.js` and `review-rows.js`** | 5.4, D-1: `reminder.js`, `review.js` | Those names. | `tools/repo_map.py` `_unambiguous_stems` (396) gives `tests/test_<stem>.py` an owner edge only when one file has the stem: `reminder.js` and `review.js` would take `tests/test_reminder.py` and `tests/test_review.py` off `tracker/reminder.py` and `tracker/review.py`, and `test_a_module_is_tested_by_its_own_test_file_if_and_only_if_that_file_exists` (test_repo_map 851) would fail. No other new name collides (measured). |
| **What `api-client.js` takes** | D-1: `TrackerError`, `call`, `takeReply`, `withEng`, `viewGeneration`, `writeRow`, `writesInFlight`, `sayNotes` | All but `viewGeneration`, which stays in `app.js` with `select`, `renderFor` and `render` (451-509). | `select` writes `active` and `render` writes the state `let`s; moving the view generation would make every one a write across scripts (D-2, phase 7). |
| **The lock watch stays in `app.js`** | D-1 places it nowhere | `app.js` keeps 1765-1925 (`renderLock` to `clearLock`). | It is the state's (`locked`, `lockStale`) and is read by every other part; the plan's list of what app.js keeps is not closed. |
| **The state `let`s move to their one writer** | 5.4: `app.js` keeps the state | A `let` at the head of `app.js` (4-20) that only one new script writes moves to that script (section 4.0); the ones two scripts write stay. | Each one left behind would be a new write across scripts (D-2). |
| **Load-time statements stay in `app.js`** | D-1: split by line range | A new script carved out of `app.js` holds declarations only; every top-level statement that runs as the page loads stays in `app.js` (the after-install registration, 2298-2315, stays though it sits in the Schedule range). | The new scripts load before `app.js`, so `app.js`'s wiring finds their functions; a script that ran code at load could meet a binding not yet made. |
| **Strict mode as the code had it** | Nothing | The scripts carved out of `app.js` and the modules carved out of `main.js` have no `"use strict"` (their source has none); `firm-loader.js` has it, as `shell.js` (41) does. | A move must not change the mode its code runs in: sloppy and strict code differ (an assignment to an undeclared name, `this` in a call). |
| **`shell-words.js`** | D-4, 5.4: `engine.js`, `open-path.js`, `menu.js`, `logs.js`, `last-pass-watch.js` | Those, and `shell-words.js`: `shellSays`, `fill` and `shellFailure`. | Four of the modules say the shell's sentences and answer with its envelope, and CommonJS files share no scope; a module that `require`d `main.js` for them would be a cycle. |
| **`last-pass-watch.js`** | Section 9 names four modules; 5.4 names five | Five (with `shell-words.js`, six). | 5.4 is the target shape; the watch (151-159, 314-378) is a concern of its own that `learn()` drives. |
| **`firm-loader.js` keeps loose `let`s** | D-7: one `const firmLoad = {...}` and one `const lastPass = {...}` | The flags move byte for byte as `let`s; the owner objects are phase 7's. | D-2 and D-7's state objects are phase 7's (section 9). |
| **D-3's `taxpayer` on every list row; the firm lists read the list's** | D-3: on each `household.returns[]` row | On every row `_return_row` makes (api 2788: the list's `engagements` and `households[].returns`, the state's `household.returns`). The firm reply gains nothing: Needs Review's headings and the Overview's and Reminders' rows read the **list's** row for the return, as they read its name today, and `pagesTaxpayer` stays only for a firm row the list cannot answer (P6.6). | `pagesTaxpayer` has four callers (pages.js 383, 1069, 1344; app.js 2334). Two cut the list row's own name and form, which the new field holds exactly. The other two cut the **list's** name, found by path (`pagesReturnName`), with the **firm** row's form. A field cut on the firm row from the firm walk's names (`firm_pages._Walk.name_of`, review 1's S2 fix) equals that only when the list and the firm reply are from one walk: after a renaming write, on the launch's last counts, or for a return the list does not hold, it would show another name. The list's own row is the page's input, so reading it changes nothing in any window; where the list has no row for the return, or one with another form, only the page has the inputs, and its cut stays (threads/P6/003, step 2). |
| **`fedReturns()` stays as the reader** | D-3: drop `fedReturns` | Its body reads `state.hand_over_targets` whenever the state it holds is the shown return's, which is every moment but one: between `select()` and the next `render`, it keeps today's rule (R6.5.4, R6.5.5). | Its three callers (app.js 1012, 1135; pages.js 2167) and the double keep one name, and the seam table does not move. The page's rule excludes `active` and the engine's excludes the state's own return; they part only in that gap, and one Hand Over entry point is live in it (R6.5.5), so the page keeps its rule there (threads/P6/003, step 2). |
| **D-6 without `call()`** | D-6: `pilot.js` awaits `appReady` and calls through `call()`, so failures become notices | `appReady` only; the record is still asked through `window.tracker.call` and a failure still goes only to the error log. Q-G asks Jason. | Through `call()` a failed or warned pilot record would show a notice it does not show today; P313 keeps today's behaviour where an answer changes what a person sees. |
| **D-11 is conditional** | Section 9: fold the CSS overrides with Q-D | P6.17 is built only if Jason answers Q-D yes; it folds by proof (section 4, P6.17). | Q-D is his; the fold reverses P51 and P67's "style.css stays unedited". |
| **D-4's split of `spawnTracker`** | D-4: `spawnTracker` split into `framePayload`, `routeCommand`, `watchReply` | Not taken: P6.15 moves `spawnTracker` (main.js 454-619) byte for byte into `engine.js`. | A move is byte for byte (P313); splitting a 166-line function changes its code, so it is phase 7's or later, with its own tests. |
| **D-3 (e) and (f), D-12's virtualizers** | D-3: the list cells twice; the nothing-asked pre-check; D-12: one `virtualSpan()` | Not taken. | Section 9 names four results; (f) is deliberate (decision 142, an instant answer); the two virtual lists are deliberate (P279). |
| **No test file split** | E-3 for big test files | `tests/test_shell.py` (8,284 lines) is not split here; a new test file holds new tests only, so `KIT_TESTS_SPLIT` (test_pilot 490) is unchanged. | Section 9's paragraph does not ask for it, and every job of this phase edits it; splitting it under the moves would double the conflicts. Section 7 carries it. |

### 2.2 Carried-forward items (`ORCH/carry-forward.md` and the brief)

*From J3 (phase 6's own list):*
- tour.js's typed `Step ${index + 1} of ${all.length}` (tour.js 58), and the pilot's scripts outside the typed-words
  guard: taken in P6.4 (R6.4.1, R6.4.2).
- The guards that read `app.js` alone or a typed list: `no_status_chip`, `types_no_colour`, `scan_buttons_label`, the
  `engagements_page` words, the `"Escape"` count, and the test_api pins (now in `test_api_*` family files): taken
  in P6.2 and P6.3, by rule (every site that names a split script), not by list.
- `roll-household`, the one command the commands guard never reads: P6.4 (R6.4.4).
- The structural error-text pass: P6.4 (R6.4.3).
- `stripped_js`'s `//` assumption: P6.1 (R6.1.2).
- One rule for the no-typed-vocabulary guard: P6.4 (R6.4.5).

*From J5:* `fromMainWindow`'s comment and `NOT_FROM_THE_WINDOW` typed in main.js: P6.15 (R6.15.7, R6.15.8).

*From P2.3:* the stub held to `replies.py`: P6.4 (R6.4.6). `shellFailure`'s `...extra` (`progress`, `killed`) at the
envelope's top level: P6.15 (R6.15.9).

*From phase 5:*
- Seven curated notes that say reads "wait for P5.16" (screen_words's node; the test-file nodes of
  request_edit/household_edit, creation, firm_view, run_log, status_page, pass_order): P6.18 (R6.18.1).
- Prose. The runner node's bare `run_log` and status-page names are in `docs/repo-map.curated.json`, which P6.18
  edits anyway: taken (R6.18.2). `scanner.py` 952, `copies.py` 67 and the store's `forget` docstring: no phase 6 job
  edits those files, so section 7 carries them to phase 7. `screen_words.py`'s item is at 1069, not 1066:
  `CLIENT_FOLDER_TAKEN` types the misfits heading's text ("listed under Folders the App Leaves Alone") inside a sentence
  a person reads. P6.18 edits that file's comments (R6.18.5), but this is a word on screen, not prose, and filling it
  from `status_page.STATUS_MISFITS_HEADING` is a change to a reply's words. No phase 6 job makes such a change, so it
  goes to phase 7 too.
- P4.13's guard walks `tracker`, `tools` and `tests`, not `pilot/` or `api_entry.py`: P6.18 (R6.18.3).

*Older items this phase reaches:*
- "Any phase that moves a module": `patch_sites`' written limits and `monkeypatch.setitem`. Not reached: no code
  leaves a Python module in this phase (P6.5 and P6.6 add fields; P6.6 makes `firm_pages._taxpayer` public, with a `chars` keyword; section 3).
- "Any phase that adds or moves module state" (the register, `tracker/resident.py`): not reached; no Python module
  gains or moves module state.
- J6's notes (a mypy upgrade's rule; `platform = "linux"`; the pip cache key; "1 files"): not reached; no job touches
  the type checker.

## 3. Rules every job follows

**The gate.** This phase does not reach the sorting engine: no job changes code in the router, the filer and its
family, `content_check`, `ocr`, the scanner or the manifest's rules, so no job runs the whole suite (CLAUDE.md, "Test
minimally"). Each job runs its named tests, each file as its own process, under PY311 and PY314, then:
1. Dead code is deleted in the changed files first: unused imports and locals, commented-out code, a top-level name
   nothing uses (in a script: a function or `const` no script calls or reads, by `grep -w` over `app/`).
2. The job's named test files.
3. `python -m ruff check .`
4. `python tools/repo_map.py update`, then `check` - in every commit that changes code (P5.15's F1.1: each commit
   carries its own refresh).
5. `python tools/typecheck.py check`
6. `python tools/patch_sites.py check`
7. `node --check` on every script the job creates or edits (the suite's `test_build` does it too).
8. `python -m pytest --collect-only -q` before and after, compared: the same ids, apart from the additions and
   removals the job names.

No job touches a catalog, the matcher or a typed case, so `tools/vocab_report.py check` is in no job's gate.

**What the base already fails** (`ORCH/baseline/README.md`): on PY314,
`tests/test_api.py::test_importing_the_api_opens_no_file_but_the_programs_own`. A test on that list passes a job's
gate if it fails the same way at the job's base. Each job's before.txt records its named tests at its own base on
both interpreters.

**Re-measure.** Every line number here is at `9df1724`. Each job measures its anchors again on its own base, by the
name the anchor gives. A range is anchored on its first and last definitions; the comment block directly above a
moved definition and a section header the job's table says moves always move with it. If a named thing is not where
the range says, or a range holds a top-level name its table does not give, stop and ask.

**The renderer's readers** (the test files that read `app/renderer` or lift its functions, measured at `9df1724`):
`test_api`, `test_api_editor`, `test_api_firm`, `test_api_household`, `test_api_reminder`, `test_api_returns`,
`test_api_review`, `test_api_root`, `test_build`, `test_layers`, `test_pilot`, `test_renderer_seams`, `test_replies`,
`test_row_columns`, `test_shell`, `test_single_source`, `test_tour` (and `test_pilot_ui` for the stylesheets). **The
main process's readers:** `test_shell_menu`, `test_single_source`, `test_shell`, `test_build`, `test_replies`,
`test_pilot`, `test_pilot_installer`, `test_scheduling`, `test_layers`, `test_api_firm`, `test_api_review` (the last
two through `run_menu`). A job that moves renderer code runs every renderer reader; one that moves main-process code
runs every main-process reader. They read the text that moves, so they are the "importers" of Jason's rule. Re-measure
with `grep -lE "node_harness|app/renderer|RENDERER|main\.js|run_menu" tests/test_*.py`.

**The API's test files** (for a job that changes what `tracker/api.py` sends, measured with `repo_map.py show
tracker/api.py`): its eight owner files `test_api`, `test_api_editor`, `test_api_firm`, `test_api_household`,
`test_api_reminder`, `test_api_returns`, `test_api_review` and `test_api_root`, and the test files of the two modules
that import it, `test_api_entry` (`api_entry.py`, at call time) and `test_resident` (`tracker/resident.py`).

**A job that edits a helper module** (`tests/node_harness.py` is imported by seventeen test files; `tests/css_rules.py`
by `test_pilot_ui` and `test_shell`) runs every test file that imports it - with phase 5's one narrowing (section 3 of
SPEC-architecture-p5): an edit confined to one function's body runs the files that call that function.

**A move is a move (the scripts).**
- Code moves byte for byte, with its comments and words, in the order it had. The only exceptions are the edits a
  requirement names. A function that moves keeps its name; a top-level name keeps its spelling.
- A new renderer script starts with a comment block in its neighbours' form (`sheet.js` 1-31): what it holds and the
  decision rows behind each part (from the moved code's own comments), where it came from (D-1 or D-7, this SPEC's
  job, its decision row), that it is a classic script sharing the page's one scope, which scripts it loads between
  and why, and that phase 7 gives its state an owner. A new main-process module starts the same way, and says what it
  `require`s and what it exports.
- The script the code left loses the comment lines that described the moved code and gains one line naming the new
  script. `shell.js`'s interface header (15-37) is kept true as code leaves `app.js` and `shell.js`.
- **Strict mode:** a script carved out of `app.js` and a module carved out of `main.js` carry no `"use strict"`;
  `firm-loader.js` carries it (section 2.1).
- **Declarations only before `app.js`:** a script carved out of `app.js` holds only `function`, `async function`,
  `class`, `let` and `const` declarations at its top level; an initializer reads no other script's binding as the page
  loads (a literal, `new Map()`, `new Set()`, an arrow function, or an object of arrow functions such as `DIALOGS`).
  P6.1's load test proves it on every commit.
- **Where a script loads** (`index.html` 562-571): the scripts carved out of `app.js` load after the two vendor
  scripts and before `app.js`, in the order section 4 gives; `firm-loader.js` loads after `pages.js` and before
  `sheet.js` and `shell.js`; nothing else moves. `test_the_loading_order_is_the_specs_and_the_csp_is_unchanged`
  (test_shell 356) names each new script in its place (a file-named claim, P6.1's `FILE_NAMED`).
- **The main process:** a module sits directly in `app/` (the gate's `app/*.js` glob, `test_build` 35; and `__dirname`
  is the same folder), is `require`d by a plain relative string (`require("./engine")`, which `APP_NETWORK_CALLS`
  allows, test_layers 943-950), never `require`s `main.js`, and is required after main.js's `app.setPath("userData",
  ...)` (30). `main.js` takes the names its existing call sites use by destructuring the module's exports, so those
  call sites stay byte for byte. The hand-over functions several modules export (`learn`, `useWindow`) it calls through
  the module object, named once: `shellWords`, `logs`, `lastPass`, `opener`, `menu` and `engine` (none is a binding of
  `main.js` at `9df1724`; `engine`, 692, is a `let` that P6.15 moves into the module, so the name is free in
  `main.js` from that job on). A module's state is its own: another file changes it only through a function the
  module exports.
- **A name a module reads but does not own** is handed over in one of two named ways, and no other: a constant
  `main.js` also keeps is declared again in the module from its source (`const PKG = require("./package.json");`,
  `const PRODUCT_NAME = PKG.productName;`); a binding that `main.js` keeps and changes (`mainWindow`, 1077, assigned
  at 1267 and nulled at 1269) is read through a getter `main.js` hands over once (`useWindow`), and each moved body
  that read the bare name gains one line before the read, `const mainWindow = windowNow();`, so the reading line
  itself is unchanged. Each such line is named in its job's requirements and is a "new line" of section 4.1's proof.

**The seam table and the writes** (`tests/test_renderer_seams.py`).
- `SEAMS` (226-389) is re-derived in every job that moves renderer code: each pair a move creates gets a line saying
  why and the names, from `seams()`; a reason line already there moves with its names. A pair no script uses any more
  is taken off. No name is added to a pair that existed unless a move put it there; the job's after.txt shows the
  table's diff against `seams()` at its base, mapped by owner.
- `WRITES` (391-397) holds five rows at `9df1724`. A job may add only the rows its section names (each is a write the
  moved code already made, now across a script boundary); a write it finds that its section does not name is a stop
  and ask. A row's comment says what is written and "phase 7's owner object takes it (D-2)".
- The double (`pilot/harness/app-stub.js`) keeps defining every name the scripts loaded beside it use of the scripts
  it stands in for (test_renderer_seams 499); P6.7 makes `serve.mjs` stand it in for `app.js`'s whole family.

**The map, the docs and the decision rows:**
- `python tools/repo_map.py update` in the same commit as the code, after any edit to `docs/repo-map.curated.json`.
- A new script gets a curated node in the commit that creates it: a role, and notes that carry the reasoning, taken
  from the curated note of the script its code left (`app/renderer/app.js`'s note is about 8,000 words; each move job
  moves the paragraphs about the moved code to the new node and leaves one sentence pointing there). A new test file
  gets a node in `tests/store_helpers.py`'s form.
- **Curated edges move with their code.** Nothing checks a curated edge against the code, so one left on the file the
  code left goes stale silently. At `9df1724` the curated edges from the split scripts are: `app/main.js --spawns-->`
  `tracker/api.py`, `tracker/resident.py` and `api_entry.py` (P6.15 moves all three to `app/engine.js`);
  `app/main.js --writes--> artifact:tracker-errors.log` (P6.13 moves it to `app/logs.js`); and
  `app/renderer/app.js --calls--> app/preload.js` (P6.7 adds `app/renderer/api-client.js --calls--> app/preload.js` for
  the one `call()`, and `app.js` keeps its edge, since it still calls `window.tracker` itself: 2023, 2103, 2127, 2143,
  2306, 2307, 4178). `app/renderer/index.html --loads--> app/renderer/app.js` and `Start App.bat --launches-->
  app/main.js` stay true. Each move job re-reads the curated edges of the file it splits (`python -c` over
  `docs/repo-map.curated.json`'s `edges`) and names in after.txt every edge it moved, added or kept, and why.
- `docs/architecture.md` names no renderer script by file; no job edits it, except P6.18 if a sentence there became
  false (measure).
- **Decision rows, in landing order:** P352 (P6.1), P353 (P6.4), P354 (P6.5), P355 (P6.6), P356 (P6.7), P357 (P6.8),
  P358 (P6.9), P359 (P6.10), P360 (P6.11), P361 (P6.12), P362 (P6.13), P363 (P6.14), P364 (P6.15), P365 (P6.16),
  P366 (P6.17, only if built). P6.2, P6.3 and P6.18 record no rule and add none. A job that lands out of order takes
  the next free number and says so.

**Golden.** `tests/golden/` changes only in P6.5 and P6.6, and there only by the fields each names, re-recorded with
`pytest tests/test_golden.py --record-golden` in the commit that adds them, with the reply contract updated in the
same commit: `tracker/replies.py`'s types where the field is typed (P6.5's two top-level `state` fields; P6.6's rows
are `list[dict]`, R6.6.6) and `tests/test_replies.py` run, and changed where it names a reply's keys. Every other job's accept-when includes "`pytest
tests/test_golden.py` passes and `git diff --stat <job base> -- tests/golden` is empty".

**Behaviour.** No job changes what a person sees, a reply's words, a file a pass writes, or the record. P6.5 and P6.6
move four derivations from the page to the engine with the same results: P6.5 holds each new field to the page's
retired rule, and keeps that rule for the Hand Over list in the one window where the two would part (R6.5.5); P6.6 holds the taxpayer the page now draws to the expression it drew before, on the page's own
inputs, in every window where the list and the firm reply are from different moments; P6.4 moves the tour's count words to `pilot-content.js`, byte for byte as shown.
`SCHEMA_VERSION` and `ADMISSION_VERSION` do not change; a job that finds one must stops and asks.

**Types.** `typecheck.py check` fails when a file gains an error; P6.5 edits `api`, `firm_view` and `replies`, and
P6.6 `api`, `firm_pages` and `replies`, which must not gain one (`firm_pages` keeps 6 or fewer). A fix is P3.1's
style: an annotation or a `cast`, never a check or a branch.

**The layer table, `COMPOSERS` and the admission pin.** Not reached: no Python module is created, changes layer,
gains an import or calls `ledger.new(`. In particular `firm_view` does not import `firm_pages`: P278's pin that nothing
but the API reaches `firm_pages`
(`test_firm_pages_joins_layer_0_and_reaches_only_the_standard_library_and_the_low_modules`, test_layers 1298-1306)
holds as it stands, since `api`, which already imports `firm_pages`, is the one new reader of `firm_pages.taxpayer`
(P6.6). `ADMISSION_PIN[6]` is unchanged; P6.5 and P6.6 run `test_admission` to show it.

**Windows and the office.** The `windows` label is for a job that touches the held engagement lock, the atomic
replace, path handling or a Windows-only test: P6.13 (`open-path.js`'s `lstat` check of every path the app opens)
and P6.15 (`engine.js`: the API executable's path, the spawn with `windowsHide`, the kill at the time limit). Every job
that changes what the installed app loads (a new renderer script in `index.html`, a new main-process module, an
engine reply the page reads, the stylesheets) names its `pilot\wintest\run_checks.ps1 -Tests` list and the screens of
its hands-on check, which is "the same as before". The office checks the stack once (section 6).

**The Mac.** Only P6.13-P6.15 reach code with a Mac branch (`SETTINGS_DIR`, the floor, `NOT_SET_UP_MAC`, the menu's
`shown()` and `MAC_ONLY`, Protected View's sentence). Section 6 says what the next scheduled Mac check runs.

**Safety:** made-up data only (decision 185); commit signing on; no model identifier in anything committed;
`STANDING_RULES` untouched; no generative AI reads a client document; nothing is sent (no network module, no new IPC
channel, no new member on the preload's bridge).

## 4. The jobs, in landing order

| Job | Title | Cost | Tier | Depends on | Windows |
|---|---|---|---|---|---|
| P6.1 | The shell's scripts read by claim: the readers, the named-script guard, the load test | M | Opus | — | no |
| P6.2 | `app.js`'s readers read by claim | L | Sonnet | P6.1 | no |
| P6.3 | `shell.js`'s and `main.js`'s readers read by claim | M | Sonnet | P6.2 | no |
| P6.4 | J3's open guards; the tour's count words; the stub held to `replies.py` | M | Opus | P6.3 | no |
| P6.5 | The engine sends `hand_over_targets`, `tally` and `groups` (D-3 a, b, d) | M | Opus | P6.4 | no |
| P6.6 | The engine sends each return's `taxpayer` (D-3 c) | M | Opus | P6.5 | no |
| P6.7 | `api-client.js`, `notices.js`, `dialogs.js`; the double stands in for the family (D-1) | M | Opus | P6.6 | no |
| P6.8 | `reminder-card.js` and `review-rows.js` (D-1) | M | Opus | P6.7 | no |
| P6.9 | `household.js` (D-1) | M | Opus | P6.8 | no |
| P6.10 | `editor.js`; the paste parser's test (D-1, D-12) | M | Opus | P6.9 | no |
| P6.11 | `schedule.js` and `pass.js` (D-1) | S | Opus | P6.10 | no |
| P6.12 | `firm-loader.js` out of `shell.js` (D-7) | M | Opus | P6.11 | no |
| P6.13 | `shell-words.js`, `logs.js`, `last-pass-watch.js`, `open-path.js` out of `main.js` (D-4) | M | Opus | P6.12 | **yes** |
| P6.14 | `menu.js` out of `main.js` (D-4) | S | Opus | P6.13 | no |
| P6.15 | `engine.js` out of `main.js`; the sender check's words; the shell's envelope typed (D-4) | M | Opus | P6.14 | **yes** |
| P6.16 | `appReady` for `pilot.js` (D-6) | S | Opus | P6.15 | no |
| P6.17 | The overriding stylesheet rules in one home (D-11; only if Jason answers Q-D yes) | M | Opus | P6.16 | no |
| P6.18 | Phase 5's loose ends; the phase's close | S | Sonnet | P6.17 (or P6.16) | no |

**Tiers** (PROMPT-refactor section 1.3):
- Opus: every job that moves code out of `app.js`, `main.js` or `shell.js` (rule (a), and the brief: P6.7-P6.15);
  P6.1 and P6.4, by rule (c): each builds a guard that derives facts by parsing source (a test file's literals; a
  script's top level; the typed-words and commands readers); P6.5 and P6.6, by rule (e): each changes what the engine
  sends and what the page reads, and a slip shows a person a different count, picker or name; P6.16 by rule (e): it
  changes when the pilot's record is first asked; P6.17 by rule (e): a fold that is wrong changes how the page looks.
- Sonnet: P6.2 and P6.3 (a retarget by rule, test-only, every site found by P6.1's guard), P6.18 (notes, prose, one
  walk widened).

Every job edits `tests/test_renderer_seams.py`, `tests/test_shell.py`, `tests/test_single_source.py` or the map, so
they are built in this order, one session each.

---

### 4.0 Where `app.js`'s code goes (P6.7-P6.11)

Measured at `9df1724` by a scan of `app.js`'s top-level declarations (`tests/test_renderer_seams.py`'s
`DECLARATION`), cut on the section headers the file already has. Each job re-measures on its base and moves exactly
its rows; a top-level name in a range that this table does not account for is a stop and ask.

| New script | Job | Ranges of `app.js` (first to last definition, with the comment block above) | Lines |
|---|---|---|---|
| `api-client.js` | P6.7 | 195-231 (`TrackerError`, `call`, `takeReply`); 473 (`withEng`); 1248-1302 (`writesInFlight`, `writeKey`, `writeBusy`, `writeStart`, `writeDone`, `writeRow`, `rethrow`, `sayNotes`) | ~95 |
| `notices.js` | P6.7 | 232-449 (`notices` to `outlineRefused`); 1376-1389 (`renderMisfits`, one keyed notice) | ~232 |
| `dialogs.js` | P6.7 | 3897-4107 (`DIALOGS`, `dialogStack`, `dialogOpener`, `dialogSnapshot`, `dialogKept`, `snapshotOf` to `trapTab`, `openSafeguards`, `openAbout`, `openMisfits`) | ~211 |
| `reminder-card.js` | P6.8 | 510-831 (the week's reminder: `reminderStage`, `reminderFor`, `reminderCard`, `reminderCardFor`, `stageOf` to `approveReminder`) | ~322 |
| `review-rows.js` | P6.8 | 832-1236 (`keywordBox` to `openReviewCopy`, with `BELONGS_TO`, `handingOver`); then 1237-1247 (the way back's header) placed before 1304-1375 (`withdrawAnswer`, `dismissParked`, `unfiling`, `openUnfile`, `confirmUnfile`, `unfileDocument`) | ~486 |
| `household.js` | P6.9 | 1391-1764 (the roll dialog, `acceptFolderName`, `markShared`, the household editor to `saveHousehold`); 2619-2912 but line 2813 (`loadForms` to `labelPeopleBlock`); 3336-3434 (custom requests, `createEngagement`); and the head `let`s `addingTo` (8), `forms` (10), `templatesByForm` (11), `defaultYear` (13), `selectedForm` (15), `templates` (16), `customItems` (17) | ~775 |
| `editor.js` | P6.10 | 2913-3335 (the one row component and the editor's virtual window); 3435-3896 (`editorState` to `saveEditor`); the head `let` `editorRows` (18) and `editorPeople` (2813) | ~885 |
| `schedule.js` | P6.11 | 2155-2297 (`moveScheduleQuestion`, `repairSchedule`, `removeScheduleHere`, the Schedule dialog to `saveSchedule`) | ~143 |
| `pass.js` | P6.11 | 2317-2618 (`scanFailed` to `forgetSortAnswers`, with `scanning`, `sortAnswers`) | ~302 |
| **`app.js` keeps** | — | 1-194 less the head `let`s that move; 451-472 and 474-509 (`viewGeneration`, `select`, `renderFor`, `render`); 1765-2154 (the lock watch, `applyVocabulary`, `loadEngagements`, `renderMachineNotices`, `adoptList`, `showReturn`, `bootstrap`, `saveRoot`, `renderShortOfRoom`, `renderAfterInstall`, `noticeOf`); 2298-2316 (the after-install registration, a statement that runs at load); 4108-4285 (the wiring, `reviewPeople`, `startWhenLoaded`) | ~830 |

**The `let`s two scripts write stay where they are declared**, and each write from the other script is a `WRITES` row
its job adds (measured): `formsUnloaded`, `nameIsAuto` and `rollChoice` (declared in `app.js`, also written in
`household.js`: P6.9); `reminderStage`, `reminderFor`, `reminderCard` and `reminderCardFor` (declared in
`reminder-card.js`, written by `render` in `app.js`: P6.8); `handingOver` and `unfiling` (declared in `review-rows.js`,
written by `DIALOGS`' `closed` hooks: `("dialogs.js", "app.js", ...)` in P6.7, which P6.8 turns into
`("dialogs.js", "review-rows.js", ...)`). Nine rows in all; no other move of `app.js`'s code writes another script's
`let` (measured).

**Load order** after P6.11: the two vendor scripts, `api-client.js`, `notices.js`, `dialogs.js`, `reminder-card.js`,
`review-rows.js`, `household.js`, `editor.js`, `schedule.js`, `pass.js`, `app.js`, `tooltip.js`, `pages.js`,
`firm-loader.js` (P6.12), `sheet.js`, `shell.js`, `pilot-content.js`, `pilot.js`, `tour.js`.

### 4.1 Rules the script moves share (P6.7-P6.15)

These hold for every job that creates a script. Each job's own requirements add to them.

- **A new script's header comment holds no word of the API's vocabulary** (`Needs Review`, `Filed` and the like):
  the no-typed-vocabulary guard reads `APP_FAMILY` raw, comments included (R6.2.1), so such a word in a header fails
  it. Name the screen by what it does, not by its vocabulary label (orchestrator, review 4's note).

- **The proof that the move moved, both ways.** after.txt pastes `git diff -M --color-moved=plain --stat` and a check
  (a short `python` given in after.txt) that two sequences of lines are equal:
  - **what arrived:** the bodies of the new scripts, each less its header block and, for a main-process module, less
    its `require` and `module.exports` lines and the new lines its requirements name, joined in the order section 4.0
    or the job's table gives (per module, for a job that makes several, as P6.13 does);
  - **what left:** the lines the job removed from the source script, less the comment lines it names as describing the
    moved code (section 3), joined range by range in the same order as "what arrived", so a move of several ranges
    compares each range with the one it became; the pointer lines it adds (one per new script, and any its
    requirements name, such as P6.15's above `LAUNCH_DONE_CHANNEL`) are additions and are in neither sequence.

  The difference of the two (`difflib.unified_diff`) is pasted and is empty. So nothing new arrives in a
  new script, and nothing removed is lost: a function dropped during an 885-line move shows as a removed line no new
  script holds. A line edited inside a moved body is one a requirement names (listed with its R-number), or it is a
  finding.
  - **The source's own edits are listed, not proved.** A line the job edits where it stays in the source (P6.13's
    three `errorLog` reads that become `named()`) is a removal and an addition in place, not a move: it is
    left out of "what left", and after.txt lists each such line, old and new, with its R-number. A line the job adds
    to the source (the calls in `learn()` to each module's hand-out and the `const learned` line, R6.13.2, R6.14.2,
    R6.15.2; the module requires; the `useWindow` calls) is listed the same way; the `learn()` lines a hand-out holds
    are moved lines, in "what left" and in that hand-out, and 394 (`learnMenu(...)` becoming `menu.learn(...)`,
    R6.14.2) is an edit in place. So the difference is empty, and every line
    that is not a move is on one of two named lists.
- **The pins.** After P6.3 no test names a split script by file except `FILE_NAMED`'s entries (P6.1), so a move's
  pin-move list is: `FILE_NAMED`'s entries for the script the code left (each re-read: does its claim still hold of
  that script, or does it now belong to the new one), the load-order test (test_shell 356), `SEAMS` and `WRITES`,
  the double (P6.7), and the map. The job greps `tests/` for each moved top-level name and lists the hits in
  before.txt; a hit that reads the name through a file is a stop and ask (P6.1's guard should have caught it).
  A claim R6.2.1 reads over `APP_FAMILY` (its family list) needs no re-read and no pin move: `APP_FAMILY` takes in
  each script P6.7-P6.11 carve out as soon as `index.html` lists it before `app.js`, so the claim reads the moved code
  where it lands. A `FILE_NAMED` claim on `app.js` that, on re-reading, turns out to be a count or an absence about
  `app.js`'s code rather than about the file is not kept there: it moves to `APP_FAMILY` by R6.2.1's rule, in the
  move job's own commit, and after.txt says so (review 3's S24).
- **The guards bite on the new script.** For each guard named in the job (the sink ban, the commands guard, the
  typed-words guard, the no-typed-vocabulary guard, the `keydown` count, the `startsWith(` scan, the seam table),
  the job plants the forbidden thing in the new script on a scratch copy, runs the guard, sees it fail, and reverts;
  after.txt lists each with its failing line. P6.7-P6.11 also plant each claim of R6.2.1's family list in one of the
  job's new scripts (a second `"Escape"`, a `.message` read, a fourth `call(["list"])`, an `e.target === $("x")`, a
  `words.loading`, a third `toastWord("x")` key, a `looks like` in a comment), and each must fail; after.txt lists
  them the same way.
- **The harness, once.** Each job runs `node pilot/harness/shoot.mjs <ORCH>/jobs/<job>/shots` with `HARNESS_PYTHON`
  set to PY314's interpreter, in the cloud (Playwright's Chromium is there), before and after; it must report no page
  error and draw every scenario. The shots are not committed. If the harness cannot start in the session, the job says
  so and the office's hands-on check carries it.
- **The accept-when every move job shares:**
  - The gate passes on both interpreters, with the base's failures and skips and no others.
  - `python -m pytest --collect-only -q` lists the same ids before and after, apart from the tests the job names.
  - The load test (R6.1.4) passes; `node --check` passes on every script the job touched.
  - `tests/golden/` is unchanged; `patch_sites report` is unchanged but for line numbers.
  - The source script is shorter by the moved lines, give or take the lines on the source's own list of edits
    (above) and the pointer lines (one per new script, and any its requirements name); after.txt gives both counts
    and the arithmetic.

---

### P6.1 The shell's scripts read by claim: the readers, the named-script guard, the load test

- **Cost:** M.
- **Tier:** Opus, rule (c): it builds a guard over the tests' own text (an AST walk) and a test that runs every
  script of the page in one scope.
- **Findings:** D-5, D-1's "do D-5 first", D-4's text slices; J3's carried `stripped_js` item.
- **Depends on:** —.

**What is measured** (an AST walk of `tests/*.py` for a string literal that is, or ends with `/` and, a script name):
439 literals name `app.js`, `shell.js` or `main.js`, in 238 functions of 22 files - `test_shell` 143,
`test_single_source` 148, `test_replies` 46, `test_renderer_seams` 31, `node_harness` 14, `test_shell_menu` 9, the
`test_api_*` family 30, `test_row_columns` 5, `test_layers` 3, `test_pilot` 4, `test_build` 2, `test_repo_map` 2,
`test_pilot_installer` 1, `test_scheduling` 1. By the call they sit in: `read` 113, a tuple 101 (test_replies' tables,
`SEAMS`' keys), `js_function` 88, a path built with `/` 39, `run_shell` 35, `stripped_js` 32, the rest 31. Beside them,
inline cuts by a function's first line (`js.split("function X(...) {", 1)[1]...`, `js[js.index("function X("):...]`)
and two node probes that read `app.js` by path and `indexOf` a function (`_BUTTON_PROBE`, test_single_source 3128;
`_LOCK_HARNESS`, 3519).

**Requirements:**

- **R6.1.1, the readers** (`tests/node_harness.py`):
  - `MAIN_SCRIPTS`: `"main.js"` and every `app/*.js` it `require`s by a `"./name"` string, transitively, in the order
    first required; `main_text()` joins them; `main_function(name)` cuts one function from them exactly as
    `js_function` does (from `function name(` or `async function name(` to the first `"\n}\n"`), asserting exactly
    one definition across them. At `9df1724` `MAIN_SCRIPTS == ("main.js",)`.
  - `js_function(name, file=None)`: without `file` it searches `APP_SCRIPTS` (the pilot's three keep their functions
    inside namespaces, and their own `show`, `fill` and `render` are why a search of every script needs the file
    today). The exactly-once assert stays. The docstring says why.
  - `run_shell`, `run_pages` and `lift` find each function they lift by name through `js_function(name)`; `run_shell`
    keeps accepting `source` until P6.3 removes it.
  - `APP_FAMILY`: `app.js` and every script `index.html` lists between the vendor scripts and it (at `9df1724`:
    `("app.js",)`), derived from `RENDERER_SCRIPTS`, never typed, in load order (so `app.js` is its last script).
    Its `#:` comment says it is what a claim about `app.js`'s code as against the other app scripts reads (R6.2.1),
    so such a claim follows the code P6.7-P6.11 carve out.
  - `js_block(head, scripts=APP_SCRIPTS)`: a bounded read for a claim about a table or a block rather than a function.
    It finds `head` (a declaration's first line, such as `const MENU_ANSWERS = {`) exactly once across `scripts`
    (assert; `MAIN_SCRIPTS` for the main process's `const BAR = [`, `const POPUPS = new Map([`, each script read from
    its own folder), and reads
    from it to the block's closing line, that line included: the first later line that starts at the head's own
    indentation with `}` or `]` (`};`, `]);`, `});` and `}` alike). The inline forms it replaces include test_shell
    1025-1027 and 2026-2028 (`text[text.index(head):]` then `table[:table.index("\n};\n")]`) and the listener slice of
    test_shell 825 (`every[every.index('document.addEventListener("keydown", (e) => {'):]`).
  - `lift_line(head, source=None)`: without `source` it finds `head` exactly once across `APP_SCRIPTS` (assert), as
    `js_function` does without `file`; with one it reads that script, as today.
  - Each new name has a `#:` comment in its neighbours' form, and the module docstring gains a paragraph on reading by
    claim: a read is bounded (one function, one block, one line) or is the whole of a set of scripts, never a slice
    from a point to the end of a joined text, whose content moves as scripts are carved out (review 1's S13).
- **R6.1.2, one reader of code.** `js_code` (test_renderer_seams 53-153) moves byte for byte to `tests/node_harness.py`
  with its `_BEFORE_A_REGEX`, and test_renderer_seams imports it. `stripped_js` finds comments with the same scanner, so
  a `//` or `/*` inside a string or a template is not a comment, and removes them as it does today (a block comment to
  nothing, a line comment to the end of its line). before.txt and after.txt hold `stripped_js` of every renderer
  script and `app/main.js`: identical, or each difference is a string that held `//` (list them).
- **R6.1.3, the named-script guard.** New in `tests/test_renderer_seams.py`:
  `test_no_test_reads_a_script_this_phase_splits_by_its_file_name`. It walks every `tests/*.py` with `ast` and fails on
  a string literal whose value is the name of a **split script**, or ends with `/` and one, unless the place is listed
  in `FILE_NAMED`. A split script is every name in `RENDERER_SCRIPTS + MAIN_SCRIPTS + PLANNED` but `tooltip.js`,
  `pages.js`, `sheet.js`, `pilot-content.js`, `pilot.js` and `tour.js`, which this phase does not split, less
  `NOT_YET = ("app.js", "shell.js", "main.js")`, which P6.2 and P6.3 empty and delete.
  - `PLANNED` is a typed tuple of the sixteen names this SPEC creates (`api-client.js`, `notices.js`, `dialogs.js`,
    `reminder-card.js`, `review-rows.js`, `household.js`, `editor.js`, `schedule.js`, `pass.js`, `firm-loader.js`,
    `shell-words.js`, `logs.js`, `last-pass-watch.js`, `open-path.js`, `menu.js`, `engine.js`), so a test that names
    a script before it exists fails too, and the guard has something to check from P6.1 on (review 1's S5: without it
    the split set is empty at P6.1). Each name is then also in `RENDERER_SCRIPTS` or `MAIN_SCRIPTS` from the job that
    creates it; P6.18 deletes `PLANNED` once every name is (R6.18.4). Measured at `9df1724`: no test names any of the
    sixteen.
  - A place is `(file, function)`: `function` is `None` for module level and `"*"` for the whole file (used only for
    `tests/test_repo_map.py`). `FILE_NAMED: dict[tuple[str, str | None], str]` maps each place a test names a split
    script on purpose to why: the claim is about that file as a file. At P6.1 it holds the definitions in
    `tests/node_harness.py` (`MAIN_SCRIPTS`' start, `APP_FAMILY`'s anchor, `run_menu`'s entry point),
    `("test_repo_map.py", "*")` (made-up repositories' paths) and `test_renderer_seams.py`'s own tables (`SEAMS`,
    `WRITES`, the double's test), each with its reason.
  - **An exemption never outlives its claim** (review 2's S19). The guard also fails on a `FILE_NAMED` place that
    holds no literal it would otherwise flag, counting `NOT_YET`'s names as flagged (so the `app.js` places listed at
    P6.1 hold while `app.js` is still in `NOT_YET`), the way test_replies' `MUST_NOT_FIND` fails on an anchor that "has
    rotted". A `"*"` place must hold at least one such literal somewhere in its file. So a place whose literals a later
    job removes (a table P6.2 converts to sides, a claim a move job re-reads) fails until that job takes it off the
    list, and a read added there later cannot hide behind it.
  - A test of the guard itself, on made-up text, shows a literal outside `FILE_NAMED` fails, one inside passes, a
    `"*"` place covers every function of its file, and a listed place that holds no such literal fails as rotted.
- **R6.1.4, the load test.** New in `tests/test_renderer_seams.py`:
  `test_every_script_the_page_loads_runs_in_order_in_one_scope`. Under `node`, one `vm` context, every `<script src>`
  of `index.html` (the vendor scripts too) is run in order, as the page's classic scripts share one global scope, with
  a permissive stand-in for `document`, `window`, `navigator`, `localStorage` and `window.tracker` (any property is a
  callable stand-in) and `document.readyState` `"loading"`, so `bootstrap` waits; it passes when no script throws while
  loading, and the probe exits when the last has run (the pilot's timers would hold node open). A second test, on two
  made-up scripts, shows a script that reads a later script's `let` at load, or names a later script's function at
  load, fails it. A third: every script in `APP_FAMILY` but `app.js` holds declarations only at its top level
  (`js_code`, then each top-level statement starts `function`, `async function`, `class`, `let` or `const`). Skipped
  with a stated reason when `node` is absent. (Measured: the ten scripts load in one context at `9df1724`.)
- **R6.1.5, the decision row P352.** "The tests read the shell's scripts by claim": a claim reads the function it is
  about (`js_function`, `main_function`) or the code as a whole (`renderer_text`, `main_text`), never a file, so a
  move cannot take code out from under a guard (D-5); a test that names a split script by file is listed in
  `FILE_NAMED` with why; a script carved out of `app.js` holds declarations only and loads before it.
- **R6.1.6, the map.** `tests/node_harness.py`'s and `tests/test_renderer_seams.py`'s curated notes say the new
  readers, the guard and the load test.

**Pin-move list:** `tests/test_renderer_seams.py`'s import of `js_code`; nothing else moves.

**Patch sites:** none (no Python code moves).

**Tests:** every importer of `tests/node_harness.py` (`test_api_editor`, `test_api_firm`, `test_api_household`,
`test_api_returns`, `test_api_review`, `test_build`, `test_layers`, `test_pilot`, `test_pilot_ui`,
`test_renderer_seams`, `test_replies`, `test_row_columns`, `test_shell`, `test_shell_menu`, `test_single_source`,
`test_suite_shape`, `test_tour`), `test_repo_map`, `test_tripwire`.

**Stop and ask:** a script that fails the load test at the base; a `stripped_js` difference that is not a string
holding `//`.

**Accept when:**
- The guard passes with `NOT_YET` holding three names; on a scratch copy it fails on a literal `"engine.js"` planted
  in a test function (a `PLANNED` name), and, with `NOT_YET` emptied, on a literal `"app.js"` planted in a test
  function outside `FILE_NAMED` (after.txt shows both failures); and, with a made-up place added to `FILE_NAMED` that
  names no split script, it fails as rotted.
- The load test passes, and fails when, on a scratch copy, `app.js`'s first wiring line is moved above the function
  it names into a new script listed before `app.js`.
- `js_function("show")` lifts `app.js`'s `show`; collect-only ids differ only by the new tests.
- **Windows:** no label (test-only). **Office `-Tests`:** none of its own.

---

### P6.2 `app.js`'s readers read by claim

- **Cost:** L: 272 literals, 97 in `test_shell` and 96 in `test_single_source`. It stays one job (review 1's note
  asked whether to split it): P5.16, also a Sonnet retarget by rule, moved 649 reads in one session. It lands as
  two commits, `test_shell.py` and `node_harness.py` first and then the rest, each with its gate, so each diff stays
  reviewable.
- **Tier:** Sonnet: a retarget by rule, test-only; every site is named by P6.1's guard once `app.js` leaves `NOT_YET`.
- **Findings:** D-5; J3's carried guards (`no_status_chip`, `types_no_colour`, `scan_buttons_label`, the
  `engagements_page` words, the `"Escape"` count, the test_api pins).
- **Depends on:** P6.1.

**Requirements:**

- **R6.2.1, `app.js` leaves `NOT_YET`,** and every site the guard then names is retargeted by these rules, in this
  order of preference:
  - a claim about one function's text reads `js_function(name)`; an inline cut by a first line (`split`, `index`)
    becomes `js_function(name)` holding the same claim;
  - every read is bounded (R6.1.1): a tail slice (`js[js.index("function X("):]`, `text[text.index(head):]`) is read
    as the function it meant (`js_function`), the block it meant (`js_block(head)`, the form of test_shell 1025 and
    2026) or the one declaration it meant (`lift_line(head)`), never as a slice of `renderer_text(...)` from a point to
    its end: in the joined text "from here to the end" changes as P6.7-P6.11 put scripts before `app.js`, so a
    negative claim on such a slice would pass silently (review 1's S13). A tail slice that meant "everything after"
    and is none of these is read as the whole text with no slice, or is a stop and ask. before.txt says per site which
    read it became;
  - **a claim about `app.js`'s code as against the other app scripts reads `APP_FAMILY`** (review 3's S24): a count
    whose number, an absence whose truth, or a set whose members would change if `tooltip.js`, `pages.js`, `sheet.js`
    or `shell.js` were read too reads `renderer_text(APP_FAMILY)`, or `stripped_js` over `APP_FAMILY`, in the form
    the claim had (raw where it read `read("app.js")`, stripped where it read `stripped_js("app.js")`). `APP_FAMILY` is
    P6.1's derived set (R6.1.1): it equals `("app.js",)` at P6.2, so each claim is the same claim then, and it takes
    in each script P6.7-P6.11 carve out as it lands, so the claim follows the code. Such a claim is **not** a
    `FILE_NAMED` claim, though its docstring says "app.js": filed there it would stop covering the code the moves
    carve out, and no net would see it (the rot rule passes while the place holds `"app.js"`, and an absence always
    "still holds of that script"). Measured at `9df1724` (an AST scan of every test function that reads `app.js`
    whole, for counts, absences, `re` scans, set equalities and derived texts, each run over `app.js` and over
    `APP_SCRIPTS`), these read `APP_FAMILY`:

    | Test | Claim on `app.js` | Over `APP_SCRIPTS` |
    |---|---|---|
    | test_single_source 3605-3612 `test_an_errors_own_message_is_read_only_where_failureSentence_logs_it` | no `.message` outside `failureSentence` (`outside = js.replace(inside, "")`) | fails: pages.js 1706 reads `one.err.message` |
    | test_single_source 3661 (3684) `test_switching_returns_is_one_state_call` | `js.count('call(["list"])') == 3` (the test's other reads of `js` go with it: `"refresh(" not in js`, the `bootstrap(` count, and `js.rstrip().endswith("startWhenLoaded(bootstrap);")`, which holds over `APP_FAMILY` because `app.js` is its last script by derivation) | 5: shell.js 272 and 1626 |
    | test_single_source 4330 (4342) `test_escape_and_an_overlay_click_reach_every_dialog_the_same_way` | `js.count('"Escape"') == 1` | 4: shell.js twice, tooltip.js once |
    | test_single_source 4345 (same test) | no `e.target === $("...")` | fails: shell.js 1731 |
    | test_shell 1742 `test_the_dialogs_help_lines_are_cut` (1750-1754) | the fourteen help keys and `words.note`, `words.loading`, `column.help`, `c.help` absent | fails: shell.js 1388 holds `words.loading` |
    | test_shell 1694 (1702-1703) `test_no_toast_types_a_sentence_and_the_words_it_asks_for_are_five_title_case_words_in_the_vocabulary` | the keys `toastWord` is given `== {"pick_request", "name_requests"}` | fails: shell.js 1798 adds `under_construction` |
    | test_single_source 1060 `test_the_renderer_types_no_vocabulary_of_its_own` (1093-1102) | `literal not in app_js`, read raw (comments included), beside a word-bounded scan of the other scripts stripped | fails: shell.js 91's comment holds `looks like` |

    The last one keeps its two-part shape: `app_js` becomes `renderer_text(APP_FAMILY)` (raw), `others` becomes
    `stripped_js` of each `APP_SCRIPTS` name outside `APP_FAMILY`, and `js` joins the two as today; so a script carved
    out of `app.js` keeps `app.js`'s stricter, comments-included rule, and the scripts outside the family keep theirs.
    The toast test's first loop (no literal in a `toast(` call, per file over four scripts) is an absence that holds
    over every app script, so it reads `APP_SCRIPTS` by the next rule.
  - **one positional claim reads the function it is about** (found with S24's scan, not in review 3's list):
    test_single_source 196 (`test_the_shell_runs_only_commands_the_api_has`, 187) takes `first_call`, the first
    `call(["name"]` in `app.js`, and holds it equal to `BOOTSTRAP_COMMAND`. Both sets are read in load order, and the
    carved-out scripts load before `app.js`, so over `APP_SCRIPTS` or `APP_FAMILY` household.js's
    `call(["templates"])` (2630) comes first from P6.9 on, and schedule.js's `call(["install-schedule"], {})` (2170)
    would too; over `app.js` alone it holds only because the call it finds (1981) stays. The claim is about the command the page sends for the list before the
    allowlist is learned, which is `loadEngagements`'s one call, so `first_call` is read from
    `js_function("loadEngagements")` with the same regex. At `9df1724` it finds `list` either way. This narrows what
    is read to the claim's subject, on purpose; before.txt records it as R6.4.5's narrowing is recorded.
  - a count, an absence or an "only once" claim that is about the app's scripts as a whole reads
    `renderer_text(APP_SCRIPTS)` (or `renderer_text()` where the pilot's scripts belong to the claim), or
    `stripped_js` over `APP_SCRIPTS`. **before.txt runs every count, absence and `re` scan this job retargets over
    both `APP_SCRIPTS` and `APP_FAMILY` at the base** and names each whose results differ; each such claim reads
    `APP_FAMILY` (the rule above), or is a stop and ask if neither set gives today's result. A claim the table above
    does not list and the run finds is added to it in after.txt;
  - a node probe that read `app.js` by path (`_BUTTON_PROBE`, `_LOCK_HARNESS`) is handed the lifted functions by
    Python (`js_function`, `lift_line`) instead of `indexOf`-ing a file;
  - `js_function(name, "app.js")` becomes `js_function(name)`; `run_shell(..., "app.js")` drops its `source`;
  - a claim that is about `app.js` as a file goes to `FILE_NAMED` with one line why. Expected, at least: the page's load
    order (`test_the_loading_order_is_the_specs_and_the_csp_is_unchanged`, test_shell 356); the one `keydown`
    listener is `app.js`'s (P76; `test_one_keydown_listener_owns_the_keyboard`, test_shell 814, says so in its
    docstring and holds it only indirectly, by reading `SHELL_SCRIPTS`; the job adds the one line
    `assert 'document.addEventListener("keydown", (e) => {' in read("app.js")` as that test's `FILE_NAMED` claim, the
    one assert this job adds, so P76's claim is said of `app.js` itself; the count across `APP_SCRIPTS` stays a
    claim by claim, and R6.3.3 retargets the `SHELL_SCRIPTS` loop by claim); `app.js` ends with `startWhenLoaded(bootstrap);`
    (`test_the_app_starts_only_after_every_script_has_loaded`, test_shell 3030); the `on-mac` class is toggled at
    `app.js`'s top, before `applyVocabulary` (test_shell 6863); the double's `EL_ATTRIBUTES` is `app.js`'s
    (test_renderer_seams 513). Each such claim is kept as narrow as its reason.
- **R6.2.2, the claims are the same claims.** No assert is loosened: a literal looked for in one file is looked for in
  at least that file's code; a count stays a count over a set that holds the old file (`APP_FAMILY` holds `app.js`,
  and `APP_SCRIPTS` holds both); no test is renamed or removed. The one narrowing is `first_call`, read from the
  function it is about (R6.2.1), named in before.txt.
- **R6.2.3, the J3 guards are named.** before.txt lists the carried guards by test name and how each now reads.
- **R6.2.4, test_replies' tables read by side** (moved here from P6.3 by review 2's S19: test_replies' `MUST_FIND` and
  `MUST_NOT_FIND`, 455-512, hold 21 module-level `"app.js"` literals that no rule of R6.2.1 fits, so P6.2 could not
  otherwise meet its accept-when). Each `_Script` gains its side, derived and never typed: `"main process"` when its
  name is in `MAIN_SCRIPTS`, else `"renderer"`. Every row of both tables records its side instead of its file - the
  `app.js`, `shell.js`, `pages.js` and `sheet.js` rows `"renderer"`, the `main.js` rows `"main process"` - so the
  tables change once, by one rule, rather than half now and half in P6.3; a row's side for `main.js` names no file,
  so the guard is satisfied either way. `test_each_pattern_still_catches_the_sites_it_was_written_for` (533) matches
  on the side, and `test_no_pattern_catches_a_failure_shaped_site_that_is_not_a_failure` (543) finds each anchor in
  its side's scripts, by script and line, and still fails on an anchor no script of its side holds ("has rotted").
  The claims are unchanged: before.txt and after.txt list, for every row, the scripts and lines it is caught on, and
  the two lists are equal. What still names `main.js` in test_replies (`_scripts()`'s read, `collected()`'s
  `script.name == "main.js"`, `_where`, the envelope test, `MAIN_JS`) is P6.3's (R6.3.2).

**Pin-move list:** every site the guard names with `NOT_YET` less `app.js` (measured at `9df1724`: 272 literals,
18 of them in `FILE_NAMED`'s files; P6.1's figures by file), test_replies 433-555 (R6.2.4).

**Patch sites:** none.

**Tests:** every test file the job edits, `test_renderer_seams`, `test_layers`, `test_single_source`, `test_repo_map`,
`test_tripwire`, `test_suite_shape` (if a helper changes).

**Stop and ask:** a claim that cannot be read by claim without loosening it; a site that is a file claim for a
reason the job cannot state in a line; a retargeted count, absence or scan that gives today's result over neither
`APP_SCRIPTS` nor `APP_FAMILY`.

**Accept when:**
- The guard passes with `NOT_YET == ("shell.js", "main.js")`.
- before.txt holds the run of every retargeted count, absence and `re` scan over both sets at the base (R6.2.1),
  and every claim whose results differ reads `APP_FAMILY`; `FILE_NAMED` holds no such claim.
- Planting the forbidden text in a scratch script listed before `app.js` in `index.html` fails each of these
  negative claims (after.txt names each and its failing line; reverted after): the sink ban, the commands guard, the
  no-typed-vocabulary guard (a `looks like` in a comment, which only the family's raw read sees), `no_status_chip`,
  `types_no_colour`, and R6.2.1's family list - the `"Escape"` count (a second `"Escape"`), `.message` outside
  `failureSentence`, the `call(["list"])` count (a fourth), the `e.target === $("x")` scan, the help words
  (`words.loading`) and the toast keys (a third `toastWord("x")`) - and three more negative claims of after.txt's
  choosing. A scratch script before `app.js` is in `APP_FAMILY`, so a claim on that list that does not fail is
  reading the wrong set.
- Collect-only ids are identical; `git diff --stat` touches `tests/` only.
- **Windows:** no label. **Office `-Tests`:** none of its own.

---

### P6.3 `shell.js`'s and `main.js`'s readers read by claim

- **Cost:** M.
- **Tier:** Sonnet (as P6.2).
- **Findings:** D-5; D-4's text slices (test_single_source 216, 231, 2577; test_shell_menu 34, 40, 88, 105).
- **Depends on:** P6.2.

**Requirements:**

- **R6.3.1, `shell.js` and `main.js` leave `NOT_YET`;** `NOT_YET` is deleted. Every site is retargeted by R6.2.1's
  rules, with `main_function` and `main_text()` for the main process: a split on a block's head (`const BAR = [`,
  `const POPUPS = new Map([`, `const DEFAULT_MENU_WORDS = {`, `const shellSays = {`) reads
  `js_block(head, MAIN_SCRIPTS)`; a slice from a function (`main_js[main_js.index("function runTracker"):]`) reads
  `main_function`. No read is a slice of `main_text()` from a point to its end (R6.2.1's bounded reads).
- **R6.3.2, test_replies' main-process reads by side.** The tables are sides since P6.2 (R6.2.4). What is left:
  `_scripts()` (434) reads every script of `MAIN_SCRIPTS` from `app/`, each by its own name, in place of
  `_read("main.js", stripped_js(MAIN_JS))`; `collected()` (441) passes `shell_failure` for a script whose side is
  `"main process"`; `_where` (515) reads each kind's own script from its side's folder; and
  `test_the_main_processs_own_envelope_has_the_envelope_and_failure_keys` (557) finds the one script of `MAIN_SCRIPTS`
  that defines `shellFailure` (asserting exactly one), so it holds wherever P6.13 puts it. `MAIN_JS` goes if nothing
  else reads it. The claims are unchanged.
- **R6.3.3, `SHELL_SCRIPTS` retires,** and is deleted from `tests/node_harness.py`. Its readers:
  - test_shell 734 (`assert set(SHELL_SCRIPTS) <= set(APP_SCRIPTS)`, "never fewer scripts than the guard read
    before"): dropped, since the guard reads `APP_SCRIPTS`, which holds every script `SHELL_SCRIPTS` named;
  - test_shell 822-823 (`'addEventListener("keydown"' not in read(name)` for each of `SHELL_SCRIPTS`): **retargeted by
    claim** (review 2's S17), with no file name:

    ```python
    for name in APP_SCRIPTS:
        if name not in APP_FAMILY:
            assert 'addEventListener("keydown"' not in read(name), name
    ```

    The loop forbids **any** keydown listener in those scripts, on an element as much as on the document, which the
    count below it (`document\.addEventListener\("keydown", ...` only) does not: `app.js` 3101 already has an element
    listener (`table.addEventListener("keydown", ...`), which the count never sees. It is not read over all of
    `APP_SCRIPTS`, because `app.js`, which holds the one listener, would fail it (review 1's S12). At P6.3 it reads
    exactly the four `SHELL_SCRIPTS`; from P6.12 it reads `firm-loader.js` too, so it widens; the editor's table
    listener moves with `editor.js` (P6.10) inside `APP_FAMILY`, so the claim holds through every move. The test's
    docstring says the scripts outside `app.js`'s family are the ones SPEC-shell added (P67), and from P6.12
    `firm-loader.js`, carved out of one of them, and that `app.js`'s family keeps the keyboard (P76, R6.2.1's `FILE_NAMED` line);
  - test_renderer_seams 408 and 411: `SHELL_SCRIPTS` leaves the tuple of parts and its subset line goes.

  The docstrings of those two tests drop the name. No assert is loosened: the loop reads the same four scripts at
  P6.3 and more from P6.12, and the line at 734 that goes held only that `SHELL_SCRIPTS` was inside `APP_SCRIPTS`.
- **R6.3.4, `run_shell`'s `source` is removed** once no caller passes it.
- **R6.3.5, file claims** go to `FILE_NAMED`, expected at least: `ipcMain.handle` is registered in `main.js` alone
  (test_shell_menu 716-742: the IPC registration stays in `main.js`, 5.4); `app.setAppUserModelId` is called in
  `main.js` before `app.whenReady()` (test_shell 3880, test_scheduling 700, test_pilot_installer 296, test_build 1353);
  `main.js` is the Electron entry (`package.json`'s `main`).
- **R6.3.6, the scan by path.** `test_the_app_never_works_out_whether_a_path_lies_under_another` (test_layers 1245)
  reads `MAIN_SCRIPTS`; `test_the_harness_is_never_loaded_by_the_app` (test_shell 832) reads `MAIN_SCRIPTS` and the
  preload.

**Pin-move list:** every site the guard names for `shell.js` and `main.js` (167 literals at `9df1724`, 15 of them in
`FILE_NAMED`'s files).

**Tests:** every test file the job edits, every importer of `tests/node_harness.py` (R6.3.3, R6.3.4 change it at module
level), `test_renderer_seams`, `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`.

**Accept when:** the guard passes with `NOT_YET` gone; ten negative claims over `main.js` and `shell.js` (named) fail on a
planted scratch module required from `main.js` or a scratch script listed in `index.html`, among them the keydown
loop of R6.3.3 on a scratch script listed after `app.js` holding `foo.addEventListener("keydown", ...)`; collect-only
ids identical.
- **Windows:** no label. **Office `-Tests`:** none of its own.

---

### P6.4 J3's open guards; the tour's count words; the stub held to `replies.py`

- **Cost:** M.
- **Tier:** Opus, rule (c): it changes how the typed-words, commands and no-typed-vocabulary guards read the scripts.
- **Findings:** D-5, D-8; the J3 and P2.3 carried items.
- **Depends on:** P6.3.

**Requirements:**

- **R6.4.1, the tour's count words.** `pilot-content.js`'s `tour` gains `"count": "Step {n} of {total}"`; `tour.js` 58
  fills it (`.replace("{n}", index + 1).replace("{total}", all.length)`, or the pilot's own fill if it has one), so the
  card says exactly what it says today. `test_the_tour_text_carries_no_placeholder_but_the_email` (test_tour 90) allows
  the count's two tokens there and nowhere else; a test lifts the count line and shows "Step 2 of 9".
- **R6.4.2, the pilot's scripts under the typed-words guard.** `test_the_apps_scripts_type_no_words_of_their_own`
  (test_shell 725) reads `pilot.js` and `tour.js` too; `pilot-content.js` stays out, the pilot's words' one home
  (test_pilot holds it). The logged-error pass of R3.4 also covers `window.tracker.logError(...)`: at `9df1724`
  `pilot.js`'s `` `pilot record: ${reply.error}` `` is a logged error, and after R6.4.1 nothing else is found.
- **R6.4.3, the error text by where it goes.** `typed_literals` (test_shell 677) passes a literal inside `new
  Error(...)` only when that error is thrown (`throw new Error(`), or handed straight to `failed(` or
  `failureSentence(` (which log its text and show the API's words), or inside a logging call (`console.*(`,
  `window.tracker.logError(`). `toast(new Error("Two words").message)` fails; a parametrized test shows each case. At
  `9df1724` the one `new Error(` not thrown is `toastWord`'s `failed(new Error(...))` (app.js 182), which passes.
- **R6.4.4, `roll-household` read.** The commands guard (`test_the_renderer_calls_only_commands_the_api_has_and_types_no_flag`, test_single_source 109-140) also reads the first element of
  every array literal whose second element is `vocab.engagement_flag` (`["roll-household", vocab.engagement_flag,
  ...]`, app.js 1477) and holds it to `api.COMMANDS`; its docstring loses the sentence that names the gap.
- **R6.4.5, one rule for the no-typed-vocabulary guard.** `test_the_renderer_types_no_vocabulary_of_its_own`
  (test_single_source 1060) reads every app script the same way: code only (`stripped_js`), a bare word as a whole
  word, a quoted word as quoted. `app.js`'s read with its comments and by substring goes; the docstring says why (a
  comment or a longer identifier puts no word on screen, and a rule tied to one file stops at the split). Measured at
  `9df1724`: the whole-word, code-only rule finds nothing in any app script.
- **R6.4.6, the stub held to the contract.** A test beside `test_the_harness_stub_replies_have_the_shape_of_the_engines`
  (test_shell 2528) holds every reply `_stub_replies` (test_shell 2442) gathers from `pilot/harness/stub.js` - `list`,
  `firm` and `firm-last` whole and paged, three `state`s - and the stub's `reminder` reply to `tracker/replies.py`'s `StateReply`, `ListReply`, `FirmReply`, `FirmLastReply` and `ReminderReply`:
  each required key present, no key the type lacks (`typing.get_type_hints`, `__required_keys__`,
  `__optional_keys__`). A difference at the base is fixed in the stub; one that means the type is wrong is a stop and
  ask. `replies.py`'s docstring sentence that the harness's stub is held to it becomes true; its curated note says
  where.
- **R6.4.7, the decision row P353.** The typed-words guard reads the pilot's scripts and judges error text by where it
  goes; the tour's count is the pilot's word; one rule for typed vocabulary; `roll-household` read; the stub held to
  `replies.py` (R3.4, D-8, P2.3). The row lists R6.4.5 as **a narrowing on purpose**: on `app.js` the
  no-typed-vocabulary guard goes from a substring search that read comments to a whole-word search of code only. A
  comment or a longer identifier puts no word on screen, and a rule tied to one file would stop covering the code
  that leaves it at the split, which is the silent loss this phase designs out.

**Pin-move list:** test_tour 90-107; test_shell 660-810; test_single_source 109-140 and 1060-1110; test_pilot's
`pilot-content.js` wording pins (measure).

**Tests:** `test_shell`, `test_single_source`, `test_tour`, `test_pilot`, `test_replies`, `test_renderer_seams`,
`test_layers`, `test_repo_map`, `test_tripwire`.

**Accept when:** the tour shows "Step 1 of N" as before (the lifted line under node); every guard named above fails on
its planted case; `grep -n "Step \${" app/renderer` is empty.
- **Windows:** no label. **Office `-Tests`:** `test_tour,test_pilot,test_shell`; hands-on: start the tour once and
  read its count line (Help > Tour).

---

### P6.5 The engine sends `hand_over_targets`, `tally` and `groups` (D-3 a, b, d)

- **Cost:** M.
- **Tier:** Opus, rule (e).
- **Findings:** D-3 (a), (b), (d); SPEC-architecture 5.1 (9).
- **Depends on:** P6.4.

**What is measured:**
- (a) `fedReturns()` (app.js 1047-1057; callers 1012, 1135, pages.js 2167) re-derives `api._fed_returns` (3575-3596),
  which `state` builds only lazily (`fed_once`, 2151) and never sends. JavaScript lists the household's active
  open-year returns other than the one shown, then every feed with a path; Python builds one dict of the same, then
  drops the shown return. They differ only if a feed's path is one of the household's own returns or the shown return.
- (b) `pagesTally` (pages.js 1595-1609) counts `state.items` by `group` and `state.index` rows whose `group` is
  `needs_you` or `set_aside`; `firm_view._firm_row` (380-391) counts the same with `item_group` and `file_group`.
  `shellCountsDiffer` (shell.js 879-885) compares the two.
- (d) `PAGES_GROUPS` (pages.js 57) types `firm_view.GROUPS` (220); read at pages.js 1432, 1473 and 1599, and copied into
  three test fakes (node_harness 218; test_single_source 4240, 4265).

**Requirements:**

- **R6.5.1, one count.** `firm_view.tally(items, placed, entries) -> dict[str, int]`: the counts by group, items by
  `item_group`, files by `file_group` when not `GROUP_RECEIVED`, in `GROUPS`' order. `_firm_row` calls it in place of
  its two loops (380-391), the comment kept.
- **R6.5.2, `state` sends them.** `api.state` adds `"tally": tally(items, placed, entries)` (the same `items`,
  `placed` and `entries` it already holds) and `"hand_over_targets": [{"path": str(path), "label": label} for path,
  label in fed.items()]`, where `fed = _fed_returns(engagement, household)` is built once and `fed_once` returns it.
  The job shows `_fed_returns` with a household given reads no file (decision 204's read was the household payload,
  built once since decision 192); if it reads one, stop and ask.
- **R6.5.3, the vocabulary sends the groups.** `api.vocab()` adds `"groups": list(GROUPS)`.
- **R6.5.4, the page reads them.** `fedReturns()` keeps its first two lines (`const hh = lastState &&
  lastState.household; if (!hh) return [];`), then returns `lastState.hand_over_targets || []` when
  `lastState.paths && lastState.paths.engagement === active`, and otherwise runs the rest of today's body unchanged
  (R6.5.5's window). Its comment says the engine's list is the one the hand-over may name, and why today's rule stays
  for that one window. `pagesTally` is deleted; `shellCountsDiffer` reads `state.tally` (`const tally = state.tally;`
  in place of `pagesTally(state)`, the line's only change); `shell.js`'s interface line for it (32) goes.
  `PAGES_GROUPS` is deleted and its readers read `vocab.groups`. The three fakes give `vocab.groups`.
- **R6.5.5, the edge cases.**
  - **The Hand Over list's own window** (review 2's S22). The page's rule leaves out the page's `active`; the engine's
    leaves out the state's own return (api 3594). They part whenever `active` is not `lastState`'s return: after
    `select(B)` (app.js 457) and before B's state reaches `render` (485), which happens in `showReturn` (2053, across
    its `await`) and after `loadEngagements`' `select(chosen)` (2007, until the next `showReturn`). `select` followed at
    once by `renderFor` (1524, 3404) opens no gap, and every `render` runs under `renderFor`'s `view ===
    viewGeneration`, so outside the gap the state is the shown return's. In the gap the old list offers A's own return
    and leaves out B; the engine's does the reverse. The writer measured the three entry points: the sheet's button
    (`reviewRow`, 1012) is drawn only by `sheetDrawCheck`, after `showReturn` returned true or after `render` (no
    gap); `openHandOver` (1135) is reached from that button; but `pagesCanHandOver` (pages.js 2163) only checks
    `state.paths.engagement === spec.step.ret`, so a row menu opened on a firm page (Needs Review) while the side
    sheet reads another return (`openCheck`, sheet.js 224) asks `fedReturns()` in the gap, and "Another Return" can be
    enabled today where the engine's list would grey it. That entry point is live, so by threads/P6/003 step 2 the page
    keeps today's rule in the gap (R6.5.4) and the engine's list everywhere else. The job re-measures the three entry
    points and names them in before.txt; a fourth caller of `fedReturns()`, or a `render` outside `renderFor`, is a stop
    and ask. The first branch needs `active` and `state.paths.engagement` to be the same string for the same return:
    the oracle shows each state's `paths.engagement` equals the list row's `path` it was asked by (the page already
    relies on it, app.js 1524 and 2005, pages.js 2165); if one differs, stop and ask.
  - **Duplicates.** The JavaScript list keeps every entry; the Python one is a dict by path, so the two differ only
    where two entries share a path. The job shows, with a test where a test can reach it:
    - **a feed never resolves to a return of its own household,** so never to the shown return: `resolve_feeds` skips a
      feed that names its own household (`households.py` 313) for any record, hand-written or not, and the editor refuses
      one (`household_edit._feeds_from_spec`, 144-145). The oracle shows the refusal: an `edit-household` naming the
      household's own return as a feed is refused with `FEED_REFUSED`'s sentence;
    - **two feed lines never resolve to one return:** the editor refuses a line the list already holds by the layout's
      key (`_feeds_from_spec` 146-149). The job measures whether `load_household_info` reads a hand-written record that
      holds two such lines; if it can, stop and ask (a person would see the return once in the Hand Over list where today
      it shows twice).

    If either can happen, stop and ask.
- **R6.5.6, the oracle.** `tests/node_harness.py` gains `RETIRED_PAGE_RULES`: a dict from each retired name
  (`PAGES_GROUPS`, `pagesTally`, `fedReturns`) to its text exactly as at `9df1724`, with a docstring saying they are
  the page's retired rules kept as the oracle. A test hands the ones it uses to `run_pages_dom` or `run_shell` through
  `setup` (`pagesTally` with `PAGES_GROUPS`, which it reads); `pagesTally` leaves `run_pages_dom`'s default list
  (node_harness 326), so nothing lifts the deleted function.
  - **Why it builds its replies.** The recordings in `tests/golden/` hold key trees only, with no values (P2.3's
    shape contract), so they cannot be the oracle's inputs; the test builds the made-up pile's replies on a scratch
    root as `tests/test_golden.py` does, and its docstring says so.
  - **What the pile must hold,** each named in the test: every group with a nonzero count across the states, with a
    parked file, **a file set aside by a person**, **a file moved by hand** and **a file moved by hand that a person
    marked missing** (`file_group`'s three branches that are not `GROUP_RECEIVED`: Needs you for the moved file, Set
    aside for the other two, firm_view 241-251). They are built as `test_api_review` builds a dismissed file and a
    moved copy, and the last as
    `test_the_moved_card_offers_mark_missing_on_a_row_whose_copy_and_original_are_both_gone` (1074) does: a
    `mark-missing` on a moved row whose copy and original are gone. The pile also holds one made-up household with two
    feeds, one resolved and one not, and the refused own-household feed of R6.5.5.
  - **What it shows,** under node, for every return's `state`: the retired `pagesTally(state)` equals `state.tally`;
    the counts `pagesReturnGroups(state)` draws, by group, equal `state.tally` (the link between what the return page
    shows and the count the Overview compares, SPEC 9.1, which
    `test_the_pages_groups_and_the_firms_tally_of_them_cannot_disagree` holds today through `pagesTally`), the
    marked-missing file's count landing in Set aside in both; with that state as `lastState` and its return as
    `active`, the retired `fedReturns()` equals `state.hand_over_targets` and so does the page's `fedReturns()` (its
    first branch); with `active` set to another return of the pile (R6.5.5's window), the page's `fedReturns()` equals
    the retired rule (its second branch); and `PAGES_GROUPS` equals `vocab.groups`.
  - **The page's tally tests keep their claims, against the retired rule** (review 1's S4, review 2's S18). Each of
    these calls the page's own `pagesTally` today; each keeps its name, its made-up state and every assert, with the
    retired `pagesTally` from `RETIRED_PAGE_RULES` in place of the deleted one, and its docstring gains one sentence:
    the engine's `state.tally` is held to the same rule by the oracle. None is rewritten to read a made-up
    `state.tally` (which would compare a fake with itself), and no assert is dropped.
    - `test_the_pages_groups_and_the_firms_tally_of_them_cannot_disagree` (test_shell 1107-1118): the drawn groups
      equal the tally.
    - `test_one_item_without_a_group_is_named_in_a_notice_and_every_other_row_is_drawn` (1317-1342): an item without
      a group is counted in none.
    - `test_a_moved_file_marked_missing_is_set_aside_and_the_tally_equals_the_firms_counts` (1570-1594): `drawn ==
      tally == firmCounts` for a moved file marked missing; the oracle's pile now holds that case on the engine's side.
    - `test_a_file_without_a_group_is_named_and_not_counted` (1597-1604): a file without a group is named and not
      counted.
  - **The error path keeps its claim with a new failing input.**
    `test_an_error_after_the_state_arrives_never_reaches_the_write_that_brought_it` (1384-1405) holds that an error of
    the page's own in the counts' compare is said and never thrown back to the write. Its stand-in `pagesTally = () => {
    throw new Error("tally"); }` reaches nothing once `shellCountsDiffer` reads `state.tally`, so the probe's second
    `shellStateArrived` is handed a state whose `tally` throws when read (`{ paths: { engagement: "r1" }, items: [],
    get tally() { throw new Error("tally"); } }`), and the stand-in line and the setup's `let pagesTally = null;` go.
    The firm's counts in the setup hold `r1`, so `shellCountsDiffer` reaches the read, and the expected result is
    unchanged: `[None, ["draw", "tally"]]`. The job shows on a scratch copy that the test fails when
    `shellStateArrived`'s `try` is removed.
- **R6.5.7, the contract and the recordings.** `replies.StateReply` gains `tally: dict[str, int]` and
  `hand_over_targets: list[dict]`. Re-recorded, and no other: `vocab.keys.json` and `replies.list.keys.json`
  (`groups`), `replies.state`, `replies.assign`, `replies.create`, `replies.edit` and `replies.edit-household` (each
  holds a state). The job lists each tree's added keys and nothing else changed.
- **R6.5.8, the harness.** `stub.js`'s `stateOf` sends `tally` (from its own made-up groups) and `hand_over_targets`;
  the double's `fedReturns` (app-stub.js 305) takes the page's new body; `SEAMS` loses `pagesTally` from `("shell.js",
  "pages.js")`.
- **R6.5.9, the decision row P354.** The engine sends who a document may be handed to, a return's counts and the group
  names, and the page draws them (D-3, 5.1 (9)); the page's retired rules are the oracle. The row names the one window
  where the page keeps its own rule, between `select()` and the next `render` (R6.5.5), and why.
- **R6.5.10, the curated notes** (review 2's S23). `tracker/firm_view.py`'s node says "the API imports back by name the
  twenty names its own code reads" and lists them; `tally` and `GROUPS` (R6.5.1, R6.5.3) make it twenty-two, added to
  the list in its order. The job greps `docs/repo-map.curated.json` for "twenty" and for the import list's names, and
  corrects every note that counts or lists the API's imports from `firm_view` (measured at `9df1724`: that one node);
  then the map refresh.

**Pin-move list:** the four tally tests and the error-path test of R6.5.6 (test_shell 1107-1118, 1317-1342,
1384-1405, 1570-1594, 1597-1604: kept, against the retired rule or with the new failing input); test_shell 1975,
2021, 6132, 8166 (`pagesTally`, `fedReturns` fakes); node_harness 218, 326, 641; test_single_source 4240, 4265;
test_firm_view's counting tests (measure); `pilot/harness/app-stub.js` 305; `SEAMS`; `docs/repo-map.curated.json`
(R6.5.10). The job greps `tests/` and `pilot/` for `pagesTally`, `PAGES_GROUPS` and `fedReturns` and lists every hit
in before.txt with what it became.

**Patch sites:** `report tracker.firm_view` and `report tracker.api` unchanged but line numbers.

**Tests:** `test_firm_view`; the API's test files (section 3: the eight `test_api*` owners, `test_api_entry`,
`test_resident`); `test_firm_cache`, `test_golden`, `test_admission`; the renderer's readers (section 3: they include
`test_build`, which runs `node --check`, `test_replies`, `test_row_columns`, `test_pilot`, `test_tour`, `test_shell`,
`test_single_source`, `test_renderer_seams` and `test_layers`); `test_repo_map`, `test_tripwire`.

**Accept when:** the oracle passes on every return, both branches of `fedReturns()` included; `grep -n
"pagesTally\|PAGES_GROUPS" app/` is empty; the five tests of R6.5.6 pass with their asserts unchanged, and each fails on
a scratch copy where the retired rule is changed (the error-path test: where `shellStateArrived`'s `try` is removed);
the firm's counts are byte for byte the same (`test_api_firm`); exactly the seven recordings changed, each only by its
new keys; `typecheck.py check` passes with `api` and `firm_view` at 0; the curated note says twenty-two.
- **Windows:** no label. **Office `-Tests`:** `test_firm_view,test_api,test_api_returns,test_api_review,test_api_firm,test_golden,test_shell`.
  Hands-on: open a return with a parked file and a household that feeds another, and see the same Hand Over list;
  file a document and see the Overview's counts follow as before.

---

### P6.6 The engine sends each return's `taxpayer` (D-3 c)

- **Cost:** M.
- **Tier:** Opus, rule (e).
- **Findings:** D-3 (c); review 1's S1, S2, S3; the orchestrator's answer (threads/P6/003).
- **Depends on:** P6.5.

**What is measured.** `pagesTaxpayer` (pages.js 221-232) has four callers, and they cut two different inputs:

| Caller | What it cuts | Whose name, whose form |
|---|---|---|
| pages.js 1344 (a household's return rows) | `one.return_name \|\| pagesReturnName(one.path)`, `one.form` | the **list's** row (`households[].returns`), both |
| app.js 2334 (`sortReturnSaid`, the pass's line) | `one.return_name`, `one.form` of `shellReturn(run.path)` | the **list's** row (`engagements`), both |
| pages.js 383 (`pagesReturnHeading`, Needs Review's return heading) | `pagesReturnName(path)`, the group's `form` | the **list's** name found by path (`shellReturn`, shell.js 751), else `folderName(path)`; the **firm** group's form |
| pages.js 1069 (`pagesReturnCells`, the Overview's and Reminders' rows) | `pagesReturnName(one.path)`, `one.form` | as 383, with the **firm** row's form |

The list's rows come from `api._return_row` (2788): `return_name` is `one.info.return_name or one.path.name`, never
empty. The firm walk's names (`firm_pages._Walk.name_of`, 429-431) are the same expression over the same registry
(api 4721) for a fresh `firm`, and the cache's kept names (`firm_view._firm_seen`, 601) for `firm-last` and a page
turn. A return's form is written only when its record is created (`manifest.create_engagement`, 1496-1497;
`rollover`), and creation refuses a folder that already has a record (manifest 1486).

**So within one walk** the firm's names and the list's agree, and a cut of the firm walk's name would equal the page's.
**They part when the list and the firm reply are from different moments**, the three windows of review 1's S2:
- (i) the launch's last counts (`firm-last`), cut from the names the cache kept, beside today's list;
- (ii) after a write that renames (`accept-folder-name` sets `return_name` to the folder's name, api 3471; Edit
  Household), until the next firm reply: the write's reply carries the new list (`LIST_CHANGING`), the firm rows are
  the old ones;
- (iii) a firm row whose path the list does not hold (a return whose folder moved or went since the firm reply; the
  list is the newer), where the page cuts the folder's name today.

A `taxpayer` cut on the firm row (review 1's S2 fix, from `walk.name_of`) differs from what the page draws in each
window, so this job puts none on the firm reply. The firm lists read the **list's** row, the page's own input, and
keep the page's cut for the two cases the list cannot answer. The result is that nothing a person sees changes in any
window (threads/P6/003, steps 1 and 2), with no question for Jason.

**Requirements:**

- **R6.6.1, one rule, public.** `firm_pages._taxpayer` becomes `firm_pages.taxpayer`; its readers follow
  (`_return_cells` 446; test_firm_pages 283; test_shell 8236).
  - **The one other edit in `firm_pages`, named** (review 3's S26): `_return_cells`' local `taxpayer` (446) would
    shadow the function it calls (`taxpayer = taxpayer(...)` raises `UnboundLocalError` on every firm page), so it is
    renamed `cut`: 446 becomes `cut = taxpayer(walk.name_of(one["path"]), one.get("form") or "")` and 447's
    `"taxpayer": taxpayer` becomes `"taxpayer": cut`. The dict's key, `"taxpayer"`, is unchanged, and so is every
    value the function returns. Its docstring keeps naming `pagesTaxpayer` as its twin
  and says why the twin stays (R6.6.3). `api` is the new reader, and it already imports `firm_pages`, so no import is
  added and P278's pin (test_layers 1298-1306) holds as it stands.
  - **The one edit to its body: the trim** (review 2's note, measured by the writer). Python's `str.strip()` and
    JavaScript's `trim()` strip different characters: `trim()` strips U+FEFF, which `strip()` keeps, and `strip()`
    strips U+001C-U+001F and U+0085, which `trim()` keeps (every other character they strip is common to both;
    enumerated over the BMP under node 22 and Python 3). So for a name with one of those next to the cut, the engine's
    cut is not the page's today. `taxpayer` gains a keyword `chars: str | None = None`, and its one `.strip()`
    becomes `.strip(chars)`, which is `.strip()` when `chars` is `None`; a module constant `PAGE_TRIM` holds the 25
    characters `trim()` strips, its comment naming its twin. `_return_cells` calls it as today, so the firm lists'
    order is unchanged (it sorts by the engine's cut, P278); `api._return_row` passes `chars=PAGE_TRIM`, so the field
    the page draws is the page's own cut for every name (R6.6.2).
- **R6.6.2, every list row carries it.** `api._return_row` (2788) adds `"taxpayer": firm_pages.taxpayer(return_name,
  one.info.form or "", chars=firm_pages.PAGE_TRIM)`, the `return_name` it already sends. That reaches every row it makes: the list's `engagements`
  and `households[].returns` (2819, 2824) and the state's `household.returns` (2088). The firm reply (`firm`,
  `firm-last`, a page turn) gains no field; `firm_view` and `firm_pages`' builders are not edited.
- **R6.6.3, the page reads it.**
  - 1344 reads `one.taxpayer`, and 2334 reads the list row's `taxpayer`. Both cut the list row's own name and form
    today, so the field is the same text.
  - 383 and 1069 read a new `pagesFirmTaxpayer(path, form)` in `pages.js` beside `pagesTaxpayer`, with a comment
    giving this section's reason:

    ```js
    function pagesFirmTaxpayer(path, form) {
      const one = shellReturn(path);
      return one && (one.form || "") === (form || "") ? one.taxpayer : pagesTaxpayer(pagesReturnName(path), form || "");
    }
    ```

    When the list holds the return with the firm row's form, `pagesReturnName(path)` is `one.return_name`, and
    `one.taxpayer` is the engine's cut of that name and form, so the text is today's in every window, (i) and (ii)
    included. When it does not, the second branch is today's expression, unchanged: window (iii), and a list row whose
    form differs from the firm row's. The latter needs a record removed and created again with another form between the
    two replies.
  - `pagesTaxpayer` stays, for that branch only, with its `vocab.layout.return_name_pattern` read. Its comment says
    so: it is the page's cut of a firm row the list cannot answer, held equal to `firm_pages.taxpayer` by R6.6.4.
  - **The pattern's loud failure narrows, named** (review 2's S21). Today every taxpayer the page shows runs
    `pagesTaxpayer`, which throws on a vocabulary without `layout.return_name_pattern` (pages.js 222-223; test_shell
    1840-1856 calls it "a loud failure"). After this job the household rows (1344), the pass's line (2334) and
    `pagesFirmTaxpayer`'s first branch read the engine's `taxpayer` and consult no pattern, so only the second branch
    still fails loudly on a vocabulary without one. The engine always sends the pattern and cuts with its own
    (`layout.RETURN_NAME_PATTERN`), so nothing a person sees changes; the failure guarded a page that cut names
    itself, and those rows no longer do. Test 1840-1856 is unchanged. P355 says this in one sentence.
  - `SEAMS` loses `pagesTaxpayer` from `("app.js", "pages.js")` (2334 no longer calls it).
- **R6.6.4, the tests that hold it** (review 1's S1: no parity guard is dropped).
  - `test_the_engines_taxpayer_form_and_count_words_are_the_pages` (test_shell 8216-8238) is **kept whole**, with
    its edge-case table and its three claims: `pagesTaxpayer` == `firm_pages.taxpayer` (the name it calls changes,
    from `_taxpayer`), `pagesCounts` == `_counts_said`, and the form order == `_form_key`. Its docstring adds that the
    first claim is what makes `one.taxpayer` safe to draw in place of the page's cut. Its table gains names with
    U+FEFF, U+0085 and U+001C after the separator and at the end. The first claim then holds `pagesTaxpayer(n, f) ==
    firm_pages.taxpayer(n, f, chars=firm_pages.PAGE_TRIM)` on every row, and `== firm_pages.taxpayer(n, f)` on
    every row without those characters (the firm lists' order keeps the engine's own trim). A second assert names
    the rows where the two trims part, so a change to either trim fails it. A further assert shows
    `firm_pages.PAGE_TRIM` equals the characters `trim()` strips, enumerated under node.
  - `test_the_taxpayer_is_the_name_without_its_recorded_form_and_never_a_guess` (test_shell 1840-1856) and
    `test_the_taxpayer_and_form_keys_follow_the_recorded_form_never_a_guess` (test_firm_pages 282) are kept as they
    are (the second calls `taxpayer`).
  - **The list rows' oracle.** A new test in `tests/test_shell.py` builds the made-up pile's `list` and `state`
    replies on a scratch root, as `tests/test_golden.py` does. The recordings hold key trees only, so they cannot be
    the inputs. The pile includes a return whose recorded name does not begin with its form, a hyphenated form
    (`1120-S`), and a return with no form. For every row of `engagements`, `households[].returns` and
    `state.household.returns` it shows under node that `pagesTaxpayer(row.return_name, row.form || "")` equals
    `row.taxpayer`.
  - **The firm lists' oracle, on the page's own inputs.** A new test builds, from one scratch root, the `list` and the
    `firm` replies for the Overview, Reminders and Needs Review. With `engagements` the list's, it shows under node that
    for every Overview and Reminders row and every Needs Review group, `pagesFirmTaxpayer(path, form)` equals today's
    expression `pagesTaxpayer(pagesReturnName(path), form)`. It then repeats the check in each window, each case named:
    - (i) a `firm-last` reply taken before one return was renamed by `accept-folder-name`, drawn beside the list read
      after it;
    - (ii) the firm rows taken before an `accept-folder-name`, beside the list its reply carried;
    - (iii) a firm row whose path the list does not hold (its return left out of `engagements`), whose recorded name
      differs from its folder's;
    - a list row whose form differs from the firm row's (made-up rows).

    In every case the two are equal. The test's docstring says why the firm reply carries no `taxpayer`.
- **R6.6.5, the saved rows.** The firm reply gains no field, so nothing kept by the base program changes shape. The
  list's rows are never kept: every `list` and every list-changing write is read fresh.
- **R6.6.6, the contract and the recordings.** `replies.py` types these rows as `list[dict]` and `dict`
  (`ListReply.engagements`, `ListReply.households`, `StateReply.household`, measured), so no `TypedDict` changes. The
  key trees are the contract that changes, and `test_replies` is run to show it still holds. Re-recorded, and no
  other: the six recordings that hold a `_return_row` row, measured at `9df1724` by a `return_name` key: `replies.list`, `replies.state`, `replies.assign`, `replies.create`,
  `replies.edit` and `replies.edit-household`. `replies.firm` and `replies.firm-last` are unchanged. The job lists
  each tree's added keys and nothing else changed.
- **R6.6.7, the harness.** `stub.js` sends `taxpayer` on every list and state return row it makes, cut by its own copy
  of the rule (stub.js 377, which reads `return_name_pattern`). The double's rows do the same where they carry
  `return_name`.
- **R6.6.8, the decision row P355.** The engine says each return's taxpayer on every list row, cut with the page's
  own trim (`PAGE_TRIM`); the firm lists read the list's, as they read its name. The page keeps its own cut only for a
  firm row the list cannot answer, which only happens when the firm reply and the list are from different moments
  (D-3 c, P194, P195, P278; this SPEC's P6.6 and threads/P6/003). The pattern's loud failure now guards only
  `pagesTaxpayer`'s second branch, because the engine's cut needs no pattern on the page (R6.6.3).
- **R6.6.9, the map** (review 3's note). `tracker/firm_pages.py`'s curated note gains one sentence: `taxpayer` (with
  `PAGE_TRIM`, the page's trim) is also the cut the API puts on every list row (`api._return_row`, P355), and still
  reads no record, so "decides no count and reads no record" stays true. `python tools/repo_map.py update` runs in the
  same commit.

**Pin-move list:**
- test_shell 1357 (`pagesReturnCells`' test lifts `pagesFirmTaxpayer`), 1859-1899
  (`test_the_firm_pages_rows_link_by_the_firms_keys_and_carry_the_year`: the same), 4143 (`sortReturnSaid`'s fake rows
  carry `taxpayer`), 8236 (the name);
- node_harness 287 and 324 (the functions the page runners lift); test_firm_pages 283; `SEAMS`.
- **Every `shellReturn` fake** (node_harness 216 and 444; test_shell 1867 and the rest, found by grep) gains the `form`
  and `taxpayer` the engine would send for its `return_name`. Without them the fake takes `pagesFirmTaxpayer`'s second
  branch, which is today's expression, and the test would no longer reach the first. A fake with no `form` beside a
  firm row with none would return `undefined`. The job lists each fake and the branch its test now reaches.
- The job greps `tests/` and `pilot/harness/` for `pagesTaxpayer`, `pagesReturnHeading`, `pagesReturnCells`,
  `sortReturnSaid`, `shellReturn =` and `_taxpayer`, and lists every hit in before.txt.

**Patch sites:** `report tracker.firm_pages` (4 at `9df1724`) and `report tracker.api`: unchanged but line numbers.

**Tests:** `test_firm_pages`; the API's test files (section 3); `test_golden`, `test_admission`; the renderer's
readers (section 3, `test_replies` among them); `test_repo_map`, `test_tripwire`.

**Accept when:**
- Both oracles pass, every window included.
- `grep -n "pagesTaxpayer(" app/` shows only its definition and `pagesFirmTaxpayer`'s second branch.
- Exactly the six recordings named changed, each only by `taxpayer`.
- `firm_pages` has no more type errors than 6, and `api` has 0.
- `report tracker.firm_pages` lists the same 4 stand-ins (`PAGE_SIZE` twice, `write_text_atomically` twice; none
  names `_taxpayer`), line numbers aside.
- **Windows:** no label. **Office `-Tests`:** `test_firm_pages,test_api_household,test_api_returns,test_golden,test_shell`.
  Hands-on, the same as before: the Overview, Reminders, Needs Review and a household page show every taxpayer as
  before (a 1040, a 1120-S, a return whose name does not start with its form); Accept Folder Name on a return that
  offers it, and watch its name on the Overview before and after the counts refresh; run Sort and read its line.

---

### P6.7 `api-client.js`, `notices.js`, `dialogs.js`; the double stands in for the family (D-1)

- **Cost:** M.
- **Tier:** Opus (rule (a)).
- **Findings:** D-1; D-8 (the double).
- **Depends on:** P6.6.

**What moves:** section 4.0's rows for `api-client.js`, `notices.js` and `dialogs.js`.

**Requirements:**

- **R6.7.1, the scripts.** `app/renderer/api-client.js` (the one `call()`, the reply's warnings and envelope, `withEng`
  and the write helpers: decisions 193, 194, P218), `notices.js` (decision 193's notices, P273's focus) and
  `dialogs.js` (decision 201's registry, D10, F-T-7; the menu's three dialogs, SPEC 2.7), by section 3's rules, loaded
  in that order after the vendor scripts and before `app.js`.
- **R6.7.2, the writes.** `WRITES` gains `("dialogs.js", "app.js", "handingOver")` and `("dialogs.js", "app.js",
  "unfiling")` (the hooks' `closed`, 3925 and 3928); no other.
- **R6.7.3, the double stands in for the family.** `pilot/harness/serve.mjs`'s double mode drops every script
  `index.html` lists between the vendor scripts and `app.js`, by a rule over the page (not one `replace` per script),
  and replaces `app.js` with the stubs and the double as today. `the_double_mode()` (test_renderer_seams 477) runs
  `serve.mjs`'s exported `page("double")` under node and compares its script list with `index.html`'s: the scripts it
  stands in for are `APP_FAMILY` and `sheet.js`. The double test's `stood_in_for` reads that. `pilot/harness/README.md`
  says the double stands in for `app.js` and the scripts carved out of it.
- **R6.7.4, `FILE_NAMED`.** `EL_ATTRIBUTES` and `el` stay in `app.js` (1-194), so the double's claim stays `app.js`'s.
- **R6.7.5, the curated nodes** of the three scripts, from `app.js`'s note; `app.js`'s note keeps a sentence per script.
  The curated edge `app/renderer/api-client.js --calls--> app/preload.js` is added (its `call()`, the one door to the
  engine); `app/renderer/app.js --calls--> app/preload.js` stays, since `app.js` still calls `window.tracker` (section 3).
- **R6.7.6, the decision row P356.** `app.js` is split by responsibility into classic scripts loaded before it, by
  this SPEC's rules (section 3); the first three; the double stands in for the family.

**Guards that must bite on each new script** (section 4.1): the sink ban, the commands guard (`call([` in
`api-client.js`), the typed-words guard, the no-typed-vocabulary guard, the `keydown` count, the `startsWith(` scan,
the seam table, the load test.

**Pin-move list:** test_shell 356 (the load order); `SEAMS` (`("shell.js", "app.js")` and `("pages.js", "app.js")`,
`("sheet.js", "app.js")`, `("pilot.js", "app.js")` split by owner; new pairs among the family); `WRITES`;
`pilot/harness/serve.mjs` and README; test_renderer_seams 477-513; the map.

**Tests:** the renderer's readers; `test_tripwire`.

**Accept when:** section 4.1's shared accept-when; the harness's double mode draws every scenario it drew (shoot.mjs);
`app.js` is shorter by the moved lines (about 538).
- **Windows:** no label. **Office `-Tests`:** the renderer's readers. Installer step: build and install over the current
  build. Hands-on, the same as before: start the app; a notice with Retry (a failed read) and its dismiss; the four
  dialogs the menu opens (Safeguards, About, Folders Left Alone from its notice, Schedule) with Escape and a click
  behind; one write (file a parked document).

---

### P6.8 `reminder-card.js` and `review-rows.js` (D-1)

- **Cost:** M.
- **Tier:** Opus (rule (a)).
- **Findings:** D-1.
- **Depends on:** P6.7.

**What moves:** section 4.0's rows for `reminder-card.js` and `review-rows.js` (the way back's header placed before
`withdrawAnswer`'s comment).

**Requirements:**

- **R6.8.1, the scripts.** `app/renderer/reminder-card.js` (decisions 118, 194, P213: the card the side sheet frames;
  nothing sends) and `review-rows.js` (decisions 109, 110, 112, 129, 201: a wandered copy, a parked file's answers, an
  unnamed issuer, the hand-over, the way back), loaded after `dialogs.js` and before `app.js`.
- **R6.8.2, the writes.** `WRITES` gains the four `("app.js", "reminder-card.js", ...)` rows (`render` at 499-502), and
  the two `("dialogs.js", "app.js", ...)` rows of P6.7 become `("dialogs.js", "review-rows.js", ...)`; no other.
- **R6.8.3, the curated nodes;** the decision row P357.

**Guards that must bite:** as P6.7, and the `withEng("assign")` and `fileRow` counts (test_single_source 179-180, after
P6.2 counted over the app's scripts).

**Pin-move list:** test_shell 356; `SEAMS` (`("sheet.js", "app.js")` and `("pages.js", "app.js")` most of all);
`WRITES`; the map.

**Tests:** the renderer's readers; `test_tripwire`.

**Accept when:** section 4.1's; the harness's real mode draws the side sheet's Check (a parked file, a moved copy) and
Draft Reminder (held, ready) as before.
- **Windows:** no label. **Office `-Tests`:** the renderer's readers. Installer step. Hands-on: Check a parked file and
  file it, with a keyword taught; hand one over to another return; unfile a filed one from its row's menu; Draft
  Reminder, move a rung, Copy.

---

### P6.9 `household.js` (D-1)

- **Cost:** M.
- **Tier:** Opus (rule (a)).
- **Findings:** D-1.
- **Depends on:** P6.8.

**What moves:** section 4.0's row for `household.js`, with the seven head `let`s it alone writes.

**Requirements:**

- **R6.9.1, the script.** `app/renderer/household.js` (decisions 125, 126, 128, 129, 196: the roll dialog, the
  household editor, Add a Return and New Household with their household and People steps, custom requests and the
  create), loaded after `review-rows.js` and before `app.js`. The People block's `wizardPeople` (2812) moves; its
  neighbour `editorPeople` (2813) stays for P6.10.
- **R6.9.2, the writes.** `WRITES` gains `("household.js", "app.js", "formsUnloaded")`, `("household.js", "app.js",
  "nameIsAuto")` and `("household.js", "app.js", "rollChoice")`; no other. A head `let` this table moves is no longer
  in `app.js`'s state block; `app.js`'s head comment says where the dialogs' state went.
- **R6.9.3, the curated node;** the decision row P358.

**Guards that must bite:** as P6.7; `requestRows` stays callable from the custom rows (it moves in P6.10; the load
test and the custom rows' node tests hold it).

**Pin-move list:** test_shell 356; `SEAMS`; `WRITES`; the map.

**Tests:** the renderer's readers; `test_tripwire`.

**Accept when:** section 4.1's; shoot.mjs's roll dialog and New Household scenarios draw as before.
- **Windows:** no label. **Office `-Tests`:** the renderer's readers. Installer step. Hands-on: New Household through to
  a created return (form grid, custom row, a person); Edit Household with a feed and a related household; Roll Forward
  on a household that offers it (unticked return, form pick); Accept folder name and Mark as Shared where offered.

---

### P6.10 `editor.js`; the paste parser's test (D-1, D-12)

- **Cost:** M.
- **Tier:** Opus (rule (a)).
- **Findings:** D-1, D-12.
- **Depends on:** P6.9.

**What moves:** section 4.0's row for `editor.js`, with `editorRows` and `editorPeople`.

**Requirements:**

- **R6.10.1, the script.** `app/renderer/editor.js` (decisions 104, 160, 176's paste, P279: the one row component, the
  editor's virtual window, the request-list editor, the paste parser), loaded after `household.js` and before
  `app.js`.
- **R6.10.2, the writes.** None added (measured: `editorRows` and `editorPeople` are written only in this script once
  they move with it).
- **R6.10.3, the paste parser's test** (D-12). New `tests/test_editor.py`, which the map takes as `editor.js`'s own test
  file by name: `csvFields` and `pasteRows` lifted with `run_shell` and fakes for `vocab.columns`, `blankEditorRow`,
  `editorRows` and `renderEditorRows`, one test per claim of their comments - a tab on any line makes every line
  tab-separated; quoted CSV fields with a doubled quote and a comma inside; a first line repeating the headings
  skipped, also with a trailing tab; short rows padded with blanks; blank lines dropped; the count returned. Named as
  claims (`test_a_tab_on_any_line_makes_every_line_tab_separated`, ...).
- **R6.10.4, the curated nodes** (the script; `tests/test_editor.py`); the decision row P359.

**Pin-move list:** test_shell 356; `SEAMS`; the map.

**Tests:** the renderer's readers; `tests/test_editor.py`; `test_tripwire`.

**Accept when:** section 4.1's; the new tests pass and each fails on a planted change to the claim it makes (after.txt);
the map shows `tests/test_editor.py --tests--> app/renderer/editor.js`.
- **Windows:** no label. **Office `-Tests`:** the renderer's readers and `test_editor`. Installer step. Hands-on: Edit
  Request List on a return with over the virtual threshold of rows: scroll, edit a row out of view, paste three rows from
  Excel (a heading line too), rename a request, Save; Cancel with a change (the unsaved bar).

---

### P6.11 `schedule.js` and `pass.js` (D-1)

- **Cost:** S.
- **Tier:** Opus (rule (a)).
- **Findings:** D-1.
- **Depends on:** P6.10.

**What moves:** section 4.0's rows for `schedule.js` and `pass.js`. The after-install registration (2298-2316) stays in
`app.js`.

**Requirements:**

- **R6.11.1, the scripts.** `app/renderer/schedule.js` (pilot P21, decision 209's deliberate re-run, P77's move
  question) and `pass.js` (decision 203: one Sort from this window, its progress and its ending; P131's answers by
  return), loaded after `editor.js` and before `app.js`.
- **R6.11.2, the writes.** None added (measured).
- **R6.11.3, the curated nodes;** the decision row P360. After this job `app.js` holds section 4.0's last row and
  nothing else of the table; after.txt gives its length.

**Pin-move list:** test_shell 356; `SEAMS`; the map.

**Tests:** the renderer's readers; `test_tripwire`.

**Accept when:** section 4.1's; `app.js` is under 900 lines.
- **Windows:** no label. **Office `-Tests`:** the renderer's readers. Installer step. Hands-on: Sort Now on a return
  (progress, its line, the household's other returns' lines), Stop a running Sort; open Schedule, change and save;
  Repair the Schedule from its notice.

---

### P6.12 `firm-loader.js` out of `shell.js` (D-7)

- **Cost:** M.
- **Tier:** Opus (the brief: code out of `shell.js`; rule (e)).
- **Findings:** D-7.
- **Depends on:** P6.11.

**What moves** (shell.js, at `9df1724`):

| Lines | Names |
|---|---|
| 60-64, 67-83 | the watch's and the counts' flags: `shellLastPassAsking`, `shellLastPassOwed`, `shellLastPassAgain`, `shellLastPassAt`, `SHELL_FOCUS_QUIET_MS`, `shellFirmNow`, `shellFirmAsked`, `shellFirmEarly`, `shellFirmEarlyLanded`, `shellFirmLast`, `shellFirmAsOf`, `shellClock`, `shellFirmSentAt`, `shellWroteAt`, `shellFirmHeld`, `shellFirmCount`, `shellFirmSlow`, `shellFirmTimer`, `shellTurns`, `shellTurnGen`, `shellTurnThen`, `SHELL_FIRM_SLOW_MS`, each with its comment |
| 215-735 | the scheduled pass, watched (`lastPassStep` to `shellShown`), the counts at launch and asked early (`shellAskFirmNow` to `shellAskFirm`), the firm lists a page at a time (`shellFirmAsk` to `shellFirm`) |
| 878-885 | `shellCountsDiffer` (D-7's list; it compares the counts) |

**Stay in `shell.js`:** `shellLastPass` (59), `shellLastPassStopped` (65), `shellProgressNow` (66), the route's and the
page's flags, and `shellAdopt` (201-213): each is written by code that stays (measured).

**Requirements:**

- **R6.12.1, the script.** `app/renderer/firm-loader.js`, `"use strict"`, loaded after `pages.js` and before `sheet.js`
  (so before `shell.js`); its header gives P218, P221, P222, P228, P229, P262, P277, P278 and says the flags become one
  owner object in phase 7 (D-7, D-2).
- **R6.12.2, the writes.** `WRITES` gains `("firm-loader.js", "shell.js", "shellLastPass")`, `("firm-loader.js",
  "shell.js", "shellLastPassStopped")` and `("firm-loader.js", "shell.js", "shellReturnStale")` (`shellAskLastPass`,
  269-284) and `("firm-loader.js", "pages.js", "pagesPageAt")` (`shellTurnFirm`, 559-560; `shell.js`'s own write at 1788
  keeps its row); no other.
- **R6.12.3, `ENGINE_FUNCTIONS` and the firm runners** (node_harness 80, 614-672) lift by name, so nothing in them names
  a file (P6.3); the job confirms each runs.
- **R6.12.4, the curated nodes** (the script; `shell.js`'s note loses the loader's paragraphs); `shell.js`'s header
  (15-37) names what it takes from `firm-loader.js`; the decision row P361.

**Guards that must bite:** the sink ban, the commands guard (`firm`, `firm-last`, `last-pass`), the typed-words guard,
the seam table, the load test, and R6.3.3's keydown loop: an element listener (`foo.addEventListener("keydown", ...)`)
planted in `firm-loader.js` fails `test_one_keydown_listener_owns_the_keyboard` (review 2's S17), and after.txt shows
that the loop now reads `firm-loader.js`.

**Pin-move list:** test_shell 356; `SEAMS`, re-derived from `seams()` at the job's base, which is after P6.7-P6.11, so
the callers of the moved names sit in the new scripts, not in `app.js`. Expected from `9df1724`'s callers and section
4.0's partition (each re-measured):
- `("app.js", "firm-loader.js")`: `shellAskFirmLast`, `shellAskFirmNow` (`bootstrap`, 2072-2073);
- `("pass.js", "firm-loader.js")`: `shellAskFirmNow`, `shellFirmProgress`, `shellLoadFirm`, `shellWriteLanded`
  (2409, 2490, 2491, 2514);
- `("api-client.js", "firm-loader.js")`: `shellWriteLanded` (`call()`, 216);
- `("pages.js", "firm-loader.js")`: `shellFirm`, `shellTurnFirm`;
- `("shell.js", "firm-loader.js")`: whatever `shell.js` still calls of the moved code (`seams()` says).

The same names leave the `(..., "shell.js")` pairs they sat in at the job's base. `WRITES`; the map.

**Tests:** the renderer's readers; `test_tripwire`.

**Accept when:** section 4.1's; `shell.js` is about 1,270 lines.
- **Windows:** no label. **Office `-Tests`:** the renderer's readers. Installer step. Hands-on: launch with a cache from an
  earlier day (the last counts marked, then the fresh ones); turn the Overview's pages and order a column; let the
  scheduled task run while the app is open and see the last-sort line follow; write something and see the counts
  follow.

---

### P6.13 `shell-words.js`, `logs.js`, `last-pass-watch.js`, `open-path.js` out of `main.js` (D-4)

- **Cost:** M.
- **Tier:** Opus (rule (a)).
- **Findings:** D-4.
- **Depends on:** P6.12.

**What moves** (main.js, at `9df1724`):

| Module | Lines | Names | Exports |
|---|---|---|---|
| `shell-words.js` | 179-197, 221-229 | `shellSays`, `fill`, `shellFailure` | the three, and `learn(said)`: the copy of every string key (main.js 390-392; `const said`, 389, stays in `learn()`; R6.13.2) |
| `logs.js` | 109-111, 199-219, 231-297 | `STDERR_CAP`, `errorLog`, `FALLBACK_LOG_NAME`, `FALLBACK_CAP`, `fallbackLogPath`, `appendToLog`, `keepInLog`, `withNoLog` | `STDERR_CAP`, `fallbackLogPath`, `keepInLog`, `withNoLog`, `named()` (the log the API named, or null) and `learn(said)` (main.js 395, 396 and 398: it returns the log it learned on this call, or null; R6.13.2) |
| `last-pass-watch.js` | 143-159, 313-378 | `LAST_PASS_CHANNEL`, `LAST_PASS_SETTLE_MS`, `LAST_PASS_POLL_MS`, `lastPassWatch`, `lastPassTimer`, `lastPassSoon`, `pollLastPass`, `watchLastPass`, `unwatchLastPass` | `watchLastPass`, `unwatchLastPass`, `useWindow(get)` (the getter of the window `lastPassSoon` sends to, R6.13.3), `learn(said)` (main.js 399-405; R6.13.2) |
| `open-path.js` | 168-178, 869-913 | `openable`, `pathKinds`, `carriesCode`, `openPath`, `openChecked` | `openPath`, `openChecked`, and one hand-out for each place its lines sit in `learn()` (R6.13.2): `learnKinds(vocab)` (main.js 388), `learnLog(errorLog)` (397) and `learnPaths(result)` (406-418) |

**Requirements:**

- **R6.13.1, the modules,** by section 3's rules; each `require`s what it reads (`electron`, `fs`, `os`, `path`,
  `./package.json`, `./shell-words`, `./logs`); none `require`s `main.js`. The bodies move byte for byte; the only new
  lines are these, each listed in after.txt as section 4.1's "new lines":
  - the `require`s and the `module.exports`;
  - in `logs.js`, `const PKG = require("./package.json");` and `const PRODUCT_NAME = PKG.productName;`
    (`fallbackLogPath`, 239, reads `PRODUCT_NAME`; `main.js` keeps its own for the floor, 92, and the title, 1239:
    review 2's S20);
  - `named()` in `logs.js` (`function named() { return errorLog; }`, one line or three), and the new lines of the
    hand-outs that R6.13.2 lists, no others. `logs.js`'s header says that `keepInLog`'s local `const named` (284,
    moved byte for byte) shadows the module's `named()` inside that one function, legally, so that a reader does not
    take one for the other;
  - in `last-pass-watch.js`, R6.13.3's three lines: `let windowNow = () => null;`, `function useWindow(get) {
    windowNow = get; }` (one line or three, as the file's style has it), and `const mainWindow = windowNow();` inside
    `lastPassSoon`'s timer callback, after the unchanged line 317 (`lastPassTimer = null;`) and directly before the
    unchanged line 318 (`if (mainWindow && !mainWindow.isDestroyed()) mainWindow.webContents.send(LAST_PASS_CHANNEL);`).
  A scan of each module's text for `main.js`'s own top-level names (the writer's and the reviewer's scan found
  `mainWindow`, `PRODUCT_NAME` and `errorLog` in these ranges, and nothing else) is pasted in after.txt: every name a
  module reads is its own, `require`d, a global of node or Electron, or one of these hand-overs. Another is a stop and
  ask.
- **R6.13.2, `learn()` dispatches, line by line** (review 3's S25). `main.js`'s `learn(result)` (380-419) keeps every
  effect in today's order: each slice that leaves is called from the place its lines were, and the slices that stay
  (the allowlist, 382-387 and 393; the menu, 394) wait for P6.14 and P6.15. After this job it reads, each line marked
  with what it replaces:

  ```js
  function learn(result) {                                   // 380, unchanged
    const vocab = result && result.vocab;                    // 381, unchanged
    ...                                                      // 382-387, unchanged (P6.15's)
    opener.learnKinds(vocab);                                // replaces 388
    const said = vocab && vocab.shell;                       // 389, unchanged
    shellWords.learn(said);                                  // replaces 390-392
    ...                                                      // 393-394, unchanged (P6.15's, P6.14's)
    const learned = logs.learn(said);                        // replaces 395, 396 and 398
    if (learned) opener.learnLog(learned);                   // replaces 397
    lastPass.learn(said);                                    // replaces 399-405
    opener.learnPaths(result);                               // replaces 406-418
  }                                                          // 419, unchanged
  ```

  (The `//` marks are this SPEC's, not the file's.) The five calls and the `const learned` line are the source's own
  edits of section 4.1, each listed in after.txt with this R-number. The hand-outs, in each module after its moved
  ranges, are the moved lines byte for byte inside these new lines, and no others:
  - `shell-words.js`: `function learn(said) {`, then 390-392, then `}`;
  - `logs.js`: `function learn(said) {`, then 395 and 396, then the new `return errorLog;`, then 398, then the new
    `return null;` and `}`. So `learned` is the log this reply named, exactly when 395's condition held, and 397
    runs exactly then, after 396, as today; 395's condition is written once, where it was;
  - `last-pass-watch.js`: `function learn(said) {`, then 399-405 (the comment and the `if`), then `}`;
  - `open-path.js`: `function learnKinds(vocab) {`, 388, `}`; `function learnLog(errorLog) {`, 397, `}` (the
    parameter has 397's name, so 397 moves byte for byte; `open-path.js` has no other `errorLog`); and
    `function learnPaths(result) {`, 406-418, `}`.

  Each moved line keeps its own indentation, since each hand-out's body sits at the depth `learn()`'s did. Each
  hand-out may carry a one-line comment naming the `learn()` lines it holds, listed as a new line. Because the
  hand-outs follow their module's moved ranges, section 4.1's "what arrived" and "what left" both take the table's
  ranges first and then the hand-outs' lines in the order above. The three reads of `errorLog` outside `logs.js`
  (main.js 558 and 587 in `spawnTracker`, 1088 in `openErrorLog`) become `named()`, the one edit inside code that
  moves later.
- **R6.13.3, the window, by a getter** (review 2's S20). `mainWindow` stays a `let` of `main.js` (1077), assigned at
  1267 and nulled at 1269, and `fromMainWindow` (921) and the theme (1335) keep reading it there. `main.js` hands
  `last-pass-watch.js` a getter once, on the line after `let mainWindow = null;`:
  `lastPass.useWindow(() => mainWindow);`. The module keeps no copy of the window: `lastPassSoon` reads it through
  the getter at the moment it sends, by the one added line of R6.13.1, so a window made, closed or replaced later is
  the one it sees, as today. (A setter that `main.js` called at 1267 and 1269 was the other way; it was not taken,
  because it would keep a second copy of the window in each module and add lines to `createWindow`.) The will-quit
  handler calls `unwatchLastPass()` as before.
- **R6.13.4, the curated nodes** of the four modules (from `app/main.js`'s note); `main.js`'s node keeps a sentence per
  module; the derived `require` edges appear by `update`. The curated edge `app/main.js --writes-->
  artifact:tracker-errors.log` becomes `app/logs.js --writes--> artifact:tracker-errors.log`, since `appendToLog` and
  `keepInLog` move (section 3). `fromMainWindow`'s comment (915-919) stays in `main.js` with the function (R6.15.7).
- **R6.13.5, the decision row P362.** `main.js` is split into CommonJS modules beside it, required by plain path, each
  owning its state; `shell-words.js` holds the shell's sentences and envelope (section 2.1).

**Guards that must bite on each module:** the network tripwire (test_layers 887), the `startsWith(`/`path.relative(`
scan (after P6.3 over `MAIN_SCRIPTS`), the defaults' pins to Python (`shellSays` to `SHELL_*`, test_single_source
589-594, 3389-3391), `openable` the one door (`shell.openPath(` once, test_single_source 593; test_shell_menu 716-718).

**Pin-move list:** `FILE_NAMED`'s `main.js` entries (re-read); the map.

**Tests:** the main process's readers; `test_tripwire`.

**Accept when:** section 4.1's; `test_shell_menu` passes unchanged in every scenario (the menu, the channels, the
strangers, the themes, the fallback log, the last-pass watch, and `_learn`'s cases, 453-544: the error log learned,
opened and refused); `MAIN_SCRIPTS` lists the four; after.txt pastes `main.js`'s `learn()` and each hand-out as
they stand after the job, line for line against R6.13.2's text (cut from each file by hand: `main_function("learn")`
would assert, since three modules now define a `learn`; no test lifts `learn` by name, measured).
- **Windows: label** (`open-path.js` checks every path the app opens with `lstat`). **Office `-Tests`:** the main
  process's readers. Installer step. Hands-on: open a filed document's copy and its folder (Show in Explorer); Help >
  Open Error Log; a path the page never reported is refused (the harness's check is enough here); let the scheduled pass
  run and see the last-sort line follow without Refresh.

---

### P6.14 `menu.js` out of `main.js` (D-4)

- **Cost:** S.
- **Tier:** Opus (rule (a)).
- **Findings:** D-4.
- **Depends on:** P6.13.

**What moves** (main.js): `learnMenu` (299-312, with its comment) and 969-1195 (the menu's header comment to
`onMenuMessage`'s closing brace) less `let mainWindow = null;` (1077), which stays in `main.js` with R6.13.3's
`lastPass.useWindow(...)` line after it: `DEFAULT_MENU_WORDS`,
`menuWords`, `MENU_CHANNEL`, `MENU_TOKEN_MAX`, `SEPARATOR`, `BAR`, `POPUPS`, `ALWAYS`, `MAC_ONLY`, `BAR_IDS`,
`CHECKABLE`, `DEFAULT_TICKED`, `menuEnabled`, `menuChecked`, `menuBuilt`, `sendMenu`, `openErrorLog`, `menuItem`,
`shown`, `buildTemplate`, `buildMenu`, `popupMenu`, `onMenuMessage`. The `ipcMain.on(MENU_CHANNEL, onMenuMessage)`
registration (1196) stays in `main.js` (5.4: the IPC registration).

**Requirements:**

- **R6.14.1, the module** `app/menu.js`: exports `buildMenu`, `onMenuMessage`, `MENU_CHANNEL`, `learn(words)` (today's
  `learnMenu`) and `useWindow(get, check)`. It `require`s `electron` (`Menu`), `./logs` (`named`, `fallbackLogPath`,
  for `openErrorLog`, whose `errorLog` read is `named()` since P6.13) and `./open-path` (`openChecked`). The window
  and the sender check are handed over as R6.13.3's window is (review 2's S20), and these are the only new lines:
  - `let windowNow = () => null;` and `let fromMainWindow = () => false;` (refusing every message until `main.js`
    hands the real check over, which it does at load, before any window exists), and `function useWindow(get, check)
    { windowNow = get; fromMainWindow = check; }`;
  - `const mainWindow = windowNow();` as the first line of `sendMenu`'s body, directly before the unchanged 1081, and
    directly before the unchanged `popupMenu(mainWindow, ...)` line (1181) inside `onMenuMessage`'s popup branch.
    `onMenuMessage`'s first line, `if (!fromMainWindow(event)) return;`, is unchanged and calls the handed check.
  `main.js` calls `menu.useWindow(() => mainWindow, fromMainWindow);` once, on the line after R6.13.3's
  `lastPass.useWindow(...)`; `fromMainWindow` stays in `main.js` (R6.15.7).
- **R6.14.2, `main.js`** calls `menu.learn(vocab && vocab.menu);` where `learnMenu(vocab && vocab.menu);` was (394:
  an edit in place, listed with this R-number; it stays between `shellWords.learn(said);` and `const learned = ...`
  of R6.13.2's text, so the order of effects is unchanged), `buildMenu()` where it was (`createWindow`), and registers
  the channel. `menu.js` exports today's `learnMenu` under the name `learn` (`module.exports = { learn: learnMenu,
  ... }`), so the function moves with its name.
- **R6.14.3, the curated node;** the decision row P363.

**Guards that must bite:** the menu's defaults pinned to `screen_words.MENU` (test_shell_menu 34-70; after P6.3 over
`main_text()`), the roles and accelerators (test_shell_menu 58-70), the POPUPS join (88-120), the network tripwire.

**Pin-move list:** `FILE_NAMED`; the map.

**Tests:** the main process's readers; `test_tripwire`.

**Accept when:** section 4.1's; every `test_shell_menu` scenario passes unchanged.
- **Windows:** no label. **Office `-Tests`:** the main process's readers. Installer step. Hands-on: every menu of the
  bar, an accelerator (Ctrl+1, F5), a row's right-click and Shift+F10, View > Compact Rows' tick, Help > Open Error Log.

---

### P6.15 `engine.js` out of `main.js`; the sender check's words; the shell's envelope typed (D-4)

- **Cost:** M.
- **Tier:** Opus (rule (a)).
- **Findings:** D-4; the J5 and P2.3 carried items.
- **Depends on:** P6.14.

**What moves** (main.js): 32-68 (`FROZEN_API`, `SOURCE_PYTHON`, `NOT_SET_UP`, `NOT_SET_UP_MAC`, `SETTINGS_DIR`,
each with its comment), and `REPO_ROOT` (17) and `API_NAME` (22), which only code that moves here reads (the
constants, `startTracker`'s `cwd` at 650 and the engine block at 707); the floor (70-93: its comment, `MAC_FLOOR`,
`MAC_FLOOR_DARWIN`, `macFloorRefusal`) stays; 95-141 less `STDERR_CAP` (109-111, P6.13's) (`TRACKER_TIMEOUT_MS`
with its comment, 95-103, `PROGRESS_KEY`,
`BOOTSTRAP_COMMAND`, `EARLY_COMMANDS`, `HELD_READING_COMMANDS`, `LAUNCH_COMMAND` with the comment block above it,
128-140; `LAUNCH_DONE_CHANNEL`, 142, stays in `main.js` under a one-line pointer to it); the allowlist state (160-167,
198: `allowedCommands`, `engagementFlag`, `passCommand`, `passes`, `writingCommands`); 422-875 (`commandProblem`,
`runTracker`, `spawnTracker`, `lineReader`, `startTracker`, the engine block to `takeEngine`, with `ownProcessCommands`).
`main.js` keeps the requires, `PKG` and `PRODUCT_NAME` (the floor, 92, and the window's title, 1239), `app.setPath`,
the floor (70-93), `LAUNCH_DONE_CHANNEL`, `learn`, `mainWindow`, `fromMainWindow`, the IPC handlers, the window, the
theme and the lifecycle.

**Requirements:**

- **R6.15.1, the module** `app/engine.js`: exports `runTracker`, `spawnTracker`, `startEngine`, `LAUNCH_COMMAND`,
  `learn(vocab)` (main.js 382-387 and 393: the allowlist, the own-process commands, the flag, the pass command, the
  writing commands), `whenReplied(fn)` (the one function `settle` calls with each good reply, today `learn(value)`, 490)
  and `quit()` (the will-quit lines that stop the passes and end the engine's input, 1345-1356, with `quitting = true` at 1349).
  - **The new lines** (review 2's S20), the only ones besides the `require`s, the exports and R6.15.1's
    functions: `const PKG = require("./package.json");` and `const PRODUCT_NAME = PKG.productName;` at the head of
    `engine.js` (`SETTINGS_DIR`, 67, and `startTracker`, 646, read `PRODUCT_NAME`; `API_NAME`, which moves, reads
    `PKG`). `main.js` keeps its own `PKG` and `PRODUCT_NAME`. `REPO_ROOT` and `API_NAME` move byte for byte, before the
    constants that read them, with the comment above `PKG` (18-19) staying in `main.js`. R6.13.1's scan is pasted for
    `engine.js` too.
  - **The hand-outs, line by line** (review 3's S25), after the moved ranges: `function learn(vocab) {`, then 382,
    383-384 (the comment), 385, 386, 387 and 393, byte for byte, then `}`; and `let replied = () => {};` with
    `function whenReplied(fn) { replied = fn; }` (one line or three). `main.js` hands its `learn` over at load, before
    any command can run, so the default is never called with a reply.
  - **The one edit inside a moved body, named:** 490, `      if (value && !value.error) learn(value);`, becomes
    `      if (value && !value.error) replied(value);`. In `engine.js` the name `learn` is the module's own hand-out,
    which takes a vocabulary; `settle` must call `main.js`'s `learn(result)`, which the handed-over `replied` is.
    after.txt lists it, old and new, with this R-number.
- **R6.15.2, `main.js`** calls `engine.whenReplied(learn);` once, on the line after the `require` of `./engine`,
  `startEngine()` and `spawnTracker([LAUNCH_COMMAND], ...)` where it does, and `engine.quit()` in will-quit after
  `unwatchLastPass()`. Its `learn()` is then only the hand-out of each module's slice, and reads, after this job:

  ```js
  function learn(result) {
    const vocab = result && result.vocab;
    engine.learn(vocab);                                     // replaces 382-387 and 393
    opener.learnKinds(vocab);
    const said = vocab && vocab.shell;
    shellWords.learn(said);
    menu.learn(vocab && vocab.menu);
    const learned = logs.learn(said);
    if (learned) opener.learnLog(learned);
    lastPass.learn(said);
    opener.learnPaths(result);
  }
  ```

  **One reorder, named:** `engine.learn` runs 382-387 and 393 together, so 393 (`writingCommands`) now runs before
  388-392 (`pathKinds`, the shell's words). The effects write disjoint state and no line of `learn()` reads
  `writingCommands`, so nothing any reader sees changes; every other slice keeps today's order (R6.13.2).
- **R6.15.3, nothing moves in time.** `SETTINGS_DIR` and `FROZEN_API` read `app.isPackaged`, `app.getPath("appData")`
  and `process.resourcesPath` when `engine.js` loads, which is after `app.setPath` (section 3); the job shows the values
  equal under `run_menu`'s packaged and unpackaged scenarios, Windows and Mac (`sc.platform`).
- **R6.15.4, the engine's pins.** `RESIDENT_FLAG`, `ENGINE_END_KEY`, `ENGINE_LINE_MAX`, `ENGINE_PAYLOAD_MAX`,
  `PROGRESS_KEY`, `HELD_READING_COMMANDS`, `BOOTSTRAP_COMMAND`, `EARLY_COMMANDS` stay pinned to Python
  (test_single_source 190-206, 3376-3382; test_resident 480), now over `main_text()`.
- **R6.15.5, the fake Electron** (`MENU_HARNESS`) is unchanged: `engine.js`'s `require("child_process")` goes through
  `Module._load` like `main.js`'s did; the job shows a resident frame and an own-process command in one scenario.
- **R6.15.6, the curated node;** `main.js`'s node is short and says what it keeps. The three curated edges
  `app/main.js --spawns--> tracker/api.py`, `tracker/resident.py` and `api_entry.py` become `app/engine.js --spawns-->`
  each, since `startTracker` and `startEngine` move (section 3); `Start App.bat --launches--> app/main.js` stays.
- **R6.15.7, `fromMainWindow`'s comment** (main.js 915-919) says what `event.sender` tells: that the message came from
  the app's window's web contents, which no other window shares; it cannot tell one frame of the page from another or a
  page before a navigation from one after, and none can arise (navigation is denied, the preload runs in the main frame
  only). No check changes.
- **R6.15.8, `NOT_FROM_THE_WINDOW`** stays typed in `main.js`, the decision row saying why: it is said only to a sender
  that is not the app's window, so no person's screen shows it, and a word of the API's would add a vocabulary key
  (`tests/golden/` changes only by D-3's fields in this phase). test_shell_menu 723 keeps its copy.
- **R6.15.9, the shell's envelope typed.** `tracker/replies.py` gains `ShellFailure(Envelope)` with `progress:
  NotRequired[dict | None]` and `killed: NotRequired[bool]`, documented as the envelope `shell-words.js`'s
  `shellFailure` answers with when no reply came (the last progress line, the kill at the time limit), which the engine
  never sends; test_replies' `shellFailure` test (558) holds every `extra` key `MAIN_SCRIPTS` passes it to
  `ShellFailure`'s keys.
- **R6.15.10, the decision row P364.** The engine's call path in `engine.js`; `main.js` keeps the window, the
  channels and the lifecycle (5.4); `NOT_FROM_THE_WINDOW` typed on purpose; `ShellFailure`.

**Guards that must bite:** the commands allowlist checks (test_single_source 190-206), the "a write is never run twice"
pins (`HELD_READING_COMMANDS`, main.js 579's retry), the timeout pins (3102-3105), the network tripwire, the `startsWith(`
scan.

**Pin-move list:** `FILE_NAMED`; test_replies 483-491 (after P6.3, by side); test_single_source 5231-5233 (the
will-quit body: the pass pipes destroyed, the engine's input ended, `"kill" not in`), which reads the will-quit block
joined with `main_function("quit")` from P6.15 on, all three asserts unchanged, and a planted `.kill(` in `quit()`
shows the negative still bites (orchestrator, review 4's S27); the map.

**Tests:** the main process's readers; `test_resident`; `test_tripwire`.

**Accept when:** section 4.1's; every `test_shell_menu` scenario passes unchanged; `main.js` is under 450 lines.
- **Windows: label** (the API executable's path, the spawn with `windowsHide`, the kill). **Office `-Tests`:** the main
  process's readers and `test_resident`. Installer step. Hands-on: start the app (the first list from the engine); open
  several returns quickly; Sort Now and Stop; close the app during a Sort (it stops after its file); Setup's launch door
  ran (no "Setup Needs Attention" unless before); a read retried after the engine is killed from Task Manager.

---

### P6.16 `appReady` for `pilot.js` (D-6)

- **Cost:** S.
- **Tier:** Opus, rule (e).
- **Findings:** D-6.
- **Depends on:** P6.15.

**Requirements:**

- **R6.16.1, the promise, resolved where `vocab` is set.** `app.js` declares `appReady` (a `Promise`, with its
  resolver kept beside it) in its state block. It resolves it **on the line after `vocab = listed.vocab;`** in
  `loadEngagements` (app.js 1984 at `9df1724`), and only when `vocab` is an object whose `commands` is an array: the
  very condition `pilot.js`'s poll tests today (pilot.js 55). Resolving it there, not in `applyVocabulary()`, keeps
  today's answer when `applyVocabulary` or `shellVocabulary()` (which throws on a missing block by design) throws:
  today the poll answers as soon as `vocab` holds `commands`, which is before `applyVocabulary` runs (review 1's S6).
  **The proof runs this way:** `appReady` resolves whenever `vocab.commands` becomes an array. The job shows (grep over
  `app/renderer`) that `vocab` is assigned in exactly two places, its declaration `let vocab = null;` (37) and 1984,
  so resolving at 1984 under the poll's own condition covers every way the poll could have answered `true`. A later
  `list` (a Retry, `saveRoot`'s `bootstrap`) that assigns `vocab` again finds the promise resolved, as the poll
  would have answered at once.
- **R6.16.2, `pilot.js` awaits it.** `ready()` (pilot.js 51-64) resolves, once `appReady` resolves, with
  `vocab.commands.indexOf(COMMAND) !== -1` read from `vocab` at that moment, as the poll reads it, and with `false`
  when `READY_WAIT_MS` passes first, measured from the call as today. `READY_LOOK_MS` and the poll go. The record is
  still asked through `window.tracker.call`, and a failure still goes only to the error log (Q-G).
- **R6.16.3, the seams and the double.** `("pilot.js", "app.js")` gains `appReady`; test_pilot's pins on `ready()`
  (measure) follow. Once that pair names it, the double's test (test_renderer_seams 499) requires the double to define
  it, and in the harness's double mode `pilot.js` would otherwise meet an undefined `appReady` (review 2's S23). So
  `pilot/harness/app-stub.js` declares `appReady` and its resolver beside its own `vocab` (10) and resolves it on the
  line after its `vocab = listed.vocab;` (227, in its `bootstrap`), under the same condition as R6.16.1 (`vocab` an
  object whose `commands` is an array).
- **R6.16.4, a test.** Under node with fakes: the record is asked once `appReady` resolves (and not before); `false`
  after the wait when it never does; **`applyVocabulary` throwing after `vocab` is set** still resolves `appReady`, and
  the record is asked at once, as today; a list whose `vocab` has no `commands` array leaves it pending, as the poll
  kept waiting. The terms gate's own `ready()` (289-301) is untouched.
- **R6.16.5, the decision row P365.**

**Tests:** the renderer's readers (section 3: `test_pilot`, `test_tour`, `test_shell`, `test_renderer_seams`,
`test_single_source`, `test_layers`, `test_build`, `test_replies`, `test_row_columns` and the `test_api*` readers),
`test_pilot_ui`, `test_repo_map`, `test_tripwire`.

**Pin-move list:** test_pilot's `ready()` pins (measure); `SEAMS`' `("pilot.js", "app.js")`;
`pilot/harness/app-stub.js` (R6.16.3); the map.

**Accept when:** the pilot's terms, badge and tour work in shoot.mjs's real mode **and** in `serve.mjs`'s double mode
(no page error, the terms drawn); the double's test passes with `appReady` in the pair; `grep -n READY_LOOK_MS app/`
is empty.
- **Windows:** no label. **Office `-Tests`:** `test_pilot,test_tour,test_shell`. Installer step. Hands-on: a fresh install
  shows the terms; sign them; the tour starts once; the badge shows.

---

### P6.17 The overriding stylesheet rules in one home (D-11; only if Jason answers Q-D yes)

- **Cost:** M.
- **Tier:** Opus, rule (e).
- **Findings:** D-11; Q-D.
- **Depends on:** P6.16; Jason's answer to Q-D. If he answers no, this job is not built, and P6.18 depends on P6.16.

**What is measured** (`tests/css_rules.blocks`, at `9df1724`): 627 selectors in the four stylesheets; 65 defined in more
than one (54 in `style.css` and `pilot-ui.css`, 9 in `pilot-ui.css` and `shell.css`, 1 in `style.css` and `shell.css`,
1 in all three); 5 `!important`. The link order (index.html 11-14) is pinned (test_shell 356).

**Requirements:**

- **R6.17.1, the dead declarations go.** A declaration in a rule that a later stylesheet's rule with the same selector
  and the same media sets again for the same property (and neither is `!important`) never applies; each is deleted,
  and a rule left empty is deleted. A test in `tests/test_pilot_ui.py` holds that no declaration in an earlier sheet is
  overridden so (`css_rules.blocks`), with the list of what was deleted in after.txt.
- **R6.17.2, the rest merged by proof.** Each selector still in more than one sheet is merged into the later sheet's
  rule only where a computed-style comparison shows nothing changes: a script under `ORCH/jobs/P6.17/` (not committed)
  loads the harness's scenarios in Chromium (shoot.mjs's list, light, dark and the contrast theme, both window sizes)
  and dumps `getComputedStyle` for every element; the dumps before and after are identical. A selector whose merge
  changes a dump stays in both sheets, listed with the element it changes.
- **R6.17.3, one token block.** `:root`'s colour tokens are defined once (`pilot-ui.css`, which `main.js`'s
  `pageBackground` reads); the link order and the `!important` count do not grow.
- **R6.17.4, the decision row P366,** retiring P51's and P67's "style.css stays unedited" (P309 ended the merges they
  protected; Q-D).

**Tests:** `test_pilot_ui`, `test_shell`, `test_shell_menu` (`pageBackground` reads `pilot-ui.css`), `test_pilot`,
`test_single_source`, `test_layers`, `test_repo_map`, `test_tripwire`.

**Accept when:** the comparison's dumps are identical; the count of selectors in more than one sheet is given before and
after with the residue listed; every stylesheet test passes.
- **Windows:** no label. **Office `-Tests`:** `test_pilot_ui,test_shell`. Installer step. Hands-on: every page in light,
  dark and a Windows contrast theme, at 1100 x 700, compared with the build before (screenshots side by side).

---

### P6.18 Phase 5's loose ends; the phase's close

- **Cost:** S.
- **Tier:** Sonnet.
- **Findings:** the carried items.
- **Depends on:** P6.17 (or P6.16).

**Requirements:**

- **R6.18.1, seven curated notes** that say reads through the old modules "wait for P5.16" (screen_words's node; the
  test-file nodes of request_edit/household_edit, creation, firm_view, run_log, status_page, pass_order) say what is
  true: the reads come from the defining module since P5.16 (`MOVED_OUT`).
- **R6.18.2, the runner node** names the `run_log` and status-page names it still says bare (`append_log`,
  `why_skipped`, `last_pass_line`, `log_counts`, `_warn`, `_log_file`; `STATUS_PAGE_FILENAME`, `STATUS_HELD`,
  `STATUS_IGNORED_HEADING`) by their homes.
- **R6.18.3, P4.13's guard walks `pilot/` and `api_entry.py` too** (`tests/test_layers.py`'s `MOVED_OUT` walk); a read
  found there is retargeted.
- **R6.18.4, the phase's close.**
  - after.txt gives each split script's length, the final `SEAMS` pair count and the `WRITES` rows (eighteen
    expected: five, nine, four).
  - `PLANNED` (R6.1.3) is deleted once every one of its sixteen names is in `RENDERER_SCRIPTS` or `MAIN_SCRIPTS`
    (asserted before the deletion). A name P6.17's absence leaves out has none, since P6.17 creates no script.
  - `docs/architecture.md`'s desktop-app sentence (16) is checked and corrected if a split made it false.
- **R6.18.5, the engine's prose names the module that holds the code** (review 1's S16; chosen over a decision row
  that would let "`main.js`" mean the main process, because a reader greps the name a comment gives). Comments and
  docstrings that name `main.js` for code P6.13 and P6.15 moved name the module it now sits in. Measured at
  `9df1724`:
  - `tracker/resident.py` 7, 19, 48, 112-120 (the engine's framing and limits: `engine.js`);
  - `tracker/progress.py` 52 (`PROGRESS_KEY`: `engine.js`);
  - `tracker/api.py` 912 (the payload as written: `engine.js`), 1254 (the shell's default words and the error log:
    `shell-words.js` and `logs.js`), 1266 (the last-pass file: `last-pass-watch.js`), 4803 (the early and held lists:
    `engine.js`); 2479 is re-read and changed only if it names moved code;
  - `tracker/screen_words.py` 132-136 and 633 (the shell's words and the writing commands: `shell-words.js`,
    `engine.js`).

  A sentence about the process as a whole (the window, the IPC, the lifecycle) keeps `main.js`. The job re-greps
  `tracker/`, `tools/` and `api_entry.py` for `main.js` and lists every hit with what it became or why it stays. Only
  comment and docstring lines change: after.txt shows each edited module's AST, with docstrings removed, is identical
  before and after (`ast.dump`). A test that reads one of those sentences (grep `tests/` for each edited phrase)
  follows.

**Tests:** `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`, `test_renderer_seams` (R6.18.4), any
test file R6.18.3 edits, and, for R6.18.5's prose-only edits (AST unchanged), each edited module's own test file
only: `test_resident`, `test_progress`, `test_screen_words`, `test_api`.

**Accept when:** `grep -n "wait for P5.16" docs/repo-map.curated.json` is empty; the walk's guard passes over
`pilot/` and `api_entry.py`; `PLANNED` is gone; every `main.js` in `tracker/` is on R6.18.5's list as staying.
- **Windows:** no label. **Office `-Tests`:** none of its own.

## 5. Risks

- **A guard that silently stops covering moved code** (D-5), the phase's main risk. The nets: P6.1's named-script
  guard (no test reads a split script by name but `FILE_NAMED`), P6.2 and P6.3's retarget by claim before anything
  moves, section 4.1's planted-fault check per guard per new script, and the seam table. The quietest gap is a claim
  about `app.js`'s code that only holds while the other app scripts are left out (review 3's S24): it reads
  `APP_FAMILY`, never `FILE_NAMED`, P6.2's before.txt runs every retargeted count and absence over both sets to find
  each one, and every move job plants a fault for each in its new scripts (R6.2.1, section 4.1).
- **The load order.** A script carved out of `app.js` runs before `app.js` and must hold declarations only; a binding
  read at load before it exists throws, and the page would draw nothing. P6.1's load test runs every script in order in
  one scope on every commit, and shoot.mjs draws the page in Chromium in each move job; the office's hands-on check is
  the proof on the machine.
- **Strict mode.** Moving sloppy code into a strict script changes how it runs; section 3 keeps each script in its
  source's mode.
- **Writes across scripts grow** from five to eighteen (sections 4.0 and P6.12). Each is a write the code already made;
  phase 7's owner objects take them (D-2). The table names every one, so none is added unseen.
- **The main process's modules.** `main.js`'s names were one scope; as modules each needs its state handed over or
  owned: the window is read through a getter and two constants are declared again (section 3, R6.13.1, R6.14.1,
  R6.15.1), each line named. A missed name is a `ReferenceError` at the first command; `test_shell_menu`'s scenarios run the real
  `main.js` under a fake Electron through every channel, and the office's installer step is the proof. Two Mac paths
  move (`SETTINGS_DIR`, `NOT_SET_UP_MAC`): R6.15.3 and section 6.
- **D-3 changes what the engine sends.** A field that differs from the page's old answer would change a count, the
  Hand Over list or a name. The safeguards:
  - P6.5's oracle holds each field to the page's retired rule on a pile that holds every group, a set-aside file, a
    moved-by-hand file and one marked missing, and the feed cases. The drawn groups are held to the tally too, the
    page's four tally tests keep their claims against the retired rule, and R6.5.5 shows the feed list's duplicates
    cannot arise. Between `select()` and the next `render` the page and the engine leave out different returns, and
    a row menu can ask in that gap, so the page keeps its own rule there (R6.5.5).
  - **The taxpayer's windows.** A name cut from the firm reply would differ from the page's whenever the firm reply
    and the list are from different moments. So P6.6 cuts it on the list's rows only, and the firm lists read the
    list's. Its oracle runs each window on the page's own inputs, and the page keeps its own cut for the one case only
    it can answer. The engine's cut for the list rows uses the page's own trim (`PAGE_TRIM`), since Python's and
    JavaScript's strip different characters (R6.6.1).
  - The firm reply's shape is untouched by P6.6, so nothing a cache or a saved view kept goes stale (R6.6.5).
- **The fold** (P6.17) is proven only on the states the harness draws (hover and focus are not dumped). R6.17.1's part
  is provably safe; R6.17.2 merges only what the dumps hold equal and lists the rest.

## 6. Owed to the office PC

Everything here runs on the office PC with the program's checkout or the installed build, never against a real clients
root's data from the suite; no generative AI reads a document. The phase does not reach the sorting engine, so no
backtest is owed by it.

**1. The stack's one Windows check.** Once, on the stack's head: `pilot\wintest\run_checks.ps1 -Tests` with the union of
the jobs' lists - the renderer's readers, the main process's readers, `test_editor`, `test_firm_view`, `test_firm_pages`,
`test_firm_cache`, `test_golden`, `test_resident`, `test_pilot_ui` - plus `test_layers,test_repo_map,test_tripwire`.
The script builds the installer beside the tests.

**2. The installer step and the hands-on checks.** Install the stack's build over the current one. Then the hands-on
steps of P6.4-P6.17 in one pass, each "the same as before": the tour's count; Hand Over and the counts following a
write; every taxpayer on the four lists; the notices and the four menu dialogs; Check a file and Draft Reminder in the
side sheet; New Household, Edit Household and Roll Forward; the editor (virtual rows, paste, rename, save, the unsaved
bar); Sort Now and Stop, Schedule and Repair the Schedule; the counts at launch and a scheduled pass seen while open;
opening a document and its folder, the error log; every menu, accelerator and right-click; closing during a Sort; the
terms, the badge and the tour on a fresh profile; and, if P6.17 is built, every page in light, dark and contrast
compared with the build before.

**3. Mac.** P6.13-P6.15 reach `main.js`'s Mac paths. The next scheduled Mac check (`pilot/mactest/run_checks.sh`, its
widened list) runs as it is, and adds: `test_shell_menu`, `test_single_source`, `test_shell`, `test_build`,
`test_renderer_seams` (each already in `KIT_TESTS` or `KIT_TESTS_SPLIT`), and by hand: the app starts (the floor passes
on Apple silicon, macOS 14 or later); the menu shows no `&`; Remove Schedule Here is in Tools; a file in
`carries_code` opens with Protected View's sentence said; the settings file is under Application Support; a Sort and a
quit during it. No list changes: no test file is split out of a listed one in this phase.

**Still owed from earlier phases** (they touch none of this phase's code and can run in the same visit): P3.8's
read-only `verify`; phase 4's two backtests (on the builds at `68b9212` and `f15eed1`, which must agree); P4.1, P4.4,
P4.6, P4.9 and P4.12's lists and hands-on steps; phase 5's section 6 (the scheduled pass on the installed build, the
Overview after it, Setup's last step, the stack's Windows check).

## 7. Questions for Jason

**Answered by Jason on 2026-11-08:** Q-D **(A)**, fold them (P6.17 is built); Q-E **yes, plan it now**: a job that type-checks the window's JavaScript with TypeScript's checker as a development-only tool reading JSDoc comments (no build step; the app still ships plain JavaScript, Setup installs nothing new) is planned for phase 7's SPEC, after phase 6 has split the scripts, with the package and its pinned version named there; Q-G **(A)**, keep the pilot's failed save silent (P6.16 builds `appReady` only, as written). The questions stay below as he was asked them.

**Q-D. Should the stylesheets' overridden rules be folded into one home now?**

Today `style.css` is never edited: the newer look in `pilot-ui.css` and `shell.css` overrides it rule by rule (decisions
P51 and P67), because the original app's merges kept arriving. P309 ended those merges. 65 rules are now written in two
or three files, and a change to one has to be checked against the others.
- **(A) Yes, fold them (recommended).** P6.17 deletes every declaration that is always overridden (provably no change),
  and merges the rest into one file only where a check of every element on every screen the harness draws, in light,
  dark and contrast, shows nothing changes; any it cannot prove stays and is listed. Nothing a person sees changes.
- **(B) No, leave the stylesheets as they are.** P6.17 is not built.

**Q-E. Should the window's JavaScript be type-checked, as the engine's Python now is?**

TypeScript's checker can read type notes written as comments in plain JavaScript, as a development-only tool; the app
would still ship plain JavaScript and Setup would install nothing new. *Recommended: decide after phase 6*, once the
scripts are small enough to annotate one at a time. Nothing in phase 6 depends on the answer.

**Q-G. Should a failure to save the pilot's record show a notice, like every other command's failure?**

The pilot's terms and tour are recorded by one command. Today, if that command fails or warns, nothing is shown; the
reason goes only to the error log. Every other command shows its failure as a notice with Retry (decision 193).
- **(A) Keep it silent (what phase 6 builds).** Nothing changes.
- **(B) Show it like every other command (the audit's recommendation, D-6).** A tester whose record could not be saved
  would see why; a later job routes the pilot through the page's one `call()`.

**Carried, not asked again:**
- Q-B (the re-send road's shortlist) stays open as P313 left it; nothing in phase 6 touches it.
- Review 1 asked whether D-3(c) might show the firm reply's name in the moments when the list and the firm reply
  disagree. The brief settles it (threads/P6/003): nothing a person sees changes. P6.6 removes the difference, so it
  is not asked.

**For a later phase (no answer needed now):**
- Phase 7: each renderer script's state in one owner object, with the eighteen `WRITES` rows and the loose `let`s of
  `firm-loader.js` folded into it (D-2, D-7).
- `tests/test_shell.py` (8,284 lines) split by the scripts it tests, with `KIT_TESTS_SPLIT` widened by P351's rule.
- Prose in files no phase 6 job edits: `scanner.py` 952 ("the runner's LOG_FILENAME"), `copies.py` 67 and the store's
  `forget` docstring (creation's undo). And `screen_words.py` 1069, `CLIENT_FOLDER_TAKEN`'s typed copy of the misfits
  heading, filled from `status_page.STATUS_MISFITS_HEADING` (a sentence a person reads, so a word change).
- After phase 7, a package-wide decision on the private names one module imports from another (measured then).
