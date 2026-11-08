# SPEC-architecture phase 5: the door and the pass

Written by the SPEC writer and measured at `f15eed1`, the phase's base, where P4.13 landed and phase 4 ended. Every
line number below is at `f15eed1` unless a job says it was measured after an earlier job. The scope is
SPEC-architecture section 9's "Phase 5" paragraph (829-835), with these parts of section 5:
- the `api.py` row (166) and the `runner.py` row (168) of section 4.2, and its `reminder.py` row (173);
- the layer picture (338-358);
- the new-module table (374-399): `screen_words`, `status_page`, `run_log`, `request_edit`, `household_edit`,
  `creation`, `firm_view`, `pass_order`, `letter_render`.

The audit findings it builds are in `pilot/AUDIT-2026-10-13-architecture.md`: C-1 (859), C-2 (910), C-5 (989), C-6
(1027), C-8 (1063), C-10 (1090), E-2 (1531) and E-3 (1565). C-3 (per-command state) is phase 7's: it is left alone,
and each job that moves code touching `api._WARNINGS`, `_ASKED` or `_RUNNING` says so. The SPEC reviewer's findings go
to `ORCH/spec-p5/review-<r>.md`. This is the round-3 draft: it answers every finding and note of `review-1.md`
(S1-S14, N1-N4) and of `review-2.md` (S15-S17, N5-N7); each change names its finding in that round's report on the
board, not here.

## 1. The answer

Phase 5 takes apart the program's door (`tracker/api.py`, 6,778 lines) and its scheduled pass (`tracker/runner.py`,
3,640 lines) without changing what either does. From the API:
- `screen_words.py` (L1): the words the API sends the screen, in one home;
- `request_edit.py`, `household_edit.py` and `creation.py` (L3): the editor's save rules, a household's edits and
  related returns, and the create transaction with its undo;
- `firm_view.py` (L4): the practice's rows and their cache, below the API, so the pass could reach them.

The API keeps `COMMANDS`, the envelope, the vocabulary (`api.vocab`, today's `_vocab`, made public with `api.state`),
`main` and the handlers. From the pass: `run_log.py` (the pass's report, its codes, the run log and the last-pass
file), `status_page.py` (the practice status page) and `pass_order.py` (the household order hint). From the reminder:
`letter_render.py` (L0), the letter's look. After-install's one-time jobs become one table, so a further job is one
entry. The big test files split with their modules, and what is left of `test_api.py` and `test_runner.py` splits by
command family. Nothing a person sees, no file a pass writes and no reply the screen reads changes; `SCHEMA_VERSION`
(20), `ADMISSION_VERSION` (6) and every recording in `tests/golden/` stay as they are.

## 2. What it relies on

**Decision rows:**
- 42: one home per fact, and the screen's words come from the API (`_vocab`).
- 51: seams where the code already turned.
- 91 and 186: the status report is a page; the run log says codes, the page and console say sentences.
- 99 and P313: the layer test; the runner never imports `scheduling` or `api`.
- 104 and 160: the request list's writes are `manifest.save_rules`'; absent means unchanged in an editor save.
- 115: nothing is ever sent; no network module anywhere under `tracker/`.
- 118: the letter is one structure rendered twice; the colours are `page.PALETTE`'s.
- 120 and P201: the firm cache never makes a status wrong; the pass fills it at its end, in a child (`python -m
  tracker.api firm`).
- 123: a rule that lived only in the API and that a command line missed (the precedent for C-1).
- 125, 126, 131, 137, 142, 144, 188: the layout, the household rollover, the room rule, the create transaction's undo,
  accepted-not-asked, short names, the folder is the name.
- 193 and P2.3 (`replies.py`): the envelope and the written reply shapes.
- 209: one-time steps run themselves; `after_install.run()` is the one place they are added.
- P217, P220, P227, P229, P276, P278: the pass order hint, the names fixed at import, the page's kept rows, the last
  counts at launch, the resident engine, the firm pages.
- P309-P314: the plan, the type checker, the loop, the answers built meanwhile, the domains.
- P319-P338: phase 2, 3 and 4's homes; P331's `copies.refuse_a_path_past_the_limit`.

**Landed jobs:**
- J4: `tools/patch_sites.py` and `tests/golden/`. J5: the state register (`tracker/resident.py`). J6:
  `tools/typecheck.py`, whose baseline at `f15eed1` is 138 errors in 22 files: api 24, runner 4, after_install 4,
  firm_pages 6, reminder 0 (measured with mypy; the brief's figures hold).
- P2.3: `replies.py` and one envelope builder. P2.8: the Open lists in `reasons` and `page.document`.
- P3.7: `COMPOSERS` (`tests/test_layers.py` 528).
- P4.13: `MOVED_OUT` and `READ_THROUGH_ON_PURPOSE` (`tests/test_layers.py` 1245-1253), the guard that a moved name is
  read from its home.

**What the audit's other slice-C findings are now** (one line each):
- C-3, per-command state: phase 7's. `_WARNINGS`, `_ASKED` and `_RUNNING` stay in `api` and keep their register keys.
- C-4, the reply contract: built by P2.3 (`replies.py`, `api._envelope_of` returns `progress.failure_reply` whole,
  the failure kinds pinned in `tests/test_replies.py`).
- C-7, the Open allow-lists: built by P2.8 (`reasons.READ_AND_PARKED_CODES` 909 and `NO_OPEN_CODES` 928).
- C-9, the page skeleton: built by P2.8 (`page.document`, read by `runner` 2808 and `view` 696).

**SPEC-architecture:** section 5.1 (flat modules; a move is a move; the door is thin), section 6 (behaviour does not
change), section 9 (phase 5's paragraph), section 11 (Q-C, Q-F) and P313's answers to them.

### 2.1 Where this SPEC departs from section 9's paragraph or the audit, and why

| Item | What the plan or the audit asks | What this SPEC does | Why |
|---|---|---|---|
| **No re-export facade** | Section 5.1: the old module re-exports what moved until a last job removes it | Phase 4's approach: the new module imports what its moved code reads, by name; the old module imports back by name only what it still uses itself; every reader in `tracker/`, `tools/` and `pilot/` is retargeted in the moving job; tests that read a moved name through an import-back may wait for P5.16, which retargets them and adds the new modules to `MOVED_OUT`. | P4.13's guard holds the rule, and a stand-in must reach its code from the first move (section 3). |
| **What `screen_words` takes** | C-1 item 1: every constant in api's word ranges, plus six strays; C-6: in the order `_vocab` sends them | The words a person reads and the vocabulary's fixed values, in file order (R5.3.1's table). These stay in `api`: `ENGAGEMENT_FLAG` (the door's command-line flag, 292 test reads), `_slug` (a function's alias), the command tables, the review buckets' keys and the group and link keys (codes, not words; they go with their rules to `firm_view` in P5.7), `FIRM_UNREADABLE` (P5.7), and the pilot record's and the firm page refusal's blocks (each a word beside a file name, a bound or an envelope key it is read with). | File order keeps the move byte for byte. A key is not a word. `firm_view` must not reach `screen_words` (next row). |
| **`SCREEN` moves, with a guard** | C-1 moves it silently | `SCREEN` (the one word table read at import: `"product": product_name()`) moves to `screen_words`. A new guard in `tests/test_layers.py` fails if any module the runner reaches at load time imports `screen_words`; P5.7 extends it to `firm_view`. | The scheduled task starts the runner with no product name (api_entry.py's docstring, P220): `settings.product_name()` raises there. Today only the API reads it at import, and the runner never imports the API. A word module the pass imported would make the scheduled pass fail to start. |
| **No `save_from_editor`** | C-1 item 2: request_edit exposes one `save_from_editor(engagement, spec)` | The editor's rules move (the merge, the refusals, the spec parsing); `api._cmd_edit` keeps its body and calls them by name. Likewise `_cmd_create`, `_cmd_edit_household` and the firm handlers keep theirs. | The handlers' bodies write the command's warnings (`_warn` into `api._WARNINGS`) and read `_ASKED`: C-3's state, phase 7's. Moving a body now would need that state passed in, a change of shape rather than a move. Phase 7's per-command context is where the handlers thin. |
| **Where the shared parsers go** | C-1: `_members_from_spec` with request_edit | `_members_from_spec` and `_folder_name` go to `household_edit` (P5.5); `creation` imports `_folder_name` from it. `_info_from_spec` and `_people_from_spec` go to `request_edit` (P5.4). `_placed` and `_tax_year` stay in `api` (spec parsing for create and the rollovers, which stay). | A household's members and a household folder's name are the household's; the editor's details are the editor's. |
| **`creation` at L3** | Section 5.3: L3 or L4 | L3. | Its imports are L3 and below (`household_edit`, `households`, `copies`, `store`, `layout`, `errors`). |
| **What `firm_view` takes** | C-2: the group rule, `_firm_row`, `_firm_draft`, `_firm_key`, `_firm_marks`, `_firm_read_households`, `_firm_fresh`, `_firm_from_cache`, `_firm_cached`, `FIRM_JUDGED` | The group rule and its keys, the row builder, the cache path (`_firm_cached`, `_firm_from_cache` and its helpers), `_firm_last`, and what they read that the API also reads: the review buckets and the copy keys (`review_bucket`, `_review_copy_key`, `_shown_copy_key`, `_moved_copy_key`, `_name_on_disk`), the household links (`_links_from`, `_household_links`) and `_year` (R5.7.1). These stay in `api`: `_firm_fresh` (it refuses through `_not_walked`, which writes the command's warnings, C-3), `_firm_key` and `_firm_reply` (the reply's shape), `_firm_reply_shell`, `_next_sort` (it reads `scheduling`), the paging (`_firm_ask`, `_firm_words`, `_firm_paged`, `_PageRefused`, `_read_optional_spec`) and the two handlers. | The builder may not import the API, so everything it reads goes down with it. The door shapes the reply and pages it (C-2's own words). |
| **Logger names** | Nothing | Each module carved out of `api` that logs binds `logging.getLogger("tracker.api")`; each carved out of `runner`, `logging.getLogger("tracker.runner")`. The module docstring says why. | Phase 4's rule (P331): the error log and the run log print `%(name)s`; a new name would change lines a person reads. |
| **`run_log` holds the pass's report** | C-5: `format_report`, `log_counts`, `append_log`, `write_last_pass`, `last_pass_line`, `amber_hours`, `PassFailed` | `run_log` takes the run log and the last-pass file, and also the pass's report records (`EngagementRun`, `RunReport`, `_warn`), the codes the run log says (the `CODE_*` table) and `why_skipped`. `format_report` and `PassFailed` stay in `runner`. | The log, the status page and the order hint all read the report records, so they must sit below all three; the first of the three to move takes them. `format_report` reads the draft-day rule (`is_draft_day`), which stays in the runner; `PassFailed` is raised and caught only by the runner. |
| **`api.MISFITS_HEADING` is the status page's** | C-6: api imports it from where the status page's word lives | P5.9: `screen_words` loses `MISFITS_HEADING`, and `api` imports `STATUS_MISFITS_HEADING as MISFITS_HEADING` from `status_page`, so `vocab` reads it byte for byte. | The one true second typing the audit found ("Folders the App Leaves Alone", twice). Same text, so nothing a person sees changes. |
| **`pass_order` at L4** | Section 5.3: L4 | L4, importing `run_log` (L3). | The plan's layer; it imports nothing above L3, so L3 would also pass, and moving it later is a decision row. |
| **`render_html` stays in the reminder** | C-8: `letter_render` takes `render_html`, `pasted_text`, `split_pasted`, `render_text_html`, the colours | `letter_render` (L0) takes the emphasis table and colours, the letter's shapes (`Run`, `Section`, `Letter`), the three run kinds, and every renderer but `render_html`, which stays in `reminder` and calls them. `pasted_text` and `split_pasted` stay too. | `render_html` is typed by `ReminderDraft`, the reminder's own record: an `if TYPE_CHECKING:` import is a load edge to `tests/import_graph.py`, so an L0 module could not name it. `pasted_text` reads a draft file and `split_pasted` the subject prefix; neither renders. |
| **E-2's scope** | E-2: `api.vocab()`, `api.state()`, `store.engagement_row()`, `store.refuse_malformed_line()`, `filer.do_op()` | `api.vocab` and `api.state` (P5.2). The store's, the admission's and the intents' private names are not renamed. | Those modules are phases 3 and 4's and have landed. Renaming `_refuse_a_malformed_line`, a part of `ADMISSION_PIN[6]`, would re-key the pin. Section 2.2 carries the rest. |
| **E-3: family files, owned** | E-3: split by command family (`test_api_commands_*.py`) | A test moves with its code (section 4.1). Then P5.14 splits what is left of `test_api.py` and `test_runner.py` into `tests/test_api_<family>.py` and `tests/test_runner_<family>.py` by their section banners; P5.13 first teaches the map that such a file is owned by `tracker/<module>.py` (decision row P350). | Owner edges come from file names (`tools/repo_map.py` `_owner_edges`); without P5.13 the family files would read as "exercised by" and an affected-tests run would skip them. The split pays because each file runs as its own process (Jason, 2026-09-29). |
| **Test files' names** | E-3: by command family | `tests/test_screen_words.py`, `test_request_edit.py`, `test_household_edit.py`, `test_creation.py`, `test_firm_view.py`, `test_run_log.py`, `test_status_page.py`, `test_pass_order.py`, `test_letter_render.py`; P5.14's family files as R5.14.1 names them. | One component per module (CLAUDE.md). |

### 2.2 Carried-forward items (`ORCH/carry-forward.md` and the brief)

*Phase 4's, for this phase:*
- **Prose under `tracker/` and `tools/` that P4.13 could not touch:** `tracker/index.py` 42-43 ("nobody else's",
  incomplete since P4.4), `tracker/door.py` 166 ("the filer's walks and its step check"), `tracker/scaffold.py` 41-42
  ("the filer at layer 3"), the filer docstring's two-sentence P4.9 pointer (`tracker/filer.py` 165-169), and
  `tools/backtest.py` 231 ("with ``ocr=True`` there is no reading child"). Taken in P5.15 (R5.15.1). No phase 5 job
  otherwise edits these files, so one wording job carries them.
- **The Mac kit's pinned test list** (`pilot/mactest/PROMPT.md` 85, `tests/test_pilot.py` `KIT_TESTS` 476 and
  `KIT_TESTS_ADDED` 483, the results template's rows). Taken in P5.15 (R5.15.3), after every split of this phase, and
  wider than the brief: not only `test_reader_child` is missing. Every file split out of a listed file since R33 is
  missing (`test_hold` and `test_errlog` from `test_settings`; `test_admission`, `test_store_check` and `test_verify`
  from `test_store`; `test_index` and the five filer files from `test_filer`; `test_renderer_seams` from
  `test_shell`; `test_keywords`, `test_verdicts`; `test_reader_child`), and phase 5 splits
  `test_api` and `test_runner`, both listed. Decision row P351.
- **The `resident_pages` flake** (`tests/test_reader_child.py::test_a_linux_childs_memory_is_its_resident_pages`, 277;
  the baseline's two notes). Taken in P5.15 (R5.15.2): the test-only fix P4.12's builder proposed (fresh pages from an
  anonymous `mmap`), which keeps the test's claim and its numbers.
- **Curated-map items:** the `RECORD_PRESERVE_INTENTS` sentence on the intents node, the ledger node's repeated
  sentence, the admission node's "five stand-ins" (six since P3.8). Taken in P5.15 (R5.15.4).
- **test_index's crossing tuple** leaves `readme_ack` out (`tests/test_index.py` 96, `family = (filer, copies,
  intents, inbox, actions)`) although its docstring says "the filer and the modules carved out of it". Taken in P5.15
  (R5.15.1): the tuple names the whole family. `FILER_FAMILY` (`tests/test_patch_sites.py` 1450) already does.
- **`MOVED_OUT`**: a later move out of a module adds its row. Taken in P5.16 (R5.16.1).

*Older items this phase reaches:*
- **after_install's curated notes list a stale import set** (P3.4 review 1, note 4). Taken in P5.12 (R5.12.7), which
  edits after_install's node.
- **"Any phase that moves a module": patch_sites' written limits and `monkeypatch.setitem`.** Taken. Every move job
  reads the tool's report and greps `tests/` by hand for each moved name in the string form (`setattr("tracker.x.y",
  ...)`), through a parameter, and through a helper that imports the module, and lists the result in before.txt. At
  `f15eed1` the string-form stand-ins on a module that moves code are `'tracker.runner.SLOW_READING_SECONDS'`
  (`tests/test_content_check.py` 254), `'tracker.runner.product_name'` and `'tracker.runner.firm'`
  (`tests/test_runner.py` 1199, 1200, 1203); the `setitem` targets are `api.COMMANDS`, `reasons.SHORT_REASONS` and
  `sys.modules`, none of which moves.
- **"Any phase that adds or moves module state": the register.** Not reached: the register's keys for these modules
  are `("api", "_ASKED")`, `("api", "_RUNNING")` and `("api", "_WARNINGS")` (`tracker/resident.py` 146-148), which
  stay. Each move job runs `test_resident` and greps its moved names against the register.
- **"A tools job": `repo_map.py` reading `ast.AnnAssign`.** Not taken; P5.13 changes the owner rule only. The moved
  annotated names are listed per job (section 4.1); at `f15eed1`: `PATH_KINDS` (api 1239), `EDITOR_LABELS` (1256),
  `EDITOR_HELP` (1261), `_WARNINGS` and `_ASKED` (stay) in api; none in runner's moving code.
- **`hold.py` 42-44's wording; the store's and store_check's notes; `ledger.apply`'s `key`.** Not taken: no phase 5
  job edits those files.
- **The writers derivation test names `accept-folder-name` but not `mark-shared`** (P3.7 review 1, N1). Taken in
  P5.14 (R5.14.6): the test moves with its family file, and its assert gains the second name.
- **E-2's other names** (`store._engagement_row`, `admission._refuse_a_malformed_line`, `intents._do_op`, and the
  private names this phase's moves import across modules). Carried: section 7's carry list asks for a package-wide
  decision on cross-module private names after phase 7, measured then.

## 3. Rules every job follows

**The gate.** This phase does not reach the sorting engine: no job changes code in the router, the filer and its
family, `content_check`, `ocr`, the scanner or the manifest's rules, so no job runs the whole suite (CLAUDE.md, "Test
minimally"). Two jobs correct a docstring or a comment there, and nothing else in those files: P5.4 (`tracker/actions.py`'s
"Only the API imports it", R5.4.11) and P5.15 (`tracker/filer.py`'s P4.9 pointer, R5.15.1). Such an edit runs no test file of that module, because no code it runs changes; instead after.txt shows
`git diff -U0 <job base> -- <file>` holding only docstring or comment lines. Each job runs its named tests, each file as
its own process, under PY311 and PY314, then:
1. Dead code is deleted in the changed files first: unused imports and locals, commented-out code, and any
   module-level name nothing uses.
2. The job's named test files.
3. `python -m ruff check .`
4. `python tools/repo_map.py update`, then `check`.
5. `python tools/typecheck.py check`
6. `python tools/patch_sites.py check`
7. `python -m pytest --collect-only -q` before and after, compared (section 4.1).

No job touches a catalog, the matcher or a typed case, so `tools/vocab_report.py check` is not part of any job's
gate; a job that finds it must edit `INPUT_PATHS`' files stops and asks.

**What the base already fails** (`ORCH/baseline/README.md`): on PY314,
`tests/test_api.py::test_importing_the_api_opens_no_file_but_the_programs_own`; the reading-child memory test now
and then (P5.15 fixes it). A test on that list passes a job's gate if it fails the same way at the job's base. Each
job's before.txt records its named tests at its own base on both interpreters.

**Re-measure.** Every line number here is at `f15eed1`. Each job after P5.1 measures its anchors again on its own
base, by the name the anchor gives. A range is anchored on its first and last definitions; the decorators, the `#:`
or `#` comment block directly above a moved definition and a section header a table says moves always move with it.
If a named thing is not where the range says, or a range holds a name the list does not give, stop and ask.

**The map, the docs and the decision rows:**
- `python tools/repo_map.py update` in the same commit as the code, after any edit to `docs/repo-map.curated.json`.
- A new module gets, in the commit that creates it:
  - a curated node (a role, and notes carrying the reasoning, as its neighbours' do), and any artifact edge that moves
    to it (section 4.1);
  - a row in `tests/test_layers.py`'s `LAYERS` (151-255), with the comment above its layer's set in its neighbours'
    form, and in `DOMAINS` (263-292);
  - a line under its layer in `docs/architecture.md`;
  - a line in `tracker/__init__.py`'s module list (`- name          : description`), after the module it came from;
  - its own `tests/test_<module>.py`, with a curated node in `tests/store_helpers.py`'s form;
  - a decision row in `pilot/DECISIONS.md`, in P338's form.
- `docs/architecture.md` line 29 says "fifty-four modules". It rises by one per new module: fifty-five at P5.3,
  fifty-six at P5.4, fifty-seven at P5.5, fifty-eight at P5.6, fifty-nine at P5.7, sixty at P5.8, sixty-one at P5.9,
  sixty-two at P5.10, sixty-three at P5.11.
- **Domains** (P314's six): `screen_words` in `door` (the words the door sends); `request_edit`, `household_edit` and
  `creation` in `record` (they hold the rules of what a person's edit writes to the record); `firm_view` and
  `status_page` in `shell` (beside `firm_cache`, `firm_pages`, `page_rows` and `view`: what a person opens);
  `run_log`, `pass_order` and `letter_render` in `pass` (beside `runner` and `reminder`).
- **Decision rows, in landing order:** P339 (P5.2), P340 (P5.3), P341 (P5.4), P342 (P5.5), P343 (P5.6), P344 (P5.7),
  P345 (P5.8), P346 (P5.9), P347 (P5.10), P348 (P5.11), P349 (P5.12), P350 (P5.13), P351 (P5.15). P5.1, P5.14 and
  P5.16 change no rule a row records and add none. A job that lands out of order takes the next free number and says
  so.

**A move is a move:**
- Code moves byte for byte, with its comments and words. The only exceptions are the edits a requirement names.
- The new module imports what its moved code reads, by name, so the bodies stay byte for byte.
- The old module imports back by name only what it still uses itself. No `# noqa: F401` line is written; ruff fails
  on an import-back nothing uses, and that is the check.
- Every reader in `tracker/`, `tools/`, `pilot/`, `api_entry.py` and `README.md` of a moved name is retargeted to its
  new home in the same commit, including an attribute read (`runner.why_skipped`), the prose pointers in docstrings and
  comments (``tracker.api.X``, `:func:` and `:data:` roles), the curated map's notes, `docs/runbook.md` and `README.md`
  (at `f15eed1` README 379 names `tracker.runner.STATUS_PAGE_FILENAME`, which P5.9 moves). The job greps
  `tracker tools pilot docs api_entry.py README.md` for each moved name and lists the hits in before.txt.
  `pilot/DECISIONS.md`, `docs/ROADMAP.md`, the audits (`pilot/AUDIT-*.md`), the handoffs (`pilot/HANDOFF-*.md`), the
  SPECs (`pilot/SPEC-*.md`) and the generated map are history or generated, and are not edited; the one exception is
  R5.15.3's sentence in `pilot/SPEC-mac.md`, which the brief asks for. `pilot/wording-shell.tsv` is a living table, not
  history: its `source` cells are retargeted (R5.2.1, R5.3.11).
- A pointer inside moved code to a name that stays behind (``:func:`_vocab` `` in a comment that moves to
  `screen_words`) is retargeted to its full name (``:func:`tracker.api.vocab` ``), so it still resolves.
- Tests:
  - A test that reads, through the old module, a name the old module no longer holds after the job (a moved name it
    does not import back, or an imported name whose last reader moved) is retargeted in the moving job, to the
    name's defining module. "Reads" includes capturing an original beside a stand-in.
  - Each move job's before.txt lists the old module's imports ruff will drop after the move, with every read of each
    in `tests/` (`grep -rnE "\b<old>(_module)?\.<name>\b|from tracker\.<old> import[^#]*\b<name>\b" tests`, and the
    multi-line `from ... import (` form by hand).
  - Section 4.0's last table lists, per job, the test reads measured at `f15eed1` that break inside that job; the
    builder's before.txt is checked against it, adds the multi-line `from ... import (` forms by hand, and stops and
    asks over a measured row it cannot find.
  - A test that reads a moved name the old module still imports back may wait for P5.16.
  - **A job that edits a helper module runs every test file that imports it** (at `f15eed1`: `tests/api_driver.py` is
    imported by test_api, test_golden, test_rollover and test_shell; `tests/passes.py` by test_golden, test_page_rows,
    test_runner and test_shell; re-measure with `grep -lE "^\s*from tests(\.| )import|^\s*import tests\." tests/*.py`
    and the helper's name), plus every family file created earlier in the phase that imports it.
    - **The one narrowing:** an edit confined to the body of one function, which changes no name, signature, default,
      decorator or module-level line of the helper, runs every test file that calls that function (grep for the
      function's name in `tests/`) in place of every importer. The helper's other importers load the same module-level
      names and never run the edited body, so they cannot see the edit. after.txt names the function and pastes the
      grep.
    - Why narrow rather than list every importer: Jason's rule (CLAUDE.md, "Test minimally") runs the files a change
      can reach, and at `f15eed1` `tests/node_harness.py` alone is imported by thirteen test files, while P5.2's one edit
      in it (362, inside `run_notices`) is reached by test_shell alone. A move of a whole helper into or out of a helper
      module (section 4.1's shared helpers, which any move job may write; P5.14's) is a module-level change and keeps the
      full rule.

**The stand-ins follow the readers** (A-4, phase 4's rule unchanged). A `monkeypatch.setattr(<module>, "<name>", ...)`
works only while the code under test looks the name up in `<module>`'s namespace:
- In the commit that moves the code, each stand-in is set on every module that reads `<name>` as a global after the
  move, whether `<name>` is defined there or imported there.
- Write it as a loop over a literal tuple of modules, which patch_sites follows (`for module in (api, firm_view):
  monkeypatch.setattr(module, "read_index", ...)`); where there is one reader, one `setattr`.
- A moved function's readers are its callers. `_refuse_a_changed_row_past_the_limit` moves to `request_edit` in P5.4,
  but its caller `_cmd_edit` stays in `api`, so its stand-in stays on `api`.
- A stand-in on an attribute read (`runner.why_skipped(...)`) needs one target: the module the attribute is read from
  after the job.
- A stand-in the tool cannot follow (a string target, a helper that takes `monkeypatch`) is read by hand and listed
  in before.txt.
- **A stand-in that forbids a call** (`raises AssertionError("... read what it must not")`, test_api 10748-10752, the
  firm-last test's loop, and 11000, `_forbid_the_walk`'s)
  is the sharpest case: left on `api` alone after its readers moved, it forbids nothing and the test passes. Section
  4.0's rows name each one.
- Stop and ask if a stand-in cannot reach the code it replaces under this rule.
- Each move job's before.txt holds `python tools/patch_sites.py report tracker.<old>`, and after.txt `report
  tracker.<old>` and `report tracker.<new>`. Every stand-in in the before list has its counterparts after, one on
  each module section 4.0 names; none is `unread`; `check` passes.

**The state register** (`tracker/resident.py`). No register key names a moving name. `_WARNINGS`, `_ASKED` and
`_RUNNING` stay in `api`; a move job whose moved code reads one of them stops and asks (none does, measured: the
moving functions' reads at `f15eed1` include none of the three).

**The layer table, the cycles and CLAUDE.md:**
- Every new module's layer is given in its job. No load-time import may point upward.
- No new `CALL_TIME_CYCLES` entry (`tests/test_layers.py` 663-668). If the cycle test (671) reports one, stop and ask.
- `test_the_runner_never_imports_the_scheduler_or_the_api` (645) holds, and every new module the runner imports
  (`run_log`, `status_page`, `pass_order`) also imports neither `scheduling` nor `api`.
- No CLAUDE.md line changes but P5.13's (R5.13.4), given with its exact old and new text.

**`COMPOSERS`** (`tests/test_layers.py` 528: `actions`, `filer`, `households`, `intents`, `manifest`, `reminder`,
`scanner`). No moved code calls `ledger.new(`; no module joins. If the composer test names any other module after a
move, stop and ask.

**The admission pin.** Not reached: no closure part lives in a module this phase edits, beyond prose pointers in
`records`, `reasons`, `ledger`, `layout` or `bounds` comments (not closure parts). Each move job's accept-when says
`ADMISSION_PIN[6]` is unchanged (`test_admission` in P5.1 and P5.16's named tests).

**Types.** `typecheck.py check` fails when a file gains an error and when a file with no entry has any, so a new
module is born clean; P5.1 brings `api`, `runner` and `after_install` to zero before anything moves. A fix is P3.1's
style: an annotation or a `cast` that states what the code already relies on, with a comment where the reason is
not plain, or a distinct local name where one name held two types. A fix never adds a check, a branch or an
`assert`. `firm_pages` keeps its 6: no code of it moves and no job edits it.

**The reply contract.** Every job that touches `api.py` says why no reply changes: the handlers stay, keep their
bodies and build each reply from the same values; `tests/golden/replies.*.keys.json` and `tests/test_replies.py`
hold the shapes.

**Golden.** `tests/golden/` is never re-recorded. Every job's accept-when includes: "`pytest tests/test_golden.py`
passes and `git diff --stat f15eed1 -- tests/golden` is empty".

**Windows.** The `windows` label is for a job that touches the held engagement lock, the atomic replace, path
handling or a Windows-only test; each job says whether it does and gives its `pilot\wintest\run_checks.ps1 -Tests`
list. The phase does not reach the engine, so the office checks the stack once with the union of those lists, the
installer build and the hands-on steps of section 6, not the whole suite.

**Safety:** made-up data only (decision 185); commit signing on; no model identifier in anything committed;
`STANDING_RULES` untouched; no `SCHEMA_VERSION` or `ADMISSION_VERSION` change; no generative AI reads a client
document; nothing is sent (no job adds an import to the network or mail modules `FORBIDDEN_MODULES` names).

## 4. The jobs, in landing order

| Job | Title | Cost | Tier | Depends on | Windows |
|---|---|---|---|---|---|
| P5.1 | Type burn-down in api, runner and after_install | M | Opus | — | no |
| P5.2 | `api.vocab` and `api.state`: the de-facto public names made public (E-2) | S | Sonnet | P5.1 | no |
| P5.3 | `screen_words.py`: the words the door sends (C-1 item 1, C-6) | L | Opus | P5.2 | no |
| P5.4 | `request_edit.py`: the editor's save rules; Q-F (C-1 item 2) | M | Opus | P5.3 | **yes** |
| P5.5 | `household_edit.py`: a household's edits and related returns (C-1 item 3) | S | Opus | P5.4 | **yes** |
| P5.6 | `creation.py`: the create transaction and its undo (C-1 item 4) | S | Opus | P5.5 | **yes** |
| P5.7 | `firm_view.py` at L4: the practice's rows and their cache; Q-C (C-2) | L | Opus | P5.6 | no |
| P5.8 | `run_log.py`: the pass's report, the run log and the last-pass file (C-5) | M | Opus | P5.7 | **yes** |
| P5.9 | `status_page.py`: the practice status page; one misfits heading (C-5, C-6) | M | Opus | P5.8 | **yes** |
| P5.10 | `pass_order.py`: the household order hint (C-5) | S | Opus | P5.9 | **yes** |
| P5.11 | `letter_render.py`: the letter's look (C-8) | S | Sonnet | P5.10 | no |
| P5.12 | after_install's jobs as a table (C-10) | M | Opus | P5.11 | **yes** |
| P5.13 | A family test file is owned by its module (E-3, the map) | S | Opus | P5.12 | no |
| P5.14 | `test_api.py` and `test_runner.py` split by command family (E-3) | M | Sonnet | P5.13 | no |
| P5.15 | Phase 4's loose ends: prose, the Mac kit's list, the memory test, curated notes | S | Sonnet | P5.14 | no |
| P5.16 | The moved names read from their home; `MOVED_OUT` rows | M | Sonnet | P5.15 | no |

**Tiers** (PROMPT-refactor section 1.3):
- Opus: every job that moves code out of `api.py` or `runner.py` (rule (a): P5.3-P5.10); P5.1, whose fixes sit in the
  API's handlers and the pass; P5.12, by rule (e): it rewrites the control flow of the one-time step path (decision
  209) rather than moving bytes, and a mistake changes what the installer records; P5.13, by rule (c): it changes how
  `tools/repo_map.py` derives a fact.
- Sonnet: P5.2 (a grep-driven rename with one collision rule), P5.11 (a small pure move out of the reminder, which rule
  (a) does not name, with no stand-in to move), P5.14 (test files moved by a banner table and a rule a script can
  check), P5.15 (wording, a pinned list, one test's mechanics) and P5.16 (a grep-driven retarget and one table).

Every job edits `tests/test_layers.py`, `tests/test_api.py` or the map, so they are built in this order, one session
each.

---
### 4.0 The stand-ins, by reader

`python tools/patch_sites.py report` at `f15eed1`: `tracker.api` 62 stand-ins in 3 files (22 defined, 40 imported, 0
unread); `tracker.runner` 80 in 8 files (48 defined, 32 imported, 0 unread); `tracker.reminder` 12 in 2 files;
`tracker.after_install` 15 in 5 files. The whole: 910 stand-ins on 53 modules. The tables give, for each name whose
readers change in this phase, its sites and the modules whose code reads it as a global, at the base and after each
job that changes them. They were computed from the module's AST at `f15eed1` with this SPEC's move lists (each
top-level definition's `ast.Name` reads, mapped to its destination); each move job re-derives its rows on its own base
and records them in before.txt.

**`tracker.api`:**

| Name | Sites (`tests/`) | Readers: base → after each job that changes them |
|---|---|---|
| `_state` | test_api 7496 | api. P5.2 renames it `state`; the site's name follows. |
| `dt` | test_api 9896 | api → P5.4: api, request_edit → P5.7: api, firm_view, request_edit |
| `load_manifest` | test_api 8475, 9009, 9195, 10752 (forbids), 11000 (forbids) | api → P5.4: api, request_edit → P5.7: api, firm_view, request_edit |
| `households_named` | test_api 7595, 10752 (forbids), 11000 (forbids) | api → P5.5: api, household_edit → P5.7: api, firm_view, household_edit |
| `load_household_info` | test_api 10161 | api → P5.5: api, household_edit → P5.6: api, creation, household_edit |
| `_firm_row` | test_api 9061, 10752 (forbids), 11000 (forbids) | api (`_firm_fresh`) → P5.7: api, firm_view (`_firm_from_cache`) |
| `read_index` | test_api 8475, 10752 (forbids), 11000 (forbids) | api → P5.7: api, firm_view |
| `load_engagement_info` | test_api 8475, 11000 (forbids) | api → P5.7: api, firm_view |
| `household_positions` | test_api 9221, 10681, 11000 (forbids) | api → P5.7: firm_view |
| `last_drafted`, `last_draft_day` | test_api 8919, 8920 | api → P5.7: api, firm_view |
| `FIRM_READ_BATCH` | test_api 10490, 10519 | api → P5.7: firm_view (it moves) |
| `_firm_cached` | test_api 9047, 11000, 11161 | api: its caller `_cmd_firm` stays, so the target stays `api` |
| `_refuse_a_changed_row_past_the_limit`, `_refuse_taking_away_documents` | test_api 6581, 6582 | api: their caller `_cmd_edit` stays |

Unchanged by the phase (each stays on `api`): `_ASKED`, `_RUNNING`, `_WARNINGS` (test_resident 667-669), `main`
(test_api_entry 189, test_resident 158, 227, 408), `_firm_fresh`, `_household_payload`, `_list_payload`,
`_may_carry_code`, `_reminder_now`, `assign_review_file`, `created_on`, `data_home`, `default_tax_year`,
`discover_engagements` (its readers after P5.7 are api's alone: `_firm_fresh`, `_cmd_list`, `_listing`),
`engagement_from`, `redirected_copies`, `scaffold_engagement`, `scan_engagement`.

**`tracker.runner`:**

| Name | Sites (`tests/`) | Readers: base → after each job that changes them |
|---|---|---|
| `SLOW_READING_SECONDS` | test_runner 1875, 4854; test_content_check 254 (string target `'tracker.runner.SLOW_READING_SECONDS'`) | runner (`EngagementRun`) → P5.8: run_log (it moves with `EngagementRun`) |
| `append_log` | test_api 1766 | runner (`_pass`): its caller stays, so the target stays `runner` |
| `write_last_pass` | test_runner 4008 | runner (`_say_last_pass`): stays `runner` |
| `write_status_page` | test_api 1767; test_runner 2395, 2771 | runner (`_pass`, `_say_no_data_home_on_the_page`): stays `runner` |
| `_parked_files` | test_runner 5326 | runner → P5.9: status_page (its caller `write_status_page` moves) |
| `load_manifest` | test_page_rows 83, 283; test_runner 2186, 2523, 2598, 2625 | runner → P5.9: runner, status_page |
| `read_index` | test_page_rows 84; test_runner 4323 | runner → P5.9: status_page |
| `firm`, `product_name` | test_runner 1199, 1200, 1203 (string targets `'tracker.runner.firm'`, `'tracker.runner.product_name'`) | runner (`_page_title`) → P5.9: status_page |
| `write_text_atomically` | test_runner 4384, 5346, 5377, 5556 | runner → P5.9: runner, status_page → P5.10: pass_order, status_page |

Unchanged by the phase (each stays on `runner`): `HOUSEHOLD_BUDGET_SECONDS`, `WATCHDOG_SLICE_SECONDS`, `Watch`,
`_emit_line`, `_end_the_process`, `_list_the_root`, `_pass`, `_sort_step`, `check_rules`, `created_on`,
`discover_engagements`, `engagement_lock`, `file_household_drops`, `fill_firm_cache` (plugin_fakes 323,
test_after_install 1382 and 1401, test_runner 5086, 5192, 5227: Q-C keeps it in the runner), `load_household_info`,
`main`, `open_years`, `reader_start_warning`, `room_for`, `run_household`, `run_registry`, `scan_engagement`,
`wall_clock`.

**`tracker.reminder`** (P5.11) and **`tracker.after_install`** (P5.12): no stand-in's readers change. None of the
reminder's twelve names (`draft_reminder`, `last_approved_event`, `triage`, `unsorted_in_inbox`, `approval_state`,
`firm_phone`, `last_draft_event`) moves; after_install's fifteen (`_tmutil`, `CHECKOUT`, `_schedule`,
`LOCK_WAIT_SECONDS`, `LOCK_POLL_SECONDS`, `program_identity`, `run`, `launch`, `read_record`) are read where they are
today, and P5.12 keeps each name and its readers (R5.12.4).

**Test reads that break inside the move job** (section 3). Names the old module stops holding after the job, with
the test reads through it, measured at `f15eed1` with single-line greps (`api.X`, `api_module.X`, `runner.X`,
`runner_module.X`, `reminder.X`, `from tracker.<old> import ... X`). Each is retargeted in the job named, to the name's
defining module; the builder adds the multi-line `from ... import (` forms, and each job's before.txt is checked
against its row.

| Job | Reads that break, by name (count) | Retarget to |
|---|---|---|
| P5.3 | `api.ASK_THE_CLIENT_NOTE` (test_api 1189), `api_module.ASK_THE_CLIENT_NOTE` (test_single_source 1127) | `screen_words` |
| P5.4 | `api.HOLDS_DOCUMENTS` ×4; `api._people_from_spec` ×3 | `screen_words`; `request_edit` |
| P5.5 | `api.RELATED_REFUSED` ×3, `api.RELATED_NOT_A_LIST` ×1, `api.RELATED_UNKNOWN` ×1 | `screen_words` |
| P5.6 | `api.DUPLICATE_HOUSEHOLD` ×2, `api.CLIENT_FOLDER_TAKEN` ×1; `api._undo_create` ×1 | `screen_words`; `creation` |
| P5.7 | `api.READ_AND_PARKED_CODES` ×5 (its home is `reasons`); `api.FIRM_UNREADABLE` ×4, `api.FIRM_JUDGED` ×2, `api.GROUP_RECEIVED` ×2, `api.GROUPS` ×1, `api.FIRM_LAST_REFUSALS` ×1, `api._firm_from_cache` ×1, `api._CONTAINER_CODES` ×3 (test_api 935 and 936 sit in a module-level `@pytest.mark.parametrize`, so the file would fail at collection; and 10834: `_CONTAINER_CODES` moves with its one reader `review_bucket` and is not imported back, R5.7.2) | `reasons`; `firm_view` |
| P5.8 | `runner.log_path` 6 reads and 4 from-imports; `LEVEL_ERR` 7, `LEVEL_OK` 3, `LEVEL_WARN` 4; `LAST_PASS_MAX_BYTES` 2, `LAST_PASS_NEVER` 2, `LAST_PASS_OFF` 2, `LAST_PASS_OLD` 2, `LAST_PASS_UNREADABLE` 1, `LAST_PASS_AMBER_HOURS` 1 read and 1 from-import, `LAST_PASS_AMBER_HOURS_DAILY` 1; `SLOW_READING_NOTE` 2 from-imports; `VIEW_NOT_REGENERATED` 1 (test_view 670); `amber_hours` 1; `runner_module.last_pass_line` 16 (test_runner 3775-3840, 3999, 4054, 4114, 4138, 5672, 5803: the runner does not import it back, R5.8.2, so the reads in tests that stay, such as 3999, 4054 and 5803, break as well as the moved ones) | `run_log` |
| P5.9 | `STATUS_RECORDS_HEADING` 2 reads and 3 from-imports; `STATUS_INDEX_UNREADABLE` 1, `STATUS_IGNORED_HEADING` 1, `STATUS_NOT_PASSED` 1, `_drafted_cell` 2; and the runner drops its import-backs of `IGNORED_NOTE` and `STAGE_NOTE` here (R5.8.2 kept them for the status page's code), so a test read of either through `runner` breaks here | `status_page`; `run_log` for the two notes |
| P5.10 | `PASS_ORDER_MAX_BYTES` 2 reads and 1 from-import, `ORDER_HINT_UNREADABLE` 1 and 2, `PASS_ORDER_VERSION` 1, `CODE_ORDER_HINT_UNREADABLE` 1 (its home is `run_log` since P5.8), `NOT_SERVED_TWICE` 1, the `WHY_*` names 4, `_why_not_served` 2 | `pass_order`; `run_log` for the code |
| P5.11 | test_reminder 34's import block names `Emphasis`, `HOLD_COLOUR`, `STAGE_COLOURS`, `STAGE_EMPHASIS`, which the reminder no longer holds, so the whole file would fail at collection; test_api 2925-2930 (`reminder.STAGE_COLOURS`, `reminder.STAGE_EMPHASIS`, `reminder.HOLD_COLOUR`); test_single_source 1044 (`from tracker.reminder import HOLD_COLOUR, LETTER_INK, STAGE_COLOURS`: the reminder imports back `LETTER_INK` but not the other two, R5.11.2, so the line becomes `from tracker.letter_render import HOLD_COLOUR, LETTER_INK, STAGE_COLOURS`, all three defined there) | `letter_render` |

---
### 4.1 Rules the move jobs share (P5.3-P5.11)

These hold for every job that creates a module. Each job's own requirements add to them and never repeat them.

**The constants that move.** A job names the definitions that move. With them move the module-level constants they
read, transitively through other constants, unless the job's table keeps one behind; a block of constants under one
`#:` comment moves whole where the job says so. The old module imports back what its staying code still reads.
before.txt lists the moved constants as the AST computes them (each moved definition's `ast.Name` reads, closed over
constants) and the import-backs.

**The test split** (E-3). A test function moves with the code it is about, by phase 4's rule:
- A test's *homes* are the modules that, after the job, define the functions and classes of the old module the test
  calls or constructs, directly in its body or through a fixture in the same file. Exception classes, word constants
  and stand-in targets do not count: a test that only reads `api.SCREEN` is about the code that sends it.
- The test moves to `tests/test_<M>.py` when the highest of its homes in the order below is `M`. A test whose highest
  home is the module that stays, or that calls nothing of the old module, stays.
  - api's family: `screen_words` < `request_edit`, `household_edit` < `creation` < `firm_view` < `api`
    (`request_edit` and `household_edit` are unordered: a test calling both stays in its file).
  - runner's: `run_log` < `status_page` < `pass_order` < `runner`.
  - reminder's: `letter_render` < `reminder`.
- Most API tests drive a command through `tests/api_driver.py`'s `run` (which calls `api.main`), so their highest
  home is `api` and they stay; few move. Measured at `f15eed1`, direct calls in `tests/` to a moving function through
  its old module: `item_group` 10, `file_group` 5, `review_bucket` 2, `_firm_from_cache` 1 (firm_view);
  `_members_from_spec` 4, `_feeds_from_spec` 2, `_folder_name` 1 (household_edit); `_people_from_spec` 3
  (request_edit); `_new_return_dir` 2, `_undo_create` 1 (creation); `last_pass_line` 16, `write_last_pass` 11,
  `append_log` 1 (run_log); `status_report` 5 (status_page); `_read_order_hint` 2, `_write_order_hint` 1
  (pass_order). A call inside a test that also runs a command stays with the command.
- If the rule sends no test to the new module's file, the job writes one or more tests of the moved code called
  directly, each named as its claim and drawn from what the moved code's docstring promises; the collect-only diff
  names them. `tests/test_screen_words.py` always gets R5.3.9's test.
- Each job lists every moved test by its old node id in before.txt, with its homes. A test the rule moves but that
  reads better where it is still moves; an exception is a stop and ask.
- A moved test moves byte for byte with its decorators and comments; its module-qualified reads change to the new
  home only where the old module no longer holds the name.

**The shared helpers.** A test file may not import another (`test_suite_shape`). What more than one of the split
files reads goes to the family's helper module: `tests/api_driver.py` for the API's (it holds `run`, `scan`,
`sample_engagement` today) and `tests/passes.py` for the runner's (it already holds the runner's helpers; no
`tests/runner_helpers.py` is made), each in `tests/store_helpers.py`'s form: a docstring saying where each helper came from and why; fixtures named once by
assignment in each user (`demo_root = api_driver.demo_root`); the helper moved byte for byte and deleted where it was.

**The module's head.** Each new module starts with a docstring that carries the reasoning: what it holds and the
decision rows behind each part (from the moved code's own comments where they say it); where it came from (the
audit finding, this SPEC's job, its decision row); why it sits at its layer and what it may not import; why it logs as
the old module (section 2.1). The old module's docstring loses the paragraphs that described the moved code and gains
one sentence naming the new home.

**The annotated names.** Each move job runs `grep -nE '^[A-Za-z_][A-Za-z0-9_]*: [^=]+ = ' tracker/<old>.py
tracker/<new>.py` before and after and lists what moved; the map sees none of them (carried tools item).

**Artifacts.** A curated `writes` or `reads` edge to an artifact moves to the node of the module whose code now does
the write or the read, in the job's commit (`tests/test_repo_map.py` 861,
`test_every_artifact_has_a_writer_and_a_reader_or_says_it_is_write_only`, holds every artifact to a writer and a
reader).

**The accept-when every move job shares:**
- The gate passes on both interpreters, with the base's failures and skips and no others.
- `python -m pytest --collect-only -q` before and after list the same tests apart from the moved ones' file part and
  the additions the job names: the job diffs the two with the file part stripped (a `sed` given in after.txt), and the
  diff holds exactly those, no other line.
- `patch_sites report` before and after meets section 3's line; `check` passes.
- `ADMISSION_PIN[6]` is unchanged; `tests/golden/` is unchanged.
- `git diff -M --stat` shows the moved code as moved, and `git diff -M -w --color-moved=plain` on the pair shows no
  line edited inside a moved body other than the ones a requirement names; after.txt pastes the command and its
  summary.

---

### P5.1 Type burn-down in api, runner and after_install

- **Cost:** M.
- **Tier:** Opus. Its fixes sit in the API's handlers (the editor, the create transaction, the firm view) and the
  pass, where a cast placed wrong hides a real `None`.
- **Findings:** section 9 ("every phase starts by burning down the type errors in the modules it will move"); E-5.
- **Depends on:** —.
- **Layer and domain:** no new module.

**What is measured** (`python -m mypy` with the repository's `[tool.mypy]`, at `f15eed1`):
- `tracker/api.py`, 24: 2231 (two, `**{key: date(key) for key in DATE_FIELDS}` into `EngagementInfo.replace`), 2753
  (`list[object]` into `list[Engagement]`), 2841-2846 (eight, `object` has no `path`/`name`/`info`, in
  `_fed_by_payload`), 3254 (`locate` given `str | None`), 4175, 4178, 4192 (`int | None` in `_cmd_create`), 5983
  (`shown` given `str | None`, in `_firm_row`), 6575, 6581, 6584, 6586, 6589, 6598, 6606 (`return refuse(...)`, where
  `refuse` returns `None`, in `_firm_last`), 6772 (indexed assignment to `object`: `payload["warnings"] =
  list(_WARNINGS)` in `main`; `payload`, bound at 6764 from `COMMANDS[argv[0]](argv[1:])`, is `object` because
  `COMMANDS`' values join to `object`, `_cmd_run_now` returning `int`).
- `tracker/runner.py`, 4: 1444 and 1687 (`Path | None` has no `parent`), 1465 (`Watch | None`), 1553 (`list[object]`
  returned as `list[Engagement]`).
- `tracker/after_install.py`, 4: 532, 535, 546 (`designation_file` given `Path | None`), 540 (`claim` given
  `Path | None`), all in `_schedule`.

**Requirements:**

- **R5.1.1, the three modules type-check clean.** Each error above is cleared in section 3's style. Where a
  `return f(...)` returns what a `None`-returning call gave (`return refuse("no_positions")`), the fix may write the
  call and `return None` on two lines, or annotate the nested function's return as the enclosing function's; it adds
  no branch either way. The 6772 site is cleared at 6764: `payload = cast(dict, COMMANDS[argv[0]](argv[1:]))`, with a
  comment that `run-now`, the one command whose handler returns an `int`, returned at 6746-6750 before this point
  (`_RUNNING`, whose `_RUNNING["command"] = ...` at 6745 is no error, is not touched).
- **R5.1.2, the baseline.** `python tools/typecheck.py update` records the lower counts: api, runner and after_install
  leave `docs/typecheck-baseline.json`, and the whole reads 106 errors in 19 files. `firm_pages` keeps its 6.
- **R5.1.3, nothing else changes.** No other file's count moves; no line outside the error sites and the annotations
  they need changes. If a fix needs a check, a branch or a new `assert`, stop and ask.

**Pin-move list:** `docs/typecheck-baseline.json` (regenerated by the tool, never by hand).

**Patch sites:** none change.

**Register:** not reached (no register name's annotation or value changes).

**Tests:** `test_api`, `test_runner`, `test_after_install`, `test_resident`, `test_api_entry`, `test_scheduling`,
`test_typecheck`, `test_admission`, `test_golden`, `test_layers`, `test_single_source`, `test_repo_map`.

**Stop and ask:** a fix that would need a runtime check; an error not in the list above at the job's base.

**Accept when:**
- `typecheck.py check` passes with api, runner and after_install at zero, 106 in 19 files.
- `git diff f15eed1 --stat -- tracker` touches only the three modules; `tests/golden/` is unchanged.
- **Windows:** no label (annotations and casts only). **Office `-Tests`:** none of its own.

---

### P5.2 `api.vocab` and `api.state`: the de-facto public names made public (E-2)

- **Cost:** S.
- **Tier:** Sonnet. A rename by grep, with one collision rule.
- **Findings:** E-2.
- **Depends on:** P5.1.
- **Layer and domain:** no new module.

`api._vocab` is the screen's vocabulary (decision 42), read 287 times by name from tests and by
`pilot/harness/make_vocab.py`; `api._state` is the `state` command's body, read 36 times. A published contract with a
private name.

**Requirements:**

- **R5.2.1, the two names.** `def _vocab()` (api 1666) becomes `def vocab()`, and `def _state(engagement)` (3062)
  becomes `def state(engagement)`. Every call and every reference in `tracker/` (with `replies.py` 72's prose,
  ``api._state`` builds both), `tools/`, `pilot/harness/` (`make_vocab.py`, its README and `stub.js`'s comment) and
  `app/renderer/app.js` 35 (a comment) names the new name. No alias is kept.
  - **`pilot/wording-shell.tsv`** is a living wording table (later SPECs add rows; test_api reads it by its `key`
    column, never by `source`), not history: its 195 `source` cells reading `api._vocab` become `api.vocab`, in the
    first column only (`awk -F'\t' -v OFS='\t' '$1=="api._vocab"{$1="api.vocab"}1'`, after.txt shows `cut -f1 | sort
    | uniq -c` before and after). Its `api.SCREEN` and `api.MENU` cells still resolve here and are P5.3's (R5.3.11).
- **R5.2.2, the collisions.** A local variable named `state` or `vocab` in a function that now calls `state(...)` or
  `vocab()` is renamed, in that function only, to a name nothing else in it uses: at `f15eed1`, `state =
  _state(engagement)` in `_cmd_edit` (3551) inside `tracker/` (`_cmd_approve`'s local `state` at 5514 never meets the
  function, since `_cmd_approve` does not call `_state`, and is left as it is); in `tests/`, `tests/test_view.py`
  749-751 (`from tracker.api import _state, _vocab`, then `state = _state(...)`), and every other hit of `grep -rnwE
  "(state|vocab) *=" tests` in a function that calls either. The two throwaway locals named `_state` at test_api 8812
  and 8827 (`_engagement, _state, firm = _firm_of_a_scanned_pile(...)` and `engagement, _state, firm = ...`) are not
  the function, but would read as a missed rename: they become `_scanned_state`. ruff's F823 and F821 and the tests
  are the check.
- **R5.2.3, the tests and the pins.** Every `api._vocab`, `api._state`, `api_module._vocab`, `from tracker.api import
  _vocab` (and `_state`) and the stand-in at test_api 7496 (`setattr(api, "_state", ...)` becomes `"state"`) name the
  new names; source pins that count or slice by name (test_api 8233, `callers.count("_state")`) are retargeted.
  Measured at `f15eed1` (lines matching `grep -rcw "_vocab\|_state"`): test_api 74 (two of them the throwaway
  locals of R5.2.2), test_shell 17, test_single_source 16, test_view 4, test_golden 2, test_row_columns 2,
  node_harness 1, test_ledger 1, test_registry 1, test_shell_menu 1, test_actions 1 (2202,
  `api_module._state(engagement)`), test_runner 1 (1582, `api_module._state(Path(engagement))` in its `api_state`
  helper). R5.2.6's grep is the list.
- **R5.2.4, prose.** The curated map's notes that name `_vocab` or `_state`, and `docs/runbook.md` if it names them.
- **R5.2.5, the decision row P339:** the vocabulary and the state reply are `api.vocab()` and `api.state()`; the
  underscore said "private" of the two names the screen, the harness and the suite read most (E-2); no alias, because
  every reader is in the repository. It cites 42, E-2 and P312.
- **R5.2.6, the grep, with its paths named.** `grep -rnw --exclude-dir=__pycache__ "_vocab\|_state" tracker tools
  app tests pilot/harness pilot/wording-shell.tsv api_entry.py README.md docs/runbook.md docs/architecture.md
  docs/tools.md docs/repo-map.curated.json` finds nothing after the job (at `f15eed1` it finds 358 lines in the 20
  files R5.2.1-R5.2.4 name, the curated map's 6 among them). History is named and not grepped or edited: `pilot/DECISIONS.md`, `docs/ROADMAP.md`, `pilot/AUDIT-*.md`,
  `pilot/HANDOFF-*.md`, `pilot/SPEC-*.md` (at `f15eed1` they hold the old names in the decision log 2, the
  architecture audit 20, the other audit 3, `HANDOFF-error-handling-small.md` 8, and about twelve SPECs);
  `docs/repo-map.json` and `.md` are regenerated by `update`.

**Pin-move list:** test_api 7496 and 8233; every test file R5.2.3 names; `pilot/wording-shell.tsv`'s `source` column;
`tracker/replies.py` 72; the curated api node (and any other curated note R5.2.6's grep finds).

**Patch sites:** the one site at test_api 7496 renames; `report tracker.api` is 62 before and after.

**Register:** not reached.

**Tests:** `test_api`, `test_shell`, `test_shell_menu`, `test_single_source`, `test_golden`, `test_row_columns`,
`test_ledger`, `test_registry`, `test_view`, `test_actions`, `test_runner`, `test_resident`, `test_replies`,
`test_layers`, `test_repo_map`. (`test_actions` and `test_runner` each change one line; they are run whole because
each runs as one process and the line sits in a test or a helper the file shares.) The edit in `tests/node_harness.py`
(362, `api._vocab()` to `api.vocab()`) sits inside `run_notices`, which only test_shell calls (`grep -n run_notices
tests/*.py`: its definition and test_shell 54 and 1275), so section 3's narrowing applies and node_harness's other
importers (test_build, test_pilot, test_pilot_ui, test_renderer_seams, test_suite_shape, test_tour) are not run for it;
those already in the list are run for their own edits.

**Stop and ask:** a reader outside the repository's files (none is known); a collision R5.2.2 cannot rename locally.

**Accept when:**
- R5.2.6's grep finds nothing.
- The collected tests are the same before and after; `tests/golden/` is unchanged; the vocabulary `make_vocab.py`
  dumps is byte-identical before and after (after.txt shows the two hashes).
- **Windows:** no label. **Office `-Tests`:** none of its own.

---

### P5.3 `screen_words.py`: the words the door sends (C-1 item 1, C-6)

- **Cost:** L.
- **Tier:** Opus. The first move out of the API: 259 names in about 1,000 lines, an import-back of nearly as many,
  and the one word table read at import.
- **Findings:** C-1 item 1; C-6.
- **Depends on:** P5.2.
- **Layer and domain:** L1, `door`.

**What moves** (api, at `f15eed1`). Re-measure each by name.

| Lines | What |
|---|---|
| 408-537 | The envelope's and the shell's words, from `USAGE`'s `#:` comment (408) to `NOTICE_ABOUT` (537): `USAGE`, `FAILED`, `STORE_UNAVAILABLE`, `RECORD_NOT_WRITTEN`, `NOTICE_LABELS`, `PRACTICE_NOT_WALKED`, the reminder-unreadable words, `NOTHING_TO_STOP`, `LOCK_WATCH_SECONDS` and the lock words, the progress words, the `SHELL_*` words, `PAGE_ERROR`, the `SCAN_*` words and `SCAN_REASONS`, `NOTICE_REPEATED`, `NOTICE_ABOUT`. The section header (390-396), `log` (388) and the three state names (397-406) stay. |
| 677-865 | From the `#:` comment over `HOUSEHOLD_HEADING` (677) to `CARD_POSITION` (865). `ENGAGEMENT_FLAG` and its comment (675-676) and the `# ---- commands ----` header (672) stay. |
| 880-1063 | From the `#:` comment after `BUCKET_HEADINGS` to `TEACH_SPELLING_HINT` (1063), with the module-level `assert` at 998-1000 (it holds `PLAIN_COLUMNS` and `ROUTING_COLUMNS` to `manifest.COLUMNS`). The review buckets' block (867-879: the three keys and `BUCKET_HEADINGS`) stays: its keys go to `firm_view` in P5.7, and `BUCKET_HEADINGS` stays in `api` with them. |
| 1107-1112 | `HOUSEHOLD_NOT_OURS` with its comment. |
| 1158-1159 | `NOT_A_SPEC` with its comment. |
| 1231-1663 | From `ROOM_HEADING`'s comment (1231) to `PROTECTED_VIEW_MAC` (1663): `ROOM_HEADING`, `PATH_KINDS`, `EDITOR_LABELS`, `EDITOR_HELP`, `MENU`, `MAC_MENU`, `MAC_SCREEN`, `MAC_SCAN_REASONS`, `SCREEN`, and the words after it. `_slug` (1206-1209), `_stages` and `standing_rules` (1212-1228) stay. |
| 2771-2775 | `FED_BY_UNREADABLE` with its comment. |
| 2852-2866 | The accept-folder-name block: `ACCEPT_FOLDER_NAME_LABEL` to `NOT_PAUSED`. |
| 4050-4061 | `DUPLICATE_HOUSEHOLD`, `CLIENT_FOLDER_TAKEN` with their comments. |
| 4261-4263 | `NOTHING_ASKED` with its comment. |
| 5283-5285 | `DRAFT_MOVED` with its comment. |
| 5619-5652 | The schedule's words and `AFTER_INSTALL_HEADING`, with their comments. |

**What stays in `api`** (measured; any other module-level assignment found in the ranges is a stop and ask): `log`,
`_WARNINGS`, `_ASKED`, `_RUNNING`; `ENGAGEMENT_FLAG`; the review buckets' block (867-879); `_slug`;
`_CONTAINER_CODES` (2325); the group keys and `GROUPS` (3020-3029); `PASS_COMMAND` (3374); `_ROW_KEYS` (3574) and
`_PATH_FIELDS` (3629); the link keys (3897-3902); `LIST_CHANGING` (4006); the pilot record's block (5788-5799:
`PILOT_RECORD_FILENAME`, `PILOT_RECORD_REFUSED`, `SIGNED_BY_LONGEST`, `SIGNED_BY_WITHHELD`); `FIRM_UNREADABLE`
(5907-5910); the firm page refusal's block (6087-6092: `FIRM_PAGE_REFUSED`, `FIRM_PAGE_REFUSED_KEY`); `_FirmShown`,
`_FirmRead`, `FIRM_JUDGED`, `FIRM_READ_BATCH`, `FIRM_LAST_REFUSALS`; `FIRM_LAST_COMMAND` and the three command sets;
`COMMANDS`.

`screen_words` imports, by name: `ERROR_LOG_FILENAME` from `errlog`; `COL_ISSUER` and `COLUMNS` from `manifest`; `NO`
from `records`; `product_name` from `settings`. Measured: no moved word reads anything else of the package (the
AST's reads of the moved assignments). It imports nothing above L1.

**Requirements:**

- **R5.3.1, the module.** `tracker/screen_words.py` holds the table's assignments and their comments, moved byte for
  byte in file order, under the head section 4.1 asks for. It defines no function and no class, and does not log.
  Its docstring says: the API's words in one home (decisions 42 and P66: a wording change is an edit here); why the
  keys, flags and command tables stayed behind; why it sits at L1 (it reads `manifest`'s and `records`' labels); and
  that `SCREEN` reads the product's name at import, so the runner must never reach it (R5.3.5).
- **R5.3.2, the API imports back** by name every moved word its remaining code reads, from `tracker.screen_words`.
  ruff is the check. Measured at `f15eed1`, one moved word has no reader left in `api`: `ASK_THE_CLIENT_NOTE` (970).
- **R5.3.3, pointers.** A moved comment that names a name staying in `api` (``:func:`vocab` ``, "referenced in
  :func:`vocab`'s ``scan.skipped``", 510 and 1331 at `f15eed1`) names it in full (``tracker.api.vocab``). Prose
  elsewhere that names a moved word through the API (`tracker/households.py` 336, ``tracker.api.FED_BY_LINE``;
  `tracker/firm_pages.py` 108, ``tracker.api.FIRM_PAGE_REFUSED``, which stays and is not retargeted) is retargeted
  where the word moved.
- **R5.3.4, tests that read a word `api` no longer holds** are retargeted (section 3): test_api 1189 and
  test_single_source 1127 (`api.ASK_THE_CLIENT_NOTE`, `api_module.ASK_THE_CLIENT_NOTE`) read
  `screen_words.ASK_THE_CLIENT_NOTE`. The rest of the test reads of a moved word through the API (about 380 in the
  `api.<WORD>` form, measured over the 259 names R5.3.1 moves, plus the `from tracker.api import` lines) keep working
  through the import-back and wait for P5.16.
- **R5.3.5, the guard.** `tests/test_layers.py` gains
  `test_nothing_the_scheduled_pass_loads_reads_the_products_name_at_import`: the transitive closure of `runner`'s
  load-time edges (`import_edges()`) holds none of `screen_words`, `scheduling` and `api` - the three modules whose
  top level reads the product's name (`SCREEN`; `TASK_NAME`, P220; and the API, which imports both). The existing
  `test_the_runner_never_imports_the_scheduler_or_the_api` (645) checks the runner's own edges; this one checks
  every module it loads. Its docstring says why: the scheduled task starts the
  runner with no product name in its environment (api_entry.py's docstring; P220), `screen_words.SCREEN` reads it at
  import, and `settings.product_name()` raises there. P5.7 extends it to `firm_view` (R5.7.9).
- **R5.3.6, the import-time pin.** `tests/test_api.py` 10443's set names `("screen_words.py", "SCREEN")` in place of
  `("api.py", "SCREEN")`; its docstring's "the side panel's word in ``SCREEN``" stays true. `tests/test_single_source.py`
  613 reads `tracker/screen_words.py` (the line `"product": product_name(),` is `SCREEN`'s), and 614's check is kept
  for `tracker/api.py` with a third line beside it for `tracker/screen_words.py` (`product_name() not in
  read("tracker/screen_words.py")`): the claim follows `SCREEN` to its home, and api.py still types the product's name
  nowhere, so the test checks both files rather than dropping api.py. The test's name and its count are unchanged (no
  collect-only line), and no reply changes. The test's `api.SCREEN` and `api.vocab()` reads stay.
- **R5.3.7, the layer table.** `screen_words` joins `LAYERS[1]`, with a comment above the set: "``screen_words``
  joins L1 with P340 (SPEC-architecture-p5 P5.3): the words the API sends the screen, out of ``api``, which imports
  them back - ``manifest`` and ``records`` (L1), ``errlog`` and ``settings`` (L0); nothing the runner loads may import
  it (``SCREEN`` reads the product's name at import)." It joins `DOMAINS["door"]`.
- **R5.3.8, the docs.** `docs/architecture.md`: "fifty-four" becomes "fifty-five", and a `screen_words` line goes under
  L1. `tracker/__init__.py`'s module list gains `- screen_words  : ...` after the api's line. `docs/runbook.md`, if it
  points a person at a wording in `tracker/api.py`, points at `tracker/screen_words.py`.
- **R5.3.9, its test file.** `tests/test_screen_words.py` holds
  `test_the_words_module_holds_words_and_fixed_values_and_nothing_that_acts`: every name the module binds that is not
  an imported one is a `str`, `int`, `float` or `bool`, or a `tuple`, `list`, `frozenset` or `dict` of those (nested),
  and the module defines no function or class. Plus any test section 4.1's rule sends (none is expected).
- **R5.3.10, the decision row P340:** the API's words left for `tracker/screen_words.py` at L1; keys, flags and
  command tables stayed; file order kept; `SCREEN` moved and the runner may not reach the module (P220); `firm_view`'s
  word stays out of it so the pass could fill the cache in-process (Q-C). It cites 42, P66, P220, C-1, C-6 and P313.
- **R5.3.11, the wording table's sources.** `pilot/wording-shell.tsv`'s `source` cells that name a table this job
  moves are retargeted, in the first column only: the 70 `api.SCREEN` cells become `screen_words.SCREEN` and the 5
  `api.MENU` cells `screen_words.MENU` (measured at `f15eed1`; `api.vocab`'s 195, renamed by P5.2, stay: the
  vocabulary is still `api`'s). after.txt shows `cut -f1 pilot/wording-shell.tsv | sort | uniq -c` before and after.

**Pin-move list:**
- `tests/test_layers.py`: `LAYERS[1]` and its comment, `DOMAINS["door"]`, R5.3.5's guard.
- `pilot/wording-shell.tsv`'s `source` column (R5.3.11).
- `tests/test_api.py` 10443 (`_fixed_at_import`); `tests/test_single_source.py` 613-614; test_api 1189 and
  test_single_source 1127.
- `docs/architecture.md` line 29 and its L1 list; `tracker/__init__.py`'s list; the curated api node and the new
  node.
- Not moved: `tests/test_shell.py` 3595 reads `'"client_type_forms": CLIENT_TYPE_FORMS,'` in `tracker/api.py`, which
  is `vocab`'s line and stays; test_errors 399 (`("api.py", "_envelope_of")`) stays.

**Patch sites:** none change (no stand-in names a moved word); `report tracker.api` is 62 before and after, `report
tracker.screen_words` 0.

**Register:** not reached.

**The reply contract:** no reply changes. `vocab` reads each word by the same name, now bound by the import-back to
the same object; `tests/golden/replies.list.keys.json` and `make_vocab.py`'s dump (byte-identical, as in P5.2) show it.

**Tests:** `tests/test_screen_words.py`, `test_api`, `test_resident`, `test_api_entry`, `test_shell`,
`test_shell_menu`, `test_single_source`, `test_golden`, `test_replies`, `test_errors`, `test_pilot`,
`test_row_columns`, `test_layers`, `test_repo_map`, `test_suite_shape`.

**Stop and ask:** a moved word that reads a name outside the four imports; an assignment in a range the tables do not
name; a reader in `tracker/` other than `api` of a moved word (none is measured).

**Accept when:**
- Section 4.1's shared accept-when holds.
- `screen_words` imports nothing above L1; R5.3.5's guard passes, and fails on a scratch edit that makes `runner`
  import `screen_words` (after.txt shows the failure; the edit is not committed).
- `make_vocab.py`'s dump is byte-identical before and after.
- **Windows:** no label. **Office `-Tests`:** none of its own (section 6's hands-on step 1 covers the scheduled pass's
  start).

---

### P5.4 `request_edit.py`: the editor's save rules; Q-F (C-1 item 2)

- **Cost:** M.
- **Tier:** Opus. It moves the editor's room check (path handling) and settles Q-F.
- **Findings:** C-1 item 2; section 4.1 item 10 (B-3); section 11 Q-F; P313.
- **Depends on:** P5.3.
- **Layer and domain:** L3, `record`.

**What moves** (api, at `f15eed1`):

| Lines | Names |
|---|---|
| 2178-2232 | `_info_from_spec` |
| 2256-2286 | `_people_from_spec` |
| 3003-3019 | `_rule_for_the_editor` (read by `_as_recorded`; `state` imports it back) |
| 3577-3620 | `_as_recorded`, `_refuse_taking_away_documents` |
| 3623-3672 | `_PATH_FIELDS` with its comment, `_refuse_a_changed_row_past_the_limit` |
| 4266-4272 | `_refuse_a_list_nobody_is_asked_for` (creation's and the editor's one refusal, decision 142's review R6) |

`_ROW_KEYS` (3570-3574) stays: its one reader is `_cmd_edit`, which stays. The words these read (`HOLDS_DOCUMENTS`,
`NOTHING_ASKED`) are `screen_words`' since P5.3. `request_edit` imports, by name: from `manifest` (`ManifestError`,
`ISO_DATE_HINT`, `Override`, `item_from_record`, `load_manifest`, `rule_as_read`, `ANY_EXTENSION`), from `records`
(`DATE_FIELDS`, `ENGAGEMENT_LABELS`, `EngagementInfo`, `PEOPLE_LABEL`, `Person`, `identifier_key`), the modules
`bounds` and `records`, `settings.firm`, `layout.PATH_TOO_LONG`, `copies.room_for`, `actions.documents_by_request` (L3,
in-layer), `datetime` as `dt`, `dataclasses.replace`, and the two words. (Measure the exact list from the moved code's
reads; ruff's F401 and F821 are the check.) It imports nothing above L3, and no `api`.

**Q-F, measured** (P313: "the editor's room check goes through the one room function only if no save could come out
differently; otherwise the docstring is corrected and the question goes to Jason"):
- The editor refuses when `copies.room_for(engagement, changed).need > path_limit()`, over the rows it changed, with
  `PATH_TOO_LONG.format(folder=engagement, length=room.need, limit=room.limit)`.
- `copies.refuse_a_path_past_the_limit(engagement, items)` refuses when `max(room_for(engagement, items).need,
  layout.folder_need(<engagement>/PREPARED_DIR_NAME/REVIEW_DIR_NAME, root)) > path_limit()`, with the same sentence.
- `folder_need` is `0` where long paths are on, and the review folder's length plus 26 (`TEMP_NAME_RESERVE`) where
  `layout.short_paths()` is true: a Windows with long paths off (the office's default, pilot decision P29) and every
  Mac.
- So routing the editor through the one function changes a save whenever the return's review folder is longer than
  233 characters there: every save of that return's list is refused, even one that changes no row's path (with no
  changed row, `room_for(..., []).need` is `0` today, and the review folder's figure alone refuses). Shown in a scratch
  run at `f15eed1` (`short_paths` stood in true; a 207-character return): today's check saves, the one function
  refuses with "the deepest file the app would write under ...". Such a return exists only when the folder above it
  has grown since creation (the clients root moved deeper, a household folder accepted under a longer name, decision
  188), because creation refused it through the same function.
- **Therefore P313's second branch held, and the question went to Jason** (section 7, Q-F). **He answered (C) on
  2026-11-08:** one room function, its review-folder term used only by creation and the rollover; the editor calls it
  with `review_folder=False`, so every save comes out as today (R5.4.4).

**Requirements:**

- **R5.4.1, the module.** `tracker/request_edit.py` holds the table's code, moved byte for byte, under section 4.1's
  head. It does not log. Its docstring says the editor's rules live here so a command line could reach them (decision
  123's lesson), that the handler keeps its body because the body writes the command's warnings (C-3), and Q-F's
  measurement in two sentences.
- **R5.4.2, the API imports back** by name what its handlers still call: `_info_from_spec` (`_cmd_create`,
  `_cmd_edit`, `_cmd_rollover`), `_as_recorded`, `_refuse_taking_away_documents`,
  `_refuse_a_changed_row_past_the_limit`, `_refuse_a_list_nobody_is_asked_for` (`_cmd_edit`, `_cmd_create`) and
  `_rule_for_the_editor` (`state`). ruff is the check.
- **R5.4.3, Q-F's sentence corrected.** `copies.refuse_a_path_past_the_limit`'s docstring (copies 477-480: "Creation,
  the household rollover and the editor's save all refuse through this one (decisions 125, 126 and 131).") becomes:
  "Creation and the household rollover refuse through this one (decisions 125 and 126). The editor's save measures
  the rows it changes with :func:`room_for` itself
  (:func:`tracker.request_edit._refuse_a_changed_row_past_the_limit`, decision 131), leaving out the review folder
  this function adds where long paths are off: a return whose folder has grown since creation would otherwise refuse
  every save (SPEC-architecture-p5, Q-F, Jason's to decide)." The rest of the docstring is unchanged. The curated
  copies node, if it repeats the false claim, is corrected the same way.
- **R5.4.4, Q-F (C): Jason's answer (2026-11-08), built in place of R5.4.3's sentence.** Under (C) (one function,
  the review folder for creation and the rollover only),
  `refuse_a_path_past_the_limit` gains a keyword-only `review_folder: bool = True` that leaves the `folder_need` term
  out when false, `_refuse_a_changed_row_past_the_limit`'s last three lines call
  `refuse_a_path_past_the_limit(engagement, changed, review_folder=False)`, and the docstring says so; every save
  comes out as today (the same comparison and the same sentence, measured above). A test proves it on R5.4's
  scratch case. `tracker/rollover.py` 983 calls the function with two positional arguments and keeps the default, so
  its refusals do not change; the job also runs `test_rollover`. R5.4.3's docstring sentence is replaced by one that
  says creation, the household rollover and the editor's save all refuse through this one, the editor with
  `review_folder=False` (decisions 125, 126 and 131; SPEC-architecture-p5, Q-F (C)), so its claim becomes true.
- **R5.4.5, readers in `tracker/`:** `records.py` 885 (``tracker.api._people_from_spec``) names
  ``tracker.request_edit._people_from_spec``; every other grep hit (section 3).
- **R5.4.6, the stand-ins** (section 4.0): `dt` gains `request_edit` beside `api`; `load_manifest` gains
  `request_edit` beside `api`; the two refusal stand-ins (test_api 6581-6582) stay on `api` (their caller stays).
- **R5.4.7, the test split.** `tests/test_request_edit.py` with the tests section 4.1's rule sends (measure; the
  direct `_people_from_spec` calls are the candidates), or R5.4's direct tests if none moves: at least one that
  `_refuse_a_changed_row_past_the_limit` never refuses a row the person did not touch, and one that `_as_recorded`
  fills only the columns a row leaves out (decision 160).
- **R5.4.8, the layer table.** `request_edit` joins `LAYERS[3]` with a comment: "``request_edit`` joins L3 with P341
  (SPEC-architecture-p5 P5.4): the editor's save rules and the spec's details, out of ``api``, which imports them
  back - ``actions`` (in-layer, the documents a request holds), ``copies`` (L2, the room), ``screen_words``,
  ``manifest``, ``records`` and ``bounds`` (L1 and L0)." It joins `DOMAINS["record"]`.
- **R5.4.9, the docs.** "fifty-five" becomes "fifty-six"; a line under L3; `- request_edit  : ...` after the api's
  line.
- **R5.4.10, the decision row P341:** the editor's rules left for `tracker/request_edit.py` at L3; the handler kept its
  body (C-3); Q-F measured, and Jason's answer (C) built: one room function, its review-folder term kept for creation
  and the rollover; every save comes out as before. It cites 131,
  142, 160, P305, P307, B-3, C-1 and P313.
- **R5.4.11, "only the API imports it" is no longer true.** `request_edit` imports `actions.documents_by_request` at
  load, so three sentences that say only the API imports `actions` are rewritten to name both importers, and nothing
  else in them changes:
  - `tests/test_layers.py` 244, the `actions` comment in `LAYERS`: "at call time; only the API imports it" becomes "at
    call time; the API and ``request_edit`` import it";
  - the `tracker/actions.py` curated node's "Only the API imports it." becomes "The API and tracker/request_edit.py
    import it.";
  - `tracker/actions.py` 105, the module docstring's "Only the API imports it." becomes "The API and
    :mod:`tracker.request_edit` import it." (a docstring edit in the filer's family, section 3: no test of `actions`
    runs for it).

**Pin-move list:** `LAYERS[3]`, `DOMAINS["record"]`; `copies.py` 477-480 (R5.4.3); `records.py` 885; the docs and the
module list; the curated nodes (api, copies, actions, request_edit, its test file); R5.4.11's three sentences
(`tests/test_layers.py` 244, the actions node, `tracker/actions.py` 105).

**Patch sites:** section 4.0's P5.4 rows; before.txt `report tracker.api`, after.txt `report tracker.api` and `report
tracker.request_edit`.

**Register:** not reached (the moved code reads none of `_WARNINGS`, `_ASKED`, `_RUNNING`; `_cmd_edit`, which does,
stays).

**The reply contract:** `edit` and `create` build their replies in the handlers, unchanged.

**Tests:** `tests/test_request_edit.py`, `test_api`, `test_copies`, `test_resident`, `test_records`, `test_golden`,
`test_layers`, `test_single_source`, `test_repo_map`, `test_suite_shape` and `test_rollover` (R5.4.4).

**Stop and ask:** a moved function that reads a name staying in `api` (the AST says none does); any save that would
come out differently under R5.4.4 (the measurement says none does).

**Accept when:**
- Section 4.1's shared accept-when holds.
- `request_edit` imports nothing above L3 and not `api`.
- `copies.refuse_a_path_past_the_limit`'s docstring names the editor's `review_folder=False` call, and R5.4.4's test
  shows a save on a return whose folder grew since creation coming out as before.
- **Windows: label.** It moves the editor's path-room check. **Office `-Tests`:**
  `test_request_edit,test_api,test_copies,test_rollover`.

---

### P5.5 `household_edit.py`: a household's edits and related returns (C-1 item 3)

- **Cost:** S.
- **Tier:** Opus. It moves `_mirror_related`, which takes each related household's engagement lock in turn (P170).
- **Findings:** C-1 item 3.
- **Depends on:** P5.4.
- **Layer and domain:** L3, `record`.

**What moves** (api, at `f15eed1`):

| Lines | Names |
|---|---|
| 1066-1079 | `_folder_name` (a folder name a spec gives; read by `_cmd_create`, `_cmd_roll_household`, `_new_return_dir`, `_feeds_from_spec`, `_related_from_spec`) |
| 2235-2253 | `_members_from_spec` |
| 4299-4412 | `_feeds_from_spec`, `_related_from_spec`, `_mirror_related` |

Their words (`MEMBERS_LABEL`, `FEEDS_LABEL`, `RELATED_REFUSED`, `RELATED_UNKNOWN`, `RELATED_NOT_A_LIST`) are
`screen_words`'. `household_edit` imports `ManifestError`, `layout`, `records`' `FEED_REFUSED` and `Feed`,
`registry.households_named` (L3), `households`' `load_household_info` and `save_household`, `locking`'s
`engagement_lock` and `EngagementLockedError`, `names`, `dataclasses.replace` and the words (measure).

**Requirements:**

- **R5.5.1, the module.** `tracker/household_edit.py` holds the table's code, byte for byte, under section 4.1's head.
  It does not log. The docstring says the household's own edits (members, feeds, related) and P170's cross-household
  mirror, taken under each household's lock in the one global order, live here; `_cmd_edit_household` keeps its body
  (C-3).
- **R5.5.2, the API imports back** `_folder_name`, `_members_from_spec`, `_feeds_from_spec`, `_related_from_spec` and
  `_mirror_related` (`_new_return_dir` reads `_folder_name` until P5.6 moves it).
- **R5.5.3, the stand-ins:** `households_named` gains `household_edit` beside `api`; `load_household_info` gains
  `household_edit` beside `api` (section 4.0).
- **R5.5.4, the test split.** `tests/test_household_edit.py` (the direct `_members_from_spec`, `_feeds_from_spec`
  and `_folder_name` calls are the candidates), or direct tests if none moves: at least one that `_mirror_related`
  refuses rather than waits when a related household's lock is held.
- **R5.5.5, the layer table.** `household_edit` joins `LAYERS[3]` ("... joins L3 with P342 (SPEC-architecture-p5
  P5.5): a household's members, feeds and related households and P170's mirror, out of ``api`` - ``registry``
  (in-layer), ``names`` (L2), ``households``, ``screen_words``, ``records`` (L1), ``locking`` and ``layout`` (L0).")
  and `DOMAINS["record"]`.
- **R5.5.6, the docs.** "fifty-six" becomes "fifty-seven"; a line under L3; the module list.
- **R5.5.7, the decision row P342.** It cites 125, 129, 188, P141, P170, P172 and C-1.

**Pin-move list:** `LAYERS[3]`, `DOMAINS["record"]`; the docs; the curated nodes.

**Patch sites:** section 4.0's P5.5 rows; `report tracker.api` before, `report tracker.api` and `report
tracker.household_edit` after.

**Register:** not reached.

**The reply contract:** `edit-household` builds its reply in the handler, unchanged.

**Tests:** `tests/test_household_edit.py`, `test_api`, `test_households`, `test_registry`, `test_resident`,
`test_locking` (the moved code takes the engagement lock; the office list runs it too), `test_golden`, `test_layers`,
`test_single_source`, `test_repo_map`, `test_suite_shape`.

**Accept when:** section 4.1's shared accept-when; `household_edit` imports nothing above L3 and not `api`.
- **Windows: label.** It moves code that takes the engagement lock. **Office `-Tests`:**
  `test_household_edit,test_api,test_households,test_locking`.

---

### P5.6 `creation.py`: the create transaction and its undo (C-1 item 4)

- **Cost:** S.
- **Tier:** Opus. It moves decision 137's undo (`shutil.rmtree`, only on folders this call made) and creation's room
  refusal.
- **Findings:** C-1 item 4.
- **Depends on:** P5.5.
- **Layer and domain:** L3, `record`.

**What moves** (api, at `f15eed1`):

| Lines | Names |
|---|---|
| 1082-1104 | `_new_return_dir` (the folder a new return takes, refused past the room limit through `copies.refuse_a_path_past_the_limit`) |
| 4064-4095 | `_folders_in`, `_refuse_a_taken_household_name` |
| 4241-4258 | `_undo_made` |
| 4275-4296 | `_undo_create` (with its comment block above it) |

`_undo_made` and `_undo_create` move together, never apart: decision 137's "remove only what this call made" is the
pair (the audit's "move it with that guard"). The words (`HOUSEHOLD_NOT_OURS`, `DUPLICATE_HOUSEHOLD`,
`CLIENT_FOLDER_TAKEN`) are `screen_words`'. `creation` imports `_folder_name` from `household_edit`, and `manifest`,
`copies`, `layout`, `households`, `ledger`, `store`, `errors`, `os`, `shutil` names (measure).

**Requirements:**

- **R5.6.1, the module.** `tracker/creation.py` holds the table's code, byte for byte, under section 4.1's head. It
  does not log. The docstring says `_cmd_create` keeps its body (C-3) and calls these; that `_undo_create`'s
  `rmtree` is reached only through `_undo_made`, on folders the call made (decision 137); that `_cmd_rollover` shares
  `_new_return_dir` and `_undo_made`.
- **R5.6.2, the API imports back** `_new_return_dir`, `_refuse_a_taken_household_name` and `_undo_made`; it drops
  `_folder_name` only if no staying function reads it (`_cmd_create` and `_cmd_roll_household` do, so it stays
  imported from `household_edit`).
- **R5.6.3, the stand-ins:** `load_household_info` gains `creation` (section 4.0).
- **R5.6.4, the test split.** `tests/test_creation.py` (the direct `_new_return_dir` and `_undo_create` calls are the
  candidates), or direct tests: at least one that `_undo_made` removes only the folders the call reports it made and
  leaves an existing household's folder alone.
- **R5.6.5, the layer table.** `creation` joins `LAYERS[3]` ("... joins L3 with P343 (SPEC-architecture-p5 P5.6):
  the create transaction's folder, its refusals and decision 137's undo, out of ``api`` - ``household_edit``
  (in-layer), ``copies`` (L2), ``households``, ``store``, ``screen_words`` (L1) and L0.") and `DOMAINS["record"]`.
- **R5.6.6, the docs.** "fifty-seven" becomes "fifty-eight"; a line under L3; the module list.
- **R5.6.7, the decision row P343.** It cites 125, 131, 137, 188 and C-1.

**Pin-move list:** `LAYERS[3]`, `DOMAINS["record"]`; the docs; the curated nodes; test_api's decision 137 tests stay
(they drive `create`).

**Patch sites:** section 4.0's P5.6 row; `report tracker.api` before, and `report tracker.api` and `report
tracker.creation` after.

**Register:** not reached.

**The reply contract:** `create` and `rollover` build their replies in the handlers, unchanged.

**Tests:** `tests/test_creation.py`, `test_api`, `test_rollover`, `test_households`, `test_resident`, `test_golden`,
`test_layers`, `test_single_source`, `test_repo_map`, `test_suite_shape`.

**Accept when:** section 4.1's shared accept-when; `creation` imports nothing above L3 and not `api`;
`grep -n "rmtree" tracker/api.py` finds nothing.
- **Windows: label.** It moves path handling (the room refusal, the folders it makes and removes). **Office
  `-Tests`:** `test_creation,test_api,test_rollover`.

---

### P5.7 `firm_view.py` at L4: the practice's rows and their cache; Q-C (C-2)

- **Cost:** L.
- **Tier:** Opus. It moves the builder whose cached and fresh replies P201 holds byte-identical, with the stand-ins
  that forbid a read.
- **Findings:** C-2; section 11 Q-C; P313.
- **Depends on:** P5.6.
- **Layer and domain:** L4, `shell`.

**Q-C, as built** (P313's interim answer, confirmed by Jason's answer (A) on 2026-11-08): the pass keeps its child for
filling the firm cache, unchanged.
`runner.fill_firm_cache` still runs `python -m tracker.api firm`; `_cmd_firm` stays in the API and now calls the
builder in `firm_view`. Only the builder moves down. Section 7 asks Jason, with what in-process filling would need.

**What moves** (api, at `f15eed1`):

| Lines | Names |
|---|---|
| 867-879 | The review buckets' three keys (`BUCKET_DOCUMENT`, `BUCKET_CONTAINER`, `BUCKET_NOT_A_DOCUMENT`) with the block's comment. `BUCKET_HEADINGS` (875-879) stays in `api`, which reads it in `vocab`, and imports the three keys back. |
| 2325-2327 | `_CONTAINER_CODES` |
| 2330-2334 | `_name_on_disk` |
| 2345-2435, four functions | `review_bucket` (2345-2358), `_review_copy_key` (2361-2378), `_moved_copy_key` (2410-2413), `_shown_copy_key` (2416-2435). Between them `true_extension` (2337), `_code_copies` (2381) and `_filed_copy_keys` (2397) stay in `api`, which imports the four back. |
| 3020-3059 | The group keys, `GROUPS`, `item_group`, `file_group` |
| 3840-3842 | `_year` |
| 3897-3953 | The link keys, `_household_links`, `_links_from` |
| 5890-5991 | `_firm_draft`, `FIRM_UNREADABLE` with its comment, `_firm_row` |
| 6141-6151 | `_FirmShown`, `_FirmRead` with their comments |
| 6221-6484 | `_firm_cached`, `FIRM_JUDGED`, `_FirmUnsure`, `FIRM_READ_BATCH`, `_say_count`, `_firm_from_cache`, `_firm_seen`, `_firm_order`, `_fact_engagement`, `_firm_marks`, `_firm_links`, `_firm_marked`, `_firm_keepable`, `_firm_read_households`, with their comments |
| 6547-6607 | `FIRM_LAST_REFUSALS` with its comment, `_firm_last` |

**What stays in `api`:** `_firm_key` (5994), `_firm_reply_shell` (6022), `_cmd_firm` (6033), `_PageRefused`,
`_read_optional_spec`, `_firm_ask`, `_firm_words`, `_firm_paged` (6095-6140), `_firm_reply` (6154), `_firm_fresh`
(6182; it refuses through `_not_walked`, which writes the command's warnings, C-3), `_cmd_firm_last` (6487),
`_next_sort` (6610; it reads `scheduling`), and every other caller of the moved names.

`firm_view` imports, by name, what its code reads (measure): `runner` (L4, in-layer: `why_skipped` and the draft-day
names `DRAFT_WEEKDAY`, `last_draft_day`, `last_drafted`), `reminder`, `review`, `view.VIEW_FILENAME`, `registry`
(L3), `containers.is_container`, `validators.is_program`, `index`,
`manifest`, `records`, `households`, `firm_cache`, `layout`, `errors`, `reasons`, `progress`. It imports neither `api`,
`scheduling` nor `screen_words`.

**Requirements:**

- **R5.7.1, the module.** `tracker/firm_view.py` holds the table's code, byte for byte, under section 4.1's head. Its
  logger is `logging.getLogger("tracker.api")` (section 2.1). Its docstring says: one builder for the Overview's rows
  and their cache (P120: a cache never makes a status wrong, and there is no second builder); the group rule the
  return's page and the Overview share (SPEC-shell 9.1); why it sits at L4 (beside the runner whose draft-day rule it
  reads); that the pass still fills the cache through `python -m tracker.api firm` (P201; Q-C as P313 left it); why
  `_firm_fresh` and the reply's shape stayed in the API; that it reads with `follow=False`, takes no lock and reads no
  document.
- **R5.7.2, the API imports back** what its staying code reads (measure): `BUCKET_DOCUMENT`, `BUCKET_CONTAINER`,
  `BUCKET_NOT_A_DOCUMENT`, `GROUP_NEEDS_YOU`, `GROUP_WAITING`, `_FirmRead`, `_FirmShown`, `_firm_cached`,
  `_firm_last`, `_firm_marked`, `_firm_row`, `_household_links`, `_moved_copy_key`, `_review_copy_key`,
  `_shown_copy_key`, `_year`, `file_group`, `item_group`, `review_bucket`, `_name_on_disk`.
- **R5.7.3, the stand-ins** (section 4.0's P5.7 rows): `_firm_row`, `read_index`, `load_engagement_info`,
  `last_drafted`, `last_draft_day`, `dt`, `load_manifest` and `households_named` each sit on `api` and `firm_view`
  (and `request_edit`, `household_edit` where the table says); `household_positions` and `FIRM_READ_BATCH` move to
  `firm_view` alone. The forbidding loops at test_api 10752 and 11000 name `firm_view` for every name whose readers
  include it; `_firm_cached` and `_firm_fresh` stay on `api`. after.txt shows each forbidding test failing on a
  scratch edit (not committed) in the moved function that test drives, so the stand-in still bites: for
  `_forbid_the_walk`'s tests (11000) an edit that makes `_firm_from_cache` call the forbidden name; for the firm-last
  test (its loop at 10748-10752) an edit that makes `_firm_last` call it.
- **R5.7.4, readers in `tracker/` and `tools/`:** `firm_pages.py` 12 and 624 (``tracker.api._cmd_firm``, which stays:
  not retargeted); every other grep hit. `fill_firm_cache`'s "Why a child and not a call" paragraph (runner 645-650 at
  `f15eed1`: "The rows the cache keeps are built by the API (``api._firm_from_cache``), and this module may not import
  it (``tests/test_layers.py``: the runner never imports ``api`` or ``scheduling``).") stops being true: the builder
  no longer lives in the API. Those two sentences become: "The rows the cache keeps are built by
  :func:`tracker.firm_view._firm_from_cache`, and this module does not import it: ``firm_view`` imports this module
  (the draft-day rule), so an import back would be a cycle, and the child stayed by P313's answer to Q-C
  (SPEC-architecture-p5 section 7)." The paragraph's next sentences (no second builder, P120; the pass runs exactly
  what Overview runs) are kept word for word.
- **R5.7.5, the `follow=False` pin.** `tests/test_runner.py` 4397 (`passing == ["api.py", "runner.py"]`) becomes
  `["firm_view.py", "runner.py"]` (api's three hits, 5917, 5940, 5941, are `_firm_row`'s); its docstring names the
  firm view.
- **R5.7.6, the test split.** `tests/test_firm_view.py` with the tests the rule sends (the direct `item_group`,
  `file_group`, `review_bucket` and `_firm_from_cache` calls are the candidates).
- **R5.7.7, the layer table.** `firm_view` joins `LAYERS[4]` ("``firm_view`` joins L4 with P344
  (SPEC-architecture-p5 P5.7): the Overview's rows, their cache and the group rule, out of ``api``, which imports
  them back - ``runner`` (in-layer, the draft-day rule), ``reminder``, ``review``, ``registry`` and ``view`` (L3),
  ``containers`` (L2), L1 and L0; never ``screen_words``.") and `DOMAINS["shell"]`. `test_firm_pages_joins_layer_0...`
  (1227-1235: `firm_pages`' only importer is `api`) holds unchanged: the paging stayed.
- **R5.7.8, the docs.** "fifty-eight" becomes "fifty-nine"; a line under L4; the module list. The api's docstring's
  first paragraph ("All real logic lives in the tracker package; this module only serializes it", C-1) gains one
  sentence naming what it now keeps and where its words, the editor's rules, the household edits, the create
  transaction and the firm view went.
- **R5.7.9, the guard widened.** R5.3.5's test also walks `firm_view`'s load-time closure, and its docstring adds:
  so the pass could call the builder in-process (Q-C) without reading the product's name.
- **R5.7.10, the decision row P344:** the firm-row builder, the group rule and the cache path left for
  `tracker/firm_view.py` at L4; Q-C kept as P313 left it (the pass's child unchanged); `_firm_fresh` and the reply's
  shape stayed (C-3); the stand-ins that forbid a read moved with their readers. It cites 120, P201, P215, P227,
  P229, P278, C-2 and P313.

**Pin-move list:** `LAYERS[4]`, `DOMAINS["shell"]`, R5.3.5's guard; `tests/test_runner.py` 4397; the forbidding
loops; the docs; the curated nodes (api, runner's P201 note, firm_view, the test file). The artifact edge: if the
curated map gives `api` a read or write of the firm cache file, it moves to `firm_view`.

**Patch sites:** section 4.0's P5.7 rows; `report tracker.api` before, `report tracker.api` and `report
tracker.firm_view` after.

**Register:** not reached.

**The reply contract:** `firm` and `firm-last` are shaped by `_firm_reply` and paged in the API, unchanged; P201's
fresh-versus-cached tests in test_api compare them byte for byte.

**Tests:** `tests/test_firm_view.py`, `test_api`, `test_runner`, `test_firm_cache`, `test_firm_pages`,
`test_page_rows`, `test_resident`, `test_reader_bench`, `test_golden`, `test_layers`, `test_single_source`,
`test_repo_map`, `test_suite_shape`.

**Stop and ask:** a moved name that reads `_not_walked`, `_warn` or a C-3 name (none is measured); `firm_view` needing
`screen_words`; a forbidding stand-in that cannot be shown to bite.

**Accept when:** section 4.1's shared accept-when; `firm_view` imports no `api`, `scheduling` or `screen_words`;
`grep -n "_firm_from_cache\|item_group" tracker/api.py` finds only import-backs and calls.
- **Windows:** no label (reads only; the cache's write is `firm_cache`'s, unchanged). **Office `-Tests`:** none of its
  own; section 6's step 2 covers a pass's fill.

---

### P5.8 `run_log.py`: the pass's report, the run log and the last-pass file (C-5)

- **Cost:** M.
- **Tier:** Opus. It moves the pass's report records every later runner job reads, and the run log's rotation.
- **Findings:** C-5.
- **Depends on:** P5.7.
- **Layer and domain:** L3, `pass`.

**What moves** (runner, at `f15eed1`):

| Lines | Names |
|---|---|
| 293-297 | The reminder modes block (`REMINDERS_AUTO`, `REMINDERS_ALWAYS`, `REMINDERS_NEVER`, `REMINDER_MODES`) whole: `RunReport`'s field takes one of them. |
| 299-305 | `LOG_FILENAME`, `LOG_MAX_BYTES`, `LOG_KEEP` with their comment |
| 395-398 | `log_path` |
| 468-563 | The last-pass file's and the pass's result words, from the `#:` comment over `LAST_PASS_FILENAME` (468-485), `LAST_PASS_AMBER_HOURS` and `_DAILY`, `PASS_RUNNING`, `PASS_SUCCEEDED`, `PASS_FAILED`, the `PASS_*` reasons and `PASS_REASONS` (508-551), the `LAST_PASS_*` lines (552-561). `AFTER_INSTALL_FILENAME` (492) stays. Re-measure: move the constants R5.8's closure computes from this range; a constant in it that no moved code reads stays. |
| 717-786, by closure | Of the notes block, what `EngagementRun` reads: `STAGE_NOTE` (723), `SKIP_INACTIVE` (727), `VIEW_NOT_REGENERATED` (734), `IGNORED_NOTE` (739), `SLOW_READING_SECONDS` and `SLOW_READING_NOTE` (750-751), each with its comment. The rest stays. |
| 859 | `LAST_PASS_MAX_BYTES` |
| 885-921 | The run log's codes, the `CODE_*` table whole, with its comment. |
| 934-1121 | `EngagementRun`, `RunReport`, `_warn` |
| 1727-1742 | `why_skipped` |
| 2338-2489 | `log_counts`, `log_codes`, `append_log`, `last_pass_path`, `_this_build`, `write_last_pass`, `_log_file`, `_log_a_failed_pass`, `amber_hours` (with the section headers over them). `PassFailed` (2412-2421) stays: only the runner raises and catches it. |
| 2492-2545 | `last_pass_line` |

`format_report` (2296-2335) stays: it reads `is_draft_day` (the draft-day rule, which stays) and the misfits heading
(P5.9's). Measured with the closure: no moved definition reads a definition that stays (`moved code reads staying
defs/consts: []` at `f15eed1`). `run_log` imports `checkpoint`, `ledger`, `store` (`last_pass_path` calls `store.store_path()`), `records`
(`ENGAGEMENT_LABELS`, `NO`), `ocr` (L2: `RunReport` holds the reading's
warning), `registry` (`Engagement`, `Misfit`, `SKIP_ROLLED_FORWARD`), `reminder`'s `APPROVED_NOTE` and
`APPROVED_THEN_EDITED`, `fsio`, `errors`, `settings` and the standard library (measure).

**Requirements:**

- **R5.8.1, the module.** `tracker/run_log.py` holds the table's code, byte for byte, under section 4.1's head. Its
  logger is `logging.getLogger("tracker.runner")`. Its docstring says: what one pass reports (the records the console,
  the page and the log read), the codes the run log says and the sentences the page says (decision 186), the run log
  and its rotation, the last-pass file the shell reads (P256), and why the records sit here (section 2.1).
- **R5.8.2, the runner imports back** what it still reads (measured: `EngagementRun`, `RunReport`, `_warn`,
  `why_skipped`, `append_log`, `write_last_pass`, `last_pass_path`, `_log_file`, `_log_a_failed_pass`,
  `REMINDERS_AUTO` and the modes it reads, `LOG_FILENAME`, `LOG_KEEP`, `LOG_MAX_BYTES`, `LAST_PASS_FILENAME`,
  `IGNORED_NOTE`, `STAGE_NOTE`, the `PASS_*` it reads, every `CODE_*` it reads).
- **R5.8.3, readers retargeted:** `api` (`LEFT_BEHIND_TO_MOVE` and `left_behind_warnings` stay runner's;
  `last_pass_line` comes from `run_log`; `runner.last_pass_path`, `runner.LAST_PASS_MAX_BYTES`,
  `runner.PASS_SUCCEEDED`, `runner.PASS_RUNNING` at api 3360, 3979-3985 read `run_log.`; `runner.why_skipped` at
  6208 reads `run_log.`); `firm_view`'s `runner.why_skipped` reads `run_log.why_skipped`; `scheduling.py` 105 keeps
  its runner flags; `tools/reader_bench.py`, if it reads a moved name; the prose (`settings.py` 703 and 975 and
  `store.py` 2205 name `runner.left_behind`, which stays; `content_check.py` 161 names
  ``runner.SLOW_READING_SECONDS``, which moves).
- **R5.8.4, the stand-ins:** `SLOW_READING_SECONDS` moves to `run_log` (test_runner 1875, 4854 and the string target
  at test_content_check 254, which becomes `'tracker.run_log.SLOW_READING_SECONDS'`); `append_log`,
  `write_last_pass` stay on `runner` (section 4.0).
- **R5.8.5, the run log's file pin.** `tests/test_errors.py` 245 (`("runner.py", "runs.log")` in
  `NOT_A_LOGGERS_FILE`) names `("run_log.py", "runs.log")`; its reason is unchanged.
- **R5.8.6, artifacts.**
  - `artifact:last-pass.json`: the curated edges `tracker/runner.py` writes and reads it move to `tracker/run_log.py`
    (`write_last_pass` and `last_pass_line` move); `tracker/api.py reads artifact:last-pass.json` stays (the API reads
    the file through `run_log`'s function, but the edge says who reads the file; keep it, and add none).
  - `artifact:runs.log`: `tracker/run_log.py writes artifact:runs.log` is **added** (`append_log` and
    `_log_a_failed_pass` move and append to it). The runner's own edges stay: `_say_the_pass_started` (runner 3604-3634
    at `f15eed1`) stays in the runner, reads the log's tail (`LOG_TAIL_BYTES`) and appends the `pass started` line
    through `append_rotating` with `LOG_MAX_BYTES` and `LOG_KEEP`, so `tracker/runner.py` still writes and reads
    `artifact:runs.log` (the curated map's two runner edges to it, `writes` and `reads`, stay as they are).
    `test_every_artifact_has_a_writer_and_a_reader_or_says_it_is_write_only` is the check.
- **R5.8.7, the test split.** `tests/test_run_log.py` with the tests the rule sends (the direct `last_pass_line`,
  `write_last_pass` and `append_log` calls are the candidates); helpers more than one file reads go to
  `tests/passes.py` (section 4.1), and the job then runs every test file that imports `passes` (section 3).
- **R5.8.8, the layer table.** `run_log` joins `LAYERS[3]` ("``run_log`` joins L3 with P345 (SPEC-architecture-p5
  P5.8): the pass's report, its codes, the run log and the last-pass file, out of ``runner``, which imports them back
  - ``registry`` and ``reminder`` (in-layer), ``ocr`` (L2), ``store``, ``records``, ``ledger`` (L1), ``checkpoint`` and L0;
  never ``scheduling``
  or ``api``.") and `DOMAINS["pass"]`.
- **R5.8.9, the docs.** "fifty-nine" becomes "sixty"; a line under L3; the module list. `docs/runbook.md`'s run log
  and last-pass paragraphs, where they name a function or file of the runner, name `run_log`.
- **R5.8.10, the decision row P345.** It cites 91, 186, 189, P223, P256, C-5 and P313.

**Pin-move list:** `LAYERS[3]`, `DOMAINS["pass"]`; test_errors 245; the string target at test_content_check 254; the
docs and the module list; the curated nodes and the artifact edges. `tests/test_build.py` 297 reads the runner's
`"--x"` flags from `tracker/runner.py`; no flag moves (the flags block, 433-466, stays), so it is unchanged.

**Patch sites:** section 4.0's P5.8 rows; `report tracker.runner` before, `report tracker.runner` and `report
tracker.run_log` after.

**Register:** not reached.

**The reply contract:** `last-pass` builds its reply in `api._last_pass` from the same file and words.

**Tests:** `tests/test_run_log.py`, `test_runner`, `test_api`, `test_after_install`, `test_scheduling`,
`test_api_entry`, `test_content_check` (its one string stand-in), `test_errors`, `test_resident`, `test_firm_view`,
`test_view` (its one read, test_view 670, retargets to `run_log.VIEW_NOT_REGENERATED`; section 4.0), `test_golden`,
`test_layers`, `test_single_source`, `test_repo_map`, `test_suite_shape`.

**Stop and ask:** a moved definition reading a definition that stays; a `CODE_*` read under another name.

**Accept when:** section 4.1's shared accept-when; `run_log` imports no `scheduling`, `api` or `runner`; the runner's
console output and run log lines for `tests/golden/pass.samples.json`'s pass are unchanged (test_golden).
- **Windows: label.** It moves the run log's rotation and the last-pass file's atomic replace. **Office `-Tests`:**
  `test_run_log,test_runner,test_errors`.

---

### P5.9 `status_page.py`: the practice status page; one misfits heading (C-5, C-6)

- **Cost:** M.
- **Tier:** Opus. It moves code out of the runner (rule (a)) and the page's reads of the store the walk left (P192).
- **Findings:** C-5; C-6 (the one second typing).
- **Depends on:** P5.8.
- **Layer and domain:** L3, `shell`.

**What moves** (runner, at `f15eed1`):

| Lines | Names |
|---|---|
| 313 | `STATUS_PAGE_FILENAME` with its comment |
| 728 | `RECORD_UNREADABLE` with its comment (read by `_engagement_status`; the runner imports it back) |
| 2259-2282 | `records_needing_a_person` |
| 2549-2977 | The status page's section from its header (2549): `STATUS_GENERATED` to `_STATUS_STYLE` (with `STATUS_MISFITS_HEADING`, `MISFIT_COLUMNS`, `RECORD_SIBLING`, `RECORD_FOREIGN`, `ACKNOWLEDGE_COMMAND`, `FOREIGN_UNLISTED`, `STATUS_COLUMNS`, `REVIEW_COLUMNS`; not `CHECKPOINT_NOT_PROVED`), `ParkedFile`, `_parked_files`, `_page_token`, `_page_title`, `_drafted_cell`, `_engagement_cells`, `write_status_page`, `_records_needing_a_person`, `_engagement_status`, `_under`, `status_report` |

Of the section's constants, `CHECKPOINT_NOT_PROVED` (2584-2585, with its comment) stays in the runner: its one
reader is `_pass` (3423). Every other constant in 2549-2615 is read by the moved code (the closure, measured) and moves. `status_page` imports from `run_log` (`EngagementRun`,
`RunReport`, `why_skipped`, `STAGE_NOTE`, `IGNORED_NOTE`, `CODE_RECORD_UNREADABLE`), and `page`, `page_rows`, `hold`,
`store`, `index`, `manifest`, `registry`, `reminder`, `records`, `settings`, `layout`, `ledger`, `fsio`, `errors`
(measure).

**Requirements:**

- **R5.9.1, the module.** `tracker/status_page.py` holds the table's code, byte for byte, under section 4.1's head;
  logger `tracker.runner`. Its docstring: the practice status page (decision 91, a page, not a workbook), read from
  the store the walk left (P192), written atomically, with nothing fetched (decision 190's policy through
  `page.document`).
- **R5.9.2, the runner imports back** (measured): `write_status_page`, `status_report`, `records_needing_a_person`,
  `STATUS_PAGE_FILENAME`, `STATUS_MISFITS_HEADING` (`format_report`), `RECORD_UNREADABLE`, and any status word its
  staying code reads. It drops the import-backs from `run_log` that only the moved code read: `IGNORED_NOTE` and
  `STAGE_NOTE` (R5.8.2 kept them for the status page's code; ruff is the check), and section 4.0's P5.9 row
  retargets the test reads of them through `runner`.
- **R5.9.3, one misfits heading** (C-6). `screen_words.MISFITS_HEADING` (with its `#:` comment, if it has one of its
  own) is deleted; `api` imports `STATUS_MISFITS_HEADING as MISFITS_HEADING` from `tracker.status_page`, so `vocab`'s
  `"misfits_heading": MISFITS_HEADING` reads byte for byte. Both were "Folders the App Leaves Alone"; a test pins
  `api.vocab()["household"]["misfits_heading"] == status_page.STATUS_MISFITS_HEADING` (api 1871 at `f15eed1`). Every test read
  of `screen_words.MISFITS_HEADING` or `api.MISFITS_HEADING` is retargeted to `status_page.STATUS_MISFITS_HEADING`.
- **R5.9.4, readers retargeted:** `api`'s `STATUS_PAGE_FILENAME` (api 319) from `status_page`; `view.py` 80's prose;
  `README.md` 379 (`tracker.runner.STATUS_PAGE_FILENAME` becomes `tracker.status_page.STATUS_PAGE_FILENAME`); every
  grep hit (section 3's grep includes `README.md`).
- **R5.9.5, the stand-ins** (section 4.0's P5.9 rows): `_parked_files`, `read_index`, `firm` and `product_name` move
  to `status_page` (the two string targets at test_runner 1199-1203 become `'tracker.status_page.firm'` and
  `'tracker.status_page.product_name'`); `load_manifest` and `write_text_atomically` sit on `runner` and
  `status_page`; `write_status_page` stays on `runner`.
- **R5.9.6, the `follow=False` pin.** `tests/test_runner.py` 4397 becomes `["firm_view.py", "status_page.py"]`
  (runner's three hits, 2644, 2662, 2896, move); its docstring follows.
- **R5.9.7, artifacts.** `tracker/runner.py writes artifact:status.html` moves to `tracker/status_page.py`.
- **R5.9.8, the test split.** `tests/test_status_page.py` (the direct `status_report` calls are the candidates).
- **R5.9.9, the layer table.** `status_page` joins `LAYERS[3]` ("``status_page`` joins L3 with P346
  (SPEC-architecture-p5 P5.9): the practice status page, out of ``runner`` - ``run_log``, ``registry`` and
  ``reminder`` (in-layer), ``store``, ``index``, ``manifest`` (L1) and ``page``, ``page_rows``, ``hold`` (L0); never
  ``scheduling`` or ``api``.") and `DOMAINS["shell"]`.
- **R5.9.10, the docs.** "sixty" becomes "sixty-one"; a line under L3; the module list; the runbook's status page
  paragraph if it names the runner's function.
- **R5.9.11, the decision row P346:** the status page left for `tracker/status_page.py`; the API's misfits heading is
  the page's own word (C-6). It cites 91, 159, 186, 190, 192, C-5, C-6 and P313.

**Pin-move list:** `LAYERS[3]`, `DOMAINS["shell"]`; test_runner 4397; the two string targets; `screen_words`'
`MISFITS_HEADING` and its readers; `README.md` 379; the docs; the curated nodes and the artifact edge.

**Patch sites:** section 4.0's P5.9 rows; `report tracker.runner` before, and `report tracker.runner` and `report
tracker.status_page` after.

**Register:** not reached.

**The reply contract:** `vocab`'s `misfits_heading` carries the same text; `tests/golden/replies.list.keys.json`
holds keys, and R5.9.3's test holds the value.

**Tests:** `tests/test_status_page.py`, `test_runner`, `test_run_log`, `test_api`, `test_screen_words`,
`test_page_rows`, `test_page`, `test_view`, `test_checkpoint`, `test_after_install`, `test_scheduling`,
`test_resident`, `test_golden`, `test_layers`, `test_single_source`, `test_repo_map`, `test_suite_shape`.

**Accept when:** section 4.1's shared accept-when; `status_page` imports no `scheduling`, `api`, `runner`; the page
the sample pass writes is byte-identical before and after (test_runner's page tests and test_golden).
- **Windows: label.** It moves `write_status_page`, which calls the atomic replace (`write_text_atomically`), as P5.8
  and P5.10 take the label for the run log's and the hint's: one rule for the three. **Office `-Tests`:**
  `test_status_page,test_runner`.

---

### P5.10 `pass_order.py`: the household order hint (C-5)

- **Cost:** S.
- **Tier:** Opus (rule (a)).
- **Findings:** C-5.
- **Depends on:** P5.9.
- **Layer and domain:** L4, `pass`.

**What moves** (runner, at `f15eed1`):

| Lines | Names |
|---|---|
| 836-875, by closure | `PASS_ORDER_FILENAME`, `PASS_ORDER_VERSION`, `_PASS_ORDER_READ`, `PASS_ORDER_MAX_BYTES`, `ORDER_HINT_UNREADABLE`, `NOT_SERVED_TWICE`, the `WHY_*` reasons (868-875), each with its comment. `NOT_SERVED_TWICE_EXIT_CODE` (865) and `LAST_PASS_MAX_BYTES` (moved in P5.8) do not move here. |
| 2061-2256 | `_working`, `_read_order_hint`, `_hint_households`, `_parsed_order_hint`, `_completed_key`, `_mark_started`, `_write_order_hint`, `_why_not_served`, `_keep_the_order` |

The two codes they read (`CODE_ORDER_HINT_UNREADABLE`, `CODE_NOT_SERVED_TWICE`) are `run_log`'s since P5.8.
`pass_order` imports from `run_log` (`EngagementRun`, `RunReport`, `_warn`, `why_skipped`, the two codes), `fsio`
(`write_text_atomically`, `full_sync`), `store`, `errors`, `json` (measure).

**Requirements:**

- **R5.10.1, the module.** `tracker/pass_order.py`, byte for byte, logger `tracker.runner`; docstring: P217's hint
  (the order the last pass served households in, so one that was not served twice goes first), read with a size
  bound, never trusted past its version, written atomically.
- **R5.10.2, the runner imports back** `_working`, `_read_order_hint`, `_completed_key`, `_mark_started`,
  `_write_order_hint`, `_keep_the_order` and `PASS_ORDER_FILENAME` (`left_behind` reads it).
- **R5.10.3, the stand-ins:** `write_text_atomically` sits on `pass_order` and `status_page` (section 4.0).
- **R5.10.4, artifacts.** `tracker/runner.py` reads and writes `artifact:pass-order.json` move to
  `tracker/pass_order.py`.
- **R5.10.5, the test split.** `tests/test_pass_order.py` (the direct `_read_order_hint` and `_write_order_hint`
  calls are the candidates).
- **R5.10.6, the layer table.** `pass_order` joins `LAYERS[4]` ("``pass_order`` joins L4 with P347
  (SPEC-architecture-p5 P5.10): the household order hint, out of ``runner`` - ``run_log`` (L3), ``store`` (L1) and
  ``fsio`` (L0); never ``scheduling`` or ``api``.") and `DOMAINS["pass"]`.
- **R5.10.7, the docs.** "sixty-one" becomes "sixty-two"; a line under L4; the module list.
- **R5.10.8, the decision row P347.** It cites P217, 186 and C-5.

**Pin-move list:** `LAYERS[4]`, `DOMAINS["pass"]`; the docs; the curated nodes and the artifact edges.

**Patch sites:** section 4.0's P5.10 row; `report tracker.runner` before, `report tracker.runner` and `report
tracker.pass_order` after.

**Register:** not reached.

**Tests:** `tests/test_pass_order.py`, `test_runner`, `test_run_log`, `test_api`, `test_after_install`,
`test_scheduling`, `test_golden`, `test_layers`, `test_single_source`, `test_repo_map`, `test_suite_shape`.

**Accept when:** section 4.1's shared accept-when; `pass_order` imports no `scheduling`, `api` or `runner`; runner is
under 3,000 lines (it was 3,640).
- **Windows: label.** It moves the hint's atomic replace and the flush (`full_sync`) after a household starts.
  **Office `-Tests`:** `test_pass_order,test_runner`.

---

### P5.11 `letter_render.py`: the letter's look (C-8)

- **Cost:** S.
- **Tier:** Sonnet. A small pure move out of the reminder (not a module rule (a) names), with no stand-in to move.
- **Findings:** C-8.
- **Depends on:** P5.10.
- **Layer and domain:** L0, `pass`.

**What moves** (reminder, at `f15eed1`):

| Lines | Names |
|---|---|
| 540-591 | `Emphasis`, `STAGE_COLOURS`, `HOLD_COLOUR`, `LETTER_INK`, `STAGE_EMPHASIS`, with their comments |
| 646-724 | `Run`, `Section`, `Letter` (the letter's shapes; `Letter.text()` is the one place the letter becomes text) |
| 1174-1178, by closure | `RUN_TARGET`, `RUN_DEADLINE_DATE`, `RUN_CONSEQUENCES` (read by `run_emphasis`); `_RUN_MARK` stays if only the reminder's run cutting reads it (measure) |
| 1559-1611 | The section header, `stage_emphasis`, `stage_colour`, `_styled`, `run_emphasis`, `_emphasised`, `_paragraph` |
| 1714-1738 | `render_text_html`, `_with_last` |

**What stays in `reminder`:** `render_html` (1612-1679; typed by `ReminderDraft`, section 2.1), `pasted_text`
(1682-1703) and `split_pasted` (1706-1711), and every decision, record and file write. `letter_render` imports `page`
and the standard library only.

**Requirements:**

- **R5.11.1, the module.** `tracker/letter_render.py`, byte for byte, under section 4.1's head; it does not log.
  Docstring: the letter's emphasis ladder and colours (decision 118; one table for the letter and the app's preview),
  the letter's shapes, and the HTML renderers for the clipboard (inline styles only, nothing fetched); why
  `render_html` stays (it is typed by the reminder's own `ReminderDraft`); that it sends nothing and imports no
  network module (decision 115).
- **R5.11.2, the reminder imports back** what its staying code reads (measured: `Letter`, `Run`, `Section`,
  `RUN_TARGET`, `RUN_DEADLINE_DATE`, `RUN_CONSEQUENCES`, `LETTER_INK`, `stage_colour`, `stage_emphasis`, `_styled`,
  `_emphasised`, `_paragraph`, `_with_last`). `STAGE_COLOURS`, `STAGE_EMPHASIS` and `HOLD_COLOUR` have no reader left
  in the reminder, so the API's reads of them are retargeted here (R5.11.3).
- **R5.11.3, readers retargeted:** `api`'s `reminder.STAGE_COLOURS`, `reminder.STAGE_EMPHASIS` (1218-1219),
  `reminder.HOLD_COLOUR`, `reminder.LETTER_INK` (2053-2054), `reminder.stage_emphasis` (5300), `reminder.run_emphasis`
  (5319), `reminder.render_text_html` (5393) read `letter_render.`; `reminder.render_html`, `pasted_text`,
  `split_pasted` stay.
- **R5.11.4, the test split.** `tests/test_letter_render.py` with the tests the rule sends (`render_html`'s tests
  stay; `test_the_emphasis_table_matches_the_design_notes`, test_reminder 1346, is a candidate), or direct tests: at
  least one that `render_text_html` keeps a person's paragraphs, in the letter's type, with no style block and no
  address.
- **R5.11.5, the layer table.** `letter_render` joins `LAYERS[0]` ("``letter_render`` joins L0 with P348
  (SPEC-architecture-p5 P5.11): the letter's emphasis, colours, shapes and HTML, out of ``reminder``, which imports
  them back - ``page`` and the standard library.") and `DOMAINS["pass"]`.
- **R5.11.6, the docs.** "sixty-two" becomes "sixty-three"; a line under L0; the module list.
- **R5.11.7, the decision row P348.** It cites 115, 117, 118, C-8 and P313.

**Pin-move list:** `LAYERS[0]`, `DOMAINS["pass"]`; the docs; the curated nodes. `ENFORCERS["rule:nothing-is-ever-sent"]`
is unchanged: the reminder still drafts and stops; rendering sends nothing.

**Patch sites:** none change (`report tracker.reminder` 12 before and after; `report tracker.letter_render` 0).

**Register:** not reached.

**The reply contract:** `reminder` and `approve` replies carry the same values (`_letter_payload` reads the same
functions).

**Tests:** `tests/test_letter_render.py`, `test_reminder`, `test_api`, `test_resident` (the job edits `api`, R5.11.3,
as every job that edits it runs the register's test), `test_runner`, `test_shell` (the preview reads the vocabulary's
emphasis), `test_page`, `test_golden`, `test_layers`, `test_single_source`, `test_repo_map`, `test_suite_shape`.

**Accept when:** section 4.1's shared accept-when; `letter_render` imports only `page` and the standard library.
- **Windows:** no label. **Office `-Tests`:** none.

---

### P5.12 after_install's jobs as a table (C-10)

- **Cost:** M.
- **Tier:** Opus (rule (e)): it restructures the one-time step path, not a move.
- **Findings:** C-10; decision 209.
- **Depends on:** P5.11.
- **Layer and domain:** no new module.

At `f15eed1`, `_run` (after_install 893-981) calls six jobs in order - the schedule (`_schedule`, with the Mac's
first-pass kick `_first_pass`, and the refused, unusable and switched-off branches), `_time_machine`, `_check`,
`_clear_test_cache`, `_remove_the_retired_caches`, `_ready_the_overview` - then builds `failed` from a hand-picked
tuple (`(schedule, excluded, check, cache)`), assembles `lines` with per-job conditions (956-970), writes the record
and fills `AfterInstall` field by field. A further job touches five places.

**Requirements:**

- **R5.12.1, the characterisation first.** A commit before any change adds
  `test_each_jobs_outcomes_and_their_crossings_give_todays_record_lines_and_reply` to `tests/test_after_install.py`,
  driven by a committed case table. Every combination of the factors below would be 13,824 cases (over 10 MB at
  about 1 KB a row, and most rows repeat one another: when the root is refused, `_check` and `_ready_the_overview`
  are never called, after_install 930-937), so the table is built this way:
  - **The stand-ins**, on `after_install` unless named: `_saved_root`, `_saved_preference`, `_save_choice` (the
    unusable choice), `_schedule`, `_first_pass`, `_time_machine`, `_check`, `_clear_test_cache`,
    `_remove_the_retired_caches`, `_ready_the_overview`, `read_record`, `record_path` (a `tmp_path` file, or one whose
    write raises `OSError`), `program_identity`, `designation_now`, `write_json_atomically`, `dt` (a fixed clock, so
    `ran_at` is the same on every run), `settings.host_system` and `settings.product_name` (the switched-off sentence
    formats it). Each stand-in returns a value named by the case, never a value computed from the machine.
  - **The factors and their levels:** the root (good, refused); the preference (good, missing, unusable through
    `start`/`every`); switched off (no, yes); the host (Windows; a Mac with the kick due; a Mac already kicked for this
    program); the schedule's own outcome when `_schedule` runs (registered, failed; on a Mac with the kick due, kicked
    by `_first_pass` or not); Time Machine (`None`, a sentence, failed); the check (clean, with findings, failed; its
    sentence equal to the schedule's or not); the cache (`None`, done, failed); the retired caches (`None`, a
    sentence); the overview (`""`, a sentence); the record (writable, refused); the designation (a string, not one).
  - **The rows:** (1) one base case (every factor at its first level); (2) every factor's every other level varied
    alone from the base; (3) the crossings that change the output: the schedule's outcome (registered, failed) × the
    check's sentence (equal, not) × the check (failed, not); each member of `failed` (schedule, Time Machine, check,
    cache) alone and all four at once with two of their sentences equal (the `dict.fromkeys` order), each × the record
    refused; the refused root × each level of Time Machine, the cache, the retired caches, the record and the host;
    the missing preference, the unusable one and the switched-off branch, each × the Mac with the kick due; a failed
    sentence already in `lines` and one not. That is under 200 rows; the builder may add rows and names each added
    kind in after.txt.
  - **What a row records:** the case's factor levels by name, the record written (or `None` when refused), `lines`,
    `failed` and `AfterInstall.reply()`, computed by today's `_run`. The rows live in
    `tests/after_install_cases.json` (a data file beside the tests, as `tests/golden/`'s are; not under
    `tests/golden/`, which no job changes; `test_suite_shape` guards Python imports only), under 200 KB, generated once at the job's base with the
    generator's command in the test's docstring, and committed in the same commit as the test. To hold the cap, every
    sentence a stand-in returns is a short name chosen by the case (`"tm-sentence"`, `"check-findings"`), never a
    realistic paragraph, and the file is written compact, one row to a line (`json.dumps(row, separators=(",", ":"))`
    per line, the rows in a JSON array). A second test,
    `test_the_case_table_holds_every_level_and_every_named_crossing`, fails if a level or a crossing listed here has no
    row, so the table cannot shrink silently.
  - The table is not edited by any later commit of the job; the restructure is held to it (R5.12.5).
- **R5.12.2, one table.** `_run`'s jobs become one tuple, `_JOBS`, in today's run order. Each entry names the job's
  key, the function that runs it (taking what it needs from a small run context: root, refused, preference,
  unusable, switched off, the kick, the reason, the checkout and the earlier steps' results), whether its failure
  counts in `failed` (today: the schedule, Time Machine, the check and the cache do; the retired caches and the
  overview never do, P218's "never a failure"), and how its step adds to `lines` (each entry's own rule, written to
  reproduce today's exactly: Time Machine only when it has a sentence and did not fail; the check only when its
  sentence is not the schedule's, then its findings indented, then `FINDINGS_WAIT` when it has findings; the cache
  only when it did not fail; the retired caches when they ran; the overview when it has a sentence). `failed` and
  `lines` are built by one loop over the entries' results; the failed sentences not yet in `lines` follow, as today.
  **How an entry reaches its job:** each entry's runner is a small module-level function (`def _run_check(context):
  return _check(context.root)` and the like; not a lambda, so its name shows in a traceback and in test_errors' keys)
  whose body calls the job **by its module-global name when it runs**. `_JOBS` never holds a job function itself
  (`("check", _check, ...)` would capture the object at import, so a later `monkeypatch.setattr(after_install,
  "_check", ...)`, R5.12.1's stand-ins and test_after_install 1286's on `_schedule` among them, would no longer reach
  the call, and `patch_sites check` does not follow a reference captured in a tuple). R5.12.1's table passing after the
  restructure, with its stand-ins on the module, is the proof.
- **R5.12.3, what stays as it is.** `AfterInstall`'s fields and `reply()`, the record's keys and their order, the
  schedule's refused, unusable and switched-off branches and the Mac kick (inside the schedule entry's function),
  `run()`'s lock (`_one_at_a_time`), `launch()`, and every sentence. A further job is one entry and its own function:
  `_run` does not change. `_run`'s docstring says so, and CLAUDE.md's "as a further job in its `run()`" stays true.
- **R5.12.4, the names.** Every function a test or the stand-in list names keeps its name and signature: `_schedule`,
  `_first_pass`, `_time_machine`, `_tmutil`, `_check`, `_clear_test_cache`, `_remove_the_retired_caches`,
  `_ready_the_overview`, `run`, `launch`, `read_record`, `program_identity`, `CHECKOUT`, `LOCK_WAIT_SECONDS`,
  `LOCK_POLL_SECONDS`. test_errors 400-406's `(file, function)` keys stay valid.
- **R5.12.5, the characterisation holds.** R5.12.1's test passes unchanged after the restructure, as do every other
  test of test_after_install, test_api's after-install tests and test_shell's (5783, `read_record`).
- **R5.12.6, the decision row P349:** after_install's jobs are one table in run order; a further one-time step is an
  entry and its function (decision 209); the record, the lines and the reply are unchanged, held by a committed case
  table of each job's outcomes and the crossings that change the output (R5.12.1). It cites 209, P218, P234, P257, SPEC-mac R7 and R27, and C-10.
- **R5.12.7, the curated node.** after_install's notes' stale import set (P3.4 review note 4: "Layer 4: imports
  scheduling, store, registry, ledger, door, ...") is rewritten to its imports at the job's head
  (`python tools/repo_map.py show tracker/after_install.py` gives them), and one sentence names `_JOBS`.

**Pin-move list:** test_after_install (R5.12.1's two tests, first commit); `tests/after_install_cases.json` (new, first
commit); the curated node.

**Patch sites:** after_install's fifteen stand-ins keep their targets; R5.12.1's stand-ins are new and on
`after_install` (plus `settings.host_system` and `settings.product_name`); none is `unread` after the restructure,
because each job is read by its name inside its entry's function; `check` passes.

**Register:** not reached.

**The reply contract:** `after-install`, `install-schedule`, `set-schedule`, `move-schedule-here` return
`AfterInstall.reply()`, unchanged (R5.12.1).

**Tests:** `test_after_install`, `test_api`, `test_api_entry`, `test_shell`, `test_scheduling`, `test_errors`,
`test_resident`, `test_golden`, `test_layers`, `test_single_source`, `test_repo_map`.

**Stop and ask:** an entry's line rule that cannot be written without a branch on another entry's key inside the
loop (the check's "not the schedule's sentence" is the one cross-entry rule: it may read the earlier results the
context carries); any table row that differs after the restructure.

**Accept when:** R5.12.1's table is unchanged after its first commit and passes; it is under 200 KB and every named
level and crossing has a row; adding a scratch seventh job is one entry and one function (after.txt shows the diff,
not committed); a scratch stand-in on `after_install._check` set after import is still called (shown by the table's
check rows); `tests/golden/` is unchanged.
- **Windows: label.** after_install is Setup.bat's last step and drives Task Scheduler. **Office `-Tests`:**
  `test_after_install,test_api,test_api_entry`; **installer step:** section 6, step 3.

---

### P5.13 A family test file is owned by its module (E-3, the map)

- **Cost:** S.
- **Tier:** Opus (rule (c)): it changes how `tools/repo_map.py` derives the owner edge.
- **Findings:** E-3.
- **Depends on:** P5.12.
- **Layer and domain:** no new module.

**Requirements:**

- **R5.13.1, the rule.** `_owner_edges` (tools/repo_map.py 717-741) also draws `tests/test_<stem>_<family>.py` →
  `tracker/<stem>.py` as a `tests` edge when `<stem>` is the stem of a module under `tracker/` and
  `<stem>_<family>` is no owned file's stem (so `tests/test_api_entry.py` stays `api_entry.py`'s, and
  `tests/test_store_check.py` stays `store_check.py`'s). The longest stem that matches wins. Files outside
  `tracker/` (scripts, the renderer's) keep the exact-name rule.
- **R5.13.2, nothing changes today.** At `f15eed1` the rule draws no new edge (measured: with `tracker/` modules
  only, no test file matches; without that limit it would claim `test_pilot_installer.py`, `test_pilot_ui.py` and
  `test_shell_menu.py` for `pilot.js` and `shell.js`, which is why the limit is there). `python tools/repo_map.py
  build` before and after gives the same derived facts; after.txt shows the diff empty.
- **R5.13.3, tests.** `tests/test_repo_map.py` gains cases on made-up trees: a family file owned by its module; a
  family file whose name is another module's stem left to that module; a family file of a non-`tracker/` stem not
  owned; two family files of one module both owners.
- **R5.13.4, CLAUDE.md.** In "Read the test edges precisely" (CLAUDE.md 45-46, wrapped as it is there), the bullet "**tested by** — the test file that owns the
  module by name (`tests/test_filer.py` → `tracker/filer.py`). This is coverage." becomes "**tested by** — the test
  file that owns the module by name (`tests/test_filer.py` → `tracker/filer.py`), or a family file split from it
  (`tests/test_api_firm.py` → `tracker/api.py`, decision P350). This is coverage." No other CLAUDE.md line changes.
- **R5.13.5, the decision row P350:** a `tests/test_<module>_<family>.py` owns `tracker/<module>.py`, so a big test
  file can split by family and an affected-tests run still finds every part (E-3; Jason, 2026-09-29: each file its
  own process). It cites E-3, 207, 211 and P312.

**Pin-move list:** `tools/repo_map.py` `_owner_edges` and its docstring; `tests/test_repo_map.py`; CLAUDE.md's one
bullet; `docs/repo-map.json` and `.md` regenerated (`update`, the generator's hash forces a full rebuild).

**Tests:** `test_repo_map`, `test_single_source` (it quotes CLAUDE.md), `test_layers`.

**Accept when:** R5.13.2's empty diff; `repo_map.py check` passes.
- **Windows:** no label. **Office `-Tests`:** none.

---

### P5.14 `test_api.py` and `test_runner.py` split by command family (E-3)

- **Cost:** M.
- **Tier:** Sonnet. Test files moved by a banner table, with a collect-only proof.
- **Findings:** E-3.
- **Depends on:** P5.13.
- **Layer and domain:** no new module.

What is left of `tests/test_api.py` (11,687 lines at `f15eed1`) and `tests/test_runner.py` (5,825) after the move jobs
is split by its own section banners into family files; each test moves byte for byte with its banner's section.

**Requirements:**

- **R5.14.1, the families.** By banner (the banner's text is the anchor; line numbers at `f15eed1` are a guide). A
  banner is a top-level comment line that starts `# ---`, `# ===` or `# ──`; all three forms are used in both files
  (`grep -nE "^# ?(-{3,}|={3,}|──)" tests/test_api.py tests/test_runner.py` lists them: 47 in test_api, of which
  four are `# ──` (2036, 10914, 10952, 10977), and 29 in test_runner at `f15eed1`, each named in the tables below). A test belongs to the section of the nearest banner
  above it.

  | File | Banners of `tests/test_api.py` |
  |---|---|
  | `test_api.py` (stays) | the contract (85); vocabulary (2785); a click walks nothing (4905); decision 193: replies never go quiet (7197); one spawn per click (7715); Title Case for every drawn word (9685); P276: the engine's commands (10266); `# ──` P265-P280 (SPEC-ui-menu-small): the side panel's and the sort buttons' words (10914); `# ──` P271-P273, P275 (SPEC-ui-menu-layout): the menu's and the household card's words (10952) |
  | `test_api_returns.py` | create (195); create + scan (325); returning clients (411); the calendar and the prior (1703); decision 137: the security review (5534) |
  | `test_api_review.py` | needs review (507); the review queue, triaged (815); a person's action is judged against the record (3092); recovery is the person's: the moved card (3219); statuses in a preparer's words (8139); decision 201: an unnamed issuer's card (8247); every file name on the page is a live link (9476) |
  | `test_api_editor.py` | engagement details (1266); edit, lock and names (1421); decision 142: accepted, not asked (5787); decision 144: short names (6002); decision 160: a save keeps (6103); the form inputs, 2026-10-12 (11241) |
  | `test_api_root.py` | the root (1889); `# ──` P277: the list names the last-pass file (2036; about 750 lines to the vocabulary banner, holding the set-root, schedule, pilot-record and after-install tests, which are the root's section continued); decision 131: the room a return has (5154); decision 159: the record's checkpoint (7040) |
  | `test_api_household.py` | the household, in the app (3781); one inbox, the household rollover, the sharing (4090); decision 196: the roll is the household on screen (4194); the name on the page (4400); the household routes: the feed list (4562); what we have received, at once (5095); decision 188: one name rule (6624); decision 188: the door, the checked root (6677); decision 188: the folder is the name (6767); pilot P141, P170, P172: linked households and the form (10005) |
  | `test_api_reminder.py` | the reminder card (3438) |
  | `test_api_firm.py` | firm (8646); the firm view's cache (9028); a wait says what it shows (10447); the Overview's last counts at launch (10538); `# ──` P278: the engine pages the firm lists (10977, with `_forbid_the_walk` at 10991) |

  | File | Banners of `tests/test_runner.py` |
  |---|---|
  | `test_runner.py` (stays) | the Saturday (205); the full pass (267); the gate, and the record (453); failure isolation (632); reporting (751); discovery end to end (807); an approved draft, in the pass (1233); the pass cannot go quiet (2247); errors are classes, end to end (4160); what an earlier version left (4577); a budget in counts (5508) |
  | `test_runner_household.py` | the household pass (1327); the household routes: the feed list (1623); what we have received, live (1910); decision 131: the room a return has (1990); the bounded household (2868); decision 188: the folder is the name, one door (3271) |
  | `test_runner_watch.py` | Run now (2261); watched, and stoppable (4400); a scheduled pass off Windows ends itself (5600) |
  | `test_runner_reports.py` | the practice on a page (966); decision 159: records that need a person (3592); the last-pass file (3974); a checkpoint that cannot be asked (4058); the page reads the store the walk left (4251); the run log: counts and codes (4801); the firm view's cache, filled (5072); the pass's two firm-wide reads (5308); the pass-order hint (5352) |

  Every banner at `f15eed1` is in a table. A banner whose tests all moved to a module's own file in P5.4-P5.10 is not
  recreated. A banner not in the table (one added after `f15eed1`) stays in the main file and is named in the
  report; before.txt runs the banner grep above and shows every hit placed.
- **R5.14.2, the helpers.** A module-level helper, constant or fixture that more than one of the resulting files reads
  moves to `tests/api_driver.py` (the API's) or `tests/passes.py` (the runner's), in section 4.1's form; one that one
  file reads moves with it. `demo_root` (test_api 59) is the largest; `COUNTS` (56) and the `_a_*` builders follow
  their readers.
- **R5.14.3, pins on the files' names.** Every reader of a moved test's place is retargeted: `tests/tripwire/sitecustomize.py`
  59's prose (`tests/test_api.py:4232`), the docstrings that say a claim is `tests/test_api.py`'s or
  `tests/test_runner.py`'s (`test_checkpoint` 4-5, `test_resident` 11, `test_firm_pages` 9, `test_firm_cache` 4,
  `test_manifest` 99, `test_page` 5, `wording.py` 7, `passes.py` 10, `api_driver.py` 10), the curated nodes of the
  test files, and any guard that names a test file (grep `test_api\b\|test_runner\b` in `tests tools pilot docs`).
  `pilot/mactest/PROMPT.md`'s list is P5.15's.
- **R5.14.4, the owners.** After `python tools/repo_map.py update`, `show tracker/api.py` lists every
  `tests/test_api_*.py` (but `test_api_entry.py`) as **tested by**, and `show tracker/runner.py` every
  `tests/test_runner_*.py` (P5.13's rule).
- **R5.14.5, curated nodes.** Each new test file gets one, in `tests/store_helpers.py`'s form (a role: which family;
  a note: split from `test_api.py` by P5.14 so each runs as its own process).
- **R5.14.6, the writers derivation.** The test holding `_writers_in_the_package` (test_api 7114-7166, decision 159's
  E5; banner "the record's checkpoint", so `test_api_root.py`) gains `"mark-shared" in derived` beside
  `"accept-folder-name"` (the carry-forward item).

**Pin-move list:** as R5.14.3; `test_suite_shape`'s view of the helper modules.

**Tests:** every resulting file, each as its own process; every test file that imports a helper module the job
edits (section 3's rule: for `tests/api_driver.py`, test_golden, test_rollover and test_shell besides the family
files; for `tests/passes.py`, test_golden, test_page_rows and test_shell besides them); `test_suite_shape`,
`test_tripwire`, `test_layers`, `test_single_source`, `test_repo_map`, and the test files whose docstrings R5.14.3
edits (`test_checkpoint`, `test_resident`, `test_firm_pages`, `test_firm_cache`, `test_manifest`, `test_page`) only
if more than a docstring changes in them (after.txt shows the diff).

**Stop and ask:** a test whose banner section cannot move without a helper it shares with a file the table does not
name; a fixture whose scope or autouse would change by moving.

**Accept when:**
- `python -m pytest --collect-only -q` before and after differ only in the moved tests' file part, plus R5.14.6's
  change of one assert (no new id); the sed in after.txt shows it.
- No resulting file is over 3,000 lines (measure; report the sizes).
- **Windows:** no label. **Office `-Tests`:** none of its own; section 6's lists name the families.

---

### P5.15 Phase 4's loose ends: prose, the Mac kit's list, the memory test, curated notes

- **Cost:** S.
- **Tier:** Sonnet.
- **Findings:** section 2.2's phase 4 items.
- **Depends on:** P5.14 (the Mac kit's list must see every split).
- **Layer and domain:** no new module.

**Requirements:**

- **R5.15.1, prose.** Each sentence corrected to what is true, in its paragraph's style, and nothing else in the file:
  - `tracker/index.py` 42-43: "so a stand-in on ``filer.read_index`` reaches the filer's own callers and nobody
    else's" names the filer's family (a stand-in on each module that reads the name, P331's rule).
  - `tracker/door.py` 166: "the filer's walks and its step check ask it" names ``inbox``'s walks and ``intents``'
    step check (and the filer's `_prune_empty_dirs`, measure).
  - `tracker/scaffold.py` 41-42: "the filer at layer 3" names ``readme_ack`` (layer 3).
  - `tracker/filer.py` 165-169: the P4.9 paragraph is one sentence, as section 4.1 of phase 4 asked.
  - `tools/backtest.py` 231: "(with ``ocr=True`` there is no reading child)" says the reading runs in a child of its
    own for each document (`route_file` → `read_once` → `judge_bounded` → `run_in_child`, one session per document,
    as `docs/tools.md` 165 says), and the rest of the paragraph is read against that.
  - `tests/test_index.py` 96: `family = (filer, copies, intents, inbox, readme_ack, actions)`, so the docstring's
    "the filer and the modules carved out of it" is true; the test's docstring gains one sentence for `readme_ack`,
    in the form P333 and P335 used for theirs: since P334 (P4.8) it is of the family too, and binds none of the three
    names today, so it is asked in case a fourth crosses into it (measured at `f15eed1`: `readme_ack` imports none of
    `PRIVATE_CROSSING`, so the assert's result is unchanged).
- **R5.15.2, the memory test.** `tests/test_reader_child.py::test_a_linux_childs_memory_is_its_resident_pages` (277)
  measures pages that are certainly new: `held = mmap.mmap(-1, 64 * 1024**2)` written one byte per page
  (`mmap.PAGESIZE` steps), in place of `bytearray(b"x" * (64 * 1024**2))`, then closed. The claim (`after - before
  >= 48 * 1024**2`), the name and the docstring's figures stay; the docstring gains why (a block the allocator kept
  resident from an earlier test could serve a `bytearray` without growing the process; P4.12's finding). The test is
  run 30 times on PY314 after the change (after.txt counts the failures: none expected); the orchestrator updates the
  baseline note.
- **R5.15.3, the Mac kit's list.** `tests/test_pilot.py` gains `KIT_TESTS_SPLIT`, after `KIT_TESTS_ADDED` (483), with
  a comment: the files split out of a listed file by SPEC-architecture's jobs (phases 2-5), so the Mac check still
  runs every test that was in a listed file. **The rule** (re-measure at the job's head): a `tests/test_*.py`
  created by a SPEC-architecture commit is a split of a listed file when some SPEC-architecture commit removes a
  `def test_` line from a listed file (`KIT_TESTS + KIT_TESTS_ADDED`) and adds one to it (`git log --diff-filter=A
  --format=%h -- tests/test_*.py`, then `git log -p` of each created file against the listed ones; after.txt shows
  the commands and their result). Measured at `f15eed1`, with the commit that moved the tests:
  - from `test_settings`: `test_hold` (eda8e57, six tests), `test_errlog` (4249a22, three);
  - from `test_store`: `test_admission`, `test_store_check`, `test_verify` (P3.2, P3.4, P3.5);
  - from `test_filer`: `test_index` (965acae, P2.9, four tests), `test_copies`, `test_intents`, `test_inbox`,
    `test_readme_ack`, `test_actions` (P4.4-P4.9);
  - from `test_shell`: `test_renderer_seams` (41d02c6, J3: the renderer-guards test moved and widened);
  - from `test_content_check`: `test_keywords`, `test_verdicts`; from `test_ocr`: `test_reader_child`;
  - from `test_api`: `test_screen_words`, `test_request_edit`, `test_household_edit`, `test_creation`,
    `test_firm_view` and P5.14's `test_api_*` files; from `test_runner`: `test_run_log`, `test_status_page`,
    `test_pass_order` and P5.14's `test_runner_*` files.
  - Not splits, measured: `test_bounds` (from `test_records`, not listed), `test_replies`, `test_corpus`,
    `test_typecheck`, `test_golden`, `test_patch_sites`, `test_suite_shape`, `test_samples` (new tests, or moved from
    a file not listed). A file of this phase whose tests the rule moved none of (R5.3.9's `test_screen_words` holds
    only new tests) is still listed: it holds the moved code's tests from now on.
  `pilot/mactest/PROMPT.md` 85's `--tests` line appends them in that order; its "Why these" paragraph gains one
  sentence saying why; `pilot/mactest/RESULTS-TEMPLATE.md` gains a row per file; the two tests at test_pilot 799 and
  832 compare against `KIT_TESTS + KIT_TESTS_ADDED + KIT_TESTS_SPLIT`, and test_pilot 799's docstring ("the
  twenty-two the SPEC lists, then the four the last job adds with its reason") gains the third group: "then the files
  split out of those by SPEC-architecture (P351)". `pilot/SPEC-mac.md` R33 gains one sentence pointing at the row:
  the one SPEC this phase edits, as the brief asks (SPEC-mac R33's list needs it with a decision row); section 3's
  "the SPECs are history" otherwise holds.
- **R5.15.4, curated notes.** On the intents node, the sentence naming `RECORD_PRESERVE_INTENTS` (a switch no code
  defines) is removed or says what the code does (measure: grep the name in `tracker/`); the ledger node's repeated
  sentence is said once; the admission node's "five stand-ins" says six.
- **R5.15.5, the decision row P351:** the Mac kit's list names every file split out of a listed one (SPEC-mac R33's
  list widened by rule, not by hand). It cites SPEC-mac R33, R36, P312 and the phase 2-5 splits.

**Pin-move list:** `tests/test_pilot.py` 476-483, 799-811, 832-846; `pilot/mactest/PROMPT.md` 85 and its paragraph;
`pilot/mactest/RESULTS-TEMPLATE.md`; `pilot/SPEC-mac.md` R33; the curated nodes.

**Tests:** `test_reader_child`, `test_index`, `test_door`, `test_scaffold` (the docstrings of `door` and `scaffold`
change; their own files are short and run as the owners of a changed module), `test_pilot`, `test_backtest`,
`test_layers`, `test_single_source`, `test_repo_map`. Not `test_filer`: R5.15.1 changes only the filer's docstring
(section 3: a docstring edit in the filer's family runs no test of it; after.txt shows `git diff -U0` of
`tracker/filer.py` holding docstring lines only).

**Accept when:** each sentence of R5.15.1 is corrected and no other line of those files changes; R5.15.2's 30 runs;
`test_pilot` passes with the widened list and every named file exists.
- **Windows:** no label. **Office `-Tests`:** none. **Mac:** the next scheduled Mac check runs the widened list; no
  Mac run is owed by this job.

---

### P5.16 The moved names read from their home; `MOVED_OUT` rows

- **Cost:** M (the API's words alone are read about 380 times through `api` in tests; the retarget is mechanical).
- **Tier:** Sonnet. A grep-driven retarget with P4.13's guard.
- **Findings:** section 2.1's "No re-export facade" row.
- **Depends on:** P5.15.
- **Layer and domain:** no new module.

**Requirements:**

- **R5.16.1, the guard's rows.** `MOVED_OUT` (`tests/test_layers.py` 1245) gains, with a comment citing P340-P348 and
  this SPEC: `"api": ("screen_words", "request_edit", "household_edit", "creation", "firm_view")`, `"runner":
  ("run_log", "status_page", "pass_order")`, `"reminder": ("letter_render",)`. The guard's walk and its rule are
  unchanged: a moved name is one defined at the top level of a new home and not of the old module.
  `READ_THROUGH_ON_PURPOSE` stays empty.
- **R5.16.2, the retargets.** Every site the guard names at P5.15's head is retargeted to the name's home in the same
  commit: `api.<WORD>` to `screen_words.<WORD>` (importing `tracker.screen_words` as each file's style is), and the
  same for the other modules. A read that captures an original beside a stand-in reads the same object from its
  home; the `setattr` beside it is not touched. before.txt holds the guard's failing output at P5.15's head (it
  proves the rows bite), after.txt its pass.
- **R5.16.3, the string programs.** The guard does not read strings: grep `tests/` for `api\.`, `runner\.` and
  `reminder\.` inside string literals (the JavaScript harness's Python strings, `pilot/harness`), list each hit and
  retarget each moved name.
- **R5.16.4, what stays.** A read through an old module of a name it imports from a module this phase did not create
  (`api.load_manifest`, `runner.discover_engagements`) is not the guard's. `api.MISFITS_HEADING` is an alias of
  `status_page.STATUS_MISFITS_HEADING` (P5.9) and not a moved name; P5.9 already retargeted its test readers.
- **R5.16.5, the curated node** of `tests/test_layers.py` gains one sentence: the guard holds phase 5's moves too.

**Pin-move list:** `tests/test_layers.py` (`MOVED_OUT`); every test file the retarget edits; the curated node.

**Patch sites:** `report` for each old and new module is unchanged by this job (no `setattr` target changes);
`check` passes.

**Register:** not reached.

**Tests:** `test_layers`, every test file the job edits, each as its own process; `test_admission` (the pin is
unchanged); `test_single_source`, `test_repo_map`, `test_golden`.

**Stop and ask:** a read the guard names that cannot be retargeted without changing what the test proves; a reader
under `tracker/`, `tools/` or `pilot/` an earlier job missed (retarget it and say which job missed it).

**Accept when:** the guard fails at P5.15's head with exactly before.txt's sites and passes after; the collected
tests are the same before and after; `tests/golden/` and `ADMISSION_PIN[6]` unchanged; `runner.py` is under 3,000
lines (expected near 2,450: about 1,320 lines move out and about 80 import lines come back). `api.py`'s size is
**reported, not a gate**: P5.3-P5.7 move 2,072 lines of ranges plus the blank lines between them, and the
import-backs add about 300 (P5.3's alone are 258 names, one to a line in api's from-import style, api 315-326), so
api ends near 4,700-5,000 lines from 6,778. The plan's target after phase 7 is about 3,600 for any module; phase 7's
per-command context, which thins the handlers, is where api gets there.
- **Windows:** no label. **Office `-Tests`:** none.

---

## 5. Risks

- **A stand-in that silently stops reaching its code** (A-4). The sharpest cases in this phase are the stand-ins that
  forbid a read (test_api 10748-10752 and 11000): left on `api` after `_firm_row`, `read_index`, `load_manifest` and
  `households_named` gained readers in `firm_view`, they forbid nothing and their test still passes. R5.7.3 makes the
  job show each one bite on a scratch edit. The other nets: section 3's rule, section 4.0's tables, `patch_sites
  report` before and after, the hand-read string targets (three on the runner) and P5.16's sweep.
- **The scheduled pass's start** (P5.3). The frozen runner has no product name at import; a word module in its
  load closure would make every scheduled pass fail before it logs anything. R5.3.5's guard is the net in the suite;
  section 6's step 1 (a scheduled pass on the installed build) is the proof on the machine.
- **The API's import-back is long** (P5.3, about 258 names). It is ugly but exact: ruff fails an unused one, and an
  `F821` fails a missing one. A star import would hide both and is not used. It is also why `api.py` stays near
  4,700-5,000 lines after the phase (P5.16 reports the figure; it is not a gate).
- **Q-F's measurement holds only as far as `layout.short_paths()`.** On Linux and a long-path Windows the review
  folder adds nothing, so the difference shows only on the office's default Windows and on a Mac; the suite stands
  `short_paths` in to show it (R5.4.4's test).
- **Q-C is answered (A), keep the child (Jason, 2026-11-08).** The pass still starts `python -m tracker.api firm` for the cache (P201). Filling
  in-process would also need the draft-day rule below the runner (`firm_view` imports it from `runner`, and the runner
  importing `firm_view` back would be a cycle) and a timing check at the office; section 7 says so.
- **after_install's table** (P5.12). The risk is a line or a failure that the restructure says differently in one
  combination of outcomes. R5.12.1's case table (each job's outcomes and the crossings that change the output, under
  200 rows), committed first and unchanged, is the net; the
  office's installer step is the proof that Setup's last step still records what it did.
- **The family files and the gate** (P5.13, P5.14). Without P5.13, a family file would read as "exercised by" and an
  affected-tests run that picks a module's own files would skip it. P5.13 lands first, and R5.14.4 checks the map.
- **`_vocab`-era docs.** `pilot/SPEC-cleanup.md`, about twelve other SPECs, the audits, the handoffs and the decision
  log name `_vocab`; they are history and are not edited (section 3, R5.2.6). `pilot/wording-shell.tsv` is not
  history and is retargeted (R5.2.1, R5.3.11).

## 6. Owed to the office PC

Everything here runs on the office PC with the program's checkout or the installed build, never against a real
clients root's data from the suite; no generative AI reads a document. The phase does not reach the sorting engine,
so no backtest is owed by it.

**1. A scheduled pass on the installed build** (P5.3, P5.8-P5.10). On the stack's build, installed: run the
scheduled task once from Task Scheduler ("Run"). Pass: the task ends with result 0 or the pass's own exit code,
`last-pass.json` in the data home shows this run, the run log gained one line set, and `Status Report.html` was
rewritten. This proves the runner starts without the product's name and writes its log, last-pass file, page and
order hint from their new modules.

**2. The Overview after a pass** (P5.7). In the installed app, after step 1: the Overview opens at once with counts
(the cache the pass filled through `tracker.api firm`), and Look Again shows the same counts.

**3. Setup's last step** (P5.12). Install the build over the current one with the installer; the first launch shows
no "Setup Needs Attention" notice unless the machine has a finding it had before. `after-install.json` holds the same
keys as before the install (compare with a copy taken first).

**4. The Windows check of the stack.** Once, on the stack's head: `pilot\wintest\run_checks.ps1 -Tests` with the union
of the jobs' lists - `test_request_edit,test_household_edit,test_creation,test_run_log,test_status_page,test_pass_order,test_api,test_copies,test_households,test_locking,test_rollover,test_runner,test_errors,test_after_install,test_api_entry`
- with every `test_api_*` and `test_runner_*` family file P5.14 created added, plus `test_layers,test_single_source,test_repo_map`.
The script builds the installer beside the tests.

**5. Mac.** Nothing in phase 5 changes a Mac path: after_install's Mac branch (the kick, Time Machine) is restructured
but held by R5.12.1's table, which stands each in. The next scheduled Mac check runs the widened list (R5.15.3); no
Mac run is owed by this phase.

**Still owed from earlier phases** (they touch none of this phase's code and can run in the same visit): P3.8's
read-only `verify` against the office's records; phase 4's two backtests (on the build at `68b9212` and on the build
at `f15eed1`, which must agree), and P4.1, P4.4, P4.6, P4.9 and P4.12's lists and hands-on steps.

## 7. Questions for Jason

**Answered by Jason on 2026-11-08:** Q-C **(A)**, keep the separate copy (P5.7 builds it as written); Q-F **(C)**, one shared check, with the extra folder test used only when creating and rolling forward (P5.4 builds R5.4.4). The questions stay below as he was asked them.

**Q-C. When the scheduled pass refreshes the Overview's counts at its end, should it keep starting a separate copy of
the program to do it, or do it itself?**

Today the pass keeps the Overview's counts up to date by starting a second copy of the program at its end (decision
P201), only because the code that builds the counts sat where the pass was not allowed to reach. Phase 5 moves that
code down (P5.7), so the pass could now run it directly. Nothing a person sees differs either way when it works.
- **(A) Keep the separate copy (recommended for now; what phase 5 builds).** It has its own five-minute limit, so a
  slow Drive folder cannot hold the pass open, and nothing about it changes.
- **(B) Do it in the pass itself.** One process fewer and a little quicker. It needs one more job first: the
  draft-day rule (which day reminders are drafted) moves out of the pass's module, because the counts read it and
  the pass would otherwise import the counts while the counts import the pass. Then the office times a pass on the
  real folder, and if the refresh can stall the pass we come back to (A).

**Q-F. Should the request-list editor check that file names fit using the same shared check as creating a return?**

When a person saves the request list, the editor refuses a change whose file names would be too long for Windows. A
shared check does the same when a return is created or a household is rolled forward. That shared check's
description says the editor uses it too; it does not, it has its own. We measured whether swapping the editor onto
the shared check would change anything: it would. On the office's default Windows and on a Mac, if a return's
folder has grown longer since it was created (the clients folder moved deeper, or a household folder renamed longer),
the shared check would refuse every save of that return's list, even one that only changes a count. Phase 5 keeps the
editor as it is and corrects the description (option A) unless you choose otherwise before P5.4 is built.
- **(A) Keep the editor's own check and correct the description.** Nothing changes for anyone.
- **(B) Use the shared check as it is.** The editor would then refuse saves on such a return until someone shortens
  its folder names, even saves that touch no file name.
- **(C) One shared check, with the extra folder test used only when creating and rolling forward (recommended).**
  Every save comes out exactly as today, there is one check to maintain, and its description becomes true. A small
  change inside P5.4.

**Carried, not asked again:** Q-B (the re-send road's shortlist) stays open as P313 left it; nothing in phase 5
touches it.

**For a later phase (no answer needed now):** after phase 7, a package-wide decision on the private names one module
imports from another (measured then); this phase adds some, as phase 4 did, rather than renaming them mid-move.
