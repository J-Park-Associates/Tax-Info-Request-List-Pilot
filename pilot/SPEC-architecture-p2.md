# SPEC-architecture phase 2: types and shared low layers

Written by the SPEC writer and measured at `286b535` (the phase's base). Every line number below is at that commit.
It had three review rounds (PROMPT-refactor section 1.1): review 1 and review 2, then a check of review 2's fixes. The
orchestrator settled the check's two findings on 2026-10-14: S34 by option (a), the parser's one named ignore in
R2.1.1, and S35 by naming the hold's import members in R2.13.3.

Round 2: revised against SPEC review 1 (`ORCH/jobs/P2/review-1.md`, S1-S19) and the orchestrator's answer to its
question (`ORCH/board/threads/P2/003`): B-6 reduced is accepted, and B-10 is carried.

Round 3: revised against SPEC review 2 (`ORCH/jobs/P2/review-2.md`, S20-S33) and the orchestrator's settlement
(`ORCH/board/threads/P2/006`): S28 takes option (b), so P2.13 re-pins the store's and the manifest's load sets and
writes decision row P317, and P2.14's row becomes P318.

## 1. The answer

Phase 2 moves code that is in the wrong layer down to where its imports belong, and writes down two contracts that
until now existed only in the code. Nothing a person sees and nothing a pass does changes.

- Five new flat modules:
  - `replies.py`: the shape of every reply, as `TypedDict`s.
  - `bounds.py`: the record's value bounds.
  - `hold.py`: the per-reply memo.
  - `errlog.py`: the error log.
  - `index.py`: the index reader and the decision words.
- `tools/corpus.py` holds the corpus harness.
- The API's failure envelope is built by one function, and the screen's failure kinds are pinned to the engine's list.
- The field rules get one home each, the Open allow-lists move into `reasons.py`, and both of the firm's pages are drawn
  by one `page.document`.
- The scanner stops importing the filer, so the filer–scanner cycle becomes one-way (Q-A, as P313 says). CLAUDE.md's
  cycle sentence is corrected to name the three call-time cycles that remain.
- The journal's event families get `TypedDict`s past the admission.
- The layer table gains a domain column.

Each move leaves a re-export behind it, and the last two jobs remove those re-exports along with decision 100's old shim.

These constants are unchanged: `SCHEMA_VERSION`, `ADMISSION_VERSION`, every golden recording, the catalog, the matcher,
the router, the vocabulary report's counts and hits (one sentence of it names the cases' new home) and the backtest
baseline.

## 2. What it relies on

**Decision rows:**
- 95 and 99: the curated cycle, and `__init__` importing nothing.
- 100: the shim this phase retires.
- 101: the store is narrow, and must not import settings at load time.
- 128: names, people and spellings.
- 137 and 188: the layout's name rule, which records re-exports.
- 186: the data home and `store_path`.
- 187: one value rule for the editor and the gate.
- 190: Open is an allow-list that fails closed.
- 193: one envelope, one error log.
- 209 R3b: the admission version.
- P118, P207 and P215: one reading, one household, `held`.
- P249: `settings.host_system` is the Mac seam.
- P288 to P307: the typed rules and the stored rules.
- P310: mypy, dev-only.
- P312: the loop.
- P313: Q-A built as one-way, and every answer keeps behaviour.

**Landed jobs:**
- J1: `ADMISSION_PIN` follows the closure, and `names_bound_in` (B-2).
- J3: `tests/node_harness.py` (`stripped_js`, `read`, the script lists).
- J4: `tools/patch_sites.py` and `tests/golden/`.
- J5: the state register in `tracker/resident.py`.
- J6: `tools/typecheck.py` and `docs/typecheck-baseline.json`, which holds 227 errors in 29 files.

**SPEC-architecture:**
- section 5.1: flat modules, a move is a move, facades;
- section 5.3: the new modules' layers;
- section 6: behaviour does not change;
- section 9: phase 2's paragraph.

### 2.1 Where this SPEC departs from section 9's paragraph, and why

| Item | What section 9 asks | What this SPEC does | Why |
|---|---|---|---|
| **B-6, reduced** (accepted, `threads/P2/003`) | `settings.store_file()`, with `store.store_path = settings.store_file` kept as the public name | `store_path` stays the rule's home. `settings._inside` becomes the public `settings.inside`. The error log asks `store.store_path()` from `errlog.py` at call time, so settings no longer imports store and the settings↔store cycle is gone. | `store.store_path = settings.store_file` needs a load-time import of settings in store. Decision 101 and `tests/test_layers.py:337` (`load["store"] == {"checkpoint", "ledger", "locking", "records"}`) forbid that, and `store_path`'s docstring (store.py:785-788) gives the reason. Moving `ENV_STORE` and its three sentences into settings would rename 140 test references for no behaviour, and those constants are not settings'. P2.7 records the reduction as a decision row. |
| **B-10, not built in phase 2** | `settings.host_system()` answers `"darwin"` from `layout.on_a_mac()` | Not built. The suite pins the two seams independently. It carries forward to the orchestrator's carry list. | In `tests/conftest.py`, `room_is_the_absolute_length` (242-257, autouse) pins `layout.on_a_mac` off for every test. `stand_on_the_floor` (348-358) and `a_mac` drive `settings.host_system`, and `REAL_HOST_SYSTEM` (294) is captured from it. Joining the two seams would make `stand_on_the_floor`'s guard (`settings.host_system() == "darwin"`, 352) read the pinned room seam. On a real Mac it would then skip pinning `locking._on_a_mac`, `fsio._on_a_mac` and `locking.platform`. It would also make `test_tripwire.py:122`'s Mac branch dead, and make the five tests that take the `on_a_mac` fixture see a Mac host as well: test_filer 6841 and 6891, test_layout 743 and 788, test_validators 100. All of that changes what the suite checks on a Mac, and only a Mac can show it (`pilot/mactest`). It needs a ruling on which seam a Mac-room test means. Carried to the orchestrator's carry list; built in the first phase that owes a Mac check (orchestrator's answer, `threads/P2/003`). The four probes stay as they are until then. |
| **bounds, reduced** | Section 5.3: bounds takes records 1444-2172 | Records 1427-1985 move to bounds. The row checks, 1988-2172, stay in records (R2.4.2). | The row checks read record shapes (`DATE_FIELDS`, `RULE_LIST_FIELDS`, `RULE_FLAG_FIELDS`, `word_list_problem`, `format_waits_for`, `parse_waits_for`), which cannot go down to L0 with the bounds. |
| **C-4's handler annotations** | The audit's seam: annotate the `_cmd_*` returns with the reply types | Not built. The reply types describe what `api.main` prints, `warnings` included, and the suite holds the recordings to them (R2.3.1, R2.3.2). | `api.main` adds `warnings` after the handler returns (api.py 6828), so no handler returns a reply type. The handlers and the helpers that build their replies are typed `-> dict`. Annotating them needs a `...Body` type per reply and typed helpers, which is the thin door's work (phase 5, SPEC-architecture 5.1 (5)), not a move's. |
| **B-3 (c) and (d)** | — | Not built. | Section 9's phase 2 paragraph names only (a), (b) and the length (e). (c) changes which sentence a blank-versus-bad identifier gets, which is a behaviour change. (d) is Q-F, which P313 answers as "only if no save could come out differently". It belongs to the phase that takes A-1's filer split. |
| **C-7 names** | The audit proposes `OPENS_CODES` | The two sets keep their names, `READ_AND_PARKED_CODES` and `NO_OPEN_CODES`. | A rename is a change that buys nothing, and seven test references keep working through api's import. |
| **E-9's `tests/cases.py`** | A new `tests/cases.py` | Built as `tests/routing_cases.py`. | J2 already made `tests/routing_cases.py` the suite's data module for routing cases (`EXPECT`, `XLSX_CASES`). A second data module would split one table's home in two. |

### 2.2 Carried-forward items (`ORCH/carry-forward.md`)

- **`monkeypatch.setitem` is outside patch_sites.** Taken: every move job greps `setitem(` for each container it moves
  (R2.k "setitem check" below). At `286b535` the only `setitem` targets are `reasons.SHORT_REASONS` (test_api 9781),
  `api.COMMANDS` and `sys.modules`. Phase 2 moves none of them.
- **Review 6's four patch_sites limits (F6.1-F6.4).** Taken as a hand check. Each move job's patch-site list is the
  tool's report plus a grep for the moved names in `tests/` (string-form `setattr("tracker.x.y", ...)`, a bare
  `import children`-style helper, a store through a parameter). The builder reads every hit that the tool did not list.
  Tightening the tool is not phase 2's (ruling 018 and Jason's "land as it is").
- **The register derivation's blind spots** (an alias of a module-level container, a mutating method outside the list,
  a nested function's shadowing). Taken in P2.6, the one job that moves module state (`_HELD`, `_HOLDING`). The builder
  reads `hold.py` by hand for the three and reports that none occurs. No other job adds or moves module state.
- **The mypy upgrade rule** (a decision row before an upgrade that counts more errors). Not reached: phase 2 upgrades
  no tool. The row stays owed before the first upgrade.
- J6's other notes (`platform = "linux"`, gate.yml's pip cache key, "1 files", PS 5.1 long paths) are not this phase's.
  Phase 2 touches none of them.

## 3. Rules every job follows

**The gate.** Each job runs it before its report, under PY311 (the floor) and PY314 (the office's):
- dead code deleted in the changed files first: unused imports and locals, commented-out code, a module-level name
  nothing uses;
- then the job's named tests;
- then `python -m ruff check .`;
- then `python tools/repo_map.py check`;
- then `python tools/typecheck.py check`;
- then `python tools/patch_sites.py check`.

**The map, the docs and the decision rows:**
- Run `python tools/repo_map.py update` in the same commit as the code, after any edit to `docs/repo-map.curated.json`.
- A new module gets:
  - a curated node (role, and notes that carry the reasoning, as its neighbours' do);
  - a row in `tests/test_layers.py`'s `LAYERS` and (from P2.2) `DOMAINS`;
  - a line under its layer in `docs/architecture.md` (whose module count, "thirty-eight", goes up by one per new module);
  - its own `tests/test_<module>.py`.
- The next free decision row is **P314** in `pilot/DECISIONS.md`. The rows this SPEC adds are numbered in landing order
  (P314 in P2.2, P315 in P2.7, P316 in P2.10, P317 in P2.13, P318 in P2.14). A job that lands out of order takes the
  next free number and says so.
- **The suite spells the settings module three ways:** `settings`, `settings_module` (13 imports, in test_after_install,
  test_api, test_page_rows, test_scheduling and test_shell) and `data_rules` (`tests/test_settings.py:15`). Every grep
  in this SPEC that looks for a settings name in `tests/` is written with `grep -E` over all three,
  `\b(settings|settings_module|data_rules)\.`, and every list of test lines below was measured that way.

**A move is a move:**
- Code moves byte for byte, with its comments and its words.
- The old module re-exports the public names that moved, with `# noqa: F401 - re-exported until P2.13` (or P2.14).
- An identity test pins each re-export: `getattr(old, name) is getattr(new, name)`.
- The re-export never covers a name rebound by `global` (a from-import copy would go stale). Such a name is read
  through the module (`hold._HELD`).

**The admission.**
- A job that moves or edits a function in the admission closure re-pins it. The closure is everything
  `tests/test_store.py::admission_closure()` (3876) reaches from `store._refuse_a_malformed_line` and
  `store._line_keys_problem`.
- Re-pinning means pasting `admission_digests()` under `ADMISSION_PIN[5]` (test_store.py 3592-3834).
  `store.ADMISSION_VERSION` stays 5 (store.py:333).
- Keys are `f"{function.__module__}.{qualname}"` for a function, and `f"{reading function's module}.{name}"` for a
  constant read by bare name. So a moved function's key and its constants' keys follow the module.
- If any moved part's source would change beyond its module key (a body, an annotation), stop and ask. The exceptions
  are the edits this SPEC names (P2.1 R2.1.2, P2.5 R2.5.1 and P2.13 R2.13.1).

**What "Test minimally" means here** (CLAUDE.md):
- A job runs:
  - each changed module's own test file;
  - each changed test file;
  - the guards `test_layers`, `test_single_source` and `test_repo_map`;
  - `test_tripwire` and `test_errors` when tests or error wording change;
  - `test_golden` for every move;
  - `test_typecheck` when the baseline changes;
  - `test_patch_sites` never (the tool is unchanged).
- Importers' test files are named per job. Two rules decide them:
  - An **additive** change (a new name, nothing existing changed) does not reach importers.
  - A **move behind an identity-pinned re-export** reaches only the importers whose own tests drive the moved code;
    they are named.
- No job reaches the sorting engine (router, filer's sorting, scanner, manifest's rules, catalog, matcher), so no job
  names the whole suite.
- A job that edits filer.py only to move definitions out and import them back runs `test_filer` as filer's own test
  file. That is not "reaching the engine".

**No routing change.** No job edits `tracker/router.py`, the catalog (`tracker/templates.py`'s rows) or the matcher.
P2.12 moves test-side case tables and the corpus harness. The vocabulary report is rebuilt only because its input
paths change and its one sentence naming where the cases live follows them (R2.12.4); every count and hit in it must
stay as it is.

**Golden.** `tests/golden/` is never re-recorded. Each move job's accept-when includes:
"`pytest tests/test_golden.py` passes and every recording in `tests/golden/` is unchanged".

## 4. The jobs, in landing order

| Job | Title | Cost | Tier | Depends on |
|---|---|---|---|---|
| P2.1 | Type burn-down in the code that moves | S | Opus (b) | — |
| P2.2 | A domain column in the layer table | S | Sonnet | P2.1 |
| P2.3 | `replies.py`, one envelope builder, the failure kinds pinned | M | Opus (a, c) | P2.2 |
| P2.4 | `bounds.py`: the value bounds out of records | M | Opus (b) | P2.3 |
| P2.5 | One file-name-part rule, the typed people rule in records | M | Opus (b) | P2.4 |
| P2.6 | `hold.py`: the per-reply memo out of settings | M | Opus (e) | P2.5 |
| P2.7 | `errlog.py`, and `settings.inside` | M | Sonnet | P2.6 |
| P2.8 | `PAGE_BREAK` into records, the Open lists into reasons, `page.document` | M | Opus (a) | P2.7 |
| P2.9 | `index.py` out of filer, re-exported | M | Opus (a) | P2.8 |
| P2.10 | The index's readers import it; the scanner never imports filer | M | Sonnet | P2.9 |
| P2.11 | Event `TypedDict`s past the admission | M | Opus (b) | P2.10 |
| P2.12 | `tools/corpus.py`, the case tables into `tests/routing_cases.py` | M | Sonnet | P2.11 |
| P2.13 | Facades removed: bounds, hold, the spelling sentence | M | Opus (b) | P2.12 |
| P2.14 | Facades removed: the index, and decision 100's shim (A-12) | M | Opus (a) | P2.13 |

The jobs land in order. P2.2 to P2.8 touch different files and could in principle be built in parallel, but each
re-pins or edits `tests/test_layers.py`, `docs/repo-map.*` and `docs/architecture.md`. Building them in order keeps those
three files free of conflicts.

---

### P2.1 Type burn-down in the code that moves

- **Cost:** S.
- **Tier:** Opus, by rule (b). It edits `records._is_number`, which is in the admission closure.
- **Findings:** section 9 ("every phase starts by burning down the type errors in the modules it will move").
- **Depends on:** nothing.

The modules phase 2 moves code out of, and their errors in `docs/typecheck-baseline.json`:

| Module | Errors | In the code that moves |
|---|---|---|
| records | 8 | all 8 |
| settings | 2 | 413 is in the error-log region; 1002 stays in settings |
| filer | 51 | none in the index closure (P2.9's list) |
| api | 24 | none in `_failure_of`/`say_failure` (557-629), the Open lists (861-920) or `_people_from_spec` (2296-2337) |
| content_check | 9 | none at `PAGE_BREAK` (168) |
| runner | 4 | none in the status page's lines (2808-2850) |
| view | 0 | — |
| tools/backtest | 0 | — |

So this job burns down records' 8 and settings' 2. The two tool errors that P2.12's files carry (reader_bench 245,
vocab_report 317) are P2.12's, because that job edits those lines' files. No other move job carries a baseline entry. If
one finds that it does, it moves the entry with `update` in its own commit.

**Requirements:**

- **R2.1.1** — records.py:74, `import re._parser as _re_parser`, is mypy's one error in records outside `_is_number`'s
  callers (`[import-not-found]`: typeshed does not stub the private parser). It is excused by name, **one named
  ignore that is not a platform line** (the orchestrator's settlement of review 3, S34, option (a)):
  - **Why not the other forms.** Loading the parser through `importlib` fails decision 190's two guards in
    `tests/test_layers.py` (`test_nothing_under_tracker_imports_by_string`, 533-544, and
    `test_every_import_under_tracker_is_allowed`, 445). A mypy override changes `[tool.mypy]`, which J6 pinned, and
    breaks `test_every_third_party_package_the_checked_code_imports_is_read_as_untyped` (304-319). Reading
    `sys.modules["re._parser"]` leans on `re`'s own imports. `ALLOWED_STDLIB` is not widened.
  - **The change.** Line 74 keeps its import and gains the ignore and its reason, exactly:

    ```python
    import re._parser as _re_parser  # type: ignore[import-not-found]  # typeshed does not stub the private parser
    ```

    (110 characters; ruff's limit is 120.)
  - **The guard.** `tests/test_typecheck.py::test_every_ignore_in_the_checked_code_is_narrow` (320-336) excuses
    that one line by file and wording, and keeps its platform count:
    - above the test, a module-level constant with its comment:

      ```python
      # The one excuse that is not a platform line (P2.1): the standard library's
      # private regular-expression parser, which the value rule reads (decision
      # 187) and typeshed does not stub. It is named by file and wording, so a
      # second such line fails here rather than passing as this one.
      UNSTUBBED = (("records.py", "# type: ignore[import-not-found]  # typeshed does not stub the private parser"),)
      ```

    - the docstring's sentence "R6.2: a platform line the checker cannot read on Linux is excused by its own error
      code, never by a whole file." gains ", never by a whole file; the one other line is excused by name
      (UNSTUBBED)." in place of ", never by a whole file.";
    - the loop collects `unstubbed = []`. A `type: ignore` comment whose `(path.name, comment)` is in `UNSTUBBED`
      is appended to it and skipped. Every other one must match `narrow` and counts toward `excused`, as now;
    - after the loop, `assert excused == 9` stays, and `assert sorted(unstubbed) == sorted(UNSTUBBED)` is added.
      So a second copy of the line fails, the same wording in another file fails `narrow`, and a stale entry fails.
  - **Measured by the orchestrator** in a copy of `286b535` with R2.1.1, R2.1.2 and R2.1.6 applied:
    - `mypy tracker/records.py` reports no issues;
    - `typecheck.py check` reads 219 errors in 28 files ("8 fewer than it records"), before R2.1.3-R2.1.4;
    - `tests/test_typecheck.py`, `tests/test_layers.py` (both decision-190 guards included) and test_records 216 pass
      under PY311 and PY314;
    - ruff passes;
    - test_store's admission test names only `tracker.records._is_number` as moved.
  - **The pin.** `_re_parser` is not a `tracker` module, so `admission_closure()` keys none of its reads. A comment
    on an import line is no function's source, so this requirement moves no `ADMISSION_PIN[5]` entry.
- **R2.1.2** — records.py:1691, `def _is_number(value: object) -> bool:` (anchor on the name; its body is 1692). Its
  return annotation becomes `TypeGuard[int | float]`, imported from `typing`. The body is unchanged. That clears the
  errors its callers carry: records 1698 (2 errors) and 1699 (2) in `count_problem`, and 1706 (3) in `number_problem`.
  With 74's one (R2.1.1) that is records' 8. `_is_number` is in the admission closure, so re-pin `ADMISSION_PIN[5]`. Its digest changes for
  this annotation, and only for it.
- **R2.1.3** — settings.py:413, inside `_ErrorLog.handleError`. Pass `cast(BaseException, sys.exc_info()[1])` to
  `errors.error_class`, with a comment: `handleError` runs only inside `emit`'s `except`, so there is an exception.
  `errors.py` is not touched; its own two errors (140, 142) are not in moving code.
- **R2.1.4** — settings.py:1002, `_redirected_package`. Return `cast("str | None", _redirect_answer)`. The `object`
  sentinel `_UNASKED` and the register key `("settings", "_redirect_answer")` are unchanged.
- **R2.1.5** — `python tools/typecheck.py update` lowers the baseline by exactly 10 (records 8, settings 2). It then
  reads 217 errors in 27 files. `check` passes.
- **R2.1.6** — records' standard-library import pin follows R2.1.2. `tests/test_records.py`
  `test_nothing_here_reaches_a_file_or_a_workbook` (216-234) asserts records' import lines exactly, so (measured: it
  fails on the change without this):
  - the set at 231-232 becomes `{"__future__", "datetime", "dataclasses", "json", "math", "pathlib", "re",
    "re._parser", "typing", "tracker.layout"}` (`"typing"` joins; `"re._parser"` stays);
  - the docstring's sentence "`math` and `re._parser` are the value rule's (decision 187): a count is finite, and a
    Date Pattern's shape is read off the standard library's own parser rather than a second engine." becomes "`math`,
    `re._parser` and `typing` are the value rule's (decision 187): a count is finite, a Date Pattern's shape is read off
    the standard library's own parser rather than a second engine, and `typing` says what `_is_number` proves (P2.1)."

**Pin-move list:**
- `ADMISSION_PIN[5]`: the digest of `tracker.records._is_number` (and no other key);
- `tests/test_records.py` 216-234, records' import set and its docstring (R2.1.6);
- `tests/test_typecheck.py` 320-336: `UNSTUBBED` and the guard's loop and last assert (R2.1.1). Its platform count
  stays 9.

**Patch sites:**
- `tracker.records`: 2 stand-ins. `test_content_check.py:2378` (`date_pattern_problem`) and `test_row_columns.py:561`
  (`RULE_FIELDS`). Neither is touched.
- `tracker.settings`: 57 stand-ins, none on `handleError` or `_redirected_package`. `test_settings.py:540` stands in for
  `_redirect_answer` (the register-reset path), and its behaviour is unchanged.

**Tests:**
- `test_records`, `test_settings`, `test_store` (the pin), `test_typecheck`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

**Accept when:**
- the gate passes;
- the baseline is lower by 10 and `check` passes;
- `grep -rn "type: ignore" tracker/records.py` finds line 74 alone, with R2.1.1's exact wording.
  `test_every_ignore_in_the_checked_code_is_narrow` passes with `excused == 9` and `unstubbed` equal to `UNSTUBBED`;
- test_layers' two decision-190 guards pass (`test_nothing_under_tracker_imports_by_string` and
  `test_every_import_under_tracker_is_allowed`), and nothing under tracker/ imports `importlib`;
- `ADMISSION_PIN[5]` differs from HEAD in that one digest;
- nothing else changes.

---

### P2.2 A domain column in the layer table

- **Cost:** S.
- **Tier:** Sonnet. It is a test table and a test.
- **Findings:** SPEC-architecture 5.1 (2).
- **Depends on:** P2.1.

**Requirements:**

- **R2.2.1** — `tests/test_layers.py`: after `LAYERS` (127-158), add
  `DOMAINS: dict[str, frozenset[str]]` with exactly these six keys and members (every module in `LAYERS` today):
  - `record`: `__init__`, ledger, locking, checkpoint, fsio, layout, door, settings, records, store, manifest,
    households, templates, scaffold.
    `door.py` is the module that knows which household a path is in (decision 188), so it belongs to the record's
    domain, not to the API door.
  - `reading`: validators, containers, content_check, ocr.
  - `sorting`: reasons, router, names, filer, scanner, review.
  - `pass`: progress, registry, rollover, reminder, runner, scheduling, after_install.
  - `door`: errors, api, resident.
  - `shell`: page, page_rows, firm_cache, firm_pages, view.
- **R2.2.2** — a test, `test_every_module_sits_in_exactly_one_domain`, asserts three things:
  - the keys are exactly the six;
  - the domains are pairwise disjoint;
  - their union equals `set(LAYER_OF)`.

  A module in `LAYERS` with no domain fails, and so does one in a domain with no layer.
- **R2.2.3** — the module docstring of test_layers says what a domain is: the grouping a folder tree would show, checked
  here instead (5.1 (3)). Each later job that adds a module adds it to both tables. It also carries this sentence, so
  that the shared name is not misread: "The `door` domain is the API's door; `tracker/door.py` is the record's."
- **R2.2.4** — decision row **P314**: the layer table carries a domain column, listing six domains. A domain is
  documentation that is checked: it forbids nothing that the layers allow. No module changes layer in this job.

**Pin-move list:** none.

**Patch sites:** none (no code moves).

**Tests:** `test_layers`, `test_single_source`, `test_repo_map`.

**Accept when:**
- the gate passes;
- the new test fails if one module is removed from `DOMAINS` (shown once by hand in the report, then restored).

---

### P2.3 `replies.py`, one envelope builder, the failure kinds pinned

- **Cost:** M.
- **Tier:** Opus, by rules (a) and (c). It moves the envelope's construction in api, and it builds a guard that parses
  JavaScript.
- **Findings:** C-4.
- **Depends on:** P2.2.

**Requirements:**

- **R2.3.1** — new `tracker/replies.py`, at L0 in the `door` domain. It imports only `typing`. It holds:
  - `Failure`: `sentence: str`, `kind: str`, `seq: int | None`, `identifier: str | None`, plus
    `lock: NotRequired[dict | None]` and `key: NotRequired[str]`.
  - `Envelope`: `error: str`, `failure: Failure`, `warnings: list[str]`.
  - One top-level `TypedDict` per recorded success reply: `AssignReply`, `CreateReply`, `EditHouseholdReply`,
    `EditReply`, `FirmLastReply`, `FirmReply`, `ListReply`, `ReminderReply`, `StateReply`.
    - **What they describe:** the reply as `api.main` prints it, which is what the screen reads. `main` adds
      `warnings` after the handler returns (api.py 6828), so every one of them has `warnings: list[str]`.
    - Their top-level keys are those of `tests/golden/replies.<command>.keys.json`. A key the recording holds only
      sometimes (the builder reads `api._cmd_*` to decide) is `NotRequired`.
    - Value types are as precise as the recording shows (`str`, `bool`, `int`, a nested `TypedDict` only where one
      already exists, otherwise `dict`/`list`/`object`).
  - A module docstring that says three things:
    - why it exists: one written contract the stub, the recordings and the JavaScript are held to (5.1 (6));
    - why `TypedDict` and not dataclasses: the replies are JSON objects the screen reads by key;
    - that the types describe `main`'s output and the suite holds the recordings to them. The `_cmd_*` handlers keep
      `-> dict`: no handler returns `warnings`, and typing the handlers is the thin door's work (section 2.1).
- **R2.3.2** — `tests/test_replies.py`:
  - For each of the nine commands, the recorded top-level keys satisfy
    `__required_keys__ <= recorded <= __required_keys__ | __optional_keys__`.
  - The keys of `progress.failure_reply("s", kind)["failure"]`, for each `kind` in `progress.FAILURE_KINDS`, satisfy
    the same against `Failure`. The `Envelope` keys equal `failure_reply`'s top-level keys.
  - It reads the recordings and calls no command, so it runs in well under a second.
- **R2.3.3** — api.py:557-629. Rename `_failure_of`'s body to `_envelope_of(exc: BaseException) -> Envelope`:
  - The same body, up to and including the `progress.failure_reply(...)` call at **604**. That call now also passes
    `warnings=_WARNINGS`, and the function returns the reply whole, through a `cast` (review 2, S21):

    ```python
    # progress builds the envelope and is typed -> dict; P2.3 does not retype it.
    return cast(Envelope, progress.failure_reply(sentence, kind, seq=seq, identifier=identifier,
                                                 warnings=_WARNINGS, **extra))
    ```

    Without the `cast`, mypy reports `Incompatible return value type (got "dict[Any, Any]", expected "Envelope")
    [return-value]` at that line, and api's count rises above its baseline of 24 (measured at `286b535`). With it,
    api's count is unchanged. Annotating `progress.failure_reply -> Envelope` instead was rejected: progress (L3) would
    import replies, a larger change to a module this job does not otherwise touch.
  - api's imports gain `from typing import cast` (standard library) and `from tracker.replies import Envelope,
    Failure`, each in ruff's order (`tracker.replies` sorts after `tracker.registry`, before `tracker.rollover`).
  - `_failure_of(exc) -> Failure` becomes `return _envelope_of(exc)["failure"]`. Its other callers keep it unchanged.
    They are api 5538 (`_reminder_said`) and test_api 7325; api 623, inside `say_failure`, is the one this job
    rewrites.
  - `say_failure` (615-629) becomes:
    1. `envelope = _envelope_of(exc)`;
    2. the `kind == "failed"` branch reads `envelope["failure"]["kind"]`, keeping `errors.keep` and `log.error` as they
       are;
    3. `print(json.dumps(envelope))`;
    4. `return 1`.
  - resident.py 324 and 366 call `api.say_failure`, not `_failure_of`. They reach the new body unchanged, and
    test_resident, which this job runs, covers both.

  The bytes printed are identical to today's: `failure_reply` builds `{"error", "failure", "warnings"}` in that order,
  with `error == failure["sentence"]`, and copies the warnings with `list(...)`.

  The warnings are read when the envelope is built, before `errors.keep`/`log.error`, where today they are read at print
  time. A `_warn` reached from inside `_envelope_of` (none at HEAD) would still land before the copy, because the
  copy is the last thing it does. The builder confirms by grep that neither `errors.keep` nor anything logging reaches calls
  `api._warn` or appends to `_WARNINGS`, and says so in the report. If anything does, stop and ask.
- **R2.3.4** — dropped in round 2 (review 1, S9). No `_cmd_*` handler is annotated with a reply type in this phase
  (section 2.1). The numbers below keep their places.
- **R2.3.5** — the failure kinds pinned (C-4's alternative to a vocabulary key, which would change
  `tests/golden/vocab.keys.json`). Add `test_every_failure_kind_the_screen_names_is_the_engines` to
  `tests/test_replies.py`.
  - **What it reads.**
    - Every script in `tests/node_harness.RENDERER_SCRIPTS`, through `node_harness.stripped_js`.
    - `app/main.js`, which `node_harness.read` cannot reach (it reads `app/renderer/` only): read from
      `node_harness.REPO / "app" / "main.js"`, with the comments removed by the same two substitutions
      `stripped_js` makes. The builder may give `stripped_js` a path form for this, provided every existing caller is
      unchanged.
  - **What it collects.** The renderer uses `kind` for many vocabularies that are not failures (sheet kinds, link
    kinds, Open kinds, step kinds), so the collector is scoped to failure contexts. It collects a double-quoted string
    literal only from these five named patterns, and from nothing else:
    1. **`sentence_object`.** The value of a `kind:` property in an object literal whose own top-level keys include
       `sentence` or a `...failure` spread. The object is found by bracket matching that skips strings and template
       literals. The value is read in one of three forms: a literal (`kind: "failed"`), the two arms of a ternary
       (`kind: cls === "err" ? "failed" : "warning"`, never the condition's `"err"`), or the right side of `||`
       (`kind: failure.kind || "failed"`).
    2. **`kind_compared`.** A literal compared (`===`, `!==`, `==`, `!=`, either side) with `failure.kind` or
       `entry.kind`, with any dotted prefix (`err.failure.kind`).
    3. **`local_kind_compared`.** Inside a function whose body assigns `const kind = failure.kind || "..."`, a literal
       compared with the bare local `kind`.
    4. **`kind_default`.** The right side of `failure.kind || "..."`.
    5. **`shell_failure`.** In main.js, the second argument of `shellFailure(...)`, found by bracket matching, when it
       is a literal.
  - **What it asserts.**
    - Every collected literal is in `progress.FAILURE_KINDS` or in a `NOTICE_KINDS` table in the test, which holds
      `{"warning": "a notice the screen raises itself, never a failure (app.js 380, 2542)"}`.
    - **The must-find list.** Every site below is collected by the pattern named, as a list in the test of
      `(file, pattern, literal, anchor)`. The anchor is a short piece of the site's own line, so line drift does not
      break it. A pattern that stops matching fails. Measured at `286b535` with a prototype of these five patterns:
      - `sentence_object`: app.js 202, 380 (both arms), 415, 1807, 2115, 2142, 2499, 2500, 2542 (both arms);
        shell.js 565, 674, 1203, 1511, 1588; pages.js 1705.
      - `kind_compared`: app.js 248, 249, 3424; shell.js 562.
      - `local_kind_compared`: app.js 320.
      - `kind_default`: app.js 304, 334, 2500.
      - `shell_failure`: main.js 444, 464, 467, 507, 555, 586, 604, 934.
    - **The must-not-find list.** These sites are failure-shaped by word but not failures. Each entry is
      `(file, literal, anchor)`, and the test asserts **per literal**: the anchor is still in the source, and that
      literal is not collected from the anchor's line. So the list cannot rot, and a line that also holds a must-find
      literal can be listed (review 2, S29):
      - sheet.js 39 (`"check"`, anchor `sheetNow.kind === "check"`) and 103 (`"moved"`, anchor
        `{ kind: "moved", moved }`);
      - main.js 901 (`"folder"`, anchor `kind === "folder"`) and 907 (`"reveal"`, anchor `kind === "reveal" && !reveal`);
      - main.js 464: `"Error"`, anchor `{ kind: err.name || "Error" }`. That inner object has no `sentence` key, so
        `"Error"` is not collected. The same line's `"refused"`, the call's second argument, **is** collected by
        `shell_failure` and stays on the must-find list above;
      - in the entries that follow, the literal is the one string the anchor quotes:
      - app.js 447 (`classList.toggle("refused"`), 496 (`sheetNow.kind === "reminder"`) and 1644
        (`one.kind === "related"`);
      - pages.js 242 (`{ kind: "file", key, paths: map }`), 246 (`link.kind === "household"`) and 495
        (`spec.step.kind === "edit"`);
      - shell.js 536 (`status !== "failed"`), 673 (`status: "failed"`) and 1133 (`key: "locked"`).
    - The prototype collects nothing outside these two lists but the `"warning"` sites `NOTICE_KINDS` covers (app.js
      392, 1387, 1796, 1907, 2023, 2027, 2128, 2525; pages.js 1618, 1627, 1632; shell.js 1604, 1607). So no exclusion
      table is needed, and none is added. If the builder's collector catches a literal that is not a failure kind,
      that literal is not excluded: the pattern is narrowed until it is not caught, and the report says how.
  - `main.js`'s `shellFailure` (227-229) gets a pin in the same test: the keys of its object literal (`error`,
    `failure`, `warnings`, and `sentence`, `kind`, `seq`, `identifier` in `failure`) equal `Envelope`'s and `Failure`'s
    required keys.
- **R2.3.6** — `tests/test_errors.py`'s `SAID_WHOLE_ON_PURPOSE` (393-419): the key `("api.py", "_failure_of")` becomes
  `("api.py", "_envelope_of")`, with the same reason, because the `str(exc)` reads move with the body.

**Pin-move list:**
- `test_errors.py:399` (the key above);
- test_layers `LAYERS[0]` and `DOMAINS["door"]` gain `replies`;
- add `assert load["replies"] == set() and call["replies"] == set()` to test_layers. replies imports nothing of the
  package, and `api` and the tests import it.

**Patch sites:**
- `tracker.api`: 62 stand-ins. The only one on a name this job touches is `test_resident.py:667` (`_WARNINGS`). It is
  read unchanged, because the envelope still reads `api._WARNINGS` by name.
- `setitem` check: `setitem(api.COMMANDS, ...)` (test_api, test_errors) is untouched.

**Tests:**
- `test_replies` (new), `test_api`, `test_resident`, `test_errors`, `test_golden`, `test_progress`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`.

`test_progress` runs because `failure_reply` is now the envelope's one builder, although progress.py itself is unchanged.

**Accept when:**
- the gate passes, and `typecheck.py check` reports api.py at 24 errors, its count at `286b535` (replies.py: 0);
- every recording in `tests/golden/` is unchanged;
- a failed command's stdout is byte-identical to `286b535`'s for one case of each kind. A test in `test_api` already
  covers each of the four kinds; the builder names them in the report;
- the guard fails when one kind literal in app.js is changed to `"faild"` (shown once, then restored).

---

### P2.4 `bounds.py`: the value bounds out of records

- **Cost:** M.
- **Tier:** Opus, by rule (b). The moved functions are in the admission closure.
- **Findings:** B-11.
- **Depends on:** P2.3.

**Requirements:**

- **R2.4.1** — new `tracker/bounds.py`, at L0 in the `record` domain. It holds records.py **1427-1985** byte for byte:
  from the section comment `# ---- the value rule ----` (1427) through `_first` (1984-1985). That is the 81 module-level
  names the region binds: `YEAR_MIN` … `typed_short_title_problem`, the Date Pattern analyser (`_walk`, `_ways`,
  `_width`, `_REPEATS`, `_REFERS_BACK`, `date_pattern_problem`), the `*_BOUNDS` phrases and the `*_problem` checks, and
  the privates `_is_number`, `_field`, `_first`, `_ISO_DATE`, `_STAMP`, `_ONE_LINE_REFUSED`, `_HEX_DIGEST`.
  - **`class Override`** (records 1575-1597) is the one class among them, and it moves too.
    - `OVERRIDE_BOUNDS` (1670) reads it at load time, in bounds.
    - `rule_row_fault` (2032), which stays in records, reads `Override.ALL` and `Override.RETIRED` through
      records' import (R2.4.3).
    - rollover, review, router, validators, api, filer and view reach it through manifest and records, and keep
      doing so through the facade until P2.13.
    - `Override.__module__` becomes `"tracker.bounds"`. Nothing reads it at `286b535`: no `__module__` or
      `__qualname__` use in tracker/, tests/ or tools/ names it, and the class is never pickled, stored or
      `repr`'d (its members are strings, and those are what the record holds). The builder repeats the grep and
      says so.
    - The admission pin does not key it: `admission_closure()` records functions and constants of simple types, and
      a class, or an attribute read off a class (`Override.ALL`), is neither. So the move changes no pin entry for it.
  - records.py:74, `import re._parser as _re_parser` with P2.1's ignore and its reason (R2.1.1), moves with them
    to bounds' standard-library imports, word for word. In the same commit, `UNSTUBBED` in `tests/test_typecheck.py`
    names `"bounds.py"` in place of `"records.py"`, and nothing else in it changes.
  - bounds imports the standard library (`from __future__ import annotations` as records has, `datetime as dt`,
    `math`, `re`, `re._parser as _re_parser`, and `TypeGuard` from `typing`) and, from `tracker.layout`, only what the region reads:
    `WINDOWS_ILLEGAL_CHARS`, `WINDOWS_ILLEGAL_CHARS_TEXT`, `WINDOWS_RESERVED_NAMES_TEXT`, `is_reserved_name`,
    `spoofing_problem`, `invisible_problem`.
  - records then has no use of `re._parser`, `math` or `typing` (measured at `286b535`: every `math.` read and every
    `_re_parser` read is inside 1427-1985), and those imports are deleted. `re` stays, for `as_pattern`.
  - Its docstring says what the region's comment says (decision 187) and why it is its own module: the gate's bounds,
    with no record shape.
- **R2.4.2** — what stays in records: **1988-2172**. That is `_RULE_TEXT` and its comment, `rule_row_fault` (1997),
  `rule_row_problem` (2044), `_INFO_TEXT`, `info_problem` (2056), `household_problem` (2085), the `_ENTRY_*` tuples,
  `WAITS_FOR_BOUNDS`, `waits_for_problem` (2117), `entry_problem` (2137) and `status_problem` (2159).

  They read records' own names, which cannot go to L0: `format_waits_for` and `parse_waits_for` (354, 361),
  `DATE_FIELDS` (1013), `RULE_LIST_FIELDS` (1291), `RULE_FLAG_FIELDS` (1297) and `word_list_problem` (1308).

  The section comment at 1427 is replaced in records by a two-line pointer: "the value rule's bounds are
  `tracker.bounds`; the row checks that read the record's own shapes stay here."
- **R2.4.3** — records imports from bounds at load time:
  - every name its remaining code reads, the privates `_field` and `_first` included, and `Override`
    (`rule_row_fault` reads `Override.ALL` and `Override.RETIRED`);
  - and, as the facade, every other public name of the 81 (`# noqa: F401 - re-exported until P2.13`).

  `person_from_json` (805) reads `text_problem` through that import. Records' line 78 (the layout re-export of decision
  137) is unchanged.
- **R2.4.4** — `tests/test_bounds.py`:
  - the import pin `load["bounds"] == {"layout"}`, `call["bounds"] == set()`;
  - `test_the_records_re_export_is_the_bounds_own`: every public name of bounds is `getattr(records, n) is getattr(bounds, n)`;
  - the value-rule tests moved from `tests/test_records.py` whose bodies name only moved names. They move unchanged
    except for imports, and the report lists them.
  - **Three tests read privates that move without a re-export.** R2.4.3 re-exports only public names, plus `_field`
    and `_first` because records uses them. So these three move to test_bounds with `records.` replaced by
    `bounds.` in the body, for the moved names only:
    - `test_every_period_form_derives_a_pattern_the_rule_admits` (test_records 425; `records._ways` and
      `records._re_parser` at 437);
    - `test_every_derived_and_common_pattern_is_within_the_cost` (467; `_re_parser`, `_ways` and `_width` at
      475-476);
    - `test_a_zero_width_assertion_counts_toward_the_width` (485; `_width` and `_re_parser` at 493).

    A name in those bodies that stays in records keeps its `records.` read, and test_bounds imports records for it.
    No `records._ways`, `records._re_parser` or `records._width` remains in tests/.

  - **The import sets.** `test_nothing_here_reaches_a_file_or_a_workbook` (test_records 216-234, as P2.1 left it)
    pins records' import lines exactly, so it is re-pinned here: its set becomes `{"__future__", "datetime",
    "dataclasses", "json", "pathlib", "re", "tracker.bounds", "tracker.layout"}`, and its docstring's sentence on
    `math`, `re._parser` and `typing` (R2.1.6) becomes "The value rule's bounds, with `math` and the standard library's
    own parser, are `tracker.bounds`' since P2.4." test_bounds gains `test_the_bounds_reach_no_file`, the same check of
    bounds' own import lines against `{"__future__", "datetime", "math", "re", "re._parser", "typing",
    "tracker.layout"}`, with R2.1.6's docstring sentence.

  The total number of tests collected from the two files equals test_records' count at `286b535`, plus the three new
  tests (the import pin, the identity pin and `test_the_bounds_reach_no_file`).
- **R2.4.5** — re-pin `ADMISSION_PIN[5]`. How the keys move follows from `admission_closure()` (test_store 3876):
  - A moved function's key is `f"{function.__module__}.{qualname}"`, so it becomes `tracker.bounds.<name>`.
  - A constant read by bare name is keyed by the **reading** function's module. A bound read bare by a moved function
    is now `tracker.bounds.X`. If a function that stays in records also reads it bare, it keeps a
    `tracker.records.X` key as well, so the pin gains an entry with the same digest.
  - A constant read as an attribute (`records.X` in store) keeps its `tracker.records.X` key until P2.13, whatever
    module X lives in.

  The accept is therefore not "only keys rename". It is:
  - no digest value appears that was not in `ADMISSION_PIN[5]` at `286b535`;
  - every changed or added key is either a `tracker.records.` → `tracker.bounds.` rename of the same digest, or a
    second key for a constant whose digest is identical to its first;
  - the builder lists the added keys in the report.

  `test_the_admission_pin_reaches_the_rules_it_calls` (test_store.py 3964-3971):
  - `tracker.records.date_pattern_problem` becomes `tracker.bounds.date_pattern_problem`;
  - `tracker.records.rule_row_problem` stays (the row checks stay in records);
  - `tracker.records.MAX_EXPECTED_COUNT` **stays**. Its one read is `rule_row_fault`'s bare read at records 2019,
    and `rule_row_fault` stays in records. Nothing in the moved region reads it.

**Pin-move list:**
- `test_records.py:211` becomes `assert load["records"] == {"bounds", "layout"}`. Its test name and docstring become
  "the records import nothing of the package but the layout's name rule and the bounds".
- `test_records.py` 216-234, records' standard-library import set and its docstring (R2.4.4, "The import sets").
- **`tests/test_single_source.py` 1555-1593**,
  `test_the_retired_override_word_survives_only_in_the_decision_logs_history` (review 2, S22). It parses
  `tracker/records.py` for the one `"Waived"` literal, `Override.RETIRED`'s key, and asserts that no other tracker file
  holds the word. Once `Override` moves, the records parse finds none and the scan finds it in bounds.py. So:
  - 1585-1586's comment ("The one literal is the fold's own key, where ``Override`` lives since decision 187 moved it
    to the record's value rule.") becomes "The one literal is the fold's own key, where ``Override`` lives: decision
    187 moved it to the record's value rule, and P2.4 moved the value rule's bounds to tracker/bounds.py.";
  - 1587 parses `read("tracker/bounds.py")` instead of `read("tracker/records.py")`;
  - 1591 becomes `if path.name != "bounds.py":`, so records.py is scanned like every other file and holds no
    `"Waived"` (the class's docstring and the fold that reads `RETIRED` name no literal; the builder confirms);
  - the rest of the test is unchanged. It is a guard file, so it is already in this job's tests.
  - Its prose scan over tracker/ and tools/ (1571-1584) also reads bounds.py from now on. The moved `Override`
    docstring says "the second value", never the word, so it passes; the builder confirms.
- test_layers `LAYERS[0]` and `DOMAINS["record"]` gain `bounds`.
- test_store's `ADMISSION_PIN[5]` keys, and `date_pattern_problem`'s name in 3964-3971 (`MAX_EXPECTED_COUNT` and
  `rule_row_problem` stay `tracker.records.`).
- test_records' moved tests (R2.4.4), the three private-reading tests among them (425, 467, 485).
- `tests/test_typecheck.py`'s `UNSTUBBED` names `"bounds.py"` in place of `"records.py"` (R2.4.1). The wording and the
  guard are P2.1's, unchanged.

**Patch sites:**
- `tracker.records`: `test_content_check.py:2378` stands in for `records.date_pattern_problem`. Records' `rule_row_fault`
  reads records' own global `date_pattern_problem`, which is the import, so the stand-in still reaches it. The builder
  reads the test to confirm it drives `rule_row_fault` or `records.date_pattern_problem` and not a bounds-internal call.
  Untouched here, and handled in P2.13.
- `test_row_columns.py:561` (`RULE_FIELDS`) does not move.
- `setitem` check: no moved container is a `setitem` target.

**Tests:**
- `test_bounds` (new), `test_records`, `test_store`, `test_manifest`, `test_api`, `test_golden`, `test_typecheck`
  (`UNSTUBBED` moves with the parser's line);
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

`test_store` covers the admission and its pin. `test_manifest` covers the editor, the rules' other caller. `test_api`
covers the create path and the people refusals, which name `text_problem`. `test_content_check`, `test_filer` and
`test_router` read no moved name except through records, which the identity test proves.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- `ADMISSION_VERSION` is still 5, and the pin meets R2.4.5's three conditions against P2.3's (no new digest; every
  changed or added key a rename or a same-digest second key; the added keys listed);
- `git diff -M` shows the moved block as a move (the builder runs `git diff --color-moved=zebra` and confirms no changed
  line inside it);
- `grep -rn "type: ignore" tracker/bounds.py tracker/records.py` finds bounds' parser line alone, with R2.1.1's
  wording, and `typecheck.py check` passes with records and bounds at 0 errors.

---

### P2.5 One file-name-part rule, the typed people rule in records

- **Cost:** M.
- **Tier:** Opus, by rule (b). `identifier_problem` and `short_title_problem` are in the admission closure.
- **Findings:** B-3 (a), (b), (e).
- **Depends on:** P2.4.

**Requirements:**

- **R2.5.1** — `tracker/layout.py`: add `file_name_part_problem(text: str, *, begins: bool) -> str`, beside
  `segment_problem` (445). It returns `""` or the first of the four checks, in today's order:
  1. `WINDOWS_ILLEGAL_CHARS`;
  2. `spoofing_problem`;
  3. a trailing dot or space;
  4. `is_reserved_name`.

  The words are byte-identical to the two bodies they replace. With `begins=True` the phrases are "(it begins a file
  name)" and "it begins a file name"; with `begins=False` they are "(it is part of a file name)" and "it is part of a
  file name".

  Then:
  - `bounds.identifier_problem` becomes `return file_name_part_problem(identifier, begins=True)`, keeping its docstring.
  - `bounds.short_title_problem` keeps its length check, then `return file_name_part_problem(short_title, begins=False)`.

  The short title's `short_title and` guard on the reserved check is dropped. That is safe because
  `layout.is_reserved_name("") is False` (measured at `286b535`), and a test in test_layout pins that fact with its
  reason. `layout.segment_problem` is not changed: its phrases are its own.

  Re-pin `ADMISSION_PIN[5]`:
  - `tracker.bounds.identifier_problem` and `tracker.bounds.short_title_problem` change digests;
  - `tracker.layout.file_name_part_problem` joins;
  - the constants they read are now keyed `tracker.layout.*`.

  No line the admission used to admit is refused, and none it refused is admitted. A test in test_layout holds every
  sentence of both callers to the strings at `286b535`, for a sample of each check.
- **R2.5.2** — `bounds.IDENTIFIER_MAX_CHARS = 80` (formerly records:1513) becomes `IDENTIFIER_MAX_CHARS = NAME_MAX_CHARS`,
  imported from layout, with a comment naming P291. Its `repr` is unchanged, so its pin digest (if keyed) is unchanged.
- **R2.5.3** — `tracker/records.py`: the typed people rule's words and checks move here, as **two** functions beside
  `person_from_json`, so that api's loop keeps its order and its laziness (review 2, S30):
  - `typed_person_problem(kind: str, name: str) -> str` returns `""` or the first of these, in today's order and
    today's words (api.py 2313-2324):
    - a kind not in `PERSON_KINDS`: `f"'{kind}' is not one of {', '.join(PERSON_KINDS)}"`;
    - an empty name: `f"Every person needs a name ({PERSON_KIND_LABELS[kind]})"`;
    - `text_problem(name)`: `f"{PEOPLE_LABEL}: the {PERSON_KIND_LABELS[kind]}'s name {problem}"`.

    `kind` is already stripped and `name` already folded by `" ".join(...split())`, as api does them today.
  - `typed_spelling_problem(name: str, spelling: str) -> str` judges **one** spelling, already folded and not empty,
    and returns `""` or the first of (api.py 2330-2338):
    - if `not is_a_spelling(spelling)`: `ONE_WORD_SPELLING`;
    - else if `text_problem(spelling)`: `f"{PEOPLE_LABEL}: a spelling of {name} {problem}"`.

    The comments at api 2318-2322 and 2332-2336 (P288, P304, P306) move with the checks they explain.
  - **Why two, not one taking every spelling.** Today api folds and judges each spelling inside its loop, after the kind
    and name checks. A single function handed the spellings would need them gathered first, and gathering moves two
    things earlier: `one.get("spellings") or []` is iterated before the kind is judged (a non-iterable `spellings` with
    a bad kind would raise `TypeError`, so the reply would be "failed" where today it is "refused"), and every
    spelling is folded before the first is judged. Two passes would also change which refusal wins: with spellings
    `[A, B]`, where A has two words but fails `text_problem` and B is one word, today's reply is A's text sentence, and
    two passes would answer `ONE_WORD_SPELLING`.
  - **The spelling sentence.** `ONE_WORD_SPELLING = "Spelling Needs Two Words"` moves from names.py:67 to records, beside
    `MIN_SPELLING_WORDS` (729). names imports it back and re-exports it
    (`# noqa: F401 - re-exported until P2.14`). names uses it nowhere itself; api.py:236 and filer.py:275 import it
    from names. `tests/test_names.py` gains `test_the_spelling_sentence_is_the_records_own`, asserting
    `names.ONE_WORD_SPELLING is records.ONE_WORD_SPELLING`; P2.14 deletes it with the re-export.
- **R2.5.4** — `api._people_from_spec` (2296-2337) keeps its shape and its order:
  - its shape checks (not a list, not a dict: `f"{PEOPLE_LABEL} must be a list of people"`);
  - `kind`'s strip and `name`'s fold (2312, 2315), then `records.typed_person_problem(kind, name)`, raising
    `ManifestError(problem)` when there is one. That call replaces the three checks at 2313-2314, 2316-2317 and
    2323-2324, and the comment at 2318-2322 moves to records with its check;
  - then the loop it has today (2326-2340), unchanged but for its two checks: for each spelling in
    `one.get("spellings") or []`, the fold, the skip of an empty one, then
    `if problem := records.typed_spelling_problem(name, spelling): raise ManifestError(problem)`, then the
    de-duplication;
  - the `Person` it builds.

  So `spellings` is first iterated after the kind and name checks, and each spelling is folded and judged before the
  next is read, exactly as today. Every refusal's sentence and order is unchanged. The docstring's `:data:` reference
  becomes `tracker.records.ONE_WORD_SPELLING`.
  - **The ordering tests**, in `tests/test_api.py` beside 11319 (`_people_from_spec` is where the order lives):
    - `test_a_persons_spellings_are_judged_one_at_a_time_in_order`: with `[A, B]` (A a two-word spelling
      `text_problem` refuses, such as one past the length bound; B one word), the refusal is A's text sentence; with
      `[B, A]` it is `ONE_WORD_SPELLING`;
    - `test_a_persons_kind_is_judged_before_their_spellings_are_read`: a person with a kind nothing knows and
      `"spellings": 5` raises `ManifestError` with the kind's sentence, not `TypeError`.
  - `tests/test_records.py` gains one test per function: every sentence each returns, against the literal strings at
    `286b535`.

**Pin-move list:**
- `ADMISSION_PIN[5]` (R2.5.1);
- test_layout gains the pin tests in R2.5.1;
- test_names: no import of `ONE_WORD_SPELLING` at HEAD; it gains the identity pin (R2.5.3);
- test_api 4423, 4479, 11321 import it from names, and keep doing so until P2.13;
- test_api gains the two ordering tests (R2.5.4).

**Patch sites:**
- `tracker.names`: 3 stand-ins (`check_name`, `read_names`, `name_parts`), none on the moved sentence.
- `tracker.api`: none on `_people_from_spec` (test_api.py:11326 calls it directly).
- `tracker.layout`: 20 stand-ins, none on a name changed here.

**Tests:**
- `test_layout`, `test_bounds`, `test_records`, `test_names`, `test_api`, `test_store`, `test_manifest`, `test_errors`
  (the refusal wording's guard), `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- every refusal sentence the identifier, short-title and people tests assert is unchanged, with no test's expected
  string edited;
- `ADMISSION_VERSION` is still 5.

---

### P2.6 `hold.py`: the per-reply memo out of settings

- **Cost:** M.
- **Tier:** Opus, by rule (e). It moves the package's one `global`-rebound memo that every held read goes through
  (`store.held_read`), together with the register keys of its state. A from-import copy would silently read a stale
  `None`.
- **Findings:** B-5 (the hold half).
- **Depends on:** P2.5.

**Requirements:**

- **R2.6.1** — new `tracker/hold.py`, at L0 in the `record` domain. It imports only the standard library, exactly:
  `from __future__ import annotations` (as settings has, so the moved annotations read as they do now), `os`
  (`resolved` asks `os.path.lexists`, settings 1238-1254), `from collections.abc import Callable, Iterator`,
  `from contextlib import contextmanager`, `from pathlib import Path` and `from typing import TypeVar`. It holds settings.py **1099-1254**
  byte for byte, **except `_SETTINGS_HELD` (1112)**, which stays in settings beside `_read` because it is the settings
  file's own memo key. That leaves:
  - `_HELD`, `_HOLDING`;
  - `HOLD_READING`, `HOLD_HOUSEHOLD`;
  - `T`;
  - `one_reading`, `one_household`, `_holding`, `held`;
  - `WRITE_WHILE_READING`, `WRITE_WHILE_HOLDING`;
  - `refuse_a_write_while_reading`, `resolved`.

  Its docstring carries P118, P207 and P215's reasoning (the hold region's comments).
- **R2.6.2** — settings imports `from tracker import hold` and reads through the module:
  - `_read` (459): `hold._HELD`;
  - `_write` (539): `hold._HELD`, `hold.WRITE_WHILE_HOLDING`, `hold.refuse_a_write_while_reading`;
  - `app_dir` (667), `program_folders` (797), `data_home` (964): `hold.held(...)`.

  As the facade, settings also re-exports the public names: `HOLD_HOUSEHOLD`, `HOLD_READING`, `WRITE_WHILE_HOLDING`,
  `WRITE_WHILE_READING`, `held`, `one_household`, `one_reading`, `refuse_a_write_while_reading` and `resolved`
  (`# noqa: F401 - re-exported until P2.13`). It never re-exports `_HELD` or `_HOLDING`.

  The standard-library imports settings no longer uses (at HEAD, `contextmanager`, `Iterator`, `Callable` and `TypeVar`
  are used only in the hold and error-log regions, so the builder checks after P2.7 too) are deleted when ruff says
  they are unused.
- **R2.6.3** — the state register (`tracker/resident.py` 186-187): `("settings", "_HELD")` becomes `("hold", "_HELD")`
  and `("settings", "_HOLDING")` becomes `("hold", "_HOLDING")`, with "reset by `hold.one_reading`". The module
  docstring's mention at resident.py:47 (`settings.one_reading()`) stays true through the facade and is left until
  P2.13.

  The test that asserts those keys and their words moves with them. tests/test_resident.py 651-652
  (`test_each_per_process_name_says_why_it_lives_as_long_as_the_engine`) become:

  ```python
  assert resident.PER_PROCESS[("hold", "_HELD")] == "reset by `hold.one_reading`"
  assert resident.PER_PROCESS[("hold", "_HOLDING")] == "reset by `hold.one_reading`"
  ```

  No other line in tests/, tracker/ or tools/ names the register's settings keys
  (`grep -rn '"settings", "_HOL\|"settings", "_HELD' tests tracker tools` finds only these four lines at `286b535`).
- **R2.6.4** — every test line that reads or sets `_HELD` or `_HOLDING` through the settings module, under any of its
  three spellings (section 3), reads `hold.` instead (25 lines; review 2, S23):
  - test_api 7925, 7929, 7940;
  - test_registry 817, 823;
  - test_resident 391, 396;
  - test_runner 713, 715, 726, 4347, 4352, 4377, 5317, 5323, 5337, 5542;
  - **test_settings 930, 931, 932, 965, 1044, 1049, 1050, 1051**, which spell the module `data_rules`
    (`from tracker import settings as data_rules`, line 15). `data_rules._HELD` becomes `hold._HELD` and
    `data_rules._HOLDING` becomes `hold._HOLDING`; test_settings imports `from tracker import hold`. A test among
    them that R2.6.5 moves to test_hold takes the same reads with it. The other names on those lines
    (`data_rules.app_dir`, `data_rules.HOLD_READING`, `data_rules.HOLD_HOUSEHOLD`) are read through the facade
    until P2.13.

  Measured at `286b535`: `grep -rnE '\._(HELD|HOLDING)\b' tests/*.py` finds these 25 lines and test_store's two old pin
  keys (3292, 3562), 27 in all, and nothing else. A read that stayed on the settings module after the move would fail with
  `AttributeError`, or, if it sets the name, set an attribute nothing reads.

  The old pin versions' keys at test_store 3031-3033, 3292 and 3562 are history and stay as written.
- **R2.6.5** — `tests/test_hold.py`:
  - `load["hold"] == set()`, `call["hold"] == set()`;
  - `test_the_settings_re_export_is_the_holds_own` (the identity pin);
  - the hold tests moved from test_settings whose bodies name only moved names, listed in the report.
- **R2.6.6** — the register's blind spots, read by hand in `hold.py`: an alias of `_HELD`, a mutating method outside the
  derivation's list, a nested function shadowing `_HELD` or `_HOLDING`. The report says that none occurs, or names the
  one that does and stops.

**Pin-move list:**
- R2.6.3 (resident.py 186-187 and test_resident 651-652) and R2.6.4;
- the curated nodes: hold gets its own node, and the settings node's hold paragraph (from "P118: one_reading() holds
  data_home ..." through "... held(key, answer, *, there=None) replaces _held ... never an error.") moves to it, with
  "settings" read as "this module" where it names the hold's home. The settings node keeps one sentence: "The per-reply
  memo is tracker/hold.py's (P2.6); data_home, app_dir and program_folders ask hold.held, and _read and _write read
  hold._HELD." Other nodes that name `settings.one_reading` and the like stay true through the facade and are
  corrected in P2.13;
- test_layers `LAYERS[0]` and `DOMAINS["record"]` gain `hold`;
- `test_layers.py:367` becomes `load["settings"] == {"fsio", "hold", "layout"}`, with its docstring gaining a sentence
  on the hold.

**Patch sites:**
- `tracker.settings`, the hold names:
  - `test_runner.py:4356` and `5551` stand in for `resolved` on settings. The callers read `settings.resolved` (content_check
    2352) or `from tracker.settings import resolved` at call time (store 861, 940, 966), so the stand-ins still reach
    them.
    - **The one call they stop reaching, and why neither test loses coverage.** `held()`'s own call to
      `resolved(there)` (settings 1209) becomes `hold.resolved`, which a stand-in on settings does not replace. That
      call runs only when `there is not None and _HOLDING != HOLD_READING`, that is, inside a household's hold.
    - test_runner 4356 runs its pass inside `settings.one_reading()` (`HOLD_READING`), so that branch never runs
      there.
    - test_runner 5551 counts only the calls made while `_HELD is None`, and the branch runs only inside a hold, where
      `_HELD` is set. So the calls it counts are the same.
    - The builder confirms both by reading them, and says so in the report.
  - `test_store.py:5633` stands in for `held` on settings. `store.held_read` (1103) and `store.engagement_key` (985) call
    `settings.held`, which reaches the stand-in. Settings' own three calls now go through `hold.held`, which this test
    does not watch: it counts only `"record read"` keys.

  The builder confirms all three by reading them.
- `setitem` check: no `setitem` on `_HELD`.

**Tests:**
- `test_hold` (new), `test_settings`, `test_store`, `test_api`, `test_registry`, `test_resident`, `test_runner`,
  `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`.

The changed test files are test_api, test_registry, test_resident, test_runner and test_settings (R2.6.4).

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- the register test (`test_resident`) passes with the moved keys;
- `grep -rnE '\b(settings|settings_module|data_rules)\._(HELD|HOLDING)\b' tracker tests tools` finds nothing, and
  `grep -rnE '\._(HELD|HOLDING)\b' tests` finds only `hold._HELD`/`hold._HOLDING` reads and the two old pin keys
  (test_store 3292, 3562), which are history.

---

### P2.7 `errlog.py`, and `settings.inside`

- **Cost:** M.
- **Tier:** Sonnet. It moves code out of settings, which is not on rule (a)'s list, and touches no admission, record
  write, lock or atomic replace. The error log's own `os.replace` rotation moves byte for byte.
- **Findings:** B-5 (the error-log half), B-6 reduced (section 2.1).
- **Depends on:** P2.6.

**Requirements:**

- **R2.7.1** — new `tracker/errlog.py`, at L0 in the `door` domain. It holds settings.py **345-456** byte for byte:
  - `ERROR_LOG_FILENAME`, `ERROR_LOG_MAX_BYTES`, `ERROR_LOG_BACKUPS`, `ERROR_LOG_FORMAT`, `ERROR_LOG_NOT_WRITTEN`;
  - `error_log_path`, `_ErrorLog`, `error_log`.

  It imports `logging`, `os` and `sys`, plus `contextlib.contextmanager`, `collections.abc.Iterator`, `pathlib.Path`,
  `typing.cast` and, at load time, `from tracker.settings import SettingsError`. `error_log_path` keeps its call-time
  `from tracker import store`, and `handleError` keeps its call-time `from tracker import errors`.

  The comment in `handleError` at settings 405-406 moves with it, and is the one changed line in the moved block,
  because its words would be false in errlog. It reads today:

  > `# At call time, as store is in error_log_path(): this module's`
  > `# load-time imports stay layout and fsio.`

  and becomes:

  > `# At call time, as store is in error_log_path(): this module's one`
  > `# load-time import of the package is settings.`

  The docstring carries decision 193's reasoning, and says why settings does not re-export it: errlog imports settings
  at load time, so a re-export would be a load-time cycle.
- **R2.7.2** — no facade. Every importer is pointed at errlog in this job:
  - api.py:325: `ERROR_LOG_FILENAME`, `error_log` and `error_log_path` come from `tracker.errlog`, and the rest of that
    settings import stays.
  - runner.py:257: `ERROR_LOG_BACKUPS`, `ERROR_LOG_FILENAME` and `error_log` come from `tracker.errlog`.
  - resident.py:267 and 323: `settings.error_log` becomes `errlog.error_log`, and the docstring at 265 follows.
    - **resident's load-time imports change** (review 2, S24). Those two lines are resident's only uses of `settings`
      (measured at `286b535`: every other `settings` in resident.py is a register key string, 186-188, or prose, 47 and
      92). So line 109, `from tracker import api, locking, ocr, settings`, becomes
      `from tracker import api, errlog, locking, ocr`: errlog joins, and settings goes, since ruff's F401 would fail on
      it otherwise. The import stays at load time, as resident's imports are. A call-time import of errlog was
      rejected: it would leave `settings` imported and unused, so the load set would change all the same.
    - resident's docstring at 91-92, "it imports ``api`` (which owns the commands), ``locking``, ``ocr`` (to forget the
      reader's warnings between commands), ``settings`` and the standard library", becomes "it imports ``api`` (which
      owns the commands), ``errlog`` (the error log every command's lines go to), ``locking``, ``ocr`` (to forget the
      reader's warnings between commands) and the standard library". The register's `("settings", ...)` keys are
      unchanged by this job: the restore reads `sys.modules["tracker.settings"]` and imports nothing.
  - The tests:
    - conftest 1021;
    - test_api 7268, 7377, 7386 (the stand-in, now on `errlog.ERROR_LOG_MAX_BYTES`), 7392, 11571, 11585;
    - test_build 156-157;
    - test_errors 188, 210 and the docstring at 186;
    - test_resident 79;
    - test_runner 4582, 4664 (only the `ERROR_LOG_FILENAME` name moves; the other names stay on settings);
    - test_settings 291, 312, 336 (these move to `tests/test_errlog.py`);
    - test_single_source 683, 744, 1749, 3250, 3361 (only the `ERROR_LOG_*` names in each import);
    - test_tripwire 96.
  - The words that name the log's old home:
    - **tracker/errors.py:48**, the docstring's ``:func:`tracker.settings.error_log```, becomes
      ``:func:`tracker.errlog.error_log```.
    - **docs/runbook.md 1616 and 2151**: `tracker.settings.ERROR_LOG_FILENAME` becomes
      `tracker.errlog.ERROR_LOG_FILENAME` in both. The runbook is part of any change it describes (CLAUDE.md).
    - **tracker/resident.py**: the docstring at 265 follows (above).
  - **The curated map** (`docs/repo-map.curated.json`):
    - errlog gets its own node. Its role is the error log's, and its notes take the settings node's "Decision 193:
      ERROR_LOG_FILENAME and error_log() ..." sentences (through "... so it moves with the store."), with "this
      module" for the log's home, plus the reason there is no facade (R2.7.1).
    - The settings node keeps one sentence in their place: "Decision 193's error log is tracker/errlog.py's (P2.7),
      which imports this module's SettingsError; this module never imports it."
    - The `artifact:tracker-errors.log` node's role (line 601): "ERROR_LOG_FILENAME and error_log() in
      tracker/settings.py" becomes "ERROR_LOG_FILENAME and error_log() in tracker/errlog.py".
    - The `artifact:the data home` node: "settings.ERROR_LOG_FILENAME" becomes "errlog.ERROR_LOG_FILENAME".
    - The resident node (line 113) and the errors node's role and notes (579, 580): "settings.error_log" becomes
      "errlog.error_log", three times.
    - Add the edge `{"from": "tracker/errlog.py", "to": "artifact:tracker-errors.log", "type": "writes"}`. The api and
      runner `writes` edges to it stay: both still open it for their lifetime, now through errlog.
- **R2.7.3** — `tests/test_errors.py`:
  - `THE_ONE_LOG = "settings.py"` (242) becomes `"errlog.py"`;
  - `test_no_module_but_settings_attaches_a_log_file_or_names_one` (321) becomes
    `test_no_module_but_errlog_attaches_a_log_file_or_names_one`, and its docstring follows.
  - `SAID_WHOLE_ON_PURPOSE`'s settings keys (`_read`, `product_name`) do not move.
- **R2.7.4** — `settings._inside` (1399) is renamed to `inside`, with the same body and docstring, plus one sentence that
  it is public because store asks it (decision 186's two checks). Every reference follows:
  - settings 690, 693, 804, 911, 1471-1481;
  - store 802 and 3942;
  - test_ocr 1632 and 1642;
  - test_backtest 381, 382, 401, 403, 441;
  - test_settings 759, 761, 1153;
  - test_layers' `ALLOWED_SPELLINGS` key `("tracker/settings.py", "_inside")` (711), which becomes
    `("tracker/settings.py", "inside")`.

  - the settings node's curated notes (`docs/repo-map.curated.json` line 69): "_inside() compares the folders
    themselves" and "_within and _inside keep their own under-a-folder spelling" name it `inside`.

  `settings._within` (1389) is unchanged. No `_inside` alias is kept. records.py's `_inside` at 1951 and 1963 is a local
  name in the Date Pattern analyser (now bounds), not this function, and is untouched.
- **R2.7.5** — `tests/test_errlog.py`:
  - `load["errlog"] == {"settings"}` and `call["errlog"] == {"errors", "store"}`;
  - the three error-log tests moved from test_settings (291, 312 and 336's functions).
- **R2.7.6** — decision row **P315**:
  - `hold.py` and `errlog.py` at L0;
  - errlog without a facade, and why;
  - B-6 built reduced: `store_path` stays the rule's home because the store may not import settings at load time
    (decision 101). `settings.inside` is public. The settings↔store call-time cycle is gone.
  - B-10 not built, with section 2.1's reason. It is on the orchestrator's carry list, to be built in the first phase
    that owes a Mac check.

**Pin-move list:**
- R2.7.2 to R2.7.4;
- test_layers `LAYERS[0]` and `DOMAINS["door"]` gain `errlog`;
- **resident's load pin** (review 2, S24), in `tests/test_layers.py`:
  - 950, `assert load["resident"] == {"api", "locking", "ocr", "settings"}, load["resident"]`, becomes
    `assert load["resident"] == {"api", "errlog", "locking", "ocr"}, load["resident"]`. 951-953 are unchanged
    (`call["resident"]` stays empty, nothing imports resident, and resident and api stay at L5);
  - the test at 945, `test_the_engine_imports_the_api_the_lock_the_reader_and_the_settings_and_nothing_imports_the_engine`,
    becomes `test_the_engine_imports_the_api_the_error_log_the_lock_and_the_reader_and_nothing_imports_the_engine`.
    Its docstring's "it reaches only those four" stays true (four modules);
  - the `LAYERS` comment at 154-156, "it imports ``api``, ``locking``, ``ocr``, ``settings`` and the standard
    library;", becomes "it imports ``api``, ``errlog``, ``locking``, ``ocr`` and the standard library;";
  - errlog sits at L0, below resident's L5, so the layer rule holds;
  - resident.py's docstring at 91-92 (R2.7.2);
- `tests/test_layers.py:367` is unchanged (settings' load set is still `{"fsio", "hold", "layout"}`; settings had no
  load-time import of store).

**Patch sites:**
- `tracker.settings`: `test_api.py:7386` (`ERROR_LOG_MAX_BYTES`) is retargeted to errlog. `_ErrorLog.emit` reads the
  module global, so the stand-in must be on the module that holds it.
- No stand-in is on `_inside`.
- `tracker.store`: 49 stand-ins, none on `store_path` or `store_named`.

**Tests:**
- `test_errlog` (new), `test_settings`, `test_store`, `test_api`, `test_runner`, `test_resident`, `test_errors`,
  `test_build`, `test_ocr`, `test_backtest`, `test_tripwire`, `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

test_build, test_ocr, test_backtest, test_tripwire, test_single_source and test_errors are run because they are changed
test files.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- `import_edges()` shows no settings↔store cycle;
- `grep -rnE "\b(settings|settings_module|data_rules)\.(ERROR_LOG|error_log|_inside)" tracker tests tools docs/runbook.md docs/repo-map.curated.json`
  finds nothing (the three spellings, section 3; test_settings' `data_rules._inside` at 759, 761 and 1153 is among the
  lines R2.7.4 renames);
- `import_edges()` gives `load["resident"] == {"api", "errlog", "locking", "ocr"}`;
- the settings node's notes no longer describe the error log, and errlog's node does.

---

### P2.8 `PAGE_BREAK` into records, the Open lists into reasons, `page.document`

- **Cost:** M.
- **Tier:** Opus, by rule (a). It moves code out of content_check, api and runner.
- **Findings:** A-9, C-7, C-9.
- **Depends on:** P2.7.

**Requirements:**

- **R2.8.1** — A-9:
  - `PAGE_BREAK = "\f"` and its comment move from content_check.py:168 to records, near the shapes, with a sentence on why
    the record's module holds it: names and content_check both read it, and names already imports records.
  - content_check imports it from records. It uses it at 1108, 1109, 1128, 1595 and 1914, so the import is a use, not a
    facade.
  - names.py:57 becomes `from tracker.records import PAGE_BREAK`. That removes names' only load-time import of
    content_check, and with it the content_check↔names cycle.
  - names.py's docstring says nothing about the import, so there is nothing to change there. The sentence that does
    is the curated names note (`docs/repo-map.curated.json` line 467): "content_check.judgment_of imports it at call
    time (names imports content_check at load time for PAGE_BREAK, so the call-time import is what keeps layers
    acyclic)" becomes "content_check.judgment_of imports it at call time (names takes PAGE_BREAK from
    tracker/records.py and never imports content_check, so that import closes no cycle)".
  - content_check.py 1562-1563's comment, above `from tracker.names import check_name, read_names`, says "names imports
    this module when it loads, so it is reached when called (the layer table's allowance for a call-time import)". After
    names.py:57 changes that is false. It becomes: "names never imports this module, so the call-time import here
    closes no cycle; it stays at call time, as every import this phase does not need to move does." The import itself
    is unchanged.
  - test_router.py:1333 still imports `PAGE_BREAK` from content_check, which is valid because content_check uses it, and
    is left as it is.
- **R2.8.2** — C-7:
  - `READ_AND_PARKED_CODES` (api.py 872-884) and `NO_OPEN_CODES` (891-920) move, with their comments (861-871, 886-890),
    to the end of `tracker/reasons.py`, with the same names and members. `reasons.X` becomes `X` inside the module.
  - api imports both from reasons. It uses them at 2428-2432, so the import is a use.
  - `test_every_code_is_placed_in_exactly_one_of_the_two_open_sets` (test_api.py 961-973) moves to `tests/test_reasons.py`
    unchanged but for `reasons.` in place of `api.`.
  - The other test references (test_api 920, 936, 976, 4761, 10764; test_single_source 2820, 2827) keep working through
    api's import and are left.
- **R2.8.3** — C-9: `tracker/page.py` gains
  `document(title: str, style: str, body: Iterable[str], *, meta: Iterable[tuple[str, str]] = (), script: str | None = None) -> list[str]`.
  It returns, in order:
  - `"<!doctype html>"`, `'<html lang="en">'`, `"<head>"`, `'<meta charset="utf-8">'`;
  - `policy(style=style, script=script)`;
  - `f"<title>{esc(title)}</title>"`;
  - one `f'<meta name="{esc(name)}" content="{esc(value)}">'` per pair in `meta`;
  - `f"<style>{style}</style>"`, `"</head>"`, `"<body>"`;
  - `*body`;
  - `"</body>"`, `"</html>"`.

  **`script` only feeds the policy; `document` never writes a `<script>` tag.** page.py's docstring ("There is no
  helper for a script tag, a style sheet link or an image") and its curated note ("Still no helper for a script tag")
  hold that rule, and this job keeps it. A page with a script hands its hash to the policy through `script=` and puts
  its own `<script>` line last in `body`, as the view does (R2.8.4).

  Its docstring says why it is here: the head and the CSP that keep both pages from fetching anything are written once,
  which serves standing rule 4's no-network discipline. page.py's module docstring gains a `document` bullet beside
  `esc`, `table` and `page_text`, and its curated role names `document()`.
- **R2.8.4** — runner.py 2808-2850: the `lines` list becomes `page.document(title, _STATUS_STYLE, [...the body lines 2819-2848...])`.
  `view._page` (690-712) becomes:

  ```python
  page_text(document(f"{label_of(engagement_dir)} — {VIEW_LABEL}", _STYLE,
                     [*_body(engagement_dir, items, entries, triaged, stamp), f"<script>{_SORT_SCRIPT}</script>"],
                     meta=((META_NAMES[label], value) for label, value in stamp.items() if label in META_NAMES),
                     script=_SORT_SCRIPT))
  ```

  The `<script>` line stays the view's own, last in its body, where it is today (view 709).

  `esc` of the joined title equals today's `esc(label) + " — " + esc(VIEW_LABEL)`, because the separator holds no
  character `esc` changes. The builder asserts that in test_page.

  `_STATUS_POLICY` (runner 2618) and `_POLICY` (view 332) are deleted if nothing else reads them (at HEAD nothing does),
  and so is `policy`'s import where it becomes unused.
- **R2.8.5** — `tests/test_page.py` gains `test_a_document_is_the_two_pages_skeleton`. It holds `document(...)`'s lines
  for a page with meta and a script, and for one without, against literal lists. It also asserts that no line
  `document` writes holds `<script`, whatever `script=` is.
- **R2.8.6** — **the two pages, byte for byte.** No golden recording holds page bytes, no test pins `view._POLICY` or
  `_STATUS_POLICY`, and none compares a page with an earlier render. So the builder proves R2.8.4 by a diff:
  1. **Before** touching runner.py, view.py or page.py, write a throwaway script under the scratchpad (never
     committed). It renders two pages from made-up inputs, with the clock fixed:
     - `view._page(...)` for a made-up engagement folder (`1040 - Made Up Person`), two request items from
       `tests.builders`, no index entries, no triage, and a fixed stamp holding every `META_NAMES` label;
     - `runner.write_status_page(root, report, now=FIXED)` for a temporary root named `Made Up Clients`, holding one
       made-up return, with a `RunReport` of that one run.

     It writes both pages' bytes into the scratchpad, with the temporary folder's path replaced by `<root>`.
  2. **After** the change, run the same script again.
  3. `cmp` the two pairs. The report gives the command and its output, which must be empty.

  Nothing here may point at a real clients root (decision 185). The made-up inputs are the suite's own.

**Pin-move list:**
- test_api 961-973, which moves to test_reasons;
- test_layers has no exact import pin on names, content_check, reasons or page. The builder confirms with
  `grep -n 'load\["\(names\|content_check\|reasons\|page\)"\]' tests/`;
- the curated notes for names and content_check that state the page-break import are corrected.

**Patch sites:**
- `tracker.content_check`: 102 stand-ins, none on `PAGE_BREAK`.
- `tracker.api`: none on the two sets.
- `tracker.runner`:
  - `write_text_atomically` at test_runner 4380, 5340, 5371, 5550 (imported). The write still goes through runner's own
    name, so they are unaffected.
  - `write_status_page` at test_api 1782 and test_runner 2391, 2767 is unchanged.
- `tracker.view`: `write_text_atomically` at test_errors 1031 and test_view 501, 639, 662 is unaffected.
- `setitem` check: `setitem(reasons.SHORT_REASONS, ...)` (test_api 9781) is a different table, untouched.

**Tests:**
- `test_records`, `test_names`, `test_content_check`, `test_reasons`, `test_api`, `test_page`, `test_runner`, `test_view`,
  `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

`test_content_check` runs as content_check's own file, since content_check changed, but only its import changed.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- R2.8.6's `cmp` of both pages, before and after, is empty, and the report shows it;
- `document` writes no `<script` line (R2.8.5);
- `import_edges()` shows no content_check↔names cycle.

---

### P2.9 `index.py` out of filer, re-exported

- **Cost:** M.
- **Tier:** Opus, by rule (a). It moves code out of filer.
- **Findings:** A-2 (step 1).
- **Depends on:** P2.8.

**Requirements:**

- **R2.9.1** — new `tracker/index.py`, at L1 in the `record` domain. It holds the index's reading closure from filer.py,
  byte for byte with comments. The builder recomputes it at build time from these roots:
  - `read_index`, `ensure`, `holds_the_row`, `prepared_location`, `moved_to`, `both_gone`, `marked_missing`,
    `interrupted`;
  - and the decision words `INDEX_HEADING`, `FILED`, `NEEDS_REVIEW`, `DUPLICATE`, `NOT_REQUESTED`, `FILE_MOVED`,
    `MARKED_MISSING`.

  At `286b535` the closure is exactly:
  - 350 `INDEX_HEADING`;
  - 363 `FILED`, 364 `NEEDS_REVIEW`, 365 `DUPLICATE`, 374 `NOT_REQUESTED`, 384 `FILE_MOVED`, 431 `MARKED_MISSING`;
  - 650-658 `prepared_location`;
  - 1287-1318 `read_index`;
  - 1737-1766 `ensure`;
  - 2645 `MOVED_SENTENCE`, 2649-2650 `MOVED_GONE_SENTENCE`, 2672-2673 `BOTH_GONE_SENTENCE`;
  - 2716 `_MOVED_DATE`;
  - 2719-2735 `_moved_tail`;
  - 2738-2740 `_MOVED_TAIL`, `_MOVED_GONE_TAIL`, `_BOTH_GONE_TAIL`;
  - 2749-2754 `_MARKED_TAIL`;
  - 2757-2774 `_moved_part`;
  - 2777-2791 `moved_to`, 2826-2838 `both_gone`, 2841-2853 `marked_missing`;
  - 3252-3253 `INTERRUPTED_MOVE_DETAIL`, 3272-3279 `_INTERRUPTED_TAIL`, 3282-3304 `interrupted`;
  - 7266-7277 `holds_the_row`.

  If the recomputed closure differs, stop and ask.

  Three filer helpers that read only the moved tail grammar move with it, so that index owns every reader and composer of
  the moved sentence's tail:
  - `_without_moved_sentence` (2794);
  - `_before_the_moved_sentence` (2807);
  - `_says_it_is_nowhere` (2818).

  Filer imports these three by their private names, and the index docstring says so. It is the one place a private name
  crosses this boundary.

  Index imports:
  - `ledger`, `re`, `reasons`, `store`;
  - `Path`;
  - `IndexEntry`, `as_pattern`, `entry_from_json` from records;
  - `PREPARED_DIR_NAME` from `tracker.layout`, its home (layout.py:88). Filer takes it through scaffold's re-import
    today; index takes it from where it is defined, so it has no edge to scaffold;
  - `is_cloud_placeholder` and `sha256_of` from validators.

  It needs no logger: none of the moved code logs (checked at HEAD). Its docstring states:
  - what it is (the index as the record holds it, and the words its rows carry);
  - why L1 (it reads only L1 and L0);
  - that Q-A's one-way cycle follows from it (P2.10).
- **R2.9.2** — filer imports from index:
  - every moved name it uses itself;
  - and, as the facade, every other public moved name (`# noqa: F401 - re-exported until P2.14`).

  At this commit api, runner, view, review, reminder, rollover, scanner and store keep importing them from filer.
- **R2.9.3** — `tests/test_reasons.py`'s `TAIL_READERS` (152-158): `("filer", "moved_to")` becomes
  `("index", "moved_to")` and `("filer", "interrupted")` becomes `("index", "interrupted")`, with the same reasons.
- **R2.9.4** — `tests/test_index.py`:
  - the import pin `load["index"] == {"layout", "ledger", "reasons", "records", "store", "validators"}`, or what
    `import_edges()` reports if it adds a module of L1 or below (the builder records which). Also `call["index"] == set()`;
  - `test_the_filers_re_export_is_the_indexs_own`: the identity pin for every public moved name;
  - the tests from test_filer whose bodies drive only moved functions (at least those of `_without_moved_sentence`
    3432-3465 and 8782-8803, `read_index`, `moved_to`, `both_gone`, `interrupted`, `holds_the_row`), moved unchanged but
    for imports and listed in the report.
- **R2.9.5** — the curated nodes: index gets its role and notes. Filer's notes keep "THE DELIBERATE CYCLE" sentence
  until P2.10, which rewrites it.

**Pin-move list:**
- R2.9.3 and R2.9.4;
- test_layers `LAYERS[1]` and `DOMAINS["record"]` gain `index`;
- test_layers 409-410 still pass at this commit, since the scanner still imports filer at call time.

**Patch sites** (`tracker.filer`, 79 stand-ins). Those on names that now live in index, or that index reads:
- **`read_index` on filer**, at test_api 7367, test_filer 1061, 3724, 6479, 9292 and test_rollover 345.
  - **The rule after the move.** No moved function calls `read_index` (`ensure` asks `store.catch_up` and
    `store.state`, filer.py 1763-1766, and nothing else in the closure reads the index file). Filer's own callers read
    filer's global, which is the function imported from index, and a stand-in on filer replaces it. A caller outside
    filer that imports `read_index` from index (from P2.10) is not reached by a stand-in on filer.
  - **At this commit all six still reach what they meant.** Every importer outside filer still takes `read_index`
    from filer, and the call-time importers (rollover 590, the scanner, review, reminder) read filer's attribute when
    they run, which is the stand-in.
  - **The six, sorted:**
    - test_filer 1061, 3724, 6479 and 9292 drive filer's own reads, and stay on filer for good;
    - test_api 7367 and test_rollover 345 drive rollover's call-time read (rollover.py 597). They stay here and move
      to `index` in P2.10 (R2.10.1).
- **`is_cloud_placeholder` and `sha256_of` on filer.** These are at:
  - test_content_check 1928;
  - test_filer 520, 1181, 1421, 1425, 1534, 1547, 1583, 1630, 1664, 1917, 1939, 3019, 3348, 3405, 5411, 5702, 7362,
    7824, 8651, 8690, 9447.

  `holds_the_row` now reads index's globals. A stand-in whose test drives `holds_the_row` (through `store.verify` or
  filer's restore path) is retargeted to `index`. One that drives filer's own copy and move stays on filer. The builder
  reads each and lists the retargeted ones. A wrong choice shows as that test failing.
- **Other modules' stand-ins** (`view.read_index` test_view 598, `api.read_index` ×3, `runner.read_index` ×2) are
  untouched.
- `setitem` check: none on a moved name.

**Tests:**
- `test_index` (new), `test_filer` (filer's own file), `test_reasons`, `test_store` (`verify` reaches `holds_the_row`),
  `test_scanner`, `test_api`, `test_rollover`, `test_content_check`, `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

`test_scanner` runs because the scanner's call-time imports reach the re-export. `test_api` and `test_rollover` run
because their `read_index` stand-ins (7367, 345) must still reach rollover's read through the re-export.
`test_content_check` runs because its `is_cloud_placeholder` stand-in (1928) is one of those the builder sorts.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- `git diff --color-moved` shows every moved block unchanged;
- filer's line count falls by the moved lines.

---

### P2.10 The index's readers import it; the scanner never imports filer

- **Cost:** M.
- **Tier:** Sonnet. It changes import lines and test pins, and adds a guard over `tests/import_graph.import_edges()`,
  which already exists. It parses no new source. The one store edit is a call-time import line in `verify`, outside the
  admission and `store.record`.
- **Findings:** A-2 (step 2), Q-A per P313, and A-9's CLAUDE.md sentence.
- **Depends on:** P2.9.

**Requirements:**

- **R2.10.1** — these imports come from `tracker.index` instead of `tracker.filer`. Each stays load-time or call-time
  exactly as it is.
  - **scanner** (all call time): 201 `read_index`; 223 `FILED`; 266 `moved_to`; 285 `interrupted`; 323 `FILE_MOVED`,
    `both_gone`, `moved_to`; 358 `FILE_MOVED`, `FILED`; 479 `FILE_MOVED`, `both_gone`, `moved_to`, `prepared_location`;
    811 `ensure`.

    After this the scanner imports nothing from filer. If any scanner import of filer names something outside index, stop
    and ask.
  - **review**: 82 (load) `NEEDS_REVIEW`; 524 (call) `ensure`, `read_index`.
  - **reminder** (call): 910 `NEEDS_REVIEW`, `both_gone`; 1139 `NOT_REQUESTED`, `read_index`; 1358 `read_index`.
    1410 (`iter_drops`, `unfinished_drops`, `unlistable_folders`, `unreachable_drops`) and 1914 (`numbered`) are not
    index names and stay on filer.
  - **rollover** (call): 590 `NEEDS_REVIEW`, `ensure`, `read_index` come from index, and `FilingError` stays from filer.
    763, 963 and 1233 are not index names and stay.
  - **view** (load): 93 `INDEX_HEADING`, `NEEDS_REVIEW`, `read_index` come from index, and `FilingError` stays from filer.
  - **store** `verify` (3833, call): `FILE_MOVED`, `holds_the_row` from `tracker.index`. The docstring at 3829-3830
    names `index.holds_the_row`.

  The resulting edges:
  - review imports nothing from filer, at load or call time. Its only filer imports are 82 (`NEEDS_REVIEW`) and 524
    (`ensure`, `read_index`), and all three are index names;
  - view and rollover keep filer for `FilingError`; reminder keeps it for 1410 and 1914.
- **R2.10.1a** — the words in the code that name the cycle. Each is given here, so the builder writes these and no
  others:
  - **scanner.py 809-810**, above the import that this job points at index:
    - old: `# The filer and this module are one deliberate cycle, closed at call` / `# time and asserted to stay that
      way (tests/test_layers.py).`
    - new: `# The index is tracker.index's. This module never imports the filer,` / `# which asks for this scan at call
      time (tests/test_layers.py holds both).`
  - **filer.py 7094-7096**, in `_rescan`:
    - old: `# The scan reads the index this module writes and this module asks for` / `# the scan: the cycle is
      deliberate and is imported where it is used, so` / `# neither module has to exist before the other at import
      time.`
    - new: `# The scan reads the index from tracker.index, never from this module,` / `# and this module asks for the
      scan. The import stays inside the call, where` / `# it has always been, and tests/test_layers.py holds it there.`
    - This is filer.py's only change in this job, and it is a comment.
  - **api.py 4949-4952**, `_shortlist_now`'s docstring. Its reason becomes history: after R2.10.1 review imports
    nothing from filer, so a filer import of review would close no cycle. The shortlist is still handed in, because
    this module draws the card the person picked from.
    - old: "Computed here, outside the lock the filer takes, because the filer does not import :mod:`tracker.review` -
      that would be a second call-time cycle beside the one deliberate one - and this module is above both and
      already draws the card the person picked from."
    - new: "Computed here, outside the lock the filer takes, because this module is above both and already draws the
      card the person picked from. The filer does not import :mod:`tracker.review`; when the shortlist was added that
      would have closed a second call-time cycle, and since P2.10 it would close none, but the card is still drawn
      here."
  - **tests/test_store.py 1100-1105**, the docstring of the test that exempts `verify`: "the registry's walk and the
    filer's own proof of a row's bytes" becomes "the registry's walk and the index's own proof of a row's bytes
    (`tracker.index.holds_the_row`)".
- **R2.10.2** — `tests/test_layers.py`:
  - 408-410, `test_the_filer_and_scanner_cycle_closes_only_at_call_time`, becomes
    `test_the_scanner_never_imports_the_filer_and_the_filer_reaches_it_only_at_call_time`:

    ```python
    load, call = import_edges()
    assert "filer" not in load["scanner"] and "filer" not in call["scanner"], (load["scanner"], call["scanner"])
    assert "scanner" not in load["filer"] and "scanner" in call["filer"], (load["filer"], call["filer"])
    ```

  - Add `CALL_TIME_CYCLES: frozenset[frozenset[str]] = frozenset({frozenset({"index", "store"}), frozenset({"registry", "store"}), frozenset({"scaffold", "validators"})})`,
    each with a comment naming where it closes:
    - `store.verify` asks the index at call time;
    - `store` asks the registry at call time;
    - validators' `__main__` block asks scaffold.
  - Add `test_the_only_two_module_cycles_are_the_named_call_time_ones`. It asserts that the set of unordered pairs `{a, b}`
    with `b` in `load[a] | call[a]` and `a` in `load[b] | call[b]` equals `CALL_TIME_CYCLES`, and that none of them has
    both edges at load time.
  - The module docstring's lines 14-15 ("The one deliberate cycle ... asserted to stay one.") become: "The scanner never
    imports the filer: the filer reaches it at call time, inside `_rescan()`. Three two-module cycles remain, each closing
    at call time, and :data:`CALL_TIME_CYCLES` names them."
- **R2.10.3** — `tests/test_repo_map.py` 876-884, `test_the_deliberate_cycle_is_stated_and_no_load_time_one_remains`,
  becomes `test_the_filer_calls_the_scanner_one_way_and_no_load_time_cycle_remains`. It asserts:
  - a curated `calls` edge from `tracker/filer.py` to `tracker/scanner.py`;
  - no `deliberate_cycle` edge anywhere in the graph;
  - the derived `imports_at_call` edge filer→scanner exists;
  - no `imports` or `imports_at_call` edge scanner→filer exists;
  - `"no load-time cycle"` is still in `tracker/__init__.py`'s notes.

  `tools/repo_map.py` is not changed: the `deliberate_cycle` type stays in its vocabulary (133, 154), unused.
- **R2.10.4** — `docs/repo-map.curated.json`:
  - The edge at 1059-1062 (`filer` → `scanner`, `deliberate_cycle`) becomes `"type": "calls"`.
  - **Filer's note.** "THE DELIBERATE CYCLE: _rescan() imports tracker/scanner.py at call time so a person's filing is
    scanned the moment it lands, and the scanner imports this module's index reader at call time; neither runs at load."
    becomes "ONE WAY TO THE SCANNER (P313's Q-A): _rescan() imports tracker/scanner.py at call time so a person's filing
    is scanned the moment it lands; the scanner reads the index from tracker/index.py and never imports this module."
  - **Scanner's note.** "Imports the filer's index reader at call time; the filer imports this module at call time
    inside _rescan() - the deliberate cycle, stated on the filer's node." becomes "Reads the index from tracker/index.py
    and never imports the filer; the filer imports this module at call time inside _rescan(), stated on the filer's node."
  - **`__init__`'s note.** "Every cycle the derived edges show closes through an import at call time (the map labels
    those separately), and tracker/filer.py <-> tracker/scanner.py inside _rescan() is the deliberate one." becomes
    "Every cycle the derived edges show closes through an import at call time (the map labels those separately), and
    tests/test_layers.py names the three that remain: store <-> index, registry <-> store, scaffold <-> validators."
  - **Filer's shortlist sentence** (the same node): "This module does not import tracker/review.py - that would be a
    second call-time cycle beside the deliberate one - which is why the shortlist is handed in." becomes "This module
    does not import tracker/review.py, and the shortlist is handed in by the caller that drew the card (api); when it
    was added, importing review would have closed a second call-time cycle, which since P2.10 it would not."
  - No other curated note is changed for the cycle.
- **R2.10.5** — **CLAUDE.md** (authorized by the brief; `STANDING_RULES` is not touched). Replace exactly this old text
  (CLAUDE.md lines 61-62, part of a paragraph):

  > The one deliberate cycle, filer ↔ scanner inside `_rescan()`, is a curated
  > `deliberate_cycle` edge and is stated on both nodes. There is no load-time

  with this new text:

  > The scanner never imports the filer: it reads the index from `index.py`, and
  > the filer reaches the scanner only at call time, inside `_rescan()` - a
  > curated `calls` edge, stated on both nodes (P313's Q-A). Three two-module
  > cycles remain, each closing at call time, and `tests/test_layers.py` names
  > them in `CALL_TIME_CYCLES`: store ↔ index (`store.verify`), registry ↔ store,
  > and scaffold ↔ validators (validators' `__main__` block). There is no load-time

  The rest of the paragraph ("cycle: `tracker/__init__.py` imports nothing (decision 99), ...") is unchanged.

  And replace exactly this old text (CLAUDE.md lines 13-14, the end of the "Start here" paragraph):

  > recover — why the router refuses to guess, why the request list lives in the
  > record and is edited only in the app, which import cycle is deliberate.

  with this new text:

  > recover — why the router refuses to guess, why the request list lives in the
  > record and is edited only in the app, which import cycles remain and why each
  > closes only at call time.
  `docs/architecture.md:31-33` ("The one deliberate cycle, filer and scanner through a rescan, is stated on both nodes of
  the map.") becomes "The scanner never imports the filer; the filer reaches it at call time through a rescan. The three
  call-time cycles that remain are named in `tests/test_layers.py`."
- **R2.10.6** — decision row **P316**:
  - Q-A built: the scanner never imports the filer;
  - the curated edge retyped `calls`;
  - the remaining call-time cycles named and pinned;
  - the content_check↔names, settings↔store and filer↔store cycles removed by P2.7, P2.8 and this job.

**Pin-move list:** R2.10.1a to R2.10.5, and the two stand-ins below.

**Patch sites:**
- A stand-in on `filer.read_index` or `filer.ensure` no longer reaches scanner, review, reminder, rollover or view
  once they import from index. P2.9's six `read_index` sites (none is on `ensure`):
  - **test_api 7367** (`test_a_rollover_that_could_not_read_last_years_index_says_so_in_its_reply`) and **test_rollover 345** (`_a_torn_index`) both patch
    `filer.read_index` to make **rollover's** read at rollover.py 597 fail. After R2.10.1 rollover imports
    `read_index` from index at call time, so both are retargeted to `index` (`monkeypatch.setattr(index,
    "read_index", torn)`, with `from tracker import index`). `torn` keeps raising `filer.FilingError`, which stays in
    filer.
    - The retarget keeps their reach on rollover, the scanner, review and reminder, which all now import it from index
      at call time. It drops filer's own reads, which a stand-in on filer used to replace too. Neither test needs
      those: what they assert (the rollover's last warning, `unfiled_last_year == []`) comes from rollover's read.
    - The builder shows each still bites: with the stand-in removed, the test fails. Shown once, then restored.
  - test_filer 1061, 3724, 6479 and 9292 drive filer's own reads and stay on filer.
- `view.read_index` (test_view 598) is a stand-in on view's own name and still reaches it.

**Tests:**
- `test_scanner`, `test_review`, `test_reminder`, `test_rollover`, `test_view`, `test_store`, `test_api`, `test_index`,
  `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

Each of the first seven is a changed module's own test file or a changed test file (test_api: the 7367 stand-in and
`_shortlist_now`'s docstring; test_store: `verify`'s import and the 1100 docstring). `test_filer` is not run: filer's
one change here is the comment in `_rescan` (R2.10.1a), which changes no behaviour, and ruff and the map still read it.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- `import_edges()` shows no edge scanner→filer;
- `CALL_TIME_CYCLES` equals the measured set;
- `grep -rn "deliberate cycle\|deliberate one\|cycle is deliberate" CLAUDE.md docs/architecture.md docs/repo-map.curated.json docs/repo-map.md docs/repo-map.json tracker tests`
  finds nothing. Left out on purpose: `docs/ROADMAP.md` and `pilot/` (history, never rewritten) and
  `tools/repo_map.py` (the unused `deliberate_cycle` type's label, R2.10.3);
- test_api 7367 and test_rollover 345 stand in on `index` and each fails without its stand-in;
- `python tools/repo_map.py check` is clean.

---

### P2.11 Event `TypedDict`s past the admission

- **Cost:** M.
- **Tier:** Opus, by rule (b). It annotates the store's apply path and the ledger's event shapes.
- **Findings:** B-8.
- **Depends on:** P2.10.

**Requirements:**

- **R2.11.1** — `tracker/ledger.py` gains `TypedDict`s per event family, keyed by the existing key constants' values. The
  standard library only, so ledger still imports nothing of the package but locking.
  - They are `Event` (`event`, `at`, plus the chain keys as `NotRequired`), `RowEvent`, `ScannedEvent`,
    `RulesChangedEvent`, `IntentEvent` (`MOVING`/`MOVE_ABANDONED`), `ReleaseEvent`, `KeywordEvent`, `HouseholdEvent` and
    `DraftEvent`.
  - The builder reads `store._apply` (2080-2172) and the admission's branches for each family's keys.
  - A key that is a Python keyword or not an identifier (`"from"`, `FROM_KEY`) requires the functional syntax
    (`TypedDict("IntentOp", {"op": str, "from": str, ...})`).
  - The ledger docstring gains a paragraph:
    - the dicts at the boundary stay `dict` on purpose (decision 187: a journal line is untrusted until admitted);
    - these types describe a line **after** the store's gate;
    - `ledger.new`, `append`, `read_events`, `replay` and `apply` keep `dict`, because `replay` also folds lines no gate
      read (`store.check` 3257, `store.verify` 3880, filer's readers).
- **R2.11.2** — `store._apply` (2080) narrows each event with `typing.cast` immediately after
  `_refuse_a_malformed_line(event, ...)` returns. That is the one narrowing point, with a comment naming decision 187.
  It passes the family type to these signatures, which change from `dict` to it:
  - `_write_intent(conn, engagement_id, event: IntentEvent, seq)` (1586);
  - `_apply_rules_event(conn, engagement_id, event: RulesChangedEvent)` (2174);
  - `_write_engagement_info` (1636) and `_write_household_info` (1653), which take the info partials. Each gets a
    `TypedDict` only if one fits without a new mypy error; otherwise `dict` stays and the report says why.

  `_write_documents`, `_write_status` and `_write_rule` keep their row-shaped `dict`s. Rows are `records`' shapes, not
  event families (B-8's rows are a later phase's, with B-4).
- **R2.11.3** — no function in the admission closure changes. `ledger.op_ends(op: dict)` is in the closure and keeps
  its annotation. `ADMISSION_PIN[5]` is unchanged, and `test_admission_version_changes_with_the_admission` proves it.
- **R2.11.4** — `typecheck.py check` passes with no new error and no `# type: ignore` added. If the store's errors fall,
  `update` lowers the baseline in the same commit.

**Pin-move list:** none.

**Patch sites:**
- `tracker.ledger`: 10 stand-ins.
- `tracker.store`: 49 stand-ins.

None is on a function whose signature changes, and annotations do not change what a stand-in replaces.

**Tests:**
- `test_ledger`, `test_store`, `test_typecheck`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

No golden run: nothing moves, and annotations only.

**Accept when:**
- the gate passes;
- `ADMISSION_PIN` is unchanged;
- the baseline does not rise;
- `git diff` touches only annotations, the new types, the `cast` lines and docstrings.

---

### P2.12 `tools/corpus.py`, the case tables into `tests/routing_cases.py`

- **Cost:** M.
- **Tier:** Sonnet. It touches tools and test data only. No tracker module changes.
- **Findings:** E-9, plus the two tool type errors (P2.1).
- **Depends on:** P2.11.

**Requirements:**

- **R2.12.1** — new `tools/corpus.py` (a tool, imported, with no `__main__`):
  - From `tools/backtest.py`, as public names: `harness` (202-212, `_harness`), `document_path` (215), `linked_under_a_neutral_name`
    (230), `temp_pointed_at` (275), `unknown_catalog` (296), `outside_the_repository` (621) and `corpus_folder`
    (633, `_corpus`).
  - From `tests/test_real_corpus.py`: `Expectation` (64), `read_expectations` (67-98), `real_corpus` (101-110) and
    `catalog_rows` (113-123), with the imports they need (the settings columns, `real_corpus_dir`, `manifest.validated`,
    `templates.template_items`, `dataclasses.replace`).

  - **The four names the moved helpers read** (review 2, S25). They are defined in backtest today, and backtest will
    import corpus, so a corpus that imported them back from backtest would be a load-time cycle between two tools.
    They move to corpus, each with its comment, byte for byte:

    | Name | backtest at `286b535` | Read by (moving) | Read by (staying in backtest) |
    |---|---|---|---|
    | `BacktestError` (the class) | 174-175 | `document_path`, `outside_the_repository`, `corpus_folder` | 10 of its 14 raises (the other 4 move) and the `except` at 698 |
    | `NEUTRAL_STEM` | 118-123 | `linked_under_a_neutral_name` | none (prose only, line 26) |
    | `CATALOGS` | 115-116, built from `FORM_TYPES` | `unknown_catalog` | `write_skeleton` (533-534) and `collect`'s `choices` (685) |
    | `OUT_FLAG` | 144 | `outside_the_repository` | `run`'s and `collect`'s `add_argument` (680, 687) |

    - backtest imports `BacktestError`, `CATALOGS` and `OUT_FLAG` from `tools.corpus` as a use: its own code reads
      them. So `tools/reader_bench.py:137` (`BacktestError` from `tools.backtest`) and test_backtest's imports of
      `BacktestError`, `CATALOGS` and `OUT_FLAG` from `backtest` keep working unchanged.
    - backtest does not import `NEUTRAL_STEM`: nothing of its own reads it, and a name kept only for a test would be a
      facade with no job to remove it. `tests/test_backtest.py:34` takes `NEUTRAL_STEM` out of its `from backtest
      import (...)` and imports it with `from tools.corpus import NEUTRAL_STEM`. backtest's module docstring at 26
      still names it; it becomes ``tools.corpus.NEUTRAL_STEM``.
    - corpus imports its tracker names directly: `FORM_TYPES` and `template_items` from `tracker.templates`,
      `SCRATCH_ENV` from `tracker.ocr`, `inside_the_app`, `real_corpus_dir` and the expectations columns from
      `tracker.settings`, `RequestItem` and `validated` from `tracker.manifest`. backtest drops each of those it no
      longer reads (ruff says which; at `286b535`, `SCRATCH_ENV`, `inside_the_app` and `contextmanager` are read only
      by moving code).
    - corpus has no `sys.path` insert: it is always imported as `tools.corpus` by a tool or a test that has put the
      repository on the path first (backtest after its own insert at 93-95).
    - **One class, two names.** `tests/test_corpus.py` (R2.12.6) asserts `backtest.BacktestError is
      corpus.BacktestError`, with `backtest` imported as test_backtest imports it (bare, after its `sys.path` insert)
      and corpus as `tools.corpus`. reader_bench's `tools.backtest` and test_backtest's bare `backtest` are two copies
      of the backtest module today, and each had its own `BacktestError`; after the move both re-import corpus's one
      class.

  `harness()` returns `(catalog_rows, read_expectations)` from this module, not from a test module.

  Its docstring says why it exists: the harness both tools share, and the one reader of the expectations file
  (decision 70, 185). It also says that `real_corpus` reads only what `ENV_REAL_CORPUS` names, as before.
- **R2.12.2** — the users point at the new names:
  - backtest uses `tools.corpus` (and its `_harness` and the moved privates are deleted);
  - `tools/reader_bench.py` 133-146 imports `harness`, `document_path`, `linked_under_a_neutral_name`,
    `outside_the_repository`, `temp_pointed_at`, `unknown_catalog`, `corpus_folder` from `tools.corpus`, and
    `EXPECTATIONS_FILENAME`, `READING_IMAGE`, `READING_OCR`, `BacktestError`, `write_json` still from `tools.backtest`.
    Its docstring 36-43 follows;
  - `tests/test_real_corpus.py` imports its four from `tools.corpus`;
  - `tools/vocab_report.py` 248 imports `real_corpus` from `tools.corpus`;
  - **`tests/test_single_source.py` 967-976**, `test_the_tools_ask_one_rule_whether_a_path_is_inside_the_repository`
    (review 2, S26). Its second loop asserts `"inside_the_app(" in read(f"tools/{name}")` for
    `("backtest.py", "learned_keywords.py")`. backtest's one call (628) is inside `_outside_the_repository`, which
    moves, so the tuple at 975 becomes `("corpus.py", "learned_keywords.py")`. The docstring is unchanged, and the
    first loop (every tools/*.py, corpus.py included) still holds no tool to spelling the rule itself;
  - `docs/tools.md` follows wherever it names a moved private, and where it says where the cases live (with R2.12.3):
    - line 11, "reconstructed case in `tests/test_catalog.py`", becomes "reconstructed case in `tests/routing_cases.py`";
    - line 25, "Every case in `tests/test_catalog.py` carries the decision that introduced it", becomes "Every case in
      `tests/routing_cases.py` carries the decision that introduced it, and `tests/test_catalog.py` runs it under an
      id that names it";
    - the paragraph at 29-32 ("The workbook cases' rows (`XLSX_CASES`), ... the names the tools import.") becomes: "The typed cases (`CASES`), the workbook cases' rows (`XLSX_CASES`), the blank
      forms' placements (`EXPECT`) and the lines of two printed forms sit in `tests/routing_cases.py`, which the suites
      import and the report reads. The harness the backtest and the reader bench share, and the one reader of the
      expectations file, is `tools/corpus.py`. No tool imports a test file."
    - line 39 ("`tests/test_real_corpus.py` routes every row of that file") stays true and is left.
- **R2.12.3** — `CASES` (test_catalog.py 1524-1533) and the case blocks it is built from (`_DECISION_62` at 55 through
  `_DECISION_146`, and the helper lists between them, 55-1522) move to `tests/routing_cases.py`. The exceptions are a
  block or helper that a test in test_catalog also reads, and `k1_received_lines` (1367) if a test uses it. Those stay
  importable from where the tests read them, and the builder lists them.

  - **routing_cases' imports.** The moved blocks call `tests.samples`' line makers (`brokerage_cover_lines`, the
    `scanned_*_lines` family and the others test_catalog 30-37 imports for them; test_catalog 1334-1342 is one use).
    routing_cases imports exactly the ones the moved blocks use from `tests.samples`, a helper module, which
    `tests/test_suite_shape.py` allows. test_catalog drops those it no longer uses itself.
  - **routing_cases' docstring.** Its second paragraph (lines 9-12, "They are moved with their words, ... so
    `tools/vocab_report.py` and `tools/backtest.py`, which import `CASES`, `XLSX_CASES`, `EXPECT` and the corpus
    readers from the suites by name, are untouched.") is now false. It becomes: "They are moved with their words, and
    each suite imports back what it uses. Since P2.12 the typed cases (`CASES`) live here too, and
    `tools/vocab_report.py` imports `CASES`, `XLSX_CASES` and `EXPECT` from this module; the corpus readers are
    `tools/corpus.py`'s. No tool imports a test file." The first line and the third paragraph name the typed cases
    beside the workbook cases.

  test_catalog imports `CASES` from routing_cases. The parametrize ids `f"d{c[0]}-{c[2]}"` (1536) and
  `f"d{c[0]}-{c[2]}-{c[1]}"` (1544) are unchanged, so decision 70's `-k d67`-style selection still works.
  `pytest --collect-only -q tests/test_catalog.py` prints the same ids before and after.
- **R2.12.4** — `tools/vocab_report.py`:
  - 222 imports `EXPECT` from `tests.routing_cases` (not `tests.test_irs_forms`);
  - 310 imports `CASES, XLSX_CASES` from `tests.routing_cases`;
  - after this no tool imports a `tests/test_*.py` module (`grep -rn "from tests.test_" tools/` finds nothing);
  - `INPUT_PATHS` (107-116) is what the report is a function of, so it follows what the report now reads:
    - `"tests/test_catalog.py"` ("the cases"), `"tests/test_irs_forms.py"` ("the corpus's expected placements") and
      `"tests/test_real_corpus.py"` ("how the firm's own documents are read") **go**. The report reads nothing from
      them any more: the cases and `EXPECT` are routing_cases', and the corpus reader is tools/corpus.py's.
    - `"tests/routing_cases.py"`'s comment becomes `# the typed cases, the workbook cases, the blank forms'
      placements and two printed forms`.
    - `"tools/corpus.py"` joins, with `# how the firm's own documents are read`.
    - A change to a test suite then no longer makes the report stale, which is right: the report is not a function of
      it. test_vocab_report 251 and 259 loop over `INPUT_PATHS` and need no change.
  - **The report's own words name where the cases live** (review 2, S32), and both follow the move:
    - the module docstring, lines 6-7: "the IRS forms in ``tests/irs/`` and the reconstructed cases in
      ``tests/test_catalog.py`` actually reach" becomes "the IRS forms in ``tests/irs/`` and the reconstructed cases in
      ``tests/routing_cases.py`` actually reach";
    - `render_markdown`'s sentence at 430-431: "IRS forms in `tests/irs/` and the reconstructed cases in
      `tests/test_catalog.py`, " becomes "IRS forms in `tests/irs/` and the reconstructed cases in
      `tests/routing_cases.py`, ". It is the sentence `docs/vocab-coverage.md` line 5 carries.

  Then `python tools/vocab_report.py build`. The report's content changes in exactly that one generated sentence (and
  in the inputs it lists and hashes); every count, catalog, keyword and hit is unchanged. The builder shows
  `git diff docs/vocab-coverage.md` and `git diff --stat docs/vocab-coverage.json` in the report.
  `tests/test_vocab_report.py` 271 compares the rendered page with the committed one, so the rebuild is what keeps it
  passing.
- **R2.12.5** — the type check:
  - the two tool type errors:
    - `tools/reader_bench.py:245`: `_ABLATION_CHANGES` (236-238) is annotated `dict[str, dict[str, object]]`;
    - `tools/vocab_report.py:317`: `XLSX_CASES`'s element type is annotated where it is defined
      (`tests/routing_cases.py` 528), not cast at the reader.
  - **`tools/corpus.py` enters the check with no baseline entry, so it must have no error** (review 2, S27). mypy does
    not check tests/, so `read_expectations`' `rows = []` (test_real_corpus.py 86) carries no error today. In
    tools/corpus.py it is `Need type annotation for "rows"  [var-annotated]`. So that one line becomes
    `rows: list[Expectation] = []`, the only departure from "byte for byte" in the moved code. Measured at
    `286b535` with a prototype of corpus.py (the moved helpers, the four names of R2.12.1 and test_real_corpus'
    four): with that line annotated, mypy reports no error in tools/corpus.py, and ruff passes.

  `typecheck.py update` lowers the baseline by 2, and tools/corpus.py has no entry (0 errors).
- **R2.12.6** — `tests/test_corpus.py`, corpus' own test file (CLAUDE.md: one component per module, each with its own
  test file; review 2, S32). Made-up inputs only, under `tmp_path`, and nothing that reads `ENV_REAL_CORPUS`
  (decision 185):
  - `test_the_backtests_error_is_the_corpus_own` (R2.12.1's "One class, two names");
  - `test_a_row_with_no_year_is_refused_by_its_number_and_never_its_name`: `read_expectations` on a made-up file whose
    second row has no year raises `ValueError` naming "row 2" and the column, and never the document the row names;
  - `test_a_bad_catalog_is_said_by_its_row_and_never_its_value`: `unknown_catalog` on made-up rows names the row
    number and not the value;
  - `test_a_report_inside_the_repository_is_refused`: `outside_the_repository(REPO / "report.json")` raises
    `BacktestError`, and a `tmp_path` path is returned resolved.

  The map then draws corpus' **tested by** edge from this file. test_backtest, test_reader_bench and test_real_corpus
  also import it, which the map draws as **exercised by**, not coverage.

**Pin-move list:**
- `tests/test_vocab_report.py` lines that name `INPUT_PATHS` or the borrowed modules, if any. The builder greps
  `routing_cases\|test_catalog\|test_irs_forms\|test_real_corpus` in it;
- `tests/test_suite_shape.py`:
  - `test_no_helper_module_or_conftest_imports_a_test_file` must still pass, so routing_cases imports no test file;
  - `test_every_helper_module_is_imported_by_a_test_file` still holds;
- the curated nodes for `tools/corpus.py` (a tool node), backtest and reader_bench;
- `tests/test_single_source.py:975`, the tool tuple of the one-rule test (R2.12.2, S26);
- `tests/test_backtest.py:34`, `NEUTRAL_STEM` imported from `tools.corpus` (R2.12.1, S25);
- `tests/test_corpus.py`, new (R2.12.6).

**Patch sites:**
- `tools.backtest`: 2 stand-ins (`route_one`, test_backtest 396 and 437), which stay. `route_one` does not move.
- `tools.reader_bench`: 7 stand-ins (`survey`, `route_file`, `_run_firm`), none on a moved name.
- `tools.vocab_report`: 7 stand-ins, none on a moved name.
- `tests.test_real_corpus` and `tests.test_catalog`: 0.

**Tests:**
- `test_corpus` (new), `test_backtest`, `test_reader_bench`, `test_vocab_report`, `test_real_corpus`, `test_catalog`,
  `test_irs_forms`, `test_suite_shape`, `test_typecheck`, `test_tripwire`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`.

`test_tripwire` runs because the corpus reader moved, and it guards the real corpus's variable (test_tripwire 70).
`test_catalog` and `test_irs_forms` route through the router. Their own files run because they changed, and they are
the evidence that no routing changed.

**Accept when:**
- the gate passes;
- `test_catalog`'s collected ids are identical;
- the vocabulary report is current, and its content differs only in the one sentence R2.12.4 names (and its listed
  inputs and hashes);
- `typecheck.py check` passes with tools/corpus.py at 0 errors;
- `backtest.BacktestError is corpus.BacktestError` (test_corpus);
- `tools/backtest.py check` against `docs/backtest-baseline.json` is owed to the office PC (section 6);
- the baseline is lower by 2.

---

### P2.13 Facades removed: bounds, hold, the spelling sentence

- **Cost:** M.
- **Tier:** Opus, by rule (b). Retargeting `records.<bound>` to `bounds.<bound>` inside store's admission
  functions changes their source, which re-pins `ADMISSION_PIN[5]`. It also edits one filer import (284), which moves
  no code out of filer, so rule (a) is not what makes it Opus (review 3, note).
- **Findings:** 5.1 (4), for P2.4, P2.5 and P2.6's facades; review 2's S28 (the layer pins).
- **Depends on:** P2.12.

**Requirements:**

- **R2.13.1** — bounds:
  - Every reference to a bounds name through records (`records.X` and `from tracker.records import X`, with X one of the
    81) is pointed at `tracker.bounds`, in tracker/ and tests/. At `286b535` these are:
    - store (23 `records.` reads), api 6, manifest 2 `records.` reads and 17 from-imported names, view 2 (147,
      `host_problem` and `stamp_problem`), filer 1 (284, `typed_identifier_problem`);
    - test_store 305 (mostly `ADMISSION_PIN` key strings, which are history in versions 2-4 and regenerated in 5),
      test_records 73, test_manifest 6, test_api 4, test_ledger 3, test_golden 1.
  - Records then deletes its facade import of the names it does not use itself. The names records' remaining code reads
    stay imported, as a use.
  - Delete `test_the_records_re_export_is_the_bounds_own`.
  - The admission's store functions now read `bounds.X`, so re-pin `ADMISSION_PIN[5]`. Every digest changes only by
    `records.` becoming `bounds.` in a source line (store.py:1713's docstring line is one of them), and the builder
    shows one diff of an old and a new closure source to prove it.
    - A constant store read as `records.X` was keyed `tracker.records.X` (R2.4.5). Read as `bounds.X` it is keyed
      `tracker.bounds.X`, so those keys rename with the same digest. Where P2.4 already added a `tracker.bounds.X` key
      for the same constant, the two become one. The builder lists the keys that renamed and the ones that merged.
      At `286b535` version 5 holds two such store reads by name, `tracker.records.host_problem` and
      `tracker.records.name_problem`.
    - `tracker.records.MAX_EXPECTED_COUNT` and `tracker.records.rule_row_problem` stay, as in R2.4.5.
    - Version 5 keys no `tracker.manifest.` part (measured at `286b535`: its keys are layout 66, ledger 51,
      reasons 1, records 114, store 9), so manifest's retargeted reads move no digest.
  - `test_content_check.py:2378`'s stand-in on `records.date_pattern_problem` is re-read. If it means `rule_row_fault`'s
    read, it stays on records, because records still imports the name for its own use. Otherwise it moves to bounds.
  - **The prose that names a bound through records** (review 2, S33) follows the code, `records.X` becoming `bounds.X`
    for the bounds name only. At `286b535`:
    - `docs/repo-map.curated.json` 25 (manifest node: `records.COUNT_BOUNDS`, `records.date_pattern_problem`), 65
      (ledger: `records.host_problem`), 97 (api: `records.MAX_EXPECTED_COUNT`, `records.MAX_SIZE_KB`), 422 (view:
      `records.host_problem`, `records.stamp_problem`) and 437 (store: `records.name_problem`);
    - `docs/storage.md` 89-90 (`records.host_problem`, `records.stamp_problem`);
    - docstrings in tracker/: ledger.py 108-109, manifest.py 957 and 1212, store.py 1713, settings.py 641
      (`records.text_problem`);
    - docstrings in tests/: test_ledger.py 980-981, test_store.py 5752 (`records.identifier_problem`).

    Left as written: the pin's version notes (test_store 2790-2800, which record what version 5 was at P301), the key
    strings of versions 2-4, and the curated notes' `records.` names that are not bounds (`records.rule_row_fault`,
    `records.RULE_FIELDS`, `records.identifier_key()` and the like stay true). The builder finds these with the scan
    in the accept below, which lists only bounds names.
- **R2.13.2** — the layer pins (review 2, S28; settled as option (b) by `threads/P2/006`):
  - **Why the edge is new.** After R2.13.1 store reads eight bounds names (`MAX_STAGE`, `count_problem`,
    `digest_problem`, `host_problem`, `name_problem`, `stamp_problem`, `text_list_problem`, `text_problem`) through
    `from tracker import bounds`, and manifest from-imports 17. Both gain `bounds` at load time. bounds is L0 and
    imports only `layout`, so the edge points down and no layer rule is broken. It widens two pins that say more than
    the layer rule.
  - **Why records stays in both sets.** Store still reads records' own shapes (`CANDIDATE_SEP`, `RULE_FIELDS`,
    `entry_from_json`, `IndexEntry` and more), and manifest still imports `COL_IDENTIFIER`, `EngagementInfo`,
    `StatusUpdate` and `rule_row_fault` from it. Both still need it, so neither set drops it.
  - `tests/test_layers.py:337`:
    - old: `assert load["store"] == {"checkpoint", "ledger", "locking", "records"}, load["store"]`
    - new: `assert load["store"] == {"bounds", "checkpoint", "ledger", "locking", "records"}, load["store"]`
    - The test at 332, `test_the_store_imports_only_the_record_the_journal_the_lock_and_the_checkpoint`, becomes
      `test_the_store_imports_only_the_bounds_the_record_the_journal_the_lock_and_the_checkpoint`. Its docstring gains
      one sentence after "...which is below it and imports nothing.": "P317 adds the bounds, which are L0 and read no
      file."
  - `tests/test_layers.py:351`:
    - old: `assert load["manifest"] == {"records"}, load["manifest"]`
    - new: `assert load["manifest"] == {"bounds", "records"}, load["manifest"]`
    - The test at 340, `test_the_manifest_imports_the_record_and_nothing_else`, becomes
      `test_the_manifest_imports_the_bounds_and_the_record_and_nothing_else`. Its docstring's last clause, "so at load
      time it names the shapes it validates into and nothing else", becomes "so at load time it names the shapes it
      validates into and the bounds it holds them to (P317), and nothing else".
  - `tests/test_layers.py`'s module docstring:
    - 44: "``manifest`` imports ``records`` and nothing else at load time, and" becomes "``manifest`` imports
      ``bounds`` and ``records`` and nothing else at load time, and";
    - 88-89: "it imports ``records``, ``ledger``, ``locking`` and (since decision 159) ``checkpoint``, and nothing else
      of the package" becomes "it imports ``bounds`` (P317), ``records``, ``ledger``, ``locking`` and (since decision
      159) ``checkpoint``, and nothing else of the package". The rest of the sentence is unchanged.
  - **CLAUDE.md 209-211** (a SPEC-named edit, which brief 000 authorizes; the standing rules' wording is untouched):
    - old:
      ```
        (its `__main__` alone reaches `page`); `store` imports `ledger`, `locking`,
        `records` and `checkpoint` and nothing else; `manifest` imports `records` and nothing else
        at load time, and reaches `store`, `ledger` and `locking` at call time
      ```
    - new:
      ```
        (its `__main__` alone reaches `page`); `store` imports `bounds`, `ledger`,
        `locking`, `records` and `checkpoint` and nothing else; `manifest` imports
        `bounds` and `records` and nothing else at load time, and reaches `store`,
        `ledger` and `locking` at call time
      ```
    - The rest, from "(decision 104 gave it the request list's writes)", is unchanged.
  - **store.py's prose on its load imports.** None of it is in an admission function (version 5 keys none of
    `_positional_root`, `_drop_the_checkpoint` or `_write_csv`), so it moves no digest:
    - 166-167, "``records``, ``ledger``, ``locking`` and the standard library" becomes "``bounds``, ``records``,
      ``ledger``, ``locking``, ``checkpoint`` and the standard library";
    - 935-936, "imports ``records``, ``ledger`` and ``locking`` and nothing else at load time" becomes "imports
      ``bounds``, ``records``, ``ledger``, ``locking`` and ``checkpoint`` and nothing else at load time";
    - 2648-2649, "the store imports only the record, the journal, the lock and the checkpoint at load" becomes "the
      store imports only the bounds, the record, the journal, the lock and the checkpoint at load";
    - 3595-3596, "the store imports the record, the journal and the lock and nothing else at load time (decision 101)"
      becomes "the store imports the bounds, the record, the journal, the lock and the checkpoint and nothing else at
      load time (decision 101, P317)".

    The three that omit the checkpoint are stale at `286b535` (decision 159 added it). They are corrected in the same
    edit because each is being rewritten anyway.
  - **manifest.py 59-60**: "imports :mod:`tracker.records` and nothing else of the package at load time" becomes
    "imports :mod:`tracker.bounds` and :mod:`tracker.records` and nothing else of the package at load time".
  - **The curated notes** (`docs/repo-map.curated.json`):
    - 25 (manifest): "so the module still imports tracker/records.py and nothing else at load time
      (tests/test_layers.py)" becomes "so the module still imports tracker/bounds.py and tracker/records.py and nothing
      else at load time (tests/test_layers.py, P317)";
    - 437 (store): "It imports records, ledger and locking and nothing else of the package at load time" becomes "It
      imports bounds, records, ledger, locking and checkpoint and nothing else of the package at load time (P317)", and
      "so store still imports only records, ledger and locking at load" becomes "so store still imports only bounds,
      records, ledger, locking and checkpoint at load".
- **R2.13.3** — hold:
  - store 861, 940, 966 (`from tracker.settings import resolved`, call time; 861 also imports `clients_root`, which
    stays on settings) and 2247 (`from tracker.settings import refuse_a_write_while_reading`, call time) import from
    `tracker.hold`;
  - store 983 and 1097 are call-time `from tracker import settings` lines, inside `_engagement_key` and the held
    record read. Their only uses are 985 and 1103 (`settings.held`). Both lines become call-time
    `from tracker import hold`, still inside their functions, and 985 and 1103 read `hold.held`. So store's load set
    stays as R2.13.2 pins it, and a load-time `from tracker import hold` in store would fail that pin (review 3, S35);
  - content_check 2352 (`settings.resolved`) uses `tracker.hold`;
  - registry 906 (`from tracker.settings import one_reading`, call time) uses `tracker.hold`;
  - the docstring and comment references `:func:\`tracker.settings.held\`` (store 1090),
    `:func:\`tracker.settings.one_reading\`` (store 2244, api 6685) and `:func:\`tracker.settings.resolved\``
    (content_check 2345) name `tracker.hold`. None is in an admission function (version 5 keys no part that reads the
    hold), so none moves a digest;
  - resident.py:47's docstring names `hold.one_reading()`;
  - runner.py 273-274 (`one_household`, `one_reading`) are members of the parenthesised load-time
    `from tracker.settings import (...)` at 257-275. They leave it for a `from tracker.hold import one_household,
    one_reading` line of their own, in ruff's order (review 3, S35);
  - api.py 339 (`one_reading`) is a member of the parenthesised `from tracker.settings import (...)` at 325-340. It
    leaves it for a `from tracker.hold import one_reading` line, in ruff's order;
  - resident's other uses, and any read the accept's checks still find in tracker/, use `tracker.hold`.
  - **The tests' uses**, at `286b535`, under the three names the suite gives the settings module (section 3):
    - test_settings 47 lines through `data_rules.` (review 2, S23): 885, 895, 915, 917, 919, 922, 927, 929, 938, 959,
      966, 974, 975, 984, 1007, 1009, 1010, 1014, 1015, 1031, 1034, 1042-1044, 1047-1049, 1068-1073, 1077-1079,
      1081-1085, 1087, 1088 and 1100-1104 (`one_reading`, `one_household`, `resolved`, `held`,
      `refuse_a_write_while_reading` and the `HOLD_*`/`WRITE_WHILE_*` constants). They read `hold.` through
      `from tracker import hold`, which R2.6.4 already added to test_settings. A test among them that R2.6.5 moved to
      test_hold reads `hold.` there already, and the builder says which of these lines it found in test_hold;
    - test_store 5332 (from-import of `one_reading`), 5540, 5557, 5581 (`one_household`) and the stand-in at 5626-5633
      (`held`);
    - test_runner 722, 5322 (`HOLD_*`), 4340 (`one_reading`), 4343 and 5526 (`resolved`, with the stand-ins at 4356
      and 5551), and 5578's docstring;
    - test_manifest 1322, 1338, 1366, 1378; test_content_check 2715, 2752; test_registry 822; test_api 7938;
      test_filer 10058 (`one_household`); test_page_rows 34 (from-import of `one_reading`).

    The stand-ins move to `hold`, and their callers now read `hold.`. Settings' own calls already read `hold.held`.
    The builder repeats the grep below at the base of the job and lists any line it finds that this list misses.
  - settings deletes its re-export, and `test_the_settings_re_export_is_the_holds_own` is deleted.
  - The curated notes that name the hold through settings follow the code: `settings.resolved` (content_check and
    store nodes), `settings.one_reading` (registry, runner and api nodes; api's twice), `settings.one_household`
    (runner) and `settings.held` (store) become `hold.`. The builder greps them in `docs/repo-map.curated.json`,
    `docs/runbook.md` and `docs/architecture.md`, and the accept below checks it.
- **R2.13.4** — the spelling sentence: test_api 4423, 4479, 11321 and api.py:236 import `ONE_WORD_SPELLING` from
  `tracker.records`. filer.py:275 does too, but in P2.14, which edits filer anyway. names keeps its re-export until
  P2.14, and P2.14 deletes it.
- **R2.13.5** — decision row **P317**:
  - the store and the manifest import `bounds` at load time: the narrow store of decision 101 widens by one L0
    module, and the manifest's load set of decision 103 by the same one;
  - why it keeps decision 101's point: bounds is in the lowest layer, imports only `layout` and reads no file, so the
    store still depends on nothing that walks folders, moves files or opens a workbook;
  - why not keep the reads through records (review 2's option (a)): it would leave a permanent facade for two readers,
    against section 5.1's rule that the facade job points every importer at the new home;
  - the pins that moved: test_layers 337 and 351, test_layers' docstring, and CLAUDE.md's conventions sentence.

**Pin-move list:**
- R2.13.1 to R2.13.4, and `ADMISSION_PIN[5]` (keys renamed or merged, digests changed only by `records.` → `bounds.`;
  `ADMISSION_VERSION` stays 5);
- `tests/test_layers.py` 332-337 and 340-351 (the two load pins, their names and docstrings) and the module docstring
  at 44 and 88-89 (R2.13.2);
- CLAUDE.md 209-211 (R2.13.2);
- store.py 166-167, 935-936, 2648-2649, 3595-3596 and manifest.py 59-60 (R2.13.2);
- `docs/repo-map.curated.json` 25 and 437 for the load sets (R2.13.2), and 25, 65, 97, 422, 437 for the bounds names
  (R2.13.1), with `docs/storage.md` 89-90;
- the deleted identity tests `test_the_records_re_export_is_the_bounds_own` and
  `test_the_settings_re_export_is_the_holds_own`.

**Patch sites:**
- `tracker.records`: the 2 (R2.13.1).
- `tracker.settings`: the three hold stand-ins (R2.13.3).
- `python tools/patch_sites.py report tracker.hold` and `report tracker.bounds` are run after the change, and listed in
  the report.

**Tests:**
- `test_records`, `test_bounds`, `test_store`, `test_manifest`, `test_api`, `test_view`, `test_ledger`, `test_golden`,
  `test_hold`, `test_settings`, `test_content_check`, `test_registry`, `test_resident`, `test_runner`, `test_filer`,
  `test_page_rows`;
- the guards `test_layers` (its two load pins move here), `test_single_source`, `test_repo_map`, `test_tripwire`.

Each is a changed module's own test file or a changed test file. test_filer runs as filer's own file: filer.py:284
from-imports `typed_identifier_problem` from records, and R2.13.1 points it at bounds (round 2 said test_filer was not
run here, which that import already contradicted). Its line 10058 reaches the hold through settings as well.
test_page_rows runs only because its line 34 does.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- `ADMISSION_VERSION` is still 5;
- `load["store"] == {"bounds", "checkpoint", "ledger", "locking", "records"}` and
  `load["manifest"] == {"bounds", "records"}` hold in test_layers, and CLAUDE.md 209-212 reads as R2.13.2's new text;
- no `# noqa: F401 - re-exported until P2.13` remains (`grep -rn "until P2.13" tracker` finds nothing);
- the alias-aware grep
  `grep -rnE "\b(settings|settings_module|data_rules)\.(one_reading|one_household|held|resolved|refuse_a_write_while_reading|HOLD_HOUSEHOLD|HOLD_READING|WRITE_WHILE_HOLDING|WRITE_WHILE_READING|_HELD|_HOLDING)\b" --include=*.py tracker tests`,
  and the same pattern over `docs/repo-map.curated.json docs/runbook.md docs/architecture.md`, find nothing outside
  test_store's old pin versions (3035 in version 2; 3287, 3292, 3297, 3301 in 3; 3557, 3562, 3567, 3571 in 4);
- no `from tracker.settings import` in tracker/ or tests/ imports one of the nine hold names R2.6.2 lists. This is
  read from each file's AST, every `ast.ImportFrom` whose `module` is `tracker.settings` and each of its `names`, so a
  member of a parenthesised import counts (review 3, S35). The builder writes the scan in its scratch area and puts its
  output in the report. Also, `patch_sites.py report tracker.settings` lists no stand-in on one of them;
- a scan for `records.<name>`, with `<name>` one of bounds' public names, in comments, strings and docs
  (`tracker/`, `tests/`, `tools/`, `docs/repo-map.curated.json`, `docs/storage.md`, `docs/architecture.md`,
  `docs/runbook.md`) finds only test_store's pin key strings in versions 2-4, its version notes at 2790-2800, and the
  two keys R2.4.5 keeps (`tracker.records.MAX_EXPECTED_COUNT`, `tracker.records.rule_row_problem`, and their names in
  test_store 3964-3971). The builder writes the scan in its scratch area (not the repository) and puts its output in the
  report.

---

### P2.14 Facades removed: the index, and decision 100's shim (A-12)

- **Cost:** M.
- **Tier:** Opus, by rule (a). It edits filer's imports and its uses of `_CANDIDATE_SEP`, and removes filer's re-exports.
- **Findings:** 5.1 (4) for P2.9's facade, and A-12.
- **Depends on:** P2.13.

**Requirements:**

- **R2.14.1** — the index:
  - api.py 121-150 and runner.py:187 import from `tracker.index` the index names they take from filer today (api:
    `DUPLICATE`, `FILE_MOVED`, `FILED`, `NEEDS_REVIEW`, `NOT_REQUESTED`, `both_gone`, `ensure`, `marked_missing`,
    `moved_to`, `read_index`; runner: `NEEDS_REVIEW`, `ensure`, `read_index`). Their filer-only names stay on filer.
  - So do the tests that import index names through filer, which the builder greps.
  - The stand-ins on `filer.read_index` left after P2.9 and P2.10 are re-read: one that meant api's or runner's read
    moves to the module that now holds the name.
  - Filer deletes its facade import of the index names it does not use, and `test_the_filers_re_export_is_the_indexs_own`
    is deleted.
- **R2.14.2** — A-12, decision 100's shim (filer.py 280-312 and 456):
  - **filer:**
    - filer's `parse_evidence  # noqa: F401` is deleted;
    - `_CANDIDATE_SEP = CANDIDATE_SEP` (456) is deleted, and filer's six uses (5512, 5514, 5623, 6462, 7770, 7771) read
      `CANDIDATE_SEP`;
    - the shim's comment (280-312) is reduced to what filer still imports from records and why;
    - `tests/builders.py:30` imports `CANDIDATE_SEP` and `IndexEntry` from `tracker.records`, and `NEEDS_REVIEW` from
      `tracker.index`. Its use at 147 follows;
    - `test_the_filers_old_private_separator_is_the_records_own` (test_records) is deleted.
  - **content_check:**
    - content_check deletes the six names of decision 100 it re-exports and does not use (`EVIDENCE_PLACES`,
      `EVIDENCE_RULES`, `RULE_FILENAME`, `RULE_REFUSED`, `format_evidence`, `parse_evidence`; its import at 112);
    - the tests that import decision-100 names through content_check (builders `format_evidence`, test_api,
      test_content_check, test_filer, test_review, test_router) import them from `tracker.records`.
  - **The other test imports:**
    - the tests that import `IndexEntry` through filer (builders, passes, test_api ×5, test_errors, test_page_rows,
      test_reminder ×5, test_rollover ×2, test_runner) import it from `tracker.records`;
    - test_ledger imports `ledger_key` from `tracker.records`.
  - **The identity test.** `tests/test_records.py`'s `RE_EXPORTED` (173-200) loses its `filer` and `content_check` rows.
    The `router` and `manifest` rows stay: those modules use the names themselves. Its docstring says decision 100's
    shim is retired, and P318 names the commit.
  - Manifest's unused layout re-exports (`WINDOWS_ILLEGAL_CHARS_TEXT`, `WINDOWS_RESERVED_NAMES`,
    `WINDOWS_RESERVED_NAMES_TEXT`, `is_reserved_name`) are decision 137's and 188's, not decision 100's, and are left.
- **R2.14.3** — the spelling sentence: filer.py:275 imports `ONE_WORD_SPELLING` from `tracker.records`. names deletes
  its re-export, and `tests/test_names.py`'s `test_the_spelling_sentence_is_the_records_own` (R2.5.3) is deleted
  with it.
- **R2.14.4** — decision row **P318**:
  - decision 100's "for one release" shim retired (A-12);
  - phase 2's facades all removed;
  - the identity-pin pattern stays for later phases' re-exports.

**Pin-move list:** R2.14.1 to R2.14.3.

**Patch sites:**
- `tracker.filer`: the stand-ins re-read in R2.14.1.
- `tracker.content_check`: 102 stand-ins, none on a deleted name (the builder confirms with the report).
- After the change, `python tools/patch_sites.py report tracker.index` is listed in the report.

**Tests:**
- `test_filer`, `test_index`, `test_records`, `test_content_check`, `test_names`, `test_api`, `test_runner`, `test_errors`,
  `test_page_rows`, `test_reminder`, `test_rollover`, `test_ledger`, `test_review`, `test_router`, `test_golden`;
- the guards `test_layers`, `test_single_source`, `test_repo_map`, `test_tripwire`.

These are filer's, content_check's and names' own files plus every changed test file. test_router and test_review run
only because their import lines changed.

**Accept when:**
- the gate passes;
- every recording in `tests/golden/` is unchanged;
- `grep -rn "until P2.1[34]\|_CANDIDATE_SEP" tracker tests` finds nothing;
- `RE_EXPORTED` holds two rows.

---

## 5. Risks

- **The admission pin is re-pinned four times** (P2.1, P2.4, P2.5, P2.13), always under version 5. Version 5's
  meaning ("these parts, with these sources") holds only if each re-pin changes exactly what the job says:
  - P2.1: one annotation;
  - P2.4: keys only, renamed or added as same-digest second keys (R2.4.5), never a new digest;
  - P2.5: the two callers and the new layout rule;
  - P2.13: `records.` → `bounds.` in source lines.

  Each job's accept-when names that. A reviewer should diff the pin and the closure sources, not trust the count.
- **The narrow store widens by one module** (P2.13, P317). store and manifest gain `bounds` at load time, and
  test_layers' two pins and CLAUDE.md's sentence move with them in the same commit. The risk is a later job reading the
  wider pin as licence for more: the pin stays an exact set, so any further module still fails it.
- **A stand-in that silently stops reaching its target** (P2.9, P2.10, P2.13, P2.14). The tool lists stand-ins by the
  module they replace on. It cannot say which call a stand-in was meant to reach once a function moves. The jobs name
  every site. A wrong choice usually fails the test that owns it. One that passes anyway is a test that no longer tests,
  and only reading finds it.
- **Warnings read earlier** (P2.3). The envelope's warnings are copied when the envelope is built, not when it is printed.
  The builder proves that nothing in between appends.
- **`test_filer` runs in P2.9, P2.13 and P2.14** as filer's own test file. It is the longest file in the suite. That is the
  cost of moving code out of filer, not a reach into the engine.
- **The renderer guard** (P2.3) reads JavaScript with patterns, as the J3 guards do. They are scoped to five named
  failure contexts, because `kind` names many vocabularies in the renderer that are not failures. Its must-find list
  keeps it from passing vacuously, and its must-not-find list keeps the scope from widening unseen. A new kind literal
  written in a shape the patterns miss passes unseen (J3's carry note on structural guards applies).
- **Found, not built: the admission pin does not see a class's members.** `admission_closure()` (test_store 3876)
  records functions and constants of simple types. `rule_row_fault` reads `Override.ALL` and `Override.RETIRED`, an
  attribute off a class, so a change to `Override`'s members changes what the admission admits without changing the
  pin. That is true at `286b535` and is not changed by moving `Override` (P2.4). Widening the closure would change
  `ADMISSION_PIN[5]`'s meaning, so it is for the carry list, not this phase.
- **B-10 is carried, not built.** The Mac's two seams stay apart until a Mac run can show what joining them changes.
- **P2.12 moves the corpus reader** that decision 185 guards. The firm's corpus variable is still read only through
  `settings.real_corpus_dir()`, and conftest still removes it for every test. test_tripwire and test_real_corpus are in
  the job's list. No generative AI reads a client document, and nothing here points at a real clients root.

## 6. Owed to the office PC

- **P2.12: the backtest against the firm's own documents.** Run on the office PC with `TRACKER_REAL_CORPUS` set:
  `python tools/backtest.py run …` then `check` against `docs/backtest-baseline.json`. The baseline must hold, because
  the harness moved. The firm's corpus never leaves that machine, and the cloud cannot run this.
- **Windows.** No job touches the engagement lock, the atomic replace, a Windows-only script or a Windows-only test, so
  no job asks for the `windows` label.
  - P2.7 renames `settings._inside`, a path relation, without changing its body. The tracker lane's office gate before
    the merge covers it.
  - The error log's `os.replace` rotation moves byte for byte into errlog.
  - Per "Test minimally", the Windows check prompt for the landing names `test_errlog`, `test_settings`, `test_store`,
    `test_hold` and `test_index`, because they hold path and file-replace behaviour. It repeats no hands-on step: no
    screen or installer behaviour changed.
- **Mac.** Nothing in phase 2 changes a Mac path. B-10's eventual build needs a Mac run (`pilot/mactest`) and is not
  scheduled here.
