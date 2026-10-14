# SPEC — Architecture: the audit, the target shape, and the refactor in phases

Written 2026-10-13 from a read-only audit of `main` at `2741665` (pull request
#55), at Jason's request for "a comprehensive, phased refactor to bring this
codebase up to production-grade standards". Nothing in this SPEC has been
built. The evidence, with every `file:line`, is
[`AUDIT-2026-10-13-architecture.md`](AUDIT-2026-10-13-architecture.md); this
file cites it by finding (A-1, B-2, ...). Jason took three decisions in the
session that wrote it (P309 to P311, section 2), then directed the whole plan
built in an orchestrated loop (P312), with its open questions answered
meanwhile as P313 says. **Tranche 1 (phases 0 and 1, jobs J1 to J6, section
8) is buildable now.** Phases 2 to 7 (section 9) each get their own SPEC,
written from the code as it then is, once the phase before has landed.
Section 13 is the ledger of what has landed.

Each job is its own agent that reads this file, `pilot/PROMPT-refactor.md` and
the loop's board, never the transcript of the session that wrote it.

## 1. The answer

**The codebase is not unstructured, but five files grew too big and the
tests are tied to where code sits.** The brief expected a system built with
no design. That is not what the audit found. The app already has a layered
design that a test enforces: six layers, and no file may lean on a layer
above it. Its four standing rules are enforced by tests. Every change to a
client's record goes through one door. Every sentence a person reads is
written in one place. What the audit did find, in order of how much it gets
in the way of a safe change:

1. **Five "god modules"** (a god module is a file that does many unrelated
   jobs, so any change to it risks the others):

   | File | Lines | Jobs in it | Finding |
   |---|---|---|---|
   | `tracker/filer.py` | 7,878 | 11: sorting, copying, the index, crash recovery, a person's actions, ... | A-1 |
   | `tracker/api.py` | 6,810 | 8, including business rules its own header says it does not hold | C-1 |
   | `app/renderer/app.js` | 4,283 | 17: the request-list editor, the review sheet, dialogs, the engine calls, ... | D-1 |
   | `tracker/store.py` | 4,143 | 18: the database, the gate that checks every record line, the audit, recovery, ... | B-1 |
   | `tracker/runner.py` | 3,652 | 6: the pass, the run log, the practice status page, ... | C-5 |

   Six more mix two or three jobs each: `content_check.py`, `ocr.py`,
   `settings.py`, `reminder.py`, `shell.js`, `main.js`.

2. **Coupling caused by where code sits, not by design.** The index's words
   ("Filed", "Needs Review") live in the sorter, so eight modules import the
   whole sorter to read a row (A-2). The code that builds the firm's lists
   lives in the top layer, so the scheduled pass starts a second copy of the
   engine as a child process just to fill a cache (C-2). The eight screen
   scripts share about a hundred names through one global scope, with no
   written boundary between them (D-2).

3. **State that outlives its command.** Since P276 one engine process serves
   up to 500 of the app's commands in a row. Some module-level lists and flags
   were written when every command had a process of its own, and nothing
   resets them now. One is a real leak: a file the reader could not start on
   is remembered and never said (A-7, C-3).

4. **The same rule written twice.** Five rules exist in both the engine and
   the screen code: who a document may be handed to, a return's counts, the
   group names, the taxpayer's name cut, the list's columns (D-3). Inside the
   engine, the check on a Windows file name is written three times (B-3), and
   the step after routing a document is written twice, and the two copies
   already differ (A-3).

5. **Types declared but never checked.** 92% of the engine's functions say
   what kind of value they take and return, but nothing checks it; a first
   check found 209 mistakes (E-5). The messages between the engine and the
   screen have no written description of their shape (C-4).

**The bigger risk is the tests, not the code.** 288 tests check the exact
text of a code file. 228 places in the tests cut a JavaScript function out of
its file by its exact first line. Tests reach 232 names the code marks as
private. About 130 tests swap in a stand-in for one piece of the engine by
name ("monkeypatching"), and a stand-in like that quietly stops applying once
the code it stood in for moves to another file. Then the test passes while
testing nothing (A-4, E-1, E-2). Several guards, the no-network test among
them, look only at files sitting directly in `tracker/`, so a file in a
subfolder would escape them (C-1). So moving code first would swap a visible
risk for an invisible one.

**So the work goes in two tranches.** Tranche 1 makes the tests tell code
that *moved* from code that *changed*, fixes the defects the audit found, and
adds the type checker (six build jobs). Then the big files are split, one
domain at a time, each move proved by the tests built in tranche 1 (about 25
more build jobs, about 31 in all). Nothing the app does changes, apart from
the defects named in section 4.1.

## 2. Decisions taken (Jason, 2026-10-13, rows P309 to P311)

1. **P309. The pilot is the one codebase.** Nothing more is merged from the
   original `J-Park-Associates/Tax-Info-Request-List`; a fix it gets is copied
   across by hand. That ends P17's hand merge and retires P7 and P10, which
   kept pilot code additive so merges stayed clean. P160 stays open for the
   rest of the fold (the office PC's move, when the original stops taking
   changes). Job J1 rewrites `pilot/README.md` rules 1 and 3 to match.
2. **P310. mypy, as a development-only tool.** It is installed from its own
   hash-checked lock, never by Setup, a build or the app, and never frozen
   into a package. The gate fails if any file gains a type error; each phase
   lowers the count. Job J6.
3. **P311. Tranches.** Tranche 1 is phases 0 and 1 (jobs J1 to J6). No
   module is split until it has landed. (Its wait for Jason's word before
   phase 2 is superseded by P312.)
4. **P312. The whole plan, in a loop.** The refactor is built to the end in
   an orchestrated loop: Sonnet builds, Opus builds the difficult jobs, Opus
   reviews at high effort in an agent that did not build, and the loop stops
   only where `pilot/PROMPT-refactor.md` section 1.2 says. The agents
   coordinate through a board outside the repository. Opening and landing
   the pull request stays a person's step.
5. **P313. The questions, meanwhile.** Section 11's questions are built as
   P313 says: the technical ones as recommended, and wherever an answer
   would change what a person sees or what a pass does, today's behaviour is
   kept and the question stays Jason's.

## 3. What was audited, and how

Five reviewers on Opus at high effort, one slice each, in parallel because the
slices are independent reads: A the sorting engine, B the record and the
store, C the door, the pass and the schedule, D the Electron shell, E the
guards, tests, tools and build. Each one checked `docs/ROADMAP.md` and
`pilot/DECISIONS.md` before calling anything wrong, and marks every finding
**accidental** (no decision explains it), **deliberate** (a decision explains
it and the reason holds) or **outgrown** (a decision explains it, but the code
has outgrown the reason). Nothing was edited and nothing was installed.

| Measure | Value |
|---|---|
| `tracker/` | 38 modules, 60.7k lines, 92% of functions fully annotated |
| `app/` (JS, HTML, CSS, not vendor) | 13k lines, 0 JSDoc type tags |
| `tests/` | 65 files, 95k lines, 3,626 test functions |
| `tools/` | 7 files, 4.3k lines |
| Load-time import cycles | 0 (call-time cycles: filer↔scanner, declared; five more, undeclared, A-9) |
| Tests that read a code file's text | 288 |
| JS functions the tests lift by name | 235 |
| Test references to private names | 885, to 232 names |
| Monkeypatches on a module's namespace | ~130 that a move could silently disarm (73 on filer, 39 on api, 19 on runner) |
| mypy, first run | 209 errors in 31 files, ~9 of them platform false positives |

## 4. Findings, by theme

Severity is the reviewer's: **high** means it makes a correct change hard or
risky today. Every row's evidence and proposed seam are in the appendix.

### 4.1 Defects found on the way

These are real faults or gaps, not matters of shape. Tranche 1 fixes the
first eight.

| # | What | Finding | Fixed in |
|---|---|---|---|
| 1 | The store's admission fingerprint (the test that forces a version bump when the record's gate changes) follows a parameter named `kind` into the function `store.kind`, so about 28 of its 271 entries hash code the gate never runs, settings' Mac seam among them. An unrelated edit trips it, which trains people to re-pin without looking. | B-2 | J1 |
| 2 | In the app's engine, a file the reader could not start on is added to `content_check._COULD_NOT_START` and never said or cleared; only a scheduled pass drains it. The names pile up until the engine retires. | A-7 | J5 |
| 3 | The Mac's "this volume refuses a full flush" warning is said once per engine session instead of once per command, as it was before P276. | C-3 | J5 |
| 4 | Three sentences are typed in `app.js` (`fileRow`'s notes) instead of coming from the engine, against P63. The guard against typed words does not read `app.js`. | D-9 | J3 (guard), J5 (fix) |
| 5 | The guards that keep the page safe (no `innerHTML`, only commands the API has, no typed words) read `app.js` alone; code in the other seven scripts is not checked. The gate syntax-checks 3 of 10 script files. | D-5, E-11 | J3 |
| 6 | `Build App.bat`, which builds the package the office carries on a USB stick, never checks that the package holds no store, log or settings file; only the CI build does. | E-10 | J6 |
| 7 | The harness's stand-in for `app.js` lacks eight names the other scripts call, so the in-browser harness throws on those paths. | D-8 | J3 |
| 8 | Four of the main process's five message channels do not check that the message came from the app's own window. Low risk with one window and navigation denied. | D-10 | J5 |
| 9 | The step after routing is written twice in `filer.py`; on the re-send road a document parked across households carries no shortlist (`candidates=""`), where the first road carries the home return's. Which is right is Jason's (section 11, Q-B). | A-3 | Phase 4 |
| 10 | `filer.refuse_a_path_past_the_limit` says the editor's save refuses through it; the editor has its own check (`api._refuse_a_changed_row_past_the_limit`) that leaves out the review folder's length. The review folder does not change with an edit, so this is probably harmless; the claim is false either way. | B-3 | Phase 5 (Q-F) |
| 11 | `docs/backtest-baseline.json` records no agreement yet, so "no routing change may lower the baseline" has nothing to compare against. Deliberate until the office runs the backtest (decision 71); listed because Phase 4 moves routing code. | E-7 | Office run before Phase 4 |

### 4.2 God modules and mixed concerns

| Module | Severity | Split proposed | Finding |
|---|---|---|---|
| `filer.py` | high | `index`, `copies`, `intents`, `inbox`, `readme_ack`, `actions`; filer keeps the household pass and the decision (~3,600 lines) | A-1 |
| `api.py` | high | `screen_words`, `request_edit`, `household_edit`, `creation`, `firm_view`; api keeps `COMMANDS`, the envelope, `_vocab`, thin handlers | C-1, C-2 |
| `app.js` | high | `api-client`, `notices`, `dialogs`, `reminder`, `review`, `household`, `editor`, `schedule`, `pass`; app.js keeps the state, `bootstrap` and the wiring | D-1 |
| `store.py` | high | `admission`, `store_check`, `verify`; store keeps the connection, schema, writes, rebuild and recovery (~3,000 lines) | B-1, B-7 |
| `runner.py` | medium | `status_page`, `run_log`, `pass_order` | C-5 |
| `content_check.py` | medium | `keywords` (pure text rules), `verdicts` (the cache) | A-5 |
| `ocr.py` | medium | `reader_child` (the child process and its supervisor) | A-6 |
| `settings.py` | medium | `hold` (the per-reply memo), `errlog` (the rotating error log) | B-5 |
| `shell.js` | medium | `firm-loader.js` (a 30-flag loading state machine) | D-7 |
| `main.js` | medium | `engine.js`, `open-path.js`, `menu.js`, `logs.js` | D-4 |
| `reminder.py`, `records.py` | low | `letter_render`, `bounds` | C-8, B-11 |

### 4.3 Coupling

- The index's words and readers sit in the sorter (L3); scanner, review,
  reminder, view, rollover and even the store (L1, at call time) import the
  sorter to read them. The scanner's half of the "deliberate" filer↔scanner
  cycle is index reading, not sorting (A-2).
- The firm-row builder sits at L5, so the pass runs `python -m tracker.api
  firm` as a child just to fill the firm cache (C-2, P201).
- The API composes record events itself in two commands, around the domain
  writers that own them (B-4).
- settings and store each ask the other where the data lives (B-6); five
  call-time cycles are undeclared (A-9).
- The renderer's scripts use each other's globals freely: shell.js uses 45
  of app.js's names, 12 of them data, against about 8 in its documented
  interface. Nothing indexes or checks it (D-2).
- `pilot.js` polls for the `vocab` global and calls the bridge directly,
  workarounds for P10, which P309 retires (D-6).

### 4.4 State

- Per-command state in api is three module globals, cleared in two places;
  the resident reaches api's private names to clear them (C-3).
- Process-wide flags (`_full_sync_said` twice, `_redirect_answer`,
  `_last_line`, `_COULD_NOT_START`) have no declared lifetime (A-7, C-3).
- The store's one connection per process is six loose globals (B-12;
  deliberate, worth one object).
- In filer, per-drop state is threaded through a shared context mutated in
  place and restored in `finally` (A-11).
- In the renderer, shared `let`s are written from other files (D-2), and
  `shell.js` keeps 30 loading flags in loose `let`s (D-7).

### 4.5 Duplicated logic

- Python and JavaScript: who a document may be handed to, a return's tally,
  the group keys, the taxpayer cut, the list columns (D-3).
- Within Python: the Windows file-name part check ×3, four sanitisers of one
  character set, the identifier rule invoked four times in one save, the
  typed-input rules in three modules (B-3); the after-routing step ×2 (A-3);
  the learned-keyword fold ×3 (B-9); four "is this a Mac" probes (B-10);
  the HTML page skeleton ×2 (C-9); a refusal sentence typed inline five
  times (A-10); the error envelope built in three places (C-4).
- In the tests: three hand-built PDF writers, an `engagement` fixture defined
  eleven times, seven separate JS function lifters, 24 test files importing
  helpers from 14 other test files, which the affected-tests gate cannot see
  (E-4, E-1).

### 4.6 Typing and the contract

- 92% annotated, 0% checked; mypy finds 209 errors, mostly an optional value
  used without a check and parameters typed `object` (E-5).
- Journal events and rule rows are bare `dict`s after the gate has admitted
  them (B-8; at the boundary that is deliberate, decisions 103 and 187).
- The engine-to-screen JSON has no written shape; the screen compares failure
  kinds by literal (`"stale"`, `"refused"`), and only one is pinned (C-4).
- `filer._park_it` takes `candidates` as a tuple or a string (A-8).

### 4.7 The tests as the refactor's risk

- 288 tests pin code text; the fragile ones slice a body by an exact
  signature or count call sites (E-1).
- 885 private-name references; `api._vocab` alone 75 times (E-2).
- ~130 monkeypatches on a module namespace, most on names that module
  imported from elsewhere, so they apply only while the caller sits in that
  module (A-4, C-1, C-5).
- Four guards in `test_layers.py` read `tracker/*.py` without descending into
  folders (lines 294, 338, 488, 750), the no-network test (488) among them, as
  do several in `test_single_source.py` and `test_api.py`'s derivation of
  `WRITING_COMMANDS` (C-1). The import allowlist test (`_tracker_trees`, 499)
  does descend, so a forbidden import in a subfolder would still fail there;
  the others would not see the file at all.
- Six test files are over 5,000 lines and mirror the god modules, so the
  affected-tests gate reruns most of the suite for any edit to api (E-3).
- `conftest.py` is 1,370 lines of nine concerns (E-6).
- Missing nets: no recorded reply shape, no recorded pass over the sample
  pile (E-7).

### 4.8 Looks wrong, is deliberate (leave alone)

Each has a decision row; the appendix lists them per slice. The ones a
refactor is most tempted to "fix": `router._decide` is long on purpose
(decision 51); the exactly-one rule applied per list in the router and across
returns in filer (decision 128); the filer→scanner rescan (decisions 95, 99);
the regular expressions that read the firm's own sentence tails (decision 190);
the two identical `full_sync` copies (SPEC-mac R22); the engine's words sent
from Python and the shell's early words typed in main.js and pinned (decisions
42, 193, P69); one store connection per process (decision 101); the gate
narrower than the typed rule (P290, P291, P301); rule rows as dicts at the
boundary (decisions 103, 187); `runner` never importing `api` or `scheduling`
(decision 99: fix the coupling by moving the builder down, never by relaxing
the rule); the Windows and Mac script pairs (SPEC-mac R16, P254); the two
virtual lists (P279); `_undo_create`'s `rmtree`, reached only on folders the
call made (decision 137).

## 5. The target architecture

### 5.1 Principles

1. **The standing rules hold, unchanged and still enforced.** No step in this
   plan reads a document differently, writes an original, guesses, or sends.
   A module that carries a rule out (the enforcers in `test_repo_map.py`)
   keeps carrying it after a move, and the enforcer list moves with it.
2. **The layer table is the domain boundary.** `tests/test_layers.py` already
   says which module sits in which layer and forbids leaning upward. The plan
   adds a *domain* column to that table (record, reading, sorting, pass, door,
   shell) so the grouping a folder tree would show is written down and
   checked.
3. **Flat modules, not subpackages.** New modules sit directly in `tracker/`.
   A `tracker/sorting/` folder would (a) escape the no-network test and the
   other guards that read only `tracker/*.py` until each is widened, (b)
   change every `from tracker.x import` path
   across 95k lines of tests, ~130 patch targets and 288 text pins, the
   runbook and the map, and (c) buy nothing the layer table does not already
   enforce. Revisit only after phase 7, if ever.
4. **A move is a move.** A function moves byte for byte, with its words. Its
   old module keeps re-exporting the public names that moved (a "facade": the
   old address still answers, pinned by an identity test as
   `tests/test_records.py::RE_EXPORTED` pins decision 100's). Each phase
   ends with a job that points the remaining importers at the new home and
   removes the facade, so shims do not linger the way decision 100's did
   (A-12).
5. **The door is thin.** An API handler parses its arguments, calls one
   domain function, and shapes the reply. Any rule lives in a module the pass
   and a command line can also reach (the lesson of decision 123).
6. **One written contract between the engine and the screen.**
   `tracker/replies.py` describes every reply's shape as a `TypedDict` (a
   standard-library way to write down a dictionary's keys and their types).
   The harness stub, the recorded replies and the JavaScript are held to it.
7. **Every piece of mutable state has a declared owner and lifetime.** A
   register says which module-level state lives per process and which is
   reset per command (J5); per-command context becomes explicit (phase 7).
   In the renderer, each script owns its state and others change it through
   that script's functions.
8. **No new runtime dependency.** Plain JavaScript in classic scripts, no
   bundler, no framework, no TypeScript compiler in the build: the tests lift
   functions as text, and every dependency is one more thing the firm must
   trust. The one new tool is mypy, development-only (P310).
9. **The engine decides; the screen draws.** Where the screen re-derives a
   result the engine already has (D-3), the engine sends the result.

### 5.2 Data flow and its boundaries

```
 A person
   │
   ▼
 Screen — app/renderer/*.js, classic scripts in index.html order.
   Draws, decides nothing. Each script owns its state; cross-script names
   are pinned by tests/test_renderer_seams.py.
   │  window.tracker.call(argv, payload)       (preload: nine members, no Node)
   ▼
 Main process — app/main.js + engine.js, open-path.js, menu.js, logs.js.
   Allowlist from the vocabulary, sender checked, one resident engine.
   │  one JSON line + payload on stdin; progress lines and one reply on stdout
   ▼
 L5 door ──── api.py (COMMANDS, envelope, _vocab, thin handlers) · resident.py
   │          replies.py: the written shape of every reply
   ▼
 L4 unattended ── runner.py (the pass) · firm_view.py · pass_order.py
   │              after_install.py · scheduling.py
   ▼
 L3 stages ── filer.py (sort a household's inbox) · actions.py (a person's
   │          actions) · intents.py · inbox.py · scanner.py · reminder.py
   │          review.py · rollover.py · registry.py · view.py · status_page.py
   │          run_log.py · request_edit.py · household_edit.py · creation.py
   │          verify.py
   ▼
 L2 reading ── content_check.py (the one reading) · keywords.py · verdicts.py
   │           router.py · names.py · containers.py · ocr.py · reader_child.py
   │           copies.py
   ▼
 L1 record ── store.py → admission.py → ledger.append (the one door into
   │          the record) · index.py · store_check.py · manifest.py
   │          records.py · templates.py · households.py · scaffold.py
   │          validators.py · screen_words.py
   ▼
 L0 basics ── layout.py · door.py · fsio.py (the one writer) · locking.py
              ledger.py · checkpoint.py · settings.py · hold.py · errlog.py
              bounds.py · reasons.py · errors.py · page.py · progress.py
              replies.py · letter_render.py · firm_cache.py · page_rows.py
              firm_pages.py
```

Three boundaries carry the weight:

- **Screen to engine:** only allowlisted commands, from the app's own window,
  shaped as `replies.py` says. The screen holds no rule the engine also holds.
- **Door to domain:** the door holds no business rule. A rule the pass or a
  command line needs is in L1 to L4.
- **Anything to the record:** one door, `store.record`, which admits every
  line through `admission` before `ledger.append`. A guard test keeps
  `ledger.new(` out of the door (B-4).

### 5.3 New modules, by layer

The layer each takes is what its imports allow; the build job confirms it.

| New module | Layer | Comes from | Finding |
|---|---|---|---|
| `hold.py` | L0 | `settings` 1099-1254 | B-5 |
| `errlog.py` | L0 | `settings` 345-456 | B-5 |
| `bounds.py` | L0 | `records` 1444-2172 (value rules) | B-11 |
| `replies.py` | L0 | new: the reply shapes | C-4 |
| `letter_render.py` | L0 or L1 | `reminder` rendering | C-8 |
| `index.py` | L1 | `filer` decision words, `read_index`, `ensure`, tail readers | A-2 |
| `admission.py` | L1 | `store` 1686-2077 | B-1, B-7 |
| `store_check.py` | L1 | `store` check and export | B-1 |
| `screen_words.py` | L1 | `api` screen-word constants | C-1, C-6 |
| `copies.py` | L2 | `filer` naming, room, copy and move, temp sweep | A-1 |
| `keywords.py` | L2 | `content_check` 326-1368 | A-5 |
| `verdicts.py` | L2 | `content_check` `ContentCache` | A-5 |
| `reader_child.py` | L2 | `ocr` 1008-1898, `content_check.in_a_child` | A-6 |
| `intents.py` | L3 | `filer` write-ahead intents and finishing them | A-1 |
| `inbox.py` | L3 | `filer` walking the inbox | A-1 |
| `readme_ack.py` | L3 | `filer` client README acknowledgement | A-1 |
| `actions.py` | L3 | `filer` assign, dismiss, unfile, restore, rename, mark missing | A-1 |
| `verify.py` | L3 | `store.verify` | B-1 |
| `status_page.py` | L3 | `runner` practice status page | C-5 |
| `run_log.py` | L3 | `runner` run log and last pass | C-5 |
| `request_edit.py` | L3 | `api` the editor's save | C-1 |
| `household_edit.py` | L3 | `api` household edits and related returns | C-1 |
| `creation.py` | L3 or L4 | `api` the create transaction and its undo | C-1 |
| `firm_view.py` | L4 | `api` the firm-row builder and the group rule | C-2 |
| `pass_order.py` | L4 | `runner` the household order hint | C-5 |

After phase 7 no module in `tracker/` should be over about 3,600 lines.

### 5.4 The shell after phases 6 and 7

`app/renderer/`: `api-client.js` (the one `call()`, `withEng`, `writeRow`),
`notices.js`, `dialogs.js` (the one dialog registry, decision 201),
`reminder.js`, `review.js`, `household.js`, `editor.js`, `schedule.js`,
`pass.js`, `firm-loader.js`, and `app.js` (state, `applyVocabulary`,
`bootstrap`, the one keydown listener of P76, the wiring). The global names
stay the same, so `shell.js`, `pages.js` and `sheet.js` keep working while
the split lands. `app/`: `main.js` (window, IPC registration, lifecycle) with
`engine.js`, `open-path.js`, `menu.js`, `logs.js` and `last-pass-watch.js`,
required by plain path.

### 5.5 What does not change

The record format, the store schema, the folder layout on the drive, the
vocabulary the screen reads, every sentence a person sees (apart from section
4.1 item 4, which moves three sentences from the page to the engine with the
same words), the package layout, the installer, the schedule. No phase
changes `SCHEMA_VERSION` or `ADMISSION_VERSION`; a job that finds it must
stops and asks.

## 6. Rules for every job

- **Behaviour does not change** outside the defects a job names. A move
  commit moves code and nothing else.
- **The standing rules, `tests/test_layers.py` and the single-source tests
  hold.** A module that changes layer, or a new module, gets its `LAYERS`
  row and a decision row in the same commit.
- **Retarget before you move.** Before code leaves a module, every
  monkeypatch on a name that code reads is pointed at the module the code
  will live in, in the same commit (after J4, `tools/patch_sites.py report`
  lists them).
- **The map in the same commit.** Edit `docs/repo-map.curated.json` where a
  module's purpose, an enforcer or a curated edge changes, then `python
  tools/repo_map.py update`. A new file is `git add`-ed before `update`.
- **The gate before every push (decisions 207, 211; Jason 2026-09-29):**
  dead code in the changed files first; then the job's named test files,
  each as its own process, under the floor interpreter (3.11) and the
  office's (3.14); then `python -m ruff check .`, `python tools/repo_map.py
  check`, `python tools/vocab_report.py check` when routing is touched, and
  after J6 `python tools/typecheck.py check`. Never the whole suite unless a
  job reaches the sorting engine and says so.
- **Sonnet builds; Opus builds the difficult jobs; Opus reviews at high
  effort in an agent that did not build** (P312; the tier rule is
  `pilot/PROMPT-refactor.md` section 1.3, and each job below names its tier).
  Numbered findings against this SPEC. A rebuild fixes the findings and
  nothing more and reruns only the tests the fixes touch. A finding that
  survives one rebuild is fixed by Opus itself; if that fails review, the
  loop stops and tells Jason.
- **No client data, anywhere.** Recordings and fixtures come from
  `tests/samples.py`'s made-up pile only. No build session points at a real
  clients root; the tripwire (decision 185) fails the run if one does.
- **Land in bulk.** Each tranche is one draft pull request, each job its own
  commits in the order of section 8, marked ready once when the stack is
  final, landed with a merge commit (decision 211). The `windows` label goes
  on when a job touches the engagement lock, the atomic replace, path handling
  or a Windows-only script (J6; phase 4's `reader_child`).
- **Each job ends** with its handoff in the pull request description (branch,
  commits, what it did and skipped, the commands run with their last line,
  what the reviewer should read first), as `pilot/HANDOFF.md` says.

## 7. The phases

| Phase | What | Jobs | Tranche |
|---|---|---|---|
| 0 | Safety nets: the tests tell a move from a change | J1-J4 | 1 |
| 1 | Defects, the state register, the type checker | J5, J6 | 1 |
| 2 | Types and shared low layers: the reply contract, the index, one home per field rule, event types | ~4 | 2 (P312) |
| 3 | Services, the record: the store split | ~3 | 2 (P312) |
| 4 | Services, the sorting engine: the filer split, content_check, the reader child | ~5 | 2 (P312) |
| 5 | Services, the door and the pass: the api and runner splits, the firm view moved down | ~5 | 2 (P312) |
| 6 | Components, the shell: app.js, main.js and shell.js split; the engine sends what the page re-derives | ~5 | 2 (P312) |
| 7 | State: per-command context, owner objects, the store's process state | ~3 | 2 (P312) |

The order is the brief's (types and utilities, then services, then
components, then state), with the safety nets first. A test file is split in
the same job as the module it owns (E-3), so `test_<module>.py` keeps meaning
ownership for the map.

## 8. Tranche 1: the jobs

**Order.** The dependencies allow two lanes (J1 and J6 beside J2, then J3
and J4 side by side, J5 after J3), but under P312 the jobs run one at a time
on the one branch, in the order J1, J2, J3, J4, J5, J6: nearly every job edits
the same guard files, and each review must see one job's diff alone
(`pilot/PROMPT-refactor.md` section 1.4).

| Job | Tier | Why (PROMPT-refactor 1.3) |
|---|---|---|
| J1 | Sonnet | a test walker fix and a README edit |
| J2 | Sonnet | mechanical moves of test helpers, checked byte for byte |
| J3 | Opus | (c) guards that parse Python and JavaScript |
| J4 | Opus | (c) a tool that parses the suite; recordings of a whole pass |
| J5 | Opus | (c) an AST-derived register; the resident engine and main.js |
| J6 | Opus | (d) `Build App.bat` and the Windows kit, which cannot run here |

### J1. The admission fingerprint follows only what the gate runs; the pilot README says P309

*Phase 0. Cost S. Findings B-2; decision P309.*

- **R1.1** In `tests/test_store.py`, `admission_closure()` collects, for each
  function it walks, every name bound inside it (parameters, assignment and
  augmented-assignment targets, `for` and `with` targets, comprehension
  variables, nested `def` and `class` names, imports inside the function) and
  never follows a name in that set as a callee.
- **R1.2** A test proves it on a made-up module: a function whose parameter
  shadows a module-level function does not pull that function into the
  closure.
- **R1.3** The version-5 pin is re-pinned with the corrected walker. The pin
  loses every entry the admission does not call (the reviewer found 19
  `tracker.settings.*` entries and 9 store entries) and gains nothing.
  `ADMISSION_VERSION` stays 5; the test's message already allows a re-pin
  that refuses nothing new.
- **R1.4** `pilot/README.md`: rule 1 and rule 3 replaced by exactly:

  > 1. **This repository is the one codebase (P309).** Since 2026-10-13
  >    nothing is merged from the original
  >    `J-Park-Associates/Tax-Info-Request-List`. A fix the original gets is
  >    copied across by hand, as a change of this repository's own with its
  >    own decision row. Pilot code no longer has to be additive: P7 and P10,
  >    which kept the pilot's differences small so merges from the original
  >    stayed clean, are retired.

  > 3. **Nothing is taken from the original by merge** (P309, ending P17's
  >    hand merge). The `upstream` remote and `git merge upstream/main` are no
  >    longer part of the work.

  and the "Where things are" line naming the current work points at this
  SPEC: `- [SPEC-architecture.md](SPEC-architecture.md) - the current work:
  the architecture audit and the refactor in phases.` (replacing the
  `SPEC-mac-check-fixes.md` line, which is landed work).
- **Tests:** `test_store`, `test_single_source` (the person-facing document
  check reads `pilot/README.md`), `test_repo_map`, `test_layers`,
  `test_tripwire`.
- **Accept when** the pin holds no settings entry, the new test passes, and
  editing `settings.host_system`'s body no longer fails
  `test_admission_version_changes_with_the_admission`.

### J2. Test helpers live in helper modules, never in another test file

*Phase 0. Cost M. Findings E-4, E-1 (the lifters), E-6 (in part).*

- **R2.1** New helper modules, none of them a test file: `tests/builders.py`
  (`make_engagement` re-exported from conftest, `drop`, `cache_rows`,
  `_link_to` renamed `link_to`, `original_at`, an `engagement` fixture factory
  taking the items and household), `tests/children.py` (`no_child_left`,
  `eventually`, `running`, `STOP_IN_TESTS`), and `tests/node_harness.py` (the
  `run_shell`, `run_pages`, `run_pages_dom` family and the other `run_*`
  runners from `test_shell.py`). `tests/samples.py` takes `text_pdf` and
  `write_pdf`.
- **R2.2** The three PDF writers become one `text_pdf(path, text_or_lines,
  *, pages=1, style=...)` whose each `style` writes **byte for byte** what its
  old writer wrote (tests pin counts and sizes against them). A test asserts
  each style's bytes equal the old writer's on three inputs, then the old
  writers are deleted.
- **R2.3** The seven JavaScript function lifters become one
  `js_function(name, file=None)` in `tests/node_harness.py`, cutting from
  `function name(` to the first `"\n}\n"` as today; with `file=None` it
  searches every script `index.html` loads (not `vendor/`) and asserts exactly
  one definition. Every caller is pointed at it. `lift()`'s semantics are
  kept.
- **R2.4** Every `from tests.test_<x> import ...` in `tests/` is replaced by an
  import from a helper module (24 files, 14 sources, E-4's list). The tools'
  imports of `tests.test_catalog`, `tests.test_irs_forms` and
  `tests.test_real_corpus` stay (decision 70, deliberate).
- **R2.5** New `tests/test_suite_shape.py`: no `tests/test_*.py` imports
  another `tests/test_*.py`; every helper module is imported by at least one
  test file.
- **R2.6** The curated map gets a node for each new helper module.
- **Tests:** every test file changed (expect about 26), `test_suite_shape`,
  `test_tripwire`, `test_layers`, `test_single_source`, `test_repo_map`.
- **Accept when** `grep -rn "from tests.test_" tests/` finds only the guard's
  own strings, and the changed files pass under both interpreters with the
  same test counts as before (state the before and after counts in the
  handoff).

### J3. The guards find code wherever it sits

*Phase 0. Cost M. Findings D-5, E-1, E-11, C-4 (the literals), D-2 (the seam
pin), D-8. Depends on J2.*

- **R3.1** New `tests/source_pins.py`: `py_function(name, module=None) -> str`
  finds a function's source through `ast` in `tracker/` (or one named
  module), asserting exactly one definition; `calls_of(name) ->
  list[tuple[str, str]]` lists `(file, enclosing function)` for every call
  across `tracker/`. These pins move to it with their claims unchanged:
  test_single_source.py:2265-2270 (`_file_into`'s three callers), 3015-3017
  (`_pass`'s exact signature), 2618-2620 (`this_host`), 934-936 (openpyxl
  inside `_extract_xlsx`); test_api.py:8039; test_runner.py:5065;
  test_fsio.py:358-359. (Line numbers as of `2741665`; find them by the
  claim.)
- **R3.2** `tests/node_harness.py` gains `RENDERER_SCRIPTS` (parsed from
  `index.html`'s `<script src>` list, without `vendor/`) and
  `renderer_text()`. `SHELL_FILES`, `TITLE_FREE`, `SPEED_SOURCES` and
  `PILOT_JS` become `RENDERER_SCRIPTS` or named subsets of it, each subset
  asserted to be inside it.
- **R3.3** These guards loop over every renderer script instead of `app.js`
  alone: the sink ban (`innerHTML`, `eval(` and the rest,
  test_single_source.py:566-575); commands called are in `api.COMMANDS`
  (105-115), now also catching `window.tracker.call([...])` and pilot.js's
  `COMMAND`; no vocabulary word typed in the renderer (test_api.py:1266-1329);
  the `startsWith(` scan (test_layers.py:960-968, which also keeps
  `app/main.js`). The count pins (`withEng("assign")` == 2, `fileRow` == 2,
  one `keydown` listener) count across all scripts.
- **R3.4** The typed-words guard reads every renderer script but the pilot's
  (`APP_SCRIPTS`). It skips only a literal that is the whole selector argument
  of `querySelector`, `querySelectorAll`, `closest` or `matches`, and the text
  of a thrown or logged error; none of them is on screen. Widened, it finds
  D-9's three sentences in `app.js` and the new-return dialog's typed
  "request list", which D-9's scan missed. Write them down as
  `KNOWN_TYPED_SENTENCES`, exactly those four, each citing D-9; J5 empties
  it. Nothing else may be added to it. The one label a ruling lets the page
  type, "Belongs To…" (ruling 10), is a one-item list of its own.
- **R3.5** `node --check` runs on every `app/*.js` and `app/renderer/*.js`
  except `vendor/`: one test in `test_build.py` (skipped with a stated reason
  when `node` is absent) and the same loop in `gate.yml`'s last step,
  replacing its three named files.
- **R3.6** Each failure-kind literal the renderer compares (`"stale"`,
  `"failed"`, `"locked"`, `"refused"`) is pinned to `progress.FAILURE_KINDS`
  in `test_single_source.py`.
- **R3.7** New `tests/test_renderer_seams.py`, the JavaScript analogue of
  `test_layers`: from `RENDERER_SCRIPTS`, collect each script's top-level
  declarations (`^(async )?function (\w+)\(`, `^(let|const|var) (\w+)`,
  `^class (\w+)`); for each ordered pair of scripts, the declared names one
  uses from the other (word-boundary match outside strings and `//`
  comments). Pin today's table as data in the test. A new cross-script name
  fails until it is added on purpose, with a line saying why. Separately, pin
  the cross-script **writes** (an assignment to another script's top-level
  `let`) found today (D-2 lists five); a new one fails.
- **R3.8** `pilot/harness/app-stub.js` defines every app.js name the seam
  table says another script uses (D-8 found eight missing), and its
  `EL_ATTRIBUTES` equals app.js's (it lacks `"open"`). A test in
  `test_renderer_seams.py` holds both.
  It also defines every name another script uses from a script `serve.mjs`
  drops in double mode (`sheet.js` today, whose `sheetNow` and `sheetPress`
  it lacked), and the same test holds that.
- **Tests:** `test_single_source`, `test_shell`, `test_shell_menu`,
  `test_api`, `test_layers`, `test_pilot`, `test_pilot_ui`, `test_row_columns`,
  `test_tour`, `test_runner`, `test_fsio`, `test_build`,
  `test_renderer_seams`, `test_tripwire`, `test_repo_map`.
- **Accept when** moving one function from `app.js` to a new script listed in
  `index.html` (tried on a scratch branch, never pushed) leaves every guard
  above still checking it, and a `node --check` failure in `shell.js` fails
  the gate.

### J4. Stand-ins that cannot silently miss, and recordings to compare a move against

*Phase 0. Cost M. Findings A-4, E-2, C-1 (patch risk), E-7. Depends on J2.*

- **R4.1** New `tools/patch_sites.py`, standard library only; it reads the
  code and runs none of it. `report <module>` lists every
  `monkeypatch.setattr` in `tests/` that it places on that module (object
  form, module-alias form and string form), each marked **defined** (the
  module defines `name`), **imported** (the module imports it and reads it)
  or **unread** (the module never reads `name` outside its own import or
  definition line). `check` exits 1 if any site is unread, if a stand-in
  cannot be placed, or if a `setattr` in the suite's text is none of a site,
  a stand-in it cannot place, or a call of the builtin. A target is placed
  only by a rule the tool can prove, so a stand-in may fail the check but
  never pass it unseen. What the tool does not read (stores through `vars()`
  or `__dict__`, `monkeypatch.setitem`, code built at run time, and the four
  forms review 6 found, which Jason ruled be written down rather than
  handled, 2026-10-14) is written in full in its docstring and its curated
  node. It keeps a `__main__` (the migration checklist runs it, P233).
- **R4.2** `tests/test_patch_sites.py` owns the tool: its cases on made-up
  modules, and `check` passing on the real suite. Any site found unread today
  is fixed in this job (pointed at the module that reads the name) and listed
  in the handoff.
- **R4.3** New `tests/golden/` and `tests/test_golden.py`, built from
  `tests/samples.py`'s made-up pile only: `vocab.keys.json` (the key tree of
  `api._vocab()`, keys and value types, never a sentence);
  `replies.<command>.keys.json` for `list`, `state`, `household`, `firm`,
  `firm-last`, `reminder`, `edit`, `assign` and `create` on a scratch root
  (keys and types); and `pass.samples.json`, one full pass over the sample
  pile (per index row: decision word, reason code, destination relative to
  the return; the record's event kinds in order; no clock, no sentence, no
  absolute path). `pytest tests/test_golden.py --record-golden` (an option
  added in `conftest.py`) rewrites them; without it the test compares.
- **R4.4** The curated map gets nodes for the tool, the test files and the
  recordings.
- **Tests:** `test_patch_sites`, `test_golden`, every test file changed by
  R4.2, `test_tripwire`, `test_layers`, `test_single_source`, `test_repo_map`.
  Recording a pass runs the sorting engine once; the job says so in its
  handoff and does not run the engine's own test files.
- **Accept when** `python tools/patch_sites.py check` exits 0 on the suite,
  `report tracker.filer` lists at least the 73 filer sites a text search
  finds (79 when J4 landed), and the recordings
  reproduce identically on a second run.

### J5. The engine's state between commands, the sender check, and the page's typed sentences

*Phase 1. Cost M. Findings A-7, C-3, D-10, D-9. Depends on J3.*

- **R5.1** `tracker/resident.py` holds the **state register**: two tables
  naming every module-level name in `tracker/` that a function rebinds with
  `global`, or that is a list, dict or set some function mutates (`append`,
  `extend`, `insert`, `update`, `setdefault`, `pop`, `clear`, `add`,
  `discard`, `remove`, item assignment, item deletion).
  `PER_PROCESS: dict[tuple[str, str], str]` maps `(module, name)` to the
  reason or decision that keeps it for the engine's life.
  `PER_COMMAND: dict[tuple[str, str], object]` maps `(module, name)` to its
  fresh value. After every command the resident restores each
  `PER_COMMAND` name: `.clear()` for a container, rebinding for anything
  else. Names whose life is a `with` block (`settings._HELD`, `_HOLDING`) go in
  `PER_PROCESS` with the reason "reset by `settings.one_reading`".
  `functools` caches on pure functions are outside the register.
- **R5.2** Per command, replacing the two private clears the resident makes
  today: `api._WARNINGS`, `api._ASKED`, `api._RUNNING`,
  `content_check._COULD_NOT_START` (the leak, A-7), `content_check._last_line`,
  `fsio._full_sync_said` and `locking._full_sync_said` (said once per command,
  as before P276, C-3). `ocr.forget_said()` keeps being called. Per process,
  with their reasons: the store's six connection globals (decision 101,
  P214), `ocr._ENGINE`/`_DEVICE`/`_PROCESSOR_ONLY`/`_SESSION` (decision 169),
  `settings._redirect_answer` (a fact about the machine), `store._REPLACED`.
  The builder confirms each against the code and records any it moves in the
  handoff.
- **R5.3** A test in `tests/test_resident.py` derives the set of such names by
  `ast` over `tracker/*.py` and fails on any name in neither table, or in
  both. A second test runs two commands through one resident engine, the
  first leaving a could-not-start name, and proves the second command's reply
  and the module state carry nothing from the first.
- **R5.4** `app/main.js`: one `fromMainWindow(event)` check, as `onMenuMessage`
  does today, applied in every `ipcMain.handle` (`tracker-cmd`, `open-path`,
  `pick-folder`, `log-error`); a message from anywhere else is refused with
  the existing refusal path and logged by kind only. `test_shell_menu.py`'s
  fake Electron passes a matching sender, and one test proves a foreign
  sender is refused on each channel.
- **R5.5** The `assign` reply carries the three sentences `fileRow` types
  today, as `said` (the way `marked_missing.reason` already does), worded
  byte for byte as now and declared as constants in `api.py`. `app.js` shows
  `said` and types none of them. `KNOWN_TYPED_SENTENCES` (R3.4) becomes empty
  and is deleted. `pilot/harness/stub.js` sends `said`.
  The new-return dialog's heading takes "request list" from the vocabulary,
  as it already takes `ask_the_client`.
- **Tests:** `test_resident`, `test_api`, `test_api_entry`, `test_shell`,
  `test_shell_menu`, `test_single_source`, `test_layers`, `test_repo_map`,
  `test_tripwire`, `test_golden` (the `assign` key tree gains `said`; re-record
  it and say so).
- **Accept when** the register test passes, the two-command test passes, and
  `grep` finds none of the three sentences in `app/renderer/`.

### J6. The type checker, and the Windows build's missing check

*Phase 1. Cost M. Findings E-5, E-10; decision P310. `windows` label.*

- **R6.1** `requirements-dev.txt` names mypy at one exact version;
  `requirements-dev.lock` is filled with hashes by `tools/lockfiles.py`, as
  the other locks are. Nothing that installs the app (`Setup.bat`,
  `setup.command`, `Build App.bat`, `build-mac.sh`, `api_entry.spec`, the
  installer) reads it. `test_build.py` and `test_lockfiles.py` assert that;
  `test_layers.ALLOWED_THIRD_PARTY` does not gain mypy (nothing under
  `tracker/` imports it).
- **R6.2** `[tool.mypy]` in `pyproject.toml`: `files = ["tracker", "tools"]`,
  `python_version = "3.11"`, `explicit_package_bases = true`, and
  per-module `ignore_missing_imports` for the reader packages only
  (`pdfplumber`, `pypdfium2`, `rapidocr`, `cv2`, `numpy`, `PIL`, `pypdf`,
  `olefile`, `openpyxl` and any the first run names). The ~9 platform false
  positives (`ctypes.WinDLL`, `fcntl.F_FULLFSYNC`) are handled with
  `sys.platform` checks mypy understands or a narrow `# type: ignore[code]` on
  the line, never a file-wide ignore.
- **R6.3** New `tools/typecheck.py`, standard library only: `check` runs mypy
  and compares errors per file with `docs/typecheck-baseline.json`; it fails
  if any file has more than its recorded count or a file with none gains one,
  and names the file and the new errors. `update` rewrites the baseline and
  refuses to raise any count. `tests/test_typecheck.py` tests it against a
  made-up mypy output; the suite never runs mypy itself.
- **R6.4** The gate in `CONTRIBUTING.md` and `CLAUDE.md`'s "Working on this
  repo" block gains `pip install --require-hashes -r requirements-dev.lock`
  (once) and `python tools/typecheck.py check`; `gate.yml` gains the same step
  on Linux. Wording any test pins is kept.
- **R6.5** `Build App.bat` checks the finished package holds no store, run
  log, settings file or data folder, by running the same check `build.yml`
  runs (moved into one PowerShell script both call, so the name list has one
  home on Windows), and stops with a sentence when one is there.
  `pilot/wintest/run_checks.ps1` and `uninstall_checks.ps1` read the product
  name from `app\package.json`, or both join
  `test_the_product_name_has_one_home`.
- **R6.6** The curated map gets nodes for the tool, its test, the lock and
  the baseline.
- **Tests:** `test_typecheck`, `test_build`, `test_lockfiles`, `test_layers`,
  `test_single_source`, `test_pilot`, `test_pilot_installer`, `test_repo_map`,
  `test_tripwire`. On the office PC: `pilot\wintest\run_checks.ps1 -Tests
  test_build.py,test_pilot.py,test_pilot_installer.py` and one `Build App.bat`
  run with a planted settings file in the package folder, which must stop it.
- **Accept when** `python tools/typecheck.py check` passes on the committed
  baseline (state its total, expected near 200), raising one error in a file
  fails it, and the planted-file build stops.

## 9. Phases 2 to 7, in outline

Scheduled by P312. Each phase gets its own SPEC, `pilot/SPEC-architecture-p<N>.md`,
written and reviewed by Opus from the code as it then is, before it builds
(`pilot/PROMPT-refactor.md` sections 3 and 4): line numbers drift, and tranche 1's
recordings and type count will say where the risk sits. Every phase starts by
burning down the type errors in the modules it will move, and ends with a job
that removes its facades.

**Phase 2: types and shared low layers.** `replies.py` and one envelope
builder (C-4); `index.py` with filer re-exporting it, then its readers
importing it directly (A-2, with Q-A); the field rules in one home:
`layout.file_name_part_problem`, the typed people rule beside the typed
identifier rule, `bounds.py` (B-3, B-11); `PAGE_BREAK` down to `records`
(A-9) and CLAUDE.md's "the one deliberate cycle" sentence corrected for the
other call-time cycles; the Open allow-lists into `reasons.py` (C-7);
`page.document` (C-9); decision 100's shim retired (A-12); `hold.py`,
`errlog.py`, `settings.store_file`, one Mac probe (B-5, B-6, B-10); event
`TypedDict`s after the gate (B-8); `tools/corpus.py` and `tests/cases.py`
(E-9); a domain column in the layer table (5.1).

**Phase 3: the record.** `admission.py` with one function per event family,
chosen by an explicit `if/elif` so the fingerprint still follows every branch
(B-1, B-7); `store_check.py`; `verify.py` at L3; the API's record events moved
to `households` and `manifest`, and a guard that `ledger.new(` stays out of
the door (B-4); one keyword fold (B-9); `test_store.py` split with them.

**Phase 4: the sorting engine.** Needs the office backtest baseline first
(section 4.1, item 11). `copies.py`, `intents.py`, `inbox.py`,
`readme_ack.py`, `actions.py` in that order (A-1); the one after-routing road
`_settle` with Q-B answered (A-3); `candidates` as `tuple[str, ...]` and an
`Op` `TypedDict` (A-8); the inline refusals named (A-10); `keywords.py`,
`verdicts.py` (A-5); `reader_child.py` with the `windows` label (A-6);
`conftest.py` into plugins (E-6); `test_filer.py` and `test_content_check.py`
split with them. This phase reaches the engine, so its gate runs the whole
suite once per job.

**Phase 5: the door and the pass.** `screen_words.py` (C-1, C-6);
`request_edit.py` with Q-F settled, `household_edit.py`, `creation.py` (C-1);
`firm_view.py` at L4 with Q-C answered (C-2); `status_page.py`, `run_log.py`,
`pass_order.py` (C-5); `letter_render.py` (C-8); after_install's jobs as a
table (C-10); the de-facto public names made public (`api.vocab`,
`api.state`, ...; E-2); `test_api.py` and `test_runner.py` split by command
family (E-3).

**Phase 6: the shell.** app.js split by responsibility (D-1); `firm-loader.js`
(D-7); `main.js` into `engine.js`, `open-path.js`, `menu.js`, `logs.js` (D-4);
the engine sends `hand_over_targets`, `tally`, `groups` and each return's
`taxpayer`, and the page stops re-deriving them (D-3); `appReady` for
`pilot.js` (D-6); the CSS overrides folded into one home with Q-D (D-11); a
test for the paste parser (D-12).

**Phase 7: state.** Per-command context in a `contextvars.ContextVar` that
`api.main` sets and resets (C-3); the could-not-start list owned by
`ocr.Session` (A-7); the store's process state as one object (B-12); filer's
per-drop `_Arrival` passed down instead of mutated (A-11); each renderer
script's state in one owner object, with the seam table tightened to the
owners' functions (D-2).

## 10. The migration guide: how to apply this without breaking the app

In plain English first: every change goes in small steps. Each step is
proved by tests that already passed before it started, and each can be undone
on its own. Code is first *copied* to its new home while the old address keeps
answering. Then everything that used the old address is pointed at the new
one. Only then is the old address removed. A reviewer who did not do the work
checks every step before it lands.

**Before a job**

1. Start a fresh session. Read section 6, the job's section, the findings it
   cites in the appendix, and `pilot/HANDOFF.md`. Do not read earlier
   transcripts.
2. Branch from the lane's stack (section 8's lanes). Run `python
   tools/repo_map.py check`; a stale map is fixed first, in its own commit.
3. Run `python tools/repo_map.py show <file>` for each file the job touches.
4. Run the job's named tests once **before any edit** and record the counts.
   They are the baseline the job must keep.

**During a job (a move, from phase 2 on)**

5. `python tools/patch_sites.py report <module>`: point every stand-in on a
   name the moving code reads at its new home. Commit.
6. Make the new module; move the code byte for byte; the old module
   re-exports what moved, with an identity test. Add the `LAYERS` row and the
   decision row. Commit.
7. Point the importers and the text pins (E-8's list for that file) at the
   new home. Commit.
8. Compare against `tests/golden/`: a move leaves every recording identical.
   A recording that changes means behaviour changed. Stop and find out why.
9. Update `docs/repo-map.curated.json` and run `python tools/repo_map.py
   update`, in the same commit as the code.

**The gate, before every push**

10. Delete dead code in the changed files.
11. Run the job's named test files, each as its own process, under Python
    3.11 and 3.14. On the office PC: `pilot\wintest\run_checks.ps1 -Tests
    <files>`.
12. Run `python -m ruff check .`, `python tools/repo_map.py check`, `python
    tools/typecheck.py check` (after J6), `python tools/vocab_report.py
    check` (when routing is touched), and `python tools/patch_sites.py check`
    (after J4).
13. Re-read the diff as a reviewer would: what would make the gate or the
    office PC reject it?

**Review and landing**

14. An Opus review at high effort, in a session that did not build. Numbered
    findings, then a rebuild of those findings only. Repeat until a review
    has no findings.
15. Each tranche, or each later phase, is one draft pull request, each job
    its own commits. Mark it ready once, when the stack is final; GitHub
    rebases it onto `main`; land it with a merge commit, never squash or
    rebase-merge (decision 211). Add the `windows` label where section 6
    says to.
16. After landing, update `pilot/HANDOFF.md` and give Jason the CODE UPDATE
    text for the Drive thread.

**Undoing a landing**

17. A landing is one merge commit, so `git revert -m 1 <merge>` undoes it
    whole. No job in this plan changes the record's format, the store's
    schema or the folders on the drive, so a revert never strands a client's
    data. A job that finds it must change one stops and asks first.

## 11. Questions for later phases

Each has a recommendation; none blocks tranche 1. P313 says how each is built
meanwhile; Jason can reverse any of them.

- **Q-A (phase 2).** Make the filer↔scanner cycle one-way: the scanner reads
  the index from `index.py` and never imports filer; filer still asks for the
  rescan at call time. That rewrites a curated `deliberate_cycle` edge, a
  `test_layers` assert and a CLAUDE.md sentence. *Recommended: yes.*
- **Q-B (phase 4).** On the re-send road, a document parked across households
  carries no shortlist; on the first road it carries the home return's
  candidates (section 4.1, item 9). Which should a person see in Needs
  Review? *Recommended: the same as the first road, so the shortlist does
  not depend on whether the document was sent before.*
- **Q-C (phase 5).** Once the firm-row builder is at L4, does the pass fill the
  firm cache in-process, or keep the child for its own time limit and closed
  input? *Recommended: in-process, unless the office's timings show the fill
  can stall a pass.*
- **Q-D (phase 6).** Fold the overriding CSS into one home now that P309 ends
  merges, which were the reason for P51 and P67. *Recommended: yes, in
  phase 6.*
- **Q-E (phase 6).** Check the JavaScript's types too, with TypeScript's
  checker as a development-only `devDependency` reading JSDoc comments (no
  build step; the app still ships plain JavaScript)? *Recommended: decide
  after phase 6, once the scripts are small enough to annotate.*
- **Q-F (phase 5).** The editor's path-room check: route it through
  `filer.refuse_a_path_past_the_limit` or correct that function's claim.
  Verify first that leaving out the review folder cannot let a save through
  that creation would refuse. *Recommended: one function, as its docstring
  says.*

## 12. Handoff

- **Done in the session that wrote this:** the audit (five slices, read only),
  this SPEC, the appendix, decision rows P309 to P313, `pilot/PROMPT-refactor.md`
  (the standing instructions for every agent in the loop), and
  `pilot/HANDOFF.md` pointed here. No code changed before J1.
- **The loop** runs the jobs in order (section 8, then each phase's own SPEC)
  as `pilot/PROMPT-refactor.md` section 1 says, and records each landing in
  section 13 below.
- **Files a job's agent needs:** `pilot/PROMPT-refactor.md` (section 2 and its
  role's section), its job's section here or in the phase SPEC, the appendix
  findings the job cites, and the board's notices and its own thread.
- **Left for Jason:** the questions P313 keeps open (Q-B and, if it comes to
  that, Q-F); any `question` the loop escalates; the office PC steps section
  13 lists as owed; opening and landing the pull request.

## 13. Built (the ledger)

One row per job, added by the orchestrator when the job's review passes and
its commits are pushed. "Owed" lists the hands-on steps that only the office
PC can run.

| Job | Tier | Rounds | Commits | Outcome | Owed to the office PC |
|---|---|---|---|---|---|
| J1 | Sonnet | 2 | `e2e700a`, `afe53f6`, `8d8e431` | Review 2 clean. The admission walker no longer follows a name the function binds itself: `ADMISSION_PIN[5]` lost 30 entries (the SPEC expected 28; `layout.root_of` and `records.status_from_json` were reached only through shadowed names), gained none, and `ADMISSION_VERSION` stays 5. The pilot README's rules 1 and 3, its "Where things are" line and its opening paragraph say P309. | None |
| J2 | Sonnet | 2 | `71a59f8`, `c826ba9`, `6bb3298`, `c8ac081`, `9aa8a1d`, `9eded66` | Review 2 clean. No test file imports another, and `tests/test_suite_shape.py` says so. The shared helpers live in `tests/builders.py`, `children.py`, `node_harness.py` and `samples.py`, and in six modules the SPEC did not name, because the SPEC's three did not hold every cross-import: `passes.py`, `css_rules.py`, `api_driver.py`, `wording.py`, `import_graph.py` and `routing_cases.py`. `text_pdf` has the styles `page`, `padded` and `bare`, byte-identical to the three writers it replaced (8000 of 8000 random inputs at build, 4500 of 4500 at review). `js_function` is the one JavaScript lifter. `tools/vocab_report.py` lists `tests/routing_cases.py` among its inputs, because the report hashes what it reads. Test ids are unchanged apart from 22 new ones. The first three commits went up unsigned and stay as they are (Jason, 2026-10-13); `c8ac081` and `9aa8a1d` are `c6b3751` and `2e15471` re-signed. | Optional: `link_to`'s junction branch and `running`'s kernel32 branch moved modules unchanged; run `test_door`, `test_filer`, `test_containers`, `test_ocr` and `test_content_check` once on Windows, one process each. |
| J3 | Opus | 2 | `cb1e2cf`, `41d02c6`, `c7f4536`, `48add35`, `36b9fa3`, `62ae901`, `cbe4123` | Review 2 clean. `tests/source_pins.py` finds a package function by name at any depth (`py_function`, `calls_of`), and the eight source pins read through it. The renderer's guards read every script `index.html` loads (`APP_SCRIPTS`, `PILOT_SCRIPTS`, `SHELL_SCRIPTS`, `renderer_text()`); the no-typed-vocabulary guard reads every app script, with a whole-word match outside app.js. The typed-words guard reads `APP_SCRIPTS` and passes over only a query's whole selector argument, the text of a thrown or logged error and a leading `"use strict"`. `KNOWN_TYPED_SENTENCES` holds D-9's three and the new-return dialog's typed "request list" (R3.4 and R5.5 amended); `RULED_LABELS` holds "Belongs To…". `node --check` parses every script the app runs, in test_build and in gate.yml's last step. `tests/test_renderer_seams.py` pins the seam table, and the double stands in for every name of the scripts `serve.mjs` drops (it gained `sheetNow` and `sheetPress`; R3.8 amended). Open for phase 6: tour.js's typed "Step N of M" and the pilot's scripts outside the typed-words guard; the guards that still read app.js or a typed list of files; `roll-household`, which no guard reads. | The usual pre-merge gate: `pilot\wintest\run_checks.ps1 -Tests test_build,test_shell,test_renderer_seams,test_single_source,test_api,test_runner,test_fsio,test_layers,test_repo_map,test_tripwire`. gate.yml's last step is now a bash loop, which runs in Git Bash on a run with the `windows` label. |
| J4 | Opus | 6 | `79d8079`, `4084f9c`, `3511a85`, `0d3283d`, `38b3a06`, `824e704`, `a6480a0`, `a641b1b`, `b13522a`, `3bae20a` | Landed as it is after six reviews, none clean (Jason, 2026-10-14). `tools/patch_sites.py` places each `<x>.setattr` in the suite only by a rule it can prove, and `check` fails an unread site, a stand-in it cannot place, and any `setattr` token in the suite's text it cannot account for (the backstop; R4.1 amended): 742 stand-ins on 41 modules, none unread, none unplaced, no token unaccounted for. What a parameter holds is not followed (ruling 015 of J4), so a test names its module directly. Review 6 found four made-up forms the tool misreads: bindings its test side does not model (a comprehension or class body as a scope, a walrus in a comprehension, except-as, a match capture, a star import), a helper module imported by its bare name (`import children`), a store through a value it does not follow, and a store into `sys.modules`. None occurs in the suite; they are written into its list of what it does not read and carried forward. A stricter rule that names every target plainly was measured and would have rewritten 490 test lines. `report tracker.filer` lists 79 sites (the SPEC's 73 was the audit's search; the acceptance line amended). Real stand-ins rewritten to name their module: two in test_locking, and others in test_fsio, test_store and test_ocr. Eleven recordings in `tests/golden/` (`--record-golden`) reproduce identically on both interpreters; J5 re-records three of them. | The usual pre-merge gate: `pilot\wintest\run_checks.ps1 -Tests test_golden,test_patch_sites,test_layers,test_single_source,test_repo_map,test_tripwire,test_suite_shape,test_errors`. Then one Windows run each of `test_locking` (its platform stand-ins now aim at `platform` itself; a Mac run too if one is available), `test_fsio` (the atomic replace) and `test_store`, whose stand-in targets were rewritten. |
| J5 | Opus | 1 | `448ea36`, `22e27ce`, `8010c52` | Review 1 clean. `tracker/resident.py` holds the state register: `PER_COMMAND` (8 names, each with its fresh value, restored after every command and before a refusal, by emptying the container and refilling it shallowly from that value) and `PER_PROCESS` (22 names, each with its reason). `tests/test_resident.py` derives 30 names from the package, `globals()` stores included, and fails on one in neither table or in both; the derivation found 9 per-process names more than R5.2 lists and `ocr._SAID`, which is per command, and the store has five connection globals plus `_REPLACED`, not six. A two-command test proves the second reply matches a fresh engine's byte for byte, which closes A-7. `app/main.js` answers only the app's own window (`fromMainWindow`) on all four IPC channels and the menu, and refuses any other sender the way that channel already refuses, logging only the channel's name. `assign` replies with `assigned.said` (`filed`, `keyword_added`, `spelling_added`; constants `api.ASSIGNED_*`, worded byte for byte as `fileRow` typed them); the vocabulary gains `request_list`; `KNOWN_TYPED_SENTENCES` is deleted. Exactly three recordings were re-recorded: `replies.assign`, `replies.list` and `vocab`. Open for phase 6: `fromMainWindow`'s comment claims more than `event.sender` can tell, and its refusal sentence is typed in main.js. | `pilot\wintest\run_checks.ps1 -Tests test_resident,test_api,test_api_entry,test_shell,test_shell_menu,test_single_source,test_layers,test_repo_map,test_tripwire,test_golden,test_patch_sites,test_suite_shape`. In the built app on a made-up clients root: run a pass, open a filed document and use Choose Folder in Settings, each answered; file a parked document from Needs Review with and without a keyword and spelling, and read its row's sentences; start a new return and read the heading ("1040 request list — Ask the Taxpayer"); run two passes where a reader could not start, and see that the second carries nothing from the first. |
| J6 | Opus | 1 | `8e5dee7`, `f20b6bd` | Review 1 clean. mypy 2.3.1 comes from `requirements-dev.lock` by hash and reaches nothing that installs or builds the app. `[tool.mypy]` checks `tracker` and `tools` as Linux on every machine (`platform = "linux"`, `no_site_packages`, `tests.*` followed silently; without them the count differs by machine and py314 stops), with the reader packages plus onnxruntime and pillow_heif ignored as missing imports. `tools/typecheck.py check` holds each file to `docs/typecheck-baseline.json`: 227 errors in 29 files (the SPEC expected about 200; tools/patch_sites.py, which landed after the audit, has 25). `update` refuses to raise a count. Nine platform-only lines carry a narrow ignore naming the platform. gate.yml gains one Linux-only step and no trigger; CONTRIBUTING.md and CLAUDE.md's gate gain the install and the check (CLAUDE.md added by the orchestrator at landing). `tools/check_package.ps1` holds the one Windows list of names a package must not contain; Build App.bat and build.yml both run it, and Build App.bat stops before `[4/4] Done.` when one is there. Both wintest scripts read the product name from `app/package.json`. Open: a mypy upgrade that counts more errors can only be taken with a fresh baseline; `platform = "linux"` leaves Windows-only branches unchecked. | `pilot\wintest\run_checks.ps1 -Tests test_build.py,test_pilot.py,test_pilot_installer.py`, whose installer build must print "The package holds no store, run log, task file or settings." then `[4/4] Done.`. One `Build App.bat` run with `app\settings.json` planted (`echo {} > app\settings.json`): it must stop naming the file and never print `[4/4] Done.`; then delete the file. Report it if Windows PowerShell 5.1 reports long paths as unreadable. Optional: `uninstall_checks.ps1` as before. The pull request takes the `windows` label. |
| P2.1 | Opus | 1 | `1afeffa`, `03130bf` | Review 1 clean. records and settings type-check clean, and the baseline reads 217 errors in 27 files (from 227 in 29). records.py:74 keeps `import re._parser` with one named ignore, `# type: ignore[import-not-found]  # typeshed does not stub the private parser`; `UNSTUBBED` in `tests/test_typecheck.py` excuses exactly that line by file and wording, and the platform count stays 9 (loading the parser through `importlib` would fail decision 190's guards). `_is_number` returns `TypeGuard[int | float]`, which moved one `ADMISSION_PIN[5]` digest under version 5; `ADMISSION_VERSION` stays 5. Two casts in settings. Open: none. | None. |
| P2.2 | Sonnet | 1 | `568c726` | Review 1 clean. `DOMAINS` in `tests/test_layers.py` sorts the 39 modules into six domains (record 14, reading 4, sorting 6, pass 7, door 3, shell 5); `door.py` sits in record. `test_every_module_sits_in_exactly_one_domain` checks the six keys, that no module is in two, and that the union is `set(LAYER_OF)`; it fails on a removed module, a doubled one, one with no layer and a renamed key. The module docstring names the domains, and decision P314 records them. No module changed layer and no code under `tracker/` changed. Open: none. | None. |
| P2.3 | Opus | 1 | `378d8c9` | Review 1 clean. `tracker/replies.py` (L0, `door`) holds `Failure`, `Envelope` and the nine success-reply `TypedDict`s; it has no future import, which would hide `NotRequired`. `api._envelope_of` returns `progress.failure_reply(...)` whole through the SPEC's `cast`, and `say_failure` prints it: stdout is byte-identical over 40 envelopes on both interpreters, and `tests/golden/` is unchanged. `tests/test_replies.py` (22 tests) holds the recordings, the envelope, `shellFailure` and every failure kind the screen names, with the SPEC's 33 must-find and 14 must-not-find entries and no exclusion table. api.py stays at 24 type errors and replies.py has none. The package docstring and `docs/architecture.md` (thirty-nine modules) list the new module. Decision row P315 was written at landing (review note N1: a new module gets a row in its own commit), and the phase SPEC's later rows moved up to P316-P322. Open: none. | None. |
| P2.4 | Opus | 1 | `18caccc`, `9979d4d` | Review 1 clean. `tracker/bounds.py` (L0, `record`) holds records' value-rule region byte for byte, `class Override` and the parser's import line among it; records keeps the row checks that read its own shapes and re-exports the other 43 public names until P2.13, and the identity test covers all 69. `ADMISSION_PIN[5]` stays version 5: 66 keys rename to `tracker.bounds.` with the same digest, one same-digest key is added (`tracker.bounds.TEXT_BOUNDS`), and no digest is new. The twelve plain value-rule tests moved to `tests/test_bounds.py` unchanged; test_records + test_bounds = 58, the base's 55 plus 3. `UNSTUBBED` names bounds.py. Decision row P316. records keeps the section's header line above its two-line pointer (review note N2, accepted). Open: none. | None. |
