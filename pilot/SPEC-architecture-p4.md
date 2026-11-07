# SPEC-architecture phase 4: the sorting engine

Written by the SPEC writer and measured at `68b9212`, the phase's base, where P3.9 landed. (`1d866d8` is a
handoff-only commit on top of it; the code is identical.) Every line number below is at `68b9212` unless a job says
it was measured after an earlier job. The scope is SPEC-architecture section 9's "Phase 4" paragraph, with these
parts of section 5:
- the filer row (166) and the ocr row (172);
- the layer picture (338-346);
- the new-module table (385-392).

The audit findings it builds are in `pilot/AUDIT-2026-10-13-architecture.md`: A-1, A-3, A-4, A-5, A-6, A-8, A-10 and
E-6. A-7 and A-11 belong to phase 7. They are left alone, and each job says where a move touches the state they name.
The SPEC reviewer's findings are in `ORCH/jobs/P4/review-<r>.md`. This is the round-2 draft, revised against review 1
(S1-S14).

## 1. The answer

Phase 4 takes apart the three large modules of the sorting engine without changing what any of them does. Each moved
job gets one flat home in `tracker/`.

From the filer (7,576 lines), in A-1's order:
- `copies.py` (L2): naming, path room, the byte-proved copy, the rename-only move, the Protected View mark, the client
  README's lock and the stranded-temp sweep.
- `intents.py` (L3): the write-ahead intents and finishing an interrupted move.
- `inbox.py` (L3): walking the inbox, and the drops that cannot be read, listed or tied to a row.
- `readme_ack.py` (L3): the client README's received list and its refresh.
- `actions.py` (L3): a person's actions (assign, dismiss, unfile, mark missing, restore, rename) and the rescan that
  follows them.

The filer keeps the household pass, the decision and the working copies: about 3,700 lines. Inside the decision, the
step after routing becomes one road, `_settle` (A-3). Today's one difference between the two roads (Q-B: what the
re-send road's across-household park carries, and where it lands) stays, as a named parameter. The decision path is typed: `candidates` is `tuple[str, ...]`, and the ops are `ledger.IntentOp`
(A-8). A person's refusals are named once (A-10).

From `content_check` (2,496 lines):
- `keywords.py` (L2): the matcher and the rules.
- `verdicts.py` (L2): the judgment's shapes and the store-backed verdict cache.

`content_check` keeps the one reading, the judgment, the child's parent side and checking (A-5).

From `ocr` (1,898 lines):
- `reader_child.py` (L2): the reading's child process, its supervisor and the Windows job object.

`ocr` keeps the engine and the preparation of a page (A-6).

The suite moves too:
- `tests/conftest.py` becomes four plugins, cut by concern where pytest's order allows (E-6). The builders move to
  `tests/builders.py`.
- `test_filer.py`, `test_content_check.py` and `test_ocr.py` split with their modules (E-3).

The first job also removes the lock leak that breaks the whole suite when two particular tests share a worker.

Nothing changes in:
- `SCHEMA_VERSION` (20), `ADMISSION_VERSION` (6) or `ADMISSION_PIN[6]`;
- any golden recording, the catalog, a keyword, a typed case or the vocabulary report's counts and hits;
- which file goes where, or anything a person sees.

## 2. What it relies on

**Decision rows:**
- 51: `_SortContext`, the seams where the code already turned.
- 95, 99 and P313: the layer test, and the scanner reaching the filer only at call time.
- 100: the records moved out of the modules that write them, the precedent for a split.
- 107: `own_forms()` is the one reading, and the verdict cache lives in the store.
- 111: a re-send is judged by the earlier row's decision.
- 119: the intents are shared by the pass and a person's actions.
- 128: the name tier; the router knows no person.
- 132 and 204: across households, a document waits for a person.
- 150, 154, 169 and 189: one reading child for every parse, the job object, and nothing but the class crossing back.
- 185: the tripwire; the suite never sees a real root.
- 190 and 193: the sentences are the firm's; codes are columns.
- 89, 91, 101 and 102: the two agreement oracles.
- P310: mypy, dev-only.
- P312 and P313: the loop, and behaviour does not change.
- P323-P328: phase 3's homes.

**Landed jobs:**
- J1: `ADMISSION_PIN` follows the closure.
- J4: `tools/patch_sites.py` and `tests/golden/`.
- J5: the state register (`tracker/resident.py`) and the said-sentence guards.
- J6: `tools/typecheck.py`. Its baseline at `68b9212` is 206 errors in 25 files: filer 51, content_check 9, ocr 8,
  router 2. (The brief's 52 for filer is 51 as measured.)
- P2.9 and P2.10: `index.py`. The scanner never imports the filer.
- P3.7: `COMPOSERS` (`tests/test_layers.py` 480).
- P3.8: `ADMISSION_VERSION` 6 and `ADMISSION_PIN[6]`.

**SPEC-architecture:**
- section 5.1 (flat modules; a move is a move), and the rows and tables cited above;
- section 6 (behaviour does not change);
- section 4.1 item 11 (the office backtest baseline);
- section 9 (phase 4's paragraph, 819-827).

### 2.1 Where this SPEC departs from section 9's paragraph or the audit, and why

| Item | What the plan or the audit asks | What this SPEC does | Why |
|---|---|---|---|
| **No re-export facade** | Section 5.1 and A-1: the old module re-exports what moved until a last job removes it | P3's approach. The new module imports what its moved code reads, by name. The old module imports back by name only what it uses itself. Every reader in `tracker/` and `tools/` is retargeted in the moving job. A test that reads a moved name through an import-back the old module keeps for its own use may wait for P4.13. A test that reads, through the old module, any name the old module no longer holds after the job (a moved name, or an imported name whose last reader moved) is retargeted in the moving job (section 3, Tests). P4.13 retargets the rest and adds a guard. | A from-import that the module itself uses is not a facade. The stand-ins (A-4) must reach the code they replace from the first move, so the tests are touched in every move anyway. |
| **Logger names** | Nothing | Each module carved out of the filer binds `log = logging.getLogger("tracker.filer")`. `reader_child` binds `logging.getLogger("tracker.ocr")`. `keywords` and `verdicts` do not log. | The run log and the error log print `%(name)s`. A new name would change the lines a person and the office read. It is the same logger object, so no test and no handler sees a difference. The module docstring says why. A later phase may rename them with a decision row. |
| **The README lock and the stranded-temp sweep go to `copies`** | A-1 step 2: 555-1283 plus the sweep. The README piece goes to `readme_ack`. | The README lock (1418-1446) goes to `copies` with the sweep (1503-1674). `readme_ack` takes the received list and the refresh. | The sweep reads the lock's file name (`README_LOCK_FILENAME`) and `_holds_the_firms_readme_text`. With the lock in `readme_ack` (L3), `copies` (L2) would import upward. |
| **`OPENED` goes to `index`** | A-1 lists the decision words with `index.py` (P2.9 moved the others) | `OPENED` (filer 395) moves beside `FILED`, `NEEDS_REVIEW`, `DUPLICATE` and `FILE_MOVED` in `tracker/index.py`, in P4.6. | `intents` and the filer both read it. It is a decision word like its neighbours, and `index` (L1) is below both. |
| **`in_a_child` stays in `content_check`** | A-6: `reader_child` also takes `content_check.in_a_child` and its outcome mapping | It stays. `reader_child` takes ocr 1011-1864 only. | `in_a_child` builds `content_check`'s Extractions (`abandoned`, `reading_failed`, `could_not_start`). `could_not_start` appends to `_COULD_NOT_START`, phase 7's state (A-7). Moving `in_a_child` without that state would make `reader_child` import `content_check` while `content_check` imports `reader_child`: a load-time cycle. |
| **The judgment's shapes go to `verdicts`** | A-5: `verdicts.py` holds `ContentCache`, `CACHE_VERSION` and `RETIRED_CACHE_FILENAME` | `verdicts` also takes `Extraction`, `RowQuestion`, `row_question`, `NameQuestion`, `Questions`, `RowJudgment`, `Judgment` and `unjudged`, with `_evidence_from_json`. | `ContentCache` stores and returns `Judgment`s, and `content_check` annotates `ContentCache`. `tests/import_graph.py` counts an `if TYPE_CHECKING:` import as a load edge, so the two modules cannot both name each other's types. Moving the shapes down to the cache is the only order with no cycle and no new type error. The shapes are what the cache keeps, so they belong with it. |
| **The Op `TypedDict`** | A-8: add an `Op` `TypedDict` beside the ledger's key constants | `ledger.IntentOp` (ledger 630), which already exists, becomes the type of every op in the filer and `intents`. No new type is added. | P2.11 added it for exactly this shape. A second name for it would be two sources. |
| **`_rescan` goes to `actions`** | Not named | `RESCAN_REFUSED` (6498) and `_rescan` (6804-6815) move with a person's actions, their only callers (6713, 6801, 7054, 7513). The curated `calls` edge moves from the filer to `actions`. CLAUDE.md's sentence changes (R4.9.9). | Leaving `_rescan` in the filer would keep a call-time edge that no filer code uses. |
| **What stays in the filer** | A-1: the filer keeps the household pass and the decision | It also keeps: the working copies (2553-2994); `Spelling`, `_taught_spelling` and the hand-over with `find_parked` (5980-6398); the decision sentences; `FileReport`; `_park_it`; `_sort_one`; the CLI. | The hand-over files through `_file_into`, the one road for the pass and the hand-over (decision 132). `Spelling` is taught by the pass. `actions` imports these from the filer at load: `actions` is L3 and the filer is L3, and the filer never imports `actions`. |
| **Layers** | Section 5's table | As the table says: `copies`, `keywords`, `verdicts` and `reader_child` at L2; `intents`, `inbox`, `readme_ack` and `actions` at L3. | The plan's layers are kept. `intents`, `inbox` and `readme_ack` import nothing above L2, so L2 would also pass the layer test. L3 keeps them beside the filer and `actions`, which they serve, and keeps L2 to what a reading or a routing needs. Moving one down later would be a decision row, and is not this phase's. |
| **The plugins' paths** | E-6: `tests/plugins/isolation.py` and the rest | Flat files: `tests/plugin_isolation.py`, `tests/plugin_fakes.py`, `tests/plugin_agreement.py`, `tests/plugin_session.py` | `tests/` has no package folders. `test_suite_shape`, `patch_sites` and `repo_map` all read `tests/*.py`. A folder would need each of them taught a new place, which is a tools job of its own. |
| **The plugins' cut** | E-6: one plugin per concern (isolation, fakes, the test cache, agreement, the session) | Four plugins. `reading_in_this_process`, `room_is_the_absolute_length` and `no_real_test_cache_is_cleared` sit in `plugin_fakes` beside the other stand-ins every test gets; `plugin_isolation` holds the test's own folders (R4.2's table). | The autouse fixtures keep their order (the brief; note 007). pytest sets a plugin's fixtures up in the order the plugins are listed and, inside one plugin, by name: it walks `dir()`, which is alphabetical. Today's order is alphabetical too (one conftest), and it interleaves the plan's concerns, so a plugin can hold only a run of names that sit together in it. This cut is the nearest to the plan's that keeps the order: all five fakes-shaped fixtures are a monkeypatch of their own on a module seam, and the isolation is the test's folders (review 2, S15). |
| **No re-export from `conftest.py`** | E-6: conftest re-exports the builders, so the 43 importers (R4.2.3) keep working | Every `from tests.conftest import ...` line is retargeted to the module that now holds the name (`tests.builders` or a plugin). `conftest.py` keeps only its docstring and `pytest_plugins`. | One home per name, as P3 did for store helpers. A re-export would be the facade this phase avoids. |
| **The test split's names** | E-3: `test_copies.py`, `test_intents.py`, ... | Exactly those: `test_copies.py`, `test_intents.py`, `test_inbox.py`, `test_readme_ack.py`, `test_actions.py`, `test_keywords.py`, `test_verdicts.py`, `test_reader_child.py`. | One component per module, each with its own test file (CLAUDE.md). The owner edge in the map is drawn from the file name. |

### 2.2 Carried-forward items (`ORCH/carry-forward.md`)

*Phase 4 items (its section "Phase 4 (the sorting engine)"):*
- **The lock leak** (`test_two_takes_in_one_clock_tick_write_two_tokens` leaves `locking._unreleased` holding a path).
  Taken: P4.1 R4.1.1 and R4.1.2, the first requirement of the first job.
- **`tests/samples.py` into `INPUT_PATHS`.** Taken in P4.10, R4.10.8, with the rebuild.
- **The router's "for one release" wording** (router 154-156 and 191-195, curated 41), and router 121's
  `tracker.content_check.Evidence`. Taken in P4.10, R4.10.9. P4.10 is the job that touches the router's imports.
- **`OTHER_DOCUMENT` and `PREPARED_DIR_NAME` reached through the filer in four test lines** (test_scaffold 704,
  test_ledger 832, test_api 6204 and 6587). Split by when each name leaves the filer (review 1, S5):
  - `OTHER_DOCUMENT`'s three lines (test_scaffold 704, test_api 6204 and 6587) are taken in P4.8 (R4.8.3). The
    filer's only reader of `OTHER_DOCUMENT` is the received list (1325-1404), which P4.8 moves, so the filer stops
    importing it there and the three lines would fail from P4.8 on.
  - `PREPARED_DIR_NAME` (test_ledger 832) is taken in P4.13 (R4.13.2). The filer reads it to the end (2695, 3138,
    3711, 5733, 6129 and more), so the line works until then.
- **The filer's curated note's older wording about `holds_the_row`** (P3.5). Taken in P4.4, R4.4.12, when the
  filer's node is rewritten for the first move.

*Any-phase items this phase reaches:*
- **"Any phase that moves a module": patch_sites' written limits.** Taken. Every move job reads the tool's report
  and also greps `tests/` by hand for each moved name, in these forms:
  - `setattr("tracker.x.y", ...)` with the target as a string;
  - a store through a parameter (F6.3);
  - a helper that imports the module.
  The job's before.txt records the result.
- **"Any phase that moves a module": `monkeypatch.setitem` outside patch_sites.** Taken. At `68b9212` the only
  `setitem` targets are `sys.modules`, `api.COMMANDS` and `reasons.SHORT_REASONS`. No job here moves them, and each
  move job greps `setitem(` for what it moves.
- **"Any phase that adds or moves module state": the register's blind spots.** Taken. Three register keys move:
  `("content_check", "_last_line")` in P4.10, and `("ocr", "_SAID")` and `("ocr", "_SESSION")` in P4.12. Each of
  those jobs runs `test_resident` and greps for the key's string form.
- **"Any phase": `hold.py` wording, and the admission, store, `after_install`, `store_helpers` and ledger notes.**
  Not taken. This phase edits none of those files beyond the retargets each job names.
- **"A tools job (any phase)": the mypy upgrade rule, and `repo_map.py` reading `ast.AnnAssign`.** Not taken. No
  tool is upgraded. Four annotated module-level names move (measured at `68b9212`; the first draft of this SPEC said
  none did, which was wrong):
  - `FORM_VARIANTS` (content_check 341) and `_last_line` (683) move to `keywords` in P4.10;
  - `_SAID` (ocr 1557) and `_SESSION` (1834) move to `reader_child` in P4.12.

  The map sees none of them before or after the move, so no export or edge changes and the item stays carried. The
  annotated names that stay are `_STOP` and `_COULD_NOT_START` (content_check), and `MODEL_TIERS`, `SETTINGS` and
  `_NOTES` (ocr). The filer has none. Each move job runs the grep in R4.4.13's form and lists what it finds.
- **`Final` key constants** (P2.11's note: "the rest stay plain until a typed reader needs one"). Taken in P4.1,
  R4.1.5. The filer's typed ops are that reader, for `OP_KEY`, `FROM_KEY`, `TO_KEY` and `DIGEST_KEY`. The map does
  not see an annotated constant, as with the five `Final` keys already there (carry-forward: "`Refuse` and the `Final`
  keys are not in the map"). The tools item stays carried.
- **The phase-3 notes that name a phase-4 file.**
  - P3.5's `holds_the_row` wording: taken, above.
  - P3.6's probe of the lock leak: taken, above.
  - P3.7's `COMPOSERS` note: taken in P4.6 and P4.9.

## 3. Rules every job follows

**The gate.** This phase reaches the engine, so each job runs the whole suite once (section 9), under PY311 (the floor)
and PY314 (the office's). The order:
1. Dead code is deleted in the changed files first: unused imports and locals, commented-out code, and any
   module-level name nothing uses.
2. `python -m pytest -q -n auto`, the whole suite. A gate never adds `-m "not corpus"`.
3. `python -m ruff check .`
4. `python tools/repo_map.py check`
5. `python tools/vocab_report.py check`
6. `python tools/typecheck.py check`
7. `python tools/patch_sites.py check`

Each job also runs its named tests first, as each file's own process, before it commits. That is the quick loop. The
whole suite is the gate.

**What the base already fails.** At `68b9212`, on PY314 only,
`tests/test_api.py::test_importing_the_api_opens_no_file_but_the_programs_own` fails: the interpreter opens
`/dev/urandom` at import. The suite skips 26 tests on this platform.
- Each job's before.txt records the whole suite at its own base, on both interpreters.
- A job passes when its failures and skips are the same set as at its base.
- A new failure is the job's to fix. A failure that disappears is said in the report.

**Re-measure.** Every line number here is at `68b9212`. Each job after P4.1 measures its anchors again on its own
base, by the name that the anchor gives (a function, a constant, a quoted line). If a named thing is not where the
range says, or a range holds a name that the list does not give, stop and ask.

A range is anchored on its first and last definitions, not on its first number. The decorators of a moved definition
(`@dataclass(...)` above `AssignResult`, filer 5567, or above `ContentResult`, content_check 259) and the `#:` or `#`
comment block directly above it always move with it, whether or not the range's first number covers them. The same
holds for a section header (`# ---- name ----`) that a table says moves.

**The map, the docs and the decision rows:**
- Run `python tools/repo_map.py update` in the same commit as the code, after any edit to
  `docs/repo-map.curated.json`.
- A new module gets all of the following in the commit that creates it:
  - a curated node (a role, and notes carrying the reasoning, as its neighbours' do);
  - a row in `tests/test_layers.py`'s `LAYERS` (151-215, with the comment above the layer's set, in its neighbours'
    form) and in `DOMAINS` (223-261);
  - a line under its layer in `docs/architecture.md`;
  - a line in `tracker/__init__.py`'s module list, in the format `- name          : description`, placed after the
    module it came from;
  - its own `tests/test_<module>.py`;
  - a decision row in `pilot/DECISIONS.md`, in P328's form.
- The count in `docs/architecture.md` (line 29, "forty-six") rises by one per new module:
  - forty-seven at P4.4, forty-eight at P4.6, forty-nine at P4.7, fifty at P4.8, fifty-one at P4.9;
  - fifty-two at P4.10, fifty-three at P4.11, fifty-four at P4.12.
- Domains: `copies`, `intents`, `inbox`, `readme_ack`, `actions` and `keywords` go in `sorting` (with `router` and
  `filer`). `verdicts` and `reader_child` go in `reading` (with `content_check` and `ocr`).
- A new test file or helper module gets a curated node in the commit that creates it. This covers each
  `tests/test_<new>.py`, each plugin file, and `tests/builders.py`'s rewritten role. Write it in the form of
  `tests/store_helpers.py`: a role saying what it holds, and notes saying where it came from and why.
- Decision rows, in landing order:
  - P329 (P4.2), P330 (P4.3), P331 (P4.4), P332 (P4.6), P333 (P4.7);
  - P334 (P4.8), P335 (P4.9), P336 (P4.10), P337 (P4.11), P338 (P4.12).
  - P4.1, P4.5 and P4.13 change no rule a row records, and add none.
  - A job that lands out of order takes the next free number and says so.

**A move is a move:**
- Code moves byte for byte, with its comments and words. The only exceptions are the edits a requirement names.
- The new module imports what its moved code reads, by name, so the bodies stay byte for byte.
- The old module imports back by name only what it still uses itself. Nothing is imported back for a reader.
  - No `# noqa: F401` line is written.
  - ruff fails on an import-back that nothing uses, and that is the check.
- Every reader in `tracker/` and `tools/` of a moved name is retargeted to its new home in the same commit. This
  includes:
  - an attribute read (`filer.X`);
  - the prose pointers in docstrings and comments (``tracker.filer.X``, `:func:` roles);
  - the curated map's notes.

  The job greps `tracker tools docs` for each moved name and lists the hits in before.txt.
- Tests:
  - A test that reads, through the old module, any name the old module no longer holds after the job is retargeted
    in the moving job, to the name's defining module. That covers two kinds of name:
    - a moved name the old module does not import back;
    - an imported name whose last reader in the old module moved, so that ruff's F401 makes the old module drop the
      import (for example `PATH_TOO_LONG`, which the filer imports from `layout` for `copies`' code alone).
  - "Reads" includes a read that captures the original beside a stand-in (`real = filer_module.acquire_lock`): the
    capture goes to the defining module, and the `setattr` beside it follows section 4.0's table.
  - Each move job's before.txt lists the old module's imports that ruff will drop after the move, with every read of
    each in `tests/` (`grep -rnE "\b<old>(_module)?\.<name>\b|from tracker\.<old> import[^#]*\b<name>\b" tests`, and
    the multi-line `from ... import (` form by hand). Measured at `68b9212` with this SPEC's move lists, the only such
    reads are:
    - P4.4: test_rollover 1339 (`filer.PATH_TOO_LONG`) and test_scaffold 926 (`filer_module.acquire_lock`);
    - P4.8: test_scaffold 704, test_api 6204 and 6587 (`from tracker.filer import OTHER_DOCUMENT`);
    - P4.11: test_scanner 388, 830 and 859 (`real = content_check_module.sha256_of`);
    - P4.12: test_ocr 1661 (`real = ocr.pid_alive`).
    No module under `tracker/` or `tools/` reads such a name through the old module.
  - A test that reads a moved name the old module still imports back for its own use may wait for P4.13, which
    retargets every such read.
- Docs:
  - `docs/runbook.md` and `docs/tools.md` name no private function. Measure that with a grep, and retarget any
    public name they give.

**The stand-ins follow the readers** (A-4). A `monkeypatch.setattr(<module>, "<name>", ...)` works only while the code
under test looks the name up in `<module>`'s namespace. Today every piece of the filer reads the filer's namespace, so
one stand-in on `filer` reaches all of them. After a split, that is true only if the stand-in is set on every module
that now holds a piece of the old code and reads the name as a global. The rule:
- **The rule.** In the commit that moves the code, each stand-in is set on every module that reads `<name>` as a
  global after the move. This holds whether `<name>` is defined there (a function the job moves) or imported there
  (`sha256_of`, `is_cloud_placeholder`, `read_index`, ...). This is exactly today's behaviour, spread across the new
  modules.
- **Write it as a loop** over a literal tuple of modules, which patch_sites follows:
  `for module in (filer, copies): monkeypatch.setattr(module, "sha256_of", ...)`. Where there is one reader, write
  one `setattr`.
- **Where the readers are.** A moved function's readers are its callers. For example, `_move_whole` moves to
  `copies` in P4.4, but every caller stays in the filer until P4.6, so its stand-ins stay on `filer` until then. The
  defining module is a target only if its own code calls the name.
- **Reads from outside the engine.** A module outside the engine (`reminder`, `rollover`) that from-imports the name
  at call time reads it from the module it imports, which the job retargets. The stand-in follows that import:
  test_reminder 1794 goes to `inbox` in P4.7, and test_rollover 1407-1408 goes to `readme_ack` in P4.8.
- **The table.** Section 4.0 gives, for every filer stand-in name, the modules that read it after each job. Each
  move job applies the rows whose readers change at that job.
- **Attribute reads.** A stand-in on a module attribute that the code reads as an attribute (`ocr.awake_clock()`)
  needs one target: the module the attribute lives on after the move.
- **Not followed by the tool.** A stand-in the tool cannot follow is read by hand and listed in before.txt. This
  covers a helper that takes `monkeypatch` as a parameter (F6.3) and a string target (test_filer 516,
  `"tracker.filer.is_cloud_placeholder"`).
- **Stop and ask** if a stand-in cannot reach the code it replaces under this rule (for example, a name read at load
  into a second name).
- **Before and after.** Each move job's before.txt holds `python tools/patch_sites.py report tracker.<old>`, with
  `report tracker.<new>` after. The accept-when: every stand-in in the before list has its counterparts after, one
  on each module that the table names; none is listed `unread`; and the tool's `check` passes.

**The state register** (`tracker/resident.py`). A module-level name in the register that moves keeps its
`(module, name)` key in step, in the same commit, and the test_resident lines that name it move with it. phase 7 owns
these, and this phase moves the code that reads them, not who owns them:
- the filer's per-drop state (A-11: `_ReturnRun`, `_SortContext`, the in-place `run.context` edit in
  `_decide_attachment`) stays in the filer;
- the could-not-start list (A-7: `content_check._COULD_NOT_START`) stays in `content_check`.

**The layer table, the cycles and CLAUDE.md:**
- Every new module's layer is given in its job. No load-time import may point upward.
- No new `CALL_TIME_CYCLES` entry is added. If `tests/test_layers.py`'s cycle test (620) reports one, stop and ask.
- P4.9 moves the call-time filer → scanner edge to `actions` → scanner (R4.9.7-R4.9.10). Every CLAUDE.md change this
  SPEC makes is a requirement with its exact old and new text, and no other CLAUDE.md line changes.

**`COMPOSERS`** (`tests/test_layers.py` 480, at `68b9212`: `{filer, households, manifest, reminder, scanner}`).
- `intents` joins in P4.6 and `actions` joins in P4.9. Each takes a decision row, P332 and P335.
- The filer stays: `_taught_spelling` and the hand-over compose events.
- No door module joins.
- If the composer test names any other module after a move, stop and ask.

**The admission pin.** `ADMISSION_PIN[6]` (`tests/test_admission.py`, 260 parts) reaches `layout`, `bounds`,
`ledger`, `records` and `reasons`.
- No job here moves or edits a closure part. `OPENED` joins `index`, which is not in the closure.
- Each job runs `test_admission` in its suite, and its accept-when says the pin is unchanged.
- If a digest changes, stop and ask. A raised version is never this phase's.

**Types:**
- **Rules.** `typecheck.py check` fails when a file gains an error, and when a file with no entry has any. A new module
  therefore has to be born clean, so P4.1 brings filer, content_check and ocr to zero before anything moves. No job
  may add an error anywhere. A job that edits a module with entries (router 2) leaves them as they are.
- **The style of a fix** is P3.1's: an annotation or a `cast` that states what the code already relies on, with a
  comment where the reason is not plain, or a distinct local name where one name held two types. A fix never adds a
  check, a branch or an `assert`.

**Routing code and the office backtest.** "Routing code" here means the matcher, the keyword fold, the router, the
catalog and the reading: what `tools/backtest.py` and `tests/test_real_corpus.py` exercise (`route_file` and
`content_check.extract`).
- Each job says whether it moves routing code. These do: P4.10 (the matcher), P4.11 (the judgment's shapes and the
  cache the router reads) and P4.12 (the reading's child). P4.1 adds annotations inside the reading's code but moves
  nothing.
- No job edits the catalog, a keyword, a typed case or the matcher's logic.
- The office backtest runs before phase 4 merges to `main` (section 6).

**The vocabulary report.** A job that adds a file to `tools/vocab_report.py`'s `INPUT_PATHS` (107-114), or edits a file
already in it, runs `python tools/vocab_report.py build` in the same commit. The report's counts and hits must come out
unchanged. Only the list of files it reads may change.

**Golden.** `tests/golden/` is never re-recorded. Every job's accept-when includes: "`pytest tests/test_golden.py`
passes and every recording in `tests/golden/` is unchanged (`git diff --stat 68b9212 -- tests/golden` is empty)".

**Windows.** The `windows` label is only for a job that touches the held engagement lock, the atomic replace, path
handling, or a Windows-only test. Each job says whether it does and gives the office's
`pilot\wintest\run_checks.ps1 -Tests ...` list. Because this phase reaches the engine, the office's Windows check of
the stack runs the whole suite (no `-Tests`) once, before the merge (section 6).

**Safety:**
- Tests use made-up data only, and nothing points at a real clients root (decision 185).
- Commit signing stays on.
- No model identifier is written into anything committed.
- The standing rules' wording (`STANDING_RULES` in `tracker/__init__.py`) is not touched.
- No job changes `SCHEMA_VERSION` or `ADMISSION_VERSION`.
- No generative AI reads a client document, and every routing decision stays deterministic.

## 4. The jobs, in landing order

| Job | Title | Cost | Tier | Depends on | Routing code | Windows |
|---|---|---|---|---|---|---|
| P4.1 | The lock leak; type burn-down in filer, content_check and ocr; `candidates` and the ops typed (A-8) | M | Opus | — | no (annotations only) | no |
| P4.2 | `conftest.py` into plugins (E-6) | M | Sonnet | P4.1 | no | no |
| P4.3 | One after-routing road, `_settle` (A-3) | M | Opus | P4.2 | no (the filer's decision, not the router) | no |
| P4.4 | `copies.py`: names, room, copies and moves (A-1 step 2) | L | Opus | P4.3 | no | **yes** |
| P4.5 | A person's refusals named once; `_here` (A-10) | S | Sonnet | P4.4 | no | no |
| P4.6 | `intents.py`: the write-ahead intents (A-1 step 3) | M | Opus | P4.5 | no | **yes** |
| P4.7 | `inbox.py`: walking the inbox (A-1 step 4) | M | Opus | P4.6 | no | no |
| P4.8 | `readme_ack.py`: the received list and the refresh (A-1 step 5) | S | Opus | P4.7 | no | no |
| P4.9 | `actions.py`: a person's actions and the rescan (A-1 step 6) | L | Opus | P4.8 | no | **yes** |
| P4.10 | `keywords.py`: the matcher out of content_check (A-5) | M | Opus | P4.9 | **yes** | no |
| P4.11 | `verdicts.py`: the judgment's shapes and the verdict cache (A-5) | M | Opus | P4.10 | **yes** | no |
| P4.12 | `reader_child.py`: the reading's child and its supervisor (A-6) | M | Opus | P4.11 | **yes** | **yes** |
| P4.13 | The moved names read from their home; a guard | S | Sonnet | P4.12 | no | no |

**Tiers** (PROMPT-refactor section 1.3):
- Opus for the following:
  - every move out of the filer, because each one carries a stand-in list with targets that change module;
  - `_settle`;
  - `reader_child`;
  - the two content_check moves, because the shapes move with the cache;
  - P4.1, because its type fixes sit inside the decision and the write-ahead path.
- Sonnet for the following:
  - E-6, which moves code with exact lists and proves the order mechanically;
  - A-10, which names sentences without changing a word;
  - the last read-from-home job.

Every job edits `tests/test_layers.py`, `tests/test_filer.py` or the map, so they are built in this order, one session
each.

---
### 4.0 The filer's stand-ins, by reader

`python tools/patch_sites.py report tracker.filer` at `68b9212` gives 77 stand-ins in 9 files (29 defined, 48
imported, 0 unread). The table below shows, for each name, the sites and the modules whose code reads the name as a
global, at the base and after each move job that changes them.
- The readers were computed from the filer's AST at `68b9212`, with this SPEC's move lists: each top-level
  definition's `ast.Name` reads, mapped to the module that the definition moves to.
- Each move job re-derives its rows the same way on its own base, and records them in before.txt.
- "Readers" is the set the rule in section 3 sets each stand-in on. A test file split by a job carries its stand-ins
  with it.

| Name | Sites (`tests/`) | Readers: base → after each job that changes them |
|---|---|---|
| `_move_whole` | test_filer 3963, 4006; test_runner 1555 | filer → P4.6: filer, intents → P4.9: actions, filer, intents |
| `_copy_whole` | test_errors 987; test_filer 4411 | filer → P4.6: filer, intents → P4.9: actions, intents |
| `_existing_copy` | test_errors 986 | filer → P4.6: filer, intents → P4.9: actions, filer, intents |
| `_review_copy_path` | test_filer 6938 | filer → P4.6: filer, intents → P4.9: actions, filer, intents |
| `README_LOCK_WAIT_SECONDS` | test_scaffold 982 | filer → P4.4: copies |
| `acquire_lock` | test_scaffold 944 (and its capture of the original at 926, which section 3's test rule sends to `tracker.locking` in P4.4) | filer → P4.4: copies |
| `limit_for` | test_api 4818 | filer → P4.4: copies |
| `make_writable` | test_filer 9794 | filer → P4.4: copies |
| `mark_from_internet` | test_filer 9509, 9529, 9659, 9681, 9697 | filer → P4.4: copies |
| `pid_alive` | test_filer 4352, 4376 | filer → P4.4: copies |
| `path_limit` | test_rollover 1331 | filer → P4.4: copies, filer → P4.9: actions, copies, filer |
| `is_cloud_placeholder` | test_content_check 1922; test_filer 516 (string target), 1168, 1408, 1617, 1926, 3345, 5374, 5665, 7325, 7789, 8613, 8652 | filer → P4.4: copies, filer → P4.6: + intents → P4.7: + inbox → P4.9: + actions |
| `locate` | test_errors 985 | filer → P4.4: copies, filer → P4.6: + intents → P4.7: + inbox → P4.9: + actions |
| `sha256_of` | test_filer 1412, 1521, 1534, 1570, 1651, 1904, 3013, 3402, 9372 | filer → P4.4: copies, filer → P4.6: + intents → P4.7: + inbox → P4.9: + actions |
| `read_index` | test_filer 1048, 3680, 6442, 9217 | filer → P4.4: copies, filer → P4.6: + intents → P4.8: + readme_ack → P4.9: + actions |
| `_do_op` | test_api 6338, 6344, 6379, 6389; test_filer 3988 | filer → P4.6: filer, intents → P4.9: actions, filer, intents |
| `_may_touch` | test_errors 983 | filer → P4.6: intents |
| `place_problem` | test_errors 984; test_filer 8775 | filer → P4.6: intents |
| `_a_copy_to_act_on` | (driven, not replaced: test_errors 975-993) | filer → P4.6: intents. test_errors calls it on `intents` from P4.6. |
| `_record` | test_api 6469, 6475; test_containers 260; test_filer 6296 | filer → P4.9: actions, filer |
| `_carry_out_a_persons_ops` | test_filer 9736 | filer → P4.9: actions |
| `iter_drops` | test_filer 1048, 7213 | filer (stays the only reader) |
| `unlistable_folders` | test_reminder 1794 | filer. The site drives `reminder`, whose call-time import P4.7 retargets, so the site goes to `inbox` in P4.7. |
| `received_for` | test_scaffold 820, 943 (and the capture at 926, which goes to `readme_ack` in P4.8) | filer → P4.8: readme_ack |
| `readme_returns` | test_filer 9200 | filer → P4.8: readme_ack |
| `write_readme` | test_api 7636; test_filer 9768 | filer → P4.8: readme_ack |
| `refresh_household_readme` | test_rollover 1408 (and its read at 1407) | no filer reader. `rollover` imports it at call time (764, 1234), so the site goes to `readme_ack` in P4.8. |
| `load_manifest` | test_filer 1048, 6444 | filer → P4.8: filer, readme_ack → P4.9: actions, filer, readme_ack |
| `load_engagement_info` | test_filer 9185 | filer (stays) |
| `read_once` | test_containers 303; test_filer 5153 | filer (stays) |
| `_decide_across`, `_decide_attachment`, `_unaccounted_in_opened`, `_spoken_for_by_an_open_intent` | test_runner 4202; test_containers 259; test_filer 587; test_filer 8112 | filer (stay) |

The test_filer 1048 line patches three names in one literal-tuple loop (`iter_drops`, `load_manifest`, `read_index`).
After P4.4 it becomes one loop per name, or a loop of `(module, name)` pairs. Use the form patch_sites follows (its
docstring), and test the form with `report` before committing.

---

### P4.1 The lock leak; type burn-down in filer, content_check and ocr; `candidates` and the ops typed (A-8)

- **Cost:** M.
- **Tier:** Opus. The type fixes sit inside the decision (`_decide_across`, `_sort_one`), in the write-ahead path
  (`_do_op`, `_finish_the_ops`) and in the reading child's supervisor.
- **Findings:** the lock leak (carry-forward); section 9 ("every phase starts by burning down the type errors in the
  modules it will move"); A-8.
- **Depends on:** nothing.
- **Routing code:** no. It changes annotations and casts in `content_check` and `ocr`, and moves nothing. The
  backtest does not need to run on it alone.

**Requirements:**

- **R4.1.1, the lock leak (first).** `tests/test_locking.py::test_two_takes_in_one_clock_tick_write_two_tokens`
  (1254) gets a stand-in on `locking._unreleased`, as its first statement after its `import tracker.locking as
  locking_module`. The form is that of test_locking 1385 and 1402: `monkeypatch.setattr(locking_module,
  "_unreleased", [])`. Nothing else in the test changes. This is a test-only fix: the leak is the test's (its two takes
  in one tick leave a path the real list keeps). `tracker/locking.py` is not edited.
- **R4.1.2, the test that fails before and passes after.** Add
  `test_the_one_clock_tick_test_leaves_no_lock_for_the_engine_after_it` to `tests/test_locking.py`.
  - It runs, in one fresh process, the test of R4.1.1 followed by
    `tests/test_resident.py::test_a_second_command_finds_nothing_the_first_left`:
    `[sys.executable, "-m", "pytest", "-q", "-p", "no:xdist", "-p", "no:randomly", "-p", "no:cacheprovider",
    "<the first node id>", "<the second node id>"]`.
  - It runs with `cwd=REPO` and `env=child_env(drop=(settings.ENV_SETTINGS_DIR, store.ENV_STORE,
    settings.ENV_DATA_HOME, "PYTEST_CURRENT_TEST"))`, as conftest's `run_in_copy` (1375-1383) builds a child's
    environment.
  - It asserts the return code is 0, and puts the child's last 40 lines in the assertion message.
  - Commit it first, without R4.1.1. Measured at `68b9212`: the pair fails
    (`PY311 -m pytest -q -p no:randomly "tests/test_locking.py::test_two_takes_in_one_clock_tick_write_two_tokens"
    tests/test_resident.py` gives 15 failed, 29 passed, each failure `engine retired: lock-left`). The commit
    message records the failing run, and the second commit (R4.1.1) makes it pass.
  - If the named resident test passes after the leaking test at the job's base, take the first failing test from
    the measured 15 and say which one in before.txt.
- **R4.1.3, the filer's 51.** Bring `tracker/filer.py` to zero errors, in P3.1's style (section 3, Types). Groups at
  `68b9212` (the `mypy` message for each is in `docs/typecheck-baseline.json`):

  | Lines | What mypy reads | The fix |
  |---|---|---|
  | 625 | `limit - room` with `room: int \| None` | `cast(int, room)` at the read. The `if candidate is None` branch is reached only after a room was measured, and the comment says so. |
  | 1189, 1194, 1195 (two), 1198, 1200 | `str \| None` and `Path \| None` reaching `len`, `measured_length`, `/` and `is_reserved_name` | A typed local or a cast, each stating the value the enclosing branch has proved |
  | 2331 | `by_path.get(path)` assigned to `entry: IndexEntry` | A distinct local name for the `get` result |
  | 2448 | `_row_these_bytes_left` (`int \| None`) assigned to `position: int` | Annotate `position: int \| None` where it is first bound |
  | 2747, 6960 | `Path \| None` to `_make_again`'s fourth parameter | A cast at the call, stating what the caller has proved |
  | 3243-3245 (four), 3278, 3290 | `op` is `dict \| None` in `_finish_interrupted_moves` | With R4.1.5, a cast to `ledger.IntentOp` where the `None` case has already returned |
  | 4791, 4798-4911 (thirteen), 5497, 5507 | `_by_the_name`'s `accepting: list[tuple[_ReturnRun, object]]`, so `kept` reads as `object` | R4.1.4 |
  | 5741 | `grown = []` needs a type | `grown: list[str] = []` (or the element type the loop appends; measure it) |
  | 5809, 5810, 5873, 5876, 5877, 5879, 5955, 5957, 6664, 6692, 7198, 7205 | `Path \| None` to `sha256_of`, `_op`, `_move_whole` and `_copy_whole`, in a person's actions | A cast, or a typed local bound once after the branch that proves it |
  | 7448, 7455, 7461, 7467, 7468 | `str \| None` in `rename_request`'s loop | A typed local, as above |

- **R4.1.4, the routing typed (A-8).** In the filer:
  - `_NameStage.kept` (4607) becomes `list[tuple[_ReturnRun, Routing]]`.
  - `_by_the_name`'s `accepting` (4634) becomes `list[tuple[_ReturnRun, Routing]]`.
  - `_the_home(accepting, routed)` (4981) is annotated `accepting: list[tuple[_ReturnRun, Routing]]`, with its return
    as `tuple[_ReturnRun, Routing]`.
  - These parameters are annotated with `Routing`, or with `Routing | _NoRouting` where `_NO_ROUTING` can reach them
    (measure each by its callers): the `routing` of `_with_the_name` (4574), of `_with_the_wanting_return` (4943, and
    its `home_routing`), of `_waits_for` (4966) and of `_file_it` (5176).
  - `Routing` joins the filer's `from tracker.records import (...)` (314), in its alphabetical place.
  - `rename_request(head: object)` stays. `head` is a freshness token the function compares and never reads, so
    `object` is its honest type. The audit's line on it is answered here.
- **R4.1.5, the ops typed (A-8).** Every write-ahead op in the filer is a `ledger.IntentOp` (ledger 630).
  - `_op` (1790) returns `ledger.IntentOp`, and its local is annotated `op: ledger.IntentOp = {...}`.
  - Every `op: dict` parameter becomes `op: ledger.IntentOp`, and every `ops: list[dict]` becomes
    `ops: list[ledger.IntentOp]`. These are `_refuse_a_step_outside` 1821, `_refuse_a_step_through_a_link` 1832,
    `_mark_a_move_into_review` 1866, `_do_op` 1887, `_intend` 1929, `_prove` 2006, `_carry_out_a_persons_ops` 2067,
    `_finish_the_ops` 3043, `_the_trouble` 3301, `_do_all_or_take_back` 4165 and `_intend_and_do` 5109.
  - The local lists at 5858 and 7114, and every other local the measurement below names, are typed the same way.
    Examples are `came_from` at 2043, `_a_copy_to_act_on`'s return at 3082-3110, the appends at 4176, 5320 and 6144,
    and 6213, 7476 and 7495.
  - Where an op arrives from the record as a plain `dict` (a folded intent's steps), the cast is
    `cast(ledger.IntentOp, ...)` with the comment `# the admission held this step to the rule`.
  - **What this needs in ledger (measured).** Typing the ops makes every `op[ledger.OP_KEY]`-style read a TypedDict key
    read. With today's plain constants, mypy refuses each one (`TypedDict key must be a string literal`). The four step
    keys therefore become `Final`, as `EVENT_KEY`, `KEY_KEY` and `RULES_KEY` already are (P2.11):
    `OP_KEY: Final = "op"`, `FROM_KEY: Final = "from"`, `TO_KEY: Final = "to"`, `DIGEST_KEY: Final = "digest"` (ledger
    238-241). `OPS_KEY` stays plain.
  - The ledger docstring's list of `Final` keys (161-163) and the ledger node's curated note ("The key constants those
    two writers read through (EVENT_KEY, KEY_KEY, RULES_KEY, REMOVED_KEY, INFO_KEY) are Final") each gain the four
    names, and the words "and the filer's steps (P4.1)".
  - `ledger.op_ends(op: dict)` (742) becomes `op_ends(op: Mapping[str, object])`. The admission hands it an untrusted
    `dict` and the filer an `IntentOp`, both of which are `Mapping[str, object]`. Its body already reads through
    `.get` and `str(...)`, so the body does not change. `Mapping` comes from `collections.abc`, in ledger's imports.
  - Measured on a scratch copy at `68b9212` with `Final` keys and the ops typed: the literal-key errors are gone, and
    what remains are the 16 locals and calls named above, each one an annotation.
- **R4.1.6, `candidates` as `tuple[str, ...]` (A-8).**
  - `_park_it`'s `candidates` (5287) becomes `candidates: tuple[str, ...]`.
  - The one string passed to it, `candidates=""` at 5492 (`_sort_one`'s across-household park), becomes
    `candidates=()`.
  - `CANDIDATE_SEP.join(())` and `CANDIDATE_SEP.join("")` are both `""`, so the row is byte-identical.
  - The `candidates=""` at 5908 and 6173 are `IndexEntry` fields (`IndexEntry.candidates: str`, records 445) and stay.
  - Q-B is not touched: the re-send road still parks with no shortlist. P4.3 names it.
- **R4.1.7, content_check's 9.**
  - 842: `key=first.get` becomes `key=lambda key: first[key]` only if `first` holds every key. Otherwise use
    `cast(Callable[[str], int], first.get)`. Measure which; the cast is the default, because it changes no behaviour.
  - 871, 881 and 1070: `cast(re.Match[str], ...)` at each `match(...)`, with the comment that the pattern matches
    every form key (871, 881) or the separator (1070) by construction.
  - 1558 and 1560: the loop variable `question` is bound to a `RowQuestion` earlier in the same function and to a
    `NameQuestion` here. The second loop's name becomes `asked`, in the `for` and in its three reads.
  - 2155: `in_a_child` returns `tuple[object, Extraction | None]`. `_read_in_a_child` casts the answer:
    `cast(Judgment, answer)`, with the comment `# judge returns a Judgment`.
- **R4.1.8, ocr's 8.** All are in the code P4.12 moves.
  - 1211 and 1292: `self._process.pid` is `int | None`. Use `cast(int, self._process.pid)`, with the comment
    `# started above`.
  - 1271, 1274 and 1275: `answer` is read as a tuple of fixed length. Annotate it where it is received as
    `tuple[Any, ...]`, which states what the pipe carries.
  - 1694: `self.device, why = cast(tuple[str, str], outcome.answer)` (measure the element types).
  - 1763 and 1773: `child` is `ReadingChild | None` after a branch that set it. Use a typed local bound after that
    branch, or a cast.
- **R4.1.9, the baseline.** `python tools/typecheck.py update` lowers filer 51 → 0, content_check 9 → 0 and ocr 8 → 0.
  The total reads 138 errors in 22 files, and `check` passes. ledger stays at 0, and no other file's count moves.
- **R4.1.10, the pin.** `ADMISSION_PIN[6]` changes in exactly one digest: `tracker.ledger.op_ends` (R4.1.5's
  annotation).
  - Re-pin by pasting `admission_digests()` under `ADMISSION_PIN[6]`.
  - Add the comment line above `ADMISSION_PIN`: "Pinned again under 6 when P4.1 typed op_ends' step as
    Mapping[str, object]: one annotation, no rule changed."
  - The four `Final` constants are digested by value (`repr`), so they do not move. If any other digest moves, stop
    and ask.

**Pin-move list:**
- `ADMISSION_PIN[6]` in `tests/test_admission.py`: `tracker.ledger.op_ends` only.
- `docs/typecheck-baseline.json`: filer, content_check and ocr leave the baseline.
- `docs/vocab-coverage.json` and `docs/vocab-coverage.md`: rebuilt with `python tools/vocab_report.py build`, because R4.1.7
  edits `tracker/content_check.py`, which is in `INPUT_PATHS` (section 3, the vocabulary report). The counts and hits
  come out unchanged; only the input hash moves. (Added after the first draft, which left it out.)
- The map: ledger's exports lose `OP_KEY`, `FROM_KEY`, `TO_KEY` and `DIGEST_KEY`. `repo_map.py` does not read an
  annotated assignment (carry-forward, "A tools job"), as with the `Final` keys already there, so `update` drops them.
  If any test or curated edge names one of the four as a ledger export, stop and ask.

**Patch sites:** none move. No stand-in replaces a function whose signature changes. The `_do_op` stand-ins (test_api
6338-6389, test_filer 3988) replace the whole function. Running the suite confirms that.

**Register:** unchanged.

**Tests:** the whole suite (section 3), including the new R4.1.2 test, `test_typecheck`, `test_admission`,
`test_ledger` and `test_golden`.

**Stop and ask:**
- An error in the table can be cleared only by a new check, branch or `assert`.
- `mypy` reports a new error outside the three modules and ledger.
- The pin moves beyond `op_ends`.
- The R4.1.2 test passes before R4.1.1.

**Accept when:**
- The gate passes.
- The baseline reads 138 in 22 files, with no entry for filer, content_check or ocr.
- The R4.1.2 test failed at its own commit and passes after R4.1.1. Both runs are in the report.
- Run on one worker in that order, `tests/test_locking.py` and `tests/test_resident.py` pass.
- `ADMISSION_PIN[6]` differs only in `tracker.ledger.op_ends`.
- `tests/golden/` is unchanged.
- **Windows:** no label. Nothing touches the lock's code, the atomic replace or a path. R4.1.1 is a stand-in in a
  test that runs on every platform.
- **Office `-Tests`:** `test_locking,test_resident` (the leak's pair).

---

### P4.2 `conftest.py` into plugins (E-6)

- **Cost:** M.
- **Tier:** Sonnet. It moves code with exact lists, and every claim it makes is proven mechanically (R4.2.6-R4.2.8).
- **Findings:** E-6.
- **Depends on:** P4.1. It goes before the moves because every later job imports builders from their new home.
- **Routing code:** no.

**The order the autouse fixtures run in** (review 2, S15; note 007). Measured at `68b9212` on PY311 and PY314, with
`--setup-plan` and with `request.fixturenames` in a one-line test, the eight function-scope autouse fixtures are set up
in this order, and torn down in the reverse:

1. `an_app_folder_of_its_own` (175)
2. `fills_asked` (518)
3. `no_real_test_cache_is_cleared` (542)
4. `no_task_scheduler_unless_faked` (365)
5. `reading_in_this_process` (226)
6. `room_is_the_absolute_length` (244)
7. `the_store_agrees_with_the_record` (903)
8. `the_view_agrees_with_the_readers` (874)

That is alphabetical, not the order of definition. pytest gathers a conftest's or a plugin's fixtures by walking
`dir()` of the module, which is sorted (`FixtureManager.parsefactories`, pytest 9.1.1). A plugin named in
`pytest_plugins` is a non-conftest plugin, so its fixtures are registered for the whole session, in the order the
plugins are registered (the list's order), and alphabetically inside each one; a test's autouse names are then
gathered from the session down. So after the cut the order is: each plugin in list order, and its own autouse
fixtures by name. That keeps today's order only if each plugin holds a run of names that sit together in the list
above. The plan's concerns interleave in it (isolation 1, fakes 2, the test cache 3, fakes 4, isolation 5-6), so no
cut that keeps isolation, fakes and the test cache apart can keep the order. The nearest cut that does (section 2.1,
"The plugins' cut") is:

- `plugin_isolation`: autouse 1, the test's own folders;
- `plugin_fakes`: autouse 2-6, the stand-ins every test gets, each a `MonkeyPatch` of its own on one module seam (the
  firm-cache fill, the after-install step's test-cache job, the scheduler and the floor's computer, the reading child,
  the room measure);
- `plugin_agreement`: autouse 7-8;
- `plugin_session`: no autouse fixture.

Measured by the writer on a scratch copy of `68b9212` cut this way by a script (top-level statements assigned by
name, the 43 importers retargeted): `--collect-only -q` lists the same 5,205 ids (diffed on PY311; the same count on
PY314); `request.fixturenames` filtered to the eight is the list above on PY311 and PY314; and `--setup-plan -q -p
no:xdist -p no:randomly` over the whole suite is identical to the base's once the object addresses in parametrize ids
(`at 0x...`) and the timing line are normalised. No `pytest_collection_modifyitems` and no new fixture dependency is
needed. (A plugin's fixtures are registered for the whole session, where a `tests/conftest.py` fixture is registered
for `tests/`; every collected test is under `tests/` (`testpaths`), so each fixture reaches the same tests, which the
setup-plan diff shows.)

**What moves** (`tests/conftest.py`, 1,383 lines at `68b9212`). The plugins are flat files, listed in `pytest_plugins`
in this order:

| New file | What moves into it (re-measure each by name) |
|---|---|
| `tests/plugin_isolation.py` | `APP_FOLDER` (151, with its `#:` comment), `own_folders` (155), `data_home_for` (165), autouse 1 `an_app_folder_of_its_own` (175), and `_ALSO_WALK` (with its `#:` comment above it; `an_app_folder_of_its_own` clears it and removes its folders, so it lives beside its first reader) |
| `tests/plugin_fakes.py` | autouse 5 `reading_in_this_process` (226), autouse 6 `room_is_the_absolute_length` (244), `on_a_mac` (265), the `REAL_*` captures, `_schtasks_unfaked`, `_launchctl_unfaked`, `_tmutil_unfaked`, `_TheFloorsPlatform`, `_not_a_mac`, `_the_floors_answer`, `stand_on_the_floor`, autouse 4 `no_task_scheduler_unless_faked` (365), `Said`, `FakeLaunchd`, `FakeTmutil`, `AMac`, `a_mac` (490), `REAL_FILL`, autouse 2 `fills_asked` (518), autouse 3 `no_real_test_cache_is_cleared` (542), `PATH_SETTINGS` (709), `_SHORT_FILE, _SHORT_FOLDER` (713), `refuse_what_windows_refuses` (716), `path_setting` (775) |
| `tests/plugin_agreement.py` | `KNOWN_DISAGREEMENTS`, `short_root` (576), `_check_view`, autouse 8 `the_view_agrees_with_the_readers` (874), `_store_check`, autouse 7 `the_store_agrees_with_the_record` (903) |
| `tests/plugin_session.py` | `REPO`, `TRIPWIRE_DIR`, `floors_data_home`, `real_places`, the `checkout_*` helpers, `child_env`, the tripwire and xdist hooks (`pytest_addoption` 1154, `pytest_configure` 1160, `pytest_sessionfinish` 1247, `pytest_testnodedown` 1269, `pytest_terminal_summary` 1280, `pytest_unconfigure` 1288) and their constants (`TRIPWIRE_HEADING`, `UNREADABLE_LOG`, `UNREADABLE_LOG_LINE`, `read_tripwire_log`, `tripwire_log_said`, ...), `RECORD_GOLDEN`, `ENV_OFFICE_SHAPED_FULL`, `office_shaped_copy` (1309, session scope), `run_in_copy` |
| `tests/builders.py` (exists) | The builders: `TEST_*` constants, `WINDOWS_PIPE_ENCODING`, `app_stdin`, `named_page`, `make_engagement`, `root_for_a_return_of`, `floor_return`, `sort_all`, `sort`, `seed_index`, `written_elsewhere`, `seed_statuses`. builders.py's own `from tests.conftest import TEST_CLIENT, make_engagement, named_page, sort` (26) goes, because those names now live in it. |

**Requirements:**

- **R4.2.1** — `tests/conftest.py` keeps its module docstring and one statement:

  ```
  pytest_plugins = ["tests.plugin_isolation", "tests.plugin_fakes", "tests.plugin_agreement", "tests.plugin_session"]
  ```

  The docstring is rewritten to say:
  - what each plugin holds;
  - why the plugins are listed in this order: pytest sets a plugin's autouse fixtures up in the list's order and,
    inside one plugin, by name, so the cut and the order together keep the order the suite was built on (the
    measured list above, which `test_suite_shape` pins, R4.2.6);
  - why the list is here and not in the root `conftest.py`. `tests/conftest.py` is loaded at start-up, because
    `testpaths = ["tests"]` or an argument under `tests/` always reaches it. Measured with pytest 9.1.1 on a scratch
    tree of the same shape: a plain run, a run of one file, a run from another directory and a run with `-n 2` all
    load the list.
  - If pytest refuses the list there ("non-top-level conftest"), it moves to the root `conftest.py`, the same
    mechanism, and the docstring says so. That is not a stop and ask.
- **R4.2.2** — Each plugin is a module docstring (the concern, the decision rows it upholds: 185 for isolation and the
  session, 89/91 and 101/102 for the agreement) followed by the code moved byte for byte, with the imports it needs.
  - **A plugin may import from a plugin listed before it in `pytest_plugins`, never from one listed after it** (review
    1, S3). Pytest imports and registers the list in order, so the earlier plugin is already in `sys.modules` (and
    already marked for assertion rewriting) when the later one imports a name from it. A plugin never imports a
    fixture function by name: pytest would register it a second time under the importing plugin, and the
    setup-plan diff (R4.2.8) would show the fixture's home move.
  - Measured at `68b9212` with an AST walk of each top-level definition's free names under R4.2's table, the cut
    needs exactly three such edges, all downward, and none of the names is a fixture. (The round-2 draft counted two:
    it put `_ALSO_WALK` in `plugin_agreement`, after its first reader in `plugin_isolation`, which was an upward edge
    it did not list. Found in round 3.)
    - `plugin_agreement` → `plugin_isolation`: `_ALSO_WALK` (read by `short_root` and both agreement fixtures). It is
      one list object, cleared and appended to, never rebound, so a from-import shares it;
    - `plugin_session` → `plugin_isolation`: `APP_FOLDER`, `own_folders`, `data_home_for` (read by
      `pytest_configure`, `pytest_unconfigure` and `office_shaped_copy`);
    - `plugin_session` → `plugin_fakes`: `REAL_HOST_SYSTEM` (read by `real_places`) and `stand_on_the_floor` (read by
      `office_shaped_copy`).
    Each is a module-level `from tests.plugin_<name> import ...` line, so the bodies move byte for byte. Each plugin's
    docstring names its edges and the rule above. `plugin_session`'s reads of `tests/builders.py` (`TEST_HOUSEHOLD`,
    `make_engagement`, by `office_shaped_copy`) are ordinary helper imports; no builder reads a plugin's name. The job
    re-measures the edges on its base with the same walk, and lists them in before.txt.
  - Module-level statements keep their relative order inside each file, and every `REAL_*` capture is still taken at
    import, before any test runs, as today. (Across files the order changes only where nothing depends on it: `REPO`
    is now bound after the captures, and reads nothing they bind.)
  - `an_app_folder_of_its_own`'s docstring says it is "Defined first in this file so it is set up before every other
    autouse fixture", which was never the reason (pytest orders by name). That sentence is corrected, the first of
    the two edits allowed inside a moved body: "Defined first in this file so it is set up before every other autouse fixture" becomes
    "In the plugin listed first, so it is set up before every other autouse fixture", with the rest of the sentence and
    the docstring as they are (the lines may be rewrapped).
  - The second, in the same docstring (review 3, S24): "the agreement fixtures below" becomes "the agreement fixtures
    (``plugin_agreement``)", because after the cut they are in another file. No other word inside a moved body changes.
  - **The old module docstring's reasoning moves with its code** (review 3, S24). `tests/conftest.py`'s module
    docstring (1-93 at `68b9212`) carries the reasoning for each piece that moves. Each of its paragraphs moves, word
    for word, into the module docstring of the file that now holds the code it describes, after that file's opening
    sentence (the concern and its decision rows, above):
    - the opening paragraph ("The agreement checks ... Three autouse fixtures hold that honest"), the view and store
      agreement, "One store per test" and "Looking changes nothing" → `plugin_agreement`. The opening's count is made
      true for that plugin, the one wording change this bullet allows, and it is named in after.txt;
    - the app folder of its own → `plugin_isolation`;
    - the real root (the tripwire) and the Mac's short temporary root → `plugin_session`;
    - reading in the test's own process → `plugin_fakes`;
    - making an engagement, sorting an inbox and seeding an index and a status → `tests/builders.py`.
    A paragraph that speaks to two of these goes to the first file it names, and the other file's docstring points to
    it in one sentence. after.txt lists each paragraph's first words and its new home, so a reviewer can check that
    none was dropped. R4.2.1's new conftest docstring then says only what R4.2.1 lists.
  - The tripwire import (`from tests.tripwire import sitecustomize as tripwire`, 112-145) goes to `plugin_session`.
  - conftest's `from tracker.filer import file_household_drops, refresh_household_readme` (128) goes to
    `tests/builders.py` (the `sort` builders read them). P4.8 retargets `refresh_household_readme`.
- **R4.2.3** — Every `from tests.conftest import ...` in `tests/` is retargeted to the module that now holds each name.
  At `68b9212` that is 43 files: 39 test files and the helper modules `api_driver.py`, `builders.py`, `passes.py` and
  `store_helpers.py` (`git grep -ln "^\s*from tests.conftest import" tests`). A plain
  `grep -l "from tests.conftest import"` also lists `test_suite_shape.py`, whose line 108 holds the words inside a
  made-up source string, not an import (below). `ensure` is re-exported by conftest from `tracker.index` today. Its
  four readers import it from `tracker.index`.

  After this job, `grep -rnE "tests[./]conftest" tests tools` finds only these, each listed in after.txt (review 1,
  S13):
  - prose that describes what conftest does, rewritten to name the plugin or builder that now does it (for example
    builders 277's ``tests.conftest.floor_return``, and the docstrings of test_ledger 4, test_store 4,
    test_store_check 4 and test_view 4, which name the agreement fixtures' home);
  - `tests/test_suite_shape.py` 108, `"from tests.conftest import make_engagement"`. It is a line of the made-up
    source that `test_the_guard_does_not_take_a_helper_or_a_word_in_a_string_for_a_test_file` feeds the
    helper-import scanner, to prove a helper import is not taken for a test file. It stays as it is: the test is
    about the scanner, and any helper's name proves the same;
  - `tests/test_patch_sites.py` 369, 557 and 840, the file name `tests/conftest.py` inside made-up repositories that
    the tool's own tests build. They stay;
  - `tests/conftest.py` itself, and test_tripwire and test_patch_sites lines that R4.2.4 changes on purpose.

  **Outside `tests/` and `tools/`** (review 3, S23). Code, documentation and the curated map also name
  `tests/conftest.py` as the home of what moves. The job runs `grep -rn "conftest" tracker docs README.md CLAUDE.md`
  (leaving out `docs/repo-map.md` and `docs/repo-map.json`, which are generated, and `docs/ROADMAP.md`, whose decision
  rows are history) and walks every string of `docs/repo-map.curated.json` for "conftest". Every hit goes in
  before.txt with one of two calls: **retarget** (it names conftest as the place a fixture, a builder, a hook or a
  stand-in lives, and it now names the plugin or builder that holds it), or **stays** (it speaks of conftests in
  general, as `tools/patch_sites.py`'s and `tests/test_patch_sites.py`'s notes on how pytest resolves a fixture do, or
  of conftest as the file that registers the plugins). Measured at `68b9212`:
  - `tracker/`: after_install 597 and scheduling 549 (the task-scheduler guard → `plugin_fakes`), ledger 67 and store
    104 (module docstrings; the agreement fixtures → `plugin_agreement`), layout 1120 (`on_a_mac`'s docstring; the room
    fixture → `plugin_fakes`), content_check 2002 (a `#:` comment; the child's stand-in readers → `plugin_fakes`);
  - `docs/`: architecture 212 (every test's settings folder → `plugin_isolation`; the session's tripwire verdict →
    `plugin_session`) and 221 (stays, naming conftest as an importer the guard checks; "imported by none" gains "nor
    named in `tests/conftest.py`'s `pytest_plugins`", R4.2.4), storage 544 (the agreement fixture → `plugin_agreement`);
  - the curated notes or roles of `tracker/content_check.py`, `tracker/store_check.py`, `tracker/ledger.py`,
    `tracker/runner.py`, `tracker/scheduling.py`, `tracker/view.py`, `tracker/store.py`, `tracker/layout.py`,
    `tracker/after_install.py`, `tools/corpus.py`, `tests/test_golden.py` (the `--record-golden` option →
    `plugin_session`), `tests/test_learned_keywords.py` and `tests/builders.py` (`make_engagement` and the rest now
    live in builders: that note's "make_engagement itself stays in conftest, which also keeps sort, seed_* and
    named_page" is rewritten to say so), `tests/test_store_check.py`, `tests/test_real_corpus.py`,
    `tests/samples.py`, `tests/tripwire/sitecustomize.py` and `tests/test_suite_shape.py`. Each gets the call above;
    the job re-measures the list on its base.
  - **The `tests/conftest.py` curated node.** Its role becomes "Registers the suite's four plugins
    (`pytest_plugins`), in the order that keeps the autouse fixtures' order (P329)", and its notes move to the nodes
    of the plugins that now hold what they describe (section 3 creates those nodes).
  None of these places is an admission closure part (`ADMISSION_PIN[6]` holds no docstring of `layout.on_a_mac`,
  `after_install` or `scheduling`, and ledger 67 and store 104 are module docstrings); if an `admission_digests()`
  value moves, stop and ask. The content_check edit moves the vocabulary report's input hash, so the job runs
  `python tools/vocab_report.py build` in the same commit, with the counts and hits unchanged.
- **R4.2.4** — The guards that name conftest:
  - test_tripwire 362: `if path.name == "conftest.py" or ...` becomes `plugin_session.py`. The shapes it allows sit
    at conftest 982, 1114-1115 and 1175, all of which move to `plugin_session`.
  - test_patch_sites 1444: `{"tests/conftest.py", "tests/test_filer.py"}` names the plugin file that now holds the
    stand-in it means. Read the test and name it.
  - test_suite_shape: `NOT_A_HELPER = {"conftest"}` stays. The plugins are helper modules by `the_helper_modules`'
    glob, and each one gets the curated node section 3 asks for.
  - test_suite_shape's `test_every_helper_module_is_imported_by_a_test_file` (76) would fail: a plugin that no test
    file imports by name reads as dead code: measured on the scratch cut, `plugin_isolation` and `plugin_agreement`
    are imported only by other plugins, never by a test file.
    The guard learns the one other way a helper is used. A module named in `tests/conftest.py`'s `pytest_plugins`,
    read with `ast` (the list's string constants, not an import), counts as imported. Add
    `test_a_plugin_conftest_registers_counts_as_used` beside it: it builds a source string with
    `pytest_plugins = ["tests.plugin_x"]` and asserts the reader returns `tests.plugin_x`. The docstring of the guard
    says why: pytest loads a plugin by its name in that list, which is a use the import walk cannot see. (Corrected
    after the first draft, which said nothing changes here.)
- **R4.2.5** — `tools/patch_sites.py` follows a stand-in through a fixture by the fixture's name. A fixture that moves
  into a plugin must still be followed: compare `python tools/patch_sites.py check` and `report` for the three engine
  modules, before and after. If a count changes, stop and ask (the tool is not edited in this job).
- **R4.2.6, the order is pinned first** (review 2, S15). Before any code moves, add to `tests/test_suite_shape.py`
  a module-level tuple `AUTOUSE_ORDER` holding the eight names in the measured order above (1-8), with a `#:` comment
  saying it was measured at `68b9212` and why the order matters (the app folder set up first and torn down last, so
  the store's connection is closed before the folder goes and the short roots are cleared after the agreement
  fixtures have walked them; the agreement fixtures set up last, so they are torn down first, while every stand-in is
  still in place), and the test

  ```
  def test_the_autouse_fixtures_run_in_the_order_the_suite_was_built_on(request):
      assert [name for name in request.fixturenames if name in AUTOUSE_ORDER] == list(AUTOUSE_ORDER)
  ```

  with a docstring saying how pytest orders them (by plugin in `pytest_plugins`' order, then by name inside one;
  a conftest by name) and that this cut keeps the order without a hook or a new dependency. It filters
  `request.fixturenames` to the eight, because pytest puts the fixtures they depend on (`tmp_path_factory`,
  `tmp_path`) and the test's own (`request`) among them. It passes at the base (measured) and must pass unchanged
  after the move: the expected tuple is not edited in this job. Commit it first, on its own.
- **R4.2.7, the ids do not change** (review 2, S18). `python -m pytest --collect-only -q` on both interpreters,
  "before" taken **after** R4.2.6's commit and "after" at the job's last commit, with the outputs diffed: the only
  difference is the one test R4.2.4 adds, `tests/test_suite_shape.py::test_a_plugin_conftest_registers_counts_as_used`.
  Both outputs and the diff go in before.txt and after.txt.
- **R4.2.8, every fixture still runs where and when it ran.** `python -m pytest --setup-plan -q -p no:xdist -p
  no:randomly` before (after R4.2.6's commit) and after, on PY311. The two outputs are identical once object
  addresses and the timing line are normalised, with
  `sed -E 's/ at 0x[0-9a-f]+>/ at 0x>/g; s/ in [0-9.]+s/ in Ns/'`, apart from R4.2.4's added test's own lines. (`-q`
  prints no fixture's home, so a moved fixture shows no path; the addresses differ between any two runs, base and
  base included.) The sed and the diff go in after.txt. This proves every fixture is set up, for every test, in the
  same place in the order and torn down in the reverse.
- **R4.2.9** — `python -m pytest --help` still lists `--record-golden` (the option `plugin_session` adds), and
  `pytest tests/test_golden.py --record-golden` is **not** run.
- **R4.2.10** — Decision row **P329**: the suite's guards are four plugins, registered in `tests/conftest.py`'s
  `pytest_plugins` (isolation, fakes, agreement, session). pytest sets a plugin's autouse fixtures up in the list's
  order and by name inside one, so the plugins are cut where the order the suite was built on allows (the fakes
  plugin holds the reading child's, the room measure's and the test cache's stand-ins with the others), and
  `test_suite_shape`'s `AUTOUSE_ORDER` pins that order. No name is re-exported from conftest. The row cites 185, E-6
  and this SPEC's P4.2.

**Pin-move list:** test_tripwire 362, test_patch_sites 1444, the import lines of the 43 files (R4.2.3), the prose and
curated places R4.2.3 lists outside `tests/` (each with its call in before.txt), `docs/vocab-coverage.*` (rebuilt for
the content_check comment, counts and hits unchanged), and the moved docstring paragraphs (R4.2.2, listed in
after.txt).

**Patch sites:** the tool's `check` total (761 on 45) may change only by file (stand-ins defined in conftest move with
it). Each one is listed.

**Register:** not reached (tests, and prose outside them).

**Tests:** the whole suite, plus R4.2.6-R4.2.9.

**Stop and ask:**
- R4.2.6's test fails at the base on either interpreter (the measured order is not the base's), or fails after the
  move.
- An autouse fixture can keep its order only by a `pytest_collection_modifyitems` or a fixture dependency that does
  not exist today.
- The collect-only diff holds anything but R4.2.4's one added test, or the setup-plan diff anything but that test's
  lines.
- patch_sites' counts change by more than file.
- A plugin needs a name from a plugin listed after it, or a fixture function from any other plugin, or an edge
  beyond R4.2.2's three. Write that down, because it means a name was cut into the wrong plugin.

**Accept when:**
- The gate passes.
- R4.2.6-R4.2.9 hold.
- `tests/conftest.py` holds only its docstring and `pytest_plugins`.
- No file imports `tests.conftest`.
- `tests/golden/` is unchanged.
- **Windows:** no label. The plugins carry Windows-only fakes (`refuse_what_windows_refuses`) unchanged, and no
  Windows-only test changes.
- **Office `-Tests`:** none of its own. The stack's whole-suite run covers it (section 6).

---

### P4.3 One after-routing road, `_settle` (A-3)

- **Cost:** M.
- **Tier:** Opus. The fold is the "nothing is guessed" rule across returns.
- **Findings:** A-3, keeping Q-B (P313).
- **Depends on:** P4.2.
- **Routing code:** no. It changes the filer's decision after the router has answered. `route_file`, the matcher and
  the catalog are untouched. The backtest does not exercise the filer.

**Measured at `68b9212`: the two roads.**
- `_decide_across` (4692-4912) is the household road.
- `_sort_one`'s after-routing part (5455-5515) is the re-send road.

Both run the same sequence after `route_file(judgment=...)`: the name tier (`_by_the_name`), the across-household park
(named or unnamed, with `_waits_for`), `_file_it`, and `NoRoom` caught into a park. They differ in ten ways:

| # | Household road (`_decide_across`) | Re-send road (`_sort_one`) |
|---|---|---|
| 1 | The across park carries the home's shortlist and evidence: `candidates=home_routing.candidates`, `evidence=_with_the_wanting_return(home_routing, run, routing)` | `candidates=()` (was `""`) and `evidence=_with_the_wanting_return(_NO_ROUTING, run, routing)`: no shortlist, and no evidence of the home's own. **This is Q-B.** |
| 2 | The across park lands in `_the_home(accepting, routed)`: the household's own return that accepted it first, else its first own return | The across park lands in `next((one for one in runs if one.home), run)`: the household's first own return. The home was never routed, so nothing can prefer an accepting one. **Part of Q-B** (below). |
| 3 | Gated on `routing.routed` (with `item is not None` checked inside the filing branch) | Gated on `routing.routed and item is not None` |
| 4 | `NoRoom`: `PATH_NO_ROOM_IN` when the home is not the run, parked in the home | `NoRoom`: always `str(exc)`, parked in the run |
| 5 | `opened_across` (an attachment never goes across, decision 143) | absent |
| 6 | Contested (more than one kept) parks as contested | absent |
| 7 | The final park (vetoed, unrouted) reads `stage.graded` for `_the_home(accepting, routed)` and lands there | The final park reads the run's `stage.graded` and lands in `run` |
| 8 | absent | `refiled` and `resent` sentences |
| 9 | Unnamed and named across are separate branches | merged |
| 10 | The across park's wanting-return evidence reads `routing` from `run, routing = kept[0]`: the routing **after** the name tier, so a confirmed name's `Evidence(RULE_NAME, spelling, where, page)` (`_with_the_name`, 4574) is in it | It reads `routing` as `route_file` returned it (5467-5470), **before** the name tier: a confirmed name's `RULE_NAME` entry is not in it. **Part of Q-B's evidence half** (review 2, S16; note 007). |

**When difference 10 shows** (review 2, S16). `_with_the_name` (4574) adds a `RULE_NAME` entry only when the verdict
carries a spelling: confirmed or vetoed. A vetoed return is dropped, so it never parks across. An unnamed request is
kept across only when the page names nobody (verdict absent, no spelling, the routing unchanged); a confirmed one is
the named across park. So the two roads' wanting-return evidence differs exactly in the **named** across park (R4.3.1
case 3), and is the same in the unnamed one (case 4). The household road's `NoRoom` park when `home is run` and the
re-send road's both read the name tier's routing (`kept[0]`), so they agree.

**Where the re-send road's parks land** (review 1, S1). `run` is the return whose record holds the bytes
(`_decide_across` 4740-4749: `mine[0]`, through `_may_hold`). For a loose drop, `run` may be a fed return in **another**
household, so `run.home` is false. Then:
- the across park (`stage.kept and not run.home`, 5478-5494) lands in the dropping household's first own return;
- the vetoed park (the name tier kept nothing; 5506-5511) and the unrouted park (5512-5514) land in `run` itself,
  reading `run`'s `stage.graded`, in the other household's record;
- the `NoRoom` park (5502-5505) is reached only with `run.home` true, because the across check returns first whenever
  `stage.kept` holds anything and `run.home` is false.

So one `home` argument cannot keep the re-send road: the across park and the other parks land in different returns
when `run` is not home. The fold below therefore computes the other parks' return itself, from `routed`, and takes the
across park's return and routing as the Q-B pair.

**Requirements:**

- **R4.3.1, the table test first.** In `tests/test_filer.py`, add
  `test_the_household_road_and_the_resend_road_settle_a_drop_the_same_way_but_for_the_across_park`. It is
  table-driven and runs one made-up drop through both roads in each of these cases:
  1. filed;
  2. parked as unrecognised;
  3. parked across households (named);
  4. parked across households (unnamed);
  5. parked for no room (the re-send road with a home `run`, the only way it reaches `NoRoom`).

  And two re-send-only cases, with a loose re-send whose bytes a fed return in another household holds (`run.home`
  false), which the household road has no counterpart for:

  6. the name tier keeps nothing (a named request and a page that names nobody, or names another return's person):
     the row lands in `run`, with the reason and evidence of `run`'s `stage.graded`;
  7. the router accepts nothing: the row lands in `run`, with the routing's own reason and evidence.

  For each case it asserts the literal row each road writes (`reason`, `code`, `candidates`, `waits_for`,
  `evidence`, `filed_to`) and **which return's record holds it**, by that return's label. The rows are written out in
  the test, not computed. The across cases (3 and 4) assert today's difference, both halves of it: the household
  road's row carries the home's shortlist and the home's evidence before the wanting return's, and the re-send road's
  row carries `candidates` `""` and only the wanting return's evidence. Case 3 also asserts difference 10 by the
  literal `evidence` cell of each road: the household road's wanting-return part (keyed `<label> / <identifier>`)
  holds the name's `RULE_NAME` entry with the firm's spelling, and the re-send road's holds no `RULE_NAME` entry at
  all. Case 4 asserts that the two roads' wanting-return parts are equal. (`candidates` in a row is the `IndexEntry`
  string, `CANDIDATE_SEP.join(...)`; at P4.3's base P4.1 has made the re-send road pass `candidates=()`, and the row
  reads `""` either way, R4.1.6.) Commit the test on its own, passing on the old code. Build the drops with
  `tests/builders.py` (P4.2), drive the re-send road through a recorded earlier row, as test_filer's re-send tests do,
  and build cases 3, 4, 6 and 7 with the earlier row in a fed return of another household (test_filer's `fed`
  fixture shape).
- **R4.3.2, the fold.** One function in the filer:

  ```
  def _settle(drop, original, digest, size_kb, stamp, runs, judgment, routed, *,
              shortlist_across: bool, refiled: str = "", resent: str = "") -> tuple[_ReturnRun, IndexEntry]
  ```

  It is placed where `_decide_across` begins. It holds the sequence after routing once, and both roads call it:
  - `_decide_across` builds `routed` over every return in `runs` and calls `_settle(..., shortlist_across=True)`.
  - `_sort_one` builds `routed = [(run, routing)]` from its one return and calls `_settle(..., shortlist_across=False,
    refiled=..., resent=...)`.

  Inside, exactly as `_decide_across` reads today: `accepting` is `routed` filtered on `routing.routed`; the name tier
  runs over `accepting`; and `home, home_routing = _the_home(accepting, routed)`, with
  `home_routing = stage.graded.get(id(home), home_routing)`. That pair serves the `NoRoom` park, the contested park
  and the final park, on both roads.

  The across parks (opened, unnamed and named) use **the across pair** and **the wanting routing**, chosen by
  `shortlist_across`:
  - `True`: `(home, home_routing)`, `candidates=home_routing.candidates`, and the wanting routing is `kept[0]`'s,
    the routing after the name tier, as the household road does today
    (`_with_the_wanting_return(home_routing, run, routing)` with `run, routing = kept[0]`);
  - `False`: `(next((one for one in runs if one.home), run), _NO_ROUTING)`, `candidates=()`, and the wanting routing
    is `routed[0][1]`, the run's routing as `route_file` returned it, before the name tier, as the re-send road does
    today (difference 10). Here `run` is the one return in `routed`. `_waits_for(run, ...)` may read either: it reads
    only `filed_to` and `answers`, which the name tier does not change; the fold passes it the same routing as the
    evidence, so the call reads as one.

  `shortlist_across` is keyword-only with no default, so each caller says which answer to Q-B it builds. It selects
  the shortlist, the home's evidence, the across park's return and the routing the wanting return's evidence is read
  from, together. The first three come from routing the home's own returns, which the re-send road does not do; the
  fourth is the re-send road's own today, and P313 keeps it (note 007: no re-send row gains evidence it does not
  carry today). Its docstring names Q-B (the shortlist, the home's evidence, the return, and the name's evidence on
  the wanting return), P313 and decision 132, and says where a later answer goes: the re-send road's call (what it
  routes, and this argument). Nothing in `_settle`'s
  sequence changes for it.
- **R4.3.3, the other differences stay, without a new parameter where the inputs already say it.** Measure each
  against R4.3.1's table.
  - Difference 2: the across pair (R4.3.2).
  - Difference 3: the re-send road's extra `item is not None` in the gate is unreachable. `context.by_id` is built at
    3710 as `{i.identifier: i for i in items}` from the same `context.items` the re-send road routes over, and
    `route_file` sets `routing.identifier` only to an identifier of an item it was given, so `routing.routed`
    implies `item is not None`. The fold keeps the household road's `item is not None` check inside the filing branch,
    which then covers both roads, and drops the re-send road's from the gate. `routed` is never built empty. The
    builder confirms the `route_file` claim by reading every `Routing(... identifier=...)` in `tracker/router.py`; if
    one can carry an identifier outside the items it was handed, stop and ask.
  - Differences 4 and 7: they follow from `_the_home(accepting, routed)` over the re-send road's one pair, which is
    always `run`: `run` itself when it is home, and `routed[0]`, which is `run`, when it is not. So `home is run` holds
    on the re-send road whatever `run.home` is, the `NoRoom` reason is `str(exc)`, and the final park reads `run`'s
    `stage.graded` and lands in `run`, as cases 5, 6 and 7 assert. (`home is run` would **not** hold if the re-send road
    passed the across return as the home; that is why the across return is a separate pair.)
  - Difference 5: `opened_across` needs `run.context.container` set and `run.home` false on the kept run. On the
    re-send road `run` came through `_may_hold`, which admits only an own return for an attachment, so a re-send of an
    attachment always has `run.home` true and the branch is not reached.
  - Difference 6: a contested park needs two kept pairs. The re-send road's `routed` holds one pair, so `kept` holds
    at most one.
  - Difference 8 (review 2, S20): `refiled` passed to `_file_it`; `resent` passed to `_file_it` and to every
    `_park_it`, as the re-send road passes them today. `_park_it` (5285) has no `refiled` parameter and gains none.
    Their defaults (`""`) are what the household road passes.
  - Difference 9: the merged branch is the separate branches with the same sentence.
  - Difference 10: the wanting routing (R4.3.2), carried on `shortlist_across` with the rest of Q-B.

  If any difference can be kept only by a further parameter, stop and ask with the case.
- **R4.3.4** — `_decide_across` keeps its name and its signature. It is still the entry the household pass and
  test_runner 4202's stand-in (`monkeypatch.setattr(filer, "_decide_across", ...)`) reach. Its body becomes the
  building of `routed` and the call to `_settle`. `_sort_one` keeps its name and signature.
- **R4.3.5** — Decision row **P330**: one after-routing road; the re-send road's across-household park still
  carries no shortlist, none of the home's evidence and, in its wanting-return evidence, none of the name tier's
  (difference 10), and lands in the household's first own return; the re-send
  road's other parks still land in the return that holds the bytes. The row says that Q-B is Jason's, open, and
  built as P313 says, and that the answer's place is the re-send road's call to `_settle` (what it routes, and
  `shortlist_across=False`).
- **R4.3.6** — The filer's curated node gains a sentence on `_settle`. `docs/architecture.md`'s filer line is
  unchanged.

**Patch sites:** test_runner 4202 (`_decide_across`, which stays). No other stand-in replaces a function the fold
removes. Confirm with `report tracker.filer` before and after: identical.

**Register:** not reached. `_ReturnRun` and `_SortContext` stay (A-11 is phase 7's). `_settle` reads `run.context`
exactly as the two roads did.

**Tests:** the whole suite, plus R4.3.1's test at both commits.

**Stop and ask:**
- R4.3.1's table shows a difference that is not one of the ten.
- Keeping a difference needs a parameter beyond `shortlist_across`, `refiled` and `resent`.
- Case 6 or 7 of R4.3.1 lands in a different return, or carries a different reason or evidence, after the fold.
- Case 3's re-send row carries a `RULE_NAME` entry after the fold, or its household row loses one (difference 10).
- `route_file` can return `routed` with an identifier outside the items it was handed (R4.3.3, difference 3).
- A golden recording would change.

**Accept when:**
- The gate passes.
- R4.3.1's test passed before the fold and passes after it, with its expected rows unchanged between the two commits.
- `_settle` is the one place the after-routing sequence is written.
- `tests/golden/` is unchanged.
- **Windows:** no label. No lock, atomic replace or path code changes, and the paths parked into are computed by the
  same calls.
- **Office `-Tests`:** none of its own.

---

### 4.1 Rules the move jobs share (P4.4, P4.6-P4.12)

These hold for every job that creates a module. Each job's own requirements add to them and never repeat them.

**The test split** (E-3). A test function moves with the code it is about, by one rule that a script can apply:
- A test's *homes* are the modules that, after the job, define the functions and classes of the old module the test
  calls or constructs, directly in its body or through a fixture defined in the same file. Exception classes, sentence
  constants and stand-in targets do not count: a test that only expects `FilingError` is about the code that raises it.
- The test moves to `tests/test_<M>.py` when the highest of its homes, in the order below, is `M`. A test whose highest
  home is the module that stays, or that calls nothing of the old module, stays.
  - The filer's family: `copies` < `intents` < `inbox`, `readme_ack` < `filer` < `actions`. (`inbox` and `readme_ack`
    are unordered: a test that calls both stays in `test_filer.py`, and none does at `68b9212`.)
  - content_check's: `keywords` < `verdicts` < `content_check`.
  - ocr's: `ocr` < `reader_child`.
- Each job applies the rule on its own base, after the code has moved, and lists every moved test by its old node id
  in before.txt, with its homes. A test that the rule moves but that reads better where it is (it pins a sentence of
  the old module, say) still moves; the rule is the reviewer's check, and an exception is a stop and ask.
- Measured at `68b9212` with this SPEC's move lists: of test_filer's 335 tests, about 21 go to `test_copies.py`, 15 to
  `test_intents.py`, 5 to `test_inbox.py`, 8 to `test_readme_ack.py` and 94 to `test_actions.py`, and about 192
  stay. Of test_content_check's 96, 27 go to `test_keywords.py` and 5 to `test_verdicts.py`. Of test_ocr's 71, 26 go
  to `test_reader_child.py`. These counts are a guide; the job's own count is the one in before.txt.
- A moved test moves byte for byte with its decorators and comments. Its module-qualified reads change to the new
  home where the old module no longer holds the name (section 3, Tests).

**The shared helpers.** A test file may not import another (`test_suite_shape`). What more than one of the split files
reads goes to one helper module per family:
- `tests/filer_helpers.py`, created by P4.4, for the filer's family. Each later filer job adds to it.
- `tests/content_check_helpers.py`, created by P4.10 only if the split needs one (measure; it may not).
- `tests/ocr_helpers.py`, created by P4.12 only if the split needs one.

Each is written in `tests/store_helpers.py`'s form:
- a docstring saying where each helper came from and why it is here;
- fixtures named once by assignment in each user (`two_returns = filer_helpers.two_returns`), never imported by name;
- the helper moves byte for byte from `test_filer.py` (or its family's file) and is deleted there; `test_filer.py`
  then names it from the helper module like any other user.

A helper only one file reads stays in, or moves with, that file. At `68b9212` test_filer's module-level helpers that
the measured split would share include `originals`, `prepared`, `kept_files`, `came_from`, the `two_returns`,
`two_1040s` and `fed` fixtures, and the `killed_*` helpers; the job measures the rest.

**The module's head.** Each new module starts with a docstring that carries the reasoning, as its neighbours' do:
- what it holds and the decision rows behind each part (copied from the moved code's own comments where they say it);
- where it came from (the audit finding, this SPEC's job and its decision row);
- why it sits at its layer, and what it may not import;
- for a module carved out of the filer, why it logs as `tracker.filer` (section 2.1, Logger names).

The old module's docstring loses the paragraphs that described the moved code and gains one sentence naming the new
home. Nothing else in it changes.

**The grep for annotated names (R4.4.13's form).** Each move job runs
`grep -nE '^[A-Za-z_][A-Za-z0-9_]*: [^=]+ = ' tracker/<old>.py tracker/<new>.py` before and after and lists what moved.

**The admission closure.** Section 3's rule holds. One more measurement belongs to every move job: the prose pointers
that name a moved name inside `records`, `reasons`, `ledger`, `layout` or `bounds` (for example records 630, reasons
779-795 and ledger 409) are `#` or `#:` comments or module docstrings at `68b9212`, which are not closure parts. They
are retargeted. If one sits inside a closure part's own source (a function's or a class's docstring), retarget it and
re-pin that one part under 6 with a comment line in R4.1.10's form ("Pinned again under 6 when P4.k retargeted a
pointer in <part>'s docstring: no rule changed"). Any other digest change is a stop and ask.

**The patch_sites floor.** `tests/test_patch_sites.py::test_the_report_on_filer_holds_every_filer_site_a_plain_search_finds`
(1448) counts the stand-ins on `tracker.filer` and requires at least 73. From P4.4 the filer's stand-ins are spread over
its family, so the count falls below 73 although no stand-in is lost. P4.4 changes the test to count over the family:
- a module-level `FILER_FAMILY = ("tracker.filer", "tracker.copies")`, which each later filer job extends with its
  module (`tracker.intents`, `tracker.inbox`, `tracker.readme_ack`, `tracker.actions`);
- `reported` takes every site whose module is in `FILER_FAMILY`;
- the plain search's regex takes each family module's name and its `_module` alias, as it takes `filer|filer_module`
  today, and the string form `setattr("tracker.<module>.`;
- the floor stays `>= 73`, now over the family, and the docstring says why.

A loop over two modules counts once per module in the tool's report, so the family count can only rise.

**The index's private crossing** (`tests/test_index.py` 72,
`test_exactly_the_three_tail_readers_cross_into_the_filer`, with `PRIVATE_CROSSING` at 39). It pins P319's one
exception to the index's boundary: of the index's private names, exactly `_before_the_moved_sentence`,
`_says_it_is_nowhere` and `_without_moved_sentence` are bound in the filer, each the index's own object. It asks only
`hasattr(filer, ...)`. Measured at `68b9212`, the moves carry those reads into the family: `inbox` (P4.7) reads
`_before_the_moved_sentence` (filer 2459), and `intents` (P4.6) and `actions` (P4.9) read `_without_moved_sentence`.
The filer keeps reads of all three (4138, 2684, 2698), so the test still passes, but it no longer pins the boundary: a
fourth private name crossing into `inbox`, `intents` or `actions` would go unseen. So:
- P4.6 changes the test to take the union over a literal tuple of the family's modules (`filer` and each new module
  that exists after the job), and to require each module that binds one of the three to bind the index's own object;
  P4.7 and P4.9 extend the tuple with their module. The set it compares with stays `PRIVATE_CROSSING`.
- The test keeps its name (the collected ids do not change); its docstring says the crossing is into the filer's
  family since P332, and why.
- `test_index` is in the named tests of P4.6, P4.7 and P4.9.

**Curated nodes and the map.** In the commit that creates the module:
- the new module's curated node (role, notes, and any runtime artifact edge that moves to it);
- the old module's node loses the sentences about the moved code and gains one naming the new home;
- the test file's node, and the helper module's;
- `python tools/repo_map.py update`, then `check`.

**ENFORCERS** (`tests/test_repo_map.py` 843-849). A module that takes code upholding a standing rule joins that rule's
set in the same commit, with a curated `enforces` edge on its node. The jobs say which.

**The accept-when every move job shares:**
- The gate passes on both interpreters, with the base's failures and skips and no others.
- `python -m pytest --collect-only -q` before and after lists the same tests, apart from the moved ones' file part
  and the additions and renames the job itself names (review 2, S18): the job diffs the two with the file part
  stripped (a `sed` given in after.txt), and the diff holds exactly those named additions and renames, no other line.
  At `68b9212` the named ones are P4.9's two renames (R4.9.8) and P4.11's one added test (R4.11.6); every other move
  job names none, so its diff is empty.
- `patch_sites report` before and after meets section 3's accept line.
- `ADMISSION_PIN[6]` is unchanged, or changed only as above.
- `tests/golden/` is unchanged.
- `git diff -M --stat` shows the moved code as moved (most of the new module's lines appear as deletions in the old
  one), and `git diff -M -w --color-moved=plain` on the pair shows no line edited inside a moved body other than the
  ones a requirement names. The job pastes the command and its summary in after.txt.

---

### P4.4 `copies.py`: names, room, copies and moves (A-1 step 2)

- **Cost:** L.
- **Tier:** Opus. It is the first move out of the filer: the stand-in table starts spreading here, and the README lock
  and the sweep come with it.
- **Findings:** A-1 step 2; A-4.
- **Depends on:** P4.3.
- **Routing code:** no. Nothing here routes; it names, measures, copies and moves files.
- **Layer and domain:** L2, `sorting`.

**What moves** (filer, at `68b9212`; about 800 lines). Re-measure each by name.

| Lines | Names |
|---|---|
| 375, 382, 450 | `_MAX_STEM`, `numbered`, `FilingError`. They move down because the copies code reads them; nothing in them reads the filer. |
| 551-1208 | `_ROOM_COUNTER` through `_unique_path`: `_parts_of`, `_stem_of`, `_named`, `prepared_name_for`, `shortest_name_for`, `PATH_NO_ROOM`, `PATH_NO_ROOM_IN`, `HOUSEHOLD_NO_ROOM`, `REVIEW_NO_ROOM`, `REVIEW_OF_A_PROGRAM`, `REVIEW_COPY_FAILED`, `REVIEW_COPY_PAST_READER`, `ROOM_PARKS`, `_kind_of`, `FIRM_WRITTEN`, `NoRoom`, `Room`, `_extensions_of`, `room_for`, `refuse_a_path_past_the_limit`, `copies_of`, `_existing_copy`, `COPY_MISMATCH`, `_DIGEST_SHOWN`, `COPY_UNPROVED`, `COPY_UNREAD`, `CopyMismatchError`, `_copy_whole`, `MARK_REFUSED`, `MARK_REFUSED_STEP`, `MarkRefusedError`, `_may_carry_code`, `_shown`, `_mark_for_review`, `_digest_or_none`, `MOVE_THROUGH_A_LINK`, `MovedThroughALinkError`, `_move_whole`, `_AN_EXTENSION`, `_room_in`, `_unique_path` |
| 1211, 1235 | `_on_record`, `_year_on_record`. (`_taken_in_the_year`, 1224, between them, stays: it reads `_ReturnRun`.) |
| 1414-1437, 1443-1446 | `README_LOCK_FILENAME` (with its `#:` comment from 1414), `README_LOCK_WAIT_SECONDS`, `_README_LOCK_POLL_SECONDS`, `_readme_lock`; then `TEMPS_NOT_SWEPT` with its comment. `README_NOT_REWRITTEN` (1442, with its `#:` comment at 1439-1441), between them, stays: P4.8 moves it to `readme_ack`. |
| 1503-1674 | the stranded-temp sweep: `_a_stranded_temp_to_take`, `_holds_the_firms_readme_text`, `_remove_a_stranded_temp`, `sweep_stranded_temps` |
| 5245 | `_review_copy_path`, which reads only names above |

The section comments over each range move with it. Measured at `68b9212`: no moved definition reads a name that stays
in the filer, so `copies` imports nothing of the filer. It imports, by name: `containers`, `door`, `errors`, `ledger`,
`store`; `ContentCache` from `content_check` (L2, in-layer); from `fsio` `copy_atomically`, `is_link`,
`make_writable`, `mark_from_internet`, `stranded_temps`, `temp_owner`; `household_returns`; `index.read_index`; the
`layout` names it reads; from `locking` `EngagementLockedError`, `acquire_lock`, `pid_alive`, `release_lock`; from
`manifest` `ANY_EXTENSION`, `DEFAULT_EXTENSIONS`, `ManifestError`, `Override`, `RequestItem`, `is_reserved_name`,
`label_for`; `IndexEntry`; from `scaffold` `PREPARED_DIR_NAME`, `README_FIRMS`, `README_FIRST_LINE`, `README_NAME`,
`REVIEW_DIR_NAME`, `assign_files`, `sanitize_component`, `whose_readme`; from `validators` `bears_macros`,
`extension_of`, `is_cloud_placeholder`, `is_program`, `sha256_of`. Nothing it imports is above L2. (Measure the exact
list from the moved code's reads; ruff's F401 and F821 are the check.)

**Requirements:**

- **R4.4.1, the module.** `tracker/copies.py` holds the table's code, moved byte for byte (section 3), under the head
  section 4.1 asks for. Its logger is `logging.getLogger("tracker.filer")` with the comment section 2.1 gives.
- **R4.4.2, the filer imports back** by name only what its own remaining code reads, from `tracker.copies`. ruff is
  the check.
- **R4.4.3, readers in `tracker/` and `tools/`,** retargeted in the same commit:
  - `api` (124): `FilingError`, `_may_carry_code`, `refuse_a_path_past_the_limit` and `room_for` from
    `tracker.copies`; the rest of its filer import is unchanged in this job.
  - `runner` (188): `HOUSEHOLD_NO_ROOM`, `ROOM_PARKS`, `room_for` and `sweep_stranded_temps` from `tracker.copies`.
  - `view` (94): `FilingError` from `tracker.copies`.
  - `rollover`: the call-time imports at 590 (`FilingError`) and 964 (`refuse_a_path_past_the_limit`).
  - `reminder` 1914: `from tracker.copies import numbered` (call time).
  - Prose: `locking.py` 545 (`README_LOCK_FILENAME`), `reasons.py` 779-795 where a pointer names a moved sentence
    (`PATH_NO_ROOM`, `PATH_NO_ROOM_IN`), `fsio.py` 416 and `runner.py` 104 where they name the sweep, `scaffold`'s
    pointers to the README lock, and every other hit of the grep in section 3. `numbered` and `Room` are common words:
    read each hit and retarget only a pointer to the name.
- **R4.4.4, tests that read a name the filer no longer holds** are retargeted (section 3): among them test_single_source
  954, 1740 and 2217 (`README_LOCK_FILENAME`), and every `filer.<moved name>` the grep finds where the filer does not
  import the name back. test_single_source 1913 (`prepared_name_for`) waits for P4.13 if the filer still imports it
  back; otherwise it is retargeted here.
  - The filer also stops importing two names whose only filer reader moves here (section 3, Tests): `PATH_TOO_LONG`
    (imported from `layout` at 246, read only at 844) and `acquire_lock` (from `locking` at 277, read only at 1432).
    So test_rollover 1339 (`filer.PATH_TOO_LONG`) reads `layout.PATH_TOO_LONG` (importing `tracker.layout` as the file's
    style is), and test_scaffold 926's `filer_module.acquire_lock` reads the original from `tracker.locking`. 926's
    other capture, `filer_module.received_for`, is P4.8's. The stand-in beside it (944) follows section 4.0's row.
  - before.txt lists every import of the filer that ruff drops after the move, with the test reads of each (section
    3); at `68b9212` these two are all.
- **R4.4.5, the stand-ins.** Apply section 4.0's rows marked P4.4. Measured at `68b9212`, the targets change for
  `README_LOCK_WAIT_SECONDS`, `acquire_lock`, `limit_for`, `make_writable`, `mark_from_internet`, `pid_alive` (copies
  only), and `path_limit`, `is_cloud_placeholder`, `locate`, `sha256_of`, `read_index` (copies and filer). The string
  target at test_filer 516 (`"tracker.filer.is_cloud_placeholder"`) becomes two `setattr`s, or a loop over the
  imported modules, in a form patch_sites follows. test_filer 1048's three-name loop is rewritten as section 4.0's
  last paragraph says. `_move_whole`, `_copy_whole`, `_existing_copy` and `_review_copy_path` keep their `filer`
  target: their callers are still the filer's.
- **R4.4.6, the test split.** `tests/test_copies.py` is created with the tests section 4.1's rule sends to `copies`,
  and `tests/filer_helpers.py` with the helpers they share with `test_filer.py`.
- **R4.4.7, the layer table.** `copies` joins `LAYERS[2]`, with a comment above the set in its neighbours' form:
  "``copies`` joins L2 with P331 (SPEC-architecture-p4 P4.4): the filer's naming, room, byte-proved copy and
  rename-only move, the client README's lock and the stranded-temp sweep - L1 and L0, and ``containers`` and
  ``content_check``'s ``ContentCache`` in-layer; the filer and a person's actions import it." It joins
  `DOMAINS["sorting"]`. (`containers`: `_may_carry_code` reads `containers.is_container`, filer 1026-1027 at
  `68b9212`; review 2, S21.)
- **R4.4.8, ENFORCERS.** `copies` joins `rule:originals-are-never-altered` (the byte-proved copy and the rename-only
  move are how an original is never altered), with the curated `enforces` edge. The filer stays in the set: it still
  decides every move.
- **R4.4.9, the docs.** `docs/architecture.md`: "forty-six" becomes "forty-seven", and a `copies` line goes under
  L2. `tracker/__init__.py`'s module list gains `- copies        : ...` after the filer's line.
- **R4.4.10, the patch_sites floor** (section 4.1): `FILER_FAMILY = ("tracker.filer", "tracker.copies")`.
- **R4.4.11, the decision row P331**: the filer's naming, room, copying and moving left for `tracker/copies.py` at
  L2; the README lock and the sweep went with them because the sweep reads the lock's file name; logger names are
  kept; the stand-ins follow the readers. It cites A-1, A-4, 51, 109, 155 and P313.
- **R4.4.12, the filer's curated note.** The filer's node is rewritten for the move: the copy, room and README-lock
  sentences go to `copies`' node, and the older wording about `holds_the_row` is corrected. Old (in the filer's
  notes): "Decision 159: holds_the_row() (was _holds_the_row) is public so verify() (tracker/verify.py since P325)
  reuses the filer's one read of a file against its row's fingerprint rather than a second fingerprint routine." New:
  "Decision 159: holds_the_row() (was _holds_the_row; tracker/index.py's since P319) is public so verify()
  (tracker/verify.py since P325) reuses the one read of a file against its row's fingerprint rather than a second
  fingerprint routine." The role's README-lock clause ("under a per-household README lock (README_LOCK_FILENAME ...;
  busy past README_LOCK_WAIT_SECONDS = skip with a log line)") names `tracker/copies.py` as the lock's home.
- **R4.4.13, the annotated names.** The grep in section 4.1's form finds no annotated module-level name in the moved
  code (the filer has none at `68b9212`). If it finds one, list it and say whether the map sees it.

**Pin-move list:**
- `tests/test_layers.py`: `LAYERS[2]` and its comment, `DOMAINS["sorting"]`.
- `tests/test_repo_map.py`: `ENFORCERS["rule:originals-are-never-altered"]`.
- test_rollover 1339 and test_scaffold 926 (R4.4.4: names the filer stops importing).
- `tests/test_patch_sites.py`: `FILER_FAMILY`, the plain search, the floor's docstring.
- `docs/architecture.md` line 29 and the L2 list; `tracker/__init__.py`'s module list.
- `ADMISSION_PIN[6]`: unchanged (no closure part names a moved name in its own source; measure).

**Patch sites:** section 4.0's P4.4 rows; before.txt holds `report tracker.filer` before, and `report tracker.filer`
and `report tracker.copies` after.

**Register:** not reached. No register key names the filer at `68b9212`; `_ROOM_COUNTER` is not module state that the
register lists (check `tracker/resident.py`; if it is listed, its key moves to `("copies", ...)`).

**Tests:** `tests/test_copies.py`, `test_filer`, `test_scaffold`, `test_api`, `test_runner`, `test_rollover`,
`test_reminder`, `test_view`, `test_errors`, `test_single_source`, `test_layers`, `test_repo_map`, `test_patch_sites`,
`test_suite_shape` and `test_golden` first, each as its own process; then the whole suite.

**Stop and ask:**
- A moved definition turns out to read a name that stays in the filer (the AST check says none does).
- A stand-in cannot reach the code it replaces under section 3's rule.
- The README lock's or the sweep's tests need a new seam.

**Accept when:**
- Section 4.1's shared accept-when holds.
- `copies` imports nothing above L2, and nothing of the filer.
- `grep -rn "filer\.\(README_LOCK_FILENAME\|sweep_stranded_temps\|room_for\|FilingError\)" tracker tools` finds
  nothing.
- **Windows: label.** It moves the README lock (the engagement lock's `acquire_lock` and `release_lock`), the atomic
  copy (`copy_atomically`) and path handling (`room_for`, `refuse_a_path_past_the_limit`, the link check).
- **Office `-Tests`:** `test_copies,test_filer,test_scaffold,test_runner,test_api,test_rollover,test_errors`. These
  hold the lock's, the copy's and the path limit's Windows paths.

---

### P4.5 A person's refusals named once; `_here` (A-10)

- **Cost:** S.
- **Tier:** Sonnet. It names sentences without changing a word, and one predicate.
- **Findings:** A-10.
- **Depends on:** P4.4 (the constants and `_here` live in `copies`).
- **Routing code:** no.

**Measured at `68b9212`** (re-measure on the base by the quoted text):
- "the original {…} is still syncing; try again when it is here", written inline at filer 5775, 6102, 6638 and 7102.
- "{location} is still syncing; try again when it is here", inline at 7083 and as `RENAME_COPY_SYNCING` (7268, read
  at 7452).
- "the original {…} is no longer there", inline at 5772 and 6099. (6635's sentence goes on with "; there is nothing to
  put back" and is a different sentence; it stays.)
- The presence test written out: `X.is_file() and not is_cloud_placeholder(X)` at 5794 and 6142, and its negation
  `not X.is_file() or is_cloud_placeholder(X)` at 2529, 2531, 3037 and 6614.
- No module outside the filer, and no test, reads `RENAME_COPY_SYNCING`. The tests that pin these sentences match the
  text (`grep -rn "still syncing" tests` gives 5 lines); they do not change.

**Requirements:**

- **R4.5.1, the sentences.** In `tracker/copies.py`, beside `FilingError`:
  - `ORIGINAL_GONE = "the original {original} is no longer there"`;
  - `ORIGINAL_SYNCING = "the original {original} is still syncing; try again when it is here"`;
  - `COPY_SYNCING = "{location} is still syncing; try again when it is here"`, which is `RENAME_COPY_SYNCING` renamed
    and moved, because 7083's refusal (a filed copy, in the recovery) says the same sentence.

  Each with a `#:` comment saying which actions refuse with it. The text of each is the inline text, letter for letter.
- **R4.5.2, the sites.** Each inline site becomes `raise FilingError(ORIGINAL_SYNCING.format(original=_shown(...)))`
  (or `ORIGINAL_GONE`, `COPY_SYNCING`) with the same argument it formatted inline. 7452 reads `COPY_SYNCING`.
  `RENAME_COPY_SYNCING` is gone.
- **R4.5.3, `_here`.** In `tracker/copies.py`:

  ```
  def _here(path: Path) -> bool:
      """The file is on this machine: there, and not a cloud placeholder still syncing. ..."""
      return path.is_file() and not is_cloud_placeholder(path)
  ```

  The six sites read `_here(X)` and `not _here(X)`. The calls are the same, in the same order, with the same
  short-circuit (`is_cloud_placeholder` is not called on a path that is not a file), and the docstring says so.
  `parked is not None and _here(parked)` keeps its `None` test outside.
- **R4.5.4, the stand-ins.** `_here` reads `is_cloud_placeholder` as a global in `copies`. A test that replaces
  `is_cloud_placeholder` to drive one of the six sites must reach `copies` (it already does after P4.4, where `copies`
  joined that row's readers); re-derive the row and confirm with `report`.
- **R4.5.5, the typed-sentence guards.** The sentences are a person's refusals. If any guard keys a sentence by its
  module and its name (test_errors, test_single_source, the vocab report's request list), the new names are entered in
  it in the same commit. Measure with `grep -rn "RENAME_COPY_SYNCING\|still syncing" tests tools`.

**Pin-move list:** none beyond the guards R4.5.5 finds.

**Patch sites:** `is_cloud_placeholder`'s row only; `report tracker.copies` before and after.

**Register:** not reached.

**Tests:** `test_copies`, `test_filer`, `test_errors`, `test_single_source`, `test_api` (it drives the refusals), then
the whole suite.

**Stop and ask:**
- A site's sentence differs from the constant by any character.
- A test pins `RENAME_COPY_SYNCING` by name.

**Accept when:**
- The gate passes.
- `grep -rn "is still syncing; try again when it is here" tracker` finds two constants and no f-string.
- `grep -n "is_file() and not is_cloud_placeholder\|is_file() or is_cloud_placeholder" tracker/filer.py tracker/copies.py`
  finds only `_here`'s body (review 1, S4: the filer family's files only). The same grep over all of `tracker` also
  finds `tracker/index.py` 408 and `tracker/scanner.py` 399 and 411. Those stay as they are: A-10 is the filer's
  refusals, index is L1 and may not import `copies` (L2), and making the scanner import the filer's family for one
  predicate would be a new edge this phase does not make (P313's Q-A keeps the scanner and the filer apart). They are
  not this job's.
- `tests/golden/` is unchanged. No decision row (no rule changes).
- **Windows:** no label. The predicate is the same calls; no lock, replace or path code changes.
- **Office `-Tests`:** none of its own.

---

### P4.6 `intents.py`: the write-ahead intents (A-1 step 3)

- **Cost:** M.
- **Tier:** Opus. The intents are decision 119's: a person's actions and the pass share them, and the interrupted move
  is finished from them after a crash.
- **Findings:** A-1 step 3; A-4.
- **Depends on:** P4.5.
- **Routing code:** no.
- **Layer and domain:** L3, `sorting`.

**What moves** (filer, at `68b9212`; about 690 lines). Re-measure each by name.

| Lines | Names |
|---|---|
| 395 | `OPENED` moves to `tracker/index.py`, beside `FILED`, `NEEDS_REVIEW`, `DUPLICATE` and `FILE_MOVED` (section 2.1) |
| 491 | `FileError` |
| 1683-1777 | the record section: `_LEDGER_EVENT_FOR`, `_ledger_event`, `_rows_changed`, `_record`. They go with the intents because `_finish_interrupted_moves` and the hand-over both compose through `_ledger_event`, and `index` composes nothing (P319). |
| 1786-2105 | `OPEN_INTENT_REFUSAL` through `_the_record_holds`: `_op`, `OP_OUTSIDE`, `_may_touch`, `_refuse_a_step_outside`, `_refuse_a_step_through_a_link`, `_door_for`, `_mark_a_move_into_review`, `_do_op`, `_intend`, `_prove`, `_abandon`, `_carry_out_a_persons_ops`, `_refuse_if_a_move_is_open`, `_the_record_holds` |
| 3002-3318 | finishing an interrupted move: `INTERRUPTED_MOVE_LOST_DETAIL`, `INTERRUPTED_ORIGINAL_HELD`, `INTERRUPTED_ORIGINAL_GONE`, `INTERRUPTED_SYNCING`, `INTERRUPTED_MARK_REFUSED`, `_FINISHED`, `_SYNCING`, `_TAKEN`, `_LOST`, `_waiting_on_sync`, `_the_bytes`, `_finish_the_ops`, `_a_copy_to_act_on`, `_finish_interrupted_moves`, `_the_trouble` |

`intents` imports from `copies`, `ContentCache` from `content_check` (L2, in the annotations of `_do_op` 1887,
`_finish_the_ops` 3043 and their kin: the cache handed down the copy path), and L1 and L0 names, and nothing of the
filer. The filer imports back what it reads.
The places that call `ledger.new` in the moved code (at `68b9212`: `_ledger_event` 1694, `_intend` 1990, `_abandon`
2060, `_finish_interrupted_moves` 3255 and 3269) make `intents` a composer.

**Requirements:**

- **R4.6.1, the module** `tracker/intents.py`, by section 4.1. Logger `tracker.filer`.
- **R4.6.2, `OPENED`** moves to `tracker/index.py` with its `#:` comment, and the filer and `intents` import it from
  there. index's docstring list of decision words gains it. Every reader of `filer.OPENED` in `tracker/`, `tools/` and
  `tests/` is retargeted to `index` (the filer no longer defines it; it imports it back only if it reads it).
- **R4.6.3, readers outside the engine.** At `68b9212` no module outside the filer imports an intents name (records'
  pointer to `FileError` is prose; retarget it). Re-measure.
- **R4.6.4, the stand-ins.** Apply section 4.0's rows marked P4.6: `_move_whole`, `_copy_whole`, `_existing_copy`,
  `_review_copy_path` and `_do_op` (filer and intents), `_may_touch` and `place_problem` (intents only), and
  `is_cloud_placeholder`, `locate`, `sha256_of` and `read_index` (intents joins). test_errors 975-993 drives
  `_a_copy_to_act_on`: it calls `intents._a_copy_to_act_on` and sets its five stand-ins on `intents`.
- **R4.6.5, the test split** into `tests/test_intents.py`; shared helpers into `tests/filer_helpers.py`.
- **R4.6.6, the layer table.** `intents` joins `LAYERS[3]` with a comment: "``intents`` joins L3 with P332
  (SPEC-architecture-p4 P4.6): decision 119's write-ahead intents and finishing an interrupted move, out of
  ``filer`` - ``copies`` and ``content_check``'s ``ContentCache`` (L2), and L1 and L0; the filer and a person's
  actions import it. It imports nothing above L2, and sits at L3 beside the two it serves." It joins
  `DOMAINS["sorting"]`. (P4.11 changes ``content_check``'s ``ContentCache`` to ``verdicts``' in this comment,
  R4.11.8.)
- **R4.6.7, `COMPOSERS`** gains `"intents"`, and the comment above it says why (the intent, the abandon and the
  finish compose the record's events).
- **R4.6.8, ENFORCERS.** `intents` joins `rule:originals-are-never-altered`: an original's move is intended, done
  and proved here. (If Jason or the reviewer reads the rule's enforcers as the deciders only, drop this; section 7
  asks.)
- **R4.6.9, the docs.** "forty-seven" becomes "forty-eight"; an `intents` line under L3; the module list.
- **R4.6.10, the patch_sites floor**: `FILER_FAMILY` gains `"tracker.intents"`.
- **R4.6.11, the decision row P332**: the intents left the filer for `tracker/intents.py` at L3; `OPENED` joined the
  index's decision words; `intents` is a composer. It cites A-1, 119, P319, P327 (`COMPOSERS`) and P313.
- **R4.6.12, the curated nodes.** `intents`' node carries decision 119's sentences and the interrupted-move notes from
  the filer's node; `index`'s node and role gain `OPENED`.

**Pin-move list:** `LAYERS[3]`, `DOMAINS`, `COMPOSERS`, `ENFORCERS`, `FILER_FAMILY`; architecture.md and the module
list; index's docstring. `ADMISSION_PIN[6]` unchanged (`index` is not in the closure).

**Patch sites:** section 4.0's P4.6 rows; `report` for `tracker.filer`, `tracker.copies`, `tracker.intents` and
`tracker.index` before and after.

**Register:** not reached.

**Tests:** `test_intents`, `test_filer`, `test_copies`, `test_index`, `test_api`, `test_runner`, `test_containers`,
`test_errors`, `test_layers`, `test_repo_map`, `test_patch_sites`, `test_ledger`, `test_golden`; then the whole suite.

**Stop and ask:**
- The composer test names a module other than `intents` as new.
- A moved definition reads a filer name (the AST check says none does).
- A test of the interrupted move needs a seam it did not have.

**Accept when:**
- Section 4.1's shared accept-when holds.
- `intents` imports nothing of the filer; the filer imports `intents` at load.
- **Windows: label.** `_refuse_a_step_through_a_link`, `_door_for` and the rename-only `_do_op` are path handling and
  the move the held engagement lock guards.
- **Office `-Tests`:** `test_intents,test_filer,test_api,test_runner,test_errors,test_containers`.

---

### P4.7 `inbox.py`: walking the inbox (A-1 step 4)

- **Cost:** M.
- **Tier:** Opus.
- **Findings:** A-1 step 4; A-4.
- **Depends on:** P4.6.
- **Routing code:** no.
- **Layer and domain:** L3, `sorting`.

**What moves** (filer 2123-2544 at `68b9212`; about 420 lines; review 2, S19): `iter_drops`, `_inbox_order`, `_subfolder_of`,
`_storable`, `unreachable_drops`, `unlistable_folders`, `unfinished_drops`, `ignored_in_inbox`, `unrecorded_in_pbc`,
`REPLACED_IN_PBC`, `replaced_in_pbc`, `MISSING_IN_PBC`, `MOVED_IN_PBC`, `MOVED_FROM_IN_PBC`, `_absent`,
`_missing_positions`, `_row_these_bytes_left`, `_follow_moved_originals`, `README_UNREAD`, `LEFT_FOR_ANOTHER_RETURN`,
`UNTIED_IN_PBC`, `_copy_taken_by_a_later_row`, `_record_missing_digests` (2503-2544). It imports `_on_record` and
`_here` from `copies` and L1 and L0 names, and nothing of the filer or `intents`. (`_record_missing_digests` holds two
of the sites P4.5 replaced with `_here`, at 2529 and 2531 at `68b9212`; they move with it as `_here` calls.)

**Requirements:**

- **R4.7.1, the module** `tracker/inbox.py`, by section 4.1. Logger `tracker.filer`.
- **R4.7.2, readers.** `reminder` 1410's call-time import becomes `from tracker.inbox import iter_drops,
  unfinished_drops, unlistable_folders, unreachable_drops`. Prose pointers by the grep.
- **R4.7.3, the stand-ins.** `is_cloud_placeholder` and `sha256_of` gain `inbox` as a reader (section 4.0).
  `iter_drops`' stand-ins (test_filer 1048, 7213) stay on `filer`: the household pass, its only caller, stays.
  test_reminder 1794 (`unlistable_folders`) moves to `inbox`, because `reminder` now imports it from there.
- **R4.7.4, the test split** into `tests/test_inbox.py`.
- **R4.7.5, the layer table**: `LAYERS[3]` with a comment in R4.6.6's form ("the inbox's walk and the drops that
  cannot be read, listed or tied to a row, out of ``filer`` - ``copies`` (L2) and L1 and L0; the filer and the
  reminder import it"); `DOMAINS["sorting"]`.
- **R4.7.6, the docs.** "forty-eight" becomes "forty-nine"; an `inbox` line under L3; the module list.
- **R4.7.7**: `FILER_FAMILY` gains `"tracker.inbox"`.
- **R4.7.8, the decision row P333**: walking the inbox left the filer for `tracker/inbox.py` at L3. It cites A-1,
  125, 168 and P313.

**Pin-move list:** `LAYERS[3]`, `DOMAINS`, `FILER_FAMILY`, architecture.md, the module list. `COMPOSERS` unchanged
(`inbox` calls `ledger.new` nowhere; the composer test is the check). `ADMISSION_PIN[6]` unchanged.

**Patch sites:** P4.7 rows; `report` for `tracker.filer` and `tracker.inbox`.

**Register:** not reached.

**Tests:** `test_inbox`, `test_filer`, `test_index`, `test_reminder`, `test_runner`, `test_layers`, `test_repo_map`,
`test_patch_sites`, `test_golden`; then the whole suite.

**Stop and ask:** the composer test names `inbox`; any moved definition reads a filer or `intents` name.

**Accept when:**
- Section 4.1's shared accept-when holds.
- **Windows:** no label. The walk reads paths but changes no path rule, lock or replace; its Windows behaviour is the
  same calls.
- **Office `-Tests`:** none of its own.

---

### P4.8 `readme_ack.py`: the received list and the refresh (A-1 step 5)

- **Cost:** S.
- **Tier:** Opus. `refresh_household_readme` is the one call the pass, the rollover and every app action make, and
  it never raises.
- **Findings:** A-1 step 5; A-4.
- **Depends on:** P4.7.
- **Routing code:** no.
- **Layer and domain:** L3, `sorting`.

**What moves** (filer, at `68b9212`; about 185 lines): `_RECEIVED_DECISIONS` (1273), `_day_of`, `_request_of_copy`,
`_requests_of`, `received_for` (1335), `README_NOT_REWRITTEN` (1442), `refresh_household_readme` (1449), and
`_counts_as_received` (2608, from the working copies). It imports `_readme_lock` and `_AN_EXTENSION` from `copies`,
and L1 and L0 names.

**What the filer imports back** (review 2, S17). Measured at `68b9212`, two of the moved names have a reader that
stays: `documents_by_request` (7224-7255, which P4.9 moves to `actions`) calls `_counts_as_received` (7248) and
`_requests_of` (7249), and names `_requests_of` in its docstring (7230). No other filer line outside the moved code
reads a moved name. So until P4.9 the filer imports exactly those two from `readme_ack` at load
(`from tracker.readme_ack import _counts_as_received, _requests_of`), for its own use, which section 2.1 allows; it is
an in-layer edge (L3 to L3), and `readme_ack` imports nothing of the filer, so no cycle. Neither name has a stand-in
or a test read at `68b9212` (`git grep` over `tests` and `tools` finds none), so no site moves for them.

**Requirements:**

- **R4.8.1, the module** `tracker/readme_ack.py`, by section 4.1. Logger `tracker.filer`.
- **R4.8.2, readers.** `api` (124) and `runner` (188) import `refresh_household_readme` from `tracker.readme_ack`.
  `rollover`'s call-time imports at 764 and 1234 likewise. `tests/builders.py`'s import from P4.2 (R4.2.2) likewise.
  Prose: records 630 (`tracker.filer.received_for`), scaffold's and scanner's pointers, and the grep's other hits.
- **R4.8.3, the stand-ins.** `received_for`, `readme_returns` and `write_readme` go to `readme_ack`; `read_index` and
  `load_manifest` gain it (section 4.0). test_rollover 1407-1408 move to `readme_ack`.
- **R4.8.3a, the test reads that break here** (section 3, Tests; review 1, S5).
  - The filer's only reader of `OTHER_DOCUMENT` (imported from `scaffold` at 343) is the received list (1325-1404),
    which moves, so the filer stops importing it. The three lines that read it through the filer are retargeted
    here to `from tracker.scaffold import OTHER_DOCUMENT`: test_scaffold 704, test_api 6204, and test_api 6587, which
    also reads `received_for` and so becomes `from tracker.scaffold import OTHER_DOCUMENT` and
    `from tracker.readme_ack import received_for` (carry-forward).
  - test_scaffold 926's capture `filer_module.received_for` reads it from `readme_ack`, beside the 943 stand-in that
    moves there.
  - before.txt lists every import of the filer that ruff drops after the move, with the test reads of each; at
    `68b9212` `OTHER_DOCUMENT` is the only one with test reads.
- **R4.8.4, the test split** into `tests/test_readme_ack.py`.
- **R4.8.5, the layer table** (`LAYERS[3]`, comment in R4.6.6's form: "decision 130's received list and the README's
  refresh, out of ``filer`` - ``copies`` (L2) and L1 and L0; the pass, the rollover, the API and the filer's
  ``documents_by_request`` import it"),
  `DOMAINS["sorting"]`.
- **R4.8.6, the docs.** "forty-nine" becomes "fifty"; a `readme_ack` line under L3; the module list.
- **R4.8.7**: `FILER_FAMILY` gains `"tracker.readme_ack"`.
- **R4.8.8, the decision row P334**: the README's received list and its refresh left the filer for
  `tracker/readme_ack.py`; the lock it takes stays in `copies` with the sweep that reads it. It cites A-1, 130 and
  P313.
- **R4.8.9, the curated nodes.** Decision 130's sentences in the filer's role go to `readme_ack`'s node; the filer's
  role says the pass calls the refresh.

**Pin-move list:** `LAYERS[3]`, `DOMAINS`, `FILER_FAMILY`, architecture.md, the module list; test_scaffold 704 and
926, test_api 6204 and 6587 (R4.8.3a).

**Patch sites:** P4.8 rows; `report` for `tracker.filer` and `tracker.readme_ack`.

**Register:** not reached.

**Tests:** `test_readme_ack`, `test_filer`, `test_scaffold`, `test_rollover`, `test_api`, `test_runner`,
`test_layers`, `test_repo_map`, `test_patch_sites`, `test_golden`; then the whole suite.

**Stop and ask:** a moved name has a reader that stays in the filer other than `documents_by_request`'s two
(`_counts_as_received`, `_requests_of`), measured on the base.

**Accept when:**
- Section 4.1's shared accept-when holds.
- `grep -rn "filer import.*refresh_household_readme\|filer.refresh_household_readme" tracker tools tests` finds
  nothing.
- **Windows:** no label. The lock's code moved in P4.4; this job only calls it.
- **Office `-Tests`:** none of its own.

---

### P4.9 `actions.py`: a person's actions and the rescan (A-1 step 6)

- **Cost:** L.
- **Tier:** Opus. The largest move, and the call-time edge to the scanner moves with it.
- **Findings:** A-1 step 6; A-4; P313's Q-A.
- **Depends on:** P4.8.
- **Routing code:** no.
- **Layer and domain:** L3, `sorting`.

**What moves** (filer, at `68b9212`; about 1,380 lines). Re-measure each by name.

| Lines | Names |
|---|---|
| 5567-5973 | `AssignResult` (with its `@dataclass` at 5567), `_issuer_to_add`, `assign_review_file`. **Not** `_taught_spelling` (5581), which stays: the hand-over calls it (6195). |
| 6404-6477 | `_said`, `DismissResult`, `dismiss_review_file` |
| 6480-6834 | the "unfile" section header (6480), `LEFT_FILED` (6489, with its `#:` comment from 6482), `RESCAN_REFUSED`, `UnfileResult`, `unfile_document`, `MarkedMissingResult`, `mark_missing_again`, `_rescan`, `find_filed` |
| 6845-7218 | `PUT_BACK`, `PUT_BACK_FROM_ORIGINAL`, `PUT_BACK_ALREADY`, `PUT_BACK_REFUSED`, `SEVERAL_COPIES_REFUSAL`, `ISSUER_LIST_MOVED`, `NOT_AN_ISSUER_CARD`, `ISSUER_DOES_NOT_NARROW`, `RestoreResult`, `find_moved`, `_gone_copies`, `_find_to_put_back`, `_make_a_gone_copy_again`, `restore_working_copy`, `_put_back_a_moved_copy` |
| 7224-7513 | `documents_by_request`, the `RENAME_*` sentences (P4.5 removed `RENAME_COPY_SYNCING`), `RenameResult`, `_renamed`, `rename_request` |

**Stays in the filer** (the hand-over needs it, decision 132): `_refuse_if_stale` (5521), `PERSON_NOT_ON_RETURN`,
`ALREADY_SPELLED`, `Spelling`, `_taught_spelling`, `StaleRowError`, `STALE_ROW`, `OVERRODE_SHORTLIST`, `_PARKED`, the
hand-over with `find_parked` (5980-6398), and the decision sentences. `actions` imports from the filer at load the
names its code reads (measured at `68b9212`: 21, among them `_find_row`, `_names_row`, `_wanted`, `find_parked`,
`_make_again`, `_remade`, `_the_original_now`, the `_ORIGINAL_*` constants, `MOVED_BACK_SENTENCE`, `MARKED_REFUSAL`
and `NOTHING_TO_PUT_BACK`). `documents_by_request` takes `_counts_as_received` and `_requests_of` with it: the filer's
import of the two from `readme_ack` (P4.8) goes in this job, `actions` imports them from `readme_ack`, and after the
job the filer imports nothing from `readme_ack` (review 2, S17; ruff's F401 is the check). The filer never imports
`actions`. The places that call `ledger.new` in the moved code
(5647, 5925 and 7485 at `68b9212`) make `actions` a composer.

**Requirements:**

- **R4.9.1, the module** `tracker/actions.py`, by section 4.1. Logger `tracker.filer`.
- **R4.9.2, readers.** `api` (124) imports `assign_review_file`, `dismiss_review_file`, `documents_by_request`,
  `mark_missing_again`, `rename_request`, `restore_working_copy` and `unfile_document` from `tracker.actions`, and
  keeps `NOT_WAITING`, `Spelling`, `StaleRowError`, `find_parked`, `hand_over`, `hand_over_copies`, `requests_taking`
  and `waiting_target` from the filer. Prose: ledger 409, `tools/learned_keywords.py` 4, reasons 795 (the pointer to
  `PUT_BACK_REFUSED`; 787-794 point to `UNFILED_BY_PERSON`, `DISMISSED_BY_PERSON` and `ASSIGNED_BY_PERSON`, which
  stay in the filer), and the grep's other hits.
- **R4.9.3, the stand-ins.** Section 4.0's P4.9 rows: `_record` and `_carry_out_a_persons_ops` go to `actions` (and
  the filer, for `_record`); `_move_whole`, `_existing_copy`, `_review_copy_path`, `_do_op` gain `actions`;
  `_copy_whole` becomes `actions` and `intents` (the filer no longer calls it); `path_limit`, `is_cloud_placeholder`,
  `locate`, `sha256_of`, `read_index` and `load_manifest` gain `actions`. test_api 6338-6389 (`_do_op`) and 6469-6475
  (`_record`) drive a person's actions through the API: their targets follow the table.
- **R4.9.4, the test split** into `tests/test_actions.py` (about 94 tests at `68b9212`).
- **R4.9.5, the layer table** (`LAYERS[3]`, comment: "``actions`` joins L3 with P335 (SPEC-architecture-p4 P4.9): a
  person's actions on the record and the rescan after them, out of ``filer`` - ``filer`` (in-layer, the hand-over's
  shared pieces), ``intents``, ``inbox``, ``readme_ack``, ``copies`` and L1 and L0 at load, ``scanner`` at call
  time; only the API imports it"), `DOMAINS["sorting"]`. (`inbox`: `actions` reads `_absent` and
  `_copy_taken_by_a_later_row`, which P4.7 moved there; review 2, S21.) In the same commit, `readme_ack`'s comment
  (R4.8.5) reads "a person's actions" in place of "the filer's ``documents_by_request``".
- **R4.9.6, `COMPOSERS`** gains `"actions"`; the filer stays.
- **R4.9.7, the call-time edge.** `_rescan` and `RESCAN_REFUSED` move, so the call-time import of `tracker.scanner`
  is in `actions` and nowhere in the filer. The curated `calls` edge `tracker/filer.py` → `tracker/scanner.py` becomes
  `tracker/actions.py` → `tracker/scanner.py`, stated on both nodes. The `precedes` edge (the pipeline's order)
  stays from the filer.
- **R4.9.8, the tests of the edge.**
  - `tests/test_layers.py::test_the_scanner_never_imports_the_filer_and_the_filer_reaches_it_only_at_call_time` (601)
    is renamed `test_the_scanner_never_imports_the_filer_or_a_persons_actions_and_they_reach_it_only_at_call_time`.
    It asserts: `filer` and `actions` are in neither `load["scanner"]` nor `call["scanner"]`; `scanner` is not in
    `load["filer"]`, `call["filer"]` or `load["actions"]`; and `scanner` is in `call["actions"]`.
  - test_layers' docstring (13-15). Old: "The scanner never imports the filer: the filer reaches it at call time,
    inside ``_rescan()``." New: "The scanner never imports the filer: a person's actions (``actions``) reach it at
    call time, inside ``_rescan()``."
  - `tests/test_repo_map.py::test_the_filer_calls_the_scanner_one_way_and_no_load_time_cycle_remains` (876) is renamed
    `test_a_persons_actions_call_the_scanner_one_way_and_no_load_time_cycle_remains`, with `tracker/actions.py` in
    place of `tracker/filer.py` in its four `from` edges, and one more assertion: no `imports` or `imports_at_call`
    edge from `tracker/filer.py` to `tracker/scanner.py`. The scanner-to-filer assertions stay, and gain the same
    two for `tracker/actions.py`.
- **R4.9.9, CLAUDE.md** (the only CLAUDE.md change in this phase). Old:

  ```
  The scanner never imports the filer: it reads the index from `index.py`, and
  the filer reaches the scanner only at call time, inside `_rescan()` - a
  curated `calls` edge, stated on both nodes (P313's Q-A).
  ```

  New:

  ```
  The scanner never imports the filer: it reads the index from `index.py`, and
  a person's actions (`actions.py`) reach the scanner only at call time, inside
  `_rescan()` - a curated `calls` edge, stated on both nodes (P313's Q-A, P335).
  ```

  The line breaks of the surrounding paragraph are kept; no other CLAUDE.md line changes. The old text ends partway
  through CLAUDE.md line 64, which goes on with " Four two-module" (review 2's note): replace the quoted text, not
  whole lines 62-64, so the next sentence keeps its start (`test_single_source` would catch a dropped one).
- **R4.9.10, the other prose.** `docs/architecture.md` 32. Old: "The scanner never imports the filer; the filer
  reaches it at call time through a rescan." New: "The scanner never imports the filer; a person's actions reach it
  at call time through a rescan." `tracker/locking.py` 93's pointer to `_rescan`, and the scanner's own docstring if it
  names the filer as the rescan's caller.
- **R4.9.11, the docs.** "fifty" becomes "fifty-one"; an `actions` line under L3; the module list.
- **R4.9.12**: `FILER_FAMILY` gains `"tracker.actions"`.
- **R4.9.13, the decision row P335**: a person's actions left the filer for `tracker/actions.py` at L3, importing the
  hand-over's shared pieces from the filer; the rescan and its call-time edge to the scanner moved with them, so the
  filer no longer reaches the scanner at all; `actions` is a composer. It cites A-1, 119, 132, P313 (Q-A) and P320.
- **R4.9.14, ENFORCERS.** `actions` joins no rule's set: a person's actions are a person's decision, and the rules'
  enforcers (filer, copies, intents) still do the work. Say so in its curated node.

**Pin-move list:** `LAYERS[3]`, `DOMAINS`, `COMPOSERS`, `FILER_FAMILY`, the two edge tests and test_layers'
docstring, CLAUDE.md, architecture.md (line 29, 32 and the L3 list), the module list, the curated `calls` edge.

**Patch sites:** P4.9 rows; `report` for `tracker.filer`, `tracker.intents`, `tracker.copies` and `tracker.actions`.

**Register:** not reached.

**Tests:** `test_actions`, `test_filer`, `test_index`, `test_api`, `test_scanner`, `test_containers`, `test_layers`,
`test_repo_map`, `test_patch_sites`, `test_single_source` (it quotes CLAUDE.md), `test_golden`; then the whole suite.

**Stop and ask:**
- `actions` needs a filer name the filer does not define at load (an import inside a filer function, say).
- The filer turns out to call anything that moves here (the AST check says it calls none).
- The cycle test reports `actions` and `filer` as a pair: that would mean the filer imports `actions`.
- `test_single_source` quotes the CLAUDE.md sentence: then its pin moves in the same commit, with the new text.

**Accept when:**
- Section 4.1's shared accept-when holds, with exactly R4.9.8's two renames in the collect-only diff (old id to new
  id, `tests/test_layers.py` and `tests/test_repo_map.py`), and no other line.
- `grep -n "scanner" tracker/filer.py` finds no import.
- The filer is about 3,700 lines (section 1); say the number.
- **Windows: label** (review 1, S6). The job moves, unchanged, code that holds the engagement lock (six
  `with engagement_lock(engagement_dir):` blocks at `68b9212`: 5737, 6454, 6575, 6770, 7028, 7380) and checks a
  rename's path length (`RENAME_PATH_TOO_LONG` 7269, raised at 7459 in `rename_request`, with `path_limit` read as a
  global). No rule in them changes, but they are the held engagement lock and path handling CLAUDE.md names, so the
  label rides the stack's one run.
- **Office `-Tests`:** `test_actions,test_api,test_filer`: the actions' own tests, the API that drives them, and the
  hand-over they share with the filer.

---

### P4.10 `keywords.py`: the matcher out of content_check (A-5)

- **Cost:** M.
- **Tier:** Opus. The matcher is routing code: every keyword, form number and place a page is judged on is computed
  here, and the stand-ins that prove the judging runs only in the child must follow it.
- **Findings:** A-5; A-4; the carry-forward's `tests/samples.py` and router-wording items.
- **Depends on:** P4.9.
- **Routing code:** **yes.** It moves the matcher (`says`, `contains_keyword`, `form_key`, `self_named_forms`,
  `own_forms`, `dominant_forms`, `evaluate_rules`) byte for byte. No keyword, catalog, typed case or rule changes. The
  office backtest covers it (section 6).
- **Layer and domain:** L2, `sorting`.

**What moves** (content_check, at `68b9212`; about 1,060 lines). Re-measure each by name.

| Lines | Names |
|---|---|
| 233-236 | `_FOOTER_LINES` with its `#:` comment. The "evidence" section header (231) stays above `_evidence_from_json` until P4.11. |
| 259-277 | `ContentResult` (with its `@dataclass` at 259), the rules' verdict: `evaluate_rules` returns it, so it moves with the rules. |
| 316-1355 | the whole "rules" section, from its header to the end of `evaluate_rules`: `has_content_rules`, `rules_fingerprint`, `FORM_VARIANTS`, the joiner and dash constants, `keyword_pattern`, `_seams`, `_occurrences`, `contains_keyword`, `TITLE_CHARS`, `is_form_number`, `form_key`, the mention and line machinery (`_weigh_mention` through `_mentions`, with `_last_line` and `_line_of`), `dominant_forms`, `form_family`, `MULTI_FORM_FAMILIES`, `own_forms`, `BROKER_FORM`, `carries_a_1099b_section`, `self_named_forms`, the ask-window machinery, `FIRST_PAGE_PHRASES`, `says`, `any_keyword_matched`, `required_matched`, `DATE_LINE_MAX`, `date_pattern_at`, `evaluate_rules` |

Measured at `68b9212` with an AST walk over the moved definitions: they read nothing that stays in content_check
(`_FOOTER_LINES` and `ContentResult` are the only outside names they read, and both move). They import `hashlib`,
`json`, `re`, `Callable` and `Iterable`, `dataclass`; from `manifest` `RequestItem`, `derived_date_pattern`,
`has_routing_rules`, `keyword_alternatives`; from `records` `PAGE_BREAK`, the `RULE_*` and `WHERE_*` names and
`Evidence`; and `reasons`. Measure the exact list from the moved code's reads; ruff's F401 and F821 are the check.
`keywords` imports nothing at L2 or above, nothing of content_check, `ocr` or `store`, and does not log (section 2.1).

**Requirements:**

- **R4.10.1, the module** `tracker/keywords.py`, by section 4.1. Its docstring carries the reasoning of the moved
  code's own comments: decisions 55, 57, 58 and 60 (the variant joiner, the one list of variants, the seams), 105 and
  107 (`own_forms` as the one reading of which forms a page counts as its own), 128 (a name is read the same
  whole-token way, but only as evidence for a person), 178 (`_line_of`'s look-back memo) and 189 (every one of these
  runs in the reading's child, inside `judge`). It says why it sits at L2 although it imports nothing above L1: it is
  what a reading is judged by, beside its one caller (`content_check.judgment_of`), and moving it lower would be a
  decision row of its own.
- **R4.10.2, content_check imports back** by name exactly what its remaining code reads, measured at `68b9212`:
  `ContentResult`, `any_keyword_matched`, `carries_a_1099b_section`, `dominant_forms`, `evaluate_rules`,
  `has_content_rules`, `own_forms`, `required_matched`, `rules_fingerprint`, `self_named_forms`. It does not import
  `says`, `contains_keyword`, `form_key` or any constant: nothing it keeps reads them. ruff is the check.
- **R4.10.3, readers in `tracker/` and `tools/`,** retargeted in the same commit:
  - `router` (174-188): `BROKER_FORM`, `ContentResult`, `contains_keyword`, `form_key` and `rules_fingerprint` from
    `tracker.keywords`; the rest of its content_check import is unchanged in this job.
  - `tools/learned_keywords.py` 99: `from tracker.keywords import dominant_forms, says  # noqa: E402`.
  - `tools/vocab_report.py` 86: `from tracker.content_check import extract  # noqa: E402` and
    `from tracker.keywords import dominant_forms, says  # noqa: E402`, in ruff's order.
  - Prose that names a moved name through content_check: `manifest` 787 (`says`), 813 (`required_matched`) and 2015
    (`contains_keyword`); `bounds` 248 (`DATE_LINE_MAX`); `records` 194-195 (`TITLE_CHARS`, `_FOOTER_LINES`);
    `templates` 283 (`FIRST_PAGE_PHRASES`); `router` 81, 277, 348, 380, 493, 562 and 596; `tools/learned_keywords.py`
    69; and every other hit of section 3's grep. `records` 194-195 and `bounds` 248 are `#:` comments at module level,
    not closure parts (section 4.1, the admission closure). A pointer to a name that stays (`extract`, `judge`,
    `judge_bounded`, `judgment_of`, `_extract_pdf`, `MAX_PAGES`) is left as it is.
- **R4.10.4, the register.** `_last_line` is rebound under `global` in `_line_of`, so the derived register key
  becomes `("keywords", "_last_line")`. In `tracker/resident.py`, `PER_COMMAND`'s key `("content_check",
  "_last_line")` becomes `("keywords", "_last_line")`, with its comment unchanged. In `tests/test_resident.py`, the
  stand-in at 669 (`monkeypatch.setattr(content_check, "_last_line", None)`) and the two reads inside the injected
  command at 682 and 692 name `keywords`, which the test imports beside `content_check`. Run `test_resident` and grep
  `tests tracker` for `"_last_line"` and `_last_line` (section 2.2, the register's blind spots).
- **R4.10.5, the stand-ins.** `python tools/patch_sites.py report tracker.content_check` at `68b9212` gives 102
  stand-ins in 13 files (97 defined, 5 imported). This job changes the targets of exactly these, by the readers
  measured at `68b9212` (re-derive them on the base, section 4.0's method):

  | Site | Names | Readers after the move |
  |---|---|---|
  | test_content_check 2328 (`in_a_child.setattr` in a literal-tuple loop) | `says` | `keywords` (read by `_keywords_said`) |
  | | `dominant_forms` | `keywords` and `content_check` (read by four keyword functions and by `judgment_of`) |
  | | `evaluate_rules`, `own_forms`, `self_named_forms`, `required_matched`, `any_keyword_matched`, `carries_a_1099b_section`, `judgment_of` | `content_check` (read by `judgment_of`, or by `judge`), unchanged |
  | test_content_check 2654 (a loop over two names, counting calls) | `dominant_forms` | `keywords` and `content_check` |
  | | `self_named_forms` | `content_check`, unchanged |
  | test_resident 669 | `_last_line` | `keywords` (R4.10.4) |

  The 2328 loop becomes a loop of `(module, name)` pairs, or two loops, in a form patch_sites follows. The 2654 test
  counts each call once: a call from a keyword function looks the name up in `keywords`, and one from `judgment_of`
  in `content_check`, so a stand-in on both counts what one stand-in counted before. Its assertion
  (`{"dominant_forms": 1, "self_named_forms": 1}`) does not change. No other content_check stand-in changes target.
- **R4.10.6, tests that read a name content_check no longer holds** are retargeted (section 3): `test_backtest`'s and
  `test_ocr`'s `from tracker.content_check import ... contains_keyword`, `test_catalog`'s `FIRST_PAGE_PHRASES`,
  `test_router`'s `TITLE_CHARS` and `_says_where`, and every `content_check.<moved name>` and
  `from tracker.content_check import <moved name>` in `test_content_check.py` and the file it splits into. Names
  content_check imports back (R4.10.2) may wait for P4.13.
- **R4.10.7, the test split** into `tests/test_keywords.py` (about 27 tests at `68b9212`, section 4.1's rule:
  `keywords` < `verdicts` < `content_check`), and `tests/content_check_helpers.py` only if the split needs one.
- **R4.10.8, `INPUT_PATHS`** (`tools/vocab_report.py` 107-114). The matcher's home and the line makers join it, and
  the reading's stays:

  ```
  INPUT_PATHS = (
      "tracker/templates.py",       # the catalog
      "tracker/keywords.py",        # says(), the matcher
      "tracker/content_check.py",   # extract(), the reading the report reads every document with
      "tracker/manifest.py",        # the validation and its defaults
      "tests/routing_cases.py",     # the typed cases, the workbook cases, the blank forms' placements and two printed forms
      "tests/samples.py",           # the line makers the typed cases are built from
      "tools/corpus.py",            # how the firm's own documents are read
      "tools/vocab_report.py",      # this generator
  )
  ```

  Then `python tools/vocab_report.py build`. Prove the counts and hits unchanged: load `docs/vocab-coverage.json`
  before and after, drop the `inputs` key from each, and compare; they are equal, and `docs/vocab-coverage.md`
  differs at most where it prints the inputs. The command and its result go in after.txt. (The carry-forward's
  `tests/samples.py` item.)
- **R4.10.9, the router's wording** (carry-forward). This job is the first to edit `tracker/router.py`:
  - Docstring, 156 (review 2, S22). Old: "It is re-exported here for one release." New: "This module reads it from there and so
    offers it too; ``tests/test_records.py`` (``RE_EXPORTED``) pins that it is the record's own object."
  - The comment over the records import, 191-195. Old:

    ```
    # The routing decision is a record and lives in tracker/records.py
    # (decision 100); this module is the deciding. Routing and EVIDENCE_CONTENT
    # are re-exported from here, so every `from tracker.router import Routing`
    # still resolves to the same class; kept for one release; import from
    # tracker.records.
    ```

    New:

    ```
    # The routing decision is a record and lives in tracker/records.py
    # (decision 100); this module is the deciding. It reads Routing and
    # EVIDENCE_CONTENT from there, so `from tracker.router import Routing`
    # resolves to the record's own class (tests/test_records.py, RE_EXPORTED).
    # A new reader imports both from tracker.records.
    ```
  - Docstring, 121: ``:class:`tracker.content_check.Evidence``` becomes ``:class:`tracker.records.Evidence```.
  - The router's curated note. Old: "The Routing record and EVIDENCE_CONTENT live in tracker/records.py (decision 100)
    and are re-exported here for one release: the decision is a record, this module is the deciding." New: "The
    Routing record and EVIDENCE_CONTENT live in tracker/records.py (decision 100); this module reads both from there
    and so offers them too (tests/test_records.py, RE_EXPORTED): the decision is a record, this module is the
    deciding."
- **R4.10.10, the layer table.** `keywords` joins `LAYERS[2]`, with a comment above the set: "``keywords`` joins L2
  with P336 (SPEC-architecture-p4 P4.10): the matcher and the rules out of ``content_check``, which imports them back -
  ``manifest`` and ``records`` (L1) and ``reasons`` (L0); nothing at L2 or above. It sits at L2 beside the one
  reading it judges for." It joins `DOMAINS["sorting"]`.
- **R4.10.11, the docs.**
  - `docs/architecture.md`: "fifty-one" becomes "fifty-two". Under L2, after the `content_check.py` line:
    "- `keywords.py`: the matcher and the rules: a keyword said whole, a form's number and its variants, which forms
    a page names as its own and where on the page a word is said; pure functions of the text, run in the reading's
    child (decision 189)." The `content_check.py` line's "tested against the row's keyword and date rules" becomes
    "tested against the row's keyword and date rules (`keywords.py`)".
  - `tracker/__init__.py`'s module list: content_check's line, old "tier 3 text extraction + rules + verdict cache",
    new "tier 3 text extraction, the judgment + verdict cache"; after it, "- keywords      : the matcher and the
    rules a reading is judged by (pure functions of the text)".
- **R4.10.12, the decision row P336**: the matcher and the rules left content_check for `tracker/keywords.py` at L2;
  content_check keeps the one reading and the judgment that calls them; `tests/samples.py` joined the vocabulary
  report's inputs. It cites A-5, 107, 189, P313 and the carry-forward.
- **R4.10.13, the curated nodes.** `keywords`' node takes the content_check notes about the matcher (decisions 55,
  57, 58, 60, 105's step-0 finding about `own_forms`, `MULTI_FORM_FAMILIES`), each sentence moved, not copied.
  content_check's node keeps the reading, the judgment and the cache. `keywords` joins no `ENFORCERS` set: "nothing is
  guessed" is upheld where the decision is made (router, filer, review), and "no AI on client documents" by the
  reading (content_check) and the validators; the node says so.
- **R4.10.14, the annotated names** (section 4.1's grep): `FORM_VARIANTS` (341) and `_last_line` (683) move. The map
  sees neither before or after (section 2.2), so no export or edge changes.

**Pin-move list:**
- `tests/test_layers.py`: `LAYERS[2]` and its comment, `DOMAINS["sorting"]`.
- `tracker/resident.py`: `PER_COMMAND`'s `_last_line` key; `tests/test_resident.py` 669, 682, 692.
- `tools/vocab_report.py` `INPUT_PATHS`; `docs/vocab-coverage.json` and `.md` (rebuilt).
- `docs/architecture.md` line 29, the L2 list and the content_check line; `tracker/__init__.py`'s module list.
- The router's curated note.
- `ADMISSION_PIN[6]`: unchanged (the `records` and `bounds` pointers are comments, not parts).

**Patch sites:** R4.10.5. before.txt holds `report tracker.content_check`; after.txt holds `report
tracker.content_check` and `report tracker.keywords`. The total over the two is 102 plus one per name the loops now set
on two modules (`says` moves rather than doubles; `dominant_forms` doubles at two sites).

**Register:** `("content_check", "_last_line")` becomes `("keywords", "_last_line")` (R4.10.4). `_STOP` and
`_COULD_NOT_START` stay in content_check (A-7 is phase 7's).

**Typecheck:** content_check has no entry after P4.1, and `keywords` is born clean. `tools/learned_keywords.py` keeps
its one entry (`import-not-found` for `vocab_report`); its count does not rise.

**Tests:** `test_keywords`, `test_content_check`, `test_router`, `test_vocab_report`, `test_learned_keywords`,
`test_backtest`, `test_catalog`, `test_ocr`, `test_names`, `test_irs_forms`, `test_resident`, `test_records`,
`test_layers`, `test_repo_map`, `test_single_source`, `test_patch_sites`, `test_suite_shape`, `test_golden`, each as
its own process; then the whole suite.

**Stop and ask:**
- A moved definition reads a name that stays in content_check (the AST walk says none does).
- The vocabulary report's counts or hits change.
- `test_content_check`'s comparison of the judgment with the rules on the corpus (the "proof that `CACHE_VERSION`
  need not move", 2548) fails.
- A keyword function is found to log.

**Accept when:**
- Section 4.1's shared accept-when holds.
- `keywords` imports nothing of `content_check`, `verdicts`, `ocr` or `store`.
- `grep -rnE "content_check import[^\n]*\b(says|contains_keyword|form_key|BROKER_FORM|dominant_forms)\b" tracker tools`
  finds nothing.
- R4.10.8's comparison is equal.
- **Windows:** no label. No lock, atomic replace or path code; pure functions of text.
- **Office `-Tests`:** none of its own. The office backtest before and after phase 4 covers the matcher (section 6).

---

### P4.11 `verdicts.py`: the judgment's shapes and the verdict cache (A-5)

- **Cost:** M.
- **Tier:** Opus. The cache is decision 107's (verdicts in the store, never text), and the judgment's shapes are what
  crosses the reading child's pipe (decision 189).
- **Findings:** A-5; A-4.
- **Depends on:** P4.10.
- **Routing code:** **yes.** The router reads the judgment's shapes and leaves its verdicts in the cache. Nothing in
  them changes: the shapes, the cache key, `CACHE_VERSION` (14) and every stored row stay as they are. The office
  backtest covers it (section 6).
- **Layer and domain:** L2, `reading`.

**What moves** (content_check, at `68b9212`; about 420 lines). Re-measure each by name.

| Lines | Names |
|---|---|
| 141-144 | `RETIRED_CACHE_FILENAME` with its `#:` comment |
| 145-152 | `CACHE_VERSION` with its `#:` comment |
| 231-256 | the "evidence" section header and `_evidence_from_json` (P4.10 took `_FOOTER_LINES` and `ContentResult` out of it) |
| 280-313 | `Extraction` |
| 1376-1513 | `RowQuestion`, `row_question`, `NameQuestion`, `Questions`, `RowJudgment`, `Judgment`, `unjudged`. The judgment section's comment block (1356-1373) stays above `judgment_of`, which stays. |
| 2269-2459 | the "cache" section: `_HELD_READINGS` and `ContentCache` |

Measured at `68b9212`: the moved definitions read, of content_check's names, only each other and `ContentResult`
(now in `keywords`, L2 in-layer). They import `OrderedDict`; `MISSING`, `asdict`, `dataclass`, `field`, `fields`,
`replace`; `os`; `Path`; `hold` and `store`; from `validators` `sha256_of`; from `records` `Evidence`; from `manifest`
`RequestItem`; from `keywords` `ContentResult`. ruff is the check. `store` makes L2 the lowest layer that holds it with
`keywords`. `verdicts` does not log.

Why the shapes move with the cache (section 2.1): `ContentCache` stores and returns `Judgment`s, and content_check
annotates with `ContentCache`. `tests/import_graph.py` counts an `if TYPE_CHECKING:` import as a load edge, so the two
modules cannot both name each other's types. With the shapes in `verdicts`, the only direction is content_check →
`verdicts` → `keywords`.

**Requirements:**

- **R4.11.1, the module** `tracker/verdicts.py`, by section 4.1. Its docstring carries decision 107 (the cache lives in
  the store, per engagement, and stores verdicts only: pass or fail, the reason and the evidence, never extracted text),
  decision 189 (the judgment's shapes are what crosses the reading child's pipe, in the firm's own words and never a
  word of the document), and why the shapes and the cache are one module (above).
- **R4.11.2, content_check imports back** by name exactly what its remaining code reads, measured at `68b9212`:
  `ContentCache`, `Extraction`, `Judgment`, `NameQuestion`, `Questions`, `RowJudgment`, `RowQuestion`, `row_question`,
  `unjudged`. Not `CACHE_VERSION`, `RETIRED_CACHE_FILENAME` or `_evidence_from_json`: nothing it keeps reads them.
  It no longer imports `sha256_of`, `hold` or `OrderedDict` unless something it keeps reads them (ruff decides).
- **R4.11.3, readers in `tracker/` and `tools/`,** retargeted in the same commit:
  - `router`: `ContentCache`, `Extraction`, `Judgment`, `Questions` and `row_question` from `tracker.verdicts`; it
    keeps `OPEN_TEST_FINGERPRINT`, `judge_bounded` and `judgment_of` from content_check.
  - `scanner` 84: `ContentCache` from `tracker.verdicts`; `OutOfTime`, `check_content` and `open_verdict` stay.
  - The filer's family: every `from tracker.content_check import` of a moved name on the job's base (at P4.9's end:
    the filer's `ContentCache`, `Judgment` and `NameQuestion`, `copies`' `ContentCache` and `intents`'
    `ContentCache`; measure).
  - `after_install` 160: `from tracker.verdicts import RETIRED_CACHE_FILENAME`.
  - Prose: `store` 153 and 289 (`CACHE_VERSION`) and 2532 (`ContentCache`); `ocr` 79 (`CACHE_VERSION`); the router's
    curated note's `content_check.ContentCache`; content_check's own docstring (its "Caching" and "Where the cache
    lives" paragraphs, 55-80, move to `verdicts`' docstring and leave one sentence naming the new home); and every other
    hit of section 3's grep.
- **R4.11.4, tests that read a name content_check no longer holds** are retargeted in this job: `CACHE_VERSION`
  (`tests/builders.py` 76, `test_store` 562, the filer family's tests at test_filer 645 and 2499 at `68b9212`, and
  test_content_check 26 with its uses), `RETIRED_CACHE_FILENAME` (`test_single_source` 21 and 738, `test_scanner` 13,
  `test_after_install` 23, test_filer 645 and 684), and any `_evidence_from_json` or `_HELD_READINGS` read. Measure on
  the base by grep, wherever the P4.4-P4.9 splits put those tests. Names content_check imports back may wait for P4.13.
- **R4.11.5, the stand-ins.** `report tracker.content_check` on the base. `sha256_of` is read in content_check only by
  `ContentCache`, so its four stand-ins on content_check (test_filer 3013, test_scanner 397, 836 and 865 at
  `68b9212`) move to `verdicts`. test_filer 3013's own `filer`-side stand-in follows section 4.0's row. No other
  content_check stand-in changes target.
  - The three captures of the original beside the test_scanner stand-ins, `real = content_check_module.sha256_of`
    (test_scanner 388, 830 and 859 at `68b9212`), read `sha256_of` from `tracker.validators`, its defining module:
    content_check's last reader of `sha256_of` is `ContentCache`, so ruff makes content_check drop the import and the
    three reads would fail (section 3, Tests; found in round 2, the same kind as review 1's S5). A stand-in on a `ContentCache` method (`monkeypatch.setattr(ContentCache,
  ...)`) replaces a class attribute and needs no change; list any found.
- **R4.11.6, the pipe and the store.** Two facts the job measures and states in before.txt, and that stop the job if
  either is false:
  - `Judgment` and `Extraction` cross the reading child's pipe pickled, under their qualified names
    (`tracker.verdicts.Judgment` after the move). Both ends import the same code, so nothing changes. No module pickles
    one to disk: `grep -rn "pickle" tracker` finds only prose (reasons 76, firm_cache 35 at `68b9212`).
  - The cache writes `asdict` rows to the store's two tables (`store.remember_verdicts`), keyed by `CACHE_VERSION`.
    No class name is stored. Rows written before the move are read after it unchanged. The job adds one test to
    `tests/test_verdicts.py`, `test_a_verdict_row_written_before_verdicts_moved_reads_after_it`: a verdict row in the
    shape the code at the job's base writes (`asdict` of a `ContentResult` carrying an `Evidence`, under
    `CACHE_VERSION`), pasted as a literal, written to an engagement's verdicts with `store.remember_verdicts`, and read
    back through the moved `ContentCache` (`get_by_digest`) as a `ContentResult` equal to the one the literal was
    made from. It is the job's one added test (section 4.1's
    collect-only line).
- **R4.11.7, the test split** into `tests/test_verdicts.py` (about 5 tests at `68b9212`).
- **R4.11.8, the layer table.** `verdicts` joins `LAYERS[2]`, with a comment: "``verdicts`` joins L2 with P337
  (SPEC-architecture-p4 P4.11): the judgment's shapes and decision 107's verdict cache out of ``content_check``, which
  imports them back - ``keywords`` (L2, the rules' verdict), ``store``, ``validators``, ``records`` and ``manifest``
  (L1) and ``hold`` (L0)." It joins `DOMAINS["reading"]`. The comments above `copies` (R4.4.7) and `intents`
  (R4.6.6) name ``verdicts``' ``ContentCache`` in place of ``content_check``'s, because both now import it from
  `verdicts`.
- **R4.11.9, the docs.**
  - `docs/architecture.md`: "fifty-two" becomes "fifty-three". The `content_check.py` line's ", with a verdict cache
    keyed by the file's content" becomes ", its verdicts kept by `verdicts.py`". Under L2, after `keywords.py`:
    "- `verdicts.py`: what a judgment says and what crosses back from the reading's child, and the verdict cache:
    pass or fail, the reason and the evidence, keyed by the file's content and kept in the store (decision 107);
    never a word of the document."
  - `tracker/__init__.py`: content_check's line becomes "tier 3: the one reading of a document, and its judgment";
    after `keywords`' line, "- verdicts      : the judgment's shapes and the verdict cache (in the store, decision
    107)".
- **R4.11.10, the decision row P337**: the judgment's shapes and the verdict cache left content_check for
  `tracker/verdicts.py` at L2; the shapes moved with the cache because the cache keeps them and the import graph
  counts a type-only import as a load edge; `CACHE_VERSION` stays 14. It cites A-5, 107, 150, 189 and P313.
- **R4.11.11, the curated nodes and edges.** `verdicts`' node takes decision 107's sentences, the step-0 re-run's
  finding as it concerns the cache, and `_evidence_from_json`'s note. The two curated edges from
  `tracker/content_check.py` to `artifact:tracker.db` (`reads`, `writes`) become edges from `tracker/verdicts.py`:
  content_check no longer touches the store. `verdicts` joins no `ENFORCERS` set; its node says the cache keeps no text,
  which is decision 107's line, and that "no AI on client documents" is upheld by the reading.
- **R4.11.12, the vocabulary report.** content_check is in `INPUT_PATHS`, so `python tools/vocab_report.py build`
  runs in the same commit, with R4.10.8's comparison (equal apart from `inputs`). `verdicts` does not join
  `INPUT_PATHS`: the report reads a document's text (`Extraction.text`) and never the cache, so nothing in `verdicts`
  can change what a keyword finds. The module docstring of `tools/vocab_report.py` is not edited.

**Pin-move list:**
- `tests/test_layers.py`: `LAYERS[2]`, `DOMAINS["reading"]`, and the comments above `copies` and `intents`.
- test_scanner 388, 830 and 859 (R4.11.5: the captures of `sha256_of`).
- The curated `tracker.db` edges (two).
- `docs/architecture.md` (count, content_check line, L2 list); `tracker/__init__.py`.
- `docs/vocab-coverage.json` and `.md` (rebuilt; inputs only).
- `ADMISSION_PIN[6]`: unchanged (`store` is not in the closure).

**Patch sites:** R4.11.5; `report` for `tracker.content_check` before, and `tracker.content_check` and
`tracker.verdicts` after.

**Register:** not reached. `verdicts` binds no module state the register derives (`_HELD_READINGS` is a constant;
a cache's memos are its instance's). A-7's row for `ContentCache` (instances owned by their callers) is unchanged.

**Tests:** `test_verdicts`, `test_content_check`, `test_router`, `test_scanner`, `test_filer` and the filer family's
test files that read a moved name, `test_store`, `test_after_install`, `test_names`, `test_catalog`,
`test_vocab_report`, `test_layers`, `test_repo_map`, `test_single_source`, `test_patch_sites`, `test_golden`, each as
its own process; then the whole suite.

**Stop and ask:**
- R4.11.6's facts do not hold: something pickles a moved class to disk, or stores a class name.
- A moved shape needs a name from content_check (the AST walk says none does).
- `CACHE_VERSION` would have to move.

**Accept when:**
- Section 4.1's shared accept-when holds, with exactly R4.11.6's one added test in the collect-only diff, and no other
  line.
- `verdicts` imports nothing of content_check; content_check imports `verdicts` and `keywords`; `keywords` imports
  neither.
- `grep -rnE "content_check import[^\n]*\b(ContentCache|CACHE_VERSION|RETIRED_CACHE_FILENAME)\b" tracker tools tests`
  finds nothing.
- **Windows:** no label. The cache's writes go through the store's own transaction, unchanged; no lock, replace or
  path code moves.
- **Office `-Tests`:** none of its own.

---

### P4.12 `reader_child.py`: the reading's child and its supervisor (A-6)

- **Cost:** M.
- **Tier:** Opus. The child is decision 150's, 154's, 169's, 186's and 189's at once: a spawned process found by its
  qualified name, a Windows job object, a lifeline, a memory watch off Windows and the awake clock.
- **Findings:** A-6; A-4.
- **Depends on:** P4.11.
- **Routing code:** **yes.** Every reading of a scan, a photo or a container runs in this child, so the office backtest's
  `--ocr` run covers it (section 6). Nothing in the child changes: the stop, the memory caps, `DOCUMENTS_PER_CHILD`
  (100), the exit codes, the error-log words and the run-log lines stay as they are.
- **Layer and domain:** L2, `reading`.

**What moves** (ocr, at `68b9212`; about 860 lines). Re-measure each by name.

| Lines | Names |
|---|---|
| 1008-1661 | the "reading's child" section, from its header: `DOCUMENTS_PER_CHILD`, `PROCESSOR_CHILD_MEMORY`, `GRAPHICS_CARD_CHILD_MEMORY`, `MEMORY_WATCH_SECONDS`, `MEMORY_UNREADABLE`, `WARM_UP_STOP_SECONDS`, `CHILD_EXIT_SECONDS`, `ORPHANED_EXIT_CODE`, `UNREADABLE_JOB_EXIT_CODE`, `OUT_OF_MEMORY_EXIT_CODE`, `_awake_clock_source`, `_AWAKE`, `awake_clock`, `Outcome`, `SCRATCH_ENV`, `sweep_scratch`, `_take_scratch`, `_remove_scratch`, `ReadingChild`, `_the_child`, `_message_of`, `_answer`, `_watch_the_pass`, `_orphaned`, `_extended_limits`, `_kill_on_close_job`, the five `_JOB_OBJECT_*` and `_PROCESS_*` numbers (1517-1521), `_job_memory`, `_close_job`, `_SAID`, `forget_said`, `_say_once`, `_libproc`, `_RUSAGE_INFO_V2` (1577), `_rusage_info_v2`, `_darwin_footprint`, `_linux_footprint`, `_footprint`, `_end` |
| 1664-1864 | the "pass's reader" section, from its header: `Session`, `_crashed`, `_document_name`, `_SESSION`, `reading_session`, `run_in_child` |
| 89-147 | the module docstring's paragraphs "The reading's child", "Nothing a reading does may outlive it in the child", "Nor may anything it writes" and the closing paragraph on `reading_session` and the pipe: they move to `reader_child`'s docstring |

What stays in ocr: the engine, the device, the fault on the card, the settings, the preparation of a page, `read_page`,
`warm_up`, `take_notes`, `reset`, `processor_only`, the short-path warning, and the CLI (1867-1898), which reads
`PACK_UNUSABLE`, `ReaderUnavailable`, `warm_up` and `read_page`, all of which stay.

Measured at `68b9212` by an AST walk over ocr's top-level statements:
- The moved code reads, of ocr's own names, `DEVICE_PROCESSOR`, `PACK_UNUSABLE`, `GPU_FAULT_WARNING`,
  `READER_CANNOT_RUN`, `ReaderUnavailable`, `gpu_pack`, `device`, `take_notes`, `processor_only`, `reset`, `warm_up`
  and `log`. Every one is a constant, an exception class or a function: no moved line reads one of ocr's mutable
  globals (`_ENGINE`, `_DEVICE`, `_PROCESSOR_ONLY`, `_NOTES`, `SETTINGS`) by name, so importing them by name
  snapshots nothing.
- Nothing ocr keeps, the CLI included, reads a moved name. `reader_child` imports from ocr (in-layer, L2); ocr
  imports nothing of `reader_child`.
- Its other imports: `errors`; `locking.pid_alive`; `settings.SettingsError` and `settings.scratch_root`; and the
  standard library (`contextlib`, `os`, `shutil`, `signal`, `subprocess`, `sys`, `tempfile`, `threading`, `time`,
  `traceback`, `Iterator`, `contextmanager`, `dataclass`, `field`, `Path`). `ctypes` and `multiprocessing` stay
  imported inside the functions that use them, as today.

**Requirements:**

- **R4.12.1, the module** `tracker/reader_child.py`, by section 4.1. Its docstring takes ocr's paragraphs (the table
  above), and adds:
  - where it came from (A-6, this job, P338);
  - why it sits at L2: it imports `ocr` (L2, in-layer), `errors`, `locking` and `settings`, and nothing above;
  - why `content_check.in_a_child` and its outcome words stay in content_check (section 2.1: they build
    content_check's Extractions and append to `_COULD_NOT_START`, A-7's state, so moving them would make a load-time
    cycle);
  - why it logs as `tracker.ocr`: it binds `log = logging.getLogger("tracker.ocr")` (section 2.1, Logger names);
  - that its `errors.keep` places keep their words (`"ocr: the scratch sweep"`, `"ocr: the reading's scratch"`,
    `"ocr: the reading child could not be made"`, `"ocr: the reading child"`, and `"ocr"` in `_end`): they are the
    error log's words, which a person reads (decision 193), and `test_errors` 219 pins one of them. They are not
    edited.
- **R4.12.2, ocr imports back nothing.** The AST walk above says no name ocr keeps reads a moved one. Its imports
  that only the moved code used go (ruff decides; at `68b9212` these are likely `signal`, `shutil`, `tempfile`,
  `threading`, `traceback`, `pid_alive`, `SettingsError` and `scratch_root`, measure). ocr's docstring keeps one
  sentence: "The reading's child, its supervisor and the pass's session live in :mod:`tracker.reader_child`
  (P338)."
- **R4.12.3, the spawned child.** `ReadingChild.start` passes `target=_the_child` to the spawn context, which pickles
  it by its qualified name, `tracker.reader_child._the_child` after the move. The spawned process imports
  `tracker.reader_child`, which imports `tracker.ocr`, so the child loads the same code as today plus one module.
  The jobs it runs (`content_check.judge`, the containers' openers, the suite's `tests.child_readers`) are pickled
  by their own names, which do not change. The job states this in before.txt and the suite proves it: every test
  that starts a real child runs.
- **R4.12.4, readers in `tracker/` and `tools/`,** retargeted in the same commit:
  - `content_check`:
    - 227 `_clock = ocr.awake_clock` becomes `_clock = reader_child.awake_clock`. This is a name read at load into a
      second name, as today: the suite moves `content_check._clock` itself, and that stand-in is unchanged. It is not
      section 3's stop-and-ask, because nothing about it changes.
    - 2084 `ocr.awake_clock()` and 2176 `ocr.run_in_child(...)` become `reader_child.`.
    - content_check imports `reader_child` beside `ocr`, which it keeps for `read_page`, `prepared`, `SETTINGS` and
      `ReaderUnavailable`.
    - Prose: 1986 (`tracker.ocr` on the child), 2082, 2160 (the docstring's `:func:` role on `tracker.ocr.run_in_child`).
  - `verdicts`: the `ContentCache.deadline` comment's ``ocr.awake_clock`` (content_check 2316 at `68b9212`).
  - The filer's family: the household pass's `ocr.awake_clock()` read (filer 3943 at `68b9212`; measure which family
    module holds it on the base). It is that module's only read of `ocr`, so its `ocr` import becomes
    `reader_child`. Prose: filer 3417 and 3867.
  - `scanner` 787 (prose).
  - `runner`: 1324 `ocr.awake_clock()` and 2026 `ocr.reading_session(...)` become `reader_child.`; it keeps `ocr`
    for `DEVICE_PROCESSOR`, `PACK_UNUSABLE` and `reader_path_warning`. Prose: 785 and 1274.
  - `api` 6758 `ocr.reading_session(...)` becomes `reader_child.`; it keeps `ocr` for `reader_path_warning`.
  - `resident`: 110's `from tracker import api, errlog, locking, ocr` becomes `api, errlog, locking, reader_child`, for
    `forget_said` (314); its docstring (88-96: "``ocr`` (to forget the reader's warnings between commands)") and the
    register comment (159) say `reader_child`. resident reads nothing else of ocr: the register's other `("ocr", ...)`
    keys are strings, restored through `sys.modules`.
  - `errors` 64 (prose, `ocr.Session`).
  - `tools/corpus.py` 49 `from tracker.ocr import SCRATCH_ENV` becomes `from tracker.reader_child import
    SCRATCH_ENV`; 198 (prose).
  - `tools/reader_bench.py` 494 `ocr.reading_session(in_a_child=False)` becomes `reader_child.`; it keeps `ocr`
    for `use_settings`, `warm_up` and `ReaderUnavailable`. Its docstring's 21-25 still hold ("A reading child
    imports :mod:`tracker.ocr` afresh": the child imports `reader_child`, which imports ocr afresh); its
    ``ocr.reading_session`` at 25 becomes `reader_child`.
  - Every other hit of section 3's grep for the moved names in `tracker tools docs`. `docs/ROADMAP.md` and
    `pilot/DECISIONS.md` are history and stay as written.
- **R4.12.5, the register** (section 2.2). `("ocr", "_SAID")` in `PER_COMMAND` and `("ocr", "_SESSION")` in
  `PER_PROCESS` become `("reader_child", "_SAID")` and `("reader_child", "_SESSION")`, with their comments, in the
  same commit. The test_resident lines that name them move with them: 507 and 672 (`ocr._SAID`), and the string
  program at 426-447 (below). The other `("ocr", ...)` keys (`SETTINGS`, `_DEVICE`, `_ENGINE`, `_NOTES`,
  `_PROCESSOR_ONLY`) stay. `grep -rn "\"ocr\", \"_S" tracker tests` finds nothing after.
- **R4.12.6, the stand-ins** (`patch_sites report tracker.ocr` on the base: 63 at `68b9212`, re-measure). By section 3's
  rule, each follows the module that reads the name after the move:
  - **To `reader_child` (19):** `DOCUMENTS_PER_CHILD` (test_content_check 2526, test_ocr 1099),
    `MEMORY_WATCH_SECONDS` (test_ocr 1413, 1441, 1459, 1481), `_SAID` (test_ocr 1483, test_resident 507, 672),
    `_footprint` (test_ocr 1418, 1425, 1442, 1460, 1482), `_libproc` (test_ocr 1391, 1395), `awake_clock` (test_ocr
    1579, test_runner 2874) and `pid_alive` (test_ocr 1662). The capture beside the last, `real = ocr.pid_alive`
    (test_ocr 1661), reads `pid_alive` from `tracker.locking`: ocr's only reader of it is `sweep_scratch`, which
    moves, so ruff makes ocr drop the import (section 3, Tests; found in round 2).
  - **On both `ocr` and `reader_child`, as a loop (6):**
    - `gpu_pack` (test_ocr 926, 961, 1223): read as a global by the engine (ocr 492, 564) and by the child
      (`ReadingChild.__init__` 1195, `Session.settle` 1688).
    - `warm_up` (test_reader_bench 135, 367, 488): the bench calls `ocr.warm_up()` as an attribute (reader_bench
      497), and `Session.settle` (1692, 1704) reads it as a global in `reader_child` after the move. Today one
      stand-in on ocr reaches both; after the move that takes both targets.
  - **Stay on `ocr` (38):** `READER_PATH_LIMIT`, `_DEVICE`, `_ENGINE`, `_NOTES`, `_PROCESSOR_ONLY`, `_build_engine`,
    `_pixels`, `_refuse_downloads`, `models_folder`, `prepared`, `read_page` and `reader_path_warning`. None is read
    by the moved code.
  - **Hand-read sites the tool does not follow** (section 2.2), retargeted in this job:
    - test_content_check 1580-1590 (`A_PASS_READING`, a string program): `ocr._kill_on_close_job = ...` becomes
      `reader_child._kill_on_close_job = ...`, and its import line takes `reader_child`.
    - test_resident 426-447 (a string program): `ocr.ReadingChild.__init__` (twice), `ocr.run_in_child` (twice) and
      `ocr._SESSION` become `reader_child.`; `ocr._ENGINE` and `ocr._PROCESSOR_ONLY` stay; the import line takes
      `reader_child`.
    - test_ocr 1160-1173 (`A_PASS_BETWEEN_DOCUMENTS`, a string program): `ocr.reading_session()` becomes
      `reader_child.`.
    - `tests/child_readers.py` (90, 141, 150, 177): reads only ocr's engine state (`read_page`, `_PROCESSOR_ONLY`,
      `_NOTES`), which stays. No change; listed in before.txt.
    - The job greps `tests/` for every other string program that names `ocr.` and lists each.
  - A fixture's monkeypatch (`in_a_child.setattr(ocr, ...)`) counts as a stand-in and follows the same rule.
- **R4.12.7, tests that read a name ocr no longer holds** are retargeted in this job (ocr imports back nothing, so
  none may wait for P4.13):
  - test_ocr: `ReadingChild`, `Session`, `reading_session`, `sweep_scratch`, `_footprint`, `_close_job`, `_end`,
    `_job_memory`, `Outcome`, `PROCESSOR_CHILD_MEMORY`, `GRAPHICS_CARD_CHILD_MEMORY`, `MEMORY_UNREADABLE`,
    `awake_clock`, and 1623's `content_check._clock is ocr.awake_clock` (becomes `reader_child.awake_clock`), in the
    tests that stay as well as the ones that move;
  - test_resident: `_say_once`, `run_in_child`, `_SAID`, `ReadingChild`, `_SESSION`;
  - test_content_check 2529 (`ocr.reading_session`);
  - test_filer 627 and test_scanner 371, 377 (`ocr.awake_clock()`), wherever the P4.4-P4.9 splits put them.
- **R4.12.8, the test split** into `tests/test_reader_child.py` (about 26 of test_ocr's 71 tests at `68b9212`), by
  section 4.1's rule with ocr's order (`ocr` < `reader_child`). test_ocr's fixtures (`a_card` 907, `in_a_child` 1058,
  `a_short_stop` 1065, `a_pack_here` 1220 at `68b9212`) go to `tests/ocr_helpers.py` only if both files read them
  after the split (measure; `a_card` and `a_pack_here` very likely are). test_content_check's own `in_a_child` and
  `a_short_stop` (1314, 1323) are separate fixtures and stay where they are.
- **R4.12.9, `test_errors`.** `SAID_WHOLE_ON_PURPOSE`'s `("ocr.py", "settle")` becomes `("reader_child.py",
  "settle")`, with its sentence unchanged: `Session.settle` moves. The other `ocr.py` keys (`_build_engine`, `_engine`,
  `_on_the_card`, and `""` for the CLI) stay.
- **R4.12.10, the layer table.** `reader_child` joins `LAYERS[2]`, with a comment: "``reader_child`` joins L2 with P338
  (SPEC-architecture-p4 P4.12): the reading's child, its supervisor and the pass's session out of ``ocr``, which it
  imports (in-layer); ``content_check`` imports it, and ``errors``, ``locking`` and ``settings`` are below it." It joins
  `DOMAINS["reading"]`. Also in `tests/test_layers.py`:
  - L5's comment (211-213: "imports ``api``, ``errlog``, ``locking``, ``ocr``") and 1168's
    `load["resident"] == {"api", "errlog", "locking", "ocr"}` take `reader_child` for `ocr`. The test's name and
    docstring ("the reader") still hold.
  - `ALLOWED_STDLIB`'s comment ("``tempfile`` decision 186's reading child pointing its temp folder at its own scratch
    in ``ocr``") says `reader_child`.
  - `test_the_readings_child_talks_over_a_named_pipe_never_a_socket` walks every `tracker/*.py` and needs no change.
  - No `CALL_TIME_CYCLES` entry: `reader_child` → `ocr` is one way.
- **R4.12.11, the docs.**
  - `docs/architecture.md`: "fifty-three" becomes "fifty-four". Under L2, after the `ocr.py` line: "- `reader_child.py`:
    the reading's child process: one spawned child per pass that every parse of a client's file runs in, with a
    lifeline to the pass, a stop on the awake clock, a memory cap (the job object on Windows, a watch elsewhere) and
    its own scratch folder; replaced after a stop, a crash or every hundred documents (decisions 150, 169, 186, 189)."
    The `ocr.py` line names no child today and is unchanged. The paragraph at 20-25 ("the reading child") is unchanged.
  - `tracker/__init__.py`: ocr's line loses " and the one child process a pass reads in"; after it, "- reader_child  :
    the one child process a pass reads in, its stop, its memory cap and its scratch".
- **R4.12.12, the decision row P338**: the reading's child, its supervisor and the pass's session left ocr for
  `tracker/reader_child.py` at L2; `in_a_child` stayed in content_check because its outcome words build
  content_check's Extractions and append to A-7's could-not-start list; the child logs as `tracker.ocr` and its
  error-log places keep their words; the child is found by its new qualified name and loads the same code. It cites
  A-6, 150, 154, 169, 186, 189, 190 and P313.
- **R4.12.13, the curated nodes and edges.**
  - `reader_child`'s node takes the ocr node's sentences about the child: from "The child: ReadingChild is one
    spawned process ..." through "content_check.in_a_child() words each Outcome.", decision 189's awake-clock
    sentences, decision 190's three parts, decision 186's scratch sentences, and "Memory cap off Windows (R31 of
    SPEC-mac, P248)" through "Windows is unchanged: the job object still enforces, the watch is off." Each pointer
    in them is retargeted (`content_check._clock` reads `reader_child.awake_clock`).
  - ocr's node keeps the engine, the device, the settings and the preparation, and gains: "The reading's child, its
    supervisor and the pass's session (reading_session, run_in_child, awake_clock) are tracker/reader_child.py's
    since P338." Its role loses "- and the pass's one long-lived reading child that every parse of a client's file
    runs in". The processor child's memory cap sentence (P285: `PROCESSOR_CHILD_MEMORY`) moves with the constant.
  - The two curated edges from `tracker/ocr.py` to `artifact:reading scratch` (`reads`, `writes`) become edges from
    `tracker/reader_child.py`: the scratch is the child's.
  - content_check's, runner's, resident's and reader_bench's nodes: each `ocr.awake_clock`, `ocr.reading_session`,
    `ocr.run_in_child` or `ocr.forget_said` in them is retargeted.
  - `reader_child` joins no `ENFORCERS` set. "No AI on client documents" is upheld by the reading's imports, which
    `test_layers` checks over every module.
- **R4.12.14, the vocabulary report.** `tools/corpus.py` is in `INPUT_PATHS` and changes (R4.12.4), so
  `python tools/vocab_report.py build` runs in the same commit, with R4.10.8's comparison (equal apart from
  `inputs`). `reader_child` does not join `INPUT_PATHS`: the report reads text and never starts a child.
- **R4.12.15, the frozen build.** `api_entry.spec`'s `hiddenimports` names `onnxruntime` and the readers, not tracker
  modules; PyInstaller follows `content_check`'s, `runner`'s and `api`'s static imports of `reader_child`, as it
  follows them to ocr today. `api_entry.py` and `api_entry.spec` are not edited. The office's installer build
  (section 6) is the check that the frozen child starts.
- **R4.12.16, the console list.** `CONSOLE_GUARDED` (`test_single_source` 2147) keeps `"ocr"`: the CLI stays.
  `reader_child` has no `__main__` block (CLAUDE.md, P233), so it is in neither list.

**Pin-move list:**
- `tests/test_layers.py`: `LAYERS[2]`, `DOMAINS["reading"]`, the L5 comment, 1168, the `ALLOWED_STDLIB` comment.
- `tracker/resident.py`: the two register keys, the import, the docstring and the comment.
- `tests/test_errors.py`: one `SAID_WHOLE_ON_PURPOSE` key.
- test_ocr 1661 (R4.12.6: the capture of `pid_alive`).
- The curated `reading scratch` edges (two).
- `docs/architecture.md` (count, L2 list); `tracker/__init__.py`.
- `docs/vocab-coverage.json` and `.md` (rebuilt; inputs only).
- `ADMISSION_PIN[6]`: unchanged (none of these modules is in the closure).

**Patch sites:** R4.12.6; `report tracker.ocr` before, and `report tracker.ocr` and `report tracker.reader_child`
after. The accept line: 19 sites on `reader_child`, 6 loops reaching both, 38 on ocr (as re-measured), and none
`unread`.

**Register:** reached (R4.12.5). `test_resident` runs, and the derived-register test proves the keys follow the code.

**Types:** P4.1's ocr fixes sit in the moved code and move with it. `reader_child` is born with no entry in
`docs/typecheck-baseline.json` and must check clean; the two `# type: ignore[attr-defined]` comments on
`ctypes.WinDLL` (ocr 1534, 1551) move byte for byte.

**Tests:** `test_reader_child`, `test_ocr`, `test_content_check`, `test_containers`, `test_resident`, `test_runner`,
`test_api`, `test_api_entry`, `test_filer` and the family file that holds the deadline test, `test_scanner`,
`test_reader_bench`, `test_gpu_pack`, `test_errors`, `test_corpus`, `test_vocab_report`,
`test_layers`, `test_repo_map`, `test_single_source`, `test_patch_sites`, `test_golden`, each as its own process; then
the whole suite.

**Stop and ask:**
- A moved line reads one of ocr's mutable globals by name (the AST walk says none does), or something ocr keeps reads
  a moved name.
- A test that starts a real child fails or hangs after the move: the spawned child did not find
  `tracker.reader_child._the_child`, or found a different module.
- Moving `in_a_child` or any of content_check's outcome words looks necessary.
- A stand-in on `awake_clock` turns out to be needed on content_check's `_clock` as well as on `reader_child` (it is
  set on `_clock` directly today).

**Accept when:**
- Section 4.1's shared accept-when holds.
- `reader_child` imports `ocr` and nothing above L2; ocr imports nothing of `reader_child`.
- `grep -rnE "\bocr\.(awake_clock|reading_session|run_in_child|ReadingChild|Session|forget_said|SCRATCH_ENV|_SAID|_SESSION|DOCUMENTS_PER_CHILD)\b" tracker tools tests`
  finds nothing, apart from prose the job lists as history.
- Every test that starts a real reading child (`no_child_left()` after it) passes on both interpreters.
- **Windows: label.** It moves the Windows job object (`_kill_on_close_job`, `_extended_limits`, `_job_memory`,
  `_close_job`), the process-tree kill (`_end`, `taskkill`, `CREATE_NO_WINDOW`) and the Windows awake clock
  (`QueryUnbiasedInterruptTime`), and several of its tests run only on Windows (the job object's memory cap).
- **Office `-Tests`:** `test_reader_child,test_ocr,test_content_check,test_containers,test_resident,test_runner,test_api_entry,test_errors,test_layers`.
  These hold the job object, the child's spawn in a frozen-style entry, a container opened in the child, the engine's
  one session per command, and the error log's words.
- **Office hands-on steps** (on the installed build from `run_checks.ps1`, with the kit's sample clients folder only):
  1. Run a pass ("Run now"). `scan 0001.pdf` files to the W-2 request (only the reader can file it), the scan inside
     `Scanned forms.zip` is read, and `vacation photo.bmp` waits in Needs Review, as on the build before P4.12. The run
     log's first line names the reader's device as before.
  2. Drop `scan 0001.pdf` again under a new name, start a pass, and close the app while it reads. In Task Manager, no
     second copy of the app's process is left once the app has closed (the job object ends the child with its pass).
  3. Nothing else is repeated: no screen, installer step or path rule changes.
- **Mac (optional, owed to no gate):** the memory watch's `_darwin_footprint` moves byte for byte; the Mac check's
  next run covers it.

---

### P4.13 The moved names read from their home; a guard

- **Cost:** S.
- **Tier:** Sonnet. A grep-driven retarget with an exact rule, and one AST guard in the form of the layer test's own.
- **Findings:** section 2.1's "No re-export facade" row; the carry-forward's test_ledger 832 line (its other three
  lines are P4.8's, section 2.2).
- **Depends on:** P4.12.
- **Routing code:** no. Test files and one guard only; no line under `tracker/` or `tools/` changes, apart from any
  reader R4.13.1's scan finds that an earlier job missed (which the guard then holds).
- **Layer and domain:** no new module.

It is phase 2's P2.13 and P2.14 for a phase that never built a facade: every move job retargeted the readers in
`tracker/` and `tools/`, and the tests that read a name the old module no longer holds. What is left is the tests that
read a moved name through an import-back the old module keeps for its own use (`from tracker.filer import
room_for` while the filer still imports `room_for` from `copies`), which section 3 let wait, and the carry-forward's
test_ledger 832, which reads `PREPARED_DIR_NAME` through the filer (the filer reads it to the end, so it has worked
until now).

**Requirements:**

- **R4.13.1, the guard** in `tests/test_layers.py`, beside the layer test, named as its claim:
  `test_a_name_this_phase_moved_is_read_from_its_home_never_through_the_module_it_left`.
  - A table, `MOVED_OUT`, says where each old module's names went:
    `{"filer": ("copies", "intents", "inbox", "readme_ack", "actions", "index"), "content_check": ("keywords",
    "verdicts"), "ocr": ("reader_child",)}`, with a comment citing P331-P338 and this SPEC.
  - A moved name, for an old module, is a name defined at the top level (a `def`, a `class`, an assignment or an
    annotated assignment) of one of its new homes and not of the old module itself; for `index` only `OPENED` counts
    (P2.9's decision words moved there in phase 2 and are not this guard's). The carry-forward's two names,
    `OTHER_DOCUMENT` (`scaffold`) and `PREPARED_DIR_NAME` (`layout`), count for the filer too, so they do not come back.
  - It walks every `*.py` under `tracker/`, `tools/` and `tests/` with `ast` and fails, naming file, line and name, on:
    - `from tracker.<old> import X` where X is a moved name for `<old>`;
    - `<alias>.X`, where `<alias>` is bound in that file by `from tracker import <old>` (with or without `as`) or
      `import tracker.<old> as <alias>`, and X is a moved name for `<old>`.
  - It reads code only, never strings or comments: a `setattr(module, "name", ...)` target is patch_sites' concern,
    and a string program is R4.13.3's.
  - An allow-list with a reason per entry, `READ_THROUGH_ON_PURPOSE`, starts empty. An entry is a stop and ask.
- **R4.13.2, the retargets.** Every site the guard names at P4.12's head is retargeted to the name's home, in the
  same commit:
  - the import-back reads the move jobs let wait (R4.4-R4.11's "may wait for P4.13" lines, for example
    test_single_source 1913's `prepared_name_for`);
  - the carry-forward's last line: `tests/test_ledger.py` 832 (`from tracker.filer import PREPARED_DIR_NAME`
    becomes `from tracker.layout import PREPARED_DIR_NAME`). The three `OTHER_DOCUMENT` lines (test_scaffold 704,
    test_api 6204 and 6587) were retargeted by P4.8 (R4.8.3a), because they fail from P4.8 on; the guard confirms
    none is left.
  - A read that takes the original object to wrap it in a stand-in (`real = filer_module.room_for`) reads the same
    object from its home; the `setattr` target beside it is not touched.
  The job's before.txt holds the guard's output at P4.12's head (it fails there, which proves it bites), and after.txt
  holds it passing.
- **R4.13.3, the string programs.** The guard cannot read a test's string program (`A_PASS_READING` and its kin). The
  job greps `tests/` for `filer\.`, `content_check\.` and `ocr\.` inside string literals, lists every hit with the
  name it reads, and retargets each moved name (P4.12 retargeted the ones it had to; this is the sweep).
- **R4.13.4, what stays.** `tests/test_records.py`'s `RE_EXPORTED` (router: `Routing`, `EVIDENCE_CONTENT`; manifest:
  three names) is decision 100's and P4.10's, pinned on purpose, and none of those modules is an old module here. A
  read through an old module of a name it still imports from a module this phase did not create
  (`filer_module.sha256_of`, `content_check.reasons`, measured at `68b9212`) is not this guard's and stays. A read of a
  name the old module no longer imports cannot stay: it fails, and section 3's test rule retargeted it in the job
  that dropped the import (`filer.PATH_TOO_LONG` in P4.4, for example).
- **R4.13.5, the curated node** of `tests/test_layers.py` gains one sentence: the guard holds every name phase 4 moved
  to its home, so a test cannot reach it through the module it left. `python tools/repo_map.py update`.

**Pin-move list:** `tests/test_layers.py` (the guard, `MOVED_OUT`, `READ_THROUGH_ON_PURPOSE`); the curated node.

**Patch sites:** `patch_sites check` passes, and `report` for each old and new module is unchanged by this job (no
`setattr` target changes).

**Register:** not reached.

**Tests:** `test_layers`, and every test file the job edits, each as its own process; then the whole suite.

**Stop and ask:**
- A read the guard names cannot be retargeted without changing what the test proves (it reads the old module's
  namespace on purpose).
- A reader under `tracker/` or `tools/` turns up that an earlier job missed: retarget it, and say which job missed it
  in the report.

**Accept when:**
- The guard fails at P4.12's head with exactly the sites before.txt lists, and passes after.
- The collected tests are the same before and after, plus the one guard.
- `tests/golden/` is unchanged; `ADMISSION_PIN[6]` is unchanged.
- **Windows:** no label.
- **Office `-Tests`:** none of its own.

---

## 5. Risks

- **A stand-in that silently stops reaching its target** (A-4). A split moves code out of the namespace the stand-in
  is set on. Most misses are loud: the stand-in's test then reads the real function, and a test that forges a fault
  sees none. Some are silent: a stand-in that only makes a test faster, or that guards against a real side effect
  (a stand-in on `sha256_of` that keeps a test off a slow path), passes either way. The nets are section 3's rule and
  section 4.0's table, `patch_sites report` before and after with its `unread` count, and the hand-read list for what
  the tool cannot follow (string targets, a helper that takes `monkeypatch`, the string programs). P4.12's string
  programs in test_content_check and test_resident are the sharpest case: `ocr.run_in_child = heard` set on a module
  that no longer holds the function would add an attribute nobody reads, and the test would count nothing. P4.12
  names each one; P4.13 sweeps the rest.
- **The spawned child is found by its qualified name** (P4.12). `_the_child` is pickled as
  `tracker.reader_child._the_child`; the spawned process imports that module. In the source tree the suite's real-child
  tests prove it. In the frozen app it depends on PyInstaller collecting `reader_child`, which it does by following
  static imports (R4.12.15); the office's installer build and the hands-on pass are the proof, and the suite cannot
  give it.
- **The judgment's shapes cross the pipe pickled** (P4.11). `Judgment`, `Extraction` and their parts are pickled under
  `tracker.verdicts.*` after the move. Both ends always run the same build, so nothing breaks; but a child left alive
  by an older build could not unpickle a newer job. That cannot happen: a child never outlives its pass (decision 150,
  the job object and the lifeline), and an upgrade replaces the program between passes. No class name is stored on
  disk (R4.11.6).
- **The two L-sized jobs** (P4.4, about 800 lines and 21 tests; P4.9, about 1,380 lines and 94 tests). Each moves
  more stand-ins than any other job and splits the largest share of test_filer. The risk is a test left behind that
  reads a name the filer no longer holds, which fails loudly, or a stand-in left on `filer` alone, which section 4.0's
  rows name. Each is one session; if either cannot finish in one, it stops at a commit that passes the gate and the
  orchestrator splits the rest into a follow-up job with the same requirements, never a half-moved module.
- **Logger names kept** (section 2.1). The carved modules log as `tracker.filer` and `reader_child` as `tracker.ocr`,
  so the run log and the error log read exactly as before. A reader of the code who expects `__name__` will be
  surprised; each module's docstring says why, and renaming them later is a decision row.
- **The error log's places keep their words** (P4.12). `errors.keep("ocr: the reading child", ...)` and its kin stay
  as written although the code now lives in `reader_child`. They are the firm's words, which a person reads
  (decision 193).
- **The office backtest baseline is not recorded** (`docs/backtest-baseline.json`: `agreement: null`). Three jobs move
  routing code (P4.10, P4.11, P4.12) with nothing to hold them to but the suite, the golden recordings and the vocabulary
  report. Section 6's before-and-after run on the office's own documents is the net, and it is owed before phase 4
  reaches `main`, whatever Jason answers to Q1.
- **Q-B is carried, not answered.** `_settle` (P4.3) keeps the re-send road's across park as it is (no shortlist,
  none of the home's evidence, no name evidence on the wanting return, the household's first own return) as a named
  parameter, and A-3's table test pins both
  roads' rows, including where each lands. A later answer changes the re-send road's call to `_settle` and is a
  decision row, never this phase's.
- **The fold and a re-send held across households** (P4.3; review 1, S1). A loose re-send whose bytes a fed return in
  another household holds parks in two different returns today: across, in the dropping household; vetoed or
  unrouted, in the return that holds the bytes. A fold that took one `home` would move one of them, which is routing
  behaviour. R4.3.2 keeps both (the other parks' return comes from `_the_home` over the one pair, the across return
  from the Q-B pair), and R4.3.1's cases 6 and 7 hold it.
- **Found, not built: the backtest's docstring.** `tools/backtest.py`'s `route_corpus` docstring (231) says "with
  ``ocr=True`` there is no reading child". Measured at `68b9212`, `route_file` with no reading handed in calls
  `read_once`, then `judge_bounded`, then `run_in_child`, which with no session open starts a session of its own for
  each document (and `docs/tools.md` 165 says each document "pays the engine's load", which agrees). The office
  `--ocr` run therefore does reach the reading child, which is why section 6 uses it for P4.12. The sentence is prose
  in a tool and is not edited here; it goes to the carry list.

## 6. Owed to the office PC

Everything here runs on the office PC, against the firm's own redacted documents, with the program's checkout
(never the installed app's data). No generative AI reads a document: the backtest and the corpus test are
deterministic, and their reports hold counts, catalog identifiers and row numbers only (`docs/tools.md`). Every
report is written outside the repository. `<corpus>` is the folder holding the firm's sorted documents and their
`expectations.csv`; `<out>` is a folder outside the checkout.

**1. The office backtest on the build before phase 4** (the branch at `68b9212`). Run once, before the phase 4 stack
merges to `main`. It may run at any time before that, and running it before P4.10 is built costs nothing.

In PowerShell, as the office's other checks run (`pilot\wintest\run_checks.ps1`):

```
git checkout 68b9212
python tools/backtest.py run "<corpus>" --out "<out>\before-plain.json"
python tools/backtest.py run "<corpus>" --out "<out>\before-ocr.json" --ocr
$env:TRACKER_REAL_CORPUS = "<corpus>"
python -m pytest -q tests/test_real_corpus.py
Remove-Item Env:TRACKER_REAL_CORPUS
```

(In `cmd` the two variable lines are `set TRACKER_REAL_CORPUS=<corpus>` and `set TRACKER_REAL_CORPUS=`. In
PowerShell, `set` is `Set-Variable` and sets no environment variable, so the corpus test would skip.)

- The plain run hands the router the text layer and routes in this process; it exercises the matcher (P4.10) and the
  judgment's shapes (P4.11). A document with no text layer is counted as no text and not routed.
- The `--ocr` run lets the router read a scan or a photo itself, through the reading child (section 5's last item),
  so it also exercises P4.12.
- `tests/test_real_corpus.py` routes every row of `expectations.csv` and names each by its row; it skips when the
  variable is not set.
- **Recording the baseline is Jason's choice, not this phase's.** If he wants the before-phase-4 number to be the
  baseline every later routing change is held to, `python tools/backtest.py record --report "<out>\before-plain.json"`
  writes `docs/backtest-baseline.json`, committed on its own with its own message, before the phase 4 stack lands.
  Without it, `check` prints that no baseline is recorded and exits 0, which is why step 2 compares the reports
  themselves.

**2. The same on the phase 4 build** (the stack's head after P4.13). Run once, before the merge.

```
git checkout <phase 4 head>
python tools/backtest.py run "<corpus>" --out "<out>\after-plain.json"
python tools/backtest.py run "<corpus>" --out "<out>\after-ocr.json" --ocr
python tools/backtest.py check --report "<out>\after-plain.json"
$env:TRACKER_REAL_CORPUS = "<corpus>"
python -m pytest -q tests/test_real_corpus.py
Remove-Item Env:TRACKER_REAL_CORPUS
```

- **Pass:** each after-report equals its before-report in everything but the time each document took. This compares
  them (it prints nothing and exits 0 when they agree):

  ```
  python -c "import json,sys; a,b=(json.load(open(p,encoding='utf-8')) for p in sys.argv[1:]); [d.pop('timing',None) for d in (a,b)]; sys.exit(a!=b)" "<out>\before-plain.json" "<out>\after-plain.json"
  ```

  and the same for the two `-ocr` reports. The agreement, the parked and no-text counts, every catalog's per-row
  table and every confusion are then the same. `check` exits 0 (at or above a recorded baseline, or none recorded).
  `tests/test_real_corpus.py` passes as it did before.
- **Fail:** any difference is a stop: the stack does not merge, and the orchestrator finds the job by running the
  plain run (for a difference there) or the `--ocr` run (for one only there) at P4.10's, P4.11's and P4.12's heads.

**3. The Windows check of the stack.** Once, on the stack's head, before the merge: `pilot\wintest\run_checks.ps1`
with no `-Tests` (the whole suite, the installer build and the silent install), because the phase reaches the engine
(section 3, Windows). The jobs that carry the `windows` label (P4.4, P4.6, P4.9, P4.12) also give their own `-Tests` lists
and, for P4.12, hands-on steps; if the stack is checked as one, the whole-suite run covers those lists and P4.12's
hands-on steps run once on the installed build.

**4. Mac.** Nothing in phase 4 changes a Mac path. The memory watch's `_darwin_footprint` moves byte for byte with
P4.12; the Mac check's next scheduled run covers it, and no Mac run is owed by this phase.

**Still owed from earlier phases:** P3.8's read-only `verify` against the office's records, before the branch reaches
`main` (`pilot/SPEC-architecture-p3.md` section 6). It does not touch this phase and can run in the same visit.

## 7. Questions for Jason

**Q1. May phase 4 be built on the branch now, with the office backtest run before it merges to `main`?**
The plan said phase 4 needs the office's backtest baseline first, because three of its jobs move code the router uses
to decide where a document goes (the keyword matching, the shape of a reading's verdict, and the separate process a
scan is read in). None of them changes what that code does.
- **(A) Build now (recommended).** The jobs are built and reviewed on the branch. Before the branch merges, the office
  PC runs the backtest twice on the firm's own documents, once on the program as it is today and once after phase 4
  (section 6), and the two results must match exactly. Nothing reaches the firm's machines until they do.
- **(B) Wait.** Nothing in phase 4 is built until the office has run the backtest and recorded its number.
- Either way you may choose to record today's number as the firm's baseline (section 6, step 1), so every later change
  to routing is held to it.

**Q2. Do the modules that do the work of a standing rule count as upholding it, or only the ones that decide?**
The map records, for each standing rule, which modules uphold it. Today "Originals are never altered" names only the
filer. Phase 4 moves the byte-for-byte copy and the rename-only move into `copies.py`, and the record of each intended
move into `intents.py`.
- **(A) The modules that do the work join (the SPEC's default).** `copies` and `intents` are listed with the filer
  (R4.4.8, R4.6.8). `keywords` (the deterministic rules) is not listed under "No generative AI ever reads a client
  financial document", because what reads a document is `content_check` and the file checks (R4.10.13).
- **(B) Only the deciders.** The filer alone stays listed; `copies` and `intents` are not added.
- **(C) The work and the rules.** As (A), and `keywords` also joins the no-AI rule, because it is where every
  deterministic rule is now evaluated.

**Carried, not asked again:** Q-B (the re-send road's empty shortlist for a document across households) stays open as
P313 left it. Phase 4 keeps today's behaviour as a named parameter in `_settle` (P4.3): a document sent again, whose
earlier copy another household's return holds, still waits at home with no shortlist. Your answer, when you give it,
changes one visible place: the call that settles a document sent again.
